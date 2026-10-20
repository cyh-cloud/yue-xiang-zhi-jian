# -*- coding: utf-8 -*-
"""运营后台农时与病虫害的对外行为测试（T14）。

测试 seam 是 API 层（Flask test client），断言状态码、响应结构与权限结果，
不测模块怎么划分。这里锁住的对外事实，逐条对应票据的验收标准：

1. 运营经接口改一条农事任务，前台接口立即返回新值，无需重启；
2. 标记复核后 verified_by / verified_at 有值，且前台接口输出形状不变；
3. 能按复核时间筛出超期未复核的条目；
4. 学员打 /api/operator/* 返回 401 或 403；
5. operator 打用户与审核接口仍为 403。

每条在下面都有同名用例。

⚠️ 本文件跑在真实库上（与既有测试同一口径）。所有写用例都在 finally 里
把库还原：造什么删什么，改什么改回去。理由同 tests/test_agriculture_domain.py
的口径 —— 这里测的就是「读库这条路产出的响应」，mock 掉库会漏掉 JOIN、
JSON 列解析、外键级联这三处真正会出错的地方。
"""

import json
import os
import sys
import unittest

BACKEND = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend')
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from db_connection import get_connection  # noqa: E402
from db_domains import farming  # noqa: E402
from db_domains import pest  # noqa: E402

OPERATOR = ('operator_demo', '123456')
STUDENT = ('student_demo', '123456')
SUPER_ADMIN = ('admin_demo', 'admin123')

# 前台接口。运营改完内容后打这两个，断言「立即生效、无需重启」。
FRONT_FARMING = '/api/agriculture/calendar/lychee'
FRONT_PEST = '/api/agriculture/pest-knowledge'


class OperatorContentTestBase(unittest.TestCase):
    """共用的登录与清理工具。"""

    @classmethod
    def setUpClass(cls):
        from app import app
        cls.app = app
        cls.app.config['TESTING'] = True

    def setUp(self):
        self.client = self.app.test_client()

    def _login(self, account=OPERATOR):
        response = self.client.post('/api/auth/login', data=json.dumps(
            {'username': account[0], 'password': account[1]}),
            content_type='application/json')
        body = json.loads(response.data)
        self.assertTrue(body.get('success'), '登录失败：%s' % body)
        return body['session_id']

    def _headers(self, session_id):
        return {'X-Session-Id': session_id}

    def _post(self, path, payload, session_id):
        return self.client.post(path, data=json.dumps(payload),
                                content_type='application/json',
                                headers=self._headers(session_id))

    def _put(self, path, payload, session_id):
        return self.client.put(path, data=json.dumps(payload),
                               content_type='application/json',
                               headers=self._headers(session_id))

    def _delete(self, path, session_id):
        return self.client.delete(path, headers=self._headers(session_id))

    def _cleanup_sessions(self, *session_ids):
        conn = get_connection()
        for sid in session_ids:
            if sid:
                conn.execute("DELETE FROM user_sessions WHERE session_id = ?", (sid,))
        conn.commit()
        conn.close()

class OperatorFarmingWriteTest(OperatorContentTestBase):
    """农时日历：作物、物候期、任务、来源、分类的增删改。"""

    # ---- 任务 ----

    def test_operator_can_create_update_and_delete_a_task(self):
        """增删改闭环：接口返回的 id 能在库里读到，改完再读也是新值。"""
        sid = self._login()
        try:
            created = self._post('/api/operator/farming/tasks', {
                'product_id': 'lychee', 'title': u'单测临时任务',
                'category': 'manage', 'month': 7, 'task_md': '07-20',
                'priority': 'low', 'description': u'单测造的任务',
                'icon': 'tasks', 'sort_order': 999,
            }, sid)
            self.assertEqual(created.status_code, 200, created.data)
            task_id = json.loads(created.data)['result']
            self.assertIsInstance(task_id, int)

            row = farming.get_farming_task_by_id(task_id)
            self.assertEqual(row['title'], u'单测临时任务')
            self.assertEqual(row['month'], 7)
            self.assertEqual(row['task_md'], '07-20')

            updated = self._put('/api/operator/farming/tasks/%d' % task_id, {
                'title': u'单测临时任务改', 'priority': 'high',
                'description': u'改过的描述',
            }, sid)
            self.assertEqual(updated.status_code, 200, updated.data)
            row = farming.get_farming_task_by_id(task_id)
            self.assertEqual(row['title'], u'单测临时任务改')
            self.assertEqual(row['priority'], 'high')

            deleted = self._delete('/api/operator/farming/tasks/%d' % task_id, sid)
            self.assertEqual(deleted.status_code, 200, deleted.data)
            self.assertIsNone(farming.get_farming_task_by_id(task_id))
        finally:
            conn = get_connection()
            conn.execute("DELETE FROM farming_tasks WHERE title LIKE '单测临时任务%'")
            conn.commit()
            conn.close()
            self._cleanup_sessions(sid)

    def test_front_end_sees_the_new_task_without_a_restart(self):
        """验收 1：运营经接口改一条农事任务，前台接口立即返回新值。"""
        sid = self._login()
        original = None
        try:
            original = next(
                t for t in farming.get_farming_tasks('lychee', month=3)
                if t['title'] != u'单测改标题')
            created = self._put(
                '/api/operator/farming/tasks/%d' % original['id'],
                {'title': u'单测改标题'}, sid)
            self.assertEqual(created.status_code, 200, created.data)

            # 前台接口：同一个进程、同一个 test client，没有重启任何东西
            response = self.client.get(FRONT_FARMING,
                                       query_string={'year': '2026', 'month': '3'})
            self.assertEqual(response.status_code, 200)
            titles = {t['id']: t['title'] for t in json.loads(response.data)['tasks']}
            self.assertEqual(titles[original['id']], u'单测改标题')
        finally:
            if original is not None:
                self._put('/api/operator/farming/tasks/%d' % original['id'],
                          {'title': original['title']}, sid)
            self._cleanup_sessions(sid)

    def test_task_payload_validation_matches_the_front_end(self):
        """验收「内容表单校验与前台一致」：日期、月份、分类、优先级逐条拒绝。"""
        sid = self._login()
        base = {'product_id': 'lychee', 'title': 'x', 'category': 'manage', 'month': 7}
        bad_cases = (
            ({'task_md': '7-05'}, u'日期格式应为 MM-DD，例如 03-15'),
            ({'task_md': '13-01'}, u'日期超出范围：月份 1-12，日期 1-31'),
            # 前台只在 mm == month 时给 date：日期与月份不一致必须拒
            ({'task_md': '08-05'}, u'日期所属月份（08）与任务的月份（7）不一致'),
            ({'category': 'nope'}, u'任务分类不在可选范围内'),
            ({'priority': 'urgent'}, u'优先级只能是 high / medium / low'),
            ({'source_key': 'no-such-source'}, u'来源不存在，请先在来源登记里添加'),
        )
        try:
            for extra, message in bad_cases:
                with self.subTest(payload=extra):
                    payload = dict(base)
                    payload.update(extra)
                    response = self._post('/api/operator/farming/tasks', payload, sid)
                    self.assertEqual(response.status_code, 400, response.data)
                    body = json.loads(response.data)
                    self.assertFalse(body['success'])
                    self.assertEqual(body['message'], message)

            # 缺必填字段同样 400，且不留半条数据
            for key in ('product_id', 'title', 'category', 'month'):
                payload = {k: v for k, v in base.items() if k != key}
                with self.subTest(missing=key):
                    response = self._post('/api/operator/farming/tasks', payload, sid)
                    self.assertEqual(response.status_code, 400, response.data)
            self.assertEqual(
                [t for t in farming.get_farming_tasks('lychee', month=7)
                 if t['title'] == 'x'], [])
        finally:
            conn = get_connection()
            conn.execute("DELETE FROM farming_tasks WHERE title = 'x'")
            conn.commit()
            conn.close()
            self._cleanup_sessions(sid)

    def test_marking_a_task_verified_writes_who_and_when(self):
        """验收 2：标记复核后 verified_by 与 verified_at 有值。"""
        sid = self._login()
        task_id = None
        try:
            created = self._post('/api/operator/farming/tasks', {
                'product_id': 'lychee', 'title': u'单测待复核',
                'category': 'manage', 'month': 9, 'task_md': '09-01',
            }, sid)
            task_id = json.loads(created.data)['result']
            self.assertEqual(farming.get_farming_task_by_id(task_id)['is_verified'], 0)

            response = self._post(
                '/api/operator/farming/tasks/%d/verify' % task_id, {}, sid)
            self.assertEqual(response.status_code, 200, response.data)
            self.assertTrue(json.loads(response.data)['success'])

            row = farming.get_farming_task_by_id(task_id)
            self.assertEqual(row['verified_by'], 'operator_demo')
            self.assertRegex(row['verified_at'],
                             r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$')
            self.assertEqual(row['is_verified'], 1)
        finally:
            if task_id is not None:
                conn = get_connection()
                conn.execute("DELETE FROM farming_tasks WHERE id = ?", (task_id,))
                conn.commit()
                conn.close()
            self._cleanup_sessions(sid)

    def test_verification_does_not_change_the_front_end_response_shape(self):
        """验收 2 后半：标记复核后前台接口输出形状不变。

        复核只填两列，前台任务的键集、类型、空值表示一律不动：
        evidence_level 从 sourced 变 verified 是既有的判定逻辑，不是新字段。
        """
        sid = self._login()
        task_id = None
        try:
            created = self._post('/api/operator/farming/tasks', {
                'product_id': 'lychee', 'title': u'单测形状',
                'category': 'manage', 'month': 9, 'task_md': '09-01',
            }, sid)
            task_id = json.loads(created.data)['result']

            def task_view():
                response = self.client.get(FRONT_FARMING,
                                           query_string={'year': '2026', 'month': '9'})
                self.assertEqual(response.status_code, 200)
                body = json.loads(response.data)
                match = [t for t in body['tasks'] if t['id'] == task_id]
                self.assertEqual(len(match), 1)
                return match[0]

            before = task_view()
            self.assertEqual(before['is_verified'], 0)
            self.assertEqual(before['evidence_level'], 'unsourced')
            keys_before = sorted(before)

            self._post('/api/operator/farming/tasks/%d/verify' % task_id, {}, sid)
            after = task_view()
            self.assertEqual(after['is_verified'], 1)
            self.assertEqual(after['evidence_level'], 'verified')
            self.assertEqual(sorted(after), keys_before, '复核改变了前台任务字段')
            for key in keys_before:
                if key in ('is_verified', 'evidence_level'):
                    continue
                self.assertEqual(after[key], before[key],
                                 '复核顺带动了前台字段 %s' % key)
        finally:
            if task_id is not None:
                conn = get_connection()
                conn.execute("DELETE FROM farming_tasks WHERE id = ?", (task_id,))
                conn.commit()
                conn.close()
            self._cleanup_sessions(sid)

    def test_overdue_filter_finds_stale_and_never_verified_tasks(self):
        """验收 3：能按复核时间筛出超期未复核的条目。"""
        sid = self._login()
        fresh_id = stale_id = never_id = None
        try:
            # 三条任务：刚核的、一年前核的、从没核过的
            fresh_id = json.loads(self._post('/api/operator/farming/tasks', {
                'product_id': 'lychee', 'title': u'单测刚核',
                'category': 'manage', 'month': 1, 'task_md': '01-01',
            }, sid).data)['result']
            stale_id = json.loads(self._post('/api/operator/farming/tasks', {
                'product_id': 'lychee', 'title': u'单测去年核',
                'category': 'manage', 'month': 1, 'task_md': '01-02',
            }, sid).data)['result']
            never_id = json.loads(self._post('/api/operator/farming/tasks', {
                'product_id': 'lychee', 'title': u'单测没核过',
                'category': 'manage', 'month': 1, 'task_md': '01-03',
            }, sid).data)['result']

            conn = get_connection()
            conn.execute("UPDATE farming_tasks SET is_verified = 1, verified_by = ?, "
                         "verified_at = datetime('now', 'localtime') WHERE id = ?",
                         ('operator_demo', fresh_id))
            # 直接写一个 400 天前的时间，绕过 verified_at 的默认值
            conn.execute("UPDATE farming_tasks SET is_verified = 1, verified_by = ?, "
                         "verified_at = datetime('now', 'localtime', '-400 days') "
                         "WHERE id = ?", ('operator_demo', stale_id))
            conn.commit()
            conn.close()

            response = self.client.get('/api/operator/farming/tasks?overdue=1',
                                       headers=self._headers(sid))
            self.assertEqual(response.status_code, 200)
            ids = {t['id'] for t in json.loads(response.data)['tasks']}
            self.assertIn(stale_id, ids, '400 天前核过的任务没被筛出来')
            self.assertIn(never_id, ids, '从没核过的任务没被筛出来')
            self.assertNotIn(fresh_id, ids, '刚核过的任务不该算超期')

            # 数据层口径同一个阈值，不另设一套
            self.assertEqual(farming.REVIEW_STALE_DAYS, 183)
            direct = {t['id'] for t in farming.get_farming_overdue_tasks()}
            self.assertEqual(direct & {stale_id, never_id, fresh_id},
                             {stale_id, never_id})
        finally:
            conn = get_connection()
            conn.execute("DELETE FROM farming_tasks WHERE id IN (?, ?, ?)",
                         (fresh_id, stale_id, never_id))
            conn.commit()
            conn.close()
            self._cleanup_sessions(sid)

    def test_task_list_filters_by_product_and_month(self):
        """列表筛选用的是前台同一条查询，月份不对的不会混进来。"""
        sid = self._login()
        try:
            response = self.client.get(
                '/api/operator/farming/tasks?product_id=lychee&month=7',
                headers=self._headers(sid))
            self.assertEqual(response.status_code, 200)
            tasks = json.loads(response.data)['tasks']
            self.assertTrue(tasks, '荔枝 7 月应有任务')
            for task in tasks:
                self.assertEqual(task['product_id'], 'lychee')
                self.assertEqual(task['month'], 7)
            # 与前台口径同源：前台 calendar 接口同月任务数与这里一致
            front = json.loads(self.client.get(FRONT_FARMING,
                                               query_string={'year': '2026',
                                                             'month': '7'}).data)
            self.assertEqual(len(front['tasks']), len(tasks))
        finally:
            self._cleanup_sessions(sid)

    def test_task_list_without_a_product_returns_every_crop(self):
        """不传 product_id = 下拉选了「全部作物」，必须返回全部作物的任务。

        交付时这条路径是坏的：数据层强制按 product_id 过滤，选「全部作物」只会得到
        一张空表，运营打开农时页看到「暂无数据」，以为平台没有任务。
        """
        sid = self._login()
        try:
            all_tasks = json.loads(self.client.get(
                '/api/operator/farming/tasks', headers=self._headers(sid)).data)['tasks']
            self.assertTrue(all_tasks, '「全部作物」应当返回任务，不是空表')
            self.assertGreater(len({t['product_id'] for t in all_tasks}), 1,
                               '「全部作物」应当跨多个作物，而不是只剩一个')
            # 与某个具体作物的结果对照：单作物结果是全量的真子集
            one = json.loads(self.client.get(
                '/api/operator/farming/tasks?product_id=lychee',
                headers=self._headers(sid)).data)['tasks']
            self.assertTrue(set(t['id'] for t in one) <= set(t['id'] for t in all_tasks))
        finally:
            self._cleanup_sessions(sid)

    def test_overdue_filter_ignores_the_month_filter(self):
        """超期筛选只看复核时间：再按月份收窄会把「该重新核了」漏掉。"""
        sid = self._login()
        try:
            overdue = self.client.get(
                '/api/operator/farming/tasks?overdue=1&product_id=lychee&month=7',
                headers=self._headers(sid))
            self.assertEqual(overdue.status_code, 200)
            months = {t['month'] for t in json.loads(overdue.data)['tasks']}
            self.assertNotEqual(months, {7},
                                '超期筛选被月份收窄了，待复核项被漏掉')
        finally:
            self._cleanup_sessions(sid)

    # ---- 作物 / 物候期 / 来源 / 分类 ----

    def test_operator_can_maintain_products_and_phenophases(self):
        """作物与物候期的增删改，前台目录与日历立即跟着变。"""
        sid = self._login()
        pid = 't14_probe_product'
        try:
            created = self._post('/api/operator/farming/products', {
                'id': pid, 'name': u'单测作物', 'summary': u'单测',
            }, sid)
            self.assertEqual(created.status_code, 200, created.data)
            listed = {p['id'] for p in json.loads(
                self.client.get('/api/operator/farming/products',
                                headers=self._headers(sid)).data)['products']}
            self.assertIn(pid, listed)
            front = {p['id'] for p in json.loads(
                self.client.get('/api/agriculture/products').data)['products']}
            self.assertIn(pid, front, '新作物没有出现在前台目录里')

            phase = self._post('/api/operator/farming/phenophases', {
                'product_id': pid, 'name': u'单测物候期',
                'start_month': 3, 'end_month': 5,
            }, sid)
            self.assertEqual(phase.status_code, 200, phase.data)
            phase_id = json.loads(phase.data)['result']
            self.assertEqual(
                self.client.get('/api/operator/farming/phenophases',
                                query_string={'product_id': pid},
                                headers=self._headers(sid)).status_code, 200)

            bad = self._post('/api/operator/farming/phenophases', {
                'product_id': pid, 'name': u'坏物候期',
                'start_month': 0, 'end_month': 5,
            }, sid)
            self.assertEqual(bad.status_code, 400, bad.data)

            updated = self._put('/api/operator/farming/phenophases/%d' % phase_id, {
                'name': u'单测物候期改',
                'start_month': 3,
                'end_month': 5,
                'sort_order': 0,
            }, sid)
            self.assertEqual(updated.status_code, 200, updated.data)
            phase_row = farming.get_farming_phenophase_by_id(phase_id)
            self.assertEqual(phase_row['sort_order'], 0,
                             '物候期排序更新被误当成月份范围校验')
            self.assertEqual(
                self.client.delete('/api/operator/farming/phenophases/%d' % phase_id,
                                   headers=self._headers(sid)).status_code, 200)
            self.assertEqual(
                self.client.delete('/api/operator/farming/products/%s' % pid,
                                   headers=self._headers(sid)).status_code, 200)
            self.assertNotIn(pid, {p['id'] for p in json.loads(
                self.client.get('/api/agriculture/products').data)['products']})
        finally:
            conn = get_connection()
            conn.execute("DELETE FROM farming_products WHERE id = ?", (pid,))
            conn.commit()
            conn.close()
            self._cleanup_sessions(sid)

    def test_operator_can_maintain_sources_and_categories(self):
        """来源与分类的增删改，前台来源角标与分类标签立即跟着变。"""
        sid = self._login()
        key = 'T14-PROBE-SRC'
        labels_before = farming.get_farming_category_labels()
        try:
            created = self._post('/api/operator/farming/sources', {
                'key': key, 'name': u'单测来源', 'org': u'单测机构',
            }, sid)
            self.assertEqual(created.status_code, 200, created.data)
            self.assertIsNotNone(farming.get_farming_source_by_key(key))

            updated = self._put('/api/operator/farming/sources/%s' % key,
                                {'name': u'单测来源改'}, sid)
            self.assertEqual(updated.status_code, 200, updated.data)
            self.assertEqual(farming.get_farming_source_by_key(key)['name'],
                             u'单测来源改')

            deleted = self._delete('/api/operator/farming/sources/%s' % key, sid)
            self.assertEqual(deleted.status_code, 200, deleted.data)
            self.assertIsNone(farming.get_farming_source_by_key(key))

            # 分类：改标签，前台 category_label 立即变
            updated = self._put('/api/operator/farming/categories/manage',
                                {'label': u'单测管理'}, sid)
            self.assertEqual(updated.status_code, 200, updated.data)
            self.assertEqual(farming.get_farming_category_labels()['manage'],
                             u'单测管理')
            category_rows = json.loads(self.client.get(
                '/api/operator/farming/categories',
                headers=self._headers(sid)).data)['categories']
            manage_row = next(row for row in category_rows
                              if row['key'] == 'manage')
            self.assertIn('color', manage_row)
            self.assertIn('sort_order', manage_row)
            front = json.loads(self.client.get(FRONT_FARMING,
                                               query_string={'year': '2026',
                                                             'month': '1'}).data)
            self.assertIn(u'单测管理',
                          {t['category_label'] for t in front['tasks']},
                          '改分类标签没有反映到前台')
        finally:
            conn = get_connection()
            conn.execute("DELETE FROM farming_sources WHERE key = ?", (key,))
            conn.execute("UPDATE farming_categories SET label = ? WHERE key = 'manage'",
                         (labels_before['manage'],))
            conn.commit()
            conn.close()
            self._cleanup_sessions(sid)


class OperatorPestWriteTest(OperatorContentTestBase):
    """病虫害：条目、来源、图片关联的增删改与复核。"""

    def test_operator_can_create_update_and_delete_an_entry(self):
        """条目增删改闭环，来源关联随条目一起落库。"""
        sid = self._login()
        entry_id = 't14_probe_entry'
        try:
            created = self._post('/api/operator/pest/entries', {
                'id': entry_id, 'crop_id': 'lychee', 'disease': u'单测病害',
                'kind': 'disease', 'symptoms': [u'单测症状甲', u'单测症状乙'],
                'source_keys': ['GD-PEST-2024'],
            }, sid)
            self.assertEqual(created.status_code, 200, created.data)

            entry = pest.get_pest_entry(entry_id)
            self.assertEqual(entry['disease'], u'单测病害')
            self.assertEqual(entry['symptoms'], [u'单测症状甲', u'单测症状乙'])
            self.assertEqual([s['key'] for s in entry['sources']], ['GD-PEST-2024'])

            updated = self._put('/api/operator/pest/entries/%s' % entry_id, {
                'disease': u'单测病害改', 'kind': 'pest',
                'source_keys': ['GD-PEST-2024', 'ICAMA'],
            }, sid)
            self.assertEqual(updated.status_code, 200, updated.data)
            entry = pest.get_pest_entry(entry_id)
            self.assertEqual(entry['disease'], u'单测病害改')
            self.assertEqual(entry['kind'], 'pest')
            self.assertEqual(len(entry['sources']), 2)

            deleted = self._delete('/api/operator/pest/entries/%s' % entry_id, sid)
            self.assertEqual(deleted.status_code, 200, deleted.data)
            self.assertIsNone(pest.get_pest_entry(entry_id))
        finally:
            conn = get_connection()
            conn.execute("DELETE FROM pest_entries WHERE id = ?", (entry_id,))
            conn.commit()
            conn.close()
            self._cleanup_sessions(sid)

    def test_single_entry_endpoint_returns_the_full_content(self):
        """按 id 取单条必须带上五个多值字段：编辑弹层靠它回填。"""
        sid = self._login()
        entry_id = 't14_entry_detail'
        try:
            self._post('/api/operator/pest/entries', {
                'id': entry_id, 'crop_id': 'lychee', 'disease': u'单测详情',
                'kind': 'disease', 'symptoms': [u'症状一'],
                'treatment': [u'防治一'], 'prevention': [u'预防一'],
                'registered': [u'嘧菌酯'],
                'chem_table': [{'agent': u'某药剂', 'dose': u'1000倍液',
                                'interval_days': '7', 'max_times': '3'}],
            }, sid)
            response = self.client.get('/api/operator/pest/entries/%s' % entry_id,
                                       headers=self._headers(sid))
            self.assertEqual(response.status_code, 200, response.data)
            entry = json.loads(response.data)['entry']
            self.assertEqual(entry['symptoms'], [u'症状一'])
            self.assertEqual(entry['treatment'], [u'防治一'])
            self.assertEqual(entry['prevention'], [u'预防一'])
            self.assertEqual(entry['registered'], [u'嘧菌酯'])
            self.assertEqual(entry['chem_table'][0]['agent'], u'某药剂')

            missing = self.client.get('/api/operator/pest/entries/no_such_entry',
                                      headers=self._headers(sid))
            self.assertEqual(missing.status_code, 404, missing.data)
        finally:
            conn = get_connection()
            conn.execute("DELETE FROM pest_entries WHERE id = ?", (entry_id,))
            conn.commit()
            conn.close()
            self._cleanup_sessions(sid)

    def test_chem_table_keeps_its_object_shape(self):
        """用药参考表是对象数组，写进库再读回来必须还是对象。

        此前写侧的归一化对每个数组项一律 str()：chem_table 的每个对象会被存成
        "{'agent': '...'}" 这样的文本，前台 pestChemTableHTML 按对象取值只会渲染出
        一张空表，而运营以为自己写进去了。
        """
        sid = self._login()
        entry_id = 't14_chem_shape'
        chem_rows = [{'agent': u'80%代森锰锌可湿性粉剂', 'dose': u'400~600倍液',
                      'interval_days': '10', 'max_times': '3'}]
        try:
            created = self._post('/api/operator/pest/entries', {
                'id': entry_id, 'crop_id': 'lychee', 'disease': u'单测药剂表',
                'kind': 'disease', 'symptoms': [u'症状一', u'  ', u'症状二'],
                'registered': [u'嘧菌酯'], 'chem_table': chem_rows,
            }, sid)
            self.assertEqual(created.status_code, 200, created.data)

            front = json.loads(self.client.get(FRONT_PEST + '?crop=lychee').data)
            view = next(e for e in front['entries'] if e['id'] == entry_id)
            self.assertEqual(view['chem_table'], chem_rows,
                             '用药参考表被写坏了：对象被压成了字符串')
            self.assertEqual(view['symptoms'], [u'症状一', u'症状二'],
                             '空行应当被丢掉')

            # 形状不对时明确 400，而不是悄悄写进一条坏数据
            bad = self._put('/api/operator/pest/entries/%s' % entry_id,
                            {'chem_table': [u'只给一个字符串']}, sid)
            self.assertEqual(bad.status_code, 400, bad.data)
        finally:
            conn = get_connection()
            conn.execute("DELETE FROM pest_entries WHERE id = ?", (entry_id,))
            conn.commit()
            conn.close()
            self._cleanup_sessions(sid)

    def test_entry_validation_rejects_bad_payloads(self):
        """验收「内容表单校验与前台一致」：作物、类型、来源 key、JSON 列逐条拒绝。"""
        sid = self._login()
        base = {'id': 't14_probe_entry', 'crop_id': 'lychee', 'disease': u'单测病害'}
        bad_cases = (
            ({'crop_id': 'no-such-crop'}, u'作物不存在，请先在作物列表里添加'),
            ({'disease': ''}, u'病害名称不能为空'),
            ({'kind': 'virus'}, u'类型只能是 disease 或 pest'),
            ({'symptoms': u'不是数组'}, u'symptoms 需要是数组'),
        )
        try:
            for extra, message in bad_cases:
                with self.subTest(payload=extra):
                    payload = dict(base)
                    payload.update(extra)
                    response = self._post('/api/operator/pest/entries', payload, sid)
                    self.assertEqual(response.status_code, 400, response.data)
                    self.assertEqual(json.loads(response.data)['message'], message)

            # 未登记的来源 key 一律拒绝，不能静默丢出一个「看不到出处」的条目
            response = self._post('/api/operator/pest/entries', dict(
                base, source_keys=['NO-SUCH-SOURCE']), sid)
            self.assertEqual(response.status_code, 400, response.data)
            self.assertIn(u'未登记的来源', json.loads(response.data)['message'])
            self.assertIsNone(pest.get_pest_entry('t14_probe_entry'))

            # 缺 id 也拒
            response = self._post('/api/operator/pest/entries',
                                  {'crop_id': 'lychee', 'disease': u'没 id'}, sid)
            self.assertEqual(response.status_code, 400, response.data)
        finally:
            conn = get_connection()
            conn.execute("DELETE FROM pest_entries WHERE id = ?", ('t14_probe_entry',))
            conn.commit()
            conn.close()
            self._cleanup_sessions(sid)

    def test_front_end_sees_the_edited_entry_without_a_restart(self):
        """验收 1（病虫害侧）：运营改一条条目，前台速查立即返回新值。"""
        sid = self._login()
        entry_id = 't14_probe_entry'
        try:
            self._post('/api/operator/pest/entries', {
                'id': entry_id, 'crop_id': 'lychee', 'disease': u'单测速查',
                'kind': 'disease', 'symptoms': [u'单测症状'],
            }, sid)
            response = self.client.get(FRONT_PEST + '?crop=lychee')
            self.assertEqual(response.status_code, 200)
            body = json.loads(response.data)
            self.assertIn(entry_id, {e['id'] for e in body['entries']},
                          '运营新建的条目没有出现在前台速查里')

            self._put('/api/operator/pest/entries/%s' % entry_id,
                      {'disease': u'单测速查改'}, sid)
            body = json.loads(self.client.get(FRONT_PEST + '?crop=lychee').data)
            names = {e['id']: e['disease'] for e in body['entries']}
            self.assertEqual(names[entry_id], u'单测速查改')

            self._delete('/api/operator/pest/entries/%s' % entry_id, sid)
            body = json.loads(self.client.get(FRONT_PEST + '?crop=lychee').data)
            self.assertNotIn(entry_id, {e['id'] for e in body['entries']})
        finally:
            conn = get_connection()
            conn.execute("DELETE FROM pest_entries WHERE id = ?", (entry_id,))
            conn.commit()
            conn.close()
            self._cleanup_sessions(sid)

    def test_marking_an_entry_verified_writes_who_and_when(self):
        """验收 2（病虫害侧）：复核人、复核时间、is_verified 三者都落库。"""
        sid = self._login()
        entry_id = 't14_probe_entry'
        try:
            self._post('/api/operator/pest/entries', {
                'id': entry_id, 'crop_id': 'lychee', 'disease': u'单测复核',
                'kind': 'disease',
            }, sid)
            self.assertEqual(pest.get_pest_entry(entry_id)['is_verified'], 0)

            response = self._post(
                '/api/operator/pest/entries/%s/verify' % entry_id, {}, sid)
            self.assertEqual(response.status_code, 200, response.data)

            entry = pest.get_pest_entry(entry_id)
            self.assertEqual(entry['verified_by'], 'operator_demo')
            self.assertRegex(entry['verified_at'],
                             r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$')
            self.assertEqual(entry['is_verified'], 1)

            # 前台输出形状不变：键集与复核前逐键相同，只 is_verified 从 0 变 1
            body = json.loads(self.client.get(FRONT_PEST + '?crop=lychee').data)
            view = next(e for e in body['entries'] if e['id'] == entry_id)
            self.assertEqual(view['is_verified'], 1)
            for key in ('id', 'crop', 'crop_name', 'disease', 'kind', 'symptoms',
                        'treatment', 'prevention', 'registered', 'chem_table',
                        'safety_note', 'image', 'sources'):
                self.assertIn(key, view)
        finally:
            conn = get_connection()
            conn.execute("DELETE FROM pest_entries WHERE id = ?", (entry_id,))
            conn.commit()
            conn.close()
            self._cleanup_sessions(sid)

    def test_overdue_filter_finds_stale_and_never_verified_entries(self):
        """验收 3（病虫害侧）：能按复核时间筛出超期未复核的条目。"""
        sid = self._login()
        try:
            for entry_id in ('t14_fresh', 't14_stale', 't14_never'):
                self._post('/api/operator/pest/entries', {
                    'id': entry_id, 'crop_id': 'lychee',
                    'disease': u'单测' + entry_id, 'kind': 'disease',
                }, sid)
            fresh_id, stale_id, never_id = 't14_fresh', 't14_stale', 't14_never'

            conn = get_connection()
            conn.execute("UPDATE pest_entries SET is_verified = 1, verified_by = ?, "
                         "verified_at = datetime('now', 'localtime') WHERE id = ?",
                         ('operator_demo', fresh_id))
            conn.execute("UPDATE pest_entries SET is_verified = 1, verified_by = ?, "
                         "verified_at = datetime('now', 'localtime', '-400 days') "
                         "WHERE id = ?", ('operator_demo', stale_id))
            conn.commit()
            conn.close()

            response = self.client.get('/api/operator/pest/entries?overdue=1',
                                       headers=self._headers(sid))
            self.assertEqual(response.status_code, 200)
            ids = {e['id'] for e in json.loads(response.data)['entries']}
            self.assertIn(stale_id, ids, '400 天前核过的条目没被筛出来')
            self.assertIn(never_id, ids, '从没核过的条目没被筛出来')
            self.assertNotIn(fresh_id, ids, '刚核过的条目不�该算超期')

            self.assertEqual(pest.REVIEW_STALE_DAYS, farming.REVIEW_STALE_DAYS,
                             '两个能力域的超期阈值必须同口径')
        finally:
            conn = get_connection()
            conn.execute("DELETE FROM pest_entries WHERE id IN (?, ?, ?)",
                         ('t14_fresh', 't14_stale', 't14_never'))
            conn.commit()
            conn.close()
            self._cleanup_sessions(sid)

    def test_image_link_can_be_set_and_removed(self):
        """实拍图关联：写了前台就显示，删掉前台回到「暂无实拍图」。"""
        sid = self._login()
        entry_id = 't14_probe_image'
        try:
            self._post('/api/operator/pest/entries', {
                'id': entry_id, 'crop_id': 'lychee', 'disease': u'单测配图',
                'kind': 'disease',
            }, sid)
            self.assertIsNone(pest.get_pest_entry(entry_id)['image'])

            response = self._put(
                '/api/operator/pest/entries/%s/image' % entry_id,
                {'file': '/images/pest/t14_probe.jpg', 'credit': u'单测',
                 'license': 'CC0', 'caption': u'单测图说'}, sid)
            self.assertEqual(response.status_code, 200, response.data)
            image = pest.get_pest_entry(entry_id)['image']
            self.assertEqual(image['file'], '/images/pest/t14_probe.jpg')
            self.assertEqual(image['credit'], u'单测')

            response = self._delete(
                '/api/operator/pest/entries/%s/image' % entry_id, sid)
            self.assertEqual(response.status_code, 200, response.data)
            self.assertIsNone(pest.get_pest_entry(entry_id)['image'])
        finally:
            conn = get_connection()
            conn.execute("DELETE FROM pest_entries WHERE id = ?", (entry_id,))
            conn.commit()
            conn.close()
            self._cleanup_sessions(sid)

    def test_operator_can_maintain_crops_and_sources(self):
        """速查作物与来源的增删改。"""
        sid = self._login()
        crop_id = 't14_probe_crop'
        key = 'T14-PROBE-PEST-SRC'
        try:
            created = self._post('/api/operator/pest/crops', {
                'id': crop_id, 'name': u'单测作物', 'summary': u'单测',
            }, sid)
            self.assertEqual(created.status_code, 200, created.data)
            self.assertIsNotNone(pest.get_pest_crop(crop_id))

            updated = self._put('/api/operator/pest/crops/%s' % crop_id,
                                {'name': u'单测作物改'}, sid)
            self.assertEqual(updated.status_code, 200, updated.data)
            self.assertEqual(pest.get_pest_crop(crop_id)['name'], u'单测作物改')

            bad = self._post('/api/operator/pest/crops', {'id': '', 'name': 'x'}, sid)
            self.assertEqual(bad.status_code, 400, bad.data)

            self.assertEqual(
                self._delete('/api/operator/pest/crops/%s' % crop_id, sid).status_code,
                200)

            created = self._post('/api/operator/pest/sources', {
                'key': key, 'name': u'单测来源', 'org': u'单测机构',
                'doc_type': u'病虫情报', 'date': '2026-01-01',
            }, sid)
            self.assertEqual(created.status_code, 200, created.data)
            self.assertIn(key, pest.get_pest_source_map())
            source_rows = json.loads(self.client.get(
                '/api/operator/pest/sources',
                headers=self._headers(sid)).data)['sources']
            source_row = next(row for row in source_rows if row['key'] == key)
            self.assertIn('sort_order', source_row)
            self.assertEqual(
                self._delete('/api/operator/pest/sources/%s' % key, sid).status_code, 200)
            self.assertNotIn(key, pest.get_pest_source_map())
        finally:
            conn = get_connection()
            conn.execute("DELETE FROM pest_crops WHERE id = ?", (crop_id,))
            conn.execute("DELETE FROM pest_sources WHERE key = ?", (key,))
            conn.commit()
            conn.close()
            self._cleanup_sessions(sid)


class OperatorAuthorizationTest(OperatorContentTestBase):
    """权限边界：谁能打运营接口，谁不能。"""

    PROBES = (
        ('/api/operator/farming/tasks', 'GET'),
        ('/api/operator/farming/products', 'GET'),
        ('/api/operator/farming/sources', 'GET'),
        ('/api/operator/farming/categories', 'GET'),
        ('/api/operator/pest/entries', 'GET'),
        ('/api/operator/pest/crops', 'GET'),
        ('/api/operator/pest/sources', 'GET'),
    )

    def test_student_is_rejected_from_every_operator_route(self):
        """验收 4：学员打 /api/operator/* 返回 401 或 403。"""
        sid = self._login(STUDENT)
        try:
            for path, method in self.PROBES:
                with self.subTest(path=path):
                    response = self.client.open(path, method=method,
                                                headers=self._headers(sid))
                    self.assertIn(response.status_code, (401, 403),
                                  '%s 给了学员 %d' % (path, response.status_code))
            # 写接口同样拒（这是「学员不能改内容」的实质）
            response = self._post('/api/operator/farming/tasks', {
                'product_id': 'lychee', 'title': u'学员不该能建',
                'category': 'manage', 'month': 1,
            }, sid)
            self.assertIn(response.status_code, (401, 403))
        finally:
            self._cleanup_sessions(sid)

    def test_anonymous_is_rejected_from_every_operator_route(self):
        """未登录同样 403，与 admin / government / enterprise 三域逐字一致。"""
        for path, method in self.PROBES:
            with self.subTest(path=path):
                response = self.client.open(path, method=method)
                self.assertEqual(response.status_code, 403, path)
                body = json.loads(response.data)
                self.assertFalse(body['success'])
                self.assertEqual(body['message'], u'权限不足')

    def test_operator_cannot_reach_user_or_review_management(self):
        """验收 5：operator 打用户与审核接口仍为 403。"""
        sid = self._login()
        probes = (
            ('/api/admin/users', 'GET'),
            ('/api/admin/reviews', 'GET'),
            ('/api/admin/system-announcements', 'GET'),
        )
        try:
            for path, method in probes:
                with self.subTest(path=path):
                    response = self.client.open(path, method=method,
                                                headers=self._headers(sid))
                    self.assertEqual(response.status_code, 403, path)
                    self.assertEqual(json.loads(response.data)['message'], u'权限不足')
        finally:
            self._cleanup_sessions(sid)

    def test_super_admin_keeps_full_access_to_operator_routes(self):
        """超管是运营的超集：同样能改内容（能力表里 farming.manage / pest.manage）。"""
        sid = self._login(SUPER_ADMIN)
        try:
            for path, method in self.PROBES:
                with self.subTest(path=path):
                    response = self.client.open(path, method=method,
                                                headers=self._headers(sid))
                    self.assertNotEqual(response.status_code, 403, path)
                    self.assertLess(response.status_code, 500)
        finally:
            self._cleanup_sessions(sid)

    def test_every_operator_route_requires_the_capability(self):
        """新增路由漏挂装饰器会在这里暴露：逐条打，未登录必须 403。"""
        from domains.operator import OPERATOR_FARMING_ROUTES, OPERATOR_PEST_ROUTES
        sid = self._login()
        # 路径参数用真实值占位：直接打 '<int:task_id>' 只会拿到 405，测不到鉴权。
        samples = {'<int:task_id>': 999999, '<int:phase_id>': 999999,
                   '<entry_id>': 'no-such-entry', '<key>': 'no-such-key',
                   '<crop_id>': 'no-such-crop', '<product_id>': 'no-such-product'}
        concrete = []
        for path, method in OPERATOR_FARMING_ROUTES + OPERATOR_PEST_ROUTES:
            for placeholder, value in samples.items():
                path = path.replace(placeholder, str(value))
            concrete.append((path, method))
        self.assertGreater(len(concrete), 30, '路由表没有覆盖全部运营接口')
        try:
            for path, method in concrete:
                with self.subTest(path=path, method=method):
                    anonymous = self.client.open(path, method=method)
                    self.assertEqual(anonymous.status_code, 403,
                                     '%s %s 未登录不是 403' % (method, path))

            # 登录后全部可达（业务错误也可能是 400 / 404，但不该是 403）
            for path, method in concrete:
                with self.subTest(authed=path, method=method):
                    response = self.client.open(path, method=method,
                                                headers=self._headers(sid))
                    self.assertNotEqual(response.status_code, 403,
                                        '%s %s 把运营拦住了' % (method, path))
        finally:
            self._cleanup_sessions(sid)


if __name__ == '__main__':
    unittest.main()
