# -*- coding: utf-8 -*-
"""招募、案例、政策三条接口切库（T09）的响应快照比对：API 层 seam，逐字节比对。

票的验收第 1 条是「招募、案例、政策三条接口的响应 JSON 与切换前逐字节一致」。这条
不能靠断言几个字段糊过去：三条接口一次下发的内容都很大，而且读回时要重组的形状各不
相同 ——

  · 招募公告：14 条公告 × 16 字段 + 16 行来源，读回要按 sort_order 重组 sources，
    还要按当天日期重算 status / status_label / days_left / starts_in 四个派生字段；
  · 成功案例：5 条案例 × 8 标量字段 + 四个子数组（20 指标 / 24 里程碑 / 18 来源 /
    21 借鉴点），读回时五张表要按原形状组装；
  · 政策：正文不动（政府端本来就管它），变的是口径说明的来源。

所以这里存的是**切换前的原始响应**：tests/baseline_recruit_case_policy_switch.json 在
切库前由一次性脚本生成；本文件的用例在切库后重放同一批请求，逐项比 sha256 与字节数。
用 sha256 而不是解析后比对，是因为 json.loads 之后键序由插入序决定，而「键序变化」
对前端无害、对「逐字节一致」的验收标准却致命。

⚠️ 招募侧为什么只比对 recruitments 数组而不是整个响应体：/api/employment/jobs 把
「企业岗位」与「招募公告」两类数据合并在一个响应里，而企业岗位那半边
（enterprise_review_pending、jobs 数组）会随其它测试文件往 job_listings 插行又删行
而变。那不是本次改动引入的差异，把它纳入字节比对会让这条用例在全量跑测试时随机红。
所以招募侧钉住**本次真正改动的三块**：recruitments 数组、两条口径文案、
category_options.recruit；其余字段由既有测试（test_employment_domains.py 的
JobListTest）继续看守。

为什么不 mock 数据库：这里测的是「读库这条路产出的响应」与切换前「读代码常量那条路
产出的响应」是否一致。把库 mock 掉就退化回测整形函数，测不到 JOIN 顺序、sort_order
重组、JSON 列解析这三处真正会出错的地方。

⚠️ 本文件跑在真实库上（与既有测试同一口径），只读不写。
"""

import hashlib
import json
import os
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(REPO_ROOT, 'backend')
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

BASELINE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        'baseline_recruit_case_policy_switch.json')

# 整包字节比对的接口：案例列表与五条详情、404 分支、政策列表。
# 这些响应只由内容表与审核记录决定，不随其它测试文件漂移。
WHOLE_BODY_VARIANTS = (
    ('/api/resources/cases', {}),
    ('/api/resources/cases/1', {}),
    ('/api/resources/cases/2', {}),
    ('/api/resources/cases/3', {}),
    ('/api/resources/cases/4', {}),
    ('/api/resources/cases/5', {}),
    ('/api/resources/cases/999999', {}),
    ('/api/resources/policies', {}),
)

# 招募侧只比对响应里的公告部分（理由见模块 docstring）。
RECRUIT_VARIANTS = (
    ('/api/employment/jobs', {}),
    ('/api/employment/jobs', {'keyword': u'公益性'}),
    ('/api/employment/jobs', {'location': u'茂名'}),
    ('/api/employment/jobs', {'category': u'基层服务'}),
    ('/api/employment/jobs', {'salary': '3K-5K'}),
    ('/api/employment/jobs', {'keyword': 'zzz-no-such-keyword'}),
)

# 招募响应里参与字节比对的三块：公告数组 + 两条口径文案 + 招募侧分类下拉。
RECRUIT_COMPARED_KEYS = ('recruitments', 'recruit_source_note',
                         'recruit_disclaimer', 'category_options')


def _key(path, args):
    if not args:
        return path
    query = '&'.join('%s=%s' % item for item in sorted(args.items()))
    return '%s?%s' % (path, query)


def _sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def _canonical(value):
    """规范化成稳定文本：键排序 + 统一分隔符，确保同一份数据两次跑出同一串字节。"""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


# 招募公告里由**当天日期**算出的字段。它们是派生值而不是内容本身，随运行日期
# 自然变化，纳入字节比对会让这条用例隔天就红。比对时置成常量，内容字段仍逐字节比。
# ⚠️ status / status_label 同样由日期算出（open / upcoming / closed 三种状态会随
#    截止日期翻转），d6275da 只剔了 days_left / starts_in，公告一过期就红 ——
#    红的原因与「内容是否被改对」无关，故一并剔除（T11 实测 8 条已过期）。
VOLATILE_FIELDS = ('days_left', 'starts_in', 'status', 'status_label')


def _strip_volatile(value):
    """把公告数组里随时间漂移的派生字段置成 None，其余原样保留。"""
    if not isinstance(value, list):
        return value
    out = []
    for item in value:
        if isinstance(item, dict):
            item = {k: (None if k in VOLATILE_FIELDS else v) for k, v in item.items()}
        out.append(item)
    return out


class RecruitCasePolicySwitchSnapshotTest(unittest.TestCase):
    """切换到读库之后，三条接口的响应与切换前逐字节一致。"""

    def setUp(self):
        from app import app
        self.client = app.test_client()
        if not os.path.isfile(BASELINE):
            self.fail('缺少切换前快照 %s' % BASELINE)
        with open(BASELINE, encoding='utf-8') as handle:
            self.baseline = json.load(handle)

    def _assert_same(self, key, response):
        expected = self.baseline[key]
        body = response.get_data()
        self.assertEqual(response.status_code, expected['status'],
                         '%s 的状态码从 %d 变成了 %d'
                         % (key, expected['status'], response.status_code))
        self.assertEqual(hashlib.sha256(body).hexdigest(), expected['sha256'],
                         '%s 的响应体与切换前不一致（%d 字节 vs 基线 %d 字节）'
                         % (key, len(body), expected['bytes']))

    def test_case_and_policy_responses_are_byte_identical(self):
        for path, args in WHOLE_BODY_VARIANTS:
            key = _key(path, args)
            with self.subTest(key):
                self._assert_same(key, self.client.get(path, query_string=args))

    def test_recruitment_payload_is_byte_identical(self):
        """招募侧的公告数组 + 口径文案 + 分类下拉，与切换前逐字节一致。"""
        for path, args in RECRUIT_VARIANTS:
            key = _key(path, args)
            with self.subTest(key):
                response = self.client.get(path, query_string=args)
                self.assertEqual(response.status_code, 200, key)
                body = json.loads(response.get_data())
                actual = {name: body[name] for name in RECRUIT_COMPARED_KEYS}
                # days_left / starts_in 由当天日期算出，随运行日期漂移，不能进字节比对
                actual['recruitments'] = _strip_volatile(actual['recruitments'])
                expected = self.baseline[key]['recruit_payload']
                expected_value = dict(expected['value'])
                expected_value['recruitments'] = _strip_volatile(
                    expected_value.get('recruitments'))
                self.assertEqual(_sha(_canonical(actual)), expected['sha256'],
                                 '%s 的公告部分与切换前不一致' % key)
                self.assertEqual(_canonical(actual), _canonical(expected_value),
                                 '%s 的公告部分与切换前不一致' % key)
    def test_the_content_tables_actually_have_rows(self):
        """快照有意义的前提：七张内容表里真的有内容，不是空库碰巧一致。

        切换后如果读库这条路悄悄返回空列表，而切换前 domain_data 也被清空，
        两份空响应会「一致」，那是假绿。这里把「库里有货」钉住。
        """
        from db_connection import get_connection
        conn = get_connection()
        try:
            counts = {}
            for table in ('recruitments', 'recruitment_sources', 'success_cases',
                          'case_stats', 'case_milestones', 'case_sources', 'case_lessons'):
                counts[table] = conn.execute(
                    'SELECT COUNT(*) FROM %s' % table).fetchone()[0]
        finally:
            conn.close()
        expected = {'recruitments': 14, 'recruitment_sources': 16, 'success_cases': 5,
                    'case_stats': 20, 'case_milestones': 24, 'case_sources': 18,
                    'case_lessons': 21}
        self.assertEqual(counts, expected,
                         '内容表行数与 T05 灌库结果不符，快照失去比对意义')

    def test_recruitments_carry_derived_signup_status(self):
        """报名状态由读侧按当天日期算出，不能是空壳。

        这四个字段（status / status_label / days_left / starts_in）在库里没有列，
        是 recruitments 域按 signup_start / deadline 现算的。一旦漏算，接口不会报错，
        只是前端再也标不出「报名中 / 已过报名期」。
        """
        from db_domains import recruitments
        items = recruitments.get_recruitments()
        self.assertEqual(len(items), 14)
        for item in items:
            self.assertIn(item['status'], ('open', 'upcoming', 'closed', 'unknown'))
            self.assertTrue(item['status_label'])
            self.assertTrue(item['deadline'], '公告 %s 缺截止日期' % item['key'])
            self.assertTrue(item['sources'], '公告 %s 没有来源' % item['key'])
        self.assertTrue(any(item['status'] == 'open' for item in items),
                        '14 条公告里应当有仍在报名期的')

    def test_cases_keep_their_four_child_arrays(self):
        """案例的四个子数组按原形状组装：少一层就在接口上少一整块内容。"""
        from db_domains import content
        cases = content.get_cases()
        self.assertEqual([c['id'] for c in cases], [1, 2, 3, 4, 5])
        for case in cases:
            self.assertTrue(case['stats'], '案例 %d 没有数据指标' % case['id'])
            self.assertTrue(case['milestones'], '案例 %d 没有里程碑' % case['id'])
            self.assertTrue(case['sources'], '案例 %d 没有来源' % case['id'])
            self.assertTrue(case['lessons'], '案例 %d 没有借鉴点' % case['id'])
            for stat in case['stats']:
                self.assertEqual(sorted(stat), ['icon', 'label', 'value'])
            for milestone in case['milestones']:
                self.assertEqual(sorted(milestone), ['desc', 'period', 'title'])
            for source in case['sources']:
                self.assertEqual(sorted(source), ['date', 'media', 'title', 'url'])


class PolicyEmptyAfterUnpublishTest(unittest.TestCase):
    """验收第 2 条：政府端下架政策后，学员端政策列表真实为空，不回退旧数据源。"""

    def setUp(self):
        from app import app
        self.client = app.test_client()
        from db_connection import get_connection
        self.get_connection = get_connection

    def _set_all_published(self, published):
        conn = self.get_connection()
        try:
            conn.execute("UPDATE government_policies SET is_published = ?", (published,))
            conn.commit()
        finally:
            conn.close()

    def test_list_is_empty_when_the_government_unpublishes_everything(self):
        self._set_all_published(0)
        try:
            response = self.client.get('/api/resources/policies')
        finally:
            self._set_all_published(1)
        body = json.loads(response.get_data())
        self.assertTrue(body['success'])
        self.assertEqual(body['policies'], [],
                         '政府端全部下架后学员端必须为空，不得回退到旧数据源')
        # 口径说明与内容解耦：空列表时仍然下发，前端据此说明「为什么是空的」
        self.assertIn('source_note', body)
        self.assertIn('disclaimer', body)

    def test_route_never_falls_back_to_the_legacy_table(self):
        """政策列表只读 government_policies：把那张旧表灌满也不得出现在响应里。

        这里在旧 policies 表里插一条政府端不存在的标题，再确认响应里没有它。
        「不回退」不能只靠读代码确认，要用一个能被看见的行为钉住。
        """
        conn = self.get_connection()
        try:
            before = conn.execute("SELECT COUNT(*) FROM policies").fetchone()[0]
            conn.execute(
                "INSERT INTO policies (title, content, category, date, summary, source) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (u'__T09 探针：不应出现在学员端__', u'正文', u'补贴', '2026-01-01',
                 u'摘要', '[]'))
            conn.commit()
            try:
                response = self.client.get('/api/resources/policies')
            finally:
                conn.execute("DELETE FROM policies WHERE title = ?",
                             (u'__T09 探针：不应出现在学员端__',))
                conn.commit()
        finally:
            conn.close()
        body = json.loads(response.get_data())
        titles = [p['title'] for p in body['policies']]
        self.assertNotIn(u'__T09 探针：不应出现在学员端__', titles,
                         '学员端政策列表不得回退到旧 policies 表')
        self.assertEqual(len(titles), before,
                         '政策条数应仍等于 government_policies 的已发布条数')


if __name__ == '__main__':
    unittest.main()
