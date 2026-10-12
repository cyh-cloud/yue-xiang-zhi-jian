# -*- coding: utf-8 -*-
"""本土资源域的路由行为测试（T14）。

方言问答（列表/详情/语音问答）、成功案例（列表/详情）与政策列表从 app.py 搬进
domains/resources/ 之后，外部契约必须一字不变：URL、请求响应结构、状态码、
错误码，以及几条业务底线，即

- 政策只认政府端 `government_policies` 里 is_published=1 的行，全部下架后学员端
  必须真实为空，**绝不回退**到旧 `policies` 表（历史坑：下架后学员端一条没少）；
- 案例与政策的口径说明（来源标注 + 免责声明）必须随内容一起下发；
- 案例只对审核通过的下发，直链拿未通过的案例是 404；
- 方言问答命中用药数值时，服务端必须单独下发 chem_notice。

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


class ResourcesDomainTestBase(unittest.TestCase):
    def setUp(self):
        from app import app
        self.client = app.test_client()


class DialectInfoTest(ResourcesDomainTestBase):
    """方言列表与详情：纯内置知识库，不读数据库、不调用上游。"""

    def test_dialect_list_returns_every_dialect(self):
        response = self.client.get('/api/resources/dialects')
        self.assertEqual(response.status_code, 200)
        body = json.loads(response.data)
        self.assertTrue(body['success'])
        dialects = body['dialects']
        self.assertEqual([d['id'] for d in dialects], ['cantonese', 'hakka', 'teochew'])
        for d in dialects:
            for key in ('id', 'name', 'region', 'emoji', 'areas', 'speakers'):
                self.assertIn(key, d)
            # 列表是摘要视图：短语与快捷问题只在详情里下发
            self.assertNotIn('phrases', d)
            self.assertNotIn('quick_questions', d)

    def test_dialect_info_returns_the_full_detail(self):
        response = self.client.get('/api/resources/dialect-info?dialect=cantonese')
        self.assertEqual(response.status_code, 200)
        body = json.loads(response.data)
        self.assertTrue(body['success'])
        info = body['info']
        self.assertEqual(info['id'], 'cantonese')
        self.assertEqual(info['name'], u'粤语')
        self.assertEqual(info['region'], u'广州话')
        self.assertEqual(info['greeting_meaning'], u'你好！吃饭了吗？')
        self.assertTrue(info['features'])
        self.assertTrue(info['phrases'])
        self.assertTrue(info['quick_questions'])
        for phrase in info['phrases']:
            for key in ('dialect', 'mandarin', 'pinyin'):
                self.assertIn(key, phrase)

    def test_dialect_info_defaults_to_cantonese(self):
        """缺省 dialect 参数时按粤语返回，与拆分前一致。"""
        default = json.loads(self.client.get('/api/resources/dialect-info').data)['info']
        cantonese = json.loads(
            self.client.get('/api/resources/dialect-info?dialect=cantonese').data)['info']
        self.assertEqual(default, cantonese)

    def test_dialect_info_unknown_id_falls_back_to_cantonese(self):
        """未知方言不报错，退回粤语（不暴露 404，也不编造一种方言）。"""
        response = self.client.get('/api/resources/dialect-info?dialect=no-such')
        self.assertEqual(response.status_code, 200)
        info = json.loads(response.data)['info']
        self.assertEqual(info['id'], 'cantonese')


class VoiceQaTest(ResourcesDomainTestBase):
    """方言语音问答：成功路径走上游，失败降级到本地方言话术库。"""

    def _voice(self, payload):
        import domains.resources.routes as module
        answer = payload.pop('__answer__', None)
        original_chat = module.chat_completion
        original_call = module.call_ai_service
        try:
            module.chat_completion = lambda messages, **kw: answer or u'荔枝要落春肥，每棵施二十到三十斤。'
            module.call_ai_service = lambda **kw: json.dumps(
                [u'追问一', u'追问二', u'追问三', u'追问四'], ensure_ascii=False)
            return self.client.post('/api/resources/voice',
                                    data=json.dumps(payload),
                                    content_type='application/json')
        finally:
            module.chat_completion = original_chat
            module.call_ai_service = original_call

    def test_voice_answers_in_the_requested_dialect(self):
        response = self._voice({'text': u'荔枝点样施肥？', 'dialect': 'cantonese'})
        self.assertEqual(response.status_code, 200)
        body = json.loads(response.data)
        self.assertTrue(body['success'])
        result = body['result']
        self.assertEqual(result['source'], 'ai')
        self.assertEqual(result['dialect'], 'cantonese')
        self.assertEqual(result['dialect_name'], u'粤语')
        self.assertEqual(result['text'], u'荔枝点样施肥？')
        self.assertEqual(result['answer'], u'荔枝要落春肥，每棵施二十到三十斤。')
        self.assertEqual(result['suggestions'], [u'追问一', u'追问二', u'追问三'])

    def test_voice_carries_history_into_the_upstream_call(self):
        """对话历史按 user/bot 交替进入上下文。"""
        import domains.resources.routes as module
        seen = {}
        history = [{'user': u'问题一', 'bot': u'回答一'}, {'user': u'问题二', 'bot': u'回答二'}]

        def fake_chat(messages, **kw):
            seen['messages'] = messages
            return u'好'

        original_chat = module.chat_completion
        original_call = module.call_ai_service
        try:
            module.chat_completion = fake_chat
            module.call_ai_service = lambda **kw: '[]'
            self.client.post('/api/resources/voice', data=json.dumps(
                {'text': u'再问', 'dialect': 'hakka', 'history': history}),
                content_type='application/json')
        finally:
            module.chat_completion = original_chat
            module.call_ai_service = original_call
        messages = seen['messages']
        self.assertEqual(messages[0]['role'], 'system')
        self.assertIn(u'客家话', messages[0]['content'])
        self.assertEqual(messages[1], {"role": "user", "content": u'问题一'})
        self.assertEqual(messages[2], {"role": "assistant", "content": u'回答一'})
        self.assertEqual(messages[3], {"role": "user", "content": u'问题二'})
        self.assertEqual(messages[4], {"role": "assistant", "content": u'回答二'})
        self.assertEqual(messages[-1], {"role": "user", "content": u'再问'})

    def test_voice_without_text_is_rejected(self):
        """没收到内容时明确失败，不去打扰上游。"""
        response = self.client.post('/api/resources/voice',
                                    data=json.dumps({'text': '', 'dialect': 'cantonese'}),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 200)
        body = json.loads(response.data)
        self.assertFalse(body['success'])
        self.assertEqual(body['message'], u'未收到内容')

    def test_voice_falls_back_to_the_dialect_phrasebook(self):
        """上游失败时降到本地方言话术库，仍 200 + source=fallback。"""
        import domains.resources.routes as module
        original_chat = module.chat_completion
        try:
            def boom(messages, **kw):
                raise RuntimeError('upstream unavailable')
            module.chat_completion = boom
            response = self.client.post(
                '/api/resources/voice',
                data=json.dumps({'text': u'荔枝点样施肥', 'dialect': 'cantonese'}),
                content_type='application/json')
        finally:
            module.chat_completion = original_chat
        self.assertEqual(response.status_code, 200)
        body = json.loads(response.data)
        self.assertTrue(body['success'])
        result = body['result']
        self.assertEqual(result['source'], 'fallback')
        self.assertEqual(result['dialect_name'], u'粤语')
        self.assertTrue(result['answer'])
        self.assertTrue(result['suggestions'])

    def test_voice_answer_with_dosage_carries_the_chem_notice(self):
        """命中用药数值时单独下发免责声明字段，三个领域同一口径。"""
        from shared.agri_dosage import CHEM_DOSE_NOTICE
        response = self._voice({'text': u'荔枝点样施肥？', 'dialect': 'cantonese'})
        result = json.loads(response.data)['result']
        self.assertEqual(result['chem_notice'], CHEM_DOSE_NOTICE)
        self.assertIn(u'请以所购农药（兽药）标签标注', result['chem_notice'])

    def test_voice_answer_without_dosage_has_no_chem_notice(self):
        response = self._voice({'text': u'龙眼几时可以摘？', 'dialect': 'cantonese',
                               '__answer__': u'龙眼一般中秋前后熟，睇下枝头转黄就可以摘。'})
        result = json.loads(response.data)['result']
        self.assertEqual(result['chem_notice'], '')

    def test_voice_is_rate_limited(self):
        """限流命中时 429 + rate_limited，错误体结构与其它 AI 路由一致。"""
        import domains.resources.routes as module
        original = module.rate_limited
        try:
            module.rate_limited = lambda key, limit: True
            response = self.client.post(
                '/api/resources/voice',
                data=json.dumps({'text': u'你好', 'dialect': 'cantonese'}),
                content_type='application/json')
        finally:
            module.rate_limited = original
        self.assertEqual(response.status_code, 429)
        body = json.loads(response.data)
        self.assertFalse(body['success'])
        self.assertEqual(body['code'], 'rate_limited')
        self.assertEqual(body['message'], u'提问过于频繁，请稍后再试')


class SuccessCaseTest(ResourcesDomainTestBase):
    """成功案例：只下发审核通过的，口径说明随内容一起下发。"""

    def test_case_list_returns_approved_cases_with_notes(self):
        response = self.client.get('/api/resources/cases')
        self.assertEqual(response.status_code, 200)
        body = json.loads(response.data)
        self.assertTrue(body['success'])
        for key in ('source_note', 'lessons_note', 'case_review'):
            self.assertIn(key, body)
        for k in ('approved', 'pending', 'rejected', 'total'):
            self.assertIn(k, body['case_review'])
        self.assertEqual(len(body['cases']), body['case_review']['approved'])
        for case in body['cases']:
            self.assertTrue(case.get('sources'), '审核通过的案例仍需带来源')

    def test_case_detail_returns_the_same_case(self):
        listed = json.loads(self.client.get('/api/resources/cases').data)['cases']
        self.assertTrue(listed, '案例列表为空，无法验证详情')
        case_id = listed[0]['id']
        response = self.client.get('/api/resources/cases/%d' % case_id)
        self.assertEqual(response.status_code, 200)
        body = json.loads(response.data)
        self.assertTrue(body['success'])
        self.assertEqual(body['case']['id'], case_id)

    def test_unknown_case_id_is_404(self):
        response = self.client.get('/api/resources/cases/999999')
        self.assertEqual(response.status_code, 404)
        body = json.loads(response.data)
        self.assertFalse(body['success'])
        self.assertEqual(body['message'], u'案例不存在或尚未通过审核')


class PolicyTest(ResourcesDomainTestBase):
    """政策列表：只认政府端已发布政策，下架必须真实生效。"""

    def _set_all_published(self, published):
        conn = database.get_connection()
        try:
            conn.execute("UPDATE government_policies SET is_published = ?", (published,))
            conn.commit()
        finally:
            conn.close()

    def test_policy_list_returns_published_policies_with_notes(self):
        response = self.client.get('/api/resources/policies')
        self.assertEqual(response.status_code, 200)
        body = json.loads(response.data)
        self.assertTrue(body['success'])
        self.assertGreater(len(body['policies']), 0)
        # 口径说明（来源说明 + 免责声明）必须随内容一起下发
        self.assertIn(u'依据公开政策文件整理', body['source_note'])
        self.assertIn(u'不替代官方文件', body['disclaimer'])

    def test_policies_are_empty_after_the_government_unpublishes_everything(self):
        """政府端全部下架后，学员端必须真实为空，绝不回退到旧 policies 表。"""
        from domain_data.resources import policies_data
        # 先确认旧数据源里有内容：回退逻辑一旦复活，这个用例就会抓到它
        self.assertGreater(len(policies_data.get_policies()), 0)
        try:
            self._set_all_published(0)
            response = self.client.get('/api/resources/policies')
        finally:
            self._set_all_published(1)
        self.assertEqual(response.status_code, 200)
        body = json.loads(response.data)
        self.assertTrue(body['success'])
        self.assertEqual(body['policies'], [])
        # 口径说明与内容解耦：空列表时仍然下发，前端据此说明「为什么是空的」
        self.assertIn('source_note', body)
        self.assertIn('disclaimer', body)

    def test_published_state_is_restored_after_the_unpublish_probe(self):
        """上面的用例动过库，这里确认它把发布态还原了（否则会污染后续用例）。"""
        self.assertGreater(len(database.get_government_policies()), 0)


if __name__ == '__main__':
    unittest.main()
