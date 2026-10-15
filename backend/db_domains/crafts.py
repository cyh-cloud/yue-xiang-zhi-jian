# -*- coding: utf-8 -*-
"""手工技艺域：技艺、步骤与采购指南的读取。

T08 从 domains/crafts/routes.py 的 CRAFTS_KNOWLEDGE 常量切到读库（ADR 0002）。
库里是**拆平**的四张表，本模块负责按原形状组装回去：

    crafts                      -> 技艺层（name/origin/history）
    craft_steps                 -> craft['steps']              （按 sort_order）
    craft_purchase_categories   -> purchase_guide['categories']（按 sort_order）
    craft_purchase_items        -> category['items']            （按 craft_id + category_key + sort_order）
    craft_budgets               -> purchase_guide['budget']     （一门技艺一行）

对外契约不变：get_crafts() 的字段与顺序、get_craft_detail() 的键集、
未知 id 返回 None（由路由翻成 200 + success=False）都与切库前逐字节一致。
"""

from db_connection import get_connection

# 本模块的数据归属这个能力域。backend/core/permissions.py 的 CAPABILITIES
# 与 tools/check_architecture.py（T02 起按能力表判权）都以此为准：谁 import
# 本模块，谁就必须持 craft.manage（读操作受 craft.read 管，该能力是空元组=公开）。
CAPABILITY = 'craft'

# 详情响应下发的键，顺序与切库前的 CRAFTS_KNOWLEDGE[cid] 一致。
# videos 与 level 不进这个列表：它们在库里没有对应列（T05 灌库时未迁，
# 见 migrations/0001_content_to_db.py），由路由层按固定口径补齐。
_DETAIL_FIELDS = ('name', 'origin', 'history')


# 列表层的产地口径。详情层 crafts.origin 是完整地名（「佛山石湾」），
# 而学员端列表卡一直只显示地级市（「佛山」）。这是同一个事实的两个粒度，
# 不是脏数据，故在读取侧按原口径收窄，不改库里的真值。
# 没有登记映射的技艺原样返回：不为凑格式把地名改短。
_LIST_ORIGIN = {
    'ceramics': u'佛山',
}


def get_crafts():
    """技艺列表：id / name / origin 三列，顺序与切库前一致。

    origin 取列表层口径（见 _LIST_ORIGIN）；难度分级 level 不在库里
    （crafts.level 全是空串，T05 未迁），由路由层补，这里不造默认值。
    """
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, name, origin FROM crafts ORDER BY sort_order, id").fetchall()
    conn.close()
    return [{'id': r['id'], 'name': r['name'],
             'origin': _LIST_ORIGIN.get(r['id'], r['origin'])} for r in rows]


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
