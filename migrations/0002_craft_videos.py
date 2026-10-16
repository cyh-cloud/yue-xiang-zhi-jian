# -*- coding: utf-8 -*-
"""把四门技艺的视频教学内容补进 craft_videos（ADR 0002：内容只存在于库里）。

背景：视频教学原先由 backend/domains/crafts/routes.py 的 CRAFTS_KNOWLEDGE 常量下发。
T08 把技艺内容切到读库时，视频因为「库里没有视频表」留在了常量里；T10 删除内容常量
时没有对应的表接手，详情响应就不再带 videos 键，前端的视频教学区（script.js 的
renderCraftVideo）整块收起。

本脚本把那段内容落进 craft_videos，并把这次动作登记进 schema_migrations。
数据取自 git 历史 f5c5d46:backend/domains/crafts/routes.py，逐条原样搬入。

幂等：按 (craft_id, bvid) 判重，已存在的跳过，不覆盖运营在后台改过的内容。

用法：
    python migrations/0002_craft_videos.py [--db 路径] [--dry-run]
"""

import argparse
import json
import os
import sys

# 后端代码整体迁入 backend/ 后，db_connection 在 backend/ 下。
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(REPO_ROOT, 'backend')
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

VERSION = '0002'
NAME = 'craft_videos'

# craft_id -> [(bvid, title, author, duration, view, danmaku, like, pubdate, cover), ...]
VIDEOS = {
    'embroidery': [
        ('BV1REKq6jEmp', '沉浸式复绣清代广绣｜从起针到成品全过程', '广绣梁绣绣', 2157, 994, 1, 60, 1784445815, 'http://i0.hdslb.com/bfs/archive/07919cc38aa7737d6620928df4136e8e0f417136.jpg'),
        ('BV1yD4y137Sv', '《南粤工匠》纪录片第十一集-用针线记录时光的末代花佬许炽光', '广东工会', 1331, 8063, 3, 193, 1676951297, 'http://i2.hdslb.com/bfs/archive/af68850d5196c4792e6e2b10a8817775953b8c15.jpg'),
        ('BV1D34y1E7ui', '广绣耳环绕边教学', '广绣梁绣绣', 186, 515, 0, 12, 1653275562, 'http://i0.hdslb.com/bfs/archive/af725d27daf591bc0fe16c335f48318dc188237d.jpg'),
        ('BV1ig411Z7oP', '广绣制作过程（花瓶）', '梁晓曼广绣', 222, 845, 0, 17, 1658566987, 'http://i1.hdslb.com/bfs/archive/da1d1f68819a4101dcd9c94801c9e8ef66f964a7.jpg'),
    ],
    'woodcarving': [
        ('BV1G54y1h7Cz', '【传统工艺】金漆木雕（潮州木雕）（1080p）', '思维什锦店', 2365, 4447, 2, 81, 1616516053, 'http://i1.hdslb.com/bfs/archive/7f12780df090bf09a5d5af7020f30f35cacd48c8.jpg'),
        ('BV1is21YjERi', '超解压纪录片来了！看金光闪闪的潮州木雕，听有趣的故事。', '广东卫视', 861, 7570, 1, 124, 1728619788, 'http://i2.hdslb.com/bfs/archive/cd752250c9e61b5458a710827981cd5523281780.jpg'),
        ('BV1cR4y1z7g1', '木雕界的天花板，潮州金漆木雕是如何制作的', '澜日记', 170, 1052, 0, 18, 1675530848, 'http://i1.hdslb.com/bfs/archive/68a2787cc31476252c9b26e864721084c515848d.jpg'),
        ('BV1Us411Y7RZ', '【探秘非遗】潮州金漆木雕之美', '发现城市之美', 341, 6244, 8, 83, 1481097934, 'http://i2.hdslb.com/bfs/archive/79496478bd45c84f36b50534fb0468b4e768af52.jpg'),
    ],
    'ceramics': [
        ('BV1QB4y1q7ER', '岭南非遗--石湾陶艺的创作过程，泥土的选择！', '岭南非遗文化', 250, 1538, 0, 16, 1656490736, 'http://i1.hdslb.com/bfs/archive/bbe52917188bf18aa9771a7e1ed0b847b51afee8.jpg'),
        ('BV1hG411x7G1', '岭南非遗--石湾陶艺的创作过程，釉料的配比！', '岭南非遗文化', 162, 1045, 0, 19, 1656749151, 'http://i0.hdslb.com/bfs/archive/c87dee231909185993e502f013971ff9b8d310c2.jpg'),
        ('BV1Ymo6YpEiA', '陶塑大师刘泽棉：石湾陶艺的匠心坚守者', '中国手艺网', 333, 230, 0, 4, 1742779408, 'http://i1.hdslb.com/bfs/archive/f6b183c1bdfecdc1dc36d8512ce78aff5f3afadc.jpg'),
        ('BV1Hq4y1A7BK', '【微纪录片】石湾公仔——泥土里的坚守', '啊蛙啊蛙-', 301, 2485, 0, 35, 1642131911, 'http://i1.hdslb.com/bfs/archive/381fc795cf9589e6ae90fab1d3a2b3b9c27dde6f.jpg'),
    ],
    'lacquer': [
        ('BV18z4y1o7p4', '【匠心工艺】真正的“国潮”长什么样？傅以周带你走进阳江髹饰技艺', '广东印记', 181, 3703, 23, 97, 1603942336, 'http://i1.hdslb.com/bfs/archive/b9df8cb4212131d9691a927b155dfc9527425d9a.jpg'),
        ('BV1rW4y1C7of', '阳江漆器', '大脚艺术', 97, 446, 1, 14, 1654212710, 'http://i2.hdslb.com/bfs/archive/1134c2ebfac381dff1fded6e26393fa616c9b8e6.jpg'),
        ('BV1BG4y1U7qG', '阳江探索之旅，漆器髹饰技艺，为阳江文化建设添光加彩', '曾小旅', 405, 2659, 0, 7, 1675404369, 'http://i0.hdslb.com/bfs/archive/31aedd10b7370de6790487ec79e938eb79f02f5e.jpg'),
        ('BV1QFYq6CEU8', '解锁 阳江漆器博物馆', '哗友仔', 58, 18, 0, 0, 1789303709, 'http://i2.hdslb.com/bfs/archive/34871925e13784bdbf7f1a3a374ed0a6c3cd3fa9.jpg'),
    ],
}

_COLUMNS = ('craft_id', 'bvid', 'title', 'author', 'duration', 'view_count',
            'danmaku', 'like_count', 'pubdate', 'cover', 'sort_order')


def migrate(db_path, dry_run=False):
    """把视频行补进库。已执行过返回 None。"""
    import sqlite3

    # craft_videos 是本次新增的表：老库还没建过它。建表唯一真相源在 db_schema，
    # 这里直接调它的 apply_schema（幂等），不另抄一份 DDL。
    from db_schema import apply_schema

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    apply_schema(cur)
    if cur.execute("SELECT 1 FROM schema_migrations WHERE version = ?",
                   (VERSION,)).fetchone():
        conn.close()
        return None

    inserted, skipped = [], []
    for craft_id, rows in VIDEOS.items():
        if not cur.execute("SELECT 1 FROM crafts WHERE id = ?", (craft_id,)).fetchone():
            raise SystemExit('库里没有技艺 %s，先跑 0001 或恢复基线库' % craft_id)
        for index, row in enumerate(rows):
            bvid = row[0]
            if cur.execute("SELECT 1 FROM craft_videos WHERE craft_id = ? AND bvid = ?",
                           (craft_id, bvid)).fetchone():
                skipped.append('%s/%s' % (craft_id, bvid))
                continue
            cur.execute(
                "INSERT INTO craft_videos (%s) VALUES (%s)"
                % (', '.join(_COLUMNS), ', '.join('?' * len(_COLUMNS))),
                (craft_id,) + tuple(row) + (index,))
            inserted.append('%s/%s' % (craft_id, bvid))

    log = {'inserted': inserted, 'skipped': skipped}
    if dry_run:
        conn.rollback()
        conn.close()
        log['dry_run'] = True
        return log

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
    parser = argparse.ArgumentParser(description='技艺视频内容落库（craft_videos）。')
    parser.add_argument('--db', default=None,
                        help='目标库路径，默认走 db_connection.DB_PATH')
    parser.add_argument('--dry-run', action='store_true', help='只报告，不写库')
    args = parser.parse_args(argv)

    from db_connection import DB_PATH
    db_path = args.db or DB_PATH
    log = migrate(db_path, dry_run=args.dry_run)
    if log is None:
        print('版本 %s 已执行过，跳过。' % VERSION)
        return 0
    print('插入 %d 条视频，跳过 %d 条（已存在）%s'
          % (len(log['inserted']), len(log['skipped']),
             '（dry-run，未写入）' if log.get('dry_run') else ''))
    return 0


if __name__ == '__main__':
    sys.exit(main())
