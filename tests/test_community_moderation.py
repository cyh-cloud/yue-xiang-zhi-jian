# -*- coding: utf-8 -*-
"""社区内容治理：敏感词初筛 → 人工审核 → 公开 / 拒绝。

覆盖五条行为：

1. 命中敏感词的发帖/评论不进公开列表，只进管理端待审队列；
2. 未命中的内容照常直接公开；
3. 审核通过后才公开，评论数在通过时才补计；
4. 拒绝后彻底不可见，直链也打不开；
5. 词表做了归一化，插空格、全角、大小写都挡得住。

测试自建讨论帖与评论，结束按 id 清干净（含 discussions 的评论计数）。
"""

import json
import os
import sys
import unittest
import uuid

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(REPO_ROOT, 'backend')
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from db_connection import get_connection  # noqa: E402
from shared import sensitive_words  # noqa: E402


class SensitiveWordsTest(unittest.TestCase):
    def test_plain_hit(self):
        self.assertEqual(sensitive_words.scan('这里可以刷单返利'), ['刷单', '返利'])

    def test_normalization_beats_spacing_and_fullwidth(self):
        # 插空格、插符号、全角字母都要挡住
        self.assertTrue(sensitive_words.scan('加 微 信 详聊'))
        self.assertTrue(sensitive_words.scan('加*微*信'))
        self.assertTrue(sensitive_words.scan('加ＱＱ聊'))
        self.assertTrue(sensitive_words.scan('赌　博'))  # 全角空格

    def test_normal_agriculture_talk_is_clean(self):
        for text in ('荔枝保花保果的关键期怎么管',
                     '今年想申请农业贷款扩大种植',
                     '合作社统一采购有机肥'):
            self.assertEqual(sensitive_words.scan(text), [], text)

    def test_empty_input(self):
        self.assertEqual(sensitive_words.scan('', None), [])


class CommunityModerationBase(unittest.TestCase):
    def setUp(self):
        from app import app
        from db_init import init_db
        init_db()
        self.client = app.test_client()
        self.student_sid = self._login('student_demo', '123456')
        self.admin_sid = self._login('admin_demo', 'admin123')
        self.created_discussions = []

    def tearDown(self):
        conn = get_connection()
        try:
            for disc_id in self.created_discussions:
                conn.execute("DELETE FROM comments WHERE target_type='discussion' "
                             "AND target_id = ?", (disc_id,))
                conn.execute("DELETE FROM discussions WHERE id = ?", (disc_id,))
            conn.commit()
        finally:
            conn.close()

    def _login(self, username, password):
        body = json.loads(self.client.post(
            '/api/auth/login',
            json={'username': username, 'password': password}).data)
        return body['session_id']

    def _h(self, sid=None):
        return {'X-Session-Id': sid or self.student_sid}

    def _post_discussion(self, title, content):
        response = self.client.post('/api/discussions', json={
            'title': title, 'content': content, 'category': 'general',
        }, headers=self._h())
        self.assertEqual(response.status_code, 200, response.data)
        body = json.loads(response.data)
        self.created_discussions.append(body['id'])
        return body

    def _post_comment(self, discussion_id, content):
        response = self.client.post('/api/comments', json={
            'target_type': 'discussion',
            'target_id': discussion_id,
            'content': content,
        }, headers=self._h())
        return response

    def _public_ids(self):
        body = json.loads(self.client.get('/api/discussions').data)
        return [item['id'] for item in body['discussions']]

    def _admin_content(self):
        return json.loads(self.client.get(
            '/api/admin/content', headers=self._h(self.admin_sid)).data)

    def _pending_discussion_id(self, disc_id):
        for item in self._admin_content()['pending_discussions']:
            if item['id'] == disc_id:
                return item['id']
        self.fail('待审队列里没有这条帖子')


class DiscussionModerationTest(CommunityModerationBase):
    def test_clean_post_is_public_immediately(self):
        body = self._post_discussion('荔枝保花保果经验', '花期注意控水控肥。')
        self.assertFalse(body.get('pending'))
        self.assertIn(body['id'], self._public_ids())

    def test_sensitive_post_goes_to_pending_and_stays_hidden(self):
        body = self._post_discussion('兼职日赚三百', '加微信详聊，刷单返利。')
        self.assertTrue(body.get('pending'))
        self.assertIn('刷单', body.get('matched', []))

        self.assertNotIn(body['id'], self._public_ids(), '待审帖子不能进公开列表')
        detail = self.client.get('/api/discussions/%s' % body['id'])
        self.assertEqual(detail.status_code, 404, '待审帖子不能靠直链打开')

        pending = self._admin_content()['pending_discussions']
        self.assertIn(body['id'], [item['id'] for item in pending])
        self.assertTrue(pending[0]['matched_words'])

    def test_approve_publishes_the_post(self):
        body = self._post_discussion('招代理加盟', '扫码进群了解。')
        response = self.client.post(
            '/api/admin/discussions/%s/approve' % body['id'],
            headers=self._h(self.admin_sid))
        self.assertEqual(response.status_code, 200, response.data)

        self.assertIn(body['id'], self._public_ids())
        detail = self.client.get('/api/discussions/%s' % body['id'])
        self.assertEqual(detail.status_code, 200)

        again = self.client.post(
            '/api/admin/discussions/%s/approve' % body['id'],
            headers=self._h(self.admin_sid))
        self.assertEqual(again.status_code, 409, '不能重复裁定')

    def test_reject_keeps_the_post_invisible(self):
        body = self._post_discussion('低价代开发票', '需要的私聊我。')
        response = self.client.post(
            '/api/admin/discussions/%s/reject' % body['id'],
            headers=self._h(self.admin_sid))
        self.assertEqual(response.status_code, 200, response.data)

        self.assertNotIn(body['id'], self._public_ids())
        self.assertEqual(
            self.client.get('/api/discussions/%s' % body['id']).status_code, 404)
        pending = self._admin_content()['pending_discussions']
        self.assertNotIn(body['id'], [item['id'] for item in pending])


class CommentModerationTest(CommunityModerationBase):
    def test_pending_comment_is_uncounted_until_approved(self):
        disc = self._post_discussion('合作社用工讨论', '今年采果季缺人手。')

        clean = self._post_comment(disc['id'], '我们村有五个熟练工。')
        self.assertEqual(clean.status_code, 200, clean.data)
        self.assertFalse(json.loads(clean.data).get('pending'))

        dirty = self._post_comment(disc['id'], '想找活的加微信 13800000000')
        self.assertEqual(dirty.status_code, 200, dirty.data)
        dirty_body = json.loads(dirty.data)
        self.assertTrue(dirty_body.get('pending'))

        detail = json.loads(self.client.get(
            '/api/discussions/%s' % disc['id']).data)
        self.assertEqual(detail['discussion']['comment_count'], 1,
                         '待审评论不应计入公开评论数')
        self.assertEqual(len(detail['comments']), 1)

        approve = self.client.post(
            '/api/admin/comments/%s/approve' % dirty_body['id'],
            headers=self._h(self.admin_sid))
        self.assertEqual(approve.status_code, 200, approve.data)

        detail = json.loads(self.client.get(
            '/api/discussions/%s' % disc['id']).data)
        self.assertEqual(detail['discussion']['comment_count'], 2)
        self.assertEqual(len(detail['comments']), 2)

    def test_deleting_a_pending_comment_does_not_eat_other_counts(self):
        disc = self._post_discussion('评论计数回归', '用于计数测试。')
        self._post_comment(disc['id'], '正常评论一')
        dirty = json.loads(self._post_comment(disc['id'], '刷单加微信').data)

        response = self.client.delete(
            '/api/admin/comments/%s' % dirty['id'],
            headers=self._h(self.admin_sid))
        self.assertEqual(response.status_code, 200, response.data)

        detail = json.loads(self.client.get(
            '/api/discussions/%s' % disc['id']).data)
        self.assertEqual(detail['discussion']['comment_count'], 1,
                         '删除待审评论不能把已公开评论的计数减掉')


if __name__ == '__main__':
    unittest.main()
