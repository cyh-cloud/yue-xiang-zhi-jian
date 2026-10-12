#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用户与认证域、学员与教学域的播种。

只负责「库里还没有演示账号时灌一份」。既有库缺哪个角色由 ensure_demo_accounts()
补齐，两者都幂等：重复执行不会造出第二个 admin_demo。
"""

import json

from db_credentials import hash_password

def seed_demo_accounts(cursor):
    """全新库：灌入演示账号、积分、证书与学员名册。

    五个演示账号对应五种角色（超管 / 政府 / 企业 / 教师 / 学员），
    口令散列走 db_credentials，与登录校验用的是同一份算法。
    """
    admin_pw = hash_password('admin123')
    gov_pw = hash_password('123456')
    enterprise_pw = hash_password('123456')
    teacher_pw = hash_password('123456')
    student_pw = hash_password('123456')
    cursor.execute("INSERT INTO users (username, password_hash, name, role) VALUES (?, ?, ?, ?)",
                   ('admin_demo', admin_pw, '系统管理员', 'super_admin'))
    cursor.execute("INSERT INTO users (username, password_hash, name, role, region) VALUES (?, ?, ?, ?, ?)",
                   ('gov_demo', gov_pw, '王主任', 'government', '广东省农业农村厅'))
    cursor.execute("INSERT INTO users (username, password_hash, name, role, company_name, region) VALUES (?, ?, ?, ?, ?, ?)",
                   ('enterprise_demo', enterprise_pw, '陈经理', 'enterprise', '广州鲜果汇电商有限公司', '广州'))
    cursor.execute("INSERT INTO users (username, password_hash, name, role) VALUES (?, ?, ?, ?)",
                   ('teacher_demo', teacher_pw, '张老师', 'teacher'))
    cursor.execute("INSERT INTO users (username, password_hash, name, role) VALUES (?, ?, ?, ?)",
                   ('student_demo', student_pw, '李同学', 'student'))

    # 积分
    cursor.execute("INSERT INTO points (user_id, balance, history) VALUES (?, ?, ?)",
                   ('student_demo', 1250, json.dumps([
                       {"action": "完成课程", "points": 50, "date": "2024-06-10"},
                       {"action": "通过考试", "points": 100, "date": "2024-06-08"}
                   ])))
    for uid in ('admin_demo', 'gov_demo', 'enterprise_demo', 'teacher_demo'):
        cursor.execute("INSERT INTO points (user_id, balance, history) VALUES (?, ?, ?)",
                       (uid, 0, '[]'))

    # 证书
    for uid in ('student_demo', 'teacher_demo'):
        cursor.execute("INSERT INTO certificates (user_id, name, status, progress, date) VALUES (?, ?, ?, ?, ?)",
                       (uid, '荔枝种植技术员', 'earned', 100, '2024-05-20'))
        cursor.execute("INSERT INTO certificates (user_id, name, status, progress) VALUES (?, ?, ?, ?)",
                       (uid, '电商运营师', 'in_progress', 75))
        cursor.execute("INSERT INTO certificates (user_id, name, status) VALUES (?, ?, ?)",
                       (uid, '广绣工艺师', 'locked'))

    # 学员
    cursor.execute("INSERT INTO students (id, user_id, name, class_name, direction, progress, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
                   ('STU001', 'student_demo', '张小明', '2024春季班', '荔枝种植', 85, 'active'))
    cursor.execute("INSERT INTO students (id, user_id, name, class_name, direction, progress, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
                   ('STU002', '', '李小红', '2024春季班', '电商运营', 62, 'active'))


def ensure_demo_accounts(cursor):
    """已有数据库时，补充缺少的新角色演示账户"""
    demo_accounts = [
        ('admin_demo', 'admin123', '系统管理员', 'super_admin', ''),
        ('gov_demo', '123456', '王主任', 'government', '广东省农业农村厅'),
        ('enterprise_demo', '123456', '陈经理', 'enterprise', '广州'),
    ]
    for username, password, name, role, region in demo_accounts:
        existing = cursor.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        if not existing:
            pw_hash = hash_password(password)
            cursor.execute(
                "INSERT INTO users (username, password_hash, name, role, region) VALUES (?, ?, ?, ?, ?)",
                (username, pw_hash, name, role, region))
            cursor.execute("INSERT INTO points (user_id, balance, history) VALUES (?, 0, '[]')", (username,))
