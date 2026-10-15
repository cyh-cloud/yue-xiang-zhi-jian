#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一次性内容迁移脚本的契约测试（T05 立，T10 改写）。

T05 时它锁住四件事：灌库结果与代码内容逐项相符、幂等、脏数据清理有日志、基线库
接口输出与现库一致。T10 把代码里的内容整体删掉之后，前两件事失去参照物（没有源头
可比），改写为现在的三件事：

1. **脏数据清理**：points 的 NULL 主键行与 messages 的孤儿收件人行被删，且清理动作
   写进迁移日志，不静默丢弃；
2. **幂等**：重复执行不改变任何一行，`--force` 重跑也不改内容（只允许迁移记录表变）；
3. **基线库**：从基线库启动的实例接口输出与现库一致，且它是「可再次迁移」的形状。

⚠️ 为什么碰库的用例一律跑子进程：DB_PATH 在 import db_connection 时就定下来了
（既有行为，部署入口也依赖「导入即定位」）。同进程里改 os.environ 不会改变它，
只会让用例悄悄打到 data/yuexiang.db 上，把真实数据写脏。所以碰库的用例都调到
migration_probe.py 那个子进程里，用环境变量 YUEXIANG_DB 把库指到临时目录。
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

# 被测的迁移脚本在仓库根 migrations/ 下，db_schema 在 backend/ 下。
REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.join(REPO_ROOT, 'backend')
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

MIGRATION = os.path.join(REPO_ROOT, 'migrations', '0001_content_to_db.py')
PROBE = os.path.join(REPO_ROOT, 'migrations', 'migration_probe.py')


def read_file(path):
    with io.open(path, encoding='utf-8') as handle:
        return handle.read()


def load_migration():
    """按文件路径加载迁移脚本，模块名固定，避免与包路径冲突。"""
    import importlib.util
    spec = importlib.util.spec_from_file_location('_content_migration', MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class IsolatedMigrationTest(unittest.TestCase):
    """在一份自建的脏库副本上跑迁移，断言清理结果。父进程不碰库。

    为什么不复制现库：现库可能已经被迁移过（`--make-baseline` 的默认目标就是它），
    那时脏数据已清、迁移记录已写，用例的「第一次执行」就永远不成立。所以用例自己
    造一份**确定脏**的库：现库的副本 + 手工插回两处脏数据 + 删掉迁移记录。这样无论
    现库处于什么状态，断言的前置条件都一致。
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix='t05_mig_')
        self.addCleanup(self._tmp.cleanup)
        self.db_file = os.path.join(self._tmp.name, 'yuexiang.db')
        self.live_db = os.path.join(REPO_ROOT, 'data', 'yuexiang.db')
        if not os.path.isfile(self.live_db):
            self.skipTest('现库 data/yuexiang.db 不存在，跳过副本用例')
        self.make_dirty_copy()

    def make_dirty_copy(self):
        """复制现库，并保证它处于「迁移前」的状态。"""
        import shutil
        import sqlite3

        shutil.copyfile(self.live_db, self.db_file)
        conn = sqlite3.connect(self.db_file)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # 1. 建表：副本可能还没有 T04 的新表与迁移记录表
        import db_schema
        db_schema.apply_schema(cur)
        # 2. 清掉迁移记录：否则第二次执行会被判定为「已执行」而跳过
        cur.execute('DELETE FROM schema_migrations')
        # 3. 插回两处脏数据：现库可能已经清过，用例要自己保证它们是脏的
        cur.execute("DELETE FROM points WHERE user_id IS NULL")
        cur.execute("INSERT INTO points (user_id, balance, history) VALUES (NULL, 0, ?)",
                    (json.dumps([{'action': '兑换化肥优惠券', 'points': -200,
                                  'date': '2026-06-21'}], ensure_ascii=False),))
        cur.execute("INSERT INTO points (user_id, balance, history) VALUES (NULL, 0, ?)",
                    (json.dumps([{'action': '兑换化肥优惠券', 'points': -200,
                                  'date': '2026-06-21'}], ensure_ascii=False),))
        cur.execute(
            "DELETE FROM messages WHERE receiver_id NOT IN (SELECT username FROM users)")
        cur.execute(
            """INSERT INTO messages (sender_id, receiver_id, content, is_read, created_at)
               VALUES (?, ?, '', 0, '2026-06-21 21:39:41')""",
            ('3474f639-4b1f-4b05-96d9-3a829a9cfbfc', 'STU001'))
        cur.execute(
            """INSERT INTO messages (sender_id, receiver_id, content, is_read, created_at)
               VALUES (?, ?, '', 0, '2026-06-21 23:50:41')""",
            ('f607f79f-3949-4330-8e9e-2e7e8ff1cf65', 'STU001'))
        conn.commit()
        conn.close()

    def run_migration(self, *args):
        env = dict(os.environ)
        env['YUEXIANG_DB'] = self.db_file
        env['PYTHONIOENCODING'] = 'utf-8'
        env['PYTHONUTF8'] = '1'
        return subprocess.run(
            [sys.executable, MIGRATION] + list(args),
            cwd=REPO_ROOT, env=env, capture_output=True)

    def probe(self, name):
        """先跑一遍迁移，再取探针结果。"""
        result = self.run_migration()
        self.assertEqual(result.returncode, 0,
                         '迁移脚本失败：\n%s\n%s' % (
                             result.stdout.decode('utf-8', 'replace'),
                             result.stderr.decode('utf-8', 'replace')))
        return self.probe_only(name)

    def probe_only(self, name):
        """只取探针结果，不先跑迁移（供断言「重复执行」的用例自己控制执行次数）。"""
        env = dict(os.environ)
        env['YUEXIANG_DB'] = self.db_file
        env['PYTHONIOENCODING'] = 'utf-8'
        env['PYTHONUTF8'] = '1'
        result = subprocess.run(
            [sys.executable, PROBE, name], cwd=REPO_ROOT, env=env, capture_output=True)
        self.assertEqual(
            result.returncode, 0,
            '探针 %s 失败：\n%s\n%s' % (name, result.stdout.decode('utf-8', 'replace'),
                                     result.stderr.decode('utf-8', 'replace')))
        return json.loads(result.stdout.decode('utf-8', 'replace'))


class MigrationLogTest(unittest.TestCase):
    """不碰库的静态检查：脚本结构与日志字段。"""

    def test_script_is_kept_in_the_repo_and_marked_executed(self):
        """脚本进版本库但标注「已执行」，靠迁移记录表防重入，不删。"""
        source = read_file(MIGRATION)
        self.assertIn('schema_migrations', source)
        self.assertIn('already', source)

    def test_migration_record_table_is_created_by_the_schema(self):
        """迁移记录表的 DDL 与建表同住，脚本不另建表（单一真相源）。"""
        schema = read_file(os.path.join(BACKEND, 'db_schema.py'))
        self.assertIn('CREATE TABLE IF NOT EXISTS schema_migrations', schema)
        self.assertNotIn('CREATE TABLE', read_file(MIGRATION),
                         '迁移脚本里不得另建表，表定义只在 db_schema.py')

    def test_dirty_cleanup_is_logged_not_silent(self):
        source = read_file(MIGRATION)
        for marker in ('cleaned_points', 'cleaned_messages', 'user_id IS NULL'):
            self.assertIn(marker, source)

    def test_script_no_longer_loads_the_deleted_content_modules(self):
        """T10 之后脚本不得 import 任何已删除的内容模块：没有源头可灌。"""
        import ast
        tree = ast.parse(read_file(MIGRATION))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                imported.add(node.module or '')
                imported.update(a.name for a in node.names)
            elif isinstance(node, ast.Import):
                imported.update(a.name for a in node.names)
        for name in ('domain_data', 'farming_data', 'jobs_data', 'pest_data',
                     'cases_data', 'policies_data', 'PEST_IMAGES',
                     'CRAFTS_KNOWLEDGE', 'DIALECTS_DATA',
                     '_DEFAULT_AGRICULTURE_PRODUCTS', '_STATIC_AGRI_SUGGESTIONS',
                     '_AGRI_PRODUCT_NAME_FALLBACK', 'AGRICULTURE_KNOWLEDGE'):
            self.assertNotIn(name, imported,
                             '脚本仍 import %s，它已随 T10 删除' % name)


class IdempotenceTest(IsolatedMigrationTest):
    """重复执行不改变任何一行。"""

    def test_second_run_is_a_no_op(self):
        # 用 probe_only：探针自己控制执行次数，父进程先跑会抵消「第一次」
        report = self.probe_only('idempotent')
        self.assertTrue(report['first_ran'])
        self.assertTrue(report['second_skipped'], '第二次执行没有跳过')
        self.assertEqual(report['second_changes'], [],
                         '第二次执行改变了这些表：%s' % report['second_changes'])

    def test_forced_rerun_keeps_every_content_row(self):
        """--force 是补漏字段用的，重跑后内容必须逐字节相同。"""
        report = self.probe_only('idempotent')
        allowed = ['schema_migrations']     # 迁移记录本身会更新，内容表一行不动
        self.assertEqual([t for t in report['force_changes'] if t not in allowed], [],
                         '--force 重跑改变了内容表：%s' % report['force_changes'])
        self.assertEqual(report['forced_cleaned'], [0, 0],
                         '重跑时不应再报脏数据（已清过）')


class BaselineLibraryTest(IsolatedMigrationTest):
    """基线库：从灌过库的实例起的接口输出与现库一致。"""

    def test_api_output_matches_the_live_database(self):
        """跑过迁移的库与基线库，同一批接口的输出逐字节一致。"""
        result = self.run_migration()
        self.assertEqual(result.returncode, 0, result.stderr.decode('utf-8', 'replace'))
        baseline = self.make_baseline_library()

        env = dict(os.environ)
        env['YUEXIANG_DB'] = baseline
        env['PYTHONIOENCODING'] = 'utf-8'
        env['PYTHONUTF8'] = '1'
        probe = subprocess.run([sys.executable, PROBE, 'api_parity'],
                               cwd=REPO_ROOT, env=env, capture_output=True)
        self.assertEqual(probe.returncode, 0,
                         '基线库探针失败：\n%s\n%s' % (
                             probe.stdout.decode('utf-8', 'replace'),
                             probe.stderr.decode('utf-8', 'replace')))

        from_baseline = json.loads(probe.stdout.decode('utf-8'))
        from_migrated = self.probe_only('api_parity')
        self.assertEqual(from_baseline, from_migrated,
                         '从基线库启动的实例接口输出与迁移后的库不一致')

    def make_baseline_library(self):
        """调脚本的 --make-baseline 生成一份基线库，返回它的路径。"""
        target = os.path.join(self._tmp.name, 'baseline.db')
        result = self.run_migration('--make-baseline', '--baseline-path', target)
        self.assertEqual(result.returncode, 0,
                         '生成基线库失败：\n%s\n%s' % (
                             result.stdout.decode('utf-8', 'replace'),
                             result.stderr.decode('utf-8', 'replace')))
        self.assertTrue(os.path.isfile(target), '基线库没有生成')
        return target

    def test_baseline_library_is_the_pre_migration_shape(self):
        """基线库可以再次被迁移：它不保留迁移记录，且 journal_mode 不是 WAL。"""
        import sqlite3
        baseline = self.make_baseline_library()
        conn = sqlite3.connect(baseline)
        recorded = conn.execute('SELECT COUNT(*) FROM schema_migrations').fetchone()[0]
        journal = conn.execute('PRAGMA journal_mode').fetchone()[0]
        counts = {t: conn.execute('SELECT COUNT(*) FROM %s' % t).fetchone()[0]
                  for t in ('farming_tasks', 'pest_entries', 'recruitments',
                            'success_cases', 'dialects', 'crafts')}
        conn.close()
        self.assertEqual(recorded, 0, '基线库不该带迁移记录，否则后续迁移会被跳过')
        self.assertEqual(journal.lower(), 'delete',
                         '基线库应切回 DELETE，别带着 WAL 附属文件被复制')
        self.assertEqual(counts, {'farming_tasks': 123, 'pest_entries': 45,
                                  'recruitments': 14, 'success_cases': 5,
                                  'dialects': 3, 'crafts': 4})

    def test_baseline_library_is_not_tracked_by_git(self):
        """.gitignore 覆盖 data/*.db，基线库不入版本库。"""
        ignored = subprocess.run(['git', 'check-ignore', 'data/baseline.db'],
                                 cwd=REPO_ROOT, capture_output=True)
        self.assertEqual(ignored.returncode, 0,
                         'data/baseline.db 没有被 .gitignore 忽略')


class DirtyDataCleanupTest(IsolatedMigrationTest):
    """两处现库脏数据被清掉，且清理动作写进迁移日志。"""

    def test_dirty_rows_are_gone_and_logged(self):
        # probe_only：探针自己以 --force 跑一次，父进程先跑会把脏数据清掉，
        # 探针就记不到「清理了 2 行」
        report = self.probe_only('cleanup')
        self.assertEqual(report['points_null_left'], 0, 'points 的 NULL 主键行没清掉')
        self.assertEqual(report['orphan_messages_left'], 0, 'messages 的孤儿收件人行没清掉')
        self.assertEqual(report['log_points'], 2, '迁移日志没记下 2 行 points 脏数据')
        self.assertEqual(report['log_messages'], 2, '迁移日志没记下 2 行 messages 脏数据')
        self.assertEqual(report['stored_points'], 2, '落库的迁移日志缺 points 清理记录')
        self.assertEqual(report['stored_messages'], 2, '落库的迁移日志缺 messages 清理记录')
        self.assertIn('STU001', report['stored_receivers'],
                      '清理记录里看不到被删的收件人，等于静默丢弃')


if __name__ == '__main__':
    unittest.main()
