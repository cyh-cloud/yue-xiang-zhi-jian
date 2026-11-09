# -*- coding: utf-8 -*-
"""0004：给速查条目补「用药参考表」，只写能逐条对上来源的数值。

背景：迁移 0003 新增的 24 条只写了病虫描述与药剂有效成分名，chem_table 一律留空，
因为当时没有逐条核对用量、安全间隔期与每季最多次数。本脚本补上能核到出处的部分。

数据只有三个来源，全部为公开文件，可在 `pest_sources` 里按 key 查到：

  · PT-LICHENG-MANUAL —— 莆田市荔城区农业局《主要农作物病虫害防治与安全用药服务手册》
    （库内既有来源）。逐条给到剂型含量、稀释倍数、安全间隔期与每季次数。
  · ICAMA —— 中国农药数字监督管理平台上的农药登记标签（库内既有来源）。
    只取标签「使用范围和使用方法」里明确写了该作物 + 该防治对象的那一行。
  · GX-LYCHEE-WINTER —— 广西壮族自治区农业农村厅《荔枝秋冬季管理要点》（新增来源）。
    只给了稀释倍数，没给安全间隔期与每季次数，故这两列如实留 null，界面显示「未提供」。

三条口径：

  1. **只补不改**。条目 chem_table 已经有内容的（含运营在后台录过的），整条跳过。
  2. **不跨病虫借用**。登记标签写的是「水稻 细菌性条斑病」就不能挪给「白叶枯病」；
     写的是「茶橙瘿螨」就不能挪给「茶跗线螨」。对不上的宁可不写。
  3. **缺项留空不推算**。来源没给安全间隔期就写 null，不按同类药剂「估一个」。

因此 24 条里只有 11 条拿到可核对的数值；其余 13 条（荔枝小灰蝶、荔枝酸腐病、
龙眼煤烟病、龙眼瘿螨、香蕉花叶心腐病、香蕉弄蝶、水稻胡麻叶斑病、稻苞虫、
茶跗线螨、茶云纹叶枯病与三条水产）保持空表：这些要么没有对应登记标签，
要么公开文件只给了药剂名而没给用量与间隔期。

幂等：按条目 id 判重，重跑不覆盖已有内容。

用法：
    python migrations/0004_pest_chem_labels.py [--db 路径] [--dry-run] [--force]
"""

import argparse
import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(REPO_ROOT, 'backend')
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

VERSION = '0004'
NAME = 'pest_chem_labels'

# 新增来源：广西农业农村厅的荔枝秋冬管理指导。文号未核到，按库内既有做法写「待核」，
# 前端 sourceMeta() 会显示成「文号待核」。
NEW_SOURCES = (
    {
        'key': 'GX-LYCHEE-WINTER',
        'name': '荔枝秋冬季管理要点',
        'org': '广西壮族自治区农业农村厅',
        'doc_type': '技术指导',
        'doc_no': '待核',
        'date': '',
        'url': 'https://nynct.gxzf.gov.cn/xwdt/gxlb/gg/t26147433.shtml',
        'sort_order': 30,
    },
)

# entry_id -> (来源 key 列表, chem_table 行列表)
# 行字段：agent（剂型+含量）、dose（制剂量或稀释倍数）、interval_days、max_times。
# 未提供的写 None，不填数字。
CHEM = {
    'lychee_erinose_mite': (['GX-LYCHEE-WINTER'], [
        {'agent': '22.4%螺虫乙酯悬浮剂', 'dose': '3000~4000倍液',
         'interval_days': None, 'max_times': None},
        {'agent': '40%联苯肼酯·乙螨唑悬浮剂', 'dose': '4000~5000倍液',
         'interval_days': None, 'max_times': None},
    ]),
    'longan_tip_borer': (['ICAMA'], [
        {'agent': '35%氯虫苯甲酰胺水分散粒剂', 'dose': '5000~9000倍液',
         'interval_days': '14', 'max_times': '2'},
    ]),
    'citrus_rust_mite': (['PT-LICHENG-MANUAL'], [
        {'agent': '1.8%阿维菌素乳油', 'dose': '3000~4000倍液',
         'interval_days': '14', 'max_times': '2'},
        {'agent': '5%唑螨酯悬浮剂', 'dose': '800~1000倍液',
         'interval_days': '15', 'max_times': '2'},
        {'agent': '95%矿物油乳油', 'dose': '100~200倍液',
         'interval_days': None, 'max_times': '2'},
    ]),
    'citrus_unaspis': (['PT-LICHENG-MANUAL', 'ICAMA'], [
        {'agent': '25%噻嗪酮可湿性粉剂', 'dose': '1000~1666倍液',
         'interval_days': '35', 'max_times': '2'},
        {'agent': '95%矿物油乳油', 'dose': '50~100倍液',
         'interval_days': None, 'max_times': '2'},
        {'agent': '39%螺虫·噻嗪酮悬浮剂', 'dose': '2500~4500倍液',
         'interval_days': '35', 'max_times': '1'},
    ]),
    'citrus_scab': (['PT-LICHENG-MANUAL'], [
        {'agent': '10%苯醚甲环唑水分散粒剂', 'dose': '1000~2000倍液',
         'interval_days': '21', 'max_times': '3'},
        {'agent': '80%代森锰锌可湿性粉剂', 'dose': '400~600倍液',
         'interval_days': '21', 'max_times': '3'},
        {'agent': '75%肟菌·戊唑醇水分散粒剂', 'dose': '4000~6000倍液',
         'interval_days': '28', 'max_times': '2'},
    ]),
    'banana_root_knot_nematode': (['ICAMA'], [
        {'agent': '22%阿维·噻唑膦水乳剂', 'dose': '190~290毫升/亩（灌根）',
         'interval_days': '35', 'max_times': '3'},
        {'agent': '30%噻唑膦微囊悬浮剂', 'dose': '250~300毫升/亩（灌根）',
         'interval_days': None, 'max_times': '1'},
    ]),
    'rice_bacterial_blight': (['ICAMA'], [
        {'agent': '20%噻菌铜悬浮剂', 'dose': '100~130克/亩',
         'interval_days': '15', 'max_times': '3'},
    ]),
    'tea_weevil': (['PT-LICHENG-MANUAL'], [
        {'agent': '25克/升联苯菊酯乳油', 'dose': '100~140毫升/亩',
         'interval_days': '7', 'max_times': '1'},
    ]),
    'vegetable_whitefly': (['PT-LICHENG-MANUAL'], [
        {'agent': '20%呋虫胺可溶粒剂', 'dose': '30~50克/亩',
         'interval_days': '3', 'max_times': '2'},
        {'agent': '25%噻虫嗪水分散粒剂', 'dose': '10~12.5克/亩',
         'interval_days': '5', 'max_times': '4'},
        {'agent': '10%溴氰虫酰胺可分散油悬浮剂', 'dose': '33~40毫升/亩',
         'interval_days': '3', 'max_times': '3'},
        {'agent': '22.4%螺虫乙酯悬浮剂', 'dose': '20~30毫升/亩',
         'interval_days': '5', 'max_times': '1'},
    ]),
    'vegetable_grey_mold': (['PT-LICHENG-MANUAL'], [
        {'agent': '400克/升嘧霉胺悬浮剂', 'dose': '63~94毫升/亩',
         'interval_days': '5', 'max_times': '3'},
        {'agent': '50%异菌脲可湿性粉剂', 'dose': '75~100克/亩',
         'interval_days': '7', 'max_times': '3'},
        {'agent': '3亿CFU/克哈茨木霉菌可湿性粉剂', 'dose': '100~166.7克/亩',
         'interval_days': None, 'max_times': '3'},
    ]),
    'vegetable_fusarium_wilt': (['PT-LICHENG-MANUAL'], [
        {'agent': '2%春雷霉素可湿性粉剂', 'dose': '700~900克/亩',
         'interval_days': '4', 'max_times': '3'},
        {'agent': '3%甲霜·噁霉灵水剂', 'dose': '500~700倍液灌根，每株250毫升',
         'interval_days': '3', 'max_times': '3'},
        {'agent': '25%咪鲜胺乳油', 'dose': '500~750倍液',
         'interval_days': '12', 'max_times': '2'},
    ]),
}

_SOURCE_COLUMNS = ('key', 'name', 'org', 'doc_type', 'doc_no', 'date', 'url',
                   'sort_order')


def _ensure_sources(cur, log):
    for source in NEW_SOURCES:
        cur.execute(
            "INSERT OR IGNORE INTO pest_sources (%s) VALUES (%s)"
            % (', '.join(_SOURCE_COLUMNS), ', '.join('?' * len(_SOURCE_COLUMNS))),
            [source[column] for column in _SOURCE_COLUMNS])
        log['sources_added' if cur.rowcount else 'sources_present'].append(source['key'])


def _link_sources(cur, entry_id, keys):
    """补来源关联。已有的一律不动，只在末尾追加，避免打乱既有顺序。"""
    have = {row['source_key'] for row in cur.execute(
        "SELECT source_key FROM pest_entry_sources WHERE entry_id = ?",
        (entry_id,)).fetchall()}
    order = cur.execute(
        "SELECT COALESCE(MAX(sort_order), -1) + 1 FROM pest_entry_sources "
        "WHERE entry_id = ?", (entry_id,)).fetchone()[0]
    added = 0
    for key in keys:
        if key in have:
            continue
        cur.execute(
            "INSERT INTO pest_entry_sources (entry_id, source_key, sort_order) "
            "VALUES (?, ?, ?)", (entry_id, key, order))
        order += 1
        added += 1
    return added


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
        return {'dry_run': True, 'entries': len(CHEM)}

    log = {'version': VERSION, 'name': NAME, 'filled': [], 'skipped': [],
           'sources_added': [], 'sources_present': [], 'links_added': 0}

    _ensure_sources(cur, log)

    for entry_id, (keys, rows) in CHEM.items():
        row = cur.execute("SELECT chem_table FROM pest_entries WHERE id = ?",
                          (entry_id,)).fetchone()
        if row is None:
            raise SystemExit('条目不存在：%s' % entry_id)
        current = (row['chem_table'] or '').strip()
        if current not in ('', '[]'):
            # 已经有人录过（可能是运营），不覆盖。
            log['skipped'].append(entry_id)
            continue
        cur.execute("UPDATE pest_entries SET chem_table = ? WHERE id = ?",
                    (json.dumps(rows, ensure_ascii=False), entry_id))
        log['links_added'] += _link_sources(cur, entry_id, keys)
        log['filled'].append(entry_id)

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
    parser = argparse.ArgumentParser(description='补病虫害用药参考表（只补可核对项）')
    parser.add_argument('--db', default=None, help='目标库路径，默认走 db_connection.DB_PATH')
    parser.add_argument('--dry-run', action='store_true', help='只报告，不写库')
    parser.add_argument('--force', action='store_true',
                        help='忽略已执行标记重跑；已有 chem_table 的条目仍会跳过')
    args = parser.parse_args(argv)

    from db_connection import DB_PATH
    db_path = args.db or DB_PATH

    log = migrate(db_path, dry_run=args.dry_run, force=args.force)
    if log is None:
        print('版本 %s 已执行过，跳过（--force 可重跑）。' % VERSION)
        return 0
    if log.get('dry_run'):
        print('dry-run：将为 %d 条条目补用药表，目标库 %s，未写入。'
              % (log['entries'], db_path))
        return 0
    print('迁移 %s（%s）完成，目标库 %s' % (VERSION, NAME, db_path))
    print('  填表 %d 条，跳过已有 %d 条，新增来源 %d 个，新增来源关联 %d 条'
          % (len(log['filled']), len(log['skipped']),
             len(log['sources_added']), log['links_added']))
    return 0


if __name__ == '__main__':
    sys.exit(main())
