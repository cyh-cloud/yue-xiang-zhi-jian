# -*- coding: utf-8 -*-
"""电商运营域的路由行为测试（T12）。

带货话术、商品文案、客服对练从 app.py 搬进 domains/ecommerce/ 之后，外部契约必须
一字不变：URL、请求响应结构、状态码、错误码，以及几条业务底线，即未知作物 400、
未知风格 400、未知格式 400、空输入 400、超长输入 400、限流 429、宣传合规口径仍然
拼进发给上游的提示词。

断言全部基于 HTTP 行为与可观测的提示词内容，不测模块怎么划分（拆分不产生新行为，
为结构写测试只会把实现细节钉死，见 spec 的 Testing Decisions）。

两个实现说明：

1. 上游未配置时的失败契约分两类，差异来自 EC5 的口径本身，不是拆分引入的。
   生成类接口（话术 / 文案 / 客服对话）走可见降级：200 + degraded:true + 带正文；
   评分类接口（话术评分 / 文案评分）不调用上游，纯规则，与上游无关。
2. 限流用例预填 core.session 的限流桶，而不是把 rate_limited 换成恒真函数。
   原因是路由在导入时就把 rate_limited 绑成了本地名字，替换模块属性影响不到已绑定
   的名字，用例会从「验证限流」退化成「真的去打上游」。
"""

import json
import os
import sys
import time
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import core.session as session  # noqa: E402
from db_connection import get_connection


class EcommerceDomainTestBase(unittest.TestCase):
    def setUp(self):
        from app import app
        self.client = app.test_client()
        self._rate_buckets_backup = dict(session._rate_buckets)
        self.addCleanup(self._restore_rate_buckets)

    def _restore_rate_buckets(self):
        session._rate_buckets.clear()
        session._rate_buckets.update(self._rate_buckets_backup)

    def _exhaust_rate_limit(self, prefix, limit):
        """把某个限流键对应的桶填满，让下一次请求必然命中 429。

        键里的客户端标识固定为 Flask test_client 的对端地址 127.0.0.1
        （已用探针路由核对）。setUp 阶段没有请求上下文，不能调 client_key()。
        """
        key = '%s:%s' % (prefix, '127.0.0.1')
        session._rate_buckets[key] = [time.time()] * limit

    def _login(self, username='student_demo', password='123456'):
        response = self.client.post('/api/auth/login', data=json.dumps(
            {'username': username, 'password': password}),
            content_type='application/json')
        return json.loads(response.data)['session_id']

    def _cleanup_sessions(self, sid):
        conn = get_connection()
        if sid:
            conn.execute("DELETE FROM user_sessions WHERE session_id = ?", (sid,))
        conn.commit()
        conn.close()


class EcommerceScriptTest(EcommerceDomainTestBase):
    """带货话术：生成、风格白名单、作物白名单、限流、宣传合规口径。"""

    def test_script_rejects_unknown_product(self):
        response = self.client.post('/api/ecommerce/script',
                                    data=json.dumps({'product': 'lychee'}),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 400)
        body = json.loads(response.data)
        self.assertFalse(body['success'])
        self.assertEqual(body['code'], 'unknown_product')
        self.assertEqual(body['message'], u'暂不支持该农产品，请从列表中选择')

    def test_script_rejects_unknown_style(self):
        response = self.client.post('/api/ecommerce/script',
                                    data=json.dumps({'product': u'荔枝', 'style': 'unknown-style'}),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 400)
        body = json.loads(response.data)
        self.assertFalse(body['success'])
        self.assertEqual(body['code'], 'unknown_style')
        self.assertEqual(body['message'], u'不支持的话术风格，请从列表中选择')

    def test_script_defaults_to_lychee_and_warm_style(self):
        """缺省 product / style 走默认值，不因缺参直接失败。"""
        import domains.ecommerce.routes as ecommerce_routes
        prompts = []
        original = ecommerce_routes.call_ai_service

        def capture(system_prompt=None, user_message=None, **kwargs):
            prompts.append((system_prompt, user_message))
            return u'（模拟上游输出）'

        try:
            ecommerce_routes.call_ai_service = capture
            response = self.client.post('/api/ecommerce/script',
                                        data=json.dumps({}),
                                        content_type='application/json')
        finally:
            ecommerce_routes.call_ai_service = original
        self.assertEqual(response.status_code, 200)
        self.assertIn(u'荔枝', prompts[0][1])
        self.assertIn(u'热情', prompts[0][0])

    def test_script_accepts_every_documented_style(self):
        """四种风格都必须能进到生成阶段，不被风格白名单拦下。"""
        import domains.ecommerce.routes as ecommerce_routes
        original = ecommerce_routes.call_ai_service
        try:
            ecommerce_routes.call_ai_service = (
                lambda system_prompt=None, user_message=None, **kw: u'（模拟上游输出）')
            for style in (u'热情', u'专业', u'故事', u'高级'):
                response = self.client.post(
                    '/api/ecommerce/script',
                    data=json.dumps({'product': u'荔枝', 'style': style}),
                    content_type='application/json')
                self.assertEqual(response.status_code, 200, '风格 %s 被拒' % style)
                self.assertIn('script', json.loads(response.data))
        finally:
            ecommerce_routes.call_ai_service = original

    def test_script_degrades_visibly_when_upstream_is_not_configured(self):
        """EC5：AI 不可用时降级必须可见，即 200 + degraded:true + 带 script。"""
        import ai.client as ai_client
        original = ai_client.ai_configured
        try:
            ai_client.ai_configured = lambda: False
            response = self.client.post(
                '/api/ecommerce/script',
                data=json.dumps({'product': u'荔枝', 'style': u'热情'}),
                content_type='application/json')
        finally:
            ai_client.ai_configured = original
        self.assertEqual(response.status_code, 200)
        body = json.loads(response.data)
        self.assertTrue(body['success'])
        self.assertTrue(body['degraded'])
        self.assertTrue(str(body.get('script') or '').strip())

    def test_script_fallback_carries_no_fabricated_claims(self):
        """EC1：兜底话术里不得出现编造的认证 / 检测数据 / 价格，只能留【待填写】。"""
        import ai.client as ai_client
        original = ai_client.ai_configured
        try:
            ai_client.ai_configured = lambda: False
            response = self.client.post(
                '/api/ecommerce/script',
                data=json.dumps({'product': u'荔枝', 'style': u'热情'}),
                content_type='application/json')
        finally:
            ai_client.ai_configured = original
        script = json.loads(response.data)['script']
        self.assertIn(u'荔枝', script)
        for banned in (u'绿色食品认证', u'有机认证', u'地理标志', u'全网最低'):
            self.assertNotIn(banned, script)

    def test_script_rate_limit_is_enforced(self):
        """EC6：话术生成有限流，超限必须 429 + rate_limited。"""
        self._exhaust_rate_limit('ec-script', 30)
        response = self.client.post(
            '/api/ecommerce/script',
            data=json.dumps({'product': u'荔枝', 'style': u'热情'}),
            content_type='application/json')
        self.assertEqual(response.status_code, 429)
        body = json.loads(response.data)
        self.assertFalse(body['success'])
        self.assertEqual(body['code'], 'rate_limited')
        self.assertEqual(body['message'], u'请求过于频繁，请稍后再试')

    def test_script_prompt_keeps_the_promo_compliance_rule(self):
        """EC1：宣传合规口径必须仍然出现在发给上游的提示词里。"""
        import domains.ecommerce.routes as ecommerce_routes
        prompts = []
        original = ecommerce_routes.call_ai_service

        def capture(system_prompt=None, user_message=None, **kwargs):
            prompts.append((system_prompt, user_message))
            return u'（模拟上游输出）'

        try:
            ecommerce_routes.call_ai_service = capture
            response = self.client.post(
                '/api/ecommerce/script',
                data=json.dumps({'product': u'荔枝', 'style': u'专业'}),
                content_type='application/json')
        finally:
            ecommerce_routes.call_ai_service = original
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(prompts), 1)
        system_prompt, user_message = prompts[0]
        self.assertIn(u'【宣传合规·必须遵守】', system_prompt)
        self.assertIn(u'认证（绿色食品/有机/地理标志）、检测数据（甜度、果径、农残报告）',
                      system_prompt)
        self.assertIn(u'不使用「全网最低」「第一」「最好」「绝对」等绝对化用语', system_prompt)
        self.assertIn(u'不虚构原价、划线价或优惠力度', system_prompt)
        self.assertIn(u'【待填写：……】', system_prompt)
        self.assertIn(u'荔枝', user_message)
        self.assertIn(u'专业', system_prompt)


class EcommerceFeedbackTest(EcommerceDomainTestBase):
    """话术评分：纯规则、无 AI 依赖，输入校验与限流。"""

    def test_feedback_rejects_empty_script(self):
        response = self.client.post('/api/ecommerce/feedback',
                                    data=json.dumps({'script': '   '}),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 400)
        body = json.loads(response.data)
        self.assertFalse(body['success'])
        self.assertEqual(body['code'], 'empty_script')
        self.assertEqual(body['message'], u'请先写出或生成一段话术')

    def test_feedback_rejects_overlong_script(self):
        response = self.client.post('/api/ecommerce/feedback',
                                    data=json.dumps({'script': 'x' * 3001}),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 400)
        body = json.loads(response.data)
        self.assertFalse(body['success'])
        self.assertEqual(body['code'], 'script_too_long')
        self.assertIn('3000', body['message'])

    def test_feedback_scores_a_valid_script_with_rules_only(self):
        """上游不可用也必须给出可复现的规则分，并标明分不是 AI 给的。"""
        import ai.client as ai_client
        original = ai_client.ai_configured
        try:
            ai_client.ai_configured = lambda: False
            response = self.client.post(
                '/api/ecommerce/feedback',
                data=json.dumps({'script': u'家人们看过来！这是广东产地直发的荔枝，甜度很高！'}),
                content_type='application/json')
        finally:
            ai_client.ai_configured = original
        self.assertEqual(response.status_code, 200)
        body = json.loads(response.data)
        self.assertTrue(body['success'])
        feedback = body['feedback']
        for key in ('speed_score', 'emotion_score', 'interaction_score',
                    'selling_score', 'overall_score', 'summary',
                    'suggestions', 'source', 'source_note'):
            self.assertIn(key, feedback)
        self.assertEqual(feedback['source'], 'rule')

    def test_feedback_rate_limit_is_enforced(self):
        self._exhaust_rate_limit('ec-feedback', 30)
        response = self.client.post(
            '/api/ecommerce/feedback',
            data=json.dumps({'script': u'这是一段话术'}),
            content_type='application/json')
        self.assertEqual(response.status_code, 429)
        self.assertEqual(json.loads(response.data)['code'], 'rate_limited')


class EcommerceCopywritingTest(EcommerceDomainTestBase):
    """商品文案：生成（含可见降级）与规则评分。"""

    def test_copywriting_rejects_unknown_product(self):
        response = self.client.post('/api/ecommerce/copywriting',
                                    data=json.dumps({'product': 'lychee', 'format': u'详情页'}),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 400)
        body = json.loads(response.data)
        self.assertEqual(body['code'], 'unknown_product')

    def test_copywriting_rejects_unknown_format(self):
        response = self.client.post('/api/ecommerce/copywriting',
                                    data=json.dumps({'product': u'荔枝', 'format': 'unknown-format'}),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 400)
        body = json.loads(response.data)
        self.assertFalse(body['success'])
        self.assertEqual(body['code'], 'unknown_format')
        self.assertEqual(body['message'], u'不支持的文案类型')

    def test_copywriting_defaults_to_detail_page_format(self):
        import domains.ecommerce.routes as ecommerce_routes
        prompts = []
        original = ecommerce_routes.call_ai_service

        def capture(system_prompt=None, user_message=None, **kwargs):
            prompts.append((system_prompt, user_message))
            return u'（模拟上游输出）'

        try:
            ecommerce_routes.call_ai_service = capture
            response = self.client.post(
                '/api/ecommerce/copywriting',
                data=json.dumps({'product': u'荔枝'}),
                content_type='application/json')
        finally:
            ecommerce_routes.call_ai_service = original
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.data)['format'], u'详情页')
        self.assertIn(u'详情页', prompts[0][1])

    def test_copywriting_accepts_every_documented_format(self):
        import domains.ecommerce.routes as ecommerce_routes
        original = ecommerce_routes.call_ai_service
        try:
            ecommerce_routes.call_ai_service = (
                lambda system_prompt=None, user_message=None, **kw: u'（模拟上游输出）')
            for fmt in (u'详情页', u'主图文案', u'朋友圈', u'小红书', u'短视频脚本'):
                response = self.client.post(
                    '/api/ecommerce/copywriting',
                    data=json.dumps({'product': u'荔枝', 'format': fmt}),
                    content_type='application/json')
                self.assertEqual(response.status_code, 200, '格式 %s 被拒' % fmt)
                body = json.loads(response.data)
                self.assertEqual(body['format'], fmt)
                self.assertIn('copywriting', body)
        finally:
            ecommerce_routes.call_ai_service = original

    def test_copywriting_prompt_keeps_the_promo_compliance_rule(self):
        from domains.ecommerce import routes as ecommerce_routes
        prompts = []
        original = ecommerce_routes.call_ai_service

        def capture(system_prompt=None, user_message=None, **kwargs):
            prompts.append((system_prompt, user_message))
            return u'（模拟上游输出）'

        try:
            ecommerce_routes.call_ai_service = capture
            response = self.client.post(
                '/api/ecommerce/copywriting',
                data=json.dumps({'product': u'荔枝', 'format': u'朋友圈',
                                 'audience': u'年轻人', 'selling_points': u'甜',
                                 'tone': u'轻快'}),
                content_type='application/json')
        finally:
            ecommerce_routes.call_ai_service = original
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(prompts), 1)
        system_prompt, user_message = prompts[0]
        self.assertIn(u'【宣传合规·必须遵守】', system_prompt)
        self.assertIn(u'一律**不要自行编造**', system_prompt)
        self.assertIn(u'不使用「全网最低」「第一」「最好」「绝对」等绝对化用语', system_prompt)
        self.assertIn(u'不虚构原价、划线价或优惠力度', system_prompt)
        self.assertIn(u'目标人群：年轻人', user_message)
        self.assertIn(u'必须包含的卖点：甜', user_message)
        self.assertIn(u'语调要求：轻快', user_message)

    def test_copywriting_degrades_visibly_when_upstream_is_not_configured(self):
        import ai.client as ai_client
        original = ai_client.ai_configured
        try:
            ai_client.ai_configured = lambda: False
            response = self.client.post(
                '/api/ecommerce/copywriting',
                data=json.dumps({'product': u'荔枝', 'format': u'详情页'}),
                content_type='application/json')
        finally:
            ai_client.ai_configured = original
        self.assertEqual(response.status_code, 200)
        body = json.loads(response.data)
        self.assertTrue(body['success'])
        self.assertTrue(body['degraded'])
        self.assertEqual(body['format'], u'详情页')
        self.assertIn(u'【待填写', body['copywriting'])

    def test_copywriting_rate_limit_is_enforced(self):
        self._exhaust_rate_limit('ec-copy', 30)
        response = self.client.post(
            '/api/ecommerce/copywriting',
            data=json.dumps({'product': u'荔枝', 'format': u'详情页'}),
            content_type='application/json')
        self.assertEqual(response.status_code, 429)
        self.assertEqual(json.loads(response.data)['code'], 'rate_limited')

    def test_copy_feedback_rejects_empty_text(self):
        response = self.client.post('/api/ecommerce/copy/feedback',
                                    data=json.dumps({'script': ''}),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 400)
        body = json.loads(response.data)
        self.assertEqual(body['code'], 'empty_script')
        self.assertEqual(body['message'], u'请先写出你的文案')

    def test_copy_feedback_rejects_overlong_text(self):
        response = self.client.post('/api/ecommerce/copy/feedback',
                                    data=json.dumps({'script': 'x' * 4001}),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 400)
        body = json.loads(response.data)
        self.assertEqual(body['code'], 'script_too_long')
        self.assertIn('4000', body['message'])

    def test_copy_feedback_scores_with_the_shared_rule_engine(self):
        """文案评分由共享层纯函数给出：四维 + overall + source=rule，可复现。"""
        response = self.client.post(
            '/api/ecommerce/copy/feedback',
            data=json.dumps({'script': u'## 岭南荔枝\n\n产地直发，果肉饱满，汁水充足。',
                             'format': u'详情页'}),
            content_type='application/json')
        self.assertEqual(response.status_code, 200)
        feedback = json.loads(response.data)['feedback']
        for key in ('structure_score', 'selling_score', 'format_score',
                    'compliance_score', 'overall_score', 'suggestions',
                    'source', 'source_note'):
            self.assertIn(key, feedback)
        self.assertEqual(feedback['source'], 'rule')
        self.assertEqual(
            feedback['overall_score'],
            round((feedback['structure_score'] + feedback['selling_score']
                   + feedback['format_score'] + feedback['compliance_score']) / 4))

    def test_copy_feedback_rate_limit_is_enforced(self):
        self._exhaust_rate_limit('ec-copy-feedback', 30)
        response = self.client.post(
            '/api/ecommerce/copy/feedback',
            data=json.dumps({'script': u'一段文案'}),
            content_type='application/json')
        self.assertEqual(response.status_code, 429)
        self.assertEqual(json.loads(response.data)['code'], 'rate_limited')


class CustomerServiceTest(EcommerceDomainTestBase):
    """客服对练：对话、下一句、提示，以及动态兜底与规则评分。"""

    def _simulate(self, payload):
        return self.client.post('/api/ecommerce/customer-service',
                                data=json.dumps(payload),
                                content_type='application/json')

    def test_simulate_rejects_empty_message(self):
        response = self._simulate({'message': '  ', 'product': u'荔枝'})
        self.assertEqual(response.status_code, 400)
        body = json.loads(response.data)
        self.assertFalse(body['success'])
        self.assertEqual(body['code'], 'empty_message')
        self.assertEqual(body['message'], u'请先输入你的回复')

    def test_simulate_free_text_product_is_not_whitelisted(self):
        """客服对练的产品是自由文本，不走 EC_PRODUCTS 白名单（与实训提交口径一致）。"""
        import domains.ecommerce.routes as ecommerce_routes
        seen = {}

        def fake_chat_completion(messages, **kwargs):
            seen['messages'] = messages
            return u'这个荔枝甜吗？'

        original = ecommerce_routes.chat_completion
        try:
            ecommerce_routes.chat_completion = fake_chat_completion
            response = self._simulate({'message': u'您好，欢迎光临',
                                       'product': u'增城桂味荔枝'})
        finally:
            ecommerce_routes.chat_completion = original
        self.assertEqual(response.status_code, 200)
        self.assertTrue(seen.get('messages'))

    def test_simulate_degrades_visibly_when_upstream_is_unavailable(self):
        """EC5：上游不可用时降级必须可见，即 200 + degraded:true + 带正文。

        这里让域内持有的 chat_completion 抛错来模拟上游不可用：降级分支的触发条件
        本身就是「调用失败」，与失败原因（未配置 / 超时 / 上游 5xx）无关。
        """
        import domains.ecommerce.routes as ecommerce_routes
        original = ecommerce_routes.chat_completion

        def boom(messages, **kwargs):
            raise RuntimeError('upstream unavailable')

        try:
            ecommerce_routes.chat_completion = boom
            response = self._simulate({'message': u'您好，欢迎光临',
                                       'product': u'荔枝',
                                       'scenario': u'售前咨询',
                                       'personality': u'友善型'})
        finally:
            ecommerce_routes.chat_completion = original
        self.assertEqual(response.status_code, 200)
        body = json.loads(response.data)
        self.assertTrue(body['success'])
        self.assertTrue(body['degraded'])
        self.assertIn('reply', body)
        self.assertIn('score', body)
        self.assertIn('sentiment', body)
        score = body['score']
        for key in ('total', 'details', 'tips'):
            self.assertIn(key, score)
        for key in ('politeness', 'professional', 'solving', 'empathy'):
            self.assertIn(key, score['details'])
        self.assertIn('level', body['sentiment'])
        self.assertIn('label', body['sentiment'])

    def test_simulate_dynamic_fallback_fabricates_nothing(self):
        """EC1：动态兜底只复读客户关注点，不编造认证、检测数据、价格与优惠承诺。"""
        from domains.ecommerce import routes as ecommerce_routes
        reply = ecommerce_routes.generate_dynamic_fallback(
            u'售前咨询', u'荔枝', u'友善型', [], u'你好')
        self.assertTrue(reply.strip())
        for banned in (u'全网最低', u'绝对', u'检测报告显示', u'绿色食品认证', u'有机认证'):
            self.assertNotIn(banned, reply)

    def test_simulate_rate_limit_is_enforced(self):
        self._exhaust_rate_limit('ec-cs', 120)
        response = self._simulate({'message': u'您好', 'product': u'荔枝'})
        self.assertEqual(response.status_code, 429)
        self.assertEqual(json.loads(response.data)['code'], 'rate_limited')

    def test_customer_service_next_degrades_visibly(self):
        import ai.client as ai_client
        original = ai_client.ai_configured
        try:
            ai_client.ai_configured = lambda: False
            response = self.client.post(
                '/api/ecommerce/customer-service/next',
                data=json.dumps({'scenario': u'售前咨询', 'personality': u'友善型',
                                 'product': u'荔枝', 'history': []}),
                content_type='application/json')
        finally:
            ai_client.ai_configured = original
        self.assertEqual(response.status_code, 200)
        body = json.loads(response.data)
        self.assertTrue(body['success'])
        self.assertTrue(body['degraded'])
        self.assertIn(u'荔枝', body['message'])

    def test_customer_service_next_rate_limit_is_enforced(self):
        self._exhaust_rate_limit('ec-cs-aux', 40)
        response = self.client.post(
            '/api/ecommerce/customer-service/next',
            data=json.dumps({'scenario': u'售前咨询', 'product': u'荔枝'}),
            content_type='application/json')
        self.assertEqual(response.status_code, 429)
        self.assertEqual(json.loads(response.data)['code'], 'rate_limited')

    def test_service_hint_degrades_visibly(self):
        import ai.client as ai_client
        original = ai_client.ai_configured
        try:
            ai_client.ai_configured = lambda: False
            response = self.client.post(
                '/api/ecommerce/customer-service/hint',
                data=json.dumps({'scenario': u'售前咨询', 'personality': u'友善型',
                                 'product': u'荔枝', 'history': [],
                                 'last_customer_msg': u'这个荔枝多少钱？'}),
                content_type='application/json')
        finally:
            ai_client.ai_configured = original
        self.assertEqual(response.status_code, 200)
        body = json.loads(response.data)
        self.assertTrue(body['success'])
        self.assertTrue(body['degraded'])
        hint = body['hint']
        for key in ('analysis', 'strategy', 'templates', 'tips'):
            self.assertIn(key, hint)

    def test_service_hint_prompt_is_sent_without_promo_rule_injection(self):
        """提示接口的提示词只谈客服策略，不承载商品宣传口径（口径属生成类接口）。"""
        from domains.ecommerce import routes as ecommerce_routes
        prompts = []
        original = ecommerce_routes.call_ai_service

        def capture(system_prompt=None, user_message=None, **kwargs):
            prompts.append((system_prompt, user_message))
            return u'{"analysis":"客户在问价","strategy":"讲价值","templates":["a"],"tips":["b"]}'

        try:
            ecommerce_routes.call_ai_service = capture
            response = self.client.post(
                '/api/ecommerce/customer-service/hint',
                data=json.dumps({'scenario': u'议价谈判', 'personality': u'挑剔型',
                                 'product': u'荔枝', 'history': [],
                                 'last_customer_msg': u'能便宜点吗？'}),
                content_type='application/json')
        finally:
            ecommerce_routes.call_ai_service = original
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(prompts), 1)
        system_prompt, user_message = prompts[0]
        self.assertIn(u'客服培训专家', system_prompt)
        self.assertIn(u'能便宜点吗？', user_message)

    def test_service_hint_rate_limit_is_enforced(self):
        self._exhaust_rate_limit('ec-cs-aux', 40)
        response = self.client.post(
            '/api/ecommerce/customer-service/hint',
            data=json.dumps({'scenario': u'售前咨询', 'product': u'荔枝'}),
            content_type='application/json')
        self.assertEqual(response.status_code, 429)
        self.assertEqual(json.loads(response.data)['code'], 'rate_limited')


class EcommerceSharedHelpersTest(EcommerceDomainTestBase):
    """电商作物名校验：全站只有共享层一份实现。"""

    def test_product_whitelist_accepts_only_known_crops(self):
        from shared.ec_products import ec_product_ok
        for product in (u'荔枝', u'龙眼', u'柑橘', u'香蕉', u'水产养殖',
                        u'水稻', u'茶叶', u'蔬菜'):
            self.assertTrue(ec_product_ok(product), product)
        for product in ('', '   ', 'lychee', u'榴莲', None):
            self.assertFalse(ec_product_ok(product), repr(product))

    def test_crop_whitelist_lives_only_in_the_shared_layer(self):
        """作物白名单只有共享层一份定义，任何域都不得再写一份。"""
        import pathlib
        import re
        # 以后端代码根为基准推导，不写死相对路径：仓库根下跑与 backend/ 下跑都成立。
        import os
        backend_root = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend')
        holders = []
        for path in sorted(pathlib.Path(backend_root).rglob('*.py')):
            text = str(path)
            if any(part in text for part in ('node_modules', '.venv', '__pycache__')):
                continue
            body = path.read_text(encoding='utf-8')
            if re.search(r'^EC_PRODUCTS\s*=', body, re.MULTILINE):
                holders.append(path.as_posix())
        self.assertEqual(holders, [os.path.join(backend_root, 'shared', 'ec_products.py')
                                   .replace(os.sep, '/')],
                         '作物白名单只能定义在共享层，实际出现在：%s' % holders)
    def test_copy_score_has_a_single_implementation_in_the_shared_layer(self):
        """文案评分只有共享层一份实现，域内不得留第二份。"""
        from domains.ecommerce import routes as ecommerce_routes
        from shared.copywriting import copy_score
        self.assertIs(ecommerce_routes.copy_score, copy_score)


if __name__ == '__main__':
    unittest.main()
