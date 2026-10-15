# -*- coding: utf-8 -*-
"""手工技艺域：技艺列表与详情。

本域只有 routes 一个模块，内容数据源在 db_domains.crafts（T08 起读库，ADR 0002）。
"""

from domains.crafts.routes import crafts_bp

__all__ = ['crafts_bp']
