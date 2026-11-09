# -*- coding: utf-8 -*-
"""0005：给缺图条目补实拍图（9 张，全部来自 iNaturalist 研究级观察）。

图片由 tools/fetch_pest_photos.py 按学名取回：只要 quality_grade=research（已有社区
鉴定到种）且授权为 CC0 / CC BY / CC BY-NC 的照片，下载后按最长边 1024px 存到
images/pest/<entry_id>.jpg。本轮下载 12 张，人工过目后剔除 3 张（两张是叶片表面
微距糊片、一张只拍到蛹壳看不出虫体），保留 9 张。

为什么病害类没有一起补：按学名取图时，真菌与细菌的分类单元照片多为培养皿、镜检
或菌落，不是田间的作物症状。把培养皿照片放进「常见病虫害速查」比留空更糟，所以
本轮只补虫害，病害的 26 条继续显示「暂无实拍图」，等实拍或按症状严格筛选后再补。

幂等：按 entry_id 判重（pest_images 的主键），已有图的行一律不覆盖。

用法：
    python migrations/0005_pest_photos.py [--db 路径] [--dry-run] [--force]
"""

import argparse
import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(REPO_ROOT, 'backend')
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

VERSION = '0005'
NAME = 'pest_photos'

NOTE = 'iNaturalist 原图，缩放到 1024px 展示；研究级观察，非本地拍摄'

# entry_id, 文件名, 署名, 授权, 图注, 观察链接, 拍摄日期, 备注
IMAGES = (
    ('lychee_erinose_mite', 'lychee_erinose_mite.jpg', 'adele_schittone', 'CC BY-NC',
     '叶背绒毛状虫瘿（毛毡状），荔枝瘿螨为害状',
     'https://www.inaturalist.org/observations/213105684', '2024-04-29', NOTE),
    ('lychee_lycaenid', 'lychee_lycaenid.jpg', 'Tejas M', 'CC BY',
     '成虫（Deudorix epijarbas）',
     'https://www.inaturalist.org/observations/303094569', '2025-08-02', NOTE),
    ('citrus_red_mite', 'citrus_red_mite.jpg', 'javixu', 'CC BY-NC',
     '成螨（Panonychus citri）',
     'https://www.inaturalist.org/observations/75691465', '2021-04-29', NOTE),
    ('citrus_unaspis', 'citrus_unaspis.jpg', 'Xinyi Zheng', 'CC BY-NC',
     '果实上密集附着的蚧壳',
     'https://www.inaturalist.org/observations/330935797', '2025-12-10', NOTE),
    ('banana_root_knot_nematode', 'banana_root_knot_nematode.jpg',
     'edwardbarrettt83', 'CC BY-NC',
     '根系上的根结（瘤状肿大）',
     'https://www.inaturalist.org/observations/4062877', '2016-09-08',
     NOTE + '；示意图拍摄于其他寄主根系，仅示根结症状'),
    ('banana_skipper', 'banana_skipper.jpg', 'Murali Mohan Bettampady', 'CC BY-NC',
     '成虫（Erionota torus）',
     'https://www.inaturalist.org/observations/148097675', '2023-02-04', NOTE),
    ('rice_skipper', 'rice_skipper.jpg', 'gg_copen', 'CC BY-NC',
     '成虫（Parnara guttata）',
     'https://www.inaturalist.org/observations/396327135', '2026-09-01', NOTE),
    ('tea_weevil', 'tea_weevil.jpg', 'Dawn_Land', 'CC BY-NC',
     '成虫（Myllocerinus aurolineatus）',
     'https://www.inaturalist.org/observations/367901107', '2026-05-28', NOTE),
    ('vegetable_whitefly', 'vegetable_whitefly.jpg', 'Fundación Dodo Colombia',
     'CC BY-NC', '成虫（Bemisia tabaci）',
     'https://www.inaturalist.org/observations/69748239', '2021-02-17', NOTE),
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
        values = (entry_id, '/images/pest/%s' % filename, credit, license_name,
                  caption, url, shot_date, note)
        cur.execute(
            "INSERT OR IGNORE INTO pest_images (%s) VALUES (%s)"
            % (', '.join(_COLUMNS), ', '.join('?' * len(_COLUMNS))), values)
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
    parser = argparse.ArgumentParser(description='补病虫害实拍图（iNaturalist 授权照片）')
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
        print('dry-run：将写入 %d 张实拍图，目标库 %s，未写入。'
              % (log['images'], db_path))
        return 0
    print('迁移 %s（%s）完成，目标库 %s' % (VERSION, NAME, db_path))
    print('  写入 %d 张，跳过 %d 张，缺文件 %d 张'
          % (len(log['inserted']), len(log['skipped']), len(log['missing_files'])))
    return 0


if __name__ == '__main__':
    sys.exit(main())
