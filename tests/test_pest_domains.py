# -*- coding: utf-8 -*-
"""病虫害诊断域与病虫害速查域的路由行为测试（T11）。

文字诊断与图片诊断、本地知识库降级匹配、结论来源标注，以及按作物的病虫害速查，
从 app.py 搬进 domains/pest/ 之后，外部契约必须一字不变：URL、请求响应结构、
状态码、错误码，以及几条业务底线，即图片张数上限、单张大小上限、图片类型白名单、
上游不可用时降级到本地知识库、降级结论仍带来源角标与免责说明、未知作物明确 400。

断言全部基于 HTTP 行为，不测模块怎么划分（拆分不产生新行为，为结构写测试只会
把实现细节钉死，见 spec 的 Testing Decisions）。
"""

import base64
import json
import os
import sys
import unittest
from db_connection import get_connection

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


# 一张合法的最小 PNG data URL，供「成功路径」用例使用。
PNG_DATA_URL = 'data:image/png;base64,' + base64.b64encode(
    b'\x89PNG\r\n\x1a\n' + b'x' * 32).decode()

# 超过单张上限（4MB）的图片：base64 长度按 4/3 膨胀，故取 6M 个字符，
# 解码后约 4.5MB，稳定越过 DIAG_MAX_IMAGE_BYTES。
HUGE_DATA_URL = 'data:image/png;base64,' + ('A' * (6 * 1024 * 1024))

# 本地知识库能匹配上的症状描述（与荔枝炭疽病的典型症状高度重合）。
MATCHING_SYMPTOMS = u'叶片出现褐色斑点，边缘枯黄，病斑上生出黑色小点'


class PestDomainTestBase(unittest.TestCase):
    def setUp(self):
        from app import app
        self.client = app.test_client()

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

    def _diagnose(self, payload, sid=None):
        headers = {'X-Session-Id': sid} if sid else {}
        return self.client.post('/api/agriculture/diagnose',
                                data=json.dumps(payload),
                                content_type='application/json',
                                headers=headers)


class PestDiagnosisTest(PestDomainTestBase):
    """病虫害诊断域：文字与图片诊断、知识库降级、来源角标。"""

    def test_text_diagnosis_uses_the_upstream_and_tags_the_ai_source(self):
        """成功路径：AI 返回合法 JSON 时下发诊断，并打上 AI 来源角标。"""
        import ai.client as ai_client
        diagnosis_payload = {
            "disease": u"荔枝炭疽病",
            "severity": u"中度",
            "symptoms": [u"叶片出现圆形褐色斑点"],
            "treatment": [u"剪除病枝病叶并集中烧毁"],
            "prevention": [u"增施有机肥增强树势"],
            "timing": u"发病初期",
            "note": u"建议结合当地农技站指导进行防治",
            # 契约里没有 confidence，模型自作主张带上时服务端必须剔除。
            "confidence": 0.93,
        }
        sid = self._login()
        original = ai_client.ai_configured
        original_call = ai_client.call_ai_service
        try:
            ai_client.ai_configured = lambda: True
            ai_client.call_ai_service = lambda **kw: json.dumps(
                diagnosis_payload, ensure_ascii=False)
            response = self._diagnose(
                {'crop': 'lychee', 'symptoms': MATCHING_SYMPTOMS}, sid)
        finally:
            ai_client.ai_configured = original
            ai_client.call_ai_service = original_call
            self._cleanup_sessions(sid)

        self.assertEqual(response.status_code, 200)
        body = json.loads(response.data)
        self.assertTrue(body['success'])
        diagnosis = body['diagnosis']
        self.assertEqual(diagnosis['disease'], u'荔枝炭疽病')
        self.assertEqual(diagnosis['crop'], u'荔枝')
        self.assertIn('crop_icon', diagnosis)
        self.assertEqual(diagnosis['source'], 'ai')
        self.assertEqual(diagnosis['source_label'], u'AI 模型生成')
        self.assertIn(u'仅供参考', diagnosis['source_note'])
        self.assertNotIn('confidence', diagnosis)

    def test_ai_diagnosis_appends_the_dosage_notice_when_doses_appear(self):
        """AI 结论里出现用药数值时，服务端强制补免责声明（不依赖模型自觉）。"""
        import ai.client as ai_client
        from shared.agri_dosage import CHEM_DOSE_NOTICE
        sid = self._login()
        original = ai_client.ai_configured
        original_call = ai_client.call_ai_service
        try:
            ai_client.ai_configured = lambda: True
            ai_client.call_ai_service = lambda **kw: json.dumps({
                "disease": u"荔枝蒂蛀虫", "severity": u"中度",
                "symptoms": [u"果实被蛀食"], "treatment": [u"每亩用 30 克药剂喷雾"],
                "prevention": [], "timing": u"幼果期",
                "note": u"注意轮换用药",
            }, ensure_ascii=False)
            response = self._diagnose(
                {'crop': 'lychee', 'symptoms': MATCHING_SYMPTOMS}, sid)
        finally:
            ai_client.ai_configured = original
            ai_client.call_ai_service = original_call
            self._cleanup_sessions(sid)

        self.assertEqual(response.status_code, 200)
        note = json.loads(response.data)['diagnosis']['note']
        self.assertTrue(note.endswith(CHEM_DOSE_NOTICE))
        self.assertIn(u'以所购农药（兽药）标签标注', note)

    def test_text_diagnosis_rejects_unknown_crop(self):
        """未知作物明确 400 + unknown_crop，不静默按默认作物处理。"""
        response = self._diagnose({'crop': 'no-such-crop', 'symptoms': u'叶片发黄'})
        self.assertEqual(response.status_code, 400)
        body = json.loads(response.data)
        self.assertFalse(body['success'])
        self.assertEqual(body['code'], 'unknown_crop')
        self.assertEqual(body['message'], u'暂不支持该作物，请从列表中选择')

    def test_text_diagnosis_rejects_too_long_symptoms(self):
        """症状描述超长 400 + symptoms_too_long。"""
        response = self._diagnose({'crop': 'lychee', 'symptoms': u'病' * 501})
        self.assertEqual(response.status_code, 400)
        body = json.loads(response.data)
        self.assertEqual(body['code'], 'symptoms_too_long')
        self.assertEqual(body['message'], u'症状描述过长，请控制在 500 字以内')

    def test_text_diagnosis_rejects_empty_payload(self):
        """文字与图片都没有时 400 + empty_symptoms，不替用户编造症状。"""
        response = self._diagnose({'crop': 'lychee', 'symptoms': ''})
        self.assertEqual(response.status_code, 400)
        body = json.loads(response.data)
        self.assertEqual(body['code'], 'empty_symptoms')

    def test_text_diagnosis_rejects_non_object_body(self):
        response = self.client.post('/api/agriculture/diagnose',
                                    data=json.dumps([1, 2, 3]),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(json.loads(response.data)['code'], 'bad_request')

    def test_text_diagnosis_rejects_non_string_symptoms(self):
        response = self._diagnose({'crop': 'lychee', 'symptoms': 42})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(json.loads(response.data)['code'], 'bad_request')
        self.assertEqual(json.loads(response.data)['message'], u'症状描述应为文本')

    def test_image_diagnosis_rejects_more_than_three_photos(self):
        """图片张数上限：一次最多 3 张，第 4 张 400 + too_many_images。"""
        response = self._diagnose(
            {'crop': 'lychee', 'symptoms': u'叶片有斑点', 'image': [PNG_DATA_URL] * 4})
        self.assertEqual(response.status_code, 400)
        body = json.loads(response.data)
        self.assertEqual(body['code'], 'too_many_images')
        self.assertEqual(body['message'], u'一次最多上传 3 张照片')

    def test_image_diagnosis_rejects_oversized_single_photo(self):
        """单张大小上限：超过 4MB 400 + image_too_large。"""
        response = self._diagnose(
            {'crop': 'lychee', 'symptoms': u'叶片有斑点', 'image': [HUGE_DATA_URL]})
        self.assertEqual(response.status_code, 400)
        body = json.loads(response.data)
        self.assertEqual(body['code'], 'image_too_large')
        self.assertEqual(body['message'], u'单张照片不能超过 4 MB，请换一张更小的图片')

    def test_image_diagnosis_rejects_disallowed_mime_type(self):
        """类型白名单：只收 jpeg / png / webp。"""
        for mime in ('image/gif', 'image/bmp', 'image/svg+xml'):
            response = self._diagnose(
                {'crop': 'lychee', 'symptoms': u'叶片有斑点',
                 'image': ['data:%s;base64,AAAA' % mime]})
            self.assertEqual(response.status_code, 400, mime)
            body = json.loads(response.data)
            self.assertEqual(body['code'], 'bad_image', mime)
            self.assertEqual(body['message'],
                             u'照片格式不受支持，请上传 JPG / PNG / WebP 格式的照片')

    def test_image_diagnosis_rejects_non_data_url(self):
        response = self._diagnose(
            {'crop': 'lychee', 'symptoms': u'叶片有斑点', 'image': ['http://x/y.png']})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(json.loads(response.data)['code'], 'bad_image')

    def test_image_diagnosis_rejects_non_string_item(self):
        response = self._diagnose(
            {'crop': 'lychee', 'symptoms': u'叶片有斑点', 'image': [123]})
        self.assertEqual(response.status_code, 400)
        body = json.loads(response.data)
        self.assertEqual(body['code'], 'bad_image')
        self.assertEqual(body['message'], u'照片格式不正确，请重新选择')

    def test_image_diagnosis_rejects_undecodable_base64(self):
        response = self._diagnose(
            {'crop': 'lychee', 'symptoms': u'叶片有斑点',
             'image': ['data:image/png;base64,!!!not-base64!!!']})
        self.assertEqual(response.status_code, 400)
        body = json.loads(response.data)
        self.assertEqual(body['code'], 'bad_image')
        self.assertEqual(body['message'], u'照片数据无法解析，请重新选择照片')

    def test_image_diagnosis_without_upstream_is_503_ai_not_configured(self):
        """带图请求在上游未配置时直接报错，绝不降级成「不看图」的知识库结论。"""
        import ai.client as ai_client
        sid = self._login()
        original = ai_client.ai_configured
        try:
            ai_client.ai_configured = lambda: False
            response = self._diagnose(
                {'crop': 'lychee', 'symptoms': u'叶片有斑点', 'image': [PNG_DATA_URL]}, sid)
        finally:
            ai_client.ai_configured = original
            self._cleanup_sessions(sid)
        self.assertEqual(response.status_code, 503)
        body = json.loads(response.data)
        self.assertFalse(body['success'])
        self.assertEqual(body['code'], 'ai_not_configured')
        self.assertEqual(body['message'],
                         u'AI 服务尚未启用，暂时无法进行图片诊断。'
                         u'你可以改用文字描述症状，或联系平台管理员；'
                         u'如需即时帮助可拨打 12316 三农服务热线。')

    def test_image_diagnosis_without_vision_model_is_503(self):
        """配了密钥但没配视觉模型：503 + ai_vision_unavailable，同样不降级。"""
        import ai.client as ai_client
        sid = self._login()
        original_configured = ai_client.ai_configured
        original_model = ai_client.AI_VL_MODEL
        try:
            ai_client.ai_configured = lambda: True
            ai_client.AI_VL_MODEL = ''
            response = self._diagnose(
                {'crop': 'lychee', 'symptoms': u'叶片有斑点', 'image': [PNG_DATA_URL]}, sid)
        finally:
            ai_client.ai_configured = original_configured
            ai_client.AI_VL_MODEL = original_model
            self._cleanup_sessions(sid)
        self.assertEqual(response.status_code, 503)
        body = json.loads(response.data)
        self.assertEqual(body['code'], 'ai_vision_unavailable')
        self.assertEqual(body['message'],
                         u'图片诊断功能暂未开放。'
                         u'你可以改用文字描述症状，或联系平台管理员；'
                         u'如需即时帮助可拨打 12316 三农服务热线。')

    def test_image_diagnosis_when_upstream_fails_is_503_ai_unavailable(self):
        """带图且上游真的失败：503 + ai_unavailable，仍不降级。"""
        import ai.client as ai_client
        sid = self._login()
        original_configured = ai_client.ai_configured
        original_call = ai_client.call_ai_vision_service
        try:
            ai_client.ai_configured = lambda: True
            ai_client.call_ai_vision_service = lambda **kw: (_ for _ in ()).throw(
                RuntimeError('upstream down'))
            response = self._diagnose(
                {'crop': 'lychee', 'symptoms': u'叶片有斑点', 'image': [PNG_DATA_URL]}, sid)
        finally:
            ai_client.ai_configured = original_configured
            ai_client.call_ai_vision_service = original_call
            self._cleanup_sessions(sid)
        self.assertEqual(response.status_code, 503)
        body = json.loads(response.data)
        self.assertEqual(body['code'], 'ai_unavailable')

    def test_image_diagnosis_success_uses_the_vision_model(self):
        """带图成功路径走多模态入口，结论同样打 AI 来源角标。"""
        import ai.client as ai_client
        sid = self._login()
        original_configured = ai_client.ai_configured
        original_call = ai_client.call_ai_vision_service
        seen = {}

        def fake_vision(**kwargs):
            seen.update(kwargs)
            return json.dumps({
                "disease": u"荔枝霜疫霉病", "severity": u"重度",
                "symptoms": [u"果实出现褐色病斑"],
                "treatment": [u"重点保护果穗"], "prevention": [u"采后彻底清园"],
                "timing": u"花穗期", "note": u"注意天气变化",
            }, ensure_ascii=False)

        try:
            ai_client.ai_configured = lambda: True
            ai_client.call_ai_vision_service = fake_vision
            response = self._diagnose(
                {'crop': 'lychee', 'image': [PNG_DATA_URL, PNG_DATA_URL]}, sid)
        finally:
            ai_client.ai_configured = original_configured
            ai_client.call_ai_vision_service = original_call
            self._cleanup_sessions(sid)

        self.assertEqual(response.status_code, 200)
        body = json.loads(response.data)
        self.assertTrue(body['success'])
        self.assertEqual(body['diagnosis']['disease'], u'荔枝霜疫霉病')
        self.assertEqual(body['diagnosis']['source'], 'ai')
        self.assertEqual(len(seen['images']), 2)
        self.assertEqual(seen['images'][0]['mime'], 'image/png')

    def test_text_diagnosis_without_upstream_falls_back_to_the_knowledge_base(self):
        """上游未配置时纯文字请求降级到本地知识库，结论带来源角标与免责说明。"""
        import ai.client as ai_client
        sid = self._login()
        original = ai_client.ai_configured
        try:
            ai_client.ai_configured = lambda: False
            response = self._diagnose(
                {'crop': 'lychee', 'symptoms': MATCHING_SYMPTOMS}, sid)
        finally:
            ai_client.ai_configured = original
            self._cleanup_sessions(sid)

        self.assertEqual(response.status_code, 200)
        body = json.loads(response.data)
        self.assertTrue(body['success'])
        diagnosis = body['diagnosis']
        self.assertEqual(diagnosis['source'], 'knowledge_base')
        self.assertEqual(diagnosis['source_label'], u'本地知识库匹配')
        self.assertIn(u'AI 服务当前不可用', diagnosis['source_note'])
        self.assertIn(u'仅供参考', diagnosis['source_note'])
        self.assertIn(u'请以当地农技站指导为准', diagnosis['source_note'])
        self.assertTrue(diagnosis['disease'])
        self.assertEqual(diagnosis['crop'], u'荔枝')
        self.assertIn('crop_icon', diagnosis)
        self.assertEqual(diagnosis['timing'], u'发病初期为最佳防治期')
        self.assertEqual(diagnosis['note'], u'建议结合当地农技站指导进行防治')
        self.assertNotIn('confidence', diagnosis)

    def test_text_diagnosis_without_match_reports_no_match(self):
        """知识库没匹配上时如实说没识别出来，不硬凑一个结论。"""
        import ai.client as ai_client
        sid = self._login()
        original = ai_client.ai_configured
        try:
            ai_client.ai_configured = lambda: False
            response = self._diagnose({'crop': 'lychee', 'symptoms': u'毛毛终经'}, sid)
        finally:
            ai_client.ai_configured = original
            self._cleanup_sessions(sid)
        self.assertEqual(response.status_code, 200)
        body = json.loads(response.data)
        self.assertFalse(body['success'])
        self.assertEqual(body['code'], 'no_match')
        self.assertIn(u'未能从描述中匹配到对应的病害', body['message'])

    def test_diagnosis_without_session_is_not_blocked(self):
        """诊断接口不带登录门禁（与拆分前一致：公开入口，靠限流保护）。"""
        import ai.client as ai_client
        original = ai_client.ai_configured
        try:
            ai_client.ai_configured = lambda: False
            response = self._diagnose({'crop': 'lychee', 'symptoms': MATCHING_SYMPTOMS})
        finally:
            ai_client.ai_configured = original
        self.assertEqual(response.status_code, 200)
        self.assertTrue(json.loads(response.data)['success'])


class PestKnowledgeTest(PestDomainTestBase):
    """病虫害速查域：只读的条目查询与来源标注。"""

    def test_entries_carry_source_and_disclaimer(self):
        response = self.client.get('/api/agriculture/pest-knowledge')
        self.assertEqual(response.status_code, 200)
        body = json.loads(response.data)
        self.assertTrue(body['success'])

        self.assertGreater(len(body['crops']), 0)
        for crop in body['crops']:
            for key in ('id', 'name', 'icon', 'summary', 'count'):
                self.assertIn(key, crop)

        self.assertGreater(len(body['entries']), 0)
        for entry in body['entries']:
            for key in ('id', 'crop', 'crop_name', 'crop_icon', 'disease', 'kind',
                        'symptoms', 'treatment', 'prevention', 'sources', 'is_verified'):
                self.assertIn(key, entry)
            self.assertIn(entry['kind'], ('disease', 'pest'))
            # 来源标注：每条都带可溯源的出处结构，不是空列表。
            self.assertGreater(len(entry['sources']), 0)
            for source in entry['sources']:
                for key in ('key', 'name', 'org', 'doc_type', 'date'):
                    self.assertIn(key, source)

        self.assertIn(u'农业农村部门', body['disclaimer'])
        self.assertIn(u'以你所购农药标签标注为准', body['disclaimer'])
        stats = body['stats']
        for key in ('crops', 'entries', 'with_image', 'verified'):
            self.assertIn(key, stats)
        self.assertEqual(stats['entries'], len(body['entries']))

    def test_crop_filter_returns_only_that_crop(self):
        response = self.client.get('/api/agriculture/pest-knowledge?crop=lychee')
        self.assertEqual(response.status_code, 200)
        body = json.loads(response.data)
        self.assertGreater(len(body['entries']), 0)
        for entry in body['entries']:
            self.assertEqual(entry['crop'], 'lychee')
            self.assertEqual(entry['crop_name'], u'荔枝')

    def test_kind_filter_returns_only_that_kind(self):
        response = self.client.get('/api/agriculture/pest-knowledge?kind=pest')
        self.assertEqual(response.status_code, 200)
        body = json.loads(response.data)
        self.assertGreater(len(body['entries']), 0)
        for entry in body['entries']:
            self.assertEqual(entry['kind'], 'pest')

    def test_keyword_filter_matches_disease_and_symptoms(self):
        response = self.client.get('/api/agriculture/pest-knowledge?q=' + u'炭疽')
        self.assertEqual(response.status_code, 200)
        body = json.loads(response.data)
        self.assertGreater(len(body['entries']), 0)
        for entry in body['entries']:
            blob = entry['disease'] + (entry['alias'] or '') + (entry['pathogen'] or '') \
                + entry['crop_name'] + ' '.join(entry['symptoms'])
            self.assertIn(u'炭疽', blob)

    def test_keyword_with_no_hit_returns_empty_entries(self):
        response = self.client.get('/api/agriculture/pest-knowledge?q=' + u'不存在的关键词xyz')
        self.assertEqual(response.status_code, 200)
        body = json.loads(response.data)
        self.assertTrue(body['success'])
        self.assertEqual(body['entries'], [])

    def test_unknown_crop_is_rejected(self):
        """未知作物 400 + unknown_crop，与诊断接口同一口径。"""
        response = self.client.get('/api/agriculture/pest-knowledge?crop=no-such-crop')
        self.assertEqual(response.status_code, 400)
        body = json.loads(response.data)
        self.assertFalse(body['success'])
        self.assertEqual(body['code'], 'unknown_crop')
        self.assertEqual(body['message'], u'暂不支持该作物，请从列表中选择')

    def test_unknown_kind_is_rejected(self):
        response = self.client.get('/api/agriculture/pest-knowledge?kind=virus')
        self.assertEqual(response.status_code, 400)
        body = json.loads(response.data)
        self.assertEqual(body['code'], 'bad_request')
        self.assertEqual(body['message'], u'类型筛选仅支持 disease 或 pest')

    def test_entries_without_authorized_photo_report_image_none(self):
        """无授权实拍图的条目 image 为 None，不用示意图冒充真实病征。"""
        response = self.client.get('/api/agriculture/pest-knowledge?crop=lychee')
        body = json.loads(response.data)
        images = [entry['image'] for entry in body['entries']]
        self.assertTrue(any(image is None for image in images))


if __name__ == '__main__':
    unittest.main()
