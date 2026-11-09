#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""社区域：讨论帖与评论。

T05 从 database.py 按领域切分抽出，SQL 语义与返回结构与拆分前逐字节一致。
"""

from db_connection import get_connection

# 本模块的数据归属这个能力域。backend/core/permissions.py 的 CAPABILITIES
# 与 tools/check_architecture.py（T02 起按能力表判权）都以此为准：谁 import
# 本模块，谁就必须持 community.manage（读操作受 community.read 管）。
CAPABILITY = 'community'


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


def add_comment(target_type, target_id, user_id, content, moderation_status='published',
                matched_words=''):
    """添加评论。

    命中敏感词的评论以 pending 入库，**不**增加所属讨论帖的评论数 ——
    否则公开页面会显示「5 条评论」却只列出 3 条，用户会以为丢数据。
    审核通过时再补计（见 approve_comment）。
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO comments (target_type, target_id, user_id, content, "
        "moderation_status, matched_words) VALUES (?, ?, ?, ?, ?, ?)",
        (target_type, target_id, user_id, content, moderation_status, matched_words))
    conn.commit()
    comment_id = cursor.lastrowid
    if target_type == 'discussion' and moderation_status == 'published':
        conn.execute("UPDATE discussions SET comment_count = comment_count + 1 WHERE id = ?", (target_id,))
        conn.commit()
    conn.close()
    return comment_id

def get_comments(target_type, target_id):
    """获取评论列表（只含审核通过的）"""
    conn = get_connection()
    rows = conn.execute(
        """SELECT c.*
           FROM comments c
           WHERE c.target_type = ? AND c.target_id = ? AND c.is_deleted = 0
             AND c.moderation_status = 'published'
           ORDER BY c.created_at ASC""",
        (target_type, target_id)).fetchall()
    conn.close()
    return _attach_author_names([dict(r) for r in rows])


def get_moderation_comments(limit=200):
    """超管内容监管用：未删除评论及所属讨论帖标题。"""
    conn = get_connection()
    rows = conn.execute(
        """SELECT c.*, d.title AS target_title
           FROM comments c
           LEFT JOIN discussions d
             ON c.target_type = 'discussion' AND c.target_id = d.id
           WHERE c.is_deleted = 0 AND c.moderation_status = 'published'
           ORDER BY c.created_at DESC, c.id DESC
           LIMIT ?""",
        (max(1, min(int(limit), 500)),)).fetchall()
    conn.close()
    return _attach_author_names([dict(r) for r in rows])


def get_pending_comments(limit=200):
    """待人工审核的评论（命中敏感词，尚未公开）。"""
    conn = get_connection()
    rows = conn.execute(
        """SELECT c.*, d.title AS target_title
           FROM comments c
           LEFT JOIN discussions d
             ON c.target_type = 'discussion' AND c.target_id = d.id
           WHERE c.is_deleted = 0 AND c.moderation_status = 'pending'
           ORDER BY c.created_at ASC, c.id ASC
           LIMIT ?""",
        (max(1, min(int(limit), 500)),)).fetchall()
    conn.close()
    return _attach_author_names([dict(r) for r in rows])


def soft_delete_comment(comment_id, deleted_by=''):
    """软删除评论，并同步所属讨论帖的评论数。

    返回是否真的从公开读路径删掉了一行。重复删除与不存在都返回 False，
    让路由层可以回 404，而不是把没有发生的操作报成成功。
    """
    conn = get_connection()
    row = conn.execute(
        "SELECT target_type, target_id, is_deleted, moderation_status "
        "FROM comments WHERE id=?",
        (comment_id,)).fetchone()
    if row is None or row['is_deleted']:
        conn.close()
        return False
    cur = conn.execute(
        "UPDATE comments SET is_deleted=1, deleted_by=? "
        "WHERE id=? AND is_deleted=0",
        (deleted_by, comment_id))
    # 只有「已在公开页计数」的评论才需要回减：pending 评论入库时没计过数，
    # 这里若无条件减一，会把其他评论数吃掉。
    if row['target_type'] == 'discussion' and row['moderation_status'] == 'published':
        conn.execute(
            "UPDATE discussions SET comment_count = "
            "CASE WHEN comment_count > 0 THEN comment_count - 1 ELSE 0 END "
            "WHERE id=?",
            (row['target_id'],))
    conn.commit()
    deleted = cur.rowcount > 0
    conn.close()
    return deleted


# ==================== 讨论区 ====================

def create_discussion(title, content, category, user_id, moderation_status='published',
                      matched_words=''):
    """创建讨论帖。命中敏感词时以 pending 入库，不进公开列表。"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO discussions (title, content, category, user_id, "
        "moderation_status, matched_words) VALUES (?, ?, ?, ?, ?, ?)",
        (title, content, category, user_id, moderation_status, matched_words))
    conn.commit()
    disc_id = cursor.lastrowid
    conn.close()
    return disc_id

def get_discussions(category=None, page=1, page_size=20):
    """获取讨论区列表（分页，只含审核通过的）"""
    conn = get_connection()
    query = ("SELECT d.* FROM discussions d WHERE d.is_deleted = 0 "
             "AND d.moderation_status = 'published'")
    params = []
    if category:
        query += " AND d.category = ?"
        params.append(category)
    query += " ORDER BY d.is_pinned DESC, d.created_at DESC LIMIT ? OFFSET ?"
    params.extend([page_size, (page - 1) * page_size])
    rows = conn.execute(query, params).fetchall()
    count_sql = ("SELECT COUNT(*) FROM discussions WHERE is_deleted = 0 "
                 "AND moderation_status = 'published'")
    if category:
        count_sql += " AND category = ?"
    total = conn.execute(count_sql, (category,) if category else ()).fetchone()[0]
    conn.close()
    return _attach_author_names([dict(r) for r in rows]), total

def get_discussion(disc_id):
    """获取讨论详情。

    只返回审核通过的帖子：待审与拒审的必须彻底不可见，否则敏感内容虽然不在
    列表里，拿到 id 仍能直链打开，等于没审。
    ⚠️ 刻意**不**过滤 is_deleted：软删除后详情仍可读是拆分前就有的对外契约
    （e2e 有用例锁着），本次不动它。
    """
    conn = get_connection()
    row = conn.execute(
        "SELECT d.* FROM discussions d WHERE d.id = ? "
        "AND d.moderation_status = 'published'",
        (disc_id,)).fetchone()
    if row:
        conn.execute("UPDATE discussions SET view_count = view_count + 1 WHERE id = ?",
                     (disc_id,))
        conn.commit()
    conn.close()
    return _attach_author_names([dict(row)])[0] if row else None

def get_pending_discussions(limit=200):
    """待人工审核的讨论帖（命中敏感词，尚未公开）。"""
    conn = get_connection()
    rows = conn.execute(
        "SELECT d.* FROM discussions d WHERE d.is_deleted = 0 "
        "AND d.moderation_status = 'pending' "
        "ORDER BY d.created_at ASC, d.id ASC LIMIT ?",
        (max(1, min(int(limit), 500)),)).fetchall()
    conn.close()
    return _attach_author_names([dict(r) for r in rows])


def _set_moderation(table, item_id, status, reviewer, from_status='pending'):
    """把一条内容的审核状态从 from_status 改成 status，返回是否真的改了。"""
    conn = get_connection()
    cur = conn.execute(
        "UPDATE %s SET moderation_status = ?, moderated_by = ?, "
        "moderated_at = datetime('now','localtime') "
        "WHERE id = ? AND moderation_status = ?" % table,
        (status, reviewer or '', item_id, from_status))
    conn.commit()
    changed = cur.rowcount > 0
    conn.close()
    return changed


def approve_discussion(disc_id, reviewer=''):
    return _set_moderation('discussions', disc_id, 'published', reviewer)


def reject_discussion(disc_id, reviewer=''):
    return _set_moderation('discussions', disc_id, 'rejected', reviewer)


def approve_comment(comment_id, reviewer=''):
    """通过评论审核。**通过时才补计**所属讨论帖的评论数（入库时没计）。"""
    conn = get_connection()
    row = conn.execute(
        "SELECT target_type, target_id FROM comments WHERE id = ? "
        "AND moderation_status = 'pending' AND is_deleted = 0",
        (comment_id,)).fetchone()
    if row is None:
        conn.close()
        return False
    cur = conn.execute(
        "UPDATE comments SET moderation_status = 'published', moderated_by = ?, "
        "moderated_at = datetime('now','localtime') "
        "WHERE id = ? AND moderation_status = 'pending'",
        (reviewer or '', comment_id))
    conn.commit()
    changed = cur.rowcount > 0
    if changed and row['target_type'] == 'discussion':
        conn.execute(
            "UPDATE discussions SET comment_count = comment_count + 1 "
            "WHERE id = ? AND is_deleted = 0", (row['target_id'],))
        conn.commit()
    conn.close()
    return changed


def reject_comment(comment_id, reviewer=''):
    return _set_moderation('comments', comment_id, 'rejected', reviewer)


def soft_delete_discussion(disc_id):
    """软删除讨论帖。返回是否真的删掉了一行。"""
    conn = get_connection()
    cur = conn.execute(
        "UPDATE discussions SET is_deleted = 1 WHERE id = ? AND is_deleted = 0",
        (disc_id,))
    conn.commit()
    deleted = cur.rowcount > 0
    conn.close()
    return deleted


# ==================== 农产品求购 ====================
