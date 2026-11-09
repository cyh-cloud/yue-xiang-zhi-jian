# -*- coding: utf-8 -*-
"""企业资质认证：提交、审核、有效期与岗位发布门禁。

覆盖四类行为：

1. 提交侧的格式校验（信用代码校验位）与「同一时刻只允许一份在审」；
2. 对外视图不泄漏证件路径，信用代码脱敏；
3. 审核侧的权限（只有超管）、驳回必须有理由、不能重复裁定；
4. 门禁：未认证企业最多 1 个在招岗位，认证通过后解除；公开岗位列表带认证标识。

测试自建企业账号与岗位，结束全部清掉（含私有目录里的证件照文件）。
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
    """按 GB 32100-2015 算出一串自洽的 18 位代码（不对应真实企业）。

    每个用例取不同的 seed：库里已有演示企业的已认证记录，代码撞上会被
    「同一张执照只能认证一个账号」的检查拦住。
    """
    if seed is None:
        seed = '91' + uuid.uuid4().hex[:15].upper()
    total = sum(CHARSET.index(ch) * WEIGHTS[i] for i, ch in enumerate(seed))
    check = 31 - (total % 31)
    if check == 31:
        check = 0
    return seed + CHARSET[check]


class QualificationBase(unittest.TestCase):
    def setUp(self):
        from app import app
        from db_init import init_db
        init_db()
        self.client = app.test_client()
        self.username = 'qual_%s' % uuid.uuid4().hex[:8]
        self.password = '123456'
        self.created_jobs = []
        response = self.client.post('/api/auth/register', json={
            'username': self.username,
            'password': self.password,
            'name': '资质测试企业',
            'role': 'enterprise',
            'company_name': '资质测试有限公司',
            'phone': '13900000000',
            'region': '广州',
        })
        self.assertEqual(response.status_code, 200, response.data)
        self.enterprise_sid = self._login(self.username, self.password)
        self.admin_sid = self._login('admin_demo', 'admin123')

    def tearDown(self):
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT license_file FROM enterprise_qualifications WHERE user_id = ?",
                (self.username,)).fetchall()
            for row in rows:
                name = row['license_file'] if row['license_file'] is not None else None
                if name:
                    path = os.path.join(QUALIFICATION_LICENSE_DIR, name)
                    if os.path.isfile(path):
                        os.remove(path)
            conn.execute("DELETE FROM enterprise_qualifications WHERE user_id = ?",
                         (self.username,))
            conn.execute("DELETE FROM notifications WHERE user_id = ?",
                         (self.username,))
            job_ids = [row['id'] for row in conn.execute(
                "SELECT id FROM job_listings WHERE enterprise_id = ?",
                (self.username,)).fetchall()]
            conn.execute("DELETE FROM job_applications WHERE job_id IN "
                         "(SELECT id FROM job_listings WHERE enterprise_id = ?)",
                         (self.username,))
            conn.execute("DELETE FROM job_listings WHERE enterprise_id = ?",
                         (self.username,))
            conn.execute("DELETE FROM users WHERE username = ?", (self.username,))
            conn.commit()
            # 审核记录必须走 reviews 域的删除入口：直接删岗位而不清审核记录，
            # 管理端会堆出一批点不进去、也驳不掉的孤儿卡片（2026-11-05 实测 48 条）。
            from db_domains import reviews as reviews_db
            for job_id in job_ids:
                reviews_db.delete_reviews_for('job', job_id)
        finally:
            conn.close()

    def _login(self, username, password):
        response = self.client.post('/api/auth/login',
                                    json={'username': username, 'password': password})
        return json.loads(response.data)['session_id']

    def _as_enterprise(self):
        return {'X-Session-Id': self.enterprise_sid}

    def _as_admin(self):
        return {'X-Session-Id': self.admin_sid}

    def _submit(self, headers=None, **overrides):
        payload = {
            'company_name': '资质测试有限公司',
            'credit_code': _valid_credit_code(),
            'legal_person': '陈测试',
            'contact_phone': '13900000000',
            'address': '广东省广州市',
            'industry': '农业',
            'company_size': '10-50人',
            'license': (io.BytesIO(b'\xff\xd8\xff\xe0' + b'0' * 1024), 'license.jpg'),
        }
        payload.update(overrides)
        return self.client.post('/api/enterprise/qualification', data=payload,
                                content_type='multipart/form-data',
                                headers=headers or self._as_enterprise())


class QualificationSubmitTest(QualificationBase):
    def test_invalid_credit_code_is_rejected(self):
        code = _valid_credit_code()
        bad = code[:-1] + ('0' if code[-1] != '0' else '1')
        response = self._submit(credit_code=bad)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(json.loads(response.data)['code'], 'invalid_credit_code')

    def test_submit_then_duplicate_is_rejected(self):
        response = self._submit()
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(json.loads(response.data)['success'])

        again = self._submit()
        self.assertEqual(again.status_code, 409)
        self.assertEqual(json.loads(again.data)['code'], 'conflict')

    def test_status_view_masks_credit_code_and_hides_file_path(self):
        code = _valid_credit_code()
        self._submit(credit_code=code)
        body = json.loads(self.client.get('/api/enterprise/qualification',
                                          headers=self._as_enterprise()).data)
        self.assertEqual(body['status'], 'pending')
        self.assertFalse(body['verified'])
        record = body['record']
        self.assertNotIn('license_file', record, '对外视图不能带证件路径')
        self.assertTrue(record['has_license'])
        self.assertEqual(record['credit_code_masked'][:4], code[:4])
        self.assertEqual(record['credit_code_masked'][-4:], code[-4:])
        self.assertIn('*', record['credit_code_masked'])
        self.assertNotEqual(record['credit_code_masked'], code,
                            '中间 10 位必须打码，不能原样下发')

    def test_license_is_served_only_to_owner(self):
        self._submit()
        own = self.client.get('/api/enterprise/qualification/license',
                              headers=self._as_enterprise())
        self.assertEqual(own.status_code, 200)
        self.assertGreater(len(own.data), 0)
        own.close()

        anonymous = self.client.get('/api/enterprise/qualification/license')
        self.assertEqual(anonymous.status_code, 403)

    def test_static_route_does_not_expose_qualification_files(self):
        """证件照不能从静态目录直链拿到（data/ 是整目录拒绝的）。"""
        self._submit()
        conn = get_connection()
        row = conn.execute("SELECT license_file FROM enterprise_qualifications "
                           "WHERE user_id = ?", (self.username,)).fetchone()
        conn.close()
        name = row['license_file']
        for path in ('/data/qualifications/%s' % name,
                     '/qualifications/%s' % name):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 404, path)


class QualificationReviewTest(QualificationBase):
    def _pending_id(self):
        body = json.loads(self.client.get('/api/admin/qualifications?status=pending',
                                          headers=self._as_admin()).data)
        for item in body['items']:
            if item['user_id'] == self.username:
                return item['id']
        self.fail('待审核队列里没有刚提交的记录')

    def test_enterprise_cannot_review(self):
        self._submit()
        qid = self._pending_id()
        response = self.client.post('/api/admin/qualifications/%s/review' % qid,
                                    json={'status': 'approved'},
                                    headers=self._as_enterprise())
        self.assertEqual(response.status_code, 403)

    def test_reject_requires_comment(self):
        self._submit()
        qid = self._pending_id()
        response = self.client.post('/api/admin/qualifications/%s/review' % qid,
                                    json={'status': 'rejected'},
                                    headers=self._as_admin())
        self.assertEqual(response.status_code, 400)

    def test_reject_then_resubmit(self):
        self._submit()
        qid = self._pending_id()
        response = self.client.post('/api/admin/qualifications/%s/review' % qid,
                                    json={'status': 'rejected',
                                          'comment': '营业执照照片不清晰'},
                                    headers=self._as_admin())
        self.assertEqual(response.status_code, 200)

        body = json.loads(self.client.get('/api/enterprise/qualification',
                                          headers=self._as_enterprise()).data)
        self.assertEqual(body['status'], 'rejected')
        self.assertEqual(body['record']['review_comment'], '营业执照照片不清晰')

        # 驳回后可以重交
        again = self._submit()
        self.assertEqual(again.status_code, 200, again.data)

    def test_approve_sets_expiry_and_cannot_be_repeated(self):
        self._submit()
        qid = self._pending_id()
        response = self.client.post('/api/admin/qualifications/%s/review' % qid,
                                    json={'status': 'approved'},
                                    headers=self._as_admin())
        self.assertEqual(response.status_code, 200)

        body = json.loads(self.client.get('/api/enterprise/qualification',
                                          headers=self._as_enterprise()).data)
        self.assertEqual(body['status'], 'approved')
        self.assertTrue(body['verified'])
        self.assertRegex(body['record']['expires_at'], r'^\d{4}-\d{2}-\d{2}$')

        repeat = self.client.post('/api/admin/qualifications/%s/review' % qid,
                                  json={'status': 'approved'},
                                  headers=self._as_admin())
        self.assertEqual(repeat.status_code, 409)


class UnverifiedJobLimitTest(QualificationBase):
    def _create_job(self):
        return self.client.post('/api/enterprise/jobs', json={
            'title': '测试岗位',
            'salary': '5000-8000',
            'description': '用于门禁测试',
            'location': '广州',
            'category': '种植',
            'requirements': ['能吃苦'],
        }, headers=self._as_enterprise())

    def _approve_first_job(self):
        """绕过审核流程直接放行第一条岗位：本用例测的是门禁，不是审核链路。"""
        conn = get_connection()
        conn.execute("UPDATE job_listings SET review_status='approved' "
                     "WHERE enterprise_id = ?", (self.username,))
        conn.commit()
        conn.close()

    def test_unverified_enterprise_is_capped_at_one_active_job(self):
        first = self._create_job()
        self.assertEqual(first.status_code, 200, first.data)
        self._approve_first_job()

        second = self._create_job()
        self.assertEqual(second.status_code, 403)
        self.assertEqual(json.loads(second.data)['code'], 'qualification_required')

    def test_verified_enterprise_can_post_again(self):
        self._submit()
        body = json.loads(self.client.get('/api/admin/qualifications?status=pending',
                                          headers=self._as_admin()).data)
        qid = [item['id'] for item in body['items']
               if item['user_id'] == self.username][0]
        self.client.post('/api/admin/qualifications/%s/review' % qid,
                         json={'status': 'approved'}, headers=self._as_admin())

        self.assertEqual(self._create_job().status_code, 200)
        self._approve_first_job()
        self.assertEqual(self._create_job().status_code, 200,
                         '已认证企业不应再受 1 条上限约束')


class PublicJobVerificationFlagTest(QualificationBase):
    def test_public_job_list_marks_verified_enterprise(self):
        job = self.client.post('/api/enterprise/jobs', json={
            'title': '认证标识测试岗位',
            'salary': '6000-9000',
            'description': '用于公开列表标识',
            'location': '广州',
            'category': '种植',
            'requirements': [],
        }, headers=self._as_enterprise())
        job_id = json.loads(job.data)['id']

        conn = get_connection()
        conn.execute("UPDATE job_listings SET review_status='approved' WHERE id = ?",
                     (job_id,))
        conn.commit()
        conn.close()

        def flag():
            body = json.loads(self.client.get('/api/employment/jobs').data)
            for item in body['jobs']:
                if item['id'] == job_id:
                    return item.get('enterprise_verified')
            self.fail('新岗位没有出现在公开列表里')

        self.assertEqual(flag(), 0, '未认证企业发布的岗位应标记为未认证')

        self._submit()
        body = json.loads(self.client.get('/api/admin/qualifications?status=pending',
                                          headers=self._as_admin()).data)
        qid = [item['id'] for item in body['items']
               if item['user_id'] == self.username][0]
        self.client.post('/api/admin/qualifications/%s/review' % qid,
                         json={'status': 'approved'}, headers=self._as_admin())
        self.assertEqual(flag(), 1, '认证通过后公开列表应带认证标识')


if __name__ == '__main__':
    unittest.main()
