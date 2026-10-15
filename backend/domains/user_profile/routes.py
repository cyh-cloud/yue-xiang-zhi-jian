# -*- coding: utf-8 -*-
"""用户资料域路由：个人资料读写与改密码。

从 app.py 迁出（后端按领域拆分 T08），URL、请求响应结构、状态码、错误码保持不变。

三条路由都只认会话头 X-Session-Id，请求体里没有 user_id 参数：这是「只能改本人」
的实现方式，不存在越权写入他人资料的入口。

⚠️ 改密码有一条拆分前就存在的缺陷，本次只搬不改：路由把 session 里的 user_id
（username 字符串）传给按数值主键查表的 users.change_password，于是任何账号
都拿到「用户不存在」。行为由 tests/test_auth_profile_domains.py 按现状锁定。
"""

from flask import Blueprint, jsonify, request
from db_domains import auth, users

CAPABILITIES_USED = ('auth.read', 'user.read')

user_profile_bp = Blueprint('user_profile', __name__)


@user_profile_bp.route('/api/user/profile', methods=['GET'])
def get_user_profile():
    """获取当前用户完整资料"""
    session_id = request.headers.get('X-Session-Id', '')
    session = auth.get_session(session_id)
    if not session:
        return jsonify({"success": False, "message": "未登录"}), 401
    user = users.get_user_by_id(session['user_id'])
    if not user:
        return jsonify({"success": False, "message": "用户不存在"})
    return jsonify({"success": True, "user": user})


@user_profile_bp.route('/api/user/profile', methods=['PUT'])
def update_profile():
    """更新用户资料"""
    session_id = request.headers.get('X-Session-Id', '')
    session = auth.get_session(session_id)
    if not session:
        return jsonify({"success": False, "message": "未登录"}), 401
    data = request.get_json()
    name = data.get('name', '').strip()
    email = data.get('email', '').strip()
    if not name:
        return jsonify({"success": False, "message": "姓名不能为空"})
    users.update_user_profile(session['user_id'], name=name, email=email)
    return jsonify({"success": True, "message": "资料更新成功"})


@user_profile_bp.route('/api/user/password', methods=['PUT'])
def change_password():
    """修改密码"""
    session_id = request.headers.get('X-Session-Id', '')
    session = auth.get_session(session_id)
    if not session:
        return jsonify({"success": False, "message": "未登录"}), 401
    data = request.get_json()
    old_password = data.get('old_password', '')
    new_password = data.get('new_password', '')
    confirm_password = data.get('confirm_password', '')
    if not old_password or not new_password:
        return jsonify({"success": False, "message": "请填写完整"})
    if new_password != confirm_password:
        return jsonify({"success": False, "message": "两次输入的新密码不一致"})
    if len(new_password) < 6:
        return jsonify({"success": False, "message": "新密码至少6位"})
    success, msg = users.change_password(session['user_id'], old_password, new_password)
    return jsonify({"success": success, "message": msg})