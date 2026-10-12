# -*- coding: utf-8 -*-
"""社区域：讨论帖与评论。

本域只有 routes 一个模块：讨论帖的列表/详情/发布与评论的读/写。发布两条路由只认
会话头，鉴权方式与其余领域一致，一律走共享层 core.session.get_session_user，
本域不持有第二份会话实现。

T09 从 app.py 迁出，对外契约（URL、请求响应结构、状态码、错误码）保持不变。
"""

from domains.community.routes import community_bp

__all__ = ['community_bp']
