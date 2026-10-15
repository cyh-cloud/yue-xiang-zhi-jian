#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T05 内容迁移契约测试用的探针：在隔离库上跑迁移并把结果以 JSON 打到 stdout。

单独成文件而不是内联在测试里的理由：探针里有大量「代码内容 vs 库里行」的逐字段
比对，内联进 Python 测试要层层转义，改一次就得重新数一遍引号。探针只由
test_content_migration.py 以子进程方式调用，不是产品代码。

用法：python migration_probe.py <name>；库路径由 YUEXIANG_DB 指定。
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


def _sources():
    return _load()._load_sources()


def probe_counts():
    """灌库后 14 张内容表的行数与代码内容逐项相符。"""
    import sqlite3

    migration = _load()
    src = migration._load_sources()
    fd = src['farming_data']
    pd = src['pest_data']
    jd = src['jobs_data']
    cd = src['cases_data']
    dialects = src['DIALECTS_DATA']
    crafts = src['CRAFTS_KNOWLEDGE']

    expected = {
        'farming_categories': len(fd.FARMING_CATEGORY_LABELS),
        'farming_sources': len(fd.FARMING_SOURCES),
        'farming_products': len(fd.FARMING_PRODUCTS),
        'farming_phenophases': len(fd.FARMING_PHENOPHASES),
        'farming_tasks': len(fd.FARMING_TASKS),
        'pest_crops': sum(1 for c in pd.PEST_CROP_ORDER if pd.PEST_KNOWLEDGE.get(c)),
        'pest_entries': len(list(pd.iter_pest_entries())),
        'pest_sources': len(pd.PEST_SOURCES),
        'pest_entry_sources': sum(len(e.get('sources') or [])
                                  for _c, _d, e in pd.iter_pest_entries()),
        'pest_images': len(src['PEST_IMAGES']),
        'recruitments': len(jd.RECRUIT_DATA),
        'recruitment_sources': sum(len(r.get('sources') or []) for r in jd.RECRUIT_DATA),
        'success_cases': len(cd.SUCCESS_CASES),
        'case_stats': sum(len(c.get('stats') or []) for c in cd.SUCCESS_CASES),
        'case_milestones': sum(len(c.get('milestones') or []) for c in cd.SUCCESS_CASES),
        'case_sources': sum(len(c.get('sources') or []) for c in cd.SUCCESS_CASES),
        'case_lessons': sum(len(c.get('lessons') or []) for c in cd.SUCCESS_CASES),
        'dialects': len(dialects),
        'dialect_phrases': sum(len(d.get('phrases') or []) for d in dialects.values()),
        'dialect_quick_questions': sum(len(d.get('quick_questions') or [])
                                       for d in dialects.values()),
        'crafts': len(crafts),
        'craft_steps': sum(len(c.get('steps') or []) for c in crafts.values()),
        'craft_purchase_categories': sum(
            len((c.get('purchase_guide') or {}).get('categories') or [])
            for c in crafts.values()),
        'craft_purchase_items': sum(
            len(cat.get('items') or []) for c in crafts.values()
            for cat in (c.get('purchase_guide') or {}).get('categories') or []),
        'craft_budgets': sum(1 for c in crafts.values()
                             if (c.get('purchase_guide') or {}).get('budget')),
    }

    conn = sqlite3.connect(os.environ['YUEXIANG_DB'])
    actual = {table: conn.execute('SELECT COUNT(*) FROM %s' % table).fetchone()[0]
              for table in expected}
    conn.close()
    return {'expected': expected, 'actual': actual,
            'mismatch': {t: (expected[t], actual[t])
                         for t in expected if expected[t] != actual[t]}}


def probe_fields():
    """逐字段比对：灌进去的内容与代码内容一致（不是只数行数）。"""
    import sqlite3

    src = _sources()
    fd = src['farming_data']
    conn = sqlite3.connect(os.environ['YUEXIANG_DB'])
    conn.row_factory = __import__('sqlite3').Row

    problems = []

    db_products = {r['id']: dict(r) for r in conn.execute('SELECT * FROM farming_products')}
    for p in fd.FARMING_PRODUCTS:
        row = db_products.get(p['id'])
        if row is None:
            problems.append('farming_products 缺 %s' % p['id'])
            continue
        for field, want in (('name', p['name']), ('icon', p.get('icon', 'seedling')),
                            ('summary', p.get('summary', '')),
                            ('sort_order', p.get('sort_order', 0))):
            if row[field] != want:
                problems.append('farming_products.%s.%s = %r，期望 %r'
                                % (p['id'], field, row[field], want))

    db_sources = {r['key']: dict(r) for r in conn.execute('SELECT * FROM farming_sources')}
    for s in fd.FARMING_SOURCES:
        row = db_sources.get(s['key'])
        if row is None:
            problems.append('farming_sources 缺 %s' % s['key'])
            continue
        for field in ('name', 'org', 'doc_type', 'doc_no', 'url'):
            want = s.get(field, '') or ('待核' if field == 'doc_no' else '')
            if row[field] != want:
                problems.append('farming_sources.%s.%s = %r，期望 %r'
                                % (s['key'], field, row[field], want))

    db_categories = {r['key']: r['label']
                     for r in conn.execute('SELECT key, label FROM farming_categories')}
    for key, label in fd.FARMING_CATEGORY_LABELS.items():
        if db_categories.get(key) != label:
            problems.append('farming_categories.%s = %r，期望 %r'
                            % (key, db_categories.get(key), label))

    # 任务：字段逐项相等，且 id 与原库一致（它直接下发给前端）
    db_tasks = {(r['product_id'], r['task_md'], r['title']): dict(r)
                for r in conn.execute('SELECT * FROM farming_tasks')}
    for t in fd.FARMING_TASKS:
        row = db_tasks.get((t['product_id'], t.get('task_md'), t['title']))
        if row is None:
            problems.append('farming_tasks 缺 %s' % (t['title'],))
            continue
        for field in ('category', 'priority', 'month', 'icon', 'description', 'tip',
                      'source_key', 'date_basis', 'is_verified'):
            want = t.get(field, '')
            if field == 'is_verified':
                want = int(t.get(field) or 0)
            if (row[field] or '') != (want or ''):
                problems.append('farming_tasks[%s].%s = %r，期望 %r'
                                % (t['title'], field, row[field], want))

    # 病虫害：五个 JSON 列解析回来要与代码里的列表相等
    pd = src['pest_data']
    db_entries = {r['id']: dict(r) for r in conn.execute('SELECT * FROM pest_entries')}
    for _crop, _crop_data, entry in pd.iter_pest_entries():
        row = db_entries.get(entry['id'])
        if row is None:
            problems.append('pest_entries 缺 %s' % entry['id'])
            continue
        for field in ('symptoms', 'treatment', 'prevention', 'registered', 'chem_table'):
            if json.loads(row[field]) != (entry.get(field) or []):
                problems.append('pest_entries[%s].%s 与代码不一致' % (entry['id'], field))
        for field in ('disease', 'alias', 'kind', 'pathogen', 'part', 'severity',
                      'occurrence', 'safety_note'):
            if (row[field] or '') != (entry.get(field) or ''):
                problems.append('pest_entries[%s].%s 与代码不一致' % (entry['id'], field))

    # 方言与技艺：嵌套结构读回后要与原常量相等
    dialects = src['DIALECTS_DATA']
    for dialect_id, d in dialects.items():
        row = conn.execute('SELECT * FROM dialects WHERE id = ?', (dialect_id,)).fetchone()
        if row is None:
            problems.append('dialects 缺 %s' % dialect_id)
            continue
        if json.loads(row['features']) != (d.get('features') or []):
            problems.append('dialects.%s.features 与代码不一致' % dialect_id)
        phrases = [dict(r) for r in conn.execute(
            'SELECT dialect, mandarin, pinyin FROM dialect_phrases '
            'WHERE dialect_id = ? ORDER BY sort_order', (dialect_id,))]
        if phrases != (d.get('phrases') or []):
            problems.append('dialect_phrases.%s 与代码不一致' % dialect_id)
        quick = [r[0] for r in conn.execute(
            'SELECT question FROM dialect_quick_questions '
            'WHERE dialect_id = ? ORDER BY sort_order', (dialect_id,))]
        if quick != (d.get('quick_questions') or []):
            problems.append('dialect_quick_questions.%s 与代码不一致' % dialect_id)

    crafts = src['CRAFTS_KNOWLEDGE']
    for craft_id, craft in crafts.items():
        steps = [dict(r) for r in conn.execute(
            'SELECT title, "desc", tips FROM craft_steps '
            'WHERE craft_id = ? ORDER BY sort_order', (craft_id,))]
        if steps != (craft.get('steps') or []):
            problems.append('craft_steps.%s 与代码不一致' % craft_id)
        budget = conn.execute('SELECT * FROM craft_budgets WHERE craft_id = ?',
                              (craft_id,)).fetchone()
        guide = craft.get('purchase_guide') or {}
        if budget is None or (budget['starter'], budget['advanced']) != (
                (guide.get('budget') or {}).get('starter', ''),
                (guide.get('budget') or {}).get('advanced', '')):
            problems.append('craft_budgets.%s 与代码不一致' % craft_id)
        for pos, cat in enumerate(guide.get('categories') or []):
            row = conn.execute(
                'SELECT label, "desc" FROM craft_purchase_categories '
                'WHERE craft_id = ? AND key = ?', (craft_id, cat['key'])).fetchone()
            if row is None or (row[0], row[1]) != (cat['label'], cat['desc']):
                problems.append('craft_purchase_categories.%s.%s 与代码不一致'
                                % (craft_id, cat['key']))
                continue
            items = [dict(r) for r in conn.execute(
                'SELECT name, price, spec, tip, "where" FROM craft_purchase_items '
                'WHERE craft_id = ? AND category_key = ? ORDER BY sort_order',
                (craft_id, cat['key']))]
            if items != (cat.get('items') or []):
                problems.append('craft_purchase_items.%s.%s 与代码不一致'
                                % (craft_id, cat['key']))

    conn.close()
    return {'problems': problems}


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
    """从灌过库的实例取接口输出，供与现库实例逐字节比对。"""
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
    conn = app.test_client()
    out['/api/agriculture/subscriptions'] = get('/api/agriculture/subscriptions', True)
    return out


PROBES = {
    'counts': probe_counts,
    'fields': probe_fields,
    'idempotent': probe_idempotent,
    'cleanup': probe_cleanup,
    'api_parity': probe_api_parity,
}


if __name__ == '__main__':
    print(json.dumps(PROBES[sys.argv[1]](), ensure_ascii=False))
