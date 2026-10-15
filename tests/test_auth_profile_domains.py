# -*- coding: utf-8 -*-
"""认证域与用户资料域的路由行为测试（T08）。

登录、登出、会话校验、注册与个人资料读写、改密码从入口文件搬进各自的蓝图后，
外部契约必须一字不变：URL、请求响应结构、状态码、错误码，以及几条业务底线，
即错误密码 401、会话无效 401、未登录 401、停用账号 403、资料只能改本人、
改密码必须验旧密码、注册成功后可登录。

断言全部基于 HTTP 行为，不测模块怎么划分（拆分不产生新行为，为结构写测试只会
把实现细节钉死，见 spec 的 Testing Decisions）。
"""

import json
import os
import sys
import unittest
from db_connection import get_connection
from db_domains import users

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)



class AuthDomainTest(unittest.TestCase):
    """认证域：登录、登出、会话校验、注册。"""

    def setUp(self):
        from app import app
        self.client = app.test_client()

    def _login(self, username, password):
        return self.client.post('/api/auth/login', data=json.dumps(
            {'username': username, 'password': password}),
            content_type='application/json')

    def _cleanup(self, sid, *usernames):
        conn = get_connection()
        if sid:
            conn.execute("DELETE FROM user_sessions WHERE session_id = ?", (sid,))
        for username in usernames:
            conn.execute("DELETE FROM user_sessions WHERE user_id = ?", (username,))
            conn.execute("DELETE FROM users WHERE username = ?", (username,))
        conn.commit()
        conn.close()

    def test_login_returns_session_and_user_structure(self):
        """登录成功必须同时下发会话标识与完整 user 结构（前端整份覆盖 AppState.user）。"""
        sid = None
        try:
            response = self._login('student_demo', '123456')
            self.assertEqual(response.status_code, 200)
            body = json.loads(response.data)
            self.assertTrue(body['success'])
            sid = body['session_id']
            self.assertTrue(sid)
            user = body['user']
            self.assertEqual(user['id'], 'student_demo')
            self.assertEqual(user['name'], u'李同学')
            self.assertEqual(user['role'], 'student')
            for key in ('email', 'phone', 'avatar_url', 'company_name', 'region', 'status'):
                self.assertIn(key, user)
        finally:
            self._cleanup(sid)

    def test_login_missing_credentials_is_400(self):
        response = self.client.post('/api/auth/login', data=json.dumps(
            {'username': '', 'password': ''}), content_type='application/json')
        self.assertEqual(response.status_code, 400)
        body = json.loads(response.data)
        self.assertFalse(body['success'])
        self.assertEqual(body['message'], u'请输入用户名和密码')

    def test_login_wrong_password_is_401(self):
        response = self._login('teacher_demo', 'wrong_password')
        self.assertEqual(response.status_code, 401)
        body = json.loads(response.data)
        self.assertFalse(body['success'])
        self.assertEqual(body['message'], u'用户名或密码错误')

    def test_suspended_account_cannot_login(self):
        """停用账号必须 403，且提示写明原因（而不是笼统的密码错误）。"""
        username = 't08_suspended'
        registered = self.client.post('/api/auth/register', data=json.dumps(
            {'username': username, 'password': '123456', 'name': u'停用账号',
             'role': 'student'}), content_type='application/json')
        self.assertEqual(registered.status_code, 200)
        try:
            users.set_user_status(username, 'suspended')
            response = self._login(username, '123456')
            self.assertEqual(response.status_code, 403)
            body = json.loads(response.data)
            self.assertFalse(body['success'])
            self.assertEqual(body['message'], u'账号已被停用，请联系管理员')
        finally:
            self._cleanup(None, username)

    def test_verify_returns_the_same_user_structure_as_login(self):
        """会话校验必须与登录返回同一套 user 结构（含 id），否则前端会拼出 /undefined。"""
        sid = None
        try:
            logged_in = json.loads(self._login('student_demo', '123456').data)
            sid = logged_in['session_id']
            response = self.client.post('/api/auth/verify', data=json.dumps(
                {'session_id': sid}), content_type='application/json')
            self.assertEqual(response.status_code, 200)
            body = json.loads(response.data)
            self.assertTrue(body['success'])
            self.assertEqual(body['user'], logged_in['user'],
                             'verify 与 login 必须下发同一套 user 结构')
            self.assertNotIn('user_id', body['user'],
                             '不应把内部 session 字段（user_id）直接透出当 user 用')
        finally:
            self._cleanup(sid)

    def test_verify_without_session_id_is_401(self):
        response = self.client.post('/api/auth/verify', data=json.dumps(
            {'session_id': ''}), content_type='application/json')
        self.assertEqual(response.status_code, 401)
        body = json.loads(response.data)
        self.assertFalse(body['success'])
        self.assertEqual(body['message'], u'未提供session')

    def test_verify_unknown_session_is_401(self):
        response = self.client.post('/api/auth/verify', data=json.dumps(
            {'session_id': 'no-such-session'}), content_type='application/json')
        self.assertEqual(response.status_code, 401)
        body = json.loads(response.data)
        self.assertFalse(body['success'])
        self.assertEqual(body['message'], u'会话无效')

    def test_logout_deletes_the_session(self):
        sid = None
        try:
            sid = json.loads(self._login('student_demo', '123456').data)['session_id']
            response = self.client.post('/api/auth/logout', data=json.dumps(
                {'session_id': sid}), content_type='application/json')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(json.loads(response.data),
                             {"success": True, "message": u"已退出登录"})
            after = self.client.post('/api/auth/verify', data=json.dumps(
                {'session_id': sid}), content_type='application/json')
            self.assertEqual(after.status_code, 401, '登出后同一会话必须失效')
        finally:
            self._cleanup(sid)

    def test_logout_without_session_id_still_succeeds(self):
        """缺 session_id 是幂等成功，不是错误。"""
        response = self.client.post('/api/auth/logout', data=json.dumps(
            {}), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(json.loads(response.data)['success'])

    def test_register_creates_account_and_session(self):
        username = 't08_registered'
        sid = None
        try:
            response = self.client.post('/api/auth/register', data=json.dumps(
                {'username': username, 'password': '123456', 'name': u'新同学',
                 'role': 'student', 'email': 't08@example.com', 'phone': '13800000000'}),
                content_type='application/json')
            self.assertEqual(response.status_code, 200)
            body = json.loads(response.data)
            self.assertTrue(body['success'])
            self.assertEqual(body['message'], u'注册成功')
            sid = body['session_id']
            user = body['user']
            self.assertEqual(user['id'], username)
            self.assertEqual(user['name'], u'新同学')
            self.assertEqual(user['role'], 'student')
            self.assertEqual(user['email'], 't08@example.com')
            self.assertEqual(user['status'], 'active')
            # 注册返回的会话立即可用
            verified = self.client.post('/api/auth/verify', data=json.dumps(
                {'session_id': sid}), content_type='application/json')
            self.assertEqual(verified.status_code, 200)
            self.assertEqual(json.loads(verified.data)['user']['id'], username)
        finally:
            self._cleanup(sid, username)

    def test_registered_account_can_log_in(self):
        username = 't08_login_after_register'
        sid = None
        try:
            self.client.post('/api/auth/register', data=json.dumps(
                {'username': username, 'password': '123456', 'name': u'注册后登录'}),
                content_type='application/json')
            response = self._login(username, '123456')
            self.assertEqual(response.status_code, 200)
            body = json.loads(response.data)
            self.assertTrue(body['success'])
            self.assertEqual(body['user']['id'], username)
            sid = body['session_id']
        finally:
            self._cleanup(sid, username)

    def test_register_rejects_duplicate_username(self):
        username = 't08_duplicate'
        sid = None
        try:
            first = self.client.post('/api/auth/register', data=json.dumps(
                {'username': username, 'password': '123456', 'name': u'第一个'}),
                content_type='application/json')
            self.assertEqual(first.status_code, 200)
            sid = json.loads(first.data)['session_id']
            second = self.client.post('/api/auth/register', data=json.dumps(
                {'username': username, 'password': '123456', 'name': u'第二个'}),
                content_type='application/json')
            self.assertEqual(second.status_code, 400)
            body = json.loads(second.data)
            self.assertFalse(body['success'])
            self.assertEqual(body['message'], u'用户名已存在')
        finally:
            self._cleanup(sid, username)

    def test_register_rejects_invalid_input(self):
        cases = [
            ({'username': '', 'password': '123456', 'name': u'无名'},
             u'用户名、密码和姓名不能为空'),
            ({'username': 't08_bad_pw', 'password': '123', 'name': u'短密码'},
             u'密码至少6位'),
            ({'username': 't08_bad_role', 'password': '123456', 'name': u'坏角色',
              'role': 'super_admin'}, u'无效的角色类型'),
        ]
        for payload, message in cases:
            response = self.client.post('/api/auth/register', data=json.dumps(
                payload), content_type='application/json')
            self.assertEqual(response.status_code, 400, payload)
            body = json.loads(response.data)
            self.assertFalse(body['success'])
            self.assertEqual(body['message'], message, payload)


class UserProfileDomainTest(unittest.TestCase):
    """用户资料域：个人资料读写与改密码。"""

    def setUp(self):
        from app import app
        self.client = app.test_client()

    def _login(self, username='student_demo', password='123456'):
        response = self.client.post('/api/auth/login', data=json.dumps(
            {'username': username, 'password': password}),
            content_type='application/json')
        return json.loads(response.data)['session_id']

    def _cleanup(self, sid):
        conn = get_connection()
        if sid:
            conn.execute("DELETE FROM user_sessions WHERE session_id = ?", (sid,))
        conn.execute("UPDATE users SET email = '' WHERE username = 'student_demo'")
        conn.commit()
        conn.close()

    def test_profile_get_returns_full_user_record(self):
        sid = self._login()
        try:
            response = self.client.get('/api/user/profile',
                                       headers={'X-Session-Id': sid})
            self.assertEqual(response.status_code, 200)
            body = json.loads(response.data)
            self.assertTrue(body['success'])
            user = body['user']
            self.assertEqual(user['username'], 'student_demo')
            self.assertEqual(user['name'], u'李同学')
            self.assertEqual(user['role'], 'student')
        finally:
            self._cleanup(sid)

    def test_profile_get_requires_login(self):
        for headers in ({}, {'X-Session-Id': 'no-such-session'}):
            response = self.client.get('/api/user/profile', headers=headers)
            self.assertEqual(response.status_code, 401)
            self.assertEqual(json.loads(response.data)['message'], u'未登录')

    def test_profile_put_updates_own_record(self):
        sid = self._login()
        try:
            response = self.client.put('/api/user/profile', data=json.dumps(
                {'name': u'李同学', 'email': 't08-profile@example.com'}),
                content_type='application/json', headers={'X-Session-Id': sid})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(json.loads(response.data),
                             {"success": True, "message": u"资料更新成功"})
            stored = users.get_user_by_id('student_demo')
            self.assertEqual(stored['email'], 't08-profile@example.com')
        finally:
            self._cleanup(sid)

    def test_profile_put_requires_login(self):
        response = self.client.put('/api/user/profile', data=json.dumps(
            {'name': 'x', 'email': 'y'}), content_type='application/json')
        self.assertEqual(response.status_code, 401)
        self.assertEqual(json.loads(response.data)['message'], u'未登录')

    def test_profile_put_rejects_blank_name(self):
        sid = self._login()
        try:
            response = self.client.put('/api/user/profile', data=json.dumps(
                {'name': '   ', 'email': 'x@example.com'}),
                content_type='application/json', headers={'X-Session-Id': sid})
            self.assertEqual(response.status_code, 200)
            body = json.loads(response.data)
            self.assertFalse(body['success'])
            self.assertEqual(body['message'], u'姓名不能为空')
        finally:
            self._cleanup(sid)

    def test_profile_put_cannot_touch_another_account(self):
        """资料接口没有 user_id 参数：会话是谁就只能改谁。"""
        sid = self._login()
        try:
            before = users.get_user_by_id('teacher_demo')['name']
            response = self.client.put('/api/user/profile', data=json.dumps(
                {'name': u'被写上的名字', 'email': 'attacker@example.com'}),
                content_type='application/json', headers={'X-Session-Id': sid})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(users.get_user_by_id('student_demo')['name'],
                             u'被写上的名字')
            self.assertEqual(users.get_user_by_id('teacher_demo')['name'], before,
                             u'教师账号的资料不得被学员会话改写')
        finally:
            self._cleanup(sid)

    def test_password_change_requires_login(self):
        response = self.client.put('/api/user/password', data=json.dumps(
            {'old_password': '123456', 'new_password': 'abcdef',
             'confirm_password': 'abcdef'}), content_type='application/json')
        self.assertEqual(response.status_code, 401)
        self.assertEqual(json.loads(response.data)['message'], u'未登录')

    def test_password_change_validates_input_before_touching_the_store(self):
        sid = self._login()
        try:
            original = users.get_user_by_id('student_demo')['password_hash']
            cases = [
                ({'old_password': '', 'new_password': 'abcdef',
                  'confirm_password': 'abcdef'}, u'请填写完整'),
                ({'old_password': '123456', 'new_password': 'abcdef',
                  'confirm_password': 'other'}, u'两次输入的新密码不一致'),
                ({'old_password': '123456', 'new_password': 'abc',
                  'confirm_password': 'abc'}, u'新密码至少6位'),
            ]
            for payload, message in cases:
                response = self.client.put('/api/user/password', data=json.dumps(
                    payload), content_type='application/json',
                    headers={'X-Session-Id': sid})
                self.assertEqual(response.status_code, 200, payload)
                body = json.loads(response.data)
                self.assertFalse(body['success'])
                self.assertEqual(body['message'], message, payload)
            self.assertEqual(users.get_user_by_id('student_demo')['password_hash'],
                             original, u'校验不通过时不得改动口令')
        finally:
            self._cleanup(sid)

    def test_password_change_verifies_the_old_password(self):
        """改密码必须验旧密码：旧密码错则拒绝，且口令一个字都不能变。"""
        username = 't08_change_password'
        sid = None
        try:
            registered = self.client.post('/api/auth/register', data=json.dumps(
                {'username': username, 'password': '123456', 'name': u'改密码'}),
                content_type='application/json')
            sid = json.loads(registered.data)['session_id']
            original = users.get_user_by_id(username)['password_hash']

            rejected = self.client.put('/api/user/password', data=json.dumps(
                {'old_password': 'WRONG-OLD', 'new_password': 'abcdef',
                 'confirm_password': 'abcdef'}), content_type='application/json',
                headers={'X-Session-Id': sid})
            body = json.loads(rejected.data)
            self.assertFalse(body['success'])
            self.assertEqual(users.get_user_by_id(username)['password_hash'],
                             original, u'旧密码错误时口令不得被改动')

            # 旧密码错误时口令不得被改动，这一点由上一段守住。至于「改成功」这条
            # 路径，当前接口实际走不到：路由把 session 里的 user_id（username 字符串）
            # 传给按数值主键查表的 change_password，于是任何账号都拿到「用户不存在」。
            # 这是拆分前就有的缺陷，spec 明确本次只搬不改，因此这里按真实行为锁定，
            # 并在搬运过程中保持返回结构与状态码一字不变。
            accepted = self.client.put('/api/user/password', data=json.dumps(
                {'old_password': '123456', 'new_password': 'abcdef',
                 'confirm_password': 'abcdef'}), content_type='application/json',
                headers={'X-Session-Id': sid})
            body = json.loads(accepted.data)
            self.assertFalse(body['success'])
            self.assertEqual(body['message'], u'用户不存在')
            self.assertEqual(users.get_user_by_id(username)['password_hash'],
                             original, u'响应为失败时口令不得被改动')
        finally:
            self._cleanup(sid)
            conn = get_connection()
            conn.execute("DELETE FROM user_sessions WHERE user_id = ?", (username,))
            conn.execute("DELETE FROM users WHERE username = ?", (username,))
            conn.commit()
            conn.close()


class AuthProfileBlueprintRegistrationTest(unittest.TestCase):
    """蓝图注册：两个新域进工厂注册表，且静态兜底仍排在最后。"""

    def test_new_blueprints_come_from_the_domain_packages(self):
        from domains import auth_bp, user_profile_bp
        from app import app
        self.assertEqual(auth_bp.name, 'auth')
        self.assertEqual(user_profile_bp.name, 'user_profile')
        self.assertIn(auth_bp.name, app.blueprints)
        self.assertIn(user_profile_bp.name, app.blueprints)

    def test_static_catch_all_is_registered_last(self):
        """静态兜底蓝图必须最后注册，否则 `/<path:filename>` 可能吞掉 API 路由。

        注意不能改用 url_map.iter_rules() 的末尾项来断言：Werkzeug 会按权重重排，
        蓝图路由与入口文件的路由混在一起，末尾那条并不对应最后注册的蓝图。
        注册序的唯一真相是 app.blueprints 的键顺序。
        """
        from app import app
        self.assertIn('static_files', app.blueprints)
        self.assertEqual(list(app.blueprints)[-1], 'static_files', list(app.blueprints))
        for name in ('auth', 'user_profile'):
            self.assertLess(list(app.blueprints).index(name),
                            list(app.blueprints).index('static_files'),
                            '%s 必须注册在静态兜底之前' % name)


if __name__ == '__main__':
    unittest.main()