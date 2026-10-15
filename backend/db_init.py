#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""启动编排：建表、补列，外加「全新库灌一份演示账号」。全站只有一个 init_db()。

内容落库（ADR 0002）之后本模块的职责收窄到极致：**不写任何内容行**。农时、病虫害、
技艺、方言、招募、案例、政策这些内容全部住在 SQLite 里，由基线库交付，启动路径碰它们
就等于覆盖运营改过的数据。原先那套「按 sha1 内容签名决定是否 DELETE + INSERT 重灌」
的机制连带删除（两张签名元数据表与三个签名函数），它的三个后果分别是：重灌吃掉人工
复核结论、启动耗时随内容量线性增长、farming_tasks.id 每次重灌都变（而这个 id 直接
下发给前端）。

唯一保留的写入是演示账号：新环境拿一份只有表结构的库起来时，六个角色的演示账号
（含 operator）要能登录，否则平台连首页都进不去。账号是**身份**不是内容，
口令散列走 db_credentials，与登录校验同一份算法。

T03 之前它住在 database.py 那个 163 符号的纯转发层里。转发层删掉后，编排本身
没有第二处可去：它不属于任何领域（不读也不写某个领域的表，只按序调用别人），
放 db_domains/ 会让「数据访问层」混进启动逻辑，放 db_connection.py 会让连接
工厂背上与「建连」无关的职责。所以它是数据层基础设施里独立的一个模块，与
连接工厂、建表定义、口令散列并列（见 PROJECT_STRUCTURE.md）。

「哪些表不该存在」不在本模块裁决：清理已下线的废弃表由 db_schema.apply_schema()
负责，与建表定义同住，避免「建表加了、清库忘了加」。
"""

from db_connection import get_connection
from db_schema import apply_schema
from db_seed_accounts import ensure_demo_accounts, seed_demo_accounts


def init_db():
    """初始化数据库：建表 + 补列 +（仅空库）灌演示账号。

    不写任何内容行。重复执行幂等：第二次不会新增账号，也不会改动任何内容表。
    部署入口与测试入口都只调这一个函数。
    """
    conn = get_connection()
    cursor = conn.cursor()

    # 建表 + 给既有库补列 + 清理已下线的废弃表（定义只在 db_schema.py 一处）
    apply_schema(cursor)

    # 演示账号只在**空库**上灌一份：既有库缺哪个角色由 ensure_demo_accounts 补齐，
    # 两者都幂等，重复执行不会造出第二个 admin_demo。
    if cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        seed_demo_accounts(cursor)
    else:
        ensure_demo_accounts(cursor)

    conn.commit()
    conn.close()
