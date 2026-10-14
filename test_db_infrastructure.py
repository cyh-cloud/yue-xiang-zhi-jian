#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""数据层基础设施的契约测试（后端按领域拆分 T04）。

锁住四件事，改动数据结构前先跑它：

1. 连接工厂：数据层只有一个函数建立连接，且 WAL / foreign_keys / busy_timeout 不丢；
2. 建表定义：建表语句只出现在一处，init_db 建出全部表且重复执行不改变结构；
3. 初始化入口：`database.init_db()` 首次建表并播种、重复执行幂等（种子不翻倍、
   审核结论不被覆盖、真实企业数据不被清）；
4. 对外契约：`import database` + `database.xxx()` 的符号面在拆分后不变，
   且基础设施模块不反向 import database（否则成环）。

⚠️ 为什么碰库的用例一律跑子进程：DB_PATH 在 import db_connection 时就定下来了
（既有行为，部署入口也依赖「导入即定位」）。同进程里改 os.environ 不会改变它，
只会让用例悄悄打到 data/yuexiang.db 上，把真实数据写脏。所以碰库的用例都调到
db_infrastructure_probe.py 那个子进程里，用环境变量 YUEXIANG_DB 把库指到临时目录。
父进程只做不碰库的静态检查。
"""

import ast
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

# 后端代码整体迁入 backend/ 后，被测的 database / db_domains / domain_data
# 都在 backend/ 下，因此路径基准指向 backend/ 而不是仓库根。
REPO_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend')
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import db_connection  # noqa: E402
import repo_paths  # noqa: E402

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
                 'db_schema_probe.py') + SEED_MODULES
DATA_LAYER_MODULES = ('database.py',) + INFRA_MODULES

# init_db() 建出的全部表。新增表时同步更新这里，让「漏建表」在单测里就炸。
# 内容落库（T04）后多出 21 张：farming_categories、pest_* 六张、recruitments 与
# recruitment_sources、success_cases 与 case_* 四张、dialect* 三张、craft* 五张。
# 完整清单与「为什么 pest_entries 是新建而非补列」见 test_db_schema.py。
EXPECTED_TABLES = {
    'announcements', 'assignment_submissions', 'assignments', 'carousels',
    'case_lessons', 'case_milestones', 'case_sources', 'case_stats',
    'certificates', 'comments', 'content_reviews', 'course_materials', 'courses',
    'craft_budgets', 'craft_purchase_categories', 'craft_purchase_items',
    'craft_steps', 'crafts', 'dialect_phrases', 'dialect_quick_questions',
    'dialects', 'discussions', 'farming_categories', 'farming_phenophases',
    'farming_products', 'farming_reminder_log', 'farming_seed_meta',
    'farming_sources', 'farming_subscriptions', 'farming_tasks',
    'government_policies', 'job_applications', 'job_intents', 'job_listings',
    'messages', 'models_3d', 'news_articles', 'notification_reads',
    'notifications', 'pest_crops', 'pest_entries', 'pest_entry_sources',
    'pest_images', 'pest_sources', 'points', 'policies', 'procurements',
    'recruitment_sources', 'recruitments', 'resumes', 'saved_jobs', 'seed_meta',
    'students', 'success_cases', 'system_announcements', 'user_sessions', 'users',
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
        self.assertEqual(self.probe('legacy_cleaned'), 0,
                         '既有库里的历史预置岗位没有被清掉')


class SeedOrchestrationTest(IsolatedDatabaseTest):
    """首次建表并播种；重复执行幂等；既有结论不被种子逻辑覆盖。"""

    def test_init_db_seeds_queryable_data(self):
        counts = self.probe('seed_counts')
        self.assertEqual(counts['users'], 5)
        self.assertEqual(counts['points'], 5)
        self.assertEqual(counts['students'], 2)
        self.assertEqual(counts['certificates'], 6)
        self.assertEqual(counts['policies'], counts['policies_total'])
        self.assertEqual(counts['government_policies'], counts['policies_total'])
        self.assertEqual(counts['carousels'], 3)
        self.assertEqual(counts['system_announcements'], 1)
        self.assertEqual(counts['discussions'], 2)
        self.assertGreater(counts['farming_products'], 0)
        self.assertGreater(counts['farming_tasks'], 0)
        self.assertEqual(counts['job_listings'], counts['demo_jobs'])

    def test_demo_jobs_carry_review_records(self):
        self.assertEqual(self.probe('job_reviews'), 2)

    def test_init_db_is_idempotent(self):
        first, second = self.probe('seed_idempotent')
        self.assertEqual(first, second)

    def test_second_init_keeps_review_conclusions_and_real_enterprise_jobs(self):
        result = self.probe('review_survives')
        self.assertEqual(result['demo_status'], 'rejected',
                         '种子重灌把管理员的审核结论覆盖掉了')
        self.assertEqual(result['real_status'], 'approved',
                         '真实企业岗位的审核结论不得被改写')
        self.assertEqual(sorted(result['demo_ids']), [1, 2],
                         '演示岗位必须按标题就地更新（id 不变），不得删后重建')


class ExternalContractTest(unittest.TestCase):
    """`import database` + `database.xxx()` 的符号面不变。"""

    APP_SYMBOLS = (
        'init_db', 'get_connection', 'DB_DIR', 'DB_PATH',
        'TRAINING_TITLE_FMTS', 'ENTERPRISE_JOB_CATEGORIES',
        'hash_password', 'verify_password',
        'POLICIES_DATA', 'POLICY_SOURCES', 'POLICIES_SEED_VERSION',
        'DEMO_JOBS', 'DEMO_JOB_ENTERPRISE_ID', 'DEMO_JOBS_SEED_KEY',
        'CASE_REVIEW_TYPE', 'LIVE_ASSIGNMENT_DIRECTION',
        'LIVE_ASSIGNMENT_TITLE_FMT', 'TRAINING_DESCRIPTIONS', 'RESUME_FIELDS',
    )

    def setUp(self):
        # database 在 import 时定下 DB_PATH；指到临时文件，父进程不写真实库。
        self._tmp = tempfile.TemporaryDirectory(prefix='t04_contract_')
        self.addCleanup(self._tmp.cleanup)
        self._original = os.environ.get('YUEXIANG_DB')
        os.environ['YUEXIANG_DB'] = os.path.join(self._tmp.name, 'contract.db')
        self.addCleanup(self._restore)

    def _restore(self):
        sys.modules.pop('database', None)
        if self._original is None:
            os.environ.pop('YUEXIANG_DB', None)
        else:
            os.environ['YUEXIANG_DB'] = self._original

    def database(self):
        import database
        return database

    def test_database_still_exposes_every_symbol_app_relies_on(self):
        database = self.database()
        for name in self.APP_SYMBOLS:
            self.assertTrue(hasattr(database, name),
                            'database.%s 在拆分后消失了' % name)

    def test_get_connection_is_reexported_not_redefined(self):
        import database
        self.assertIs(database.get_connection, db_connection.get_connection)

    def test_hash_password_round_trip_still_works(self):
        database = self.database()
        stored = database.hash_password('secret')
        self.assertTrue(database.verify_password(stored, 'secret'))
        self.assertFalse(database.verify_password(stored, 'wrong'))

    def test_infrastructure_modules_do_not_import_database(self):
        for name in INFRA_MODULES:
            source = read_module(name)
            self.assertNotIn('import database', source,
                             '%s 反向 import database 会形成环' % name)

    def test_repo_never_imports_names_from_database(self):
        pattern = re.compile(r'^\s*from\s+database\s+import\b', re.M)
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
                         '外部只应 import database + database.xxx()：%s' % offenders)


if __name__ == '__main__':
    unittest.main()