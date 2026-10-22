# -*- coding: utf-8 -*-
"""能力矩阵：每个能力 × 每个角色，用 Flask test client 打真实接口。

spec 的 Testing Decisions 把测试面定在 API 层。这里守住的对外事实是：
某个角色打某个接口，拿到的状态码与它是否持有该能力一致。表驱动，
新增能力或角色时只改下面两张表。

T13 落地 operator 角色后，operator 会作为第六个角色自动进入矩阵。
"""
import json
import os
import sys
import unittest

REPO_ROOT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend')
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

# 演示账号：口令与 db_seed_accounts 一致
ACCOUNTS = {
    'student': ('student_demo', '123456'),
    'teacher': ('teacher_demo', '123456'),
    'enterprise': ('enterprise_demo', '123456'),
    'government': ('gov_demo', '123456'),
    'super_admin': ('admin_demo', 'admin123'),
}

# 能力 -> 打哪个接口。只挑每个域一条最便宜的 GET。
# 只收录有安全 GET 探针的能力。course.manage 只出现在 POST/PUT/DELETE 上
# （GET /api/teacher/courses 走的是 course.read），打它会写数据，所以它不进 HTTP 矩阵，
# 由 test_course_capability_split_preserves_current_behaviour 直接覆盖。
PROBES = {
    'user.manage': ('/api/admin/users', 'GET'),
    'review.moderate': ('/api/admin/reviews', 'GET'),
    'policy.manage': ('/api/government/policies', 'GET'),
    'job.manage': ('/api/enterprise/jobs', 'GET'),
    'course.read': ('/api/teacher/courses', 'GET'),
    'announcement.manage': ('/api/admin/system-announcements', 'GET'),
}

# 未登录一律 403（域内联守卫的历史行为，本票据承诺逐字保留）
ANONYMOUS_STATUS = 403


class PermissionMatrixTest(unittest.TestCase):
    """逐角色逐能力打接口，断言状态码与能力表一致。"""

    @classmethod
    def setUpClass(cls):
        from app import app
        cls.app = app
        cls.app.config['TESTING'] = True

    def setUp(self):
        self.client = self.app.test_client()

    def _session(self, role):
        username, password = ACCOUNTS[role]
        r = self.client.post('/api/auth/login',
                             data=json.dumps({'username': username,
                                              'password': password,
                                              'role': role}),
                             content_type='application/json')
        body = json.loads(r.data)
        self.assertTrue(body.get('success'), '登录失败：%s' % body)
        return body['session_id']

    def test_anonymous_is_rejected_everywhere(self):
        """未登录打管理接口，全部 403（与改动前的内联守卫一致）。"""
        for capability, (path, method) in PROBES.items():
            with self.subTest(capability=capability):
                r = self.client.open(path, method=method)
                self.assertEqual(r.status_code, ANONYMOUS_STATUS,
                                 '%s 未登录应得 %d，实得 %d'
                                 % (path, ANONYMOUS_STATUS, r.status_code))

    def test_capability_holders_get_through(self):
        """持有能力的角色不被能力判定拦下（可能是 200，也可能是业务上的空结果）。"""
        from core.permissions import can
        for capability, (path, method) in PROBES.items():
            for role in ACCOUNTS:
                if not can(role, capability):
                    continue
                with self.subTest(capability=capability, role=role):
                    session_id = self._session(role)
                    r = self.client.open(path, method=method,
                                         headers={'X-Session-Id': session_id})
                    self.assertNotEqual(r.status_code, 403,
                                        '%s 持 %s 却拿到 403' % (role, capability))

    def test_non_holders_are_rejected(self):
        """不持有能力的角色一律 403。"""
        from core.permissions import can
        for capability, (path, method) in PROBES.items():
            for role in ACCOUNTS:
                if can(role, capability):
                    continue
                with self.subTest(capability=capability, role=role):
                    session_id = self._session(role)
                    r = self.client.open(path, method=method,
                                         headers={'X-Session-Id': session_id})
                    self.assertEqual(r.status_code, 403,
                                     '%s 不持 %s 却拿到 %d'
                                     % (role, capability, r.status_code))

    def test_operator_is_not_in_user_or_review_capability(self):
        """operator 是 super_admin 的子集：用户管理与内容审核显式不含它。

        T13 才会把 operator 变成真实角色，这里先锁住能力表的边界，
        让「加角色时不小心把 operator 加进 user.manage」立刻红灯。
        """
        from core.permissions import can
        for capability in ('user.manage', 'review.moderate'):
            self.assertFalse(can('operator', capability),
                             'operator 不应持有 %s' % capability)
        for capability in ('farming.manage', 'pest.manage', 'craft.manage',
                           'craft.content.manage',
                           'dialect.manage', 'recruit.manage', 'case.manage'):
            self.assertTrue(can('operator', capability),
                            'operator 应持有 %s' % capability)

    def test_course_capability_split_preserves_current_behaviour(self):
        """course.read 与 course.manage 必须分开，且与改动前的路由一致。

        GET /api/teacher/courses 现在放行 teacher + super_admin（改前就是这样），
        而 POST/PUT/DELETE 只放行 teacher。若合并成一个 course.manage，
        超管会突然能删别人的课程，属于对外行为变化，本票据不允许。
        """
        from core.permissions import CAPABILITIES
        self.assertEqual(CAPABILITIES['course.read'], ('teacher', 'super_admin'))
        self.assertEqual(CAPABILITIES['course.manage'], ('teacher',))

    def test_unknown_capability_fails_closed(self):
        """能力表里没有的能力一律不放行，不因为拼写错误而敞开。"""
        from core.permissions import can
        self.assertFalse(can('super_admin', 'nope.manage'))
        self.assertFalse(can(None, 'user.manage'))

    def test_require_capability_rejects_unknown_capability_at_import(self):
        """装饰器对未知能力立刻炸，而不是运行到一半才发现写错了名字。"""
        from core.permissions import require_capability
        with self.assertRaises(KeyError):
            require_capability('nope.manage')

    def test_student_cannot_reach_admin_surface(self):
        """学员打管理端全部 403。spec 用户故事 9 的底线。"""
        session_id = self._session('student')
        for path in ('/api/admin/users', '/api/admin/reviews',
                     '/api/admin/dashboard', '/api/admin/system-announcements'):
            with self.subTest(path=path):
                r = self.client.get(path, headers={'X-Session-Id': session_id})
                self.assertEqual(r.status_code, 403)


if __name__ == '__main__':
    unittest.main()
