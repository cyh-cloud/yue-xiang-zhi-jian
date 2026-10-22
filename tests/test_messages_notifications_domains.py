#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""消息域与通知域的行为测试。

T09 搬公开域与社区域时漏掉了这两个区块，它们一直滞留在 app.py 直到 T18 前才补搬。
这些用例锁住搬迁时最容易搬错的两处：身份护栏（只能以本人身份读自己的数据）
与未读总数的四源口径。
"""

import json
import os
import sys
import unittest
from db_connection import get_connection
from db_domains.users import register_user

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


class _LoggedInBase(unittest.TestCase):
    def setUp(self):
        from app import app
        self.app = app
        self.app.config['TESTING'] = True
        self.client = app.test_client()
        self.sessions = {}
        for key, username, password in (
                ('student', 'student_demo', '123456'),
                ('teacher', 'teacher_demo', '123456'),
                ('enterprise', 'enterprise_demo', '123456'),
                ('government', 'gov_demo', '123456'),
                ('operator', 'operator_demo', '123456'),
                ('admin', 'admin_demo', 'admin123')):
            r = self.client.post('/api/auth/login', data=json.dumps(
                {'username': username, 'password': password}),
                content_type='application/json')
            self.sessions[key] = json.loads(r.data).get('session_id')

    def _headers(self, session_id):
        return {'X-Session-Id': session_id}


class MessagesGuardTest(_LoggedInBase):
    """消息接口的身份护栏：只能以本人身份读自己的私信。"""

    def test_inbox_requires_login(self):
        r = self.client.get('/api/messages/inbox?user_id=student_demo')
        self.assertEqual(r.status_code, 401)

    def test_inbox_rejects_other_users_id(self):
        """带合法会话但查别人的收件箱，必须 403（越权红线）。"""
        r = self.client.get('/api/messages/inbox?user_id=teacher_demo',
                            headers=self._headers(self.sessions['student']))
        self.assertEqual(r.status_code, 403)

    def test_send_rejects_forged_sender(self):
        """sender 一律取会话用户，请求体里的 sender_id 不得被采信。"""
        r = self.client.post('/api/messages/send', data=json.dumps(
            {'sender_id': 'teacher_demo', 'receiver_id': 'teacher_demo',
             'content': '__T18 伪造发送者__'}),
            content_type='application/json',
            headers=self._headers(self.sessions['student']))
        self.assertEqual(r.status_code, 200, r.data)
        conn = get_connection()
        row = conn.execute(
            "SELECT id, sender_id FROM messages WHERE content = ?",
            ('__T18 伪造发送者__',)).fetchone()
        conn.close()
        self.assertIsNotNone(row)
        self.assertEqual(row['sender_id'], 'student_demo',
                         '发送者必须是会话用户，不能由请求体伪造')
        conn = get_connection()
        conn.execute('DELETE FROM messages WHERE id = ?', (row['id'],))
        conn.commit()
        conn.close()

    def test_send_rejects_self_message(self):
        r = self.client.post('/api/messages/send', data=json.dumps(
            {'receiver_id': 'student_demo', 'content': 'x'}),
            content_type='application/json',
            headers=self._headers(self.sessions['student']))
        self.assertEqual(r.status_code, 400)

    def test_conversation_marks_the_other_side_read(self):
        """打开会话要把对方发来的消息标已读。"""
        self.client.post('/api/messages/send', data=json.dumps(
            {'receiver_id': 'student_demo', 'content': '__T18 已读__'}),
            content_type='application/json',
            headers=self._headers(self.sessions['teacher']))
        r = self.client.get(
            '/api/messages/conversation/teacher_demo?user_id=student_demo',
            headers=self._headers(self.sessions['student']))
        self.assertEqual(r.status_code, 200)
        conn = get_connection()
        unread = conn.execute(
            "SELECT COUNT(*) FROM messages WHERE sender_id = ? AND receiver_id = ? "
            "AND is_read = 0", ('teacher_demo', 'student_demo')).fetchone()[0]
        conn.execute('DELETE FROM messages WHERE content = ?', ('__T18 已读__',))
        conn.commit()
        conn.close()
        self.assertEqual(unread, 0, '打开会话后对方发来的消息应全部标已读')

    def test_recipient_boundaries_follow_teacher_and_enterprise_relationships(self):
        register_user('__t_msg_teacher', '123456', '隔离消息教师', 'teacher')
        register_user('__t_msg_student', '123456', '隔离消息学员', 'student')
        other_teacher = self.client.post(
            '/api/auth/login',
            data=json.dumps({
                'username': '__t_msg_teacher',
                'password': '123456',
            }),
            content_type='application/json',
        ).get_json()['session_id']
        other_student = self.client.post(
            '/api/auth/login',
            data=json.dumps({
                'username': '__t_msg_student',
                'password': '123456',
            }),
            content_type='application/json',
        ).get_json()['session_id']

        conn = get_connection()
        conn.execute(
            "INSERT INTO job_listings (title, company, salary, requirements, "
            "description, location, category, enterprise_id, review_status, is_demo) "
            "VALUES ('__T_MSG_JOB__', '演示企业', '5K', '[]', '消息边界', "
            "'广州', '电商运营', 'enterprise_demo', 'approved', 0)"
        )
        job_id = conn.execute(
            "SELECT id FROM job_listings WHERE title = '__T_MSG_JOB__'"
        ).fetchone()[0]
        conn.execute(
            "INSERT INTO job_applications (user_id, job_id) VALUES (?, ?)",
            ('student_demo', job_id),
        )
        conn.commit()
        conn.close()
        self.addCleanup(self._cleanup_message_boundary, job_id)

        def send(session_id, receiver_id):
            return self.client.post(
                '/api/messages/send',
                data=json.dumps({
                    'receiver_id': receiver_id,
                    'content': '__T_MSG_BOUNDARY__',
                }),
                content_type='application/json',
                headers=self._headers(session_id),
            )

        allowed = (
            (self.sessions['teacher'], 'student_demo'),
            (self.sessions['enterprise'], 'student_demo'),
            (self.sessions['student'], 'teacher_demo'),
            (self.sessions['student'], 'enterprise_demo'),
        )
        for session_id, receiver_id in allowed:
            with self.subTest(allowed=receiver_id):
                response = send(session_id, receiver_id)
                self.assertEqual(response.status_code, 200, response.data)
                self.assertTrue(response.get_json()['success'])

        denied = (
            (other_teacher, 'student_demo'),
            (other_student, 'teacher_demo'),
            (self.sessions['enterprise'], '__t_msg_student'),
            (self.sessions['government'], 'student_demo'),
            (self.sessions['operator'], 'student_demo'),
            (self.sessions['admin'], 'student_demo'),
        )
        for session_id, receiver_id in denied:
            with self.subTest(denied=receiver_id):
                response = send(session_id, receiver_id)
                self.assertEqual(response.status_code, 403, response.data)
                self.assertEqual(
                    response.get_json()['message'],
                    '无权向该用户发送消息',
                )

    def _cleanup_message_boundary(self, job_id):
        conn = get_connection()
        conn.execute(
            "DELETE FROM messages WHERE content = '__T_MSG_BOUNDARY__'"
        )
        conn.execute(
            "DELETE FROM job_applications WHERE job_id = ?", (job_id,)
        )
        conn.execute("DELETE FROM job_listings WHERE id = ?", (job_id,))
        conn.execute(
            "DELETE FROM user_sessions WHERE user_id IN "
            "('__t_msg_teacher', '__t_msg_student')"
        )
        conn.execute(
            "DELETE FROM users WHERE username IN "
            "('__t_msg_teacher', '__t_msg_student')"
        )
        conn.commit()
        conn.close()


class NotificationsGuardTest(_LoggedInBase):
    """通知接口同样只看本人，且未读总数是四个数据源相加。"""

    def test_notifications_require_login(self):
        r = self.client.get('/api/notifications?user_id=student_demo')
        self.assertEqual(r.status_code, 401)

    def test_notifications_reject_other_users_id(self):
        r = self.client.get('/api/notifications?user_id=teacher_demo',
                            headers=self._headers(self.sessions['student']))
        self.assertEqual(r.status_code, 403)

    def test_unread_count_requires_login(self):
        r = self.client.get('/api/notifications/unread?user_id=student_demo')
        self.assertEqual(r.status_code, 401)

    def test_read_state_rejects_other_users_id(self):
        r = self.client.get('/api/notifications/read-state?user_id=teacher_demo',
                            headers=self._headers(self.sessions['student']))
        self.assertEqual(r.status_code, 403)

    def test_notification_list_limit_keeps_more_than_the_legacy_twenty(self):
        """The message center asks for a bounded larger list so its badge and
        visible unread rows keep the same four-source count beyond 20 items."""
        from db_domains import notifications as notifications_db

        prefix = '__T44_LIMIT__'
        for index in range(21):
            notifications_db.create_notification(
                'student_demo', 'system', f'{prefix}{index}', '')
        try:
            r = self.client.get(
                '/api/notifications?user_id=student_demo&limit=200',
                headers=self._headers(self.sessions['student']))
            self.assertEqual(r.status_code, 200)
            titles = [n['title'] for n in json.loads(r.data)['notifications']]
            self.assertEqual(21, sum(t.startswith(prefix) for t in titles))
        finally:
            conn = get_connection()
            conn.execute(
                "DELETE FROM notifications WHERE user_id = ? AND title LIKE ?",
                ('student_demo', prefix + '%'))
            conn.commit()
            conn.close()

    def test_total_unread_count_matches_the_four_sources(self):
        """未读总数 = 通知 + 私信会话 + 就业投递 + 系统公告，口径不得漂移。"""
        conn = get_connection()
        notif = conn.execute(
            "SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0",
            ('student_demo',)).fetchone()[0]
        conn.close()
        from db_domains.announcements import count_unread_system_announcements
        from db_domains.employment import count_unread_job_applications
        from db_domains.messages import count_unread_conversations
        from db_domains.notifications import get_read_refs

        # 公告侧只数「还没被标已读」的，已读集合由通知域持有
        read = set(get_read_refs('student_demo', 'system_announcement'))

        expected = (notif
                    + count_unread_conversations('student_demo')
                    + count_unread_job_applications('student_demo')
                    + count_unread_system_announcements(read))
        r = self.client.get('/api/notifications/unread?user_id=student_demo',
                            headers=self._headers(self.sessions['student']))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(json.loads(r.data)['count'], expected)

    def test_clear_read_removes_all_four_sources_without_reopening_them(self):
        from db_domains import notifications as notifications_db

        prefix = '__T_CLEAR__'
        conn = get_connection()
        conn.execute(
            "INSERT INTO system_announcements (title, content, is_active) "
            "VALUES (?, ?, 1)",
            (prefix + '公告', '公告正文'),
        )
        announcement_id = str(conn.execute(
            "SELECT id FROM system_announcements WHERE title = ?",
            (prefix + '公告',),
        ).fetchone()[0])
        conn.execute(
            "INSERT INTO job_listings (title, company, salary, requirements, "
            "description, location, category, enterprise_id, review_status, is_demo) "
            "VALUES (?, '演示企业', '5K', '[]', '清空测试', '广州', "
            "'电商运营', 'enterprise_demo', 'approved', 0)",
            (prefix + '岗位',),
        )
        job_id = conn.execute(
            "SELECT id FROM job_listings WHERE title = ?",
            (prefix + '岗位',),
        ).fetchone()[0]
        conn.execute(
            "INSERT INTO job_applications (user_id, job_id) VALUES (?, ?)",
            ('student_demo', job_id),
        )
        application_id = str(conn.execute(
            "SELECT id FROM job_applications WHERE job_id = ?", (job_id,)
        ).fetchone()[0])
        conn.commit()
        conn.close()

        notifications_db.create_notification(
            'student_demo', 'system', prefix + '通知', '通知正文'
        )
        self.client.post(
            '/api/messages/send',
            data=json.dumps({
                'receiver_id': 'student_demo',
                'content': prefix + '私信',
            }),
            content_type='application/json',
            headers=self._headers(self.sessions['teacher']),
        )
        self.addCleanup(
            self._cleanup_clear_read,
            job_id,
            announcement_id,
            application_id,
        )

        read_all = self.client.post(
            '/api/notifications/read',
            data=json.dumps({'user_id': 'student_demo'}),
            content_type='application/json',
            headers=self._headers(self.sessions['student']),
        )
        self.assertEqual(read_all.status_code, 200)
        self.client.get(
            '/api/messages/conversation/teacher_demo?user_id=student_demo',
            headers=self._headers(self.sessions['student']),
        )

        state_before = self.client.get(
            '/api/notifications/read-state?user_id=student_demo',
            headers=self._headers(self.sessions['student']),
        ).get_json()
        self.assertIn(announcement_id, state_before['refs']['system_announcement'])
        self.assertIn(application_id, state_before['refs']['job_application'])

        cleared = self.client.delete(
            '/api/notifications/clear?user_id=student_demo',
            headers=self._headers(self.sessions['student']),
        )
        self.assertEqual(cleared.status_code, 200)

        state_after = self.client.get(
            '/api/notifications/read-state?user_id=student_demo',
            headers=self._headers(self.sessions['student']),
        ).get_json()
        self.assertNotIn(
            announcement_id, state_after['refs']['system_announcement']
        )
        self.assertNotIn(application_id, state_after['refs']['job_application'])
        self.assertIn(
            announcement_id, state_after['dismissed']['system_announcement']
        )
        self.assertIn(
            application_id, state_after['dismissed']['job_application']
        )

        notifications = self.client.get(
            '/api/notifications?user_id=student_demo&limit=200',
            headers=self._headers(self.sessions['student']),
        ).get_json()['notifications']
        self.assertFalse(any(
            item['title'] == prefix + '通知' for item in notifications
        ))
        inbox = self.client.get(
            '/api/messages/inbox?user_id=student_demo',
            headers=self._headers(self.sessions['student']),
        ).get_json()['inbox']
        self.assertFalse(any(
            item['content'] == prefix + '私信' for item in inbox
        ))

        unread = self.client.get(
            '/api/notifications/unread?user_id=student_demo',
            headers=self._headers(self.sessions['student']),
        ).get_json()['count']
        self.assertEqual(unread, 0)

        again = self.client.delete(
            '/api/notifications/clear?user_id=student_demo',
            headers=self._headers(self.sessions['student']),
        )
        self.assertEqual(again.status_code, 200)
        still_zero = self.client.get(
            '/api/notifications/unread?user_id=student_demo',
            headers=self._headers(self.sessions['student']),
        ).get_json()['count']
        self.assertEqual(still_zero, 0)

        read_again = self.client.post(
            '/api/notifications/read',
            data=json.dumps({'user_id': 'student_demo'}),
            content_type='application/json',
            headers=self._headers(self.sessions['student']),
        )
        self.assertEqual(read_again.status_code, 200)
        state_after_read_again = self.client.get(
            '/api/notifications/read-state?user_id=student_demo',
            headers=self._headers(self.sessions['student']),
        ).get_json()
        self.assertNotIn(
            announcement_id,
            state_after_read_again['refs']['system_announcement'],
        )
        self.assertNotIn(
            application_id,
            state_after_read_again['refs']['job_application'],
        )
        self.assertIn(
            announcement_id,
            state_after_read_again['dismissed']['system_announcement'],
        )
        self.assertIn(
            application_id,
            state_after_read_again['dismissed']['job_application'],
        )

    def _cleanup_clear_read(self, job_id, announcement_id, application_id):
        conn = get_connection()
        conn.execute(
            "DELETE FROM messages WHERE content = '__T_CLEAR__私信'"
        )
        conn.execute(
            "DELETE FROM notifications WHERE title = '__T_CLEAR__通知'"
        )
        conn.execute(
            "DELETE FROM notification_reads WHERE user_id = 'student_demo' "
            "AND ((source = 'system_announcement' AND ref_id = ?) "
            "OR (source = 'job_application' AND ref_id = ?))",
            (announcement_id, application_id),
        )
        conn.execute(
            "DELETE FROM job_applications WHERE id = ?", (application_id,)
        )
        conn.execute("DELETE FROM job_listings WHERE id = ?", (job_id,))
        conn.execute(
            "DELETE FROM system_announcements WHERE id = ?",
            (announcement_id,),
        )
        conn.commit()
        conn.close()


if __name__ == '__main__':
    unittest.main()
