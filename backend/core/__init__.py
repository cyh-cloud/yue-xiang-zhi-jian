# -*- coding: utf-8 -*-
"""应用级横切能力：应用工厂、跨域配置、会话鉴权、角色装饰器、限流与统一错误响应。

本目录只放「被多个领域共用的横切能力」，不感知任何具体领域（见 docs/adr/0001）。
领域路由蓝图由入口文件经 create_app 注册，领域之间永不互相 import。
"""

from core.app_factory import BASE_DIR, create_app

__all__ = ['create_app', 'BASE_DIR']
