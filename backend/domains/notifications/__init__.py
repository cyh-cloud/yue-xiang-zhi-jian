# -*- coding: utf-8 -*-
"""通知域的门面：系统通知、已读状态与未读总数。

只导出蓝图对象给 core.app_factory 注册；域内实现不对外暴露。
"""

from domains.notifications.routes import notifications_bp

__all__ = ['notifications_bp']
