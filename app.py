#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
粤乡智匠 - 基于AI实训系统的农村本土人才赋能平台
Flask后端应用
"""

from flask import Flask, request, jsonify, send_from_directory, Response, stream_with_context
from flask_cors import CORS
from datetime import datetime
from dotenv import load_dotenv
import os
import re
import json
import math
import time
import base64
import logging
import threading
import database
# 病虫害速查与诊断共用的事实源。原先把 PEST_KNOWLEDGE 内联在本文件里，
# 现在抽到 pest_data.py，由「常见病虫害速查」与「诊断知识库降级」两条路径共用，
# 避免出现「速查更新了、诊断还停在旧内容」的双份数据。
from pest_data import (
    PEST_KNOWLEDGE,
    PEST_SOURCE_MAP,
    PEST_CROP_ORDER,
    iter_pest_entries,
    get_pest_stats,
)
# 公开招聘（招募）信息的事实源。与 cases_data.py / policies_data.py 同构：
# 「就业对接」板块里的**公开招聘公告**属策展内容，不落库、import 即用；
# 企业自行发布的岗位仍走 job_listings 表 + 内容审核，两者在
# /api/employment/jobs 里合并下发（前端按 source_type 区分展示）。
import jobs_data

# 加载环境变量（优先 .env 文件）
load_dotenv()

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 初始化Flask应用
app = Flask(__name__)

# ---- CORS：只放行本机来源 ----
# 本应用的所有页面（index.html / teacher.html / admin.html / 各门户页）都跟 API 同源，
# 同源请求根本用不到 CORS 头；跨域只可能出现在本地调试时（例如页面在 127.0.0.1
# 而 js/core.js 的默认 API 基址是 http://localhost:5000）。
# 此前是 CORS(app) —— 等于对**任意来源**开放。一旦填上 AI_API_KEY，任何站点都能借
# 用户浏览器直接调本站接口，把这里当成免费大模型代理刷额度（还可能顺带试出会话头）。
# 需要跨域部署（独立域名前端）时，用环境变量 CORS_ORIGINS 显式追加，逗号分隔。
_CORS_LOCAL_PATTERNS = [
    r'http://localhost(:\d+)?$',
    r'http://127\.0\.0\.1(:\d+)?$',
    r'http://\[::1\](:\d+)?$',
]
_CORS_EXTRA_ORIGINS = [o.strip() for o in os.getenv('CORS_ORIGINS', '').split(',') if o.strip()]
# 仅对 /api/* 下发 CORS 头：静态资源一律不参与跨域（默认拒绝）。
CORS(app, resources={r'/api/*': {
    'origins': _CORS_LOCAL_PATTERNS + _CORS_EXTRA_ORIGINS,
    'methods': ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
    'allow_headers': ['Content-Type', 'X-Session-Id'],
}})

# 应用配置
app.config.update(
    SECRET_KEY=os.getenv('SECRET_KEY', os.urandom(24).hex()),
    MAX_CONTENT_LENGTH=16 * 1024 * 1024,
    JSON_AS_ASCII=False
)


# ==================== 会话与权限助手 ====================
# ⚠️ 必须定义在**所有路由之前**：`@_require_role(...)` 是装饰器工厂，
#    在模块导入、装饰函数的那一刻就会被调用；定义在文件后半段会直接 NameError。
#    2026-10-07 之前 _require_role 一直被定义在 5600 行附近、**从未被任何路由使用**，
#    导致 /api/teacher/* 几乎全部裸奔（不带会话头也能读学员名册、改分数、删学员）。

def _get_session_user():
    """从请求头获取当前登录用户，未登录返回 None"""
    session_id = request.headers.get('X-Session-Id', '')
    if not session_id:
        return None
    session = database.get_session(session_id)
    if not session:
        return None
    user = database.get_user_by_id(session['user_id'])
    return user


def _require_role(*roles):
    """角色权限装饰器：检查当前用户是否拥有指定角色（未登录 401 / 角色不符 403 / 停用 403）"""
    from functools import wraps
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = _get_session_user()
            if not user:
                return jsonify({"success": False, "message": "请先登录"}), 401
            if user['role'] not in roles:
                return jsonify({"success": False, "message": "权限不足"}), 403
            if user.get('status') == 'suspended':
                return jsonify({"success": False, "message": "账号已被停用"}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator


# 教师端接口统一要求的角色（教师本人 + 超级管理员）
_TEACHER_ROLES = ('teacher', 'super_admin')


# AI服务配置
AI_API_URL = os.getenv('AI_API_URL', 'https://api.siliconflow.cn/v1/chat/completions')
AI_API_KEY = os.getenv('AI_API_KEY', '')
AI_MODEL = os.getenv('AI_MODEL', 'Qwen/Qwen3-32B')
# 视觉模型独立配置：AI_MODEL 是纯文本模型，本身不能看图。
# 单独用 AI_VL_MODEL，避免把问答/追问建议这类纯文本调用一并升级到视觉档（单次成本更高）。
# 需要关闭图片诊断时，把 AI_VL_MODEL 显式留空即可。
AI_VL_MODEL = os.getenv('AI_VL_MODEL', 'Qwen/Qwen3-VL-32B-Instruct')
# 问答/追问建议专用模型。与诊断模型分开配置，原因是两者能力面不同：
#   ① 流式体验：stepaudio-2.5-chat 实测首字 0.39~0.41s、全文 1.3s 出完；
#      step-3.7-flash 是推理模型，要先思考约 3.2s 才吐第一个正文字（总 3.6s）。
#   ② 它**只支持文本与音频**：传图片会 400「only support text and audio」，
#      且输出的诊断 JSON 键名会带空格（`{ " disease": ... }`），
#      会被 _parse_ai_diagnosis 判成「缺少病害名称」。
#   所以它只能承担问答/建议，**图片诊断（AI_VL_MODEL）与结构化诊断（AI_MODEL）
#   必须留在 step-3.7-flash**。想让问答回到同一个推理模型，把这里留空即可（空值 = 跟随 AI_MODEL）。
AI_CHAT_MODEL = os.getenv('AI_CHAT_MODEL', '').strip()
# 推理强度（推理模型专用，如 step-3.7-flash 支持 low/medium/high）。
# ⚠️ 推理模型的「思考」会占用 max_tokens 额度：实测不给这个参数时，一次
# 「按 JSON 返回诊断」的请求会思考 1400+ 字、把 1000 的额度吃光，正文一个字都吐不出来。
# 实测 7 种关闭思考的写法（enable_thinking / thinking.type=disabled / reasoning_effort=none|minimal /
# enable_reason / chat_template_kwargs）全部无效，所以只能：① 调低到 low（实测思考量减少约 35%）
# ② 把各处 max_tokens 留出思考余量。非推理模型会忽略这个参数。
AI_REASONING_EFFORT = os.getenv('AI_REASONING_EFFORT', '').strip()
# 推理模型的思考余量（token）。给每个 max_tokens 预算加这么多，保证「思考完还有正文」。
AI_REASONING_TOKEN_RESERVE = int(os.getenv('AI_REASONING_TOKEN_RESERVE', '600'))

# ---- 病虫害诊断：输入约束、图片上限与限流 ----
DIAG_SYMPTOMS_MAX_LEN = 500              # 症状描述最大字符数（与前端 maxlength 保持一致）
DIAG_RATE_LIMIT = int(os.getenv('DIAG_RATE_LIMIT', '60'))   # 每窗口内诊断请求上限
DIAG_MAX_IMAGES = 3                      # 单次最多上传图片数
DIAG_MAX_IMAGE_BYTES = 4 * 1024 * 1024   # 单张图片解码后字节上限（前端已压缩，通常远低于此）
DIAG_ALLOWED_IMAGE_TYPES = ('image/jpeg', 'image/png', 'image/webp')

# ---- 农业问答：输入约束与限流 ----
AGRI_QUESTION_MAX_LEN = 500          # 单条问题最大字符数（与前端 maxlength 保持一致）
AGRI_HISTORY_MAX_TURNS = 5           # 参与上下文的历史轮数上限
AGRI_HISTORY_MAX_CHARS = 4000        # 参与上下文的历史总字符上限
AGRI_RATE_WINDOW = 300               # 限流窗口（秒）
AGRI_RATE_ASK_LIMIT = int(os.getenv('AGRI_RATE_ASK_LIMIT', '60'))          # 每窗口内问答请求上限
AGRI_RATE_SUGGEST_LIMIT = int(os.getenv('AGRI_RATE_SUGGEST_LIMIT', '120'))  # 每窗口内建议请求上限

# ---- 方言语音问答：限流（缺陷 A7）----
# 该接口同样走 _chat_model()，在 AI_API_KEY 生效之前只是个隐患，现在是**可被白刷算力的入口**。
# 口径与农技问答对齐（同一个窗口、同为对话型调用），可用环境变量覆盖。
VOICE_RATE_LIMIT = int(os.getenv('VOICE_RATE_LIMIT', '60'))   # 每窗口内语音问答请求上限

# ---- AI 简历辅助：输入约束与限流（2026-10-06）----
# 与农技问答/方言助手同一口径：同一个限流窗口、可用环境变量覆盖。
# 定位是「抑制滥用」而非安全边界（内存态滑动窗口，重启即重置）。
RESUME_AI_SECTION_MAX_LEN = 2000      # 学员自填经历描述的单段上限
RESUME_AI_RATE_LIMIT = int(os.getenv('RESUME_AI_RATE_LIMIT', '30'))   # 每窗口内简历 AI 调用上限

# ---- 电商运营实训：输入约束、限流与宣传口径（2026-10-05 首轮终检 EC1–EC9）----
# 这 5 条路由此前**一条限流都没有**，而它们同样调用上游、且走的是推理模型
# （单次实测 9~12s），白刷成本远高于 voice。口径与农技问答对齐：同一个窗口、可用环境变量覆盖。
EC_RATE_SCRIPT_LIMIT = int(os.getenv('EC_RATE_SCRIPT_LIMIT', '30'))       # 带货话术生成
EC_RATE_FEEDBACK_LIMIT = int(os.getenv('EC_RATE_FEEDBACK_LIMIT', '30'))   # 话术评分
EC_RATE_COPY_LIMIT = int(os.getenv('EC_RATE_COPY_LIMIT', '30'))           # 商品文案
EC_RATE_CS_LIMIT = int(os.getenv('EC_RATE_CS_LIMIT', '120'))              # 客服对练（逐轮对话，放宽）
EC_RATE_CS_AUX_LIMIT = int(os.getenv('EC_RATE_CS_AUX_LIMIT', '40'))       # 客服辅助（开场白/提示），与对话拆开避免挤占额度
EC_SCRIPT_MAX_LEN = 3000     # 送去评分 / 入库的话术最大字符数
EC_LIVE_TRANSCRIPT_MAX_LEN = 4000   # 朗读识别文本最大字符数
EC_COPY_MAX_LEN = 4000             # 文案实训「我的稿」最大字符数（详情页文案普遍较长）
EC_CS_TRANSCRIPT_MAX_TURNS = 30    # 客服对练最多保存的轮数
EC_CS_TURN_MAX_LEN = 500           # 客服对练单条消息最大字符数
EC_RATE_COMMENTS_LIMIT = int(os.getenv('EC_RATE_COMMENTS_LIMIT', '30'))  # 观众提问（AI 题库化）

# 电商实训的**唯一**作物表（中文名）。前端作物卡与下拉展示的都是中文名，故这里用中文名做白名单。
EC_PRODUCTS = ('荔枝', '龙眼', '柑橘', '香蕉', '水产养殖', '水稻', '茶叶', '蔬菜')

EC_STYLE_KEYS = ('热情', '专业', '故事', '高级')
EC_COPY_FORMATS = ('详情页', '主图文案', '朋友圈', '小红书', '短视频脚本')

# 商品宣传口径（EC1）：与 A2「用药数值必须给出来源」同源 —— 说不出真实情况的具体承诺一律不给。
# 原提示词直接要求模型「引用权威认证：绿色食品、有机认证、地理标志」「用具体数据说话：
# 甜度、含水量、营养成分、检测指标」，模型无从得知这些，只能编造；学员照读即成虚假宣传。
_EC_PROMO_RULE = (
    "【宣传合规·必须遵守】\n"
    "1) 只描述该类农产品普遍成立的特征（口感、食用场景、产地气候的常识性描述）；\n"
    "2) 认证（绿色食品/有机/地理标志）、检测数据（甜度、果径、农残报告）、"
    "具体价格与规格、物流时效、赔付承诺 —— 一律**不要自行编造**，"
    "改为输出 `【待填写：……】` 占位，提示用户按自己产品的真实情况填入；\n"
    "3) 不使用「全网最低」「第一」「最好」「绝对」等绝对化用语；\n"
    "4) 不虚构原价、划线价或优惠力度。\n"
)


def _ec_product_ok(product):
    """校验电商实训的作物名（中文）。空值视为未选择，由调用方决定是否回退默认值。"""
    return str(product or '').strip() in EC_PRODUCTS

# 下发前端的文案不暴露部署细节（匿名访客同样能看到这条消息）；
# 具体排查指引只写进服务端日志。
AI_NOT_CONFIGURED_MSG = (
    'AI 农技问答尚未启用，请联系平台管理员。'
    '如需即时帮助，可咨询当地农技站或拨打 12316 三农服务热线。'
)
AI_NOT_CONFIGURED_LOG = 'AI_API_KEY 未配置：请在项目根目录 .env 中填入有效密钥后重启服务'
AI_UNAVAILABLE_MSG = (
    'AI 服务暂时不可用，请稍后重试。'
    '如需即时帮助，可咨询当地农技站或拨打 12316 三农服务热线。'
)
# 图片诊断不可用时的对外文案：与上面一样不含部署细节，只告诉用户「现在能做什么」。
AI_VISION_NOT_CONFIGURED_MSG = (
    'AI 服务尚未启用，暂时无法进行图片诊断。'
    '你可以改用文字描述症状，或联系平台管理员；如需即时帮助可拨打 12316 三农服务热线。'
)
AI_VISION_UNAVAILABLE_MSG = (
    '图片诊断功能暂未开放。'
    '你可以改用文字描述症状，或联系平台管理员；如需即时帮助可拨打 12316 三农服务热线。'
)
AI_VISION_NOT_CONFIGURED_LOG = 'AI_VL_MODEL 未配置：请在项目根目录 .env 中填入支持图片输入的模型名后重启服务'

# ---- 诊断结论来源标注 ----
# 诊断接口有两条产出路径（AI 模型 / 内置知识库关键词匹配），此前两者返回
# 完全相同的 success:True 且无任何来源标记，用户无法分辨结论可信度。
DIAG_SOURCE_AI = 'ai'
DIAG_SOURCE_KB = 'knowledge_base'
DIAG_SOURCE_META = {
    DIAG_SOURCE_AI: {
        'label': 'AI 模型生成',
        'note': '结论由 AI 模型依据症状描述生成，可能存在偏差，仅供参考，请以当地农技站指导为准。',
    },
    DIAG_SOURCE_KB: {
        'label': '本地知识库匹配',
        'note': 'AI 服务当前不可用，本条结论由平台内置知识库按关键词匹配得出，'
                '未必与你描述的症状完全对应，仅供参考，请以当地农技站指导为准。',
    },
}


def _tag_diagnosis_source(diagnosis, source):
    """给诊断结论打上来源标记，供前端展示角标与免责说明。"""
    meta = DIAG_SOURCE_META.get(source) or DIAG_SOURCE_META[DIAG_SOURCE_KB]
    diagnosis['source'] = source if source in DIAG_SOURCE_META else DIAG_SOURCE_KB
    diagnosis['source_label'] = meta['label']
    diagnosis['source_note'] = meta['note']
    return diagnosis


def _ai_configured():
    """是否已配置可用的 AI 密钥。空密钥时上游必然返回 401，提前短路可避免无谓等待。"""
    return bool((AI_API_KEY or '').strip())


def _ai_vision_configured():
    """是否具备图片诊断能力：既要有密钥，也要配置了支持图片输入的模型。"""
    return _ai_configured() and bool((AI_VL_MODEL or '').strip())


def _chat_model():
    """问答 / 追问建议 / 方言语音问答使用的模型。

    未单独配置 AI_CHAT_MODEL 时跟随默认文本模型 AI_MODEL，行为与只有
    AI_MODEL/AI_VL_MODEL 两个配置时完全一致。诊断路径不走这里（见 AI_CHAT_MODEL 注释）。
    """
    return (AI_CHAT_MODEL or AI_MODEL)


_rate_lock = threading.Lock()
_rate_buckets = {}


def _rate_limited(key, limit, window=AGRI_RATE_WINDOW):
    """按客户端标识做滑动窗口限流，返回 True 表示本次请求应被拒绝。

    仅用于保护会消耗算力的 AI 类接口，限额取得较宽（默认 5 分钟 60 次），
    正常提问不会触发。说明：这是内存态限流，多进程/重启后会重置，
    定位是「抑制滥用」而非安全边界。
    """
    now = time.time()
    cutoff = now - window
    with _rate_lock:
        bucket = _rate_buckets.get(key)
        if bucket is None:
            bucket = _rate_buckets[key] = []
        while bucket and bucket[0] < cutoff:
            bucket.pop(0)
        if len(bucket) >= limit:
            return True
        bucket.append(now)
        # 顺带回收过期桶，避免字典随 IP 数无限增长
        if len(_rate_buckets) > 2048:
            for k in [k for k, v in _rate_buckets.items() if not v or v[-1] < cutoff]:
                _rate_buckets.pop(k, None)
        return False


# X-Forwarded-For 是请求头，客户端想写什么就写什么。此前限流键优先取它，
# 等于「换个头就换一个桶」—— 限流形同虚设，填了 AI_API_KEY 之后可被无限刷。
# 默认只信任对端地址（不可伪造）；只有确实部署在可信反代之后（并由反代覆写 XFF）
# 才用 TRUST_PROXY=1 显式开启。
TRUST_PROXY = os.getenv('TRUST_PROXY', '').strip().lower() in ('1', 'true', 'yes', 'on')


def _client_key():
    """限流键。默认取对端地址；仅在显式信任反代时才采信 X-Forwarded-For 的最左值。"""
    if TRUST_PROXY:
        forwarded = (request.headers.get('X-Forwarded-For') or '').split(',')[0].strip()
        if forwarded:
            return forwarded
    return request.remote_addr or 'unknown'


# 作物 id → 中文名的内置兜底表。
# 历史缺陷：专家身份此前只从 AGRICULTURE_KNOWLEDGE 取名，而该字典仅覆盖
# 荔枝/龙眼/水产养殖 3 个作物，导致选水稻/茶叶/蔬菜提问时 system_prompt
# 静默退化为「专注于广东特色农产品领域」，专家身份实际失效。
_AGRI_PRODUCT_NAME_FALLBACK = {
    'lychee': '荔枝',
    'longan': '龙眼',
    # v3 新增（A3）：柑橘、香蕉此前只存在于诊断库与速查，问答取不到名字会退化为
    # 「广东特色农产品」，专家身份实际失效。此处补齐，与 farming_data.FARMING_PRODUCTS 一致。
    'citrus': '柑橘',
    'banana': '香蕉',
    'aquatic': '水产养殖',
    'rice': '水稻',
    'tea': '茶叶',
    'vegetable': '蔬菜',
}

_agri_name_cache = {}

# 问答接口接受的作物集合（缺陷 A5）。
# 直接取内置名表：这张表是问答路径上「能不能给模型一个真实作物名」的最后一道底线 ——
# 取不到名字就会退化成「广东特色农产品」，生成的 system_prompt 丢掉作物针对性。
# 此前 /api/agriculture/ask 对任意 product 都返回 200 并静默退化，属「能力虚化」。
#
# ⚠️ 这张表必须与下面几处保持同一套 8 个作物（本项目历史上就吃过「三套口径」的亏）：
#   · farming_data.FARMING_PRODUCTS（农时日历，DB 播种）  · index.html 的顶部 .product-card
#   · script.js 的 getProductName()                        · pest_data.PEST_CROP_ORDER（诊断/速查）
_AGRI_SUPPORTED_PRODUCTS = frozenset(_AGRI_PRODUCT_NAME_FALLBACK)
_agri_name_cache_lock = threading.Lock()


def _agriculture_product_name(product):
    """取作物的中文名，用于拼装 AI 专家身份与提示文案。

    取值顺序：farming_products 目录（可随种子数据扩充）→ AGRICULTURE_KNOWLEDGE
    → 内置兜底表。三级回退确保任何已知作物都能拿到准确名称。
    """
    if not product:
        return '广东特色农产品'

    cached = _agri_name_cache.get(product)
    if cached:
        return cached

    name = ''
    try:
        row = database.get_farming_product(product)
        if row and row.get('name'):
            name = str(row['name']).strip()
    except Exception as e:
        logger.debug('读取农产品名称失败(%s)，改用内置表: %s', product, e)

    if not name:
        name = str((AGRICULTURE_KNOWLEDGE.get(product) or {}).get('name') or '').strip()
    if not name:
        name = _AGRI_PRODUCT_NAME_FALLBACK.get(product, '')

    if name:
        with _agri_name_cache_lock:
            _agri_name_cache[product] = name
    return name or '广东特色农产品'


def _agri_system_prompt(product):
    product_name = _agriculture_product_name(product)
    return (
        f"你是粤乡智匠平台的专业农业技术专家，专注于{product_name}领域。"
        f"回答要求：1)简洁实用，分点列出；2)结合广东本地气候和种植条件；"
        f"3)涉及农药、兽药时：可以给出药剂名称与防治思路；"
        f"若给出具体用量、稀释倍数或安全间隔期，必须同时写明该数值的出处"
        f"（例如某产品的标签、当地农业农村部门的技术指导、某个具体标准），"
        f"并且只能引用你确实掌握出处的数值；"
        f"凡拿不准出处的，一律不给数字，只给药剂名称与施用方法，并提示用户以所购产品标签为准；"
        f"严禁凭印象编造用量、倍数、间隔期，也不要给出自己说不出出处的具体数值；"
        f"4)适当用通俗易懂的语言。回答控制在300字以内。"
    )


# ---- 用药数值：模型可以给，但必须能说出出处；服务端再强制补一条免责声明 ----
#
# 背景（缺陷 A2）：本站「常见病虫害速查」严守「来源没给就写未提供、不作推算」，
# 而 AI 问答/诊断的自由文本里会出现「1500倍液」「间隔7天」这类看起来专业的数字 ——
# 这些数字由模型生成、无任何可核来源，与本站「不展示不存在的量化保证」的红线冲突。
# 口径选定为「保留数字但标注来源」，因此分两层落地：
#   ① 提示词要求模型给出处、拿不准就不给数字（见上方 _agri_system_prompt 与 _CHEM_DOSE_RULE）；
#   ② 服务端检测正文里出现用药数值时，强制在答案末尾补一条免责声明。
#      —— 不依赖模型自觉：模型漏了，服务端补上。这是「强制」二字的落点。
_CHEM_DOSE_NOTICE = (
    "⚠️ 以上用量、稀释倍数与安全间隔期由 AI 生成，本站未逐条核对出处，"
    "请以所购农药（兽药）标签标注与当地农业农村部门的指导为准；涉及食品安全，务必按标签执行。"
)
_CHEM_DOSE_NOTICE_BLOCK = "\n\n——\n" + _CHEM_DOSE_NOTICE

# 命中任一条即认为正文出现了「用药数值」，需要补免责声明。
# ⚠️ 宁可多补一句声明，也不要漏 —— 漏了就等于「保留数字但无提示」，
#    与「不展示不存在的量化保证」的红线直接冲突。因此最后一条做得较宽。
_CHEM_DOSE_PATTERNS = (
    # 30-40克/亩、80毫升/亩、0.5公斤/株
    re.compile(r'\d+\s*[-~～至]?\s*\d*\s*(?:克|千克|公斤|市斤|斤|毫升|升|g|kg|ml|L)\s*/?\s*(?:亩|株|桶|公顷)'),
    # 兑水60公斤 / 兑水 60 公斤
    re.compile(r'兑水\s*\d+'),
    # 1000倍液、1500 倍液
    re.compile(r'\d{2,}\s*倍液'),
    # 稀释1000倍
    re.compile(r'稀释\s*\d+'),
    # 安全间隔期（无论后面带不带数字都要提示）
    re.compile(r'安全间隔期'),
    # 间隔7天、等待 7 天、停药7-10天、采收前 15 天
    re.compile(r'(?:间隔|等待|停药|采收前)\s*\d+\s*[-~～至]?\s*\d*\s*天'),
    # 兜底：任意「数值 + 质量/体积/浓度单位」。覆盖「每亩用75%可湿性粉剂30-40克」
    # 「每株施复合肥0.5-1公斤」「3-5波美度」这类单位不在数字紧邻位置的写法。
    re.compile(r'\d+(?:\.\d+)?\s*(?:[-~～至]\s*\d+(?:\.\d+)?\s*)?'
               r'(?:克|千克|公斤|市斤|斤|毫升|升|ppm|波美度|g|kg|ml|L)',
               re.IGNORECASE),
    # ⚠️ 中文数字写法 —— 上面全是阿拉伯数字，会**整条漏掉**中文数字写法。
    #    实测：方言话术库里「每棵大树施二十到三十斤」导致 hakka / teochew 的施肥话术
    #    100% 命中不了免责声明，而 cantonese 用「20-30斤」就命中了 ——
    #    同一平台同类内容，只因数字写法不同就一个提示一个不提示，属口径不一致。
    #    AI 自由文本同样可能写中文数字，故在此补齐（宁可多补一句声明，也不要漏）。
    re.compile(r'[零一二三四五六七八九十百两]+'
               r'(?:\s*[-~～至到]\s*[零一二三四五六七八九十百两]+)?'
               r'\s*(?:斤|公斤|千克|克|市斤|毫升|升|亩|株|桶|倍)'),
    # 中文小数浓度：零八点三写法里的「零点三（个）」、葉面喷零点三个磷酸二氢钾
    re.compile(r'[零一二三四五六七八九十]+点[零一二三四五六七八九十]+'),
    # 施药间隔的中文 / 「日」写法：每隔7-10日、隔七八日、隔两三回
    # （原模式只认「间隔…天」，而话术库普遍写「隔…日」，同样整条漏掉）
    re.compile(r'(?:每隔|隔|间隔|等待|停药|采收前)\s*'
               r'[0-9零一二三四五六七八九十两]+'
               r'(?:\s*[-~～至到]\s*[0-9零一二三四五六七八九十两]+)?\s*[日天回次]'),
)


def _has_chem_dosage(text):
    """正文里是否出现了用量 / 稀释倍数 / 安全间隔期这类「用药数值」。

    只做触发判断，不解析数值本身 —— 目的仅是决定要不要补免责声明。
    """
    s = str(text or '')
    if not s:
        return False
    return any(p.search(s) for p in _CHEM_DOSE_PATTERNS)


def _chem_dose_notice_for(text):
    """正文命中用药数值时返回免责声明文本，否则返回空串。

    ⚠️ 为什么单独下发一个字段、而不是像农技问答那样拼进答案正文：
    方言助手是**多轮**的，前端会把历史里的 assistant 内容回传给模型。
    声明拼进正文会被当成「模型自己的话」进入下一轮上下文，声明越滚越多，
    并且挤占 max_tokens。故这里以独立字段下发，由前端单独渲染。

    为什么需要它：此前只有农技问答（非流式 1306 / SSE 1400）和病虫害诊断（3289）
    接了用药免责声明，**方言语音助手漏了** —— 而它的本地话术库里恰恰写着
    「用多菌灵、甲基托布津，每隔7-10日喷一次，连喷2-3次」「每棵大树施20-30斤」
    这类具体用量，等于同一个平台三处出口两处免责、一处免责缺失。
    """
    return _CHEM_DOSE_NOTICE if _has_chem_dosage(text) else ''


def _parse_agri_request():
    """解析并校验问答请求。返回 (payload, error_response)，error_response 非空即需直接返回。"""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return None, (jsonify({
            "success": False, "code": "bad_request",
            "message": "请求格式不正确，应为 JSON 对象"
        }), 400)

    question = str(data.get('question', '') or '').strip()
    if not question:
        return None, (jsonify({
            "success": False, "code": "empty_question",
            "message": "请输入问题"
        }), 400)
    if len(question) > AGRI_QUESTION_MAX_LEN:
        return None, (jsonify({
            "success": False, "code": "question_too_long",
            "message": f"问题过长，请控制在 {AGRI_QUESTION_MAX_LEN} 字以内"
        }), 400)

    history = data.get('history', [])
    if not isinstance(history, list):
        history = []

    # A5：未知 product 明确拒绝，不再退化成一个跟作物无关的泛泛回答。
    # 缺省（未传/空串）与诊断接口保持一致的宽容度：按荔枝处理，避免生成无作物针对性的提示词。
    product = str(data.get('product', '') or '').strip() or 'lychee'
    if product not in _AGRI_SUPPORTED_PRODUCTS:
        return None, (jsonify({
            "success": False, "code": "unknown_product",
            "message": "暂不支持该农产品，请从列表中选择"
        }), 400)

    return {
        "question": question,
        "product": product,
        "history": history,
    }, None


def _build_agri_messages(system_prompt, history, question):
    """按「轮数 + 字符数」双重上限拼装上下文，避免历史本身撑爆上下文窗口。"""
    messages = [{"role": "system", "content": system_prompt}]
    picked = []
    used = 0
    for item in reversed(history[-AGRI_HISTORY_MAX_TURNS:]):
        if not isinstance(item, dict):
            continue
        q = str(item.get('question', '') or '').strip()
        a = str(item.get('answer', '') or '').strip()
        if not q or not a:
            continue
        cost = len(q) + len(a)
        if used + cost > AGRI_HISTORY_MAX_CHARS:
            break
        used += cost
        picked.append((q, a))
    for q, a in reversed(picked):
        messages.append({"role": "user", "content": q})
        messages.append({"role": "assistant", "content": a})
    messages.append({"role": "user", "content": question})
    return messages


def _chat_completion(messages, temperature=0.3, max_tokens=800, timeout=30, model=None):
    """单次调用上游 Chat Completions，返回正文文本；任何异常/结构异常均抛出。

    model 为空时使用默认文本模型 AI_MODEL；多模态调用传入 AI_VL_MODEL。
    """
    import requests
    payload = {
        "model": (model or AI_MODEL),
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens
    }
    # 推理模型专用；非推理模型会忽略。留空则用上游默认（思考量更大、更慢）。
    if AI_REASONING_EFFORT:
        payload["reasoning_effort"] = AI_REASONING_EFFORT
    resp = requests.post(
        AI_API_URL,
        headers={
            "Authorization": f"Bearer {AI_API_KEY}",
            "Content-Type": "application/json"
        },
        json=payload,
        timeout=timeout
    )
    resp.raise_for_status()
    data = resp.json()
    choices = data.get('choices') if isinstance(data, dict) else None
    if not choices:
        raise ValueError('上游响应缺少 choices 字段')
    choice = choices[0] if isinstance(choices[0], dict) else {}
    message = choice.get('message') if isinstance(choice.get('message'), dict) else {}
    content = message.get('content')
    if not content or not str(content).strip():
        # 推理模型（如 step-3.7-flash）会把 max_tokens 额度先花在思考上，额度不够时正文为空。
        # 必须把「额度不够」与「上游真挂了」区分开，否则只会看到一句笼统的「服务不可用」。
        reason = str(message.get('reasoning_content') or message.get('reasoning') or '')
        if choice.get('finish_reason') == 'length' or reason:
            raise ValueError(
                '上游输出被 max_tokens 截断：思考已消耗约 %d 字，正文为空（请调大 max_tokens）' % len(reason))
        raise ValueError('上游响应内容为空')
    return str(content).strip()


# 农业知识库
AGRICULTURE_KNOWLEDGE = {
    "lychee": {
        "name": "荔枝",
        "seasons": {
            "spring": {
                "tasks": ["促花肥施用", "病虫害预防", "修剪整形"],
                "tips": "春季是荔枝开花关键期，注意防治霜疫霉病"
            },
            "summer": {
                "tasks": ["果实采收", "采后修剪", "恢复肥施用"],
                "tips": "及时采收成熟果实，采后及时补充营养"
            },
            "autumn": {
                "tasks": ["秋梢管理", "病虫害防治", "水分管理"],
                "tips": "培养健壮秋梢，为来年结果打基础"
            },
            "winter": {
                "tasks": ["冬季清园", "树干涂白", "深翻改土"],
                "tips": "做好防寒措施，减少越冬病虫源"
            }
        },
        "diseases": [
            {"name": "霜疫霉病", "symptoms": "果实表面出现褐色病斑", "treatment": "喷施甲霜灵·锰锌"},
            {"name": "炭疽病", "symptoms": "叶片出现圆形病斑", "treatment": "喷施咪鲜胺"},
            {"name": "蒂蛀虫", "symptoms": "果实被蛀食", "treatment": "喷施高效氯氰菊酯"}
        ]
    },
    "longan": {
        "name": "龙眼",
        "seasons": {
            "spring": {"tasks": ["促花肥", "疏花"], "tips": "控制花量，提高坐果率"},
            "summer": {"tasks": ["壮果肥", "水分管理"], "tips": "保持土壤湿润"},
            "autumn": {"tasks": ["采收", "采后管理"], "tips": "适时采收"},
            "winter": {"tasks": ["冬季修剪", "清园"], "tips": "做好防寒"}
        }
    },
    "aquatic": {
        "name": "水产养殖",
        "basics": [
            "水质管理是关键",
            "合理投喂饲料",
            "定期消毒防病",
            "保持溶氧充足"
        ]
    }
}

# 手工艺知识
CRAFTS_KNOWLEDGE = {
    "embroidery": {
        "name": "广绣",
        "origin": "广州",
        "history": "国家级非物质文化遗产，起源于唐代，与苏绣、湘绣、蜀绣并称中国四大名绣。广绣以构图饱满、色彩艳丽、针法多变著称，尤以金银线绣最为独特。",
        "steps": [
            {
                "title": "准备工具与材料",
                "desc": "准备绣架、绣针（12号-7号）、真丝绣线（建议从12色基础色开始）、丝绸绣布（19姆米素绉缎）、剪刀、水消笔、复写纸。",
                "tips": "初学者建议选白色或浅色绣布，便于看清针脚；绣线不要剪太长，50cm左右为宜，过长容易打结。"
            },
            {
                "title": "图案设计与转印",
                "desc": "在纸上绘制或打印图案，用复写纸转印到绣布上。也可用水消笔直接在绣布上绘制。初学者建议从简单的花卉、水果图案开始。",
                "tips": "转印时力度要轻，避免划伤绣布；水消笔画错可用湿布擦掉重画。"
            },
            {
                "title": "上绷与固定",
                "desc": "将绣布平整地固定在绣绷上，调整松紧度。绣布要绷紧但不能变形，以手指轻弹有弹性为宜。",
                "tips": "每隔10分钟检查一次绷紧度，绣制过程中绣布可能会松弛。"
            },
            {
                "title": "基础针法练习",
                "desc": "掌握直针（最基础，用于轮廓）、扭针（用于花瓣叶片）、长短针（用于渐变色彩）、打籽针（用于花蕊点缀）。每种针法先在废布上练习20分钟。",
                "tips": "针距保持均匀，一般2-3mm；起针收针都要在背面打结，正面不能露线头。"
            },
            {
                "title": "配色与绣制",
                "desc": "根据图案选择绣线颜色，广绣讲究'花无正色'，常用渐变色表现立体感。从深色到浅色逐层绣制，先绣主体再绣背景。",
                "tips": "配色时准备色卡对比；同一区域用3-5个渐变色会更自然；丝线有正反面，光泽面朝外。"
            },
            {
                "title": "收尾与装裱",
                "desc": "绣完后剪去多余线头，从绣绷上取下，用蒸汽熨斗低温熨平背面。然后选择合适的画框或屏风进行装裱。",
                "tips": "熨烫时绣面朝下，垫一块薄布；装裱前确保绣品完全干燥，避免发霉。"
            }
        ],
        "purchase_guide": {
            "budget": {"starter": "约130-320元", "advanced": "约500-1000元"},
            "buying_tips": "买齐必买5样（合计300元内）就能完成第一幅作品；绣线颜色宁多勿少——渐变配色是广绣的灵魂；先小成本试水，熟练后再添置绣架和金银线材料。",
            "categories": [
                {
                    "key": "essential", "label": "必买基础工具", "desc": "完成第一幅作品缺一不可，建议一次性买齐",
                    "items": [
                        {"name": "实木绣绷（30cm）", "price": "35-80元", "spec": "选榉木材质、带双层固定螺丝；圆形最适合新手", "where": "淘宝搜'广绣绣绷 榉木'，或本地文体用品店", "tip": "20cm只够练针法，30cm绣整幅图案刚好；超过40cm手够不着中心，新手别买"},
                        {"name": "广绣专用针套装（12支）", "price": "15-35元", "spec": "不锈钢材质，含12号-7号各2支；细针绣细节、粗针铺底", "where": "淘宝搜'广绣针 12支装'", "tip": "过针要顺滑不拉丝，生锈或带毛刺的针会刮伤丝线"},
                        {"name": "真丝绣线（12色基础装）", "price": "45-120元", "spec": "认准100%蚕丝、150D粗细，每色8米", "where": "淘宝搜'蚕丝绣线 12色'，广州/苏州产地优先", "tip": "用打火机烧一小段鉴别：结硬块的是化纤线，光泽和色牢度差很远"},
                        {"name": "素绉缎绣布（19姆米）", "price": "25-60元", "spec": "19姆米厚薄适中，白色最百搭；先买0.5米够绣2-3幅小品", "where": "淘宝搜'真丝绣布 素绉缎 19姆米'", "tip": "姆米数越大布越厚实；新手避开乔其纱（太滑难控制针脚）"},
                        {"name": "水消笔 + 复写纸", "price": "10-20元", "spec": "水消笔选蓝色（白布上最清晰），复写纸选灰色", "where": "文具店或淘宝均有", "tip": "水消笔遇水痕迹即消、画错好改；千万别用圆珠笔，洗不掉"}
                    ]
                },
                {
                    "key": "consumable", "label": "常用耗材", "desc": "持续消耗品，用完再补，单次花费不大",
                    "items": [
                        {"name": "绣线单色补充装", "price": "3-8元/支", "spec": "大红、胭脂、翠绿、藏蓝等主色消耗最快", "where": "与基础装同店补货", "tip": "同批同色号一次多买1-2支，不同批次有色差"},
                        {"name": "绣绷包边胶带", "price": "5-10元", "spec": "宽2cm左右的布基胶带", "where": "淘宝搜'绣绷包边带'", "tip": "包住绣绷外圈，防止绣布抽丝起毛"},
                        {"name": "大头针 + 线蜡", "price": "10-15元", "spec": "不锈钢大头针一盒、线蜡一块", "where": "淘宝或缝纫用品店", "tip": "绣线过蜡可减少打结，长线绣制必备"}
                    ]
                },
                {
                    "key": "advanced", "label": "进阶选配", "desc": "先用家里现有物品代替，练熟基础针法后再考虑",
                    "items": [
                        {"name": "台式可调绣架", "price": "80-200元", "spec": "可调节高度和角度，绣大件解放双手", "where": "淘宝搜'刺绣台式绣架'", "tip": "只绣小品用不上，想绣衣片、大幅作品时再买"},
                        {"name": "金银线绣材料包", "price": "60-150元", "spec": "含金银绒线、垫棉、钉线针——广绣最具特色的技法", "where": "淘宝搜'广绣金银线材料包'", "tip": "金银线绣对手上功夫要求高，建议绣完2-3幅普通作品后再尝试"},
                        {"name": "装裱画框 / 小屏风", "price": "50-300元", "spec": "按成品尺寸选购，画框留出3-5cm衬边", "where": "画材店或淘宝定制", "tip": "作品完全干透再装裱，否则易发霉变形"}
                    ]
                }
            ]
        }
    },
    "woodcarving": {
        "name": "潮汕木雕",
        "origin": "潮汕",
        "history": "国家级非物质文化遗产，始于唐代，盛于明清。以多层镂通雕刻技法闻名，作品玲珑剔透、层次分明，常用于建筑装饰、家具和祭祀器具。潮汕金漆木雕与东阳木雕、黄杨木雕、龙眼木雕并称中国四大木雕。",
        "steps": [
            {
                "title": "选材与备料",
                "desc": "常用木材有樟木（防虫）、椴木（易雕刻）、红木（高档作品）。选材要求木纹细腻、无裂纹、无虫蛀。原木需自然干燥3-6个月，含水率控制在12%以下。",
                "tips": "初学者建议用椴木练习，价格便宜且质地均匀；樟木有特殊气味，需在通风处操作。"
            },
            {
                "title": "画样与放稿",
                "desc": "在纸上绘制1:1图稿，传统题材有花鸟鱼虫、戏曲人物、祥瑞图案。用复写纸将图稿转印到木料上，或用铅笔直接绘制。",
                "tips": "图稿线条要清晰，标注好哪些部分需要镂空、哪些保留；初学者避免选择过于复杂的图案。"
            },
            {
                "title": "开粗坯",
                "desc": "用大号平刀和圆刀去除多余木料，雕刻出大体轮廓。先从最高层开始，逐层向下推进。注意留出精雕余量，一般多留1-2mm。",
                "tips": "刀具要保持锋利，钝刀容易崩木；用力要均匀，顺着木纹方向雕刻；大块废料可用木槌敲击刀背去除。"
            },
            {
                "title": "精雕细刻",
                "desc": "用小号雕刻刀精修细节，如羽毛纹理、花瓣脉络、人物五官。多层镂通作品需要逐层打通，注意层与层之间的连接强度。",
                "tips": "精雕时坐姿要正，手肘撑在桌面上保持稳定；镂空部分从中间向两边雕，避免边缘崩裂。"
            },
            {
                "title": "打磨与修光",
                "desc": "用砂纸从180目逐级打磨到600目，使表面光滑。凹陷处可用砂纸卷成小棒打磨。最后用棉布擦拭干净。",
                "tips": "打磨方向要顺着木纹；每次换更细砂纸前要清除上一级的木屑；600目以上可用木蜡油抛光。"
            },
            {
                "title": "上漆与装饰",
                "desc": "传统潮汕木雕常用金漆装饰：先涂生漆底漆，干燥后贴金箔或涂金粉。也可选择清漆保持原木色，或用木蜡油保养。",
                "tips": "生漆会引起过敏，操作时必须戴手套和口罩；金箔很薄，操作时不能有风。"
            }
        ],
        "purchase_guide": {
            "budget": {"starter": "约150-330元", "advanced": "约600-1500元"},
            "buying_tips": "刀具是一分钱一分货，建议把一半预算花在刀上；先在椴木废料上练推刀手感，稳了再上正式作品；电动工具新手阶段完全不需要。",
            "categories": [
                {
                    "key": "essential", "label": "必买基础工具", "desc": "第一件木雕作品的核心工具，宁可刀具买好一点",
                    "items": [
                        {"name": "木雕刀具套装（12件）", "price": "80-200元", "spec": "认准SK5或T8钢，含平刀、圆刀、三角刀、斜刀；最好附带磨刀石", "where": "淘宝搜'木雕刀套装 SK5'", "tip": "30元以下的'合金刀'多是冲压铁皮，卷刃后无法磨复——这是最大坑点"},
                        {"name": "椴木方料（20×10×5cm）", "price": "20-40元", "spec": "选无裂纹、木纹通直的；一次买2-3块练手", "where": "淘宝搜'椴木方料 雕刻'或本地木材店", "tip": "椴木软硬适中最适合练习；樟木防虫但有刺激性气味，需在通风处操作"},
                        {"name": "木槌", "price": "15-30元", "spec": "黄杨木或榉木材质，重量150-250g", "where": "五金店或淘宝", "tip": "千万别用铁锤代替——震手且容易敲裂刀柄"},
                        {"name": "砂纸套装（180-600目）", "price": "10-25元", "spec": "180/240/400/600目各买2-3张", "where": "五金店", "tip": "打磨必须逐级进行不能跳级，否则深划痕磨不掉"},
                        {"name": "防割手套 + 防滑垫", "price": "15-30元", "spec": "5级防割性能手套，防滑垫略大于木料", "where": "劳保店或淘宝", "tip": "左手扶料必须戴手套；木料下垫防滑垫，进刀时才不会打滑"}
                    ]
                },
                {
                    "key": "consumable", "label": "常用耗材", "desc": "边雕边耗的物品，定期补充即可",
                    "items": [
                        {"name": "砂纸（持续消耗）", "price": "10-25元/批", "spec": "主力消耗180-400目", "where": "五金店批量购买更划算", "tip": "粗磨产生的木屑会堵住砂纸，可用旧牙刷清理延长寿命"},
                        {"name": "硬质木蜡油", "price": "25-50元", "spec": "选食品级更安全，无色透明", "where": "淘宝搜'硬质木蜡油'", "tip": "小罐装足够用很久；上蜡前务必打磨到600目以上"},
                        {"name": "复写纸 + 铅笔（HB/2B）", "price": "5-10元", "spec": "普通文具即可", "where": "文具店", "tip": "图稿转印用灰色复写纸，黑色痕迹太重难擦"}
                    ]
                },
                {
                    "key": "advanced", "label": "进阶选配", "desc": "传统金漆、电动工具等，有稳定作品产出后再添置",
                    "items": [
                        {"name": "金漆装饰材料（生漆+金箔）", "price": "100-300元", "spec": "生漆底漆+贴金箔，潮汕金漆木雕的灵魂", "where": "淘宝搜'生漆 金箔 木雕'", "tip": "生漆会引发严重过敏，必须戴手套口罩操作；金箔怕风，操作时关窗"},
                        {"name": "电动雕刻笔（电磨）", "price": "150-400元", "spec": "功率40W以上，配尖头/圆头磨头套装", "where": "淘宝搜'电磨机 雕刻'", "tip": "新手手不稳容易打滑伤料，建议手工刀用熟半年后再入手"},
                        {"name": "樟木原木/大尺寸木料", "price": "50-200元", "spec": "做摆件、笔筒等实用器", "where": "本地木材市场", "tip": "原木需自然干燥3-6个月才能用，买'干燥料'可省时间"}
                    ]
                }
            ]
        }
    },
    "ceramics": {
        "name": "石湾陶艺",
        "origin": "佛山石湾",
        "history": "国家级非物质文化遗产，始于新石器时代，盛于明清。石湾公仔以'胎骨朴拙、釉色斑斓、造型生动'著称，尤以人物陶塑最为出名，被誉为'石湾公仔甲天下'。",
        "steps": [
            {
                "title": "揉泥排气",
                "desc": "将陶泥反复揉压，排出内部气泡。采用菊花揉或螺旋揉法，揉至泥料柔软均匀、切面无气孔为止。每次揉泥至少15分钟。",
                "tips": "泥中有气泡烧制时会炸裂；揉泥时如果太干可适量喷水，太湿可晾干一会儿。"
            },
            {
                "title": "拉坯成型",
                "desc": "将揉好的泥放在拉坯机中心，双手沾水后从中间开孔，慢慢向上提拉塑形。初学者先练习拉圆柱体，再尝试碗、杯等器型。",
                "tips": "拉坯时身体重心要稳，双手力度均匀；转速先快后慢；失败了重新揉泥再来，不要灰心。"
            },
            {
                "title": "修坯利底",
                "desc": "待坯体半干（皮革硬度）时，用修坯刀修整外形和底部。修出圈足，使底部平整。壁厚控制在3-5mm为宜。",
                "tips": "修坯时坯体要固定好，可用泥条粘在转盘上；太干修不动，太湿会变形。"
            },
            {
                "title": "装饰雕刻",
                "desc": "在坯体上进行刻花、贴花、镂空等装饰。石湾陶艺特色是'贴塑'技法——用泥片捏出花叶、人物等部件贴在坯体上。",
                "tips": "贴花时接触面要划毛并涂泥浆，否则烧制时会脱落；细节工具可用牙签、旧毛笔代替。"
            },
            {
                "title": "干燥与素烧",
                "desc": "坯体需自然干燥7-10天，完全干透后入窑素烧。素烧温度约800°C，升温要缓慢（每小时50°C），防止开裂。",
                "tips": "干燥时避免阳光直射和风吹，可用塑料薄膜半遮盖；底部也要干透才能入窑。"
            },
            {
                "title": "上釉与釉烧",
                "desc": "素烧后的坯体浸釉或刷釉，石湾特色是使用低温颜色釉（如翠毛蓝、石榴红）。釉烧温度约1100-1200°C。",
                "tips": "釉层厚度要均匀，底部要刮掉釉料防止粘连；可先试烧小样看颜色效果。"
            }
        ],
        "purchase_guide": {
            "budget": {"starter": "约100-220元（代烧）", "advanced": "约2000-4500元（含拉坯机+电窑）"},
            "buying_tips": "陶艺最大开销是窑——新手强烈建议找本地陶艺工作室代烧（约10-30元/件），省下1500-3000元的电窑钱；泥+工具+釉全齐200元内就能开始玩。",
            "categories": [
                {
                    "key": "essential", "label": "必买基础工具", "desc": "手动成型+修坯+上釉的最小工具集",
                    "items": [
                        {"name": "中温陶泥（10斤装）", "price": "20-40元", "spec": "选1180-1250°C中温泥，要与代烧窑的温度匹配", "where": "淘宝搜'石湾陶泥 中温'或佛山陶艺店", "tip": "先买5斤练手感；泥料要密封保存（装保鲜袋喷水），干了的泥救不回来"},
                        {"name": "陶艺工具10件套", "price": "30-60元", "spec": "含刮刀、环形刀、海绵、木质整形刀、修坯针", "where": "淘宝搜'陶艺工具套装'", "tip": "套装够用很久；细节工具（划花、压纹）用牙签、旧毛笔就能代替"},
                        {"name": "修坯刀套装", "price": "25-50元", "spec": "含圆头/平头修坯刀、圈足刀", "where": "淘宝搜'陶艺修坯刀'", "tip": "修坯要在坯体'皮革硬度'（半干）时进行，太湿会粘刀变形、太干崩坯"},
                        {"name": "手动转盘", "price": "30-60元", "spec": "铝合金或铸铁盘面，直径20-25cm", "where": "淘宝搜'陶艺手动转盘'", "tip": "修坯和贴塑都要用；拉坯机不必急着买，手动转盘足够初期使用"},
                        {"name": "颜色釉基础装（5色）", "price": "60-150元", "spec": "翠毛蓝、石榴红是石湾经典色，配1个透明釉", "where": "淘宝搜'石湾陶釉'或佛山陶艺店", "tip": "釉料含金属氧化物不能入口，操作后务必洗手；上釉前先摇匀"}
                    ]
                },
                {
                    "key": "consumable", "label": "常用耗材", "desc": "每次创作都在消耗的材料",
                    "items": [
                        {"name": "陶泥（持续补充）", "price": "20-40元/10斤", "spec": "练手阶段每月约耗5-10斤", "where": "同上", "tip": "失败的坯体没上釉前可回收：敲碎加水做成'回炉泥'再用"},
                        {"name": "釉料补充", "price": "12-30元/瓶", "spec": "常用色按500ml瓶装补", "where": "同上", "tip": "釉浆沉淀后要充分搅拌；稠了加水、稀了让它蒸发浓缩"},
                        {"name": "石膏垫板 / 帆布垫布", "price": "15-30元", "spec": "石膏板吸水加速坯体干燥，帆布防粘", "where": "淘宝搜'陶艺石膏板'", "tip": "泥料千万别直接放木桌上——木头吸水会导致底部开裂"}
                    ]
                },
                {
                    "key": "advanced", "label": "进阶选配", "desc": "设备类投入大，确定长期玩再买；窑优先考虑代烧",
                    "items": [
                        {"name": "小型拉坯机", "price": "300-800元", "spec": "40cm转盘直径、可无级调速即可", "where": "淘宝搜'小型拉坯机 无级变速'", "tip": "先确认自己喜欢拉坯（圆器）路线；手捏/泥板成型路线用不到它"},
                        {"name": "小型电窑（1200度）", "price": "1500-3000元", "spec": "家用220V、容量20L以上，注意电路负荷", "where": "淘宝搜'小型电窑 1200度'", "tip": "需要专用插座和通风位置；烧窑全程不能离人"},
                        {"name": "喷釉壶 + 气泵", "price": "100-250元", "spec": "做渐变釉面效果用", "where": "淘宝搜'陶艺喷釉套装'", "tip": "浸釉/刷釉已能满足新手，追求专业釉面效果时再上"}
                    ]
                }
            ]
        }
    },
    "lacquer": {
        "name": "阳江漆器",
        "origin": "阳江",
        "history": "广东省级非物质文化遗产，始于明末清初，以阳江漆器厂为代表。阳江漆器以皮胎漆器闻名，工艺精湛，色彩绚丽，曾是广东重要的出口工艺品。",
        "steps": [
            {
                "title": "制作胎体",
                "desc": "传统阳江漆器用牛皮制胎（皮胎），也可用木胎或布胎。木胎需选用质地细腻的木材，打磨光滑后涂生漆封底。",
                "tips": "皮胎制作难度高，初学者建议从木胎开始；木胎表面要彻底打磨光滑，否则影响漆面效果。"
            },
            {
                "title": "批灰与打磨",
                "desc": "在胎体上批涂生漆与瓦灰调和的漆灰，填补缝隙和不平处。干燥后打磨平整，一般需要批灰2-3遍。",
                "tips": "每遍批灰要薄而均匀，厚了容易开裂；打磨后要用布擦干净再批下一遍。"
            },
            {
                "title": "髹底漆",
                "desc": "涂刷生漆作为底漆，每遍薄涂，自然阴干（需在温度25°C、湿度80%的环境下）。底漆一般涂3-5遍，每遍干燥后需水磨。",
                "tips": "生漆干燥需要高湿度，可在房间放加湿器；生漆会引起皮肤过敏，必须戴手套操作。"
            },
            {
                "title": "装饰工艺",
                "desc": "阳江漆器装饰技法有：描金（用金粉描绘图案）、螺钿（镶嵌贝壳片）、推光（反复抛光至镜面效果）、彩绘（用矿物颜料作画）。",
                "tips": "描金时金粉要用桐油调和；螺钿片要提前裁剪好形状；彩绘颜料要与漆兼容。"
            },
            {
                "title": "上面漆与推光",
                "desc": "最后一道面漆要特别精细，涂完后在特定条件下干燥7天以上。然后用细砂纸水磨，再用抛光粉反复推光至镜面效果。",
                "tips": "推光是体力活，需要耐心；用棉花蘸瓦灰和人头油反复擦拭，越推越亮。"
            },
            {
                "title": "完成与保养",
                "desc": "成品完成后避免阳光直射和高温环境。日常保养用柔软干布擦拭，避免接触化学溶剂。传统漆器越用越有光泽。",
                "tips": "漆器怕干燥，长期不用可涂薄薄一层核桃油保养；避免与硬物碰撞。"
            }
        ],
        "purchase_guide": {
            "budget": {"starter": "约250-450元", "advanced": "约800-2000元"},
            "buying_tips": "第一笔钱要花在防护上——生漆过敏可持续7-15天且无特效药；过敏体质先在手背滴一滴生漆观察24小时再决定入手；没有荫房可用纸箱+加湿器代替（成本100元内）。",
            "categories": [
                {
                    "key": "essential", "label": "必买基础工具", "desc": "安全防护优先，其次是漆和胎体",
                    "items": [
                        {"name": "丁腈手套 + 防尘口罩", "price": "20-40元", "spec": "必须是丁腈材质（乳胶手套会被生漆渗透），口罩选KN95", "where": "药店或劳保店", "tip": "生漆过敏是漆艺最大的门槛，防护用品宁可多买不可省——这是清单里优先级最高的一项"},
                        {"name": "天然生漆（500g）", "price": "100-200元", "spec": "选'生漆'而非'腰果漆'练真手感；正品有酸香气，刺鼻化学味是假货", "where": "淘宝搜'天然生漆 漆农直供'（陕西/湖北产地）", "tip": "初学者买小包装即可；生漆密封避光可存数年，一次不用买太多"},
                        {"name": "漆器木胎（简单器型）", "price": "50-200元", "spec": "选手镯、圆盘、笔筒等小件；木胎必须干透（含水率12%以下）", "where": "淘宝搜'漆器木胎'或本地木作店定制", "tip": "皮胎工艺太难，新手一律从木胎开始；胎体不干透日后必开裂"},
                        {"name": "瓦灰 / 漆灰", "price": "15-30元", "spec": "粗灰（120目）批灰找平、细灰（600目）收光，各一袋", "where": "淘宝搜'漆艺瓦灰'", "tip": "批灰要'薄而匀'，厚了必裂；每遍干透打磨后再批下一遍"},
                        {"name": "水磨砂纸（800-2000目）", "price": "15-30元", "spec": "800/1500/2000目各3-5张，全部水磨专用", "where": "五金店或淘宝", "tip": "漆艺打磨一律水磨，干磨粉尘伤肺且漆面会发热受损"},
                        {"name": "漆刷（发刷）", "price": "30-60元", "spec": "女性头发制发刷最佳，牛尾刷次之；宽窄各备1把", "where": "淘宝搜'漆艺发刷'", "tip": "新刷要用肥皂水洗去浮毛；漆刷用后及时用桐油保养，干硬了就报废"}
                    ]
                },
                {
                    "key": "consumable", "label": "常用耗材", "desc": "反复消耗的材料，按进度补货",
                    "items": [
                        {"name": "生漆（持续消耗）", "price": "100-200元/500g", "spec": "底漆+面漆+灰调，单件小作品约耗50-100g", "where": "同上", "tip": "生漆桶口盖紧后倒置存放可隔绝空气结皮"},
                        {"name": "棉布 / 无尘布", "price": "10-20元", "spec": "推光和擦漆用，选不起毛的", "where": "超市或劳保店", "tip": "推光是体力+耐心的活，棉布蘸瓦灰反复擦拭，越推越亮"},
                        {"name": "抛光粉（瓦灰细粉）", "price": "10-20元", "spec": "800目以上细瓦灰", "where": "淘宝搜'漆艺抛光瓦灰'", "tip": "与人头油（或花生油）调和使用，最后一道推光的关键材料"}
                    ]
                },
                {
                    "key": "advanced", "label": "进阶选配", "desc": "装饰技法和环境设备，基本功扎实后再投入",
                    "items": [
                        {"name": "描金笔 + 24K铜金粉", "price": "40-80元", "spec": "狼毫描笔2支（细1粗1）、铜金粉+桐油调和", "where": "淘宝搜'漆艺描金工具'", "tip": "金粉调桐油要'糊而不流'，调好后当天用完"},
                        {"name": "螺钿贝壳片", "price": "30-80元", "spec": "鲍鱼贝/夜光贝薄片，厚0.2-0.5mm", "where": "淘宝搜'螺钿片 漆艺'", "tip": "镶嵌前先在胎面划毛+涂漆，否则干后脱落"},
                        {"name": "荫房设备（加湿器+温湿度计）", "price": "100-300元", "spec": "湿度80%左右、温度25°C上下最理想；纸箱+小型加湿器即可搭建", "where": "淘宝搜'小型加湿器 温湿度计'", "tip": "生漆不干多因湿度不够，投入100元做个'纸箱荫房'比开空调除湿管用得多"},
                        {"name": "核桃油（保养用）", "price": "15-30元", "spec": "食用级冷压核桃油", "where": "超市", "tip": "成品每隔几个月薄涂一层保养，漆器越用越润"}
                    ]
                }
            ]
        }
    }
}


# ==================== 静态文件 ====================

# 项目根目录（适配 Vercel Serverless 环境）
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))

@app.route('/')
def index():
    return send_from_directory(_BASE_DIR, 'index.html')


# ==================== 二十四节气计算 ====================
# 采用 Meeus《Astronomical Algorithms》第 25 章太阳视黄经公式，纯 Python 实现，无新依赖。
# 精度 ≤ 1 分钟，覆盖 1900-2100，可任意年份计算，取代原先硬编码在 js/core.js 的节气表
# （原表仅覆盖 2024-2025，且经外部权威源核对存在至少 5 处日期错误）。

SOLAR_TERM_NAMES = [
    '小寒', '大寒', '立春', '雨水', '惊蛰', '春分',
    '清明', '谷雨', '立夏', '小满', '芒种', '夏至',
    '小暑', '大暑', '立秋', '处暑', '白露', '秋分',
    '寒露', '霜降', '立冬', '小雪', '大雪', '冬至',
]

_SOLAR_START_LONGITUDE = 285.0   # 小寒的太阳视黄经
_SOLAR_DEG_PER_DAY = 0.9856473   # 太阳平均日行度
_solar_terms_cache = {}


def _solar_delta_t_days(year):
    """ΔT(TT-UT) 近似值（天），覆盖 2005-2050 精度足够。"""
    t = year - 2000
    return (62.92 + 0.32217 * t + 0.005589 * t * t) / 86400.0


def _solar_julian_day(year, month, day):
    """由公历日期求儒略日（含小数日）。"""
    if month <= 2:
        year -= 1
        month += 12
    a = year // 100
    b = 2 - a + a // 4
    return (math.floor(365.25 * (year + 4716))
            + math.floor(30.6001 * (month + 1))
            + day + b - 1524.5)


def _sun_apparent_longitude(jde):
    """太阳视黄经（度）。"""
    t = (jde - 2451545.0) / 36525.0
    l0 = 280.46646 + 36000.76983 * t + 0.0003032 * t * t
    m = 357.52911 + 35999.05029 * t - 0.0001537 * t * t
    mr = math.radians(m)
    c = ((1.914602 - 0.004817 * t - 0.000014 * t * t) * math.sin(mr)
         + (0.019993 - 0.000101 * t) * math.sin(2 * mr)
         + 0.000289 * math.sin(3 * mr))
    true_long = l0 + c
    omega = 125.04 - 1934.136 * t
    return (true_long - 0.00569 - 0.00478 * math.sin(math.radians(omega))) % 360.0


def _solar_jd_to_ymd(jd_ut):
    """儒略日(UT) 转北京时间(UTC+8) 的年月日。"""
    jd = jd_ut + 8.0 / 24.0 + 0.5
    z = int(math.floor(jd))
    f = jd - z
    if z < 2299161:
        a = z
    else:
        alpha = int((z - 1867216.25) / 36524.25)
        a = z + 1 + alpha - alpha // 4
    b = a + 1524
    c = int((b - 122.1) / 365.25)
    d = int(365.25 * c)
    e = int((b - d) / 30.6001)
    day = b - d - int(30.6001 * e) + f
    month = e - 1 if e < 14 else e - 13
    year = c - 4716 if month > 2 else c - 4715
    return year, month, int(math.floor(day))


def solar_terms(year):
    """计算指定年份的 24 个节气。

    返回 [{'date': '2026-10-08', 'day': 8, 'month': 10, 'name': '寒露'}, ...]
    结果按年份进程内缓存（同一进程同年份只算一次）。
    """
    if year in _solar_terms_cache:
        return _solar_terms_cache[year]

    dt = _solar_delta_t_days(year)
    result = []
    for i, name in enumerate(SOLAR_TERM_NAMES):
        target = (_SOLAR_START_LONGITUDE + 15.0 * i) % 360.0
        # 初值：小寒约 1 月 6 日，此后每个节气平均间隔 15.2184 天
        jd = _solar_julian_day(year, 1, 6.0) + 15.2184 * i
        for _ in range(60):
            lon = _sun_apparent_longitude(jd + dt)
            diff = (target - lon + 180.0) % 360.0 - 180.0
            jd += diff / _SOLAR_DEG_PER_DAY
            if abs(diff) < 1e-7:
                break
        y, m, d = _solar_jd_to_ymd(jd)
        result.append({
            'date': '%04d-%02d-%02d' % (y, m, d),
            'year': y, 'month': m, 'day': d, 'name': name,
        })

    _solar_terms_cache[year] = result
    return result


def solar_terms_of_month(year, month):
    """取指定年月的节气列表。"""
    return [t for t in solar_terms(year) if t['month'] == month]

# ==================== 农业技能API ====================

# farming_products 表为空时的回退目录（与原硬编码一致，保证平滑过渡）
_DEFAULT_AGRICULTURE_PRODUCTS = [
    {"id": "lychee", "name": "荔枝", "icon": "apple-alt", "desc": "广东特色水果"},
    {"id": "longan", "name": "龙眼", "icon": "circle", "desc": "岭南佳果"},
    {"id": "aquatic", "name": "水产养殖", "icon": "fish", "desc": "鱼虾蟹贝"},
    {"id": "rice", "name": "水稻", "icon": "seedling", "desc": "主要粮食作物"},
    {"id": "tea", "name": "茶叶", "icon": "mug-hot", "desc": "广东名茶"},
    {"id": "vegetable", "name": "蔬菜", "icon": "carrot", "desc": "时令蔬菜"},
]


def _month_in_phase(month, start_month, end_month):
    """物候期命中判定。start_month > end_month 表示跨年区间（如 11月 → 次年1月）。"""
    if start_month <= end_month:
        return start_month <= month <= end_month
    return month >= start_month or month <= end_month


@app.route('/api/agriculture/products', methods=['GET'])
def get_products():
    """农产品目录：优先读 farming_products 表（is_active=1，按 sort_order 排序）。

    返回结构与旧版保持一致（desc 由 summary 映射），表为空时回退硬编码列表。
    """
    try:
        rows = database.get_farming_products()
    except Exception as e:
        logging.warning('读取农产品目录失败，回退硬编码: %s', e)
        rows = []
    if rows:
        products = [{
            "id": r["id"],
            "name": r["name"],
            "icon": r.get("icon") or "seedling",
            "desc": r.get("summary") or "",
        } for r in rows]
    else:
        products = [dict(p) for p in _DEFAULT_AGRICULTURE_PRODUCTS]
    return jsonify({"success": True, "products": products})


@app.route('/api/agriculture/calendar/<product_id>', methods=['GET'])
def get_farming_calendar(product_id):
    """农时日历（年周期模板）。

    query:
      year   可选，缺省取服务器当前年
      month  可选，1-12；传 0 视为 0-indexed 的一月（兼容旧调用）；缺省取当前月
    """
    product = database.get_farming_product(product_id)
    if not product or not product.get('is_active', 1):
        return jsonify({"success": False, "message": "未找到该农产品信息"}), 404

    now = datetime.now()
    try:
        year = int(request.args.get('year') or now.year)
    except (TypeError, ValueError):
        year = now.year

    raw_month = request.args.get('month')
    if raw_month is None or raw_month == '':
        month = now.month
    else:
        try:
            month = int(raw_month)
        except (TypeError, ValueError):
            month = now.month
        if month == 0:
            month = 1          # 0-indexed 兼容
        if month < 1 or month > 12:
            month = now.month

    phases = database.get_farming_phenophases(product_id)
    tasks = database.get_farming_tasks(product_id, month=month)
    labels = database.get_farming_category_labels()
    source_map = database.get_farming_source_map()

    # 物候期：标记当月命中项，并给出「当前物候期」（取首个命中项）
    phase_current = None
    for ph in phases:
        ph['in_month'] = _month_in_phase(month, ph['start_month'], ph['end_month'])
        if ph['in_month'] and phase_current is None:
            phase_current = ph

    # 节气：复用 Meeus 算法结果，day 预拆好供前端直接索引
    solar = [{"date": t["date"], "day": t["day"], "name": t["name"]}
             for t in solar_terms_of_month(year, month)]

    # 任务：MM-DD 拆出 date/day；task_md 为空则 day/date 均为 null（前端归入「本月内」）
    out_tasks = []
    for t in tasks:
        md = t.get('task_md')
        verified = int(t.get('is_verified') or 0)
        src = source_map.get(t.get('source_key') or '')
        day = None
        date = None
        if md:
            try:
                mm, dd = md.split('-')
                day = int(dd)
                date = '%04d-%s' % (year, md) if int(mm) == month else None
                if date is None:
                    day = None
            except (ValueError, AttributeError):
                day = None
        out_tasks.append({
            "id": t["id"],
            "date": date,
            "day": day,
            "task_md": md,
            "title": t["title"],
            "category": t["category"],
            "category_label": labels.get(t["category"], t["category"]),
            "priority": t.get("priority") or "medium",
            "icon": t.get("icon") or "tasks",
            "description": t.get("description") or "",
            "tip": t.get("tip") or "",
            "phase_id": t.get("phase_id"),
            "phase_name": t.get("phase_name"),
            "phase_color": t.get("phase_color"),
            "sort_order": t.get("sort_order", 0),
            # 日期是否已由农技人员复核：0 表示按农时规律推算的参考值（前端加「约」并挂提示条）
            "is_verified": verified,
            # evidence_level：verified（已人工复核）/ sourced（有公开技术资料依据，待核）
            #                 / unsourced（无来源登记，不应出现）
            "evidence_level": ("verified" if verified
                               else ("sourced" if src else "unsourced")),
            # 该日期的农艺依据（为什么定在这个时间），供前端展开给用户看
            "date_basis": t.get("date_basis") or "",
            # 来源方向：机构 + 文件类型；doc_no 多为「待核」
            "source": ({
                "key": src.get("key"),
                "name": src.get("name") or "",
                "org": src.get("org") or "",
                "doc_type": src.get("doc_type") or "",
                "doc_no": src.get("doc_no") or "",
                "url": src.get("url") or "",
            } if src else None),
        })

    # 只要存在「有日期但未复核」的任务，就向前端声明本月日期为推算参考值
    dates_provisional = any(t["day"] and not t["is_verified"] for t in out_tasks)

    # 本月数据底账：让前端能如实说明「依据什么编排、还有多少条待农技复核」
    sourced_keys = []
    for t in out_tasks:
        k = (t.get("source") or {}).get("key")
        if k and k not in sourced_keys:
            sourced_keys.append(k)
    source_summary = {
        "total": len(out_tasks),
        "verified": sum(1 for t in out_tasks if t["evidence_level"] == "verified"),
        "sourced": sum(1 for t in out_tasks if t["evidence_level"] == "sourced"),
        "unsourced": sum(1 for t in out_tasks if t["evidence_level"] == "unsourced"),
        "sources": [{
            "key": source_map[k]["key"],
            "name": source_map[k]["name"],
            "org": source_map[k].get("org") or "",
            "doc_type": source_map[k].get("doc_type") or "",
            "doc_no": source_map[k].get("doc_no") or "",
            "url": source_map[k].get("url") or "",
        } for k in sourced_keys],
    }

    # 该作物全年用到的来源集合（供「数据依据」说明面板一次列全，避免逐月变动）
    year_keys = []
    try:
        for t in database.get_farming_tasks(product_id):
            k = t.get('source_key') or ''
            if k and k in source_map and k not in year_keys:
                year_keys.append(k)
    except Exception as e:
        logging.warning('收集作物全年来源失败: %s', e)
    sources_all = [{
        "key": source_map[k]["key"],
        "name": source_map[k]["name"],
        "org": source_map[k].get("org") or "",
        "doc_type": source_map[k].get("doc_type") or "",
        "doc_no": source_map[k].get("doc_no") or "",
        "url": source_map[k].get("url") or "",
    } for k in year_keys]

    return jsonify({
        "success": True,
        "product": {
            "id": product["id"], "name": product["name"],
            "icon": product.get("icon") or "seedling",
        },
        "year": year,
        "month": month,
        "is_configured": bool(tasks or phases),
        "dates_provisional": dates_provisional,
        "source_summary": source_summary,
        "sources_all": sources_all,
        "phenophase_current": ({
            "id": phase_current["id"],
            "name": phase_current["name"],
            "color": phase_current.get("color"),
            "description": phase_current.get("description") or "",
        } if phase_current else None),
        "phenophases": [{
            "id": ph["id"], "name": ph["name"],
            "start_month": ph["start_month"], "end_month": ph["end_month"],
            "color": ph.get("color"), "description": ph.get("description") or "",
            "in_month": ph["in_month"],
        } for ph in phases],
        "solar_terms": solar,
        "tasks": out_tasks,
    })


@app.route('/api/agriculture/subscriptions', methods=['GET'])
def get_my_farming_subscriptions():
    """当前用户订阅的作物列表"""
    user = _get_session_user()
    if not user:
        return jsonify({"success": False, "message": "请先登录"}), 401
    return jsonify({
        "success": True,
        "product_ids": database.get_farming_subscriptions(user['username']),
    })


@app.route('/api/agriculture/subscribe', methods=['POST'])
def subscribe_farming():
    """订阅某作物的农事提醒（幂等）"""
    user = _get_session_user()
    if not user:
        return jsonify({"success": False, "message": "请先登录"}), 401
    data = request.get_json(silent=True) or {}
    pid = (data.get('product_id') or '').strip()
    if not pid:
        return jsonify({"success": False, "message": "缺少 product_id"}), 400
    _p = database.get_farming_product(pid)
    if not _p or not _p.get('is_active', 1):
        # 与 /api/agriculture/calendar/<id> 保持一致：停用作物不可订阅，避免订阅后无日历可看
        return jsonify({"success": False, "message": "未找到该农产品信息"}), 404
    database.set_farming_subscription(user['username'], pid, True)
    return jsonify({
        "success": True, "subscribed": True,
        "product_ids": database.get_farming_subscriptions(user['username']),
    })


@app.route('/api/agriculture/subscribe/<product_id>', methods=['DELETE'])
def unsubscribe_farming(product_id):
    """取消订阅（幂等）"""
    user = _get_session_user()
    if not user:
        return jsonify({"success": False, "message": "请先登录"}), 401
    database.set_farming_subscription(user['username'], product_id, False)
    # 同步清理当期提醒日志：否则「退订 → 当月重新订阅」会因幂等键命中而静默收不到提醒
    database.clear_farming_reminder_log(user['username'], product_id)
    return jsonify({
        "success": True, "subscribed": False,
        "product_ids": database.get_farming_subscriptions(user['username']),
    })


def _farming_task_brief(task):
    """把任务压成「05日 花前病虫害预防」的一行摘要，供提醒文案使用。"""
    md = (task.get('task_md') or '')
    day = None
    if '-' in md:
        try:
            day = int(md.split('-', 1)[1])
        except (ValueError, IndexError):
            day = None
    return ('%d日 %s' % (day, task.get('title', ''))) if day else task.get('title', '')


@app.route('/api/agriculture/reminders/check', methods=['POST'])
def check_farming_reminders():
    """登录时补发农事提醒。

    对每个订阅作物，若当期（YYYY-MM）尚未推送过，则生成一条站内通知并记录日志。
    幂等：同一用户 + 同一作物 + 同一月份只发一次。

    取「已到期」任务（task_md 的日 <= 今天），避免在月初就预告整月的未来农事；
    若今天尚无到期任务，则不发送、也不写日志，用户下次登录会在此后的日期正常收到。
    """
    user = _get_session_user()
    if not user:
        return jsonify({"success": False, "message": "请先登录"}), 401

    uid = user['username']
    now = datetime.now()
    period = '%04d-%02d' % (now.year, now.month)
    sent, details = 0, []

    for pid in database.get_farming_subscriptions(uid):
        if database.has_farming_reminder_sent(uid, pid, period):
            continue
        product = database.get_farming_product(pid)
        # 与 /api/agriculture/calendar/<id> 一致：停用作物不再推送（否则点进通知是 404）
        if not product or not product.get('is_active', 1):
            continue
        due = database.get_due_farming_tasks(pid, now.year, now.month, until_day=now.day)
        if not due:
            continue
        # 文案带具体日期：优先高优先级，最多 3 条
        picked = [t for t in due if t.get('priority') == 'high'][:3] or due[:3]
        highlights = [_farming_task_brief(t) for t in picked]
        title = '%d月%s农事提醒' % (now.month, product['name'])
        content = '本月已到期农事：' + '、'.join(highlights) + '。详情见「农业技能 · 农时智能日历」。'
        try:
            database.create_notification(uid, 'farming_reminder', title, content, 'farming', pid)
        except Exception as e:
            logging.warning('农事提醒写入通知失败(%s/%s): %s', uid, pid, e)
            continue
        database.mark_farming_reminder_sent(uid, pid, period)
        sent += 1
        details.append({
            "product_id": pid, "product_name": product['name'],
            "period": period, "title": title,
            "items": [t['task_md'] for t in picked],
        })

    return jsonify({"success": True, "period": period, "sent": sent, "details": details})


@app.route('/api/agriculture/ask', methods=['POST'])
def ask_agriculture():
    payload, err = _parse_agri_request()
    if err:
        return err

    if _rate_limited('ask:' + _client_key(), AGRI_RATE_ASK_LIMIT):
        return jsonify({
            "success": False, "code": "rate_limited",
            "message": "提问过于频繁，请稍后再试"
        }), 429

    question = payload['question']
    product = payload['product']
    messages = _build_agri_messages(_agri_system_prompt(product), payload['history'], question)

    # 未配置密钥：明确告知，不再返回一条伪装成正常回答的兜底文案
    if not _ai_configured():
        logger.warning("AI问答被调用但未配置密钥：%s", AI_NOT_CONFIGURED_LOG)
        return jsonify({
            "success": False, "code": "ai_not_configured",
            "message": AI_NOT_CONFIGURED_MSG
        }), 503

    try:
        answer = _chat_completion(messages, temperature=0.4, max_tokens=800, timeout=30,
                                  model=_chat_model())
    except Exception as e:
        logger.error("AI问答失败: %s", e)
        return jsonify({
            "success": False, "code": "ai_unavailable",
            "message": AI_UNAVAILABLE_MSG
        }), 503

    # A2：正文里出现用量 / 稀释倍数 / 安全间隔期时，服务端强制补免责声明。
    # 放在生成追问建议之前，让建议基于补齐后的完整回答。
    if _has_chem_dosage(answer):
        answer = answer.rstrip() + _CHEM_DOSE_NOTICE_BLOCK

    # 追问建议失败不影响主回答
    try:
        suggestions = _generate_suggestions(product, question, answer)
    except Exception as e:
        logger.warning("生成追问建议失败: %s", e)
        suggestions = []

    return jsonify({"success": True, "answer": answer, "suggestions": suggestions})


@app.route('/api/agriculture/ask/stream', methods=['POST'])
def ask_agriculture_stream():
    """SSE 流式 AI 问答"""
    payload, err = _parse_agri_request()
    if err:
        return err

    if _rate_limited('ask:' + _client_key(), AGRI_RATE_ASK_LIMIT):
        return jsonify({
            "success": False, "code": "rate_limited",
            "message": "提问过于频繁，请稍后再试"
        }), 429

    if not _ai_configured():
        logger.warning("SSE问答被调用但未配置密钥：%s", AI_NOT_CONFIGURED_LOG)
        return jsonify({
            "success": False, "code": "ai_not_configured",
            "message": AI_NOT_CONFIGURED_MSG
        }), 503

    question = payload['question']
    product = payload['product']
    messages = _build_agri_messages(_agri_system_prompt(product), payload['history'], question)
    collected = []

    def generate():
        import requests as req
        payload = {
            "model": _chat_model(),
            "messages": messages,
            "temperature": 0.4,
            # 推理模型会把额度先花在思考上（实测约 400 token），留出余量给正文；
            # 非推理模型（stepaudio-2.5-chat）不会思考，这只是个用不到的上限，无副作用。
            "max_tokens": 800 + AI_REASONING_TOKEN_RESERVE,
            "stream": True
        }
        if AI_REASONING_EFFORT:
            payload["reasoning_effort"] = AI_REASONING_EFFORT
        try:
            resp = req.post(
                AI_API_URL,
                headers={
                    "Authorization": f"Bearer {AI_API_KEY}",
                    "Content-Type": "application/json"
                },
                json=payload,
                stream=True,
                timeout=(10, 60)
            )
            resp.raise_for_status()

            try:
                for line in resp.iter_lines():
                    if not line:
                        continue
                    line = line.decode('utf-8', 'replace')
                    if not line.startswith('data: '):
                        continue
                    data_str = line[6:].strip()
                    if data_str == '[DONE]':
                        break
                    try:
                        chunk = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue
                    choices = chunk.get('choices') if isinstance(chunk, dict) else None
                    if not choices:
                        continue
                    content = (choices[0].get('delta') or {}).get('content') or ''
                    if content:
                        collected.append(content)
                        yield f'data: {json.dumps({"content": content}, ensure_ascii=False)}\n\n'
            finally:
                resp.close()

            # 上游「成功但没内容」也是一种失败，必须让前端知道，不能留一个空气泡
            if not ''.join(collected).strip():
                raise ValueError('上游未返回任何内容')

            # A2：正文出现用药数值时强制补免责声明。必须在 event: done 之前发出 ——
            # 前端收到 done 就会收尾气泡并渲染操作按钮，之后再发的内容不会被渲染。
            if _has_chem_dosage(''.join(collected)):
                yield 'data: %s\n\n' % json.dumps(
                    {"content": _CHEM_DOSE_NOTICE_BLOCK}, ensure_ascii=False)
        except Exception as e:
            logger.error("SSE问答失败: %s", e)
            yield 'event: error\ndata: %s\n\n' % json.dumps(
                {"code": "ai_unavailable", "message": AI_UNAVAILABLE_MSG},
                ensure_ascii=False)
            return

        # 先收尾正文（前端据此渲染操作按钮），再补发追问建议，
        # 避免「建议生成」这段额外耗时拖慢回答的收尾。
        yield 'event: done\ndata: [DONE]\n\n'

        try:
            suggestions = _generate_suggestions(product, question, ''.join(collected))
        except Exception as e:
            logger.warning("流式追问建议生成失败: %s", e)
            suggestions = []
        if suggestions:
            yield 'event: suggestions\ndata: %s\n\n' % json.dumps(
                {"suggestions": suggestions}, ensure_ascii=False)

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive'
        }
    )


def _generate_suggestions(product, question, answer):
    """基于当前问答生成3个追问建议。任何失败都返回空列表，不抛异常、不影响主回答。"""
    product_name = _agriculture_product_name(product)
    try:
        result = call_ai_service(
            system_prompt=f"你是{product_name}种植专家。根据用户的问题和AI回答，生成3个相关的追问建议。只输出3个问题，每行一个，不要编号，不要其他内容。每个问题控制在20字以内。",
            user_message="用户问：%s\nAI答：%s" % (str(question or '')[:200], str(answer or '')[:200]),
            max_tokens=300 + AI_REASONING_TOKEN_RESERVE,
            temperature=0.6,
            model=_chat_model()
        )
    except Exception as e:
        logger.warning("生成追问建议失败: %s", e)
        return []

    items = []
    for raw in str(result or '').split('\n'):
        text = raw.strip().lstrip('0123456789.、）) ').strip()
        if text and len(text) <= 40:
            items.append(text)
    return items[:3]


# 建议问题缓存
_suggestions_cache = {}
_suggestions_cache_time = {}
SUGGESTIONS_CACHE_TTL = 300  # 5分钟

# 静态兜底建议：未配置密钥 / 上游失败 / 被限流时使用，保证建议栏始终可用
_STATIC_AGRI_SUGGESTIONS = {
    "lychee": ["荔枝花期如何管理？", "如何防治荔枝霜疫霉病？", "荔枝采后怎样恢复树势？", "荔枝膨大期施什么肥？"],
    "longan": ["龙眼如何疏花疏果？", "龙眼鬼帚病怎么防治？", "龙眼冬季管理要点？", "龙眼什么时候采收最好？"],
    "aquatic": ["鱼塘水质如何调节？", "虾塘增氧机怎么开？", "鱼病预防有哪些方法？", "养殖密度多少合适？"],
    "rice": ["水稻纹枯病怎么防治？", "水稻什么时候晒田好？", "稻飞虱用什么药？", "水稻收割最佳时期？"],
    "tea": ["茶园如何进行冬管？", "茶叶虫害绿色防控？", "春茶采摘标准是什么？", "茶树修剪技术要点？"],
    "vegetable": ["蔬菜大棚如何控温？", "叶菜类常见病害防治？", "有机蔬菜怎么施肥？", "蔬菜轮作有什么好处？"]
}


def _static_agri_suggestions(product):
    return list(_STATIC_AGRI_SUGGESTIONS.get(product, _STATIC_AGRI_SUGGESTIONS["lychee"]))


@app.route('/api/agriculture/suggestions', methods=['GET'])
def get_agriculture_suggestions():
    """获取指定农产品的常见问题建议。

    建议栏属于「锦上添花」的辅助内容：任何失败都退化为静态建议，
    对前端始终返回 success=True，不把错误抛给用户。
    """
    product = request.args.get('product', 'lychee')
    now = time.time()

    # 命中缓存不消耗配额
    if product in _suggestions_cache and now - _suggestions_cache_time.get(product, 0) < SUGGESTIONS_CACHE_TTL:
        return jsonify({"success": True, "suggestions": _suggestions_cache[product]})

    if _rate_limited('suggest:' + _client_key(), AGRI_RATE_SUGGEST_LIMIT):
        return jsonify({"success": True, "suggestions": _static_agri_suggestions(product)})

    if not _ai_configured():
        return jsonify({"success": True, "suggestions": _static_agri_suggestions(product)})

    product_name = _agriculture_product_name(product)
    try:
        result = call_ai_service(
            system_prompt=f"你是{product_name}种植专家。生成4个农民最常问的实用问题，每行一个，不要编号，不要其他内容。每个问题控制在15-25字。要覆盖不同方面（种植、病虫害、施肥、采收等）。",
            user_message=f"请为{product_name}生成4个常见问题",
            max_tokens=300 + AI_REASONING_TOKEN_RESERVE,
            temperature=0.7,
            model=_chat_model()
        )
        suggestions = [s.strip().lstrip('0123456789.、 ') for s in result.strip().split('\n') if s.strip()][:4]
        if not suggestions:
            raise ValueError('上游未返回可用问题')
        _suggestions_cache[product] = suggestions
        _suggestions_cache_time[product] = now
        return jsonify({"success": True, "suggestions": suggestions})
    except Exception as e:
        logger.error("生成建议问题失败: %s", e)
        return jsonify({"success": True, "suggestions": _static_agri_suggestions(product)})


# ==================== 电商运营API ====================

@app.route('/api/ecommerce/script', methods=['POST'])
def generate_script():
    data = request.get_json() or {}
    product = str(data.get('product', '') or '').strip() or '荔枝'
    style = str(data.get('style', '') or '').strip() or '热情'

    # EC6：本接口此前无任何限流；与农业三路口径对齐。
    if _rate_limited('ec-script:' + _client_key(), EC_RATE_SCRIPT_LIMIT):
        return jsonify({"success": False, "code": "rate_limited",
                        "message": "请求过于频繁，请稍后再试"}), 429
    # EC9：未知风格此前静默降级为「热情」，现明确拒绝。
    if style not in EC_STYLE_KEYS:
        return jsonify({"success": False, "code": "unknown_style",
                        "message": "不支持的话术风格，请从列表中选择"}), 400
    # EC9：空 product 会生成「为广东撰写…」这类丢了作物的提示词，现明确拒绝。
    if not _ec_product_ok(product):
        return jsonify({"success": False, "code": "unknown_product",
                        "message": "暂不支持该农产品，请从列表中选择"}), 400

    style_prompts = {
        '热情': {
            'desc': '热情洋溢、极具感染力的带货风格',
            'techniques': [
                '开场用"家人们""宝子们"等亲昵称呼拉近距离',
                '用感叹句和反问句制造情绪高潮，如"这也太香了吧！""你们说值不值？"',
                '重复强调核心卖点至少3次，形成记忆锚点',
                '表达紧迫感用「限时/限量」即可，价格一律写成【待填写：直播间价格】',
                '穿插互动指令："想要的扣1""觉得值的点个赞"',
                '不虚构原价与划线价；需要价格锚点时写【待填写：原价】→【待填写：直播间价】'
            ]
        },
        '专业': {
            'desc': '专业可信、知识型带货风格',
            'techniques': [
                '开场介绍产品产地、品种、种植/养殖方式等专业背景',
                '讲清产品特点；没有真实数据时不要填数字，写成【待填写：甜度/规格等实测值】',
                '对比同类产品突出差异化优势',
                '涉及认证时不要替产品认定，写成【待填写：认证名称与编号】',
                '讲解挑选技巧和食用方法，提供附加价值',
                '语调沉稳但不失热情，像专家在分享而非推销'
            ]
        },
        '故事': {
            'desc': '故事型、情感共鸣带货风格',
            'techniques': [
                '营造产地氛围与人物感即可，不要虚构具体人名、年份、产量或获奖经历',
                '描述产品的生长环境、气候、水土等自然条件',
                '讲述从田间到餐桌的旅程，强调用心与坚持（不虚构具体流程数据）',
                '融入岭南文化元素和乡土情怀',
                '用五感描写让消费者"看到""闻到""尝到"',
                '结尾升华：支持乡村振兴、助力农户增收'
            ]
        },
        '高级': {
            'desc': '高级感、品质生活带货风格',
            'techniques': [
                '用品质生活的角度切入，不直接叫卖',
                '营造场景感：夏日冰镇荔枝配白葡萄酒、秋日茶席',
                '可以表达品质感，但不要虚构稀缺性、产区限定或获奖背书',
                '用文艺化的语言描述产品，如"岭南夏日的第一口甜"',
                '可描述香气、口感等品鉴角度，但不要虚构第三方评价',
                '控制节奏，留白有度，不急不躁地展示品质'
            ]
        }
    }
    style_config = style_prompts.get(style, style_prompts['热情'])
    techniques_text = '\n'.join(f'- {t}' for t in style_config['techniques'])
    try:
        ai_script = call_ai_service(
            system_prompt=f"""你是一位顶级直播带货话术专家，擅长为广东特色农产品撰写高转化率的直播脚本。

【风格】{style_config['desc']}

【话术技巧】
{techniques_text}

【结构要求】
1. 开场钩子（1-2句）：3秒内抓住注意力
2. 产品亮点（2-3句）：核心卖点（无真实数据时用【待填写】占位）
3. 产地特色（1-2句）：产地/品种的自然条件（认证信息用【待填写】占位）
4. 促单话术（1-2句）：紧迫感（价格用【待填写】占位）
5. 互动引导（1句）：引导点赞/下单

【输出要求】
- 总共8-12句，每句一行
- 口语化，有节奏感，适合朗读
- 用【】标注关键卖点，需要用户补充的信息用【待填写：……】
- 穿插互动指令（括号标注，如：(引导点赞)）

{_EC_PROMO_RULE}""",
            user_message=f"为广东{product}撰写直播带货话术，要突出岭南特色和产品优势",
            model=_chat_model()
        )
        return jsonify({"success": True, "script": ai_script})
    except Exception as e:
        logger.error(f"话术生成失败: {e}")
        # EC5：降级必须可见。此前这里是 success:True + 硬编码话术，界面完全看不出这不是
        # AI 生成的（违反本项目「失败必须可见」红线）。现返回 degraded 标记，前端在话术框
        # 顶部显示「本条为系统内置示例，非 AI 生成」。
        # 同时按 EC1 的宣传口径，把原先写死的认证、检测数据、价格与赔付承诺全部改为【待填写】。
        fallback_scripts = {
            '热情': f"""家人们！今天给你们带来广东的{product}！
(互动) 想要的扣1，让我看看有多少人识货！
你们看这个品相，【请按实际品相描述】！
价格：【待填写：直播间价格】（除非能给出真实原价，否则不要写「原价多少」）
(引导) 觉得值的给我点个赞！
限量【待填写：库存数量】单，拍完就下架，手慢无！""",

            '专业': f"""各位朋友好，今天给大家带来的是广东{product}。
它产自岭南产区，日照充足、雨热同期——这是这类农产品普遍的生长条件。
每一批的检测情况请以实际报告为准：【待填写：检测项目与报告】
它区别于同类产品的特点：【待填写：真实的差异点】
今天的优惠形式：【待填写：优惠形式】。""",

            '故事': f"""在广东的一个小村子里，{product}的种植已经延续了好几代人。
老话讲："好东西急不得，要等天时、靠地利、更要用心。"
(停顿) 每年这个时候，果农天不亮就下地，只为赶在日出前采摘最新鲜的一批。
从枝头到你手里，只求尽快——这是我们对新鲜的态度。
今天把这份来自岭南的用心带给大家。
(引导) 想尝尝这份用心的，点下方链接下单吧。""",

            '高级': f"""岭南的时令风物里，最令人期待的，莫过于这口来自广东的{product}。
它生长在北回归线以南的沃土，吸饱了亚热带的阳光和雨露。
【果肉细腻，汁水丰盈】，入口即化的口感，是大自然最好的馈赠。
把这份岭南的时令滋味带回家，只需一键下单。
今日供应情况：【待填写：规格与库存】。
品味不将就，生活要讲究。"""
        }
        return jsonify({"success": True, "degraded": True,
                        "script": fallback_scripts.get(style, fallback_scripts['热情'])})


@app.route('/api/ecommerce/feedback', methods=['POST'])
def get_live_feedback():
    """评一段直播带货话术稿的质量。

    口径说明（2026-10-05，EC2/EC3）：这里评的是**送进来的稿子**；EC3 之后前端改为提交
    「学员自己的稿」。另新增 `/api/ecommerce/live/report` 度量学员的**现场朗读表现**，
    两者是不同对象，不要混为一谈。
    """
    data = request.get_json() or {}
    script_text = str(data.get('script', '') or '')

    # EC6：本接口此前无任何限流、无输入上限（实测匿名连打 8 次全部 200）。
    if _rate_limited('ec-feedback:' + _client_key(), EC_RATE_FEEDBACK_LIMIT):
        return jsonify({"success": False, "code": "rate_limited",
                        "message": "请求过于频繁，请稍后再试"}), 429
    if not script_text.strip():
        return jsonify({"success": False, "code": "empty_script",
                        "message": "请先写出或生成一段话术"}), 400
    if len(script_text) > EC_SCRIPT_MAX_LEN:
        return jsonify({"success": False, "code": "script_too_long",
                        "message": f"话术过长，请控制在 {EC_SCRIPT_MAX_LEN} 字以内"}), 400

    import re

    def analyze_script(text):
        """基于规则分析话术内容，生成差异化分数"""
        # 统计各类特征
        exclamation = len(re.findall(r'[！!]{1,}', text))
        question = len(re.findall(r'[？?]{1,}', text))
        interaction_words = len(re.findall(r'扣\d|点[个一]赞|觉得值|想要的|有没有|是不是|对不对|家人们|宝子们', text))
        pause_marks = len(re.findall(r'停顿|稍等|等一下|\.\.\.|\…', text))
        data_marks = len(re.findall(r'\d+[%°度]|【[^】]+】|\d+[元斤箱份]', text))
        emotion_words = len(re.findall(r'太[香好吃棒]|绝了|真的|必须|一定要|超级|特别|非常', text))
        price_words = len(re.findall(r'原价|划线价|专属价|只要|仅需|优惠|折扣|限量|最后|手慢无', text))

        # 基础分 + 特征加权
        speed = 68 + min(pause_marks * 6, 20) + min(exclamation * 2, 10) - (0 if len(text) > 100 else 5)
        emotion = 65 + min(emotion_words * 5, 20) + min(exclamation * 3, 15) + min(question * 2, 10)
        interaction = 60 + min(interaction_words * 8, 30) + min(question * 3, 10)
        selling = 66 + min(data_marks * 5, 20) + min(price_words * 4, 16)

        # ⚠️ EC2：这里原先每个维度都叠加 random.randint(-3, 3) 随机扰动，
        # 导致**同一份话术每次得分都不同**（实测 80/81/78）。测评必须是可复现的 ——
        # 学员无法凭一个每次都在跳的分数判断自己有没有进步，教师也无法用它打分。
        # 现已全部去掉随机数：同样的输入必然得到同样的输出。
        return (max(50, min(98, speed)), max(50, min(98, emotion)),
                max(50, min(98, interaction)), max(50, min(98, selling)))

    def generate_suggestions(speed, emotion, interaction, selling, text):
        """基于分数和内容生成针对性建议"""
        suggestions = []
        has_interaction = bool(re.search(r'扣\d|点[个一]赞|觉得值', text))
        has_pause = bool(re.search(r'停顿|\.\.\.', text))
        has_data = bool(re.search(r'\d+[元斤箱度%]', text))
        has_price = bool(re.search(r'原价|只要|专属价', text))
        has_emotion = bool(re.search(r'家人们|宝子们|太[香好吃]', text))

        if interaction < 75 and not has_interaction:
            suggestions.append('加入互动指令，如"想要的扣1""觉得值的点个赞"')
        if speed < 72 and not has_pause:
            suggestions.append('适当加入停顿，制造悬念感，如"(停顿3秒)"')
        if selling < 75 and not has_data:
            suggestions.append('需要补充的真实数据（规格、检测指标等）用【待填写】标注，不要编数字')
        if emotion < 72 and not has_emotion:
            suggestions.append('增加情绪词和感叹句，如"这也太香了吧！"')
        if not has_price:
            suggestions.append('加入价格信息；价格必须填真实值，不要虚构原价或划线价')
        if selling >= 75 and interaction >= 75:
            suggestions.append('整体不错，可以尝试讲故事增加情感共鸣')

        # 补充通用建议到至少3条。EC2：去掉 random.shuffle —— 建议列表同样必须可复现。
        general = [
            '开场3秒内抛出核心卖点抓住注意力',
            '用真实的库存或时限表达紧迫感，不要虚构销量',
            '补充可核实的信任信息（产地、检测报告编号）',
            '结尾引导关注直播间获取更多优惠',
            '用对比法突出产品差异化优势'
        ]
        for g in general:
            if len(suggestions) >= 3:
                break
            suggestions.append(g)

        return suggestions[:3]

    try:
        # EC2：改走对话模型 `_chat_model()`。此前留空 → 用默认推理模型 step-3.7-flash，
        # 其「思考」会吃掉 max_tokens，额度不够时正文为空 → 抛错 → 静默降级为规则分。
        # 这也正是实测 6 次里 3 次走 except 分支的原因（单次还要等 10s）。
        result = call_ai_service(
            system_prompt="""你是直播话术评分专家。分析以下直播带货话术，给出四个维度的评分和改进建议。

请先分析话术中的具体特征（互动词数量、感叹句数量、信息支撑等），然后给出评分。

评分维度（每项0-100整数，四个分数必须不同）：
- speed_score：文案节奏（**只看文本**：停顿标记、句子长短变化、朗读顺不顺；不代表实际语速）
- emotion_score：情绪感染力（看感叹句、情绪词、反问句）
- interaction_score：互动技巧（看"扣1""点赞""家人们"等互动词数量）
- selling_score：卖点提炼（看卖点是否清晰、【】标注是否到位）

注意：不要因为话术里出现【待填写】占位就扣分 —— 占位是刻意要求用户补真实信息的；
反过来，若话术里出现了无法核实的具体认证、检测数据或价格承诺，应在 summary 里提醒。

输出格式（严格JSON，不要其他文字）。每个维度必须同时给出 evidence ——
用一句话**引用或概括稿子里的原文**说明给分依据（不超过40字），让学员知道分从哪来：
{"speed_score":数字,"speed_evidence":"...","emotion_score":数字,"emotion_evidence":"...","interaction_score":数字,"interaction_evidence":"...","selling_score":数字,"selling_evidence":"...","summary":"20字总评","suggestions":["针对性建议1","建议2","建议3"]}""",
            user_message=f"请评分：\n{script_text}",
            model=_chat_model()
        )
        try:
            json_match = re.search(r'\{.*?\}', result, re.DOTALL)
            feedback = json.loads(json_match.group()) if json_match else json.loads(result)
        except (json.JSONDecodeError, AttributeError, TypeError):
            feedback = {}

        # 用规则分析作为基础
        s, e, i, se = analyze_script(script_text)

        # 如果AI返回了有效分数且有差异，优先用AI的；否则用规则分析
        ai_scores = [feedback.get('speed_score'), feedback.get('emotion_score'),
                     feedback.get('interaction_score'), feedback.get('selling_score')]
        ai_valid = all(isinstance(x, (int, float)) and 40 <= x <= 100 for x in ai_scores)
        ai_diff = len(set(ai_scores)) >= 3  # 至少3个不同才算有效

        if ai_valid and ai_diff:
            final_speed, final_emotion, final_interaction, final_selling = [int(x) for x in ai_scores]
            final_suggestions = feedback.get('suggestions', []) if feedback.get('suggestions') else generate_suggestions(s, e, i, se, script_text)
            final_summary = feedback.get('summary', '整体表现不错')
        else:
            final_speed, final_emotion, final_interaction, final_selling = s, e, i, se
            final_suggestions = generate_suggestions(s, e, i, se, script_text)
            final_summary = feedback.get('summary', '') or '整体表现不错，有提升空间'

        ai_used = bool(ai_valid and ai_diff)
        scores = [final_speed, final_emotion, final_interaction, final_selling]
        # 直播间进阶（2026-10-05）：AI 每维度给出 evidence（引用原文的一句话依据），
        # 前端随分数展示；规则路径无 evidence 则不下发该键。
        evidence = None
        if ai_used:
            ev = {}
            for dim in ('speed', 'emotion', 'interaction', 'selling'):
                t = str(feedback.get(dim + '_evidence', '') or '').strip()[:120]
                if t:
                    ev[dim + '_score'] = t
            if ev:
                evidence = ev
        fb_body = {
            "speed_score": scores[0],
            "emotion_score": scores[1],
            "interaction_score": scores[2],
            "selling_score": scores[3],
            "overall_score": round(sum(scores) / 4),
            "summary": final_summary,
            "suggestions": final_suggestions[:3],
            # EC2：把「这个分是谁给的」明确下发，前端据此标注，不再冒充 AI 评分。
            "source": "ai" if ai_used else "rule",
            "source_note": "" if ai_used else "本次未采用 AI 评分，分数由规则分析给出（可复现，仅反映文本特征）"
        }
        if evidence:
            fb_body["evidence"] = evidence
        return jsonify({"success": True, "feedback": fb_body})
    except Exception as e:
        # EC2/EC5：AI 失败必须可见 —— 不再无声地拿规则分冒充 AI 评分。
        logger.error(f"AI评分失败: {e}")
        s, e, i, se = analyze_script(script_text)
        suggestions = generate_suggestions(s, e, i, se, script_text)
        return jsonify({"success": True, "feedback": {
            "speed_score": s, "emotion_score": e, "interaction_score": i, "selling_score": se,
            "overall_score": round((s + e + i + se) / 4),
            "summary": "本次未能调用 AI，以下为规则分析结果",
            "suggestions": suggestions,
            "source": "rule",
            "source_note": "AI 调用失败，分数由规则分析给出（可复现，仅反映文本特征）"
        }})


# ==================== 直播实训：朗读实录分析 + 落库 ====================

# 必卖点 rubric（EC3/EC4）。每一项写明「怎样算命中」，使评价**可复现、可解释**，
# 而不是给学员一个说不清由来的裸分。与农技板块「能给依据才给结论」的口径一致。
_LIVE_RUBRIC = (
    ('开场钩子', r'家人们|宝子们|姐妹们|各位|大家|欢迎|开播|来啦|看过来'),
    ('产地来源', r'广东|岭南|产地|原产|本地|种植|养殖|产区|果园|农场'),
    ('规格品相', r'斤|克|公斤|规格|果径|大小|个头|品相|颗|箱|份|装|袋'),
    ('口感特点', r'甜|香|鲜|脆|嫩|糯|口感|风味|好吃|品质|汁水'),
    # P2-5（2026-10-05 走查）：价格项要求「数字 + 价格单位/优惠词」，纯问价（多少钱/划算吗）
    # 不再误判为「已命中价格信息」——学员必须真的报出价格才算讲到位。
    ('价格信息', r'\d+(?:\.\d+)?\s*(?:元|块|块钱|折|包邮|券|优惠)'),
    ('售后保障', r'售后|退|换|赔|保障|包退|包赔|放心|时效'),
    ('互动引导', r'扣|点赞|关注|想要的|评论区|下单|链接|购买|拍|点个赞'),
)
_LIVE_RUBRIC_RE = tuple((name, re.compile(pat)) for name, pat in _LIVE_RUBRIC)

# 直播带货的舒适语速带（汉字/分钟）。这是**真正可测**的语速：
# 由「识别到的字数 ÷ 实际朗读秒数」得出，取代此前靠数标点符号估算的假「语速节奏」。
_LIVE_SPEED_IDEAL = (180, 300)


def _live_cjk(s):
    """只保留汉字，规避标点 / 空白 / 数字对字数与覆盖率计算的干扰。"""
    return re.sub(r'[^\u4e00-\u9fff]', '', s or '')


def _live_speed_score(cpm):
    lo, hi = _LIVE_SPEED_IDEAL
    if cpm <= 0:
        return 0
    if lo <= cpm <= hi:
        return 100
    if cpm < lo:
        return max(40, int(100 - (lo - cpm) * 100.0 / lo))
    return max(40, int(100 - (cpm - hi) * 100.0 / (hi * 1.2)))


@app.route('/api/ecommerce/live/report', methods=['POST'])
def live_reading_report():
    """朗读实录分析：把「学员现场说了什么」变成可复现的指标（EC3/EC4）。

    与 `/api/ecommerce/feedback` 的分工：
      · feedback 评的是**稿子的文本质量**；
      · 本接口评的是**学员朗读时的实际表现** —— 完成度 / 真实语速 / 必卖点命中 / 冷场。
    不调用 AI、不含随机数：同样的输入必然得到同样的输出。
    """
    data = request.get_json() or {}
    script = str(data.get('script', '') or '')
    transcript = str(data.get('transcript', '') or '')

    def _f(v):
        try:
            return float(v or 0)
        except (TypeError, ValueError):
            return 0.0

    duration = _f(data.get('duration_sec'))
    max_silence = _f(data.get('max_silence_sec'))

    if not transcript.strip():
        return jsonify({"success": False, "code": "empty_transcript",
                        "message": "还没有识别到朗读内容"}), 400
    if len(transcript) > EC_LIVE_TRANSCRIPT_MAX_LEN:
        return jsonify({"success": False, "code": "transcript_too_long",
                        "message": "朗读内容过长"}), 400

    # ① 完成度：稿子里的汉字被念出来的比例（按字去重，避免重复朗读刷分）
    script_chars = set(_live_cjk(script))
    said_chars = set(_live_cjk(transcript))
    missed_chars = script_chars - said_chars
    coverage = round(len(script_chars & said_chars) * 100.0 / len(script_chars)) if script_chars else 0

    # ② 真实语速
    spoken_chars = len(_live_cjk(transcript))
    cpm = round(spoken_chars / (duration / 60.0)) if duration > 0 else 0
    speed_score = _live_speed_score(cpm)

    # ③ 必卖点命中 —— 逐项给出「稿里有没有 / 嘴上有没有」
    items = []
    hit = 0
    for name, rx in _LIVE_RUBRIC_RE:
        in_script = bool(rx.search(script))
        said = bool(rx.search(transcript))
        items.append({"name": name, "in_script": in_script, "said": said})
        if said:
            hit += 1
    rubric_score = round(hit * 100.0 / len(_LIVE_RUBRIC_RE))

    # ④ 冷场
    silence_penalty = 15 if max_silence >= 10 else (8 if max_silence >= 6 else 0)

    overall = max(0, min(100, round(rubric_score * 0.5 + coverage * 0.3 + speed_score * 0.2)
                         - silence_penalty))

    tips = []
    for it in items:
        if it['in_script'] and not it['said']:
            tips.append('稿子里写了「%s」但朗读时没有说出来' % it['name'])
        elif not it['in_script']:
            tips.append('稿子里缺少「%s」这一项' % it['name'])
    if missed_chars:
        tips.append('稿子里有 %d 个字没有念到' % len(missed_chars))
    if cpm and cpm < _LIVE_SPEED_IDEAL[0]:
        tips.append('语速偏慢（约 %d 字/分钟），可适当加快' % cpm)
    elif cpm > _LIVE_SPEED_IDEAL[1]:
        tips.append('语速偏快（约 %d 字/分钟），注意留出停顿' % cpm)
    if max_silence >= 6:
        tips.append('最长冷场约 %.1f 秒；直播中超过 5 秒不说话，观众容易流失' % max_silence)

    return jsonify({"success": True, "report": {
        "coverage": coverage,
        "missed_chars": len(missed_chars),
        "spoken_chars": spoken_chars,
        "duration_sec": round(duration, 1),
        "speed_cpm": cpm,
        "speed_score": speed_score,
        "rubric_score": rubric_score,
        "rubric_hit": hit,
        "rubric_total": len(_LIVE_RUBRIC_RE),
        "rubric_items": items,
        "max_silence_sec": round(max_silence, 1),
        "silence_penalty": silence_penalty,
        "overall_score": overall,
        "tips": tips[:5],
        "source": "rule",
        "source_note": "本组指标由规则分析给出（可复现），不含 AI 评分。"
    }})


@app.route('/api/ecommerce/live/comments', methods=['POST'])
def live_ai_comments():
    """观众提问（2026-10-05 直播间进阶·题库化）：按学员刚说的内容生成 1-2 条针对性提问。

    走 `_chat_model()`；失败或限流时由前端回退到规则评论池（本接口不返回兜底，
    由前端决定，避免「AI 失败却拿到看似正常的评论」不可见）。
    """
    data = request.get_json() or {}
    speech = str(data.get('speech', '') or '').strip()[:300]
    difficulty = str(data.get('difficulty', '') or '新手').strip()[:8] or '新手'

    if _rate_limited('ec-comments:' + _client_key(), EC_RATE_COMMENTS_LIMIT):
        return jsonify({"success": False, "code": "rate_limited",
                        "message": "请求过于频繁，请稍后再试"}), 429
    if not speech:
        return jsonify({"success": False, "code": "empty_speech",
                        "message": "没有收到主播说的话"}), 400

    tone = {
        '新手': '友善、好奇，顺着主播的话提问',
        '进阶': '会比较、会质疑（比价、追问依据）',
        '挑战': '挑剔甚至带攻击性，可能提售后维权、要求看检测报告',
    }.get(difficulty, '友善、好奇')

    try:
        result = _chat_completion(
            messages=[
                {"role": "system", "content":
                    "你是农产品直播间的观众。根据主播刚说的话，生成 1-2 条你会发的弹幕提问，"
                    "语气要求：" + tone + "。只输出严格 JSON：{\"comments\":[\"...\",\"...\"]}，"
                    "每条不超过 30 字，不要输出其他文字。"},
                {"role": "user", "content": "主播刚说：「" + speech + "」"},
            ],
            temperature=0.8,
            max_tokens=120 + AI_REASONING_TOKEN_RESERVE,
            timeout=20,
            model=_chat_model()
        )
        m = re.search(r'\{.*?\}', result, re.DOTALL)
        obj = json.loads(m.group()) if m else {}
        comments = [str(c).strip()[:60] for c in (obj.get('comments') or []) if str(c).strip()][:2]
        if comments:
            return jsonify({"success": True, "comments": comments, "source": "ai"})
        return jsonify({"success": False, "code": "ai_empty",
                        "message": "上游未返回有效评论"}), 503
    except Exception as e:
        logger.error(f"观众提问生成失败: {e}")
        return jsonify({"success": False, "code": "ai_unavailable",
                        "message": "AI 评论暂不可用"}), 503


# 实训提交状态 → 中文标签（学员端与教师端共用，避免两处各写一套字符串）
_TRAINING_STATUS_LABELS = {
    'pending': '待提交',
    'submitted': '待批改',
    'graded': '已批改',
    'resubmitted': '已重新提交·待复核',
}


def _training_status_label(status):
    return _TRAINING_STATUS_LABELS.get((status or '').strip(), '待批改')


def _training_submit_core(kind):
    """把一次实训落库到既有作业链路（EC7 + 2026-10-05 文案/客服闭环）。

    kind ∈ {'live','copy','cs'}：落点都是 `assignments` + `assignment_submissions`，
    只以题目 title 前缀区分（见 database.TRAINING_TITLE_FMTS）。
    需要登录；同一学员同一作物同一 kind 只保留最新一次提交，attempts 递增。
    """
    user = _get_session_user()
    if not user:
        return jsonify({"success": False, "code": "login_required",
                        "message": "登录后即可保存实训记录"}), 401

    data = request.get_json() or {}
    product = str(data.get('product', '') or '').strip()
    if kind == 'cs':
        # 客服对练的产品是自由文本（学员可自填，如「增城桂味荔枝」），
        # 与模拟对话接口 `simulate_customer_service` 的口径一致：不做白名单，
        # 只做非空 + 长度校验，避免 prompt 注入面并防止作业标题无限膨胀。
        if not product:
            return jsonify({"success": False, "code": "empty_product",
                            "message": "请填写产品名称"}), 400
        product = product[:30]
    else:
        if not _ec_product_ok(product):
            return jsonify({"success": False, "code": "unknown_product",
                            "message": "暂不支持该农产品，请从列表中选择"}), 400

    meta = data.get('meta') if isinstance(data.get('meta'), dict) else {}
    payload = {"type": kind + "_training", "product": product, "meta": meta}

    if kind == 'cs':
        transcript = data.get('transcript')
        if not isinstance(transcript, list) or not transcript:
            return jsonify({"success": False, "code": "empty_transcript",
                            "message": "请先完成至少一轮对话再提交"}), 400
        turns = []
        for t in transcript[:EC_CS_TRANSCRIPT_MAX_TURNS]:
            if not isinstance(t, dict):
                continue
            turns.append({
                "role": str(t.get('role', '') or '')[:12],
                "content": str(t.get('content', '') or '')[:EC_CS_TURN_MAX_LEN],
            })
        if not turns:
            return jsonify({"success": False, "code": "empty_transcript",
                            "message": "对话记录为空"}), 400
        payload['transcript'] = turns
        score_raw = data.get('score')
    else:
        script = str(data.get('script', '') or '')
        cap = EC_COPY_MAX_LEN if kind == 'copy' else EC_SCRIPT_MAX_LEN
        if not script.strip():
            return jsonify({"success": False, "code": "empty_script",
                            "message": "请先写出或生成你的内容"}), 400
        if len(script) > cap:
            return jsonify({"success": False, "code": "script_too_long",
                            "message": f"内容过长，请控制在 {cap} 字以内"}), 400
        payload['script'] = script
        if kind == 'live':
            fb = data.get('feedback') if isinstance(data.get('feedback'), dict) else {}
            rp = data.get('report') if isinstance(data.get('report'), dict) else {}
            payload['feedback'] = fb
            payload['report'] = rp
            score_raw = fb.get('overall_score')
        else:
            score_raw = data.get('score')

    try:
        overall = int(score_raw or 0)
    except (TypeError, ValueError):
        overall = 0

    student_id = str(user.get('username') or user.get('id') or '')
    if not student_id:
        return jsonify({"success": False, "code": "login_required",
                        "message": "登录后即可保存实训记录"}), 401

    aid = database.get_or_create_training_assignment(product, kind)
    sid, attempts = database.save_live_training(aid, student_id, payload, overall)
    # ⚠️ 只回 rule_score（系统规则分）。score 列现在是**教师批改分**，
    #    提交接口不该回一个自己刚算出来的规则分冒充「分数」。
    return jsonify({"success": True, "submission_id": sid, "assignment_id": aid,
                    "attempts": attempts, "rule_score": overall})


@app.route('/api/ecommerce/live/submit', methods=['POST'])
def submit_live_training():
    """直播带货实训提交（话术稿 + 评分 + 朗读实录），需要登录。"""
    return _training_submit_core('live')


@app.route('/api/ecommerce/copy/submit', methods=['POST'])
def submit_copy_training():
    """商品文案实训提交（学员改写的「我的稿」），需要登录。"""
    return _training_submit_core('copy')


@app.route('/api/ecommerce/cs/submit', methods=['POST'])
def submit_cs_training():
    """客服对练实训提交（完整对话记录 + 规则评分），需要登录。"""
    return _training_submit_core('cs')


@app.route('/api/ecommerce/live/records', methods=['GET'])
def get_my_live_trainings():
    """当前登录学员的实训记录（每个作物一条）。

    `?kind=` 可取 live（默认）/ copy / cs；只认 database.TRAINING_TITLE_FMTS 里的键。
    """
    user = _get_session_user()
    if not user:
        return jsonify({"success": False, "code": "login_required",
                        "message": "登录后可查看实训记录"}), 401
    student_id = str(user.get('username') or user.get('id') or '')
    kind = str(request.args.get('kind', '') or 'live').strip()
    if kind not in database.TRAINING_TITLE_FMTS:
        kind = 'live'
    rows = database.get_trainings(student_id, kind)
    out = []
    for r in rows:
        try:
            detail = json.loads(r.get('content') or '{}')
        except Exception:
            detail = {}
        out.append({
            "id": r.get('id'),
            "assignment_title": r.get('assignment_title'),
            "product": detail.get('product'),
            # score = 教师批改分（未批改为 None）；系统规则分单独给 rule_score，
            # 两者不能混为一谈（2026-10-07 前 score 被规则分占用，学员端把规则分当成了最终成绩）。
            "score": r.get('score'),
            "rule_score": detail.get('rule_score'),
            "status": r.get('status'),
            "status_label": _training_status_label(r.get('status')),
            "attempts": detail.get('attempts', 1),
            "submitted_at": r.get('submitted_at'),
            "graded_at": r.get('graded_at'),
            "feedback": r.get('feedback') or '',
            "report": detail.get('report') or {},
            "feedback_detail": detail.get('feedback') or {},
            "meta": detail.get('meta') or {},
        })
    return jsonify({"success": True, "records": out, "kind": kind})


@app.route('/api/ecommerce/copywriting', methods=['POST'])
def generate_copywriting():
    """AI生成商品文案 - 支持多种格式"""
    data = request.get_json() or {}
    product = str(data.get('product', '') or '').strip() or '荔枝'
    fmt = str(data.get('format', '') or '').strip() or '详情页'
    audience = data.get('audience', '')
    selling_points = data.get('selling_points', '')
    tone = data.get('tone', '')

    # EC6/EC9：本接口此前既无限流也无校验，与 /script 一并对齐。
    if _rate_limited('ec-copy:' + _client_key(), EC_RATE_COPY_LIMIT):
        return jsonify({"success": False, "code": "rate_limited",
                        "message": "请求过于频繁，请稍后再试"}), 429
    if not _ec_product_ok(product):
        return jsonify({"success": False, "code": "unknown_product",
                        "message": "暂不支持该农产品，请从列表中选择"}), 400
    if fmt not in EC_COPY_FORMATS:
        return jsonify({"success": False, "code": "unknown_format",
                        "message": "不支持的文案类型"}), 400

    format_prompts = {
        '详情页': {
            'desc': '电商商品详情页文案',
            'structure': '包含：吸引眼球的主标题（10字内）→ 副标题（一句话卖点）→ 5-8个核心卖点（每个配小标题+1-2句描述）→ 使用场景（2-3个）→ 品质承诺 → 促单话术',
            'style': '专业可信，层次分明，卖点突出，适合长图文排版'
        },
        '主图文案': {
            'desc': '电商主图/轮播图上的短文案',
            'structure': '生成5条独立的主图文案，每条8-15字，要求：第1条突出核心卖点，第2条突出价格优势，第3条突出产地/品质，第4条突出促销活动，第5条突出情感/场景',
            'style': '简洁有力，一击即中，适合小空间展示'
        },
        '朋友圈': {
            'desc': '微信朋友圈推广文案',
            'structure': '包含：生活化开场（1句）→ 产品体验描述（2-3句，用五感描写）→ 信任背书（1句）→ 互动引导（1句）→ 适当emoji，总长度150字内',
            'style': '真实自然，像朋友分享而非广告，有生活气息'
        },
        '小红书': {
            'desc': '小红书种草笔记',
            'structure': '包含：吸睛标题（带emoji，15字内）→ 开头hook（1句，制造好奇）→ 产品体验（3-4句，真实感受）→ 使用tips（2-3条）→ 总结推荐 → 标签推荐（5-8个）',
            'style': '种草感强，真实分享，有闺蜜推荐的感觉，多用emoji和口语化表达'
        },
        '短视频脚本': {
            'desc': '15-30秒短视频带货脚本',
            'structure': '按时间轴输出：【0-3秒】开场hook（制造悬念/反差）→ 【3-8秒】展示产品（描述外观/特点）→ 【8-15秒】核心卖点+使用场景 → 【15-20秒】价格促单 → 【20-25秒】行动指令',
            'style': '节奏紧凑，口语化，适合朗读，每句标注时间点'
        }
    }

    config = format_prompts.get(fmt, format_prompts['详情页'])
    extra = []
    if audience:
        extra.append(f"目标人群：{audience}")
    if selling_points:
        extra.append(f"必须包含的卖点：{selling_points}")
    if tone:
        extra.append(f"语调要求：{tone}")
    extra_text = '\n'.join(extra) if extra else ''

    try:
        result = call_ai_service(
            system_prompt=f"""你是顶级电商文案专家，擅长为广东特色农产品撰写高转化率文案。

【文案类型】{config['desc']}
【输出结构】{config['structure']}
【风格要求】{config['style']}

【通用要求】
- 语言生动有画面感，避免空洞的"品质保证"类套话
- 善用场景、情感、对比等说服技巧；**具体数据一律不要自行编造**
- 突出广东/岭南地域特色和产品差异化优势
- 输出格式清晰，用markdown排版

{_EC_PROMO_RULE}""",
            user_message=f"请为「{product}」撰写{fmt}文案。\n{extra_text}",
            model=_chat_model()
        )
        return jsonify({"success": True, "copywriting": result, "format": fmt})
    except Exception as e:
        # EC5：与 /script 一致 —— 降级必须可见。
        logger.error(f"文案生成失败: {e}")
        fallback = generate_fallback_copywriting(product, fmt)
        return jsonify({"success": True, "degraded": True,
                        "copywriting": fallback, "format": fmt})


def generate_fallback_copywriting(product, fmt):
    """生成fallback文案"""
    if fmt == '详情页':
        return f"""## {product} · 岭南鲜味直达

### 一口入夏，满嘴甘甜

**核心卖点**
- **产地直供** — 来自广东产区（【待填写：具体产区】）
- **严选品质** — 【待填写：等级 / 规格等真实描述】
- **新鲜直达** — 【待填写：采摘与发货时效】
- **安心保障** — 【待填写：检测项目与报告】

**适用场景**
- 夏日冰镇鲜食，消暑解渴
- 送礼佳品，精美礼盒装
- 家庭分享，亲子时光

**品质承诺**
【待填写：售后与赔付政策，须与平台实际规则一致】

> 【待填写：优惠活动】"""

    elif fmt == '主图文案':
        return f"""**主图文案（5条）**

1. **岭南直供·{product}** — 核心卖点
2. **【待填写：到手价】** — 价格优势
3. **【待填写：发货时效】** — 品质保障
4. **【待填写：促销活动】** — 促销活动
5. **【待填写：情感场景文案】** — 情感场景"""

    elif fmt == '朋友圈':
        return f"""今天收到了从广东寄来的{product}🌿

【待填写：开箱与外观的真实感受】

产地直发的，图的就是一个新鲜。

想尝鲜的朋友扣1，我发链接给你们～"""

    elif fmt == '小红书':
        return f"""🌿广东人的夏天，从这口{product}开始！

姐妹们！！这个{product}真的绝了😭 从广东产地直发的，打开箱子那股清香直接梦回岭南～

✨真实体验：
• 【待填写：外观 / 品相的真实描述】
• 【待填写：口感 / 风味的真实描述】
• 【待填写：与同类相比的真实差异】
• 【待填写：复购理由】

💡小tips：
1. 【待填写：保存 / 食用建议】
2. 【待填写：规格选择建议】
3. 【待填写：当前优惠，若无则删除本条】

#广东美食 #时令水果 #夏日限定 #吃货日记 #好物分享"""

    else:
        return f"""**短视频脚本（25秒）**

**【0-3秒】开场hook**
"广东人夏天最馋的水果，你猜是什么？"

**【3-8秒】产品展示**
（镜头给到{product}特写）
"看这个品相，【待填写：按实际外观描述】，从广东产地直发的。"

**【8-15秒】核心卖点**
（展示产品实际形态）
"【待填写：口感与卖点，按真实情况描述】"

**【15-20秒】价格促单**
"【待填写：直播间价与优惠】"

**【20-25秒】行动指令**
"想要的赶紧点下方链接，手慢无！" """


# ---- 文案实训评分（2026-10-05 走查 P1-2）：纯规则、可复现，不依赖 AI ----
# 与直播话术的 /api/ecommerce/feedback 分开：文案评的是「结构/卖点/格式契合/合规」，
# 且长度上限按文案的 EC_COPY_MAX_LEN。打分依据逐项给出，让学员知道分从哪来。


def _copy_score(text, fmt):
    """规则评分商品文案（0-100，四维）。可复现、无随机数。"""
    t = text or ''
    n = len(t)

    # ① 结构完整度：是否有标题/分点/换行分层
    has_heading = bool(re.search(r'(?:^|\n)\s*(?:##|###|【|\d{1,2}[.、])', t))
    has_multi_line = t.count('\n') >= 3
    structure = 50 + (20 if has_heading else 0) + (15 if has_multi_line else 0) + \
        min(10, t.count('\n') // 2)

    # ② 卖点具体度：命中的具体描述词越多分越高（避免空话）
    selling_kw = re.findall(r'甜|香|鲜|脆|嫩|糯|口感|风味|产地|直发|冷链|规格|新鲜|品质|果肉|核|汁', t)
    selling = 45 + min(len(set(selling_kw)) * 6, 40) + (15 if len(t) >= 120 else 0)

    # ③ 格式契合度：按所选格式的典型特征（主图短句 / 短视频时间轴 / 朋友圈 emoji 等）
    fmt_fit = 60
    if fmt == '主图文案':
        fmt_fit += 15 if re.search(r'\d{1,2}[.、]', t) else 0
        fmt_fit += 10 if len(t) < 300 else 0
    elif fmt == '短视频脚本':
        fmt_fit += 15 if re.search(r'\d+[-~]\d+\s*秒', t) else 0
    elif fmt == '朋友圈':
        fmt_fit += 10 if len(t) < 200 else 0
    elif fmt == '小红书':
        fmt_fit += 10 if re.search(r'#\S+|emoji|姐妹|家人们', t) else 0
    else:  # 详情页
        fmt_fit += 15 if re.search(r'(?:^|\n)\s*(?:##|###)', t) else 0
    fmt_fit = min(98, fmt_fit)

    # ④ 合规自检：残留【待填写】或绝对化用语扣分
    compliance = 100
    todo_count = t.count('【待填写')
    compliance -= min(todo_count * 6, 30)          # 未补真实信息扣分
    if re.search(r'全网最低|第一|最好|绝对|顶级|唯一', t):
        compliance -= 20                            # 绝对化用语扣分
    compliance = max(30, compliance)

    overall = round((structure + selling + fmt_fit + compliance) / 4)
    tips = []
    if todo_count:
        tips.append('还有 %d 处【待填写】没有换成真实信息' % todo_count)
    if re.search(r'全网最低|第一|最好|绝对|顶级|唯一', t):
        tips.append('避免「全网最低/第一/最好」等绝对化用语')
    if n < 80:
        tips.append('篇幅偏短，建议补充卖点与场景细节')
    return {
        "structure_score": min(98, structure),
        "selling_score": min(98, selling),
        "format_score": fmt_fit,
        "compliance_score": compliance,
        "overall_score": overall,
        "suggestions": (tips or ['结构完整、卖点具体，整体不错']) + ['评分由规则分析给出（可复现）'],
        "source": "rule",
        "source_note": "文案评分由规则分析给出（可复现，不含 AI 评分）"
    }


@app.route('/api/ecommerce/copy/feedback', methods=['POST'])
def copy_feedback():
    """商品文案规则评分（2026-10-05 走查 P1-2）。纯规则、可复现，无 AI 依赖。"""
    data = request.get_json() or {}
    text = str(data.get('script', '') or '')
    fmt = str(data.get('format', '') or '详情页').strip()
    if _rate_limited('ec-copy-feedback:' + _client_key(), EC_RATE_FEEDBACK_LIMIT):
        return jsonify({"success": False, "code": "rate_limited",
                        "message": "请求过于频繁，请稍后再试"}), 429
    if not text.strip():
        return jsonify({"success": False, "code": "empty_script",
                        "message": "请先写出你的文案"}), 400
    if len(text) > EC_COPY_MAX_LEN:
        return jsonify({"success": False, "code": "script_too_long",
                        "message": f"文案过长，请控制在 {EC_COPY_MAX_LEN} 字以内"}), 400
    return jsonify({"success": True, "feedback": _copy_score(text, fmt)})


def _sentiment_from_score(total):
    """体验优化⑥（2026-10-06）：把本轮学员回复质量映射为客户情绪信号。

    纯规则、无随机，供前端「客户情绪温度条」展示。返回 0-100 的满意度 + 文案标签。
    """
    if total >= 85:
        return {'level': 90, 'label': '满意'}
    if total >= 70:
        return {'level': 72, 'label': '较满意'}
    if total >= 55:
        return {'level': 52, 'label': '一般'}
    return {'level': 32, 'label': '不满'}


@app.route('/api/ecommerce/customer-service', methods=['POST'])
def simulate_customer_service():
    """AI客服模拟 - 多场景、多性格、实时评分"""
    data = request.get_json() or {}
    message = str(data.get('message', '') or '')
    history = data.get('history', [])
    scenario = data.get('scenario', '售前咨询')
    difficulty = data.get('difficulty', '进阶')
    personality = data.get('personality', '友善型')
    # 本模块的产品是**自由文本**（学员可自填），不做白名单，但必须限长，避免 prompt 注入面。
    product = str(data.get('product', '') or '').strip()[:30] or '农产品'

    # EC6：逐轮对话型接口，此前同样无限流。限额按「一轮一次调用」放宽。
    if _rate_limited('ec-cs:' + _client_key(), EC_RATE_CS_LIMIT):
        return jsonify({"success": False, "code": "rate_limited",
                        "message": "对话过于频繁，请稍后再试"}), 429
    if not message.strip():
        return jsonify({"success": False, "code": "empty_message",
                        "message": "请先输入你的回复"}), 400

    # 场景配置
    scenario_config = {
        '售前咨询': {
            'desc': '客户询问产品信息、价格、发货等',
            'customer_prompts': [
                '我想买{product}，新鲜吗？', '你们的{product}多少钱？', '{product}甜不甜？',
                '发货快吗？几天能到？', '有没有礼盒装？', '可以试吃吗？',
                '你们的{product}和别家有什么区别？', '产地是哪里的？'
            ]
        },
        '售后处理': {
            'desc': '客户收到货后反馈问题',
            'customer_prompts': [
                '我收到的{product}有几个坏的', '收到的和图片不一样啊',
                '物流太慢了，等了好久', '口感没有描述的那么好',
                '我要退货，怎么操作？', '包装破了，{product}都压坏了',
                '发错货了，我订的不是这个', '怎么和上次买的不一样？'
            ]
        },
        '投诉应对': {
            'desc': '客户情绪激动，需要安抚和解决',
            'customer_prompts': [
                '你们这是什么质量！太差了！', '我要投诉你们！太坑了！',
                '再也不买了，骗子！', '我要给差评！退款！',
                '等了一个星期还没到，什么意思？', '客服在吗？怎么一直不回复？',
                '你们是不是卖假货？', '我要找平台介入！'
            ]
        },
        '议价谈判': {
            'desc': '客户要求优惠、降价、赠品',
            'customer_prompts': [
                '能便宜点吗？', '买多几箱有优惠吗？', '别家比你们便宜啊',
                '送点赠品呗', '老客户了，给个优惠价', '零头去掉行不行？',
                '下次还买能打折吗？', '我介绍朋友来买，能便宜不？'
            ]
        },
        '产品推荐': {
            'desc': '客户不确定买什么，需要推荐',
            'customer_prompts': [
                '你们有什么好吃的推荐？', '送人买什么比较好？',
                '第一次买，选哪个品种？', '家里老人吃什么合适？',
                '哪个性价比最高？', '有没有适合煲汤的？',
                '当季有什么新鲜的？', '我想买点特产，有推荐吗？'
            ]
        }
    }

    # 客户性格配置
    personality_config = {
        '友善型': '语气友好、有耐心、好说话，容易被说服',
        '急躁型': '语气急躁、没耐心、喜欢催促，需要快速回应',
        '犹豫型': '犹豫不决、反复比较、需要更多说服和信心',
        '挑剔型': '要求高、爱挑毛病、注重细节、不好糊弄'
    }

    sc = scenario_config.get(scenario, scenario_config['售前咨询'])
    pc = personality_config.get(personality, personality_config['友善型'])

    # 难度调整
    diff_prompt = {
        '新手': '客户问题简单直接，容易回答，不太会追问',
        '进阶': '客户会追问细节、比较竞品，需要专业回答',
        '挑战': '客户很挑剔、会质疑回答、要求证据、不好对付'
    }

    system_prompt = f"""【重要】你必须只扮演客户角色，绝对不能扮演客服！

你的身份：一个想买{product}的网购客户。
性格：{pc}
场景：{scenario}（{sc['desc']}）
难度：{diff_prompt.get(difficulty, diff_prompt['进阶'])}

【你只能说客户该说的话】
- 提出问题、表达顾虑、追问细节
- 对客服的回答表示满意或不满
- 提出新的要求或疑虑
- 绝对不能说"亲""您好""帮您处理"等客服用语

【对话节奏】
- 客服回答好 → 表示认可，可以追问或说"那行，我下单了"
- 客服回答差 → 追问、质疑、表达不满
- 客服没解决问题 → 继续追问，不要轻易放过

【回复要求】
- 不超过60字
- 口语化，像真人在聊天
- 不要输出括号里的动作描述
- 不要输出任何解释，只输出客户说的话"""

    try:
        messages = [{"role": "system", "content": system_prompt}]
        for h in history[-8:]:
            messages.append({"role": h.get('role', 'user'), "content": h.get('content', '')})
        messages.append({"role": "user", "content": message})

        # EC10：原先这里是**裸 requests.post**，绕过了统一入口 _chat_completion ——
        # 既缺上游响应结构校验（空正文会被静默当成有效回复），也违反本项目
        # 「所有 AI 调用一律走 _chat_completion / call_ai_service」这条红线。现改回统一入口。
        reply = _chat_completion(
            messages, temperature=0.7,
            max_tokens=200 + AI_REASONING_TOKEN_RESERVE,
            timeout=30, model=_chat_model()
        ).strip()

        # 分析客服表现（规则关键词评分，评的是**学员自己的回复**，对象正确）
        score = analyze_service_reply(message, reply, scenario, history, difficulty)
        sentiment = _sentiment_from_score(score['total'])

        return jsonify({"success": True, "reply": reply, "score": score, "sentiment": sentiment})
    except Exception as e:
        # EC5：降级必须可见。
        logger.error(f"客服模拟失败: {e}")
        # 根据对话历史和客服回复动态生成fallback
        reply = generate_dynamic_fallback(scenario, product, personality, history, message)
        score = analyze_service_reply(message, reply, scenario, history, difficulty)
        sentiment = _sentiment_from_score(score['total'])
        return jsonify({"success": True, "degraded": True, "reply": reply, "score": score,
                        "sentiment": sentiment})


def generate_dynamic_fallback(scenario, product, personality, history, last_reply):
    """根据对话上下文动态生成客户回复（不依赖AI）"""
    import random

    # 统计对话轮数
    rounds = len([h for h in history if h.get('role') == 'user'])

    # 分析客服回复的关键词
    has_apology = any(w in last_reply for w in ['抱歉', '不好意思', '对不起', 'sorry'])
    has_solution = any(w in last_reply for w in ['补发', '退款', '换货', '处理', '解决', '补偿'])
    has_data = any(w in last_reply for w in ['甜度', '产地', '品种', '规格', '检测', '冷链'])
    has_price = any(w in last_reply for w in ['优惠', '打折', '便宜', '减', '送'])
    has_greeting = any(w in last_reply for w in ['亲', '您好', '欢迎'])

    if scenario == '售前咨询':
        if rounds <= 1:
            options = [
                f"这个{product}到底新不新鲜啊？能发个实拍看看吗？",
                f"你们的{product}多少钱一斤？比别家贵不？",
                f"{product}是哪里产的？当季的吗？",
                f"我想买点{product}，发货快吗？几天能到？"
            ]
        elif has_data:
            options = [
                "听起来还不错，有没有买家秀看看？",
                "那和其他家比你们有什么优势？",
                "可以先买少一点试试吗？",
                "礼盒装多少钱？送人合适吗？"
            ]
        elif has_price:
            options = [
                "这个价格能再便宜点不？",
                "买多几箱有优惠吗？",
                "行吧，那我先下一单试试",
                "有没有满减活动？"
            ]
        else:
            options = [
                "嗯...我再看看吧",
                "你说的这些我不太懂，能简单点说吗？",
                "那你们售后怎么样？坏了怎么办？",
                "行，我考虑一下"
            ]

    elif scenario == '售后处理':
        if has_apology and has_solution:
            options = [
                "那行吧，你帮我处理一下",
                "补发的话多久能到？",
                "退款多久能到账？",
                "这次就算了，下次注意点"
            ]
        elif has_apology:
            options = [
                "光道歉有什么用，倒是给个解决方案啊",
                "我都等了好几天了，怎么处理？",
                "那你说怎么办吧"
            ]
        else:
            options = [
                f"我收到的{product}有几个坏的，你们怎么处理？",
                "你们客服怎么回事？半天不处理",
                "我要退货，怎么操作？",
                "包装都破了，东西都压坏了"
            ]

    elif scenario == '投诉应对':
        if rounds >= 4:
            options = [
                "行吧，这次就这样吧",
                "那你赶紧处理吧，我等着",
                "补偿就算了，下次别这样了",
                "我再信你们一次"
            ]
        elif has_apology:
            options = [
                "道歉有什么用？我要实际的解决方案！",
                "你们每次都这样说，有啥用？",
                "那你说怎么补偿吧"
            ]
        else:
            options = [
                "你们这是什么服务态度！太差了！",
                "我要投诉你们！太坑了！",
                "再也不买了，什么玩意儿！",
                "找你们领导来！"
            ]

    elif scenario == '议价谈判':
        if has_price:
            options = [
                "还是有点贵，再便宜点呗",
                "行吧，那你送点赠品",
                "那我先买一箱试试",
                "下次再来买能给老客户价不？"
            ]
        else:
            options = [
                "能便宜点吗？别家比你们便宜啊",
                "买两箱给个优惠价呗",
                "零头去掉行不行？",
                "送点赠品呗，我介绍朋友也来买"
            ]

    else:  # 产品推荐
        if rounds <= 1:
            options = [
                "你们有什么好吃的推荐？",
                "第一次来，哪个比较好？",
                "送人买什么合适？",
                "当季有什么新鲜的？"
            ]
        else:
            options = [
                "这个口感怎么样？甜不甜？",
                "那就要这个吧，怎么下单？",
                "有没有礼盒装的？",
                "行，我再看看其他的"
            ]

    # 根据性格调整
    if personality == '急躁型':
        options = [o + '！快点回复' if random.random() > 0.5 else o for o in options]
    elif personality == '挑剔型':
        if random.random() > 0.5:
            options.append('你确定没问题吧？我可不好糊弄')

    return random.choice(options)


def analyze_service_reply(customer_msg, ai_reply, scenario, history, difficulty='进阶'):
    """分析客服（用户）的回复质量。

    customer_msg = 学员（客服）这一句回复；history = 前端传来的对话历史
    （其中 role='assistant' 是 AI 客户、role='user' 是学员客服，均不含当前句）。
    据此额外判定「答非所问」：取客户上一句，看学员回复是否回应了它。
    """
    last_user_msg = customer_msg

    scores = {
        'politeness': 50,   # 礼貌度
        'professional': 50, # 专业度
        'solving': 50,      # 解决问题能力
        'empathy': 50,      # 同理心
    }
    tips = []

    # 礼貌度检测
    polite_words = ['亲', '您好', '感谢', '抱歉', '不好意思', '请', '麻烦', '感谢您']
    polite_count = sum(1 for w in polite_words if w in last_user_msg)
    scores['politeness'] = min(95, 50 + polite_count * 12)
    if polite_count == 0:
        tips.append('开头用"亲"或"您好"会更亲切')

    # 专业度检测
    pro_words = ['产地', '品种', '甜度', '规格', '发货', '冷链', '检测', '新鲜', '当季', '直发']
    pro_count = sum(1 for w in pro_words if w in last_user_msg)
    scores['professional'] = min(95, 45 + pro_count * 10)
    if pro_count < 2:
        tips.append('加入产品专业信息（产地、品种、规格）更有说服力')

    # 解决问题能力
    solving_words = ['可以', '没问题', '帮您', '给您', '安排', '处理', '解决方案', '补偿', '退款', '换货']
    solving_count = sum(1 for w in solving_words if w in last_user_msg)
    scores['solving'] = min(95, 40 + solving_count * 12)
    if solving_count < 2 and scenario in ['售后处理', '投诉应对']:
        tips.append('明确告诉客户解决方案，如"帮您补发""给您退款"')

    # 同理心检测
    empathy_words = ['理解', '抱歉', '不好意思', '确实', '换做我', '体谅', '心情', '感受']
    empathy_count = sum(1 for w in empathy_words if w in last_user_msg)
    scores['empathy'] = min(95, 40 + empathy_count * 15)
    if empathy_count == 0 and scenario in ['投诉应对', '售后处理']:
        tips.append('先表达理解和歉意，再解决问题效果更好')

    # ===== P1-2（2026-10-06 走查）：答非所问判定 =====
    # 取客户上一句（history 里最后一条 assistant = AI 客户），若学员回复与它
    # 毫无关联（既没回应关键词、也没给解决方案），则视为「答非所问」，整体降分。
    # 反之，正面回应了客户关注点，是「解决力」的核心体现，应给 solving 加分。
    if isinstance(history, list):
        last_customer = ''
        for h in reversed(history):
            if isinstance(h, dict) and h.get('role') == 'assistant':
                last_customer = str(h.get('content', '') or '')
                break
        if last_customer:
            # 客户上一句的「关注点」关键词（价格/品质/发货/售后/议价/推荐）
            concern_words = {
                'price': ['钱', '价格', '贵', '便宜', '优惠', '折', '包邮', '多少'],
                'quality': ['新鲜', '甜', '好吃', '品质', '质量', '口感', '坏', '破'],
                'delivery': ['发货', '几天', '到货', '快递', '物流', '到'],
                'aftersale': ['退货', '退款', '换货', '补偿', '处理', '投诉', '差评'],
                'recommend': ['推荐', '哪个', '选', '适合', '什么'],
            }
            concern = None
            for key, words in concern_words.items():
                if any(w in last_customer for w in words):
                    concern = key
                    break
            # 学员回复里「回应了客户关注点」的迹象
            respond_words = {
                'price': ['价', '元', '优惠', '折', '包邮', '划算', '活动', '送'],
                'quality': ['新鲜', '甜', '品质', '产地', '品种', '检测', '冷链', '口感'],
                'delivery': ['发货', '天', '顺丰', '快递', '物流', '到货', '加急'],
                'aftersale': ['退款', '退货', '换货', '补发', '补偿', '处理', '安排', '帮您', '解决'],
                'recommend': ['推荐', '这款', '适合', '送', '礼盒', '建议', '可以'],
            }
            if concern and concern in respond_words:
                responded = any(w in last_user_msg for w in respond_words[concern])
                if not responded:
                    # 答非所问：整体每项都打折，并给明确提示
                    for k in scores:
                        scores[k] = max(35, int(scores[k] * 0.6))
                    tips.insert(0, f'客户在问「{concern}」相关，你的回复没有正面回应')
                else:
                    # 正面回应客户关注点 = 解决力的核心，给 solving 加分；
                    # 同时「回应」本身就是专业 + 共情的体现，小幅提升这两维，
                    # 避免「正确报了价格」的学员因专业/同理基线分而显得不及格。
                    scores['solving'] = min(95, scores['solving'] + 20)
                    scores['professional'] = min(95, scores['professional'] + 10)
                    scores['empathy'] = min(95, scores['empathy'] + 8)
                    if scenario in ['售后处理', '投诉应对']:
                        scores['solving'] = min(95, scores['solving'] + 10)

    # 长度合理性
    if len(last_user_msg) < 10:
        tips.append('回复太短，客户可能觉得敷衍')
    elif len(last_user_msg) > 200:
        tips.append('回复太长，客户可能没耐心看完')

    total = round(sum(scores.values()) / 4)

    # ===== P3-8（2026-10-06）：难度加权 =====
    # 挑战难度下，简单/敷衍的回复应被压分，否则难度对评分零作用。
    if difficulty == '挑战':
        if len(last_user_msg) < 10:
            total = max(20, total - 12)
            tips.append('挑战难度下回复过于简单，客户会被"糊弄"激怒')
        elif total >= 80:
            # 挑战难度拿高分的门槛更高，轻微回压体现区分度
            total = total - 3

    # 通用建议
    if not tips:
        if total >= 85:
            tips.append('回复很棒！继续保持')
        elif total >= 70:
            tips.append('整体不错，可以再多一些情感表达')
        else:
            tips.append('多站在客户角度思考，理解他们的真实需求')

    return {
        'total': total,
        'details': scores,
        'tips': tips[:3]
    }


@app.route('/api/ecommerce/customer-service/next', methods=['POST'])
def get_next_customer_msg():
    """AI生成下一句客户消息（用于主动引导对话）"""
    data = request.get_json() or {}
    scenario = data.get('scenario', '售前咨询')
    personality = data.get('personality', '友善型')
    product = str(data.get('product', '') or '').strip()[:30] or '农产品'
    history = data.get('history', [])

    # EC6：补限流（本接口同样调用上游）。P3（2026-10-06）：辅助接口拆到 ec-cs-aux，
    # 避免频繁点「提示/开场白」挤占正常对话的 ec-cs 额度。
    if _rate_limited('ec-cs-aux:' + _client_key(), EC_RATE_CS_AUX_LIMIT):
        return jsonify({"success": False, "code": "rate_limited",
                        "message": "操作过于频繁，请稍后再试"}), 429

    sc_map = {
        '售前咨询': f'询问{product}的品质、价格、发货等信息',
        '售后处理': f'反馈收到的{product}有问题，要求处理',
        '投诉应对': f'对{product}或服务不满意，情绪激动',
        '议价谈判': f'想买{product}但要求优惠',
        '产品推荐': f'想买{product}但不确定选什么'
    }

    try:
        result = call_ai_service(
            system_prompt=f"""你是一个电商客户，性格：{personality}。
场景：{scenario}，{sc_map.get(scenario, '')}。
请生成一句自然的客户开场白或追问，不超过50字，口语化。
只输出客户说的话，不要其他内容。""",
            user_message="请生成一句客户消息",
            model=_chat_model()
        )
        return jsonify({"success": True, "message": result.strip()})
    except:
        fallback = {
            '售前咨询': f'你好，这个{product}怎么卖？',
            '售后处理': f'我收到的{product}有问题，怎么办？',
            '投诉应对': '你们客服呢？怎么半天不回复？',
            '议价谈判': '能便宜点不？',
            '产品推荐': '有什么推荐的吗？'
        }
        return jsonify({"success": True, "degraded": True, "message": fallback.get(scenario, '你好')})


@app.route('/api/ecommerce/customer-service/hint', methods=['POST'])
def get_service_hint():
    """根据当前对话动态生成回复建议"""
    data = request.get_json() or {}
    scenario = data.get('scenario', '售前咨询')
    personality = data.get('personality', '友善型')
    product = str(data.get('product', '') or '').strip()[:30] or '农产品'
    history = data.get('history', [])
    last_customer_msg = data.get('last_customer_msg', '')

    # EC6：补限流（本接口同样调用上游）。P3（2026-10-06）：辅助接口拆到 ec-cs-aux。
    if _rate_limited('ec-cs-aux:' + _client_key(), EC_RATE_CS_AUX_LIMIT):
        return jsonify({"success": False, "code": "rate_limited",
                        "message": "操作过于频繁，请稍后再试"}), 429

    # 获取最近的对话上下文
    recent = history[-4:] if len(history) > 4 else history
    context = '\n'.join(
        f"{'客户' if h.get('role') == 'assistant' else '客服'}：{h.get('content', '')}"
        for h in recent
    )

    try:
        result = call_ai_service(
            system_prompt=f"""你是客服培训专家。根据当前对话情况，给出具体的回复建议。

【场景】{scenario}，客户性格：{personality}，产品：{product}

【输出格式】严格JSON，不要其他文字：
{{
    "analysis": "客户当前的真实需求/情绪（15字内）",
    "strategy": "推荐的回复策略（15字内）",
    "templates": ["建议回复1（可直接复制使用）", "建议回复2", "建议回复3"],
    "tips": ["注意事项1", "注意事项2"]
}}

【要求】
- 建议回复要口语化、自然、不超过50字
- 根据客户性格调整语气（急躁的要快速回应，犹豫的要给信心）
- 根据对话阶段调整策略（初期多了解需求，中期解决问题，后期促单）""",
            user_message=f"最近对话：\n{context}\n\n客户最新消息：{last_customer_msg}\n\n请给出回复建议。",
            model=_chat_model()
        )
        import re, json
        json_match = re.search(r'\{.*?\}', result, re.DOTALL)
        hint = json.loads(json_match.group()) if json_match else {}
        return jsonify({"success": True, "hint": hint})
    except:
        # 根据对话上下文动态生成建议
        hint = generate_dynamic_hint(scenario, product, personality, last_customer_msg, history)
        return jsonify({"success": True, "degraded": True, "hint": hint})


def generate_dynamic_hint(scenario, product, personality, last_msg, history):
    """根据对话上下文动态生成回复建议（不虚构优惠/物流/赔付承诺）"""

    rounds = len([h for h in history if h.get('role') == 'user'])

    ask_price = any(w in last_msg for w in ['多少钱', '价格', '贵', '便宜', '优惠'])
    ask_quality = any(w in last_msg for w in ['新鲜', '甜', '好吃', '品质', '质量'])
    ask_delivery = any(w in last_msg for w in ['发货', '几天', '到货', '快递', '物流'])
    ask_refund = any(w in last_msg for w in ['退货', '退款', '换货', '坏了', '破损'])
    is_angry = any(w in last_msg for w in ['差评', '投诉', '骗子', '垃圾', '太差'])
    is_hesitating = any(w in last_msg for w in ['考虑', '想想', '再看看', '犹豫'])

    if scenario == '售前咨询':
        if ask_price:
            return {
                'analysis': '客户在关注价格',
                'strategy': '讲价值+按实际活动谈优惠',
                'templates': [
                    f'我们的{product}是产地直发，品质和性价比都不错，您可以先了解下规格',
                    '具体优惠以本店当前活动为准，您可以先看看商品详情页',
                    '您大概想买多少？量大我帮您看看有没有合适的方案'
                ],
                'tips': ['先讲价值再谈价格', '优惠以店铺实际活动为准，不要随口承诺']
            }
        elif ask_quality:
            return {
                'analysis': '客户在担心品质',
                'strategy': '用真实信息建立信任',
                'templates': [
                    f'{product}的甜度和新鲜度都不错，具体以您收到的实物为准',
                    '我们有相关的检测/实拍资料，稍后可以发您参考',
                    '很多老客户都回购，您可以看看真实评价'
                ],
                'tips': ['用真实信息说话', '有检测报告/实拍图就主动展示']
            }
        elif ask_delivery:
            return {
                'analysis': '客户关心物流时效',
                'strategy': '给明确预期但不虚构时效',
                'templates': [
                    '发货和物流时效以实际下单后为准，您可以关注物流信息',
                    '我们会尽快安排发出，具体到达时间视物流情况',
                    '您在哪个城市？我帮您估一下大致时效'
                ],
                'tips': ['给明确预期但不虚构时效', '物流以实际情况为准']
            }
        elif is_hesitating:
            return {
                'analysis': '客户在犹豫中',
                'strategy': '用真实卖点促单',
                'templates': [
                    f'{product}当季吃口感最好，错过要等明年了',
                    '您可以先少拿一点试试，觉得好再回购',
                    '有不清楚的随时问我，我帮您参谋'
                ],
                'tips': ['用真实卖点促单', '不要编造限时/限量优惠']
            }
        else:
            return {
                'analysis': '客户在了解产品',
                'strategy': '主动引导+了解需求',
                'templates': [
                    f'亲，您是自己吃还是送人呢？我帮您推荐',
                    f'我们的{product}当季新鲜，很多客户都回购',
                    '您有什么顾虑可以告诉我，我帮您解答'
                ],
                'tips': ['主动问客户需求', '用提问引导对话']
            }

    elif scenario == '售后处理':
        if ask_refund:
            return {
                'analysis': '客户要退换货',
                'strategy': '快速处理+减少损失',
                'templates': [
                    '亲，非常抱歉给您带来不便，马上帮您处理',
                    '您看是补发还是退款呢？我这边都可以',
                    '方便拍个照片给我看看吗？我好给您处理'
                ],
                'tips': ['先道歉再处理', '给客户选择权']
            }
        elif rounds <= 2:
            return {
                'analysis': '客户刚开始反馈问题',
                'strategy': '耐心倾听+了解详情',
                'templates': [
                    '亲，非常抱歉给您带来不好的体验',
                    '方便说下具体情况吗？我帮您核实',
                    '您放心，问题我们一定会跟进处理'
                ],
                'tips': ['先倾听再处理', '不要急着辩解']
            }
        else:
            return {
                'analysis': '客户等待解决方案',
                'strategy': '给出具体可执行的方案',
                'templates': [
                    '我这边马上帮您登记处理，您看补发方便吗？',
                    '给您退款可以吗？具体按本店售后流程办',
                    '这次真的很抱歉，后续我们一定改进'
                ],
                'tips': ['方案要具体可执行', '补偿按店铺实际政策，不口头承诺额外好处']
            }

    elif scenario == '投诉应对':
        if is_angry:
            return {
                'analysis': '客户情绪很激动',
                'strategy': '先安抚情绪再处理',
                'templates': [
                    '亲，真的很抱歉，您的心情我完全理解',
                    '这种情况确实不应该发生，我马上帮您处理',
                    '您先消消气，我一定给您一个明确答复'
                ],
                'tips': ['不要反驳', '让客户先发泄']
            }
        elif rounds >= 4:
            return {
                'analysis': '客户情绪已缓和',
                'strategy': '提出合规补偿方案',
                'templates': [
                    '给您申请一下本店当前的补偿方案可以吗？',
                    '这次我们按规则为您处理退款',
                    '后续您来都是按会员权益对待'
                ],
                'tips': ['补偿要有诚意且合规', '优惠/补偿以店铺实际政策为准']
            }
        else:
            return {
                'analysis': '客户在表达不满',
                'strategy': '真诚道歉+表达重视',
                'templates': [
                    '亲，真的很抱歉给您带来这么差的体验',
                    '您反馈的问题我们非常重视',
                    '我马上帮您处理，您看怎么处理比较合适？'
                ],
                'tips': ['态度要诚恳', '不要推卸责任']
            }

    elif scenario == '议价谈判':
        if rounds >= 3:
            return {
                'analysis': '客户多次议价',
                'strategy': '守价格底线+讲价值',
                'templates': [
                    f'亲，{product}这个价已经很有诚意了',
                    '您可以看看我们的品质，值这个价',
                    '您先拿一点试试，满意再回头'
                ],
                'tips': ['守住价格底线', '用价值代替降价']
            }
        elif ask_price:
            return {
                'analysis': '客户想要优惠',
                'strategy': '强调价值+按实际活动优惠',
                'templates': [
                    f'亲，{product}品质对得起这个价',
                    '具体优惠以本店当前活动为准，您可以先看看',
                    '您想买多少？我帮您看下合适的方案'
                ],
                'tips': ['先说价值再说优惠', '不虚构折扣']
            }
        else:
            return {
                'analysis': '客户在比较价格',
                'strategy': '突出差异化优势',
                'templates': [
                    '我们的和别家不一样的，您看这个品相',
                    '我们是产地直发，少中间环节',
                    '品质有保证，您可以先少拿点试'
                ],
                'tips': ['强调品质差异', '不编造绝对化承诺']
            }

    else:  # 产品推荐
        if rounds <= 1:
            return {
                'analysis': '客户需要推荐',
                'strategy': '问需求再推荐',
                'templates': [
                    '请问您是自己吃还是送人呢？',
                    '您喜欢甜一点的还是清淡一点的？',
                    f'现在当季的{product}最好吃，推荐您试试'
                ],
                'tips': ['先了解需求', '不要盲目推荐']
            }
        else:
            return {
                'analysis': '客户在考虑选择',
                'strategy': '精准推荐+打消顾虑',
                'templates': [
                    f'这款是最受欢迎的{product}，回头客很多',
                    '送人的话推荐礼盒装，包装更有面子',
                    '您要几斤的？我帮您推荐合适的规格'
                ],
                'tips': ['推荐1-2款就行', '说明推荐理由']
            }


# ==================== 手工技能API ====================

@app.route('/api/crafts/list', methods=['GET'])
def get_crafts_list():
    crafts = [
        {"id": "embroidery", "name": "广绣", "level": "入门级", "origin": "广州"},
        {"id": "woodcarving", "name": "潮汕木雕", "level": "进阶级", "origin": "潮汕"},
        {"id": "ceramics", "name": "石湾陶艺", "level": "中级", "origin": "佛山"},
        {"id": "lacquer", "name": "阳江漆器", "level": "高级", "origin": "阳江"}
    ]
    return jsonify({"success": True, "crafts": crafts})


@app.route('/api/crafts/<craft_id>', methods=['GET'])
def get_craft_detail(craft_id):
    if craft_id in CRAFTS_KNOWLEDGE:
        return jsonify({"success": True, "data": CRAFTS_KNOWLEDGE[craft_id]})
    return jsonify({"success": False, "message": "未找到该手工艺信息"})


# ==================== 农业技能扩展API（病虫害诊断） ====================

# 注：原内联在本文件的 PEST_KNOWLEDGE 已抽到 pest_data.py，见文件顶部 import。
# 抽出的原因：新增的「常见病虫害速查」与诊断的知识库降级需要读同一份数据，
# 内联在本文件里会出现两处事实源、互相漂移。

# ---- 诊断请求解析与提示词拼装 ----

# 前端提交的图片用 base64 data URL（JSON 通道），不用 multipart：
# 既有 apiCall 与 request.get_json() 都已是 JSON，改 multipart 会同时牵动两端。
_DATA_URL_RE = re.compile(r'^data:(image/[a-z0-9.+-]+);base64,(.+)$', re.IGNORECASE | re.DOTALL)

# ⚠️ 这个契约里**故意没有** confidence 字段。
# 此前提示词要求模型给出「0.0-1.0 的置信度」，前端把它渲染成「置信度 92%」——
# 一个并不存在的量化保证：同一个症状，模型曾给出 confidence 0.95 却配了一个错误的病名。
# 结论可以给，百分比不给。前端也已移除该控件，_parse_ai_diagnosis 会兜底剔除。
_DIAG_JSON_CONTRACT = """{
    "disease": "病名",
    "severity": "轻度/中度/重度",
    "symptoms": ["症状1", "症状2", "症状3"],
    "treatment": ["治疗方案1", "治疗方案2", "治疗方案3"],
    "prevention": ["预防措施1", "预防措施2", "预防措施3"],
    "timing": "最佳防治时期",
    "note": "注意事项"
}"""

# 用药数值约束（缺陷 A2）。与问答提示词同一口径：
# 药剂名称可以给，具体用量/稀释倍数/安全间隔期只在能说明出处时才给，
# 说不出出处就只给药剂与施用方法。服务端还会在 results 收口处兜底补免责声明。
_CHEM_DOSE_RULE = (
    "treatment 中涉及用药时：可以给出药剂名称与施用方法；"
    "若给出具体用量、稀释倍数或安全间隔期，必须在同一条里写明该数值的出处"
    "（例如某产品的标签、当地农业农村部门的指导、某个具体标准）；"
    "凡说不出出处的，不要给数字，改为提示以所购农药标签为准。严禁编造数值。\n"
)


def _parse_diag_images(raw):
    """解析并校验前端提交的照片（base64 data URL）。

    返回 (images, message, code)：校验通过时 message 为 None；
    images 形如 [{'mime': 'image/jpeg', 'data': '<base64>'}]。
    """
    if raw is None or raw == '' or raw == []:
        return [], None, None
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, list):
        return None, '照片格式不正确，请重新选择', 'bad_image'
    if len(raw) > DIAG_MAX_IMAGES:
        return None, f'一次最多上传 {DIAG_MAX_IMAGES} 张照片', 'too_many_images'

    max_mb = DIAG_MAX_IMAGE_BYTES // (1024 * 1024)
    images = []
    for item in raw:
        if not isinstance(item, str):
            return None, '照片格式不正确，请重新选择', 'bad_image'
        m = _DATA_URL_RE.match(item.strip())
        if not m:
            return None, '照片格式不受支持，请上传 JPG / PNG / WebP 格式的照片', 'bad_image'
        mime = m.group(1).lower()
        if mime not in DIAG_ALLOWED_IMAGE_TYPES:
            return None, '照片格式不受支持，请上传 JPG / PNG / WebP 格式的照片', 'bad_image'
        b64 = re.sub(r'\s+', '', m.group(2))
        try:
            decoded = base64.b64decode(b64, validate=True)
        except Exception:
            return None, '照片数据无法解析，请重新选择照片', 'bad_image'
        if len(decoded) > DIAG_MAX_IMAGE_BYTES:
            return None, f'单张照片不能超过 {max_mb} MB，请换一张更小的图片', 'image_too_large'
        images.append({'mime': mime, 'data': b64})
    return images, None, None


def _parse_diag_request():
    """解析并校验诊断请求。返回 (payload, error_response)，error_response 非空即需直接返回。"""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return None, (jsonify({
            "success": False, "code": "bad_request",
            "message": "请求格式不正确，应为 JSON 对象"
        }), 400)

    # 未知作物此前会被静默当成荔枝处理，用户无从察觉，改为明确拒绝。
    crop = str(data.get('crop') or '').strip() or 'lychee'
    if crop not in PEST_KNOWLEDGE:
        return None, (jsonify({
            "success": False, "code": "unknown_crop",
            "message": "暂不支持该作物，请从列表中选择"
        }), 400)

    symptoms = data.get('symptoms')
    if symptoms is None:
        symptoms = ''
    if not isinstance(symptoms, str):
        return None, (jsonify({
            "success": False, "code": "bad_request",
            "message": "症状描述应为文本"
        }), 400)
    symptoms = symptoms.strip()
    if len(symptoms) > DIAG_SYMPTOMS_MAX_LEN:
        return None, (jsonify({
            "success": False, "code": "symptoms_too_long",
            "message": f"症状描述过长，请控制在 {DIAG_SYMPTOMS_MAX_LEN} 字以内"
        }), 400)

    images, img_msg, img_code = _parse_diag_images(data.get('image'))
    if img_msg:
        return None, (jsonify({
            "success": False, "code": img_code or "bad_image", "message": img_msg
        }), 400)

    # 照片与文字至少要有一样。此前两者都没有时，服务端会替用户编造
    # 「叶片发黄、有斑点」再送进提示词，等于凭空生成一份不存在的诊断依据。
    if not symptoms and not images:
        return None, (jsonify({
            "success": False, "code": "empty_symptoms",
            "message": "请先上传一张作物照片，或描述症状后再开始诊断"
        }), 400)

    return {"crop": crop, "symptoms": symptoms, "images": images}, None


def _diag_system_prompt(crop_data, crop, has_image):
    """按作物与是否带图生成提示词。水产养殖是病害，不是「植物病虫害」。"""
    name = crop_data['name']
    if crop == 'aquatic':
        role = f"你是水产养殖病害诊断专家，擅长诊断{name}中的病害（细菌性、病毒性与寄生虫类）。"
    else:
        role = f"你是植物病虫害诊断专家，擅长诊断{name}的病虫害。"
    if has_image:
        body = ("请结合随附照片与用户的文字描述给出诊断；照片不清晰或信息不足时，"
                "请在 note 中如实说明判断依据有限。")
    else:
        body = "请根据用户描述的症状给出诊断结果。"
    return (f"{role}{body}\n{_CHEM_DOSE_RULE}"
            f"返回JSON格式：\n{_DIAG_JSON_CONTRACT}\n只返回JSON，不要其他文字。")


def _diag_user_message(crop_data, symptoms, image_count=0):
    """拼装用户消息。用户没提供的信息如实说明，不再替用户补一个症状。"""
    lines = [f"作物：{crop_data['name']}"]
    if image_count:
        lines.append(f"随附照片：{image_count} 张")
    if symptoms:
        lines.append(f"症状描述：{symptoms}")
    elif image_count:
        lines.append("症状描述：（用户未提供文字描述，请仅依据照片判断）")
    return "\n".join(lines)


def _parse_ai_diagnosis(result, crop_data):
    """解析模型返回的 JSON 诊断并补齐作物信息。内容不完整时抛 ValueError。"""
    clean = str(result or '').strip()
    if clean.startswith('```'):
        clean = clean.split('\n', 1)[-1].rsplit('```', 1)[0].strip()
    diagnosis = json.loads(clean)          # 非法 JSON → JSONDecodeError
    if not isinstance(diagnosis, dict) or not str(diagnosis.get('disease') or '').strip():
        raise ValueError('AI 返回内容缺少病害名称')
    # 契约里已不再要求 confidence，但模型（或换用的模型）仍可能自作主张带上。
    # 这里直接剔除，保证「结论可以给、百分比不给」不变量只由服务端把关，不依赖前端自觉。
    diagnosis.pop('confidence', None)
    # A2：treatment / note 里若出现用量、稀释倍数、安全间隔期，服务端强制补免责声明。
    # 放在 AI 结果的收口处（而不是只写在提示词里）—— 模型漏了，这里补上。
    # 知识库降级路径不经过本函数，故不会给「已编排的参考值」贴上「AI 生成」的标签。
    _dose_probe = ' '.join(str(x) for x in (diagnosis.get('treatment') or [])) \
        + ' ' + str(diagnosis.get('note') or '')
    if _has_chem_dosage(_dose_probe):
        _note = str(diagnosis.get('note') or '').strip()
        diagnosis['note'] = (_note + '\n\n' + _CHEM_DOSE_NOTICE) if _note else _CHEM_DOSE_NOTICE
    diagnosis['crop'] = crop_data['name']
    diagnosis['crop_icon'] = crop_data['icon']
    return diagnosis


def _diagnose_via_ai(crop_data, crop, user_symptoms, images):
    """调用 AI 得到诊断结果（带图走视觉模型）。任何失败抛异常，降级策略由调用方决定。"""
    has_image = bool(images)
    system_prompt = _diag_system_prompt(crop_data, crop, has_image)
    user_message = _diag_user_message(crop_data, user_symptoms, len(images))
    if has_image:
        result = call_ai_vision_service(
            system_prompt=system_prompt,
            user_message=user_message,
            images=images,
            temperature=0.3,
            # 诊断要输出一段结构化 JSON，推理模型思考约 800~1800 token，必须留足
            max_tokens=2000 + AI_REASONING_TOKEN_RESERVE,
            timeout=120
        )
    else:
        result = call_ai_service(
            system_prompt=system_prompt,
            user_message=user_message,
            temperature=0.3,
            max_tokens=2000 + AI_REASONING_TOKEN_RESERVE
        )
    return _parse_ai_diagnosis(result, crop_data)


# 知识库匹配阈值：低于此分视为「没匹配上」，宁可如实说没识别出来，也不硬凑一个结论。
KB_MATCH_THRESHOLD = 0.30

# 只保留汉字/字母/数字，其余（标点、空白、括号）一律剔除后再切双字词。
_KB_NOISE_RE = re.compile(r'[^\u4e00-\u9fffA-Za-z0-9]+')


def _kb_bigrams(text):
    """把文本切成双字词集合。

    历史缺陷：原实现用 `s[:2]` 再 `for kw in s[:2]`，得到的是**单个汉字**，
    于是「叶」「病」「斑」这类字在任何农事描述里都必然出现，判别力接近于零。
    改为双字词后，「叶片」「病斑」「果实」这类组合才具备区分度。
    """
    cleaned = _KB_NOISE_RE.sub('', str(text or ''))
    if not cleaned:
        return set()
    if len(cleaned) == 1:
        return {cleaned}
    return {cleaned[i:i + 2] for i in range(len(cleaned) - 1)}


def _kb_overlap_ratio(user_bigrams, text):
    """用户描述与一段文本的双字词重合率（用文本自身的词数归一化，长度无关）。"""
    ref = _kb_bigrams(text)
    if not ref or not user_bigrams:
        return 0.0
    return len(user_bigrams & ref) / float(len(ref))


def _match_kb_disease(crop_data, user_symptoms):
    """知识库匹配。返回 (病害条目或 None, 得分)。

    对所有条目的「病名 + 各条典型症状的重合度」取最高分，而不是首个命中即返回 ——
    后者会让排在前面的病害吃掉所有命中。得分低于 KB_MATCH_THRESHOLD 时返回 None，
    不再默认返回第一条病害（那会把「没匹配上」伪装成结论）。
    """
    text = str(user_symptoms or '').strip()
    if not text:
        return None, 0.0
    user_bigrams = _kb_bigrams(text)
    if not user_bigrams:
        return None, 0.0

    best, best_score = None, 0.0
    for d in crop_data['common_diseases']:
        # 用户直接报病名是最强的信号，与各条症状描述的重合度一起取最大值
        score = _kb_overlap_ratio(user_bigrams, d.get('disease'))
        for symptom in d.get('symptoms') or []:
            score = max(score, _kb_overlap_ratio(user_bigrams, symptom))
        if score > best_score:
            best, best_score = d, score
    if best_score < KB_MATCH_THRESHOLD:
        return None, best_score
    return best, best_score


@app.route('/api/agriculture/diagnose', methods=['POST'])
def diagnose_pest():
    """AI 病虫害诊断 —— 支持文字描述与照片（多模态）。

    路径约定：
      · 带照片 → 必须走视觉模型。知识库匹配根本不读图片，带图时降级返回 KB 结论
        会让用户误以为「看图诊断成功」，因此 AI 不可用时直接报错，不降级。
      · 纯文字 → 优先 AI；AI 不可用时降级知识库，来源由 _tag_diagnosis_source 如实标注。
    """
    payload, err = _parse_diag_request()
    if err:
        return err

    if _rate_limited('diag:' + _client_key(), DIAG_RATE_LIMIT):
        return jsonify({
            "success": False, "code": "rate_limited",
            "message": "诊断请求过于频繁，请稍后再试"
        }), 429

    crop = payload['crop']
    user_symptoms = payload['symptoms']
    images = payload['images']
    crop_data = PEST_KNOWLEDGE[crop]
    has_image = bool(images)

    if has_image:
        if not _ai_configured():
            logger.warning("图片诊断被调用但未配置密钥：%s", AI_NOT_CONFIGURED_LOG)
            return jsonify({
                "success": False, "code": "ai_not_configured",
                "message": AI_VISION_NOT_CONFIGURED_MSG
            }), 503
        if not (AI_VL_MODEL or '').strip():
            logger.warning("图片诊断被调用但未配置视觉模型：%s", AI_VISION_NOT_CONFIGURED_LOG)
            return jsonify({
                "success": False, "code": "ai_vision_unavailable",
                "message": AI_VISION_UNAVAILABLE_MSG
            }), 503

    # 未配置密钥的纯文字请求不必白跑一次上游（空密钥必然 401）
    if has_image or _ai_configured():
        try:
            diagnosis = _diagnose_via_ai(crop_data, crop, user_symptoms, images)
            return jsonify({
                "success": True,
                "diagnosis": _tag_diagnosis_source(diagnosis, DIAG_SOURCE_AI),
            })
        except json.JSONDecodeError:
            logger.warning('AI 诊断返回内容不是合法 JSON')
        except ValueError as e:
            logger.warning('AI 诊断返回内容不完整(%s)', e)
        except Exception as e:
            logger.error("AI诊断失败: %s", e)

    # 带图请求走到这里说明上游失败：只能报错，绝不能降级成「不看图」的知识库结论
    if has_image:
        return jsonify({
            "success": False, "code": "ai_unavailable",
            "message": AI_UNAVAILABLE_MSG
        }), 503

    # 纯文字：降级知识库，来源如实标注
    matched, match_score = _match_kb_disease(crop_data, user_symptoms)
    if matched is None:
        logger.info('知识库未匹配到病害(crop=%s, score=%.3f)', crop, match_score)
        return jsonify({
            "success": False, "code": "no_match",
            "message": "未能从描述中匹配到对应的病害，请补充发病部位、病斑颜色与形状等更具体的症状后重试。"
        })

    diagnosis = {
        "disease": matched['disease'],
        # 知识库条目里的 confidence 是固定常量、不是真实匹配度，故不再下发给前端，
        # 避免界面把「置信度 92%」呈现成一个并不存在的量化保证。
        "severity": matched['severity'],
        "symptoms": matched['symptoms'],
        "treatment": matched['treatment'],
        "prevention": matched['prevention'],
        "timing": "发病初期为最佳防治期",
        "note": "建议结合当地农技站指导进行防治",
        "crop": crop_data['name'],
        "crop_icon": crop_data['icon']
    }
    return jsonify({
        "success": True,
        "diagnosis": _tag_diagnosis_source(diagnosis, DIAG_SOURCE_KB),
    })


# 注：原 /api/agriculture/diag-crops 已删除。
# 它是全项目无调用者的死接口（诊断面板的作物按钮由 index.html 静态渲染），
# 保留只会让「支持哪些作物」有两个互相不同步的出口。


# ==================== 常见病虫害速查 ====================
#
# 与上面的 /api/agriculture/diagnose 共用同一份 pest_data.PEST_KNOWLEDGE。
# 速查定位是「只读参考」，不做任何推断：来源资料没给出的数值（尤其是安全间隔期）
# 如实留空并由界面显示「未提供」，不用一个看起来合理的数字把空白填上。

PEST_DISCLAIMER = (
    '本速查整理自省、市、县农业农村部门公开发布的病虫情报、防控技术指引与农药登记数据，'
    '仅供学习与参考。农药的实际用药量、安全间隔期与每季最多使用次数，'
    '一律以你所购农药标签标注为准；资料中未给出安全间隔期的药剂，请勿自行推算。'
    '标注「暂无实拍图」的条目表示尚未取得可用的授权照片，界面上不会用示意图冒充真实病征。'
)


def _pest_entry_view(entry, crop, crop_data):
    """把一条病虫害记录整理成对外结构（不做推断，缺什么就缺什么）。"""
    return {
        'id': entry.get('id'),
        'crop': crop,
        'crop_name': crop_data.get('name'),
        'crop_icon': crop_data.get('icon'),
        'disease': entry.get('disease'),
        'alias': entry.get('alias') or '',
        'kind': entry.get('kind'),
        'pathogen': entry.get('pathogen') or '',
        'part': entry.get('part') or '',
        'severity': entry.get('severity') or '',
        'symptoms': entry.get('symptoms') or [],
        'occurrence': entry.get('occurrence') or '',
        'treatment': entry.get('treatment') or [],
        'prevention': entry.get('prevention') or [],
        'registered': entry.get('registered') or [],
        'chem_table': entry.get('chem_table') or [],
        'safety_note': entry.get('safety_note') or '',
        # 无授权实拍图时明确为 None，前端据此显示「暂无实拍图」占位。
        'image': entry.get('image'),
        'sources': [PEST_SOURCE_MAP[k] for k in (entry.get('sources') or [])
                    if k in PEST_SOURCE_MAP],
        'is_verified': int(entry.get('is_verified') or 0),
    }


@app.route('/api/agriculture/pest-knowledge', methods=['GET'])
def get_pest_knowledge():
    """常见病虫害速查 —— 只读。

    数据量很小（数十条），一次取回由前端本地筛选，避免每次切作物都打一次请求。
    支持 crop / kind / q 三个可选筛选参数，便于将来直接以 URL 定位。
    """
    crop = (request.args.get('crop') or '').strip()
    kind = (request.args.get('kind') or '').strip()
    keyword = (request.args.get('q') or '').strip()

    if crop and crop not in PEST_KNOWLEDGE:
        return jsonify({
            "success": False, "code": "unknown_crop",
            "message": "暂不支持该作物，请从列表中选择"
        }), 400
    if kind and kind not in ('disease', 'pest'):
        return jsonify({
            "success": False, "code": "bad_request",
            "message": "类型筛选仅支持 disease 或 pest"
        }), 400

    entries = []
    for c, crop_data, entry in iter_pest_entries():
        if crop and c != crop:
            continue
        if kind and entry.get('kind') != kind:
            continue
        if keyword:
            blob = ' '.join([
                str(entry.get('disease') or ''),
                str(entry.get('alias') or ''),
                str(entry.get('pathogen') or ''),
                str(crop_data.get('name') or ''),
                ' '.join(entry.get('symptoms') or []),
            ])
            if keyword not in blob:
                continue
        entries.append(_pest_entry_view(entry, c, crop_data))

    crops = []
    for c in PEST_CROP_ORDER:
        cd = PEST_KNOWLEDGE.get(c)
        if not cd:
            continue
        crops.append({
            'id': c,
            'name': cd.get('name'),
            'icon': cd.get('icon'),
            'summary': cd.get('summary') or '',
            'count': len(cd.get('common_diseases') or []),
        })

    return jsonify({
        "success": True,
        "crops": crops,
        "entries": entries,
        "stats": get_pest_stats(),
        "disclaimer": PEST_DISCLAIMER,
    })


# ==================== 本土资源API ====================

# 方言知识库
DIALECTS_DATA = {
    "cantonese": {
        "id": "cantonese", "name": "粤语", "region": "广州话", "emoji": "🗣️",
        "areas": "广州、佛山、深圳、东莞、中山、珠海、江门",
        "speakers": "约7000万使用者",
        "greeting": "你好！食咗饭未？",
        "greeting_meaning": "你好！吃饭了吗？",
        "features": ["九声六调", "保留古汉语词汇", "大量外来语借词"],
        "phrases": [
            {"dialect": "你好", "mandarin": "你好", "pinyin": "nei5 hou2"},
            {"dialect": "多谢", "mandarin": "谢谢", "pinyin": "do1 ze6"},
            {"dialect": "几多钱？", "mandarin": "多少钱？", "pinyin": "gei2 do1 cin2"},
            {"dialect": "好食", "mandarin": "好吃", "pinyin": "hou2 sik6"},
            {"dialect": "唔该", "mandarin": "麻烦/请", "pinyin": "m4 goi1"},
            {"dialect": "点解？", "mandarin": "为什么？", "pinyin": "dim2 gaai2"},
            {"dialect": "边度", "mandarin": "哪里", "pinyin": "bin1 dou6"},
            {"dialect": "靓", "mandarin": "漂亮/好", "pinyin": "leng3"}
        ],
        "quick_questions": [
            "荔枝点样施肥最好？",
            "龙眼几时可以摘？",
            "香蕉点样防虫？",
            "柑橘落叶点处理？"
        ]
    },
    "hakka": {
        "id": "hakka", "name": "客家话", "region": "梅州话", "emoji": "🏔️",
        "areas": "梅州、惠州、河源、韶关、深圳(部分)",
        "speakers": "约4500万使用者",
        "greeting": "你好！食咗饭无？",
        "greeting_meaning": "你好！吃饭了吗？",
        "features": ["六声调", "保留入声", "古汉语活化石"],
        "phrases": [
            {"dialect": "你好", "mandarin": "你好", "pinyin": "ngi2 hau3"},
            {"dialect": "多谢", "mandarin": "谢谢", "pinyin": "do1 cia5"},
            {"dialect": "几多钱？", "mandarin": "多少钱？", "pinyin": "gi1 do1 qian2"},
            {"dialect": "好食", "mandarin": "好吃", "pinyin": "hau3 siid6"},
            {"dialect": "对唔住", "mandarin": "对不起", "pinyin": "dui4 m4 cu5"},
            {"dialect": "做麻个？", "mandarin": "做什么？", "pinyin": "zo4 ma2 ge4"},
            {"dialect": "奈里", "mandarin": "哪里", "pinyin": "nai4 li1"},
            {"dialect": "靓", "mandarin": "漂亮", "pinyin": "liang4"}
        ],
        "quick_questions": [
            "荔枝样般施肥做得好？",
            "龙眼几时可以摘？",
            "香蕉样般防虫？",
            "柑橘落叶样般处理？"
        ]
    },
    "teochew": {
        "id": "teochew", "name": "潮汕话", "region": "汕头话", "emoji": "🌊",
        "areas": "汕头、潮州、揭阳、汕尾",
        "speakers": "约1500万使用者",
        "greeting": "你好！食未？",
        "greeting_meaning": "你好！吃了吗？",
        "features": ["八声调", "保留古汉语入声", "文白异读丰富"],
        "phrases": [
            {"dialect": "你好", "mandarin": "你好", "pinyin": "le2 ho2"},
            {"dialect": "多谢", "mandarin": "谢谢", "pinyin": "do1 sia7"},
            {"dialect": "若挤？", "mandarin": "多少钱？", "pinyin": "rioh8 zoi6"},
            {"dialect": "好食", "mandarin": "好吃", "pinyin": "ho2 ziah8"},
            {"dialect": "对唔住", "mandarin": "对不起", "pinyin": "dui3 m6 zu6"},
            {"dialect": "做呢？", "mandarin": "为什么？", "pinyin": "zo3 ni1"},
            {"dialect": "地块", "mandarin": "哪里", "pinyin": "de7 kau3"},
            {"dialect": "雅", "mandarin": "漂亮", "pinyin": "ngia2"}
        ],
        "quick_questions": [
            "荔枝怎生施肥正好？",
            "龙眼时阵好摘？",
            "香蕉怎生防虫？",
            "柑橘落叶怎生处理？"
        ]
    }
}


@app.route('/api/resources/dialects', methods=['GET'])
def get_dialects():
    dialects = [{"id": v["id"], "name": v["name"], "region": v["region"],
                 "emoji": v["emoji"], "areas": v["areas"], "speakers": v["speakers"]}
                for v in DIALECTS_DATA.values()]
    return jsonify({"success": True, "dialects": dialects})


@app.route('/api/resources/dialect-info', methods=['GET'])
def get_dialect_info():
    """获取方言详细信息（问候、短语、快捷问题）"""
    dialect_id = request.args.get('dialect', 'cantonese')
    d = DIALECTS_DATA.get(dialect_id, DIALECTS_DATA['cantonese'])
    return jsonify({"success": True, "info": {
        "id": d["id"], "name": d["name"], "region": d["region"],
        "emoji": d["emoji"], "areas": d["areas"], "speakers": d["speakers"],
        "greeting": d["greeting"], "greeting_meaning": d["greeting_meaning"],
        "features": d["features"], "phrases": d["phrases"],
        "quick_questions": d["quick_questions"]
    }})


@app.route('/api/resources/cases', methods=['GET'])
def get_success_cases():
    # 内容唯一事实源 = cases_data.py（经 database.get_success_cases 读取，不落库）
    # ⚠️ 只下发**超级管理员审核通过**的案例（审核状态存 content_reviews，见 _seed_case_reviews）
    cases = database.get_success_cases()
    payload = {"success": True, "cases": cases}
    payload.update(database.get_case_notes())
    # 附审核统计：前端据此区分"审核中"与"加载失败"，不把待审当成没数据
    payload.update(database.get_case_review_stats())
    return jsonify(payload)


@app.route('/api/resources/cases/<int:case_id>', methods=['GET'])
def get_success_case(case_id):
    # 同样只认审核通过的案例 —— 否则未通过/已驳回的案例能靠直链看到，审核就形同虚设
    cases = database.get_success_cases()
    case = next((c for c in cases if c['id'] == case_id), None)
    if case:
        return jsonify({"success": True, "case": case})
    return jsonify({"success": False, "message": "案例不存在或尚未通过审核"}), 404


@app.route('/api/resources/policies', methods=['GET'])
def get_policies():
    # 学员端唯一的政策来源 = 政府端政策表（government_policies）中 is_published=1 的行。
    #
    # ⚠️ 这里**绝不能**再降级到旧 `policies` 表（原实现 `gp if gp else database.get_policies()`）：
    #    平台预置的 5 条政策在两张表里各存了一份，政府端把政策**全部下架**时
    #    `get_government_policies()` 返回空 → 降级逻辑把旧表那 5 条端上学員端
    #    → 政务人员明明点了「下架」，学员端却一条没少（实测表现为"下架完全无效"）。
    #    下架是政府对外的正式动作，必须真实生效；学员端「空」就是要如实呈现为空。
    policies = database.get_government_policies()
    payload = {"success": True, "policies": policies}
    # 口径说明（来源说明 + 免责声明）与内容同源，由 policies_data.py 提供
    payload.update(database.get_policy_notes())
    return jsonify(payload)


@app.route('/api/resources/voice', methods=['POST'])
def process_voice():
    """处理语音/文字输入 — 支持对话历史"""
    data = request.get_json()
    text = data.get('text', '')
    dialect = data.get('dialect', 'cantonese')
    history = data.get('history', [])  # 最近对话历史

    if not text:
        return jsonify({"success": False, "message": "未收到内容"})

    # A7：本接口此前**没有任何限流**，而它同样走 _chat_model() 调用上游。
    # 限流键与其它 AI 路由共用 _client_key()，错误体结构与农技问答保持一致。
    if _rate_limited('voice:' + _client_key(), VOICE_RATE_LIMIT):
        return jsonify({
            "success": False, "code": "rate_limited",
            "message": "提问过于频繁，请稍后再试"
        }), 429

    d = DIALECTS_DATA.get(dialect, DIALECTS_DATA['cantonese'])
    dialect_name = d['name']
    areas = d['areas']

    # 构建对话历史
    messages = [{
        "role": "system",
        "content": f"""你是粤乡智匠平台的AI农业助手，精通{dialect_name}（{areas}地区）。
用户用{dialect_name}方言提问，你也必须用{dialect_name}方言回答！
要求：
1. 全程用{dialect_name}方言回答，不要用普通话
2. 语气亲切自然，像老乡之间聊天
3. 回答简洁实用，200字以内
4. 涉及病虫害给出具体防治方案
5. 结合广东本地气候和种植习惯
6. 如果不确定某个方言词怎么写，就用普通话混搭，但整体风格必须是{dialect_name}"""
    }]
    # 加入历史对话（最多5轮）
    for h in history[-5:]:
        if h.get('user'):
            messages.append({"role": "user", "content": h['user']})
        if h.get('bot'):
            messages.append({"role": "assistant", "content": h['bot']})
    messages.append({"role": "user", "content": text})

    try:
        # 走统一入口：自带推理模型的思考余量、上游结构校验，以及「被 max_tokens 截断」的识别。
        # 上游失败时由外层 except 退到本地方言话术库，降级行为与改动前一致。
        answer = _chat_completion(
            messages,
            temperature=0.4,
            max_tokens=600 + AI_REASONING_TOKEN_RESERVE,
            timeout=60,
            model=_chat_model()
        )

        # 生成追问建议
        suggestions = []
        try:
            sug_resp = call_ai_service(
                system_prompt="根据用户的问题和你的回答，生成3个相关的追问建议。返回JSON数组格式，如：[\"问题1\",\"问题2\",\"问题3\"]。只返回JSON。",
                user_message=f"用户问题：{text}\n回答：{answer}",
                temperature=0.5, max_tokens=300 + AI_REASONING_TOKEN_RESERVE,
                model=_chat_model()
            )
            clean = sug_resp.strip()
            if clean.startswith('```'):
                clean = clean.split('\n', 1)[-1].rsplit('```', 1)[0].strip()
            suggestions = json.loads(clean)[:3]
        except:
            # 根据用户问题生成动态追问建议
            sug_map = {
                "施肥": ["有机肥和化肥怎么搭配？", "叶面肥什么时候喷？", "施肥后要浇水吗？"],
                "病": ["怎么区分真菌和细菌病害？", "打药要注意什么？", "有没有不用药的方法？"],
                "虫": ["黄板蓝板怎么选？", "什么虫害最常见？", "天敌怎么保护？"],
                "种植": ["第一年怎么管理？", "什么时候种最好？", "要挖多大的坑？"],
                "修剪": ["什么时候修剪最好？", "大枝小枝怎么分？", "修剪后怎么护理？"],
                "直播": ["开场怎么吸引人？", "产品怎么展示？", "怎么引导下单？"],
                "电商": ["图片怎么拍好看？", "标题怎么写？", "怎么处理售后？"]
            }
            suggestions = None
            for kw, sugs in sug_map.items():
                if kw in text:
                    suggestions = sugs
                    break
            if not suggestions:
                suggestions = [f"{text}有什么技巧？", "需要注意什么问题？", "有没有成功案例？"]

        return jsonify({"success": True, "result": {
            "text": text, "dialect": dialect, "dialect_name": dialect_name,
            "answer": answer, "suggestions": suggestions,
            "source": "ai",
            # 用药口径：与农技问答 / 诊断同一条红线 —— 给了用量就必须给用户提示
            "chem_notice": _chem_dose_notice_for(answer)
        }})
    except Exception as e:
        logger.error(f"语音处理失败: {e}")
        answer, suggestions = generate_dynamic_voice_answer(text, dialect)
        return jsonify({"success": True, "result": {
            "text": text, "dialect": dialect, "dialect_name": dialect_name,
            "answer": answer, "suggestions": suggestions,
            "source": "fallback",
            # 降级话术库里就写着具体用量与施用间隔，同样必须提示
            "chem_notice": _chem_dose_notice_for(answer)
        }})


def generate_dynamic_voice_answer(text, dialect):
    """根据用户问题动态生成方言回答，不依赖AI"""
    import random
    text_lower = text.lower()

    # 方言版回答模板
    dialect_templates = {
        "cantonese": {
            "施肥": {
                "answer": "广东施肥要睇季节嘅：冬天施基肥，用腐熟嘅有机肥，每棵大树施20-30斤；开花前（2-3月）追磷钾肥，帮手促花；幼果期补复合肥，氮磷钾大约1:0.5:1。施完肥要覆土浇水，唔好烧根。{extra}",
                "extras": [
                    "叶面喷0.3%磷酸二氢钾效果都几好。",
                    "有机肥同化肥夹埋用效果最好。",
                    "落雨后施肥吸收更好，但暴雨前就唔好施。"
                ],
                "suggestions": ["用咩有机肥最好？", "施肥量点控制？", "叶面肥点喷？"]
            },
            "病": {
                "answer": "防病最紧要预防为主。先做好冬季清园，清走病枝落叶集中烧咗；再加强果园管理，剪好枝保持通风透光；发病初期快啲喷药，用多菌灵、甲基托布津都得，每隔7-10日喷一次，连喷2-3次。{extra}",
                "extras": [
                    "雨季系病害高发期，要提前预防。",
                    "唔同病害用药唔同，最好先确认系咩病。",
                    "生物菌肥都可以增强抗病能力。"
                ],
                "suggestions": ["点判断系咩病害？", "有冇生物防治方法？", "雨季点预防？"]
            },
            "虫": {
                "answer": "治虫要综合嚟搞：物理方法可以挂黄板诱杀蚜虫、蓟马，用灯诱杀蛾类；生物防治要保护天敌好似瓢虫、草蛉；化学防治拣低毒药，注意安全间隔期。最紧要早发现早处理，定期巡查果园。{extra}",
                "extras": [
                    "挂黄板系简单又有效嘅方法。",
                    "蚜虫可以用吡虫啉，螨类用阿维菌素。",
                    "生物农药更安全，啱绿色种植。"
                ],
                "suggestions": ["黄板点挂效果好？", "安全间隔期系几耐？", "有边啲生物农药？"]
            },
            "种植": {
                "answer": "广东天气暖湿，种荔枝、龙眼、香蕉、柑橘都得。种嘅时候要注意拣好品种，因地制宜；合理密植，保证通风透光；做好水肥管理，旱季灌水雨季排水；仲要注意病虫害防治。{extra}",
                "extras": [
                    "拣苗好紧要，要拣冇病嘅壮苗。",
                    "种之前要深翻泥土施足基肥。",
                    "可以去当地农技站问下啱种嘅品种。"
                ],
                "suggestions": ["咩品种最好？", "种植密度点定？", "基肥点施？"]
            },
            "修剪": {
                "answer": "剪枝系果树管理好重要嘅一环。冬天大剪，剪走病虫枝、交叉枝、下垂枝；夏天搞摘心抹芽，控制营养生长。剪完要及时涂伤口愈合剂，防止病菌感染。{extra}",
                "extras": [
                    "剪刀要消毒，避免传播病害。",
                    "幼树以整形为主，结果树以调节为主。",
                    "剪嘅量唔好超过总量嘅三分之一。"
                ],
                "suggestions": ["冬剪同夏剪有咩区别？", "伤口愈合剂点配？", "幼树点整形？"]
            },
            "浇水": {
                "answer": "浇水要睇季节同生长阶段。春天发芽期保持泥土湿润；夏天高温朝晚浇水，唔好中午浇伤根；秋天果实膨大期需水量大；冬天控水促花。雨季要及时排水防涝。{extra}",
                "extras": [
                    "滴灌比漫灌更省水，效果仲好啲。",
                    "泥面发白就要浇水啦。",
                    "铺啲禾秆可以减少水分蒸发。"
                ],
                "suggestions": ["滴灌点装？", "点判断缺水？", "铺咩材料好？"]
            },
            "直播": {
                "answer": "做农产品直播要注意几点：首先要熟识产品，讲得出产地、口感、种植过程；其次要有感染力，用真实嘅场景打动观众；第三要善于互动，及时回复评论引导下单；最后要保证物流同售后。{extra}",
                "extras": [
                    "喺果园现场直播效果更加好。",
                    "讲故事比硬推产品更加有效。",
                    "固定时间直播培养观众习惯。"
                ],
                "suggestions": ["直播话术点设计？", "点涨粉？", "物流点拣？"]
            },
            "电商": {
                "answer": "做农村电商首先要拣好产品，搵差异化卖点；其次要影好相拍好视频，真实展示产品；然后拣好平台，淘宝、拼多多、抖音都得；仲要做好包装同物流，保证产品完好送到。{extra}",
                "extras": [
                    "短视频引流系而家最有效嘅方式。",
                    "包装要兼顾保护同靓观。",
                    "售后服务决定复购率。"
                ],
                "suggestions": ["边个平台啱新手？", "点影好产品图？", "包装点设计？"]
            }
        },
        "hakka": {
            "施肥": {
                "answer": "广东施肥要看季节嘅：冬天施基肥，用沤熟嘅有机肥，每棵大树施二十到三十斤；开花前（二三月）追磷钾肥，帮手促花；幼果期补复合肥，氮磷钾大概一比零点五比一。施完肥要覆土浇水，莫烧根。{extra}",
                "extras": [
                    "叶面喷零点三嘅磷酸二氢钾效果都做得。",
                    "有机肥同化肥搭起来用效果最好。",
                    "落水后施肥吸收更好，但大水前就莫施。"
                ],
                "suggestions": ["用么嘢有机肥最好？", "施肥量样般控制？", "叶面肥样般喷？"]
            },
            "病": {
                "answer": "防病最紧要预防为主。先做好冬季清园，清走病枝落叶集中烧咗；再加强果园管理，修好枝保持通风透光；发病初期快滴喷药，用多菌灵、甲基托布津都做得，隔七八日喷一次，连喷两三回。{extra}",
                "extras": [
                    "雨季系病害多发期，要提前预防。",
                    "唔同病害用药唔同，最好先确认系么嘢病。",
                    "生物菌肥都可以增强抗病能力。"
                ],
                "suggestions": ["样般判断系么嘢病害？", "有冇生物防治方法？", "雨季样般预防？"]
            },
            "虫": {
                "answer": "治虫要综合来做：物理方法可以挂黄板诱杀蚜虫、蓟马，用灯诱杀蛾类；生物防治要保护天敌像瓢虫、草蛉；化学防治拣低毒药，注意安全间隔期。最紧要早发现早处理，定期巡查果园。{extra}",
                "extras": [
                    "挂黄板系简单又有效嘅方法。",
                    "蚜虫可以用吡虫啉，螨类用阿维菌素。",
                    "生物农药更安全，做得绿色种植。"
                ],
                "suggestions": ["黄板样般挂效果好？", "安全间隔期系几久？", "有哪滴生物农药？"]
            },
            "种植": {
                "answer": "广东天气暖湿，种荔枝、龙眼、香蕉、柑橘都做得。种嘅时节要注意拣好品种，因地制宜；合理密植，保证通风透光；做好水肥管理，旱季灌水雨季排水；还要注意病虫害防治。{extra}",
                "extras": [
                    "拣苗好紧要，要拣冇病嘅壮苗。",
                    "种之前要深翻泥巴施足基肥。",
                    "可以去当地农技站问下适合种嘅品种。"
                ],
                "suggestions": ["么嘢品种最好？", "种植密度样般定？", "基肥样般施？"]
            },
            "修剪": {
                "answer": "修枝系果树管理好紧要嘅一环。冬天大修，剪走病虫枝、交叉枝、下垂枝；夏天做摘心抹芽，控制营养生长。修完要及时涂伤口愈合剂，防止病菌感染。{extra}",
                "extras": [
                    "剪刀要消毒，避免传播病害。",
                    "幼树以整形为主，结果树以调节为主。",
                    "修嘅量莫超过总量嘅三分之一。"
                ],
                "suggestions": ["冬修同夏修有么嘢区别？", "伤口愈合剂样般配？", "幼树样般整形？"]
            },
            "浇水": {
                "answer": "浇水要看季节同生长阶段。春天发芽期保持泥巴湿润；夏天高温朝晚浇水，莫中午浇伤根；秋天果实膨大期需水量大；冬天控水促花。雨季要及时排水防涝。{extra}",
                "extras": [
                    "滴灌比漫灌更省水，效果还更好。",
                    "泥面发白就要浇水了。",
                    "铺滴禾秆可以减少水分蒸发。"
                ],
                "suggestions": ["滴灌样般装？", "样般判断缺水？", "铺么嘢材料好？"]
            },
            "直播": {
                "answer": "做农产品直播要注意几滴：首先要识得产品，讲得出产地、口感、种植过程；其次要有感染力，用真实嘅场景打动观众；第三要善于互动，及时回复评论引导下单；最后要保证物流同售后。{extra}",
                "extras": [
                    "在果园现场直播效果更加好。",
                    "讲故事比硬推产品更加有效。",
                    "固定时间直播培养观众习惯。"
                ],
                "suggestions": ["直播话术样般设计？", "样般涨粉？", "物流样般拣？"]
            },
            "电商": {
                "answer": "做农村电商首先要拣好产品，寻差异化卖点；其次要影好相拍好视频，真实展示产品；然后拣好平台，淘宝、拼多多、抖音都做得；还要做好包装同物流，保证产品完好送到。{extra}",
                "extras": [
                    "短视频引流系如今最有效嘅方式。",
                    "包装要兼顾保护同靓观。",
                    "售后服务决定复购率。"
                ],
                "suggestions": ["哪只平台适合新手？", "样般影好产品图？", "包装样般设计？"]
            }
        },
        "teochew": {
            "施肥": {
                "answer": "广东施肥着看季节个：冬天施底肥，用沤熟个有机肥，每丛大树施二十到三十斤；开花前（二三月）追磷钾肥，帮手促花；幼果期补复合肥，氮磷钾大概一比零点五比一。施了肥着覆土浇水，勿烧根。{extra}",
                "extras": [
                    "叶面喷零点三个磷酸二氢钾效果都做得。",
                    "有机肥同化肥配起来用效果正好。",
                    "落雨后施肥吸收更好，但大雨前就勿施。"
                ],
                "suggestions": ["用什物有机肥最好？", "施肥量怎生控制？", "叶面肥怎生喷？"]
            },
            "病": {
                "answer": "防病上紧预防为主。先做好冬季清园，清走病枝落叶集中烧掉；再加强果园管理，修好枝保持通风透光；发病初期猛个喷药，用多菌灵、甲基托布津都做得，隔七八日喷一次，连喷两三回。{extra}",
                "extras": [
                    "雨季系病害多发期，着提前预防。",
                    "唔同病害用药唔同，上好先确认系什物病。",
                    "生物菌肥都可能增强抗病能力。"
                ],
                "suggestions": ["怎生判断系什物病害？", "有无生物防治方法？", "雨季怎生预防？"]
            },
            "虫": {
                "answer": "治虫着综合来做：物理方法可能挂黄板诱杀蚜虫、蓟马，用灯诱杀蛾类；生物防治着保护天敌像瓢虫、草蛉；化学防治拣低毒药，注意安全间隔期。上紧早发现早处理，定期巡查果园。{extra}",
                "extras": [
                    "挂黄板系简单又有效个方法。",
                    "蚜虫可能用吡虫啉，螨类用阿维菌素。",
                    "生物农药更安全，做得绿色种植。"
                ],
                "suggestions": ["黄板怎生挂效果好？", "安全间隔期系偌久？", "有什物生物农药？"]
            },
            "种植": {
                "answer": "广东天气暖湿，种荔枝、龙眼、香蕉、柑橘都做得。种个时节着注意拣好品种，因地制宜；合理密植，保证通风透光；做好水肥管理，旱季灌水雨季排水；还要注意病虫害防治。{extra}",
                "extras": [
                    "拣苗上紧要，着拣无病个壮苗。",
                    "种之前着深翻涂土施足底肥。",
                    "可能去当地农技站问下适合种个品种。"
                ],
                "suggestions": ["什物品种最好？", "种植密度怎生定？", "底肥怎生施？"]
            },
            "修剪": {
                "answer": "修枝系果树管理上紧要个一环。冬天大修，剪走病虫枝、交叉枝、下垂枝；夏天做摘心抹芽，控制营养生长。修了着及时涂伤口愈合剂，防止病菌感染。{extra}",
                "extras": [
                    "剪刀着消毒，避免传播病害。",
                    "幼树以整形为主，结果树以调节为主。",
                    "修个量勿超过总量个三分之一。"
                ],
                "suggestions": ["冬修同夏修有什物区别？", "伤口愈合剂怎生配？", "幼树怎生整形？"]
            },
            "浇水": {
                "answer": "浇水着看季节同生长阶段。春天发芽期保持涂土湿润；夏天高温朝晚浇水，勿中午浇伤根；秋天果实膨大期需水量大；冬天控水促花。雨季着要及时排水防涝。{extra}",
                "extras": [
                    "滴灌比漫灌更省水，效果还更好。",
                    "涂面发白就着浇水了。",
                    "铺滴稻草可能减少水分蒸发。"
                ],
                "suggestions": ["滴灌怎生装？", "怎生判断缺水？", "铺什物材料好？"]
            },
            "直播": {
                "answer": "做农产品直播着注意几滴：上先着识得产品，讲得出产地、口感、种植过程；其次着有感染力，用真实个场景打动观众；第三着善于互动，及时回复评论引导下单；上后着保证物流同售后。{extra}",
                "extras": [
                    "在现场果园直播效果更加好。",
                    "讲故事比硬推产品更加有效。",
                    "固定时间直播培养观众习惯。"
                ],
                "suggestions": ["直播话术怎生设计？", "怎生涨粉？", "物流怎生拣？"]
            },
            "电商": {
                "answer": "做农村电商上先着拣好产品，寻差异化卖点；其次着影好相拍好视频，真实展示产品；然后拣好平台，淘宝、拼多多、抖音都做得；还着做好包装同物流，保证产品完好送到。{extra}",
                "extras": [
                    "短视频引流系现今上有效个方式。",
                    "包装着兼顾保护同雅观。",
                    "售后服务决定复购率。"
                ],
                "suggestions": ["什物平台适合新手？", "怎生影好产品图？", "包装怎生设计？"]
            }
        }
    }

    # 获取该方言的模板，没有则用粤语
    templates = dialect_templates.get(dialect, dialect_templates["cantonese"])

    # 匹配主题
    matched_topic = None
    for keyword, topic in templates.items():
        if keyword in text_lower:
            matched_topic = topic
            break

    if matched_topic:
        extra = random.choice(matched_topic["extras"])
        answer = matched_topic["answer"].format(extra=extra)
        suggestions = matched_topic["suggestions"]
    else:
        # 通用回答（方言版）
        general = {
            "cantonese": [
                "呢个问题问得好！广东做农业要注意因地制宜，睇下当地气候同土壤条件。建议多啲同周围有经验嘅农户倾下，都可以去当地农技站攞专业指导。",
                "种嘢要讲究科学管理，由拣种、施肥、浇水到病虫害防治，每个环节都好紧要。建议做好记录，总结经验，慢慢提高种植技术。",
                "做农业要有耐性，都要多学新技术。而家有好多农业技术培训同线上课程，可以多参加。有咩具体问题随时问我。"
            ],
            "hakka": [
                "这个问题问得做得！广东做农业要注意因地制宜，看下当地气候同土壤条件。建议多滴同周围有经验嘅农户聊下，都可以去当地农技站拿专业指导。",
                "种嘢要讲究科学管理，由拣种、施肥、浇水到病虫害防治，每个环节都好紧要。建议做好记录，总结经验，慢慢提高种植技术。",
                "做农业要有耐性，都要多学新技术。今下有好多农业技术培训同线上课程，可以多参加。有么嘢具体问题随时问我。"
            ],
            "teochew": [
                "这个问题问得好！广东做农业着因地制宜，看下当地气候同涂土条件。建议多滴同周围有经验个农户聊下，都可能去当地农技站拿专业指导。",
                "种嘢着讲究科学管理，由拣种、施肥、浇水到病虫害防治，每个环节都上紧要。建议做好记录，总结经验，慢慢提高种植技术。",
                "做农业着有耐性，都要多学新技术。现今有好多农业技术培训同线上课程，可能多参加。有什物具体问题随时问我。"
            ]
        }
        answers = general.get(dialect, general["cantonese"])
        answer = random.choice(answers)
        suggestions = ["样般提高产量？", "有么嘢新技术？", "样般申请农业补贴？"]

    return answer, suggestions


# ==================== 就业对接API ====================

@app.route('/api/employment/jobs', methods=['GET'])
def get_jobs():
    """学员端职位列表（公开，免登录）。

    下发两部分，前端按 `source_type` 区分展示：
      · jobs         —— 企业端发布且**已通过审核**的岗位（可在站内申请 / 收藏）
      · recruitments —— 公开招聘（招募）公告（策展内容，不落库、**不做站内申请**，
                        卡片提供「查看公告」直达发布单位原文）

    注意：jobs 侧的审核过滤在 `database.get_job_listings_filtered()` 里，
    学员端永远拿不到 `pending` 岗位 —— 见该函数 docstring。

    另下发 `category_options`（两类各自的真实条数）+ `salary_filtered_out`：
    前端据此把分类下拉标出条数、并在「按薪资筛选时公告被隐藏」这件事上说清楚，
    避免学员看到一整页「未找到匹配的职位」却不知道为什么（2026-10-07）。
    """
    keyword = request.args.get('keyword', '')
    location = request.args.get('location', '')
    salary_range = request.args.get('salary', '')
    category = request.args.get('category', '')

    # 先取「不含分类过滤」的基础集，才能统计每个分类各多少条
    # （若先按分类过滤，统计永远只剩当前选中的那一项）。
    jobs_base = database.get_job_listings_base(keyword, location, salary_range)
    ent_counts = {}
    for j in jobs_base:
        c = (j.get('category') or '').strip() or '未分类'
        ent_counts[c] = ent_counts.get(c, 0) + 1
    jobs = [j for j in jobs_base if not category or (j.get('category') or '') == category]
    for j in jobs:
        j['source_type'] = 'enterprise'

    # 公开招聘公告：只按 关键词 / 地区 / 类别 过滤。
    # 公告没有「薪资」字段，所以薪资筛选对它不生效（前端也不展示该项）。
    kw = (keyword or '').strip()
    rec_pool, rec_counts = [], {}
    for r in jobs_data.get_recruitment_list():
        if kw and (kw not in (r.get('title') or '')) and (kw not in (r.get('org') or '')) \
                and (kw not in (r.get('description') or '')):
            continue
        if location and location != r.get('region'):
            continue
        r['source_type'] = 'public_recruit'
        rec_pool.append(r)
        c = (r.get('category') or '').strip() or '未分类'
        rec_counts[c] = rec_counts.get(c, 0) + 1

    recruitments = [r for r in rec_pool if not category or r.get('category') == category]

    notes = jobs_data.get_recruitment_notes()
    return jsonify({
        "success": True,
        "jobs": jobs,
        "recruitments": recruitments,
        "recruit_source_note": notes['source_note'],
        "recruit_disclaimer": notes['disclaimer'],
        # 分类下拉：两组各自真实的条数（口径 = 已应用 关键词/地点/薪资，未应用分类）
        "category_options": {
            "enterprise": _category_option_list(ent_counts, database.ENTERPRISE_JOB_CATEGORIES),
            "recruit": _category_option_list(rec_counts, jobs_data.CATEGORY_LIST),
        },
        # 薪资筛选对公告不生效，被隐藏的公告条数 —— 前端据此给出明确说明
        "recruit_hidden_by_salary": len(rec_pool) if salary_range else 0,
        # 尚未过审的企业岗位条数。企业发布的岗位要经管理员审核才露出，
        # 若此刻一条都没通过，学员端应说明「岗位审核中」而不是「没有岗位」。
        "enterprise_review_pending": database.count_pending_job_listings(),
    })


def _category_option_list(counts, known):
    """`{分类: 条数}` → `[{"value","count"}]`。

    `known` 里的分类**即使 0 条也保留**（前端标「（暂无）」）——
    把死分类直接从下拉里删掉，学员会以为平台不支持这类岗位；
    而数据里冒出来的新分类（企业端分类是自由文本）追加在后面，不漏。
    顺序固定为 `known` 原始顺序，避免条数变化时选项来回跳。
    """
    vals = list(known)
    vals += [k for k in counts if k not in vals]
    return [{"value": k, "count": counts.get(k, 0)} for k in vals]


@app.route('/api/employment/jobs/<int:job_id>', methods=['GET'])
def get_job_detail(job_id):
    job = database.get_job_by_id(job_id)
    # 未通过审核的岗位对学员端等同「不存在」——
    # 否则随便猜个 id 就能看到 pending 岗位，审核门禁被直链绕过。
    if not job or (job.get('review_status') or '') != 'approved':
        return jsonify({"success": False, "message": "职位不存在或尚未通过审核"}), 404
    return jsonify({"success": True, "job": job})


@app.route('/api/employment/jobs/<int:job_id>/similar', methods=['GET'])
def get_similar_jobs(job_id):
    job = database.get_job_by_id(job_id)
    if not job or (job.get('review_status') or '') != 'approved':
        return jsonify({"success": True, "jobs": []})
    similar = database.get_similar_jobs(job_id, job.get('category', ''), 3)
    return jsonify({"success": True, "jobs": similar})


@app.route('/api/employment/certificates/<user_id>', methods=['GET'])
def get_certificates(user_id):
    certs = database.get_certificates(user_id)
    return jsonify({"success": True, "certificates": certs})


@app.route('/api/employment/points/<user_id>', methods=['GET'])
def get_points(user_id):
    pts = database.get_points(user_id)
    return jsonify({"success": True, "points": pts['balance'], "history": pts['history']})


@app.route('/api/employment/exchange', methods=['POST'])
def exchange_points():
    data = request.get_json()
    user_id = data.get('user_id')
    item = data.get('item', '商品')
    cost = data.get('cost', 0)

    new_balance = database.update_points(user_id, -cost, f"兑换{item}")
    if new_balance == -1:
        return jsonify({"success": False, "message": "积分不足"})
    return jsonify({"success": True, "message": f"成功兑换：{item}", "remaining_points": new_balance})


@app.route('/api/employment/apply', methods=['POST'])
def apply_job():
    """申请职位"""
    data = request.get_json()
    user_id = data.get('user_id')
    job_id = data.get('job_id')

    if not user_id or not job_id:
        return jsonify({"success": False, "message": "参数不完整"})

    result = database.apply_for_job(user_id, job_id)
    if result == 'ok':
        # 申请成功加积分
        database.update_points(user_id, 20, "申请职位奖励")
        return jsonify({"success": True, "message": "申请成功！已获得20积分奖励",
                        # 前端据此在提示里补一句「你还没有填写简历」——
                        # 否则学员以为简历已经随申请投出去了（2026-10-07）
                        "has_resume": _user_has_resume(user_id)})
    if result == 'dup':
        return jsonify({"success": False, "message": "您已申请过该职位"})
    # 'unavailable'：职位不存在或未通过审核
    return jsonify({"success": False, "message": "该职位不存在或尚未通过审核，无法申请"})


@app.route('/api/employment/applications/<user_id>', methods=['GET'])
def get_user_applications(user_id):
    status_filter = request.args.get('status', '')
    apps = database.get_user_applications(user_id, status_filter)
    return jsonify({"success": True, "applications": apps})


@app.route('/api/employment/applications/<user_id>/counts', methods=['GET'])
def get_application_counts(user_id):
    counts = database.get_application_counts(user_id)
    return jsonify({"success": True, "counts": counts})


@app.route('/api/employment/save', methods=['POST'])
def save_job():
    data = request.get_json()
    user_id = data.get('user_id')
    job_id = data.get('job_id')
    if not user_id or not job_id:
        return jsonify({"success": False, "message": "参数不完整"})
    success = database.save_job(user_id, job_id)
    if success:
        return jsonify({"success": True, "message": "收藏成功"})
    return jsonify({"success": False, "message": "已收藏过该职位"})


@app.route('/api/employment/save', methods=['DELETE'])
def unsave_job():
    data = request.get_json()
    user_id = data.get('user_id')
    job_id = data.get('job_id')
    if not user_id or not job_id:
        return jsonify({"success": False, "message": "参数不完整"})
    database.unsave_job(user_id, job_id)
    return jsonify({"success": True, "message": "已取消收藏"})


@app.route('/api/employment/saved/<user_id>', methods=['GET'])
def get_saved_jobs(user_id):
    saved_ids = database.get_saved_jobs(user_id)
    return jsonify({"success": True, "saved_ids": saved_ids})


@app.route('/api/employment/stats/<user_id>', methods=['GET'])
def get_employment_stats(user_id):
    stats = database.get_employment_stats(user_id)
    return jsonify({"success": True, "stats": stats})


# ==================== 就业对接：能力档案 / 在线简历 / 求职意向 ====================
#
# 链路设计（2026-10-06 用户拍板「把这些功能弄成一条链路」）：
#   能力档案 → AI 简历 → 岗位匹配 → 投递/报名 → 反馈回流
#
# 两条投递通道的区别（务必保持）：
#   · 企业岗位（job_listings）—— 站内投递，走 job_applications，企业端「简历管理」可见并给反馈；
#   · 公开招聘公告（jobs_data.py）—— **平台不是官方报名系统**，只做「求职意向登记」（job_intents），
#     报名由学员按公告原文自行完成，接口文案与前端都必须显式声明这一点。

def _self_only(user_id):
    """校验「当前登录用户就是 user_id 本人」——求职资料属个人数据，不可跨用户读写。

    返回 (user, None) 或 (None, (response, status))。
    """
    user = _get_session_user()
    if not user:
        return None, (jsonify({"success": False, "message": "请先登录"}), 401)
    if user['username'] != user_id:
        return None, (jsonify({"success": False, "message": "无权访问他人的求职资料"}), 403)
    return user, None


@app.route('/api/employment/profile/<user_id>', methods=['GET'])
def get_employment_profile(user_id):
    """能力档案：聚合学员**真实**的证书 / 学习进度 / 实训成绩 / 积分。

    这些数据同时是 AI 简历的素材来源 —— 前端要把它与简历面板并排展示，
    让学员清楚「AI 是根据这些东西写的」。
    """
    user, err = _self_only(user_id)
    if err:
        return err
    profile = database.get_learner_profile(user_id)
    return jsonify({"success": True, "profile": profile})


@app.route('/api/employment/resume/<user_id>', methods=['GET'])
def get_resume(user_id):
    user, err = _self_only(user_id)
    if err:
        return err
    return jsonify({"success": True, "resume": database.get_resume(user_id)})


@app.route('/api/employment/resume/<user_id>', methods=['PUT'])
def save_resume(user_id):
    """保存在线简历（学员自填内容）。AI 产出同样走这里落库，由学员确认后再保存。"""
    user, err = _self_only(user_id)
    if err:
        return err
    data = request.get_json(silent=True) or {}
    resume = database.save_resume(user_id, data)
    return jsonify({"success": True, "message": "简历已保存", "resume": resume})


# AI 可起草/润色的段落。刻意**不含**「学历 / 工作年限 / 期望岗位」这类
# 平台无从核实的字段 —— 那些必须由学员自己填。
RESUME_AI_SECTIONS = {
    'self_eval': '自我评价',
    'skills': '专业技能',
    'experience': '工作与实践经历',
}

RESUME_AI_SYSTEM_PROMPT = """你是求职简历写作助手，服务于「农村技能人才就业平台」的学员。

你的任务：**仅根据**系统提供的学员真实数据，撰写或润色简历的指定段落。

必须遵守的硬性规则：
1. 只使用提供的数据。**绝不编造**工作经历、学历、学校、公司、证书、获奖、年限、数字。
2. 标注为「学习中」「尚未获得」「未开始学习」的证书，**不得**写成「已获得」「已掌握」「熟练」。
3. 数据里没有的信息，用【待补充：具体内容】的形式占位，不要猜测，也不要用行业常见说法填充。
4. 不使用夸张自夸的措辞（如「顶尖」「资深多年」「行业领先」「精通」），平实客观即可。
5. 只输出该段落的正文。不要写标题、不要写解释说明、不要使用 Markdown 标记。
6. 使用简体中文，控制在 150 字以内。"""


def _profile_for_ai(profile):
    """把能力档案整理成交给 AI 的纯文本素材。

    ⚠️ 只列**真实存在**的字段，缺项一律标注「（未填写）」而不是编一个合理值。
    证书必须带状态前缀，否则模型很容易把「学习中」写成「已获得」。
    """
    basic = profile.get('basic') or {}
    rows = [
        '姓名：%s' % (basic.get('name') or '（未填写）'),
        '所在地区：%s' % (basic.get('region') or '（未填写）'),
    ]

    learning = profile.get('learning')
    if learning:
        rows.append('平台学习方向：%s（课程完成度 %s%%）' % (
            learning.get('direction') or '（未填写）', learning.get('progress', 0)))
    else:
        rows.append('平台学习方向：（未填写）')

    certs = profile.get('certificates') or []
    if certs:
        parts = []
        for c in certs:
            status = (c.get('status') or '').lower()
            if c.get('earned'):
                tail = ('，取得时间 ' + c['date']) if c.get('date') else ''
                parts.append('%s（已获得%s）' % (c['name'], tail))
            elif status == 'in_progress':
                parts.append('%s（学习中，进度 %s%%，尚未获得）' % (c['name'], c.get('progress', 0)))
            else:
                parts.append('%s（未开始学习）' % c['name'])
        rows.append('平台学习证书：' + '；'.join(parts))
    else:
        rows.append('平台学习证书：（无）')

    scored = [t for t in (profile.get('training') or []) if t.get('scored')]
    if scored:
        rows.append('平台实训成绩：' + '；'.join('%s %s 分' % (t['title'], t['score']) for t in scored))
    else:
        rows.append('平台实训成绩：（无已评分记录）')

    if profile.get('points'):
        rows.append('平台学习积分：%s' % profile['points'])

    return '\n'.join(rows)


@app.route('/api/employment/resume/ai', methods=['POST'])
def resume_ai_generate():
    """AI 简历辅助：**仅根据学员真实数据**起草/润色指定段落。

    红线（与全项目口径一致）：
      · AI 只做「组织与表达」，**不做事实生成**；未提供的信息一律用【待补充】占位；
      · 失败必须可见 —— 返回 503 + 明确 code，绝不返回 success=True 的兜底文案；
      · 调用成功后会置 `resumes.ai_used = 1`，前端据此如实标注「本段经 AI 辅助生成」。
    """
    data = request.get_json(silent=True) or {}
    user_id = data.get('user_id')
    section = (data.get('section') or '').strip()
    draft = data.get('draft') or ''

    if not user_id:
        return jsonify({"success": False, "code": "bad_request", "message": "参数不完整"}), 400
    user, err = _self_only(user_id)
    if err:
        return err
    if section not in RESUME_AI_SECTIONS:
        return jsonify({"success": False, "code": "bad_section",
                        "message": "不支持的简历段落"}), 400
    if isinstance(draft, str) and len(draft) > RESUME_AI_SECTION_MAX_LEN:
        return jsonify({"success": False, "code": "draft_too_long",
                        "message": "内容过长，请精简后再试"}), 400

    if _rate_limited('resume-ai:' + _client_key(), RESUME_AI_RATE_LIMIT):
        return jsonify({"success": False, "code": "rate_limited",
                        "message": "AI 使用过于频繁，请稍后再试"}), 429

    if not _ai_configured():
        return jsonify({"success": False, "code": "ai_not_configured",
                        "message": "AI 辅助功能尚未启用，请联系管理员（12316）"}), 503

    profile = database.get_learner_profile(user_id)
    material = _profile_for_ai(profile)
    label = RESUME_AI_SECTIONS[section]

    resume = database.get_resume(user_id) or {}
    own_input = ''
    if section == 'experience':
        exp = resume.get('experience') or []
        if isinstance(exp, list) and exp:
            own_input = '\n'.join(
                '- %s / %s / %s：%s' % (e.get('company') or '', e.get('position') or '',
                                        e.get('period') or '', (e.get('desc') or '').strip())
                for e in exp if isinstance(e, dict))
    elif isinstance(draft, str):
        own_input = draft.strip()

    user_prompt = '【学员真实数据（唯一可用事实来源）】\n%s\n' % material
    if own_input:
        user_prompt += '\n【学员本人已填写的原文（可在不改变事实的前提下润色）】\n%s\n' % own_input
    elif section != 'experience':
        user_prompt += '\n【学员本人已填写的原文】（暂无，请完全基于上面的真实数据来写）\n'
    user_prompt += '\n请撰写「%s」这一段。' % label

    try:
        text = call_ai_service(
            RESUME_AI_SYSTEM_PROMPT, user_prompt,
            temperature=0.4, max_tokens=600 + AI_REASONING_TOKEN_RESERVE)
    except Exception as e:
        app.logger.warning('简历 AI 生成失败: %s', e)
        return jsonify({"success": False, "code": "ai_unavailable",
                        "message": "AI 服务暂时不可用，请稍后重试"}), 503

    if not text or not str(text).strip():
        return jsonify({"success": False, "code": "ai_unavailable",
                        "message": "AI 没有返回内容，请稍后重试"}), 503

    database.mark_resume_ai_used(user_id)
    return jsonify({
        "success": True,
        "section": section,
        "section_label": label,
        "text": str(text).strip(),
        "notice": "本段由 AI 根据你的平台学习数据起草，请核对其中的每一项事实后再用于投递。",
    })


@app.route('/api/employment/intent', methods=['POST'])
def add_job_intent():
    """登记对某条公开招聘公告的求职意向（幂等）。

    ⚠️ 平台**不是**官方报名系统：这里只记录意向，**不代表报名成功**。
    前端的成功提示与公告详情页都必须写明「请按公告原文自行报名」。
    """
    data = request.get_json(silent=True) or {}
    user_id = data.get('user_id')
    recruit_key = (data.get('recruit_key') or '').strip()
    note = data.get('note') or ''

    if not user_id or not recruit_key:
        return jsonify({"success": False, "code": "bad_request", "message": "参数不完整"}), 400
    user, err = _self_only(user_id)
    if err:
        return err
    if not jobs_data.get_recruitment(recruit_key):
        return jsonify({"success": False, "code": "not_found",
                        "message": "公告不存在或已下架"}), 404

    created = database.add_job_intent(user_id, recruit_key, note)
    return jsonify({
        "success": True,
        "created": created,
        "message": "已记录求职意向" if created else "意向备注已更新",
        "notice": "本平台不代办报名，请按公告原文的要求和时间自行报名。",
    })


@app.route('/api/employment/intent', methods=['DELETE'])
def remove_job_intent():
    """取消求职意向登记。"""
    data = request.get_json(silent=True) or {}
    user_id = data.get('user_id')
    recruit_key = (data.get('recruit_key') or '').strip()
    if not user_id or not recruit_key:
        return jsonify({"success": False, "code": "bad_request", "message": "参数不完整"}), 400
    user, err = _self_only(user_id)
    if err:
        return err
    removed = database.remove_job_intent(user_id, recruit_key)
    return jsonify({"success": True, "removed": removed,
                    "message": "已取消意向登记" if removed else "未找到该意向记录"})


@app.route('/api/employment/my-jobs/<user_id>', methods=['GET'])
def get_my_jobs(user_id):
    """「我的求职」聚合：企业岗位投递 + 公开招聘意向。

    两条通道在数据结构上完全不同（前者挂在数字 job_id 上、后者挂在公告字符串 key 上），
    这里统一成前端可直接渲染的两组，并**如实标注通道类型**。
    """
    user, err = _self_only(user_id)
    if err:
        return err

    applications = database.get_user_applications(user_id)
    for a in applications:
        a['channel'] = 'enterprise'

    # 意向记录只有 recruit_key，这里补上公告的标题/单位/地区/报名截止，
    # 并对**已从 jobs_data 中移除**的公告做剪枝（否则会渲染出一条点不开的空卡）。
    intents = []
    for it in database.get_job_intents(user_id):
        rec = jobs_data.get_recruitment(it['recruit_key'])
        if not rec:
            continue
        intents.append({
            'channel': 'public_recruit',
            'recruit_key': it['recruit_key'],
            'note': it['note'],
            'created_at': it['created_at'],
            'title': rec.get('title') or '',
            'org': rec.get('org') or '',
            'region': rec.get('region') or '',
            'category': rec.get('category') or '',
            'deadline': rec.get('deadline') or '',
            'status': rec.get('status') or 'unknown',
            'status_label': rec.get('status_label') or '',
        })

    return jsonify({
        "success": True,
        "applications": applications,
        "intents": intents,
        "intent_notice": jobs_data.get_recruitment_notes().get('disclaimer', ''),
        # ⚠️ 平台**不强制**先写简历才能投递（投递只记一条申请 + 给积分），
        # 但企业端看到的是「无简历的空申请」。这里如实下发简历状态，
        # 前端据此给出持久提示 —— 而不是让文案和实际行为互相打架（2026-10-07）。
        "has_resume": _user_has_resume(user_id),
    })


def _user_has_resume(user_id):
    """学员是否填过简历（判断「有内容」而非「有行」：只有意向岗位或任一正文段才算）。"""
    r = database.get_resume(user_id) or {}
    keys = ('title', 'region', 'education', 'work_years', 'self_eval',
            'skills', 'experience', 'phone', 'email')
    return any((r.get(k) or '').strip() for k in keys)


# ==================== 教师管理API ====================

@app.route('/api/teacher/dashboard', methods=['GET'])
@_require_role(*_TEACHER_ROLES)
def get_teacher_dashboard():
    # 2026-10-07：原返回里有一段硬编码的 recent_activities（"张小明 2小时前" 等
    # 编造数据），前端从未渲染它。按「不编造」红线直接移除，只回真实统计。
    stats = database.get_dashboard_stats()
    return jsonify({"success": True, "dashboard": {"stats": stats}})


@app.route('/api/teacher/students', methods=['GET'])
@_require_role(*_TEACHER_ROLES)
def get_students():
    search = request.args.get('search', None)
    students = database.get_students(search)
    # 附上「证书真实完成度」—— 名册自己的 progress 是手填字段，学员端没有任何入口
    # 会更新它；前端「已获得证书」的判定改用真实证书数据（2026-10-07）。
    comp = {r['id']: r for r in database.get_roster_completion()}
    for s in students:
        r = comp.get(s['id'])
        if r:
            s['cert_total'] = r['cert_total']
            s['cert_earned'] = r['cert_earned']
            s['completion'] = r['completion']
            s['has_cert_data'] = r['has_cert_data']
    return jsonify({"success": True, "students": students})


@app.route('/api/teacher/students/<student_id>', methods=['GET'])
@_require_role(*_TEACHER_ROLES)
def get_student_detail(student_id):
    """获取学员详情（附证书真实完成度）"""
    student = database.get_student(student_id)
    if student:
        for r in database.get_roster_completion():
            if r['id'] == student_id:
                student.update({
                    'cert_total': r['cert_total'], 'cert_earned': r['cert_earned'],
                    'completion': r['completion'], 'has_cert_data': r['has_cert_data'],
                })
                break
        return jsonify({"success": True, "student": student})
    return jsonify({"success": False, "message": "未找到学员"})


@app.route('/api/teacher/students/add', methods=['POST'])
@_require_role(*_TEACHER_ROLES)
def add_student():
    """添加学员（名册行），并可选「关联已有账号」或「新建账号」。

    2026-10-07 用户拍板：名册与账号长期是两套数据，新加的学员登不进来、
    收不到通知、证书也进不了统计。现在添加时可以在三种模式里选一种：
      · link_username  —— 关联一个尚未被占用的学员账号；
      · new_username + new_password —— 直接为该学员新建平台账号并关联；
      · 都不传        —— 只建名册（接口会在 message 里明确提示「无法登录」）。
    失败时不留半成品：账号建好但关联失败，会把刚插入的名册行删掉。
    """
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    class_name = data.get('class_name', '')
    direction = data.get('direction', '')
    link_username = (data.get('link_username') or '').strip()
    new_username = (data.get('new_username') or '').strip()
    new_password = (data.get('new_password') or '').strip()

    if not name:
        return jsonify({"success": False, "message": "请输入学员姓名"}), 400

    account_username = ''
    if new_username:
        if len(new_password) < 6:
            return jsonify({"success": False, "message": "初始密码至少 6 位"}), 400
        uid, msg = database.register_user(new_username, new_password, name, 'student')
        if not uid:
            return jsonify({"success": False, "message": f"账号创建失败：{msg}"}), 400
        account_username = uid
    elif link_username:
        account_username = link_username

    sid = database.add_student(name, class_name, direction)
    if account_username:
        ok, msg = database.set_student_account(sid, account_username)
        if not ok:
            # 关联失败（账号不存在 / 已被别人占用…）→ 回滚名册行，避免留下孤儿记录
            database.delete_student(sid)
            return jsonify({"success": False, "message": msg}), 400
        tail = (f'已新建并关联账号 {account_username}' if new_username
                else f'已关联账号 {account_username}')
    else:
        tail = '尚未关联平台账号，该学员暂时无法登录、收不到站内通知'

    return jsonify({"success": True, "message": f"添加成功，学员编号：{sid}；{tail}",
                    "student_id": sid, "linked_account": account_username})


@app.route('/api/teacher/linkable-accounts', methods=['GET'])
@_require_role(*_TEACHER_ROLES)
def get_linkable_accounts():
    """可供名册关联的学员账号（role=student 且未被占用）。"""
    return jsonify({"success": True, "accounts": database.get_linkable_student_accounts()})


@app.route('/api/teacher/students/<student_id>/link', methods=['POST'])
@_require_role(*_TEACHER_ROLES)
def link_student_account(student_id):
    """关联 / 解除名册与平台账号。body: {"username": "xxx"}，空串表示解除。"""
    data = request.get_json() or {}
    username = (data.get('username') or '').strip()
    ok, msg = database.set_student_account(student_id, username)
    if not ok:
        return jsonify({"success": False, "message": msg}), 400
    return jsonify({"success": True, "message": msg, "user_id": username})


@app.route('/api/teacher/students/<student_id>', methods=['PUT'])
@_require_role(*_TEACHER_ROLES)
def update_student(student_id):
    """编辑学员"""
    data = request.get_json()
    result = database.update_student(
        student_id,
        name=data.get('name'),
        class_name=data.get('class_name'),
        direction=data.get('direction'),
        progress=data.get('progress'),
        status=data.get('status')
    )
    if result:
        return jsonify({"success": True, "message": "更新成功"})
    return jsonify({"success": False, "message": "未找到学员"})


@app.route('/api/teacher/students/<student_id>', methods=['DELETE'])
@_require_role(*_TEACHER_ROLES)
def delete_student(student_id):
    """删除学员"""
    result = database.delete_student(student_id)
    if result:
        return jsonify({"success": True, "message": "删除成功"})
    return jsonify({"success": False, "message": "未找到学员"})


@app.route('/api/teacher/reports/generate', methods=['POST'])
@_require_role(*_TEACHER_ROLES)
def generate_report():
    """AI生成教学报告 — 接受自然语言prompt，灵活生成"""
    data = request.get_json()
    user_prompt = data.get('prompt', '').strip()
    if not user_prompt:
        return jsonify({"success": False, "message": "请输入分析需求"}), 400

    try:
        # 2026-10-07：改用「证书真实完成度」口径（get_roster_completion）。
        # 原 context 直接聚合 students.progress —— 那是**手填**字段，学员端没有任何
        # 入口会更新它，AI 据此写出的「学员进度」与真实学习情况无关。
        roster = database.get_roster_completion()
        if not roster:
            return jsonify({"success": True, "report": {
                "title": "AI 教学报告",
                "generated_at": datetime.now().isoformat(),
                "content": "## 暂无数据\n\n当前没有学员数据，请先添加学员后再生成报告。"
            }})

        # 全量数据采集
        total = len(roster)
        with_data = [s for s in roster if s['has_cert_data']]
        no_cert = [s for s in roster if not s['has_cert_data']]
        avg_progress = (sum(s['completion'] for s in with_data) / len(with_data)) if with_data else 0

        directions = {}
        for s in roster:
            d = s.get('direction', '未分类')
            directions.setdefault(d, {'count': 0, 'progresses': [], 'students': []})
            directions[d]['count'] += 1
            directions[d]['progresses'].append(s['completion'])
            directions[d]['students'].append(s['name'])

        # 完成度分段（只统计有证书记录的学员）
        brackets = {'0-25%': 0, '25-50%': 0, '50-75%': 0, '75-100%': 0}
        for s in with_data:
            p = s['completion']
            if p < 25: brackets['0-25%'] += 1
            elif p < 50: brackets['25-50%'] += 1
            elif p < 75: brackets['50-75%'] += 1
            else: brackets['75-100%'] += 1

        # 风险/优秀只在「有证书记录」的学员里判 —— 没有证书记录 ≠ 0% 完成，
        # 把他们算进风险名单属于编造结论。
        at_risk = [s for s in with_data if s['completion'] < 30]
        excellent = [s for s in with_data if s['completion'] >= 80]
        completed = [s for s in roster if s['cert_earned'] > 0]

        # 组装数据上下文
        dir_lines = []
        for d, info in directions.items():
            avg = sum(info['progresses']) / info['count']
            hi = max(info['progresses'])
            lo = min(info['progresses'])
            names = '、'.join(info['students'])
            dir_lines.append(f"- {d}：{info['count']}人，平均完成度{avg:.1f}%，最高{hi}%，最低{lo}%，学员：{names}")

        student_lines = []
        for s in roster:
            if not s['has_cert_data']:
                status = '暂无证书记录' + ('（未关联平台账号）' if not s['has_account'] else '')
            elif s['cert_earned'] > 0:
                status = '已获得证书'
            else:
                status = '学习中'
            student_lines.append(
                f"- {s['name']}（学号 {s['id']}{'，账号 ' + s['user_id'] if s['has_account'] else '，未关联平台账号'}）"
                f"方向={s['direction']} 完成度={s['completion']}% "
                f"证书={s['cert_earned']}/{s['cert_total']}已获得 状态={status}")

        risk_lines = [f"- {s['name']}：完成度{s['completion']}%，方向{s['direction']}" for s in at_risk]
        good_lines = [f"- {s['name']}：完成度{s['completion']}%，方向{s['direction']}" for s in excellent]

        data_context = f"""数据口径：证书真实完成度（学员名下证书进度的平均值；没有任何证书记录的学员单独列出，不计入完成度分布）
学员总数：{total}
平均完成度：{avg_progress:.1f}%（有证书记录的 {len(with_data)} 人）
暂无证书记录：{len(no_cert)}人{('（' + '、'.join(s['name'] for s in no_cert) + '）') if no_cert else ''}
方向数量：{len(directions)}
已获得证书学员：{len(completed)}人
风险学员（完成度<30%）：{len(at_risk)}人
优秀学员（完成度>=80%）：{len(excellent)}人

完成度分布：
{chr(10).join(f'{k}: {v}人' for k, v in brackets.items())}

各方向详情：
{chr(10).join(dir_lines)}

全部学员：
{chr(10).join(student_lines)}

风险学员名单：
{chr(10).join(risk_lines) if risk_lines else '无'}

优秀学员名单：
{chr(10).join(good_lines) if good_lines else '无'}"""

        result = call_ai_service(
            system_prompt=(
                "你是一位资深教学数据分析师。用户会给你一份学员数据和一个具体的分析问题。"
                "你必须紧紧围绕用户的问题来生成报告，不要生成与问题无关的内容。\n"
                "要求：\n"
                "1）报告标题和所有小节都要围绕用户的问题展开\n"
                "2）引用具体数据和学员姓名，不要泛泛而谈\n"
                "3）建议要具体可执行，不要空话套话\n"
                "4）不同问题生成完全不同的报告结构和内容，禁止千篇一律"
            ),
            user_message=f"## 用户的问题\n{user_prompt}\n\n## 学员数据\n{data_context}\n\n请围绕上述问题生成报告。"
        )

        # 构建概览数据
        overview = {
            "total": total,
            "avg_progress": round(avg_progress, 1),
            "no_cert_count": len(no_cert),
            "direction_count": len(directions),
            "completed_count": len(completed),
            "risk_count": len(at_risk),
            "excellent_count": len(excellent),
            "brackets": brackets,
            "directions": [
                {"name": d, "count": info['count'],
                 "avg_progress": round(sum(info['progresses'])/info['count'], 1),
                 "students": info['students']}
                for d, info in directions.items()
            ],
            "at_risk": [{"name": s['name'], "progress": s['completion'], "direction": s['direction']} for s in at_risk],
            "excellent": [{"name": s['name'], "progress": s['completion'], "direction": s['direction']} for s in excellent]
        }

        # 根据 prompt 分析报告主题，决定概览侧重点
        p = user_prompt.lower()
        if any(k in p for k in ['风险', '预警', '掉队', '落后', '关注', '帮扶', '干预']):
            overview['focus'] = 'risk'
            overview['title'] = '风险预警概览'
            overview['highlight_stats'] = ['risk_count', 'total', 'avg_progress']
        elif any(k in p for k in ['方向', '对比', '比较', '哪个', '排名', '对比分析']):
            overview['focus'] = 'direction'
            overview['title'] = '方向对比概览'
            overview['highlight_stats'] = ['direction_count', 'total', 'avg_progress']
        elif any(k in p for k in ['进度', '滞后', '完成', '速度', '加快']):
            overview['focus'] = 'progress'
            overview['title'] = '进度分析概览'
            overview['highlight_stats'] = ['avg_progress', 'completed_count', 'total']
        elif any(k in p for k in ['优秀', '突出', '表扬', '先进', '领先']):
            overview['focus'] = 'excellent'
            overview['title'] = '优秀学员概览'
            overview['highlight_stats'] = ['excellent_count', 'completed_count', 'total']
        elif any(k in p for k in ['预测', '趋势', '未来', '下月', '计划']):
            overview['focus'] = 'trend'
            overview['title'] = '趋势预测概览'
            overview['highlight_stats'] = ['avg_progress', 'completed_count', 'risk_count']
        elif any(k in p for k in ['效果', '评估', '教学', '质量']):
            overview['focus'] = 'performance'
            overview['title'] = '教学效果概览'
            overview['highlight_stats'] = ['completed_count', 'avg_progress', 'excellent_count']
        else:
            overview['focus'] = 'general'
            overview['title'] = '班级总览'
            overview['highlight_stats'] = ['total', 'avg_progress', 'direction_count']

        return jsonify({"success": True, "report": {
            "title": "AI 教学报告",
            "generated_at": datetime.now().isoformat(),
            "content": result,
            "overview": overview
        }})

    except Exception as e:
        logger.error(f"报告生成失败: {e}")
        # 兜底报告（口径与主路径一致：证书真实完成度）
        try:
            roster = database.get_roster_completion()
            fallback = _build_fallback_report(roster, user_prompt)
            overview = _build_fallback_overview(roster, user_prompt)
        except Exception:
            fallback = "## 生成失败\n\nAI 服务暂时不可用，请稍后重试。"
            overview = None
        resp = {"success": True, "report": {
            "title": "AI 教学报告",
            "generated_at": datetime.now().isoformat(),
            "content": fallback
        }}
        if overview:
            resp["report"]["overview"] = overview
        return jsonify(resp)


def _normalize_roster_rows(students):
    """把 get_roster_completion() 的行归一成报告用的统一结构。

    ⚠️ 2026-10-07 起学情/报告口径 = **证书真实完成度**（students.progress 是手填字段，
    不再使用）。归一后统一叫 `progress`，下文沿用原变量名，避免两套口径并存。
    `has_cert_data=False` 表示该学员名下没有任何证书记录 —— 不能当成「0% 完成」。
    """
    rows = []
    for s in students or []:
        rows.append({
            'id': s.get('id', ''), 'name': s.get('name', ''),
            'direction': s.get('direction') or '未分类',
            'progress': s.get('completion', 0) or 0,
            'has_cert_data': bool(s.get('has_cert_data')),
            'cert_earned': s.get('cert_earned', 0),
            'cert_total': s.get('cert_total', 0),
            'has_account': bool(s.get('has_account')),
        })
    return rows


def _build_fallback_overview(students, prompt):
    """兜底报告的概览数据（口径：证书真实完成度）"""
    students = _normalize_roster_rows(students)
    if not students:
        return None
    total = len(students)
    with_data = [s for s in students if s['has_cert_data']]
    avg_progress = (sum(s['progress'] for s in with_data) / len(with_data)) if with_data else 0
    directions = {}
    for s in students:
        d = s.get('direction', '未分类')
        directions.setdefault(d, {'count': 0, 'progresses': [], 'students': []})
        directions[d]['count'] += 1
        directions[d]['progresses'].append(s['progress'])
        directions[d]['students'].append(s['name'])
    at_risk = [s for s in with_data if s['progress'] < 30]
    excellent = [s for s in with_data if s['progress'] >= 80]
    completed = [s for s in students if s['cert_earned'] > 0]
    brackets = {'0-25%': 0, '25-50%': 0, '50-75%': 0, '75-100%': 0}
    for s in with_data:
        p = s['progress']
        if p < 25: brackets['0-25%'] += 1
        elif p < 50: brackets['25-50%'] += 1
        elif p < 75: brackets['50-75%'] += 1
        else: brackets['75-100%'] += 1

    overview = {
        "total": total, "avg_progress": round(avg_progress, 1),
        "no_cert_count": len(students) - len(with_data),
        "direction_count": len(directions), "completed_count": len(completed),
        "risk_count": len(at_risk), "excellent_count": len(excellent),
        "brackets": brackets,
        "directions": [{"name": d, "count": info['count'],
                        "avg_progress": round(sum(info['progresses'])/info['count'], 1),
                        "students": info['students']} for d, info in directions.items()],
        "at_risk": [{"name": s['name'], "progress": s['progress'], "direction": s['direction']} for s in at_risk],
        "excellent": [{"name": s['name'], "progress": s['progress'], "direction": s['direction']} for s in excellent]
    }

    p = prompt.lower()
    if any(k in p for k in ['风险', '预警', '掉队', '落后', '关注', '帮扶', '干预']):
        overview['focus'] = 'risk'; overview['title'] = '风险预警概览'
        overview['highlight_stats'] = ['risk_count', 'total', 'avg_progress']
    elif any(k in p for k in ['方向', '对比', '比较', '哪个', '排名']):
        overview['focus'] = 'direction'; overview['title'] = '方向对比概览'
        overview['highlight_stats'] = ['direction_count', 'total', 'avg_progress']
    elif any(k in p for k in ['进度', '滞后', '完成', '速度']):
        overview['focus'] = 'progress'; overview['title'] = '进度分析概览'
        overview['highlight_stats'] = ['avg_progress', 'completed_count', 'total']
    elif any(k in p for k in ['优秀', '突出', '表扬', '领先']):
        overview['focus'] = 'excellent'; overview['title'] = '优秀学员概览'
        overview['highlight_stats'] = ['excellent_count', 'completed_count', 'total']
    elif any(k in p for k in ['预测', '趋势', '未来', '计划']):
        overview['focus'] = 'trend'; overview['title'] = '趋势预测概览'
        overview['highlight_stats'] = ['avg_progress', 'completed_count', 'risk_count']
    elif any(k in p for k in ['效果', '评估', '教学', '质量']):
        overview['focus'] = 'performance'; overview['title'] = '教学效果概览'
        overview['highlight_stats'] = ['completed_count', 'avg_progress', 'excellent_count']
    else:
        overview['focus'] = 'general'; overview['title'] = '班级总览'
        overview['highlight_stats'] = ['total', 'avg_progress', 'direction_count']
    return overview


def _build_fallback_report(students, prompt):
    """AI不可用时根据prompt生成不同的兜底报告（口径：证书真实完成度）"""
    students = _normalize_roster_rows(students)
    if not students:
        return "## 暂无数据\n\n当前没有学员数据，请先添加学员。"

    total = len(students)
    with_data = [s for s in students if s['has_cert_data']]
    no_cert = [s for s in students if not s['has_cert_data']]
    avg_progress = (sum(s['progress'] for s in with_data) / len(with_data)) if with_data else 0
    directions = {}
    for s in students:
        d = s.get('direction', '未分类')
        directions.setdefault(d, []).append(s)

    # 风险/优秀只在「有证书记录」的学员里判 —— 没有证书记录 ≠ 0% 完成
    at_risk = sorted([s for s in with_data if s['progress'] < 30], key=lambda x: x['progress'])
    excellent = sorted([s for s in with_data if s['progress'] >= 80], key=lambda x: -x['progress'])
    completed = [s for s in students if s['cert_earned'] > 0]
    mid_risk = [s for s in with_data if 30 <= s['progress'] < 50]

    p = prompt.lower()

    # 风险主题
    if any(k in p for k in ['风险', '预警', '掉队', '落后', '关注', '帮扶', '干预']):
        lines = [
            "> 数据口径：证书真实完成度（学员名下证书进度的平均值）",
            "",
            "## 一、风险概况",
            f"当前共 **{total}** 名学员，其中 **{len(at_risk)}** 人完成度低于30%，处于高风险状态。",
            f"另有 **{len(mid_risk)}** 人完成度在30%-50%之间，需要持续关注。",
            f"**{len(no_cert)}** 人暂无任何证书记录，无法评估（不是 0% 完成）。",
            ""
        ]
        if at_risk:
            lines.append("## 二、高风险学员详情")
            for s in at_risk:
                lines.append(f"- **{s['name']}**（{s['direction']}）：完成度仅 **{s['progress']}%**，建议优先介入")
            lines.append("")
        if mid_risk:
            lines.append("## 三、中等风险学员")
            for s in mid_risk:
                lines.append(f"- {s['name']}（{s['direction']}）：完成度 {s['progress']}%，有下滑风险")
            lines.append("")
        if no_cert:
            lines.append("## 四、暂无证书记录的学员")
            for s in no_cert:
                tail = '（未关联平台账号，无法产生学习记录）' if not s['has_account'] else ''
                lines.append(f"- {s['name']}（{s['direction']}）{tail}")
            lines.append("")
        lines.append("## 五、分级干预方案")
        lines.append(f"1. **高风险（<30%）**：一对一约谈，了解学习障碍，制定个性化追赶计划")
        lines.append(f"2. **中等风险（30-50%）**：安排学习伙伴，每周检查进度")
        lines.append(f"3. **无证书记录的学员**：先确认是否已关联平台账号，再补录/核对学习记录")
        return "\n".join(lines)

    # 方向对比主题
    if any(k in p for k in ['方向', '对比', '比较', '哪个', '排名']):
        dir_stats = []
        for d, sts in directions.items():
            d_with = [s for s in sts if s['has_cert_data']]
            if not d_with:
                dir_stats.append((d, len(sts), 0.0, 0, 0, d_with))
                continue
            avg = sum(s['progress'] for s in d_with) / len(d_with)
            hi = max(s['progress'] for s in d_with)
            lo = min(s['progress'] for s in d_with)
            dir_stats.append((d, len(sts), avg, hi, lo, d_with))
        dir_stats.sort(key=lambda x: -x[2])

        lines = [
            "> 数据口径：证书真实完成度（学员名下证书进度的平均值）",
            "",
            "## 一、方向排名",
            f"共 **{len(dir_stats)}** 个方向，按平均完成度排名如下：", ""
        ]
        for i, (d, cnt, avg, hi, lo, d_with) in enumerate(dir_stats):
            medal = '🥇' if i == 0 else '🥈' if i == 1 else '🥉' if i == 2 else f'{i+1}.'
            if not d_with:
                lines.append(f"{medal} **{d}**：{cnt}人，暂无证书记录，无法评估")
            else:
                lines.append(f"{medal} **{d}**：{cnt}人，平均完成度 {avg:.1f}%（最高{hi}%，最低{lo}%）")
        lines.append("")

        if len(dir_stats) >= 2:
            best = dir_stats[0]
            worst = dir_stats[-1]
            if best[5] and worst[5]:
                lines.append("## 二、差距分析")
                lines.append(f"- 最优方向 **{best[0]}** 平均完成度 {best[2]:.1f}%，最弱方向 **{worst[0]}** 平均完成度 {worst[2]:.1f}%")
                lines.append(f"- 差距 **{best[2]-worst[2]:.1f}** 个百分点")
                lines.append("")

        lines.append("## 三、资源调配建议")
        lines.append(f"1. 对完成度较低的方向增加教学资源和辅导频次")
        lines.append(f"2. 让优秀方向的学员分享学习经验")
        lines.append(f"3. 分析各方向教学方法差异，推广最佳实践")
        return "\n".join(lines)

    # 进度主题
    if any(k in p for k in ['进度', '滞后', '完成', '速度', '加快']):
        brackets = {'0-25%': [], '25-50%': [], '50-75%': [], '75-100%': []}
        for s in with_data:
            if s['progress'] < 25: brackets['0-25%'].append(s)
            elif s['progress'] < 50: brackets['25-50%'].append(s)
            elif s['progress'] < 75: brackets['50-75%'].append(s)
            else: brackets['75-100%'].append(s)

        lines = [
            "> 数据口径：证书真实完成度（学员名下证书进度的平均值）",
            "",
            "## 一、完成度分布",
            f"平均完成度 **{avg_progress:.1f}%**（有证书记录的 {len(with_data)} 人），各阶段分布如下：", ""
        ]
        for k, sts in brackets.items():
            pct = len(sts)/total*100 if total else 0
            names = '、'.join(s['name'] for s in sts[:5])
            extra = f'（{names}）' if names else ''
            lines.append(f"- **{k}**：{len(sts)}人，占 {pct:.0f}% {extra}")
        if no_cert:
            lines.append(f"- **暂无证书记录**：{len(no_cert)}人（{'、'.join(s['name'] for s in no_cert)}）")
        lines.append("")

        if brackets['0-25%']:
            lines.append("## 二、完成度偏低学员")
            for s in brackets['0-25%']:
                lines.append(f"- {s['name']}（{s['direction']}）：{s['progress']}%，需要加速")
            lines.append("")

        lines.append("## 三、提速建议")
        lines.append(f"1. 为完成度<25%的学员制定每周学习目标")
        lines.append(f"2. 完成度>75%的学员可作为小组长带动后进")
        lines.append(f"3. 增加实操练习，减少纯理论学习时间")
        return "\n".join(lines)

    # 优秀主题
    if any(k in p for k in ['优秀', '突出', '表扬', '先进', '领先']):
        lines = [
            "> 数据口径：证书真实完成度（学员名下证书进度的平均值）",
            "",
            "## 一、优秀学员概况",
            f"当前共 **{len(excellent)}** 名学员完成度达到80%以上（有证书记录的 {len(with_data)} 人中），"
            f"另有 **{len(completed)}** 人已获得至少一张证书。", ""
        ]
        if excellent:
            lines.append("## 二、优秀学员名单")
            for s in excellent:
                lines.append(f"- **{s['name']}**（{s['direction']}）：完成度 {s['progress']}%，已获得 {s['cert_earned']}/{s['cert_total']} 张证书")
            lines.append("")

        lines.append("## 三、优秀学员特征分析")
        for d, sts in directions.items():
            d_with = [s for s in sts if s['has_cert_data']]
            d_excellent = [s for s in d_with if s['progress'] >= 80]
            if d_with:
                lines.append(f"- **{d}**：{len(d_excellent)}/{len(d_with)} 人优秀（有证书记录者中），比例 {len(d_excellent)/len(d_with)*100:.0f}%")
        lines.append("")

        lines.append("## 四、激励建议")
        lines.append(f"1. 对已获得证书的学员安排进阶课程或实践项目")
        lines.append(f"2. 安排优秀学员担任学习助教，辅导后进学员")
        lines.append(f"3. 为尚未获得证书的学员明确取证路径")
        return "\n".join(lines)

    # 预测/趋势主题
    if any(k in p for k in ['预测', '趋势', '未来', '下月', '计划']):
        completion_rate = len(completed)/total*100 if total else 0
        risk_rate = len(at_risk)/total*100 if total else 0
        lines = [
            "> 数据口径：证书真实完成度（学员名下证书进度的平均值）",
            "",
            "## 一、当前状态",
            f"- 获证率：**{completion_rate:.1f}%**（{len(completed)}/{total}人至少获得一张证书）",
            f"- 风险率：**{risk_rate:.1f}%**（{len(at_risk)}人完成度<30%）",
            f"- 平均完成度：**{avg_progress:.1f}%**（有证书记录的 {len(with_data)} 人）",
            f"- 暂无证书记录：**{len(no_cert)}** 人", ""
        ]
        lines.append("## 二、趋势预测")
        if avg_progress >= 60:
            lines.append(f"- 整体趋势向好，预计多数学员可在2-3个月内完成取证")
        elif avg_progress >= 40:
            lines.append(f"- 整体完成度中等，预计需要3-4个月完成，需加强辅导力度")
        else:
            lines.append(f"- 整体完成度偏慢，需要调整教学计划并加大辅导投入")
        lines.append("")
        lines.append("## 三、下阶段计划建议")
        lines.append(f"1. 对{len(at_risk)}名风险学员制定专项提升计划")
        lines.append(f"2. 每周跟踪证书进度，及时调整教学节奏")
        lines.append(f"3. 组织阶段性测评，检验学习效果")
        return "\n".join(lines)

    # 教学效果主题
    if any(k in p for k in ['效果', '评估', '教学', '质量']):
        lines = [
            "> 数据口径：证书真实完成度（学员名下证书进度的平均值）",
            "",
            "## 一、教学完成情况",
            f"共 **{total}** 名学员，{len(completed)} 人已获得证书，平均完成度 **{avg_progress:.1f}%**"
            f"（有证书记录的 {len(with_data)} 人），{len(no_cert)} 人暂无证书记录。", ""
        ]
        lines.append("## 二、各方向教学效果")
        for d, sts in directions.items():
            d_with = [s for s in sts if s['has_cert_data']]
            if not d_with:
                lines.append(f"- **{d}**：{len(sts)}人，暂无证书记录，无法评估")
                continue
            avg = sum(s['progress'] for s in d_with) / len(d_with)
            done = len([s for s in d_with if s['cert_earned'] > 0])
            level = '优秀' if avg >= 70 else '良好' if avg >= 50 else '需加强'
            lines.append(f"- **{d}**：{len(sts)}人，平均完成度 {avg:.1f}%，已获证{done}人，评价：{level}")
        lines.append("")
        lines.append("## 三、改进建议")
        for d, sts in directions.items():
            d_with = [s for s in sts if s['has_cert_data']]
            if d_with:
                avg = sum(s['progress'] for s in d_with) / len(d_with)
                if avg < 50:
                    lines.append(f"1. **{d}**方向完成度偏低，建议增加辅导频次和实操练习")
        lines.append(f"2. 建立学员互评机制，促进同伴学习")
        lines.append(f"3. 定期收集学员反馈，优化教学内容")
        return "\n".join(lines)

    # 默认：通用报告
    lines = [
        "> 数据口径：证书真实完成度（学员名下证书进度的平均值）",
        "",
        "## 一、总体概况",
        f"- 共 **{total}** 名学员，平均完成度 **{avg_progress:.1f}%**（有证书记录的 {len(with_data)} 人）",
        f"- {len(completed)} 人已获得至少一张证书，{len(no_cert)} 人暂无证书记录",
        f"- 涵盖 **{len(directions)}** 个方向",
        ""
    ]
    lines.append("## 二、各方向情况")
    for d, sts in directions.items():
        d_with = [s for s in sts if s['has_cert_data']]
        if not d_with:
            lines.append(f"- **{d}**：{len(sts)}人，暂无证书记录，无法评估")
            continue
        avg = sum(s['progress'] for s in d_with) / len(d_with)
        names = '、'.join(s['name'] for s in sts)
        lines.append(f"- **{d}**：{len(sts)}人，平均完成度 {avg:.1f}%，学员：{names}")
    lines.append("")
    if at_risk:
        lines.append(f"## 三、风险预警（{len(at_risk)}人）")
        for s in at_risk:
            lines.append(f"- {s['name']}（{s['direction']}）：完成度仅 {s['progress']}%")
        lines.append("")
    if excellent:
        lines.append(f"## 四、优秀学员（{len(excellent)}人）")
        for s in excellent:
            lines.append(f"- {s['name']}（{s['direction']}）：完成度 {s['progress']}%")
        lines.append("")
    lines.append("## 五、建议")
    if at_risk:
        lines.append(f"1. 对 {len(at_risk)} 名风险学员进行一对一辅导，了解学习障碍")
    if no_cert:
        lines.append(f"2. 核对 {len(no_cert)} 名无证书记录学员的账号关联与学习记录")
    lines.append(f"3. 对已获证学员安排进阶内容或实践项目")
    lines.append(f"4. 组织方向间交流活动，促进经验分享")
    return "\n".join(lines)


# ==================== 通知公告API ====================

@app.route('/api/teacher/announcements', methods=['GET'])
@_require_role(*_TEACHER_ROLES)
def get_announcements():
    announcements = database.get_announcements()
    return jsonify({"success": True, "announcements": announcements})

@app.route('/api/teacher/announcements', methods=['POST'])
@_require_role(*_TEACHER_ROLES)
def create_announcement():
    data = request.get_json()
    title = data.get('title', '')
    content = data.get('content', '')
    category = data.get('category', '通知')
    pinned = 1 if data.get('pinned') else 0
    if not title or not content:
        return jsonify({"success": False, "message": "请填写标题和内容"})
    aid = database.create_announcement(title, content, category, pinned)
    # 自动给所有学员发通知
    database.create_notification_for_all_students(
        'announcement', f'新{category}', title, 'announcement', aid
    )
    return jsonify({"success": True, "message": "发布成功", "id": aid})

@app.route('/api/teacher/announcements/<int:ann_id>', methods=['DELETE'])
@_require_role(*_TEACHER_ROLES)
def delete_announcement(ann_id):
    if database.delete_announcement(ann_id):
        return jsonify({"success": True, "message": "删除成功"})
    return jsonify({"success": False, "message": "未找到通知"})


# ==================== 学员个人数据API ====================

# 2026-10-07：「发布作业」整块下架，`/api/student/submissions`（我的作业提交）
# 与它配套的教师侧 `/api/teacher/submissions/<id>` 一并删除 —— 前端零调用，
# 学员端的「我的作业」面板已在 v55 下架；三种实训的历史记录走 /api/ecommerce/*/records。

@app.route('/api/student/announcements', methods=['GET'])
def get_my_announcements():
    """获取通知公告列表（学员可见）"""
    announcements = database.get_announcements(limit=30)
    return jsonify({"success": True, "announcements": announcements})


# ==================== 消息系统API ====================

def _messages_self_guard(user_id):
    """消息接口的身份护栏：只能以本人身份读自己的私信。

    返回 (user, None) 放行，或 (None, (response, status)) 拒绝。
    ⚠️ /api/messages/* 此前**完全不鉴权**：inbox / conversation / unread 按 query 里的
    `user_id` 直查，任何人都能读别人的私信；send 的 `sender_id` 直接取自请求体，
    不带会话也能冒名发送（2026-10-09 实测伪造 admin_demo 发送成功）。
    """
    user = _get_session_user()
    if not user:
        return None, (jsonify({"success": False, "message": "请先登录"}), 401)
    if not user_id or user_id != user['username']:
        return None, (jsonify({"success": False, "message": "权限不足"}), 403)
    return user, None


@app.route('/api/messages/send', methods=['POST'])
def send_message():
    user = _get_session_user()
    if not user:
        return jsonify({"success": False, "message": "请先登录"}), 401
    data = request.get_json(silent=True) or {}
    # ⚠️ sender_id 一律取会话用户，**不再信任请求体** —— 否则谁都能冒名发消息。
    sender_id = user['username']
    receiver_id = (data.get('receiver_id') or '').strip()
    content = (data.get('content') or '').strip()
    if not receiver_id or not content:
        return jsonify({"success": False, "message": "参数不完整"}), 400
    if receiver_id == sender_id:
        return jsonify({"success": False, "message": "不能给自己发消息"}), 400
    if not database.get_user_by_id(receiver_id):
        return jsonify({"success": False, "message": "收件人不存在"}), 404
    mid = database.send_message(sender_id, receiver_id, content)
    return jsonify({"success": True, "message": "发送成功", "id": mid})


@app.route('/api/messages/inbox', methods=['GET'])
def get_inbox():
    user_id = request.args.get('user_id', '')
    if not user_id:
        return jsonify({"success": False, "message": "缺少用户ID"}), 400
    _, err = _messages_self_guard(user_id)
    if err:
        return err
    inbox = database.get_inbox(user_id)
    return jsonify({"success": True, "inbox": inbox})


@app.route('/api/messages/conversation/<other_id>', methods=['GET'])
def get_conversation(other_id):
    user_id = request.args.get('user_id', '')
    if not user_id:
        return jsonify({"success": False, "message": "缺少用户ID"}), 400
    _, err = _messages_self_guard(user_id)
    if err:
        return err
    messages = database.get_messages(user_id, other_id)
    # 标记对方发来的消息为已读
    database.mark_messages_read(other_id, user_id)
    return jsonify({"success": True, "messages": messages})


@app.route('/api/messages/read', methods=['POST'])
def mark_messages_read():
    data = request.get_json(silent=True) or {}
    receiver_id = (data.get('receiver_id') or '').strip()
    sender_id = (data.get('sender_id') or '').strip()
    if not receiver_id or not sender_id:
        return jsonify({"success": False, "message": "参数不完整"}), 400
    # 标为已读的是「别人发给我的」→ receiver 必须是本人
    _, err = _messages_self_guard(receiver_id)
    if err:
        return err
    database.mark_messages_read(sender_id, receiver_id)
    return jsonify({"success": True})


@app.route('/api/messages/unread', methods=['GET'])
def get_unread_count():
    user_id = request.args.get('user_id', '')
    if not user_id:
        return jsonify({"success": False, "message": "缺少用户ID"}), 400
    _, err = _messages_self_guard(user_id)
    if err:
        return err
    count = database.get_unread_count(user_id)
    return jsonify({"success": True, "count": count})


# ==================== 系统通知API ====================

@app.route('/api/notifications', methods=['GET'])
def get_notifications():
    user_id = request.args.get('user_id', '')
    # 通知属个人数据：与消息接口同款护栏，只看本人（修复越权：此前按 user_id 直查、不鉴权）
    _, err = _messages_self_guard(user_id)
    if err:
        return err
    notifications = database.get_notifications(user_id)
    return jsonify({"success": True, "notifications": notifications})


@app.route('/api/notifications/read', methods=['POST'])
def mark_notifications_read():
    data = request.get_json()
    user_id = data.get('user_id', '')
    _, err = _messages_self_guard(user_id)
    if err:
        return err
    # 全部已读必须覆盖消息中心的**四个数据源**：站内通知、私信、投递状态、系统公告。
    # 此前只标了 notifications 一张表，企业通知与系统公告永远不会变已读 ——
    # 表现为「点了全部已读，未读项一条不少」（2026-10-09 用户走查反馈）。
    database.mark_notifications_read(user_id)
    database.mark_all_messages_read(user_id)
    database.mark_refs_read(user_id, 'job_application',
                            database.get_job_application_ids(user_id))
    database.mark_refs_read(user_id, 'system_announcement',
                            database.get_active_system_announcement_ids())
    return jsonify({"success": True})


@app.route('/api/notifications/read-state', methods=['GET'])
def get_notification_read_state():
    """取自建已读旁路表里两个来源的已读 ref 列表。"""
    user_id = request.args.get('user_id', '')
    _, err = _messages_self_guard(user_id)
    if err:
        return err
    return jsonify({
        "success": True,
        "refs": {
            "system_announcement": database.get_read_refs(user_id, 'system_announcement'),
            "job_application": database.get_read_refs(user_id, 'job_application')
        }
    })


@app.route('/api/notifications/read-one', methods=['POST'])
def mark_one_notification_read():
    """把单条通知标为已读（消息中心「未读」页签点击即归档）。

    source 取值与前端 item.source 一致：
      notifications        站内通知（公告 / 实训批改），走 notifications.is_read
      messages             互动私信，ref_id 是对方 username，走 messages.is_read
      system_announcement  系统公告，走旁路表
      job_application      投递状态，走旁路表
    """
    data = request.get_json(silent=True) or {}
    user_id = data.get('user_id', '')
    source = (data.get('source') or '').strip()
    ref_id = str(data.get('ref_id') or '').strip()
    _, err = _messages_self_guard(user_id)
    if err:
        return err
    if not source or not ref_id:
        return jsonify({"success": False, "message": "参数不完整"}), 400

    if source == 'notifications':
        conn = database.get_connection()
        # 只允许标自己的，避免拿别人的通知 id 乱标
        cur = conn.execute(
            "UPDATE notifications SET is_read = 1 WHERE user_id = ? AND id = ? AND is_read = 0",
            (user_id, ref_id)
        )
        conn.commit()
        changed = cur.rowcount
        conn.close()
        if not changed:
            return jsonify({"success": False, "message": "通知不存在"}), 404
    elif source == 'messages':
        database.mark_messages_read(ref_id, user_id)
    elif source in ('system_announcement', 'job_application'):
        database.mark_ref_read(user_id, source, ref_id)
    else:
        return jsonify({"success": False, "message": "未知的通知来源"}), 400
    return jsonify({"success": True})


@app.route('/api/notifications/clear', methods=['DELETE'])
def clear_read_notifications():
    user_id = request.args.get('user_id', '')
    _, err = _messages_self_guard(user_id)
    if err:
        return err
    database.clear_read_notifications(user_id)
    return jsonify({"success": True})


@app.route('/api/notifications/unread', methods=['GET'])
def get_unread_notification_count():
    user_id = request.args.get('user_id', '')
    _, err = _messages_self_guard(user_id)
    if err:
        return err
    # 口径与消息中心「未读」页签一致：四个数据源一起数。
    # 此前只数 notifications 表，红点数字比「未读」页签少一截。
    count = database.get_total_unread_count(user_id)
    return jsonify({"success": True, "count": count})


# ==================== 实训批改 API ====================
# 2026-10-07 用户拍板：**「发布作业」整块下架**（`POST|GET /api/teacher/assignments`、
# `GET /api/teacher/assignments/<id>` 三条路由删除，前端本来就零调用）。
# 保留的只有批改：三种电商实训（直播/文案/客服）复用 assignments 表当题目载体，
# 学员提交落在 assignment_submissions，教师在这里批改。
# ⚠️ 顺带解决了一个真实缺陷：原「发布作业」按方向通知学员时，比较的是
#    `assignments.direction`（英文 slug 'ecommerce'）与 `students.direction`（中文
#    '电商运营'），两者永不相等 → 通知一个也发不出去。该逻辑随本块一并删除。
@app.route('/api/teacher/assignments/grade', methods=['POST'])
@_require_role(*_TEACHER_ROLES)
def grade_submission():
    data = request.get_json()
    submission_id = data.get('submission_id')
    score = data.get('score')
    feedback = data.get('feedback', '')
    if submission_id is None or score is None:
        return jsonify({"success": False, "message": "请填写批改信息"})
    # 获取提交信息以发送通知
    conn = database.get_connection()
    sub = conn.execute("SELECT student_id, assignment_id FROM assignment_submissions WHERE id = ?", (submission_id,)).fetchone()
    conn.close()
    if database.grade_submission(submission_id, score, feedback):
        if sub:
            database.create_notification(sub['student_id'], 'grade', '实训已批改', f'得分：{score}', 'assignment', sub['assignment_id'])
        return jsonify({"success": True, "message": "批改成功"})
    return jsonify({"success": False, "message": "批改失败"})


@app.route('/api/teacher/trainings', methods=['GET'])
@_require_role(*_TEACHER_ROLES)
def teacher_get_trainings():
    """教师端「实训提交」页：全部学员的电商实训提交（直播/文案/客服）。

    数据来自 assignment_submissions（学生端 /api/ecommerce/{live,copy,cs}/submit 写入）。
    批改仍走既有 /api/teacher/assignments/grade，会给学员发站内通知。
    """
    out = []
    for r in database.get_all_trainings():
        detail = {}
        try:
            detail = json.loads(r.get('content') or '{}')
        except Exception:
            detail = {}
        if not isinstance(detail, dict):
            detail = {}
        # ⚠️ 学生作品正文必须下发，否则教师端就是「盲批」：
        #    直播/文案形态是 script，客服对练形态是 transcript（[{role,content}]）。
        #    2026-10-07 前这里只给了 product/attempts/score，教师只能凭「类型+产品」猜分。
        script = str(detail.get('script') or '')
        transcript = detail.get('transcript')
        if not isinstance(transcript, list):
            transcript = []
        meta = detail.get('meta')
        if not isinstance(meta, dict):
            meta = {}
        out.append({
            "id": r.get('id'),
            "student_id": r.get('student_id'),
            "student_name": r.get('student_name') or '',
            "assignment_id": r.get('assignment_id'),
            "assignment_title": r.get('assignment_title') or '',
            "kind": r.get('kind') or '',
            "product": str(detail.get('product') or ''),
            "attempts": detail.get('attempts') or 1,
            # score = 教师批改分（未批改为 None）；rule_score = 系统规则分（存 content 里）
            "score": r.get('score'),
            "rule_score": detail.get('rule_score'),
            "script": script,
            "transcript": transcript,
            "meta": meta,
            "script_len": len(script),
            "feedback": r.get('feedback') or '',
            "status": r.get('status') or 'submitted',
            "status_label": _training_status_label(r.get('status')),
            "submitted_at": r.get('submitted_at') or '',
            "graded_at": r.get('graded_at') or '',
            "regrade_needed": (r.get('status') or '') == 'resubmitted',
        })
    pending_regrade = sum(1 for x in out if x['regrade_needed'])
    return jsonify({"success": True, "trainings": out, "pending_regrade": pending_regrade})


# ==================== 学情分析API ====================

@app.route('/api/teacher/analytics', methods=['GET'])
@_require_role(*_TEACHER_ROLES)
def get_analytics():
    data = database.get_analytics_data()
    return jsonify({"success": True, "analytics": data})


# ==================== 用户认证API ====================

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({"success": False, "message": "请输入用户名和密码"}), 400

    user = database.authenticate_user(username, password)
    if user:
        if user.get('status') == 'suspended':
            return jsonify({"success": False, "message": "账号已被停用，请联系管理员"}), 403
        session_id = database.create_session(username)
        return jsonify({
            "success": True,
            "session_id": session_id,
            "user": {"id": user['username'], "name": user['name'], "role": user['role'],
                     "email": user.get('email', ''), "phone": user.get('phone', ''),
                     "avatar_url": user.get('avatar_url', ''), "company_name": user.get('company_name', ''),
                     "region": user.get('region', ''), "status": user.get('status', 'active')}
        })

    return jsonify({"success": False, "message": "用户名或密码错误"}), 401


@app.route('/api/auth/logout', methods=['POST'])
def logout():
    data = request.get_json()
    session_id = data.get('session_id')
    if session_id:
        database.delete_session(session_id)
    return jsonify({"success": True, "message": "已退出登录"})


@app.route('/api/auth/verify', methods=['POST'])
def verify_session():
    data = request.get_json()
    session_id = data.get('session_id')
    if not session_id:
        return jsonify({"success": False, "message": "未提供session"}), 401

    session = database.get_session(session_id)
    if session:
        # ⚠️ 这里必须与 /api/auth/login 返回同一套 user 结构。
        # 前端 restoreSession() 会用它**整体覆盖** AppState.user，而 database.get_session()
        # 只给 {user_id, name, role}（键名是 user_id，没有 id）→ AppState.user.id 变成
        # undefined，此后所有 `/api/.../${AppState.user.id}` 都会拼成 `/api/.../undefined`。
        # 旧接口大多不校验 user_id 所以没暴露；就业对接的 _self_only() 会直接 403。
        user = database.get_user_by_id(session['user_id']) or {}
        return jsonify({
            "success": True,
            "user": {
                "id": session['user_id'],
                "name": session.get('name') or user.get('name', ''),
                "role": session.get('role') or user.get('role', ''),
                "email": user.get('email', ''),
                "phone": user.get('phone', ''),
                "avatar_url": user.get('avatar_url', ''),
                "company_name": user.get('company_name', ''),
                "region": user.get('region', ''),
                "status": user.get('status', 'active')
            }
        })
    return jsonify({"success": False, "message": "会话无效"}), 401


# ==================== 用户资料API ====================

@app.route('/api/user/profile', methods=['GET'])
def get_user_profile():
    """获取当前用户完整资料"""
    session_id = request.headers.get('X-Session-Id', '')
    session = database.get_session(session_id)
    if not session:
        return jsonify({"success": False, "message": "未登录"}), 401
    user = database.get_user_by_id(session['user_id'])
    if not user:
        return jsonify({"success": False, "message": "用户不存在"})
    return jsonify({"success": True, "user": user})


@app.route('/api/user/profile', methods=['PUT'])
def update_profile():
    """更新用户资料"""
    session_id = request.headers.get('X-Session-Id', '')
    session = database.get_session(session_id)
    if not session:
        return jsonify({"success": False, "message": "未登录"}), 401
    data = request.get_json()
    name = data.get('name', '').strip()
    email = data.get('email', '').strip()
    if not name:
        return jsonify({"success": False, "message": "姓名不能为空"})
    database.update_user_profile(session['user_id'], name=name, email=email)
    return jsonify({"success": True, "message": "资料更新成功"})


@app.route('/api/user/password', methods=['PUT'])
def change_password():
    """修改密码"""
    session_id = request.headers.get('X-Session-Id', '')
    session = database.get_session(session_id)
    if not session:
        return jsonify({"success": False, "message": "未登录"}), 401
    data = request.get_json()
    old_password = data.get('old_password', '')
    new_password = data.get('new_password', '')
    confirm_password = data.get('confirm_password', '')
    if not old_password or not new_password:
        return jsonify({"success": False, "message": "请填写完整"})
    if new_password != confirm_password:
        return jsonify({"success": False, "message": "两次输入的新密码不一致"})
    if len(new_password) < 6:
        return jsonify({"success": False, "message": "新密码至少6位"})
    success, msg = database.change_password(session['user_id'], old_password, new_password)
    return jsonify({"success": success, "message": msg})


# ==================== 健康检查 ====================

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({
        "success": True, "healthy": True,
        "service": "粤乡智匠API",
        "timestamp": datetime.now().isoformat()
    })


# ==================== AI服务调用 ====================

def call_ai_service(system_prompt, user_message, temperature=0.3,
                    max_tokens=1000 + AI_REASONING_TOKEN_RESERVE, model=None):
    """通用 AI 调用入口（供全站各 AI 功能复用）。

    统一走 _chat_completion，因此同样受益于：
      ① 上游响应结构校验（缺 choices / 空内容会抛错，不再静默返回 None）
      ② 未配置密钥时的快速失败
      ③ 推理模型的思考余量（默认值已加上 AI_REASONING_TOKEN_RESERVE）

    model 留空时用默认文本模型 AI_MODEL；问答/建议这类对话型调用传 _chat_model()。
    """
    if not _ai_configured():
        raise RuntimeError('未配置 AI_API_KEY，AI 功能不可用')
    return _chat_completion(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=30,
        model=model
    )


def call_ai_vision_service(system_prompt, user_message, images,
                           temperature=0.3, max_tokens=2000 + AI_REASONING_TOKEN_RESERVE,
                           timeout=120):
    """多模态调用：把图片和文本一起送进支持图片输入的模型。

    与 call_ai_service 分开实现，避免改动既有签名影响纯文本功能（问答 / 追问建议）。
    images 形如 [{'mime': 'image/jpeg', 'data': '<base64>'}]，按 OpenAI 兼容的
    image_url(data URL) 结构拼进 user content 数组。
    """
    if not _ai_configured():
        raise RuntimeError('未配置 AI_API_KEY，AI 功能不可用')
    model = (AI_VL_MODEL or '').strip()
    if not model:
        raise RuntimeError('未配置 AI_VL_MODEL，图片诊断不可用')

    content = [
        {"type": "image_url", "image_url": {"url": f"data:{item['mime']};base64,{item['data']}"}}
        for item in (images or [])
    ]
    content.append({"type": "text", "text": user_message})

    return _chat_completion(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content}
        ],
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
        model=model
    )


# ==================== 用户注册 ====================

@app.route('/api/auth/register', methods=['POST'])
def register():
    """用户注册"""
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    name = data.get('name', '').strip()
    role = data.get('role', 'student')
    email = data.get('email', '').strip()
    phone = data.get('phone', '').strip()
    company_name = data.get('company_name', '').strip()
    region = data.get('region', '').strip()

    if not username or not password or not name:
        return jsonify({"success": False, "message": "用户名、密码和姓名不能为空"}), 400
    if len(password) < 6:
        return jsonify({"success": False, "message": "密码至少6位"}), 400
    if role not in ('student', 'teacher', 'enterprise'):
        return jsonify({"success": False, "message": "无效的角色类型"}), 400

    user_id, msg = database.register_user(username, password, name, role,
                                          email, phone, company_name, region)
    if user_id:
        session_id = database.create_session(username)
        user = database.get_user_by_id(username)
        return jsonify({
            "success": True,
            "message": msg,
            "session_id": session_id,
            "user": {"id": user['username'], "name": user['name'], "role": user['role'],
                     "email": user.get('email', ''), "phone": user.get('phone', ''),
                     "avatar_url": user.get('avatar_url', ''), "company_name": user.get('company_name', ''),
                     "region": user.get('region', ''), "status": user.get('status', 'active')}
        })
    return jsonify({"success": False, "message": msg}), 400


# ==================== 超级管理员 API ====================

@app.route('/api/admin/dashboard', methods=['GET'])
def admin_dashboard():
    """超级管理员仪表盘统计。

    ⚠️ 前端此前调的是 `/api/government/dashboard`（只允许 government）→ super_admin
       恒 403，统计区长期空白。这里给 admin 自己的口径。
    ⚠️ 只输出真实可算的项：在线人数 / 日活 / 增长趋势 / 平均审核时长一律不下发 ——
       没有在线状态表、没有埋点、没有访问日志，凑出来的数字就是编造。
       成功案例正文不落库，条数从 cases_data 取（与审核详情同一来源）。
    """
    user = _get_session_user()
    if not user or user['role'] != 'super_admin':
        return jsonify({"success": False, "message": "权限不足"}), 403
    ov = database.get_admin_overview()
    try:
        import cases_data
        ov['content']['cases'] = len(cases_data.get_cases())
    except Exception:
        # 案例模块取不到就置 None，前端该卡不渲染，绝不补 0
        ov['content']['cases'] = None
    return jsonify({"success": True, "overview": ov})


@app.route('/api/admin/users', methods=['GET'])
def admin_get_users():
    user = _get_session_user()
    if not user or user['role'] != 'super_admin':
        return jsonify({"success": False, "message": "权限不足"}), 403
    search = request.args.get('search', '')
    role_filter = request.args.get('role', '')
    users = database.get_all_users(search=search or None, role=role_filter or None)

    # 逐条算出「能不能删」。
    # ⚠️ 规则只放后端 —— 前端照 can_delete 渲染，不再自己判断，
    #    否则「界面藏了按钮、接口照样能删」等于没拦。
    me = user['username']
    super_admin_count = database.count_super_admins()
    for u in users:
        # password_hash 绝不下发给前端（它是 SELECT * 带出来的）
        u.pop('password_hash', None)
        rel = database.count_user_relations(u['username'])
        u['relation_count'] = rel['total']
        u['relations'] = rel['items']
        if u['username'] == me:
            u['can_delete'] = False
            u['block_reason'] = '当前登录账号，不能删除自己'
        elif u.get('role') == 'super_admin' and super_admin_count <= 1:
            u['can_delete'] = False
            u['block_reason'] = '系统必须保留至少一个超级管理员'
        elif rel['total'] > 0:
            u['can_delete'] = False
            u['block_reason'] = '有 %d 条关联业务数据，请改用「停用」' % rel['total']
        else:
            u['can_delete'] = True
            u['block_reason'] = ''
        # 自己也不能停用（停了就把自己锁在门外）
        u['can_suspend'] = (u['username'] != me)
    return jsonify({"success": True, "users": users})


@app.route('/api/admin/users/<user_id>', methods=['PUT'])
def admin_update_user(user_id):
    user = _get_session_user()
    if not user or user['role'] != 'super_admin':
        return jsonify({"success": False, "message": "权限不足"}), 403
    data = request.get_json(silent=True) or {}
    target = database.get_user_by_id(user_id)
    if not target:
        return jsonify({"success": False, "message": "用户不存在"}), 404

    # 末位 super_admin 不能被降级。
    # ⚠️ 这条守卫放在 PUT 而不是 DELETE 才有意义：DELETE 要求操作者本人就是
    #    super_admin，于是 count_super_admins() 恒 >= 1，「最后一个超管」只可能是
    #    操作者自己，而自删已被前面拦掉 —— DELETE 里那条守卫实际不可触发。
    #    真正能把全站最后一个超管搞没的路径是**改角色**：把 admin_demo 的 role
    #    从 super_admin 改成别的，此后没有任何账号能进管理端，且无法自恢复。
    new_role = data.get('role')
    if (new_role is not None and new_role != 'super_admin'
            and target.get('role') == 'super_admin'
            and database.count_super_admins() <= 1):
        return jsonify({
            "success": False,
            "message": "系统必须保留至少一个超级管理员，不能把最后一个超级管理员改成其他角色"}), 400

    ok = database.update_user_by_admin(user_id,
        name=data.get('name'), role=new_role, status=data.get('status'),
        phone=data.get('phone'), email=data.get('email'))
    if not ok:
        return jsonify({"success": False, "message": "用户不存在"}), 404
    return jsonify({"success": True, "message": "更新成功"})


@app.route('/api/admin/users/<user_id>/status', methods=['POST'])
def admin_set_user_status(user_id):
    """启用 / 停用账号 —— **删除的替代方案**（2026-10-08）。

    删用户会留下跨表孤儿（students.user_id 是名册收件人与证书归属的唯一依据），
    所以凡是有业务数据的账号一律走「停用」：登录接口本来就认 status='suspended'，
    停用后本人进不来，但所有历史数据完整保留，随时可以恢复。
    """
    user = _get_session_user()
    if not user or user['role'] != 'super_admin':
        return jsonify({"success": False, "message": "权限不足"}), 403
    if user_id == user['username']:
        return jsonify({"success": False, "message": "不能停用当前登录的账号"}), 400
    data = request.get_json(silent=True) or {}
    status = data.get('status', '')
    if status not in ('active', 'suspended'):
        return jsonify({"success": False, "message": "状态只能是 active 或 suspended"}), 400
    n = database.set_user_status(user_id, status)
    if n <= 0:
        return jsonify({"success": False, "message": "用户不存在"}), 404
    return jsonify({"success": True,
                    "message": "已停用，该账号无法登录" if status == 'suspended' else "已启用"})


@app.route('/api/admin/users/<user_id>', methods=['DELETE'])
def admin_delete_user(user_id):
    """删除用户。四道关依次拦：自删 / 末位超管 / 关联数据 / 不存在。

    ⚠️ 2026-10-08 之前本路由无条件返回 200「删除成功」——删一个不存在的人
       也照样报成功，且能把自己删掉（删完全站再无 super_admin，会话立即失效、
       不可自恢复）。现在逐条校验，并把 `delete_user_by_admin()` 的返回值
       （真实影响行数）作为最终判据。
    """
    user = _get_session_user()
    if not user or user['role'] != 'super_admin':
        return jsonify({"success": False, "message": "权限不足"}), 403

    if user_id == user['username']:
        return jsonify({"success": False, "message": "不能删除当前登录的账号"}), 400

    target = database.get_user_by_id(user_id)
    if not target:
        return jsonify({"success": False, "message": "用户不存在"}), 404

    if target.get('role') == 'super_admin' and database.count_super_admins() <= 1:
        return jsonify({"success": False, "message": "系统必须保留至少一个超级管理员"}), 400

    rel = database.count_user_relations(user_id)
    if rel['total'] > 0:
        return jsonify({
            "success": False,
            "message": "该账号有 %d 条关联业务数据，不能删除。请改用「停用」。" % rel['total'],
            "relations": rel['items'],
            "relation_total": rel['total'],
        }), 409

    n = database.delete_user_by_admin(user_id)
    if n <= 0:
        return jsonify({"success": False, "message": "用户不存在"}), 404
    return jsonify({"success": True, "message": "删除成功"})


# ---- 内容审核 ----

@app.route('/api/admin/reviews', methods=['GET'])
def admin_get_reviews():
    user = _get_session_user()
    if not user or user['role'] != 'super_admin':
        return jsonify({"success": False, "message": "权限不足"}), 403
    content_type = request.args.get('content_type', '')
    ct = content_type or None
    # status 支持 pending / approved / rejected / all；默认仍是 pending ——
    # 仪表盘「待审核 N 项」依赖这个默认值，不能改。
    status = request.args.get('status', '') or 'pending'
    if status not in ('pending', 'approved', 'rejected', 'all'):
        status = 'pending'
    # 排序：modified（默认，按最后修改时间倒序）/ created（按提交时间倒序）。
    # 与 status 一样做白名单校验，非法值回落默认，前端乱传参打不飞排序。
    sort = request.args.get('sort', '') or 'modified'
    if sort not in ('modified', 'created'):
        sort = 'modified'
    reviews = database.get_reviews_by_status(None if status == 'all' else status, ct, sort)

    # 关联审核内容详情
    enriched = []
    for r in reviews:
        rd = dict(r)
        rd['detail'] = None
        ctype, cid = r['content_type'], r['content_id']
        if ctype == 'procurement':
            # 求购已在 2026-10-06 随「供应链求购不做」整块下线。
            # 历史遗留的待审求购不再下发给管理端 —— 否则审核列表里会出现
            # 「看不到内容、界面也没有处理入口」的孤儿卡片。
            continue
        if ctype == 'course':
            rd['detail'] = database.get_course(cid)
        elif ctype == 'job':
            rd['detail'] = database.get_job_by_id(cid)
        elif ctype == 'model_3d':
            conn = database.get_connection()
            row = conn.execute("SELECT * FROM models_3d WHERE id=?", (cid,)).fetchone()
            conn.close()
            rd['detail'] = dict(row) if row else None
        elif ctype == 'success_case':
            # 案例正文不落库（内容在 cases_data.py），详情直接取数据模块
            import cases_data
            rd['detail'] = cases_data.get_case(cid)
        # 「自提自审」如实标注：提交者与审核人是同一个人时，这条审核记录
        # 不含任何第三方把关，界面必须标出来，不能被当成「已审核」背书。
        # （平台预置内容的 5 条 success_case 就是这种情况，数据本身是真实的，
        #   只是提交与审核都记在 admin_demo 名下 —— 2026-10-08）
        rd['is_self_reviewed'] = bool(r.get('submitter_id') and r.get('reviewed_by')
                                      and r['submitter_id'] == r['reviewed_by'])
        enriched.append(rd)
    counts = database.count_reviews_by_status(ct)
    return jsonify({"success": True, "reviews": enriched, "counts": counts, "status": status})


@app.route('/api/admin/reviews/<int:review_id>/approve', methods=['POST'])
def admin_approve_review(review_id):
    user = _get_session_user()
    if not user or user['role'] != 'super_admin':
        return jsonify({"success": False, "message": "权限不足"}), 403
    database.approve_review(review_id, user['username'])
    return jsonify({"success": True, "message": "已审核通过"})


@app.route('/api/admin/reviews/<int:review_id>/reject', methods=['POST'])
def admin_reject_review(review_id):
    user = _get_session_user()
    if not user or user['role'] != 'super_admin':
        return jsonify({"success": False, "message": "权限不足"}), 403
    data = request.get_json()
    comment = data.get('comment', '')
    database.reject_review(review_id, user['username'], comment)
    return jsonify({"success": True, "message": "已驳回"})


@app.route('/api/admin/reviews/<int:review_id>/revoke', methods=['POST'])
def admin_revoke_review(review_id):
    """撤销审核：把已通过 / 已驳回的记录退回「待审核」，可重新处理。

    2026-10-08 新增（管理端「内容审核」要能回看并纠正历史）。
    与 approve / reject 走同一套对称回写规则，目标表的 review_status 一并退回
    pending，不会出现「审核表已撤销、岗位却还挂着 approved」的不一致。
    """
    user = _get_session_user()
    if not user or user['role'] != 'super_admin':
        return jsonify({"success": False, "message": "权限不足"}), 403
    result = database.revoke_review(review_id)
    if result == 'not_found':
        return jsonify({"success": False, "message": "审核记录不存在"}), 404
    if result == 'not_reviewed':
        return jsonify({"success": False, "message": "该记录本就处于待审核状态"}), 400
    return jsonify({"success": True, "message": "已撤销，退回待审核"})



# ---- 系统公告管理 ----

@app.route('/api/admin/system-announcements', methods=['GET'])
def admin_get_system_announcements():
    user = _get_session_user()
    if not user or user['role'] != 'super_admin':
        return jsonify({"success": False, "message": "权限不足"}), 403
    anns = database.get_system_announcements(active_only=False)
    return jsonify({"success": True, "announcements": anns})


@app.route('/api/admin/system-announcements', methods=['POST'])
def admin_add_system_announcement():
    user = _get_session_user()
    if not user or user['role'] != 'super_admin':
        return jsonify({"success": False, "message": "权限不足"}), 403
    data = request.get_json()
    ann_id = database.add_system_announcement(
        data.get('title', ''), data.get('content', ''),
        data.get('is_pinned', 0), user['username'])
    return jsonify({"success": True, "id": ann_id, "message": "发布成功"})


@app.route('/api/admin/system-announcements/<int:ann_id>', methods=['DELETE'])
def admin_delete_system_announcement(ann_id):
    user = _get_session_user()
    if not user or user['role'] != 'super_admin':
        return jsonify({"success": False, "message": "权限不足"}), 403
    database.delete_system_announcement(ann_id)
    return jsonify({"success": True, "message": "已删除"})


# ---- 内容监管 ----

@app.route('/api/admin/comments/<int:comment_id>', methods=['DELETE'])
def admin_delete_comment(comment_id):
    user = _get_session_user()
    if not user or user['role'] != 'super_admin':
        return jsonify({"success": False, "message": "权限不足"}), 403
    database.soft_delete_comment(comment_id, user['username'])
    return jsonify({"success": True, "message": "已删除违规评论"})


@app.route('/api/admin/discussions/<int:disc_id>', methods=['DELETE'])
def admin_delete_discussion(disc_id):
    user = _get_session_user()
    if not user or user['role'] != 'super_admin':
        return jsonify({"success": False, "message": "权限不足"}), 403
    database.soft_delete_discussion(disc_id)
    return jsonify({"success": True, "message": "已删除违规帖子"})


# ==================== 政府人员 API ====================

# ---- 政策管理 ----

@app.route('/api/government/policies', methods=['GET'])
def gov_get_policies():
    user = _get_session_user()
    if not user or user['role'] != 'government':
        return jsonify({"success": False, "message": "权限不足"}), 403
    policies = database.get_all_government_policies()
    return jsonify({"success": True, "policies": policies})


@app.route('/api/government/policies', methods=['POST'])
def gov_create_policy():
    user = _get_session_user()
    if not user or user['role'] != 'government':
        return jsonify({"success": False, "message": "权限不足"}), 403
    data = request.get_json() or {}
    title = (data.get('title') or '').strip()
    content = (data.get('content') or '').strip()
    if not title or not content:
        return jsonify({"success": False, "message": "标题和内容不能为空"}), 400
    policy_id = database.create_policy(
        title, content,
        # 「综合」在政府端表单里的 value 是英文 general，入库前统一归一化成中文分类，
        # 否则学员端会显示成英文标签、且任何分类筛选都筛不到（详见 database.normalize_policy_category）
        database.normalize_policy_category(data.get('category')),
        user['username'],
        # 摘要 / 发布日期 / 资料来源全部落库（缺了学员端卡片就是残缺的，见 create_policy 注释）
        summary=(data.get('summary') or '').strip(),
        date=(data.get('date') or '').strip() or datetime.now().strftime('%Y-%m-%d'),
        source_text=data.get('source') or '')
    return jsonify({"success": True, "id": policy_id, "message": "政策发布成功"})


@app.route('/api/government/policies/<int:policy_id>', methods=['PUT'])
def gov_update_policy(policy_id):
    user = _get_session_user()
    if not user or user['role'] != 'government':
        return jsonify({"success": False, "message": "权限不足"}), 403
    data = request.get_json() or {}
    fields = {k: v for k, v in data.items()
              if k in ('title', 'content', 'category', 'is_published', 'summary', 'date')}
    if 'category' in fields:
        fields['category'] = database.normalize_policy_category(fields['category'])
    # 资料来源单独走 source_text（表单原文 → JSON），不直接写 source 列
    if 'source' in data:
        fields['source_text'] = data.get('source') or ''
    database.update_policy(policy_id, **fields)
    return jsonify({"success": True, "message": "更新成功"})


@app.route('/api/government/policies/<int:policy_id>', methods=['DELETE'])
def gov_delete_policy(policy_id):
    user = _get_session_user()
    if not user or user['role'] != 'government':
        return jsonify({"success": False, "message": "权限不足"}), 403
    database.delete_policy(policy_id)
    return jsonify({"success": True, "message": "已删除"})


# ---- 数据大屏 ----

@app.route('/api/government/dashboard', methods=['GET'])
def gov_dashboard():
    user = _get_session_user()
    if not user or user['role'] != 'government':
        return jsonify({"success": False, "message": "权限不足"}), 403
    return jsonify({"success": True, "overview": database.get_government_overview()})


# ==================== 教师扩展 API ====================

# ---- 课程管理 ----

@app.route('/api/teacher/courses', methods=['GET'])
def teacher_get_courses():
    user = _get_session_user()
    if not user or user['role'] not in ('teacher', 'super_admin'):
        return jsonify({"success": False, "message": "权限不足"}), 403
    courses = database.get_courses(teacher_id=user['username'], published_only=False)
    return jsonify({"success": True, "courses": courses})


@app.route('/api/teacher/courses', methods=['POST'])
def teacher_create_course():
    user = _get_session_user()
    if not user or user['role'] != 'teacher':
        return jsonify({"success": False, "message": "权限不足"}), 403
    data = request.get_json()
    course_id = database.create_course(
        data.get('title', ''), data.get('description', ''),
        data.get('category', ''), user['username'],
        data.get('cover_url', ''))
    return jsonify({"success": True, "id": course_id, "message": "课程创建成功，等待审核"})


@app.route('/api/teacher/courses/<int:course_id>', methods=['PUT'])
def teacher_update_course(course_id):
    user = _get_session_user()
    if not user or user['role'] != 'teacher':
        return jsonify({"success": False, "message": "权限不足"}), 403
    data = request.get_json()
    database.update_course(course_id, **{k: v for k, v in data.items()
        if k in ('title', 'description', 'category', 'cover_url')})
    return jsonify({"success": True, "message": "更新成功"})


@app.route('/api/teacher/courses/<int:course_id>', methods=['DELETE'])
def teacher_delete_course(course_id):
    user = _get_session_user()
    if not user or user['role'] != 'teacher':
        return jsonify({"success": False, "message": "权限不足"}), 403
    database.delete_course(course_id)
    return jsonify({"success": True, "message": "删除成功"})


# ---- 课程素材 ----

@app.route('/api/teacher/courses/<int:course_id>/materials', methods=['GET'])
def teacher_get_materials(course_id):
    materials = database.get_course_materials(course_id)
    return jsonify({"success": True, "materials": materials})


@app.route('/api/teacher/courses/<int:course_id>/materials', methods=['POST'])
def teacher_add_material(course_id):
    user = _get_session_user()
    if not user or user['role'] != 'teacher':
        return jsonify({"success": False, "message": "权限不足"}), 403
    if 'file' not in request.files:
        return jsonify({"success": False, "message": "请选择文件"}), 400
    f = request.files['file']
    if not f.filename:
        return jsonify({"success": False, "message": "文件名为空"}), 400
    # 保存文件
    filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{f.filename}"
    filepath = os.path.join('uploads', 'courses', str(course_id), filename)
    os.makedirs(os.path.dirname(os.path.join(_BASE_DIR, filepath)), exist_ok=True)
    f.save(os.path.join(_BASE_DIR, filepath))
    # 判断类型
    ext = f.filename.rsplit('.', 1)[-1].lower() if '.' in f.filename else ''
    if ext in ('mp4', 'avi', 'mov', 'webm', 'mkv'):
        mtype = 'video'
    elif ext == 'pdf':
        mtype = 'pdf'
    else:
        mtype = 'other'
    mat_id = database.add_course_material(course_id, mtype, f.filename, filepath)
    return jsonify({"success": True, "id": mat_id, "message": "上传成功"})


@app.route('/api/teacher/materials/<int:mat_id>', methods=['DELETE'])
def teacher_delete_material(mat_id):
    user = _get_session_user()
    if not user or user['role'] != 'teacher':
        return jsonify({"success": False, "message": "权限不足"}), 403
    filepath = database.delete_course_material(mat_id)
    if filepath:
        full = os.path.join(_BASE_DIR, filepath)
        if os.path.exists(full):
            os.remove(full)
    return jsonify({"success": True, "message": "删除成功"})


# ---- 3D 模型管理 ----

@app.route('/api/teacher/models-3d', methods=['GET'])
@_require_role(*_TEACHER_ROLES)
def teacher_get_models_3d():
    user = _get_session_user()
    models = database.get_models_3d(teacher_id=user['username'] if user['role'] == 'teacher' else None,
                                    published_only=False)
    return jsonify({"success": True, "models": models})


@app.route('/api/teacher/models-3d', methods=['POST'])
@_require_role('teacher')
def teacher_create_model_3d():
    user = _get_session_user()
    if 'file' not in request.files:
        return jsonify({"success": False, "message": "请选择模型文件"}), 400
    f = request.files['file']
    if not f.filename:
        return jsonify({"success": False, "message": "文件名为空"}), 400
    # 文件类型校验：仅允许常见 3D 模型格式
    ext = os.path.splitext(f.filename)[1].lower().lstrip('.')
    if ext not in ('glb', 'gltf', 'obj', 'fbx', 'stl', 'dae', 'ply', 'usdz'):
        return jsonify({"success": False, "message": "不支持的文件格式，仅支持 glb/gltf/obj/fbx/stl/dae/ply/usdz"}), 400
    title = request.form.get('title', f.filename)
    description = request.form.get('description', '')
    craft_type = request.form.get('craft_type', '')
    # 保存文件
    filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{f.filename}"
    filepath = os.path.join('uploads', 'models_3d', filename)
    os.makedirs(os.path.dirname(os.path.join(_BASE_DIR, filepath)), exist_ok=True)
    save_full = os.path.join(_BASE_DIR, filepath)
    f.save(save_full)
    # 记录真实文件大小（上限 50MB，超限删除并拒绝）
    file_size = os.path.getsize(save_full) if os.path.exists(save_full) else 0
    if file_size > 50 * 1024 * 1024:
        if os.path.exists(save_full):
            os.remove(save_full)
        return jsonify({"success": False, "message": "文件过大，模型文件不能超过 50MB"}), 400
    model_id = database.create_model_3d(title, description, craft_type,
                                         filepath, f.filename, file_size, user['username'])
    return jsonify({"success": True, "id": model_id, "message": "3D模型上传成功，等待审核"})


@app.route('/api/teacher/models-3d/<int:model_id>', methods=['DELETE'])
@_require_role('teacher')
def teacher_delete_model_3d(model_id):
    filepath = database.delete_model_3d(model_id)
    if filepath:
        full = os.path.join(_BASE_DIR, filepath)
        if os.path.exists(full):
            os.remove(full)
    return jsonify({"success": True, "message": "删除成功"})


# ==================== 企业用户 API ====================

# ---- 职位管理 ----

@app.route('/api/enterprise/jobs', methods=['GET'])
def enterprise_get_jobs():
    user = _get_session_user()
    if not user or user['role'] != 'enterprise':
        return jsonify({"success": False, "message": "权限不足"}), 403
    conn = database.get_connection()
    rows = conn.execute(
        "SELECT * FROM job_listings WHERE enterprise_id = ? ORDER BY posted_at DESC",
        (user['username'],)).fetchall()
    conn.close()
    jobs = []
    for r in rows:
        d = dict(r)
        d['requirements'] = json.loads(d['requirements'])
        # 附上最近一次审核记录：企业需要知道「是否被驳回、为什么」才能修改重投。
        # 只给一个「已驳回」状态、不给理由，企业只能干等（2026-10-07 补）。
        review = database.get_review_by_content('job', d['id'])
        d['review_comment'] = (review or {}).get('review_comment') or ''
        d['reviewed_at'] = (review or {}).get('reviewed_at') or ''
        jobs.append(d)
    return jsonify({"success": True, "jobs": jobs})


@app.route('/api/enterprise/jobs', methods=['POST'])
def enterprise_create_job():
    user = _get_session_user()
    if not user or user['role'] != 'enterprise':
        return jsonify({"success": False, "message": "权限不足"}), 403
    data = request.get_json()
    conn = database.get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO job_listings (title, company, salary, requirements, description, "
        "location, category, job_type, education, experience, company_size, industry, "
        "enterprise_id, review_status, posted_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now','localtime'))",
        (data.get('title', ''), user.get('company_name', data.get('company', '')),
         data.get('salary', ''), json.dumps(data.get('requirements', [])),
         data.get('description', ''), data.get('location', ''),
         data.get('category', ''), data.get('job_type', '全职'),
         data.get('education', ''), data.get('experience', ''),
         user.get('company_name', ''), data.get('industry', ''),
         user['username'], 'pending'))
    conn.commit()
    job_id = cursor.lastrowid
    conn.close()
    database.create_content_review('job', job_id, user['username'])
    return jsonify({"success": True, "id": job_id, "message": "职位发布成功，等待审核"})


@app.route('/api/enterprise/jobs/<int:job_id>', methods=['PUT'])
def enterprise_update_job(job_id):
    user = _get_session_user()
    if not user or user['role'] != 'enterprise':
        return jsonify({"success": False, "message": "权限不足"}), 403
    data = request.get_json()
    conn = database.get_connection()
    updates = []
    params = []
    for k in ('title', 'company', 'salary', 'description', 'location',
              'category', 'job_type', 'education', 'experience', 'industry'):
        if k in data and data[k] is not None:
            updates.append(f"{k}=?"); params.append(data[k])
    if 'requirements' in data:
        updates.append("requirements=?"); params.append(json.dumps(data['requirements']))
    if updates:
        # 内容改了就重新走审核：否则「先发一条合规的骗过审核、通过后再改成违规内容」
        # 会绕过整个审核链路。改回 pending 并新开一条审核记录。
        updates.append("review_status=?")
        params.append('pending')
        params.append(job_id)
        conn.execute(f"UPDATE job_listings SET {', '.join(updates)} WHERE id=?", params)
        conn.commit()
    conn.close()
    if updates:
        database.create_content_review('job', job_id, user['username'])
        return jsonify({"success": True, "message": "更新成功，需重新审核"})
    return jsonify({"success": True, "message": "更新成功"})


@app.route('/api/enterprise/jobs/<int:job_id>', methods=['DELETE'])
def enterprise_delete_job(job_id):
    user = _get_session_user()
    if not user or user['role'] != 'enterprise':
        return jsonify({"success": False, "message": "权限不足"}), 403
    conn = database.get_connection()
    # 只能删自己发布的岗位（此前不校验归属，任何企业账号都能按 id 删别人的岗位）
    row = conn.execute("SELECT enterprise_id FROM job_listings WHERE id = ?", (job_id,)).fetchone()
    if not row or row['enterprise_id'] != user['username']:
        conn.close()
        return jsonify({"success": False, "message": "职位不存在或无权操作"}), 404
    conn.execute("DELETE FROM job_listings WHERE id = ?", (job_id,))
    conn.execute("DELETE FROM saved_jobs WHERE job_id = ?", (job_id,))
    conn.execute("DELETE FROM content_reviews WHERE content_type = 'job' AND content_id = ?", (job_id,))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": "删除成功"})


# ---- 求购管理：2026-10-06 用户拍板「供应链求购不做」，整块下线 ----
# 原 /api/enterprise/procurements 的 GET/POST/PUT/DELETE 四个接口连同企业端
# 「求购管理」页面一起移除。数据层（procurements 表与 database 的 CRUD）保留不动 ——
# 只下线对外入口，不做破坏性迁移；`/api/admin/reviews` 也不再下发求购待审项。


# ---- 简历管理 ----

@app.route('/api/enterprise/applications', methods=['GET'])
def enterprise_get_applications():
    user = _get_session_user()
    if not user or user['role'] != 'enterprise':
        return jsonify({"success": False, "message": "权限不足"}), 403
    conn = database.get_connection()
    # ⚠️ 原先只 JOIN users，**没有 JOIN resumes** → 企业端只能看到申请人姓名/电话/邮箱，
    #   学员在「我的简历」里填的意向岗位、学历、年限、技能、经历**企业完全看不到**，
    #   「简历管理」名不副实（2026-10-09）。这里 LEFT JOIN 补上，学员没填简历时
    #   resume_* 全为 NULL，前端如实显示「未填写」，不做任何补白。
    rows = conn.execute("""
        SELECT ja.id, ja.user_id, ja.job_id, ja.status, ja.applied_at,
               jl.title as job_title,
               u.name as applicant_name, u.phone as applicant_phone,
               u.email as applicant_email, u.bio as applicant_bio,
               r.title as resume_title, r.region as resume_region,
               r.education as resume_education, r.work_years as resume_work_years,
               r.phone as resume_phone, r.email as resume_email,
               r.self_eval as resume_self_eval, r.skills as resume_skills,
               r.experience as resume_experience, r.updated_at as resume_updated_at
        FROM job_applications ja
        JOIN job_listings jl ON ja.job_id = jl.id
        JOIN users u ON ja.user_id = u.username
        LEFT JOIN resumes r ON r.user_id = ja.user_id
        WHERE jl.enterprise_id = ?
        ORDER BY ja.applied_at DESC
    """, (user['username'],)).fetchall()
    conn.close()
    return jsonify({"success": True, "applications": [dict(r) for r in rows]})


@app.route('/api/enterprise/applications/<int:app_id>', methods=['PUT'])
def enterprise_update_application(app_id):
    user = _get_session_user()
    if not user or user['role'] != 'enterprise':
        return jsonify({"success": False, "message": "权限不足"}), 403
    data = request.get_json()
    new_status = data.get('status', '')
    if new_status not in ('approved', 'rejected', 'interview'):
        return jsonify({"success": False, "message": "无效的状态"}), 400
    conn = database.get_connection()
    conn.execute("UPDATE job_applications SET status = ? WHERE id = ?", (new_status, app_id))
    conn.commit()
    conn.close()
    status_labels = {'approved': '已通过', 'rejected': '已拒绝', 'interview': '已通知面试'}
    return jsonify({"success": True, "message": f"状态已更新为：{status_labels.get(new_status, new_status)}"})


@app.route('/api/enterprise/stats', methods=['GET'])
def enterprise_get_stats():
    user = _get_session_user()
    if not user or user['role'] != 'enterprise':
        return jsonify({"success": False, "message": "权限不足"}), 403
    conn = database.get_connection()
    # ⚠️ 「在招职位」只算**审核通过**的：企业刚发布的岗位是 `pending`，学员端只展示
    #    `review_status='approved'`（见 get_job_listings_base）。若这里把未审核岗位也数进去，
    #    企业会以为岗位已经对外可见 —— 与「职位管理」列表/学员端口径必须一致。
    total_jobs = conn.execute(
        "SELECT COUNT(*) FROM job_listings WHERE enterprise_id = ? AND review_status = 'approved'",
        (user['username'],)).fetchone()[0]
    # 未通过审核的（pending / rejected）单列，让企业知道有几个岗位在排队或被打回。
    # COALESCE 是 fail-safe：历史行若 review_status 为 NULL，也按「未通过」计，不会漏报。
    pending_jobs = conn.execute(
        "SELECT COUNT(*) FROM job_listings WHERE enterprise_id = ? "
        "AND COALESCE(review_status, '') != 'approved'",
        (user['username'],)).fetchone()[0]
    total_apps = conn.execute("""
        SELECT COUNT(*) FROM job_applications ja
        JOIN job_listings jl ON ja.job_id = jl.id
        WHERE jl.enterprise_id = ?
    """, (user['username'],)).fetchone()[0]
    conn.close()
    return jsonify({"success": True, "stats": {
        "total_jobs": total_jobs,
        "pending_jobs": pending_jobs,
        "total_applications": total_apps
    }})


# ==================== 公开 API ====================


# ---- 首页统计（公开，真实库计数） ----
# P1-3：Hero 三个统计数字原为硬编码假数据（12000/86/3500），违反「不编造」红线。
# 改为读取数据库真实条数：服务农户=学员数、培训课程=课程数、就业对接=岗位数。
# 即便演示库稀疏也照实展示，绝不虚构。

@app.route('/api/home/stats', methods=['GET'])
def public_home_stats():
    conn = database.get_connection()
    try:
        farmers = conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]
        courses = conn.execute("SELECT COUNT(*) FROM courses").fetchone()[0]
        jobs = conn.execute("SELECT COUNT(*) FROM job_listings").fetchone()[0]
    finally:
        conn.close()
    return jsonify({
        "success": True,
        "stats": {
            "farmers": farmers,
            "courses": courses,
            "jobs": jobs
        }
    })


# ---- 系统公告（公开） ----

@app.route('/api/system-announcements', methods=['GET'])
def public_get_system_announcements():
    anns = database.get_system_announcements(active_only=True)
    return jsonify({"success": True, "announcements": anns})


# ---- 公开课程（用户端可见） ----

@app.route('/api/teacher/public-courses', methods=['GET'])
def public_get_courses():
    courses = database.get_courses(published_only=True)
    return jsonify({"success": True, "courses": courses})


@app.route('/api/teacher/public-courses/<int:course_id>', methods=['GET'])
def public_get_course_detail(course_id):
    course = database.get_course(course_id)
    if not course:
        return jsonify({"success": False, "message": "课程不存在"}), 404
    materials = database.get_course_materials(course_id)
    return jsonify({"success": True, "course": course, "materials": materials})


# ---- 公开3D模型（用户端可见） ----

@app.route('/api/teacher/public-models-3d', methods=['GET'])
def public_get_models_3d():
    craft_type = request.args.get('craft_type', '')
    models = database.get_models_3d(published_only=True)
    if craft_type:
        models = [m for m in models if m.get('craft_type') == craft_type]
    return jsonify({"success": True, "models": models})


# ---- 公开求购（用户端可见）：2026-10-06 随「供应链求购不做」整体下线 ----
# 学员端从未渲染过该接口（首页只有标题文案），此处一并移除，不留无界面的空接口。


# ---- 评论系统 ----

@app.route('/api/comments', methods=['GET'])
def public_get_comments():
    target_type = request.args.get('target_type', '')
    target_id = request.args.get('target_id', 0, type=int)
    if not target_type or not target_id:
        return jsonify({"success": False, "message": "参数不完整"}), 400
    comments = database.get_comments(target_type, target_id)
    return jsonify({"success": True, "comments": comments})


@app.route('/api/comments', methods=['POST'])
def public_add_comment():
    user = _get_session_user()
    if not user:
        return jsonify({"success": False, "message": "请先登录"}), 401
    data = request.get_json()
    target_type = data.get('target_type', '')
    target_id = data.get('target_id', 0)
    content = data.get('content', '').strip()
    if not target_type or not target_id or not content:
        return jsonify({"success": False, "message": "参数不完整"}), 400
    comment_id = database.add_comment(target_type, target_id, user['username'], content)
    return jsonify({"success": True, "id": comment_id, "message": "评论成功"})


# ---- 讨论区 ----

@app.route('/api/discussions', methods=['GET'])
def public_get_discussions():
    category = request.args.get('category', '')
    page = request.args.get('page', 1, type=int)
    discs, total = database.get_discussions(category=category or None, page=page)
    return jsonify({"success": True, "discussions": discs, "total": total})


@app.route('/api/discussions', methods=['POST'])
def public_create_discussion():
    user = _get_session_user()
    if not user:
        return jsonify({"success": False, "message": "请先登录"}), 401
    data = request.get_json()
    title = data.get('title', '').strip()
    content = data.get('content', '').strip()
    category = data.get('category', 'general')
    if not title or not content:
        return jsonify({"success": False, "message": "标题和内容不能为空"}), 400
    disc_id = database.create_discussion(title, content, category, user['username'])
    return jsonify({"success": True, "id": disc_id, "message": "发布成功"})


@app.route('/api/discussions/<int:disc_id>', methods=['GET'])
def public_get_discussion(disc_id):
    disc = database.get_discussion(disc_id)
    if not disc:
        return jsonify({"success": False, "message": "帖子不存在"}), 404
    comments = database.get_comments('discussion', disc_id)
    return jsonify({"success": True, "discussion": disc, "comments": comments})

# ==================== 静态文件兜底（必须放最后） ====================

# ⚠️ 这条路由此前是 send_from_directory(_BASE_DIR, filename) ——
# 等于把**项目根下的任何文件**挂到了公网：`GET /.env` 可以直接读走 AI_API_KEY 与
# SECRET_KEY，`/database.py` 拿到全部源码，`/data/yuexiang.db` 拿到整个数据库。
# 现在收敛为「资源目录 + 静态资源后缀」双白名单，并显式拒绝隐藏文件、源码、数据与备份。
#
# 前端实际引用（已逐文件核对）：*.html、*.css、*.js、js/core.js、images/**、sw.js。
# uploads/ 下是教师上传的课程材料与 3D 模型（后缀不定），因此按**目录**整体放行。
_ALLOWED_STATIC_DIRS = frozenset((
    'js', 'css', 'images', 'img', 'assets', 'fonts', 'uploads', 'vendor',
))
_ALLOWED_STATIC_EXTS = frozenset((
    '.html', '.htm', '.css', '.js', '.mjs', '.map',
    '.jpg', '.jpeg', '.png', '.webp', '.gif', '.svg', '.ico', '.bmp', '.avif',
    '.woff', '.woff2', '.ttf', '.otf', '.eot',
    '.mp4', '.webm', '.ogv', '.ogg', '.mp3', '.wav', '.m4a',
    '.pdf',
    '.glb', '.gltf', '.obj', '.fbx', '.stl', '.dae', '.ply', '.mtl', '.usdz',
))
# 即使落在被放行的目录里，这些后缀（源码 / 配置 / 数据 / 密钥 / 备份）也一律不提供下载。
_FORBIDDEN_STATIC_EXTS = frozenset((
    '.py', '.pyc', '.pyo', '.pyd', '.pyw',
    '.env', '.ini', '.cfg', '.conf', '.toml', '.yaml', '.yml',
    '.sql', '.sh', '.bash', '.zsh', '.bat', '.cmd', '.ps1',
    '.db', '.sqlite', '.sqlite3', '.log', '.bak', '.old', '.orig', '.swp', '.tmp',
    '.pem', '.key', '.crt', '.cer', '.p12', '.pfx',
))
# 顶层的敏感目录（源码 / 数据 / 部署配置），整目录拒绝
_FORBIDDEN_STATIC_DIRS = frozenset((
    'data', 'db', 'api', 'logs', '__pycache__', 'venv', '.venv', 'node_modules',
))


def _static_not_found():
    """统一以 404 + JSON 返回，避免用不同响应暴露「这个文件到底存不存在」。"""
    return jsonify({"success": False, "code": "not_found", "message": "文件不存在"}), 404


@app.route('/<path:filename>')
def serve_static(filename):
    # 逐段归一化；send_from_directory 自身也带路径穿越防护，这里再挡一层更直观
    parts = [p for p in filename.replace('\\', '/').split('/') if p not in ('', '.')]
    if not parts or '..' in parts:
        return _static_not_found()
    # 1) 任何一段以「.」开头（.env / .env.example / .git / .workbuddy ...）一律拒绝
    for seg in parts:
        if seg.startswith('.'):
            return _static_not_found()
    # 2) 敏感目录整目录拒绝（放行目录只可能是 parts[0]）
    head = parts[0].lower()
    if head in _FORBIDDEN_STATIC_DIRS:
        return _static_not_found()

    ext = os.path.splitext(parts[-1])[1].lower()
    if ext in _FORBIDDEN_STATIC_EXTS:
        return _static_not_found()
    # 3) 放行条件：位于资源目录内，或根目录下的白名单后缀
    in_allowed_dir = len(parts) > 1 and head in _ALLOWED_STATIC_DIRS
    if not in_allowed_dir and ext not in _ALLOWED_STATIC_EXTS:
        return _static_not_found()

    return send_from_directory(_BASE_DIR, filename)


# ==================== 启动 ====================

if __name__ == '__main__':
    database.init_db()
    print("🌾 启动粤乡智匠服务...")
    print("=" * 50)
    print("🌱 粤乡智匠 - AI驱动的农村人才赋能平台")
    print(f"📊 服务地址: http://localhost:5000")
    print(f"📚 健康检查: http://localhost:5000/api/health")
    if not _ai_configured():
        print("⚠️  未配置 AI_API_KEY：所有 AI 功能将返回明确的「未启用」提示")
    print("=" * 50)
    # 安全：调试模式会把 Werkzeug 交互式调试器暴露给能访问该端口的所有人。
    # 仅在显式设置 FLASK_DEBUG=1 时开启，默认关闭。
    _debug = os.getenv('FLASK_DEBUG', '').strip().lower() in ('1', 'true', 'yes', 'on')
    app.run(host='0.0.0.0', port=5000, debug=_debug, use_reloader=False)
