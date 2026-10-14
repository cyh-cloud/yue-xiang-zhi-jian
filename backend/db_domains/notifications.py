#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""通知域：系统通知、已读状态与未读总数。

T05 从 database.py 按领域切分抽出，SQL 语义与返回结构与拆分前逐字节一致。
"""

from db_connection import get_connection

# 本模块的数据归属这个能力域。机械检查（tools/check_architecture.py）与
# backend/core/permissions.py 的 CAPABILITIES 都以此为准：谁 import 本模块，
# 谁就必须持 ${cap}.manage（读操作受 ${cap}.read 管）。
CAPABILITY = 'notification'


def create_notification(user_id, ntype, title, content='', link_type='', link_id=None):
    conn = get_connection()
    conn.execute(
        "INSERT INTO notifications (user_id, type, title, content, link_type, link_id) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, ntype, title, content, link_type, link_id)
    )
    conn.commit()
    conn.close()

def create_notification_for_all_students(ntype, title, content='', link_type='', link_id=None):
    """给所有**已关联平台账号**的学员发站内通知。

    ⚠️ notifications.user_id 的语义是全站统一的 username（见全局红线）。
    名册表 students 有自己的 id（STU001…）与可选的 user_id（= username）。
    早期实现误把 students.id 当作收件人写入，导致真实登录学员收不到任何通知
    （2026-10-07 修复）。没有关联账号的名册行直接跳过，不写无人认领的脏行。
    """
    conn = get_connection()
    # T05：收件人清单由学员域的窄接口提供，本域 SQL 只碰 notifications
    from db_domains.students import get_linked_student_user_ids
    recipients = get_linked_student_user_ids()
    for r in recipients:
        conn.execute(
            "INSERT INTO notifications (user_id, type, title, content, link_type, link_id) VALUES (?, ?, ?, ?, ?, ?)",
            (r, ntype, title, content, link_type, link_id)
        )
    conn.commit()
    conn.close()

def get_notifications(user_id, limit=20):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM notifications WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
        (user_id, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_unread_notification_count(user_id):
    conn = get_connection()
    count = conn.execute(
        "SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0",
        (user_id,)
    ).fetchone()[0]
    conn.close()
    return count

def mark_notifications_read(user_id):
    conn = get_connection()
    conn.execute(
        "UPDATE notifications SET is_read = 1 WHERE user_id = ? AND is_read = 0",
        (user_id,)
    )
    conn.commit()
    conn.close()

def clear_read_notifications(user_id):
    conn = get_connection()
    conn.execute(
        "DELETE FROM notifications WHERE user_id = ? AND is_read = 1",
        (user_id,)
    )
    conn.commit()
    conn.close()

# ---- 已读旁路表（system_announcements / job_applications 两个无 is_read 的来源）----

def get_read_refs(user_id, source):
    """取某用户在某来源上已读的 ref_id 列表。"""
    conn = get_connection()
    rows = conn.execute(
        "SELECT ref_id FROM notification_reads WHERE user_id = ? AND source = ?",
        (user_id, source)
    ).fetchall()
    conn.close()
    return [r[0] for r in rows]

def mark_ref_read(user_id, source, ref_id):
    conn = get_connection()
    conn.execute(
        "INSERT OR IGNORE INTO notification_reads (user_id, source, ref_id) VALUES (?, ?, ?)",
        (user_id, source, str(ref_id))
    )
    conn.commit()
    conn.close()

def mark_refs_read(user_id, source, ref_ids):
    """批量标记已读（「全部已读」用）。ref_ids 为空时不做任何写入。"""
    conn = get_connection()
    for rid in ref_ids:
        conn.execute(
            "INSERT OR IGNORE INTO notification_reads (user_id, source, ref_id) VALUES (?, ?, ?)",
            (user_id, source, str(rid))
        )
    conn.commit()
    conn.close()

def clear_read_refs(user_id, source):
    conn = get_connection()
    conn.execute(
        "DELETE FROM notification_reads WHERE user_id = ? AND source = ?",
        (user_id, source)
    )
    conn.commit()
    conn.close()

def get_total_unread_count(user_id):
    """消息中心四个数据源的未读总数。

    红点与「未读」页签都按这个口径，避免出现「红点有数、未读页签是空的」。

    T05 收敛：私信数与投递数不再由本域直接 SQL 数 messages / job_applications，
    改为显式调用消息域与就业域各自的未读计数窄接口；本域只负责相加。
    """
    conn = get_connection()
    notif = conn.execute(
        "SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0",
        (user_id,)
    ).fetchone()[0]
    # 延迟导入：消息域与就业域都不依赖本域，但为保持「领域模块只在调用点建立依赖」，
    # 这里用函数内导入，避免顶层把三个域绑成一条导入链。
    from db_domains.employment import count_unread_job_applications
    from db_domains.messages import count_unread_conversations

    msgs = count_unread_conversations(user_id)
    apps = count_unread_job_applications(user_id)
    conn.close()

    # 系统公告的未读数由公告域按「哪些还没被标已读」算，本域只做减法
    from db_domains.announcements import count_unread_system_announcements
    read = set(get_read_refs(user_id, 'system_announcement'))
    anns = count_unread_system_announcements(read)
    return notif + msgs + apps + anns


# ==================== 就业 ====================
