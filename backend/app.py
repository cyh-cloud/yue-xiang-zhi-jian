#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
粤乡智匠 - 基于AI实训系统的农村本土人才赋能平台
Flask后端应用
"""

import repo_paths

# 后端代码整体迁入 backend/ 后，本文件与它 import 的 core / ai / shared /
# db_domains / domains / db_init 都同在 backend/ 下。把 backend/
# 放进 sys.path，这些 import 才能继续用顶层包名解析，不必把每一处都改成
# backend.xxx 的限位导入。放在 repo_paths 之后、其它 import 之前。
import os as _os
import sys as _sys

_BACKEND_DIR = _os.path.dirname(_os.path.abspath(__file__))
if _BACKEND_DIR not in _sys.path:
    _sys.path.insert(0, _BACKEND_DIR)

# 环境变量必须先于任何读配置的模块导入：上游模型配置（ai.client）、CORS 白名单
# （core.app_factory）都在 import 时就从 os.environ 取值。放在 import 之后会让
# .env 里的 AI_API_KEY / CORS_ORIGINS 静默失效 —— 症状是「本地明明配了却提示未配置」。
from dotenv import load_dotenv

load_dotenv(repo_paths.ENV_FILE)

from flask import jsonify
from datetime import datetime
import os
import logging

# 共享层：应用级横切、上游模型调用、纯函数工具（见 docs/adr/0001-backend-domain-split.md）
from core.app_factory import BASE_DIR, create_app
# 「上游是否已配置」按模块属性调用（ai.client.ai_configured()），不从上面的
# `from ai.client import ...` 再绑一个同名本地名。原因是测试模拟「上游未配置」时
# 改写的是 ai.client.ai_configured 这个模块属性，也就是开关的真正持有者；本地名字
# 在 import 时就绑定了函数对象，改写模块属性影响不到它，用例会从「验证明确失败」
# 退化成真的去打上游。T08 删掉了原先那层 app._ai_configured 转发票，就是靠这里的
# 属性查找接住 patch。
import ai.client

# 电商运营域（带货话术 / 商品文案 / 客服对练）已整体迁至 domains.ecommerce
# （蓝图 ecommerce_bp，由 core.app_factory 注册）。该域专属的限流额度、输入上限、
# 风格与格式配置、宣传合规口径 _EC_PROMO_RULE 都在 domains.ecommerce.prompts；
# 作物白名单与 EC_* 额度因直播实训域也要用，按 T13 的裁决放在共享层
# shared.ec_products。本文件不持有任何一份副本。

# 静态资源域的静态白名单常量：随路由一起迁到 domains.static_files，这里只做别名
# 转发，供 test_paths.py 的「uploads 在放行目录里」断言继续从 app 读取。
from domains.static_files import _ALLOWED_STATIC_DIRS as static_allowlist_dirs

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 应用由工厂创建：Flask 实例、应用配置、跨域配置、蓝图注册都收在 core.app_factory。
# 本文件只保留「创建应用 + 挂路由」，路由在 T07 起按领域陆续迁出为蓝图。
app = create_app()


# 静态资源根目录的唯一常量在 core.app_factory（BASE_DIR，从仓库根推导，与上传落盘
# 目录同源）。`_BASE_DIR` 是同一对象的旧名，保留给既有的路径基准测试与外部脚本引用
# （test_paths.py 断言 app._BASE_DIR 等于仓库根）。首页与静态兜底本身已迁至
# domains.static_files，白名单说明见那里。
_BASE_DIR = BASE_DIR
# 静态白名单常量随路由一起迁走，这里保留同名别名：test_paths.py 的
# 「uploads 在放行目录里」断言仍从 app 读。
_ALLOWED_STATIC_DIRS = static_allowlist_dirs


# ==================== 会话与权限助手 ====================
# 会话取用户、角色装饰器、限流与限流键的唯一实现在 core.session（共享层）。
#
# ⚠️ 装饰器工厂的时序前提：`@require_role(...)` 在**导入使用它的路由模块时**就会被
# 调用，因此它必须在那些模块顶部的 import 区就已完成绑定，不能放进函数体内延迟导入。
# （历史教训：2026-10-07 之前它一直被定义在 5600 行附近、从未被任何路由使用，
#  导致 /api/teacher/* 几乎全部裸奔，不带会话头也能读学员名册、改分数、删学员。）


# ---- 农业培训域：农技问答（含流式）、追问建议、农事日历、作物订阅与到期提醒 ----
# 已整体迁至 domains.agriculture（蓝图 agriculture_bp，由 core.app_factory 注册）。
# 本域专属的 helper 与缓存（_parse_agri_request / _build_agri_messages /
# _generate_suggestions / _suggestions_cache / _month_in_phase /
# _farming_task_brief）随路由一起搬走。
# 农技问答的系统提示词在 domains.agriculture.prompts，农技口径的判定函数
# has_chem_dosage 在共享层 shared.agri_dosage。

# ---- 本土资源域：方言问答、成功案例、政策信息 ----
# 已整体迁至 domains.resources（蓝图 resources_bp，由 core.app_factory 注册）。
# 方言知识库 DIALECTS_DATA 与方言降级话术库（原 generate_dynamic_voice_answer）在
# domains.resources.dialect_voice，随域一起搬走；方言语音问答的限流额度 VOICE_RATE_LIMIT
# 也随它走。案例与政策的内容事实源在 db_domains.content（T09 起读库，ADR 0002），
# 经 db_domains.resources 组装可见性，这里不持有第二份。
# 用药口径的判定函数与免责声明文案仍在共享层 shared.agri_dosage（农业培训域、病虫害
# 诊断域也判定它），本域按 chem_notice 单独字段下发，拼法见域内 _chem_dose_notice_for。


# ==================== 电商运营域 ====================
# 带货话术、商品文案、客服对练三条链路已整体迁至 domains.ecommerce
# （蓝图 ecommerce_bp，由 core.app_factory 注册）。
#
# T12 收尾时漏搬了商品文案与客服对练两条链路，它们在此滞留到 T13 才被发现：
# 后果是 5 条路由被注册两次、4 个 helper 存在两份实现。现已删除本文件中的副本，
# domains/ecommerce/ 成为唯一实现。


# ==================== 就业对接域 / 就业能力档案域 ====================
# 两个区块已整体迁出为蓝图，由 core.app_factory 注册：
#
# 就业对接域（domains.employment，蓝图 employment_bp）：岗位浏览与筛选、详情、
# 相似推荐、证书与积分、投递、收藏。
#
# 就业能力档案域（domains.employment_profile，蓝图 employment_profile_bp）：
# 能力档案、在线简历、AI 简历辅助、求职意向登记。
#
# 两个域共用 /api/employment/* 前缀但分属不同领域（spec 的切分单位一节），
# 因此是两个蓝图对象。原 helper 的归属：
#   _self_only      -> core.session.self_only_guard（身份护栏，与 messages_self_guard 同构）
#   _profile_for_ai -> domains.employment_profile.service.profile_for_ai
#   _user_has_resume-> domains.employment_profile.service.user_has_resume
#                       （spec 的边界件归属：归就业能力档案域，就业对接域显式引用）
#   _category_option_list -> shared.options.category_option_list（T03 已上提共享层，
#                       app.py 里那份同名副本早已删掉）
#
# 原 app.py 里的 RESUME_AI_* 常量随 AI 简历辅助一起搬进
# domains.employment_profile.prompts。领域路由模块之间不得互相 import（T01 机械检查），
# 所以「是否已有简历」不能放在就业对接域里让就业能力档案域来取。

# ==================== 教师管理域 / 教学支撑域 ====================
# 两个区块已整体迁出为蓝图，由 core.app_factory 注册：
#
# 教师管理域（domains.teacher，蓝图 teacher_bp）：名册与学员的增删改查、账号绑定、
# AI 教学报告。因 spec 的「单个领域路由文件不超过 600 行」拆成
# routes.py + reports.py，共用同一个蓝图对象。
#
# 教学支撑域（domains.teaching_support，蓝图 teaching_support_bp）：公告（教师增删 +
# 学员读）、实训批改、教师端实训提交列表、学情分析、课程增删改、课程材料上传与删除、
# 3D 模型上传与删除。
#
# 两个域共用 /api/teacher/* 前缀但按 spec 的切分单位分属不同领域，因此是两个蓝图
# 对象。原 helper 的归属：
#   _normalize_roster_rows / _build_fallback_overview / _build_fallback_report
#                       -> domains.teacher.reports（随教师管理域走）
#   _training_status_label -> shared.training_status（零领域状态的查表）
#                       T13 把它搬进 domains/live_training/routes.py 时删掉了 app.py
#                       的定义，却漏了这个调用点（/api/teacher/trainings 直接 500）。
#                       教师端与学员端都要用它，而领域之间不得互相 import（T01），
#                       因此上提共享层，两边共用同一份。
#   上传落盘目录基准     -> core.app_factory.BASE_DIR（仓库根），与静态资源域放行的
#                       uploads/ 同源，仍是「存得下也取得到」。


# ==================== 超级管理员域 / 政府域 / 企业域 ====================
# 三个区块已整体迁出为蓝图，由 core.app_factory 注册：
#
# 超级管理员域（domains.admin，蓝图 admin_bp）：用户管理（列表/改/停用/删）、
# 内容审核（列表 + 通过/驳回/撤销）、系统公告增删、评论与帖子删除。
#
# 政府域（domains.government，蓝图 government_bp）：政策管理与数据大屏。
#
# 企业域（domains.enterprise，蓝图 enterprise_bp）：岗位管理（列表/发/改/删）、
# 投递处理（列表/改状态）、统计。
#
# 三个域共用「按角色切分管理端」的形状，但按 spec 的切分单位分属不同领域，
# 因此是三个蓝图对象而不是一个 admin 大蓝图。角色边界逐字保持不变：
# admin_bp 只允许 super_admin、government_bp 只允许 government、
# enterprise_bp 只允许 enterprise，把关写法仍是拆分前的函数内 inline 403，
# 不改成 require_role 装饰器 —— 改写判定形式就是改行为（未登录拿到的是 403）。
#
# 审核三种动作对四个领域公开状态的影响没有动：T05 已把审核状态变更收敛为
# db_domains/reviews.py 的 set_review_status() 单一分派入口，按内容类型分派到
# 课程 / 岗位 / 3D 模型各域的窄接口。admin_bp 只调
# db_domains.reviews 的 approve_review / reject_review / revoke_review 这三个入口，
# 不在路由层直接写任何领域表。
#
# 政策发布/更新的三条口径（normalize_policy_category / policy_sources_to_json /
# default_policy_summary）都在 db_domains/resources.py，调用方按域 import 访问；
# 政策内容的事实源是 government_policies 表（政府端可发布与下架），本文件不持有副本。


# ==================== 健康检查 ====================
# 不属于任何业务领域，因此不建领域蓝图，留在入口文件。
# 理由：spec 的切分单位一节按业务内聚性划域，而这条路由既不读数据层也不调上游，
# 只是「进程活着、能回 JSON」的探针。它的真实消费者是运维与自动化 ——
# e2e/playwright.config.js 用它作 webServer 的就绪探针，e2e 的 smoke 与
# portals-smoke 也打它。把它塞进任一会影响它可用性的业务域（例如该域蓝图的
# 注册顺序或 import 出错）都是把探针的可靠性绑到无关代码上。
# 它仍然由 core.app_factory 创建的应用承载，`from app import app` 的行为不变。


@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({
        "success": True, "healthy": True,
        "service": "粤乡智匠API",
        "timestamp": datetime.now().isoformat()
    })


# ==================== 启动 ====================

if __name__ == '__main__':
    # 端口与 run.py / _serve.py 同一解析逻辑：环境变量 PORT > .env 的 PORT > 默认 5000。
    from run import resolve_port
    port, port_source = resolve_port()
    from db_init import init_db
    init_db()
    print("🌾 启动粤乡智匠服务...")
    print("=" * 50)
    print("🌱 粤乡智匠 - AI驱动的农村人才赋能平台")
    print(f"📊 服务地址: http://localhost:{port}")
    print(f"📚 健康检查: http://localhost:{port}/api/health")
    if port_source == 'config':
        print(f"端口 {port} 来自 PORT 配置（环境变量或 .env）")
    else:
        print(f"端口 {port}（PORT 未配置或配置为空，使用默认端口）")
    if not ai.client.ai_configured():
        print("⚠️  未配置 AI_API_KEY：所有 AI 功能将返回明确的「未启用」提示")
    print("=" * 50)
    # 安全：调试模式会把 Werkzeug 交互式调试器暴露给能访问该端口的所有人。
    # 仅在显式设置 FLASK_DEBUG=1 时开启，默认关闭。
    _debug = os.getenv('FLASK_DEBUG', '').strip().lower() in ('1', 'true', 'yes', 'on')
    app.run(host='0.0.0.0', port=port, debug=_debug, use_reloader=False)
