# -*- coding: utf-8 -*-
"""复核有效期：后台超期筛选与公开页推算提示必须使用同一条 183 天规则。"""

import json
import os
import sys
import unittest
from datetime import datetime

BACKEND = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend')
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from db_connection import get_connection  # noqa: E402

OPERATOR = ('operator_demo', '123456')


class ReviewFreshnessTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app import app
        cls.app = app
        cls.app.config['TESTING'] = True

    def setUp(self):
        self.client = self.app.test_client()
        login = self.client.post(
            '/api/auth/login',
            data=json.dumps({'username': OPERATOR[0], 'password': OPERATOR[1]}),
            content_type='application/json',
        )
        self.session_id = json.loads(login.data)['session_id']
        self.headers = {'X-Session-Id': self.session_id}

    def tearDown(self):
        conn = get_connection()
        conn.execute("DELETE FROM user_sessions WHERE session_id = ?",
                     (self.session_id,))
        conn.commit()
        conn.close()

    def _post(self, path, payload):
        return self.client.post(
            path,
            data=json.dumps(payload),
            content_type='application/json',
            headers=self.headers,
        )

    def test_stale_verified_task_is_publicly_marked_as_inferred(self):
        now = datetime.now()
        task_id = None
        try:
            response = self._post('/api/operator/farming/tasks', {
                'product_id': 'lychee',
                'title': u'单测超期复核任务',
                'category': 'manage',
                'month': now.month,
                'task_md': '%02d-20' % now.month,
            })
            self.assertEqual(response.status_code, 200, response.data)
            task_id = json.loads(response.data)['result']
            conn = get_connection()
            conn.execute(
                "UPDATE farming_tasks SET is_verified = 1, verified_by = ?, "
                "verified_at = datetime('now', 'localtime', '-200 days') "
                "WHERE id = ?",
                ('operator_demo', task_id),
            )
            conn.commit()
            conn.close()

            public = self.client.get(
                '/api/agriculture/calendar/lychee',
                query_string={'year': now.year, 'month': now.month},
            )
            self.assertEqual(public.status_code, 200)
            task = next(
                item for item in json.loads(public.data)['tasks']
                if item['id'] == task_id
            )
            self.assertEqual(task['is_verified'], 0,
                             '超过 183 天的复核仍被公开页当成已验证')
            self.assertNotEqual(task['evidence_level'], 'verified')
        finally:
            if task_id is not None:
                conn = get_connection()
                conn.execute("DELETE FROM farming_tasks WHERE id = ?", (task_id,))
                conn.commit()
                conn.close()

    def test_stale_verified_pest_entry_is_publicly_marked_as_inferred(self):
        entry_id = 't20_stale_public'
        try:
            response = self._post('/api/operator/pest/entries', {
                'id': entry_id,
                'crop_id': 'lychee',
                'disease': u'单测超期复核病害',
                'kind': 'disease',
            })
            self.assertEqual(response.status_code, 200, response.data)
            conn = get_connection()
            conn.execute(
                "UPDATE pest_entries SET is_verified = 1, verified_by = ?, "
                "verified_at = datetime('now', 'localtime', '-200 days') "
                "WHERE id = ?",
                ('operator_demo', entry_id),
            )
            conn.commit()
            conn.close()

            public = self.client.get(
                '/api/agriculture/pest-knowledge',
                query_string={'crop': 'lychee'},
            )
            self.assertEqual(public.status_code, 200)
            entry = next(
                item for item in json.loads(public.data)['entries']
                if item['id'] == entry_id
            )
            self.assertEqual(entry['is_verified'], 0,
                             '超过 183 天的复核仍被公开页当成已验证')
        finally:
            conn = get_connection()
            conn.execute("DELETE FROM pest_entries WHERE id = ?", (entry_id,))
            conn.commit()
            conn.close()


if __name__ == '__main__':
    unittest.main()
