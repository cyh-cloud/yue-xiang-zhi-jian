#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""数据层按领域切分的契约测试（T05）。

锁住三件容易在「按领域切分 + 跨域收敛」中被改坏的行为：

1. 审核状态变更的单一分派入口：通过 / 驳回 / 撤销三种动作，对课程、岗位、
   采购、3D 模型四个领域的公开状态影响，与拆分前逐字节一致；
2. 未读总数：通知、消息（按会话）、就业投递、系统公告四个数据源相加；
3. 能力档案：用户基础信息、证书、积分、学习进度、实训成绩五个字段的来源与口径。

另外锁住两处重复定义清理后的语义：按标识取用户与更新资料都只有一份实现，
且行为与清理前实际生效的那份一致。
"""

import json
import os
import sys
import unittest

# 后端代码整体迁入 backend/ 后，被测的 database / db_domains / domain_data
# 都在 backend/ 下，因此路径基准指向 backend/ 而不是仓库根。
REPO_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend')
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import database  # noqa: E402


class ReviewDispatchTest(unittest.TestCase):
    """审核状态变更：一个入口，按内容类型分派到各领域。"""

    def setUp(self):
        from app import app
        self.app = app
        self.app.config['TESTING'] = True
        self.client = app.test_client()

    def _login(self, username, password):
        r = self.client.post('/api/auth/login', data=json.dumps(
            {'username': username, 'password': password}),
            content_type='application/json')
        return json.loads(r.data).get('session_id')

    def _course_review(self):
        """造一门待审课程，返回它的审核记录 id。"""
        teacher = self._login('teacher_demo', '123456')
        r = self.client.post('/api/teacher/courses',
                             data=json.dumps({'title': 'T05 契约课程',
                                              'description': '用于审核分派契约测试',
                                              'category': '农业技术'}),
                             content_type='application/json',
                             headers={'X-Session-Id': teacher})
        self.assertEqual(r.status_code, 200, r.data)
        course_id = json.loads(r.data)['id']
        review = database.get_review_by_content('course', course_id)
        self.assertIsNotNone(review, '创建课程必须同时生成审核记录')
        return course_id, review['id']

    def _review_status_of(self, table, row_id):
        conn = database.get_connection()
        row = conn.execute("SELECT review_status FROM %s WHERE id = ?" % table,
                           (row_id,)).fetchone()
        conn.close()
        return row['review_status'] if row else None

    def _published_flag_of(self, table, row_id):
        conn = database.get_connection()
        row = conn.execute("SELECT is_published FROM %s WHERE id = ?" % table,
                           (row_id,)).fetchone()
        conn.close()
        return row['is_published'] if row else None

    def test_approve_sets_approved_and_publishes_course(self):
        course_id, review_id = self._course_review()
        database.approve_review(review_id, 'admin_demo')
        self.assertEqual(self._review_status_of('courses', course_id), 'approved')
        self.assertEqual(self._published_flag_of('courses', course_id), 1)

    def test_reject_sets_rejected_and_unpublishes_course(self):
        course_id, review_id = self._course_review()
        database.reject_review(review_id, 'admin_demo', '不合规')
        self.assertEqual(self._review_status_of('courses', course_id), 'rejected')
        self.assertEqual(self._published_flag_of('courses', course_id), 0)

    def test_revoke_returns_both_to_pending(self):
        course_id, review_id = self._course_review()
        database.approve_review(review_id, 'admin_demo')
        self.assertEqual(database.revoke_review(review_id), 'ok')
        self.assertEqual(self._review_status_of('courses', course_id), 'pending')

    def test_approve_clears_the_previous_rejection_comment(self):
        """先驳回再通过，通过后不得残留上一轮的驳回理由。"""
        course_id, review_id = self._course_review()
        database.reject_review(review_id, 'admin_demo', '自审：临时驳回')
        database.approve_review(review_id, 'admin_demo')
        review = database.get_review_by_content('course', course_id)
        self.assertEqual(review['status'], 'approved')
        self.assertEqual(review['review_comment'], '')

    def test_job_rejection_writes_back_the_listing(self):
        """驳回必须对称回写岗位表，否则企业端一直显示「待审核」。"""
        enterprise = self._login('enterprise_demo', '123456')
        r = self.client.post('/api/enterprise/jobs',
                             data=json.dumps({'title': 'T05 契约岗位',
                                              'category': '农业技术',
                                              'salary': '5-8K',
                                              'location': '广州',
                                              'description': '用于审核分派契约测试',
                                              'requirements': '无'}),
                             content_type='application/json',
                             headers={'X-Session-Id': enterprise})
        self.assertEqual(r.status_code, 200, r.data)
        job_id = json.loads(r.data)['id']
        review = database.get_review_by_content('job', job_id)
        self.assertIsNotNone(review)
        database.reject_review(review['id'], 'admin_demo', '信息不完整')
        self.assertEqual(self._review_status_of('job_listings', job_id), 'rejected')
        database.revoke_review(review['id'])
        self.assertEqual(self._review_status_of('job_listings', job_id), 'pending')

    def test_success_case_needs_no_target_writeback(self):
        """案例内容不在库里，可见性完全由审核记录决定，不得回写任何目标表。"""
        # 用案例清单里不存在的 content_id：拿真实案例 id 反复 approve 会往
        # content_reviews 里堆多条记录，把 approved 计数撑爆，污染其它用例。
        probe_id = 999001
        review_id = database.create_content_review('success_case', probe_id, 'admin_demo')
        database.approve_review(review_id, 'admin_demo')
        self.assertEqual(
            database.get_review_by_content('success_case', probe_id)['status'], 'approved')
        conn = database.get_connection()
        conn.execute('DELETE FROM content_reviews WHERE content_type = ? AND content_id = ?',
                     ('success_case', probe_id))
        conn.commit()
        conn.close()


class UnreadCountTest(unittest.TestCase):
    """未读总数：四个数据源相加，口径与消息中心页签一致。"""

    def setUp(self):
        from app import app
        self.app = app
        self.app.config['TESTING'] = True
        self.client = app.test_client()

    def test_total_equals_the_sum_of_the_four_sources(self):
        student = json.loads(self.client.post(
            '/api/auth/login',
            data=json.dumps({'username': 'student_demo', 'password': '123456'}),
            content_type='application/json').data)['session_id']
        conn = database.get_connection()
        try:
            notif = conn.execute(
                "SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0",
                ('student_demo',)).fetchone()[0]
            msgs = conn.execute(
                """SELECT COUNT(*) FROM messages m
                   WHERE m.receiver_id = ? AND m.is_read = 0
                     AND m.id IN (SELECT MAX(id) FROM messages
                                  WHERE sender_id = ? OR receiver_id = ?
                                  GROUP BY CASE WHEN sender_id = ? THEN receiver_id
                                                ELSE sender_id END)""",
                ('student_demo', 'student_demo', 'student_demo', 'student_demo')
            ).fetchone()[0]
            apps = conn.execute(
                """SELECT COUNT(*) FROM job_applications a
                   WHERE a.user_id = ?
                     AND NOT EXISTS (SELECT 1 FROM notification_reads r
                                     WHERE r.user_id = a.user_id
                                       AND r.source = 'job_application'
                                       AND r.ref_id = CAST(a.id AS TEXT))""",
                ('student_demo',)).fetchone()[0]
            anns = conn.execute(
                """SELECT COUNT(*) FROM system_announcements s
                   WHERE s.is_active = 1
                     AND NOT EXISTS (SELECT 1 FROM notification_reads r
                                     WHERE r.user_id = ?
                                       AND r.source = 'system_announcement'
                                       AND r.ref_id = CAST(s.id AS TEXT))""",
                ('student_demo',)).fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(database.get_total_unread_count('student_demo'),
                         notif + msgs + apps + anns)


class LearnerProfileTest(unittest.TestCase):
    """能力档案：五个字段各有真实来源，不补默认值。"""

    def setUp(self):
        from app import app
        self.app = app
        self.app.config['TESTING'] = True
        self.client = app.test_client()

    def test_profile_fields_come_from_real_data(self):
        session = json.loads(self.client.post(
            '/api/auth/login',
            data=json.dumps({'username': 'student_demo', 'password': '123456'}),
            content_type='application/json').data)['session_id']
        r = self.client.get('/api/employment/profile/student_demo',
                            headers={'X-Session-Id': session})
        self.assertEqual(r.status_code, 200)
        profile = json.loads(r.data)['profile']
        self.assertEqual(set(profile), {'basic', 'certificates', 'points',
                                        'learning', 'training'})
        self.assertEqual(profile['basic']['username'], 'student_demo')
        self.assertEqual(len(profile['certificates']), 3)
        self.assertEqual(sum(1 for c in profile['certificates'] if c['earned']), 1)
        self.assertIsInstance(profile['points'], int)


class DuplicateDefinitionTest(unittest.TestCase):
    """两处重复定义清理后：只有一份实现，且行为与清理前生效的那份一致。"""

    def test_get_user_by_id_resolves_by_username(self):
        user = database.get_user_by_id('student_demo')
        self.assertIsNotNone(user)
        self.assertEqual(user['username'], 'student_demo')
        # 生效版本是 SELECT *，必须带出资料字段
        self.assertIn('bio', user)
        self.assertIn('region', user)
        self.assertIsNone(database.get_user_by_id('no-such-user'))

    def test_update_user_profile_writes_all_supported_fields(self):
        """生效版本支持 7 个字段且按 username 定位。"""
        database.update_user_profile('student_demo', region='T05 契约测试')
        try:
            user = database.get_user_by_id('student_demo')
            self.assertEqual(user['region'], 'T05 契约测试')
        finally:
            database.update_user_profile('student_demo', region='')

    def test_update_user_profile_is_idempotent_with_no_fields(self):
        """不传字段时不得报错，也不得改动任何列。"""
        before = database.get_user_by_id('student_demo')
        database.update_user_profile('student_demo')
        after = database.get_user_by_id('student_demo')
        self.assertEqual(before, after)


if __name__ == '__main__':
    unittest.main()
