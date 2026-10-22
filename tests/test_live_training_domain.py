#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""直播实训域的行为测试（T13）。

锁住搬迁时最容易搬错的几处：朗读实录的完成度 / 语速 / 必卖点 / 冷场四项指标、
三类实训提交的作物校验分支（客服对练是自由文本、其余走白名单）、
以及实训记录查询的登录要求。
"""

import json
import os
import sys
import unittest
from unittest.mock import patch

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


class LiveReportTest(unittest.TestCase):
    """朗读实录分析：纯规则，同样的输入必然得到同样的输出。"""

    def setUp(self):
        from app import app
        self.app = app
        self.app.config['TESTING'] = True
        self.client = app.test_client()

    def _report(self, **payload):
        body = {'script': '', 'transcript': '', 'duration_sec': 0, 'max_silence_sec': 0}
        body.update(payload)
        r = self.client.post('/api/ecommerce/live/report', data=json.dumps(body),
                             content_type='application/json')
        self.assertEqual(r.status_code, 200, r.data)
        return json.loads(r.data)['report']

    def test_empty_transcript_is_rejected(self):
        r = self.client.post('/api/ecommerce/live/report',
                             data=json.dumps({'script': 'abc', 'transcript': '  '}),
                             content_type='application/json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(json.loads(r.data)['code'], 'empty_transcript')

    def test_over_long_transcript_is_rejected(self):
        r = self.client.post('/api/ecommerce/live/report',
                             data=json.dumps({'script': 'a', 'transcript': '啊' * 5000}),
                             content_type='application/json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(json.loads(r.data)['code'], 'transcript_too_long')

    def test_coverage_counts_distinct_chars(self):
        """完成度按**去重汉字**算，重复朗读同一批字不能刷分。"""
        report = self._report(script='家人们看过来', transcript='家人们看过来家人们看过来')
        self.assertEqual(report['coverage'], 100)
        self.assertEqual(report['missed_chars'], 0)
        self.assertEqual(report['spoken_chars'], 12)

    def test_missed_chars_are_reported(self):
        report = self._report(script='家人们看过来', transcript='家人们')
        self.assertLess(report['coverage'], 100)
        self.assertGreater(report['missed_chars'], 0)

    def test_speed_is_measured_in_real_characters_per_minute(self):
        """语速 = 识别到的字数 ÷ 实际朗读秒数，不靠数标点估算。"""
        report = self._report(script='啊' * 100, transcript='啊' * 100, duration_sec=60)
        self.assertEqual(report['speed_cpm'], 100)
        # 100 字/分低于舒适带下限 180，按线性折算得 55（60 字/分才触底 40）
        self.assertEqual(report['speed_score'], 55)

    def test_speed_inside_the_comfort_band_scores_full(self):
        report = self._report(script='啊' * 240, transcript='啊' * 240, duration_sec=60)
        self.assertEqual(report['speed_cpm'], 240)
        self.assertEqual(report['speed_score'], 100)

    def test_rubric_reports_both_script_and_speech(self):
        """必卖点要分别给出「稿里有没有」与「嘴上有没有」。"""
        report = self._report(script='家人们欢迎来到我的果园', transcript='家人们欢迎')
        items = {it['name']: it for it in report['rubric_items']}
        self.assertIn('开场钩子', items)
        self.assertTrue(items['开场钩子']['in_script'])
        self.assertTrue(items['开场钩子']['said'])
        self.assertTrue(items['产地来源']['in_script'])
        self.assertFalse(items['产地来源']['said'])
        self.assertEqual(report['rubric_total'], len(report['rubric_items']))

    def test_silence_penalty_is_applied(self):
        quiet = self._report(script='啊' * 240, transcript='啊' * 240,
                             duration_sec=60, max_silence_sec=12)
        loud = self._report(script='啊' * 240, transcript='啊' * 240,
                            duration_sec=60, max_silence_sec=0)
        self.assertEqual(quiet['silence_penalty'], 15)
        self.assertEqual(loud['silence_penalty'], 0)
        self.assertLess(quiet['overall_score'], loud['overall_score'])

    def test_report_is_marked_as_rule_based(self):
        report = self._report(script='啊', transcript='啊', duration_sec=10)
        self.assertEqual(report['source'], 'rule')
        self.assertIn('可复现', report['source_note'])


class TrainingSubmitTest(unittest.TestCase):
    """三类实训提交：作物校验分支与落库结果。"""

    def setUp(self):
        from app import app
        self.app = app
        self.app.config['TESTING'] = True
        self.client = app.test_client()
        r = self.client.post('/api/auth/login', data=json.dumps(
            {'username': 'student_demo', 'password': '123456'}),
            content_type='application/json')
        self.session = json.loads(r.data).get('session_id')

    def _submit(self, path, payload):
        return self.client.post(path, data=json.dumps(payload),
                                content_type='application/json',
                                headers={'X-Session-Id': self.session})

    def test_anonymous_is_rejected(self):
        r = self.client.post('/api/ecommerce/live/submit',
                             data=json.dumps({'product': '荔枝', 'script': 'x'}),
                             content_type='application/json')
        self.assertEqual(r.status_code, 401)
        self.assertEqual(json.loads(r.data)['code'], 'login_required')

    def test_unknown_product_is_rejected_for_live_and_copy(self):
        for path in ('/api/ecommerce/live/submit', '/api/ecommerce/copy/submit'):
            r = self._submit(path, {'product': '榴莲', 'script': 'x'})
            self.assertEqual(r.status_code, 400, path)
            self.assertEqual(json.loads(r.data)['code'], 'unknown_product', path)

    def test_customer_service_accepts_free_text_product(self):
        """客服对练的产品是自由文本，不走作物白名单。"""
        r = self._submit('/api/ecommerce/cs/submit', {
            'product': '增城桂味荔枝',
            'transcript': [{'role': 'customer', 'content': '多少钱'},
                           {'role': 'seller', 'content': '十元'}],
        })
        self.assertEqual(r.status_code, 200, r.data)

    def test_customer_service_rejects_empty_product(self):
        r = self._submit('/api/ecommerce/cs/submit', {
            'product': '',
            'transcript': [{'role': 'customer', 'content': '在吗'}],
        })
        self.assertEqual(r.status_code, 400)
        self.assertEqual(json.loads(r.data)['code'], 'empty_product')

    def test_empty_script_is_rejected(self):
        r = self._submit('/api/ecommerce/live/submit', {'product': '荔枝', 'script': '  '})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(json.loads(r.data)['code'], 'empty_script')

    def test_resubmitting_keeps_one_record_and_counts_attempts(self):
        """同一学员同一作物同一 kind 只保留最新一次，attempts 递增。"""
        first = self._submit('/api/ecommerce/live/submit',
                             {'product': '荔枝', 'script': '第一版'})
        self.assertEqual(first.status_code, 200, first.data)
        first_attempts = json.loads(first.data)['attempts']
        second = self._submit('/api/ecommerce/live/submit',
                              {'product': '荔枝', 'script': '第二版更长一点'})
        self.assertEqual(second.status_code, 200, second.data)
        second_attempts = json.loads(second.data)['attempts']
        # 不断言绝对值：库里可能已有该学员的历史提交， attempts 是全账号累计的
        self.assertEqual(second_attempts, first_attempts + 1, 'attempts 应递增 1')
        records = self.client.get('/api/ecommerce/live/records',
                                  headers={'X-Session-Id': self.session})
        self.assertEqual(records.status_code, 200)
        rows = json.loads(records.data)['records']
        lychee = [r for r in rows if r.get('product') == '荔枝']
        self.assertEqual(len(lychee), 1, '同一作物只应保留一条最新提交，不堆多条')
        self.assertEqual(lychee[0]['attempts'], second_attempts)

    def test_records_require_login(self):
        r = self.client.get('/api/ecommerce/live/records')
        self.assertEqual(r.status_code, 401)


class LiveCommentsTest(unittest.TestCase):
    """AI 观众评论未配置时必须快速返回可见不可用，不等待上游超时。"""

    def setUp(self):
        from app import app
        self.app = app
        self.app.config['TESTING'] = True
        self.client = app.test_client()

    def test_unconfigured_ai_returns_unavailable_without_upstream_call(self):
        with patch('domains.live_training.routes.ai_configured', return_value=False), \
                patch('domains.live_training.routes.chat_completion') as upstream:
            response = self.client.post(
                '/api/ecommerce/live/comments',
                data=json.dumps({'speech': '家人们看过来', 'difficulty': '新手'}),
                content_type='application/json',
            )
        self.assertEqual(response.status_code, 503)
        body = json.loads(response.data)
        self.assertFalse(body['success'])
        self.assertEqual(body['code'], 'ai_unavailable')
        upstream.assert_not_called()


if __name__ == '__main__':
    unittest.main()
