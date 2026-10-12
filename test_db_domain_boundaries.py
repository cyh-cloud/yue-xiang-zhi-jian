#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""数据层领域边界测试（T05）。

把 spec 里「每个领域模块只读写自己领域的表」从一句口头承诺变成可机械检查的事实：
扫每个领域模块里的 SQL 语句，抽出涉及的表名，与该领域登记在册的表集合比对。

白名单机制：确实需要跨域读写的少数地方，必须在 OWNED_TABLES 里显式登记并写明理由，
新增一条未登记的跨域访问就让测试红。这样边界是「显式清单」而不是「靠自觉」。
"""

import ast
import io
import os
import re
import sys
import unittest

# 后端代码整体迁入 backend/ 后，被测的 database / db_domains / domain_data
# 都在 backend/ 下，因此路径基准指向 backend/ 而不是仓库根。
REPO_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend')
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

DOMAINS_DIR = os.path.join(REPO_ROOT, 'db_domains')

# 领域 -> 该领域拥有的表
OWNED_TABLES = {
    'auth': {'user_sessions', 'users'},
    'users': {'users'},
    'auth': {'user_sessions', 'users'},
    'points': {'points'},
    'points': {'points'},
    'certificates': {'certificates'},
    'farming': {
        'farming_products', 'farming_phenophases', 'farming_tasks',
        'farming_subscriptions', 'farming_reminder_log', 'farming_sources',
    },
    'students': {'students'},
    'teaching': {'announcements', 'assignments', 'assignment_submissions'},
    'messages': {'messages'},
    'notifications': {'notifications', 'notification_reads'},
    'employment': {
        'job_listings', 'job_applications', 'saved_jobs', 'resumes', 'job_intents',
    },
    'resources': {'content_reviews'},
    'courses': {'courses', 'course_materials', 'models_3d', 'content_reviews'},
    'community': {'comments', 'discussions'},
    'procurements': {'procurements', 'content_reviews'},
    'policies': {'government_policies', 'content_reviews'},
    'announcements': {'system_announcements'},
    'reviews': {'content_reviews'},
}

# profile_sources 不拥有任何表：它是「能力档案的取数窄接口」模块，只跨域取数
# 交给就业域拼装，因此不出现在 OWNED_TABLES 里（否则每张表都会有第二个属主）。
# 它的跨域读取在 ALLOWED_FOREIGN_TABLES 里逐条登记并写明理由。
NO_OWNED_TABLES = ('profile_sources',)

# 显式登记的跨域读写例外。每条都必须写理由；空字典意味着「没有任何例外」。
#
# profile_sources 是「能力档案的取数窄接口」模块，它的职责就是跨域取数后交给
# 就业域拼装，因此它读 users / points / students / certificates /
# assignment_submissions / assignments 六张表是设计使然，不是遗漏。
# 真正的约束是：除它之外，任何领域都不得直读别人的表。
ALLOWED_FOREIGN_TABLES = {
    # 删用户时必须连带清掉它的会话与积分行，否则留下永远登录不上去的僵尸会话
    # 和无人认领的积分。属主虽是 auth / points 域，这个清理动作归 users 域。
    'users': {
        'user_sessions': '删用户时连带清理会话',
        'points': '删用户时连带清理积分',
    },
    'profile_sources': {
        'users': '能力档案的基础资料段',
        'points': '能力档案的积分段',
        'students': '能力档案的学习进度段',
        'certificates': '能力档案的证书段',
        'assignment_submissions': '能力档案的实训成绩段',
        'assignments': '能力档案的实训成绩段（取作业标题）',
    },
}

# SQL 里出现的表名抽取：INSERT INTO x / UPDATE x / DELETE FROM x / FROM x [ JOIN ] / JOIN x
_TABLE_RE = re.compile(
    r'\b(?:INSERT\s+INTO|UPDATE|DELETE\s+FROM|FROM|JOIN)\s+([a-zA-Z_][a-zA-Z0-9_]*)',
    re.IGNORECASE,
)

# 已知的本仓库全部表名（用于把「抽到的名字」过滤成真表名）
ALL_TABLES = set()
for _tables in OWNED_TABLES.values():
    ALL_TABLES |= _tables
ALL_TABLES |= {'policies', 'seed_meta', 'carousels', 'farming_seed_meta', 'users'}


def tables_in_sql(sql):
    found = set()
    for match in _TABLE_RE.finditer(sql):
        name = match.group(1).lower()
        if name in ALL_TABLES:
            found.add(name)
    return found


def sql_strings_in(path):
    """只收**会送进 SQL 执行的字符串**，不收 docstring 与普通注释。

    判据是「作为 conn.execute(...) / cursor.execute(...) 的首个实参出现」，
    这样文档里提到表名不会被误判成跨域访问。
    """
    with io.open(path, encoding='utf-8') as handle:
        tree = ast.parse(handle.read())
    return _collect_sql(tree)


def _collect_sql(tree):
    """从已解析的 AST 里收集 execute(...) 的首个字符串实参。"""
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else (
            func.id if isinstance(func, ast.Name) else '')
        if name != 'execute':
            continue
        if not node.args:
            continue
        first = node.args[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            out.append((first.lineno, first.value))
        elif isinstance(first, ast.JoinedStr):
            # f-string：只取其中的字面量片段
            parts = [v.value for v in first.values
                     if isinstance(v, ast.Constant) and isinstance(v.value, str)]
            out.append((first.lineno, ' '.join(parts)))
    return out


def domain_of_table(table):
    owners = [d for d, tables in OWNED_TABLES.items() if table in tables]
    return owners


class DomainBoundaryTest(unittest.TestCase):
    """扫每个领域模块的 SQL，检查它只碰自己的表。"""

    def _modules(self):
        for name in sorted(os.listdir(DOMAINS_DIR)):
            if name.endswith('.py') and name != '__init__.py':
                yield name[:-3], os.path.join(DOMAINS_DIR, name)

    def test_every_domain_module_is_registered(self):
        """新加的领域模块必须登记在 OWNED_TABLES 里，否则它的边界无人检查。"""
        for domain, _path in self._modules():
            if domain in NO_OWNED_TABLES:
                continue
            self.assertIn(domain, OWNED_TABLES,
                          '%s 没有登记自己拥有的表，边界检查形同虚设' % domain)

    def test_no_unregistered_foreign_table_access(self):
        offenders = []
        for domain, path in self._modules():
            owned = OWNED_TABLES.get(domain, set())
            allowed = ALLOWED_FOREIGN_TABLES.get(domain, set())
            for lineno, sql in sql_strings_in(path):
                for table in tables_in_sql(sql):
                    if table in owned or table in allowed:
                        continue
                    offenders.append('%s:%d 访问了非本域表 %s' % (domain, lineno, table))
        self.assertEqual(offenders, [], '存在未登记的跨域表访问：\n' + '\n'.join(offenders))

    def test_each_table_has_exactly_one_owner(self):
        """除显式共享表外，一张表只能有一个属主，否则「改我这张表」没有唯一接口。"""
        shared = {'content_reviews', 'notification_reads', 'users'}
        for table in sorted(ALL_TABLES):
            if table in shared:
                continue
            owners = domain_of_table(table)
            self.assertLessEqual(len(owners), 1,
                                 '表 %s 被多个领域同时拥有：%s' % (table, owners))


class SharedDbHygieneTest(unittest.TestCase):
    """共享种子库的卫生检查。

    T05 与 T17 都踩过同一个坑：测试对 content_reviews 里已过审的案例反复 approve，
    每次 create_content_review 都新增一行，于是同一个 (content_type, content_id,
    status) 出现多条记录，把 get_case_review_stats 的 approved 计数撑爆，
    进而污染其它测试文件里的案例可见性断言。症状是「单独跑全绿、合到一起就红」。

    这条检查把那个状态变成可见的失败，而不是留给下一个跑测试的人猜。
    """

    def test_no_duplicate_review_rows_per_content_and_status(self):
        import database
        conn = database.get_connection()
        try:
            dupes = conn.execute(
                'SELECT content_type, content_id, status, COUNT(*) AS n '
                'FROM content_reviews '
                'GROUP BY content_type, content_id, status '
                'HAVING n > 1').fetchall()
        finally:
            conn.close()
        self.assertEqual(
            [(d['content_type'], d['content_id'], d['status'], d['n'])
             for d in dupes], [],
            '同一内容的同一审核状态出现了多条记录，通常是测试 cleanup 不完整'
            '（无条件把全部记录置 approved 会留下多余行）。')

    def test_approved_case_count_matches_the_content_source(self):
        """approved 计数必须等于内容源里的案例数，多出来就是被测试撑爆的。"""
        import database
        from domain_data.resources import cases_data
        stats = database.get_case_review_stats()['case_review']
        total_cases = len(cases_data.get_cases())
        self.assertEqual(stats['total'], total_cases,
                         '审核记录覆盖的内容数与内容源不一致')
        self.assertLessEqual(stats['approved'], total_cases,
                             'approved 超过了内容源条数，说明有重复的过审记录')


if __name__ == '__main__':
    unittest.main()
