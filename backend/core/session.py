# -*- coding: utf-8 -*-
"""会话取用户、角色装饰器、限流与限流键、消息身份护栏。

这几件事都是应用级横切能力，全站只有这一处实现。它们不感知任何领域，
只依赖请求上下文与数据层的会话表，因此任何领域都能直接调用。
"""

import os
import threading
import time

from flask import jsonify, request

import database

# 限流窗口（秒）。各接口的限额由各自的常量给出，窗口口径全站统一。
RATE_WINDOW = 300

# 教师端接口统一要求的角色（教师本人 + 超级管理员）
TEACHER_ROLES = ('teacher', 'super_admin')

# X-Forwarded-For 是请求头，客户端想写什么就写什么。此前限流键优先取它，
# 等于「换个头就换一个桶」—— 限流形同虚设，填了 AI_API_KEY 之后可被无限刷。
# 默认只信任对端地址（不可伪造）；只有确实部署在可信反代之后（并由反代覆写 XFF）
# 才用 TRUST_PROXY=1 显式开启。
TRUST_PROXY = os.getenv('TRUST_PROXY', '').strip().lower() in ('1', 'true', 'yes', 'on')

_rate_lock = threading.Lock()
_rate_buckets = {}


def get_session_user():
    """从请求头获取当前登录用户，未登录返回 None"""
    session_id = request.headers.get('X-Session-Id', '')
    if not session_id:
        return None
    session = database.get_session(session_id)
    if not session:
        return None
    user = database.get_user_by_id(session['user_id'])
    return user


def require_role(*roles):
    """角色权限装饰器：检查当前用户是否拥有指定角色（未登录 401 / 角色不符 403 / 停用 403）

    ⚠️ 这是装饰器**工厂**，在模块导入、装饰函数的那一刻就会被调用。所以调用方必须在
    import 阶段就能解析到它：领域路由模块在文件顶部 `from core.session import require_role`，
    不放进函数体内延迟导入，也不从入口文件转手。
    """
    from functools import wraps

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = get_session_user()
            if not user:
                return jsonify({"success": False, "message": "请先登录"}), 401
            if user['role'] not in roles:
                return jsonify({"success": False, "message": "权限不足"}), 403
            if user.get('status') == 'suspended':
                return jsonify({"success": False, "message": "账号已被停用"}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def rate_limited(key, limit, window=RATE_WINDOW):
    """按客户端标识做滑动窗口限流，返回 True 表示本次请求应被拒绝。

    仅用于保护会消耗算力的 AI 类接口，限额取得较宽（默认 5 分钟 60 次），
    正常提问不会触发。说明：这是内存态限流，多进程/重启后会重置，
    定位是「抑制滥用」而非安全边界。
    """
    now = time.time()
    cutoff = now - window
    with _rate_lock:
        bucket = _rate_buckets.get(key)
        if bucket is None:
            bucket = _rate_buckets[key] = []
        while bucket and bucket[0] < cutoff:
            bucket.pop(0)
        if len(bucket) >= limit:
            return True
        bucket.append(now)
        # 顺带回收过期桶，避免字典随 IP 数无限增长
        if len(_rate_buckets) > 2048:
            for k in [k for k, v in _rate_buckets.items() if not v or v[-1] < cutoff]:
                _rate_buckets.pop(k, None)
        return False


def client_key():
    """限流键。默认取对端地址；仅在显式信任反代时才采信 X-Forwarded-For 的最左值。"""
    if TRUST_PROXY:
        forwarded = (request.headers.get('X-Forwarded-For') or '').split(',')[0].strip()
        if forwarded:
            return forwarded
    return request.remote_addr or 'unknown'


def messages_self_guard(user_id):
    """消息接口的身份护栏：只能以本人身份读自己的私信。

    返回 (user, None) 放行，或 (None, (response, status)) 拒绝。
    ⚠️ 消息与通知两个领域都要用它：它本质是鉴权，放消息域会让通知域反向依赖消息域。
    """
    user = get_session_user()
    if not user:
        return None, (jsonify({"success": False, "message": "请先登录"}), 401)
    if not user_id or user_id != user['username']:
        return None, (jsonify({"success": False, "message": "权限不足"}), 403)
    return user, None


def self_only_guard(user_id, deny_message='权限不足'):
    """求职资料的身份护栏：只能以本人身份读写自己的求职资料。

    返回 (user, None) 放行，或 (None, (response, status)) 拒绝。
    ⚠️ 与 messages_self_guard 同构，区别只在 403 的文案：求职资料被越权访问时要
    说清「这是他人的求职资料」，而消息侧只说「权限不足」。两条护栏共用一个实现，
    按 spec 的边界件归属进共享层（本质是鉴权，放进任一领域都会让另一个领域反向依赖它）。
    """
    user = get_session_user()
    if not user:
        return None, (jsonify({"success": False, "message": "请先登录"}), 401)
    if not user_id or user_id != user['username']:
        return None, (jsonify({"success": False, "message": deny_message}), 403)
    return user, None


__all__ = [
    'RATE_WINDOW', 'TEACHER_ROLES', 'get_session_user', 'require_role',
    'rate_limited', 'client_key', 'messages_self_guard',
    'self_only_guard',
]
