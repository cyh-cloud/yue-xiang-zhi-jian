# -*- coding: utf-8 -*-
"""学员域：学号生成的并发安全性（内容落库 T16）。

学号原先由「取当前最大号 +1」算出：两个并发请求会算出同一个号，后写入的那个撞
students.id 主键，SQLite 抛 IntegrityError，冒到前端是 500。

测试面选 API 层（Flask test client）而不是直接调 add_student：要守住的对外事实是
「接口不 500、学号格式不变、每条都落库」，取号策略之后换成哪一种都不该让这条
用例变色（spec 的 Testing Decisions）。
"""

import json
import os
import re
import sys
import threading
import unittest

REPO_ROOT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend')
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import database  # noqa: E402

# 名册行的识别前缀。清理只删这个前缀的行，不碰库里任何既有数据。
NAME_PREFIX = '__RACE'
# 改动前后的学号形态：STU + 至少三位数字（STU999 之后是 STU1000，位数会变长）。
STUDENT_ID_RE = re.compile(r'^STU\d{3,}$')


class StudentIdTestBase(unittest.TestCase):
    """脚手架：登录、调创建接口、按前缀清理自己造出来的名册行。"""

    def setUp(self):
        from app import app
        self.app = app
        self.app.config['TESTING'] = True
        self.client = app.test_client()

    def _login(self, username='teacher_demo', password='123456'):
        r = self.client.post('/api/auth/login', data=json.dumps(
            {'username': username, 'password': password}),
            content_type='application/json')
        return json.loads(r.data).get('session_id')

    def _add_student(self, session_id, name, client=None):
        client = client or self.client
        return client.post(
            '/api/teacher/students/add',
            data=json.dumps({'name': name, 'class_name': '并发班', 'direction': '荔枝种植'}),
            content_type='application/json', headers={'X-Session-Id': session_id})

    def _cleanup(self):
        conn = database.get_connection()
        try:
            conn.execute("DELETE FROM students WHERE name LIKE ?", (NAME_PREFIX + '%',))
            conn.commit()
        finally:
            conn.close()

    def _max_numeric_suffix(self):
        conn = database.get_connection()
        try:
            return conn.execute(
                "SELECT MAX(CAST(SUBSTR(id, 4) AS INTEGER)) FROM students "
                "WHERE id GLOB 'STU[0-9]*'").fetchone()[0] or 0
        finally:
            conn.close()


class StudentIdRaceTest(StudentIdTestBase):
    """并发创建学员：不 500、不撞主键、学号格式不变、条数对得上。"""

    WORKERS = 8
    ROUNDS = 4

    def test_concurrent_add_student_never_conflicts(self):
        self.addCleanup(self._cleanup)
        session_id = self._login()
        barrier = threading.Barrier(self.WORKERS)
        outcomes = []
        lock = threading.Lock()

        def worker(index):
            # 每个线程一个 client：Flask 的 test_client 不保证跨线程共享安全。
            client = self.app.test_client()
            for attempt in range(self.ROUNDS):
                barrier.wait()
                response = self._add_student(
                    session_id, '%s%d_%d' % (NAME_PREFIX, index, attempt), client)
                body = json.loads(response.data)
                with lock:
                    outcomes.append((response.status_code, body.get('student_id'),
                                     body.get('message')))

        threads = [threading.Thread(target=worker, args=(i,))
                   for i in range(self.WORKERS)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        expected_count = self.WORKERS * self.ROUNDS
        self.assertEqual(len(outcomes), expected_count)
        failures = [o for o in outcomes if o[0] != 200]
        self.assertEqual(failures[:5], [],
                         '并发创建学员出现失败响应（含主键冲突导致的 500）')
        ids = [o[1] for o in outcomes]
        for sid in ids:
            self.assertIsNotNone(sid, '创建成功却没有返回学号')
            self.assertRegex(sid, STUDENT_ID_RE)
        self.assertEqual(len(set(ids)), len(ids), '并发下产生了重复学号：%r' % (ids,))

        conn = database.get_connection()
        try:
            stored = [r[0] for r in conn.execute(
                "SELECT id FROM students WHERE name LIKE ?", (NAME_PREFIX + '%',))]
        finally:
            conn.close()
        self.assertEqual(sorted(stored), sorted(ids),
                         '接口返回的学号与落库的学号不一致')


class StudentIdFormatTest(StudentIdTestBase):
    """学号形态与改动前一致：接着当前最大号往后排，不足三位左侧补零。"""

    def test_first_id_follows_the_current_maximum(self):
        self.addCleanup(self._cleanup)
        session_id = self._login()
        expected = 'STU%03d' % (self._max_numeric_suffix() + 1)
        response = self._add_student(session_id, NAME_PREFIX + '格式')
        self.assertEqual(response.status_code, 200)
        body = json.loads(response.data)
        self.assertTrue(body['success'])
        self.assertEqual(body['student_id'], expected)
        self.assertRegex(body['student_id'], STUDENT_ID_RE)

    def test_id_generation_skips_numbers_already_taken(self):
        """STU1000 在字符串序下小于 STU999，只按 ORDER BY id DESC 取号会取到已存在的号。

        这里预置 STU999 与 STU1000 两行（都是库里没有的号），断言新学号是 STU1001。
        这一条同时锁住「查重后取号」：没有查重就会取到 STU1000 并撞主键。
        """
        self.addCleanup(self._cleanup)
        session_id = self._login()
        conn = database.get_connection()
        try:
            conn.execute("INSERT INTO students (id, user_id, name, class_name, direction) "
                         "VALUES ('STU999', '', ?, '并发班', '荔枝种植')", (NAME_PREFIX + '预置999',))
            conn.execute("INSERT INTO students (id, user_id, name, class_name, direction) "
                         "VALUES ('STU1000', '', ?, '并发班', '荔枝种植')", (NAME_PREFIX + '预置1000',))
            conn.commit()
        finally:
            conn.close()

        response = self._add_student(session_id, NAME_PREFIX + '顺延')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.data)['student_id'], 'STU1001')


if __name__ == '__main__':
    unittest.main()
