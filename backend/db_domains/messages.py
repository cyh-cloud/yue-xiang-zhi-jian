#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""消息域：站内私信的收发、会话与已读。

T05 从 database.py 按领域切分抽出，SQL 语义与返回结构与拆分前逐字节一致。
"""

from db_connection import get_connection

# 本模块的数据归属这个能力域。机械检查（tools/check_architecture.py）与
# backend/core/permissions.py 的 CAPABILITIES 都以此为准：谁 import 本模块，
# 谁就必须持 ${cap}.manage（读操作受 ${cap}.read 管）。
CAPABILITY = 'message'


def count_unread_conversations(user_id):
    """消息域的未读窄接口：未读**会话**数。

    按会话数而不是按消息条数：消息中心「互动」条目是一行一个会话，
    按条数会让红点比可见条目多出一截（实测 15 对 9）。口径与 get_inbox 一致。
    由通知域的未读总数显式调用，本域不读 notifications 表。
    """
    conn = get_connection()
    n = conn.execute(
        """SELECT COUNT(*) FROM messages m
           WHERE m.receiver_id = ? AND m.is_read = 0
             AND m.id IN (
                 SELECT MAX(id) FROM messages
                 WHERE sender_id = ? OR receiver_id = ?
                 GROUP BY CASE WHEN sender_id = ? THEN receiver_id ELSE sender_id END
             )""",
        (user_id, user_id, user_id, user_id)
    ).fetchone()[0]
    conn.close()
    return n


def send_message(sender_id, receiver_id, content):
    # messages.id 是 INTEGER PRIMARY KEY AUTOINCREMENT，**不能**塞 uuid 字符串
    # （SQLite 会报 datatype mismatch）。落库后取自增主键返回，供前端轮询去重。
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO messages (sender_id, receiver_id, content) VALUES (?, ?, ?)",
        (sender_id, receiver_id, content)
    )
    mid = cur.lastrowid
    conn.commit()
    conn.close()
    return mid

def get_messages(user1_id, user2_id, limit=50):
    conn = get_connection()
    rows = conn.execute(
        """SELECT * FROM messages
           WHERE (sender_id = ? AND receiver_id = ?) OR (sender_id = ? AND receiver_id = ?)
           ORDER BY created_at DESC LIMIT ?""",
        (user1_id, user2_id, user2_id, user1_id, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in reversed(rows)]

def _resolve_display_names(ids):
    """按「名册名优先、账号名兜底、最后回退裸 id」解析显示名。

    T05：students 与 users 分属两个域，这里分别调它们的窄接口再按原优先级合并，
    不再由本域直接查别人的表。原实现的优先级顺序保持不变。
    """
    from db_domains.students import get_roster_names_by_user_id
    from db_domains.users import get_display_names
    roster = get_roster_names_by_user_id(ids)
    accounts = get_display_names(ids)
    out = {}
    for i in ids:
        if not i:
            out[i] = ''
        elif roster.get(i):
            out[i] = roster[i]
        elif accounts.get(i):
            out[i] = accounts[i]
        else:
            out[i] = i
    return out


def get_inbox(user_id):
    """会话列表（按最近一条消息分组）。

    ⚠️ messages 表的 sender_id / receiver_id 全站是 **username**（与 user_id 红线一致）。
    原实现拿它去 JOIN students.id（名册号 STU001…）必然 JOIN 不上 → 对方名字
    只能显示成裸用户名（student_demo / teacher_demo）。现在按优先级解析：
    名册（students.user_id = username）→ 账号表（users.name）→ 才回退用户名。
    """
    conn = get_connection()
    rows = conn.execute(
        """SELECT m.* FROM messages m
           WHERE m.id IN (
               SELECT MAX(id) FROM messages
               WHERE sender_id = ? OR receiver_id = ?
               GROUP BY CASE WHEN sender_id = ? THEN receiver_id ELSE sender_id END
           )
           ORDER BY m.created_at DESC""",
        (user_id, user_id, user_id)
    ).fetchall()

    # T05 搬迁时漏掉了这一行：names 从未赋值，只要有任意一条私信，
    # /api/messages/inbox 就 NameError 500（收件箱为空时循环不进，所以不暴露）。
    names = _resolve_display_names(
        [r['receiver_id'] if r['sender_id'] == user_id else r['sender_id']
         for r in rows])


    # ⚠️ 下面的循环必须发生在 conn.close() **之前**：_resolve_name 是闭包，
    #   里面还要用同一个 conn 去查 students / users。原先 close 写在循环前，
    #   导致「只要收件箱里有一条消息」就会抛
    #   `ProgrammingError: Cannot operate on a closed database` → /api/messages/inbox 恒 500。
    #   库里没有消息时 rows 为空、闭包不被调用，所以这个 bug 长期不暴露（2026-10-09）。
    result = []
    for r in rows:
        d = dict(r)
        other_id = d['receiver_id'] if d['sender_id'] == user_id else d['sender_id']
        d['other_id'] = other_id
        d['other_name'] = names.get(other_id) or other_id
        d['is_mine'] = d['sender_id'] == user_id
        result.append(d)
    conn.close()
    return result

def get_unread_count(user_id):
    conn = get_connection()
    count = conn.execute(
        "SELECT COUNT(*) FROM messages WHERE receiver_id = ? AND is_read = 0",
        (user_id,)
    ).fetchone()[0]
    conn.close()
    return count

def mark_messages_read(sender_id, receiver_id):
    conn = get_connection()
    conn.execute(
        "UPDATE messages SET is_read = 1 WHERE sender_id = ? AND receiver_id = ? AND is_read = 0",
        (sender_id, receiver_id)
    )
    conn.commit()
    conn.close()


# ==================== 系统通知 ====================

def mark_all_messages_read(user_id):
    """把「别人发给我的」所有私信标为已读（全部已读用）。"""
    conn = get_connection()
    conn.execute(
        "UPDATE messages SET is_read = 1 WHERE receiver_id = ? AND is_read = 0",
        (user_id,)
    )
    conn.commit()
    conn.close()
