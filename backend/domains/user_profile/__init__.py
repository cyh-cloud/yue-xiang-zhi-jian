# -*- coding: utf-8 -*-
"""用户资料域：个人资料读写与改密码。

本域只有 routes 一个模块：三条路由，共用「从会话头取当前用户」这一种鉴权方式，
没有第二个消费方，没有必要再拆层。

T08 从 app.py 迁出，对外契约（URL、请求响应结构、状态码、错误码）保持不变。
"""

from domains.user_profile.routes import user_profile_bp

__all__ = ['user_profile_bp']