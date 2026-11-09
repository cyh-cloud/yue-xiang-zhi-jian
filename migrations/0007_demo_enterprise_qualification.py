# -*- coding: utf-8 -*-
"""0007：给演示企业预置一条「已认证」资质，让答辩时能看到通过态。

为什么需要：资质认证上线后，新注册企业一律从「未认证」开始，要通过人工审核才有
「已认证」的样子。演示账号如果也是未认证，现场演示只能看到灰色状态，看不到认证标识
与解除发布上限的效果。

三条口径：

1. **只给 enterprise_demo 预置，不碰其他账号**。其他企业保持真实流程。
2. **不伪造证件照**。approved 但没有 license_file：营业执照是法律文件，不能拿
   示意图或占位图冒充。界面对这种情况显示「演示数据，未上传证件照」。
3. **信用代码是演示值**，extra 里明确标注 non-real，避免被人当成真实企业代码引用。
   （校验位是真的，能通过 shared.credit_code 的算法，但不对应任何真实企业。）

幂等：该账号已有 approved 记录时直接跳过，不重复插入。

用法：
    python migrations/0007_demo_enterprise_qualification.py [--db 路径] [--dry-run]
"""

import argparse
import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(REPO_ROOT, 'backend')
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

VERSION = '0007'
NAME = 'demo_enterprise_qualification'

DEMO_USER = 'enterprise_demo'
DEMO_FIELDS = {
    'company_name': '粤乡优品农业发展有限公司（演示）',
    # 校验位按 GB 32100-2015 算过，但不对应任何真实企业。
    'credit_code': '91440101MA5D8K7X29',
    'legal_person': '陈经理',
    'contact_phone': '13800000000',
    'address': '广东省广州市',
    'industry': '农业',
    'company_size': '50-100人',
    'license_file': '',
    'license_name': '',
}
DEMO_EXTRA = {
    'demo': True,
    'note': '演示数据：用于展示已认证状态，不对应真实企业，也没有营业执照照片',
}


def migrate(db_path, dry_run=False, force=False):
    import sqlite3

    if not os.path.isfile(db_path):
        raise SystemExit('目标库不存在：%s' % db_path)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    import db_schema
    db_schema.apply_schema(cur)
    conn.commit()

    already = cur.execute(
        "SELECT version FROM schema_migrations WHERE version = ?", (VERSION,)).fetchone()
    if already and not force:
        conn.close()
        return None

    if dry_run:
        conn.close()
        return {'dry_run': True}

    has_approved = cur.execute(
        "SELECT id FROM enterprise_qualifications WHERE user_id = ? "
        "AND status = 'approved' LIMIT 1", (DEMO_USER,)).fetchone()

    # 账号的公司名是空的，会让审核侧的「名称是否一致」检查恒为不一致。
    # 只在该字段为空时补一次，运营之后改过就不动。
    cur.execute(
        "UPDATE users SET company_name = ? WHERE username = ? "
        "AND COALESCE(company_name, '') = ''",
        (DEMO_FIELDS['company_name'], DEMO_USER))

    if has_approved:
        log = {'version': VERSION, 'name': NAME, 'inserted': False,
               'reason': 'already-approved'}
    else:
        columns = ['user_id', 'status', 'reviewed_by', 'reviewed_at', 'expires_at',
                   'extra'] + list(DEMO_FIELDS)
        values = [DEMO_USER, 'approved', 'admin_demo',
                  None, None,
                  json.dumps(DEMO_EXTRA, ensure_ascii=False)] + \
                 [DEMO_FIELDS[key] for key in DEMO_FIELDS]
        cur.execute(
            "INSERT INTO enterprise_qualifications (%s) VALUES (%s)"
            % (', '.join(columns), ', '.join('?' * len(columns))), values)
        # reviewed_at / expires_at 用 SQLite 的日期函数算，避免把「今天」写死在脚本里。
        cur.execute(
            "UPDATE enterprise_qualifications SET "
            "reviewed_at = datetime('now','localtime'), "
            "expires_at = date('now','localtime','+1 year') "
            "WHERE user_id = ? AND status = 'approved' "
            "AND reviewed_at IS NULL", (DEMO_USER,))
        log = {'version': VERSION, 'name': NAME, 'inserted': True}

    cur.execute(
        """INSERT INTO schema_migrations (version, name, applied_at, extra)
           VALUES (?, ?, datetime('now','localtime'), ?)
           ON CONFLICT(version) DO UPDATE SET
               name=excluded.name, applied_at=excluded.applied_at, extra=excluded.extra""",
        (VERSION, NAME, json.dumps(log, ensure_ascii=False)))
    conn.commit()
    conn.close()
    return log


def main(argv=None):
    parser = argparse.ArgumentParser(description='给演示企业预置已认证资质')
    parser.add_argument('--db', default=None, help='目标库路径，默认走 db_connection.DB_PATH')
    parser.add_argument('--dry-run', action='store_true', help='只报告，不写库')
    parser.add_argument('--force', action='store_true',
                        help='忽略已执行标记重跑；已有 approved 记录时仍会跳过')
    args = parser.parse_args(argv)

    from db_connection import DB_PATH
    db_path = args.db or DB_PATH

    log = migrate(db_path, dry_run=args.dry_run, force=args.force)
    if log is None:
        print('版本 %s 已执行过，跳过（--force 可重跑）。' % VERSION)
        return 0
    if log.get('dry_run'):
        print('dry-run：目标库 %s，未写入。' % db_path)
        return 0
    print('迁移 %s（%s）完成，目标库 %s' % (VERSION, NAME, db_path))
    print('  预置已认证：%s' % ('是' if log.get('inserted') else '已有记录，跳过'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
