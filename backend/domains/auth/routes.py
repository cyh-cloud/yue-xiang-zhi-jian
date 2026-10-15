# -*- coding: utf-8 -*-
"""认证域路由：登录、登出、会话校验、注册。

从 app.py 迁出（后端按领域拆分 T08），URL、请求响应结构、状态码、错误码保持不变。

会话的读写一律走共享层 core.session 与数据层的 db_domains.auth，本域不再持有
第二份会话实现。`/api/auth/verify` 返回的 user 结构必须与 `/api/auth/login`
逐键一致：前端 restoreSession() 会用它整体覆盖 AppState.user，少一个 id 就会让
所有 `/api/.../${user.id}` 拼成 /undefined（这条契约由
tests/test_auth_profile_domains.py 锁定）。
"""

from flask import Blueprint, jsonify, request
from db_domains import auth, users


CAPABILITIES_USED = ('auth.read', 'user.read')

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({"success": False, "message": "请输入用户名和密码"}), 400

    user = auth.authenticate_user(username, password)
    if user:
        if user.get('status') == 'suspended':
            return jsonify({"success": False, "message": "账号已被停用，请联系管理员"}), 403
        session_id = auth.create_session(username)
        return jsonify({
            "success": True,
            "session_id": session_id,
            "user": {"id": user['username'], "name": user['name'], "role": user['role'],
                     "email": user.get('email', ''), "phone": user.get('phone', ''),
                     "avatar_url": user.get('avatar_url', ''), "company_name": user.get('company_name', ''),
                     "region": user.get('region', ''), "status": user.get('status', 'active')}
        })

    return jsonify({"success": False, "message": "用户名或密码错误"}), 401


@auth_bp.route('/api/auth/logout', methods=['POST'])
def logout():
    data = request.get_json()
    session_id = data.get('session_id')
    if session_id:
        auth.delete_session(session_id)
    return jsonify({"success": True, "message": "已退出登录"})


@auth_bp.route('/api/auth/verify', methods=['POST'])
def verify_session():
    data = request.get_json()
    session_id = data.get('session_id')
    if not session_id:
        return jsonify({"success": False, "message": "未提供session"}), 401

    session = auth.get_session(session_id)
    if session:
        # ⚠️ 这里必须与 /api/auth/login 返回同一套 user 结构。
        # 前端 restoreSession() 会用它**整体覆盖** AppState.user，而 auth.get_session()
        # 只给 {user_id, name, role}（键名是 user_id，没有 id）→ AppState.user.id 变成
        # undefined，此后所有 `/api/.../${AppState.user.id}` 都会拼成 `/api/.../undefined`。
        # 旧接口大多不校验 user_id 所以没暴露；就业对接的 _self_only() 会直接 403。
        user = users.get_user_by_id(session['user_id']) or {}
        return jsonify({
            "success": True,
            "user": {
                "id": session['user_id'],
                "name": session.get('name') or user.get('name', ''),
                "role": session.get('role') or user.get('role', ''),
                "email": user.get('email', ''),
                "phone": user.get('phone', ''),
                "avatar_url": user.get('avatar_url', ''),
                "company_name": user.get('company_name', ''),
                "region": user.get('region', ''),
                "status": user.get('status', 'active')
            }
        })
    return jsonify({"success": False, "message": "会话无效"}), 401


@auth_bp.route('/api/auth/register', methods=['POST'])
def register():
    """用户注册"""
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    name = data.get('name', '').strip()
    role = data.get('role', 'student')
    email = data.get('email', '').strip()
    phone = data.get('phone', '').strip()
    company_name = data.get('company_name', '').strip()
    region = data.get('region', '').strip()

    if not username or not password or not name:
        return jsonify({"success": False, "message": "用户名、密码和姓名不能为空"}), 400
    if len(password) < 6:
        return jsonify({"success": False, "message": "密码至少6位"}), 400
    if role not in ('student', 'teacher', 'enterprise'):
        return jsonify({"success": False, "message": "无效的角色类型"}), 400

    user_id, msg = users.register_user(username, password, name, role,
                                          email, phone, company_name, region)
    if user_id:
        session_id = auth.create_session(username)
        user = users.get_user_by_id(username)
        return jsonify({
            "success": True,
            "message": msg,
            "session_id": session_id,
            "user": {"id": user['username'], "name": user['name'], "role": user['role'],
                     "email": user.get('email', ''), "phone": user.get('phone', ''),
                     "avatar_url": user.get('avatar_url', ''), "company_name": user.get('company_name', ''),
                     "region": user.get('region', ''), "status": user.get('status', 'active')}
        })
    return jsonify({"success": False, "message": msg}), 400