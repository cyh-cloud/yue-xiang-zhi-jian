# -*- coding: utf-8 -*-
"""超级管理员域、政府域与企业域的路由行为测试（T17）。

锁住从 app.py 搬进 domains/admin、domains/government、domains/enterprise 之后必须
一字不变的外部契约：URL、请求响应结构、状态码、错误码，以及四条业务底线：

- 三个管理端的读写行为与拆分前一致（用户管理、内容审核、系统公告、评论与帖子删除；
  政策管理与仪表板；企业岗位管理、投递处理与统计）；
- 审核三种动作对四个领域的公开状态影响一致：通过后公开发布、驳回后下架、
  撤销后退回待审核（学员端重新看不到）；
- 角色边界：管理员端只允许 super_admin、政府端只允许 government、企业端只允许
  enterprise，跨角色访问一律被拒；
- 审核状态变更一律经 database 的三个审核入口，路由层不直接写任何领域表。

断言全部基于 HTTP 行为，不测模块怎么划分（拆分不产生新行为，为结构写测试只会把
实现细节钉死，见 spec 的 Testing Decisions）。
"""


import json
import os
import sys
import unittest
from db_connection import get_connection
from db_domains import employment, reviews, users
from db_domains import policies as policies_db

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)



class AdminGovEntTestBase(unittest.TestCase):
    def setUp(self):
        from app import app
        self.app = app
        self.app.config['TESTING'] = True
        self.client = app.test_client()

    def _login(self, username, password='123456'):
        r = self.client.post('/api/auth/login', data=json.dumps(
            {'username': username, 'password': password}),
            content_type='application/json')
        return json.loads(r.data).get('session_id')

    def _headers(self, session_id):
        return {'X-Session-Id': session_id} if session_id else {}

    def _json(self, method, path, payload=None, session_id=None):
        return self.client.open(path, method=method, data=json.dumps(payload or {}),
                                content_type='application/json',
                                headers=self._headers(session_id))

    def _sessions(self):
        return {
            'admin': self._login('admin_demo', 'admin123'),
            'gov': self._login('gov_demo'),
            'enterprise': self._login('enterprise_demo'),
            'teacher': self._login('teacher_demo'),
            'student': self._login('student_demo'),
        }


class _DbCleanupMixin(AdminGovEntTestBase):
    def _cleanup(self):
        conn = get_connection()
        conn.execute("DELETE FROM job_applications WHERE user_id = 'student_demo'")
        conn.execute("DELETE FROM resumes WHERE user_id = 'student_demo'")
        conn.execute("DELETE FROM job_listings WHERE title LIKE '__T17%'")
        conn.execute("DELETE FROM government_policies WHERE title LIKE '__T17%'")
        conn.execute("DELETE FROM system_announcements WHERE title LIKE '__T17%'")
        conn.execute("DELETE FROM users WHERE username LIKE '__t17%'")
        conn.execute("DELETE FROM students WHERE name LIKE '__T17%'")
        conn.commit()
        conn.close()


class SuperAdminUserManagementTest(_DbCleanupMixin):
    """super admin: user management read/update/suspend/delete."""

    def setUp(self):
        super().setUp()
        self.addCleanup(self._cleanup)
        self.sessions = self._sessions()

    def _create_user(self, username, role='student'):
        r = self.client.post('/api/auth/register', data=json.dumps({
            'username': username, 'password': '123456', 'name': 'T17用户',
            'role': role,
        }), content_type='application/json')
        self.assertEqual(r.status_code, 200, r.data)

    def test_users_list_only_for_super_admin(self):
        r = self.client.get('/api/admin/users',
                            headers=self._headers(self.sessions['admin']))
        self.assertEqual(r.status_code, 200)
        body = json.loads(r.data)
        self.assertTrue(body['success'])
        self.assertIsInstance(body['users'], list)
        for u in body['users']:
            self.assertNotIn('password_hash', u)
            self.assertIn('can_delete', u)
            self.assertIn('can_suspend', u)
            self.assertIn('block_reason', u)

    def test_users_list_rejects_other_roles(self):
        for name in ('gov', 'enterprise', 'teacher', 'student'):
            r = self.client.get('/api/admin/users',
                                headers=self._headers(self.sessions[name]))
            self.assertEqual(r.status_code, 403, name)
            self.assertFalse(json.loads(r.data)['success'])
        self.assertEqual(self.client.get('/api/admin/users').status_code, 403)

    def test_admin_dashboard_reports_real_counts(self):
        r = self.client.get('/api/admin/dashboard',
                            headers=self._headers(self.sessions['admin']))
        self.assertEqual(r.status_code, 200)
        ov = json.loads(r.data)['overview']
        conn = get_connection()
        try:
            self.assertEqual(ov['users']['total'], conn.execute(
                "SELECT COUNT(*) FROM users").fetchone()[0])
            self.assertEqual(ov['reviews']['pending'], conn.execute(
                "SELECT COUNT(*) FROM content_reviews WHERE status='pending'"
            ).fetchone()[0])
        finally:
            conn.close()
        self.assertEqual(self.client.get(
            '/api/admin/dashboard', headers=self._headers(self.sessions['student'])
        ).status_code, 403)
        self.assertEqual(self.client.get('/api/admin/dashboard').status_code, 403)

    def test_update_user_role_and_profile(self):
        self._create_user('__t17user')
        r = self._json('PUT', '/api/admin/users/__t17user',
                       {'name': 'T17改名', 'role': 'teacher', 'status': 'active'},
                       session_id=self.sessions['admin'])
        self.assertEqual(r.status_code, 200)
        target = users.get_user_by_id('__t17user')
        self.assertEqual(target['name'], 'T17改名')
        self.assertEqual(target['role'], 'teacher')

        r = self._json('PUT', '/api/admin/users/__t17nobody', {'name': 'x'},
                       session_id=self.sessions['admin'])
        self.assertEqual(r.status_code, 404)
        self.assertFalse(json.loads(r.data)['success'])

    def test_last_super_admin_cannot_be_downgraded(self):
        r = self._json('PUT', '/api/admin/users/admin_demo', {'role': 'teacher'},
                       session_id=self.sessions['admin'])
        self.assertEqual(r.status_code, 400)
        body = json.loads(r.data)
        self.assertFalse(body['success'])
        self.assertIn('超级管理员', body['message'])
        self.assertEqual(users.get_user_by_id('admin_demo')['role'], 'super_admin')

    def test_suspend_and_restore_account(self):
        self._create_user('__t17suspend')
        r = self._json('POST', '/api/admin/users/__t17suspend/status',
                       {'status': 'suspended'}, session_id=self.sessions['admin'])
        self.assertEqual(r.status_code, 200)
        self.assertEqual(users.get_user_by_id('__t17suspend')['status'], 'suspended')
        login = self.client.post('/api/auth/login', data=json.dumps(
            {'username': '__t17suspend', 'password': '123456'}),
            content_type='application/json')
        self.assertFalse(json.loads(login.data)['success'])

        r = self._json('POST', '/api/admin/users/__t17suspend/status',
                       {'status': 'active'}, session_id=self.sessions['admin'])
        self.assertEqual(r.status_code, 200)
        self.assertEqual(users.get_user_by_id('__t17suspend')['status'], 'active')

    def test_cannot_suspend_self_or_use_bad_status(self):
        r = self._json('POST', '/api/admin/users/admin_demo/status',
                       {'status': 'suspended'}, session_id=self.sessions['admin'])
        self.assertEqual(r.status_code, 400)
        r = self._json('POST', '/api/admin/users/student_demo/status',
                       {'status': 'deleted'}, session_id=self.sessions['admin'])
        self.assertEqual(r.status_code, 400)
        r = self._json('POST', '/api/admin/users/__t17nobody/status',
                       {'status': 'active'}, session_id=self.sessions['admin'])
        self.assertEqual(r.status_code, 404)

    def test_delete_user_guards(self):
        r = self.client.delete('/api/admin/users/admin_demo',
                               headers=self._headers(self.sessions['admin']))
        self.assertEqual(r.status_code, 400)
        r = self.client.delete('/api/admin/users/__t17nobody',
                               headers=self._headers(self.sessions['admin']))
        self.assertEqual(r.status_code, 404)
        r = self.client.delete('/api/admin/users/student_demo',
                               headers=self._headers(self.sessions['admin']))
        self.assertEqual(r.status_code, 409)
        body = json.loads(r.data)
        self.assertFalse(body['success'])
        self.assertIn('relations', body)
        self.assertIn('relation_total', body)

    def test_delete_user_removes_row(self):
        self._create_user('__t17delete')
        r = self.client.delete('/api/admin/users/__t17delete',
                               headers=self._headers(self.sessions['admin']))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(json.loads(r.data)['success'])
        self.assertIsNone(users.get_user_by_id('__t17delete'))


class SuperAdminReviewTest(_DbCleanupMixin):
    """super admin: review list and the three review actions on four domains."""

    def setUp(self):
        super().setUp()
        self.addCleanup(self._cleanup)
        self.sessions = self._sessions()

    def _create_course_review(self):
        r = self._json('POST', '/api/teacher/courses',
                       {'title': '__T17课程__', 'description': 'T17', 'category': '综合'},
                       session_id=self.sessions['teacher'])
        self.assertEqual(r.status_code, 200, r.data)
        course_id = json.loads(r.data)['id']
        return course_id, reviews.get_review_by_content('course', course_id)['id']

    def _create_job_review(self):
        r = self._json('POST', '/api/enterprise/jobs',
                       {'title': '__T17岗位__', 'salary': '面议', 'location': '广州',
                        'category': '综合', 'description': 'T17'},
                       session_id=self.sessions['enterprise'])
        self.assertEqual(r.status_code, 200, r.data)
        job_id = json.loads(r.data)['id']
        return job_id, reviews.get_review_by_content('job', job_id)['id']

    def _create_model_3d_review(self):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO models_3d (title, description, craft_type, file_path, "
            "file_name, file_size, teacher_id, review_status, is_published) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', 0)",
            ('__T17模型__', 'T17', '', '/uploads/models_3d/t17.glb', 't17.glb', 1,
             'teacher_demo'))
        model_id = cursor.lastrowid
        conn.commit()
        conn.close()
        reviews.create_content_review('model_3d', model_id, 'teacher_demo')
        return model_id, reviews.get_review_by_content('model_3d', model_id)['id']

    def test_reviews_list_shape_and_filters(self):
        r = self.client.get('/api/admin/reviews',
                            headers=self._headers(self.sessions['admin']))
        self.assertEqual(r.status_code, 200)
        body = json.loads(r.data)
        self.assertTrue(body['success'])
        self.assertIn('reviews', body)
        self.assertIn('counts', body)
        for key in ('pending', 'approved', 'rejected'):
            self.assertIn(key, body['counts'])
        for review in body['reviews']:
            self.assertEqual(review['status'], 'pending')
            self.assertIn('detail', review)
            self.assertIn('is_self_reviewed', review)

        for query in ('?status=bogus', '?sort=bogus', '?status=all&sort=created'):
            r = self.client.get('/api/admin/reviews' + query,
                                headers=self._headers(self.sessions['admin']))
            self.assertEqual(r.status_code, 200, query)
        self.assertEqual(self.client.get(
            '/api/admin/reviews', headers=self._headers(self.sessions['teacher'])
        ).status_code, 403)
        self.assertEqual(self.client.get('/api/admin/reviews').status_code, 403)

    def test_approve_publishes_course_job_and_model_3d(self):
        course_id, course_review = self._create_course_review()
        job_id, job_review = self._create_job_review()
        model_id, model_review = self._create_model_3d_review()

        for review_id in (course_review, job_review, model_review):
            r = self._json('POST', '/api/admin/reviews/%d/approve' % review_id, {},
                           session_id=self.sessions['admin'])
            self.assertEqual(r.status_code, 200)
            self.assertTrue(json.loads(r.data)['success'])

        conn = get_connection()
        try:
            self.assertEqual(conn.execute(
                "SELECT is_published FROM courses WHERE id=?", (course_id,)
            ).fetchone()[0], 1)
            self.assertEqual(conn.execute(
                "SELECT review_status FROM job_listings WHERE id=?", (job_id,)
            ).fetchone()[0], 'approved')
            self.assertEqual(conn.execute(
                "SELECT is_published FROM models_3d WHERE id=?", (model_id,)
            ).fetchone()[0], 1)
        finally:
            conn.close()

        courses = json.loads(self.client.get('/api/teacher/public-courses').data)['courses']
        self.assertIn(course_id, [c['id'] for c in courses])
        jobs = json.loads(self.client.get('/api/employment/jobs').data)['jobs']
        self.assertIn(job_id, [j['id'] for j in jobs])
        models = json.loads(self.client.get('/api/teacher/public-models-3d').data)['models']
        self.assertIn(model_id, [m['id'] for m in models])

    def test_reject_unpublishes_course_and_job(self):
        course_id, course_review = self._create_course_review()
        job_id, job_review = self._create_job_review()

        for review_id in (course_review, job_review):
            r = self._json('POST', '/api/admin/reviews/%d/reject' % review_id,
                           {'comment': 'T17驳回理由'}, session_id=self.sessions['admin'])
            self.assertEqual(r.status_code, 200)

        conn = get_connection()
        try:
            self.assertEqual(conn.execute(
                "SELECT is_published FROM courses WHERE id=?", (course_id,)
            ).fetchone()[0], 0)
            self.assertEqual(conn.execute(
                "SELECT review_status FROM job_listings WHERE id=?", (job_id,)
            ).fetchone()[0], 'rejected')
        finally:
            conn.close()

        courses = json.loads(self.client.get('/api/teacher/public-courses').data)['courses']
        self.assertNotIn(course_id, [c['id'] for c in courses])
        jobs = json.loads(self.client.get('/api/employment/jobs').data)['jobs']
        self.assertNotIn(job_id, [j['id'] for j in jobs])

        review = reviews.get_review_by_content('job', job_id)
        self.assertEqual(review['review_comment'], 'T17驳回理由')
        mine = json.loads(self._json(
            'GET', '/api/enterprise/jobs',
            session_id=self.sessions['enterprise']).data)['jobs']
        row = next(j for j in mine if j['id'] == job_id)
        self.assertEqual(row['review_comment'], 'T17驳回理由')

    def test_revoke_hides_content_from_learners_again(self):
        course_id, course_review = self._create_course_review()
        job_id, job_review = self._create_job_review()
        for review_id in (course_review, job_review):
            self._json('POST', '/api/admin/reviews/%d/approve' % review_id, {},
                       session_id=self.sessions['admin'])

        r = self._json('POST', '/api/admin/reviews/%d/revoke' % course_review, {},
                       session_id=self.sessions['admin'])
        self.assertEqual(r.status_code, 200)
        self.assertEqual(json.loads(r.data)['message'], '已撤销，退回待审核')
        r = self._json('POST', '/api/admin/reviews/%d/revoke' % job_review, {},
                       session_id=self.sessions['admin'])
        self.assertEqual(r.status_code, 200)

        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT review_status, is_published FROM courses WHERE id=?",
                (course_id,)).fetchone()
            self.assertEqual((row[0], row[1]), ('pending', 0))
            self.assertEqual(conn.execute(
                "SELECT review_status FROM job_listings WHERE id=?", (job_id,)
            ).fetchone()[0], 'pending')
        finally:
            conn.close()

        jobs = json.loads(self.client.get('/api/employment/jobs').data)['jobs']
        self.assertNotIn(job_id, [j['id'] for j in jobs])
        courses = json.loads(self.client.get('/api/teacher/public-courses').data)['courses']
        self.assertNotIn(course_id, [c['id'] for c in courses])
        self.assertEqual(
            self.client.get('/api/employment/jobs/%d' % job_id).status_code, 404)

    def test_revoke_error_branches(self):
        r = self._json('POST', '/api/admin/reviews/999999/revoke', {},
                       session_id=self.sessions['admin'])
        self.assertEqual(r.status_code, 404)
        _, pending_review = self._create_course_review()
        r = self._json('POST', '/api/admin/reviews/%d/revoke' % pending_review, {},
                       session_id=self.sessions['admin'])
        # 现状：本就是 pending 时 reviews.revoke_review 返回 'unchanged'，它不在
        # 路由层的两个分支里，因此落回成功分支。这是拆分前的行为，本次只锁不改。
        self.assertEqual(r.status_code, 200)
        self.assertTrue(json.loads(r.data)['success'])

    def test_review_actions_require_super_admin(self):
        _, review_id = self._create_course_review()
        for action in ('approve', 'reject', 'revoke'):
            for name in ('gov', 'enterprise', 'teacher', 'student'):
                r = self._json('POST', '/api/admin/reviews/%d/%s' % (review_id, action),
                               {'comment': 'x'}, session_id=self.sessions[name])
                self.assertEqual(r.status_code, 403, '%s/%s' % (name, action))
            self.assertEqual(
                self._json('POST', '/api/admin/reviews/%d/%s' % (review_id, action),
                           {'comment': 'x'}).status_code, 403, action)

    def test_review_dispatch_keeps_success_case_visible_after_approve(self):
        """第四种可审核内容：案例过审后学员端可见（审核分派不能漏类型）。

        案例正文不落库，可见性完全由 content_reviews.status 决定，因此它没有
        目标表窄接口 —— 分派表里没有 success_case 一行，审核状态本身就是开关。
        这里自造一条 pending 记录来验证，不依赖演示库里恰好有待审案例。
        """
        from db_domains import content
        cases = content.get_cases()
        self.assertTrue(cases, 'success_cases 表为空，无法验证案例审核门禁')
        case_id = cases[0]['id']
        conn = get_connection()
        # 记下原始状态，cleanup 按原样恢复（不是无条件全置 approved）：
        # 若某条内容原本有多条审核记录，无条件置 approved 会让同一个 content_id
        # 出现多条 approved，把 get_case_review_stats 的 approved 计数撑爆，
        # 进而污染其它测试文件里的案例可见性断言。
        original = {r['id']: (r['status'], r['review_comment'], r['reviewed_by'],
                              r['reviewed_at'])
                    for r in conn.execute(
                        'SELECT id, status, review_comment, reviewed_by, reviewed_at '
                        "FROM content_reviews WHERE content_type='success_case'")}
        created_ids = []
        conn.close()
        conn = get_connection()
        # 预置案例默认已通过，先整体退回 pending，才能观察「过审后重新可见」。
        conn.execute(
            "UPDATE content_reviews SET status='pending', "
            "review_comment='', reviewed_at=NULL WHERE content_type='success_case'")
        conn.commit()
        conn.close()
        self.addCleanup(self._restore_case_review, original, created_ids)

        before = json.loads(self.client.get('/api/resources/cases').data)['cases']
        self.assertNotIn(case_id, [c['id'] for c in before],
                         '待审案例不应对学员端可见')

        # 走审核列表取回真正的审核记录 id（不是自造的），证明列表与动作用的是同一条记录
        listed = json.loads(self.client.get(
            '/api/admin/reviews?content_type=success_case&status=pending',
            headers=self._headers(self.sessions['admin'])).data)['reviews']
        row = next(r for r in listed if r['content_id'] == case_id)
        self.assertEqual(row['detail']['id'], case_id, '审核详情应带上案例正文')
        self.assertTrue(row['is_self_reviewed'], '预置案例是自提自审，必须如实标注')

        r = self._json('POST', '/api/admin/reviews/%d/approve' % row['id'], {},
                       session_id=self.sessions['admin'])
        self.assertEqual(r.status_code, 200)
        after = json.loads(self.client.get('/api/resources/cases').data)['cases']
        self.assertIn(case_id, [c['id'] for c in after], '过审后案例应对学员端可见')

    def _restore_case_review(self, original, created_ids):
        """把案例审核记录恢复成测试前的原样，不污染后续用例。

        逐条按 id 复原 status / review_comment / reviewed_by / reviewed_at，
        并删掉测试期间新建的记录。无条件「全部置 approved」会让同一 content_id
        出现多条 approved，把 approved 计数撑爆（T17 合并后实测踩到过）。
        """
        for review_id in created_ids:
            reviews.delete_review_by_id(review_id)
        conn = get_connection()
        for review_id, state in original.items():
            status, comment, reviewed_by, reviewed_at = state
            conn.execute(
                'UPDATE content_reviews SET status=?, review_comment=?, '
                'reviewed_by=?, reviewed_at=? WHERE id=?',
                (status, comment, reviewed_by, reviewed_at, review_id))
        conn.commit()
        conn.close()


class SuperAdminAnnouncementAndModerationTest(_DbCleanupMixin):
    """super admin: system announcements CRUD plus comment/discussion deletion."""

    def setUp(self):
        super().setUp()
        self.addCleanup(self._cleanup)
        self.sessions = self._sessions()

    def test_system_announcement_crud(self):
        r = self.client.get('/api/admin/system-announcements',
                            headers=self._headers(self.sessions['admin']))
        self.assertEqual(r.status_code, 200)
        self.assertIsInstance(json.loads(r.data)['announcements'], list)
        self.assertEqual(self.client.get(
            '/api/admin/system-announcements',
            headers=self._headers(self.sessions['student'])).status_code, 403)
        self.assertEqual(self.client.get('/api/admin/system-announcements').status_code, 403)

        r = self._json('POST', '/api/admin/system-announcements',
                       {'title': '__T17公告__', 'content': 'T17内容', 'is_pinned': 1},
                       session_id=self.sessions['admin'])
        self.assertEqual(r.status_code, 200)
        ann_id = json.loads(r.data)['id']

        anns = json.loads(self.client.get('/api/system-announcements').data)['announcements']
        self.assertIn(ann_id, [a['id'] for a in anns])

        r = self.client.delete('/api/admin/system-announcements/%d' % ann_id,
                               headers=self._headers(self.sessions['admin']))
        self.assertEqual(r.status_code, 200)
        anns = json.loads(self.client.get('/api/system-announcements').data)['announcements']
        self.assertNotIn(ann_id, [a['id'] for a in anns])

    def test_announcement_write_requires_super_admin(self):
        for name in ('gov', 'enterprise', 'teacher', 'student'):
            self.assertEqual(self._json(
                'POST', '/api/admin/system-announcements',
                {'title': '__T17公告__', 'content': 'x'},
                session_id=self.sessions[name]).status_code, 403, name)
            self.assertEqual(self.client.delete(
                '/api/admin/system-announcements/1',
                headers=self._headers(self.sessions[name])).status_code, 403, name)
        self.assertEqual(self._json(
            'POST', '/api/admin/system-announcements',
            {'title': '__T17公告__', 'content': 'x'}).status_code, 403)

    def test_delete_comment_and_discussion_soft_delete(self):
        disc = self._json('POST', '/api/discussions',
                          {'title': '__T17帖子__', 'content': 'T17', 'category': 'general'},
                          session_id=self.sessions['student'])
        self.assertEqual(disc.status_code, 200, disc.data)
        disc_id = json.loads(disc.data)['id']
        comment = self._json('POST', '/api/comments',
                             {'target_type': 'discussion', 'target_id': disc_id,
                              'content': 'T17评论'},
                             session_id=self.sessions['student'])
        self.assertEqual(comment.status_code, 200, comment.data)
        comment_id = json.loads(comment.data)['id']

        for name in ('gov', 'enterprise', 'teacher', 'student'):
            self.assertEqual(self.client.delete(
                '/api/admin/comments/%d' % comment_id,
                headers=self._headers(self.sessions[name])).status_code, 403, name)

        r = self.client.delete('/api/admin/comments/%d' % comment_id,
                               headers=self._headers(self.sessions['admin']))
        self.assertEqual(r.status_code, 200)
        self.assertIn('已删除违规评论', json.loads(r.data)['message'])

        r = self.client.delete('/api/admin/discussions/%d' % disc_id,
                               headers=self._headers(self.sessions['admin']))
        self.assertEqual(r.status_code, 200)
        self.assertIn('已删除违规帖子', json.loads(r.data)['message'])

        comments = json.loads(self.client.get(
            '/api/comments?target_type=discussion&target_id=%d' % disc_id).data)['comments']
        self.assertNotIn(comment_id, [c['id'] for c in comments])
        discussions = json.loads(self.client.get('/api/discussions').data)['discussions']
        self.assertNotIn(disc_id, [d['id'] for d in discussions])


class GovernmentDomainTest(_DbCleanupMixin):
    """government: policy management and dashboard."""

    def setUp(self):
        super().setUp()
        self.addCleanup(self._cleanup)
        self.sessions = self._sessions()

    def test_policy_crud_round_trip(self):
        r = self._json('POST', '/api/government/policies',
                       {'title': '__T17政策__', 'content': 'T17内容', 'category': 'general',
                        'summary': 'T17摘要', 'source': 'T17来源'},
                       session_id=self.sessions['gov'])
        self.assertEqual(r.status_code, 200)
        policy_id = json.loads(r.data)['id']

        policies = json.loads(self._json(
            'GET', '/api/government/policies',
            session_id=self.sessions['gov']).data)['policies']
        row = next(p for p in policies if p['id'] == policy_id)
        self.assertEqual(row['category'], '综合')
        self.assertEqual(row['summary'], 'T17摘要')
        self.assertEqual(row['title'], '__T17政策__')

        r = self._json('PUT', '/api/government/policies/%d' % policy_id,
                       {'title': '__T17政策改__', 'is_published': 0, 'source': '新来源'},
                       session_id=self.sessions['gov'])
        self.assertEqual(r.status_code, 200)
        row = policies_db.get_policy_by_id(policy_id)
        self.assertEqual(row['title'], '__T17政策改__')
        self.assertEqual(row['is_published'], 0)

        r = self.client.delete('/api/government/policies/%d' % policy_id,
                               headers=self._headers(self.sessions['gov']))
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(policies_db.get_policy_by_id(policy_id))

    def test_policy_create_requires_title_and_content(self):
        for payload in ({'title': '', 'content': 'x'}, {'title': 'x', 'content': ''}):
            r = self._json('POST', '/api/government/policies', payload,
                           session_id=self.sessions['gov'])
            self.assertEqual(r.status_code, 400)
            self.assertIn('标题和内容不能为空', json.loads(r.data)['message'])

    def test_policy_write_role_boundary(self):
        for name in ('admin', 'enterprise', 'teacher', 'student'):
            self.assertEqual(self._json(
                'POST', '/api/government/policies', {'title': 'x', 'content': 'y'},
                session_id=self.sessions[name]).status_code, 403, name)
            self.assertEqual(self._json(
                'GET', '/api/government/policies', session_id=self.sessions[name]
            ).status_code, 403, name)
        self.assertEqual(self._json('GET', '/api/government/policies').status_code, 403)
        self.assertEqual(self._json('PUT', '/api/government/policies/1', {}).status_code, 403)
        self.assertEqual(self.client.delete('/api/government/policies/1').status_code, 403)

    def test_unpublished_policy_hidden_from_learners(self):
        r = self._json('POST', '/api/government/policies',
                       {'title': '__T17下架__', 'content': 'T17'},
                       session_id=self.sessions['gov'])
        policy_id = json.loads(r.data)['id']
        before = json.loads(self.client.get('/api/resources/policies').data)['policies']
        self.assertIn(policy_id, [p['id'] for p in before])

        r = self._json('PUT', '/api/government/policies/%d' % policy_id,
                       {'is_published': 0}, session_id=self.sessions['gov'])
        self.assertEqual(r.status_code, 200)
        after = json.loads(self.client.get('/api/resources/policies').data)['policies']
        self.assertNotIn(policy_id, [p['id'] for p in after])

    def test_dashboard_overview(self):
        r = self.client.get('/api/government/dashboard',
                            headers=self._headers(self.sessions['gov']))
        self.assertEqual(r.status_code, 200)
        body = json.loads(r.data)
        self.assertTrue(body['success'])
        self.assertIn('policies', body['overview'])
        self.assertIn('cases', body['overview'])
        for name in ('admin', 'enterprise', 'teacher', 'student'):
            self.assertEqual(self.client.get(
                '/api/government/dashboard',
                headers=self._headers(self.sessions[name])).status_code, 403, name)
        self.assertEqual(self.client.get('/api/government/dashboard').status_code, 403)


class EnterpriseDomainTest(_DbCleanupMixin):
    """enterprise: job management, application handling and stats."""

    def setUp(self):
        super().setUp()
        self.addCleanup(self._cleanup)
        self.sessions = self._sessions()

    def _create_job(self, title='__T17岗位__'):
        r = self._json('POST', '/api/enterprise/jobs',
                       {'title': title, 'salary': '面议', 'location': '广州',
                        'category': '综合', 'description': 'T17',
                        'requirements': ['会打字']},
                       session_id=self.sessions['enterprise'])
        self.assertEqual(r.status_code, 200, r.data)
        return json.loads(r.data)['id']

    def test_job_list_and_create(self):
        job_id = self._create_job()
        r = self._json('GET', '/api/enterprise/jobs',
                       session_id=self.sessions['enterprise'])
        self.assertEqual(r.status_code, 200)
        jobs = json.loads(r.data)['jobs']
        row = next(j for j in jobs if j['id'] == job_id)
        self.assertEqual(row['title'], '__T17岗位__')
        self.assertEqual(row['requirements'], ['会打字'])
        self.assertIn('review_comment', row)
        self.assertIn('reviewed_at', row)
        self.assertEqual(row['review_status'], 'pending')
        self.assertTrue(json.loads(r.data)['success'])

    def test_job_update_and_delete(self):
        job_id = self._create_job()
        r = self._json('PUT', '/api/enterprise/jobs/%d' % job_id,
                       {'title': '__T17改题__', 'requirements': ['会写字']},
                       session_id=self.sessions['enterprise'])
        self.assertEqual(r.status_code, 200)
        self.assertIn('需重新审核', json.loads(r.data)['message'])
        row = employment.get_job_by_id(job_id)
        self.assertEqual(row['review_status'], 'pending')
        self.assertEqual(row['requirements'], ['会写字'])

        r = self.client.delete('/api/enterprise/jobs/%d' % job_id,
                               headers=self._headers(self.sessions['enterprise']))
        self.assertEqual(r.status_code, 200)
        jobs = json.loads(self._json(
            'GET', '/api/enterprise/jobs',
            session_id=self.sessions['enterprise']).data)['jobs']
        self.assertNotIn(job_id, [j['id'] for j in jobs])

    def test_cannot_delete_other_enterprises_job(self):
        job_id = self._create_job()
        for name in ('admin', 'gov', 'teacher', 'student'):
            r = self.client.delete('/api/enterprise/jobs/%d' % job_id,
                                   headers=self._headers(self.sessions[name]))
            self.assertEqual(r.status_code, 403, name)
        self.assertEqual(self.client.delete(
            '/api/enterprise/jobs/%d' % job_id).status_code, 403)

    def test_enterprise_routes_role_boundary(self):
        job_id = self._create_job()
        paths = [
            ('GET', '/api/enterprise/jobs'),
            ('POST', '/api/enterprise/jobs'),
            ('PUT', '/api/enterprise/jobs/%d' % job_id),
            ('DELETE', '/api/enterprise/jobs/%d' % job_id),
            ('GET', '/api/enterprise/applications'),
            ('PUT', '/api/enterprise/applications/1'),
            ('GET', '/api/enterprise/stats'),
        ]
        for name in ('admin', 'gov', 'teacher', 'student'):
            for method, path in paths:
                r = self._json(method, path, {}, session_id=self.sessions[name])
                self.assertEqual(r.status_code, 403, '%s %s' % (name, path))
        for method, path in paths:
            self.assertEqual(self._json(method, path, {}).status_code, 403, path)

    def test_applications_join_resume_fields(self):
        job_id = self._create_job()
        conn = get_connection()
        conn.execute("UPDATE job_listings SET review_status='approved' WHERE id=?", (job_id,))
        conn.commit()
        conn.close()

        self._json('POST', '/api/employment/apply',
                   {'user_id': 'student_demo', 'job_id': job_id},
                   session_id=self.sessions['student'])
        self._json('PUT', '/api/employment/resume/student_demo',
                   {'title': 'T17简历', 'education': '本科', 'work_years': 3,
                    'skills': '荔枝种植', 'self_eval': '踏实肯干'},
                   session_id=self.sessions['student'])

        r = self._json('GET', '/api/enterprise/applications',
                       session_id=self.sessions['enterprise'])
        self.assertEqual(r.status_code, 200)
        apps = [a for a in json.loads(r.data)['applications'] if a['job_id'] == job_id]
        self.assertTrue(apps)
        row = apps[0]
        for key in ('resume_title', 'resume_education', 'resume_work_years',
                    'resume_skills', 'resume_self_eval', 'job_title'):
            self.assertIn(key, row)
        self.assertEqual(row['resume_title'], 'T17简历')
        self.assertEqual(int(row['resume_work_years']), 3)

    def test_update_application_status(self):
        job_id = self._create_job()
        conn = get_connection()
        conn.execute("UPDATE job_listings SET review_status='approved' WHERE id=?", (job_id,))
        conn.commit()
        conn.close()
        self._json('POST', '/api/employment/apply',
                   {'user_id': 'student_demo', 'job_id': job_id},
                   session_id=self.sessions['student'])
        conn = get_connection()
        app_id = conn.execute(
            "SELECT id FROM job_applications WHERE job_id=?", (job_id,)).fetchone()[0]
        conn.close()

        r = self._json('PUT', '/api/enterprise/applications/%d' % app_id,
                       {'status': 'interview'}, session_id=self.sessions['enterprise'])
        self.assertEqual(r.status_code, 200)
        self.assertIn('已通知面试', json.loads(r.data)['message'])
        row = get_connection().execute(
            "SELECT status FROM job_applications WHERE id=?", (app_id,)).fetchone()
        self.assertEqual(row[0], 'interview')

        r = self._json('PUT', '/api/enterprise/applications/%d' % app_id,
                       {'status': 'hired'}, session_id=self.sessions['enterprise'])
        self.assertEqual(r.status_code, 400)
        self.assertIn('无效的状态', json.loads(r.data)['message'])

    def test_stats_counts_only_approved_jobs(self):
        job_id = self._create_job()
        r = self._json('GET', '/api/enterprise/stats',
                       session_id=self.sessions['enterprise'])
        self.assertEqual(r.status_code, 200)
        stats = json.loads(r.data)['stats']
        self.assertEqual(set(stats), {'total_jobs', 'pending_jobs', 'total_applications'})
        conn = get_connection()
        try:
            approved = conn.execute(
                "SELECT COUNT(*) FROM job_listings WHERE enterprise_id='enterprise_demo' "
                "AND review_status='approved'").fetchone()[0]
            pending = conn.execute(
                "SELECT COUNT(*) FROM job_listings WHERE enterprise_id='enterprise_demo' "
                "AND COALESCE(review_status,'') != 'approved'").fetchone()[0]
            apps = conn.execute(
                "SELECT COUNT(*) FROM job_applications ja JOIN job_listings jl "
                "ON ja.job_id=jl.id WHERE jl.enterprise_id='enterprise_demo'").fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(stats['total_jobs'], approved)
        self.assertEqual(stats['pending_jobs'], pending)
        self.assertEqual(stats['total_applications'], apps)

        conn = get_connection()
        conn.execute("UPDATE job_listings SET review_status='approved' WHERE id=?", (job_id,))
        conn.commit()
        conn.close()
        stats2 = json.loads(self._json(
            'GET', '/api/enterprise/stats',
            session_id=self.sessions['enterprise']).data)['stats']
        self.assertEqual(stats2['total_jobs'], approved + 1)
        self.assertEqual(stats2['pending_jobs'], pending - 1)


if __name__ == '__main__':
    unittest.main()

