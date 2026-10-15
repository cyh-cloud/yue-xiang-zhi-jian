#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""能力档案的取数窄接口。

T05 把原先挤在就业域 `get_learner_profile()` 里的五段 SQL 拆回各领域的窄接口，
让「就业能力档案域只拼装、不读别人的表」成为事实。每个函数只读自己领域的表。

这些函数的形状是为「拼一个档案」而设计的，因此刻意与各域原有的公开函数不同：
它们返回的是档案字段本身，不是领域对象。
"""

from db_connection import get_connection

# 本模块不拥有任何能力域：它是取数窄接口，数据全部来自下面的域。
CAPABILITY = ''


def get_home_stats():
    """首页 Hero 三个统计数字：服务农户 / 培训课程 / 就业对接。

    三个数字分别来自学员、课程、岗位三个能力域，原先是 public 域自己写三次
    COUNT 直连三张表。现在走 v_home_stats：JOIN 与计数口径只有一份，
    且与「学员端看到的真实条数」同源。本模块是取数窄接口（CAPABILITY = ''），
    跨域取数后交给 public 域下发，与档案三段同构。
    """
    conn = get_connection()
    row = conn.execute(
        "SELECT farmers, courses, jobs FROM v_home_stats").fetchone()
    conn.close()
    return {'farmers': row['farmers'], 'courses': row['courses'], 'jobs': row['jobs']}


def get_profile_basic(user_id):
    """用户域的档案窄接口：学员的基础资料。"""
    conn = get_connection()
    u = conn.execute(
        "SELECT username, name, email, phone, bio, region FROM users WHERE username = ?",
        (user_id,)).fetchone()
    conn.close()
    if not u:
        return {}
    return {
        'username': u['username'], 'name': u['name'] or '',
        'email': u['email'] or '', 'phone': u['phone'] or '',
        'bio': u['bio'] or '', 'region': u['region'] or '',
    }


def get_profile_certificates(user_id):
    """证书域的档案窄接口：学员证书及其完成度。

    只有 status='earned' 才算「已获得」，其余如实带出状态（否则 AI 会把
    「进行中 75%」的证书写成「已获得」，属于事实性错误）。
    """
    conn = get_connection()
    rows = conn.execute(
        "SELECT name, status, progress, date FROM certificates WHERE user_id = ? ORDER BY id",
        (user_id,)).fetchall()
    conn.close()
    return [{
        'name': r['name'], 'status': r['status'],
        'earned': (r['status'] == 'earned'),
        'progress': r['progress'] or 0, 'date': r['date'] or '',
    } for r in rows]


def get_points_balance(user_id):
    """积分域的档案窄接口：只给余额这一个数。"""
    conn = get_connection()
    p = conn.execute("SELECT balance FROM points WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return (p['balance'] or 0) if p else 0


def get_student_progress_for_profile(user_id, name):
    """学员域的档案窄接口：学习方向与进度。

    历史数据里 students.user_id 常为空串，故用姓名兜底匹配。
    """
    conn = get_connection()
    st = conn.execute(
        "SELECT direction, progress FROM students "
        "WHERE user_id = ? OR (name <> '' AND name = ?) LIMIT 1",
        (user_id, name)).fetchone()
    conn.close()
    if not st:
        return None
    return {'direction': st['direction'] or '', 'progress': st['progress'] or 0}


def get_recent_training_results(user_id, limit=10):
    """教学支撑域的档案窄接口：最近的实训成绩。

    ⚠️ score 列 = **教师批改分**（2026-10-07 起语义变更，系统规则分存 content.rule_score）。
    未批改时为 NULL → scored=False，让 AI 说「待老师批改」，
    绝不能把规则分或 0 说成成绩。
    """
    conn = get_connection()
    rows = conn.execute("""
            SELECT a.title, s.score, s.status, s.submitted_at
              FROM assignment_submissions s
              LEFT JOIN assignments a ON s.assignment_id = a.id
             WHERE s.student_id = ?
             ORDER BY s.submitted_at DESC LIMIT ?
    """, (user_id, limit)).fetchall()
    conn.close()
    out = []
    for r in rows:
        score = r['score']
        graded = isinstance(score, int)
        out.append({
            'title': (r['title'] or '实训作业'),
            'score': score if graded else None,
            'scored': graded,
            'status': r['status'] or '',
            'submitted_at': r['submitted_at'] or '',
        })
    return out
