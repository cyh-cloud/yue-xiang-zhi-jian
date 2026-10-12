# -*- coding: utf-8 -*-
"""认证域：登录、登出、会话校验、注册。

本域只有 routes 一个模块：四条路由加它们共用的会话读写。会话与角色鉴权的唯一
实现在共享层 core.session，本域直接调用，不再复制一份。

T08 从 app.py 迁出，对外契约（URL、请求响应结构、状态码、错误码）保持不变。
"""

from domains.auth.routes import auth_bp

__all__ = ['auth_bp']