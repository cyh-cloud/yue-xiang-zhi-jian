# -*- coding: utf-8 -*-
"""电商运营域：带货话术、商品文案、客服对练三条实训链路。

一个领域一个蓝图（docs/adr/0001），蓝图对象 ecommerce_bp 定义在 routes.py。
本域在 `/api/ecommerce/*` 前缀下只含这三条链路，朗读实录分析与三类实训提交属
直播实训域（T13）。

因 spec 的「单个领域路由文件不超过 600 行」，本域按关注点拆成四个模块，
共用同一个蓝图对象，全部是本域的模块：

- routes.py         三条链路的路由与提示词拼装；
- prompts.py        限流与输入上限、风格 / 格式 / 场景配置、宣传合规口径 _EC_PROMO_RULE；
- feedback_rules.py 话术评分规则（纯函数、无随机数）；
- service_rules.py  客服回复评分、情绪信号、动态兜底与动态提示；
- copy_fallback.py  商品文案的降级正文。

作物白名单与校验函数在共享层 shared.ec_products（T13 迁入）。原按 spec 的边界件
规则定在本域，但「领域路由模块之间不得互相 import」是 T01 的机械硬约束，
直播实训域引用它必然违规；白名单是零领域状态的纯数据，放共享层最合适。
本域改为从 prompts 再导出，全站仍只有一份作物表。

文案评分只有共享层一份实现（shared.copywriting.copy_score），本域直接取用，
不留第二份。上游调用一律走共享层 ai.client，限流与取用户走共享层 core.session。
"""

from domains.ecommerce.prompts import (
    EC_COPY_FORMATS,
    EC_PRODUCTS,
    EC_STYLE_KEYS,
    _EC_PROMO_RULE,
)
from domains.ecommerce.routes import ecommerce_bp

__all__ = [
    'ecommerce_bp',
    'EC_PRODUCTS', 'EC_STYLE_KEYS', 'EC_COPY_FORMATS',
    '_EC_PROMO_RULE',
]
