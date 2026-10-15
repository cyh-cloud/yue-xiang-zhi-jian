# -*- coding: utf-8 -*-
"""一次性内容迁移的收尾形态：脏数据清理 + 防重入记录（ADR 0002）。

它原本是 6400 行内容进库的唯一凭据（把六份 domain_data 内容模块与六份 domains 内容
常量灌进 T04 新建的 20 张表）。T10 是切换点：那 12 份代码内容已整体删除，内容只在
SQLite 里、由基线库交付，本脚本的灌库半边随之失效 —— 没有源头可灌，也不该再灌
（重灌会覆盖运营改过的内容）。

保留的两件事：

  1. **脏数据清理**：points 表 user_id IS NULL 的行、messages 表收件人指向不存在
     用户的行。这是迁移前对现库做的数据修复，与内容灌入无关，仍然有效；
  2. **防重入记录**：schema_migrations 里记一条 version，让后续迁移脚本知道这库
     已经走到过内容落库这一步。

清理动作逐行写进迁移日志（schema_migrations.extra 里的 JSON），不静默丢弃。

用法：
    python migrations/0001_content_to_db.py [--db 路径] [--dry-run] [--force]

  --db       指定目标库，默认走 db_connection.DB_PATH（即 YUEXIANG_DB 或 data/yuexiang.db）
  --dry-run  只报告将要做什么，不写库
  --force    忽略已执行标记重新跑一遍（会再次清理脏数据；不碰任何内容表）
"""

import argparse
import json
import os
import sys

# 后端代码整体迁入 backend/ 后，db_schema 与 db_connection 都在 backend/ 下。
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(REPO_ROOT, 'backend')
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

VERSION = '0001'
NAME = 'content_to_db'


def clean_dirty_rows(cur, log):
    """清两处现库脏数据，逐行记进日志（不静默丢弃）。

    points 的 user_id 是主键却出现了 NULL 行；messages 有 2 行收件人指向不存在的
    用户（一个 uuid、一个学号）。两者都是历史缺陷留下的行，删除前先把内容记下来。
    """
    dirty_points = [dict(r) for r in cur.execute(
        "SELECT rowid, user_id, balance, history FROM points "
        "WHERE user_id IS NULL").fetchall()]
    for r in dirty_points:
        cur.execute("DELETE FROM points WHERE rowid = ?", (r['rowid'],))

    orphan_messages = [dict(r) for r in cur.execute(
        "SELECT m.id, m.sender_id, m.receiver_id, m.created_at FROM messages m "
        "LEFT JOIN users u ON u.username = m.receiver_id "
        "WHERE u.username IS NULL").fetchall()]
    for r in orphan_messages:
        cur.execute("DELETE FROM messages WHERE id = ?", (r['id'],))

    log['cleaned_points'] = dirty_points
    log['cleaned_messages'] = orphan_messages


def migrate(db_path, dry_run=False, force=False):
    """执行迁移，返回本次写入的日志 dict。重复执行时返回 None（已执行过）。"""
    import sqlite3

    if not os.path.isfile(db_path):
        raise SystemExit('目标库不存在：%s' % db_path)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 先建表再查迁移记录：现库副本可能还没有 T04 的新表与迁移记录表。
    # apply_schema 只用 CREATE ... IF NOT EXISTS 加补列，重复执行安全。
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

    log = {'version': VERSION, 'name': NAME, 'tables': {},
           'cleaned_points': [], 'cleaned_messages': []}

    clean_dirty_rows(cur, log)

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
    parser = argparse.ArgumentParser(
        description='一次性内容迁移：清脏数据 + 记迁移版本（ADR 0002，T10 后不再灌内容）。')
    parser.add_argument('--db', default=None,
                        help='目标库路径，默认走 db_connection.DB_PATH')
    parser.add_argument('--dry-run', action='store_true', help='只报告，不写库')
    parser.add_argument('--force', action='store_true',
                        help='忽略已执行标记重新跑一遍（不碰任何内容表）')
    parser.add_argument('--make-baseline', action='store_true',
                        help='跑完后另存一份基线库（默认 data/baseline.db），'
                             '供新环境还原与 e2e 使用；不入版本库')
    parser.add_argument('--baseline-path', default=None,
                        help='基线库输出路径，默认 data/baseline.db')
    args = parser.parse_args(argv)

    from db_connection import DB_PATH
    db_path = args.db or DB_PATH

    if args.make_baseline:
        return make_baseline(db_path, args.baseline_path, force=args.force)

    log = migrate(db_path, dry_run=args.dry_run, force=args.force)
    if log is None:
        print('版本 %s 已执行过，跳过（--force 可重跑）。' % VERSION)
        return 0
    if log.get('dry_run'):
        print('dry-run：目标库 %s，未写入。' % db_path)
        return 0
    print('迁移 %s（%s）完成，目标库 %s' % (VERSION, NAME, db_path))
    print('  清理 points 脏行 %d 条、messages 孤儿行 %d 条' % (
        len(log['cleaned_points']), len(log['cleaned_messages'])))
    return 0


def make_baseline(db_path, output=None, force=False):
    """生成基线库：跑完迁移的库另存一份，删掉迁移记录，让它可以被再次迁移。

    为什么删掉 schema_migrations：基线库是「新环境的起点」，不是「已迁移完的库」。
    留着记录会让任何在它上面跑迁移的尝试直接跳过，新环境就永远拿不到后续迁移。
    删掉之后，基线库回到「表在、内容在、没有迁移历史」的状态，与现库迁移前的
    形状一致，任何迁移脚本都能在它身上从头跑。
    """
    import shutil
    import sqlite3

    target = output or os.path.join(REPO_ROOT, 'data', 'baseline.db')
    if os.path.abspath(target) == os.path.abspath(db_path):
        raise SystemExit('基线库不能覆盖目标库：%s' % target)

    log = migrate(db_path, force=force)
    if log is None:
        print('目标库 %s 已迁移过，直接复制为基线库。' % db_path)
    else:
        print('目标库 %s 已清理脏数据。' % db_path)

    os.makedirs(os.path.dirname(target), exist_ok=True)
    for suffix in ('', '-wal', '-shm', '-journal'):
        candidate = target + suffix
        if os.path.exists(candidate):
            os.remove(candidate)
    shutil.copyfile(db_path, target)

    # 基线库是「迁移前的形状」：去掉 WAL 附属文件与迁移记录，让后续迁移能在它上面跑。
    conn = sqlite3.connect(target)
    conn.execute("PRAGMA journal_mode=DELETE")
    conn.execute("DELETE FROM schema_migrations WHERE version = ?", (VERSION,))
    conn.commit()
    conn.close()
    for suffix in ('-wal', '-shm', '-journal'):
        candidate = target + suffix
        if os.path.exists(candidate):
            os.remove(candidate)

    print('基线库已生成：%s（%.1f KB）' % (target, os.path.getsize(target) / 1024.0))
    print('注意：data/*.db 已被 .gitignore 忽略，基线库不入版本库；'
          '新环境用本命令重新生成。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
