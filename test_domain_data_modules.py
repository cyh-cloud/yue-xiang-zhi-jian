# -*- coding: utf-8 -*-
"""内容表有货 + 接口输出形状不变（T10）。

原文件是 T06 的「五个 domain_data 模块搬迁一致性测试」：它断言 pest_data / jobs_data /
cases_data / policies_data / farming_data 五个文件必须存在、公开符号面必须不变、内容计数
必须等于硬编码数字。T10 把那五个模块整体删掉（ADR 0002：代码零硬数据，SQLite 是唯一
数据源），那份测试的前提随之消失，按 spec 的 Testing Decisions 改写为现在的形状：

  1. **内容表有行**：灌进库的那 14 张内容表每张都有行，且行数等于 T05 迁移脚本灌进去的
     数量。没有这一条，「接口输出不变」会是假绿：代码不再读 domain_data 之后，如果读库
     那条路悄悄返回空，两个空响应会「一致」。
  2. **接口输出形状不变**：四类内容的接口仍下发同样的键集、同样的条目数、同样的口径文案。
     这里比的是**形状与计数**，不是逐字节：字节比对由 tests/test_*_snapshot.py 那三个
     快照文件负责（它们比对的是切换前后的响应），本文件负责的是「删掉 domain_data 之后
     这些形状还在」。

为什么不 mock 数据库：这里测的就是「读库这条路产出的响应」。把库 mock 掉就退化回测整形
函数，测不到 JOIN、sort_order 重组、JSON 列解析这三处真正会出错的地方。

⚠️ 本文件跑在真实库上（与既有测试同一口径），只读不写。
"""

import json
import os
import sys
import unittest

# 后端代码整体迁入 backend/ 后，app 与 db_domains 都在 backend/ 下。
REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.join(REPO_ROOT, 'backend')
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

# T05 的 migrations/0001_content_to_db.py 灌进去的行数。它们是本文件断言「库里有货」的
# 基准：内容由基线库交付（ADR 0002 的部署方式），运营改了行数不算破坏，但表被清空就算。
EXPECTED_ROWS = {
    'farming_categories': 5,
    'farming_sources': 14,
    'farming_products': 8,
    'farming_phenophases': 38,
    'farming_tasks': 123,
    'pest_crops': 8,
    'pest_entries': 45,
    'pest_sources': 24,
    'pest_entry_sources': 117,
    'pest_images': 18,
    'recruitments': 14,
    'recruitment_sources': 16,
    'success_cases': 5,
    'case_stats': 20,
    'case_milestones': 24,
    'case_sources': 18,
    'case_lessons': 21,
    'dialects': 3,
    'dialect_phrases': 24,
    'dialect_quick_questions': 12,
    'crafts': 4,
    'craft_steps': 24,
    'craft_purchase_categories': 12,
    'craft_purchase_items': 46,
    'craft_budgets': 4,
}


def table_counts():
    from db_connection import get_connection
    conn = get_connection()
    try:
        return {table: conn.execute('SELECT COUNT(*) FROM %s' % table).fetchone()[0]
                for table in EXPECTED_ROWS}
    finally:
        conn.close()


class ContentTablesHaveRowsTest(unittest.TestCase):
    """库里有货：删掉 domain_data 之后，内容表的行数是接口有东西可返回的前提。"""

    def test_every_content_table_has_rows(self):
        counts = table_counts()
        empty = {table: n for table, n in counts.items() if n == 0}
        self.assertEqual(empty, {}, '这些内容表是空的，接口会返回空列表：%s' % empty)

    def test_row_counts_match_the_migrated_baseline(self):
        """行数与 T05 灌库结果一致。运营增删内容是正常的，这里只钉「没有整表消失」。"""
        counts = table_counts()
        self.assertEqual(counts, EXPECTED_ROWS,
                         '内容表行数与迁移灌入的结果不符，快照类测试会失去比对意义')


class ContentShapeTest(unittest.TestCase):
    """删掉代码常量之后，四类内容的接口输出形状不变。"""

    def setUp(self):
        from app import app
        self.client = app.test_client()

    def _get(self, path):
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200, path)
        return json.loads(response.data)

    # ---- 农时 ----

    def test_products_catalog_keeps_its_shape(self):
        body = self._get('/api/agriculture/products')
        self.assertTrue(body['success'])
        products = body['products']
        self.assertEqual(len(products), 8, 'farming_products 应有 8 个作物')
        for product in products:
            self.assertEqual(sorted(product), ['desc', 'icon', 'id', 'name'])
            for key in ('id', 'name', 'icon'):
                self.assertTrue(product[key], '%s 为空' % key)
        self.assertIn('lychee', [p['id'] for p in products])

    def test_calendar_keeps_its_shape(self):
        body = self._get('/api/agriculture/calendar/lychee')
        for key in ('product', 'year', 'month', 'is_configured', 'dates_provisional',
                    'phenophases', 'solar_terms', 'tasks'):
            self.assertIn(key, body)
        self.assertEqual(body['product']['id'], 'lychee')
        self.assertEqual(body['product']['name'], u'荔枝')
        self.assertTrue(body['tasks'], '荔枝当月应有农事任务')
        for task in body['tasks']:
            for key in ('id', 'date', 'day', 'task_md', 'title', 'category',
                        'category_label', 'priority', 'icon', 'description', 'tip',
                        'phase_id', 'phase_name', 'phase_color', 'sort_order',
                        'is_verified', 'evidence_level', 'date_basis', 'source'):
                self.assertIn(key, task, '任务缺字段 %s' % key)

    # ---- 病虫害 ----

    def test_pest_knowledge_keeps_its_shape(self):
        body = self._get('/api/agriculture/pest-knowledge')
        self.assertTrue(body['success'])
        self.assertEqual(len(body['entries']), 45, 'pest_entries 应有 45 条')
        self.assertEqual(len(body['crops']), 8, 'pest_crops 应有 8 个作物')
        self.assertEqual(body['stats'], {'crops': 8, 'entries': 45,
                                         'with_image': 18, 'verified': 0})
        self.assertTrue(body['disclaimer'])
        for entry in body['entries']:
            for key in ('id', 'crop', 'crop_name', 'crop_icon', 'disease', 'alias',
                        'kind', 'pathogen', 'part', 'severity', 'symptoms',
                        'occurrence', 'treatment', 'prevention', 'registered',
                        'chem_table', 'safety_note', 'image', 'sources',
                        'is_verified'):
                self.assertIn(key, entry, '条目 %s 缺字段 %s' % (entry['id'], key))

    # ---- 手工技艺与方言 ----

    def test_crafts_keep_their_shape(self):
        listing = self._get('/api/crafts/list')
        self.assertEqual([c['id'] for c in listing['crafts']],
                         ['embroidery', 'woodcarving', 'ceramics', 'lacquer'])
        for craft in listing['crafts']:
            self.assertEqual(sorted(craft), ['id', 'level', 'name', 'origin'])

        detail = self._get('/api/crafts/embroidery')
        craft = detail['data']
        self.assertEqual(sorted(craft), ['history', 'name', 'origin',
                                         'purchase_guide', 'steps'])
        self.assertTrue(craft['steps'], '广绣应有步骤')
        guide = craft['purchase_guide']
        self.assertEqual(sorted(guide), ['budget', 'buying_tips', 'categories'])
        self.assertEqual(sorted(guide['budget']), ['advanced', 'starter'])
        self.assertEqual([c['key'] for c in guide['categories']],
                         ['essential', 'consumable', 'advanced'])
        for category in guide['categories']:
            self.assertEqual(sorted(category), ['desc', 'items', 'key', 'label'])
            for item in category['items']:
                self.assertEqual(sorted(item), ['name', 'price', 'spec', 'tip', 'where'])

    def test_dialects_keep_their_shape(self):
        listing = self._get('/api/resources/dialects')
        self.assertEqual([d['id'] for d in listing['dialects']],
                         ['cantonese', 'hakka', 'teochew'])
        for dialect in listing['dialects']:
            for key in ('id', 'name', 'region', 'emoji', 'areas', 'speakers'):
                self.assertIn(key, dialect)

        info = self._get('/api/resources/dialect-info?dialect=cantonese')['info']
        for key in ('id', 'name', 'region', 'emoji', 'areas', 'speakers', 'greeting',
                    'greeting_meaning', 'features', 'phrases', 'quick_questions'):
            self.assertIn(key, info)
        self.assertTrue(info['phrases'], '粤语应有短语')
        self.assertTrue(info['quick_questions'], '粤语应有快捷问题')
        self.assertEqual(sorted(info['phrases'][0]), ['dialect', 'mandarin', 'pinyin'])

    # ---- 招募、案例、政策 ----

    def test_recruitments_keep_their_shape(self):
        body = self._get('/api/employment/jobs')
        self.assertTrue(body['success'])
        self.assertEqual(len(body['recruitments']), 14, 'recruitments 应有 14 条公告')
        self.assertTrue(body['recruit_source_note'])
        self.assertTrue(body['recruit_disclaimer'])
        for item in body['recruitments']:
            for key in ('key', 'title', 'org', 'region', 'category', 'job_type',
                        'headcount', 'education', 'experience', 'salary',
                        'description', 'publish_date', 'signup_start', 'deadline',
                        'signup_way', 'contact', 'sources', 'status',
                        'status_label', 'days_left', 'starts_in'):
                self.assertIn(key, item, '公告 %s 缺字段 %s' % (item['key'], key))
            self.assertTrue(item['sources'], '公告 %s 没有来源' % item['key'])

    def test_cases_keep_their_shape(self):
        body = self._get('/api/resources/cases')
        self.assertTrue(body['success'])
        self.assertEqual([c['id'] for c in body['cases']], [1, 2, 3, 4, 5])
        self.assertIn('source_note', body)
        self.assertIn('lessons_note', body)
        for case in body['cases']:
            for key in ('id', 'title', 'region', 'location', 'background',
                        'description', 'quote', 'quote_author', 'stats',
                        'milestones', 'sources', 'lessons'):
                self.assertIn(key, case, '案例 %s 缺字段 %s' % (case['id'], key))
            self.assertTrue(case['stats'], '案例 %d 没有数据指标' % case['id'])
            self.assertTrue(case['milestones'], '案例 %d 没有里程碑' % case['id'])
            self.assertTrue(case['sources'], '案例 %d 没有来源' % case['id'])
            self.assertTrue(case['lessons'], '案例 %d 没有借鉴点' % case['id'])

    def test_policies_keep_their_shape(self):
        body = self._get('/api/resources/policies')
        self.assertTrue(body['success'])
        self.assertGreater(len(body['policies']), 0)
        self.assertIn('source_note', body)
        self.assertIn('disclaimer', body)
        for policy in body['policies']:
            for key in ('title', 'content', 'category', 'summary', 'date', 'sources'):
                self.assertIn(key, policy)


if __name__ == '__main__':
    unittest.main()
