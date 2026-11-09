#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一键填充演示账号（供演示前快速恢复）。

直接复用 db_init.init_db()：建表 + 补列 + 灌演示账号，全部幂等，可重复运行。
  - 空库：seed_demo_accounts 灌全部 6 个角色账号 + 积分/证书/学员名册
  - 非空库：ensure_demo_accounts 补齐缺失的 4 个核心角色
            (admin_demo / gov_demo / enterprise_demo / operator_demo)

如需把演示账号整体重建（含 teacher_demo / student_demo），先删除 data/yuexiang.db
再运行本脚本即可（会重新建表并全量灌入）。

运行：python backend/seed_demo.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db_init import init_db
from db_domains import users


def main():
    init_db()
    demo = ('admin_demo', 'gov_demo', 'enterprise_demo',
            'teacher_demo', 'operator_demo', 'student_demo')
    print("演示账号状态：")
    for u in demo:
        row = users.get_user_by_id(u)
        if row:
            print("  [ok]   %-16s %-12s %s" % (u, row.get('role'), row.get('name')))
        else:
            print("  [缺失] %s" % u)
    print("完成。")


if __name__ == '__main__':
    main()
