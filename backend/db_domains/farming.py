#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""农业培训域：农时日历的作物、生育期、农事任务、订阅与提醒。

T05 从 database.py 按领域切分抽出，SQL 语义与返回结构与拆分前逐字节一致。
T06 把分类标签与两个纯函数收进本模块：分类标签改读 farming_categories 表
（原 get_farming_category_labels 从代码常量现取，
是当时唯一的代码常量残留），_month_in_phase 与 _farming_task_brief 从
domains/agriculture/calendar_data.py 移入，一并列在 __all__ 里。
"""

import sqlite3
from db_connection import get_connection

# 本模块的数据归属这个能力域。backend/core/permissions.py 的 CAPABILITIES
# 与 tools/check_architecture.py（T02 起按能力表判权）都以此为准：谁 import
# 本模块，谁就必须持 farming.manage（读操作受 farming.read 管）。
CAPABILITY = 'farming'

__all__ = [
    'CAPABILITY',
    'clear_farming_reminder_log', 'get_due_farming_tasks',
    'get_farming_categories', 'get_farming_category_labels',
    'get_farming_phenophases', 'get_farming_product', 'get_farming_products',
    'get_farming_source_map', 'get_farming_sources', 'get_farming_subscribers',
    'get_farming_subscriptions', 'get_farming_task_by_id', 'get_farming_tasks',
    'has_farming_reminder_sent', 'is_farming_subscribed',
    'mark_farming_reminder_sent', 'set_farming_subscription',
    'month_in_phase', 'farming_task_brief',
    'create_farming_category', 'delete_farming_category',
    'update_farming_category', 'create_farming_phenophase',
    'update_farming_phenophase', 'delete_farming_phenophase',
    'get_farming_phenophase_by_id', 'create_farming_source',
    'update_farming_source', 'delete_farming_source',
    'get_farming_source_by_key', 'create_farming_product',
    'update_farming_product', 'delete_farming_product', 'create_farming_task',
    'update_farming_task', 'delete_farming_task', 'verify_farming_task',
    'get_farming_overdue_tasks',
]


def get_farming_products(active_only=True):
    """返回农产品目录列表"""
    conn = get_connection()
    sql = "SELECT * FROM farming_products"
    if active_only:
        sql += " WHERE is_active = 1"
    sql += " ORDER BY sort_order, id"
    rows = [dict(r) for r in conn.execute(sql).fetchall()]
    conn.close()
    return rows

def get_farming_product(product_id):
    """按 id 取单个农产品（含停用状态），不存在返回 None"""
    conn = get_connection()
    row = conn.execute("SELECT * FROM farming_products WHERE id = ?", (product_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def get_farming_sources():
    """返回数据来源登记表（key -> 来源方向）。doc_no 可能为「待核」。"""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM farming_sources ORDER BY sort_order, key").fetchall()
    except sqlite3.OperationalError:
        rows = []          # 旧库尚未建表时降级为空
    conn.close()
    return [dict(r) for r in rows]

def get_farming_source_map():
    """返回 {source_key: 来源对象} 映射，供接口把任务的 source_key 展开成可读信息。"""
    return {s['key']: s for s in get_farming_sources()}

def get_farming_category_labels():
    """返回 {分类key: 中文标签}，来自 farming_categories 表。"""
    return {row['key']: row['label'] for row in get_farming_categories()}


def get_farming_categories():
    """返回分类标签行（按 sort_order、key 排序）。"""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT key, label FROM farming_categories ORDER BY sort_order, key").fetchall()
    except sqlite3.OperationalError:
        rows = []          # 旧库尚未建表时降级为空
    finally:
        conn.close()
    return [dict(r) for r in rows]


def month_in_phase(month, start_month, end_month):
    """物候期命中判定。start_month > end_month 表示跨年区间（如 11月 → 次年1月）。"""
    if start_month <= end_month:
        return start_month <= month <= end_month
    return month >= start_month or month <= end_month


def farming_task_brief(task):
    """把任务压成「05日 花前病虫害预防」的一行摘要，供提醒文案使用。"""
    md = (task.get('task_md') or '')
    day = None
    if '-' in md:
        try:
            day = int(md.split('-', 1)[1])
        except (ValueError, IndexError):
            day = None
    return ('%d日 %s' % (day, task.get('title', ''))) if day else task.get('title', '')

def get_farming_phenophases(product_id=None):
    """返回物候期列表（可按产品过滤）"""
    conn = get_connection()
    if product_id:
        rows = conn.execute(
            "SELECT * FROM farming_phenophases WHERE product_id = ? ORDER BY sort_order, id",
            (product_id,)).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM farming_phenophases ORDER BY product_id, sort_order, id").fetchall()
    out = [dict(r) for r in rows]
    conn.close()
    return out

def get_farming_tasks(product_id, month=None):
    """返回某产品的农事任务（可按月过滤）。phase 以名称形式一并返回，便于前端直接渲染。"""
    conn = get_connection()
    sql = """SELECT t.*, p.name AS phase_name, p.color AS phase_color
             FROM farming_tasks t
             LEFT JOIN farming_phenophases p ON p.id = t.phase_id
             WHERE t.product_id = ? AND t.is_active = 1"""
    params = [product_id]
    if month is not None:
        sql += " AND t.month = ?"
        params.append(int(month))
    sql += " ORDER BY t.month, t.sort_order, t.id"
    rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
    conn.close()
    return rows

def get_farming_task_by_id(task_id):
    """按 id 取单条任务（含物候期名称）"""
    conn = get_connection()
    row = conn.execute(
        """SELECT t.*, p.name AS phase_name, p.color AS phase_color
           FROM farming_tasks t
           LEFT JOIN farming_phenophases p ON p.id = t.phase_id
           WHERE t.id = ?""", (task_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


# ---------- 订阅 ----------

def get_farming_subscriptions(user_id):
    """返回某用户订阅的产品 id 列表"""
    conn = get_connection()
    rows = conn.execute(
        "SELECT product_id FROM farming_subscriptions WHERE user_id = ? ORDER BY id",
        (user_id,)).fetchall()
    conn.close()
    return [r[0] for r in rows]

def is_farming_subscribed(user_id, product_id):
    conn = get_connection()
    row = conn.execute(
        "SELECT 1 FROM farming_subscriptions WHERE user_id = ? AND product_id = ? LIMIT 1",
        (user_id, product_id)).fetchone()
    conn.close()
    return row is not None

def set_farming_subscription(user_id, product_id, subscribe=True):
    """订阅/退订。返回操作后的订阅状态。"""
    conn = get_connection()
    if subscribe:
        conn.execute(
            "INSERT OR IGNORE INTO farming_subscriptions (user_id, product_id) VALUES (?, ?)",
            (user_id, product_id))
    else:
        conn.execute(
            "DELETE FROM farming_subscriptions WHERE user_id = ? AND product_id = ?",
            (user_id, product_id))
    conn.commit()
    conn.close()
    return bool(subscribe)

def get_farming_subscribers(product_id):
    """返回订阅某产品的用户 id 列表（供管理/推送使用）"""
    conn = get_connection()
    rows = conn.execute(
        "SELECT user_id FROM farming_subscriptions WHERE product_id = ? ORDER BY id",
        (product_id,)).fetchall()
    conn.close()
    return [r[0] for r in rows]


# ---------- 提醒补发 ----------

def has_farming_reminder_sent(user_id, product_id, period):
    conn = get_connection()
    row = conn.execute(
        """SELECT 1 FROM farming_reminder_log
           WHERE user_id = ? AND product_id = ? AND period = ? LIMIT 1""",
        (user_id, product_id, period)).fetchone()
    conn.close()
    return row is not None

def mark_farming_reminder_sent(user_id, product_id, period):
    conn = get_connection()
    conn.execute(
        """INSERT OR IGNORE INTO farming_reminder_log (user_id, product_id, period)
           VALUES (?, ?, ?)""",
        (user_id, product_id, period))
    conn.commit()
    conn.close()

def clear_farming_reminder_log(user_id, product_id, period=None):
    """清除某用户在某作物上的提醒发送记录。

    退订时调用：幂等键是 (user_id, product_id, period)，日志一旦存在就永久跳过当期，
    若退订时不清理，用户「退订 → 重新订阅」在当月将静默收不到提醒。
    清除后语义为「重新订阅 = 重新开始接收」。
    """
    conn = get_connection()
    if period is None:
        conn.execute(
            "DELETE FROM farming_reminder_log WHERE user_id = ? AND product_id = ?",
            (user_id, product_id))
    else:
        conn.execute(
            "DELETE FROM farming_reminder_log WHERE user_id = ? AND product_id = ? AND period = ?",
            (user_id, product_id, period))
    conn.commit()
    conn.close()

def get_due_farming_tasks(product_id, year, month, until_day=None):
    """取某产品在指定年月、且已到期的任务。

    - until_day 为空 -> 该月全部任务（含尚未指定日期的，供列表展示）
    - until_day 有值 -> 仅 task_md 落在 1..until_day 之间的任务（供补发提醒，避免预告未来任务）
    """
    tasks = get_farming_tasks(product_id, month=month)
    if until_day is None:
        return tasks
    prefix = '%02d-' % month
    out = []
    for t in tasks:
        md = t.get('task_md')
        if not md or not md.startswith(prefix):
            continue
        try:
            day = int(md[3:5])
        except ValueError:
            continue
        if day <= int(until_day):
            out.append(t)
    return out


# ==================== 运营维护（写侧，T14） ====================
# 下面这批函数服务运营后台（domains/operator）。三条口径：
#
# 1. 列名白名单：update_* 只收 fields 字典里登记过的列，未知键一律忽略。
#    客户端改不到 id / created_at，也不必为每个字段写一个参数。
# 2. 校验归路由层，写侧只保证落库的形状合法：任务缺 product_id / title / month
#    这类缺了就渲染不出来的字段直接 ValueError，由路由转 400。
# 3. 本域没有跨域删除：farming_* 全部由外键级联兜住（foreign_keys=ON），
#    所以这里不需要「先 commit 再删别人」的顺序，也不需要 reviews 域参与
#    —— farming 的内容不送审。

# 任务表可写的列。id / created_at / verified_* 不在其中：id 由自增分配，
# verified_* 只能经 verify_farming_task 改（要留复核人）。
_TASK_FIELDS = ('product_id', 'phase_id', 'title', 'category', 'priority',
                'task_md', 'month', 'icon', 'description', 'tip', 'source_key',
                'date_basis', 'is_verified', 'is_active', 'sort_order')
_PHASE_FIELDS = ('product_id', 'name', 'start_month', 'end_month', 'color',
                 'description', 'sort_order')
_PRODUCT_FIELDS = ('name', 'icon', 'summary', 'region', 'sort_order', 'is_active')
_SOURCE_FIELDS = ('name', 'org', 'doc_type', 'doc_no', 'url', 'sort_order')
_CATEGORY_FIELDS = ('label', 'color', 'sort_order')

# 复核过期阈值（天）。「半年前核的、该重新核了」按 183 天算：半年按 365/2 取整，
# 不按 30*6，否则 2 月核的到 8 月就该重核，比「半年」短了 12 天。
REVIEW_STALE_DAYS = 183


def _pick(fields, allowed):
    """按白名单挑出要写的列。None 表示「不碰这一列」，与「置空」是两件事。"""
    return {k: v for k, v in fields.items() if k in allowed and v is not None}


def _int_or(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


# ---- 农事任务 ----

def create_farming_task(product_id, title, category, month, **fields):
    """新增一条农事任务，返回新 id。"""
    product_id = (product_id or '').strip()
    title = (title or '').strip()
    category = (category or '').strip()
    if not product_id:
        raise ValueError('缺少 product_id')
    if not title:
        raise ValueError('任务标题不能为空')
    if not category:
        raise ValueError('缺少 category')
    month = _int_or(month, None)
    if month is None or month < 1 or month > 12:
        raise ValueError('month 需为 1 到 12 的整数')

    values = _pick(fields, _TASK_FIELDS)
    values.update({'product_id': product_id, 'title': title,
                   'category': category, 'month': month})
    columns = ', '.join(values)
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO farming_tasks (%s) VALUES (%s)"
        % (columns, ', '.join('?' * len(values))), list(values.values()))
    task_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return task_id


def update_farming_task(task_id, **fields):
    """按白名单改一条农事任务。字段全是 None 时不动库，返回是否真的改了。"""
    updates = _pick(fields, _TASK_FIELDS)
    if 'product_id' in updates:
        updates['product_id'] = (updates['product_id'] or '').strip()
    if 'title' in updates:
        updates['title'] = (updates['title'] or '').strip()
    if 'category' in updates:
        updates['category'] = (updates['category'] or '').strip()
    if not updates:
        return False
    # 只校验**这次传进来的**字段：PUT 是局部改，运营改一个标题不该被要求
    # 把整条任务重填一遍，所以不能拿「没传的字段也是空」当错误。
    for key in ('product_id', 'title', 'category'):
        if key in updates and not updates[key]:
            raise ValueError('%s 不允许置空' % key)
    if 'month' in updates:
        month = _int_or(updates['month'], None)
        if month is None or month < 1 or month > 12:
            raise ValueError('month 需为 1 到 12 的整数')
        updates['month'] = month
    if 'task_md' in updates:
        updates['task_md'] = (updates['task_md'] or '').strip()
    set_clause = ', '.join('%s=?' % column for column in updates)
    conn = get_connection()
    cur = conn.execute("UPDATE farming_tasks SET %s WHERE id=?"
                       % set_clause, list(updates.values()) + [task_id])
    changed = cur.rowcount
    conn.commit()
    conn.close()
    return changed > 0


def delete_farming_task(task_id):
    """删除一条农事任务。返回是否真的删掉了行。"""
    conn = get_connection()
    cur = conn.execute("DELETE FROM farming_tasks WHERE id = ?", (task_id,))
    deleted = cur.rowcount
    conn.commit()
    conn.close()
    return deleted > 0


def verify_farming_task(task_id, verifier):
    """标记已复核：写 is_verified=1 与 verified_by / verified_at（当前登录用户）。

    verified_at 走 SQLite 的 localtime，与库里其它时间列同一口径
    （datetime('now','localtime')），不引入 Python 侧时钟，避免两台机器时区不一致。
    """
    verifier = (verifier or '').strip()
    if not verifier:
        raise ValueError('复核人不能为空')
    conn = get_connection()
    cur = conn.execute(
        "UPDATE farming_tasks SET is_verified = 1, verified_by = ?, "
        "verified_at = datetime('now','localtime') WHERE id = ?", (verifier, task_id))
    updated = cur.rowcount
    conn.commit()
    conn.close()
    return updated > 0


def get_farming_overdue_tasks(days=REVIEW_STALE_DAYS, product_id=None):
    """复核超期的农事任务：超过 days 天没再核的，以及从未复核的。

    「半年前核的、该重新核了」的口径：verified_at 距今天超过 days 天算超期；
    verified_at 为空的（从未复核）同样该核，一并列出。按复核时间升序，
    让「最早该重核的」排在列表最上面。
    """
    conn = get_connection()
    sql = ("SELECT t.*, p.name AS phase_name, p.color AS phase_color "
           "FROM farming_tasks t "
           "LEFT JOIN farming_phenophases p ON p.id = t.phase_id "
           "WHERE t.is_active = 1 AND (t.verified_at = '' OR "
           "julianday('now', 'localtime') - julianday(t.verified_at) > ?)")
    params = [days]
    if product_id:
        sql += " AND t.product_id = ?"
        params.append(product_id)
    sql += " ORDER BY t.verified_at = '' DESC, t.verified_at"
    rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
    conn.close()
    return rows


# ---- 物候期 ----

# ---- 物候期 ----

def get_farming_phenophase_by_id(phase_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM farming_phenophases WHERE id = ?",
                       (phase_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def create_farming_phenophase(product_id, name, start_month, end_month, **fields):
    """新增物候期，返回新 id。"""
    product_id = (product_id or '').strip()
    name = (name or '').strip()
    if not product_id:
        raise ValueError('缺少 product_id')
    if not name:
        raise ValueError('物候期名称不能为空')
    start = _int_or(start_month, None)
    end = _int_or(end_month, None)
    for value in (start, end):
        if value is None or value < 1 or value > 12:
            raise ValueError('start_month / end_month 需为 1 到 12 的整数')

    values = _pick(fields, _PHASE_FIELDS)
    values.update({'product_id': product_id, 'name': name,
                   'start_month': start, 'end_month': end})
    columns = ', '.join(values)
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO farming_phenophases (%s) VALUES (%s)"
        % (columns, ', '.join('?' * len(values))), list(values.values()))
    phase_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return phase_id


def update_farming_phenophase(phase_id, **fields):
    updates = _pick(fields, _PHASE_FIELDS)
    if not updates:
        return False
    if 'name' in updates:
        updates['name'] = (updates['name'] or '').strip()
    if not updates.get('name'):
        raise ValueError('物候期名称不能为空')
    for key in ('start_month', 'end_month'):
        if key in updates:
            value = _int_or(updates[key], None)
            if value is None or value < 1 or value > 12:
                raise ValueError('%s 需为 1 到 12 的整数' % key)
            updates[key] = value
    set_clause = ', '.join('%s=?' % column for column in updates)
    conn = get_connection()
    cur = conn.execute("UPDATE farming_phenophases SET %s WHERE id=?"
                       % set_clause, list(updates.values()) + [phase_id])
    changed = cur.rowcount
    conn.commit()
    conn.close()
    return changed > 0


def delete_farming_phenophase(phase_id):
    """删除物候期。任务的 phase_id 由外键置 NULL，任务本身不随之消失。"""
    conn = get_connection()
    cur = conn.execute("DELETE FROM farming_phenophases WHERE id = ?", (phase_id,))
    deleted = cur.rowcount
    conn.commit()
    conn.close()
    return deleted > 0


# ---- 农产品目录 ----

def create_farming_product(product_id, name, **fields):
    """新增农产品，返回新 id（调用方给出的 slug）。"""
    product_id = (product_id or '').strip()
    name = (name or '').strip()
    if not product_id:
        raise ValueError('缺少 id')
    if not name:
        raise ValueError('作物名称不能为空')
    values = _pick(fields, _PRODUCT_FIELDS)
    values.update({'id': product_id, 'name': name})
    columns = ', '.join(values)
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO farming_products (%s) VALUES (%s)"
        % (columns, ', '.join('?' * len(values))), list(values.values()))
    conn.commit()
    conn.close()
    return product_id


def update_farming_product(product_id, **fields):
    updates = _pick(fields, _PRODUCT_FIELDS)
    if not updates:
        return False
    if 'name' in updates:
        updates['name'] = (updates['name'] or '').strip()
    if not updates.get('name'):
        raise ValueError('作物名称不能为空')
    set_clause = ', '.join('%s=?' % column for column in updates)
    conn = get_connection()
    cur = conn.execute("UPDATE farming_products SET %s WHERE id=?"
                       % set_clause, list(updates.values()) + [product_id])
    changed = cur.rowcount
    conn.commit()
    conn.close()
    return changed > 0


def delete_farming_product(product_id):
    """删除作物。物候期、任务、订阅、提醒日志由外键级联删除。"""
    conn = get_connection()
    cur = conn.execute("DELETE FROM farming_products WHERE id = ?", (product_id,))
    deleted = cur.rowcount
    conn.commit()
    conn.close()
    return deleted > 0


# ---- 来源登记 ----

def get_farming_source_by_key(key):
    conn = get_connection()
    row = conn.execute("SELECT * FROM farming_sources WHERE key = ?", (key,)).fetchone()
    conn.close()
    return dict(row) if row else None


def create_farming_source(key, name, **fields):
    key = (key or '').strip()
    name = (name or '').strip()
    if not key:
        raise ValueError('来源 key 不能为空')
    if not name:
        raise ValueError('来源名称不能为空')
    values = _pick(fields, _SOURCE_FIELDS)
    values.update({'key': key, 'name': name})
    columns = ', '.join(values)
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO farming_sources (%s) VALUES (%s)"
        % (columns, ', '.join('?' * len(values))), list(values.values()))
    conn.commit()
    conn.close()
    return key


def update_farming_source(key, **fields):
    updates = _pick(fields, _SOURCE_FIELDS)
    if not updates:
        return False
    if 'name' in updates:
        updates['name'] = (updates['name'] or '').strip()
    if not updates.get('name'):
        raise ValueError('来源名称不能为空')
    set_clause = ', '.join('%s=?' % column for column in updates)
    conn = get_connection()
    cur = conn.execute("UPDATE farming_sources SET %s WHERE key=?"
                       % set_clause, list(updates.values()) + [key])
    changed = cur.rowcount
    conn.commit()
    conn.close()
    return changed > 0


def delete_farming_source(key):
    """删除来源。任务的 source_key 不会被外键清掉（无 FK），由路由层先摘掉引用。"""
    conn = get_connection()
    cur = conn.execute("DELETE FROM farming_sources WHERE key = ?", (key,))
    deleted = cur.rowcount
    conn.commit()
    conn.close()
    return deleted > 0


# ---- 分类标签 ----

def create_farming_category(key, label, **fields):
    key = (key or '').strip()
    label = (label or '').strip()
    if not key:
        raise ValueError('分类 key 不能为空')
    if not label:
        raise ValueError('分类标签不能为空')
    values = _pick(fields, _CATEGORY_FIELDS)
    values.update({'key': key, 'label': label})
    columns = ', '.join(values)
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO farming_categories (%s) VALUES (%s)"
        % (columns, ', '.join('?' * len(values))), list(values.values()))
    conn.commit()
    conn.close()
    return key


def update_farming_category(key, **fields):
    updates = _pick(fields, _CATEGORY_FIELDS)
    if not updates:
        return False
    if 'label' in updates:
        updates['label'] = (updates['label'] or '').strip()
    if not updates.get('label'):
        raise ValueError('分类标签不能为空')
    set_clause = ', '.join('%s=?' % column for column in updates)
    conn = get_connection()
    cur = conn.execute("UPDATE farming_categories SET %s WHERE key=?"
                       % set_clause, list(updates.values()) + [key])
    changed = cur.rowcount
    conn.commit()
    conn.close()
    return changed > 0


def delete_farming_category(key):
    """删除分类标签。任务的 category 是裸字符串（无外键），由路由层先确认无引用。"""
    conn = get_connection()
    cur = conn.execute("DELETE FROM farming_categories WHERE key = ?", (key,))
    deleted = cur.rowcount
    conn.commit()
    conn.close()
    return deleted > 0
