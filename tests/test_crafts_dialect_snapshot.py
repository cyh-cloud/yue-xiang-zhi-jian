# -*- coding: utf-8 -*-
"""技艺与方言内容切库的响应快照比对（T08）。

切换前先跑本文件，把四条接口的响应字节写成基线；切库后再跑一次，逐字节比对。
这里断言的是**字节**，不是「结构上有 steps / purchase_guide 这些键」——
键的存在性断言不出「budget 少了一档」「items 少了 where 列」这类形状变化，
而采购指南是三层嵌套，读回时按原形状组装正是本票的核心风险。

基线缺失时自动生成并在本次运行报失败（提示再跑一次即可验证），
避免「第一条就建基线」被误当成通过。
"""

import json
import os
import sys
import unittest

# 后端代码整体迁入 backend/ 后，app 与 db_domains 都在 backend/ 下。
_BACKEND_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend')
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

SNAPSHOT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'snapshots')

# 四条接口覆盖票面的「2 条技艺 + 2 条方言」，外加两条契约分支：
# 未知技艺 id 的 200 + success=False、未知方言 id 退回粤语。
SNAPSHOT_PATHS = (
    ('crafts_list.json', '/api/crafts/list'),
    ('craft_embroidery.json', '/api/crafts/embroidery'),
    ('craft_woodcarving.json', '/api/crafts/woodcarving'),
    ('craft_ceramics.json', '/api/crafts/ceramics'),
    ('craft_lacquer.json', '/api/crafts/lacquer'),
    ('craft_unknown.json', '/api/crafts/no-such-craft'),
    ('dialects.json', '/api/resources/dialects'),
    ('dialect_info.json', '/api/resources/dialect-info'),
    ('dialect_info_cantonese.json', '/api/resources/dialect-info?dialect=cantonese'),
    ('dialect_info_hakka.json', '/api/resources/dialect-info?dialect=hakka'),
    ('dialect_info_teochew.json', '/api/resources/dialect-info?dialect=teochew'),
    ('dialect_info_unknown.json', '/api/resources/dialect-info?dialect=no-such'),
)


def _canonical(body):
    """响应字节的规范形式：UTF-8 解码后统一行尾。

    比对的是服务端实际下发的字节，不是 Python 对象：json.loads 之后键序由
    插入序决定，而键序变化对前端无害、对「逐字节一致」的验收标准却致命。
    """
    return body.decode('utf-8').replace('\r\n', '\n')


class CraftsDialectSnapshotTest(unittest.TestCase):
    """切换前后的响应字节必须一致。"""

    def setUp(self):
        from app import app
        self.client = app.test_client()

    def _snapshot_path(self, name):
        return os.path.join(SNAPSHOT_DIR, name)

    def test_responses_match_the_recorded_baseline(self):
        missing = []
        for name, path in SNAPSHOT_PATHS:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200, path)
            actual = _canonical(response.get_data())
            baseline_file = self._snapshot_path(name)
            if not os.path.isfile(baseline_file):
                missing.append(name)
                os.makedirs(SNAPSHOT_DIR, exist_ok=True)
                with open(baseline_file, 'wb') as handle:
                    handle.write(response.get_data())
                continue
            with open(baseline_file, 'rb') as handle:
                expected = _canonical(handle.read())
            self.assertEqual(
                actual, expected,
                '%s 的响应与基线不一致\n期望（截断）: %.2000s\n实际（截断）: %.2000s'
                % (path, expected, actual))
        if missing:
            self.fail('已生成缺失的快照：%s。再跑一次即可验证。' % ', '.join(missing))

    def test_purchase_guide_keeps_its_nested_shape(self):
        """采购指南三层嵌套（分类 -> 条目 -> 预算）在接口输出里形状不变。

        单独列出来而不是只靠上面的字节比对：字节一致是结果，这条锁住**为什么会变**。
        库侧是拆平的四张表（crafts / craft_steps / craft_purchase_categories /
        craft_purchase_items / craft_budgets），读回时要按 sort_order 重组，
        漏一层、错一层、字段少一个，都在这里现形。
        """
        response = self.client.get('/api/crafts/embroidery')
        self.assertEqual(response.status_code, 200)
        guide = json.loads(response.get_data(as_text=True))['data']['purchase_guide']
        self.assertEqual(sorted(guide), ['budget', 'buying_tips', 'categories'])
        self.assertEqual(sorted(guide['budget']), ['advanced', 'starter'])
        self.assertTrue(guide['buying_tips'])
        categories = guide['categories']
        self.assertEqual([c['key'] for c in categories], ['essential', 'consumable', 'advanced'])
        for category in categories:
            self.assertEqual(sorted(category), ['desc', 'items', 'key', 'label'])
            self.assertTrue(category['items'], category['key'])
            for item in category['items']:
                self.assertEqual(sorted(item), ['name', 'price', 'spec', 'tip', 'where'])
                for key in ('name', 'price', 'spec', 'tip', 'where'):
                    self.assertTrue(item[key], '%s.%s 为空' % (category['key'], key))
        # 条目按 sort_order 归位：拆平存、按 craft_id + category_key 读回
        self.assertEqual(categories[0]['items'][0]['name'], u'实木绣绷（30cm）')
        self.assertEqual(categories[0]['items'][1]['name'], u'广绣专用针套装（12支）')


if __name__ == '__main__':
    unittest.main()
