#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""内容审核域：审核记录的创建、查询与**唯一的状态变更入口**。

T05 从 database.py 按领域切分抽出。原来的 `approve_review` / `reject_review` /
`revoke_review` 三个函数各自直接 UPDATE courses / job_listings / procurements /
models_3d 四张表，等于审核域反向写四个领域。现在收敛为 `set_review_status()`
一个入口：它改自己的 content_reviews，再按内容类型分派到对应领域的窄接口。

分派表是这里唯一的扩展点：新增一种可审核内容，只需加一行
`'新类型': 领域模块.写入函数`，不需要再改任何领域，也不需要再改路由层。
"""

from db_connection import get_connection

# 本模块的数据归属这个能力域。backend/core/permissions.py 的 CAPABILITIES
# 与 tools/check_architecture.py（T02 起按能力表判权）都以此为准：谁 import
# 本模块，谁就必须持 review.manage（读操作受 review.read 管）。
CAPABILITY = 'review'
from db_domains import courses, procurements
from db_domains.employment import set_job_review_status

# 内容类型 -> 该领域的「改我这张表的审核字段」窄接口。
# 每个签名统一为 (content_id, review_status)；没有目标表的类型（如 success_case，
# 其内容在 cases_data.py、可见性完全由 content_reviews.status 决定）不进本表。
REVIEW_TARGET_WRITERS = {
    'course': courses.set_course_review_status,
    'job': set_job_review_status,
    'procurement': procurements.set_procurement_review_status,
    'model_3d': courses.set_model_3d_review_status,
}


def _target_writer(content_type):
    return REVIEW_TARGET_WRITERS.get(content_type)


def create_content_review(content_type, content_id, submitter_id):
    """创建内容审核记录"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO content_reviews (content_type, content_id, submitter_id) VALUES (?, ?, ?)",
        (content_type, content_id, submitter_id))
    review_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return review_id


def get_pending_reviews(content_type=None):
    """获取待审核记录"""
    conn = get_connection()
    if content_type:
        rows = conn.execute(
            "SELECT * FROM content_reviews WHERE status='pending' AND content_type=? ORDER BY created_at DESC",
            (content_type,)).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM content_reviews WHERE status='pending' ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def set_review_status(review_id, status, reviewer_id='', comment=''):
    """审核状态变更的唯一入口。

    先改自己的 content_reviews，再按内容类型分派到对应领域回写 review_status。
    返回 'ok' / 'not_found'（没有这条记录）/ 'unchanged'（状态没变）。

    ⚠️ 通过时必须清掉 review_comment：一条记录可能「先驳回、再撤销、后通过」，
    若不清，已通过的卡片上会残留上一轮的驳回理由，极易被误读为
    「通过了但有驳回意见」（2026-10-08 在 success_case#1 上实测到过）。
    """
    if status not in ('approved', 'rejected', 'pending'):
        raise ValueError('未知的审核状态：%r' % (status,))

    conn = get_connection()
    review = conn.execute("SELECT * FROM content_reviews WHERE id=?", (review_id,)).fetchone()
    if not review:
        conn.close()
        return 'not_found'

    if status == 'pending':
        # 撤销：reviewed_by / review_comment / reviewed_at 一并清空
        conn.execute(
            "UPDATE content_reviews SET status='pending', reviewed_by='', review_comment='', "
            "reviewed_at=NULL WHERE id=?", (review_id,))
    elif status == 'approved':
        conn.execute(
            "UPDATE content_reviews SET status='approved', reviewed_by=?, review_comment='', "
            "reviewed_at=datetime('now','localtime') WHERE id=?",
            (reviewer_id, review_id))
    else:
        conn.execute(
            "UPDATE content_reviews SET status='rejected', reviewed_by=?, review_comment=?, "
            "reviewed_at=datetime('now','localtime') WHERE id=?",
            (reviewer_id, comment, review_id))
    conn.commit()
    conn.close()

    writer = _target_writer(review['content_type'])
    if writer is not None:
        writer(review['content_id'], status)
    return 'ok'


def approve_review(review_id, reviewer_id):
    """审核通过。保留原签名供既有调用方使用，实际转发到 set_review_status。"""
    return set_review_status(review_id, 'approved', reviewer_id=reviewer_id)


def reject_review(review_id, reviewer_id, comment=''):
    """审核拒绝。

    ⚠️ 必须与 approve_review() 对称地回写目标表的 review_status ——
    此前只改 content_reviews，导致岗位被驳回后企业端一直显示「待审核」，
    企业会以为还在排队等审（2026-10-07 修）。
    """
    return set_review_status(review_id, 'rejected', reviewer_id=reviewer_id, comment=comment)


def revoke_review(review_id):
    """撤销审核：approved / rejected 退回 pending，并对称回写目标表。

    返回 'ok' / 'not_found'（没有这条记录）/ 'unchanged'（本来就是 pending）。
    """
    conn = get_connection()
    row = conn.execute("SELECT status FROM content_reviews WHERE id = ?", (review_id,)).fetchone()
    conn.close()
    if not row:
        return 'not_found'
    if row['status'] == 'pending':
        return 'unchanged'
    return set_review_status(review_id, 'pending')


def get_oldest_pending_at():
    """审核域窄接口：最早一条待审核记录的提交时间，没有则 None。"""
    conn = get_connection()
    row = conn.execute(
        "SELECT MIN(created_at) AS t FROM content_reviews WHERE status='pending'").fetchone()
    conn.close()
    return row["t"] if row else None


def get_reviews_by_status(status=None, content_type=None, sort='modified'):
    """按状态取审核记录（status 为空 = 全部）。

    sort：'modified'（默认）按最后修改时间倒序，取最近一次审核动作的
    reviewed_at；没审过、或撤销后 reviewed_at 被清空的，退回 created_at；
    'created' 按提交时间倒序。两者都用 id 兜底拆同秒戳。
    """
    conn = get_connection()
    sql = "SELECT * FROM content_reviews WHERE 1=1"
    params = []
    if status:
        sql += " AND status = ?"
        params.append(status)
    if content_type:
        sql += " AND content_type = ?"
        params.append(content_type)
    if sort == 'created':
        sql += " ORDER BY created_at DESC, id DESC"
    else:
        sql += " ORDER BY COALESCE(reviewed_at, created_at) DESC, id DESC"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def count_reviews_by_status(content_type=None):
    """各状态的审核记录条数（供页签显示数量）。三个 key 恒存在，缺失补 0。"""
    conn = get_connection()
    sql = "SELECT status, COUNT(*) AS n FROM content_reviews"
    params = []
    if content_type:
        sql += " WHERE content_type = ?"
        params.append(content_type)
    sql += " GROUP BY status"
    out = {r["status"]: r["n"] for r in conn.execute(sql, params).fetchall()}
    conn.close()
    for k in ("pending", "approved", "rejected"):
        out.setdefault(k, 0)
    return out


def get_review_by_content(content_type, content_id):
    """获取内容的审核记录"""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM content_reviews WHERE content_type=? AND content_id=? ORDER BY id DESC LIMIT 1",
        (content_type, content_id)).fetchone()
    conn.close()
    return dict(row) if row else None
