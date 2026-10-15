# -*- coding: utf-8 -*-
"""共享层（core / ai / shared）与农业培训域提示词组的行为测试（T03）。

共享层是横切基建：它一坏，全站跟着坏。这些用例锁住拆分时最容易搬错的几处行为：
会话鉴权的三种结果、角色装饰器的三个分支、限流的窗口与回收、节气计算的已知日期、
朗读评分的边界、文案评分的输入、上游未配置时的失败形态、统一错误响应的形状。
"""

import os
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import ai.client as ai_client  # noqa: E402
import core.session as session  # noqa: E402
from core.errors import error_response  # noqa: E402
from shared.agri_dosage import has_chem_dosage  # noqa: E402
from shared.copywriting import copy_score  # noqa: E402
from shared.live_reading import live_cjk, live_speed_score  # noqa: E402
from shared.options import category_option_list  # noqa: E402
from db_connection import get_connection
from shared.solar_terms import solar_terms, solar_terms_of_month  # noqa: E402


class SessionAuthTest(unittest.TestCase):
    """会话鉴权的三种结果：未登录 / 会话无效 / 正常取到用户。"""

    def setUp(self):
        from app import app
        self.app = app
        self.ctx = app.test_request_context('/api/health')
        self.ctx.push()
        self.addCleanup(self.ctx.pop)

    def test_missing_session_header_returns_none(self):
        self.assertIsNone(session.get_session_user())

    def test_unknown_session_returns_none(self):
        from flask import request
        request.headers = {'X-Session-Id': 'no-such-session-id'}
        self.assertIsNone(session.get_session_user())

    def test_valid_session_returns_user(self):
        import json
        from flask import request
        client = self.app.test_client()
        r = client.post('/api/auth/login', data=json.dumps(
            {'username': 'student_demo', 'password': '123456'}),
            content_type='application/json')
        session_id = json.loads(r.data)['session_id']
        try:
            request.headers = {'X-Session-Id': session_id}
            user = session.get_session_user()
            self.assertEqual(user['username'], 'student_demo')
        finally:
            conn = get_connection()
            conn.execute("DELETE FROM user_sessions WHERE session_id = ?", (session_id,))
            conn.commit()
            conn.close()


class RequireRoleTest(unittest.TestCase):
    """角色装饰器的三个分支：未登录 401、角色不符 403、停用 403。"""

    def setUp(self):
        from app import app
        self.app = app

    def _call(self, user):
        import core.session as cs

        @session.require_role('teacher')
        def view():
            return 'ok'

        with self.app.test_request_context('/api/probe'):
            if user is not None:
                original = cs.get_session_user
                cs.get_session_user = lambda: user
                self.addCleanup(setattr, cs, 'get_session_user', original)
            return view()

    def test_anonymous_is_401(self):
        response, status = self._call(None)
        self.assertEqual(status, 401)

    def test_wrong_role_is_403(self):
        response, status = self._call({'username': 's', 'role': 'student', 'status': 'active'})
        self.assertEqual(status, 403)

    def test_suspended_user_is_403(self):
        response, status = self._call(
            {'username': 't', 'role': 'teacher', 'status': 'suspended'})
        self.assertEqual(status, 403)

    def test_matching_role_passes_through(self):
        self.assertEqual(
            self._call({'username': 't', 'role': 'teacher', 'status': 'active'}), 'ok')


class RateLimitTest(unittest.TestCase):
    """限流：窗口内计数、超限拒绝、过期后回收。"""

    def setUp(self):
        self._saved = dict(session._rate_buckets)
        self.addCleanup(self._restore)

    def _restore(self):
        session._rate_buckets.clear()
        session._rate_buckets.update(self._saved)

    def test_counts_within_window_then_rejects(self):
        key = 't03-probe-window'
        self.assertFalse(session.rate_limited(key, 3, window=300))
        self.assertFalse(session.rate_limited(key, 3, window=300))
        self.assertFalse(session.rate_limited(key, 3, window=300))
        self.assertTrue(session.rate_limited(key, 3, window=300))

    def test_entries_expire_after_the_window(self):
        key = 't03-probe-expire'
        self.assertFalse(session.rate_limited(key, 1, window=300))
        session._rate_buckets[key][0] -= 301
        self.assertFalse(session.rate_limited(key, 1, window=300))

    def test_expired_buckets_are_reclaimed(self):
        for i in range(2100):
            session._rate_buckets['t03-flood-%d' % i] = [0.0]
        session.rate_limited('t03-trigger', 5, window=300)
        self.assertLess(len(session._rate_buckets), 2100,
                        '过期桶必须被回收，否则字典随 IP 数无限增长')

    def test_client_key_ignores_forged_forwarded_for_by_default(self):
        from app import app
        with app.test_request_context('/api/health', headers={'X-Forwarded-For': '1.2.3.4'},
                                      environ_base={'REMOTE_ADDR': '10.0.0.9'}):
            self.assertEqual(session.client_key(), '10.0.0.9')


class ErrorResponseTest(unittest.TestCase):
    """统一错误响应：形状与既有手写响应一致，code 缺省时不下发。"""

    def setUp(self):
        from app import app
        self.app = app

    def test_body_shape_without_code(self):
        with self.app.test_request_context('/api/health'):
            body, status = error_response('请先登录', status=401)
        self.assertEqual(status, 401)
        self.assertEqual(body.get_json(), {"success": False, "message": "请先登录"})

    def test_body_shape_with_code(self):
        with self.app.test_request_context('/api/health'):
            body, status = error_response('过于频繁', code='rate_limited', status=429)
        self.assertEqual(status, 429)
        self.assertEqual(body.get_json(),
                         {"success": False, "code": "rate_limited", "message": "过于频繁"})


class SolarTermsTest(unittest.TestCase):
    """节气计算：已知日期必须算对（基准来自权威节气表）。"""

    def test_known_dates(self):
        expected = {
            '小寒': '2026-01-05',
            '立春': '2026-02-04',
            '春分': '2026-03-20',
            '夏至': '2026-06-21',
            '秋分': '2026-09-23',
            '冬至': '2026-12-22',
        }
        by_name = {t['name']: t for t in solar_terms(2026)}
        for name, date in expected.items():
            self.assertEqual(by_name[name]['date'], date, '%s 算错' % name)

    def test_twenty_four_terms_in_order(self):
        terms = solar_terms(2025)
        self.assertEqual(len(terms), 24)
        self.assertEqual(terms[0]['name'], '小寒')
        self.assertEqual(terms[-1]['name'], '冬至')

    def test_of_month_filters(self):
        october = solar_terms_of_month(2026, 10)
        self.assertEqual([t['name'] for t in october], ['寒露', '霜降'])

    def test_result_is_cached_per_year(self):
        self.assertIs(solar_terms(2027), solar_terms(2027))


class LiveReadingTest(unittest.TestCase):
    """朗读评分：汉字抽取与语速打分的边界。"""

    def test_cjk_keeps_only_han(self):
        self.assertEqual(live_cjk(u'你好，world 123！'), u'你好')
        self.assertEqual(live_cjk(None), '')

    def test_speed_score_bands(self):
        self.assertEqual(live_speed_score(0), 0)
        self.assertEqual(live_speed_score(-5), 0)
        self.assertEqual(live_speed_score(180), 100)
        self.assertEqual(live_speed_score(240), 100)
        self.assertEqual(live_speed_score(300), 100)
        self.assertGreater(live_speed_score(179), 40)
        self.assertGreater(live_speed_score(301), 40)

    def test_speed_score_never_below_floor(self):
        for cpm in (1, 500, 1000, 5000):
            self.assertGreaterEqual(live_speed_score(cpm), 40)


class CopyScoreTest(unittest.TestCase):
    """文案评分：四维都在 0-100，可复现，占位与绝对化用语要扣分。"""

    def test_empty_text_is_scored_not_crashed(self):
        score = copy_score('', '详情页')
        for key in ('structure_score', 'selling_score', 'format_score',
                    'compliance_score', 'overall_score'):
            self.assertIn(key, score)
            self.assertGreaterEqual(score[key], 0)
            self.assertLessEqual(score[key], 100)

    def test_placeholder_and_absolute_wording_lower_compliance(self):
        clean = copy_score(u'荔枝甜香鲜脆，产地直发冷链配送，果肉饱满汁水充足。' * 3, '详情页')
        dirty = copy_score(u'【待填写：口感】全网最好的荔枝，绝对顶级，唯一选择。' * 3, '详情页')
        self.assertLess(dirty['compliance_score'], clean['compliance_score'])
        self.assertTrue(any(u'待填写' in tip for tip in dirty['suggestions']))

    def test_deterministic(self):
        text = u'广东荔枝，产地直发，甜香鲜脆。\n\n\n规格：5斤装'
        self.assertEqual(copy_score(text, '详情页'), copy_score(text, '详情页'))


class ChemDosageTest(unittest.TestCase):
    """农技口径判定：阿拉伯数字、中文数字、间隔期写法都要命中，普通文本不误报。"""

    def test_hits(self):
        for text in (u'每亩用30克', u'兑水60公斤', u'1000倍液', u'稀释1000倍',
                     u'安全间隔期', u'每隔7-10日喷一次', u'每棵大树施二十到三十斤'):
            self.assertTrue(has_chem_dosage(text), u'应当命中：%s' % text)

    def test_misses(self):
        for text in (u'普通文本', '', None, u'今天天气不错'):
            self.assertFalse(has_chem_dosage(text), u'不应命中：%r' % text)


class CategoryOptionListTest(unittest.TestCase):
    """下拉选项：known 里的分类零条也保留，新分类追加在后。"""

    def test_known_zero_count_kept_and_new_appended(self):
        result = category_option_list({'a': 1, 'b': 2}, ['x', 'y'])
        self.assertEqual(result, [
            {"value": 'x', "count": 0},
            {"value": 'y', "count": 0},
            {"value": 'a', "count": 1},
            {"value": 'b', "count": 2},
        ])


class AiClientConfigTest(unittest.TestCase):
    """上游调用模块：未配置时的失败形态，以及模型选择的兜底。"""

    def setUp(self):
        self._saved = {
            'AI_API_KEY': ai_client.AI_API_KEY,
            'AI_CHAT_MODEL': ai_client.AI_CHAT_MODEL,
            'AI_MODEL': ai_client.AI_MODEL,
            'AI_VL_MODEL': ai_client.AI_VL_MODEL,
        }
        self.addCleanup(self._restore)

    def _restore(self):
        for name, value in self._saved.items():
            setattr(ai_client, name, value)

    def test_not_configured_raises_rather_than_faking(self):
        ai_client.AI_API_KEY = ''
        self.assertFalse(ai_client.ai_configured())
        with self.assertRaises(RuntimeError):
            ai_client.call_ai_service('sys', 'user')

    def test_vision_requires_both_key_and_model(self):
        ai_client.AI_API_KEY = 'k'
        ai_client.AI_VL_MODEL = ''
        self.assertFalse(ai_client.ai_vision_configured())
        with self.assertRaises(RuntimeError):
            ai_client.call_ai_vision_service('sys', 'user', [])

    def test_chat_model_falls_back_to_default(self):
        ai_client.AI_CHAT_MODEL = ''
        ai_client.AI_MODEL = 'text-model'
        self.assertEqual(ai_client.chat_model(), 'text-model')
        ai_client.AI_CHAT_MODEL = 'chat-model'
        self.assertEqual(ai_client.chat_model(), 'chat-model')


class AppFactoryTest(unittest.TestCase):
    """应用工厂：产出的应用带跨域白名单与应用配置，路由可注册。"""

    def test_factory_builds_usable_app(self):
        from core.app_factory import create_app
        fresh = create_app()
        self.assertEqual(fresh.config['MAX_CONTENT_LENGTH'], 16 * 1024 * 1024)
        # 工厂只管创建与装配，路由挂在入口文件上，所以未注册路由返回 404
        self.assertEqual(fresh.test_client().get('/api/health').status_code, 404)

    def test_cors_only_allows_local_origins_on_api(self):
        from core.app_factory import create_app
        client = create_app().test_client()
        allowed = client.get('/api/health', headers={'Origin': 'http://localhost:5173'})
        self.assertEqual(allowed.headers.get('Access-Control-Allow-Origin'),
                         'http://localhost:5173')
        denied = client.get('/api/health', headers={'Origin': 'http://evil.example'})
        self.assertIsNone(denied.headers.get('Access-Control-Allow-Origin'))

    def test_entry_app_comes_from_the_factory(self):
        import app as app_module
        from flask import Flask
        self.assertIsInstance(app_module.app, Flask)
        self.assertEqual(app_module.create_app.__module__, 'core.app_factory')


class AgriculturePromptsTest(unittest.TestCase):
    """农业培训域提示词组：作物名解析的三级回退与提示词拼装。"""

    def test_known_product_gets_its_name(self):
        from domains.agriculture.prompts import agriculture_product_name
        self.assertEqual(agriculture_product_name('lychee'), u'荔枝')
        self.assertEqual(agriculture_product_name('rice'), u'水稻')

    def test_unknown_and_empty_fall_back(self):
        from domains.agriculture.prompts import agriculture_product_name
        self.assertEqual(agriculture_product_name('no-such-product'), u'广东特色农产品')
        self.assertEqual(agriculture_product_name(''), u'广东特色农产品')
        self.assertEqual(agriculture_product_name(None), u'广东特色农产品')

    def test_system_prompt_embeds_product_name(self):
        from domains.agriculture.prompts import agri_system_prompt
        prompt = agri_system_prompt('lychee')
        self.assertIn(u'荔枝', prompt)
        self.assertIn(u'农业技术专家', prompt)

    def test_shared_layer_holds_the_single_agri_notice_copy(self):
        """农技口径的免责声明由共享层持有唯一一份：问答、诊断、方言问答三个领域共用。"""
        import shared
        self.assertTrue(hasattr(shared, 'CHEM_DOSE_NOTICE'))
        self.assertTrue(hasattr(shared, 'CHEM_DOSE_NOTICE_BLOCK'))
        self.assertTrue(shared.CHEM_DOSE_NOTICE_BLOCK.startswith('\n\n——\n'))
        self.assertTrue(shared.CHEM_DOSE_NOTICE_BLOCK.endswith(shared.CHEM_DOSE_NOTICE))
        self.assertIn(u'请以所购农药（兽药）标签标注', shared.CHEM_DOSE_NOTICE)

    def test_agriculture_domain_re_exports_the_shared_notice(self):
        """农业培训域经 prompts 转发同一份文案，不持有第二份。"""
        from domains.agriculture import prompts
        import shared
        self.assertIs(prompts.CHEM_DOSE_NOTICE, shared.CHEM_DOSE_NOTICE)
        self.assertIs(prompts.CHEM_DOSE_NOTICE_BLOCK, shared.CHEM_DOSE_NOTICE_BLOCK)


if __name__ == '__main__':
    unittest.main()
