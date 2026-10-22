#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""消息域：站内私信的发送、会话列表、已读状态。

T18 从 app.py 迁出。T09 搬公开域与社区域时漏掉了这个区块，它一直滞留到 T18 前。

身份护栏用共享层 core.session.messages_self_guard：它本质是鉴权，且通知域也要用，
放消息域会让通知域反向依赖消息域。落库走 database 契约层
（db_domains/messages.py 那批函数）。
"""

from flask import Blueprint, jsonify, request

from core.permissions import ENTERPRISE, STUDENT, TEACHER
from core.session import get_session_user, messages_self_guard
from db_domains import employment
from db_domains import students
from db_domains import users
from db_domains import messages as messages_db


CAPABILITIES_USED = ('message.read', 'user.read', 'student.read', 'job.read')

messages_bp = Blueprint('messages', __name__)


def _recipient_allowed(sender, receiver):
    """Business relationships that permit a direct message."""
    sender_role = sender.get('role')
    receiver_role = receiver.get('role')
    sender_id = sender.get('username') or ''
    receiver_id = receiver.get('username') or ''

    if sender_role == TEACHER and receiver_role == STUDENT:
        return students.is_student_linked_to_teacher(receiver_id, sender_id)
    if sender_role == ENTERPRISE and receiver_role == STUDENT:
        return employment.has_applied_to_enterprise(receiver_id, sender_id)
    if sender_role == STUDENT and receiver_role == TEACHER:
        return students.is_student_linked_to_teacher(sender_id, receiver_id)
    if sender_role == STUDENT and receiver_role == ENTERPRISE:
        return employment.has_applied_to_enterprise(sender_id, receiver_id)
    return False


@messages_bp.route('/api/messages/send', methods=['POST'])
def send_message():
    user = get_session_user()
    if not user:
        return jsonify({"success": False, "message": "请先登录"}), 401
    data = request.get_json(silent=True) or {}
    # ⚠️ sender_id 一律取会话用户，**不再信任请求体** —— 否则谁都能冒名发消息。
    sender_id = user['username']
    receiver_id = (data.get('receiver_id') or '').strip()
    content = (data.get('content') or '').strip()
    if not receiver_id or not content:
        return jsonify({"success": False, "message": "参数不完整"}), 400
    if receiver_id == sender_id:
        return jsonify({"success": False, "message": "不能给自己发消息"}), 400
    receiver = users.get_user_by_id(receiver_id)
    if not receiver:
        return jsonify({"success": False, "message": "收件人不存在"}), 404
    if not _recipient_allowed(user, receiver):
        return jsonify({
            "success": False,
            "message": "无权向该用户发送消息",
        }), 403
    mid = messages_db.send_message(sender_id, receiver_id, content)
    return jsonify({"success": True, "message": "发送成功", "id": mid})


@messages_bp.route('/api/messages/inbox', methods=['GET'])
def get_inbox():
    user_id = request.args.get('user_id', '')
    if not user_id:
        return jsonify({"success": False, "message": "缺少用户ID"}), 400
    _, err = messages_self_guard(user_id)
    if err:
        return err
    inbox = messages_db.get_inbox(user_id)
    return jsonify({"success": True, "inbox": inbox})


@messages_bp.route('/api/messages/conversation/<other_id>', methods=['GET'])
def get_conversation(other_id):
    user_id = request.args.get('user_id', '')
    if not user_id:
        return jsonify({"success": False, "message": "缺少用户ID"}), 400
    _, err = messages_self_guard(user_id)
    if err:
        return err
    messages = messages_db.get_messages(user_id, other_id)
    # 标记对方发来的消息为已读
    messages_db.mark_messages_read(other_id, user_id)
    return jsonify({"success": True, "messages": messages})


@messages_bp.route('/api/messages/read', methods=['POST'])
def mark_messages_read():
    data = request.get_json(silent=True) or {}
    receiver_id = (data.get('receiver_id') or '').strip()
    sender_id = (data.get('sender_id') or '').strip()
    if not receiver_id or not sender_id:
        return jsonify({"success": False, "message": "参数不完整"}), 400
    # 标为已读的是「别人发给我的」→ receiver 必须是本人
    _, err = messages_self_guard(receiver_id)
    if err:
        return err
    messages_db.mark_messages_read(sender_id, receiver_id)
    return jsonify({"success": True})


@messages_bp.route('/api/messages/unread', methods=['GET'])
def get_unread_count():
    user_id = request.args.get('user_id', '')
    if not user_id:
        return jsonify({"success": False, "message": "缺少用户ID"}), 400
    _, err = messages_self_guard(user_id)
    if err:
        return err
    count = messages_db.get_unread_count(user_id)
    return jsonify({"success": True, "count": count})


__all__ = ['messages_bp']
