# -*- coding: utf-8 -*-
"""0008：给讨论区预置一批演示帖与评论。

为什么需要：讨论区此前是空的，演示时整页「暂无讨论」，看不出这个板块长什么样。

三条口径：

1. **标记为演示**。所有预置帖 `is_demo=1`，前端打「演示」标；与真实用户发帖
   严格区分，便于识别与一键清理（照 job_listings.is_demo 的既有做法）。
2. **不编造社区活跃度**。评论数按真实插入的评论条数回写；浏览数给的是演示值，
   但帖子带演示标，不会被当成真实流量统计。
3. **内容贴合平台业务**：广东荔枝/水稻、生鲜电商、广绣竹编、合作社采购、
   返乡创业，不写与平台无关的灌水内容。

幂等：库里已存在任一 `is_demo=1` 的帖子时直接跳过，不重复插入。

用法：
    python migrations/0008_demo_discussions.py [--db 路径] [--dry-run]
"""

import argparse
import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(REPO_ROOT, 'backend')
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

VERSION = '0008'
NAME = 'demo_discussions'

# (标题, 正文, 分类, 作者, 几天前, 几小时前, 浏览数, 是否置顶)
POSTS = [
    ('荔枝保花保果期到底要不要控水？',
     '家里 20 亩妃子笑，现在正抽穗。老一辈说花期要控水，控到叶子有点卷才坐果；'
     '但农技站的资料写的是保持土壤湿润。两边说法不一样，怕控过头影响坐果率。'
     '有没有广东这边实际管过的朋友说说经验？',
     'agriculture', 'student_demo', 5, 3, 57, 1),
    ('稻飞虱打什么药轮换比较稳？',
     '去年晚稻后期稻飞虱压不住，打了两次吡虫啉效果都一般。今年想提前准备轮换用药，'
     '噻嗪酮、烯啶虫胺这些怎么搭配？安全间隔期大概要留多少天？',
     'agriculture', 'student_demo', 4, 6, 34, 0),
    ('生鲜寄省内，泡沫箱加冰袋还是保温袋？',
     '做荔枝和龙眼的小件发货，省内次日达。现在用泡沫箱加两个冰袋，'
     '夏天客户收到还是会有闷坏的情况。保温袋成本高一些，实际效果差别大吗？',
     'ecommerce', 'enterprise_demo', 4, 2, 28, 0),
    ('直播间讲农产品，怎么把"土"讲成卖点？',
     '我们的番薯干是农户自己晒的，外观确实不如工厂货整齐，颜色也偏深。'
     '主播一开口就解释"这是手工的"，观众反而觉得在找借口。这种怎么讲更自然？',
     'ecommerce', 'student_demo', 3, 5, 46, 0),
    ('广绣入门先练哪种针法？',
     '完全零基础，想跟着课程自学广绣。看资料说先练直针，也有人说先练续针打基础。'
     '每天能挤出一个小时，大概多久能绣出一个小件？',
     'crafts', 'student_demo', 3, 1, 19, 0),
    ('竹编产品回南天怎么防霉？',
     '工作室在二楼，回南天墙面出水，竹篮放一周就开始起霉点。'
     '现在只能开抽湿机，电费顶不住。有没有更省的办法，涂木蜡油管用吗？',
     'crafts', 'teacher_demo', 2, 7, 22, 0),
    ('合作社统一采购化肥，怎么跟经销商谈价？',
     '我们社里 30 多户，一年复合肥用量大概 40 吨。之前各家自己买，'
     '今年想统一采购压成本。第一次谈，除了价格还能争取什么条件？账期一般怎么谈？',
     'general', 'enterprise_demo', 2, 3, 31, 0),
    ('返乡做农业，第一步先跑哪几个部门？',
     '在外面做了六年电商，准备明年回梅州包地种金柚。'
     '土地流转、营业执照、食品经营许可这几件事的先后顺序是什么？'
     '怕跑错顺序来回折腾，想先问清楚。',
     'general', 'student_demo', 1, 4, 40, 0),
]

# (帖子序号, 评论人, 内容, 几天前, 几小时前)
COMMENTS = [
    (0, 'teacher_demo',
     '花期控水不是控到卷叶，是控制土壤不积水。广州这边花期雨水多，'
     '重点是排水沟要通，不是断水。可以拿手抓一把土，捏成团松手能散开就差不多。', 5, 1),
    (0, 'enterprise_demo',
     '我们果园的做法是花穗期少灌勤灌，一次浇透不如小水多次。控过头落果会更严重。', 4, 8),
    (0, 'student_demo',
     '去年就是控太狠，坐果明显少了一截，今年准备按农技站的说法来。', 4, 2),
    (1, 'teacher_demo',
     '稻飞虱重点在压低虫口基数，别等爆发了再打。噻嗪酮和烯啶虫胺可以轮换，'
     '同一季同一种药不要连用两次。安全间隔期按标签来，晚稻一般不少于 14 天。', 4, 1),
    (1, 'student_demo',
     '收到，那前期要不要先放干田晒一晒？', 3, 9),
    (1, 'teacher_demo',
     '分蘖末期可以晒田，但抽穗扬花期不能断水，那会儿缺水直接影响结实率。', 3, 4),
    (2, 'teacher_demo',
     '荔枝呼吸热大，冰袋只是降温，关键是把果子预冷透再装箱。'
     '采后两小时内降到 5℃ 左右，再配泡沫箱，闷坏会少很多。', 3, 6),
    (2, 'student_demo',
     '我们合作社也是这么做的，预冷这一步省不得，直接装冰袋效果差一半。', 3, 2),
    (3, 'enterprise_demo',
     '不用急着解释"手工"，先讲为什么颜色深——晒足天数、没熏硫。'
     '把差异讲成工序的结果，观众接受度会高很多。', 3, 2),
    (3, 'teacher_demo',
     '同意。农产品直播最怕一上来道歉式开场，先把产地说清楚，再讲工艺。', 2, 7),
    (3, 'student_demo',
     '试过拍晒场的过程，评论区反而问得更细，转化确实好一些。', 2, 3),
    (4, 'teacher_demo',
     '先练直针，把起针落针的间距练匀，再上续针。每天一小时的话，'
     '两周左右能绣出一片像样的叶子。别一上来就绣复杂图样。', 2, 8),
    (4, 'student_demo',
     '谢谢，我先从叶片开始练，之前直接照着花样绣，线总是起毛。', 2, 1),
    (5, 'teacher_demo',
     '木蜡油能隔潮但不防霉，竹器长霉是含水率没降下来。'
     '编完先阴干到含水率 12% 以下，再上油，梅雨季收进密封箱加干燥剂更实在。', 1, 9),
    (5, 'student_demo',
     '干燥剂这个办法简单，我试试，抽湿机确实扛不住电费。', 1, 4),
    (6, 'teacher_demo',
     '40 吨的量可以谈阶梯价，另外争取送货到社、免费仓储一段时间。'
     '账期第一次合作别拉太长，现结换 3% 左右的价格优惠更划算。', 2, 2),
    (6, 'student_demo',
     '我们社去年谈的是送到村口，运费省下来也不少。', 1, 6),
    (6, 'enterprise_demo',
     '记得把用量和付款方式写进合同，口头承诺到旺季容易变。', 1, 2),
    (7, 'enterprise_demo',
     '先谈地，再办照。土地流转合同拿到乡镇经管站备案，'
     '营业执照下来后再去办食品经营许可，顺序反了要重跑。', 1, 3),
    (7, 'teacher_demo',
     '金柚如果做初加工，还要看厂房环评，这一步最容易漏。', 0, 9),
    (7, 'student_demo',
     '明白了，我先把流转合同和备案跑完再动别的。', 0, 5),
]


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
        return {'dry_run': True, 'posts': len(POSTS), 'comments': len(COMMENTS)}

    seeded = cur.execute(
        "SELECT COUNT(*) FROM discussions WHERE is_demo = 1").fetchone()[0]
    if seeded:
        log = {'version': VERSION, 'name': NAME, 'inserted': False,
               'reason': 'already-seeded'}
    else:
        ids = []
        for title, content, category, author, days, hours, views, pinned in POSTS:
            cur.execute(
                "INSERT INTO discussions (title, content, category, user_id, "
                "is_pinned, view_count, comment_count, is_demo, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, 0, 1, "
                "datetime('now','localtime','-%d days','-%d hours'))"
                % (days, hours),
                (title, content, category, author, pinned, views))
            ids.append(cur.lastrowid)

        for index, author, content, days, hours in COMMENTS:
            cur.execute(
                "INSERT INTO comments (target_type, target_id, user_id, content, "
                "created_at) VALUES ('discussion', ?, ?, ?, "
                "datetime('now','localtime','-%d days','-%d hours'))"
                % (days, hours),
                (ids[index], author, content))

        # 评论数按真实插入条数回写，不手填。
        cur.execute(
            "UPDATE discussions SET comment_count = ("
            "SELECT COUNT(*) FROM comments c WHERE c.target_type='discussion' "
            "AND c.target_id = discussions.id) WHERE is_demo = 1")

        log = {'version': VERSION, 'name': NAME, 'inserted': True,
               'posts': len(POSTS), 'comments': len(COMMENTS)}

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
    parser = argparse.ArgumentParser(description='预置讨论区演示帖')
    parser.add_argument('--db', default=None)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--force', action='store_true',
                        help='忽略已执行标记重跑；已有演示帖时仍会跳过')
    args = parser.parse_args(argv)

    from db_connection import DB_PATH
    db_path = args.db or DB_PATH

    log = migrate(db_path, dry_run=args.dry_run, force=args.force)
    if log is None:
        print('版本 %s 已执行过，跳过（--force 可重跑）。' % VERSION)
        return 0
    if log.get('dry_run'):
        print('dry-run：将插入 %d 帖 / %d 条评论，未写入。'
              % (log['posts'], log['comments']))
        return 0
    print('迁移 %s（%s）完成：%s'
          % (VERSION, NAME, '已插入 %d 帖 / %d 条评论'
             % (log.get('posts', 0), log.get('comments', 0))
             if log.get('inserted') else '已有演示帖，跳过'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
