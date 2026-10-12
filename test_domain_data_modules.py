# -*- coding: utf-8 -*-
"""五个领域数据模块的搬迁一致性测试（T06）。

背景：这五个模块（病虫害知识、公开招聘、成功案例、政策、农时日历种子）是**纯数据模块**，
内容一行不改地搬进 domains/<领域>/ 下。本测试锁住「搬完之后内容没变」这条验收条件。

为什么用「结构 + 关键数据快照」而不是文件哈希：搬迁后这些文件仍会被人工编辑
（新增一条政策、补一张实拍图）。哈希会把「内容被正常编辑了」和「搬错了」混为一谈，
于是这个测试会在一次正当编辑后变红，逼人回来改测试。快照只覆盖**结构形状与关键计数**，
编辑内容通常不改变这些形状，因此它是「搬错就红、正常编辑不红」的稳定哨兵。

快照怎么取到的：搬迁前跑一次探针脚本，把每个模块的公开符号面、条目计数、关键 id、
口径文案长度写进本文件。搬迁后由本测试重新导入新位置的模块并逐项比对。
"""

import io
import os
import sys
import unittest

# 后端代码整体迁入 backend/ 后，被测的 database / db_domains / domain_data
# 都在 backend/ 下，因此路径基准指向 backend/ 而不是仓库根。
REPO_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend')
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

DATA_DIR = os.path.join(REPO_ROOT, 'domain_data')

MODULES = {
    'pest_data': 'domain_data/pest_diagnosis/pest_data.py',
    'jobs_data': 'domain_data/employment/jobs_data.py',
    'cases_data': 'domain_data/resources/cases_data.py',
    'policies_data': 'domain_data/resources/policies_data.py',
    'farming_data': 'domain_data/agriculture/farming_data.py',
}

# 领域归属：数据模块按 T05 已建立的领域结构分组，与 db_domains/ 的领域划分对得上。
DOMAINS = {
    'pest_data': 'pest_diagnosis',
    'jobs_data': 'employment',
    'cases_data': 'resources',
    'policies_data': 'resources',
    'farming_data': 'agriculture',
}


def read_module(relative):
    with io.open(os.path.join(REPO_ROOT, relative), encoding='utf-8') as handle:
        return handle.read()


def public_symbols(module):
    return sorted(name for name in vars(module) if not name.startswith('_'))


class DataModuleLocationTest(unittest.TestCase):
    """五个数据模块必须在新位置，且原位置不得再留副本（单一事实源）。"""

    def test_each_data_module_lives_in_its_domain_package(self):
        for module_name, relative in MODULES.items():
            path = os.path.join(REPO_ROOT, relative)
            self.assertTrue(os.path.isfile(path),
                            '%s 不在预期位置 %s' % (module_name, relative))

    def test_no_second_copy_at_repo_root(self):
        """同一份数据不得有两个副本：原位置必须搬空。"""
        for module_name in MODULES:
            stray = os.path.join(REPO_ROOT, module_name + '.py')
            self.assertFalse(os.path.exists(stray),
                             '仓库根仍留着 %s，出现两份数据' % (module_name + '.py'))

    def test_manifest_moves_with_its_consumer(self):
        """pest_image_manifest 只被 pest_data 消费，必须跟着它一起搬。"""
        moved = os.path.join(DATA_DIR, 'pest_diagnosis', 'pest_image_manifest.py')
        stray = os.path.join(REPO_ROOT, 'pest_image_manifest.py')
        self.assertTrue(os.path.isfile(moved), 'pest_image_manifest.py 没有跟着搬走')
        self.assertFalse(os.path.exists(stray), '仓库根仍留着 pest_image_manifest.py')

    def test_each_module_sits_under_its_domain(self):
        """数据模块必须落在与它所属领域同名的子包里。"""
        for module_name, relative in MODULES.items():
            expected = 'domain_data/%s/%s.py' % (DOMAINS[module_name], module_name)
            self.assertEqual(relative, expected)

    def test_domain_data_has_no_route_blueprints(self):
        """T01 的检查器把「含 Blueprint 定义的目录」判为领域路由目录。

        domain_data/ 是纯数据层，一个蓝图都不该有：这里一旦出现蓝图，
        该目录就会被判成路由层，1000+ 行的 pest_data.py 立刻撞上 600 行上限。
        """
        for dirpath, dirnames, filenames in os.walk(DATA_DIR):
            dirnames[:] = [d for d in dirnames if d != '__pycache__']
            for filename in filenames:
                if not filename.endswith('.py'):
                    continue
                path = os.path.join(dirpath, filename)
                self.assertNotIn('Blueprint(', read_module(os.path.relpath(path, REPO_ROOT)),
                                 '%s 里出现了蓝图定义' % filename)

    def test_reference_sites_no_longer_import_from_repo_root(self):
        """引用方必须改成从新位置导入，仓库里不能再有指向旧路径的顶层 import。"""
        for dirpath, dirnames, filenames in os.walk(REPO_ROOT):
            dirnames[:] = [d for d in dirnames
                           if d not in ('.venv', 'node_modules', '__pycache__',
                                        '.git', '.scratch', 'e2e')]
            for filename in filenames:
                if not filename.endswith('.py'):
                    continue
                path = os.path.join(dirpath, filename)
                relative = os.path.relpath(path, REPO_ROOT).replace(os.sep, '/')
                if relative.startswith('domain_data/'):
                    continue
                source = read_module(relative)
                for module_name in MODULES:
                    for statement in ('import %s' % module_name,
                                      'import %s as' % module_name,
                                      'from %s import' % module_name):
                        self.assertNotIn(
                            '\n%s' % statement, '\n' + source,
                            '%s 仍在按旧路径 import %s' % (relative, module_name))

    def test_domain_data_packages_are_not_blueprint_directories(self):
        """T01 的检查器把「含 Blueprint 定义的目录」判为领域路由目录。

        数据模块目录里不能出现蓝图，否则它们会被误判成路由层并套上 600 行上限
        （pest_data.py 有 1999 行），也会让「领域间不得 import」误伤数据模块。
        """
        for relative in MODULES.values():
            source = read_module(relative)
            self.assertNotIn('Blueprint(', source,
                             '%s 里出现了蓝图定义，所在目录会被判为路由目录' % relative)

    def test_data_module_paths_avoid_shared_layer_names(self):
        """T01 的检查器把路径上带 shared/core/ai 的模块判为共享层。

        数据模块若落在这些名字下，就会被套上「共享层不得 import 领域」的约束。
        """
        for module_name, relative in MODULES.items():
            parts = os.path.dirname(relative).replace(os.sep, '/').split('/')
            for part in parts:
                self.assertNotIn(part, ('shared', 'core', 'ai'),
                                 '%s 的路径 %s 含共享层名 %s' % (module_name, relative, part))


class PestDataTest(unittest.TestCase):
    """病虫害知识：速查与诊断共用的唯一事实源。"""

    @classmethod
    def setUpClass(cls):
        from domain_data.pest_diagnosis import pest_data
        cls.mod = pest_data

    def test_public_symbol_surface(self):
        self.assertEqual(public_symbols(self.mod), [
            'PEST_CROP_ORDER', 'PEST_KNOWLEDGE', 'PEST_SOURCES', 'PEST_SOURCE_MAP',
            'get_pest_stats', 'iter_pest_entries',
        ])

    def test_source_registry(self):
        self.assertEqual(len(self.mod.PEST_SOURCES), 24)
        self.assertEqual(len(self.mod.PEST_SOURCE_MAP), 24)

    def test_knowledge_volume_and_crop_order(self):
        self.assertEqual(len(self.mod.PEST_KNOWLEDGE), 8)
        self.assertEqual(self.mod.PEST_CROP_ORDER,
                         ['lychee', 'longan', 'citrus', 'banana', 'rice', 'tea',
                          'vegetable', 'aquatic'])
        self.assertEqual(len(list(self.mod.iter_pest_entries())), 45)

    def test_stats_shape(self):
        self.assertEqual(self.mod.get_pest_stats(),
                         {'crops': 8, 'entries': 45, 'with_image': 18, 'verified': 0})

    def test_first_entry_keeps_rich_fields(self):
        entry = self.mod.PEST_KNOWLEDGE['lychee']['common_diseases'][0]
        self.assertEqual(sorted(entry), [
            'alias', 'chem_table', 'disease', 'id', 'image', 'is_verified', 'kind',
            'occurrence', 'part', 'pathogen', 'prevention', 'registered',
            'safety_note', 'severity', 'sources', 'symptoms', 'treatment',
        ])

    def test_manifest_merged_images(self):
        """实拍图清单在导入时合并进 PEST_KNOWLEDGE，搬目录后不能失效。"""
        with_image = [e for _, _, e in self.mod.iter_pest_entries() if e.get('image')]
        self.assertEqual(len(with_image), 18)
        sample = self.mod.PEST_IMAGES if hasattr(self.mod, 'PEST_IMAGES') else None
        # 合并后第一条带图条目的 image 仍是 manifest 里的形状
        first = next(e for _, _, e in self.mod.iter_pest_entries() if e.get('image'))
        self.assertEqual(sorted(first['image']),
                         ['caption', 'credit', 'file', 'license', 'note', 'shot_date',
                          'source_url'])


class JobsDataTest(unittest.TestCase):
    """公开招聘：就业对接域的策展内容，不落库。"""

    @classmethod
    def setUpClass(cls):
        from domain_data.employment import jobs_data
        cls.mod = jobs_data

    def test_public_symbol_surface(self):
        self.assertEqual(public_symbols(self.mod), [
            'CATEGORY_LIST', 'RECRUIT_DATA', 'RECRUIT_DISCLAIMER',
            'RECRUIT_SOURCE_NOTE', 'STATUS_LABEL',
            'get_recruitment', 'get_recruitment_list', 'get_recruitment_notes',
        ])

    def test_recruitment_volume_and_keys(self):
        self.assertEqual(len(self.mod.RECRUIT_DATA), 14)
        self.assertEqual([r['key'] for r in self.mod.RECRUIT_DATA], [
            'hj-nync-2026', 'lp-sanjiao-2026', 'gz-dwfyz-2026', 'lc-beixiang-gy-2026',
            'hz-tongqing-gy-2026', 'ys-jiangying-gy-2026', 'szyf-2026', 'xy-gy-2026',
            'bl-gy-2026', 'yjc-gy-2026', 'gz-gy-2026-4', 'ts-baisha-2026',
            'ln-sanjiang-2026', 'lp-xiuduan-2026',
        ])

    def test_categories_and_status_labels(self):
        self.assertEqual(self.mod.CATEGORY_LIST, ['农业技术', '基层服务', '乡村治理'])
        self.assertEqual(self.mod.STATUS_LABEL, {
            'upcoming': '即将开始报名', 'open': '报名中',
            'closed': '已过报名期', 'unknown': '详见公告',
        })

    def test_notes_and_entry_shape(self):
        notes = self.mod.get_recruitment_notes()
        self.assertEqual(sorted(notes), ['disclaimer', 'source_note'])
        self.assertEqual(len(self.mod.RECRUIT_SOURCE_NOTE), 103)
        self.assertEqual(len(self.mod.RECRUIT_DISCLAIMER), 67)
        self.assertEqual(sorted(self.mod.RECRUIT_DATA[0]), [
            'category', 'contact', 'deadline', 'description', 'education', 'experience',
            'headcount', 'job_type', 'key', 'org', 'publish_date', 'region', 'salary',
            'signup_start', 'signup_way', 'sources', 'title',
        ])

    def test_get_recruitment_list_returns_every_entry(self):
        self.assertEqual(len(self.mod.get_recruitment_list()), 14)


class CasesDataTest(unittest.TestCase):
    """成功案例：本土资源域的策展内容，不落库。"""

    @classmethod
    def setUpClass(cls):
        from domain_data.resources import cases_data
        cls.mod = cases_data

    def test_public_symbol_surface(self):
        self.assertEqual(public_symbols(self.mod), [
            'CASE_SOURCE_NOTE', 'LESSONS_NOTE', 'SUCCESS_CASES', 'get_case', 'get_cases',
        ])

    def test_case_volume_and_ids(self):
        self.assertEqual(len(self.mod.SUCCESS_CASES), 5)
        self.assertEqual([c['id'] for c in self.mod.SUCCESS_CASES], [1, 2, 3, 4, 5])
        self.assertEqual([c['id'] for c in self.mod.get_cases()], [1, 2, 3, 4, 5])

    def test_get_case_returns_full_record(self):
        case = self.mod.get_case(1)
        self.assertEqual(case['title'], '梅县南福村：一颗金柚的电商逆袭')
        self.assertEqual(case['location'], '梅州市梅县区雁洋镇南福村')
        self.assertEqual(case['region'], '梅州')
        self.assertEqual(len(case['stats']), 4)
        self.assertEqual(len(case['milestones']), 4)
        self.assertEqual(len(case['sources']), 4)
        self.assertEqual(len(case['lessons']), 4)

    def test_every_case_keeps_twelve_fields(self):
        self.assertEqual({c['id']: len(c) for c in self.mod.SUCCESS_CASES},
                         {1: 12, 2: 12, 3: 12, 4: 12, 5: 12})

    def test_notes_wording(self):
        self.assertEqual(len(self.mod.CASE_SOURCE_NOTE), 33)
        self.assertEqual(len(self.mod.LESSONS_NOTE), 22)


class PoliciesDataTest(unittest.TestCase):
    """政策：本土资源域的预置内容。"""

    @classmethod
    def setUpClass(cls):
        from domain_data.resources import policies_data
        cls.mod = policies_data

    def test_public_symbol_surface(self):
        self.assertEqual(public_symbols(self.mod), [
            'POLICIES', 'POLICY_DISCLAIMER', 'POLICY_SOURCE_NOTE',
            'get_policies', 'get_policy_notes',
        ])

    def test_policy_volume_and_titles(self):
        titles = ['农业补贴申请指南', '农村电商扶持政策', '非遗传承人认定办法',
                  '农业技术培训补贴', '农产品质量安全认证']
        self.assertEqual([p['title'] for p in self.mod.POLICIES], titles)
        self.assertEqual([p['title'] for p in self.mod.get_policies()], titles)

    def test_every_policy_keeps_six_fields(self):
        self.assertEqual({p['title']: len(p) for p in self.mod.POLICIES}, {
            '农业补贴申请指南': 6, '农村电商扶持政策': 6, '非遗传承人认定办法': 6,
            '农业技术培训补贴': 6, '农产品质量安全认证': 6,
        })

    def test_notes_wording(self):
        notes = self.mod.get_policy_notes()
        self.assertEqual(sorted(notes), ['disclaimer', 'source_note'])
        self.assertEqual(len(self.mod.POLICY_SOURCE_NOTE), 49)
        self.assertEqual(len(self.mod.POLICY_DISCLAIMER), 29)


class FarmingDataTest(unittest.TestCase):
    """农事基础数据：农业培训域农时日历的种子。"""

    @classmethod
    def setUpClass(cls):
        from domain_data.agriculture import farming_data
        cls.mod = farming_data

    def test_public_symbol_surface(self):
        self.assertEqual(public_symbols(self.mod), [
            'FARMING_CATEGORY_LABELS', 'FARMING_PHENOPHASES', 'FARMING_PRODUCTS',
            'FARMING_SOURCES', 'FARMING_TASKS',
        ])

    def test_products_and_labels(self):
        self.assertEqual([p['id'] for p in self.mod.FARMING_PRODUCTS],
                         ['lychee', 'longan', 'citrus', 'banana', 'aquatic', 'rice',
                          'tea', 'vegetable'])
        self.assertEqual(self.mod.FARMING_CATEGORY_LABELS,
                         {'fertilize': '施肥', 'pest': '植保', 'harvest': '采收',
                          'manage': '管理', 'water': '水分'})

    def test_sources_and_phases(self):
        self.assertEqual(len(self.mod.FARMING_SOURCES), 14)
        self.assertEqual([s['key'] for s in self.mod.FARMING_SOURCES], [
            'GD-LYCHEE-TG', 'GD-LONGAN-TG', 'CARS-LZ', 'MOA-RICE-TG', 'GD-TEA-TG',
            'GD-VEG-TG', 'MOA-AQUA-TG', 'GD-FERT-GUIDE', 'CMA-AGRO', 'MOA-PEST-MON',
            'GD-CITRUS-TG', 'CARS-CITRUS', 'GD-BANANA-TG', 'CARS-BANANA',
        ])
        self.assertEqual(len(self.mod.FARMING_PHENOPHASES), 38)

    def test_tasks_volume_months_and_shape(self):
        self.assertEqual(len(self.mod.FARMING_TASKS), 123)
        self.assertEqual(sorted({t['month'] for t in self.mod.FARMING_TASKS}),
                         list(range(1, 13)))
        self.assertEqual(sorted(self.mod.FARMING_TASKS[0]), [
            'category', 'date_basis', 'description', 'icon', 'month', 'phase',
            'priority', 'product_id', 'source_key', 'task_md', 'tip', 'title',
        ])


if __name__ == '__main__':
    unittest.main()
