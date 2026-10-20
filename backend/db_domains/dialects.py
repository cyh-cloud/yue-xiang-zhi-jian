# -*- coding: utf-8 -*-
"""方言知识域：方言、短语与快捷问题的读取与维护。

T08 从 domains/resources/dialect_voice.py 的 DIALECTS_DATA 常量切到读库（ADR 0002）。
库里是方言层 + 短语 + 快捷问题三张表，本模块负责按原形状组装回去：

    dialects                -> 方言层（含 features，JSON 文本解析成列表）
    dialect_phrases         -> dialect['phrases']          （按 sort_order）
    dialect_quick_questions -> dialect['quick_questions']  （按 sort_order）

对外契约不变：列表的顺序（dialects 按 sort_order）、详情的键与键序、
未知方言 id 退回粤语（由调用方按 None 处理）都与切库前逐字节一致。

T15 补写侧（运营后台）。features 列存 JSON 文本，写侧只接受数组，
空数组写 '[]'：与读侧 _decode_features 对称，一条坏 JSON 会被静默读成
空列表，「运营以为自己写了特色标签」这种事看不出痕迹。
"""

import json

from db_connection import get_connection

# 本模块的数据归属这个能力域。backend/core/permissions.py 的 CAPABILITIES
# 与 tools/check_architecture.py（T02 起按能力表判权）都以此为准：谁 import
# 本模块，谁就必须持 dialect.manage（读操作受 dialect.read 管，该能力是空元组=公开）。
CAPABILITY = 'dialect'

# 方言列表与详情共用的摘要字段。详情额外下发问候语、短语与快捷问题。
_SUMMARY_FIELDS = ('id', 'name', 'region', 'emoji', 'areas', 'speakers')


def _decode_features(raw):
    """features 列存的是 JSON 文本，读侧解析回列表。

    解析失败（脏数据）时返回空列表而不是抛错：这一列只驱动前端的特色标签，
    一条坏数据不该让整条方言详情 500。
    """
    try:
        value = json.loads(raw or '[]')
    except (ValueError, TypeError):
        return []
    return value if isinstance(value, list) else []


def get_dialects():
    """方言列表：只含摘要字段，顺序与切库前一致。"""
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, name, region, emoji, areas, speakers FROM dialects "
        "ORDER BY sort_order, id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_dialect_info(dialect_id):
    """单种方言的完整内容。不存在返回 None（由调用方退回默认方言）。"""
    conn = get_connection()
    row = conn.execute(
        "SELECT id, name, region, emoji, areas, speakers, greeting, greeting_meaning, "
        "features FROM dialects WHERE id = ?", (dialect_id,)).fetchone()
    if row is None:
        conn.close()
        return None

    dialect = dict(row)
    dialect['features'] = _decode_features(dialect.pop('features'))
    dialect['phrases'] = [
        {'dialect': r['dialect'], 'mandarin': r['mandarin'], 'pinyin': r['pinyin']}
        for r in conn.execute(
            'SELECT dialect, mandarin, pinyin FROM dialect_phrases '
            'WHERE dialect_id = ? ORDER BY sort_order', (dialect_id,)).fetchall()]
    dialect['quick_questions'] = [
        r['question'] for r in conn.execute(
            'SELECT question FROM dialect_quick_questions '
            'WHERE dialect_id = ? ORDER BY sort_order', (dialect_id,)).fetchall()]
    conn.close()
    return dialect


# ==================== 运营维护（写侧，T15） ====================
# 列名白名单、校验归路由层、无跨域删除三条口径与 farming / pest / crafts 一致。
# dialect_* 三张表全部由外键级联兜住（foreign_keys=ON），删方言连带删短语与快问。

# 方言主表可写的列。id 是主键，由调用方给出，不在白名单里。
DIALECT_FIELDS = ('name', 'region', 'emoji', 'areas', 'speakers', 'greeting',
                  'greeting_meaning', 'features', 'sort_order')
PHRASE_FIELDS = ('dialect', 'mandarin', 'pinyin', 'sort_order')
QUESTION_FIELDS = ('question', 'sort_order')


def _pick(fields, allowed):
    """按白名单挑出要写的列。None 表示「不碰这一列」，与「置空」是两件事。"""
    return {k: v for k, v in fields.items() if k in allowed and v is not None}


def _encode_features(value):
    """把 features 入参序列化回 JSON 文本。只接受 list，其余一律 ValueError。"""
    if not isinstance(value, list):
        raise ValueError('features 需要是数组')
    return json.dumps(value, ensure_ascii=False)


def _require_dialect(conn, dialect_id):
    row = conn.execute("SELECT id FROM dialects WHERE id = ?", (dialect_id,)).fetchone()
    if row is None:
        raise ValueError(u'方言不存在：%s' % dialect_id)


def get_dialect_row(dialect_id):
    """按 id 取一行方言（含 features 原文），不存在返回 None。"""
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM dialects WHERE id = ?", (dialect_id,)).fetchone()
    finally:
        conn.close()
    return dict(row) if row else None


def get_dialect_editor_row(dialect_id):
    """运营编辑用的一行方言：保留全部可写列，并把 features 解成数组。"""
    row = get_dialect_row(dialect_id)
    if row is None:
        return None
    row['features'] = _decode_features(row.get('features'))
    return row


def create_dialect(dialect_id, name, **fields):
    """新增一种方言，返回 dialect_id（字符串主键由调用方给出）。"""
    dialect_id = (dialect_id or '').strip()
    name = (name or '').strip()
    if not dialect_id:
        raise ValueError(u'方言 id 不能为空')
    if not name:
        raise ValueError(u'方言名称不能为空')
    values = _pick(fields, DIALECT_FIELDS)
    if 'features' in values:
        values['features'] = _encode_features(values['features'])
    values.update({'id': dialect_id, 'name': name})
    columns = ', '.join(values)
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO dialects (%s) VALUES (%s)"
            % (columns, ', '.join('?' * len(values))), list(values.values()))
        conn.commit()
    finally:
        conn.close()
    return dialect_id


def update_dialect(dialect_id, **fields):
    """按白名单改一种方言。字段全是 None 时不动库，返回是否真的改了。"""
    updates = _pick(fields, DIALECT_FIELDS)
    if 'features' in updates:
        updates['features'] = _encode_features(updates['features'])
    if 'name' in updates:
        updates['name'] = (updates['name'] or '').strip()
    if 'name' in updates and not updates['name']:
        raise ValueError(u'方言名称不能为空')
    if not updates:
        return False
    # 列名走双引号：desc / where 是 SQL 关键字，裸拼进 SET 子句会语法错误
    set_clause = ', '.join('"%s"=?' % column for column in updates)
    conn = get_connection()
    try:
        cur = conn.execute("UPDATE dialects SET %s WHERE id=?" % set_clause,
                           list(updates.values()) + [dialect_id])
        changed = cur.rowcount
        conn.commit()
    finally:
        conn.close()
    return changed > 0


def delete_dialect(dialect_id):
    """删除一种方言。短语与快捷问题由外键级联删除。"""
    conn = get_connection()
    try:
        cur = conn.execute("DELETE FROM dialects WHERE id = ?", (dialect_id,))
        deleted = cur.rowcount
        conn.commit()
    finally:
        conn.close()
    return deleted > 0


# ---- 短语 ----

def create_dialect_phrase(dialect_id, **fields):
    """新增一条短语，返回新 id。"""
    values = _pick(fields, PHRASE_FIELDS)
    for key in ('dialect', 'mandarin', 'pinyin'):
        if key in values:
            values[key] = (values[key] or '').strip()
    if not values.get('mandarin'):
        raise ValueError(u'普通话说法不能为空')
    values.update({'dialect_id': dialect_id})
    columns = ', '.join(values)
    conn = get_connection()
    try:
        _require_dialect(conn, dialect_id)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO dialect_phrases (%s) VALUES (%s)"
            % (columns, ', '.join('?' * len(values))), list(values.values()))
        phrase_id = cursor.lastrowid
        conn.commit()
    finally:
        conn.close()
    return phrase_id


def update_dialect_phrase(phrase_id, **fields):
    """按白名单改一条短语。"""
    updates = _pick(fields, PHRASE_FIELDS)
    for key in ('dialect', 'mandarin', 'pinyin'):
        if key in updates:
            updates[key] = (updates[key] or '').strip()
    if 'mandarin' in updates and not updates['mandarin']:
        raise ValueError(u'普通话说法不能为空')
    if not updates:
        return False
    # 列名走双引号：desc / where 是 SQL 关键字，裸拼进 SET 子句会语法错误
    set_clause = ', '.join('"%s"=?' % column for column in updates)
    conn = get_connection()
    try:
        cur = conn.execute("UPDATE dialect_phrases SET %s WHERE rowid=?" % set_clause,
                           list(updates.values()) + [phrase_id])
        changed = cur.rowcount
        conn.commit()
    finally:
        conn.close()
    return changed > 0


def delete_dialect_phrase(phrase_id):
    """删除一条短语。返回是否真的删掉了行。"""
    conn = get_connection()
    try:
        cur = conn.execute("DELETE FROM dialect_phrases WHERE rowid = ?", (phrase_id,))
        deleted = cur.rowcount
        conn.commit()
    finally:
        conn.close()
    return deleted > 0


def get_dialect_phrases(dialect_id):
    """一种方言的短语，带 rowid（后台编辑用）。顺序与前台一致。"""
    conn = get_connection()
    try:
        rows = conn.execute(
            'SELECT rowid AS id, dialect, mandarin, pinyin, sort_order '
            'FROM dialect_phrases WHERE dialect_id = ? ORDER BY sort_order, rowid',
            (dialect_id,)).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


# ---- 快捷问题 ----

def create_dialect_quick_question(dialect_id, question, **fields):
    """新增一个快捷问题，返回新 id。"""
    question = (question or '').strip()
    if not question:
        raise ValueError(u'快捷问题不能为空')
    values = _pick(fields, QUESTION_FIELDS)
    values.update({'dialect_id': dialect_id, 'question': question})
    columns = ', '.join(values)
    conn = get_connection()
    try:
        _require_dialect(conn, dialect_id)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO dialect_quick_questions (%s) VALUES (%s)"
            % (columns, ', '.join('?' * len(values))), list(values.values()))
        question_id = cursor.lastrowid
        conn.commit()
    finally:
        conn.close()
    return question_id


def update_dialect_quick_question(question_id, **fields):
    """按白名单改一个快捷问题。"""
    updates = _pick(fields, QUESTION_FIELDS)
    if 'question' in updates:
        updates['question'] = (updates['question'] or '').strip()
    if 'question' in updates and not updates['question']:
        raise ValueError(u'快捷问题不能为空')
    if not updates:
        return False
    # 列名走双引号：desc / where 是 SQL 关键字，裸拼进 SET 子句会语法错误
    set_clause = ', '.join('"%s"=?' % column for column in updates)
    conn = get_connection()
    try:
        cur = conn.execute(
            "UPDATE dialect_quick_questions SET %s WHERE rowid=?" % set_clause,
            list(updates.values()) + [question_id])
        changed = cur.rowcount
        conn.commit()
    finally:
        conn.close()
    return changed > 0


def delete_dialect_quick_question(question_id):
    """删除一个快捷问题。返回是否真的删掉了行。"""
    conn = get_connection()
    try:
        cur = conn.execute(
            "DELETE FROM dialect_quick_questions WHERE rowid = ?", (question_id,))
        deleted = cur.rowcount
        conn.commit()
    finally:
        conn.close()
    return deleted > 0


def get_dialect_quick_questions(dialect_id):
    """一种方言的快捷问题，带 rowid（后台编辑用）。顺序与前台一致。"""
    conn = get_connection()
    try:
        rows = conn.execute(
            'SELECT rowid AS id, question, sort_order FROM dialect_quick_questions '
            'WHERE dialect_id = ? ORDER BY sort_order, rowid',
            (dialect_id,)).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]
