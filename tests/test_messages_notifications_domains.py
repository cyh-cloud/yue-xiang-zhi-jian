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
                ('teacher', 'teacher_demo', '123456')):
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
        import database
        conn = database.get_connection()
        row = conn.execute(
            "SELECT id, sender_id FROM messages WHERE content = ?",
            ('__T18 伪造发送者__',)).fetchone()
        conn.close()
        self.assertIsNotNone(row)
        self.assertEqual(row['sender_id'], 'student_demo',
                         '发送者必须是会话用户，不能由请求体伪造')
        conn = database.get_connection()
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
        import database
        conn = database.get_connection()
        unread = conn.execute(
            "SELECT COUNT(*) FROM messages WHERE sender_id = ? AND receiver_id = ? "
            "AND is_read = 0", ('teacher_demo', 'student_demo')).fetchone()[0]
        conn.execute('DELETE FROM messages WHERE content = ?', ('__T18 已读__',))
        conn.commit()
        conn.close()
        self.assertEqual(unread, 0, '打开会话后对方发来的消息应全部标已读')


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

    def test_total_unread_count_matches_the_four_sources(self):
        """未读总数 = 通知 + 私信会话 + 就业投递 + 系统公告，口径不得漂移。"""
        import database
        conn = database.get_connection()
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


if __name__ == '__main__':
    unittest.main()
