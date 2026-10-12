# -*- coding: utf-8 -*-
"""消息域的门面：站内私信的发送、会话、已读。

只导出蓝图对象给 core.app_factory 注册；域内实现不对外暴露，
避免别的域绕过门面直接 import 本域实现。
"""

from domains.messages.routes import messages_bp

__all__ = ['messages_bp']
