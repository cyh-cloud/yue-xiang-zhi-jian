# -*- coding: utf-8 -*-
"""农业培训域的路由行为测试（T10）。

农技问答（含流式）、追问建议、农事日历、作物订阅与到期提醒从 app.py 搬进
domains/agriculture/ 之后，外部契约必须一字不变：URL、请求响应结构、状态码、
错误码，以及几条业务底线，即未登录 401、未知作物 400、超长输入 400、
上游未配置 503 + ai_not_configured、农技口径的剂量免责声明强制补齐。

断言全部基于 HTTP 行为，不测模块怎么划分（拆分不产生新行为，为结构写测试只会
把实现细节钉死，见 spec 的 Testing Decisions）。
"""

import json
import os
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import database  # noqa: E402


class AgricultureDomainTestBase(unittest.TestCase):
    def setUp(self):
        from app import app
        self.client = app.test_client()

    def _login(self, username='student_demo', password='123456'):
        response = self.client.post('/api/auth/login', data=json.dumps(
            {'username': username, 'password': password}),
            content_type='application/json')
        return json.loads(response.data)['session_id']

    def _cleanup_sessions(self, sid):
        conn = database.get_connection()
        if sid:
            conn.execute("DELETE FROM user_sessions WHERE session_id = ?", (sid,))
        conn.commit()
        conn.close()


class ProductCatalogTest(AgricultureDomainTestBase):
    """农产品目录：优先读 farming_products 表，空表回退内置目录。"""

    def test_products_returns_success_with_nonempty_list(self):
        response = self.client.get('/api/agriculture/products')
        self.assertEqual(response.status_code, 200)
        body = json.loads(response.data)
        self.assertTrue(body['success'])
        self.assertGreater(len(body['products']), 0)
        for product in body['products']:
            for key in ('id', 'name', 'icon', 'desc'):
                self.assertIn(key, product)

    def test_products_falls_back_to_the_builtin_catalog_when_table_is_empty(self):
        """表读空时回退硬编码目录：六种作物的 id/name/icon/desc 与拆分前逐字一致。"""
        original = database.get_farming_products
        try:
            database.get_farming_products = lambda: []
            response = self.client.get('/api/agriculture/products')
        finally:
            database.get_farming_products = original
        self.assertEqual(response.status_code, 200)
        body = json.loads(response.data)
        self.assertTrue(body['success'])
        self.assertEqual([p['id'] for p in body['products']],
                         ['lychee', 'longan', 'aquatic', 'rice', 'tea', 'vegetable'])
        self.assertEqual([p['name'] for p in body['products']],
                         [u'荔枝', u'龙眼', u'水产养殖', u'水稻', u'茶叶', u'蔬菜'])
        self.assertEqual([p['icon'] for p in body['products']],
                         ['apple-alt', 'circle', 'fish', 'seedling', 'mug-hot', 'carrot'])

    def test_products_survives_a_database_failure(self):
        """读表异常时同样回退内置目录，不外抛 500。"""
        original = database.get_farming_products

        def boom():
            raise RuntimeError('database down')

        try:
            database.get_farming_products = boom
            response = self.client.get('/api/agriculture/products')
        finally:
            database.get_farming_products = original
        self.assertEqual(response.status_code, 200)
        body = json.loads(response.data)
        self.assertTrue(body['success'])
        self.assertEqual(len(body['products']), 6)


class FarmingCalendarTest(AgricultureDomainTestBase):
    """农时日历：年周期模板、节气、物候期与来源标注。"""

    def test_calendar_returns_the_full_contract(self):
        response = self.client.get('/api/agriculture/calendar/lychee')
        self.assertEqual(response.status_code, 200)
        body = json.loads(response.data)
        self.assertTrue(body['success'])
        for key in ('product', 'year', 'month', 'is_configured', 'dates_provisional',
                    'source_summary', 'sources_all', 'phenophase_current',
                    'phenophases', 'solar_terms', 'tasks'):
            self.assertIn(key, body)
        self.assertEqual(body['product']['id'], 'lychee')
        self.assertEqual(body['product']['name'], u'荔枝')

    def test_calendar_unknown_product_is_404(self):
        response = self.client.get('/api/agriculture/calendar/no-such-product')
        self.assertEqual(response.status_code, 404)
        body = json.loads(response.data)
        self.assertFalse(body['success'])
        self.assertEqual(body['message'], u'未找到该农产品信息')

    def test_calendar_accepts_explicit_year_and_month(self):
        response = self.client.get('/api/agriculture/calendar/lychee?year=2026&month=3')
        self.assertEqual(response.status_code, 200)
        body = json.loads(response.data)
        self.assertEqual(body['year'], 2026)
        self.assertEqual(body['month'], 3)

    def test_calendar_month_zero_is_treated_as_january(self):
        """month=0 是 0-indexed 兼容写法，按一月处理。"""
        response = self.client.get('/api/agriculture/calendar/lychee?month=0')
        self.assertEqual(response.status_code, 200)
        body = json.loads(response.data)
        self.assertEqual(body['month'], 1)

    def test_calendar_invalid_month_falls_back_to_the_current_month(self):
        response = self.client.get('/api/agriculture/calendar/lychee?month=abc')
        self.assertEqual(response.status_code, 200)
        body = json.loads(response.data)
        self.assertGreaterEqual(body['month'], 1)
        self.assertLessEqual(body['month'], 12)

    def test_calendar_includes_solar_terms_of_the_month(self):
        response = self.client.get('/api/agriculture/calendar/lychee?year=2026&month=3')
        body = json.loads(response.data)
        self.assertTrue(body['solar_terms'])
        for term in body['solar_terms']:
            self.assertIn('date', term)
            self.assertIn('day', term)
            self.assertIn('name', term)

    def test_calendar_marks_phenophases_in_month(self):
        response = self.client.get('/api/agriculture/calendar/rice?year=2026&month=6')
        self.assertEqual(response.status_code, 200)
        body = json.loads(response.data)
        for phase in body['phenophases']:
            self.assertIn('in_month', phase)
            self.assertIsInstance(phase['in_month'], bool)

    def test_calendar_deactivated_product_is_404(self):
        """停用作物不可订阅也不可看日历，否则订阅后点进通知是 404。"""
        pid = 't10_inactive_crop'
        conn = database.get_connection()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO farming_products (id, name, summary, icon, is_active, sort_order) "
                "VALUES (?, ?, ?, ?, 0, 99)", (pid, u'测试停用作物', '', 'seedling'))
            conn.commit()
            response = self.client.get('/api/agriculture/calendar/%s' % pid)
        finally:
            conn.execute("DELETE FROM farming_products WHERE id = ?", (pid,))
            conn.commit()
            conn.close()
        self.assertEqual(response.status_code, 404)
        body = json.loads(response.data)
        self.assertFalse(body['success'])


class SubscriptionTest(AgricultureDomainTestBase):
    """作物订阅与取消：幂等，未登录一律 401。"""

    def _subscribe_pid(self):
        products = json.loads(self.client.get('/api/agriculture/products').data)['products']
        return next(p['id'] for p in products if p.get('is_active', 1) != 0)

    def _drop_subscription(self, username, pid):
        conn = database.get_connection()
        conn.execute("DELETE FROM farming_subscriptions WHERE user_id = ? AND product_id = ?",
                     (username, pid))
        conn.execute("DELETE FROM farming_reminder_log WHERE user_id = ? AND product_id = ?",
                     (username, pid))
        conn.commit()
        conn.close()

    def test_subscriptions_require_login(self):
        response = self.client.get('/api/agriculture/subscriptions')
        self.assertEqual(response.status_code, 401)
        self.assertEqual(json.loads(response.data), {"success": False, "message": u"请先登录"})

    def test_subscribe_requires_login(self):
        response = self.client.post('/api/agriculture/subscribe',
                                    data=json.dumps({'product_id': 'lychee'}),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 401)
        self.assertEqual(json.loads(response.data), {"success": False, "message": u"请先登录"})

    def test_unsubscribe_requires_login(self):
        response = self.client.delete('/api/agriculture/subscribe/lychee')
        self.assertEqual(response.status_code, 401)
        self.assertEqual(json.loads(response.data), {"success": False, "message": u"请先登录"})

    def test_reminders_check_requires_login(self):
        response = self.client.post('/api/agriculture/reminders/check')
        self.assertEqual(response.status_code, 401)
        self.assertEqual(json.loads(response.data), {"success": False, "message": u"请先登录"})

    def test_subscribe_list_unsubscribe_round_trip(self):
        sid = self._login()
        pid = self._subscribe_pid()
        try:
            subscribed = self.client.post(
                '/api/agriculture/subscribe', data=json.dumps({'product_id': pid}),
                content_type='application/json', headers={'X-Session-Id': sid})
            self.assertEqual(subscribed.status_code, 200)
            body = json.loads(subscribed.data)
            self.assertTrue(body['success'])
            self.assertTrue(body['subscribed'])
            self.assertIn(pid, body['product_ids'])

            listed = json.loads(self.client.get(
                '/api/agriculture/subscriptions',
                headers={'X-Session-Id': sid}).data)
            self.assertEqual(listed, {"success": True, "product_ids": body['product_ids']})

            # 幂等：重复订阅不会产生第二条记录
            self.client.post('/api/agriculture/subscribe',
                             data=json.dumps({'product_id': pid}),
                             content_type='application/json',
                             headers={'X-Session-Id': sid})
            again = json.loads(self.client.get(
                '/api/agriculture/subscriptions', headers={'X-Session-Id': sid}).data)
            self.assertEqual(again['product_ids'].count(pid), 1)

            unsubscribed = self.client.delete(
                '/api/agriculture/subscribe/%s' % pid, headers={'X-Session-Id': sid})
            self.assertEqual(unsubscribed.status_code, 200)
            unsub_body = json.loads(unsubscribed.data)
            self.assertTrue(unsub_body['success'])
            self.assertFalse(unsub_body['subscribed'])
            self.assertNotIn(pid, unsub_body['product_ids'])

            after = json.loads(self.client.get(
                '/api/agriculture/subscriptions', headers={'X-Session-Id': sid}).data)
            self.assertNotIn(pid, after['product_ids'])
        finally:
            self._drop_subscription('student_demo', pid)
            self._cleanup_sessions(sid)

    def test_subscribe_missing_product_id_is_400(self):
        sid = self._login()
        try:
            response = self.client.post('/api/agriculture/subscribe',
                                        data=json.dumps({}),
                                        content_type='application/json',
                                        headers={'X-Session-Id': sid})
            self.assertEqual(response.status_code, 400)
            self.assertEqual(json.loads(response.data),
                             {"success": False, "message": u"缺少 product_id"})
        finally:
            self._cleanup_sessions(sid)

    def test_subscribe_unknown_product_is_404(self):
        sid = self._login()
        try:
            response = self.client.post(
                '/api/agriculture/subscribe',
                data=json.dumps({'product_id': 'no-such-product'}),
                content_type='application/json', headers={'X-Session-Id': sid})
            self.assertEqual(response.status_code, 404)
            self.assertEqual(json.loads(response.data),
                             {"success": False, "message": u"未找到该农产品信息"})
        finally:
            self._cleanup_sessions(sid)

    def test_subscribe_deactivated_product_is_404(self):
        """停用作物不可订阅（与日历接口同一口径）。"""
        pid = 't10_inactive_crop'
        sid = self._login()
        conn = database.get_connection()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO farming_products (id, name, summary, icon, is_active, sort_order) "
                "VALUES (?, ?, ?, ?, 0, 99)", (pid, u'测试停用作物', '', 'seedling'))
            conn.commit()
            response = self.client.post(
                '/api/agriculture/subscribe',
                data=json.dumps({'product_id': pid}),
                content_type='application/json', headers={'X-Session-Id': sid})
            self.assertEqual(response.status_code, 404)
            self.assertEqual(json.loads(response.data),
                             {"success": False, "message": u"未找到该农产品信息"})
        finally:
            conn.execute("DELETE FROM farming_products WHERE id = ?", (pid,))
            conn.commit()
            conn.close()
            self._drop_subscription('student_demo', pid)
            self._cleanup_sessions(sid)

    def test_unsubscribe_is_idempotent(self):
        """未订阅过的作物取消订阅同样 200，不报错。"""
        sid = self._login()
        try:
            response = self.client.delete('/api/agriculture/subscribe/banana',
                                          headers={'X-Session-Id': sid})
            self.assertEqual(response.status_code, 200)
            body = json.loads(response.data)
            self.assertTrue(body['success'])
            self.assertFalse(body['subscribed'])
            self.assertNotIn('banana', body['product_ids'])
        finally:
            self._drop_subscription('student_demo', 'banana')
            self._cleanup_sessions(sid)

    def test_subscriptions_are_scoped_to_the_session_user(self):
        """订阅列表只回本人的数据，不因他人订阅而变化。"""
        sid = self._login()
        other_sid = self._login('teacher_demo')
        pid = 'tea'
        try:
            self.client.post('/api/agriculture/subscribe',
                             data=json.dumps({'product_id': pid}),
                             content_type='application/json',
                             headers={'X-Session-Id': sid})
            mine = json.loads(self.client.get(
                '/api/agriculture/subscriptions', headers={'X-Session-Id': sid}).data)
            self.assertIn(pid, mine['product_ids'])
            theirs = json.loads(self.client.get(
                '/api/agriculture/subscriptions',
                headers={'X-Session-Id': other_sid}).data)
            self.assertNotIn(pid, theirs['product_ids'])
        finally:
            self._drop_subscription('student_demo', pid)
            self._cleanup_sessions(sid)
            self._cleanup_sessions(other_sid)


class ReminderCheckTest(AgricultureDomainTestBase):
    """到期提醒：登录补发，幂等按「用户 + 作物 + 月份」记日志。"""

    def _drop_subscription(self, username, pid):
        conn = database.get_connection()
        conn.execute("DELETE FROM farming_subscriptions WHERE user_id = ? AND product_id = ?",
                     (username, pid))
        conn.execute("DELETE FROM farming_reminder_log WHERE user_id = ? AND product_id = ?",
                     (username, pid))
        conn.commit()
        conn.close()

    def test_reminders_check_returns_period_and_details(self):
        sid = self._login()
        pid = 'lychee'
        try:
            self.client.post('/api/agriculture/subscribe',
                             data=json.dumps({'product_id': pid}),
                             content_type='application/json',
                             headers={'X-Session-Id': sid})
            response = self.client.post('/api/agriculture/reminders/check',
                                        headers={'X-Session-Id': sid})
            self.assertEqual(response.status_code, 200)
            body = json.loads(response.data)
            self.assertTrue(body['success'])
            self.assertIn('period', body)
            self.assertIn('sent', body)
            self.assertIsInstance(body['sent'], int)
            self.assertIsInstance(body['details'], list)
            self.assertRegex(body['period'], r'^\d{4}-\d{2}$')
        finally:
            self._drop_subscription('student_demo', pid)
            self._cleanup_sessions(sid)

    def test_reminders_check_is_idempotent_within_the_same_period(self):
        """同一月份重复检查不会重复推送（幂等键命中后 continue）。"""
        sid = self._login()
        pid = 'lychee'
        try:
            self.client.post('/api/agriculture/subscribe',
                             data=json.dumps({'product_id': pid}),
                             content_type='application/json',
                             headers={'X-Session-Id': sid})
            first = json.loads(self.client.post(
                '/api/agriculture/reminders/check',
                headers={'X-Session-Id': sid}).data)
            second = json.loads(self.client.post(
                '/api/agriculture/reminders/check',
                headers={'X-Session-Id': sid}).data)
            self.assertEqual(second['sent'], 0)
            self.assertEqual(second['details'], [])
            self.assertEqual(first['period'], second['period'])
        finally:
            self._drop_subscription('student_demo', pid)
            self._cleanup_sessions(sid)


class AgriAskTest(AgricultureDomainTestBase):
    """农技问答：输入校验、限流、上游未配置的明确失败。"""

    def _ask(self, payload, sid):
        return self.client.post('/api/agriculture/ask', data=json.dumps(payload),
                                content_type='application/json',
                                headers={'X-Session-Id': sid})

    def test_ask_rejects_non_json_body(self):
        sid = self._login()
        try:
            response = self.client.post('/api/agriculture/ask', data='not-json',
                                        content_type='application/json',
                                        headers={'X-Session-Id': sid})
            self.assertEqual(response.status_code, 400)
            body = json.loads(response.data)
            self.assertFalse(body['success'])
            self.assertEqual(body['code'], 'bad_request')
            self.assertEqual(body['message'], u'请求格式不正确，应为 JSON 对象')
        finally:
            self._cleanup_sessions(sid)

    def test_ask_rejects_empty_question(self):
        sid = self._login()
        try:
            response = self._ask({'question': '   ', 'product': 'lychee'}, sid)
            self.assertEqual(response.status_code, 400)
            body = json.loads(response.data)
            self.assertFalse(body['success'])
            self.assertEqual(body['code'], 'empty_question')
            self.assertEqual(body['message'], u'请输入问题')
        finally:
            self._cleanup_sessions(sid)

    def test_ask_rejects_overlong_question(self):
        """超长输入必须 400 + question_too_long（与前端 maxlength 同一口径）。"""
        sid = self._login()
        try:
            response = self._ask({'question': 'x' * 501, 'product': 'lychee'}, sid)
            self.assertEqual(response.status_code, 400)
            body = json.loads(response.data)
            self.assertFalse(body['success'])
            self.assertEqual(body['code'], 'question_too_long')
            self.assertEqual(body['message'], u'问题过长，请控制在 500 字以内')
        finally:
            self._cleanup_sessions(sid)

    def test_ask_rejects_unknown_product(self):
        """未知作物明确拒绝，不静默退化成泛泛回答。"""
        sid = self._login()
        try:
            response = self._ask({'question': '荔枝叶子发黄怎么办', 'product': 'no-such'}, sid)
            self.assertEqual(response.status_code, 400)
            body = json.loads(response.data)
            self.assertFalse(body['success'])
            self.assertEqual(body['code'], 'unknown_product')
            self.assertEqual(body['message'], u'暂不支持该农产品，请从列表中选择')
        finally:
            self._cleanup_sessions(sid)

    def test_ask_without_upstream_is_503_ai_not_configured(self):
        """上游未配置时明确失败，绝不返回伪装成正常回答的兜底文案。"""
        import ai.client as ai_client
        sid = self._login()
        original = ai_client.ai_configured
        try:
            ai_client.ai_configured = lambda: False
            response = self._ask({'question': '荔枝叶子发黄怎么办', 'product': 'lychee'}, sid)
        finally:
            ai_client.ai_configured = original
            self._cleanup_sessions(sid)
        self.assertEqual(response.status_code, 503)
        body = json.loads(response.data)
        self.assertFalse(body['success'])
        self.assertEqual(body['code'], 'ai_not_configured')
        self.assertEqual(body['message'],
                         u'AI 农技问答尚未启用，请联系平台管理员。'
                         u'如需即时帮助，可咨询当地农技站或拨打 12316 三农服务热线。')

    def test_ask_stream_rejects_bad_payload_before_touching_the_upstream(self):
        """流式接口与同步接口共用同一套入参校验，错误码一致。"""
        sid = self._login()
        try:
            response = self.client.post(
                '/api/agriculture/ask/stream',
                data=json.dumps({'question': 'x' * 501, 'product': 'lychee'}),
                content_type='application/json', headers={'X-Session-Id': sid})
            self.assertEqual(response.status_code, 400)
            body = json.loads(response.data)
            self.assertEqual(body['code'], 'question_too_long')
        finally:
            self._cleanup_sessions(sid)

    def test_ask_stream_without_upstream_is_503_ai_not_configured(self):
        import ai.client as ai_client
        sid = self._login()
        original = ai_client.ai_configured
        try:
            ai_client.ai_configured = lambda: False
            response = self.client.post(
                '/api/agriculture/ask/stream',
                data=json.dumps({'question': '荔枝叶子发黄怎么办', 'product': 'lychee'}),
                content_type='application/json', headers={'X-Session-Id': sid})
        finally:
            ai_client.ai_configured = original
            self._cleanup_sessions(sid)
        self.assertEqual(response.status_code, 503)
        body = json.loads(response.data)
        self.assertFalse(body['success'])
        self.assertEqual(body['code'], 'ai_not_configured')


class AgriSuggestionsTest(AgricultureDomainTestBase):
    """追问建议：任何失败都退化为静态建议，对前端始终 success=True。"""

    def _suggestions(self, product=None):
        url = '/api/agriculture/suggestions'
        if product is not None:
            url += '?product=%s' % product
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        body = json.loads(response.data)
        self.assertTrue(body['success'])
        return body['suggestions']

    def test_suggestions_return_four_questions_for_a_known_product(self):
        self.assertTrue(self._suggestions('lychee'))

    def test_suggestions_unknown_product_falls_back_to_lychee(self):
        """未知作物不报错：作物名解析有内置兜底表，取不到就退化成泛泛提问。"""
        self.assertTrue(self._suggestions('no-such'))

    def test_suggestions_default_product_is_lychee(self):
        """缺省按荔枝处理，与问答接口的 product 缺省同一口径。"""
        self.assertEqual(self._suggestions(), self._suggestions('lychee'))

    def test_suggestions_are_stable_within_the_cache_ttl(self):
        self.assertEqual(self._suggestions('rice'), self._suggestions('rice'))

    def test_static_fallback_used_when_upstream_is_not_configured(self):
        """上游未配置时退到静态建议：仍是 200 + success=True + 四条内置问题。"""
        import ai.client as ai_client
        original = ai_client.ai_configured
        try:
            ai_client.ai_configured = lambda: False
            suggestions = self._suggestions('lychee')
        finally:
            ai_client.ai_configured = original
        self.assertEqual(suggestions, [
            u'荔枝花期如何管理？', u'如何防治荔枝霜疫霉病？',
            u'荔枝采后怎样恢复树势？', u'荔枝膨大期施什么肥？'])


class AgriDosageNoticeTest(AgricultureDomainTestBase):
    """农技口径：命中用药数值时服务端强制补免责声明（判定函数只在共享层一处）。"""

    def test_shared_layer_owns_the_dosage_predicate(self):
        from shared.agri_dosage import has_chem_dosage
        self.assertTrue(has_chem_dosage(u'每 15 公斤水兑 50 克药剂'))
        self.assertFalse(has_chem_dosage(u'加强通风透光'))

    def test_notice_block_is_appended_to_dosage_answers(self):
        from shared.agri_dosage import has_chem_dosage
        from shared.agri_dosage import CHEM_DOSE_NOTICE_BLOCK
        answer = u'每 15 公斤水兑 50 克药剂，间隔 7 天喷一次'
        self.assertTrue(has_chem_dosage(answer))
        self.assertTrue(CHEM_DOSE_NOTICE_BLOCK.startswith('\n\n——\n'))
        self.assertIn(u'请以所购农药（兽药）标签标注', CHEM_DOSE_NOTICE_BLOCK)


if __name__ == '__main__':
    unittest.main()
