#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""案例域的播种：给本地成功案例补审核记录。

案例正文在 domain_data.resources.cases_data（不落库），但**审核状态必须落库**，
否则重启后审核结果就丢。这里复用通用 content_reviews 表，
与 course / job / procurement / model_3d 同一套链路。

CASE_REVIEW_TYPE 由本模块持有：它是「哪种内容走哪条审核记录」的登记处，
database.py 再原样再导出，`database.CASE_REVIEW_TYPE` 不变。
"""

# 成功案例的审核类型标识（走通用 content_reviews 链路，与 course/job/procurement/model_3d 同级）
CASE_REVIEW_TYPE = 'success_case'


def seed_case_reviews(cursor):
    """为「本地成功案例」补审核记录（幂等）。

    案例内容在 `domain_data.resources.cases_data`（不落库），但**审核状态必须落库**，
    否则重启后审核结果就丢了。这里复用通用 `content_reviews` 表：
      · 案例在库里没有审核记录 → 新增一条 `pending`（提交者 = admin_demo，即内容发布方）；
      · 已有记录（任何状态）→ **原样保留**，绝不把已通过的案例打回待审；
      · cases_data 里已删掉的案例 → 连带清掉其审核记录，避免脏数据。

    即：**新增案例需要超级管理员审核通过，才会出现在学员端首页**。
    """
    from domain_data.resources import cases_data
    valid_ids = {c['id'] for c in cases_data.get_cases()}

    rows = cursor.execute(
        "SELECT id, content_id FROM content_reviews WHERE content_type = ?",
        (CASE_REVIEW_TYPE,)).fetchall()
    existing = {r['content_id'] for r in rows}

    # 清理已不存在的案例残留记录
    for r in rows:
        if r['content_id'] not in valid_ids:
            cursor.execute("DELETE FROM content_reviews WHERE id = ?", (r['id'],))

    for cid in sorted(valid_ids - existing):
        cursor.execute(
            "INSERT INTO content_reviews (content_type, content_id, submitter_id, status) "
            "VALUES (?, ?, 'admin_demo', 'pending')",
            (CASE_REVIEW_TYPE, cid))
