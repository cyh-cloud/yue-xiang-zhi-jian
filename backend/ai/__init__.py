# -*- coding: utf-8 -*-
"""上游模型调用：模型配置、同步补全、流式补全、多模态补全。

全站所有 AI 调用只有这一个出口（含流式）。本模块不感知任何具体领域，
只依赖环境变量里的上游配置与 requests。
"""

from ai.client import (
    AI_API_KEY,
    AI_API_URL,
    AI_CHAT_MODEL,
    AI_MODEL,
    AI_REASONING_EFFORT,
    AI_REASONING_TOKEN_RESERVE,
    AI_VL_MODEL,
    ai_configured,
    ai_vision_configured,
    call_ai_service,
    call_ai_vision_service,
    chat_completion,
    chat_model,
    stream_chat_completion,
)

__all__ = [
    'AI_API_URL', 'AI_API_KEY', 'AI_MODEL', 'AI_VL_MODEL', 'AI_CHAT_MODEL',
    'AI_REASONING_EFFORT', 'AI_REASONING_TOKEN_RESERVE',
    'ai_configured', 'ai_vision_configured', 'chat_model',
    'chat_completion', 'stream_chat_completion',
    'call_ai_service', 'call_ai_vision_service',
]
