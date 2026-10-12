# -*- coding: utf-8 -*-
"""公开域：首页统计、公开课程、公开 3D 模型、系统公告的公开读。

本域只有 routes 一个模块：四条路由，全部不带登录门禁。门户页对匿名访客开放，
发布态的过滤（published_only / active_only）由数据层按参数保证，路由层只多一层
craft_type 的内存过滤，这一行与拆分前逐字一致。

T09 从 app.py 迁出，对外契约（URL、请求响应结构、状态码、错误码）保持不变。
"""

from domains.public.routes import public_bp

__all__ = ['public_bp']
