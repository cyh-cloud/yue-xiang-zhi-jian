# -*- coding: utf-8 -*-
"""领域路由层：一个领域一个 Blueprint，领域之间禁止互相 import。

蓝图门面：core.app_factory 只从这里取蓝图对象，不写
`from domains.<域>.routes import ...`。共享层不得 import 领域模块，而
tools/check_architecture.py 正是用这条线来判定违规的（见 T01 与 T07）。

电商运营域（domains.ecommerce）导出蓝图 ecommerce_bp。该域的三条链路（带货话术、
商品文案、客服对练）共用同一个蓝图对象；朗读实录分析与三类实训提交属直播实训域，
不在该域内。

农业培训域（domains.agriculture）导出蓝图 agriculture_bp。该域因 600 行上限把路由
拆在 routes.py（问答与追问建议）与 calendar.py（目录、日历、订阅与提醒）两个模块里，
但蓝图对象只有一个，由本文件统一导出。农技问答的系统提示词组是该域自己的资产，
不进共享层；共享层只保留农技口径的**判定函数** has_chem_dosage，病虫害诊断域与
方言问答域都从那里取（见 docs/adr/0001 的边界件归属一节）。

病虫害域（domains.pest）导出蓝图 pest_bp，覆盖 URL 前缀 /api/agriculture/ 下的
诊断与速查两条链路。它与农业培训域共用前缀但分属不同领域（spec 的切分单位一节把
「病虫害诊断域」与「病虫害速查域」单列），因此独立成目录，不并进 domains/agriculture。
本域同样因 600 行上限拆成 routes / diagnosis / knowledge 三个模块，蓝图只有一个。

本土资源域（domains.resources）导出蓝图 resources_bp：方言问答、成功案例、政策信息。
案例与政策的内容事实源在 domain_data.resources，经 database 契约层读取；方言知识库与
降级话术库是本域自己的资产（dialect_voice.py）；农技口径的判定函数与免责声明在
共享层 shared.agri_dosage，与农业培训域、病虫害诊断域共用同一份。

就业对接域（domains.employment）导出蓝图 employment_bp：岗位浏览与筛选、详情、
相似推荐、证书与积分、投递、收藏。

就业能力档案域（domains.employment_profile）导出蓝图 employment_profile_bp：能力档案、
在线简历、AI 简历辅助、求职意向。它与就业对接域共用 `/api/employment/*` 前缀但分属
不同领域（spec 的切分单位一节把两者单列），因此是两个蓝图对象而不是一个。
两域之间**没有** import 边：它们唯一共享的「是否已有简历」判断放在共享层
shared.resume_state，两边都从那里取同一份口径。
"""
from domains.agriculture import agriculture_bp
from domains.auth import auth_bp
from domains.community import community_bp
from domains.crafts import crafts_bp
from domains.ecommerce import ecommerce_bp
from domains.employment import employment_bp
from domains.employment_profile import employment_profile_bp
from domains.admin import admin_bp
from domains.enterprise import enterprise_bp
from domains.government import government_bp
from domains.live_training import live_training_bp
from domains.messages import messages_bp
from domains.notifications import notifications_bp
from domains.pest import pest_bp
from domains.public import public_bp
from domains.resources import resources_bp
from domains.teaching_support import teaching_support_bp
from domains.teacher import teacher_bp
from domains.static_files import static_bp
from domains.user_profile import user_profile_bp

__all__ = ['agriculture_bp', 'auth_bp', 'community_bp', 'crafts_bp',
           'ecommerce_bp', 'employment_bp', 'employment_profile_bp',
           'admin_bp', 'enterprise_bp', 'government_bp',
           'live_training_bp', 'pest_bp', 'public_bp',
           'messages_bp', 'notifications_bp',
           'resources_bp', 'static_bp',
           'teaching_support_bp', 'teacher_bp',
           'user_profile_bp']
