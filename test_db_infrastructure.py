#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""数据层基础设施的契约测试（后端按领域拆分 T04；T03 删转发层后重写符号面一段）。

锁住四件事，改动数据结构前先跑它：

1. 连接工厂：数据层只有一个函数建立连接，且 WAL / foreign_keys / busy_timeout 不丢；
2. 建表定义：建表语句只出现在一处，init_db 建出全部表且重复执行不改变结构；
3. 初始化入口：`database.init_db()` 首次建表并播种、重复执行幂等（种子不翻倍、
   审核结论不被覆盖、真实企业数据不被清）；
4. 符号面：每个 `db_domains` 模块对外暴露的函数集合不变，调用方按域 import 后
   仍然拿得到全部名字（转发层 database.py 已在 T03 删除）。

⚠️ 为什么碰库的用例一律跑子进程：DB_PATH 在 import db_connection 时就定下来了
（既有行为，部署入口也依赖「导入即定位」）。同进程里改 os.environ 不会改变它，
只会让用例悄悄打到 data/yuexiang.db 上，把真实数据写脏。所以碰库的用例都调到
db_infrastructure_probe.py 那个子进程里，用环境变量 YUEXIANG_DB 把库指到临时目录。
父进程只做不碰库的静态检查。
"""

import ast
import importlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

# 后端代码整体迁入 backend/ 后，被测的 db_init / db_domains / domain_data
# 都在 backend/ 下，因此路径基准指向 backend/ 而不是仓库根。
REPO_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend')
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import db_connection  # noqa: E402
import repo_paths  # noqa: E402
from test_db_schema import EXPECTED_TABLES  # noqa: E402

PROBE = os.path.join(REPO_ROOT, 'db_infrastructure_probe.py')

# 播种按领域归组后的模块集合。每个新播种模块都会自动进入这两条机械检查：
# 「建表语句只在一处」「只有一个建连点」。
SEED_MODULES = tuple(sorted(
    name for name in os.listdir(REPO_ROOT)
    if name.startswith('db_seed_') and name.endswith('.py')
))
# db_schema_probe.py 是 T04 的 schema 契约测试探针，同样只被测试以子进程调用，
# 不是产品代码；把它纳入机械检查，将来有人在探针里写建表语句才会被发现。
INFRA_MODULES = ('db_connection.py', 'db_schema.py', 'db_credentials.py',
                 'db_schema_probe.py', 'db_init.py') + SEED_MODULES
DATA_LAYER_MODULES = ('db_init.py',) + INFRA_MODULES

# 符号面的期望清单：模块名 -> 该模块必须对外暴露的名字。
# 断言按模块逐个数，不再数 database.py 那个聚合后的 163 个符号：转发层已删，
# 调用方按 from db_domains import farming 后 farming.get_x() 取数，所以, farming
# 「名字还在不在原模块里」就是唯一有意义的形状。
DOMAIN_MODULES = tuple(sorted(
    name for name in os.listdir(os.path.join(REPO_ROOT, 'db_domains'))
    if name.endswith('.py') and name != '__init__.py'
))
DOMAIN_SYMBOLS = {
    'announcements.py': ('add_system_announcement', 'delete_system_announcement',
                         'get_active_system_announcement_ids', 'get_system_announcements'),
    'auth.py': ('authenticate_user', 'create_session', 'delete_session', 'get_session'),
    'certificates.py': ('get_certificates',),
    'community.py': ('add_comment', 'create_discussion', 'get_comments', 'get_discussion',
                     'get_discussions', 'soft_delete_comment', 'soft_delete_discussion'),
    # T09：招募公告与成功案例 / 政策口径改读库，两个新域模块。
    'recruitments.py': ('get_recruitment', 'get_recruitment_notes', 'get_recruitments',
                        # T15 运营后台写侧
                        'get_recruitment_rows', 'get_recruitment_row',
                        'get_recruitment_sources', 'create_recruitment',
                        'update_recruitment', 'delete_recruitment',
                        'create_recruitment_source', 'update_recruitment_source',
                        'delete_recruitment_source'),
    'content.py': ('get_case', 'get_case_notes', 'get_cases', 'get_policy_notes',
                   # T15 运营后台写侧
                   'create_case', 'update_case', 'delete_case',
                   'get_case_stats', 'create_case_stat', 'update_case_stat',
                   'delete_case_stat', 'get_case_milestones', 'create_case_milestone',
                   'update_case_milestone', 'delete_case_milestone',
                   'get_case_sources', 'create_case_source', 'update_case_source',
                   'delete_case_source', 'get_case_lessons', 'create_case_lesson',
                   'update_case_lesson', 'delete_case_lesson'),
    'courses.py': ('add_course_material', 'create_course', 'create_model_3d', 'delete_course',
                   'delete_course_material', 'delete_model_3d', 'get_course',
                   'get_course_materials', 'get_courses', 'get_models_3d', 'update_course'),
    'employment.py': ('ENTERPRISE_JOB_CATEGORIES', 'RESUME_FIELDS', 'add_job_intent',
                      'apply_for_job', 'count_pending_job_listings',
                      'count_unread_job_applications', 'get_application_counts',
                      'get_employment_stats', 'get_job_application_ids', 'get_job_by_id',
                      'get_job_category_counts', 'get_job_intents', 'get_job_listings',
                      'get_job_listings_base', 'get_job_listings_filtered',
                      'get_learner_profile', 'get_resume', 'get_saved_jobs', 'get_similar_jobs',
                      'get_user_applications', 'mark_resume_ai_used', 'parse_salary_bounds',
                      'remove_job_intent', 'save_job', 'save_resume', 'unsave_job'),
    'farming.py': ('clear_farming_reminder_log', 'get_due_farming_tasks',
                   'farming_task_brief', 'get_farming_categories',
                   'get_farming_category_labels', 'get_farming_phenophases',
                   'get_farming_product', 'get_farming_products', 'get_farming_source_map',
                   'get_farming_sources', 'get_farming_subscribers',
                   'get_farming_subscriptions', 'get_farming_task_by_id',
                   'get_farming_tasks', 'has_farming_reminder_sent', 'is_farming_subscribed',
                   'mark_farming_reminder_sent', 'month_in_phase',
                   'set_farming_subscription',
                   # T14 运营后台写侧
                   'REVIEW_STALE_DAYS', 'create_farming_category',
                   'delete_farming_category', 'update_farming_category',
                   'create_farming_phenophase', 'update_farming_phenophase',
                   'delete_farming_phenophase', 'get_farming_phenophase_by_id',
                   'create_farming_product', 'update_farming_product',
                   'delete_farming_product', 'create_farming_source',
                   'update_farming_source', 'delete_farming_source',
                   'get_farming_source_by_key', 'create_farming_task',
                   'update_farming_task', 'delete_farming_task', 'verify_farming_task',
                   'get_farming_overdue_tasks'),
    'messages.py': ('count_unread_conversations', 'get_inbox', 'get_messages',
                    'get_unread_count', 'mark_all_messages_read', 'mark_messages_read',
                    'send_message'),
    'notifications.py': ('clear_read_notifications', 'clear_read_refs', 'create_notification',
                         'create_notification_for_all_students', 'get_notifications',
                         'get_read_refs', 'get_total_unread_count',
                         'get_unread_notification_count', 'mark_notifications_read',
                         'mark_ref_read', 'mark_refs_read'),
    'points.py': ('get_points', 'update_points'),
    # profile_sources 是取数窄接口（CAPABILITY = ''），本身不拥有能力域，
    # 由拼装方负责权限，因此单独登记。
    'profile_sources.py': ('get_profile_basic', 'get_profile_certificates',
                           'get_points_balance', 'get_recent_training_results',
                           'get_student_progress_for_profile'),
    'policies.py': ('create_policy', 'delete_policy', 'get_all_government_policies',
                    'get_government_overview', 'get_government_policies',
                    'get_policy_by_id', 'update_policy'),
    'procurements.py': ('create_procurement', 'delete_procurement', 'get_procurements',
                        'update_procurement'),
    'resources.py': ('CASE_REVIEW_TYPE', 'default_policy_summary', 'get_case_notes',
                     'get_case_review_stats', 'get_policy_notes', 'get_success_cases',
                     'normalize_policy_category', 'policy_sources_to_json',
                     # T15 运营后台新建案例时开审核记录
                     'create_case_review'),
    'reviews.py': ('approve_review', 'count_reviews_by_status', 'create_content_review',
                   'get_pending_reviews', 'get_review_by_content', 'get_reviews_by_status',
                   'reject_review', 'revoke_review', 'set_review_status'),
    'students.py': ('add_student', 'delete_student', 'get_linkable_student_accounts',
                    'get_student', 'get_students', 'set_student_account', 'update_student'),
    'teaching.py': ('TRAINING_DESCRIPTIONS', 'TRAINING_TITLE_FMTS',
                    'LIVE_ASSIGNMENT_DIRECTION', 'LIVE_ASSIGNMENT_TITLE_FMT',
                    'create_announcement', 'delete_announcement', 'get_announcements',
                    'get_all_trainings', 'get_analytics_data', 'get_dashboard_stats',
                    'get_live_trainings', 'get_or_create_live_assignment',
                    'get_or_create_training_assignment', 'get_roster_completion',
                    'get_trainings', 'grade_submission', 'save_live_training'),
    'users.py': ('change_password', 'count_super_admins', 'count_user_relations',
                 'delete_user_by_admin', 'get_admin_overview', 'get_all_users',
                 'get_user_by_id', 'get_user_by_username', 'register_user', 'set_user_status',
                 'update_user_by_admin', 'update_user_profile'),
    # T15 运营后台写侧。craft_steps / craft_purchase_items 没有显式主键，
    # 后台读取函数一律 SELECT rowid AS id，写侧按 rowid 定位单行。
    'crafts.py': ('get_craft_detail', 'get_crafts', 'get_craft_row',
                  'create_craft', 'update_craft', 'delete_craft',
                  'get_craft_steps', 'create_craft_step', 'update_craft_step',
                  'delete_craft_step', 'get_craft_purchase_categories',
                  'create_craft_purchase_category', 'update_craft_purchase_category',
                  'delete_craft_purchase_category', 'get_craft_purchase_items',
                  'create_craft_purchase_item', 'update_craft_purchase_item',
                  'delete_craft_purchase_item', 'get_craft_budget',
                  'set_craft_budget', 'delete_craft_budget',
                  'get_craft_videos', 'create_craft_video', 'update_craft_video',
                  'delete_craft_video'),
    'dialects.py': ('get_dialect_info', 'get_dialects', 'get_dialect_row',
                    'create_dialect', 'update_dialect', 'delete_dialect',
                    'get_dialect_phrases', 'create_dialect_phrase',
                    'update_dialect_phrase', 'delete_dialect_phrase',
                    'get_dialect_quick_questions', 'create_dialect_quick_question',
                    'update_dialect_quick_question', 'delete_dialect_quick_question'),
    'pest.py': ('get_pest_crop', 'get_pest_crop_ids', 'get_pest_crops',
                'get_pest_entries', 'get_pest_entry', 'get_pest_source_map',
                'get_pest_stats',
                # T14 运营后台写侧
                'REVIEW_STALE_DAYS', 'create_pest_entry', 'update_pest_entry',
                'delete_pest_entry', 'verify_pest_entry', 'get_overdue_pest_entries',
                'set_pest_image', 'delete_pest_image', 'create_pest_crop',
                'update_pest_crop', 'delete_pest_crop', 'create_pest_source',
                'update_pest_source', 'delete_pest_source'),
}

# 基础设施侧必须对外暴露的名字。
INFRA_SYMBOLS = {
    'db_init.py': ('init_db',),
    'db_connection.py': ('DB_DIR', 'DB_PATH', 'get_connection'),
    'db_credentials.py': ('hash_password', 'verify_password'),
}

def read_module(name):
    with io.open(os.path.join(REPO_ROOT, name), encoding='utf-8') as handle:
        return handle.read()


class IsolatedDatabaseTest(unittest.TestCase):
    """把探针脚本跑在一份临时库上，拿回它打印的 JSON。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix='t04_db_')
        self.addCleanup(self._tmp.cleanup)
        self.db_file = os.path.join(self._tmp.name, 'yuexiang.db')

    def probe(self, name):
        env = dict(os.environ)
        env['YUEXIANG_DB'] = self.db_file
        env['PYTHONIOENCODING'] = 'utf-8'
        env['PYTHONUTF8'] = '1'
        result = subprocess.run([sys.executable, PROBE, name],
                                cwd=REPO_ROOT, env=env, capture_output=True)
        self.assertEqual(
            result.returncode, 0,
            '探针 %s 失败：\n%s\n%s' % (name, result.stdout.decode('utf-8', 'replace'),
                                     result.stderr.decode('utf-8', 'replace')))
        return json.loads(result.stdout.decode('utf-8', 'replace'))


class ConnectionFactoryTest(IsolatedDatabaseTest):
    """数据层只有一个函数建立连接，且连接参数一个都不能少。"""

    def test_only_one_function_establishes_connections(self):
        # 只扫真实调用点：用 ast 找 Call 节点，注释与文档字符串里的同名字样不算。
        sites = []
        for name in DATA_LAYER_MODULES:
            for node in ast.walk(ast.parse(read_module(name))):
                if (isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Attribute)
                        and isinstance(node.func.value, ast.Name)
                        and node.func.value.id == 'sqlite3'
                        and node.func.attr == 'connect'):
                    sites.append('%s:%d' % (name, node.lineno))
        self.assertEqual(len(sites), 1, '数据层出现多个建连点：%s' % sites)
        self.assertTrue(sites[0].startswith('db_connection.py:'), sites)

    def test_connection_applies_required_pragmas(self):
        pragmas = self.probe('pragmas')
        self.assertEqual(pragmas['journal'], 'wal')
        self.assertEqual(pragmas['foreign_keys'], 1)
        self.assertEqual(pragmas['busy_timeout'], 8000)
        self.assertEqual(pragmas['row_factory'], 'Row')

    def test_connection_honours_the_yuexiang_db_override(self):
        self.assertEqual(self.probe('override_db'), True,
                         'YUEXIANG_DB 指定的库没有被创建')

    def test_db_path_stays_outside_the_module_directory(self):
        self.assertEqual(db_connection.DB_DIR,
                         os.path.join(repo_paths.REPO_ROOT, 'data'))
        self.assertEqual(db_connection.DB_PATH,
                         os.path.join(db_connection.DB_DIR, 'yuexiang.db'))


class SchemaDefinitionTest(IsolatedDatabaseTest):
    """建表语句集中在一处，init_db 建出全部表。"""

    def test_create_table_statements_live_in_one_module(self):
        # 只扫真实 SQL 文本：用 ast 找字符串字面量，注释里的字样不算。
        holders = []
        for name in DATA_LAYER_MODULES:
            for node in ast.walk(ast.parse(read_module(name))):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    if 'CREATE TABLE' in node.value:
                        holders.append(name)
                        break
        self.assertEqual(holders, ['db_schema.py'], '建表语句散落：%s' % holders)

    def test_init_db_creates_every_table(self):
        self.assertEqual(set(self.probe('tables')), EXPECTED_TABLES)

    def test_init_db_does_not_change_the_schema_on_rerun(self):
        before, after = self.probe('schema_stable')
        self.assertEqual(before, after)

    def test_legacy_demo_jobs_are_cleaned_on_existing_databases(self):
        """历史遗留的空 enterprise_id 预置岗位不再由启动路径清理（T10 删掉了那段种子逻辑）。"""
        self.assertEqual(self.probe('legacy_cleaned'), 1,
                         'init_db() 不应再删既有库里的任何 job_listings 行')


class SeedOrchestrationTest(IsolatedDatabaseTest):
    """首次建表并灌演示账号；重复执行幂等；不写任何内容行。"""

    def test_init_db_seeds_queryable_data(self):
        counts = self.probe('seed_counts')
        # 六个演示账号对应六种角色：超管 / 政府 / 企业 / 教师 / 运营（T13）/ 学员
        self.assertEqual(counts['users'], 6)
        self.assertEqual(counts['points'], 6)
        self.assertEqual(counts['students'], 2)
        self.assertEqual(counts['certificates'], 6)
        # 内容一律不播种（ADR 0002）：内容由基线库交付，启动路径只建表补列
        for table in ('policies', 'government_policies', 'carousels',
                      'system_announcements', 'discussions', 'farming_products',
                      'farming_tasks', 'pest_entries', 'recruitments',
                      'success_cases', 'crafts', 'dialects'):
            self.assertEqual(counts[table], 0,
                             'init_db() 往 %s 里写了行，启动路径不得写内容' % table)
        # job_listings 同属内容侧：演示岗位也由基线库交付，不再由种子逻辑灌
        self.assertEqual(counts['job_listings'], 0)

    def test_init_db_is_idempotent(self):
        first, second = self.probe('seed_idempotent')
        self.assertEqual(first, second)



class DomainSymbolSurfaceTest(unittest.TestCase):
    """每个数据层模块对外暴露的名字集合不变（T03 删掉 database.py 转发层后重写）。

    转发层活着的时候，这条断言数的是 database 这个聚合模块上的 163 个名字。
    删掉之后调用方改成按域 import，所以改成按模块数：名字少一个，就是某个域
    在删转发层时被顺手删掉或改名了。期望清单里的模块必须与 db_domains/ 的
    实际内容一一对应，新增模块要同步登记，否则下面的清单一致性用例会红。
    """

    def test_domain_modules_match_the_expected_list(self):
        expected = tuple(sorted(DOMAIN_SYMBOLS))
        self.assertEqual(DOMAIN_MODULES, expected,
                         'db_domains 的模块与 DOMAIN_SYMBOLS 的登记不一致：'
                         '多出 %s，缺少 %s'
                         % (set(DOMAIN_MODULES) - set(expected),
                            set(expected) - set(DOMAIN_MODULES)))

    def test_every_domain_module_exposes_its_symbols(self):
        for name, expected in sorted(DOMAIN_SYMBOLS.items()):
            module = importlib.import_module('db_domains.' + name[:-3])
            missing = [symbol for symbol in expected
                       if not hasattr(module, symbol)]
            self.assertEqual(missing, [],
                             '%s 少了这些对外名字：%s' % (name, missing))

    def test_infrastructure_modules_expose_their_symbols(self):
        for name, expected in sorted(INFRA_SYMBOLS.items()):
            module = importlib.import_module(name[:-3])
            missing = [symbol for symbol in expected
                       if not hasattr(module, symbol)]
            self.assertEqual(missing, [],
                             '%s 少了这些对外名字：%s' % (name, missing))

    def test_get_connection_is_not_redefined_in_db_init(self):
        """db_init 只是调用方，连接工厂仍只有 db_connection 一处实现。"""
        import db_init
        self.assertIs(db_init.get_connection, db_connection.get_connection)

    def test_hash_password_round_trip_still_works(self):
        from db_credentials import hash_password, verify_password
        stored = hash_password('secret')
        self.assertTrue(verify_password(stored, 'secret'))
        self.assertFalse(verify_password(stored, 'wrong'))

    def test_no_module_reintroduces_the_forwarder(self):
        """转发层不得复活：任何模块都不得再 import database。"""
        for name in INFRA_MODULES + tuple(
                'db_domains/' + m for m in DOMAIN_MODULES):
            source = read_module(name)
            self.assertNotIn('import database', source,
                             '%s 又 import 了已删除的 database' % name)

    def test_repo_never_imports_from_the_forwarder(self):
        pattern = re.compile(r'^\s*(?:from\s+database\s+import|import\s+database)\b', re.M)
        offenders = []
        for dirpath, dirnames, filenames in os.walk(REPO_ROOT):
            dirnames[:] = [d for d in dirnames
                           if d not in ('.venv', 'node_modules', '__pycache__',
                                    '.git', '.scratch')]
            for filename in filenames:
                if not filename.endswith('.py'):
                    continue
                path = os.path.join(dirpath, filename)
                if pattern.search(read_module(path)):
                    offenders.append(os.path.relpath(path, REPO_ROOT))
        self.assertEqual(offenders, [],
                         'database.py 已删除，不得再有人 import 它：%s' % offenders)


if __name__ == '__main__':
    unittest.main()
