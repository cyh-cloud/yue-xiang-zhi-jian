#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
粤乡智匠 - 测试文件
"""

import unittest
import json
from app import app

class TestYueXiangApp(unittest.TestCase):
    """测试粤乡智匠应用"""

    def setUp(self):
        """测试前准备"""
        self.app = app
        self.client = app.test_client()
        self.app.config['TESTING'] = True

    def test_index_page(self):
        """测试主页"""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)

    def test_health_check(self):
        """测试健康检查"""
        response = self.client.get('/api/health')
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertTrue(data['healthy'])

    def test_get_products(self):
        """测试获取农产品列表"""
        response = self.client.get('/api/agriculture/products')
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertGreater(len(data['products']), 0)

    def test_get_crafts(self):
        """测试获取手工艺列表"""
        response = self.client.get('/api/crafts/list')
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertGreater(len(data['crafts']), 0)

    def test_get_dialects(self):
        """测试获取方言列表"""
        response = self.client.get('/api/resources/dialects')
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertGreater(len(data['dialects']), 0)

    def test_get_success_cases(self):
        """测试获取成功案例

        红线：案例内容必须可溯源 —— 每条都要有 sources，且每条来源都要有
        标题 / 媒体 / 链接。禁止出现无出处的编造案例。

        注意：接口只下发**超级管理员审核通过**的案例（见 database._seed_case_reviews），
        所以「内容完整性」对 cases_data 全量校验，「可见性」对接口返回校验。
        """
        import cases_data
        all_cases = cases_data.get_cases()
        self.assertGreater(len(all_cases), 0)

        for case in all_cases:
            self.assertTrue(case.get('title'), '案例缺少标题')
            self.assertTrue(case.get('location'), '案例缺少地点')
            self.assertTrue(case.get('background'), '案例缺少背景')
            sources = case.get('sources') or []
            self.assertGreater(len(sources), 0, '案例 %s 没有任何资料来源' % case.get('title'))
            for s in sources:
                self.assertTrue(s.get('title'), '来源缺少标题')
                self.assertTrue(s.get('media'), '来源缺少媒体名')
                self.assertTrue(s.get('url'), '来源缺少链接')

        response = self.client.get('/api/resources/cases')
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertIn('source_note', data)
        self.assertIn('lessons_note', data)

        # 审核统计必须下发（前端据此区分"审核中"与"加载失败"）
        self.assertIn('case_review', data)
        for k in ('approved', 'pending', 'rejected', 'total'):
            self.assertIn(k, data['case_review'])
        self.assertEqual(data['case_review']['total'], len(all_cases))
        # 接口下发的条数必须等于"已通过"数 —— 未通过的一条都不能漏出去
        self.assertEqual(len(data['cases']), data['case_review']['approved'])
        for c in data['cases']:
            self.assertTrue(c.get('sources'), '审核通过的案例仍需带来源')

        # 未审核通过的案例不能靠直链看到（否则审核形同虚设）
        approved_ids = {c['id'] for c in data['cases']}
        for c in all_cases:
            if c['id'] not in approved_ids:
                self.assertEqual(
                    self.client.get('/api/resources/cases/%d' % c['id']).status_code, 404)
                break

    def test_get_success_case_by_id(self):
        """按 id 获取单个案例：已通过的 200，不存在 / 未通过的 404"""
        listed = json.loads(self.client.get('/api/resources/cases').data)['cases']
        if listed:  # 案例需审核通过才可见；全部待审时列表为空属预期，不视为失败
            cid = listed[0]['id']
            ok = json.loads(self.client.get('/api/resources/cases/%d' % cid).data)
            self.assertTrue(ok['success'])
            self.assertEqual(ok['case']['id'], cid)

        bad = self.client.get('/api/resources/cases/9999')
        self.assertEqual(bad.status_code, 404)

    def test_get_policies(self):
        """测试获取政策信息"""
        response = self.client.get('/api/resources/policies')
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertGreater(len(data['policies']), 0)

    def test_get_jobs(self):
        """测试获取就业岗位（企业已审岗位 + 公开招聘公告两条数据源）

        ⚠️ 口径已随 2026-10-06「就业对接」改造更新：
        旧断言只看 `jobs` 是否非空，而演示岗位（`JOBS_DATA`）已被整体移除，
        学员端的企业岗位改为「企业发布 → 管理员审核通过」才可见（fail-closed），
        因此 `jobs` 在无已审企业岗位时为 0 属预期。
        真实内容在 `recruitments`（公开招聘公告，来自 jobs_data.py 策展模块），
        断言改为「两者合计 > 0」，并单独校验公告侧字段与来源口径完整。
        """
        response = self.client.get('/api/employment/jobs')
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertIn('jobs', data)
        self.assertIn('recruitments', data)
        # 两条数据源合计必须有内容（企业岗位可能为 0，公告必有）
        self.assertGreater(len(data['jobs']) + len(data['recruitments']), 0)

        # 公开招聘公告：条数、字段完整、来源齐全、source_type 标注正确
        self.assertGreater(len(data['recruitments']), 0)
        for r in data['recruitments']:
            self.assertEqual(r.get('source_type'), 'public_recruit')
            self.assertTrue(r.get('title'))
            self.assertTrue(r.get('org'))
            self.assertTrue(r.get('sources'), '每条公告都必须带官方来源')
            # 公告不做站内申请 —— 必须带官方原文链接字段
            self.assertTrue(r.get('signup_way'))
        # 来源口径说明随列表一起下发（前端据此展示脚注）
        self.assertTrue(data.get('recruit_source_note'))
        self.assertTrue(data.get('recruit_disclaimer'))

        # 企业岗位侧：接口只下发已通过审核的岗位（fail-closed）
        for j in data['jobs']:
            self.assertEqual(j.get('source_type'), 'enterprise')

    def test_job_review_gate(self):
        """审核门禁：未通过审核的企业岗位，学员端任何入口都拿不到

        固化 2026-10-06「就业对接」改造的核心红线（fail-closed）：
          ① 未审岗位不出现在 /api/employment/jobs 列表；
          ② 直链 /api/employment/jobs/<id> 返回 404（不能靠猜 id 绕过审核）；
          ③ 未审岗位不能被申请（apply_for_job 返回 unavailable 且不落投递记录）。
        用例结束会删除自建岗位，不污染真实数据。
        """
        import database
        ent_sid = None
        job_id = None
        try:
            # 企业端登录
            r = self.client.post('/api/auth/login', data=json.dumps({
                'username': 'enterprise_demo', 'password': '123456', 'role': 'enterprise'
            }), content_type='application/json')
            ent_sid = json.loads(r.data)['session_id']
            headers = {'X-Session-Id': ent_sid}

            # 企业发布岗位 → 初始状态 pending
            r = self.client.post('/api/enterprise/jobs', data=json.dumps({
                'title': '__门禁用例-测试岗位__', 'salary': '面议',
                'location': '广州', 'category': '综合', 'description': '仅供测试'
            }), content_type='application/json', headers=headers)
            job_id = json.loads(r.data)['id']

            # ① 待审岗位不出现在学员端列表
            data = json.loads(self.client.get('/api/employment/jobs').data)
            self.assertNotIn(job_id, [j['id'] for j in data['jobs']])

            # ② 直链 404
            self.assertEqual(
                self.client.get('/api/employment/jobs/%d' % job_id).status_code, 404)

            # ③ 未审岗位不能被申请
            r = self.client.post('/api/employment/apply', data=json.dumps({
                'user_id': 'student_demo', 'job_id': job_id
            }), content_type='application/json')
            self.assertFalse(json.loads(r.data)['success'])
            conn = database.get_connection()
            cnt = conn.execute(
                "SELECT COUNT(*) FROM job_applications WHERE job_id = ?", (job_id,)).fetchone()[0]
            conn.close()
            self.assertEqual(cnt, 0, '未审岗位不得产生投递记录')

            # 审核通过 → 立即对学员端可见（证明门禁只挡未审，不挡正常流程）
            conn = database.get_connection()
            conn.execute("UPDATE job_listings SET review_status = 'approved' WHERE id = ?", (job_id,))
            conn.commit()
            conn.close()
            data = json.loads(self.client.get('/api/employment/jobs').data)
            self.assertIn(job_id, [j['id'] for j in data['jobs']])
            self.assertEqual(
                self.client.get('/api/employment/jobs/%d' % job_id).status_code, 200)
        finally:
            if job_id:
                conn = database.get_connection()
                conn.execute("DELETE FROM job_applications WHERE job_id = ?", (job_id,))
                conn.execute("DELETE FROM saved_jobs WHERE job_id = ?", (job_id,))
                conn.execute("DELETE FROM content_reviews WHERE content_type='job' AND content_id = ?", (job_id,))
                conn.execute("DELETE FROM job_listings WHERE id = ?", (job_id,))
                conn.commit()
                conn.close()
            if ent_sid:
                import database as _db
                try:
                    conn = _db.get_connection()
                    conn.execute("DELETE FROM user_sessions WHERE session_id = ?", (ent_sid,))
                    conn.commit()
                    conn.close()
                except Exception:
                    pass

    def test_recruit_matches_platform_positioning(self):
        """公开招聘公告必须与「农村本土人才赋能」定位一致，且不能全是过期的

        背景（2026-10-06 用户拍板）：
          ① 招聘公告**过期即失效**（与长期有效的政策不同）。改造前 10 条里 8 条已过期，
             学员打开只看到一片「已过报名期」，所以列表必须始终保留可报名的条目；
          ② 原先混入了 3 条「省属单位 / 城市 / 研究生」岗（省事业单位集中招聘、省农科院两家院所），
             受众不是本平台学员 —— 已移除，此后不得再出现研究生学历门槛的公告；
          ③ 分类必须落在 CATEGORY_LIST 内，否则前端会出现「筛了永远是 0 条」的死筛选项。
        """
        import datetime
        import jobs_data
        items = jobs_data.get_recruitment_list(today=datetime.date.today())

        actionable = [r for r in items if r['status'] in ('open', 'upcoming')]
        self.assertGreaterEqual(
            len(actionable), 1, '公告列表里至少要有一条还能报名的岗位')

        for r in items:
            self.assertTrue(r.get('deadline'), '公告 %s 缺少报名截止日期' % r.get('key'))
            self.assertIn(r.get('category'), jobs_data.CATEGORY_LIST,
                          '公告 %s 的分类不在 CATEGORY_LIST 内' % r.get('key'))
            self.assertTrue(r.get('signup_way'), '公告 %s 缺少报名方式' % r.get('key'))
            edu = r.get('education') or ''
            self.assertNotIn('研究生', edu, '公告 %s 设了研究生门槛，与平台定位不符' % r.get('key'))
            self.assertNotIn('硕士', edu, '公告 %s 设了硕士门槛，与平台定位不符' % r.get('key'))

        # 分类白名单里不该再有「科研辅助」这类与定位无关的分类
        self.assertNotIn('科研辅助', jobs_data.CATEGORY_LIST)

    def test_resume_profile_and_ai_guardrails(self):
        """简历链路：能力档案取自真实数据、字段不可越权改写、AI 失败必须可见

        背景（2026-10-06 用户要求「把就业对接这些功能串成一条链路」）：
          链路为 能力档案 → AI 简历 → 相似职位推荐 → 投递/报名。
        本用例守住三条底线：
          ① 求职资料属个人数据，未登录 401、他人 403；
          ② user_id / ai_used **不能**由客户端 PUT 改写（否则可以伪称没用过 AI）；
          ③ AI 未配置时必须 503 + code，**绝不返回 success=True 的兜底文案**（全项目红线）。
        """
        import app as app_module
        import database
        sid = None
        orig_ai_configured = app_module._ai_configured
        try:
            r = self.client.post('/api/auth/login', data=json.dumps({
                'username': 'student_demo', 'password': '123456'
            }), content_type='application/json')
            sid = json.loads(r.data)['session_id']
            headers = {'X-Session-Id': sid}

            # ① 鉴权边界
            self.assertEqual(
                self.client.get('/api/employment/profile/student_demo').status_code, 401)
            self.assertEqual(
                self.client.get('/api/employment/profile/student_demo',
                                headers={'X-Session-Id': 'no-such-session'}).status_code, 401)
            self.assertEqual(
                self.client.put('/api/employment/resume/student_demo',
                                data=json.dumps({'title': 'x'}),
                                content_type='application/json',
                                headers={'X-Session-Id': 'no-such-session'}).status_code, 401)

            # ② 能力档案来自真实数据（student_demo 有 3 张证书 / 荔枝种植方向）
            data = json.loads(self.client.get(
                '/api/employment/profile/student_demo', headers=headers).data)
            self.assertTrue(data['success'])
            prof = data['profile']
            self.assertEqual(len(prof['certificates']), 3)
            self.assertEqual(sum(1 for c in prof['certificates'] if c['earned']), 1,
                             '只有「已获得」的证书才算 earned，其余必须如实标注状态')
            # 积分**不写死常数**：演示账号会被真实使用改变余额（学员每投一次 +20，
            # 浏览器走查点一次「申请职位」就 +20）→ 写死必然误报。
            # 真正要守的契约是「能力档案里的积分 = points 表的真实余额，不是编的」。
            _conn = database.get_connection()
            _row = _conn.execute(
                "SELECT balance FROM points WHERE user_id = 'student_demo'").fetchone()
            _conn.close()
            expect_points = (_row['balance'] if _row else 0)
            self.assertGreater(expect_points, 0, '演示账号应有真实积分数据')
            self.assertEqual(prof['points'], expect_points,
                             '能力档案的积分必须等于 points 表的真实余额')
            self.assertEqual((prof['learning'] or {}).get('direction'), '荔枝种植')

            # ③ 越权字段不可写
            # 先读一次当前 ai_used 作为基线：这个字段只能由 AI 接口置位，客户端 PUT 必须原样保持。
            # 不断言「恒为 0」—— 如果库里有上一轮 AI 调用留下的 ai_used=1（例如并行跑过
            # 一点真实 AI 的浏览器验证），「恒为 0」会误报；断言「PUT 前后不变」才是真契约。
            _before = json.loads(self.client.get(
                '/api/employment/resume/student_demo', headers=headers).data)
            before_ai_used = ((_before or {}).get('resume') or {}).get('ai_used', 0)
            r = self.client.put('/api/employment/resume/student_demo',
                                data=json.dumps({
                                    'title': '农产品电商运营', 'self_eval': '测试',
                                    'user_id': 'HACK', 'ai_used': 999,
                                }), content_type='application/json', headers=headers)
            resume = json.loads(r.data)['resume']
            self.assertEqual(resume['user_id'], 'student_demo')
            self.assertNotEqual(resume['ai_used'], 999, '客户端提交的 ai_used 必须被忽略')
            self.assertEqual(resume['ai_used'], before_ai_used,
                             'ai_used 只能由 AI 接口置位，客户端 PUT 不得改写')

            # ④ AI 未配置 → 503 + code，且不得出现 success=True
            app_module._ai_configured = lambda: False
            r = self.client.post('/api/employment/resume/ai',
                                 data=json.dumps({'user_id': 'student_demo',
                                                  'section': 'self_eval'}),
                                 content_type='application/json', headers=headers)
            body = json.loads(r.data)
            self.assertEqual(r.status_code, 503)
            self.assertEqual(body.get('code'), 'ai_not_configured')
            self.assertIsNot(body.get('success'), True)

            # ⑤ 非法段落 → 400
            r = self.client.post('/api/employment/resume/ai',
                                 data=json.dumps({'user_id': 'student_demo',
                                                  'section': 'education'}),
                                 content_type='application/json', headers=headers)
            self.assertEqual(r.status_code, 400)
        finally:
            app_module._ai_configured = orig_ai_configured
            conn = database.get_connection()
            conn.execute("DELETE FROM resumes WHERE user_id = 'student_demo'")
            if sid:
                conn.execute("DELETE FROM user_sessions WHERE session_id = ?", (sid,))
            conn.commit()
            conn.close()

    def test_job_intent_and_my_jobs(self):
        """公告「求职意向」链路：登记幂等、聚合下发、且明确不代办报名

        公开招聘公告**不是**站内投递（报名要去发布单位官方系统），
        所以它走 job_intents 这条独立通道；接口文案必须声明「平台不代办报名」，
        避免学员误以为登记意向 = 已报名。
        """
        import database
        import jobs_data
        sid = None
        try:
            r = self.client.post('/api/auth/login', data=json.dumps({
                'username': 'student_demo', 'password': '123456'
            }), content_type='application/json')
            sid = json.loads(r.data)['session_id']
            headers = {'X-Session-Id': sid}

            key = jobs_data.get_recruitment_list()[0]['key']

            # 未登录不可登记
            self.assertEqual(
                self.client.post('/api/employment/intent',
                                 data=json.dumps({'user_id': 'student_demo',
                                                  'recruit_key': key}),
                                 content_type='application/json').status_code, 401)

            r = self.client.post('/api/employment/intent',
                                 data=json.dumps({'user_id': 'student_demo',
                                                  'recruit_key': key, 'note': '想去'}),
                                 content_type='application/json', headers=headers)
            body = json.loads(r.data)
            self.assertTrue(body['success'])
            self.assertIn('不代办报名', body.get('notice', ''),
                          '登记成功提示必须声明平台不代办报名')

            # 幂等：重复登记不产生第二行
            r = self.client.post('/api/employment/intent',
                                 data=json.dumps({'user_id': 'student_demo',
                                                  'recruit_key': key, 'note': '改了'}),
                                 content_type='application/json', headers=headers)
            self.assertFalse(json.loads(r.data)['created'])
            self.assertEqual(len(database.get_job_intents('student_demo')), 1)

            # 不存在的公告 key → 404
            self.assertEqual(
                self.client.post('/api/employment/intent',
                                 data=json.dumps({'user_id': 'student_demo',
                                                  'recruit_key': 'no-such-key'}),
                                 content_type='application/json',
                                 headers=headers).status_code, 404)

            # 聚合接口把意向补全为可直接渲染的字段
            data = json.loads(self.client.get(
                '/api/employment/my-jobs/student_demo', headers=headers).data)
            self.assertTrue(data['success'])
            self.assertEqual(len(data['intents']), 1)
            it = data['intents'][0]
            self.assertEqual(it['channel'], 'public_recruit')
            self.assertTrue(it['title'] and it['org'])
            self.assertTrue(data.get('intent_notice'))

            # 他人不可读
            self.assertEqual(
                self.client.get('/api/employment/my-jobs/student_demo',
                                headers={'X-Session-Id': 'no-such-session'}).status_code, 401)

            # 取消
            r = self.client.delete('/api/employment/intent',
                                   data=json.dumps({'user_id': 'student_demo',
                                                    'recruit_key': key}),
                                   content_type='application/json', headers=headers)
            self.assertTrue(json.loads(r.data)['success'])
            self.assertEqual(database.get_job_intents('student_demo'), [])
        finally:
            conn = database.get_connection()
            conn.execute("DELETE FROM job_intents WHERE user_id = 'student_demo'")
            if sid:
                conn.execute("DELETE FROM user_sessions WHERE session_id = ?", (sid,))
            conn.commit()
            conn.close()

    def test_demo_jobs_follow_enterprise_review_flow(self):
        """演示岗位必须与真实链路一致：挂企业演示账号 + 经管理员审核才在学员端露出

        用户 2026-10-07 要求：「就业对接下面那两个演示数据要跟企业端挂钩，
        企业端发布岗位，管理员审核通过后才可以在学员端显示」。
        此前它们是平台直接塞进库、`review_status` 写死 `approved` 的，等于绕过了审核。
        这里固化六点：
          ① 归属账号 = **真实企业演示账号** `enterprise_demo`（不是平台 sentinel
             `'__demo__'`）—— 企业端「岗位管理」才看得到、才能管；
          ② 四重「演示」标注不放松（公司名 / `is_demo` / 前端角标 / 描述声明）；
          ③ 每条都有一条 `content_reviews` 记录 —— 没有记录就不会出现在管理端审核列表里，
             「企业发布 → 平台审核」这条链路就是断的；
          ④ **未过审时学员端不可见**（列表不出现 + 直链 404）；
          ⑤ 重跑 `init_db()` 幂等：id 不变（否则学员已有投递变孤儿）、
             **不覆盖已有审核结论**、不碰真实企业岗位及其投递/收藏；
          ⑥ 驳回会回写 `job_listings.review_status`（见 test_reject_review_writes_back_job_status）。
        """
        import database
        conn = database.get_connection()
        demo = conn.execute(
            "SELECT id, title, company, description, review_status, enterprise_id "
            "FROM job_listings WHERE is_demo = 1").fetchall()
        conn.close()
        self.assertGreaterEqual(len(demo), 2, '应预置 2 条演示岗位')
        demo_ids = {d['id'] for d in demo}
        for d in demo:
            self.assertIn('演示', d['company'], '公司名必须带「（演示）」后缀')
            self.assertIn('演示', d['description'], '描述必须声明是演示数据')
            self.assertEqual(d['enterprise_id'], 'enterprise_demo',
                             '演示岗位必须挂在企业演示账号下，企业端才能管理、审核才能对上')

        # ③ 每条演示岗位都必须有审核记录
        conn = database.get_connection()
        for jid in demo_ids:
            rv = conn.execute(
                "SELECT status FROM content_reviews WHERE content_type='job' AND content_id=?",
                (jid,)).fetchone()
            self.assertIsNotNone(rv, '演示岗位缺审核记录 → 管理端审核列表里看不到，链路是断的')
        conn.close()

        # ④ 未过审 → 学员端列表看不到、直链 404
        probe_id = sorted(demo_ids)[0]
        conn = database.get_connection()
        conn.execute("UPDATE job_listings SET review_status='pending' WHERE id=?", (probe_id,))
        conn.commit()
        conn.close()
        try:
            listed = {j['id'] for j in database.get_job_listings_filtered()}
            self.assertNotIn(probe_id, listed, '未过审的岗位不得出现在学员端列表')
            r = self.client.get('/api/employment/jobs/%d' % probe_id)
            self.assertEqual(r.status_code, 404, '未过审的岗位直链必须 404（否则猜 id 可绕开审核）')
        finally:
            conn = database.get_connection()
            conn.execute("UPDATE job_listings SET review_status='approved' WHERE id=?", (probe_id,))
            conn.commit()
            conn.close()

        # ⑤ 造一条真实企业岗位 + 投递，并把一条演示岗位标成 rejected，重灌后都必须原样存活
        conn = database.get_connection()
        conn.execute("UPDATE job_listings SET review_status='rejected' WHERE id=?", (probe_id,))
        conn.execute("""
            INSERT INTO job_listings (title, company, salary, requirements, description,
                                      location, category, enterprise_id, review_status, is_demo)
            VALUES ('__单测真实岗位__', '真实公司', '9K', '[]', '真实描述',
                    '广州', '电商运营', 'enterprise_demo', 'approved', 0)
        """)
        conn.commit()
        real_id = conn.execute(
            "SELECT id FROM job_listings WHERE title = '__单测真实岗位__'").fetchone()[0]
        conn.execute("INSERT INTO job_applications (user_id, job_id) VALUES ('student_demo', ?)",
                     (real_id,))
        conn.commit()
        conn.close()

        try:
            database.init_db()

            conn = database.get_connection()
            # 演示岗位的审核结论不得被种子逻辑改写（驳回后一重启就变回待审 = 静默覆盖数据）
            row = conn.execute("SELECT review_status FROM job_listings WHERE id = ?",
                               (probe_id,)).fetchone()
            self.assertEqual(row['review_status'], 'rejected',
                             '种子重灌把管理员的审核结论覆盖掉了')
            # 真实企业岗位及其投递必须存活，且审核结论也不得被改写
            real = conn.execute("SELECT id, is_demo, review_status FROM job_listings WHERE id = ?",
                                (real_id,)).fetchone()
            self.assertIsNotNone(real, '真实企业岗位在种子重灌后不得消失')
            self.assertEqual(real['is_demo'], 0)
            self.assertEqual(real['review_status'], 'approved')
            cnt = conn.execute("SELECT COUNT(*) FROM job_applications WHERE job_id = ?",
                               (real_id,)).fetchone()[0]
            self.assertEqual(cnt, 1, '真实岗位的投递记录不得被演示岗位种子逻辑清掉')
            after = {r[0] for r in conn.execute(
                "SELECT id FROM job_listings WHERE is_demo = 1").fetchall()}
            self.assertEqual(after, demo_ids, '演示岗位必须按标题就地更新（id 不变），不得删后重建')
            conn.close()
        finally:
            conn = database.get_connection()
            conn.execute("UPDATE job_listings SET review_status='approved' WHERE id=?", (probe_id,))
            conn.execute("DELETE FROM job_applications WHERE job_id = ?", (real_id,))
            conn.execute("DELETE FROM saved_jobs WHERE job_id = ?", (real_id,))
            conn.execute("DELETE FROM job_listings WHERE id = ?", (real_id,))
            conn.commit()
            conn.close()

    def test_reject_review_writes_back_job_status(self):
        """驳回必须回写目标表状态 —— 否则企业端一直显示「待审核」，企业只能干等

        `approve_review()` 会回写 `job_listings.review_status`，而 `reject_review()`
        此前只改 `content_reviews`，两边不对称：被驳回的企业岗位在企业端永远停在
        「待审核」，企业既不知道被拒、也不会去改内容重投（2026-10-07 修）。
        """
        import database
        conn = database.get_connection()
        conn.execute("""
            INSERT INTO job_listings (title, company, salary, requirements, description,
                                      location, category, enterprise_id, review_status, is_demo)
            VALUES ('__单测驳回岗位__', '某某公司', '5K', '[]', '描述',
                    '广州', '电商运营', 'enterprise_demo', 'pending', 0)
        """)
        conn.commit()
        jid = conn.execute(
            "SELECT id FROM job_listings WHERE title = '__单测驳回岗位__'").fetchone()[0]
        conn.close()
        database.create_content_review('job', jid, 'enterprise_demo')
        rv = database.get_review_by_content('job', jid)
        try:
            database.reject_review(rv['id'], 'admin_demo', '岗位信息不完整，请补充职责描述')
            conn = database.get_connection()
            row = conn.execute("SELECT review_status FROM job_listings WHERE id = ?",
                               (jid,)).fetchone()
            conn.close()
            self.assertEqual(row['review_status'], 'rejected',
                             '驳回必须回写 job_listings.review_status')
            after = database.get_review_by_content('job', jid)
            self.assertEqual(after['status'], 'rejected')
            self.assertEqual(after['review_comment'], '岗位信息不完整，请补充职责描述')
        finally:
            conn = database.get_connection()
            conn.execute("DELETE FROM content_reviews WHERE content_type='job' AND content_id=?",
                         (jid,))
            conn.execute("DELETE FROM job_listings WHERE id = ?", (jid,))
            conn.commit()
            conn.close()

    def test_login(self):
        """测试登录功能"""
        # 测试正确登录
        response = self.client.post('/api/auth/login',
            data=json.dumps({
                'username': 'teacher_demo',
                'password': '123456',
                'role': 'teacher'
            }),
            content_type='application/json'
        )
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertIn('session_id', data)

    def test_login_wrong_password(self):
        """测试错误密码登录"""
        response = self.client.post('/api/auth/login',
            data=json.dumps({
                'username': 'teacher_demo',
                'password': 'wrong_password'
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 401)

    def test_verify_session_returns_user_id(self):
        """会话校验必须与登录返回同一套 user 结构（含 id）。

        回归背景：/api/auth/verify 曾直接返回 database.get_session() 的结果
        （{user_id, name, role}，键名是 user_id，没有 id）。而前端 restoreSession()
        会用它整体覆盖 AppState.user → AppState.user.id 变成 undefined →
        所有 `/api/xxx/${AppState.user.id}` 被拼成 `/api/xxx/undefined`。
        旧接口大多不校验 user_id 所以没暴露；就业对接的 _self_only() 会直接 403。
        """
        import database
        r = self.client.post('/api/auth/login',
            data=json.dumps({'username': 'student_demo', 'password': '123456'}),
            content_type='application/json')
        sid = json.loads(r.data)['session_id']
        try:
            v = self.client.post('/api/auth/verify',
                data=json.dumps({'session_id': sid}),
                content_type='application/json')
            self.assertEqual(v.status_code, 200)
            user = json.loads(v.data)['user']
            self.assertEqual(user.get('id'), 'student_demo',
                             'verify 必须下发 user.id（= username），否则前端会拼出 /undefined')
            self.assertEqual(user.get('name'), '李同学')
            self.assertEqual(user.get('role'), 'student')
            self.assertNotIn('user_id', user,
                             '不应把内部 session 字段（user_id）直接透出当 user 用')
            # 会话无效 → 401
            bad = self.client.post('/api/auth/verify',
                data=json.dumps({'session_id': 'no-such-session'}),
                content_type='application/json')
            self.assertEqual(bad.status_code, 401)
        finally:
            conn = database.get_connection()
            conn.execute("DELETE FROM user_sessions WHERE session_id = ?", (sid,))
            conn.commit()
            conn.close()

    def test_generate_script(self):
        """测试生成带货话术接口契约

        ⚠️ 原测试传 product='lychee'（英文），而 EC_PRODUCTS 只认中文作物名
        → 命中 EC9 的白名单校验返回 400 unknown_product，断言必然失败。
        改为传合法作物；并允许 AI 未启用时明确失败（该接口不得返回假话术）。
        """
        response = self.client.post('/api/ecommerce/script',
            data=json.dumps({'product': '荔枝', 'style': '热情'}),
            content_type='application/json'
        )
        self.assertIn(response.status_code, (200, 400, 429, 503))
        data = json.loads(response.data)   # 必须始终是 JSON
        if response.status_code == 200:
            self.assertTrue(data.get('success'))
            self.assertIn('script', data)
        else:
            self.assertFalse(data.get('success'), '失败时不得返回 success=True')
            self.assertTrue(data.get('code'), '失败时必须给出可判别的错误码')

    def test_generate_script_rejects_unknown_product(self):
        """白名单外的作物必须明确 400，不能静默按默认作物生成"""
        response = self.client.post('/api/ecommerce/script',
            data=json.dumps({'product': 'lychee'}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(json.loads(response.data).get('code'), 'unknown_product')

    def test_diagnose_pest(self):
        """测试病虫害诊断接口契约

        ⚠️ 原测试打的是 /api/simulation/diagnose —— 该路由早已不存在，
        404 返回 HTML 导致 json.loads 抛 JSONDecodeError（测试长期失真）。
        真实路由是 /api/agriculture/diagnose；该接口依赖 AI 上游，不可用时
        明确返回 503（不返回假结论），故这里校验契约而非强制 success。
        """
        response = self.client.post('/api/agriculture/diagnose',
            data=json.dumps({'product': '荔枝', 'symptoms': '叶片出现褐色斑点，边缘枯黄'}),
            content_type='application/json'
        )
        self.assertIn(response.status_code, (200, 400, 503))
        data = json.loads(response.data)
        if response.status_code == 200:
            self.assertTrue(data.get('success'))
            self.assertIn('diagnosis', data)
        else:
            self.assertFalse(data.get('success'), '失败时不得返回 success=True')

    def test_get_teacher_dashboard(self):
        """测试教师仪表板"""
        response = self.client.get('/api/teacher/dashboard')
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertIn('dashboard', data)

    def test_get_students(self):
        """测试获取学员列表"""
        response = self.client.get('/api/teacher/students')
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertIn('students', data)


if __name__ == '__main__':
    unittest.main()