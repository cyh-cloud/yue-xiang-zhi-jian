# -*- coding: utf-8 -*-
"""运营角色（operator）基础设施的对外行为测试（T13）。

本票只做基础设施，不实现运营后台业务接口。这里锁住的事实：

1. operator 是一个真实角色：能登录、能建会话，登录下发结构与其余五个角色逐键一致；
2. operator 是 super_admin 的子集：用户管理与内容审核一律 403，
   六个内容管理能力域不被能力判定拦下；
3. 五个既有角色的行为与 T13 之前逐字一致（能力矩阵由 tests/test_permissions.py 管，
   这里补的是「operator 出现后它们没有被顺手改宽」）；
4. operator 不能自助注册：运营身份由超管指派，注册白名单不收它；
5. 能力表自身的一致性：ROLES 与 CAPABILITIES 不脱节，未知角色一律不放行。

断言全部基于 HTTP 行为与能力表本身，不测前端怎么渲染（那是 T14/T15 的事）。
"""

import json
import os
import sys
import unittest

REPO_ROOT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend')
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

# 演示账号口令与 db_seed_accounts 一致。operator 由本票新增。
OPERATOR_ACCOUNT = ('operator_demo', '123456')

# 既有五个角色。验收要求「行为与改动前一致」，逐条打回这些探针。
EXISTING_ROLES = {
    'student': ('student_demo', '123456'),
    'teacher': ('teacher_demo', '123456'),
    'enterprise': ('enterprise_demo', '123456'),
    'government': ('gov_demo', '123456'),
    'super_admin': ('admin_demo', 'admin123'),
}

# operator 明确不持有的能力 -> 打哪个接口。user.manage 与 review.moderate
# 是 spec 用户故事 9 的底线：运营看不到用户管理与内容审核。
FORBIDDEN_PROBES = {
    'user.manage': ('/api/admin/users', 'GET'),
    'review.moderate': ('/api/admin/reviews', 'GET'),
    'announcement.manage': ('/api/admin/system-announcements', 'GET'),
    'community.manage': ('/api/admin/comments/1', 'DELETE'),
}

# operator 持有的内容管理能力域。T14/T15 才会建 /api/operator/* 路由，
# 所以这里不能打那些路径；改为打各域现有的读接口，证明能力判定不拦它。
# 断言「不是 403」即证明没有任何按角色名的守卫把 operator 挡在内容之外。
CONTENT_READ_PROBES = (
    ('/api/agriculture/products', 'GET'),
    ('/api/agriculture/calendar/lychee', 'GET'),
    ('/api/agriculture/pest-knowledge', 'GET'),
    ('/api/crafts/list', 'GET'),
    ('/api/resources/dialects', 'GET'),
    ('/api/resources/cases', 'GET'),
    ('/api/resources/policies', 'GET'),
    ('/api/employment/jobs', 'GET'),
)


class OperatorRoleTest(unittest.TestCase):
    """operator 作为第六个角色的对外行为。"""

    @classmethod
    def setUpClass(cls):
        from app import app
        cls.app = app
        cls.app.config['TESTING'] = True

    def setUp(self):
        self.client = self.app.test_client()

    def _login(self, username, password):
        return self.client.post('/api/auth/login', data=json.dumps(
            {'username': username, 'password': password}),
            content_type='application/json')

    def _session(self, username, password):
        body = json.loads(self._login(username, password).data)
        self.assertTrue(body.get('success'), '登录失败：%s' % body)
        return body['session_id']

    def test_operator_can_log_in(self):
        """运营演示账号能登录并拿到会话（用户故事 10 的第一步）。"""
        r = self._login(*OPERATOR_ACCOUNT)
        self.assertEqual(r.status_code, 200, r.data)
        body = json.loads(r.data)
        self.assertTrue(body['success'])
        self.assertTrue(body['session_id'])
        self.assertEqual(body['user']['id'], 'operator_demo')
        self.assertEqual(body['user']['role'], 'operator')
        self.assertEqual(body['user']['name'], u'运营专员')

    def test_operator_session_is_usable(self):
        """登录拿到的会话能过 /api/auth/verify，不是一次性摆设。"""
        sid = self._session(*OPERATOR_ACCOUNT)
        r = self.client.post('/api/auth/verify', data=json.dumps(
            {'session_id': sid}), content_type='application/json')
        self.assertEqual(r.status_code, 200)
        body = json.loads(r.data)
        self.assertEqual(body['user']['role'], 'operator')
        self.assertEqual(body['user']['id'], 'operator_demo')

    def test_operator_login_user_shape_matches_the_other_roles(self):
        """登录下发的 user 结构与其余角色逐键一致（前端整份覆盖 AppState.user）。"""
        expected_keys = None
        roles = dict(EXISTING_ROLES)
        roles['operator'] = OPERATOR_ACCOUNT
        for role, (username, password) in roles.items():
            body = json.loads(self._login(username, password).data)
            with self.subTest(role=role):
                keys = set(body['user'])
                if expected_keys is None:
                    expected_keys = keys
                self.assertEqual(keys, expected_keys,
                                 '%s 的 user 结构与其它角色不一致' % role)

    def test_operator_cannot_reach_user_or_review_management(self):
        """用户故事 9：运营打用户管理与内容审核一律 403。"""
        sid = self._session(*OPERATOR_ACCOUNT)
        for capability, (path, method) in FORBIDDEN_PROBES.items():
            with self.subTest(capability=capability, path=path):
                r = self.client.open(path, method=method,
                                     headers={'X-Session-Id': sid})
                self.assertEqual(r.status_code, 403,
                                 'operator 不持 %s，却拿到 %d' % (capability, r.status_code))
                body = json.loads(r.data)
                self.assertFalse(body['success'])
                self.assertEqual(body['message'], u'权限不足')

    def test_operator_is_not_blocked_by_capability_checks_on_content_reads(self):
        """运营打内容域读接口不被能力判定拦下（T14/T15 的写接口挂同一批能力）。"""
        sid = self._session(*OPERATOR_ACCOUNT)
        for path, method in CONTENT_READ_PROBES:
            with self.subTest(path=path):
                r = self.client.open(path, method=method,
                                     headers={'X-Session-Id': sid})
                self.assertNotEqual(r.status_code, 403,
                                    'operator 被拦在 %s 之外' % path)
                self.assertLess(r.status_code, 500)

    def test_operator_cannot_self_register(self):
        """运营身份由超管指派，注册白名单不收它（否则等于人人可自助提权）。"""
        username = 't13_self_operator'
        r = self.client.post('/api/auth/register', data=json.dumps(
            {'username': username, 'password': '123456',
             'name': u'自助运营', 'role': 'operator'}),
            content_type='application/json')
        self.assertEqual(r.status_code, 400)
        body = json.loads(r.data)
        self.assertFalse(body['success'])
        self.assertEqual(body['message'], u'无效的角色类型')
        # 注册被拒时不得留下账号
        from db_domains.users import get_user_by_id
        self.assertIsNone(get_user_by_id(username))

    def test_login_hands_the_frontend_the_capability_list(self):
        """登录必须下发能力清单，前端据此按能力显隐，不自己复制一份能力表。"""
        body = json.loads(self._login(*OPERATOR_ACCOUNT).data)
        self.assertIn('capabilities', body)
        from core.permissions import capabilities_for_role
        self.assertEqual(body['capabilities'], capabilities_for_role('operator'))
        self.assertIn('farming.manage', body['capabilities'])
        self.assertNotIn('user.manage', body['capabilities'])

    def test_verify_hands_the_frontend_the_capability_list(self):
        """会话校验下发同一份清单：刷新页面后显隐不会整块消失。"""
        sid = self._session(*OPERATOR_ACCOUNT)
        body = json.loads(self.client.post('/api/auth/verify', data=json.dumps(
            {'session_id': sid}), content_type='application/json').data)
        self.assertEqual(body['capabilities'],
                         json.loads(self._login(*OPERATOR_ACCOUNT).data)['capabilities'])

    def test_capabilities_endpoint_reports_the_session_role(self):
        """按需再取入口：登录态返回本人能力，访客返回空清单而不是报错。"""
        sid = self._session(*OPERATOR_ACCOUNT)
        r = self.client.get('/api/auth/capabilities',
                            headers={'X-Session-Id': sid})
        self.assertEqual(r.status_code, 200)
        body = json.loads(r.data)
        self.assertEqual(body['role'], 'operator')
        self.assertIn('case.manage', body['capabilities'])

        anon = self.client.get('/api/auth/capabilities')
        self.assertEqual(anon.status_code, 200)
        self.assertEqual(json.loads(anon.data)['capabilities'], [])

    def test_register_still_accepts_the_three_self_service_roles(self):
        """注册白名单对既有的三个自助角色不变（student / teacher / enterprise）。"""
        for role in ('student', 'teacher', 'enterprise'):
            username = 't13_reg_%s' % role
            sid = None
            try:
                r = self.client.post('/api/auth/register', data=json.dumps(
                    {'username': username, 'password': '123456',
                     'name': u'注册' + role, 'role': role}),
                    content_type='application/json')
                with self.subTest(role=role):
                    self.assertEqual(r.status_code, 200, r.data)
                    body = json.loads(r.data)
                    self.assertTrue(body['success'])
                    self.assertEqual(body['user']['role'], role)
                    sid = body['session_id']
            finally:
                _cleanup_user(username, sid)


class ExistingRolesUnchangedTest(unittest.TestCase):
    """既有五个角色的边界在 operator 落地后一个都没被改宽。"""

    @classmethod
    def setUpClass(cls):
        from app import app
        cls.app = app
        cls.app.config['TESTING'] = True

    def setUp(self):
        self.client = self.app.test_client()

    def _session(self, username, password):
        r = self.client.post('/api/auth/login', data=json.dumps(
            {'username': username, 'password': password}),
            content_type='application/json')
        return json.loads(r.data)['session_id']

    def test_only_super_admin_reaches_user_and_review_management(self):
        """user.manage / review.moderate 仍然只有 super_admin 持有。

        operator 落地最容易犯的错就是「顺手把它加进 user.manage」：那样运营
        就能改角色、停用账号，与 spec 用户故事 9 直接冲突。
        """
        from core.permissions import can
        for role in EXISTING_ROLES:
            for capability in ('user.manage', 'review.moderate'):
                with self.subTest(role=role, capability=capability):
                    self.assertEqual(can(role, capability),
                                     role == 'super_admin')

    def test_existing_roles_keep_their_capability_surface(self):
        """五个既有角色持有的能力集合逐条不变（与 T01 的能力表一致）。"""
        from core.permissions import CAPABILITIES, can
        from core.permissions import ROLES
        # 支撑域的 .read 是 T03 删掉 database.py 后补上的：跨域读从隐式变成显式
        # import 边，必须有明确归属，机械检查才判得了权。它们对全部已登录角色
        # 一致放行，不改变任何角色能做的事，所以这里按「全角色共有」处理。
        logged_in_reads = {c for c, holders in CAPABILITIES.items()
                           if c.endswith('.read') and len(holders) == len(ROLES)}
        expected = {
            'student': set(),
            'teacher': {'craft.manage', 'course.read', 'course.manage',
                        'teaching.read', 'teaching.manage'},
            'enterprise': {'job.manage'},
            'government': {'case.manage', 'policy.manage'},
            # 公开能力（farming/pest/craft/dialect/recruit/case/policy 的 .read）
            # 对任何角色都放行，不属于「显式授予」，因此不列在这里。
            'super_admin': {'farming.manage', 'pest.manage', 'craft.manage',
                            'dialect.manage', 'recruit.manage', 'case.manage',
                            'course.read', 'teaching.read',
                            'teaching.manage', 'user.manage', 'review.moderate',
                            'announcement.manage', 'community.manage'},
        }
        for role, wanted in expected.items():
            # 只数**显式授予**的能力：公开能力（空元组）对任何角色都返回 True，            # 把它算进来会让每个角色都带上全部 .read，掩盖真正的边界。            granted = {c for c, holders in CAPABILITIES.items() if role in holders}
            granted -= logged_in_reads
            with self.subTest(role=role):
                self.assertEqual(granted, wanted,
                                 '%s 的能力集合变了' % role)

    def test_existing_roles_still_get_their_expected_status_codes(self):
        """五个既有角色打管理端探针的状态码与 T13 之前一致。"""
        sessions = {role: self._session(*account)
                    for role, account in EXISTING_ROLES.items()}
        probes = {
            'user.manage': ('/api/admin/users', 'GET'),
            'review.moderate': ('/api/admin/reviews', 'GET'),
            'policy.manage': ('/api/government/policies', 'GET'),
            'job.manage': ('/api/enterprise/jobs', 'GET'),
            'course.read': ('/api/teacher/courses', 'GET'),
        }
        from core.permissions import can
        for capability, (path, method) in probes.items():
            for role, sid in sessions.items():
                with self.subTest(capability=capability, role=role):
                    r = self.client.open(path, method=method,
                                         headers={'X-Session-Id': sid})
                    if can(role, capability):
                        self.assertNotEqual(r.status_code, 403,
                                            '%s 持 %s 却拿到 403' % (role, capability))
                    else:
                        self.assertEqual(r.status_code, 403,
                                         '%s 不持 %s 却拿到 %d'
                                         % (role, capability, r.status_code))


class CapabilityTableConsistencyTest(unittest.TestCase):
    """能力表自身不脱节：ROLES 与 CAPABILITIES 对得上，未知角色一律不放行。"""

    def test_operator_is_a_registered_role(self):
        from core.permissions import ROLES, OPERATOR
        self.assertEqual(OPERATOR, 'operator')
        self.assertIn(OPERATOR, ROLES)
        self.assertEqual(ROLES, ('student', 'teacher', 'enterprise',
                                 'government', 'operator', 'super_admin'))

    def test_every_capability_holder_is_a_registered_role(self):
        """能力表里出现未注册角色就是漏洞：那条能力谁都拿不到，却看着像配了。"""
        from core.permissions import ROLES, CAPABILITIES
        for capability, holders in CAPABILITIES.items():
            for role in holders:
                with self.subTest(capability=capability, role=role):
                    self.assertIn(role, ROLES,
                                  '%s 列出了未注册的角色 %s' % (capability, role))

    def test_unknown_role_holds_nothing(self):
        from core.permissions import can
        for capability in ('user.manage', 'farming.manage', 'course.read'):
            self.assertFalse(can('no_such_role', capability))

    def test_capabilities_for_role_matches_the_table(self):
        """下发给前端的能力清单与能力表逐条一致（单一真相源的守门测试）。"""
        from core.permissions import CAPABILITIES, can, capabilities_for_role
        granted = capabilities_for_role('operator')
        # 只列 manage 侧：.read 大多是公开元组，下发给前端会让「显隐」退化成
        # 「全部显示」，没有判断价值（见 capabilities_for_role 的 docstring）。
        self.assertEqual(set(granted),
                         {c for c, holders in CAPABILITIES.items()
                          if 'operator' in holders and c.endswith('.manage')})
        self.assertNotIn('user.manage', granted)
        self.assertNotIn('review.moderate', granted)
        for capability in granted:
            self.assertTrue(can('operator', capability))
        self.assertEqual(capabilities_for_role(None), [])


def _cleanup_user(username, sid):
    """删掉注册用例造出的账号与会话，避免污染后续用例。"""
    from db_connection import get_connection
    conn = get_connection()
    if sid:
        conn.execute("DELETE FROM user_sessions WHERE session_id = ?", (sid,))
    conn.execute("DELETE FROM user_sessions WHERE user_id = ?", (username,))
    conn.execute("DELETE FROM users WHERE username = ?", (username,))
    conn.commit()
    conn.close()


if __name__ == '__main__':
    unittest.main()
