# -*- coding: utf-8 -*-
"""病虫害域：诊断（文字与图片）与常见病虫害速查。

T11 从 app.py 迁出。诊断与速查合成一个领域路由目录，而不是两个，理由是它们共用
同一份病虫害知识：诊断的知识库降级读条目的病名与症状，速查读全部富字段。
分成两个目录会让这两个读者变成跨领域关系，而它们本来就是同一份事实源的两个视图，
耦合是本质的、不是偶然的。T07 起这份知识住在 pest 域的五张表里（db_domains.pest），
两个读者都从那里取。

一个领域一个蓝图（docs/adr/0001），蓝图对象 pest_bp 定义在 routes.py。
因 spec 的「单个领域路由文件不超过 600 行」，本域拆成三个模块，共用同一个蓝图对象：

- routes.py    两条路由的装配：POST /api/agriculture/diagnose 与
               GET /api/agriculture/pest-knowledge；
- diagnosis.py 文字/图片诊断：请求解析与图片校验、提示词组装、AI 结果解析、
               本地知识库双字词匹配，以及结论来源角标；
- knowledge.py 速查视图：一条记录的对外字段整形、筛选与免责说明。

跨域边界：病虫害知识只从 db_domains.pest 取，农技口径的判定函数只从共享层
shared.agri_dosage 取，上游模型调用只走共享层 ai.client，会话取用户与限流只用
共享层 core.session。本域不 import 任何其他领域路由模块。
"""

from domains.pest.diagnosis import DIAG_SOURCE_AI, DIAG_SOURCE_KB
from domains.pest.knowledge import PEST_DISCLAIMER
from domains.pest.routes import pest_bp

__all__ = [
    'pest_bp',
    'DIAG_SOURCE_AI', 'DIAG_SOURCE_KB',
    'PEST_DISCLAIMER',
]
