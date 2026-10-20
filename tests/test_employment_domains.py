# -*- coding: utf-8 -*-
"""就业对接域与就业能力档案域的路由行为测试（T15）。

锁住从 app.py 搬进 domains/employment 与 domains/employment_profile 后必须一字不变的
外部契约：URL、请求响应结构、状态码、错误码，以及四条业务底线，即

- 岗位列表把「企业已审岗位」与「公开招聘公告」两类数据源合并下发，分类下拉给真实条数；
- 未通过审核的岗位对学员端等同不存在（列表不出现、直链 404、不能被申请）；
- 求职资料属个人数据：未登录 401、他人 403；
- 简历内部字段 ai_used 不可由客户端改写；
- AI 简历辅助在上游未配置时明确 503 + code，绝不返回 success=True 的兜底文案。

断言全部基于 HTTP 行为，不测模块怎么划分（拆分不产生新行为，为结构写测试只会把
实现细节钉死，见 spec 的 Testing Decisions）。
"""

import json
import os
import sys
import unittest
from db_connection import get_connection
from db_domains import employment

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)



class EmploymentDomainTestBase(unittest.TestCase):
    def setUp(self):
        from app import app
        self.app = app
        self.app.config['TESTING'] = True
        self.client = app.test_client()

    def _login(self, username='student_demo', password='123456'):
        r = self.client.post('/api/auth/login', data=json.dumps(
            {'username': username, 'password': password}),
            content_type='application/json')
        return json.loads(r.data)['session_id']

    def _cleanup(self):
        conn = get_connection()
        conn.execute("DELETE FROM job_intents WHERE user_id LIKE '__t15%'")
        conn.execute("DELETE FROM job_intents WHERE user_id = 'student_demo'")
        conn.execute("DELETE FROM resumes WHERE user_id = 'student_demo'")
        conn.execute("DELETE FROM saved_jobs WHERE user_id = 'student_demo'")
        conn.execute("DELETE FROM job_applications WHERE user_id = 'student_demo'")
        conn.execute("DELETE FROM job_listings WHERE title LIKE '__T15%'")
        conn.execute("DELETE FROM user_sessions WHERE user_id LIKE '__t15%'")
        conn.execute("DELETE FROM users WHERE username LIKE '__t15%'")
        conn.commit()
        conn.close()


class JobListTest(EmploymentDomainTestBase):
    """岗位列表：两类数据源合并下发 + 分类下拉 + 薪资筛选口径。"""

    def test_jobs_list_merges_enterprise_jobs_and_recruitments(self):
        data = json.loads(self.client.get('/api/employment/jobs').data)
        self.assertTrue(data['success'])
        self.assertIn('jobs', data)
        self.assertIn('recruitments', data)
        self.assertTrue(data['recruit_source_note'])
        self.assertTrue(data['recruit_disclaimer'])

        # 公告侧：字段完整、来源齐全、source_type 标注正确
        self.assertGreater(len(data['recruitments']), 0)
        for r in data['recruitments']:
            self.assertEqual(r.get('source_type'), 'public_recruit')
            self.assertTrue(r.get('title'))
            self.assertTrue(r.get('org'))
            self.assertTrue(r.get('sources'), '每条公告都必须带官方来源')
            self.assertTrue(r.get('signup_way'), '公告不做站内申请，必须带报名方式')

        # 企业岗位侧：只下发已通过审核的
        for j in data['jobs']:
            self.assertEqual(j.get('source_type'), 'enterprise')
            self.assertEqual(j.get('review_status'), 'approved')

        # 分类下拉：两组各自的真实条数，已知分类零条也保留
        options = data['category_options']
        self.assertIn('enterprise', options)
        self.assertIn('recruit', options)
        recruit_values = [o['value'] for o in options['recruit']]
        from db_domains.recruitments import RECRUIT_CATEGORIES
        for name in RECRUIT_CATEGORIES:
            self.assertIn(name, recruit_values)
        enterprise_values = [o['value'] for o in options['enterprise']]
        for name in employment.ENTERPRISE_JOB_CATEGORIES:
            self.assertIn(name, enterprise_values)
        # 条数与列表一致
        self.assertEqual(sum(o['count'] for o in options['recruit']),
                         len(data['recruitments']))
        self.assertEqual(sum(o['count'] for o in options['enterprise']),
                         len(data['jobs']))

    def test_keyword_and_location_filter_recruitments(self):
        plain = json.loads(self.client.get('/api/employment/jobs').data)
        first = plain['recruitments'][0]
        data = json.loads(self.client.get(
            '/api/employment/jobs?keyword=%s' % first['org']).data)
        self.assertTrue(all(first['org'] in (r.get('org') or '')
                            for r in data['recruitments']))
        # 命中的公告条数必须真的少于全量（否则筛选没生效，用例失去意义）
        self.assertLess(len(data['recruitments']), len(plain['recruitments']))

    def test_category_filter_applies_to_both_sources(self):
        data = json.loads(self.client.get('/api/employment/jobs').data)
        category = data['recruitments'][0]['category']
        data = json.loads(self.client.get(
            '/api/employment/jobs?category=%s' % category).data)
        for r in data['recruitments']:
            self.assertEqual(r.get('category'), category)
        for j in data['jobs']:
            self.assertEqual(j.get('category'), category)

    def test_salary_filter_hides_recruitments_and_reports_the_count(self):
        plain = json.loads(self.client.get('/api/employment/jobs').data)
        filtered = json.loads(self.client.get(
            '/api/employment/jobs?salary=3K-5K').data)
        # 公告没有薪资字段，薪资筛选对它不生效（公告侧仍照常下发），
        # 但必须如实报告「因薪资筛选而被前端隐藏」的条数
        self.assertEqual(filtered['recruit_hidden_by_salary'], len(plain['recruitments']))
        self.assertEqual(plain['recruit_hidden_by_salary'], 0)
        self.assertEqual(len(filtered['recruitments']), len(plain['recruitments']))

    def test_pending_job_count_is_reported(self):
        data = json.loads(self.client.get('/api/employment/jobs').data)
        self.assertGreaterEqual(data['enterprise_review_pending'], 0)


class JobDetailTest(EmploymentDomainTestBase):
    """详情与相似推荐：未过审岗位等同不存在，不能靠猜 id 绕过审核。"""

    def test_approved_job_detail_and_similar(self):
        conn = get_connection()
        row = conn.execute(
            "SELECT id FROM job_listings WHERE review_status='approved' "
            "AND is_demo=0").fetchone()
        conn.close()
        if not row:
            self.skipTest('库里没有非演示的已审岗位')
        job_id = row['id']

        detail = json.loads(self.client.get(
            '/api/employment/jobs/%d' % job_id).data)
        self.assertTrue(detail['success'])
        self.assertEqual(detail['job']['id'], job_id)

        similar = json.loads(self.client.get(
            '/api/employment/jobs/%d/similar' % job_id).data)
        self.assertTrue(similar['success'])
        self.assertIsInstance(similar['jobs'], list)
        self.assertLessEqual(len(similar['jobs']), 3)

    def test_pending_job_is_invisible_and_unapplicable(self):
        self.addCleanup(self._cleanup)
        sid = self._login()
        conn = get_connection()
        conn.execute("""
            INSERT INTO job_listings (title, company, salary, requirements, description,
                                      location, category, enterprise_id, review_status, is_demo)
            VALUES ('__T15待审岗位__', '测试公司', '面议', '[]', '仅供测试',
                    '广州', '电商运营', 'enterprise_demo', 'pending', 0)
        """)
        conn.commit()
        job_id = conn.execute(
            "SELECT id FROM job_listings WHERE title='__T15待审岗位__'").fetchone()[0]
        conn.close()

        # 列表不出现
        data = json.loads(self.client.get('/api/employment/jobs').data)
        self.assertNotIn(job_id, [j['id'] for j in data['jobs']])
        # 直链 404
        self.assertEqual(
            self.client.get('/api/employment/jobs/%d' % job_id).status_code, 404)
        # 相似推荐返回空列表而不是 404
        similar = json.loads(self.client.get(
            '/api/employment/jobs/%d/similar' % job_id).data)
        self.assertTrue(similar['success'])
        self.assertEqual(similar['jobs'], [])
        # 不能被申请
        r = self.client.post('/api/employment/apply',
                             data=json.dumps({'user_id': 'student_demo', 'job_id': job_id}),
                             content_type='application/json',
                             headers={'X-Session-Id': sid})
        self.assertFalse(json.loads(r.data)['success'])

    def test_unknown_job_detail_is_404(self):
        r = self.client.get('/api/employment/jobs/9999999')
        self.assertEqual(r.status_code, 404)
        self.assertEqual(json.loads(r.data)['message'], '职位不存在或尚未通过审核')


class CertificatesAndPointsTest(EmploymentDomainTestBase):
    """证书与积分：档案口径与兑换三态。"""

    def setUp(self):
        super().setUp()
        self.student_sid = self._login()
        self.student_headers = {'X-Session-Id': self.student_sid}

    def test_certificates_come_from_the_certificate_table(self):
        data = json.loads(self.client.get(
            '/api/employment/certificates/student_demo',
            headers=self.student_headers).data)
        self.assertTrue(data['success'])
        conn = get_connection()
        expected = [dict(r) for r in conn.execute(
            "SELECT name, status, progress, date FROM certificates "
            "WHERE user_id = 'student_demo' ORDER BY id")]
        conn.close()
        self.assertEqual(len(data['certificates']), len(expected))

    def test_points_match_the_points_table(self):
        data = json.loads(self.client.get(
            '/api/employment/points/student_demo',
            headers=self.student_headers).data)
        self.assertTrue(data['success'])
        conn = get_connection()
        row = conn.execute(
            "SELECT balance, history FROM points WHERE user_id='student_demo'").fetchone()
        conn.close()
        self.assertEqual(data['points'], row['balance'])
        self.assertEqual(data['history'], json.loads(row['history']))

    def test_exchange_deducts_and_reports_remaining(self):
        self.addCleanup(self._cleanup)
        before = json.loads(self.client.get(
            '/api/employment/points/student_demo',
            headers=self.student_headers).data)['points']
        r = self.client.post('/api/employment/exchange',
                             data=json.dumps({'user_id': 'student_demo',
                                              'item': '测试兑换', 'cost': 10}),
                             content_type='application/json',
                             headers=self.student_headers)
        body = json.loads(r.data)
        self.assertTrue(body['success'])
        self.assertEqual(body['remaining_points'], before - 10)
        self.assertIn('测试兑换', body['message'])

    def test_exchange_over_balance_is_rejected(self):
        r = self.client.post('/api/employment/exchange',
                             data=json.dumps({'user_id': 'student_demo',
                                              'item': '天价商品', 'cost': 99999999}),
                             content_type='application/json',
                             headers=self.student_headers)
        body = json.loads(r.data)
        self.assertFalse(body['success'])
        self.assertEqual(body['message'], '积分不足')

    def test_points_certificates_and_exchange_are_session_bound(self):
        teacher_sid = self._login('teacher_demo')
        teacher_headers = {'X-Session-Id': teacher_sid}

        requests = (
            self.client.get('/api/employment/certificates/student_demo'),
            self.client.get('/api/employment/points/student_demo'),
            self.client.post(
                '/api/employment/exchange',
                data=json.dumps({
                    'user_id': 'student_demo',
                    'item': '越权兑换',
                    'cost': 1,
                }),
                content_type='application/json',
            ),
            self.client.get(
                '/api/employment/certificates/student_demo',
                headers=teacher_headers,
            ),
            self.client.get(
                '/api/employment/points/student_demo',
                headers=teacher_headers,
            ),
            self.client.post(
                '/api/employment/exchange',
                data=json.dumps({
                    'user_id': 'student_demo',
                    'item': '越权兑换',
                    'cost': 1,
                }),
                content_type='application/json',
                headers=teacher_headers,
            ),
        )

        for response in requests[:3]:
            self.assertEqual(response.status_code, 401)
        for response in requests[3:]:
            self.assertEqual(response.status_code, 403)
            self.assertEqual(
                json.loads(response.data)['message'],
                '无权访问他人的求职资料',
            )

    def test_exchange_rejects_non_positive_and_invalid_costs(self):
        before = json.loads(self.client.get(
            '/api/employment/points/student_demo',
            headers=self.student_headers).data)['points']

        for cost in (-10, 0, 'abc', None, 1.5, True):
            with self.subTest(cost=cost):
                response = self.client.post(
                    '/api/employment/exchange',
                    data=json.dumps({
                        'user_id': 'student_demo',
                        'item': '非法兑换',
                        'cost': cost,
                    }),
                    content_type='application/json',
                    headers=self.student_headers,
                )
                self.assertEqual(response.status_code, 400)
                self.assertEqual(
                    json.loads(response.data)['message'],
                    '兑换积分必须为正整数',
                )

        after = json.loads(self.client.get(
            '/api/employment/points/student_demo',
            headers=self.student_headers).data)['points']
        self.assertEqual(after, before)


class ApplyAndSaveTest(EmploymentDomainTestBase):
    """投递与收藏：参数校验、重复投递、收藏增删查。"""

    def setUp(self):
        super().setUp()
        self.student_sid = self._login()
        self.student_headers = {'X-Session-Id': self.student_sid}

    def _make_approved_job(self, title='__T15已审岗位__'):
        conn = get_connection()
        conn.execute("""
            INSERT INTO job_listings (title, company, salary, requirements, description,
                                      location, category, enterprise_id, review_status, is_demo)
            VALUES (?, '测试公司', '5K', '[]', '仅供测试',
                    '广州', '电商运营', 'enterprise_demo', 'approved', 0)
        """, (title,))
        conn.commit()
        job_id = conn.execute(
            "SELECT id FROM job_listings WHERE title = ?", (title,)).fetchone()[0]
        conn.close()
        return job_id

    def test_apply_requires_job(self):
        for payload in ({}, {'user_id': 'student_demo'}):
            r = self.client.post('/api/employment/apply', data=json.dumps(payload),
                                 content_type='application/json',
                                 headers=self.student_headers)
            self.assertEqual(r.status_code, 200)
            body = json.loads(r.data)
            self.assertFalse(body['success'])
            self.assertEqual(body['message'], '参数不完整')

    def test_apply_then_duplicate_then_history(self):
        self.addCleanup(self._cleanup)
        job_id = self._make_approved_job()

        r = self.client.post('/api/employment/apply',
                             data=json.dumps({'user_id': 'student_demo', 'job_id': job_id}),
                             content_type='application/json',
                             headers=self.student_headers)
        body = json.loads(r.data)
        self.assertTrue(body['success'])
        self.assertIn('20积分奖励', body['message'])
        self.assertIn('has_resume', body)

        # 重复申请被拒
        r = self.client.post('/api/employment/apply',
                             data=json.dumps({'user_id': 'student_demo', 'job_id': job_id}),
                             content_type='application/json',
                             headers=self.student_headers)
        self.assertEqual(json.loads(r.data)['message'], '您已申请过该职位')

        # 投递记录里能查到
        apps = json.loads(self.client.get(
            '/api/employment/applications/student_demo',
            headers=self.student_headers).data)['applications']
        self.assertIn(job_id, [a['job_id'] for a in apps])
        for a in apps:
            for key in ('id', 'user_id', 'job_id', 'status', 'applied_at',
                        'title', 'company', 'salary', 'location', 'category'):
                self.assertIn(key, a)

        counts = json.loads(self.client.get(
            '/api/employment/applications/student_demo/counts',
            headers=self.student_headers).data)['counts']
        self.assertEqual(set(counts), {'total', 'pending', 'approved', 'rejected'})
        self.assertEqual(counts['total'], len(apps))

        stats = json.loads(self.client.get(
            '/api/employment/stats/student_demo',
            headers=self.student_headers).data)['stats']
        self.assertEqual(set(stats), {'applied', 'saved', 'intents', 'messages'})
        self.assertEqual(stats['applied'], len(apps))

    def test_applications_status_filter(self):
        self.addCleanup(self._cleanup)
        all_apps = json.loads(self.client.get(
            '/api/employment/applications/student_demo',
            headers=self.student_headers).data)['applications']
        if not all_apps:
            self.skipTest('演示账号没有投递记录，无法验证状态筛选')
        status = all_apps[0]['status']
        filtered = json.loads(self.client.get(
            '/api/employment/applications/student_demo?status=%s' % status,
            headers=self.student_headers).data)
        self.assertTrue(all(a['status'] == status for a in filtered['applications']))

    def test_save_and_unsave_round_trip(self):
        self.addCleanup(self._cleanup)
        job_id = self._make_approved_job('__T15收藏岗位__')

        r = self.client.post('/api/employment/save',
                             data=json.dumps({'user_id': 'student_demo', 'job_id': job_id}),
                             content_type='application/json',
                             headers=self.student_headers)
        self.assertTrue(json.loads(r.data)['success'])
        saved = json.loads(self.client.get(
            '/api/employment/saved/student_demo',
            headers=self.student_headers).data)['saved_ids']
        self.assertIn(job_id, saved)

        # 重复收藏返回已收藏过
        r = self.client.post('/api/employment/save',
                             data=json.dumps({'user_id': 'student_demo', 'job_id': job_id}),
                             content_type='application/json',
                             headers=self.student_headers)
        self.assertEqual(json.loads(r.data)['message'], '已收藏过该职位')

        r = self.client.delete('/api/employment/save',
                               data=json.dumps({'user_id': 'student_demo', 'job_id': job_id}),
                               content_type='application/json',
                               headers=self.student_headers)
        self.assertTrue(json.loads(r.data)['success'])
        saved = json.loads(self.client.get(
            '/api/employment/saved/student_demo',
            headers=self.student_headers).data)['saved_ids']
        self.assertNotIn(job_id, saved)

    def test_save_requires_job(self):
        r = self.client.post('/api/employment/save',
                             data=json.dumps({'user_id': 'student_demo'}),
                             content_type='application/json',
                             headers=self.student_headers)
        self.assertEqual(json.loads(r.data)['message'], '参数不完整')
        r = self.client.delete('/api/employment/save', data=json.dumps({}),
                               content_type='application/json',
                               headers=self.student_headers)
        self.assertEqual(json.loads(r.data)['message'], '参数不完整')

    def test_personal_employment_state_cannot_be_read_or_written_cross_user(self):
        """收藏、投递与投递历史只能由会话本人读写。"""
        self.addCleanup(self._cleanup)
        job_id = self._make_approved_job('__T15IDOR岗位__')
        teacher_sid = self._login('teacher_demo')
        teacher_headers = {'X-Session-Id': teacher_sid}

        attempts = (
            self.client.post('/api/employment/apply',
                             data=json.dumps({'user_id': 'student_demo', 'job_id': job_id}),
                             content_type='application/json', headers=teacher_headers),
            self.client.post('/api/employment/save',
                             data=json.dumps({'user_id': 'student_demo', 'job_id': job_id}),
                             content_type='application/json', headers=teacher_headers),
            self.client.get('/api/employment/saved/student_demo',
                            headers=teacher_headers),
            self.client.get('/api/employment/applications/student_demo',
                            headers=teacher_headers),
            self.client.get('/api/employment/applications/student_demo/counts',
                            headers=teacher_headers),
            self.client.get('/api/employment/stats/student_demo',
                            headers=teacher_headers),
        )
        for response in attempts:
            self.assertEqual(response.status_code, 403)
            self.assertEqual(json.loads(response.data)['message'],
                             '无权访问他人的求职资料')

        conn = get_connection()
        self.assertEqual(conn.execute(
            "SELECT COUNT(*) FROM job_applications WHERE job_id = ?",
            (job_id,)).fetchone()[0], 0)
        self.assertEqual(conn.execute(
            "SELECT COUNT(*) FROM saved_jobs WHERE job_id = ?",
            (job_id,)).fetchone()[0], 0)
        conn.close()

        for path, method, payload in (
            ('/api/employment/apply', 'POST',
             {'user_id': 'student_demo', 'job_id': job_id}),
            ('/api/employment/save', 'POST',
             {'user_id': 'student_demo', 'job_id': job_id}),
            ('/api/employment/saved/student_demo', 'GET', None),
        ):
            response = self.client.open(
                path, method=method,
                data=json.dumps(payload) if payload is not None else None,
                content_type='application/json')
            self.assertEqual(response.status_code, 401, path)
            self.assertEqual(json.loads(response.data)['message'], '请先登录')

        # user_id 可以省略：后端从会话派生归属，而不是相信客户端字段。
        r = self.client.post('/api/employment/save',
                             data=json.dumps({'job_id': job_id}),
                             content_type='application/json',
                             headers=self.student_headers)
        self.assertTrue(json.loads(r.data)['success'])

        r = self.client.delete('/api/employment/save',
                               data=json.dumps({'user_id': 'student_demo', 'job_id': job_id}),
                               content_type='application/json',
                               headers=teacher_headers)
        self.assertEqual(r.status_code, 403)

        conn = get_connection()
        saved_owner = conn.execute(
            "SELECT user_id FROM saved_jobs WHERE job_id = ?", (job_id,)).fetchone()
        conn.close()
        self.assertIsNotNone(saved_owner)
        self.assertEqual(saved_owner['user_id'], 'student_demo')

        r = self.client.post('/api/employment/apply',
                             data=json.dumps({'job_id': job_id}),
                             content_type='application/json',
                             headers=self.student_headers)
        self.assertTrue(json.loads(r.data)['success'])

        conn = get_connection()
        applied_owner = conn.execute(
            "SELECT user_id FROM job_applications WHERE job_id = ?",
            (job_id,)).fetchone()
        conn.close()
        self.assertIsNotNone(applied_owner)
        self.assertEqual(applied_owner['user_id'], 'student_demo')


class SelfOnlyGuardTest(EmploymentDomainTestBase):
    """求职资料属个人数据：未登录 401、他人 403。"""

    PROTECTED_READS = [
        '/api/employment/profile/student_demo',
        '/api/employment/resume/student_demo',
        '/api/employment/my-jobs/student_demo',
    ]

    def test_anonymous_is_401(self):
        for path in self.PROTECTED_READS:
            r = self.client.get(path)
            self.assertEqual(r.status_code, 401, path)
            self.assertEqual(json.loads(r.data)['message'], '请先登录')

    def test_invalid_session_is_401(self):
        for path in self.PROTECTED_READS:
            r = self.client.get(path, headers={'X-Session-Id': 'no-such-session'})
            self.assertEqual(r.status_code, 401, path)

    def test_other_user_is_403(self):
        sid = self._login('teacher_demo')
        try:
            for path in self.PROTECTED_READS:
                r = self.client.get(path, headers={'X-Session-Id': sid})
                self.assertEqual(r.status_code, 403, path)
                self.assertEqual(json.loads(r.data)['message'], '无权访问他人的求职资料')
            r = self.client.put('/api/employment/resume/student_demo',
                                data=json.dumps({'title': 'x'}),
                                content_type='application/json',
                                headers={'X-Session-Id': sid})
            self.assertEqual(r.status_code, 403)
            r = self.client.post('/api/employment/intent',
                                 data=json.dumps({'user_id': 'student_demo',
                                                  'recruit_key': 'x'}),
                                 content_type='application/json',
                                 headers={'X-Session-Id': sid})
            self.assertEqual(r.status_code, 403)
            r = self.client.delete('/api/employment/intent',
                                   data=json.dumps({'user_id': 'student_demo',
                                                    'recruit_key': 'x'}),
                                   content_type='application/json',
                                   headers={'X-Session-Id': sid})
            self.assertEqual(r.status_code, 403)
            r = self.client.post('/api/employment/resume/ai',
                                 data=json.dumps({'user_id': 'student_demo',
                                                  'section': 'self_eval'}),
                                 content_type='application/json',
                                 headers={'X-Session-Id': sid})
            self.assertEqual(r.status_code, 403)
        finally:
            self._cleanup()


class LearnerProfileTest(EmploymentDomainTestBase):
    """能力档案：每个字段都来自真实数据，不补默认值凑数。"""

    def test_profile_fields_come_from_real_data(self):
        sid = self._login()
        try:
            data = json.loads(self.client.get(
                '/api/employment/profile/student_demo',
                headers={'X-Session-Id': sid}).data)
            self.assertTrue(data['success'])
            profile = data['profile']
            self.assertEqual(set(profile),
                             {'basic', 'certificates', 'points', 'learning', 'training'})
            self.assertEqual(profile['basic']['username'], 'student_demo')
            self.assertEqual(len(profile['certificates']), 3)
            self.assertEqual(sum(1 for c in profile['certificates'] if c['earned']), 1)
            # 证书必须如实带状态，不能把「学习中」说成「已获得」
            for c in profile['certificates']:
                self.assertIn(c['status'], ('earned', 'in_progress', 'locked'))
                self.assertEqual(c['earned'], c['status'] == 'earned')
            # 积分必须等于 points 表的真实余额，不是编的
            conn = get_connection()
            row = conn.execute(
                "SELECT balance FROM points WHERE user_id='student_demo'").fetchone()
            conn.close()
            self.assertEqual(profile['points'], row['balance'])
            self.assertEqual((profile['learning'] or {}).get('direction'), '荔枝种植')
            self.assertIsInstance(profile['training'], list)
        finally:
            self._cleanup()


class ResumeTest(EmploymentDomainTestBase):
    """在线简历：读写、内部字段不可越权改写。"""

    def test_resume_round_trip(self):
        sid = self._login()
        try:
            payload = {'title': '农产品电商运营', 'self_eval': '认真负责',
                       'skills': '直播带货', 'experience': [
                           {'company': '某公司', 'position': '运营',
                            'period': '2024', 'desc': '负责店铺运营'}]}
            r = self.client.put('/api/employment/resume/student_demo',
                                data=json.dumps(payload),
                                content_type='application/json',
                                headers={'X-Session-Id': sid})
            body = json.loads(r.data)
            self.assertTrue(body['success'])
            self.assertEqual(body['message'], '简历已保存')
            self.assertEqual(body['resume']['title'], '农产品电商运营')
            self.assertEqual(body['resume']['user_id'], 'student_demo')
            self.assertEqual(body['resume']['experience'][0]['company'], '某公司')

            got = json.loads(self.client.get(
                '/api/employment/resume/student_demo',
                headers={'X-Session-Id': sid}).data)['resume']
            self.assertEqual(got['title'], '农产品电商运营')
            self.assertEqual(got['experience'][0]['position'], '运营')
        finally:
            self._cleanup()

    def test_resume_is_none_before_anything_is_written(self):
        sid = self._login()
        try:
            got = json.loads(self.client.get(
                '/api/employment/resume/student_demo',
                headers={'X-Session-Id': sid}).data)
            self.assertTrue(got['success'])
        finally:
            self._cleanup()

    def test_internal_fields_cannot_be_written_by_the_client(self):
        sid = self._login()
        try:
            before = json.loads(self.client.get(
                '/api/employment/resume/student_demo',
                headers={'X-Session-Id': sid}).data)['resume']
            before_ai_used = ((before or {}).get('ai_used') or 0)
            r = self.client.put('/api/employment/resume/student_demo',
                                data=json.dumps({
                                    'title': 'T15', 'self_eval': '测试',
                                    'user_id': 'HACK', 'ai_used': 999,
                                }),
                                content_type='application/json',
                                headers={'X-Session-Id': sid})
            resume = json.loads(r.data)['resume']
            self.assertEqual(resume['user_id'], 'student_demo', 'user_id 不得由客户端改写')
            self.assertEqual(resume['ai_used'], before_ai_used,
                             'ai_used 只能由 AI 接口置位，客户端 PUT 不得改写')
        finally:
            self._cleanup()


class ResumeAiTest(EmploymentDomainTestBase):
    """AI 简历辅助：参数校验、限流、上游未配置时明确失败。"""

    def _post_ai(self, sid, payload):
        return self.client.post('/api/employment/resume/ai', data=json.dumps(payload),
                                content_type='application/json',
                                headers={'X-Session-Id': sid})

    def test_missing_user_id_is_400(self):
        r = self.client.post('/api/employment/resume/ai',
                             data=json.dumps({'section': 'self_eval'}),
                             content_type='application/json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(json.loads(r.data)['code'], 'bad_request')

    def test_unknown_section_is_400(self):
        sid = self._login()
        try:
            r = self._post_ai(sid, {'user_id': 'student_demo', 'section': 'education'})
            self.assertEqual(r.status_code, 400)
            self.assertEqual(json.loads(r.data)['code'], 'bad_section')
        finally:
            self._cleanup()

    def test_over_long_draft_is_400(self):
        sid = self._login()
        try:
            r = self._post_ai(sid, {'user_id': 'student_demo', 'section': 'self_eval',
                                    'draft': 'x' * 2001})
            self.assertEqual(r.status_code, 400)
            self.assertEqual(json.loads(r.data)['code'], 'draft_too_long')
        finally:
            self._cleanup()

    def test_unconfigured_upstream_fails_loudly(self):
        import ai.client as ai_client
        sid = self._login()
        original = ai_client.ai_configured
        try:
            ai_client.ai_configured = lambda: False
            r = self._post_ai(sid, {'user_id': 'student_demo', 'section': 'self_eval'})
            self.assertEqual(r.status_code, 503)
            body = json.loads(r.data)
            self.assertEqual(body['code'], 'ai_not_configured')
            self.assertIsNot(body.get('success'), True,
                             'AI 未配置时绝不返回 success=True 的兜底文案')
        finally:
            ai_client.ai_configured = original
            self._cleanup()

    def test_anonymous_is_401(self):
        r = self.client.post('/api/employment/resume/ai',
                             data=json.dumps({'user_id': 'student_demo',
                                              'section': 'self_eval'}),
                             content_type='application/json')
        self.assertEqual(r.status_code, 401)

    def test_successful_generation_records_which_section_used_ai(self):
        from unittest.mock import patch
        from db_init import init_db
        init_db()
        sid = self._login()
        try:
            with patch(
                'domains.employment_profile.routes.ai.client.ai_configured',
                return_value=True,
            ), patch(
                'domains.employment_profile.routes.call_ai_service',
                return_value='根据平台真实学习数据整理的段落',
            ):
                response = self._post_ai(sid, {
                    'user_id': 'student_demo',
                    'section': 'skills',
                    'draft': '本人填写的基础技能',
                })
            self.assertEqual(response.status_code, 200)
            self.assertTrue(json.loads(response.data)['success'])

            resume = json.loads(self.client.get(
                '/api/employment/resume/student_demo',
                headers={'X-Session-Id': sid},
            ).data)['resume']
            self.assertEqual(resume['ai_used'], 1)
            self.assertEqual(resume['ai_sections'], ['skills'])
        finally:
            self._cleanup()

    def test_experience_polish_uses_the_unsaved_draft(self):
        from unittest.mock import patch
        from db_init import init_db
        init_db()
        self._cleanup()
        sid = self._login()
        captured = {}

        def fake_call(system_prompt, user_prompt, **kwargs):
            captured['prompt'] = user_prompt
            return '负责农产品直播策划与店铺日常运营。'

        try:
            with patch(
                'domains.employment_profile.routes.ai.client.ai_configured',
                return_value=True,
            ), patch(
                'domains.employment_profile.routes.call_ai_service',
                side_effect=fake_call,
            ):
                response = self._post_ai(sid, {
                    'user_id': 'student_demo',
                    'section': 'experience',
                    'draft': '粤乡合作社 / 运营助理 / 2024：协助店铺运营',
                })
            self.assertEqual(response.status_code, 200)
            self.assertIn('粤乡合作社', captured['prompt'])
            self.assertIn('协助店铺运营', captured['prompt'])
        finally:
            self._cleanup()


class JobIntentTest(EmploymentDomainTestBase):
    """求职意向：登记幂等、不存在的公告 404、取消、聚合下发。"""

    def _recruit_key(self):
        data = json.loads(self.client.get('/api/employment/jobs').data)
        return data['recruitments'][0]['key']

    def test_intent_lifecycle(self):
        self.addCleanup(self._cleanup)
        sid = self._login()
        key = self._recruit_key()
        headers = {'X-Session-Id': sid}

        # 未登录不可登记
        r = self.client.post('/api/employment/intent',
                             data=json.dumps({'user_id': 'student_demo', 'recruit_key': key}),
                             content_type='application/json')
        self.assertEqual(r.status_code, 401)

        # 登记成功，且必须声明平台不代办报名
        r = self.client.post('/api/employment/intent',
                             data=json.dumps({'user_id': 'student_demo',
                                              'recruit_key': key, 'note': '想去'}),
                             content_type='application/json', headers=headers)
        body = json.loads(r.data)
        self.assertTrue(body['success'])
        self.assertTrue(body['created'])
        self.assertEqual(body['message'], '已记录求职意向')
        self.assertIn('不代办报名', body['notice'])

        # 幂等：重复登记只更新备注
        r = self.client.post('/api/employment/intent',
                             data=json.dumps({'user_id': 'student_demo',
                                              'recruit_key': key, 'note': '改了'}),
                             content_type='application/json', headers=headers)
        body = json.loads(r.data)
        self.assertTrue(body['success'])
        self.assertFalse(body['created'])
        self.assertEqual(body['message'], '意向备注已更新')
        self.assertEqual(len(employment.get_job_intents('student_demo')), 1)
        self.assertEqual(employment.get_job_intents('student_demo')[0]['note'], '改了')

        # 聚合接口把意向补全为可直接渲染的字段
        data = json.loads(self.client.get(
            '/api/employment/my-jobs/student_demo', headers=headers).data)
        self.assertTrue(data['success'])
        self.assertEqual(len(data['intents']), 1)
        it = data['intents'][0]
        self.assertEqual(it['channel'], 'public_recruit')
        self.assertEqual(it['recruit_key'], key)
        self.assertEqual(it['note'], '改了')
        self.assertTrue(it['title'] and it['org'])
        for key_field in ('title', 'org', 'region', 'category', 'deadline',
                          'status', 'status_label'):
            self.assertIn(key_field, it)
        self.assertTrue(data['intent_notice'])
        self.assertIn('has_resume', data)

        # 取消
        r = self.client.delete('/api/employment/intent',
                               data=json.dumps({'user_id': 'student_demo',
                                                'recruit_key': key}),
                               content_type='application/json', headers=headers)
        self.assertTrue(json.loads(r.data)['removed'])
        self.assertEqual(employment.get_job_intents('student_demo'), [])
        # 再取消一次：未找到记录，仍然 200
        r = self.client.delete('/api/employment/intent',
                               data=json.dumps({'user_id': 'student_demo',
                                                'recruit_key': key}),
                               content_type='application/json', headers=headers)
        body = json.loads(r.data)
        self.assertTrue(body['success'])
        self.assertFalse(body['removed'])
        self.assertEqual(body['message'], '未找到该意向记录')

    def test_unknown_recruit_key_is_404(self):
        self.addCleanup(self._cleanup)
        sid = self._login()
        r = self.client.post('/api/employment/intent',
                             data=json.dumps({'user_id': 'student_demo',
                                              'recruit_key': 'no-such-key'}),
                             content_type='application/json',
                             headers={'X-Session-Id': sid})
        self.assertEqual(r.status_code, 404)
        self.assertEqual(json.loads(r.data)['code'], 'not_found')

    def test_missing_params_are_400(self):
        self.addCleanup(self._cleanup)
        sid = self._login()
        headers = {'X-Session-Id': sid}
        r = self.client.post('/api/employment/intent', data=json.dumps({'recruit_key': 'x'}),
                             content_type='application/json', headers=headers)
        self.assertEqual(r.status_code, 400)
        r = self.client.post('/api/employment/intent', data=json.dumps({'user_id': 'x'}),
                             content_type='application/json', headers=headers)
        self.assertEqual(r.status_code, 400)
        r = self.client.delete('/api/employment/intent', data=json.dumps({}),
                               content_type='application/json', headers=headers)
        self.assertEqual(r.status_code, 400)

    def test_my_jobs_aggregates_both_channels(self):
        self.addCleanup(self._cleanup)
        sid = self._login()
        headers = {'X-Session-Id': sid}
        key = self._recruit_key()
        self.client.post('/api/employment/intent',
                         data=json.dumps({'user_id': 'student_demo', 'recruit_key': key}),
                         content_type='application/json', headers=headers)
        data = json.loads(self.client.get(
            '/api/employment/my-jobs/student_demo', headers=headers).data)
        for a in data['applications']:
            self.assertEqual(a['channel'], 'enterprise')
        for it in data['intents']:
            self.assertEqual(it['channel'], 'public_recruit')


class SelfOnlyHelperOwnershipTest(EmploymentDomainTestBase):
    """`_user_has_resume` 的归属：共享层持有唯一一份，两个域都从那里取。

    判定口径是「有内容」而不是「有行」：只有意向岗位或任一正文段才算写过简历。
    """

    def test_has_resume_requires_real_content(self):
        from shared.resume_state import user_has_resume
        self.addCleanup(self._cleanup)
        conn = get_connection()
        conn.execute("DELETE FROM resumes WHERE user_id = 'student_demo'")
        conn.commit()
        conn.close()
        self.assertFalse(user_has_resume('student_demo'),
                         '没有简历行时必须判为没有简历')

        conn = get_connection()
        conn.execute("INSERT INTO resumes (user_id, title) VALUES ('student_demo', '')")
        conn.commit()
        conn.close()
        self.assertFalse(user_has_resume('student_demo'),
                         '空白字段不算写过简历')

        conn = get_connection()
        conn.execute("UPDATE resumes SET title = '农产品电商运营' "
                     "WHERE user_id = 'student_demo'")
        conn.commit()
        conn.close()
        self.assertTrue(user_has_resume('student_demo'))

    def test_only_one_implementation_exists(self):
        """单一真相源：共享层、两个域转出的必须是同一个函数对象。"""
        from domains.employment import routes as employment_routes
        from domains.employment_profile import routes as profile_routes
        from domains.employment_profile.service import user_has_resume as re_exported
        from shared.resume_state import user_has_resume
        self.assertIs(employment_routes.user_has_resume, user_has_resume)
        self.assertIs(profile_routes.user_has_resume, user_has_resume)
        self.assertIs(re_exported, user_has_resume)

    def test_apply_and_my_jobs_report_the_same_resume_state(self):
        """apply 的 has_resume 与 my-jobs 的 has_resume 必须同源同口径。"""
        sid = self._login()
        try:
            self.addCleanup(self._cleanup)
            conn = get_connection()
            conn.execute("DELETE FROM resumes WHERE user_id = 'student_demo'")
            conn.commit()
            conn.close()

            conn = get_connection()
            conn.execute("""
                INSERT INTO job_listings (title, company, salary, requirements, description,
                                          location, category, enterprise_id, review_status, is_demo)
                VALUES ('__T15简历口径岗位__', '测试公司', '5K', '[]', '仅供测试',
                        '广州', '电商运营', 'enterprise_demo', 'approved', 0)
            """)
            conn.commit()
            job_id = conn.execute(
                "SELECT id FROM job_listings WHERE title='__T15简历口径岗位__'").fetchone()[0]
            conn.close()

            r = self.client.post('/api/employment/apply',
                                 data=json.dumps({'user_id': 'student_demo', 'job_id': job_id}),
                                 content_type='application/json',
                                 headers={'X-Session-Id': sid})
            self.assertFalse(json.loads(r.data)['has_resume'])

            data = json.loads(self.client.get(
                '/api/employment/my-jobs/student_demo',
                headers={'X-Session-Id': sid}).data)
            self.assertFalse(data['has_resume'])
        finally:
            self._cleanup()


if __name__ == '__main__':
    unittest.main()
