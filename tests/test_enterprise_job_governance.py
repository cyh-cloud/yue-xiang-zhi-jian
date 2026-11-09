# -*- coding: utf-8 -*-
"""企业岗位治理：发布上限、审核复查、关闭与删除、停用联动。

这些用例对应 2026-11-05 的一轮企业视角审计，每条都先构造出「原本能绕过」的路径，
再断言它已被堵住：

  1. 编辑岗位会把审核状态打回 pending，用「在招数」计上限就能靠编辑无限追加；
  2. 只在创建时拦上限，逐条通过审核仍能超限；
  3. 删除有投递的岗位会留下孤儿投递（学员端整条消失）；
  4. 停用企业后岗位仍挂在公网，还带「已认证」标。
"""

import io
import json
import os
import sys
import unittest
import uuid

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(REPO_ROOT, 'backend')
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from db_connection import get_connection  # noqa: E402
from shared.credit_code import CHARSET, WEIGHTS  # noqa: E402
from shared.enterprise_limits import QUALIFICATION_LICENSE_DIR  # noqa: E402


def _valid_credit_code(seed=None):
    """按 GB 32100-2015 算一串自洽的 18 位代码。

    seed 必须每个用例都不同：库里已有演示企业的 approved 记录，代码相同会被
    「同一张执照只能认证一个账号」的检查拦下，测试就测不到自己想测的东西。
    """
    if seed is None:
        seed = '91' + ''.join(uuid.uuid4().hex[i] for i in range(15)).upper()
        seed = ''.join(ch if ch in CHARSET else '0' for ch in seed)
    total = sum(CHARSET.index(ch) * WEIGHTS[i] for i, ch in enumerate(seed))
    check = 31 - (total % 31)
    return seed + CHARSET[0 if check == 31 else check]


class JobGovernanceBase(unittest.TestCase):
    def setUp(self):
        from app import app
        from db_init import init_db
        init_db()
        self.client = app.test_client()
        self.username = 'jobgov_%s' % uuid.uuid4().hex[:8]
        register = self.client.post('/api/auth/register', json={
            'username': self.username,
            'password': '123456',
            'name': '岗位治理测试',
            'role': 'enterprise',
            'company_name': '岗位治理测试有限公司',
            'phone': '13700000000',
            'region': '广州',
        })
        self.assertEqual(register.status_code, 200, register.data)
        self.sid = self._login(self.username, '123456')
        self.admin_sid = self._login('admin_demo', 'admin123')

    def tearDown(self):
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT license_file FROM enterprise_qualifications WHERE user_id = ?",
                (self.username,)).fetchall()
            for row in rows:
                if row['license_file']:
                    path = os.path.join(QUALIFICATION_LICENSE_DIR, row['license_file'])
                    if os.path.isfile(path):
                        os.remove(path)
            conn.execute("DELETE FROM job_applications WHERE job_id IN "
                         "(SELECT id FROM job_listings WHERE enterprise_id = ?)",
                         (self.username,))
            job_ids = [row['id'] for row in conn.execute(
                "SELECT id FROM job_listings WHERE enterprise_id = ?",
                (self.username,)).fetchall()]
            conn.execute("DELETE FROM job_listings WHERE enterprise_id = ?",
                         (self.username,))
            conn.commit()
            # 审核记录走 reviews 域的删除入口：content_reviews 的属主是它，
            # 测试也不该自己写那条 DELETE（跨域视图测试会扫全仓库的 SQL 字面量）。
            from db_domains import reviews as reviews_db
            for job_id in job_ids:
                reviews_db.delete_reviews_for('job', job_id)
            conn.execute("DELETE FROM enterprise_qualifications WHERE user_id = ?",
                         (self.username,))
            conn.execute("DELETE FROM notifications WHERE user_id = ?",
                         (self.username,))
            conn.execute("DELETE FROM users WHERE username = ?", (self.username,))
            conn.commit()
        finally:
            conn.close()

    # ---- 基础动作 ----

    def _login(self, username, password):
        body = json.loads(self.client.post(
            '/api/auth/login',
            json={'username': username, 'password': password}).data)
        return body['session_id']

    def _h(self, sid=None):
        return {'X-Session-Id': sid or self.sid}

    def _create_job(self, title='测试岗位'):
        return self.client.post('/api/enterprise/jobs', json={
            'title': title,
            'salary': '6000-9000',
            'description': '岗位治理测试',
            'location': '广州',
            'category': '种植',
            'requirements': [],
        }, headers=self._h())

    def _job_id(self, response):
        return json.loads(response.data)['id']

    def _edit_job(self, job_id):
        return self.client.put('/api/enterprise/jobs/%s' % job_id, json={
            'title': '改过的岗位',
        }, headers=self._h())

    def _approve_job(self, job_id):
        """找到该岗位的待审记录，走审核通过接口。"""
        conn = get_connection()
        row = conn.execute(
            "SELECT id FROM content_reviews WHERE content_type='job' "
            "AND content_id=? ORDER BY id DESC LIMIT 1", (job_id,)).fetchone()
        conn.close()
        self.assertIsNotNone(row, '岗位没有审核记录')
        return self.client.post('/api/admin/reviews/%s/approve' % row['id'],
                                headers=self._h(self.admin_sid))

    def _insert_job(self, title, review_status='pending'):
        """绕过接口直接插一条岗位，用于构造「接口本该拦住」的场景。"""
        conn = get_connection()
        cur = conn.execute(
            "INSERT INTO job_listings (title, company, salary, requirements, "
            "description, enterprise_id, review_status, is_closed, posted_at) "
            "VALUES (?, ?, '', '[]', '', ?, ?, 0, datetime('now','localtime'))",
            (title, '岗位治理测试有限公司', self.username, review_status))
        conn.commit()
        job_id = cur.lastrowid
        conn.close()
        return job_id

    def _add_review(self, job_id):
        conn = get_connection()
        conn.execute(
            "INSERT INTO content_reviews (content_type, content_id, submitter_id) "
            "VALUES ('job', ?, ?)", (job_id, self.username))
        conn.commit()
        conn.close()

    def _submit_qualification(self, credit_code=None):
        payload = {
            'company_name': '岗位治理测试有限公司',
            'credit_code': credit_code or _valid_credit_code(),
            'license': (io.BytesIO(b'\xff\xd8\xff\xe0' + b'0' * 512), 'license.jpg'),
        }
        return self.client.post('/api/enterprise/qualification', data=payload,
                                content_type='multipart/form-data', headers=self._h())

    def _approve_qualification(self, comment=''):
        body = json.loads(self.client.get(
            '/api/admin/qualifications?status=pending',
            headers=self._h(self.admin_sid)).data)
        ids = [item['id'] for item in body['items']
               if item['user_id'] == self.username]
        self.assertTrue(ids, '没有待审的资质')
        return self.client.post(
            '/api/admin/qualifications/%s/review' % ids[0],
            json={'status': 'approved', 'comment': comment},
            headers=self._h(self.admin_sid))


class JobQuotaTest(JobGovernanceBase):
    def test_editing_a_job_does_not_free_the_quota(self):
        first = self._create_job()
        self.assertEqual(first.status_code, 200, first.data)
        job_id = self._job_id(first)

        # 编辑会把审核状态打回 pending；用「在招数」计上限时这里额度会归零
        self._edit_job(job_id)
        second = self._create_job('第二条')
        self.assertEqual(second.status_code, 403,
                         '编辑岗位不应腾出未认证企业的发布额度')
        self.assertEqual(json.loads(second.data)['code'], 'qualification_required')

    def test_approval_rechecks_the_quota(self):
        """两条待审岗位逐条通过时，第二条必须被上限拦住。"""
        first = self._insert_job('待审岗位一')
        second = self._insert_job('待审岗位二')
        self._add_review(first)
        self._add_review(second)

        ok = self._approve_job(first)
        self.assertEqual(ok.status_code, 200, ok.data)

        blocked = self._approve_job(second)
        self.assertEqual(blocked.status_code, 409)
        self.assertEqual(json.loads(blocked.data)['code'], 'qualification_required')

    def test_verified_enterprise_is_not_capped(self):
        self.assertTrue(self._submit_qualification().status_code, 200)
        self.assertEqual(self._approve_qualification().status_code, 200)

        self.assertEqual(self._create_job('一').status_code, 200)
        self.assertEqual(self._create_job('二').status_code, 200)


class JobCloseAndDeleteTest(JobGovernanceBase):
    def _approved_job_with_application(self):
        job_id = self._job_id(self._create_job())
        self._approve_job(job_id)
        conn = get_connection()
        conn.execute("INSERT INTO job_applications (user_id, job_id) "
                     "VALUES ('student_demo', ?)", (job_id,))
        conn.commit()
        conn.close()
        return job_id

    def test_delete_is_rejected_when_applications_exist(self):
        job_id = self._approved_job_with_application()
        response = self.client.delete('/api/enterprise/jobs/%s' % job_id,
                                      headers=self._h())
        self.assertEqual(response.status_code, 409)
        self.assertEqual(json.loads(response.data)['code'], 'has_applications')

        conn = get_connection()
        left = conn.execute("SELECT COUNT(*) FROM job_applications WHERE job_id = ?",
                            (job_id,)).fetchone()[0]
        conn.close()
        self.assertEqual(left, 1, '被拒绝的删除不能留下半截数据')

    def test_closing_hides_the_job_but_keeps_applications(self):
        job_id = self._approved_job_with_application()

        closed = self.client.post('/api/enterprise/jobs/%s/close' % job_id,
                                  headers=self._h())
        self.assertEqual(closed.status_code, 200, closed.data)

        public = json.loads(self.client.get('/api/employment/jobs').data)['jobs']
        self.assertNotIn(job_id, [job['id'] for job in public], '已关闭岗位不应出现在学员端')

        detail = self.client.get('/api/employment/jobs/%s' % job_id)
        self.assertEqual(detail.status_code, 404, '直链也不能绕过关闭状态')

        conn = get_connection()
        left = conn.execute("SELECT COUNT(*) FROM job_applications WHERE job_id = ?",
                            (job_id,)).fetchone()[0]
        conn.close()
        self.assertEqual(left, 1, '关闭岗位必须保留投递记录')

        stats = json.loads(self.client.get('/api/enterprise/stats',
                                           headers=self._h()).data)['stats']
        self.assertEqual(stats['total_jobs'], 0, '已关闭岗位不应算在招')

        reopened = self.client.post('/api/enterprise/jobs/%s/reopen' % job_id,
                                    headers=self._h())
        self.assertEqual(reopened.status_code, 200, reopened.data)
        public = json.loads(self.client.get('/api/employment/jobs').data)['jobs']
        self.assertIn(job_id, [job['id'] for job in public], '重新开放后应恢复展示')


class SuspendedEnterpriseTest(JobGovernanceBase):
    def test_suspended_enterprise_jobs_disappear_from_public_list(self):
        job_id = self._job_id(self._create_job())
        self._approve_job(job_id)

        public = json.loads(self.client.get('/api/employment/jobs').data)['jobs']
        self.assertIn(job_id, [job['id'] for job in public])

        conn = get_connection()
        conn.execute("UPDATE users SET status='suspended' WHERE username=?",
                     (self.username,))
        conn.commit()
        conn.close()

        public = json.loads(self.client.get('/api/employment/jobs').data)['jobs']
        self.assertNotIn(job_id, [job['id'] for job in public],
                         '停用企业的岗位必须一并下线')

        detail = self.client.get('/api/employment/jobs/%s' % job_id)
        self.assertEqual(detail.status_code, 404)

        apply = self.client.post('/api/employment/apply', json={'job_id': job_id},
                                 headers=self._h(self._login('student_demo', '123456')))
        self.assertIn('不存在或尚未通过审核', json.loads(apply.data)['message'])


class QualificationIntegrityTest(JobGovernanceBase):
    def test_same_credit_code_cannot_be_used_by_two_accounts(self):
        code = _valid_credit_code()
        self.assertEqual(self._submit_qualification(code).status_code, 200)

        # 换一个账号提交同一张执照
        other = 'jobgov_%s' % uuid.uuid4().hex[:8]
        self.client.post('/api/auth/register', json={
            'username': other, 'password': '123456', 'name': '另一家',
            'role': 'enterprise', 'company_name': '另一家有限公司'})
        sid = self._login(other, '123456')
        response = self.client.post('/api/enterprise/qualification', data={
            'company_name': '另一家有限公司',
            'credit_code': code,
            'license': (io.BytesIO(b'\xff\xd8\xff\xe0' + b'0' * 512), 'l.jpg'),
        }, content_type='multipart/form-data', headers=self._h(sid))
        self.assertEqual(response.status_code, 409)
        self.assertIn('已被其他企业账号使用', json.loads(response.data)['message'])

        conn = get_connection()
        conn.execute("DELETE FROM enterprise_qualifications WHERE user_id = ?",
                     (other,))
        conn.execute("DELETE FROM users WHERE username = ?", (other,))
        conn.commit()
        conn.close()

    def test_account_with_qualification_cannot_be_deleted(self):
        self._submit_qualification()
        response = self.client.delete('/api/admin/users/%s' % self.username,
                                      headers=self._h(self.admin_sid))
        self.assertEqual(response.status_code, 409,
                         '有资质记录的账号应改走停用，不能直接删除')
        body = json.loads(response.data)
        labels = [item['label'] for item in body.get('relations', [])]
        self.assertIn('企业资质记录', labels)

    def test_withdraw_pending_then_resubmit(self):
        self.assertEqual(self._submit_qualification().status_code, 200)

        withdrawn = self.client.post('/api/enterprise/qualification/withdraw',
                                     headers=self._h())
        self.assertEqual(withdrawn.status_code, 200, withdrawn.data)

        status = json.loads(self.client.get('/api/enterprise/qualification',
                                            headers=self._h()).data)
        self.assertEqual(status['status'], 'withdrawn')
        self.assertEqual(status['status_label'], '已撤回')
        self.assertFalse(status['verified'])

        again = self._submit_qualification()
        self.assertEqual(again.status_code, 200, '撤回后应允许重新提交')

    def test_approval_writes_company_name_back_to_the_account(self):
        self._submit_qualification()
        self.assertEqual(self._approve_qualification().status_code, 200)

        conn = get_connection()
        row = conn.execute("SELECT company_name FROM users WHERE username = ?",
                           (self.username,)).fetchone()
        conn.close()
        self.assertEqual(row['company_name'], '岗位治理测试有限公司')


class AdminQueueIntegrityTest(JobGovernanceBase):
    def test_orphan_reviews_are_hidden_and_not_counted(self):
        """内容被删后残留的审核记录不能出现在队列里，也不能计入页签数量。

        2026-11-05 实测：测试直接删岗位留下 48 条孤儿记录，管理端页签显示
        46 条待审核、点进去只有「岗位 #358」没有正文，也无从驳回。
        """
        job_id = self._job_id(self._create_job())
        before = json.loads(self.client.get(
            '/api/admin/reviews?status=pending',
            headers=self._h(self.admin_sid)).data)
        self.assertIn(job_id, [item['content_id'] for item in before['reviews']],
                      '刚提交的岗位应出现在待审核队列')

        conn = get_connection()
        conn.execute("DELETE FROM job_listings WHERE id = ?", (job_id,))
        conn.commit()
        conn.close()
        try:
            after = json.loads(self.client.get(
                '/api/admin/reviews?status=pending',
                headers=self._h(self.admin_sid)).data)
            self.assertNotIn(job_id,
                             [item['content_id'] for item in after['reviews']],
                             '内容已删除的审核记录不应下发')
            self.assertEqual(after['counts']['pending'],
                             before['counts']['pending'] - 1,
                             '孤儿记录不能计入页签数量')
        finally:
            from db_domains import reviews as reviews_db
            reviews_db.delete_reviews_for('job', job_id)


if __name__ == '__main__':
    unittest.main()
