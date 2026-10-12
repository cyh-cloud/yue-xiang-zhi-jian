# -*- coding: utf-8 -*-
"""直播实训域的门面。

只导出蓝图对象给 core.app_factory 注册；域内模块不对外暴露，
避免别的域绕过门面直接 import 本域实现。
"""

from domains.live_training.routes import live_bp as live_training_bp

__all__ = ['live_training_bp']
