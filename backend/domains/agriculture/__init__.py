# -*- coding: utf-8 -*-
"""农业培训域：农技问答（含流式）、追问建议、农事日历、作物订阅与到期提醒。

T03 先落地农技问答的系统提示词组（作物名解析 + 农业知识常量 + 农技口径文案常量），
T10 把路由也搬进同一目录，本域自此成为一个完整的领域路由模块。

一个领域一个蓝图（docs/adr/0001），蓝图对象 agriculture_bp 定义在 routes.py。
因 spec 的「单个领域路由文件不超过 600 行」，本域的路由拆在两个模块里，共用同一个
蓝图对象，两者都是本域的模块：

- routes.py   农技问答（含 SSE 流式）与追问建议；
- calendar.py 农产品目录、农事日历、作物订阅与到期提醒。

两者共享 calendar_data 里的兜底目录与纯函数，prompts 里的提示词组只被问答路径取用。

农技口径的分工：判定函数 has_chem_dosage 在共享层（病虫害诊断域与方言问答域也判定它），
命中后展示的文案常量在 prompts，随本域走。

会话取用户与限流只用共享层 core.session，上游模型调用只用共享层 ai.client，
数据访问走 database，本域不持有第二份实现。
"""

from domains.agriculture.calendar import agriculture_bp
from domains.agriculture.prompts import (
    AGRICULTURE_KNOWLEDGE,
    CHEM_DOSE_NOTICE,
    CHEM_DOSE_NOTICE_BLOCK,
    agriculture_product_name,
    agri_system_prompt,
)
from domains.agriculture.routes import agriculture_bp

__all__ = [
    'agriculture_bp',
    'AGRICULTURE_KNOWLEDGE',
    'CHEM_DOSE_NOTICE', 'CHEM_DOSE_NOTICE_BLOCK',
    'agriculture_product_name', 'agri_system_prompt',
]