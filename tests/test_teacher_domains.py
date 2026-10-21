# -*- coding: utf-8 -*-
"""教师管理域与教学支撑域的路由行为测试（T16）。

锁住从 app.py 搬进 domains/teacher 与 domains/teaching_support 之后必须一字不变的
外部契约：URL、请求响应结构、状态码、错误码，以及四条业务底线：

- 名册与学员的增删改查：学号生成、关联账号三种模式、失败回滚；
- 教师报表与学情分析的口径是「证书真实完成度」，不读手填的 students.progress；
- 公告与课程材料、3D 模型的增删，以及上传落盘与静态取回是同一处目录；
- 角色边界：教师端接口只允许 teacher 与 super_admin，学员与未登录一律被拒。

断言全部基于 HTTP 行为，不测模块怎么划分（拆分不产生新行为，为结构写测试只会把
实现细节钉死，见 spec 的 Testing Decisions）。
"""

import io
import json
import os
import sys
import unittest

REPO_ROOT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend')
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import repo_paths  # noqa: E402
from db_connection import get_connection
from db_domains import teaching, users
from db_domains import courses as courses_db


class TeacherDomainTestBase(unittest.TestCase):
    """公共脚手架：按需登录、按需清理自己造出来的行。"""

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

    def _json(self, method, path, payload=None, session_id=None):
        headers = {}
        if session_id:
            headers['X-Session-Id'] = session_id
        return self.client.open(path, method=method, data=json.dumps(payload or {}),
                                content_type='application/json', headers=headers)

class RosterCrudTest(TeacherDomainTestBase):
    """名册增删改查：字段、状态码、错误码。"""

    def _cleanup(self):
        conn = get_connection()
        conn.execute("DELETE FROM students WHERE name LIKE '__T16%'")
        conn.execute("DELETE FROM users WHERE username LIKE '__t16%' OR username = '__t16free'")
        conn.commit()
        conn.close()

    def test_roster_crud_round_trip(self):
        self.addCleanup(self._cleanup)
        sid = self._login()
        headers = {'X-Session-Id': sid}

        r = self._json('POST', '/api/teacher/students/add',
                       {'name': '__T16学员__', 'class_name': '一班', 'direction': '荔枝种植'},
                       session_id=sid)
        self.assertEqual(r.status_code, 200)
        body = json.loads(r.data)
        self.assertTrue(body['success'])
        student_id = body['student_id']
        self.assertTrue(student_id.startswith('STU'), student_id)
        # 三种关联模式之一：都不传 -> 只建名册，并明确提示无法登录
        self.assertEqual(body['linked_account'], '')
        self.assertIn('无法登录', body['message'])

        # 列表里能读到，且带证书真实完成度字段
        roster = json.loads(self.client.get(
            '/api/teacher/students', headers=headers).data)['students']
        row = next(s for s in roster if s['id'] == student_id)
        for key in ('cert_total', 'cert_earned', 'completion', 'has_cert_data'):
            self.assertIn(key, row)
        self.assertEqual(row['name'], '__T16学员__')
        self.assertFalse(row['has_cert_data'], '没有证书记录不等于 0% 完成')

        # 详情与列表口径一致
        detail = json.loads(self.client.get(
            '/api/teacher/students/%s' % student_id, headers=headers).data)
        self.assertTrue(detail['success'])
        self.assertEqual(detail['student']['id'], student_id)
        self.assertFalse(detail['student']['has_cert_data'])

        # 更新：手填 progress 可以写，但学情口径不读它
        r = self._json('PUT', '/api/teacher/students/%s' % student_id,
                       {'name': '__T16改名__', 'progress': 99}, session_id=sid)
        self.assertTrue(json.loads(r.data)['success'])
        detail = json.loads(self.client.get(
            '/api/teacher/students/%s' % student_id, headers=headers).data)['student']
        self.assertEqual(detail['name'], '__T16改名__')
        self.assertFalse(detail['has_cert_data'], '手填 progress 不得改变完成度口径')

        # 删除后详情变成「未找到学员」，且返回 200
        r = self.client.delete('/api/teacher/students/%s' % student_id, headers=headers)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(json.loads(r.data)['success'])
        detail = json.loads(self.client.get(
            '/api/teacher/students/%s' % student_id, headers=headers).data)
        self.assertFalse(detail['success'])
        self.assertEqual(detail['message'], '未找到学员')

    def test_add_student_requires_a_name(self):
        sid = self._login()
        r = self._json('POST', '/api/teacher/students/add', {'class_name': '一班'}, session_id=sid)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(json.loads(r.data)['message'], '请输入学员姓名')

    def test_new_account_needs_a_long_enough_password(self):
        sid = self._login()
        r = self._json('POST', '/api/teacher/students/add',
                       {'name': '__T16学员__', 'new_username': '__t16new',
                        'new_password': '123'},
                       session_id=sid)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(json.loads(r.data)['message'], '初始密码至少 6 位')

    def test_add_student_rolls_back_when_link_fails(self):
        """账号创建成功但关联失败时，不得留下只建了名册的半成品。

        触发条件选「账号已被另一条名册行占用」：这是 set_student_account 会返回
        失败的三种情形里唯一能在不碰 users 表的前提下稳定造出来的。
        """
        self.addCleanup(self._cleanup)
        self.addCleanup(self._unlink, 'student_demo')
        sid = self._login()
        conn = get_connection()
        conn.execute("DELETE FROM students WHERE name = '__T16占位__'")
        conn.execute("INSERT INTO students (id, name, user_id) "
                     "VALUES ('STU999', '__T16占位__', 'student_demo')")
        conn.commit()
        conn.close()

        r = self._json('POST', '/api/teacher/students/add',
                       {'name': '__T16占用__', 'link_username': 'student_demo'}, session_id=sid)
        self.assertEqual(r.status_code, 400)
        body = json.loads(r.data)
        self.assertFalse(body['success'])
        self.assertIn('已关联到名册', body['message'])
        # 名册行必须回滚掉，不能留下一条没人认领的半成品
        roster = json.loads(self.client.get(
            '/api/teacher/students', headers={'X-Session-Id': sid}).data)['students']
        self.assertEqual([s for s in roster if s['name'] == '__T16占用__'], [])

    def _unlink(self, username):
        conn = get_connection()
        conn.execute("DELETE FROM students WHERE name = '__T16占位__'")
        conn.commit()
        conn.close()

    def test_add_student_creates_and_links_a_new_account(self):
        self.addCleanup(self._cleanup)
        sid = self._login()
        r = self._json('POST', '/api/teacher/students/add',
                       {'name': '__T16新账号__', 'new_username': '__t16account',
                        'new_password': '123456'},
                       session_id=sid)
        self.assertEqual(r.status_code, 200)
        body = json.loads(r.data)
        self.assertTrue(body['success'])
        self.assertEqual(body['linked_account'], '__t16account')
        self.assertIn('已新建并关联账号', body['message'])
        row = next(s for s in json.loads(self.client.get(
            '/api/teacher/students', headers={'X-Session-Id': sid}).data)['students']
            if s['name'] == '__T16新账号__')
        self.assertEqual(row['user_id'], '__t16account')

    def test_add_student_links_an_existing_account(self):
        self.addCleanup(self._cleanup)
        sid = self._login()
        r = self._json('POST', '/api/teacher/students/add',
                       {'name': '__T16关联__', 'link_username': 'test_user'}, session_id=sid)
        self.assertEqual(r.status_code, 200)
        body = json.loads(r.data)
        self.assertTrue(body['success'])
        self.assertEqual(body['linked_account'], 'test_user')
        self.assertIn('已关联账号', body['message'])
        row = next(s for s in json.loads(self.client.get(
            '/api/teacher/students', headers={'X-Session-Id': sid}).data)['students']
            if s['name'] == '__T16关联__')
        self.assertEqual(row['user_id'], 'test_user')


class AccountLinkTest(TeacherDomainTestBase):
    """账号绑定：可关联清单、绑定与解除、占用与不存在。"""

    def _cleanup(self):
        conn = get_connection()
        conn.execute("DELETE FROM students WHERE name LIKE '__T16%'")
        conn.execute("DELETE FROM users WHERE username LIKE '__t16%' OR username = '__t16free'")
        conn.commit()
        conn.close()

    def test_linkable_accounts_exclude_taken_ones(self):
        """可关联清单 = role=student 且未被任何名册行占用。

        这条用例的断言语义与库里已有的演示数据无关：先在库内造一条已知未占用的
        学员账号，断言它在清单里；再把它绑到名册行上，断言它从清单里消失。
        这样无论同批次其他用例留下什么行，断言都成立。
        """
        self.addCleanup(self._cleanup)
        sid = self._login()
        conn = get_connection()
        conn.execute("DELETE FROM users WHERE username = '__t16free'")
        conn.commit()
        conn.close()
        users.register_user('__t16free', '123456', '__T16未占用__', 'student')

        data = json.loads(self.client.get(
            '/api/teacher/linkable-accounts', headers={'X-Session-Id': sid}).data)
        self.assertTrue(data['success'])
        usernames = [a['username'] for a in data['accounts']]
        self.assertIn('__t16free', usernames)
        # student_demo 已被 STU001 占用，不能再出现在可关联清单里
        self.assertNotIn('student_demo', usernames)

        # 绑走之后它就从清单里消失：一个账号不能挂到两个学员上
        self._json('POST', '/api/teacher/students/add',
                   {'name': '__T16占用清单__', 'link_username': '__t16free'}, session_id=sid)
        again = json.loads(self.client.get(
            '/api/teacher/linkable-accounts', headers={'X-Session-Id': sid}).data)['accounts']
        self.assertNotIn('__t16free', [a['username'] for a in again])

        conn = get_connection()
        conn.execute("DELETE FROM users WHERE username = '__t16free'")
        conn.commit()
        conn.close()

    def test_link_and_unlink_round_trip(self):
        self.addCleanup(self._cleanup)
        sid = self._login()
        headers = {'X-Session-Id': sid}
        r = self._json('POST', '/api/teacher/students/add',
                       {'name': '__T16绑定__'}, session_id=sid)
        student_id = json.loads(r.data)['student_id']

        r = self._json('POST', '/api/teacher/students/%s/link' % student_id,
                       {'username': 'test_user'}, session_id=sid)
        body = json.loads(r.data)
        self.assertTrue(body['success'])
        self.assertEqual(body['user_id'], 'test_user')

        r = self._json('POST', '/api/teacher/students/%s/link' % student_id,
                       {'username': ''}, session_id=sid)
        body = json.loads(r.data)
        self.assertTrue(body['success'])
        self.assertEqual(body['user_id'], '')

    def test_link_rejects_unknown_account(self):
        self.addCleanup(self._cleanup)
        sid = self._login()
        r = self._json('POST', '/api/teacher/students/add',
                       {'name': '__T16坏账号__'}, session_id=sid)
        student_id = json.loads(r.data)['student_id']
        r = self._json('POST', '/api/teacher/students/%s/link' % student_id,
                       {'username': 'no_such_user_here'}, session_id=sid)
        self.assertEqual(r.status_code, 400)
        self.assertFalse(json.loads(r.data)['success'])


class TeacherReportTest(TeacherDomainTestBase):
    """教师报表：空名册不调 AI、口径用证书真实完成度、AI 不可用走兜底。"""

    def _cleanup(self):
        conn = get_connection()
        conn.execute("DELETE FROM students WHERE name LIKE '__T16%'")
        conn.execute("DELETE FROM users WHERE username LIKE '__t16%' OR username = '__t16free'")
        conn.commit()
        conn.close()

    def test_empty_prompt_is_rejected(self):
        sid = self._login()
        r = self._json('POST', '/api/teacher/reports/generate', {'prompt': '  '}, session_id=sid)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(json.loads(r.data)['message'], '请输入分析需求')

    def test_empty_roster_returns_a_report_without_calling_ai(self):
        self.addCleanup(self._cleanup)
        self.addCleanup(self._restore_roster)
        conn = get_connection()
        conn.execute("DELETE FROM students")
        conn.commit()
        conn.close()

        import domains.teacher.reports as reports
        original = reports.call_ai_service
        try:
            def boom(**kwargs):
                raise AssertionError('名册为空时不得调用上游')
            reports.call_ai_service = boom
            sid = self._login()
            r = self._json('POST', '/api/teacher/reports/generate',
                           {'prompt': '分析风险学员'}, session_id=sid)
        finally:
            reports.call_ai_service = original

        self.assertEqual(r.status_code, 200)
        body = json.loads(r.data)
        self.assertTrue(body['success'])
        self.assertEqual(body['report']['title'], 'AI 教学报告')
        self.assertIn('暂无数据', body['report']['content'])
        self.assertTrue(body['report']['degraded'])
        self.assertEqual(body['report']['degraded_reason'], 'no_roster_data')

    def _restore_roster(self):
        conn = get_connection()
        if conn.execute("SELECT COUNT(*) FROM students").fetchone()[0] == 0:
            conn.execute(
                "INSERT INTO students "
                "(id, user_id, teacher_id, name, class_name, direction) "
                "VALUES ('STU001', 'student_demo', 'teacher_demo', "
                "'小明', '一班', '荔枝种植')")
            conn.execute(
                "INSERT INTO students "
                "(id, user_id, teacher_id, name, class_name, direction) "
                "VALUES ('STU002', '', 'teacher_demo', "
                "'小红', '一班', '电商运营')")
            conn.commit()
        conn.close()

    def test_report_falls_back_when_upstream_is_unavailable(self):
        """上游不可用时仍回 200 + 兜底报告，概览口径与主路径一致。"""
        self.addCleanup(self._cleanup)
        sid = self._login()
        self._json('POST', '/api/teacher/students/add',
                   {'name': '__T16报表__'}, session_id=sid)

        import domains.teacher.reports as reports
        original = reports.call_ai_service
        try:
            reports.call_ai_service = lambda **kw: (_ for _ in ()).throw(
                RuntimeError('upstream down'))
            r = self._json('POST', '/api/teacher/reports/generate',
                           {'prompt': '分析风险学员'}, session_id=sid)
        finally:
            reports.call_ai_service = original

        self.assertEqual(r.status_code, 200)
        report = json.loads(r.data)['report']
        self.assertEqual(report['title'], 'AI 教学报告')
        self.assertTrue(report['degraded'])
        self.assertEqual(report['degraded_reason'], 'ai_unavailable')
        self.assertIn('数据口径：证书真实完成度', report['content'])
        self.assertIn('__T16报表__', report['content'])
        # 兜底概览与主路径同一套键
        self.assertEqual(set(report['overview']), {
            'total', 'avg_progress', 'no_cert_count', 'direction_count',
            'completed_count', 'risk_count', 'excellent_count', 'brackets',
            'directions', 'at_risk', 'excellent', 'focus', 'title',
            'highlight_stats'})
        self.assertEqual(report['overview']['total'],
                         len(teaching.get_roster_completion('teacher_demo')))

    def test_report_sends_roster_context_to_the_upstream(self):
        """上游调用必须带上名册数据，且报告主题随 prompt 切换。

        桩打在域自己持有的 `call_ai_service` 名字上（与 tests/test_resources_domain.py
        同一手法），不改写共享层的开关：改写 ai.client.ai_configured 只会影响
        「上游是否已配置」这一判断，而这里要验的是主路径确实把名册数据送给上游。
        """
        self.addCleanup(self._cleanup)
        sid = self._login()
        self._json('POST', '/api/teacher/students/add',
                   {'name': '__T16报表__', 'direction': '水产养殖'}, session_id=sid)

        import domains.teacher.reports as reports
        original = reports.call_ai_service
        captured = {}
        try:
            def capture(**kwargs):
                captured.update(kwargs)
                return '## 风险预警\n\n内容'
            reports.call_ai_service = capture
            r = self._json('POST', '/api/teacher/reports/generate',
                           {'prompt': '分析风险学员'}, session_id=sid)
        finally:
            reports.call_ai_service = original

        self.assertEqual(r.status_code, 200)
        report = json.loads(r.data)['report']
        self.assertEqual(report['content'], '## 风险预警\n\n内容')
        self.assertFalse(report['degraded'])
        self.assertEqual(report['degraded_reason'], '')
        self.assertEqual(report['overview']['focus'], 'risk')
        self.assertEqual(report['overview']['title'], '风险预警概览')
        self.assertEqual(report['overview']['highlight_stats'],
                         ['risk_count', 'total', 'avg_progress'])
        # 名册数据必须真的进上下文，否则报告就是无据可查的编造
        self.assertIn('__T16报表__', captured['user_message'])
        self.assertIn('证书真实完成度', captured['user_message'])
        self.assertIn('水产养殖', captured['user_message'])


class DashboardAndAnalyticsTest(TeacherDomainTestBase):
    """仪表板与学情分析：口径一致，全部来自真实数据。"""

    def test_dashboard_stats_come_from_the_certificate_caliber(self):
        sid = self._login()
        data = json.loads(self.client.get(
            '/api/teacher/dashboard', headers={'X-Session-Id': sid}).data)
        self.assertTrue(data['success'])
        stats = data['dashboard']['stats']
        self.assertEqual(set(stats), {'total_students', 'certificates_earned',
                                      'completion_rate', 'avg_score', 'no_cert_count'})
        self.assertEqual(stats['total_students'], len(teaching.get_roster_completion()))
        self.assertLessEqual(stats['completion_rate'], 100)

    def test_analytics_reports_certificate_basis(self):
        sid = self._login()
        data = json.loads(self.client.get(
            '/api/teacher/analytics', headers={'X-Session-Id': sid}).data)
        self.assertTrue(data['success'])
        analytics = data['analytics']
        self.assertEqual(analytics['basis'], 'certificates')
        self.assertEqual(analytics['roster_count'], len(teaching.get_roster_completion()))
        self.assertEqual([d['label'] for d in analytics['progress_distribution']],
                         ['0-20%', '21-40%', '41-60%', '61-80%', '81-100%'])
        for d in analytics['direction_progress']:
            self.assertLessEqual(d['no_cert_count'], d['student_count'])
        self.assertEqual(sum(d['count'] for d in analytics['direction_distribution']),
                         analytics['roster_count'])


class AnnouncementTest(TeacherDomainTestBase):
    """公告：教师增删、学员可读、参数校验。"""

    def _cleanup(self):
        conn = get_connection()
        conn.execute("DELETE FROM announcements WHERE title LIKE '__T16%'")
        conn.execute(
            "DELETE FROM notifications "
            "WHERE title LIKE '新通知' OR title LIKE '__T16%'"
        )
        conn.commit()
        conn.close()

    def test_announcement_crud_and_student_visibility(self):
        self.addCleanup(self._cleanup)
        teacher = self._login('teacher_demo')
        student = self._login('student_demo')

        r = self._json('POST', '/api/teacher/announcements',
                       {'title': '__T16公告__', 'content': '公告正文', 'pinned': 1},
                       session_id=teacher)
        body = json.loads(r.data)
        self.assertTrue(body['success'])
        ann_id = body['id']

        created = json.loads(self.client.get(
            '/api/teacher/announcements', headers={'X-Session-Id': teacher}).data)['announcements']
        row = next(a for a in created if a['id'] == ann_id)
        self.assertEqual(row['title'], '__T16公告__')
        self.assertEqual(row['pinned'], 1)

        # 学员端能读到，且默认 limit=30
        mine = json.loads(self.client.get(
            '/api/student/announcements', headers={'X-Session-Id': student}).data)['announcements']
        self.assertTrue(any(a['id'] == ann_id for a in mine))
        self.assertLessEqual(len(mine), 30)

        # 学员端公告路由本来不带登录门禁，匿名也能读
        anonymous = json.loads(self.client.get('/api/student/announcements').data)
        self.assertTrue(anonymous['success'])

        r = self.client.delete('/api/teacher/announcements/%d' % ann_id,
                               headers={'X-Session-Id': teacher})
        self.assertTrue(json.loads(r.data)['success'])
        again = json.loads(self.client.get(
            '/api/teacher/announcements', headers={'X-Session-Id': teacher}).data)['announcements']
        self.assertFalse(any(a['id'] == ann_id for a in again))

    def test_announcement_broadcast_hits_the_data_layer_contract(self):
        """发公告后，已关联平台账号的学员必须真的收到一条通知。

        走完整链路，不打桩。T05 收窄接口时这里曾把 `for r in rows` 写成读未定义的
        rows，整条链路一调就 NameError 500，而种子库里没有公告类未读数据所以单测
        一直没暴露。这条用例就是堵那个洞：断言落在 notifications 表里的行数等于
        名册中已关联账号的学员数。
        """
        self.addCleanup(self._cleanup)
        sid = self._login('teacher_demo')
        # 清掉历史通知，让计数从已知起点开始
        conn = get_connection()
        conn.execute('DELETE FROM notifications')
        conn.commit()
        conn.close()
        from db_domains.students import get_linked_student_user_ids
        expected = len(get_linked_student_user_ids())
        self.assertGreater(expected, 0, '种子库里应至少有一个已关联账号的学员')

        r = self._json('POST', '/api/teacher/announcements',
                       {'title': '__T16广播__', 'content': '正文',
                        'category': '通知', 'pinned': 0}, session_id=sid)

        self.assertEqual(r.status_code, 200)
        self.assertTrue(json.loads(r.data)['success'])
        conn = get_connection()
        rows = conn.execute(
            'SELECT user_id, type, title, link_type, link_id FROM notifications'
        ).fetchall()
        conn.close()
        self.assertEqual(len(rows), expected,
                         '每个已关联账号的学员都该收到一条，不多不少')
        self.assertTrue(all(r['type'] == 'announcement' for r in rows))
        self.assertTrue(all(r['title'] == '新通知' for r in rows))
        self.assertTrue(all(r['link_type'] == 'announcement' for r in rows))
        # 收件人必须是 username 而不是名册号（STU001…）
        self.assertTrue(all(not r['user_id'].startswith('STU') for r in rows),
                        '收件人必须是 username，早期实现误用名册号导致学员收不到')

    def test_announcement_delete_removes_only_its_notification_copies(self):
        """删除公告要同步撤回共享消息中心的副本，其他消息不受影响。"""
        self.addCleanup(self._cleanup)
        teacher = self._login('teacher_demo')
        student = self._login('student_demo')

        first = self._json(
            'POST',
            '/api/teacher/announcements',
            {'title': '__T16删除一__', 'content': '第一条公告正文'},
            session_id=teacher,
        ).get_json()
        second = self._json(
            'POST',
            '/api/teacher/announcements',
            {'title': '__T16删除二__', 'content': '第二条公告正文'},
            session_id=teacher,
        ).get_json()
        self.assertTrue(first['success'])
        self.assertTrue(second['success'])

        conn = get_connection()
        conn.execute(
            "INSERT INTO notifications "
            "(user_id, type, title, content, link_type, link_id) "
            "VALUES (?, 'system', '__T16无关通知__', '保留', 'system', NULL)",
            ('student_demo',),
        )
        conn.commit()
        before = conn.execute(
            "SELECT COUNT(*) FROM notifications WHERE user_id = ? "
            "AND link_type = 'announcement' AND link_id IN (?, ?)",
            ('student_demo', first['id'], second['id']),
        ).fetchone()[0]
        conn.close()

        unread_before = self.client.get(
            '/api/notifications/unread?user_id=student_demo',
            headers={'X-Session-Id': student},
        ).get_json()['count']

        deleted = self.client.delete(
            '/api/teacher/announcements/%d' % first['id'],
            headers={'X-Session-Id': teacher},
        )
        self.assertTrue(deleted.get_json()['success'])

        conn = get_connection()
        remaining_announcement_links = conn.execute(
            "SELECT COUNT(*) FROM notifications "
            "WHERE user_id = ? AND link_type = 'announcement' "
            "AND link_id = ?",
            ('student_demo', first['id']),
        ).fetchone()[0]
        second_links = conn.execute(
            "SELECT COUNT(*) FROM notifications "
            "WHERE user_id = ? AND link_type = 'announcement' "
            "AND link_id = ?",
            ('student_demo', second['id']),
        ).fetchone()[0]
        unrelated = conn.execute(
            "SELECT COUNT(*) FROM notifications "
            "WHERE user_id = ? AND title = '__T16无关通知__'",
            ('student_demo',),
        ).fetchone()[0]
        conn.close()

        self.assertEqual(remaining_announcement_links, 0)
        self.assertGreater(second_links, 0)
        self.assertEqual(unrelated, 1)
        self.assertLess(
            self.client.get(
                '/api/notifications/unread?user_id=student_demo',
                headers={'X-Session-Id': student},
            ).get_json()['count'],
            unread_before,
        )
        self.assertEqual(before, 2)

    def test_unauthorized_announcement_delete_has_no_side_effects(self):
        """越权删除公告时，公告与对应通知都保持原样。"""
        self.addCleanup(self._cleanup)
        owner = self._login('teacher_demo')
        created = self._json(
            'POST',
            '/api/teacher/announcements',
            {'title': '__T16越权删除__', 'content': '不可越权删除'},
            session_id=owner,
        ).get_json()
        self.assertTrue(created['success'])

        from db_domains.users import register_user
        register_user('__t16_other_teacher', '123456', '其他教师', 'teacher')
        self.addCleanup(self._delete_other_teacher)
        other = self._login('__t16_other_teacher')

        denied = self.client.delete(
            '/api/teacher/announcements/%d' % created['id'],
            headers={'X-Session-Id': other},
        )
        self.assertFalse(denied.get_json()['success'])

        conn = get_connection()
        announcement = conn.execute(
            'SELECT 1 FROM announcements WHERE id = ?',
            (created['id'],),
        ).fetchone()
        notification = conn.execute(
            "SELECT 1 FROM notifications WHERE user_id = 'student_demo' "
            "AND link_type = 'announcement' AND link_id = ?",
            (created['id'],),
        ).fetchone()
        conn.close()
        self.assertIsNotNone(announcement)
        self.assertIsNotNone(notification)

    def _delete_other_teacher(self):
        conn = get_connection()
        conn.execute(
            "DELETE FROM user_sessions WHERE user_id = '__t16_other_teacher'"
        )
        conn.execute(
            "DELETE FROM users WHERE username = '__t16_other_teacher'"
        )
        conn.commit()
        conn.close()

    def test_announcement_requires_title_and_content(self):
        sid = self._login('teacher_demo')
        for payload in ({'title': 'x'}, {'content': 'x'}, {}):
            r = self._json('POST', '/api/teacher/announcements', payload, session_id=sid)
            self.assertEqual(r.status_code, 200)
            self.assertFalse(json.loads(r.data)['success'])
            self.assertEqual(json.loads(r.data)['message'], '请填写标题和内容')

    def test_delete_unknown_announcement_says_not_found(self):
        sid = self._login('teacher_demo')
        r = self.client.delete('/api/teacher/announcements/99999999',
                               headers={'X-Session-Id': sid})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(json.loads(r.data)['success'])
        self.assertEqual(json.loads(r.data)['message'], '未找到通知')


class GradingTest(TeacherDomainTestBase):
    """实训批改：参数校验、批改落库与通知。"""

    def _cleanup(self):
        conn = get_connection()
        conn.execute("DELETE FROM notifications WHERE title = '实训已批改' "
                     "AND content = '得分：88'")
        conn.commit()
        conn.close()

    def test_missing_fields_are_rejected(self):
        sid = self._login('teacher_demo')
        for payload in ({}, {'submission_id': 1}, {'score': 80}):
            r = self._json('POST', '/api/teacher/assignments/grade', payload, session_id=sid)
            self.assertEqual(r.status_code, 200)
            self.assertFalse(json.loads(r.data)['success'])
            self.assertEqual(json.loads(r.data)['message'], '请填写批改信息')

    def test_grading_a_submission_notifies_the_student(self):
        self.addCleanup(self._cleanup)
        sid = self._login('teacher_demo')
        conn = get_connection()
        sub = conn.execute("SELECT id FROM assignment_submissions LIMIT 1").fetchone()
        conn.close()
        self.assertIsNotNone(sub, '库里需要有实训提交记录')

        r = self._json('POST', '/api/teacher/assignments/grade',
                       {'submission_id': sub['id'], 'score': 88, 'feedback': 'T16 批改'},
                       session_id=sid)
        self.assertTrue(json.loads(r.data)['success'])
        self.assertEqual(json.loads(r.data)['message'], '批改成功')
        conn = get_connection()
        row = conn.execute("SELECT score, feedback, status FROM assignment_submissions "
                           "WHERE id = ?", (sub['id'],)).fetchone()
        conn.close()
        self.assertEqual(row['score'], 88)
        self.assertEqual(row['feedback'], 'T16 批改')
        self.assertEqual(row['status'], 'graded')


class TrainingListTest(TeacherDomainTestBase):
    """教师端实训提交列表：正文必须下发，状态标签与学员端同源。"""

    def test_trainings_expose_the_work_and_a_status_label(self):
        sid = self._login('teacher_demo')
        data = json.loads(self.client.get(
            '/api/teacher/trainings', headers={'X-Session-Id': sid}).data)
        self.assertTrue(data['success'])
        self.assertIn('pending_regrade', data)
        self.assertIsInstance(data['trainings'], list)
        if data['trainings']:
            row = data['trainings'][0]
            for key in ('id', 'student_id', 'assignment_id', 'kind', 'product',
                        'attempts', 'score', 'rule_score', 'script', 'transcript',
                        'meta', 'script_len', 'feedback', 'status', 'status_label',
                        'submitted_at', 'graded_at', 'regrade_needed'):
                self.assertIn(key, row)
            # 状态标签与直播实训域同一份查表，不是两套字符串
            self.assertIn(row['status_label'],
                          ('待提交', '待批改', '已批改', '已重新提交·待复核'))
            self.assertEqual(row['regrade_needed'], row['status'] == 'resubmitted')
        self.assertEqual(data['pending_regrade'],
                         sum(1 for t in data['trainings'] if t['regrade_needed']))

    def test_trainings_include_the_student_work_body(self):
        """作品正文必须下发，否则教师只能「盲批」。"""
        sid = self._login('teacher_demo')
        data = json.loads(self.client.get(
            '/api/teacher/trainings', headers={'X-Session-Id': sid}).data)
        for row in data['trainings']:
            if row['kind'] == 'live':
                self.assertIsInstance(row['script'], str)
            if row['kind'] == 'cs':
                self.assertIsInstance(row['transcript'], list)

    def test_status_label_has_a_single_implementation(self):
        """单一真相源：教师端与学员端必须是同一个函数对象。"""
        from domains.live_training import routes as live_routes
        from domains.teaching_support import routes as support_routes
        from shared.training_status import training_status_label
        self.assertIs(live_routes._training_status_label, training_status_label)
        self.assertIs(support_routes.training_status_label, training_status_label)


class CourseCrudTest(TeacherDomainTestBase):
    """课程增删改：角色边界与返回结构。"""

    def _cleanup(self):
        conn = get_connection()
        conn.execute("DELETE FROM courses WHERE title LIKE '__T16%'")
        conn.commit()
        conn.close()

    def test_course_crud_round_trip(self):
        self.addCleanup(self._cleanup)
        sid = self._login('teacher_demo')
        headers = {'X-Session-Id': sid}

        r = self._json('POST', '/api/teacher/courses',
                       {'title': '__T16课程__', 'description': 'desc', 'category': '种植'},
                       session_id=sid)
        body = json.loads(r.data)
        self.assertTrue(body['success'])
        course_id = body['id']
        self.assertIn('等待审核', body['message'])

        courses = json.loads(self.client.get(
            '/api/teacher/courses', headers=headers).data)['courses']
        row = next(c for c in courses if c['id'] == course_id)
        self.assertEqual(row['title'], '__T16课程__')
        self.assertEqual(row['teacher_id'], 'teacher_demo')
        # 未发布不应出现在公开课程里
        public = json.loads(self.client.get('/api/teacher/public-courses').data)['courses']
        self.assertNotIn(course_id, [c['id'] for c in public])

        r = self._json('PUT', '/api/teacher/courses/%d' % course_id,
                       {'title': '__T16课程改名__'}, session_id=sid)
        self.assertTrue(json.loads(r.data)['success'])
        courses = json.loads(self.client.get(
            '/api/teacher/courses', headers=headers).data)['courses']
        self.assertEqual(next(c for c in courses if c['id'] == course_id)['title'],
                         '__T16课程改名__')

        r = self.client.delete('/api/teacher/courses/%d' % course_id, headers=headers)
        self.assertTrue(json.loads(r.data)['success'])
        courses = json.loads(self.client.get(
            '/api/teacher/courses', headers=headers).data)['courses']
        self.assertNotIn(course_id, [c['id'] for c in courses])

    def test_courses_get_allows_super_admin_but_write_does_not(self):
        """读允许 teacher 与 super_admin；写只允许 teacher。"""
        self.addCleanup(self._cleanup)
        admin = self._login('admin_demo', 'admin123')
        r = self.client.get('/api/teacher/courses', headers={'X-Session-Id': admin})
        self.assertEqual(r.status_code, 200)
        r = self._json('POST', '/api/teacher/courses', {'title': '__T16超管__'},
                       session_id=admin)
        self.assertEqual(r.status_code, 403)

    def test_materials_read_and_write_require_the_course_teacher(self):
        """素材读写：课程教师本人可读可写，匿名与学员均被拒绝。

        课程由本用例自己造，不再去库里挑一门现成的。内容落库之后课程是教师产生的、
        没有演示数据，挑现成的会让用例依赖「库里恰好残留着别处造的数据」。
        """
        sid = self._login('teacher_demo')
        created = self._json('POST', '/api/teacher/courses',
                             {'title': '__T16素材课程__', 'description': 'materials'},
                             session_id=sid)
        course_id = json.loads(created.data)['id']
        # courses 域的删除入口会一并删素材与审核记录，不留半成品
        self.addCleanup(courses_db.delete_course, course_id)

        r = self.client.get('/api/teacher/courses/%d/materials' % course_id)
        self.assertEqual(r.status_code, 403)
        r = self.client.get(
            '/api/teacher/courses/%d/materials' % course_id,
            headers={'X-Session-Id': sid},
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(json.loads(r.data)['materials'], [])

        # 写侧是 inline 守卫：未登录与角色不符都是 403
        r = self.client.post('/api/teacher/courses/%d/materials' % course_id)
        self.assertEqual(r.status_code, 403)
        self.assertEqual(json.loads(r.data)['message'], '权限不足')
        student = self._login('student_demo')
        r = self.client.post('/api/teacher/courses/%d/materials' % course_id,
                             headers={'X-Session-Id': student})
        self.assertEqual(r.status_code, 403)


class MaterialUploadTest(TeacherDomainTestBase):
    """课程材料上传：类型判定、上传往返、删除。"""

    def _cleanup(self):
        conn = get_connection()
        conn.execute("DELETE FROM course_materials WHERE course_id >= 990100")
        conn.commit()
        conn.close()

    def _create_course(self, session_id):
        response = self.client.post(
            '/api/teacher/courses',
            json={'title': '__T16材料课程__', 'description': 'material test'},
            headers={'X-Session-Id': session_id},
        )
        self.assertEqual(response.status_code, 200, response.data)
        course_id = response.get_json()['id']

        def cleanup():
            conn = get_connection()
            rows = conn.execute(
                "SELECT file_path FROM course_materials WHERE course_id = ?",
                (course_id,),
            ).fetchall()
            conn.close()
            for row in rows:
                path = os.path.join(repo_paths.REPO_ROOT, row['file_path'])
                if os.path.exists(path):
                    os.remove(path)
            courses_db.delete_course(course_id)

        self.addCleanup(cleanup)
        return course_id

    def test_material_upload_round_trip_and_type_judgement(self):
        sid = self._login('teacher_demo')
        headers = {'X-Session-Id': sid}
        course_id = self._create_course(sid)

        payload = b'%PDF-1.4 T16 material round trip probe\n'
        uploaded = self.client.post(
            '/api/teacher/courses/%d/materials' % course_id,
            data={'file': (io.BytesIO(payload), 't16_probe_material.pdf')},
            headers=headers)
        self.assertEqual(uploaded.status_code, 200)
        mat_id = json.loads(uploaded.data)['id']

        row = next(r for r in courses_db.get_course_materials(course_id)
                   if r['id'] == mat_id)
        self.assertEqual(row['material_type'], 'pdf')
        self.assertEqual(row['file_name'], 't16_probe_material.pdf')
        # os.path.join yields a backslash on Windows, so assert on the path segments rather than a literal prefix
        parts = row['file_path'].replace('\\', '/').split('/')
        self.assertEqual(parts[:3], ['uploads', 'courses', str(course_id)], row['file_path'])

        # 落盘位置必须是仓库根下的 uploads/，且能经静态路由原路取回
        on_disk = os.path.join(repo_paths.REPO_ROOT, row['file_path'])
        self.assertTrue(os.path.isfile(on_disk), '上传文件没有落在仓库根的上传目录下')
        with open(on_disk, 'rb') as handle:
            self.assertEqual(handle.read(), payload)
        fetched = self.client.get('/' + row['file_path'].replace('\\', '/'))
        self.assertEqual(fetched.status_code, 200)
        self.assertEqual(fetched.data, payload)
        fetched.close()

        r = self.client.delete('/api/teacher/materials/%d' % mat_id, headers=headers)
        self.assertTrue(json.loads(r.data)['success'])
        self.assertFalse(os.path.isfile(on_disk), '删除后文件必须真的从磁盘上消失')

    def test_video_extension_is_judged_as_video(self):
        sid = self._login('teacher_demo')
        course_id = self._create_course(sid)
        uploaded = self.client.post(
            '/api/teacher/courses/%d/materials' % course_id,
            data={'file': (io.BytesIO(b'not really a video'), 't16_probe.mp4')},
            headers={'X-Session-Id': sid})
        self.assertEqual(uploaded.status_code, 200)
        mat_id = json.loads(uploaded.data)['id']
        row = next(r for r in courses_db.get_course_materials(course_id) if r['id'] == mat_id)
        self.assertEqual(row['material_type'], 'video')
        self.client.delete('/api/teacher/materials/%d' % mat_id,
                           headers={'X-Session-Id': sid})

    def test_unknown_extension_is_judged_as_other(self):
        sid = self._login('teacher_demo')
        course_id = self._create_course(sid)
        uploaded = self.client.post(
            '/api/teacher/courses/%d/materials' % course_id,
            data={'file': (io.BytesIO(b'whatever'), 't16_probe.xyz')},
            headers={'X-Session-Id': sid})
        self.assertEqual(uploaded.status_code, 200)
        mat_id = json.loads(uploaded.data)['id']
        row = next(r for r in courses_db.get_course_materials(course_id) if r['id'] == mat_id)
        self.assertEqual(row['material_type'], 'other')
        self.client.delete('/api/teacher/materials/%d' % mat_id,
                           headers={'X-Session-Id': sid})

    def test_missing_file_and_empty_filename_are_rejected(self):
        sid = self._login('teacher_demo')
        headers = {'X-Session-Id': sid}
        course_id = self._create_course(sid)
        r = self.client.post('/api/teacher/courses/%d/materials' % course_id,
                             data={}, headers=headers)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(json.loads(r.data)['message'], '请选择文件')
        r = self.client.post('/api/teacher/courses/%d/materials' % course_id,
                             data={'file': (io.BytesIO(b'x'), '')}, headers=headers)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(json.loads(r.data)['message'], '文件名为空')

    def test_uploaded_filename_gets_a_timestamp_prefix(self):
        """文件名带时间戳前缀，避免同名文件互相覆盖。"""
        sid = self._login('teacher_demo')
        course_id = self._create_course(sid)
        uploaded = self.client.post(
            '/api/teacher/courses/%d/materials' % course_id,
            data={'file': (io.BytesIO(b'x'), 't16_probe.pdf')},
            headers={'X-Session-Id': sid})
        mat_id = json.loads(uploaded.data)['id']
        row = next(r for r in courses_db.get_course_materials(course_id) if r['id'] == mat_id)
        self.assertTrue(row['file_path'].endswith('_t16_probe.pdf'))
        self.client.delete('/api/teacher/materials/%d' % mat_id,
                           headers={'X-Session-Id': sid})


class Model3dTest(TeacherDomainTestBase):
    """3D 模型管理：格式白名单、上传往返、删除。"""

    def _cleanup(self):
        conn = get_connection()
        rows = conn.execute(
            "SELECT id, file_path FROM models_3d "
            "WHERE title LIKE '__T16%' OR title LIKE '__T17%'").fetchall()
        conn.close()
        for row in rows:
            courses_db.delete_model_3d(row['id'])
            full = os.path.join(repo_paths.REPO_ROOT, row['file_path'])
            if os.path.isfile(full):
                os.remove(full)

    def _upload(self, session_id, filename, content, **fields):
        data = {'file': (io.BytesIO(content), filename)}
        data.update(fields)
        return self.client.post('/api/teacher/models-3d', data=data,
                                headers={'X-Session-Id': session_id})

    def test_model_upload_round_trip_and_delete(self):
        self.addCleanup(self._cleanup)
        sid = self._login('teacher_demo')
        payload = b'glTF T16 repo-root path probe'
        uploaded = self._upload(sid, 't16_probe_model.glb', payload,
                                title='__T16模型__', description='probe', craft_type='广绣')
        self.assertEqual(uploaded.status_code, 200)
        body = json.loads(uploaded.data)
        self.assertTrue(body['success'])
        self.assertIn('等待审核', body['message'])
        model_id = body['id']

        conn = get_connection()
        row = conn.execute("SELECT * FROM models_3d WHERE id = ?", (model_id,)).fetchone()
        conn.close()
        self.assertEqual(row['file_size'], len(payload))
        self.assertEqual(row['teacher_id'], 'teacher_demo')
        parts = row['file_path'].replace('\\', '/').split('/')
        self.assertEqual(parts[:2], ['uploads', 'models_3d'], row['file_path'])

        on_disk = os.path.join(repo_paths.REPO_ROOT, row['file_path'])
        self.assertTrue(os.path.isfile(on_disk))
        fetched = self.client.get('/' + row['file_path'].replace('\\', '/'))
        self.assertEqual(fetched.status_code, 200)
        self.assertEqual(fetched.data, payload)
        fetched.close()

        models = json.loads(self.client.get(
            '/api/teacher/models-3d', headers={'X-Session-Id': sid}).data)['models']
        self.assertIn(model_id, [m['id'] for m in models])

        r = self.client.delete('/api/teacher/models-3d/%d' % model_id,
                               headers={'X-Session-Id': sid})
        self.assertTrue(json.loads(r.data)['success'])
        self.assertFalse(os.path.isfile(on_disk))

    def test_unsupported_extension_is_rejected(self):
        self.addCleanup(self._cleanup)
        sid = self._login('teacher_demo')
        r = self._upload(sid, 't16_probe.exe', b'MZ', title='__T16坏格式__')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(json.loads(r.data)['message'],
                         '不支持的文件格式，仅支持 glb/gltf/obj/fbx/stl/dae/ply/usdz')

    def test_empty_filename_is_rejected(self):
        self.addCleanup(self._cleanup)
        sid = self._login('teacher_demo')
        r = self._upload(sid, '', b'', title='__T16空名__')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(json.loads(r.data)['message'], '文件名为空')

    def test_missing_file_is_rejected(self):
        self.addCleanup(self._cleanup)
        sid = self._login('teacher_demo')
        r = self.client.post('/api/teacher/models-3d', data={},
                             headers={'X-Session-Id': sid})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(json.loads(r.data)['message'], '请选择模型文件')

    def test_title_defaults_to_the_filename(self):
        self.addCleanup(self._cleanup)
        sid = self._login('teacher_demo')
        uploaded = self._upload(sid, 't16_probe_default.glb', b'glTF')
        self.assertEqual(uploaded.status_code, 200)
        model_id = json.loads(uploaded.data)['id']
        conn = get_connection()
        row = conn.execute("SELECT title FROM models_3d WHERE id = ?", (model_id,)).fetchone()
        conn.close()
        self.assertEqual(row['title'], 't16_probe_default.glb')
        self.client.delete('/api/teacher/models-3d/%d' % model_id,
                           headers={'X-Session-Id': sid})

    def test_list_only_contains_the_current_teachers_models(self):
        self.addCleanup(self._cleanup)
        other_id = courses_db.create_model_3d(
            '__T17其他教师模型__', '', '', 'uploads/models_3d/other.glb',
            'other.glb', 4, 'another_teacher')
        own_id = courses_db.create_model_3d(
            '__T17本人模型__', '', '', 'uploads/models_3d/own.glb',
            'own.glb', 4, 'teacher_demo')

        sid = self._login('teacher_demo')
        models = json.loads(self.client.get(
            '/api/teacher/models-3d',
            headers={'X-Session-Id': sid}).data)['models']
        ids = [model['id'] for model in models]
        self.assertIn(own_id, ids)
        self.assertNotIn(other_id, ids)

    def test_teacher_cannot_delete_another_teachers_model(self):
        self.addCleanup(self._cleanup)
        file_path = 'uploads/models_3d/__T17_other_teacher.glb'
        full_path = os.path.join(repo_paths.REPO_ROOT, file_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, 'wb') as handle:
            handle.write(b'other')
        other_id = courses_db.create_model_3d(
            '__T17其他教师删除保护__', '', '', file_path,
            '__T17_other_teacher.glb', 5, 'another_teacher')

        sid = self._login('teacher_demo')
        r = self.client.delete(
            '/api/teacher/models-3d/%d' % other_id,
            headers={'X-Session-Id': sid})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(json.loads(r.data)['message'], '只能删除自己上传的模型')
        self.assertTrue(os.path.isfile(full_path))

    def test_approval_publishes_and_delete_removes_the_model_everywhere(self):
        self.addCleanup(self._cleanup)
        sid = self._login('teacher_demo')
        payload = b'glTF T17 public lifecycle'
        uploaded = self._upload(
            sid, 't17_public_lifecycle.glb', payload,
            title='__T17公开生命周期__', craft_type='embroidery')
        self.assertEqual(uploaded.status_code, 200)
        model_id = json.loads(uploaded.data)['id']

        from db_domains import reviews
        review = reviews.get_review_by_content('model_3d', model_id)
        admin = self._login('admin_demo', 'admin123')
        approved = self._json(
            'POST', '/api/admin/reviews/%d/approve' % review['id'], {},
            session_id=admin)
        self.assertEqual(approved.status_code, 200)

        public_before = json.loads(
            self.client.get('/api/teacher/public-models-3d').data)['models']
        self.assertIn(model_id, [model['id'] for model in public_before])

        conn = get_connection()
        row = conn.execute(
            "SELECT file_path FROM models_3d WHERE id = ?", (model_id,)
        ).fetchone()
        conn.close()
        on_disk = os.path.join(repo_paths.REPO_ROOT, row['file_path'])
        self.assertTrue(os.path.isfile(on_disk))

        removed = self.client.delete(
            '/api/teacher/models-3d/%d' % model_id,
            headers={'X-Session-Id': sid})
        self.assertEqual(removed.status_code, 200)
        self.assertFalse(os.path.isfile(on_disk))
        self.assertIsNone(reviews.get_review_by_content('model_3d', model_id))

        public_after = json.loads(
            self.client.get('/api/teacher/public-models-3d').data)['models']
        self.assertNotIn(model_id, [model['id'] for model in public_after])

    def test_rejection_reason_is_visible_to_the_teacher(self):
        self.addCleanup(self._cleanup)
        sid = self._login('teacher_demo')
        uploaded = self._upload(
            sid, 't17_rejected_reason.glb', b'glTF rejected',
            title='__T17驳回理由模型__')
        self.assertEqual(uploaded.status_code, 200)
        model_id = json.loads(uploaded.data)['id']

        from db_domains import reviews
        review = reviews.get_review_by_content('model_3d', model_id)
        admin = self._login('admin_demo', 'admin123')
        rejected = self._json(
            'POST', '/api/admin/reviews/%d/reject' % review['id'],
            {'comment': '模型缺少正面展示'}, session_id=admin)
        self.assertEqual(rejected.status_code, 200)

        models = json.loads(self.client.get(
            '/api/teacher/models-3d',
            headers={'X-Session-Id': sid}).data)['models']
        row = next(model for model in models if model['id'] == model_id)
        self.assertEqual(row['review_status'], 'rejected')
        self.assertEqual(row['review_comment'], '模型缺少正面展示')
        self.assertIn('reviewed_at', row)


class HealthCheckTest(TeacherDomainTestBase):
    """健康检查：匿名可读，是 e2e webServer 的就绪探针。"""

    def test_health_is_public_and_has_the_documented_shape(self):
        r = self.client.get('/api/health')
        self.assertEqual(r.status_code, 200)
        body = json.loads(r.data)
        self.assertTrue(body['success'])
        self.assertTrue(body['healthy'])
        self.assertEqual(body['service'], '粤乡智匠API')
        self.assertIn('timestamp', body)


class RoleBoundaryTest(TeacherDomainTestBase):
    """角色边界：教师端接口只允许 teacher 与 super_admin。"""

    # require_role 装饰器把关的路由：未登录 401
    PROTECTED_401 = [
        ('/api/teacher/dashboard', 'GET'),
        ('/api/teacher/students', 'GET'),
        ('/api/teacher/students/STU001', 'GET'),
        ('/api/teacher/linkable-accounts', 'GET'),
        ('/api/teacher/reports/generate', 'POST'),
        ('/api/teacher/announcements', 'GET'),
        ('/api/teacher/assignments/grade', 'POST'),
        ('/api/teacher/trainings', 'GET'),
        ('/api/teacher/analytics', 'GET'),
        ('/api/teacher/models-3d', 'GET'),
    ]

    # 课程与材料这几条是函数内 inline 守卫（get_session_user + 角色判断），
    # 未登录与角色不符都返回 403，与装饰器的 401/403 分工不同。拆分前就是这样，
    # 这里按实际行为断言，不改成统一形态。
    PROTECTED_403 = [
        ('/api/teacher/courses', 'GET'),
        ('/api/teacher/courses', 'POST'),
        ('/api/teacher/courses/1', 'PUT'),
        ('/api/teacher/courses/1', 'DELETE'),
        ('/api/teacher/courses/1/materials', 'POST'),
        ('/api/teacher/materials/1', 'DELETE'),
    ]

    def test_anonymous_is_401_everywhere(self):
        for path, method in self.PROTECTED_401:
            r = self.client.open(path, method=method, data='{}',
                                 content_type='application/json')
            self.assertEqual(r.status_code, 401, path)
            self.assertEqual(json.loads(r.data)['message'], '请先登录', path)

    def test_invalid_session_is_401_everywhere(self):
        for path, method in self.PROTECTED_401:
            r = self.client.open(path, method=method, data='{}',
                                 content_type='application/json',
                                 headers={'X-Session-Id': 'no-such-session'})
            self.assertEqual(r.status_code, 401, path)

    def test_student_is_403_everywhere(self):
        sid = self._login('student_demo')
        for path, method in self.PROTECTED_401 + self.PROTECTED_403:
            r = self.client.open(path, method=method, data='{}',
                                 content_type='application/json',
                                 headers={'X-Session-Id': sid})
            self.assertEqual(r.status_code, 403, path)
            self.assertEqual(json.loads(r.data)['message'], '权限不足', path)

    def test_enterprise_and_government_are_403(self):
        for account in ('enterprise_demo', 'gov_demo'):
            sid = self._login(account)
            r = self.client.get('/api/teacher/students', headers={'X-Session-Id': sid})
            self.assertEqual(r.status_code, 403, account)

    def test_suspended_account_cannot_keep_operating(self):
        """停用账号：先拿到会话，再把账号停用，带原会话访问必须被 403 拦下。

        不能反过来先停用再登录：登录接口本身就认 status='suspended'，停用后根本
        拿不到会话，那样验证到的是登录分支而不是守卫分支。这里的顺序是
        真实世界里「账号在使用中被停用」的场景。
        """
        self.addCleanup(self._restore, 'teacher_demo')
        sid = self._login('teacher_demo')
        conn = get_connection()
        conn.execute("UPDATE users SET status='suspended' WHERE username='teacher_demo'")
        conn.commit()
        conn.close()

        r = self.client.get('/api/teacher/dashboard', headers={'X-Session-Id': sid})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(json.loads(r.data)['message'], '账号已被停用')

    def _restore(self, username):
        conn = get_connection()
        conn.execute("UPDATE users SET status='active' WHERE username = ?", (username,))
        conn.commit()
        conn.close()


class TeacherBlueprintRegistrationTest(unittest.TestCase):
    """蓝图注册：两个新域进工厂注册表，静态兜底仍排在最后。"""

    def test_new_blueprints_come_from_the_domain_packages(self):
        from domains import teaching_support_bp, teacher_bp
        from app import app
        self.assertEqual(teacher_bp.name, 'teacher')
        self.assertEqual(teaching_support_bp.name, 'teaching_support')
        self.assertIn(teacher_bp.name, app.blueprints)
        self.assertIn(teaching_support_bp.name, app.blueprints)

    def test_new_blueprints_precede_the_static_catch_all(self):
        from app import app
        self.assertEqual(list(app.blueprints)[-1], 'static_files', list(app.blueprints))
        for name in ('teacher', 'teaching_support'):
            self.assertLess(list(app.blueprints).index(name),
                            list(app.blueprints).index('static_files'),
                            '%s 必须注册在静态兜底之前' % name)


if __name__ == '__main__':
    unittest.main()
