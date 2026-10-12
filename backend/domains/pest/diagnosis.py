# -*- coding: utf-8 -*-
"""病虫害诊断：文字与图片两条路径、本地知识库降级、结论来源标注。

从 app.py 迁出（后端按领域拆分 T11），行为逐字不变。两条路径的约定：

  · 带照片 → 必须走视觉模型。知识库匹配根本不读图片，带图时降级返回 KB 结论
    会让用户误以为「看图诊断成功」，因此 AI 不可用时直接报错，不降级。
  · 纯文字 → 优先 AI；AI 不可用时降级知识库，来源由 tag_diagnosis_source 如实标注。

上游是否已配置按**模块属性**调用（ai.client.ai_configured()），不在 import 时绑定
本地名字：测试模拟「上游未配置」时改写的是这个模块属性，也就是开关的真正持有者，
import 时绑定会让 patch 失效，用例会从「验证明确失败」退化成真的去打上游。
"""

import base64
import json
import logging
import re
import os

from flask import jsonify, request

import ai.client
from ai.client import AI_REASONING_TOKEN_RESERVE
from core.session import client_key, rate_limited
from domain_data.pest_diagnosis.pest_data import PEST_KNOWLEDGE
from shared.agri_dosage import CHEM_DOSE_NOTICE, has_chem_dosage

logger = logging.getLogger(__name__)

# ---- 输入约束、图片上限与限流 ----
DIAG_SYMPTOMS_MAX_LEN = 500              # 症状描述最大字符数（与前端 maxlength 保持一致）
DIAG_RATE_LIMIT = int(os.getenv('DIAG_RATE_LIMIT', '60'))   # 每窗口内诊断请求上限
DIAG_MAX_IMAGES = 3                      # 单次最多上传图片数
DIAG_MAX_IMAGE_BYTES = 4 * 1024 * 1024   # 单张图片解码后字节上限（前端已压缩，通常远低于此）
DIAG_ALLOWED_IMAGE_TYPES = ('image/jpeg', 'image/png', 'image/webp')

# 图片诊断不可用时的对外文案：不含部署细节，只告诉用户「现在能做什么」。
AI_VISION_NOT_CONFIGURED_MSG = (
    'AI 服务尚未启用，暂时无法进行图片诊断。'
    '你可以改用文字描述症状，或联系平台管理员；如需即时帮助可拨打 12316 三农服务热线。'
)
AI_VISION_UNAVAILABLE_MSG = (
    '图片诊断功能暂未开放。'
    '你可以改用文字描述症状，或联系平台管理员；如需即时帮助可拨打 12316 三农服务热线。'
)
AI_VISION_NOT_CONFIGURED_LOG = 'AI_VL_MODEL 未配置：请在项目根目录 .env 中填入支持图片输入的模型名后重启服务'
AI_NOT_CONFIGURED_LOG = 'AI_API_KEY 未配置：请在项目根目录 .env 中填入有效密钥后重启服务'
AI_UNAVAILABLE_MSG = (
    'AI 服务暂时不可用，请稍后重试。'
    '如需即时帮助，可咨询当地农技站或拨打 12316 三农服务热线。'
)

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


def tag_diagnosis_source(diagnosis, source):
    """给诊断结论打上来源标记，供前端展示角标与免责说明。"""
    meta = DIAG_SOURCE_META.get(source) or DIAG_SOURCE_META[DIAG_SOURCE_KB]
    diagnosis['source'] = source if source in DIAG_SOURCE_META else DIAG_SOURCE_KB
    diagnosis['source_label'] = meta['label']
    diagnosis['source_note'] = meta['note']
    return diagnosis


def parse_diag_images(raw):
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


def parse_diag_request():
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

    images, img_msg, img_code = parse_diag_images(data.get('image'))
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


def diag_system_prompt(crop_data, crop, has_image):
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


def diag_user_message(crop_data, symptoms, image_count=0):
    """拼装用户消息。用户没提供的信息如实说明，不再替用户补一个症状。"""
    lines = [f"作物：{crop_data['name']}"]
    if image_count:
        lines.append(f"随附照片：{image_count} 张")
    if symptoms:
        lines.append(f"症状描述：{symptoms}")
    elif image_count:
        lines.append("症状描述：（用户未提供文字描述，请仅依据照片判断）")
    return "\n".join(lines)


def parse_ai_diagnosis(result, crop_data):
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
    if has_chem_dosage(_dose_probe):
        _note = str(diagnosis.get('note') or '').strip()
        diagnosis['note'] = (_note + '\n\n' + CHEM_DOSE_NOTICE) if _note else CHEM_DOSE_NOTICE
    diagnosis['crop'] = crop_data['name']
    diagnosis['crop_icon'] = crop_data['icon']
    return diagnosis


def diagnose_via_ai(crop_data, crop, user_symptoms, images):
    """调用 AI 得到诊断结果（带图走视觉模型）。任何失败抛异常，降级策略由调用方决定。"""
    has_image = bool(images)
    system_prompt = diag_system_prompt(crop_data, crop, has_image)
    user_message = diag_user_message(crop_data, user_symptoms, len(images))
    if has_image:
        result = ai.client.call_ai_vision_service(
            system_prompt=system_prompt,
            user_message=user_message,
            images=images,
            temperature=0.3,
            # 诊断要输出一段结构化 JSON，推理模型思考约 800~1800 token，必须留足
            max_tokens=2000 + AI_REASONING_TOKEN_RESERVE,
            timeout=120
        )
    else:
        result = ai.client.call_ai_service(
            system_prompt=system_prompt,
            user_message=user_message,
            temperature=0.3,
            max_tokens=2000 + AI_REASONING_TOKEN_RESERVE
        )
    return parse_ai_diagnosis(result, crop_data)


# 知识库匹配阈值：低于此分视为「没匹配上」，宁可如实说没识别出来，也不硬凑一个结论。
KB_MATCH_THRESHOLD = 0.30

# 只保留汉字/字母/数字，其余（标点、空白、括号）一律剔除后再切双字词。
_KB_NOISE_RE = re.compile(r'[^\u4e00-\u9fffA-Za-z0-9]+')


def kb_bigrams(text):
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


def kb_overlap_ratio(user_bigrams, text):
    """用户描述与一段文本的双字词重合率（用文本自身的词数归一化，长度无关）。"""
    ref = kb_bigrams(text)
    if not ref or not user_bigrams:
        return 0.0
    return len(user_bigrams & ref) / float(len(ref))


def match_kb_disease(crop_data, user_symptoms):
    """知识库匹配。返回 (病害条目或 None, 得分)。

    对所有条目的「病名 + 各条典型症状的重合度」取最高分，而不是首个命中即返回 ——
    后者会让排在前面的病害吃掉所有命中。得分低于 KB_MATCH_THRESHOLD 时返回 None，
    不再默认返回第一条病害（那会把「没匹配上」伪装成结论）。
    """
    text = str(user_symptoms or '').strip()
    if not text:
        return None, 0.0
    user_bigrams = kb_bigrams(text)
    if not user_bigrams:
        return None, 0.0

    best, best_score = None, 0.0
    for d in crop_data['common_diseases']:
        # 用户直接报病名是最强的信号，与各条症状描述的重合度一起取最大值
        score = kb_overlap_ratio(user_bigrams, d.get('disease'))
        for symptom in d.get('symptoms') or []:
            score = max(score, kb_overlap_ratio(user_bigrams, symptom))
        if score > best_score:
            best, best_score = d, score
    if best_score < KB_MATCH_THRESHOLD:
        return None, best_score
    return best, best_score


def run_diagnosis(payload):
    """诊断主流程。payload 已由 parse_diag_request 校验，形如
    {'crop': ..., 'symptoms': ..., 'images': [...]}。返回可直接交给路由的 (响应, 状态码)。
    """
    if rate_limited('diag:' + client_key(), DIAG_RATE_LIMIT):
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
        if not ai.client.ai_configured():
            logger.warning("图片诊断被调用但未配置密钥：%s", AI_NOT_CONFIGURED_LOG)
            return jsonify({
                "success": False, "code": "ai_not_configured",
                "message": AI_VISION_NOT_CONFIGURED_MSG
            }), 503
        # 视觉模型名按模块属性取，不在 import 时绑定本地名字：测试改写
    # ai.client.AI_VL_MODEL 时要能生效（与 ai_configured 同一套 patch 约定）。
    if not (ai.client.AI_VL_MODEL or '').strip():
            logger.warning("图片诊断被调用但未配置视觉模型：%s", AI_VISION_NOT_CONFIGURED_LOG)
            return jsonify({
                "success": False, "code": "ai_vision_unavailable",
                "message": AI_VISION_UNAVAILABLE_MSG
            }), 503

    # 未配置密钥的纯文字请求不必白跑一次上游（空密钥必然 401）
    if has_image or ai.client.ai_configured():
        try:
            diagnosis = diagnose_via_ai(crop_data, crop, user_symptoms, images)
            return jsonify({
                "success": True,
                "diagnosis": tag_diagnosis_source(diagnosis, DIAG_SOURCE_AI),
            }), 200
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
    matched, match_score = match_kb_disease(crop_data, user_symptoms)
    if matched is None:
        logger.info('知识库未匹配到病害(crop=%s, score=%.3f)', crop, match_score)
        return jsonify({
            "success": False, "code": "no_match",
            "message": "未能从描述中匹配到对应的病害，请补充发病部位、病斑颜色与形状等更具体的症状后重试。"
        }), 200

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
        "diagnosis": tag_diagnosis_source(diagnosis, DIAG_SOURCE_KB),
    }), 200


__all__ = [
    'DIAG_SOURCE_AI', 'DIAG_SOURCE_KB', 'DIAG_SOURCE_META',
    'DIAG_SYMPTOMS_MAX_LEN', 'DIAG_RATE_LIMIT', 'DIAG_MAX_IMAGES',
    'DIAG_MAX_IMAGE_BYTES', 'DIAG_ALLOWED_IMAGE_TYPES',
    'tag_diagnosis_source', 'parse_diag_images', 'parse_diag_request',
    'diag_system_prompt', 'diag_user_message', 'parse_ai_diagnosis',
    'diagnose_via_ai', 'KB_MATCH_THRESHOLD',
    'kb_bigrams', 'kb_overlap_ratio', 'match_kb_disease',
    'run_diagnosis',
]
