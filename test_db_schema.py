#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""建表定义的契约测试（内容落库 T04）。

锁住六件事，改动数据结构前先跑它：

1. 表数量与清单：init_db() 建出全部表，新增表漏登记就在这里炸；
2. extra 预留列：全部表都有，且默认值是 '{}'；
3. 复核人字段：farming_tasks 与 pest_entries 各补 verified_by / verified_at；
4. 幂等：init_db() 跑两次，第二次不改变任何一行；
5. 既有库升级：在现库副本上跑 init_db()，既有表的数据一行不丢；
6. 视图等价：5 个视图均可 SELECT，且结果与改写前的直连 SQL 一致。

⚠️ 为什么碰库的用例一律跑子进程：DB_PATH 在 import db_connection 时就定下来了
（既有行为，部署入口也依赖「导入即定位」）。同进程里改 os.environ 不会改变它，
只会让用例悄悄打到 data/yuexiang.db 上，把真实数据写脏。所以碰库的用例都调到
db_schema_probe.py 那个子进程里，用环境变量 YUEXIANG_DB 把库指到临时目录。
父进程只做不碰库的静态检查。

⚠️ 为什么「现库副本」用例必须复制而不是原地跑：data/yuexiang.db 是用户的数据，
虽然已被 .gitignore，也不该被测试写入。副本上验证完逐表比行数，再丢掉副本。
"""

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest

# 后端代码整体迁入 backend/ 后，被测的 db_schema / db_connection 都在 backend/ 下，
# 因此路径基准指向 backend/ 而不是仓库根。
REPO_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend')
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

PROBE = os.path.join(REPO_ROOT, 'db_schema_probe.py')

# 内容落库（T04）新增的 21 张表。pest_entries 在 spec 里写作「已存在，改为补列」，
# 但现库里并没有这张表（病虫害内容此前只在 domain_data 里），所以它同样要建。
NEW_TABLES = (
    'farming_categories', 'pest_crops', 'pest_entries', 'pest_sources',
    'pest_entry_sources', 'pest_images', 'recruitments', 'recruitment_sources',
    'success_cases', 'case_stats', 'case_milestones', 'case_sources',
    'case_lessons', 'dialects', 'dialect_phrases', 'dialect_quick_questions',
    'crafts', 'craft_steps', 'craft_purchase_categories', 'craft_purchase_items',
    'craft_budgets',
)

# init_db() 建出的全部表。sqlite_sequence 是 SQLite 在出现第一张 AUTOINCREMENT 表时
# 自动建的书目表，不属于业务表，故不在清单里（用 NOT LIKE 'sqlite_%' 排除）。
EXPECTED_TABLES = {
    'announcements', 'assignment_submissions', 'assignments', 'carousels',
    'certificates', 'comments', 'content_reviews', 'course_materials', 'courses',
    'discussions', 'farming_categories', 'farming_phenophases',
    'farming_products', 'farming_reminder_log',
    'farming_sources', 'farming_subscriptions', 'farming_tasks',
    'government_policies', 'job_applications', 'job_intents', 'job_listings',
    'messages', 'models_3d', 'news_articles', 'notification_reads',
    'notifications', 'pest_crops', 'pest_entries', 'pest_entry_sources',
    'pest_images', 'pest_sources', 'points', 'policies', 'procurements',
    'recruitment_sources', 'recruitments', 'resumes', 'saved_jobs',
    'students', 'success_cases', 'system_announcements', 'user_sessions', 'users',
    'case_stats', 'case_milestones', 'case_sources', 'case_lessons',
    'dialects', 'dialect_phrases', 'dialect_quick_questions', 'crafts',
    'craft_steps', 'craft_purchase_categories', 'craft_purchase_items',
    'craft_budgets',
    # 迁移记录表（T05）：migrations/0001_content_to_db.py 靠它防重入
    'schema_migrations',
}
# 36 张既有表 + 21 张新表。spec 4.4 写作「36 -> 56」，那是按
# 「pest_entries 已存在、只补列」算的；实测现库里并没有 pest_entries
# （病虫害内容此前只在代码常量里，从未落库），所以实际新建 21 张。
# T10 删掉两张内容签名表（seed_meta / farming_seed_meta），故 58 - 2 = 56。
EXPECTED_TABLE_COUNT = 56

EXPECTED_VIEWS = {
    'v_enterprise_applications', 'v_enterprise_job_stats', 'v_home_stats',
    'v_submission_context', 'v_reviewable_models',
}

# 补 verified_by / verified_at 的两张表（REFACTOR-PLAN 4.5）
VERIFIED_TABLES = ('farming_tasks', 'pest_entries')

# 视图 -> 改写前的直连 SQL（REFACTOR-PLAN 3.2 表格里的原始位置）。
# 探针在同一个库上分别跑视图与直连 SQL，逐行比对；不一致就是视图定义漂了。
VIEW_EQUIVALENT_SQL = {
    'v_enterprise_applications': """
        SELECT ja.id, ja.user_id, ja.job_id, ja.status, ja.applied_at,
               jl.title as job_title,
               u.name as applicant_name, u.phone as applicant_phone,
               u.email as applicant_email, u.bio as applicant_bio,
               r.title as resume_title, r.region as resume_region,
               r.education as resume_education, r.work_years as resume_work_years,
               r.phone as resume_phone, r.email as resume_email,
               r.self_eval as resume_self_eval, r.skills as resume_skills,
               r.experience as resume_experience, r.updated_at as resume_updated_at
        FROM job_applications ja
        JOIN job_listings jl ON ja.job_id = jl.id
        JOIN users u ON ja.user_id = u.username
        LEFT JOIN resumes r ON r.user_id = ja.user_id
        ORDER BY ja.applied_at DESC
    """,
    'v_enterprise_job_stats': """
        SELECT jl.enterprise_id,
               SUM(CASE WHEN jl.review_status = 'approved' THEN 1 ELSE 0 END) as total_jobs,
               SUM(CASE WHEN COALESCE(jl.review_status, '') != 'approved' THEN 1 ELSE 0 END) as pending_jobs,
               COUNT(ja.id) as total_apps
        FROM job_listings jl
        LEFT JOIN job_applications ja ON ja.job_id = jl.id
        GROUP BY jl.enterprise_id
    """,
    'v_home_stats': None,      # 三次 COUNT，单独比对
    'v_submission_context': """
        SELECT s.id, s.assignment_id, s.student_id
        FROM assignment_submissions s
        JOIN assignments a ON a.id = s.assignment_id
        ORDER BY s.id
    """,
    'v_reviewable_models': "SELECT * FROM models_3d ORDER BY id",
}


def read_module(name):
    with io.open(os.path.join(REPO_ROOT, name), encoding='utf-8') as handle:
        return handle.read()


class IsolatedDatabaseTest(unittest.TestCase):
    """把探针脚本跑在一份临时库上，拿回它打印的 JSON。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix='t04_schema_')
        self.addCleanup(self._tmp.cleanup)
        self.db_file = os.path.join(self._tmp.name, 'yuexiang.db')

    def probe(self, name, *args):
        env = dict(os.environ)
        env['YUEXIANG_DB'] = self.db_file
        env['PYTHONIOENCODING'] = 'utf-8'
        env['PYTHONUTF8'] = '1'
        result = subprocess.run(
            [sys.executable, PROBE, name] + [str(a) for a in args],
            cwd=REPO_ROOT, env=env, capture_output=True)
        self.assertEqual(
            result.returncode, 0,
            '探针 %s 失败：\n%s\n%s' % (name, result.stdout.decode('utf-8', 'replace'),
                                     result.stderr.decode('utf-8', 'replace')))
        return json.loads(result.stdout.decode('utf-8', 'replace'))


class SchemaDefinitionTest(unittest.TestCase):
    """不碰库的静态检查：建表语句仍在一处，视图定义与建表同住。"""

    def test_create_table_statements_live_in_one_module(self):
        import ast
        holders = []
        for name in ('db_schema.py', 'db_connection.py', 'db_credentials.py',
                     'db_infrastructure_probe.py', 'db_schema_probe.py'):
            if not os.path.exists(os.path.join(REPO_ROOT, name)):
                continue
            for node in ast.walk(ast.parse(read_module(name))):
                if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                        and 'CREATE TABLE' in node.value):
                    holders.append(name)
                    break
        self.assertEqual(holders, ['db_schema.py'], '建表语句散落：%s' % holders)

    def test_view_definitions_live_with_the_schema(self):
        self.assertIn('v_enterprise_applications', read_module('db_schema.py'))
        self.assertIn('v_home_stats', read_module('db_schema.py'))
        self.assertIn('CREATE VIEW IF NOT EXISTS', read_module('db_schema.py'))

    def test_extra_column_is_declared_for_every_new_table(self):
        """20 张新表每张都要带 extra，漏一张将来加字段就得改全库。"""
        source = read_module('db_schema.py')
        for table in NEW_TABLES:
            self.assertIn('CREATE TABLE IF NOT EXISTS %s' % table, source,
                          '新表 %s 的建表语句不见了' % table)
        # 每条 CREATE TABLE 体内都要出现 extra 列
        import re
        for match in re.finditer(r'CREATE TABLE IF NOT EXISTS (\w+) \((.*?)\n\s*\);',
                                 source, re.S):
            self.assertIn("extra TEXT NOT NULL DEFAULT '{}'", match.group(2),
                          '表 %s 没有 extra 预留列' % match.group(1))

    def test_no_index_is_created_on_the_extra_column(self):
        """spec 4.6：extra 不建索引。当前没有任何查询走这一列。"""
        source = read_module('db_schema.py')
        indexes = [line.strip() for line in source.splitlines()
                   if 'CREATE INDEX' in line and 'extra' in line]
        self.assertEqual(indexes, [], 'extra 列不得建索引：%s' % indexes)

    def test_no_index_is_created_on_any_new_table(self):
        """spec 4.4：新表不建索引。等真有需求时在同一处迁移里补，并写清为什么。"""
        source = read_module('db_schema.py')
        offenders = [line.strip() for line in source.splitlines()
                     if 'CREATE INDEX' in line
                     and any(t in line for t in NEW_TABLES)]
        self.assertEqual(offenders, [], '新表上出现了索引：%s' % offenders)


class TableInventoryTest(IsolatedDatabaseTest):
    """init_db() 建出全部表，且清单与本文件登记的一致。"""

    def test_init_db_creates_every_table(self):
        tables = set(self.probe('tables'))
        self.assertEqual(tables, EXPECTED_TABLES)

    def test_table_count_matches_the_spec(self):
        """spec 4.4 写作「36 -> 56」，实测是 58，差异在 pest_entries 与迁移记录表。

        spec 把 pest_entries 算作「已存在，改为补列」，但现库里并没有这张表，
        病虫害内容此前只活在 domain_data 里，从未落库。所以它是新建而非补列，
        36 + 21 = 57；T05 又加了 schema_migrations（迁移记录表），故 58。
        这里断言真实建出的表数，让文档与库的差异显式可见。
        """
        self.assertEqual(len(self.probe('tables')), EXPECTED_TABLE_COUNT)

    def test_init_db_creates_the_five_views(self):
        self.assertEqual(set(self.probe('views')), EXPECTED_VIEWS)

    def test_every_table_carries_the_extra_column(self):
        missing = self.probe('tables_missing_extra')
        self.assertEqual(missing, [], '这些表没有 extra 列：%s' % missing)

    def test_extra_column_defaults_to_empty_json_object(self):
        defaults = self.probe('extra_defaults')
        wrong = {t: d for t, d in defaults.items() if d != "'{}'"}
        self.assertEqual(wrong, {}, 'extra 的默认值不是 {}：%s' % wrong)

    def test_farming_tasks_and_pest_entries_carry_the_verifier_fields(self):
        cols = self.probe('verified_columns')
        for table in VERIFIED_TABLES:
            self.assertIn('verified_by', cols[table],
                          '%s 缺 verified_by' % table)
            self.assertIn('verified_at', cols[table],
                          '%s 缺 verified_at' % table)

    def test_verifier_fields_default_to_empty_string(self):
        defaults = self.probe('verified_defaults')
        wrong = {'%s.%s' % k: v for k, v in defaults.items() if v != "''"}
        self.assertEqual(wrong, {}, '复核人字段的默认值不是空串：%s' % wrong)


class IdempotenceTest(IsolatedDatabaseTest):
    """启动路径只建表与补列，跑两次第二次不变。"""

    def test_second_init_changes_no_row(self):
        first, second = self.probe('idempotent_counts')
        self.assertEqual(first, second, '第二次 init_db() 改变了数据行')

    def test_second_init_keeps_the_schema(self):
        before, after = self.probe('idempotent_schema')
        self.assertEqual(before, after)

    def test_init_db_does_not_seed_content_rows(self):
        """ADR 0002：启动路径只建表与补列，不播种、不重灌。"""
        counts = self.probe('idempotent_counts')[0]
        content_tables = set(NEW_TABLES) - {'pest_entry_sources', 'pest_images',
                                            'case_stats', 'case_milestones',
                                            'case_sources', 'case_lessons',
                                            'dialect_phrases',
                                            'dialect_quick_questions',
                                            'craft_steps',
                                            'craft_purchase_categories',
                                            'craft_purchase_items', 'craft_budgets',
                                            'recruitment_sources'}
        seeded = {t: n for t, n in counts.items()
                  if t in content_tables and n != 0}
        self.assertEqual(seeded, {}, 'init_db() 往内容表里写了行：%s' % seeded)

    def test_third_init_also_changes_nothing(self):
        first, second, third = self.probe('idempotent_counts_thrice')
        self.assertEqual(first, second)
        self.assertEqual(second, third)


class ExistingDatabaseUpgradeTest(unittest.TestCase):
    """在现库副本上跑 init_db()：既有 36 张表的数据一行不丢。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix='t04_upgrade_')
        self.addCleanup(self._tmp.cleanup)
        # __file__ 在仓库根，REPO_ROOT 是 backend/，所以现库在 REPO_ROOT 的上级。
        self.real_db = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            'data', 'yuexiang.db')

    def test_existing_database_keeps_every_row(self):
        if not os.path.isfile(self.real_db):
            self.skipTest('现库 data/yuexiang.db 不存在，跳过升级用例')
        import shutil
        copy = os.path.join(self._tmp.name, 'yuexiang.db')
        shutil.copyfile(self.real_db, copy)
        env = dict(os.environ)
        env['YUEXIANG_DB'] = copy
        env['PYTHONIOENCODING'] = 'utf-8'
        env['PYTHONUTF8'] = '1'
        result = subprocess.run([sys.executable, PROBE, 'upgrade'],
                                cwd=REPO_ROOT, env=env, capture_output=True)
        self.assertEqual(result.returncode, 0,
                         '升级探针失败：\n%s\n%s' % (
                             result.stdout.decode('utf-8', 'replace'),
                             result.stderr.decode('utf-8', 'replace')))
        report = json.loads(result.stdout.decode('utf-8', 'replace'))
        self.assertEqual(report['lost'], {},
                         '既有库升级后丢了行：%s' % report['lost'])
        self.assertGreaterEqual(report['table_count'], 57,
                                '升级后表数量不足')


class ViewEquivalenceTest(IsolatedDatabaseTest):
    """5 个视图均可 SELECT，且结果与改写前的直连 SQL 等价。"""

    def test_every_view_is_selectable(self):
        """视图在空库上也要能 SELECT（T11 切换前先保证它不是一个坏视图）。"""
        self.assertEqual(self.probe('views_selectable'), True)

    def test_views_match_the_original_direct_sql(self):
        """灌入可比对的数据后，视图逐行等于改写前的直连 SQL。"""
        result = self.probe('view_equivalence')
        self.assertEqual(result, {}, '视图与直连 SQL 不一致：%s' % json.dumps(
            result, ensure_ascii=False)[:2000])

    def test_view_columns_keep_the_original_aliases(self):
        """列名必须与原直连 SQL 的别名一致，否则 T11 换了查询方就静默改字段名。"""
        cols = self.probe('view_columns')
        self.assertEqual(cols['v_enterprise_applications'][5], 'job_title')
        self.assertEqual(cols['v_enterprise_applications'][6], 'applicant_name')
        self.assertEqual(cols['v_enterprise_applications'][10], 'resume_title')
        self.assertEqual(cols['v_enterprise_job_stats'],
                         ['enterprise_id', 'total_jobs', 'pending_jobs', 'total_apps'])
        self.assertEqual(cols['v_home_stats'], ['farmers', 'courses', 'jobs'])
        self.assertEqual(cols['v_submission_context'][0], 'submission_id')
        self.assertEqual(cols['v_reviewable_models'][0], 'id')


if __name__ == '__main__':
    unittest.main()
