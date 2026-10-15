#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""通知域：系统通知、已读状态与未读总数。

T18 从 app.py 迁出。T09 搬公开域与社区域时漏掉了这个区块，它一直滞留到 T18 前。

T11：单条已读原先在本文件里直连 UPDATE notifications（绕过数据层），
已收进 db_domains/notifications.py 的 mark_notification_read。

身份护栏与消息域共用共享层的 core.session.messages_self_guard（它本质是鉴权，
放任一业务域都会让另一个域反向依赖）。未读总数由 db_domains/notifications.py 的
get_total_unread_count 算出，本域只负责把它下发。
"""

from flask import Blueprint, jsonify, request

from core.session import messages_self_guard
from db_domains import announcements, employment, messages
from db_domains import notifications as notifications_db

CAPABILITIES_USED = ('notification.read', 'message.read')

notifications_bp = Blueprint('notifications', __name__)


@notifications_bp.route('/api/notifications', methods=['GET'])
def get_notifications():
    user_id = request.args.get('user_id', '')
    # 通知属个人数据：与消息接口同款护栏，只看本人（修复越权：此前按 user_id 直查、不鉴权）
    _, err = messages_self_guard(user_id)
    if err:
        return err
    notifications = notifications_db.get_notifications(user_id)
    return jsonify({"success": True, "notifications": notifications})


@notifications_bp.route('/api/notifications/read', methods=['POST'])
def mark_notifications_read():
    data = request.get_json()
    user_id = data.get('user_id', '')
    _, err = messages_self_guard(user_id)
    if err:
        return err
    # 全部已读必须覆盖消息中心的**四个数据源**：站内通知、私信、投递状态、系统公告。
    # 此前只标了 notifications 一张表，企业通知与系统公告永远不会变已读 ——
    # 表现为「点了全部已读，未读项一条不少」（2026-10-09 用户走查反馈）。
    notifications_db.mark_notifications_read(user_id)
    messages.mark_all_messages_read(user_id)
    notifications_db.mark_refs_read(user_id, 'job_application',
                            employment.get_job_application_ids(user_id))
    notifications_db.mark_refs_read(user_id, 'system_announcement',
                            announcements.get_active_system_announcement_ids())
    return jsonify({"success": True})


@notifications_bp.route('/api/notifications/read-state', methods=['GET'])
def get_notification_read_state():
    """取自建已读旁路表里两个来源的已读 ref 列表。"""
    user_id = request.args.get('user_id', '')
    _, err = messages_self_guard(user_id)
    if err:
        return err
    return jsonify({
        "success": True,
        "refs": {
            "system_announcement": notifications_db.get_read_refs(user_id, 'system_announcement'),
            "job_application": notifications_db.get_read_refs(user_id, 'job_application')
        }
    })


@notifications_bp.route('/api/notifications/read-one', methods=['POST'])
def mark_one_notification_read():
    """把单条通知标为已读（消息中心「未读」页签点击即归档）。

    source 取值与前端 item.source 一致：
      notifications        站内通知（公告 / 实训批改），走 notifications.is_read
      messages             互动私信，ref_id 是对方 username，走 messages.is_read
      system_announcement  系统公告，走旁路表
      job_application      投递状态，走旁路表
    """
    data = request.get_json(silent=True) or {}
    user_id = data.get('user_id', '')
    source = (data.get('source') or '').strip()
    ref_id = str(data.get('ref_id') or '').strip()
    _, err = messages_self_guard(user_id)
    if err:
        return err
    if not source or not ref_id:
        return jsonify({"success": False, "message": "参数不完整"}), 400

    if source == 'notifications':
        # 只允许标自己的，避免拿别人的通知 id 乱标（过滤条件收在数据层里）
        if not notifications_db.mark_notification_read(user_id, ref_id):
            return jsonify({"success": False, "message": "通知不存在"}), 404
    elif source == 'messages':
        messages.mark_messages_read(ref_id, user_id)
    elif source in ('system_announcement', 'job_application'):
        notifications_db.mark_ref_read(user_id, source, ref_id)
    else:
        return jsonify({"success": False, "message": "未知的通知来源"}), 400
    return jsonify({"success": True})


@notifications_bp.route('/api/notifications/clear', methods=['DELETE'])
def clear_read_notifications():
    user_id = request.args.get('user_id', '')
    _, err = messages_self_guard(user_id)
    if err:
        return err
    notifications_db.clear_read_notifications(user_id)
    return jsonify({"success": True})


@notifications_bp.route('/api/notifications/unread', methods=['GET'])
def get_unread_notification_count():
    user_id = request.args.get('user_id', '')
    _, err = messages_self_guard(user_id)
    if err:
        return err
    # 口径与消息中心「未读」页签一致：四个数据源一起数。
    # 此前只数 notifications 表，红点数字比「未读」页签少一截。
    count = notifications_db.get_total_unread_count(user_id)
    return jsonify({"success": True, "count": count})


__all__ = ['notifications_bp']
