# -*- coding: utf-8 -*-
"""农业培训域：农技问答（含流式）、追问建议、农事日历、作物订阅与到期提醒。

一个领域一个蓝图（docs/adr/0001），蓝图对象 agriculture_bp 定义在 routes.py。
因 spec 的「单个领域路由文件不超过 600 行」，本域的路由拆在两个模块里，共用同一个
蓝图对象，两者都是本域的模块：

- routes.py   农技问答（含 SSE 流式）与追问建议；
- calendar.py 农产品目录、农事日历、作物订阅与到期提醒。

prompts 里的提示词组只被问答路径取用。作物名解析改读 farming_products 目录表
（ADR 0002 删掉了代码里的四份作物名副本），问答题支持的作物集合随之由运营维护。

农技口径的分工：判定函数 has_chem_dosage 在共享层（病虫害诊断域与方言问答域也判定它），
命中后展示的文案常量在 prompts，随本域走。

会话取用户与限流只用共享层 core.session，上游模型调用只用共享层 ai.client，
数据访问走 db_domains，本域不持有第二份实现。
"""

from domains.agriculture.calendar import agriculture_bp
from domains.agriculture.prompts import (
    CHEM_DOSE_NOTICE,
    CHEM_DOSE_NOTICE_BLOCK,
    agriculture_product_name,
    agri_system_prompt,
)

__all__ = [
    'agriculture_bp',
    'CHEM_DOSE_NOTICE', 'CHEM_DOSE_NOTICE_BLOCK',
    'agriculture_product_name', 'agri_system_prompt',
]
