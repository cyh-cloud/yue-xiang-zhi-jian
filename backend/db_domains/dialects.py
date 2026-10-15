# -*- coding: utf-8 -*-
"""方言知识域：方言、短语与快捷问题的读取。

T08 从 domains/resources/dialect_voice.py 的 DIALECTS_DATA 常量切到读库（ADR 0002）。
库里是方言层 + 短语 + 快捷问题三张表，本模块负责按原形状组装回去：

    dialects                -> 方言层（含 features，JSON 文本解析成列表）
    dialect_phrases         -> dialect['phrases']          （按 sort_order）
    dialect_quick_questions -> dialect['quick_questions']  （按 sort_order）

对外契约不变：列表的顺序（dialects 按 sort_order）、详情的键与键序、
未知方言 id 退回粤语（由调用方按 None 处理）都与切库前逐字节一致。
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
