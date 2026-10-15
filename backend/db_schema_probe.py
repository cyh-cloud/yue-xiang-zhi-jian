#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T04 建表契约测试用的探针：在隔离库上跑断言，把结果以 JSON 打到 stdout。

单独成文件而不是内联在测试里的理由：探针脚本里有大量 SQL 字符串，
内联进 Python 测试要层层转义，改一次就得重新数一遍引号。探针只由
test_db_schema.py 以子进程方式调用，不是产品代码。

用法：python db_schema_probe.py <name> [参数]；库路径由 YUEXIANG_DB 指定。
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import db_schema  # noqa: E402
from db_connection import get_connection  # noqa: E402


def init_schema():
    """只建表与补列，不播种、不清库。

    T04 的范围就是 schema 层，所以探针直接调 db_schema.apply_schema()。
    init_schema() 里还留着播种与「DROP 已废弃表」两段（属 T03/T10 的范围），
    其中 `DROP TABLE IF EXISTS success_cases` 会把本票新建的 success_cases 删掉。
    那条 DROP 是 content-into-db 之前的旧结论，T03 删掉 database.py 时自然消失；
    本票不越界去改它，因此在 schema 层单独验证。
    """
    conn = get_connection()
    try:
        db_schema.apply_schema(conn.cursor())
        conn.commit()
    finally:
        conn.close()


def table_names(conn):
    return [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' "
        "AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall()]


def view_names(conn):
    return [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'view' ORDER BY name").fetchall()]


def table_columns(conn):
    return {name: [r[1] for r in conn.execute('PRAGMA table_info(%s)' % name)]
            for name in table_names(conn)}


def table_counts(conn):
    return {name: conn.execute('SELECT COUNT(*) FROM %s' % name).fetchone()[0]
            for name in table_names(conn)}


def probe_tables():
    init_schema()
    conn = get_connection()
    names = table_names(conn)
    conn.close()
    print(json.dumps(names))


def probe_views():
    init_schema()
    conn = get_connection()
    names = view_names(conn)
    conn.close()
    print(json.dumps(names))


def probe_tables_missing_extra():
    init_schema()
    conn = get_connection()
    missing = [name for name, cols in table_columns(conn).items()
               if 'extra' not in cols]
    conn.close()
    print(json.dumps(missing))


def probe_extra_defaults():
    init_schema()
    conn = get_connection()
    out = {}
    for name in table_names(conn):
        for row in conn.execute('PRAGMA table_info(%s)' % name):
            if row[1] == 'extra':
                out[name] = row[4]
    conn.close()
    print(json.dumps(out))


def probe_verified_columns():
    init_schema()
    conn = get_connection()
    out = {name: cols for name, cols in table_columns(conn).items()
           if name in ('farming_tasks', 'pest_entries')}
    conn.close()
    print(json.dumps(out))


def probe_verified_defaults():
    init_schema()
    conn = get_connection()
    out = {}
    for name in ('farming_tasks', 'pest_entries'):
        for row in conn.execute('PRAGMA table_info(%s)' % name):
            if row[1] in ('verified_by', 'verified_at'):
                out['%s.%s' % (name, row[1])] = row[4]
    conn.close()
    print(json.dumps(out))


def probe_idempotent_counts():
    init_schema()
    conn = get_connection()
    before = table_counts(conn)
    conn.close()
    init_schema()
    conn = get_connection()
    after = table_counts(conn)
    conn.close()
    print(json.dumps([before, after]))


def probe_idempotent_counts_thrice():
    snapshots = []
    for _ in range(3):
        init_schema()
        conn = get_connection()
        snapshots.append(table_counts(conn))
        conn.close()
    print(json.dumps(snapshots))


def probe_idempotent_schema():
    init_schema()
    conn = get_connection()
    before = table_columns(conn)
    before_views = view_names(conn)
    conn.close()
    init_schema()
    conn = get_connection()
    after = table_columns(conn)
    after_views = view_names(conn)
    conn.close()
    print(json.dumps([before, after]))
    if before_views != after_views:
        raise SystemExit('视图集合在第二次 init_db() 后变了')


def probe_views_selectable():
    """5 个视图在空库上都要能 SELECT，且 SELECT 不抛异常。"""
    init_schema()
    conn = get_connection()
    try:
        for name in view_names(conn):
            conn.execute('SELECT * FROM %s LIMIT 1' % name).fetchall()
    finally:
        conn.close()
    print(json.dumps(True))


# 灌一套能同时命中 5 个视图的数据。数量刻意保持最小：
# 等价性比的是「同一份数据下两条 SQL 的结果」，不是比大小。
SEED_SQL = [
    "INSERT INTO users (username, password_hash, name, role, email, phone, bio) "
    "VALUES ('ent_probe', 'x', '探测企业', 'enterprise', 'e@x.cn', '139', '企业简介')",
    "INSERT INTO users (username, password_hash, name, role) "
    "VALUES ('stu_probe', 'x', '探测学员', 'student')",
    "INSERT INTO students (id, user_id, name) VALUES ('STU900', 'stu_probe', '探测学员')",
    "INSERT INTO job_listings (title, company, enterprise_id, review_status) "
    "VALUES ('探测岗位A', '探测企业', 'ent_probe', 'approved')",
    "INSERT INTO job_listings (title, company, enterprise_id, review_status) "
    "VALUES ('探测岗位B', '探测企业', 'ent_probe', 'pending')",
    "INSERT INTO job_listings (title, company, enterprise_id, review_status) "
    "VALUES ('别家岗位', '别家', 'other_ent', 'approved')",
    "INSERT INTO job_applications (user_id, job_id) VALUES ('stu_probe', 1)",
    "INSERT INTO resumes (user_id, title, region, education, work_years, "
    "phone, email, self_eval, skills, experience) "
    "VALUES ('stu_probe', '探测意向', '广州', '大专', '2年', '138', 's@x.cn', "
    "'自评', '技能', '[]')",
    "INSERT INTO courses (title, description, teacher_id) "
    "VALUES ('探测课程', 'desc', 'teacher_demo')",
    "INSERT INTO assignments (title, description, direction) "
    "VALUES ('探测作业', 'desc', 'ecommerce')",
    "INSERT INTO assignment_submissions (assignment_id, student_id, content) "
    "VALUES (1, 'STU900', '{}')",
    "INSERT INTO models_3d (title, description, craft_type, file_path, file_name, "
    "file_size, teacher_id, review_status, is_published) "
    "VALUES ('探测模型', 'desc', '广绣', 'uploads/models_3d/p.glb', 'p.glb', 10, "
    "'teacher_demo', 'pending', 0)",
]

# 视图 -> 改写前的直连 SQL。逐行语义必须与视图一致。
EQUIVALENT_SQL = {
    'v_enterprise_applications': """
        SELECT ja.id, ja.user_id, ja.job_id, ja.status, ja.applied_at,
               jl.title as job_title,
               u.name as applicant_name, u.phone as applicant_phone,
               u.email as applicant_email, u.bio as applicant_bio,
               r.title as resume_title, r.region as resume_region,
               r.education as resume_education, r.work_years as resume_work_years,
               r.phone as resume_phone, r.email as resume_email,
               r.self_eval as resume_self_eval, r.skills as resume_skills,
               r.experience as resume_experience, r.updated_at as resume_updated_at
        FROM job_applications ja
        JOIN job_listings jl ON ja.job_id = jl.id
        JOIN users u ON ja.user_id = u.username
        LEFT JOIN resumes r ON r.user_id = ja.user_id
    """,
    'v_enterprise_job_stats': """
        SELECT jl.enterprise_id,
               SUM(CASE WHEN jl.review_status = 'approved' THEN 1 ELSE 0 END) as total_jobs,
               SUM(CASE WHEN COALESCE(jl.review_status, '') != 'approved' THEN 1 ELSE 0 END) as pending_jobs,
               COUNT(ja.id) as total_apps
        FROM job_listings jl
        LEFT JOIN job_applications ja ON ja.job_id = jl.id
        GROUP BY jl.enterprise_id
    """,
    'v_submission_context': """
        SELECT s.id as submission_id, s.assignment_id, s.student_id
        FROM assignment_submissions s
        JOIN assignments a ON a.id = s.assignment_id
    """,
    'v_reviewable_models': "SELECT * FROM models_3d",
}


def probe_view_equivalence():
    init_schema()
    conn = get_connection()
    for stmt in SEED_SQL:
        conn.execute(stmt)
    conn.commit()

    out = {}

    for view, direct in EQUIVALENT_SQL.items():
        view_rows = [tuple(r) for r in conn.execute(
            'SELECT * FROM %s' % view).fetchall()]
        direct_rows = [tuple(r) for r in conn.execute(direct).fetchall()]
        # 视图不背 ORDER BY（原 SQL 的排序在路由层），故按键排序后比对集合。
        # 直连 SQL 只取原路由真正用到的列，因此这里按「共有列」比对：
        # 视图可以比原 SQL 宽（多带几列供路由取用），但不能在共有列上给出不同值。
        view_cols = [d[0] for d in conn.execute(
            'SELECT * FROM %s LIMIT 0' % view).description]
        direct_cols = [d[0] for d in conn.execute(
            'SELECT * FROM (%s) LIMIT 0' % direct).description]
        shared = [c for c in direct_cols if c in view_cols]
        if shared != direct_cols:
            out[view] = {'missing_columns': [c for c in direct_cols
                                             if c not in view_cols]}
            continue
        idx = [view_cols.index(c) for c in shared]
        narrowed = [tuple(row[i] for i in idx) for row in view_rows]
        if sorted(map(repr, narrowed)) != sorted(map(repr, direct_rows)):
            out[view] = {'view': narrowed, 'direct': direct_rows}

    # v_home_stats：三次 COUNT 的合并，逐项比对
    stats = dict(conn.execute('SELECT * FROM v_home_stats').fetchone())
    expected = {
        'farmers': conn.execute('SELECT COUNT(*) FROM students').fetchone()[0],
        'courses': conn.execute('SELECT COUNT(*) FROM courses').fetchone()[0],
        'jobs': conn.execute('SELECT COUNT(*) FROM job_listings').fetchone()[0],
    }
    if stats != expected:
        out['v_home_stats'] = {'view': stats, 'direct': expected}

    conn.close()
    print(json.dumps(out))


def probe_view_columns():
    init_schema()
    conn = get_connection()
    out = {}
    for name in view_names(conn):
        cur = conn.execute('SELECT * FROM %s LIMIT 0' % name)
        out[name] = [d[0] for d in cur.description]
    conn.close()
    print(json.dumps(out))


def probe_upgrade():
    """在现库副本上跑 apply_schema()，逐表比升级前后的行数。

    副本由调用方（测试）准备好，本探针只负责跑升级与比对，不自己拷文件。
    库路径只从 YUEXIANG_DB 读，不接受命令行参数，避免「传了路径却被忽略」。
    """
    # 用数据层唯一的连接工厂读副本（本文件不得出现第二个 sqlite3.connect，
    # 那条约束由 test_db_infrastructure.py 机械检查）。
    before_conn = get_connection()
    before = {name: before_conn.execute('SELECT COUNT(*) FROM %s' % name).fetchone()[0]
              for name in table_names(before_conn)}
    before_views = view_names(before_conn)
    before_conn.close()

    init_schema()

    conn = get_connection()
    after = table_counts(conn)
    lost = {name: {'before': n, 'after': after.get(name)}
            for name, n in before.items() if after.get(name) != n}
    report = {
        'lost': lost,
        'table_count': len(after),
        'views_before': before_views,
        'views_after': view_names(conn),
        'before_total': sum(before.values()),
        'after_total': sum(after.values()),
    }
    conn.close()
    print(json.dumps(report))


PROBES = {
    'tables': probe_tables,
    'views': probe_views,
    'tables_missing_extra': probe_tables_missing_extra,
    'extra_defaults': probe_extra_defaults,
    'verified_columns': probe_verified_columns,
    'verified_defaults': probe_verified_defaults,
    'idempotent_counts': probe_idempotent_counts,
    'idempotent_counts_thrice': probe_idempotent_counts_thrice,
    'idempotent_schema': probe_idempotent_schema,
    'views_selectable': probe_views_selectable,
    'view_equivalence': probe_view_equivalence,
    'view_columns': probe_view_columns,
    'upgrade': probe_upgrade,
}


if __name__ == '__main__':
    PROBES[sys.argv[1]]()
