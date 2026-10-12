#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T04 数据层契约测试用的探针：在隔离库上跑断言，把结果以 JSON 打到 stdout。

单独成文件而不是内联在测试里的理由：探针脚本里有大量 SQL 字符串，
内联进 Python 测试要层层转义，改一次就得重新数一遍引号。探针只由
test_db_infrastructure.py 以子进程方式调用，不是产品代码。

用法：python db_infrastructure_probe.py <name>；库路径由 YUEXIANG_DB 指定。
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import database


def table_names(conn):
    return [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' "
        "AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall()]


def table_columns(conn):
    return {name: [r[1] for r in conn.execute('PRAGMA table_info(%s)' % name)]
            for name in table_names(conn)}


def table_counts(conn):
    return {name: conn.execute('SELECT COUNT(*) FROM %s' % name).fetchone()[0]
            for name in table_names(conn)}


def probe_tables():
    database.init_db()
    conn = database.get_connection()
    names = table_names(conn)
    conn.close()
    print(json.dumps(names))


def probe_pragmas():
    conn = database.get_connection()
    print(json.dumps({
        'journal': conn.execute('PRAGMA journal_mode').fetchone()[0].lower(),
        'foreign_keys': conn.execute('PRAGMA foreign_keys').fetchone()[0],
        'busy_timeout': conn.execute('PRAGMA busy_timeout').fetchone()[0],
        'row_factory': conn.row_factory.__name__,
    }))
    conn.close()


def probe_seed_counts():
    database.init_db()
    conn = database.get_connection()
    out = {
        'policies_total': len(database.POLICIES_DATA),
        'demo_jobs': len(database.DEMO_JOBS),
    }
    for name in ('users', 'points', 'students', 'certificates', 'policies',
                 'government_policies', 'carousels', 'system_announcements',
                 'discussions', 'farming_products', 'farming_tasks',
                 'job_listings'):
        out[name] = conn.execute('SELECT COUNT(*) FROM %s' % name).fetchone()[0]
    conn.close()
    print(json.dumps(out))


def probe_schema_stable_across_rerun():
    database.init_db()
    conn = database.get_connection()
    before = table_columns(conn)
    conn.close()
    database.init_db()
    conn = database.get_connection()
    after = table_columns(conn)
    conn.close()
    print(json.dumps([before, after]))


def probe_seed_idempotent():
    database.init_db()
    conn = database.get_connection()
    before = table_counts(conn)
    before['demo_job_ids'] = sorted(
        r[0] for r in conn.execute(
            'SELECT id FROM job_listings WHERE is_demo = 1').fetchall())
    before['demo_job_status'] = sorted(
        (r[0], r[1]) for r in conn.execute(
            'SELECT id, review_status FROM job_listings WHERE is_demo = 1'
        ).fetchall())
    conn.close()
    database.init_db()
    conn = database.get_connection()
    after = table_counts(conn)
    after['demo_job_ids'] = sorted(
        r[0] for r in conn.execute(
            'SELECT id FROM job_listings WHERE is_demo = 1').fetchall())
    after['demo_job_status'] = sorted(
        (r[0], r[1]) for r in conn.execute(
            'SELECT id, review_status FROM job_listings WHERE is_demo = 1'
        ).fetchall())
    conn.close()
    print(json.dumps([before, after]))


def probe_review_conclusions_survive_rerun():
    database.init_db()
    conn = database.get_connection()
    demo_id = conn.execute(
        'SELECT id FROM job_listings WHERE is_demo = 1 ORDER BY id LIMIT 1'
    ).fetchone()[0]
    conn.execute('UPDATE job_listings SET review_status = ? WHERE id = ?',
                 ('rejected', demo_id))
    conn.execute(
        'INSERT INTO job_listings '
        '(title, company, salary, requirements, description, location, '
        ' category, enterprise_id, review_status, is_demo) '
        "VALUES ('__t04真实岗位__', '真实公司', '9K', '[]', '真实描述', "
        "'广州', '电商运营', 'enterprise_demo', 'approved', 0)")
    conn.commit()
    real_id = conn.execute(
        "SELECT id FROM job_listings WHERE title = '__t04真实岗位__'").fetchone()[0]
    conn.close()

    database.init_db()

    conn = database.get_connection()
    print(json.dumps({
        'demo_status': conn.execute(
            'SELECT review_status FROM job_listings WHERE id = ?',
            (demo_id,)).fetchone()[0],
        'real_status': conn.execute(
            'SELECT review_status FROM job_listings WHERE id = ?',
            (real_id,)).fetchone()[0],
        'demo_ids': [r[0] for r in conn.execute(
            'SELECT id FROM job_listings WHERE is_demo = 1').fetchall()],
    }))
    conn.close()


def probe_legacy_demo_jobs_cleaned():
    database.init_db()
    conn = database.get_connection()
    conn.execute("INSERT INTO job_listings (title, company, enterprise_id) "
                 "VALUES ('__t04遗留预置__', '假公司', '')")
    conn.commit()
    conn.close()
    database.init_db()
    conn = database.get_connection()
    print(json.dumps(conn.execute(
        "SELECT COUNT(*) FROM job_listings WHERE enterprise_id = ''").fetchone()[0]))
    conn.close()


def probe_demo_job_review_records():
    database.init_db()
    conn = database.get_connection()
    print(json.dumps(conn.execute(
        "SELECT COUNT(*) FROM content_reviews WHERE content_type = 'job'"
    ).fetchone()[0]))
    conn.close()


def probe_override_creates_db():
    conn = database.get_connection()
    conn.close()
    print(json.dumps(os.path.isfile(os.environ['YUEXIANG_DB'])))


PROBES = {
    'tables': probe_tables,
    'pragmas': probe_pragmas,
    'seed_counts': probe_seed_counts,
    'schema_stable': probe_schema_stable_across_rerun,
    'seed_idempotent': probe_seed_idempotent,
    'review_survives': probe_review_conclusions_survive_rerun,
    'legacy_cleaned': probe_legacy_demo_jobs_cleaned,
    'job_reviews': probe_demo_job_review_records,
    'override_db': probe_override_creates_db,
}


if __name__ == '__main__':
    PROBES[sys.argv[1]]()