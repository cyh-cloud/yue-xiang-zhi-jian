#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""教学支撑域：公告、实训作业、批改、学情分析。

T05 从 database.py 按领域切分抽出，SQL 语义与返回结构与拆分前逐字节一致。
"""

import json
from db_connection import get_connection


def create_announcement(title, content, category='通知', pinned=0):
    conn = get_connection()
    cursor = conn.execute("INSERT INTO announcements (title, content, category, pinned) VALUES (?, ?, ?, ?)",
                          (title, content, category, pinned))
    conn.commit()
    aid = cursor.lastrowid
    conn.close()
    return aid

def get_announcements(limit=50):
    conn = get_connection()
    rows = conn.execute("SELECT * FROM announcements ORDER BY pinned DESC, created_at DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def delete_announcement(ann_id):
    conn = get_connection()
    result = conn.execute("DELETE FROM announcements WHERE id = ?", (ann_id,))
    conn.commit()
    deleted = result.rowcount > 0
    conn.close()
    return deleted


# ==================== 实训批改（原「作业管理」） ====================
# 2026-10-07 用户拍板：**「发布作业」整块下架**。
# ⚠️ `assignments` 表**必须保留** —— 它现在的唯一用途是承载三种电商实训的题目
#    （`TRAINING_TITLE_FMTS` 用 title 前缀反推 kind，见下方「直播带货实训（EC7）」段），
#    `get_or_create_*_assignment` / `grade_submission` 都依赖它。
#    删掉的只是「教师手动建作业/看作业」这条链路：
#    create_assignment / get_assignments / get_assignment / submit_assignment /
#    get_student_submissions（经核查前端零调用）。

def grade_submission(submission_id, score, feedback=''):
    conn = get_connection()
    conn.execute("UPDATE assignment_submissions SET score = ?, feedback = ?, status = 'graded', graded_at = datetime('now','localtime') WHERE id = ?",
                 (score, feedback, submission_id))
    conn.commit()
    updated = conn.execute("SELECT changes()").fetchone()[0] > 0
    conn.close()
    return updated


# ---- 直播带货实训（EC7）：复用既有作业链路，不新建数据表 --------------------
# 设计取舍：一次直播实训 = 一条 assignment_submissions。
#  · 每个作物复用一个实训题目，避免每提交一次就往教师端塞一条新作业；
#  · assignment_submissions 有 UNIQUE(assignment_id, student_id)，故同一学员同一作物
#    只保留**最新一次**提交，历史尝试次数记在 content 的 JSON 里（attempts）。
LIVE_ASSIGNMENT_DIRECTION = 'ecommerce'
LIVE_ASSIGNMENT_TITLE_FMT = '直播带货实训 · {}'

# 2026-10-05 文案 / 客服闭环：三种实训共用同一套题目/提交机制，只用 title 前缀区分 kind。
# title 前缀即 records 接口的过滤依据 —— 改前缀必须同步改 app.py 的 kind 校验与前端。
TRAINING_TITLE_FMTS = {
    'live': LIVE_ASSIGNMENT_TITLE_FMT,
    'copy': '商品文案实训 · {}',
    'cs':   '客服对练实训 · {}',
}
TRAINING_DESCRIPTIONS = {
    'live': '{product} 直播带货实训：提交学员自己的话术稿，并附朗读实录分析。'
            '指标由规则分析给出、可复现；教师可复核。',
    'copy': '{product} 商品文案实训：AI 只出初稿，学员改写后提交自己的版本。'
            '具体认证/数据/价格必须用真实信息，不得编造；教师可复核。',
    'cs':   '{product} 客服对练实训：学员扮演客服逐轮回复模拟客户，提交完整对话记录'
            '与规则评分明细；教师可复核。',
}

def get_or_create_training_assignment(product, kind='live'):
    """按 kind + 作物取/建实训题目，返回 assignment_id。"""
    fmt = TRAINING_TITLE_FMTS.get(kind)
    if not fmt:
        raise ValueError('unknown training kind: %r' % kind)
    title = fmt.format(product)
    conn = get_connection()
    row = conn.execute(
        "SELECT id FROM assignments WHERE title = ? AND direction = ? LIMIT 1",
        (title, LIVE_ASSIGNMENT_DIRECTION)
    ).fetchone()
    if row:
        conn.close()
        return row['id']
    cur = conn.execute(
        "INSERT INTO assignments (title, description, direction, deadline, total_score) "
        "VALUES (?, ?, ?, '', 100)",
        (title, TRAINING_DESCRIPTIONS.get(kind, '').format(product=product),
         LIVE_ASSIGNMENT_DIRECTION)
    )
    conn.commit()
    aid = cur.lastrowid
    conn.close()
    return aid

def get_or_create_live_assignment(product):
    """按作物取/建实训题目，返回 assignment_id。"""
    return get_or_create_training_assignment(product, 'live')

def save_live_training(assignment_id, student_id, payload, rule_score=None):
    """写入/更新一次实训提交。

    ⚠️ score 列语义 = **教师批改分**，只由 grade_submission() 写。
       系统规则分存进 content 的 rule_score，**不再写进 score**。
       2026-10-07 前这里是 `SET score = ?` 直接写规则分，造成三个后果：
         ① 教师端出现「85 分 + 待批改」「0 分 + 待批改」这种自相矛盾的行；
         ② 教师批改后学员重新提交，教师给的分被规则分**静默覆盖**；
         ③ 评语被清空、graded_at 归零，而没人告诉教师批改结果已经失效。
       现在重新提交的规则：
         · 从未批改过 → status 保持 'submitted'（待批改），score/feedback 本来就是空；
         · 已批改过   → **保留** score / feedback / graded_at，status 改 'resubmitted'
                        （已重新提交·待复核），教师端会醒目提示。
    返回 (提交 id, 累计尝试次数)。
    """
    conn = get_connection()
    row = conn.execute(
        "SELECT id, content, status, score, feedback FROM assignment_submissions "
        "WHERE assignment_id = ? AND student_id = ?",
        (assignment_id, student_id)
    ).fetchone()
    attempts = 1
    if row:
        try:
            attempts = int(json.loads(row['content'] or '{}').get('attempts', 0)) + 1
        except Exception:
            attempts = 1
    payload = dict(payload or {})
    payload['attempts'] = attempts
    try:
        payload['rule_score'] = int(rule_score or 0)
    except (TypeError, ValueError):
        payload['rule_score'] = 0
    content_json = json.dumps(payload, ensure_ascii=False)
    if row:
        prev_status = (row['status'] or 'submitted')
        # 判据用「有没有教师批改结果」而不是 status 字符串：
        # 历史数据里 status 可能被老逻辑重置过，而 score 一旦有值就是教师给的。
        already_graded = (row['score'] is not None) or (prev_status == 'graded')
        new_status = 'resubmitted' if already_graded else 'submitted'
        conn.execute(
            "UPDATE assignment_submissions SET content = ?, status = ?, "
            "submitted_at = datetime('now','localtime') WHERE id = ?",
            (content_json, new_status, row['id'])
        )
        conn.commit()
        sid = row['id']
    else:
        cur = conn.execute(
            "INSERT INTO assignment_submissions (assignment_id, student_id, content, score, status) "
            "VALUES (?, ?, ?, NULL, 'submitted')",
            (assignment_id, student_id, content_json)
        )
        conn.commit()
        sid = cur.lastrowid
    conn.close()
    return sid, attempts

def get_trainings(student_id, kind=None):
    """取某学员的实训记录（每个作物各一条）。

    kind 为 None 时返回全部电商实训（三种混合）；否则按 title 前缀过滤。
    """
    conn = get_connection()
    if kind and kind in TRAINING_TITLE_FMTS:
        rows = conn.execute(
            "SELECT s.*, a.title AS assignment_title FROM assignment_submissions s "
            "LEFT JOIN assignments a ON s.assignment_id = a.id "
            "WHERE s.student_id = ? AND a.direction = ? AND a.title LIKE ? "
            "ORDER BY s.submitted_at DESC",
            (student_id, LIVE_ASSIGNMENT_DIRECTION,
             TRAINING_TITLE_FMTS[kind].format('%'))
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT s.*, a.title AS assignment_title FROM assignment_submissions s "
            "LEFT JOIN assignments a ON s.assignment_id = a.id "
            "WHERE s.student_id = ? AND a.direction = ? ORDER BY s.submitted_at DESC",
            (student_id, LIVE_ASSIGNMENT_DIRECTION)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_live_trainings(student_id):
    """取某学员的全部直播实训记录（每个作物各一条）。"""
    return get_trainings(student_id, 'live')

def get_all_trainings():
    """教师端：全部学员的电商实训提交（按提交时间倒序）。

    复用既有作业链路（assignments + assignment_submissions），
    kind 由作业标题前缀反推（见 TRAINING_TITLE_FMTS），不改表结构。

    另带出**名册姓名**：assignment_submissions.student_id 存的是 username（如 student_demo），
    教师端直接显示登录名不好认人（2026-10-07）。
    ⚠️ 姓名用**标量子查询**取，不用 LEFT JOIN —— 名册允许同一 user_id 出现多行时
       JOIN 会让同一条提交重复出现。
    """
    conn = get_connection()
    rows = conn.execute(
        "SELECT s.*, a.title AS assignment_title "
        "FROM assignment_submissions s "
        "LEFT JOIN assignments a ON s.assignment_id = a.id "
        "WHERE a.direction = ? ORDER BY s.submitted_at DESC"
        , (LIVE_ASSIGNMENT_DIRECTION,)
    ).fetchall()
    conn.close()
    # T05：名册姓名由学员域窄接口补齐（原先是标量子查询，改成批量一次取回）
    from db_domains.students import get_roster_names_by_user_id
    roster_names = get_roster_names_by_user_id([r['student_id'] for r in rows])
    out = []
    for r in rows:
        item = dict(r)
        item['student_name'] = roster_names.get(r['student_id']) or ''
        title = item.get('assignment_title') or ''
        item['kind'] = ''
        for k, fmt in TRAINING_TITLE_FMTS.items():
            if title.startswith(fmt.format('')):
                item['kind'] = k
                break
        out.append(item)
    return out


# ==================== 学情分析 ====================

def get_roster_completion():
    """名册每位学员的「证书真实完成度」。

    口径（2026-10-07 用户拍板：学情分析 / AI 教学报告 / 仪表板统计不再使用
    students.progress 这个**手填**字段）：
      · 完成度 = 该学员名下 certificates.progress 的平均值（0-100 整数）；
      · 没有任何证书记录 → completion = 0 且 has_cert_data = 0
        （统计里单独说明「暂无证书记录」，不冒充「0% 完成」）；
      · 证书按 user_id（= username）归属，未关联账号的名册行必然没有证书记录。
    """
    # T05：名册行与证书进度分别向学员域、证书域取，本域 SQL 只碰 assignments
    from db_domains.certificates import get_cert_progress_for
    from db_domains.students import get_roster_rows_for_completion
    rows = get_roster_rows_for_completion()
    out = []
    for r in rows:
        uid = r['user_id'] or ''
        certs = get_cert_progress_for(uid) if uid else []
        earned = sum(1 for c in certs if c['status'] == 'earned')
        has_data = len(certs) > 0
        completion = int(round(sum((c['progress'] or 0) for c in certs) / len(certs))) if has_data else 0
        out.append({
            'id': r['id'], 'name': r['name'], 'direction': r['direction'] or '未分类',
            'user_id': uid, 'status': r['status'],
            'has_account': bool(uid), 'has_cert_data': has_data,
            'cert_total': len(certs), 'cert_earned': earned,
            'completion': completion,
        })
    return out

def get_analytics_data():
    """学情分析数据 —— 口径：**证书真实完成度**（见 get_roster_completion）。

    2026-10-07 修正：原实现直接聚合 students.progress（教师手填、学员端没有任何
    入口会更新它），画出来的「进度分布」与学员真实学习情况无关。
    """
    roster = get_roster_completion()
    ranges = [(0, 20, '0-20%'), (21, 40, '21-40%'), (41, 60, '41-60%'), (61, 80, '61-80%'), (81, 100, '81-100%')]
    progress_dist = []
    for low, high, label in ranges:
        count = sum(1 for r in roster if r['has_cert_data'] and low <= r['completion'] <= high)
        progress_dist.append({'label': label, 'count': count})

    no_cert = [r for r in roster if not r['has_cert_data']]

    by_dir = {}
    for r in roster:
        by_dir.setdefault(r['direction'], []).append(r)
    direction_dist = [{'direction': d, 'count': len(v)} for d, v in by_dir.items()]
    direction_progress = [{
        'direction': d,
        'student_count': len(v),
        'avg_progress': round(sum(x['completion'] for x in v) / len(v), 1),
        'cert_earned': sum(x['cert_earned'] for x in v),
        'no_cert_count': sum(1 for x in v if not x['has_cert_data']),
    } for d, v in by_dir.items()]

    return {
        'basis': 'certificates',
        'basis_label': '证书真实完成度（学员名下证书进度的平均值）',
        'roster_count': len(roster),
        'no_cert_count': len(no_cert),
        'progress_distribution': progress_dist,
        'direction_distribution': direction_dist,
        'direction_progress': direction_progress
    }


# ==================== 消息系统 ====================


def get_dashboard_stats():
    """获取教师仪表板统计（口径：教师名册表 students + 证书真实完成度）。

    2026-10-07 修正（两处）：
    ① 原实现把 certificates **全表**（含教师本人等非学员的证书）当作「学员已获证书」，
       现改为只统计名册中**已关联平台账号**（students.user_id = username）的学员证书；
       完成率 = 名册中至少获得 1 张证书的学员占比。
    ② avg_score（界面文案「平均进度」）原取 students.progress 的平均值 —— 那是**手填**
       字段，学员端没有任何入口会更新它。现改用证书真实完成度（见 get_roster_completion）。
    """
    roster = get_roster_completion()
    total = len(roster)
    earned = sum(r['cert_earned'] for r in roster)
    with_cert = sum(1 for r in roster if r['cert_earned'] > 0)
    with_data = [r for r in roster if r['has_cert_data']]
    avg_completion = (sum(r['completion'] for r in with_data) / len(with_data)) if with_data else 0
    return {
        "total_students": total,
        "certificates_earned": earned,
        "completion_rate": int(with_cert / total * 100) if total > 0 else 0,
        "avg_score": int(round(avg_completion)),
        "no_cert_count": total - len(with_data)
    }
