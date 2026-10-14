#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""系统公告域：全员公告的读写删。

T05 从 database.py 按领域切分抽出，SQL 语义与返回结构与拆分前逐字节一致。
"""

from db_connection import get_connection

# 本模块的数据归属这个能力域。机械检查（tools/check_architecture.py）与
# backend/core/permissions.py 的 CAPABILITIES 都以此为准：谁 import 本模块，
# 谁就必须持 ${cap}.manage（读操作受 ${cap}.read 管）。
CAPABILITY = 'announcement'


def count_active_system_announcements():
    """公告域窄接口：仍生效的全员公告条数。"""
    conn = get_connection()
    n = conn.execute(
        "SELECT COUNT(*) FROM system_announcements WHERE is_active = 1").fetchone()[0]
    conn.close()
    return n


def count_unread_system_announcements(read_ids):
    """公告域的未读窄接口：仍生效且不在已读集合里的公告条数。

    由通知域的未读总数调用，把「哪些算已读」的判断留给通知域（它拥有 notification_reads），
    本域只回答「现在有哪些生效公告」。
    """
    conn = get_connection()
    rows = conn.execute(
        "SELECT id FROM system_announcements WHERE is_active = 1").fetchall()
    conn.close()
    read = {str(i) for i in (read_ids or [])}
    return sum(1 for r in rows if str(r['id']) not in read)


def get_system_announcements(active_only=True):
    """获取系统公告"""
    conn = get_connection()
    if active_only:
        rows = conn.execute(
            "SELECT * FROM system_announcements WHERE is_active=1 ORDER BY is_pinned DESC, created_at DESC"
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM system_announcements ORDER BY is_pinned DESC, created_at DESC"
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def add_system_announcement(title, content, is_pinned=0, created_by=''):
    """新增系统公告"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO system_announcements (title, content, is_pinned, created_by) VALUES (?, ?, ?, ?)",
        (title, content, is_pinned, created_by))
    conn.commit()
    ann_id = cursor.lastrowid
    conn.close()
    return ann_id

def delete_system_announcement(ann_id):
    """删除系统公告（软删除）"""
    conn = get_connection()
    conn.execute("UPDATE system_announcements SET is_active=0 WHERE id=?", (ann_id,))
    conn.commit()
    conn.close()
    return True


# ==================== 课程 ====================

def get_active_system_announcement_ids():
    """在投的系统公告 id（全局来源，不随用户变化）。"""
    conn = get_connection()
    rows = conn.execute(
        "SELECT id FROM system_announcements WHERE is_active = 1"
    ).fetchall()
    conn.close()
    return [str(r[0]) for r in rows]
