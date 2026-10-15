#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""启动编排：建表、补列、播种、一次性迁移。全站只有一个 init_db()。

T03 之前它住在 database.py 那个 163 符号的纯转发层里。转发层删掉后，编排本身
没有第二处可去：它不属于任何领域（不读也不写某个领域的表，只按序调用别人），
放 db_domains/ 会让「数据访问层」混进启动逻辑，放 db_connection.py 会让连接
工厂背上与「建连」无关的职责。所以它是数据层基础设施里独立的一个模块，与
连接工厂、建表定义、口令散列、播种逻辑并列（见 PROJECT_STRUCTURE.md）。

播种顺序是有意义的，不要重排：

  1. 账号必须先于演示岗位 —— 演示岗位挂在 enterprise_demo 名下；
  2. 政策必须在案例审核之前 —— 案例审核只补记录，政策签名重灌会重建 policies 全表。

「哪些表不该存在」不在本模块裁决：清理已下线的废弃表由 db_schema.apply_schema()
负责，与建表定义同住，避免「建表加了、清库忘了加」。
"""

import json

from db_connection import get_connection
from db_schema import apply_schema
from db_seed_accounts import ensure_demo_accounts, seed_demo_accounts
from db_seed_cases import seed_case_reviews
from db_seed_demo_jobs import seed_demo_jobs
from db_seed_farming import seed_farming
from db_seed_policies import (
    refresh_policies,
    seed_government_policies,
    seed_policies,
)
from db_seed_portal import seed_carousels, seed_portal_content


def init_db():
    """初始化数据库：建表 + 填充种子数据

    首次执行建表并播种；重复执行幂等（种子按内容签名或存在性判断，不翻倍、
    不覆盖已审核结论、不清真实企业数据）。部署入口与测试入口都只调这一个函数。
    """
    conn = get_connection()
    cursor = conn.cursor()

    # 建表 + 给既有库补列（定义只在 db_schema.py 一处）
    apply_schema(cursor)

    # 检查是否已有种子数据
    count = cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if count == 0:
        # 顺序与原 _seed_data() 逐行对应：账号 -> policies -> government_policies
        # -> 轮播/公告/讨论。三者互不读对方，换序不会改变结果，但保持一致便于逐行比对。
        seed_demo_accounts(cursor)
        seed_policies(cursor)
        seed_government_policies(cursor)
        seed_portal_content(cursor)
    else:
        # 已有数据时，刷新政策内容（保证政策详情是最新的）
        refresh_policies(cursor)
        # 一次性清理历史遗留的"演示岗位"。
        # 旧版在 job_listings 里预置了 30 条**编造**岗位（假公司名/假薪资），
        # 现架构已改为：公开招聘信息走 jobs_data.py（策展、带来源），企业岗位走企业端发布+审核。
        # 这些演示行会冒充"真实在招职位"（学员可申请、还留真实姓名电话），必须移除。
        # 判定依据：企业端发布的行 enterprise_id 恒为**非空**的用户名，
        # 只有旧预置行是空串 —— 该条件精确命中预置行，不会误删企业数据。
        demo_ids = [r[0] for r in cursor.execute(
            "SELECT id FROM job_listings WHERE enterprise_id IS NULL OR enterprise_id = ''").fetchall()]
        if demo_ids:
            _qm = ','.join('?' * len(demo_ids))
            cursor.execute("DELETE FROM job_applications WHERE job_id IN (%s)" % _qm, demo_ids)
            cursor.execute("DELETE FROM saved_jobs WHERE job_id IN (%s)" % _qm, demo_ids)
            cursor.execute("DELETE FROM job_listings WHERE id IN (%s)" % _qm, demo_ids)
        # 如果政府政策表为空，填充初始数据
        gp_count = cursor.execute("SELECT COUNT(*) FROM government_policies").fetchone()[0]
        if gp_count == 0:
            seed_government_policies(cursor)
        # 如果轮播图为空，填充默认数据
        car_count = cursor.execute("SELECT COUNT(*) FROM carousels").fetchone()[0]
        if car_count == 0:
            seed_carousels(cursor)
        # 如果缺少新角色演示账户，补充创建
        ensure_demo_accounts(cursor)

    # 农时日历种子数据（幂等，两个分支都需保证存在）
    seed_farming(cursor)

    # 预置政策：按内容签名自动重灌（幂等；只重建 author_id='gov_demo' 的预置行，不动自建政策）
    refresh_policies(cursor)

    # 成功案例：把 cases_data.py 里新增的案例补一条**待审核**记录（幂等，不覆盖已有审核结果）
    seed_case_reviews(cursor)

    # 演示企业岗位（用户 2026-10-06 拍板）：让「投递」链路有可演示的载体。
    # 只动 is_demo=1 的行，真实企业岗位与其投递/收藏不受影响。
    seed_demo_jobs(cursor)

    # 废弃表清理已移入 db_schema.apply_schema()：内容落库（ADR 0002）把 success_cases
    # 翻回正式表后，原先那条 DROP 会在每次 init_db() 时把它连同灌进去的内容一起删掉。
    # 「哪些表不该存在」与「哪些表该存在」是同一份真相，故只在 db_schema 一处裁决。

    # 一次性迁移（2026-10-07）：assignment_submissions.score 的语义由
    # 「系统规则分」改为「教师批改分」（见 save_live_training 的说明）。
    # 历史上 status 还是 submitted/pending（从未被教师批改过）的行，其 score 其实是
    # 提交时算出的规则分 —— 若原样留着，教师端会把旧规则分显示成「我的评分」，
    # 学员端也会以为是老师给的成绩。这里把它们搬进 content.rule_score、score 置 NULL。
    # 幂等：迁完 score 即 NULL，不会再被这条查询命中。
    _legacy = cursor.execute(
        "SELECT id, content, score FROM assignment_submissions "
        "WHERE score IS NOT NULL AND (status IS NULL OR status IN ('submitted', 'pending'))"
    ).fetchall()
    for _r in _legacy:
        try:
            _d = json.loads(_r['content'] or '{}')
        except Exception:
            _d = {}
        if not isinstance(_d, dict):
            _d = {}
        _d.setdefault('rule_score', _r['score'])
        cursor.execute("UPDATE assignment_submissions SET content = ?, score = NULL WHERE id = ?",
                       (json.dumps(_d, ensure_ascii=False), _r['id']))

    conn.commit()
    conn.close()
