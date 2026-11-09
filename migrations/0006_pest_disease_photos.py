# -*- coding: utf-8 -*-
"""0006：病害症状图第二轮补图（2 张，来自 iNaturalist 研究级观察）。

背景：迁移 0005 只补了虫害。病害按学名取图时，绝大多数命中培养皿、镜检或寄主不符
（详见 output/pest-photos/disease-screening.md 的逐条结论）。本轮对 37 条缺图病害
抓了 26 帧候选，逐张过目后只有 2 帧同时满足「寄主对得上 + 症状可辨」：

  · 稻曲病：穗部谷粒被墨绿色菌块包裹，田间拍摄，寄主为水稻。
  · 蔬菜霜霉病：黄瓜叶片受叶脉限制的多角形黄褐色病斑，寄主为瓜类（属蔬菜范畴）。

其余 24 帧的淘汰理由记在筛选报告里，不在这里重复。剩 35 条病害仍无图，
继续显示「暂无实拍图」——这比放一张培养皿或别的作物的病斑更有用。

幂等：按 entry_id 判重，已有图的行不覆盖。

用法：
    python migrations/0006_pest_disease_photos.py [--db 路径] [--dry-run] [--force]
"""

import argparse
import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(REPO_ROOT, 'backend')
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

VERSION = '0006'
NAME = 'pest_disease_photos'

NOTE = 'iNaturalist 原图，缩放到 1024px 展示；研究级观察，非本地拍摄'

IMAGES = (
    ('rice_false_smut', 'rice_false_smut.jpg', 'hayaty', 'CC BY-NC',
     '穗部谷粒被墨绿色菌块包裹（稻曲病）',
     'https://www.inaturalist.org/observations/129502453', '2022-08-05', NOTE),
    ('vegetable_downy_mildew', 'vegetable_downy_mildew.jpg', 'Nicolas Schwab',
     'CC BY-NC', '叶面受叶脉限制的多角形黄褐色病斑（霜霉病）',
     'https://www.inaturalist.org/observations/237871099', '2024-08-23', NOTE),
)

_COLUMNS = ('entry_id', 'file', 'credit', 'license', 'caption', 'source_url',
            'shot_date', 'note')


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
        return {'dry_run': True, 'images': len(IMAGES)}

    log = {'version': VERSION, 'name': NAME, 'inserted': [], 'skipped': [],
           'missing_files': []}

    image_dir = os.path.join(REPO_ROOT, 'images', 'pest')
    for entry_id, filename, credit, license_name, caption, url, shot_date, note in IMAGES:
        if not os.path.isfile(os.path.join(image_dir, filename)):
            log['missing_files'].append(filename)
            continue
        cur.execute(
            "INSERT OR IGNORE INTO pest_images (%s) VALUES (%s)"
            % (', '.join(_COLUMNS), ', '.join('?' * len(_COLUMNS))),
            (entry_id, '/images/pest/%s' % filename, credit, license_name,
             caption, url, shot_date, note))
        if cur.rowcount:
            log['inserted'].append(entry_id)
        else:
            log['skipped'].append(entry_id)

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
    parser = argparse.ArgumentParser(description='补病害症状图（第二轮，仅收录逐张过目的）')
    parser.add_argument('--db', default=None, help='目标库路径，默认走 db_connection.DB_PATH')
    parser.add_argument('--dry-run', action='store_true', help='只报告，不写库')
    parser.add_argument('--force', action='store_true',
                        help='忽略已执行标记重跑；已有图的行不会覆盖')
    args = parser.parse_args(argv)

    from db_connection import DB_PATH
    db_path = args.db or DB_PATH

    log = migrate(db_path, dry_run=args.dry_run, force=args.force)
    if log is None:
        print('版本 %s 已执行过，跳过（--force 可重跑）。' % VERSION)
        return 0
    if log.get('dry_run'):
        print('dry-run：将写入 %d 张病害图，目标库 %s，未写入。'
              % (log['images'], db_path))
        return 0
    print('迁移 %s（%s）完成，目标库 %s' % (VERSION, NAME, db_path))
    print('  写入 %d 张，跳过 %d 张，缺文件 %d 张'
          % (len(log['inserted']), len(log['skipped']), len(log['missing_files'])))
    return 0


if __name__ == '__main__':
    sys.exit(main())
