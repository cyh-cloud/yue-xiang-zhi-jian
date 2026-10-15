# -*- coding: utf-8 -*-
"""认证域路由：登录、登出、会话校验、注册。

从 app.py 迁出（后端按领域拆分 T08），URL、请求响应结构、状态码、错误码保持不变。

会话的读写一律走共享层 core.session 与数据层的 db_domains.auth，本域不再持有
第二份会话实现。`/api/auth/verify` 返回的 user 结构必须与 `/api/auth/login` 逐键一致：
前端 restoreSession() 会用它整体覆盖 AppState.user，少一个 id 就会让
所有 `/api/.../${user.id}` 拼成 /undefined（这条契约由
tests/test_auth_profile_domains.py 锁定）。

登录不按角色名分流：`ROLES` 只是「这个角色存在」的登记，会话与鉴权都由能力表裁决
（core/permissions.py）。运营角色 operator 由超管在管理端指派，不进这里的注册白名单。
"""

from flask import Blueprint, jsonify, request

from core.permissions import capabilities_for_role

import database

auth_bp = Blueprint('auth', __name__)

# 可自助注册的角色。operator / government / super_admin 一律不在其列：这三种身份
# 由超管在管理端指派（用户故事 9 的权限边界），放开自助注册等于人人可自助提权。
SELF_SERVICE_ROLES = ('student', 'teacher', 'enterprise')


@auth_bp.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({"success": False, "message": "请输入用户名和密码"}), 400

    user = database.authenticate_user(username, password)
    if user:
        if user.get('status') == 'suspended':
            return jsonify({"success": False, "message": "账号已被停用，请联系管理员"}), 403
        session_id = database.create_session(username)
        return jsonify({
            "success": True,
            "session_id": session_id,
            "user": {"id": user['username'], "name": user['name'], "role": user['role'],
                     "email": user.get('email', ''), "phone": user.get('phone', ''),
                     "avatar_url": user.get('avatar_url', ''), "company_name": user.get('company_name', ''),
                     "region": user.get('region', ''), "status": user.get('status', 'active')},
            # 当前角色持有的能力清单，随登录一并下发。前端据此按能力显隐导航与按钮，
            # 不必自己维护一份角色表（单一真相源：能力只在 core.permissions 一处定义）。
            # 未登录的访客走不到这里，故 capabilities 恒为非空数组。
            "capabilities": capabilities_for_role(user.get('role'))
        })

    return jsonify({"success": False, "message": "用户名或密码错误"}), 401


@auth_bp.route('/api/auth/logout', methods=['POST'])
def logout():
    data = request.get_json()
    session_id = data.get('session_id')
    if session_id:
        database.delete_session(session_id)
    return jsonify({"success": True, "message": "已退出登录"})


@auth_bp.route('/api/auth/verify', methods=['POST'])
def verify_session():
    data = request.get_json()
    session_id = data.get('session_id')
    if not session_id:
        return jsonify({"success": False, "message": "未提供session"}), 401

    session = database.get_session(session_id)
    if session:
        # ⚠️ 这里必须与 /api/auth/login 返回同一套 user 结构。
        # 前端 restoreSession() 会用它**整体覆盖** AppState.user，而 database.get_session()
        # 只给 {user_id, name, role}（键名是 user_id，没有 id）→ AppState.user.id 变成
        # undefined，此后所有 `/api/.../${AppState.user.id}` 都会拼成 `/api/.../undefined`。
        # 旧接口大多不校验 user_id 所以没暴露；就业对接的 _self_only() 会直接 403。
        user = database.get_user_by_id(session['user_id']) or {}
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
            },
            # 与 login 同一口径：刷新页面后前端仍要知道这个角色能做什么，
            # 否则按能力显隐的导航会在刷新后整块消失。
            "capabilities": capabilities_for_role(
                session.get('role') or user.get('role', ''))
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
    if role not in SELF_SERVICE_ROLES:
        return jsonify({"success": False, "message": "无效的角色类型"}), 400

    user_id, msg = database.register_user(username, password, name, role,
                                          email, phone, company_name, region)
    if user_id:
        session_id = database.create_session(username)
        user = database.get_user_by_id(username)
        return jsonify({
            "success": True,
            "message": msg,
            "session_id": session_id,
            "user": {"id": user['username'], "name": user['name'], "role": user['role'],
                     "email": user.get('email', ''), "phone": user.get('phone', ''),
                     "avatar_url": user.get('avatar_url', ''), "company_name": user.get('company_name', ''),
                     "region": user.get('region', ''), "status": user.get('status', 'active')},
            "capabilities": capabilities_for_role(user.get('role'))
        })
    return jsonify({"success": False, "message": msg}), 400


@auth_bp.route('/api/auth/capabilities', methods=['GET'])
def capabilities():
    """当前会话角色持有的能力清单（按能力显隐的前端数据源）。

    前端把登录/校验时拿到的 capabilities 存进 AppState；这个接口是同一份数据的
    按需再取入口，供「会话已在但页面刚加载完」的时序用。未登录返回空数组而不是
    401：显隐逻辑需要能跑在访客态上（访客什么管理入口都看不到）。
    """
    from core.session import get_session_user
    user = get_session_user()
    role = user.get('role') if user else None
    return jsonify({"success": True, "role": role or '',
                    "capabilities": capabilities_for_role(role)})


__all__ = ['auth_bp', 'SELF_SERVICE_ROLES']
