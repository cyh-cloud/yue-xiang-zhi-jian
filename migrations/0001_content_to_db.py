# -*- coding: utf-8 -*-
"""一次性内容迁移：把代码里的内容灌进内容落库新建的表（ADR 0002）。

本脚本是 6400 行内容进库的唯一凭据。它进版本库但标注「已执行」，靠 schema_migrations
表防重入，不删。理由见 spec 的「迁移脚本」一节：发现漏字段时重跑比手工补快，
且它是转换逻辑，不是数据副本。

三类动作，全部写进迁移日志（schema_migrations.extra 里的 JSON），不静默丢弃：

  1. 清现库脏数据：points 表 user_id IS NULL 的行、messages 表收件人指向不存在用户的行；
  2. 灌内容：农时日历、病虫害知识、实拍图、招募公告、成功案例、方言、手工技艺；
  3. 记录本次执行的版本号，供防重入与事后追溯。

按 spec 4.2 删除、本次**不迁移**的四个常量（_DEFAULT_AGRICULTURE_PRODUCTS、
_STATIC_AGRI_SUGGESTIONS、_AGRI_PRODUCT_NAME_FALLBACK、AGRICULTURE_KNOWLEDGE）
一个字节都不进库：它们不再是数据，是缺陷，删它们是 T10 的范围。

用法：
    python migrations/0001_content_to_db.py [--db 路径] [--dry-run] [--force]

  --db       指定目标库，默认走 db_connection.DB_PATH（即 YUEXIANG_DB 或 data/yuexiang.db）
  --dry-run  只报告将要做什么，不写库
  --force    忽略已执行标记重新灌一遍（仅用于补漏字段；会覆盖运营改过的内容）
"""

import argparse
import json
import os
import sys

# 后端代码整体迁入 backend/ 后，被灌的 domain_data / domains 与 db_schema 都在 backend/ 下。
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(REPO_ROOT, 'backend')
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

VERSION = '0001'
NAME = 'content_to_db'


def _load_sources():
    """导入六份 domain_data 与两份 domains 内容常量。

    放在函数里而不是模块顶部：这些模块是 T10 要删的对象，导入失败时脚本仍要能跑
    （例如已经删干净的仓库上重跑，只做幂等校验）。
    """
    from domain_data.agriculture import farming_data
    from domain_data.employment import jobs_data
    from domain_data.pest_diagnosis import pest_data
    from domain_data.pest_diagnosis.pest_image_manifest import PEST_IMAGES
    from domain_data.resources import cases_data
    from domains.crafts.routes import CRAFTS_KNOWLEDGE
    from domains.resources.dialect_voice import DIALECTS_DATA
    return {
        'farming_data': farming_data,
        'jobs_data': jobs_data,
        'pest_data': pest_data,
        'PEST_IMAGES': PEST_IMAGES,
        'cases_data': cases_data,
        'CRAFTS_KNOWLEDGE': CRAFTS_KNOWLEDGE,
        'DIALECTS_DATA': DIALECTS_DATA,
    }


# ---------- 灌库：农时日历 ----------

def migrate_farming(cur, src, log):
    """农时日历：分类标签、来源、作物、物候期、任务。

    任务与物候期按「自然键」定位而不是按自增 id：现库里这些行本来就是同一份
    domain_data 灌的，按 (product_id, task_md, title) 命中就能保住 farming_tasks.id
    （它直接下发给前端，且订阅与提醒日志不指向它，见 db_seed_farming 的说明）。
    """
    fd = src['farming_data']

    for key, label in sorted(fd.FARMING_CATEGORY_LABELS.items()):
        cur.execute(
            "INSERT INTO farming_categories (key, label, sort_order) VALUES (?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET label=excluded.label",
            (key, label, 0))
    log['farming_categories'] = len(fd.FARMING_CATEGORY_LABELS)

    for idx, s in enumerate(fd.FARMING_SOURCES):
        cur.execute(
            """INSERT INTO farming_sources (key, name, org, doc_type, doc_no, url, sort_order)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(key) DO UPDATE SET
                   name=excluded.name, org=excluded.org, doc_type=excluded.doc_type,
                   doc_no=excluded.doc_no, url=excluded.url, sort_order=excluded.sort_order""",
            (s['key'], s.get('name', ''), s.get('org', ''), s.get('doc_type', ''),
             s.get('doc_no', '') or '待核', s.get('url', ''), idx))
    log['farming_sources'] = len(fd.FARMING_SOURCES)

    for p in fd.FARMING_PRODUCTS:
        cur.execute(
            """INSERT INTO farming_products (id, name, icon, summary, region, sort_order, is_active)
               VALUES (?, ?, ?, ?, ?, ?, 1)
               ON CONFLICT(id) DO UPDATE SET
                   name=excluded.name, icon=excluded.icon, summary=excluded.summary,
                   region=excluded.region, sort_order=excluded.sort_order, is_active=1""",
            (p['id'], p['name'], p.get('icon', 'seedling'), p.get('summary', ''),
             p.get('region', '广东'), p.get('sort_order', 0)))
    log['farming_products'] = len(fd.FARMING_PRODUCTS)

    # 物候期同样按自然键 (product_id, name) 定位：farming_tasks.phase_id 指向它，
    # 删后重建会换 id，任务的 phase_id 跟着变，接口输出里 phase_id 是可见字段。
    for ph in fd.FARMING_PHENOPHASES:
        row = cur.execute(
            "SELECT id FROM farming_phenophases WHERE product_id = ? AND name = ? LIMIT 1",
            (ph['product_id'], ph['name'])).fetchone()
        if row:
            cur.execute(
                """UPDATE farming_phenophases
                      SET start_month = ?, end_month = ?, color = ?, description = ?, sort_order = ?
                    WHERE id = ?""",
                (ph['start_month'], ph['end_month'], ph.get('color', '#1f5e43'),
                 ph.get('description', ''), ph.get('sort_order', 0), row[0]))
        else:
            cur.execute(
                """INSERT INTO farming_phenophases
                       (product_id, name, start_month, end_month, color, description, sort_order)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (ph['product_id'], ph['name'], ph['start_month'], ph['end_month'],
                 ph.get('color', '#1f5e43'), ph.get('description', ''), ph.get('sort_order', 0)))
    log['farming_phenophases'] = len(fd.FARMING_PHENOPHASES)

    phase_map = {}
    for r in cur.execute("SELECT id, product_id, name FROM farming_phenophases").fetchall():
        phase_map[(r[1], r[2])] = r[0]

    # 任务按自然键 upsert：命中的行就地更新（id 不变），没命中的才插入。
    # 自然键 (product_id, task_md, title) 在库里没有唯一约束（T04 建表时没加，
    # 本票也不改它的表结构），所以这里不能写 ON CONFLICT，改成先查后写。
    # farming_tasks.id 直接下发给前端，重建会换 id，故必须就地更新。
    for idx, t in enumerate(fd.FARMING_TASKS):
        phase_id = phase_map.get((t['product_id'], t.get('phase')))
        row = cur.execute(
            """SELECT id FROM farming_tasks
                WHERE product_id = ? AND task_md IS ? AND title = ? LIMIT 1""",
            (t['product_id'], t.get('task_md'), t['title'])).fetchone()
        if row:
            cur.execute(
                """UPDATE farming_tasks
                      SET phase_id = ?, category = ?, priority = ?, month = ?, icon = ?,
                          description = ?, tip = ?, is_verified = ?, source_key = ?,
                          date_basis = ?, is_active = 1, sort_order = ?
                    WHERE id = ?""",
                (phase_id, t['category'], t.get('priority', 'medium'), t['month'],
                 t.get('icon', 'tasks'), t.get('description', ''), t.get('tip', ''),
                 int(t.get('is_verified', 0) or 0), t.get('source_key', '') or '',
                 t.get('date_basis', '') or '', idx, row[0]))
        else:
            cur.execute(
                """INSERT INTO farming_tasks
                       (product_id, phase_id, title, category, priority, task_md, month, icon,
                        description, tip, is_verified, source_key, date_basis, is_active, sort_order)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)""",
                (t['product_id'], phase_id, t['title'], t['category'],
                 t.get('priority', 'medium'), t.get('task_md'), t['month'],
                 t.get('icon', 'tasks'), t.get('description', ''), t.get('tip', ''),
                 int(t.get('is_verified', 0) or 0), t.get('source_key', '') or '',
                 t.get('date_basis', '') or '', idx))
    log['farming_tasks'] = len(fd.FARMING_TASKS)


def migrate_pest(cur, src, log):
    """病虫害：作物层、来源、条目、条目与来源多对多、实拍图。"""
    pd = src['pest_data']

    # 展示顺序与农时日历的作物顺序一致（PEST_CROP_ORDER 是既有口径）
    for idx, crop in enumerate(pd.PEST_CROP_ORDER):
        crop_data = pd.PEST_KNOWLEDGE.get(crop)
        if not crop_data:
            continue
        cur.execute(
            """INSERT INTO pest_crops (id, name, icon, summary, sort_order)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                   name=excluded.name, icon=excluded.icon, summary=excluded.summary,
                   sort_order=excluded.sort_order""",
            (crop, crop_data.get('name', ''), crop_data.get('icon', ''),
             crop_data.get('summary', ''), idx))
    log['pest_crops'] = sum(1 for c in pd.PEST_CROP_ORDER if pd.PEST_KNOWLEDGE.get(c))

    for idx, s in enumerate(pd.PEST_SOURCES):
        cur.execute(
            """INSERT INTO pest_sources (key, name, org, doc_type, doc_no, date, url, sort_order)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(key) DO UPDATE SET
                   name=excluded.name, org=excluded.org, doc_type=excluded.doc_type,
                   doc_no=excluded.doc_no, date=excluded.date, url=excluded.url,
                   sort_order=excluded.sort_order""",
            (s['key'], s.get('name', ''), s.get('org', ''), s.get('doc_type', ''),
             s.get('doc_no', ''), s.get('date', ''), s.get('url', ''), idx))
    log['pest_sources'] = len(pd.PEST_SOURCES)

    entries = list(pd.iter_pest_entries())
    for idx, (crop, _crop_data, entry) in enumerate(entries):
        cur.execute(
            """INSERT INTO pest_entries
                   (id, crop_id, disease, alias, kind, pathogen, part, severity, symptoms,
                    occurrence, treatment, prevention, registered, chem_table, safety_note,
                    is_verified, sort_order)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                   crop_id=excluded.crop_id, disease=excluded.disease, alias=excluded.alias,
                   kind=excluded.kind, pathogen=excluded.pathogen, part=excluded.part,
                   severity=excluded.severity, symptoms=excluded.symptoms,
                   occurrence=excluded.occurrence, treatment=excluded.treatment,
                   prevention=excluded.prevention, registered=excluded.registered,
                   chem_table=excluded.chem_table, safety_note=excluded.safety_note,
                   is_verified=excluded.is_verified, sort_order=excluded.sort_order""",
            (entry['id'], crop, entry.get('disease', ''), entry.get('alias', ''),
             entry.get('kind', ''), entry.get('pathogen', ''), entry.get('part', ''),
             entry.get('severity', ''), _json(entry.get('symptoms')),
             entry.get('occurrence', ''), _json(entry.get('treatment')),
             _json(entry.get('prevention')), _json(entry.get('registered')),
             _json(entry.get('chem_table')), entry.get('safety_note', ''),
             int(entry.get('is_verified') or 0), idx))
    log['pest_entries'] = len(entries)

    links = 0
    for _crop, _crop_data, entry in entries:
        for pos, key in enumerate(entry.get('sources') or []):
            cur.execute(
                """INSERT INTO pest_entry_sources (entry_id, source_key, sort_order)
                   VALUES (?, ?, ?)
                   ON CONFLICT(entry_id, source_key) DO UPDATE SET sort_order=excluded.sort_order""",
                (entry['id'], key, pos))
            links += 1
    log['pest_entry_sources'] = links

    images = src['PEST_IMAGES']
    for entry_id, img in images.items():
        cur.execute(
            """INSERT INTO pest_images
                   (entry_id, file, credit, license, caption, source_url, shot_date, note)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(entry_id) DO UPDATE SET
                   file=excluded.file, credit=excluded.credit, license=excluded.license,
                   caption=excluded.caption, source_url=excluded.source_url,
                   shot_date=excluded.shot_date, note=excluded.note""",
            (entry_id, img.get('file', ''), img.get('credit', ''), img.get('license', ''),
             img.get('caption', ''), img.get('source_url', ''), img.get('shot_date', ''),
             img.get('note', '')))
    log['pest_images'] = len(images)


# ---------- 灌库：招募、案例、方言、技艺 ----------

def migrate_recruitments(cur, src, log):
    """招募公告：主表 + 来源子表。"""
    jd = src['jobs_data']
    for idx, r in enumerate(jd.RECRUIT_DATA):
        cur.execute(
            """INSERT INTO recruitments
                   (key, title, org, region, category, job_type, headcount, education,
                    experience, salary, description, publish_date, signup_start, deadline,
                    signup_way, contact, sort_order)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(key) DO UPDATE SET
                   title=excluded.title, org=excluded.org, region=excluded.region,
                   category=excluded.category, job_type=excluded.job_type,
                   headcount=excluded.headcount, education=excluded.education,
                   experience=excluded.experience, salary=excluded.salary,
                   description=excluded.description, publish_date=excluded.publish_date,
                   signup_start=excluded.signup_start, deadline=excluded.deadline,
                   signup_way=excluded.signup_way, contact=excluded.contact,
                   sort_order=excluded.sort_order""",
            (r['key'], r.get('title', ''), r.get('org', ''), r.get('region', ''),
             r.get('category', ''), r.get('job_type', ''), r.get('headcount', ''),
             r.get('education', ''), r.get('experience', ''), r.get('salary', ''),
             r.get('description', ''), r.get('publish_date', ''), r.get('signup_start', ''),
             r.get('deadline', ''), r.get('signup_way', ''), r.get('contact', ''), idx))
        for pos, s in enumerate(r.get('sources') or []):
            cur.execute(
                """INSERT INTO recruitment_sources
                       (recruit_key, title, media, date, url, sort_order)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(recruit_key, title) DO UPDATE SET
                       media=excluded.media, date=excluded.date, url=excluded.url,
                       sort_order=excluded.sort_order""",
                (r['key'], s.get('title', ''), s.get('media', ''), s.get('date', ''),
                 s.get('url', ''), pos))
    log['recruitments'] = len(jd.RECRUIT_DATA)
    log['recruitment_sources'] = sum(len(r.get('sources') or []) for r in jd.RECRUIT_DATA)


def migrate_cases(cur, src, log):
    """成功案例：主表 + 指标 / 里程碑 / 来源 / 借鉴点四个子表。"""
    cd = src['cases_data']
    for idx, c in enumerate(cd.SUCCESS_CASES):
        cur.execute(
            """INSERT INTO success_cases
                   (id, title, region, location, background, description, quote,
                    quote_author, sort_order)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                   title=excluded.title, region=excluded.region, location=excluded.location,
                   background=excluded.background, description=excluded.description,
                   quote=excluded.quote, quote_author=excluded.quote_author,
                   sort_order=excluded.sort_order""",
            (c['id'], c.get('title', ''), c.get('region', ''), c.get('location', ''),
             c.get('background', ''), c.get('description', ''), c.get('quote', ''),
             c.get('quote_author', ''), idx))
        # 子表按 case_id 删后重建：它们是纯内容，没有外部引用，也不需要保 id。
        for table in ('case_stats', 'case_milestones', 'case_sources', 'case_lessons'):
            cur.execute("DELETE FROM %s WHERE case_id = ?" % table, (c['id'],))
        for pos, s in enumerate(c.get('stats') or []):
            cur.execute(
                """INSERT INTO case_stats (case_id, label, value, icon, sort_order)
                   VALUES (?, ?, ?, ?, ?)""",
                (c['id'], s.get('label', ''), s.get('value', ''), s.get('icon', ''), pos))
        for pos, m in enumerate(c.get('milestones') or []):
            cur.execute(
                """INSERT INTO case_milestones (case_id, period, title, "desc", sort_order)
                   VALUES (?, ?, ?, ?, ?)""",
                (c['id'], m.get('period', ''), m.get('title', ''), m.get('desc', ''), pos))
        for pos, s in enumerate(c.get('sources') or []):
            cur.execute(
                """INSERT INTO case_sources (case_id, title, media, date, url, sort_order)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (c['id'], s.get('title', ''), s.get('media', ''), s.get('date', ''),
                 s.get('url', ''), pos))
        for pos, text in enumerate(c.get('lessons') or []):
            cur.execute(
                "INSERT INTO case_lessons (case_id, text, sort_order) VALUES (?, ?, ?)",
                (c['id'], text, pos))
    log['success_cases'] = len(cd.SUCCESS_CASES)
    log['case_stats'] = sum(len(c.get('stats') or []) for c in cd.SUCCESS_CASES)
    log['case_milestones'] = sum(len(c.get('milestones') or []) for c in cd.SUCCESS_CASES)
    log['case_sources'] = sum(len(c.get('sources') or []) for c in cd.SUCCESS_CASES)
    log['case_lessons'] = sum(len(c.get('lessons') or []) for c in cd.SUCCESS_CASES)


def migrate_dialects(cur, src, log):
    """方言：方言层 + 短语 + 快捷问题。"""
    data = src['DIALECTS_DATA']
    for idx, (dialect_id, d) in enumerate(data.items()):
        cur.execute(
            """INSERT INTO dialects
                   (id, name, region, emoji, areas, speakers, greeting, greeting_meaning,
                    features, sort_order)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                   name=excluded.name, region=excluded.region, emoji=excluded.emoji,
                   areas=excluded.areas, speakers=excluded.speakers,
                   greeting=excluded.greeting, greeting_meaning=excluded.greeting_meaning,
                   features=excluded.features, sort_order=excluded.sort_order""",
            (dialect_id, d.get('name', ''), d.get('region', ''), d.get('emoji', ''),
             d.get('areas', ''), d.get('speakers', ''), d.get('greeting', ''),
             d.get('greeting_meaning', ''), _json(d.get('features')), idx))
        for table in ('dialect_phrases', 'dialect_quick_questions'):
            cur.execute("DELETE FROM %s WHERE dialect_id = ?" % table, (dialect_id,))
        for pos, p in enumerate(d.get('phrases') or []):
            cur.execute(
                """INSERT INTO dialect_phrases (dialect_id, dialect, mandarin, pinyin, sort_order)
                   VALUES (?, ?, ?, ?, ?)""",
                (dialect_id, p.get('dialect', ''), p.get('mandarin', ''),
                 p.get('pinyin', ''), pos))
        for pos, q in enumerate(d.get('quick_questions') or []):
            cur.execute(
                """INSERT INTO dialect_quick_questions (dialect_id, question, sort_order)
                   VALUES (?, ?, ?)""",
                (dialect_id, q, pos))
    log['dialects'] = len(data)
    log['dialect_phrases'] = sum(len(d.get('phrases') or []) for d in data.values())
    log['dialect_quick_questions'] = sum(len(d.get('quick_questions') or [])
                                        for d in data.values())


def migrate_crafts(cur, src, log):
    """手工技艺：技艺层 + 步骤 + 采购分类 + 采购条目 + 预算（三层嵌套拆平）。"""
    knowledge = src['CRAFTS_KNOWLEDGE']
    for idx, (craft_id, craft) in enumerate(knowledge.items()):
        cur.execute(
            """INSERT INTO crafts (id, name, origin, history, level, sort_order)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                   name=excluded.name, origin=excluded.origin, history=excluded.history,
                   level=excluded.level, sort_order=excluded.sort_order""",
            (craft_id, craft.get('name', ''), craft.get('origin', ''),
             craft.get('history', ''), craft.get('level', ''), idx))
        for table in ('craft_steps', 'craft_purchase_categories', 'craft_purchase_items'):
            cur.execute("DELETE FROM %s WHERE craft_id = ?" % table, (craft_id,))
        cur.execute("DELETE FROM craft_budgets WHERE craft_id = ?", (craft_id,))
        for pos, s in enumerate(craft.get('steps') or []):
            cur.execute(
                """INSERT INTO craft_steps (craft_id, title, "desc", tips, sort_order)
                   VALUES (?, ?, ?, ?, ?)""",
                (craft_id, s.get('title', ''), s.get('desc', ''), s.get('tips', ''), pos))
        guide = craft.get('purchase_guide') or {}
        budget = guide.get('budget') or {}
        cur.execute(
            """INSERT INTO craft_budgets (craft_id, starter, advanced, buying_tips)
               VALUES (?, ?, ?, ?)""",
            (craft_id, budget.get('starter', ''), budget.get('advanced', ''),
             guide.get('buying_tips', '')))
        for pos, cat in enumerate(guide.get('categories') or []):
            cur.execute(
                """INSERT INTO craft_purchase_categories (craft_id, key, label, "desc", sort_order)
                   VALUES (?, ?, ?, ?, ?)""",
                (craft_id, cat.get('key', ''), cat.get('label', ''), cat.get('desc', ''), pos))
            for item_pos, item in enumerate(cat.get('items') or []):
                cur.execute(
                    """INSERT INTO craft_purchase_items
                           (craft_id, category_key, name, price, spec, tip, "where", sort_order)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (craft_id, cat.get('key', ''), item.get('name', ''), item.get('price', ''),
                     item.get('spec', ''), item.get('tip', ''), item.get('where', ''), item_pos))
    log['crafts'] = len(knowledge)
    log['craft_steps'] = sum(len(c.get('steps') or []) for c in knowledge.values())
    log['craft_purchase_categories'] = sum(
        len((c.get('purchase_guide') or {}).get('categories') or []) for c in knowledge.values())
    log['craft_purchase_items'] = sum(
        len(cat.get('items') or [])
        for c in knowledge.values() for cat in (c.get('purchase_guide') or {}).get('categories') or [])
    log['craft_budgets'] = sum(1 for c in knowledge.values() if (c.get('purchase_guide') or {}).get('budget'))


# ---------- 脏数据清理 ----------

def clean_dirty_rows(cur, log):
    """清两处现库脏数据，逐行记进日志，不静默丢弃。

    - points：2 行 user_id IS NULL，而 user_id 是主键。NULL 主键在 SQLite 里能插进去，
      却让「按 user_id 查积分」与「删用户时连带清理」都漏掉它们。
    - messages：2 行收件人指向不存在的 username（一个 uuid、一个名册号 STU001），
      是历史上「把 students.id 当收件人」那个 bug 的残留。收件人不存在，这两行
      永远收不进任何人的收件箱。
    """
    bad_points = [dict(r) for r in cur.execute(
        "SELECT rowid, user_id, balance, history FROM points WHERE user_id IS NULL").fetchall()]
    if bad_points:
        cur.execute("DELETE FROM points WHERE user_id IS NULL")
    log['cleaned_points'] = [{'rowid': r['rowid'], 'balance': r['balance'],
                              'history': r['history']} for r in bad_points]

    orphans = [dict(r) for r in cur.execute(
        """SELECT m.id, m.sender_id, m.receiver_id, m.created_at
             FROM messages m
             LEFT JOIN users u ON u.username = m.receiver_id
            WHERE u.username IS NULL""").fetchall()]
    if orphans:
        ids = [r['id'] for r in orphans]
        _qm = ','.join('?' * len(ids))
        cur.execute("DELETE FROM messages WHERE id IN (%s)" % _qm, ids)
    log['cleaned_messages'] = orphans


# ---------- 入口 ----------

def _json(value):
    return json.dumps(value if value is not None else [], ensure_ascii=False)


def _row_factory(conn):
    import sqlite3
    conn.row_factory = sqlite3.Row


MIGRATORS = (
    ('farming', migrate_farming),
    ('pest', migrate_pest),
    ('recruitments', migrate_recruitments),
    ('cases', migrate_cases),
    ('dialects', migrate_dialects),
    ('crafts', migrate_crafts),
)


def migrate(db_path, dry_run=False, force=False):
    """执行迁移，返回本次写入的日志 dict。重复执行时返回 None（已执行过）。"""
    import sqlite3

    if not os.path.isfile(db_path):
        raise SystemExit('目标库不存在：%s' % db_path)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 先建表再查迁移记录：现库副本可能还没有 T04 的新表与迁移记录表。
    # apply_schema 只用 CREATE ... IF NOT EXISTS 加补列，重复执行安全。
    import db_schema
    db_schema.apply_schema(cur)
    conn.commit()

    already = cur.execute(
        "SELECT version FROM schema_migrations WHERE version = ?", (VERSION,)).fetchone()
    if already and not force:
        conn.close()
        return None

    if dry_run:
        conn.close()
        return {'dry_run': True}

    log = {'version': VERSION, 'name': NAME, 'tables': {}, 'cleaned_points': [], 'cleaned_messages': []}
    src = _load_sources()

    clean_dirty_rows(cur, log)
    for label, func in MIGRATORS:
        func(cur, src, log['tables'])

    cur.execute(
        """INSERT INTO schema_migrations (version, name, applied_at, extra)
           VALUES (?, ?, datetime('now','localtime'), ?)
           ON CONFLICT(version) DO UPDATE SET
               name=excluded.name, applied_at=excluded.applied_at, extra=excluded.extra""",
        (VERSION, NAME, json.dumps(log, ensure_ascii=False)))
    conn.commit()
    conn.close()
    return log


def main(argv=None):
    parser = argparse.ArgumentParser(description='一次性内容迁移：代码内容灌库（ADR 0002）。')
    parser.add_argument('--db', default=None,
                        help='目标库路径，默认走 db_connection.DB_PATH')
    parser.add_argument('--dry-run', action='store_true', help='只报告，不写库')
    parser.add_argument('--force', action='store_true', help='忽略已执行标记重新灌一遍')
    parser.add_argument('--make-baseline', action='store_true',
                        help='灌完库后另存一份基线库（默认 data/baseline.db），'
                             '供新环境还原与 e2e 使用；不入版本库')
    parser.add_argument('--baseline-path', default=None,
                        help='基线库输出路径，默认 data/baseline.db')
    args = parser.parse_args(argv)

    from db_connection import DB_PATH
    db_path = args.db or DB_PATH

    if args.make_baseline:
        return make_baseline(db_path, args.baseline_path, force=args.force)

    log = migrate(db_path, dry_run=args.dry_run, force=args.force)
    if log is None:
        print('版本 %s 已执行过，跳过（--force 可重跑）。' % VERSION)
        return 0
    if log.get('dry_run'):
        print('dry-run：目标库 %s，未写入。' % db_path)
        return 0
    print('迁移 %s（%s）完成，目标库 %s' % (VERSION, NAME, db_path))
    print('  清理 points 脏行 %d 条、messages 孤儿行 %d 条' % (
        len(log['cleaned_points']), len(log['cleaned_messages'])))
    for table in sorted(log['tables']):
        print('  %-26s %d' % (table, log['tables'][table]))
    return 0


def make_baseline(db_path, output=None, force=False):
    """生成基线库：灌完内容的库另存一份，删掉迁移记录表，让它可以被再次迁移。

    为什么删掉 schema_migrations：基线库是「新环境的起点」，不是「已迁移完的库」。
    留着记录会让任何在它上面跑迁移的尝试直接跳过，新环境就永远拿不到后续迁移。
    删掉之后，基线库回到「表在、内容在、没有迁移历史」的状态，与现库迁移前的
    形状一致，任何迁移脚本都能在它身上从头跑。
    """
    import shutil
    import sqlite3

    target = output or os.path.join(REPO_ROOT, 'data', 'baseline.db')
    if os.path.abspath(target) == os.path.abspath(db_path):
        raise SystemExit('基线库不能覆盖目标库：%s' % target)

    log = migrate(db_path, force=force)
    if log is None:
        print('目标库 %s 已迁移过，直接复制为基线库。' % db_path)
    else:
        print('目标库 %s 已灌入内容。' % db_path)

    os.makedirs(os.path.dirname(target), exist_ok=True)
    for suffix in ('', '-wal', '-shm', '-journal'):
        candidate = target + suffix
        if os.path.exists(candidate):
            os.remove(candidate)
    shutil.copyfile(db_path, target)

    # 基线库是「迁移前的形状」：去掉 WAL 附属文件与迁移记录，让后续迁移能在它上面跑。
    conn = sqlite3.connect(target)
    conn.execute("PRAGMA journal_mode=DELETE")
    conn.execute("DELETE FROM schema_migrations WHERE version = ?", (VERSION,))
    conn.commit()
    conn.close()
    for suffix in ('-wal', '-shm', '-journal'):
        candidate = target + suffix
        if os.path.exists(candidate):
            os.remove(candidate)

    print('基线库已生成：%s（%.1f KB）' % (target, os.path.getsize(target) / 1024.0))
    print('注意：data/*.db 已被 .gitignore 忽略，基线库不入版本库；'
          '新环境用本命令重新生成。')
    return 0


if __name__ == '__main__':
    sys.exit(main())



