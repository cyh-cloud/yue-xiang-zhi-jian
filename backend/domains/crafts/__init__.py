# -*- coding: utf-8 -*-
"""手工技艺域：技艺列表与详情。

本域只有 routes 一个模块：两条路由加它们共用的 CRAFTS_KNOWLEDGE 数据源，
没有第二个消费方，没有必要再拆层。
"""

from domains.crafts.routes import CRAFTS_KNOWLEDGE, crafts_bp

__all__ = ['crafts_bp', 'CRAFTS_KNOWLEDGE']
