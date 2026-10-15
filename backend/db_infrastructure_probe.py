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

from db_connection import get_connection
from db_init import init_db


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
    init_db()
    conn = get_connection()
    names = table_names(conn)
    conn.close()
    print(json.dumps(names))


def probe_pragmas():
    conn = get_connection()
    print(json.dumps({
        'journal': conn.execute('PRAGMA journal_mode').fetchone()[0].lower(),
        'foreign_keys': conn.execute('PRAGMA foreign_keys').fetchone()[0],
        'busy_timeout': conn.execute('PRAGMA busy_timeout').fetchone()[0],
        'row_factory': conn.row_factory.__name__,
    }))
    conn.close()


def probe_seed_counts():
    init_db()
    conn = get_connection()
    out = {
        'demo_accounts': 6,
    }
    for name in ('users', 'points', 'students', 'certificates', 'policies',
                 'government_policies', 'carousels', 'system_announcements',
                 'discussions', 'farming_products', 'farming_tasks',
                 'job_listings', 'pest_entries', 'recruitments', 'success_cases',
                 'crafts', 'dialects'):
        out[name] = conn.execute('SELECT COUNT(*) FROM %s' % name).fetchone()[0]
    conn.close()
    print(json.dumps(out))


def probe_schema_stable_across_rerun():
    init_db()
    conn = get_connection()
    before = table_columns(conn)
    conn.close()
    init_db()
    conn = get_connection()
    after = table_columns(conn)
    conn.close()
    print(json.dumps([before, after]))


def probe_seed_idempotent():
    init_db()
    conn = get_connection()
    before = table_counts(conn)
    conn.close()
    init_db()
    conn = get_connection()
    after = table_counts(conn)
    conn.close()
    print(json.dumps([before, after]))


def probe_legacy_demo_jobs_cleaned():
    init_db()
    conn = get_connection()
    conn.execute("INSERT INTO job_listings (title, company, enterprise_id) "
                 "VALUES ('__t04遗留预置__', '假公司', '')")
    conn.commit()
    conn.close()
    init_db()
    conn = get_connection()
    print(json.dumps(conn.execute(
        "SELECT COUNT(*) FROM job_listings WHERE enterprise_id = ''").fetchone()[0]))
    conn.close()


def probe_override_creates_db():
    conn = get_connection()
    conn.close()
    print(json.dumps(os.path.isfile(os.environ['YUEXIANG_DB'])))


PROBES = {
    'tables': probe_tables,
    'pragmas': probe_pragmas,
    'seed_counts': probe_seed_counts,
    'schema_stable': probe_schema_stable_across_rerun,
    'seed_idempotent': probe_seed_idempotent,
    'legacy_cleaned': probe_legacy_demo_jobs_cleaned,
    'override_db': probe_override_creates_db,
}


if __name__ == '__main__':
    PROBES[sys.argv[1]]()
