# -*- coding: utf-8 -*-
"""哨兵：开发库里不该留着测试造出来的内容行。

为什么需要这条：测试跑在真实开发库上，个别用例只删了自己造的一半（另建的课程、
3D 模型、帖子、会话、审核记录都漏过），残留随每次跑测试长大。更糟的是
migrations/0001_content_to_db.py --make-baseline 会把当时的开发库原样复制成基线库，
于是垃圾被固化进新环境的起点（真发生过：基线库里躺着 126 门 T05 契约课程）。

判定只认测试惯用的命名标记（票据前缀 T + 两位数字、双下划线开头的标记），
不认识真实内容，所以不会因为运营真的写了什么而误报。
"""

import os
import re
import sqlite3
import sys
import unittest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(TESTS_DIR)
if os.path.join(REPO_ROOT, 'backend') not in sys.path:
    sys.path.insert(0, os.path.join(REPO_ROOT, 'backend'))

from db_connection import DB_PATH

# 表 -> 承载标题/名称的列
TEXT_COLUMNS = (
    ('courses', 'title'),
    ('job_listings', 'title'),
    ('models_3d', 'title'),
    ('discussions', 'title'),
    ('government_policies', 'title'),
    ('system_announcements', 'title'),
    ('farming_tasks', 'title'),
    ('pest_entries', 'disease'),
    ('crafts', 'name'),
    ('dialects', 'name'),
    ('recruitments', 'title'),
    ('success_cases', 'title'),
)

# 票据前缀形如 T16、T05。双下划线开头是测试惯用的隔离标记。
TICKET_PREFIX = re.compile(r'^T\d{2}')
UNDERSCORE_PREFIX = '__'


class NoTestResidueTest(unittest.TestCase):
    """库里有测试残留就红，并列出具体是哪张表、哪一行。"""

    def test_content_tables_hold_no_rows_created_by_tests(self):
        conn = sqlite3.connect(DB_PATH)
        offenders = []
        try:
            for table, column in TEXT_COLUMNS:
                try:
                    rows = conn.execute(
                        'SELECT "%s" FROM "%s"' % (column, table)).fetchall()
                except sqlite3.Error as exc:
                    self.fail('读取 %s.%s 失败：%s' % (table, column, exc))
                for (value,) in rows:
                    text = (value or '').strip()
                    if not text:
                        continue
                    if text.startswith(UNDERSCORE_PREFIX) or TICKET_PREFIX.match(text):
                        offenders.append('%s.%s = %r' % (table, column, text))
        finally:
            conn.close()

        self.assertEqual(
            offenders, [],
            '开发库 %s 里有测试残留，说明某个用例没有清干净自己造的数据：\n  %s\n'
            '清理后重跑。' % (DB_PATH, '\n  '.join(offenders[:40])))


if __name__ == '__main__':
    unittest.main()
