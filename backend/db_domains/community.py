#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""社区域：讨论帖与评论。

T05 从 database.py 按领域切分抽出，SQL 语义与返回结构与拆分前逐字节一致。
"""

from db_connection import get_connection


def _attach_author_names(rows):
    """给评论/讨论行补上作者显示名。

    T05：原先 JOIN users 取 name，现在改为批量查一次 users 域的展示窄接口，
    让本域的 SQL 只碰 comments / discussions。
    """
    from db_domains.users import get_display_names
    names = get_display_names([r['user_id'] for r in rows])
    for r in rows:
        r['user_name'] = names.get(r['user_id']) or r['user_id']
    return rows


def add_comment(target_type, target_id, user_id, content):
    """添加评论"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO comments (target_type, target_id, user_id, content) VALUES (?, ?, ?, ?)",
        (target_type, target_id, user_id, content))
    conn.commit()
    comment_id = cursor.lastrowid
    # 更新讨论区评论计数
    if target_type == 'discussion':
        conn.execute("UPDATE discussions SET comment_count = comment_count + 1 WHERE id = ?", (target_id,))
        conn.commit()
    conn.close()
    return comment_id

def get_comments(target_type, target_id):
    """获取评论列表"""
    conn = get_connection()
    rows = conn.execute(
        """SELECT c.*
           FROM comments c
           WHERE c.target_type = ? AND c.target_id = ? AND c.is_deleted = 0
           ORDER BY c.created_at ASC""",
        (target_type, target_id)).fetchall()
    conn.close()
    return _attach_author_names([dict(r) for r in rows])

def soft_delete_comment(comment_id, deleted_by=''):
    """软删除评论"""
    conn = get_connection()
    conn.execute("UPDATE comments SET is_deleted=1, deleted_by=? WHERE id=?", (deleted_by, comment_id))
    conn.commit()
    conn.close()
    return True


# ==================== 讨论区 ====================

def create_discussion(title, content, category, user_id):
    """创建讨论帖"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO discussions (title, content, category, user_id) VALUES (?, ?, ?, ?)",
        (title, content, category, user_id))
    conn.commit()
    disc_id = cursor.lastrowid
    conn.close()
    return disc_id

def get_discussions(category=None, page=1, page_size=20):
    """获取讨论区列表（分页）"""
    conn = get_connection()
    query = "SELECT d.* FROM discussions d WHERE d.is_deleted = 0"
    params = []
    if category:
        query += " AND d.category = ?"
        params.append(category)
    query += " ORDER BY d.is_pinned DESC, d.created_at DESC LIMIT ? OFFSET ?"
    params.extend([page_size, (page - 1) * page_size])
    rows = conn.execute(query, params).fetchall()
    total = conn.execute(
        "SELECT COUNT(*) FROM discussions WHERE is_deleted = 0" +
        (f" AND category = ?" if category else ""),
        (category,) if category else ()).fetchone()[0]
    conn.close()
    return _attach_author_names([dict(r) for r in rows]), total

def get_discussion(disc_id):
    """获取讨论详情"""
    conn = get_connection()
    conn.execute("UPDATE discussions SET view_count = view_count + 1 WHERE id = ?", (disc_id,))
    row = conn.execute(
        "SELECT d.* FROM discussions d WHERE d.id = ?",
        (disc_id,)).fetchone()
    conn.commit()
    conn.close()
    return _attach_author_names([dict(row)])[0] if row else None

def soft_delete_discussion(disc_id):
    """软删除讨论帖"""
    conn = get_connection()
    conn.execute("UPDATE discussions SET is_deleted = 1 WHERE id = ?", (disc_id,))
    conn.commit()
    conn.close()
    return True


# ==================== 农产品求购 ====================
