# -*- coding: utf-8 -*-
"""公开域与社区域的路由行为测试（T09）。

首页统计、公开课程、公开 3D 模型、系统公告的公开读，以及讨论帖与评论的读写，
各自成为领域路由模块后，对外契约必须一字不变：URL、请求响应结构、状态码、错误码。

本文件锁住的是匿名访客的读边界（哪些内容不带会话就能看到）、社区发布的登录门禁、
发布成功后可读回、软删除行为，以及未知 id 的返回形态。

断言全部基于 HTTP 行为，不测模块怎么划分（拆分不产生新行为，为结构写测试只会
把实现细节钉死，见 spec 的 Testing Decisions）。
"""

import json
import os
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# backend/ 也要在路径上：本文件在顶部就 import db_connection，靠「前面某个模块
# 碰巧补过路径」是隐式顺序依赖，单独跑这个文件就会炸。
for _path in (REPO_ROOT, os.path.join(REPO_ROOT, 'backend')):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from db_connection import get_connection
from db_domains import courses as courses_db
from db_domains import reviews



class _CommunityCase(unittest.TestCase):
    """公共脚手架：按需登录、按需清理自己造出来的行。"""

    def setUp(self):
        from app import app
        self.client = app.test_client()

    def _login(self, username='student_demo', password='123456'):
        response = self.client.post('/api/auth/login', data=json.dumps(
            {'username': username, 'password': password}),
            content_type='application/json')
        return json.loads(response.data)['session_id']

    def _post_json(self, path, payload, session_id=None):
        headers = {'Content-Type': 'application/json'}
        if session_id:
            headers['X-Session-Id'] = session_id
        return self.client.post(path, data=json.dumps(payload),
                                content_type='application/json', headers=headers)


class PublicDomainTest(_CommunityCase):
    """公开域：首页统计、系统公告、公开课程、公开 3D 模型。"""

    def test_home_stats_are_readable_anonymously(self):
        """首页统计不带任何会话头即可读，且三个键都由真实库计数给出。"""
        response = self.client.get('/api/home/stats')
        self.assertEqual(response.status_code, 200)
        body = json.loads(response.data)
        self.assertTrue(body['success'])
        stats = body['stats']
        self.assertEqual(set(stats), {'farmers', 'courses', 'jobs'})
        conn = get_connection()
        try:
            for key, table in (('farmers', 'students'), ('courses', 'courses'),
                               ('jobs', 'job_listings')):
                expected = conn.execute(
                    "SELECT COUNT(*) FROM %s" % table).fetchone()[0]
                self.assertEqual(stats[key], expected, key)
        finally:
            conn.close()

    def test_system_announcements_are_readable_anonymously(self):
        """公告公开读：匿名可读，且只下发仍生效的公告。"""
        response = self.client.get('/api/system-announcements')
        self.assertEqual(response.status_code, 200)
        body = json.loads(response.data)
        self.assertTrue(body['success'])
        self.assertIsInstance(body['announcements'], list)
        for ann in body['announcements']:
            self.assertNotEqual(ann.get('is_active'), 0)

    def test_public_courses_list_only_contains_published(self):
        """公开课程列表只含已发布课程，匿名可读。"""
        response = self.client.get('/api/teacher/public-courses')
        self.assertEqual(response.status_code, 200)
        body = json.loads(response.data)
        self.assertTrue(body['success'])
        self.assertIsInstance(body['courses'], list)
        for course in body['courses']:
            self.assertNotEqual(course.get('is_published'), 0)

    def test_public_course_detail_returns_course_and_materials(self):
        # 课程自己造并过审，不依赖库里恰好残留着别的用例造出来的公开课程
        course_id = self._published_course()
        listed = json.loads(self.client.get('/api/teacher/public-courses').data)['courses']
        self.assertIn(course_id, [c['id'] for c in listed],
                      '已发布课程必须出现在公开列表里')
        response = self.client.get('/api/teacher/public-courses/%d' % course_id)
        self.assertEqual(response.status_code, 200)
        body = json.loads(response.data)
        self.assertTrue(body['success'])
        self.assertEqual(body['course']['id'], course_id)
        self.assertIsInstance(body['materials'], list)

    def _published_course(self):
        """造一门已发布课程，返回它的 id（用完由 addCleanup 删干净）。"""
        sid = self._login('teacher_demo')
        created = self.client.post(
            '/api/teacher/courses',
            data=json.dumps({'title': '__T09公开课程__', 'description': 'public'}),
            content_type='application/json', headers={'X-Session-Id': sid})
        course_id = json.loads(created.data)['id']
        self.addCleanup(courses_db.delete_course, course_id)
        review = reviews.get_review_by_content('course', course_id)
        reviews.approve_review(review['id'], 'admin_demo')
        return course_id

    def test_public_course_detail_unknown_id_is_404(self):
        """未知课程 id：404 + success=False，与拆分前一致。"""
        response = self.client.get('/api/teacher/public-courses/999999')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(json.loads(response.data),
                         {"success": False, "message": "课程不存在"})

    def test_public_models_3d_only_contains_published(self):
        """公开 3D 模型匿名可读，且只含已发布模型。"""
        response = self.client.get('/api/teacher/public-models-3d')
        self.assertEqual(response.status_code, 200)
        body = json.loads(response.data)
        self.assertTrue(body['success'])
        self.assertIsInstance(body['models'], list)
        for model in body['models']:
            self.assertNotEqual(model.get('is_published'), 0)

    def test_public_models_3d_filters_by_craft_type(self):
        """craft_type 是路由层过滤，只改筛选不改响应形状。"""
        response = self.client.get('/api/teacher/public-models-3d?craft_type=embroidery')
        self.assertEqual(response.status_code, 200)
        body = json.loads(response.data)
        self.assertTrue(body['success'])
        for model in body['models']:
            self.assertEqual(model['craft_type'], 'embroidery')

    def test_public_models_3d_unknown_craft_type_returns_empty_list(self):
        """未知 craft_type 是空列表，不是 404。"""
        response = self.client.get('/api/teacher/public-models-3d?craft_type=no-such-craft')
        self.assertEqual(response.status_code, 200)
        body = json.loads(response.data)
        self.assertTrue(body['success'])
        self.assertEqual(body['models'], [])


class CommunityDomainTest(_CommunityCase):
    """社区域：讨论帖与评论的读写。"""

    def setUp(self):
        super(CommunityDomainTest, self).setUp()
        self._created_ids = []

    def tearDown(self):
        conn = get_connection()
        for disc_id in self._created_ids:
            conn.execute("DELETE FROM comments WHERE target_type='discussion' AND target_id=?", (disc_id,))
            conn.execute("DELETE FROM discussions WHERE id=?", (disc_id,))
        conn.commit()
        conn.close()

    def _create_discussion(self, title, content='社区测试内容', category='general'):
        sid = self._login()
        response = self._post_json('/api/discussions', {
            'title': title, 'content': content, 'category': category}, sid)
        self.assertEqual(response.status_code, 200, response.data)
        body = json.loads(response.data)
        self.assertTrue(body['success'])
        self._created_ids.append(body['id'])
        return body['id']

    def test_discussions_list_is_readable_anonymously(self):
        response = self.client.get('/api/discussions')
        self.assertEqual(response.status_code, 200)
        body = json.loads(response.data)
        self.assertTrue(body['success'])
        self.assertIsInstance(body['discussions'], list)
        self.assertIsInstance(body['total'], int)
        for disc in body['discussions']:
            self.assertNotEqual(disc.get('is_deleted'), 1)

    def test_discussions_list_filters_by_category(self):
        disc_id = self._create_discussion('T09分类帖', category='planting')
        response = self.client.get('/api/discussions?category=planting')
        self.assertEqual(response.status_code, 200)
        ids = [d['id'] for d in json.loads(response.data)['discussions']]
        self.assertIn(disc_id, ids)

    def test_create_discussion_requires_login(self):
        response = self._post_json('/api/discussions', {
            'title': '未登录发帖', 'content': '不应成功'})
        self.assertEqual(response.status_code, 401)
        body = json.loads(response.data)
        self.assertFalse(body['success'])
        self.assertEqual(body['message'], '请先登录')

    def test_create_discussion_rejects_blank_title_or_content(self):
        sid = self._login()
        for payload in ({'title': '', 'content': 'x'}, {'title': 'x', 'content': ''}):
            response = self._post_json('/api/discussions', payload, sid)
            self.assertEqual(response.status_code, 400, payload)
            body = json.loads(response.data)
            self.assertFalse(body['success'])
            self.assertEqual(body['message'], '标题和内容不能为空')

    def test_create_discussion_rejects_overlong_title_and_content(self):
        sid = self._login()
        cases = (
            ({'title': '长' * 81, 'content': '正文'},
             '标题过长，请控制在 80 字以内', 'title_too_long'),
            ({'title': '标题', 'content': '长' * 5001},
             '帖子内容过长，请控制在 5000 字以内', 'content_too_long'),
        )
        for payload, message, code in cases:
            response = self._post_json('/api/discussions', payload, sid)
            self.assertEqual(response.status_code, 400, payload['title'][:10])
            body = json.loads(response.data)
            self.assertFalse(body['success'])
            self.assertEqual(body['message'], message)
            self.assertEqual(body['code'], code)

    def test_create_discussion_then_read_back(self):
        title = 'T09发布后读回%s' % len(self._created_ids)
        disc_id = self._create_discussion(title)
        response = self.client.get('/api/discussions/%d' % disc_id)
        self.assertEqual(response.status_code, 200)
        body = json.loads(response.data)
        self.assertTrue(body['success'])
        self.assertEqual(body['discussion']['id'], disc_id)
        self.assertEqual(body['discussion']['title'], title)
        self.assertEqual(body['discussion']['user_id'], 'student_demo')
        self.assertEqual(body['comments'], [])

    def test_discussion_detail_unknown_id_is_404(self):
        response = self.client.get('/api/discussions/999999')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(json.loads(response.data),
                         {"success": False, "message": "帖子不存在"})

    def test_get_comments_requires_both_query_params(self):
        """缺 target_type 或 target_id 一律 400 + 参数不完整。"""
        for path in ('/api/comments', '/api/comments?target_type=discussion',
                     '/api/comments?target_id=1'):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 400, path)
            self.assertEqual(json.loads(response.data),
                             {"success": False, "message": "参数不完整"})

    def test_comments_are_readable_anonymously(self):
        disc_id = self._create_discussion('T09评论读回')
        sid = self._login()
        posted = self._post_json('/api/comments', {
            'target_type': 'discussion', 'target_id': disc_id,
            'content': 'T09评论内容'}, sid)
        self.assertEqual(posted.status_code, 200, posted.data)
        self.assertTrue(json.loads(posted.data)['success'])

        response = self.client.get('/api/comments?target_type=discussion&target_id=%d' % disc_id)
        self.assertEqual(response.status_code, 200)
        comments = json.loads(response.data)['comments']
        self.assertTrue(any(c['content'] == 'T09评论内容' for c in comments))

    def test_add_comment_requires_login(self):
        response = self._post_json('/api/comments', {
            'target_type': 'discussion', 'target_id': 1, 'content': '未登录评论'})
        self.assertEqual(response.status_code, 401)
        body = json.loads(response.data)
        self.assertFalse(body['success'])
        self.assertEqual(body['message'], '请先登录')

    def test_add_comment_rejects_blank_fields(self):
        sid = self._login()
        for payload in ({'target_type': '', 'target_id': 1, 'content': 'x'},
                        {'target_type': 'discussion', 'target_id': 0, 'content': 'x'},
                        {'target_type': 'discussion', 'target_id': 1, 'content': '   '}):
            response = self._post_json('/api/comments', payload, sid)
            self.assertEqual(response.status_code, 400, payload)
            self.assertEqual(json.loads(response.data),
                             {"success": False, "message": "参数不完整"})

    def test_add_comment_rejects_overlong_content(self):
        disc_id = self._create_discussion('T12评论长度')
        sid = self._login()
        response = self._post_json('/api/comments', {
            'target_type': 'discussion', 'target_id': disc_id,
            'content': '长' * 1001}, sid)
        self.assertEqual(response.status_code, 400)
        body = json.loads(response.data)
        self.assertFalse(body['success'])
        self.assertEqual(body['message'], '评论过长，请控制在 1000 字以内')
        self.assertEqual(body['code'], 'content_too_long')

    def test_add_comment_shows_up_in_discussion_detail(self):
        disc_id = self._create_discussion('T09评论入详情')
        sid = self._login()
        self._post_json('/api/comments', {
            'target_type': 'discussion', 'target_id': disc_id,
            'content': 'T09详情内可见'}, sid)
        response = self.client.get('/api/discussions/%d' % disc_id)
        comments = json.loads(response.data)['comments']
        self.assertTrue(any(c['content'] == 'T09详情内可见' for c in comments))

    def test_soft_deleted_discussion_disappears_from_list_but_detail_keeps_working(self):
        """软删帖子：列表不再返回它，详情仍可读（与拆分前一致，不改成 404）。"""
        disc_id = self._create_discussion('T09软删帖子')
        conn = get_connection()
        try:
            conn.execute("UPDATE discussions SET is_deleted = 1 WHERE id = ?", (disc_id,))
            conn.commit()
        finally:
            conn.close()

        listed = [d['id'] for d in json.loads(self.client.get('/api/discussions').data)['discussions']]
        self.assertNotIn(disc_id, listed)

        response = self.client.get('/api/discussions/%d' % disc_id)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.data)['discussion']['id'], disc_id)

    def test_soft_deleted_comment_disappears_from_read_paths(self):
        """软删评论：详情与评论列表都不再返回它。"""
        disc_id = self._create_discussion('T09软删评论')
        sid = self._login()
        self._post_json('/api/comments', {
            'target_type': 'discussion', 'target_id': disc_id,
            'content': 'T09将被软删'}, sid)
        comment_id = get_connection().execute(
            "SELECT id FROM comments WHERE content = ?", ('T09将被软删',)).fetchone()[0]
        conn = get_connection()
        try:
            conn.execute("UPDATE comments SET is_deleted = 1 WHERE id = ?", (comment_id,))
            conn.commit()
        finally:
            conn.close()

        for path in ('/api/comments?target_type=discussion&target_id=%d' % disc_id,
                     '/api/discussions/%d' % disc_id):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200, path)
            payload = json.loads(response.data)
            comments = payload.get('comments', [])
            self.assertFalse(any(c['content'] == 'T09将被软删' for c in comments), path)

    def test_discussion_author_name_comes_from_the_user_table(self):
        """列表与详情的作者显示名由数据层补齐，匿名读也能看到。"""
        disc_id = self._create_discussion('T09作者名')
        listed = [d for d in json.loads(self.client.get('/api/discussions').data)['discussions']
                  if d['id'] == disc_id]
        self.assertEqual(listed[0]['user_name'], '李同学')


class PublicCommunityBlueprintRegistrationTest(_CommunityCase):
    """蓝图注册：两个新域进工厂注册表，且静态兜底仍排在最后。"""

    def test_new_blueprints_come_from_the_domain_packages(self):
        from domains import community_bp, public_bp
        from app import app
        self.assertEqual(public_bp.name, 'public')
        self.assertEqual(community_bp.name, 'community')
        self.assertIn(public_bp.name, app.blueprints)
        self.assertIn(community_bp.name, app.blueprints)

    def test_static_catch_all_is_registered_last(self):
        """静态兜底蓝图必须最后注册，否则 `/<path:filename>` 可能吞掉 API 路由。

        注册序的唯一真相是 app.blueprints 的键顺序（url_map.iter_rules() 会按
        权重重排，末尾那条并不对应最后注册的蓝图，见 T07/T08 的同名断言）。
        """
        from app import app
        self.assertIn('static_files', app.blueprints)
        self.assertEqual(list(app.blueprints)[-1], 'static_files', list(app.blueprints))
        for name in ('public', 'community'):
            self.assertLess(list(app.blueprints).index(name),
                            list(app.blueprints).index('static_files'),
                            '%s 必须注册在静态兜底之前' % name)

    def test_api_routes_are_not_swallowed_by_the_catch_all(self):
        """新域的 URL 必须仍由蓝图响应，不能被静态兜底吃掉。"""
        for path in ('/api/home/stats', '/api/system-announcements',
                     '/api/teacher/public-courses', '/api/teacher/public-models-3d',
                     '/api/discussions', '/api/comments?target_type=discussion&target_id=1'):
            response = self.client.get(path)
            self.assertIn(response.status_code, (200, 400), path)
            self.assertNotIn(u'文件不存在'.encode('utf-8'), response.data, path)


if __name__ == '__main__':
    unittest.main()
