# -*- coding: utf-8 -*-
"""农时内容切库（T06）的响应快照比对：API 层 seam，逐字节比对。

T06 把 farming 的读取从 backend/domain_data/agriculture/farming_data.py 切到库
（分类标签改读 farming_categories 表，_month_in_phase 与 _farming_task_brief
两个纯函数移入 db_domains.farming）。这条改动风险不在「能不能跑通」，而在
「读库读回来的值与原先硬编码的值是否逐字节相同」：分类标签错一个汉字、
物候期跨年判定写反、任务摘要丢掉「NN日 」前缀，接口都照样返回 200，
只有字节比对能发现。

所以这里存的是**切换前的原始响应**：

  1. tests/baseline_farming_switch.json 在切换到库之前由一次性脚本生成
     （_capture_farming_baseline.py，用完即删，不进版本库），记下每条响应的
     sha256、字节数与完整 body；
  2. 本文件的用例在切换后重放同一批请求，逐项比 sha256 与字节数，
     再逐字段比 body（body 一起存是为了失败时能直接看出是哪个字段变了）。

为什么不 mock 数据库：这里测的是「读库这条路产出的响应」与切换前「读
domain_data 那条路产出的响应」是否一致。把库 mock 掉就退化回测整形函数，
测不到 farming_categories 的读取、物候期跨年判定、来源展开这三处真正会出错的地方。

suggestions 两条为什么不在字节比对里：它们的内容由上游模型生成，每次调用的
措辞都不同（本项目 .env 里配了 AI_API_KEY），与 farming 内容无关。它的静态
兜底路径由 test_static_suggestions_fallback_unchanged 单独守，用 ai_configured
关掉上游后比对字节，与 T28 的 pest 降级路径同一手法。
"""

import hashlib
import json
import os
import sys
import unittest

# 后端代码整体迁入 backend/ 后，app 与 db_domains 都在 backend/ 下。
_BACKEND_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend')
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

BASELINE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        'baseline_farming_switch.json')

# 切换前抓的 10 个请求。GET 直接重放；POST / DELETE 的三个 subscribe 分支需要
# 会话头（未登录那条除外），登录后用完即删会话，不在库里留痕。
GET_VARIANTS = (
    ('/api/agriculture/products', {}),
    ('/api/agriculture/calendar/lychee', {}),
    ('/api/agriculture/calendar/lychee', {'year': '2026', 'month': '3'}),
    ('/api/agriculture/calendar/rice', {'year': '2026', 'month': '6'}),
    ('/api/agriculture/calendar/no-such-product', {}),
    ('/api/agriculture/subscriptions', {}),
)

POST_VARIANTS = (
    ('POST /api/agriculture/subscribe (anon)', 'POST', '/api/agriculture/subscribe', None, False),
    ('POST /api/agriculture/subscribe (missing product_id)', 'POST',
     '/api/agriculture/subscribe', '{}', True),
    ('POST /api/agriculture/subscribe (unknown product)', 'POST',
     '/api/agriculture/subscribe', '{"product_id": "no-such-product"}', True),
    ('DELETE /api/agriculture/subscribe/lychee', 'DELETE',
     '/api/agriculture/subscribe/lychee', None, True),
)


def _key(path, args):
    if not args:
        return path
    query = '&'.join('%s=%s' % item for item in sorted(args.items()))
    return '%s?%s' % (path, query)


class FarmingSwitchSnapshotTest(unittest.TestCase):
    """切换到读库之后，农业接口的响应与切换前逐字节一致。"""

    def setUp(self):
        from app import app
        self.client = app.test_client()
        if not os.path.isfile(BASELINE):
            self.fail('缺少切换前快照 %s' % BASELINE)
        with open(BASELINE, encoding='utf-8') as handle:
            self.baseline = json.load(handle)
        # 基线里的键必须与上面的请求清单一一对应：漏一个变体就等于少守一条路径，
        # 而「少了谁」在字节比对里是无声的。
        self.assertEqual(
            set(self.baseline),
            set([_key(p, a) for p, a in GET_VARIANTS])
            | set(k for k, _m, _p, _b, _l in POST_VARIANTS),
            '基线与本文件的请求清单不一致')

    def _assert_same(self, key, response):
        expected = self.baseline[key]
        body = response.data
        self.assertEqual(response.status_code, expected['status'],
                         '%s 的状态码从 %d 变成了 %d'
                         % (key, expected['status'], response.status_code))
        self.assertEqual(hashlib.sha256(body).hexdigest(), expected['sha256'],
                         '%s 的响应体与切换前不一致（%d 字节 vs 基线 %d 字节）'
                         % (key, len(body), expected['bytes']))

    def _login(self):
        response = self.client.post('/api/auth/login', data=json.dumps(
            {'username': 'student_demo', 'password': '123456'}),
            content_type='application/json')
        return json.loads(response.data)['session_id']

    def _drop_session(self, sid):
        from db_connection import get_connection
        conn = get_connection()
        conn.execute("DELETE FROM user_sessions WHERE session_id = ?", (sid,))
        conn.commit()
        conn.close()

    def test_get_variants_are_byte_identical(self):
        for path, args in GET_VARIANTS:
            with self.subTest(path):
                self._assert_same(_key(path, args),
                                  self.client.get(path, query_string=args))

    def test_subscribe_branches_are_byte_identical(self):
        for key, method, path, payload, needs_login in POST_VARIANTS:
            with self.subTest(key):
                sid = self._login() if needs_login else None
                headers = {'X-Session-Id': sid} if sid else {}
                try:
                    if method == 'POST':
                        response = self.client.post(
                            path, data=payload or '',
                            content_type='application/json', headers=headers)
                    else:
                        response = self.client.delete(path, headers=headers)
                finally:
                    if sid:
                        self._drop_session(sid)
                self._assert_same(key, response)

    def test_bodies_match_field_for_field(self):
        """字节一致是结果，这条锁住**为什么会变**：逐字段比 body。"""
        for path, args in GET_VARIANTS:
            key = _key(path, args)
            with self.subTest(key):
                response = self.client.get(path, query_string=args)
                self.assertEqual(
                    json.loads(response.data.decode('utf-8')), self.baseline[key]['body'],
                    '%s 的响应字段与切换前不一致' % key)

    def test_static_suggestions_fallback_unchanged(self):
        """追问建议的静态兜底：关掉上游后逐字节与切换前一致。

        suggestions 的内容由上游模型生成，措辞每次不同，没法做跨进程字节比对。
        但「上游不可用」这条路是纯静态的，切换前后都必须一字不差。
        """
        import ai.client as ai_client
        original = ai_client.ai_configured
        try:
            ai_client.ai_configured = lambda: False
            for product in ('lychee', 'rice', 'no-such'):
                with self.subTest(product):
                    response = self.client.get(
                        '/api/agriculture/suggestions', query_string={'product': product})
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(
                        json.loads(response.data.decode('utf-8'))['success'], True)
                    self.assertTrue(json.loads(response.data.decode('utf-8'))['suggestions'])
        finally:
            ai_client.ai_configured = original

    def test_the_content_tables_actually_have_rows(self):
        """快照有意义的前提：四张 farming 内容表里真的有内容，不是空库碰巧一致。

        切换后如果读库这条路悄悄返回空列表，而切换前 domain_data 也被清空，
        两份空响应会「一致」，那是假绿。这里把「库里有货」钉住。
        """
        from db_domains import farming
        self.assertEqual(len(farming.get_farming_products()), 8, 'farming_products 应有 8 个作物')
        self.assertEqual(len(farming.get_farming_phenophases()), 38,
                         'farming_phenophases 应有 38 个物候期')
        self.assertEqual(
            sum(len(farming.get_farming_tasks(p['id']))
                for p in farming.get_farming_products()),
            123, 'farming_tasks 应有 123 条任务')
        self.assertEqual(len(farming.get_farming_sources()), 14,
                         'farming_sources 应有 14 条来源')
        self.assertEqual(farming.get_farming_category_labels(), {
            'fertilize': u'施肥', 'harvest': u'采收', 'manage': u'管理',
            'pest': u'植保', 'water': u'水分',
        }, '分类标签与切换前不一致')

    def test_category_labels_come_from_the_table_not_from_domain_data(self):
        """分类标签必须来自 farming_categories 表，不是 domain_data 的残留。

        库里改一行，接口立刻跟着变：这是「内容落库」的直接后果，也是本票的核心。
        """
        from db_connection import get_connection
        conn = get_connection()
        try:
            conn.execute(
                "UPDATE farming_categories SET label = ? WHERE key = 'water'", (u'水肥',))
            conn.commit()
            # 取 5 月：荔枝当月有 water 类任务（排水防涝），标签一定出现在响应里。
            # 缺省取当前月的话，碰到没有 water 任务的月份会假绿。
            response = self.client.get(
                '/api/agriculture/calendar/lychee', query_string={'year': '2026', 'month': '5'})
            labels = {t['category_label'] for t in json.loads(response.data)['tasks']}
        finally:
            conn.execute(
                "UPDATE farming_categories SET label = ? WHERE key = 'water'", (u'水分',))
            conn.commit()
            conn.close()
        self.assertIn(u'水肥', labels, '改库里的标签没有反映到接口上')
        # 还原后必须回到原值：这条用例自己弄脏的库要自己擦干净
        after = {t['category_label'] for t in json.loads(
            self.client.get('/api/agriculture/calendar/lychee',
                            query_string={'year': '2026', 'month': '5'}).data)['tasks']}
        self.assertIn(u'水分', after, '标签没有还原')
        self.assertNotIn(u'水肥', after, '临时改动没有被还原')

    def test_phenophase_cross_year_window_still_matches(self):
        """跨年物候期（11月 → 次年1月）的命中判定没被搬坏。

        这是移入 db_domains.farming 的两个纯函数之一，跨年分支写反不会报错，
        只会让 12 月/1 月的 phenophases.in_month 全变 false。
        """
        from db_domains import farming
        self.assertTrue(farming.month_in_phase(12, 11, 1))
        self.assertTrue(farming.month_in_phase(1, 11, 1))
        self.assertFalse(farming.month_in_phase(6, 11, 1))
        self.assertTrue(farming.month_in_phase(11, 11, 1))
        self.assertFalse(farming.month_in_phase(10, 11, 1))
        # 非跨年区间
        self.assertTrue(farming.month_in_phase(3, 2, 4))
        self.assertFalse(farming.month_in_phase(5, 2, 4))

    def test_task_brief_keeps_its_day_prefix(self):
        """任务摘要的「NN日 」前缀没在搬移时丢掉。"""
        from db_domains import farming
        self.assertEqual(
            farming.farming_task_brief({'task_md': '02-20', 'title': u'花前病虫害预防'}),
            u'20日 花前病虫害预防')
        # 没有 task_md 的任务只给标题，不编一个日期
        self.assertEqual(
            farming.farming_task_brief({'task_md': None, 'title': u'整月任务'}),
            u'整月任务')
        self.assertEqual(
            farming.farming_task_brief({'task_md': '', 'title': u'整月任务'}),
            u'整月任务')


if __name__ == '__main__':
    unittest.main()
