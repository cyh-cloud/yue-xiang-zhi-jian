#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T05 内容迁移契约测试用的探针：在隔离库上跑迁移并把结果以 JSON 打到 stdout。

单独成文件而不是内联在测试里的理由：探针里有大量「代码内容 vs 库里行」的逐字段
比对，内联进 Python 测试要层层转义，改一次就得重新数一遍引号。探针只由
test_content_migration.py 以子进程方式调用，不是产品代码。

T10 之后灌库半边已随代码内容一起删除，本探针只剩三件事：脏数据清理、幂等、
基线库的接口输出。库路径由 YUEXIANG_DB 指定。

用法：python migration_probe.py <name>
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'backend'))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _load():
    import importlib.util
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        'migrations', '0001_content_to_db.py')
    spec = importlib.util.spec_from_file_location('_content_migration', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def probe_idempotent():
    """重复执行：第二次跳过，且全库一行不变。"""
    import sqlite3

    migration = _load()
    path = os.environ['YUEXIANG_DB']
    SQL = ("SELECT name FROM sqlite_master WHERE type='table' "
           "AND name NOT LIKE 'sqlite_%' ORDER BY name")

    def snap():
        conn = sqlite3.connect(path)
        out = {}
        for (name,) in conn.execute(SQL):
            out[name] = sorted(repr(r) for r in conn.execute('SELECT * FROM %s' % name))
        conn.close()
        return out

    first = migration.migrate(path)
    before = snap()
    second = migration.migrate(path)
    after = snap()
    forced = migration.migrate(path, force=True)
    after_force = snap()
    return {
        'first_ran': first is not None,
        'second_skipped': second is None,
        'second_changes': sorted(t for t in before if before[t] != after[t]),
        'force_changes': sorted(t for t in after if after[t] != after_force[t]),
        'forced_cleaned': [len(forced['cleaned_points']), len(forced['cleaned_messages'])],
    }


def probe_cleanup():
    """脏数据清理：两处都清掉，且清理记录写进迁移日志。"""
    import sqlite3

    migration = _load()
    path = os.environ['YUEXIANG_DB']
    log = migration.migrate(path, force=True)
    conn = sqlite3.connect(path)
    points_null = conn.execute(
        'SELECT COUNT(*) FROM points WHERE user_id IS NULL').fetchone()[0]
    orphan_messages = conn.execute(
        """SELECT COUNT(*) FROM messages m
             LEFT JOIN users u ON u.username = m.receiver_id
            WHERE u.username IS NULL""").fetchone()[0]
    recorded = conn.execute(
        "SELECT extra FROM schema_migrations WHERE version = ?",
        (migration.VERSION,)).fetchone()
    conn.close()
    stored = json.loads(recorded[0]) if recorded else {}
    return {
        'points_null_left': points_null,
        'orphan_messages_left': orphan_messages,
        'log_points': len(log['cleaned_points']),
        'log_messages': len(log['cleaned_messages']),
        'stored_points': len(stored.get('cleaned_points', [])),
        'stored_messages': len(stored.get('cleaned_messages', [])),
        'stored_receivers': [r['receiver_id'] for r in stored.get('cleaned_messages', [])],
    }


def probe_api_parity():
    """从跑过迁移的实例取接口输出，供与基线库实例逐字节比对。"""
    from app import app
    client = app.test_client()
    out = {}

    login = client.post('/api/auth/login', data=json.dumps(
        {'username': 'student_demo', 'password': '123456'}),
        content_type='application/json')
    sid = json.loads(login.data)['session_id']
    headers = {'X-Session-Id': sid}

    def get(path, with_session=False):
        response = client.get(path, headers=headers if with_session else {})
        return {'status': response.status_code,
                'body': json.loads(response.data.decode('utf-8'))}

    paths = [
        '/api/agriculture/products',
        '/api/agriculture/calendar/lychee',
        '/api/agriculture/calendar/rice?year=2026&month=9',
        '/api/agriculture/pest-knowledge',
        '/api/crafts/list',
        '/api/crafts/embroidery',
        '/api/resources/dialects',
        '/api/resources/dialect-info?dialect=teochew',
        '/api/resources/cases',
        '/api/resources/cases/1',
        '/api/employment/jobs',
        '/api/home/stats',
    ]
    for path in paths:
        out[path] = get(path)
    out['/api/agriculture/subscriptions'] = get('/api/agriculture/subscriptions', True)
    return out


PROBES = {
    'idempotent': probe_idempotent,
    'cleanup': probe_cleanup,
    'api_parity': probe_api_parity,
}


if __name__ == '__main__':
    print(json.dumps(PROBES[sys.argv[1]](), ensure_ascii=False))
