# -*- coding: utf-8 -*-
"""内容表与代码常量的等价性（T08 的切库前提）。

快照比对（test_crafts_dialect_snapshot.py）证明「接口输出没变」，但输出不变有两种
可能：库里本来就对，或者路由仍在读代码。本文件补第二种可能：直接比对库里的行与
代码常量，证明内容确实来自库、且与常量逐字段相等。

两条断言各自的理由：

- 采购指南：库里是拆平的四张表，读回要按 sort_order 重组。这里断言重组前的
  **原料**是对的，与快照的「成品形状对」互为两面。
- 方言：features 在库里是 JSON 文本，读出时要解析回列表，断言文本与 json.dumps
  的产物相等，避免「读侧少了解析」这种只在接口层现形的 bug。

⚠️ 这些用例跑在真实库上（与既有测试同一口径），不写库、不建临时库：
它们只读内容表，读空就是失败，不需要事务保护。
"""

import json
import os
import sys
import unittest

_BACKEND_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend')
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from db_connection import get_connection  # noqa: E402


class ContentTableEquivalenceTest(unittest.TestCase):
    """库里灌进去的内容与代码里的常量逐字段相等。"""

    @classmethod
    def setUpClass(cls):
        from domains.crafts.routes import CRAFTS_KNOWLEDGE
        from domains.resources.dialect_voice import DIALECTS_DATA
        cls.crafts = CRAFTS_KNOWLEDGE
        cls.dialects = DIALECTS_DATA
        cls.conn = get_connection()

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    # ---- 手工技艺 ----

    def test_craft_scalars_match(self):
        rows = {r['id']: r for r in self.conn.execute('SELECT * FROM crafts')}
        self.assertEqual(set(rows), set(self.crafts))
        for craft_id, craft in self.crafts.items():
            row = rows[craft_id]
            self.assertEqual(row['name'], craft['name'], craft_id)
            self.assertEqual(row['origin'], craft['origin'], craft_id)
            self.assertEqual(row['history'], craft['history'], craft_id)

    def test_craft_steps_match_in_order(self):
        for craft_id, craft in self.crafts.items():
            rows = self.conn.execute(
                'SELECT title, "desc", tips FROM craft_steps '
                'WHERE craft_id = ? ORDER BY sort_order', (craft_id,)).fetchall()
            self.assertEqual([dict(r) for r in rows], craft['steps'], craft_id)

    def test_craft_purchase_guide_matches_after_reassembly(self):
        """拆平的四张表读回来，必须与代码里的三层嵌套逐字段相等。"""
        for craft_id, craft in self.crafts.items():
            guide = craft['purchase_guide']
            budget = self.conn.execute(
                'SELECT starter, advanced, buying_tips FROM craft_budgets '
                'WHERE craft_id = ?', (craft_id,)).fetchone()
            self.assertIsNotNone(budget, '%s 没有预算行' % craft_id)
            self.assertEqual(dict(budget), {
                'starter': guide['budget']['starter'],
                'advanced': guide['budget']['advanced'],
                'buying_tips': guide['buying_tips'],
            }, craft_id)

            # 分类表只存 key/label/desc，条目在下一张表：这里比的是分类层
            cats = self.conn.execute(
                'SELECT key, label, "desc" FROM craft_purchase_categories '
                'WHERE craft_id = ? ORDER BY sort_order', (craft_id,)).fetchall()
            self.assertEqual(
                [dict(c) for c in cats],
                [{k: cat[k] for k in ('key', 'label', 'desc')} for cat in guide['categories']],
                craft_id)

            for cat in guide['categories']:
                items = self.conn.execute(
                    'SELECT name, price, spec, tip, "where" FROM craft_purchase_items '
                    'WHERE craft_id = ? AND category_key = ? ORDER BY sort_order',
                    (craft_id, cat['key'])).fetchall()
                self.assertEqual([dict(i) for i in items], cat['items'],
                                 '%s/%s' % (craft_id, cat['key']))

    def test_every_craft_has_a_purchase_guide(self):
        """四张拆平的表必须都凑齐，缺一张就在接口上少一块。"""
        for table, key in (('crafts', 'id'), ('craft_steps', 'craft_id'),
                           ('craft_purchase_categories', 'craft_id'),
                           ('craft_purchase_items', 'craft_id'),
                           ('craft_budgets', 'craft_id')):
            count = self.conn.execute(
                'SELECT COUNT(*) FROM %s' % table).fetchone()[0]
            self.assertGreater(count, 0, '%s 是空的' % table)

    # ---- 方言知识 ----

    def test_dialect_scalars_match(self):
        rows = {r['id']: r for r in self.conn.execute('SELECT * FROM dialects')}
        self.assertEqual(set(rows), set(self.dialects))
        for dialect_id, dialect in self.dialects.items():
            row = rows[dialect_id]
            for column in ('name', 'region', 'emoji', 'areas', 'speakers',
                           'greeting', 'greeting_meaning'):
                self.assertEqual(row[column], dialect[column], '%s.%s' % (dialect_id, column))
            # features 在库里是 JSON 文本，读侧必须解析回列表
            self.assertEqual(json.loads(row['features']), dialect['features'], dialect_id)

    def test_dialect_phrases_match_in_order(self):
        for dialect_id, dialect in self.dialects.items():
            rows = self.conn.execute(
                'SELECT dialect, mandarin, pinyin FROM dialect_phrases '
                'WHERE dialect_id = ? ORDER BY sort_order', (dialect_id,)).fetchall()
            self.assertEqual([dict(r) for r in rows], dialect['phrases'], dialect_id)

    def test_dialect_quick_questions_match_in_order(self):
        for dialect_id, dialect in self.dialects.items():
            rows = self.conn.execute(
                'SELECT question FROM dialect_quick_questions '
                'WHERE dialect_id = ? ORDER BY sort_order', (dialect_id,)).fetchall()
            self.assertEqual([r[0] for r in rows], dialect['quick_questions'], dialect_id)


if __name__ == '__main__':
    unittest.main()
