# -*- coding: utf-8 -*-
"""手工技艺域：技艺、步骤与采购指南的读取与维护。

T08 从 domains/crafts/routes.py 的 CRAFTS_KNOWLEDGE 常量切到读库（ADR 0002）。
库里是**拆平**的四张表，本模块负责按原形状组装回去：

    crafts                      -> 技艺层（name/origin/history）
    craft_steps                 -> craft['steps']              （按 sort_order）
    craft_purchase_categories   -> purchase_guide['categories']（按 sort_order）
    craft_purchase_items        -> category['items']            （按 craft_id + category_key + sort_order）
    craft_budgets               -> purchase_guide['budget']     （一门技艺一行）

对外契约不变：get_crafts() 的字段与顺序、get_craft_detail() 的键集、
未知 id 返回 None（由路由翻成 200 + success=False）都与切库前逐字节一致。

T15 补写侧（运营后台）。采购指南的三层嵌套在库里是四张平表，写侧也按
平表收口：分类与条目各走一张表，预算单独一张（一门技艺一行，所以 craft_id
是主键，「改」与「建」是同一句 INSERT OR REPLACE）。写侧不碰 sort_order
之外的口径，顺序由调用方给的 sort_order 决定，读侧按它重组回三层嵌套。
"""

from db_connection import get_connection

# 本模块的数据归属这个能力域。backend/core/permissions.py 的 CAPABILITIES
# 与 tools/check_architecture.py（T02 起按能力表判权）都以此为准：谁 import
# 本模块，谁就必须持 craft.manage（读操作受 craft.read 管，该能力是空元组=公开）。
CAPABILITY = 'craft'

# 详情响应下发的键，顺序与切库前的 CRAFTS_KNOWLEDGE[cid] 一致。
# videos 不在这个列表里：库里没有视频表，运营补上之前详情不下发这个键。
_DETAIL_FIELDS = ('name', 'origin', 'history')


# 列表层的产地口径。详情层 crafts.origin 是完整地名（「佛山石湾」），
# 而学员端列表卡一直只显示地级市（「佛山」）。这是同一个事实的两个粒度，
# 不是脏数据，故在读取侧按原口径收窄，不改库里的真值。
# 没有登记映射的技艺原样返回：不为凑格式把地名改短。
_LIST_ORIGIN = {
    'ceramics': u'佛山',
}

# ---- 写侧列白名单（T15）----
# id 一律不在其中：主键由调用方给出（delete_* 按 id 定位），update 改不到它。
# 与 farming / pest 两个域同一口径：None 表示「不碰这一列」，与「置空」两回事。
CRAFT_FIELDS = ('name', 'origin', 'history', 'level', 'sort_order')
STEP_FIELDS = ('title', 'desc', 'tips', 'sort_order')
CATEGORY_FIELDS = ('label', 'desc', 'sort_order')
ITEM_FIELDS = ('name', 'price', 'spec', 'tip', 'where', 'sort_order')
BUDGET_FIELDS = ('starter', 'advanced', 'buying_tips')


def _pick(fields, allowed):
    """按白名单挑出要写的列。None 表示「不碰这一列」，与「置空」是两件事。"""
    return {k: v for k, v in fields.items() if k in allowed and v is not None}


def _require_text(value, label):
    text = (value or '').strip() if isinstance(value, str) else str(value or '')
    text = text.strip()
    if not text:
        raise ValueError('%s不能为空' % label)
    return text


def _optional_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _require_craft(conn, craft_id):
    row = conn.execute("SELECT id FROM crafts WHERE id = ?", (craft_id,)).fetchone()
    if row is None:
        raise ValueError(u'技艺不存在：%s' % craft_id)


def _require_category(conn, craft_id, category_key):
    row = conn.execute(
        "SELECT key FROM craft_purchase_categories WHERE craft_id = ? AND key = ?",
        (craft_id, category_key)).fetchone()
    if row is None:
        raise ValueError(u'采购分类不存在：%s' % category_key)


def get_crafts():
    """技艺列表：id / name / origin / level，顺序与切库前一致。

    origin 取列表层口径（见 _LIST_ORIGIN）；level 直接取库里的 crafts.level，
    该列目前是空串（T05 灌库时未迁该值），运营在后台补等级后这里立即生效。
    """
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, name, origin, level FROM crafts ORDER BY sort_order, id").fetchall()
    conn.close()
    return [{'id': r['id'], 'name': r['name'],
             'origin': _LIST_ORIGIN.get(r['id'], r['origin']),
             'level': r['level'] or ''} for r in rows]


def get_craft_detail(craft_id):
    """单门技艺的完整内容：steps + purchase_guide 原样组装。不存在返回 None。"""
    conn = get_connection()
    row = conn.execute(
        "SELECT id, name, origin, history FROM crafts WHERE id = ?",
        (craft_id,)).fetchone()
    if row is None:
        conn.close()
        return None

    craft = {field: row[field] for field in _DETAIL_FIELDS}
    craft['steps'] = [dict(r) for r in conn.execute(
        'SELECT title, "desc", tips FROM craft_steps '
        'WHERE craft_id = ? ORDER BY sort_order', (craft_id,)).fetchall()]
    craft['purchase_guide'] = _purchase_guide(conn, craft_id)
    conn.close()
    return craft


def _purchase_guide(conn, craft_id):
    """采购指南：三层嵌套按原形状组装。

    categories 的 items 用一次查询按 craft_id 全取回来再分组，避免每个分类一次
    往返（三层嵌套逐类查询会让请求数随分类数线性增长）。条目按
    (category_key, sort_order) 归位，保证「分类内顺序」与「条目在分类内的位置」
    都与拆平前一致。
    """
    budget = conn.execute(
        "SELECT starter, advanced, buying_tips FROM craft_budgets WHERE craft_id = ?",
        (craft_id,)).fetchone()
    if budget is None:
        return None

    categories = [dict(r) for r in conn.execute(
        'SELECT key, label, "desc" FROM craft_purchase_categories '
        'WHERE craft_id = ? ORDER BY sort_order', (craft_id,)).fetchall()]
    items = {}
    for row in conn.execute(
            'SELECT category_key, name, price, spec, tip, "where" '
            'FROM craft_purchase_items WHERE craft_id = ? '
            'ORDER BY category_key, sort_order', (craft_id,)).fetchall():
        items.setdefault(row['category_key'], []).append(
            {k: row[k] for k in ('name', 'price', 'spec', 'tip', 'where')})

    return {
        'budget': {
            'starter': budget['starter'],
            'advanced': budget['advanced'],
        },
        'buying_tips': budget['buying_tips'],
        'categories': [
            {
                'key': c['key'],
                'label': c['label'],
                'desc': c['desc'],
                'items': items.get(c['key'], []),
            }
            for c in categories
        ],
    }


# ==================== 运营维护（写侧，T15） ====================
# 三条口径与 farming / pest 两个域一致：
#
# 1. 列名白名单：update_* 只收 fields 里登记过的列，未知键一律忽略，
#    客户端改不到 id，也不必为每个字段写一个参数；
# 2. 校验归路由层，写侧只保证落库形状合法：缺了渲染不出来的字段直接
#    ValueError，由路由转 400；
# 3. 本域没有跨域删除：craft_* 五张表全部由外键级联兜住
#    （foreign_keys=ON），所以不需要「先 commit 再删别人」的顺序，
#    也不需要 reviews 域参与 —— 技艺内容不送审。


# ---- 技艺 ----

def create_craft(craft_id, name, **fields):
    """新增一门技艺，返回 craft_id（字符串主键由调用方给出）。"""
    craft_id = (craft_id or '').strip()
    name = (name or '').strip()
    if not craft_id:
        raise ValueError(u'技艺 id 不能为空')
    if not name:
        raise ValueError(u'技艺名称不能为空')
    values = _pick(fields, CRAFT_FIELDS)
    values.update({'id': craft_id, 'name': name})
    # 列名走双引号：desc / where 是 SQL 关键字，裸拼会语法错误
    columns = ', '.join('"%s"' % column for column in values)
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO crafts (%s) VALUES (%s)"
            % (columns, ', '.join('?' * len(values))), list(values.values()))
        conn.commit()
    finally:
        conn.close()
    return craft_id


def update_craft(craft_id, **fields):
    """按白名单改一门技艺。字段全是 None 时不动库，返回是否真的改了。"""
    updates = _pick(fields, CRAFT_FIELDS)
    if 'name' in updates:
        updates['name'] = (updates['name'] or '').strip()
    if 'name' in updates and not updates['name']:
        raise ValueError(u'技艺名称不能为空')
    if not updates:
        return False
    # 列名走双引号：desc / where 是 SQL 关键字，裸拼进 SET 子句会语法错误
    set_clause = ', '.join('"%s"=?' % column for column in updates)
    conn = get_connection()
    try:
        cur = conn.execute("UPDATE crafts SET %s WHERE id=?" % set_clause,
                           list(updates.values()) + [craft_id])
        changed = cur.rowcount
        conn.commit()
    finally:
        conn.close()
    return changed > 0


def delete_craft(craft_id):
    """删除技艺。步骤、采购指南（三张表）由外键级联删除。"""
    conn = get_connection()
    try:
        cur = conn.execute("DELETE FROM crafts WHERE id = ?", (craft_id,))
        deleted = cur.rowcount
        conn.commit()
    finally:
        conn.close()
    return deleted > 0


def get_craft_row(craft_id):
    """按 id 取一行技艺（含 level / sort_order），不存在返回 None。"""
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM crafts WHERE id = ?", (craft_id,)).fetchone()
    finally:
        conn.close()
    return dict(row) if row else None


# ---- 后台列表用的读取（T15）----
# 与前台 get_craft_detail 分开的理由：那个函数是对外契约，键集被快照测试
# 逐字节锁死（tests/test_crafts_dialect_snapshot.py），不能往里加 rowid。
# 后台要的是「哪一行」：craft_steps / craft_purchase_items 没有显式主键
# （schema 里只有外键，见 backend/db_schema.py），定位只能靠 rowid。
# 表不是 WITHOUT ROWID，所以 rowid 稳定可用；删行后 SQLite 不复用同一 rowid。

def get_craft_steps(craft_id):
    """一门技艺的步骤，带 rowid（后台编辑用）。顺序与前台一致。"""
    conn = get_connection()
    try:
        rows = conn.execute(
            'SELECT rowid AS id, title, "desc", tips, sort_order FROM craft_steps '
            'WHERE craft_id = ? ORDER BY sort_order, rowid', (craft_id,)).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def get_craft_purchase_categories(craft_id):
    """采购分类，带 craft_id + key（后台编辑用）。"""
    conn = get_connection()
    try:
        rows = conn.execute(
            'SELECT craft_id, key, label, "desc", sort_order '
            'FROM craft_purchase_categories WHERE craft_id = ? '
            'ORDER BY sort_order, key', (craft_id,)).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def get_craft_purchase_items(craft_id, category_key=None):
    """采购条目，带 rowid（后台编辑用）。可按分类过滤。"""
    conn = get_connection()
    try:
        sql = ('SELECT rowid AS id, craft_id, category_key, name, price, spec, tip, '
               '"where", sort_order FROM craft_purchase_items WHERE craft_id = ?')
        params = [craft_id]
        if category_key:
            sql += ' AND category_key = ?'
            params.append(category_key)
        sql += ' ORDER BY category_key, sort_order, rowid'
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def get_craft_budget(craft_id):
    """一门技艺的采购预算行，不存在返回 None。"""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM craft_budgets WHERE craft_id = ?", (craft_id,)).fetchone()
    finally:
        conn.close()
    return dict(row) if row else None


# ---- 技艺步骤 ----

def create_craft_step(craft_id, title, **fields):
    """新增一个步骤，返回新 id。"""
    craft_id = (craft_id or '').strip()
    title = (title or '').strip()
    if not title:
        raise ValueError(u'步骤标题不能为空')
    values = _pick(fields, STEP_FIELDS)
    values.update({'craft_id': craft_id, 'title': title})
    # 列名走双引号：desc / where 是 SQL 关键字，裸拼会语法错误
    columns = ', '.join('"%s"' % column for column in values)
    conn = get_connection()
    try:
        _require_craft(conn, craft_id)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO craft_steps (%s) VALUES (%s)"
            % (columns, ', '.join('?' * len(values))), list(values.values()))
        step_id = cursor.lastrowid
        conn.commit()
    finally:
        conn.close()
    return step_id


def update_craft_step(step_id, **fields):
    """按白名单改一个步骤。"""
    updates = _pick(fields, STEP_FIELDS)
    if 'title' in updates:
        updates['title'] = (updates['title'] or '').strip()
    if 'title' in updates and not updates['title']:
        raise ValueError(u'步骤标题不能为空')
    if not updates:
        return False
    # 列名走双引号：desc / where 是 SQL 关键字，裸拼进 SET 子句会语法错误
    set_clause = ', '.join('"%s"=?' % column for column in updates)
    conn = get_connection()
    try:
        cur = conn.execute("UPDATE craft_steps SET %s WHERE rowid=?" % set_clause,
                           list(updates.values()) + [step_id])
        changed = cur.rowcount
        conn.commit()
    finally:
        conn.close()
    return changed > 0


def delete_craft_step(step_id):
    """删除一个步骤。返回是否真的删掉了行。"""
    conn = get_connection()
    try:
        cur = conn.execute("DELETE FROM craft_steps WHERE rowid = ?", (step_id,))
        deleted = cur.rowcount
        conn.commit()
    finally:
        conn.close()
    return deleted > 0


# ---- 采购指南：分类 ----

def create_craft_purchase_category(craft_id, key, **fields):
    """新增一个采购分类，返回 (craft_id, key)。"""
    craft_id = (craft_id or '').strip()
    key = (key or '').strip()
    if not key:
        raise ValueError(u'分类 key 不能为空')
    values = _pick(fields, CATEGORY_FIELDS)
    values.update({'craft_id': craft_id, 'key': key})
    # 列名走双引号：desc / where 是 SQL 关键字，裸拼会语法错误
    columns = ', '.join('"%s"' % column for column in values)
    conn = get_connection()
    try:
        _require_craft(conn, craft_id)
        conn.execute(
            "INSERT INTO craft_purchase_categories (%s) VALUES (%s)"
            % (columns, ', '.join('?' * len(values))), list(values.values()))
        conn.commit()
    finally:
        conn.close()
    return {'craft_id': craft_id, 'key': key}


def update_craft_purchase_category(craft_id, key, **fields):
    """按白名单改一个采购分类。"""
    updates = _pick(fields, CATEGORY_FIELDS)
    if 'label' in updates:
        updates['label'] = (updates['label'] or '').strip()
    if not updates:
        return False
    # 列名走双引号：desc / where 是 SQL 关键字，裸拼进 SET 子句会语法错误
    set_clause = ', '.join('"%s"=?' % column for column in updates)
    conn = get_connection()
    try:
        cur = conn.execute(
            "UPDATE craft_purchase_categories SET %s WHERE craft_id=? AND key=?"
            % set_clause, list(updates.values()) + [craft_id, key])
        changed = cur.rowcount
        conn.commit()
    finally:
        conn.close()
    return changed > 0


def delete_craft_purchase_category(craft_id, key):
    """删除一个采购分类，连同它下面的条目。

    为什么要在本域显式删条目、而不是靠外键级联：craft_purchase_items 的外键
    只指向 crafts(id)（见 backend/db_schema.py），不指向
    craft_purchase_categories —— 后者的主键是复合键 (craft_id, key)，
    SQLite 的复合外键要求两列一起引用，schema 里没有这一条。
    只删分类行的话，它的条目会变成「没有分类归属」的孤儿：读侧按
    items.get(c['key'], []) 分组，孤儿掉出所有分类，学员端看不到，
    而运营以为连内容一起删干净了。

    两步在同一个连接同一个事务里，要么都删要么都不删。
    """
    conn = get_connection()
    try:
        conn.execute("DELETE FROM craft_purchase_items WHERE craft_id = ? AND category_key = ?",
                     (craft_id, key))
        cur = conn.execute(
            "DELETE FROM craft_purchase_categories WHERE craft_id = ? AND key = ?",
            (craft_id, key))
        deleted = cur.rowcount
        conn.commit()
    finally:
        conn.close()
    return deleted > 0


# ---- 采购指南：条目 ----

def create_craft_purchase_item(craft_id, category_key, name, **fields):
    """新增一个采购条目，返回新 id。"""
    craft_id = (craft_id or '').strip()
    category_key = (category_key or '').strip()
    name = (name or '').strip()
    if not name:
        raise ValueError(u'物品名称不能为空')
    values = _pick(fields, ITEM_FIELDS)
    values.update({'craft_id': craft_id, 'category_key': category_key,
                   'name': name})
    # 列名走双引号：desc / where 是 SQL 关键字，裸拼会语法错误
    columns = ', '.join('"%s"' % column for column in values)
    conn = get_connection()
    try:
        _require_category(conn, craft_id, category_key)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO craft_purchase_items (%s) VALUES (%s)"
            % (columns, ', '.join('?' * len(values))), list(values.values()))
        item_id = cursor.lastrowid
        conn.commit()
    finally:
        conn.close()
    return item_id


def update_craft_purchase_item(item_id, **fields):
    """按白名单改一个采购条目。"""
    updates = _pick(fields, ITEM_FIELDS)
    if 'name' in updates:
        updates['name'] = (updates['name'] or '').strip()
    if 'name' in updates and not updates['name']:
        raise ValueError(u'物品名称不能为空')
    if not updates:
        return False
    # 列名走双引号：desc / where 是 SQL 关键字，裸拼进 SET 子句会语法错误
    set_clause = ', '.join('"%s"=?' % column for column in updates)
    conn = get_connection()
    try:
        cur = conn.execute("UPDATE craft_purchase_items SET %s WHERE rowid=?" % set_clause,
                           list(updates.values()) + [item_id])
        changed = cur.rowcount
        conn.commit()
    finally:
        conn.close()
    return changed > 0


def delete_craft_purchase_item(item_id):
    """删除一个采购条目。返回是否真的删掉了行。"""
    conn = get_connection()
    try:
        cur = conn.execute(
            "DELETE FROM craft_purchase_items WHERE rowid = ?", (item_id,))
        deleted = cur.rowcount
        conn.commit()
    finally:
        conn.close()
    return deleted > 0


# ---- 采购指南：预算 ----

def set_craft_budget(craft_id, **fields):
    """写入 / 覆盖一门技艺的采购预算。craft_id 是主键，所以「改」与「建」是同一句。

    buying_tips 与 starter / advanced 同级：前台 purchase_guide 把它与 budget
    并列展示，缺了它前端会显示空标题。缺列时按空串补，不留 NULL。
    """
    craft_id = (craft_id or '').strip()
    values = _pick(fields, BUDGET_FIELDS)
    for column in BUDGET_FIELDS:
        values.setdefault(column, '')
    values.update({'craft_id': craft_id})
    # 列名走双引号：desc / where 是 SQL 关键字，裸拼会语法错误
    columns = ', '.join('"%s"' % column for column in values)
    conn = get_connection()
    try:
        _require_craft(conn, craft_id)
        conn.execute(
            "INSERT OR REPLACE INTO craft_budgets (%s) VALUES (%s)"
            % (columns, ', '.join('?' * len(values))), list(values.values()))
        conn.commit()
    finally:
        conn.close()
    return craft_id


def delete_craft_budget(craft_id):
    """删掉一门技艺的采购预算。返回是否真的删掉了行。"""
    conn = get_connection()
    try:
        cur = conn.execute("DELETE FROM craft_budgets WHERE craft_id = ?", (craft_id,))
        deleted = cur.rowcount
        conn.commit()
    finally:
        conn.close()
    return deleted > 0
