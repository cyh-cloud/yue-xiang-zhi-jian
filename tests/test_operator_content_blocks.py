# -*- coding: utf-8 -*-
"""运营后台剩下四块内容的对外行为测试（T15）：技艺、方言、招募公告、成功案例。

测试 seam 是 API 层（Flask test client），断言状态码、响应结构与权限结果，
不测模块怎么划分。这里锁住的对外事实，逐条对应票据的验收标准：

1. 四块内容经接口增删改后，前台接口立即返回新值，无需重启；
2. 学员打 /api/operator/* 返回 401 或 403；
3. craft.manage 含 teacher：教师能进技艺后台，但进不了招募后台（能力边界）；
4. 拆平入库的数据按原形状组装回前台（采购指南三层嵌套、案例四个子数组）；
5. 派生字段不可编辑：招募公告的 status / days_left / starts_in 由当天日期算。

⚠️ 本文件跑在真实库上（与既有测试同一口径）。所有写用例都在 finally 里
把库还原：造什么删什么，改什么改回去。理由同
tests/test_operator_content_domains.py —— 这里测的就是「读库这条路产出的响应」，
mock 掉库会漏掉外键级联、sort_order 重组、JSON 列解析这三处真正会出错的地方。
"""

import json
import os
import sys
import unittest

BACKEND = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend')
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from db_connection import get_connection  # noqa: E402
from db_domains import content  # noqa: E402
from db_domains import crafts  # noqa: E402
from db_domains import dialects  # noqa: E402
from db_domains import recruitments  # noqa: E402
from db_domains import resources  # noqa: E402

OPERATOR = ('operator_demo', '123456')
STUDENT = ('student_demo', '123456')
TEACHER = ('teacher_demo', '123456')
SUPER_ADMIN = ('admin_demo', 'admin123')

# 前台接口。运营改完内容后打这些，断言「立即生效、无需重启」。
FRONT_CRAFT = '/api/crafts/embroidery'
FRONT_CRAFT_LIST = '/api/crafts/list'
FRONT_DIALECT = '/api/resources/dialect-info?dialect=cantonese'
FRONT_DIALECTS = '/api/resources/dialects'
# 详情接口单独一个常量：它本身已带 ?dialect=cantonese，拼查询串会重复
FRONT_DIALECT_INFO = '/api/resources/dialect-info'
FRONT_JOBS = '/api/employment/jobs'
FRONT_CASES = '/api/resources/cases'


class OperatorBlocksTestBase(unittest.TestCase):
    """共用的登录与清理工具。"""

    @classmethod
    def setUpClass(cls):
        from app import app
        cls.app = app
        cls.app.config['TESTING'] = True

    def setUp(self):
        self.client = self.app.test_client()

    def _login(self, account=OPERATOR):
        response = self.client.post('/api/auth/login', data=json.dumps(
            {'username': account[0], 'password': account[1]}),
            content_type='application/json')
        body = json.loads(response.data)
        self.assertTrue(body.get('success'), '登录失败：%s' % body)
        return body['session_id']

    def _headers(self, session_id):
        return {'X-Session-Id': session_id}

    def _post(self, path, payload, session_id):
        return self.client.post(path, data=json.dumps(payload),
                                content_type='application/json',
                                headers=self._headers(session_id))

    def _put(self, path, payload, session_id):
        return self.client.put(path, data=json.dumps(payload),
                               content_type='application/json',
                               headers=self._headers(session_id))

    def _delete(self, path, session_id):
        return self.client.delete(path, headers=self._headers(session_id))

    def _cleanup_sessions(self, *session_ids):
        conn = get_connection()
        for sid in session_ids:
            if sid:
                conn.execute("DELETE FROM user_sessions WHERE session_id = ?", (sid,))
        conn.commit()
        conn.close()

    def _cleanup_case(self, case_id):
        """删掉一条案例的正文与审核记录。

        审核记录走 reviews 域的入口，不自己写 DELETE FROM content_reviews：
        那条 SQL 全仓库只允许出现在 reviews.py（T11 收敛），测试同样遵守。
        """
        if case_id is None:
            return
        self._sql("DELETE FROM success_cases WHERE id = ?", (case_id,))
        from db_domains import reviews as reviews_db
        reviews_db.delete_reviews_for('success_case', case_id)

    def _sql(self, statement, params=()):
        conn = get_connection()
        try:
            conn.execute(statement, params)
            conn.commit()
        finally:
            conn.close()


class OperatorCraftsWriteTest(OperatorBlocksTestBase):
    """手工技艺：技艺、步骤、采购分类、采购条目、预算的增删改。"""

    def test_operator_can_create_update_and_delete_a_craft(self):
        """技艺增删改闭环，前台列表与详情立即跟着变。"""
        sid = self._login()
        craft_id = 't15_probe_craft'
        try:
            created = self._post('/api/operator/crafts', {
                'id': craft_id, 'name': u'单测技艺', 'origin': u'单测产地',
                'history': u'单测历史', 'level': u'入门',
            }, sid)
            self.assertEqual(created.status_code, 200, created.data)

            front = {c['id'] for c in json.loads(
                self.client.get(FRONT_CRAFT_LIST).data)['crafts']}
            self.assertIn(craft_id, front, '新技艺没有出现在前台列表里')

            updated = self._put('/api/operator/crafts/%s' % craft_id,
                                {'name': u'单测技艺改', 'level': u'进阶'}, sid)
            self.assertEqual(updated.status_code, 200, updated.data)
            row = crafts.get_craft_row(craft_id)
            self.assertEqual(row['name'], u'单测技艺改')
            self.assertEqual(row['level'], u'进阶')

            self.assertEqual(
                self._delete('/api/operator/crafts/%s' % craft_id, sid).status_code, 200)
            self.assertIsNone(crafts.get_craft_row(craft_id))
            self.assertNotIn(craft_id, {c['id'] for c in json.loads(
                self.client.get(FRONT_CRAFT_LIST).data)['crafts']})
        finally:
            self._sql("DELETE FROM crafts WHERE id = ?", (craft_id,))
            self._cleanup_sessions(sid)

    def test_craft_videos_can_be_created_updated_and_deleted(self):
        """视频教学增删改闭环，前台详情（videos 键）立即跟着变。

        视频原先借代码常量下发，T10 删常量后详情不再带 videos 键，前端的视频教学区
        整块收起。这条锁住「内容在库里、运营改完前台立刻能看到」。
        """
        sid = self._login()
        bvid = '__probe_bvid__'
        try:
            created = self._post('/api/operator/crafts/embroidery/videos', {
                'bvid': bvid, 'title': u'单测视频', 'author': u'单测UP主',
                'duration': 120, 'view_count': 5, 'danmaku': 1, 'like_count': 2,
            }, sid)
            self.assertEqual(created.status_code, 200, created.data)
            video_id = json.loads(created.data)['result']

            detail = json.loads(self.client.get(
                '/api/crafts/embroidery').data)['data']
            mine = [v for v in detail['videos'] if v['bvid'] == bvid]
            self.assertEqual(len(mine), 1, '新视频没有出现在前台详情里')
            self.assertEqual(mine[0]['title'], u'单测视频')
            self.assertEqual(mine[0]['view'], 5, '库里的 view_count 要按前台契约映射成 view')
            self.assertEqual(mine[0]['like'], 2)

            updated = self._put('/api/operator/crafts/videos/%d' % video_id,
                                {'title': u'单测视频改'}, sid)
            self.assertEqual(updated.status_code, 200, updated.data)
            detail = json.loads(self.client.get(
                '/api/crafts/embroidery').data)['data']
            mine = [v for v in detail['videos'] if v['bvid'] == bvid]
            self.assertEqual(mine[0]['title'], u'单测视频改')

            self.assertEqual(
                self._delete('/api/operator/crafts/videos/%d' % video_id, sid).status_code, 200)
            detail = json.loads(self.client.get(
                '/api/crafts/embroidery').data)['data']
            self.assertNotIn(bvid, [v['bvid'] for v in detail['videos']])
        finally:
            self._sql("DELETE FROM craft_videos WHERE bvid = ?", (bvid,))
            self._cleanup_sessions(sid)

    def test_craft_requires_a_name(self):
        """缺名称不落库：列表卡片直接渲染 name，空名就是一张白卡片。"""
        sid = self._login()
        try:
            for payload in ({'id': 't15_probe_craft'},
                            {'id': 't15_probe_craft', 'name': ''},
                            {'name': u'没有 id'}):
                with self.subTest(payload=payload):
                    response = self._post('/api/operator/crafts', payload, sid)
                    self.assertEqual(response.status_code, 400, response.data)
            self.assertIsNone(crafts.get_craft_row('t15_probe_craft'))
        finally:
            self._sql("DELETE FROM crafts WHERE id = ?", ('t15_probe_craft',))
            self._cleanup_sessions(sid)

    def test_steps_can_be_created_updated_and_deleted(self):
        """步骤增删改，前台详情 steps 数组立即跟着变。"""
        sid = self._login()
        step_id = None
        try:
            created = self._post('/api/operator/crafts/embroidery/steps', {
                'title': u'单测步骤', 'desc': u'单测描述', 'tips': u'单测提示',
                'sort_order': 999,
            }, sid)
            self.assertEqual(created.status_code, 200, created.data)
            step_id = json.loads(created.data)['result']

            steps = crafts.get_craft_steps('embroidery')
            added = next(s for s in steps if s['id'] == step_id)
            self.assertEqual(added['title'], u'单测步骤')
            self.assertEqual(added['desc'], u'单测描述')

            self.assertEqual(self._put(
                '/api/operator/crafts/steps/%d' % step_id,
                {'title': u'单测步骤改', 'tips': u'改过的提示'}, sid).status_code, 200)
            updated = next(s for s in crafts.get_craft_steps('embroidery')
                           if s['id'] == step_id)
            self.assertEqual(updated['title'], u'单测步骤改')
            self.assertEqual(updated['tips'], u'改过的提示')

            # 前台详情：steps 是原样组装的数组，新步骤应当出现在里面
            detail = json.loads(self.client.get(FRONT_CRAFT).data)['data']
            titles = [s['title'] for s in detail['steps']]
            self.assertIn(u'单测步骤改', titles)

            self.assertEqual(self._delete(
                '/api/operator/crafts/steps/%d' % step_id, sid).status_code, 200)
            self.assertNotIn(step_id, {s['id'] for s in
                                       crafts.get_craft_steps('embroidery')})
        finally:
            if step_id is not None:
                self._sql("DELETE FROM craft_steps WHERE rowid = ?", (step_id,))
            self._sql("DELETE FROM craft_steps WHERE title LIKE '单测步骤%'")
            self._cleanup_sessions(sid)

    def test_purchase_guide_keeps_its_nested_shape_after_writes(self):
        """验收 4（采购指南）：四张平表写回去，前台三层嵌套形状不变。

        库里 crafts -> craft_purchase_categories -> craft_purchase_items 三层是
        平的，craft_budgets 单独一张；前台要的是
        purchase_guide.categories[].items[] 与 purchase_guide.budget。
        这条用例把三层各改一遍，再断言前台输出仍是原形状。
        """
        sid = self._login()
        item_id = None
        original_budget = crafts.get_craft_budget('embroidery')
        try:
            # 第一层：分类标签改了，前台 categories[].label 立即变
            self.assertEqual(self._put(
                '/api/operator/crafts/embroidery/purchase-categories/essential',
                {'label': u'单测必买'}, sid).status_code, 200)

            # 第二层：在已有分类下加一个条目，前台要落在该分类的 items 里
            created = self._post('/api/operator/crafts/embroidery/purchase-items', {
                'category_key': 'essential', 'name': u'单测物品',
                'price': u'单测价', 'spec': u'单测规格',
                'tip': u'单测提示', 'where': u'单测渠道', 'sort_order': 999,
            }, sid)
            self.assertEqual(created.status_code, 200, created.data)
            item_id = json.loads(created.data)['result']

            # 第三层：预算覆盖写，前台 budget 两档与 buying_tips 都要变
            self.assertEqual(self._put(
                '/api/operator/crafts/embroidery/budget',
                {'starter': u'单测入门预算', 'advanced': u'单测进阶预算',
                 'buying_tips': u'单测采购建议'}, sid).status_code, 200)

            guide = json.loads(self.client.get(FRONT_CRAFT).data)[
                'data']['purchase_guide']
            self.assertEqual(sorted(guide), ['budget', 'buying_tips', 'categories'])
            self.assertEqual(sorted(guide['budget']), ['advanced', 'starter'])
            self.assertEqual(guide['buying_tips'], u'单测采购建议')

            essential = next(c for c in guide['categories'] if c['key'] == 'essential')
            self.assertEqual(essential['label'], u'单测必买')
            item = next((i for i in essential['items'] if i['name'] == u'单测物品'),
                        None)
            self.assertIsNotNone(item, '新条目没有落在它所属分类的 items 里')
            self.assertEqual(item['price'], u'单测价')
            self.assertEqual(item['where'], u'单测渠道')
            # 条目行的键集与其它条目一致（读侧统一组装，不因来源不同而变形）
            self.assertEqual(sorted(item), ['name', 'price', 'spec', 'tip', 'where'])

            # 条目归属的校验：写一个不存在的分类必须拒，否则读侧分组时
            # items.get(c['key'], []) 会静默丢掉它 —— 学员端看不到这条物品，
            # 而运营以为自己写进去了。
            bad = self._post('/api/operator/crafts/embroidery/purchase-items', {
                'category_key': 'no-such-category', 'name': u'单测孤儿条目',
            }, sid)
            self.assertEqual(bad.status_code, 400, bad.data)
            self.assertIn(u'采购分类不存在', json.loads(bad.data)['message'])
        finally:
            if item_id is not None:
                self._sql("DELETE FROM craft_purchase_items WHERE rowid = ?",
                          (item_id,))
            self._sql("DELETE FROM craft_purchase_items WHERE name = '单测孤儿条目'")
            if original_budget:
                self._sql(
                    "UPDATE craft_budgets SET starter = ?, advanced = ?, "
                    "buying_tips = ? WHERE craft_id = 'embroidery'",
                    (original_budget['starter'], original_budget['advanced'],
                     original_budget['buying_tips']))
            self._sql("UPDATE craft_purchase_categories SET label = ? "
                      "WHERE craft_id = 'embroidery' AND key = 'essential'",
                      (u'必买基础工具',))
            self._cleanup_sessions(sid)

    def test_purchase_category_delete_cascades_to_its_items(self):
        """删分类连带删它的条目：前台不能再出现没有分类归属的物品。"""
        sid = self._login()
        item_id = None
        try:
            self._post('/api/operator/crafts/embroidery/purchase-categories', {
                'key': 't15_probe_cat', 'label': u'单测分类',
            }, sid)
            created = self._post('/api/operator/crafts/embroidery/purchase-items', {
                'category_key': 't15_probe_cat', 'name': u'单测连带删',
            }, sid)
            item_id = json.loads(created.data)['result']

            self.assertEqual(self._delete(
                '/api/operator/crafts/embroidery/purchase-categories/t15_probe_cat',
                sid).status_code, 200)
            self.assertEqual(
                crafts.get_craft_purchase_items('embroidery', 't15_probe_cat'), [])
        finally:
            if item_id is not None:
                self._sql("DELETE FROM craft_purchase_items WHERE rowid = ?",
                          (item_id,))
            self._sql("DELETE FROM craft_purchase_categories WHERE craft_id = "
                      "'embroidery' AND key = 't15_probe_cat'")
            self._cleanup_sessions(sid)


class OperatorDialectsWriteTest(OperatorBlocksTestBase):
    """方言知识：方言、短语、快捷问题的增删改。"""

    def test_operator_can_create_update_and_delete_a_dialect(self):
        """方言增删改闭环，前台列表与详情立即跟着变。"""
        sid = self._login()
        dialect_id = 't15_probe_dialect'
        try:
            created = self._post('/api/operator/dialects', {
                'id': dialect_id, 'name': u'单测方言', 'region': u'单测地区',
                'emoji': 'x', 'areas': u'单测范围', 'speakers': u'单测人数',
                'greeting': u'单测问候', 'greeting_meaning': u'单测意思',
                'features': [u'单测特色甲', u'单测特色乙'],
            }, sid)
            self.assertEqual(created.status_code, 200, created.data)

            front = {d['id'] for d in json.loads(
                self.client.get(FRONT_DIALECTS).data)['dialects']}
            self.assertIn(dialect_id, front, '新方言没有出现在前台列表里')

            self.assertEqual(self._put('/api/operator/dialects/%s' % dialect_id,
                                       {'name': u'单测方言改',
                                        'features': [u'只剩一个特色']},
                                       sid).status_code, 200)
            detail = json.loads(self.client.get(
                FRONT_DIALECT_INFO,
                query_string={'dialect': dialect_id}).data)['info']
            self.assertEqual(detail['name'], u'单测方言改')
            self.assertEqual(detail['features'], [u'只剩一个特色'])

            self.assertEqual(
                self._delete('/api/operator/dialects/%s' % dialect_id, sid).status_code,
                200)
            self.assertNotIn(dialect_id, {d['id'] for d in json.loads(
                self.client.get(FRONT_DIALECTS).data)['dialects']})
        finally:
            self._sql("DELETE FROM dialects WHERE id = ?", (dialect_id,))
            self._cleanup_sessions(sid)

    def test_features_must_be_an_array(self):
        """features 在库里是 JSON 文本，写侧只收数组。

        读侧解析失败给空列表，写侧若也收，运营以为自己写了特色标签，
        学员端一个都不显示，且没有任何报错。
        """
        sid = self._login()
        try:
            response = self._post('/api/operator/dialects', {
                'id': 't15_probe_dialect', 'name': u'单测方言',
                'features': u'不是数组',
            }, sid)
            self.assertEqual(response.status_code, 400, response.data)
            self.assertEqual(json.loads(response.data)['message'],
                             u'features 需要是数组')
            self.assertIsNone(dialects.get_dialect_row('t15_probe_dialect'))
        finally:
            self._sql("DELETE FROM dialects WHERE id = ?", ('t15_probe_dialect',))
            self._cleanup_sessions(sid)

    def test_fallback_dialect_cannot_be_deleted(self):
        """兜底方言不能删：前台查不到入参方言时退回它，删了会 500。"""
        sid = self._login()
        try:
            response = self._delete('/api/operator/dialects/cantonese', sid)
            self.assertEqual(response.status_code, 400, response.data)
            self.assertIn(u'兜底', json.loads(response.data)['message'])
            self.assertIsNotNone(dialects.get_dialect_row('cantonese'))
        finally:
            self._cleanup_sessions(sid)

    def test_phrases_and_quick_questions_can_be_maintained(self):
        """短语与快捷问题增删改，前台详情两个数组立即跟着变。"""
        sid = self._login()
        phrase_id = question_id = None
        try:
            created = self._post('/api/operator/dialects/cantonese/phrases', {
                'dialect': u'单测方言说法', 'mandarin': u'单测普通话',
                'pinyin': 'ceot1 si3', 'sort_order': 999,
            }, sid)
            self.assertEqual(created.status_code, 200, created.data)
            phrase_id = json.loads(created.data)['result']

            question = self._post(
                '/api/operator/dialects/cantonese/quick-questions',
                {'question': u'单测快问？', 'sort_order': 999}, sid)
            self.assertEqual(question.status_code, 200, question.data)
            question_id = json.loads(question.data)['result']

            detail = json.loads(self.client.get(FRONT_DIALECT).data)['info']
            phrase = next(p for p in detail['phrases'] if p['mandarin'] == u'单测普通话')
            self.assertEqual(phrase['dialect'], u'单测方言说法')
            self.assertEqual(phrase['pinyin'], 'ceot1 si3')
            # 快捷问题在前台是纯字符串数组，不是一个 dict 列表
            self.assertIn(u'单测快问？', detail['quick_questions'])
            self.assertTrue(all(isinstance(q, str) for q in detail['quick_questions']))

            self.assertEqual(self._put(
                '/api/operator/dialects/phrases/%d' % phrase_id,
                {'mandarin': u'单测普通话改'}, sid).status_code, 200)
            self.assertEqual(self._put(
                '/api/operator/dialects/quick-questions/%d' % question_id,
                {'question': u'单测快问改？'}, sid).status_code, 200)

            detail = json.loads(self.client.get(FRONT_DIALECT).data)['info']
            self.assertIn(u'单测普通话改',
                          {p['mandarin'] for p in detail['phrases']})
            self.assertIn(u'单测快问改？', detail['quick_questions'])

            self.assertEqual(self._delete(
                '/api/operator/dialects/phrases/%d' % phrase_id, sid).status_code, 200)
            self.assertEqual(self._delete(
                '/api/operator/dialects/quick-questions/%d' % question_id,
                sid).status_code, 200)
        finally:
            if phrase_id is not None:
                self._sql("DELETE FROM dialect_phrases WHERE rowid = ?", (phrase_id,))
            if question_id is not None:
                self._sql("DELETE FROM dialect_quick_questions WHERE rowid = ?",
                          (question_id,))
            self._sql("DELETE FROM dialect_phrases WHERE mandarin LIKE '单测普通话%'")
            self._sql("DELETE FROM dialect_quick_questions WHERE question LIKE '单测快问%'")
            self._cleanup_sessions(sid)


class OperatorRecruitmentsWriteTest(OperatorBlocksTestBase):
    """招募公告：公告与来源的增删改。"""

    def test_operator_can_create_update_and_delete_a_recruitment(self):
        """公告增删改闭环，前台就业页的 recruitments 数组立即跟着变。"""
        sid = self._login()
        key = 't15-probe-recruit'
        try:
            created = self._post('/api/operator/recruitments', {
                'key': key, 'title': u'单测公告', 'org': u'单测单位',
                'region': u'单测地区', 'category': u'基层服务',
                'job_type': u'专职', 'headcount': u'1 人', 'education': u'大专',
                'experience': u'不限', 'salary': u'面议',
                'description': u'单测描述', 'publish_date': '2026-01-01',
                'signup_start': '2026-01-02', 'deadline': '2099-12-31',
                'signup_way': u'网上报名', 'contact': u'单测联系方式',
            }, sid)
            self.assertEqual(created.status_code, 200, created.data)

            body = json.loads(self.client.get(FRONT_JOBS).data)
            row = next((r for r in body['recruitments'] if r['key'] == key), None)
            self.assertIsNotNone(row, '新公告没有出现在前台就业页里')
            self.assertEqual(row['title'], u'单测公告')
            self.assertEqual(row['org'], u'单测单位')
            self.assertEqual(row['sources'], [])

            self.assertEqual(self._put('/api/operator/recruitments/%s' % key,
                                       {'title': u'单测公告改',
                                        'salary': u'单测薪资'}, sid).status_code, 200)
            row = next(r for r in json.loads(
                self.client.get(FRONT_JOBS).data)['recruitments'] if r['key'] == key)
            self.assertEqual(row['title'], u'单测公告改')
            self.assertEqual(row['salary'], u'单测薪资')

            self.assertEqual(
                self._delete('/api/operator/recruitments/%s' % key, sid).status_code,
                200)
            self.assertIsNone(recruitments.get_recruitment_row(key))
        finally:
            self._sql("DELETE FROM recruitments WHERE key = ?", (key,))
            self._cleanup_sessions(sid)

    def test_recruitment_rejects_unknown_categories(self):
        """分类必须走白名单：写一个表外的值会出现永远筛不到的死筛选项。"""
        sid = self._login()
        try:
            response = self._post('/api/operator/recruitments', {
                'key': 't15-probe-recruit', 'title': u'单测公告',
                'category': u'不存在的分类',
            }, sid)
            self.assertEqual(response.status_code, 400, response.data)
            self.assertEqual(json.loads(response.data)['message'],
                             u'岗位类别不在可选范围内')
            self.assertIsNone(recruitments.get_recruitment_row('t15-probe-recruit'))
        finally:
            self._sql("DELETE FROM recruitments WHERE key = ?", ('t15-probe-recruit',))
            self._cleanup_sessions(sid)

    def test_derived_signup_fields_are_not_editable(self):
        """验收 5：status / days_left / starts_in 由当天日期算，不是可编辑字段。

        库里没有这三列，写侧也不接收这三个键：收下来没处存，
        只会让运营以为改成功了，而前台照旧按日期算。
        """
        sid = self._login()
        key = 't15-probe-recruit'
        try:
            self._post('/api/operator/recruitments', {
                'key': key, 'title': u'单测公告', 'category': u'基层服务',
                'deadline': '2099-12-31',
            }, sid)
            # 运营把报名状态「改成」closed，前台必须仍按 2099 截止算成 open
            response = self._put('/api/operator/recruitments/%s' % key,
                                 {'status': 'closed', 'status_label': u'已过报名期',
                                  'days_left': -99, 'starts_in': -99}, sid)
            self.assertEqual(response.status_code, 200, response.data)

            row = next(r for r in json.loads(
                self.client.get(FRONT_JOBS).data)['recruitments'] if r['key'] == key)
            self.assertEqual(row['status'], 'open', '报名状态被运营覆盖了')
            self.assertEqual(row['status_label'], u'报名中')
            self.assertGreater(row['days_left'], 0)

            # 反过来：改截止日期，派生值必须跟着变 —— 这才是正确的编辑入口
            self._put('/api/operator/recruitments/%s' % key,
                      {'deadline': '2000-01-01'}, sid)
            row = next(r for r in json.loads(
                self.client.get(FRONT_JOBS).data)['recruitments'] if r['key'] == key)
            self.assertEqual(row['status'], 'closed')
            self.assertEqual(row['status_label'], u'已过报名期')
        finally:
            self._sql("DELETE FROM recruitments WHERE key = ?", (key,))
            self._cleanup_sessions(sid)

    def test_bad_dates_are_rejected(self):
        """日期必须是 ISO 格式：读侧 _parse_date 解析失败会把 status 算成 unknown。"""
        sid = self._login()
        try:
            response = self._post('/api/operator/recruitments', {
                'key': 't15-probe-recruit', 'title': u'单测公告',
                'deadline': u'今年年底',
            }, sid)
            self.assertEqual(response.status_code, 400, response.data)
            self.assertIn(u'YYYY-MM-DD', json.loads(response.data)['message'])
        finally:
            self._sql("DELETE FROM recruitments WHERE key = ?", ('t15-probe-recruit',))
            self._cleanup_sessions(sid)

    def test_recruitment_sources_can_be_maintained(self):
        """公告来源增删改，前台 sources 数组立即跟着变。"""
        sid = self._login()
        key = 't15-probe-recruit'
        source_id = None
        try:
            self._post('/api/operator/recruitments', {
                'key': key, 'title': u'单测公告', 'category': u'基层服务',
            }, sid)
            created = self._post('/api/operator/recruitments/%s/sources' % key, {
                'title': u'单测来源', 'media': u'单测媒体', 'date': '2026-01-01',
                'url': 'https://example.com/t15',
            }, sid)
            self.assertEqual(created.status_code, 200, created.data)
            source_id = json.loads(created.data)['result']

            row = next(r for r in json.loads(
                self.client.get(FRONT_JOBS).data)['recruitments'] if r['key'] == key)
            source = next(s for s in row['sources'] if s['title'] == u'单测来源')
            self.assertEqual(source['media'], u'单测媒体')
            self.assertEqual(source['url'], 'https://example.com/t15')
            # 来源行的键集与切换前一致（多一个 sort_order 会让响应变形）
            self.assertEqual(sorted(source), ['date', 'media', 'title', 'url'])

            self.assertEqual(self._put(
                '/api/operator/recruitments/sources/%d' % source_id,
                {'media': u'单测媒体改'}, sid).status_code, 200)
            row = next(r for r in json.loads(
                self.client.get(FRONT_JOBS).data)['recruitments'] if r['key'] == key)
            self.assertEqual(row['sources'][0]['media'], u'单测媒体改')

            self.assertEqual(self._delete(
                '/api/operator/recruitments/sources/%d' % source_id,
                sid).status_code, 200)
            row = next(r for r in json.loads(
                self.client.get(FRONT_JOBS).data)['recruitments'] if r['key'] == key)
            self.assertEqual(row['sources'], [])
        finally:
            self._sql("DELETE FROM recruitment_sources WHERE title LIKE '单测来源%'")
            self._sql("DELETE FROM recruitments WHERE key = ?", (key,))
            self._cleanup_sessions(sid)


class OperatorCasesWriteTest(OperatorBlocksTestBase):
    """成功案例：案例与四个子表的增删改。"""

    def test_operator_can_create_update_and_delete_a_case(self):
        """案例增删改闭环。新案例先进审核队列，过审后前台才看得到。"""
        sid = self._login()
        case_id = None
        try:
            created = self._post('/api/operator/cases', {
                'title': u'单测案例', 'region': u'单测地区',
                'location': u'单测地点', 'background': u'单测背景',
                'description': u'单测描述', 'quote': u'单测引语',
                'quote_author': u'单测受访者',
            }, sid)
            self.assertEqual(created.status_code, 200, created.data)
            case_id = json.loads(created.data)['result']

            # 新案例必须进审核队列：不过审学员端看不到
            stats = resources.get_case_review_stats()['case_review']
            self.assertGreaterEqual(stats['pending'], 1, '新案例没有进入审核队列')
            self.assertNotIn(case_id, {c['id'] for c in json.loads(
                self.client.get(FRONT_CASES).data)['cases']},
                '未过审的案例不应对学员端可见')

            self.assertEqual(self._put('/api/operator/cases/%d' % case_id,
                                       {'title': u'单测案例改'}, sid).status_code, 200)
            row = content.get_case(case_id)
            self.assertEqual(row['title'], u'单测案例改')

            self.assertEqual(
                self._delete('/api/operator/cases/%d' % case_id, sid).status_code, 200)
            self.assertIsNone(content.get_case(case_id))
            # 删案例必须连带清掉审核记录，否则审核列表里留下看不到内容的孤儿卡片
            from db_domains import reviews as reviews_db
            self.assertIsNone(reviews_db.get_review_by_content('success_case',
                                                               case_id))
        finally:
            self._cleanup_case(case_id)
            self._cleanup_sessions(sid)

    def test_case_requires_a_title(self):
        sid = self._login()
        try:
            response = self._post('/api/operator/cases', {'region': u'只有地区'}, sid)
            self.assertEqual(response.status_code, 400, response.data)
            self.assertEqual(json.loads(response.data)['message'], u'案例标题不能为空')
        finally:
            self._cleanup_sessions(sid)

    def test_four_child_tables_keep_their_shapes(self):
        """验收 4（案例）：四个子表写回去，前台按原形状组装。"""
        sid = self._login()
        case_id = None
        stat_id = milestone_id = source_id = lesson_id = None
        try:
            created = self._post('/api/operator/cases', {'title': u'单测子表案例'},
                                 sid)
            case_id = json.loads(created.data)['result']

            stat_id = json.loads(self._post(
                '/api/operator/cases/%d/stats' % case_id,
                {'label': u'单测指标', 'value': u'单测数值', 'icon': 'fa-leaf',
                 'sort_order': 0}, sid).data)['result']
            milestone_id = json.loads(self._post(
                '/api/operator/cases/%d/milestones' % case_id,
                {'period': u'单测时期', 'title': u'单测里程碑',
                 'desc': u'单测描述', 'sort_order': 0}, sid).data)['result']
            source_id = json.loads(self._post(
                '/api/operator/cases/%d/sources' % case_id,
                {'title': u'单测来源', 'media': u'单测媒体', 'date': '2026-01-01',
                 'url': 'https://example.com/t15', 'sort_order': 0}, sid).data)['result']
            lesson_id = json.loads(self._post(
                '/api/operator/cases/%d/lessons' % case_id,
                {'text': u'单测借鉴点', 'sort_order': 0}, sid).data)['result']

            case = content.get_case(case_id)
            self.assertEqual(case['stats'], [{'label': u'单测指标',
                                             'value': u'单测数值',
                                             'icon': 'fa-leaf'}])
            self.assertEqual(case['milestones'], [{'period': u'单测时期',
                                                   'title': u'单测里程碑',
                                                   'desc': u'单测描述'}])
            self.assertEqual(case['sources'], [{'title': u'单测来源',
                                                'media': u'单测媒体',
                                                'date': '2026-01-01',
                                                'url': 'https://example.com/t15'}])
            # 借鉴点在前台是纯字符串数组
            self.assertEqual(case['lessons'], [u'单测借鉴点'])

            # 四个子表各自能改能删
            self.assertEqual(self._put('/api/operator/cases/stats/%d' % stat_id,
                                       {'value': u'改过的数值'}, sid).status_code, 200)
            self.assertEqual(self._put(
                '/api/operator/cases/milestones/%d' % milestone_id,
                {'title': u'改过的里程碑'}, sid).status_code, 200)
            self.assertEqual(self._put(
                '/api/operator/cases/sources/%d' % source_id,
                {'media': u'改过的媒体'}, sid).status_code, 200)
            self.assertEqual(self._put(
                '/api/operator/cases/lessons/%d' % lesson_id,
                {'text': u'改过的借鉴点'}, sid).status_code, 200)

            case = content.get_case(case_id)
            self.assertEqual(case['stats'][0]['value'], u'改过的数值')
            self.assertEqual(case['milestones'][0]['title'], u'改过的里程碑')
            self.assertEqual(case['sources'][0]['media'], u'改过的媒体')
            self.assertEqual(case['lessons'], [u'改过的借鉴点'])

            for path in ('/api/operator/cases/stats/%d' % stat_id,
                         '/api/operator/cases/milestones/%d' % milestone_id,
                         '/api/operator/cases/sources/%d' % source_id,
                         '/api/operator/cases/lessons/%d' % lesson_id):
                self.assertEqual(self._delete(path, sid).status_code, 200, path)
            case = content.get_case(case_id)
            self.assertEqual(case['stats'], [])
            self.assertEqual(case['milestones'], [])
            self.assertEqual(case['sources'], [])
            self.assertEqual(case['lessons'], [])
        finally:
            for table in ('case_stats', 'case_milestones', 'case_sources',
                          'case_lessons'):
                self._sql("DELETE FROM %s WHERE case_id = ?" % table, (case_id,))
            self._cleanup_case(case_id)
            self._cleanup_sessions(sid)


class OperatorBlocksAuthorizationTest(OperatorBlocksTestBase):
    """权限边界：谁能打这四块的运营接口，谁不能。"""

    PROBES = (
        ('/api/operator/crafts', 'GET'),
        ('/api/operator/crafts/embroidery/steps', 'GET'),
        ('/api/operator/crafts/embroidery/purchase-categories', 'GET'),
        ('/api/operator/crafts/embroidery/purchase-items', 'GET'),
        ('/api/operator/crafts/embroidery/budget', 'GET'),
        ('/api/operator/dialects', 'GET'),
        ('/api/operator/dialects/cantonese/phrases', 'GET'),
        ('/api/operator/dialects/cantonese/quick-questions', 'GET'),
        ('/api/operator/recruitments', 'GET'),
        ('/api/operator/recruitments/bl-gy-2026/sources', 'GET'),
        ('/api/operator/cases', 'GET'),
        ('/api/operator/cases/1/stats', 'GET'),
        ('/api/operator/cases/1/milestones', 'GET'),
        ('/api/operator/cases/1/sources', 'GET'),
        ('/api/operator/cases/1/lessons', 'GET'),
    )

    def test_student_is_rejected_from_every_new_route(self):
        """验收 2：学员打这四块的运营接口一律 401 或 403。"""
        sid = self._login(STUDENT)
        try:
            for path, method in self.PROBES:
                with self.subTest(path=path):
                    response = self.client.open(path, method=method,
                                                headers=self._headers(sid))
                    self.assertIn(response.status_code, (401, 403),
                                  '%s 给了学员 %d' % (path, response.status_code))
            # 写接口同样拒（这是「学员不能改内容」的实质）
            response = self._post('/api/operator/crafts', {
                'id': 'student-should-not-create', 'name': u'学员不该能建',
            }, sid)
            self.assertIn(response.status_code, (401, 403))
        finally:
            self._cleanup_sessions(sid)


    def test_anonymous_is_rejected_from_every_new_route(self):
        """未登录同样 403 + 「权限不足」，与既有域逐字一致。"""
        for path, method in self.PROBES:
            with self.subTest(path=path):
                response = self.client.open(path, method=method)
                self.assertEqual(response.status_code, 403, path)
                body = json.loads(response.data)
                self.assertFalse(body['success'])
                self.assertEqual(body['message'], u'权限不足')

    def test_teacher_reaches_crafts_but_not_recruitments(self):
        """验收 3：craft.manage 含 teacher，recruit.manage 不含。

        能力边界是表里显式的两条（T01），这里用两个角色探针把它钉住：
        同一只会话，进得了技艺后台、进不了招募后台。
        """
        sid = self._login(TEACHER)
        try:
            crafts_response = self.client.get(
                '/api/operator/crafts', headers=self._headers(sid))
            self.assertEqual(crafts_response.status_code, 200, crafts_response.data)

            recruitments_response = self.client.get(
                '/api/operator/recruitments', headers=self._headers(sid))
            self.assertEqual(recruitments_response.status_code, 403)
            self.assertEqual(json.loads(recruitments_response.data)['message'],
                             u'权限不足')

            # 写侧同样分界：教师能建技艺，建不了公告
            write = self._post('/api/operator/recruitments', {
                'key': 'teacher-should-not-create', 'title': u'教师不该能建',
            }, sid)
            self.assertEqual(write.status_code, 403, write.data)
        finally:
            self._sql("DELETE FROM recruitments WHERE key = ?",
                      ('teacher-should-not-create',))
            self._cleanup_sessions(sid)

    def test_government_reaches_cases_but_not_dialects(self):
        """另一条边界：case.manage 含 government，dialect.manage 不含。"""
        sid = self._login(('gov_demo', '123456'))
        try:
            cases_response = self.client.get('/api/operator/cases',
                                             headers=self._headers(sid))
            self.assertEqual(cases_response.status_code, 200, cases_response.data)

            dialects_response = self.client.get('/api/operator/dialects',
                                                headers=self._headers(sid))
            self.assertEqual(dialects_response.status_code, 403)
        finally:
            self._cleanup_sessions(sid)

    def test_super_admin_keeps_full_access_to_the_new_routes(self):
        """超管是运营的超集：四块都能进。"""
        sid = self._login(SUPER_ADMIN)
        try:
            for path, method in self.PROBES:
                with self.subTest(path=path):
                    response = self.client.open(path, method=method,
                                                headers=self._headers(sid))
                    self.assertNotEqual(response.status_code, 403, path)
                    self.assertLess(response.status_code, 500)
        finally:
            self._cleanup_sessions(sid)


class OperatorPageBlocksTest(OperatorBlocksTestBase):
    """运营后台页面本身：四块的容器与新建入口都在。"""

    def test_operator_page_carries_all_six_content_blocks(self):
        """六块内容都有可渲染的容器，不是只剩四个占位文案。"""
        body = self.client.get('/operator.html').data.decode('utf-8')
        for page in ('farming', 'pest', 'crafts', 'dialects', 'recruitments', 'cases'):
            self.assertIn('id="page-%s"' % page, body)
        # 四块各自的列表容器：没有它们，写接口通了也看不到内容
        for container in ('craft-rows', 'dialect-rows', 'recruit-rows', 'case-rows',
                          'craft-detail-rows', 'dialect-detail-rows',
                          'recruit-source-rows', 'case-detail-rows'):
            self.assertIn('id="%s"' % container, body)
        # 新建入口：每块至少一个
        for button in ('craft-new', 'dialect-new', 'recruit-new', 'case-new'):
            self.assertIn('id="%s"' % button, body)
        # 占位样式已退役
        self.assertNotIn('operator-todo', body)

    def test_page_scripts_reference_the_new_endpoints(self):
        """页面脚本打的是本票新增的接口路径，不是还指向占位。"""
        body = self.client.get('/operator.html').data.decode('utf-8')
        for path in ('/api/operator/crafts', '/api/operator/dialects',
                     '/api/operator/recruitments', '/api/operator/cases'):
            self.assertIn(path, body, '页面没有引用 %s' % path)

if __name__ == '__main__':
    unittest.main()
