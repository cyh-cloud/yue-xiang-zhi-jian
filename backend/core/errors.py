# -*- coding: utf-8 -*-
"""统一错误响应出口。

全站错误响应一律是 `{"success": False, ...}` 加一个可判别的 code 与一段面向用户的
文案，前端与自动化测试都按 code 断言。此前每处都是手写 jsonify，形状靠人记；
这里给一个出口，保证新增错误响应时形状不漂移。

⚠️ 只提供**新的**出口，不改写既有调用点：本次拆分的红线是对外行为零变化，
既有调用点逐步迁入，迁移前后响应体必须逐字节一致。
"""

from flask import jsonify


def error_response(message, code=None, status=400, **extra):
    """构造统一形状的错误响应，返回 (response, status)。

    code 缺省时不下发该键 —— 既有大量响应只有 success + message，
    统一补一个 code 会改变对外契约。
    """
    body = {"success": False}
    if code:
        body["code"] = code
    body["message"] = message
    body.update(extra)
    return jsonify(body), status


def login_required(message='请先登录'):
    return error_response(message, status=401)


def forbidden(message='权限不足'):
    return error_response(message, status=403)


def not_found(message='不存在'):
    return error_response(message, status=404)


def bad_request(message='参数不完整', code=None):
    return error_response(message, code=code, status=400)


__all__ = [
    'error_response', 'login_required', 'forbidden', 'not_found', 'bad_request',
]
