#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""农业域（农时智能日历）的播种。

数据源是 farming_data.py，按内容签名判断是否需要重灌：仅比行数发现不了
「条数不变但内容变了」（例如给已有任务补 task_md、修正物候期月份区间）。
重写时先删后插；farming_subscriptions / farming_reminder_log 不含外键指向任务 id，
且均以 (user_id, product_id[, period]) 为业务键，因此用户订阅数据不受影响。
"""

import hashlib
import json
import sys

import repo_paths

# ==================== 农时智能日历 种子数据 ====================

def farming_seed_signature(sources, products, phases, tasks):
    """计算种子数据内容签名（sha1）。

    仅比行数无法发现"条数不变但内容变了"的情况（例如为已有任务补 task_md、
    修正物候期月份区间、补齐 source_key / date_basis）。此处对全部字段做规范化
    JSON 序列化后取 sha1，内容有任何变化都会导致签名不同，从而触发重灌。
    """
    payload = {
        'sources': [
            [s['key'], s.get('name', ''), s.get('org', ''), s.get('doc_type', ''),
             s.get('doc_no', ''), s.get('url', '')]
            for s in sources
        ],
        'products': [
            [p['id'], p.get('name', ''), p.get('icon', 'seedling'),
             p.get('summary', ''), p.get('region', '广东'), p.get('sort_order', 0)]
            for p in products
        ],
        'phases': [
            [ph['product_id'], ph.get('name', ''), ph.get('start_month'),
             ph.get('end_month'), ph.get('color', ''), ph.get('description', ''),
             ph.get('sort_order', 0)]
            for ph in phases
        ],
        'tasks': [
            [t['product_id'], t.get('phase'), t.get('title', ''), t.get('category', ''),
             t.get('priority', 'medium'), t.get('task_md'), t.get('month'),
             t.get('icon', 'tasks'), t.get('description', ''), t.get('tip', ''),
             t.get('is_verified', 0), t.get('source_key', ''),
             t.get('date_basis', '')]
            for t in tasks
        ],
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return hashlib.sha1(raw.encode('utf-8')).hexdigest()


def seed_farming(cursor):
    """写入农时日历种子数据（幂等，按内容签名判断是否需要重灌）。

    - 数据源：仓库根的 farming_data.py
    - 仅当数据模块的**内容签名**与 farming_seed_meta 中记录的不一致时才重写，
      避免每次启动都产生写放大；同时可捕获"条数不变但内容变了"的更新
    - 重写时先删后插：farming_subscriptions / farming_reminder_log 不含外键指向任务 id，
      且均以 (user_id, product_id[, period]) 为业务键，因此用户订阅数据不受影响
    """
    # 数据模块在 domain_data/agriculture/ 下，与数据库目录同一基准（T02 的路径约定）
    if repo_paths.REPO_ROOT not in sys.path:
        sys.path.insert(0, repo_paths.REPO_ROOT)
    try:
        from domain_data.agriculture import farming_data as fd
    except Exception:
        return  # 数据模块缺失时静默跳过，不阻断建库

    sources = getattr(fd, 'FARMING_SOURCES', [])
    products = getattr(fd, 'FARMING_PRODUCTS', [])
    phases = getattr(fd, 'FARMING_PHENOPHASES', [])
    tasks = getattr(fd, 'FARMING_TASKS', [])
    if not (products and phases and tasks):
        return

    signature = farming_seed_signature(sources, products, phases, tasks)
    row = cursor.execute(
        "SELECT value FROM farming_seed_meta WHERE key = 'farming_seed'").fetchone()
    if row and row[0] == signature:
        return  # 内容未变化，跳过

    # ① 数据来源登记表（整体替换：来源集合只随数据模块变化）
    cursor.execute("DELETE FROM farming_sources")
    for idx, s in enumerate(sources):
        cursor.execute(
            """INSERT INTO farming_sources (key, name, org, doc_type, doc_no, url, sort_order)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (s['key'], s.get('name', ''), s.get('org', ''), s.get('doc_type', ''),
             s.get('doc_no', '') or '待核', s.get('url', ''), idx))

    # ② 产品目录（upsert，不动订阅）
    for p in products:
        cursor.execute(
            """INSERT INTO farming_products (id, name, icon, summary, region, sort_order, is_active)
               VALUES (?, ?, ?, ?, ?, ?, 1)
               ON CONFLICT(id) DO UPDATE SET
                   name=excluded.name, icon=excluded.icon, summary=excluded.summary,
                   region=excluded.region, sort_order=excluded.sort_order, is_active=1""",
            (p['id'], p['name'], p.get('icon', 'seedling'), p.get('summary', ''),
             p.get('region', '广东'), p.get('sort_order', 0)))

    # ③ 物候期（按产品删后重建）
    for p in products:
        cursor.execute("DELETE FROM farming_phenophases WHERE product_id = ?", (p['id'],))
    for ph in phases:
        cursor.execute(
            """INSERT INTO farming_phenophases
                   (product_id, name, start_month, end_month, color, description, sort_order)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (ph['product_id'], ph['name'], ph['start_month'], ph['end_month'],
             ph.get('color', '#1f5e43'), ph.get('description', ''), ph.get('sort_order', 0)))

    # ④ 任务（按产品删后重建；phase 名称 -> phase_id）
    phase_map = {}
    for r in cursor.execute("SELECT id, product_id, name FROM farming_phenophases").fetchall():
        phase_map[(r[1], r[2])] = r[0]

    for p in products:
        cursor.execute("DELETE FROM farming_tasks WHERE product_id = ?", (p['id'],))
    for idx, t in enumerate(tasks):
        phase_id = phase_map.get((t['product_id'], t.get('phase')))
        cursor.execute(
            """INSERT INTO farming_tasks
                   (product_id, phase_id, title, category, priority, task_md, month,
                    icon, description, tip, is_verified, source_key, date_basis,
                    is_active, sort_order)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)""",
            (t['product_id'], phase_id, t['title'], t['category'],
             t.get('priority', 'medium'), t.get('task_md'), t['month'],
             t.get('icon', 'tasks'), t.get('description', ''), t.get('tip', ''),
             int(t.get('is_verified', 0) or 0), t.get('source_key', '') or '',
             t.get('date_basis', '') or '', idx))

    # ⑤ 记录本次签名
    cursor.execute(
        """INSERT INTO farming_seed_meta (key, value, updated_at)
           VALUES ('farming_seed', ?, datetime('now','localtime'))
           ON CONFLICT(key) DO UPDATE SET
               value=excluded.value, updated_at=excluded.updated_at""",
        (signature,))
