#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""内容表的组装等价性（T08 的切库前提，T10 改与接口比对）。

快照比对（tests/test_crafts_dialect_snapshot.py）证明「接口输出没变」，但输出不变有两种
可能：库里本来就对，或者路由仍在读代码常量。T08 之前本文件直接比对库里的行与代码
常量；T10 把那些常量整体删掉（ADR 0002），参照物只剩接口本身，于是改成：

  · 采购指南与方言：把**拆平的库行**按 sort_order 重组，与接口下发的成品逐字段相等。
    这里断言的是重组前的**原料**与重组后的**成品**对得上，与快照的「成品形状对」
    互为两面 —— 少一层、错一层、字段漏一个，都在这里现形。
  · 方言的 features 在库里是 JSON 文本，读出时要解析回列表，断言文本与 json.dumps
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
    """拆平的库行按 sort_order 重组后，与接口下发的成品逐字段相等。"""

    @classmethod
    def setUpClass(cls):
        from app import app
        cls.client = app.test_client()
        cls.conn = get_connection()

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    # ---- 手工技艺 ----

    def test_craft_scalars_match(self):
        rows = {r['id']: r for r in self.conn.execute('SELECT * FROM crafts')}
        listing = json.loads(self.client.get('/api/crafts/list').data)['crafts']
        self.assertEqual({c['id'] for c in listing}, set(rows))
        by_id = {c['id']: c for c in listing}
        for craft_id, row in rows.items():
            self.assertEqual(by_id[craft_id]['name'], row['name'], craft_id)
            self.assertEqual(by_id[craft_id]['level'], row['level'] or '', craft_id)

    def test_craft_steps_match_in_order(self):
        rows = self.conn.execute(
            'SELECT craft_id, title, "desc", tips FROM craft_steps '
            'ORDER BY craft_id, sort_order').fetchall()
        expected = {}
        for r in rows:
            expected.setdefault(r['craft_id'], []).append(
                {'title': r['title'], 'desc': r['desc'], 'tips': r['tips']})
        for craft_id, steps in expected.items():
            body = json.loads(self.client.get('/api/crafts/%s' % craft_id).data)
            self.assertEqual(body['data']['steps'], steps, craft_id)

    def test_craft_purchase_guide_matches_after_reassembly(self):
        """拆平的四张表读回来，必须与接口下发的三层嵌套逐字段相等。"""
        for row in self.conn.execute(
                'SELECT craft_id, starter, advanced, buying_tips FROM craft_budgets'):
            craft_id = row['craft_id']
            body = json.loads(self.client.get('/api/crafts/%s' % craft_id).data)
            guide = body['data']['purchase_guide']
            self.assertEqual(guide['budget'], {
                'starter': row['starter'], 'advanced': row['advanced'],
            }, craft_id)
            self.assertEqual(guide['buying_tips'], row['buying_tips'], craft_id)

            # 分类表只存 key/label/desc，条目在下一张表：这里比的是分类层
            cats = self.conn.execute(
                'SELECT key, label, "desc" FROM craft_purchase_categories '
                'WHERE craft_id = ? ORDER BY sort_order', (craft_id,)).fetchall()
            self.assertEqual(
                [dict(c) for c in cats],
                [{k: cat[k] for k in ('key', 'label', 'desc')}
                 for cat in guide['categories']],
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
        listing = json.loads(self.client.get('/api/resources/dialects').data)['dialects']
        self.assertEqual({d['id'] for d in listing}, set(rows))
        by_id = {d['id']: d for d in listing}
        for dialect_id, row in rows.items():
            for column in ('name', 'region', 'emoji', 'areas', 'speakers'):
                self.assertEqual(by_id[dialect_id][column], row[column],
                                 '%s.%s' % (dialect_id, column))

    def test_dialect_info_scalars_match(self):
        """详情接口下发的问候语与 features：features 在库里是 JSON 文本，
        读侧必须解析回列表，否则「读侧少了解析」这种 bug 只在接口层现形。"""
        for row in self.conn.execute('SELECT * FROM dialects'):
            body = json.loads(self.client.get(
                '/api/resources/dialect-info?dialect=%s' % row['id']).data)['info']
            for column in ('name', 'region', 'emoji', 'areas', 'speakers',
                           'greeting', 'greeting_meaning'):
                self.assertEqual(body[column], row[column],
                                 '%s.%s' % (row['id'], column))
            self.assertEqual(body['features'], json.loads(row['features']), row['id'])

    def test_dialect_phrases_match_in_order(self):
        rows = self.conn.execute(
            'SELECT dialect_id, dialect, mandarin, pinyin FROM dialect_phrases '
            'ORDER BY dialect_id, sort_order').fetchall()
        expected = {}
        for r in rows:
            expected.setdefault(r['dialect_id'], []).append(
                {'dialect': r['dialect'], 'mandarin': r['mandarin'],
                 'pinyin': r['pinyin']})
        for dialect_id, phrases in expected.items():
            body = json.loads(self.client.get(
                '/api/resources/dialect-info?dialect=%s' % dialect_id).data)
            self.assertEqual(body['info']['phrases'], phrases, dialect_id)

    def test_dialect_quick_questions_match_in_order(self):
        rows = self.conn.execute(
            'SELECT dialect_id, question FROM dialect_quick_questions '
            'ORDER BY dialect_id, sort_order').fetchall()
        expected = {}
        for r in rows:
            expected.setdefault(r['dialect_id'], []).append(r['question'])
        for dialect_id, questions in expected.items():
            body = json.loads(self.client.get(
                '/api/resources/dialect-info?dialect=%s' % dialect_id).data)
            self.assertEqual(body['info']['quick_questions'], questions, dialect_id)


if __name__ == '__main__':
    unittest.main()
