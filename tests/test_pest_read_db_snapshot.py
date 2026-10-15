# -*- coding: utf-8 -*-
"""病虫害内容切库（T07）的响应快照比对：API 层 seam，逐字节比对。

票的验收第 1、2 条是「2 条病虫害接口的响应 JSON 与切换前逐字节一致」与「诊断降级路径
在知识库有数据时结论与切换前一致」。这两条没法靠断言几个字段糊过去：pest-knowledge
一次下发 45 条条目，每条 20 个字段，字段值来自五张表；诊断降级的 treatment /
prevention / symptoms 又是整段文本。所以这里存的是**切换前的原始响应**：

  1. tests/baseline_pest_switch.json 在切换到库之前由一次性脚本生成，记下每条
     响应的 sha256、字节数，以及诊断降级的完整 body；
  2. 本文件的用例在切换后重放同一批请求，逐项比 sha256 与字节数，降级路径再逐字段
     比 body。

为什么把降级 body 一起存下来：降级结论是知识库匹配出来的，匹配结果会随库里条目的
顺序与内容变化，而 sha256 只告诉你不一致、不告诉你怎么不一致。存下 body 之后失败
信息能直接指出是哪个字段变了，不用人肉去 diff 两份 JSON。

为什么不 mock 数据库：这里测的是「读库这条路产出的响应」与切换前「读 domain_data
那条路产出的响应」是否一致。把库 mock 掉就退化回测整形函数，测不到 JOIN 顺序、
JSON 列解析、来源展开这三处真正会出错的地方。
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
                        'baseline_pest_switch.json')

# T12 起速查改成服务端筛选 + 分页，响应多了 total，crops[].count 语义也变了。
# 所以速查那六个变体不再比整个响应体，而是比「除掉分页字段之后」的规范形式
# （见 _strip_pagination），并把 sha256 换成键名 sha256_ex_total 的基线条目。
# 分页本身的新形状由 test_pest_domains.py 的 PestKnowledgeServerFilterTest 覆盖。
#
# 用「排序后 JSON 的 sha256」而不是原文字节数：JSON 键序由 dict 插入顺序决定，
# 新增一个键就会让后面所有键错位，那样比的其实是「JSON 序列化细节」而不是内容。
# 速查的六个变体：全量 + 三个成功筛选 + 两个错误分支。全量那条覆盖
# 45 条条目、8 个作物、18 张授权图与全部来源展开，是比对的主体。
KNOWLEDGE_VARIANTS = (
    ('/api/agriculture/pest-knowledge', {}),
    ('/api/agriculture/pest-knowledge', {'crop': 'lychee'}),
    ('/api/agriculture/pest-knowledge', {'kind': 'pest'}),
    ('/api/agriculture/pest-knowledge', {'q': '炭疽'}),
    ('/api/agriculture/pest-knowledge', {'crop': 'no-such-crop'}),
    ('/api/agriculture/pest-knowledge', {'kind': 'virus'}),
)

# 诊断降级用的症状描述：与荔枝炭疽病的典型症状高度重合，切换前后都能稳定命中
# 同一条目（与 tests/test_pest_domains.py 的 MATCHING_SYMPTOMS 同一口径）。
FALLBACK_SYMPTOMS = u'叶片出现褐色斑点，边缘枯黄，病斑上生出黑色小点'


def _key(path, args):
    if not args:
        return path
    query = '&'.join('%s=%s' % item for item in sorted(args.items()))
    return '%s?%s' % (path, query)


def _strip_pagination(body):
    u"""剥掉 T12 新增/改语义的分页字段，留下切换前的等价内容。

    剥 total 是因为它是新增字段；剥 crops[].count 是因为它的语义从「该作物全部
    条目数」改成了「当前筛选条件下该作物的条目数」，两者本来就不可比。
    entries / stats / disclaimer / crops 的其余字段一律保留，逐字节比对。
    """
    stripped = dict(body)
    stripped.pop('total', None)
    if 'crops' in stripped:
        stripped['crops'] = [
            {k: v for k, v in crop.items() if k != 'count'} for crop in stripped['crops']
        ]
    return stripped


class PestSwitchSnapshotTest(unittest.TestCase):
    """切换到读库之后，病虫害接口的响应与切换前一致。

    诊断降级那条仍逐字节比对（它没被 T12 碰过）；速查那六条比对去掉分页字段后的
    规范形式，因为 T12 新增了 total 并改了 crops[].count 的语义。
    """

    def setUp(self):
        from app import app
        self.client = app.test_client()
        if not os.path.isfile(BASELINE):
            self.fail('缺少切换前快照 %s' % BASELINE)
        with open(BASELINE, encoding='utf-8') as handle:
            self.baseline = json.load(handle)

    def _assert_same(self, key, response):
        expected = self.baseline[key]
        body = response.data
        self.assertEqual(response.status_code, expected['status'],
                         '%s 的状态码从 %d 变成了 %d'
                         % (key, expected['status'], response.status_code))
        self.assertEqual(hashlib.sha256(body).hexdigest(), expected['sha256'],
                         '%s 的响应体与切换前不一致（%d 字节 vs 基线 %d 字节）'
                         % (key, len(body), expected['bytes']))

    def _assert_knowledge_unchanged(self, key, response):
        expected = self.baseline[key]
        self.assertEqual(response.status_code, expected['status'],
                         '%s 的状态码从 %d 变成了 %d'
                         % (key, expected['status'], response.status_code))
        body = json.loads(response.data.decode('utf-8'))
        canonical = json.dumps(_strip_pagination(body), ensure_ascii=False,
                               sort_keys=True).encode('utf-8')
        self.assertEqual(
            hashlib.sha256(canonical).hexdigest(), expected['sha256_ex_total'],
            '%s 去掉分页字段后与切换前不一致' % key)

    def _knowledge(self, args):
        query = '&'.join('%s=%s' % item for item in sorted(args.items()))
        return self.client.get('/api/agriculture/pest-knowledge',
                               query_string=args if args else None)

    def _diagnose_fallback(self):
        import ai.client as ai_client
        original = ai_client.ai_configured
        ai_client.ai_configured = lambda: False
        try:
            return self.client.post(
                '/api/agriculture/diagnose',
                data=json.dumps({'crop': 'lychee', 'symptoms': FALLBACK_SYMPTOMS}),
                content_type='application/json')
        finally:
            ai_client.ai_configured = original

    def test_knowledge_variants_are_byte_identical(self):
        for path, args in KNOWLEDGE_VARIANTS:
            key = _key(path, args)
            with self.subTest(key):
                self._assert_knowledge_unchanged(key, self._knowledge(args))

    def test_diagnosis_fallback_is_byte_identical(self):
        """降级路径：整段响应逐字节一致（含来源角标与免责说明）。"""
        self._assert_same('POST /api/agriculture/diagnose (fallback)',
                          self._diagnose_fallback())

    def test_diagnosis_fallback_conclusion_is_field_for_field_identical(self):
        """降级结论逐字段一致：匹配到的条目、五个文本字段、来源角标。"""
        expected = self.baseline['POST /api/agriculture/diagnose (fallback)']['body']
        body = json.loads(self._diagnose_fallback().data.decode('utf-8'))
        self.assertEqual(body, expected,
                         '降级结论与切换前不一致：\n实际 %s\n基线 %s'
                         % (json.dumps(body, ensure_ascii=False, sort_keys=True),
                            json.dumps(expected, ensure_ascii=False, sort_keys=True)))

    def test_the_knowledge_base_actually_has_rows(self):
        """快照有意义的前提：五张 pest 表里真的有内容，不是空库碰巧一致。

        切换后如果读库这条路悄悄返回空列表，而切换前 domain_data 也被清空，
        两份空响应会「一致」，那是假绿。这里把「库里有货」钉住。
        """
        from db_domains import pest
        stats = pest.get_pest_stats()
        self.assertEqual(stats['crops'], 8, 'pest_crops 应有 8 个作物')
        self.assertEqual(stats['entries'], 45, 'pest_entries 应有 45 条条目')
        self.assertEqual(stats['with_image'], 18, 'pest_images 应有 18 张授权图')

    def test_entries_without_authorized_photo_stay_none(self):
        """无授权实拍图的条目 image 仍为 None，不用示意图冒充真实病征。

        这是硬约定。库里 pest_images 缺行 = 没有授权图，读出来必须是 None；
        一旦有人为了「界面好看」补一个占位 URL，这条用例就红。
        """
        response = self.client.get('/api/agriculture/pest-knowledge?crop=lychee')
        body = json.loads(response.data)
        images = [entry['image'] for entry in body['entries']]
        self.assertTrue(any(image is None for image in images),
                        '荔枝条目里应该有没有授权实拍图的')
        for image in [image for image in images if image is not None]:
            self.assertTrue(image.get('file'), '授权图必须带 file 字段')
            self.assertTrue(image.get('credit'), '授权图必须带署名 credit')

    def test_missing_source_values_are_not_invented(self):
        """来源没给的字段就是空列表，不填一个看起来合理的值。

        库里 chem_table / registered 为空的条目（现库 15 条与 10 条），响应里必须
        原样是空列表，不能是「可参照当地农技站推荐」这类代填内容，也不能因为
        找不到数值就把别的条目的药剂名搬过来。
        """
        from db_domains import pest
        blanks = {e['id']: e for e in pest.get_pest_entries()
                  if not e.get('chem_table') or not e.get('registered')}
        self.assertGreater(len(blanks), 0, '库里应当有没有用量表或登记药剂的条目')
        response = self.client.get('/api/agriculture/pest-knowledge')
        by_id = {entry['id']: entry for entry in
                 json.loads(response.data)['entries']}
        for entry_id, entry in blanks.items():
            for field in ('chem_table', 'registered'):
                if not entry.get(field):
                    self.assertEqual(by_id[entry_id][field], [],
                                     '%s 的 %s 在库里是空的，不得代填'
                                     % (entry_id, field))


if __name__ == '__main__':
    unittest.main()
