#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""政府政策域：政策发布、查询、更新、删除与工作概览。

T05 从 database.py 按领域切分抽出，SQL 语义与返回结构与拆分前逐字节一致。
"""

from datetime import datetime
from db_connection import get_connection

# 预置政策的标题白名单与政策来源辅助，与播种同住政策域
from db_seed_policies import POLICIES_DATA
from db_domains.resources import (
    _attach_policy_sources,
    default_policy_summary,
    get_case_review_stats,
    get_success_cases,
    policy_sources_to_json,
)


def count_government_policies():
    """政府政策域窄接口：(已发布数, 总数)。"""
    conn = get_connection()
    total = conn.execute("SELECT COUNT(*) FROM government_policies").fetchone()[0]
    published = conn.execute(
        "SELECT COUNT(*) FROM government_policies WHERE is_published = 1").fetchone()[0]
    conn.close()
    return published, total


def create_policy(title, content, category, author_id,
                  summary='', date='', source_text=''):
    """发布政策（政府端）。

    ⚠️ summary / date / source 必须一起写入（原实现只写 4 列）：
       学员端政策卡片会渲染「摘要」与「发布日期」两行，任一为空就整行不渲染；
       政府端刚发布的政策于是成了一张**没有摘要、没有日期、也没有资料来源**的残缺卡片，
       夹在 5 条预置政策（各有 32–42 字摘要 + 日期 + 4 条来源）中间格外突兀，
       点进详情还会看到「文号与数据均可溯源」这句**它并不具备**的背书。
    · summary 留空 → 取正文首段（default_policy_summary）；
    · date 留空 → 由调用方传当天（app.py），这里不再兜底，避免藏住"没填"这件事；
    · source_text 是表单原文（一行一条），在这里转成 source 列要的 JSON。
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO government_policies "
        "(title, content, category, author_id, summary, date, source) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (title, content, category, author_id,
         summary or default_policy_summary(content), date,
         policy_sources_to_json(source_text)))
    conn.commit()
    policy_id = cursor.lastrowid
    conn.close()
    return policy_id

def get_government_policies(category=None):
    """获取政府政策列表"""
    conn = get_connection()
    query = "SELECT * FROM government_policies WHERE is_published = 1"
    params = []
    if category:
        query += " AND category = ?"
        params.append(category)
    # 排序：政策发布日期优先；未填日期的（政府端新发布的）退回按发布时间
    query += " ORDER BY COALESCE(NULLIF(date, ''), substr(created_at, 1, 10)) DESC, id DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [_attach_policy_sources(dict(r)) for r in rows]

def get_all_government_policies():
    """获取所有政府政策（含未发布，政府端使用）"""
    conn = get_connection()
    rows = conn.execute("SELECT * FROM government_policies ORDER BY created_at DESC").fetchall()
    conn.close()
    return [_attach_policy_sources(dict(r)) for r in rows]

def get_policy_by_id(policy_id):
    """获取政策详情"""
    conn = get_connection()
    row = conn.execute("SELECT * FROM government_policies WHERE id = ?", (policy_id,)).fetchone()
    conn.close()
    return _attach_policy_sources(dict(row)) if row else None

def update_policy(policy_id, source_text=None, **kwargs):
    """更新政策。

    `source_text` 单独取值（表单原文，一行一条）：它不直接写库，
    而是经 policy_sources_to_json 转成 source 列要的 JSON。
    其它字段仍走白名单 —— 未知键一律忽略，不允许客户端改 author_id / created_at。
    """
    conn = get_connection()
    allowed = {'title', 'content', 'category', 'is_published', 'summary', 'date'}
    updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
    if source_text is not None:
        updates['source'] = policy_sources_to_json(source_text)
    if updates:
        updates['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        set_clause = ', '.join(f"{k}=?" for k in updates)
        params = list(updates.values()) + [policy_id]
        conn.execute(f"UPDATE government_policies SET {set_clause} WHERE id=?", params)
        conn.commit()
    conn.close()
    return True

def delete_policy(policy_id):
    """删除政策"""
    conn = get_connection()
    conn.execute("DELETE FROM government_policies WHERE id = ?", (policy_id,))
    conn.commit()
    conn.close()
    return True


# ==================== 政府端工作概览 ====================
# ⚠️ 口径红线（2026-10-07 用户拍板后重做）：
#   政府端概览只呈现**政务侧自己产生、且可核**的信息：政策发布情况 + 本地成功案例。
#   原先的「总用户 / 培训学员 / 岗位数 / 内容生产 / 已获证书 / 讨论帖 / 地区分布 / 培训方向」
#   全部移出，原因：
#     · 岗位数属企业侧数据 → 企业端「工作台」(/api/enterprise/stats)
#     · 培训口径原用 students.progress（**手填**字段；教师端口径是证书真实完成度，两者会打架）
#     · 「地区分布」按 users.region，实际多为空串，「广东省农业农村厅」等机构名还会混进来
#     · 证书/讨论帖在真实数据量下多为 0，硬拼成"大屏"只会显得空

def get_government_overview():
    """政府端工作概览：政策发布情况 + 本地成功案例。

    ⚠️ 政策必须区分「本级发布」与「平台预置」：
      预置政策是用 `gov_demo` 这个账号身份灌进去的（见 `_refresh_policies`），
      只按 author_id 分不开 —— 若直接 COUNT，平台预置的 5 条会被算成本级发布的政绩。
      这里复用与 `_refresh_policies` 相同的**预置标题白名单**（POLICIES_DATA）做区分。

    案例口径与学员端一致：只统计 `content_reviews` 中 status='approved' 的
    （未通过审核的案例，政府端同样不应看到）。
    """
    conn = get_connection()
    preset_titles = {p[0] for p in POLICIES_DATA}
    rows = conn.execute(
        "SELECT title, category, is_published FROM government_policies"
    ).fetchall()
    conn.close()

    own = {"total": 0, "published": 0, "unpublished": 0}
    preset = {"total": 0, "published": 0, "unpublished": 0}
    categories = {}
    for r in rows:
        bucket = preset if r["title"] in preset_titles else own
        bucket["total"] += 1
        if r["is_published"]:
            bucket["published"] += 1
        else:
            bucket["unpublished"] += 1
        cat = (r["category"] or "").strip() or "未分类"
        categories[cat] = categories.get(cat, 0) + 1

    review = get_case_review_stats()["case_review"]
    approved = get_success_cases(only_approved=True)

    region_count = {}
    for c in approved:
        reg = (c.get("region") or "").strip() or "未标注地区"
        region_count[reg] = region_count.get(reg, 0) + 1
    src_total = sum(len(c.get("sources") or []) for c in approved)

    return {
        "policies": {
            "own": own,
            "preset": preset,
            "categories": [
                {"category": k, "count": v}
                for k, v in sorted(categories.items(), key=lambda kv: (-kv[1], kv[0]))
            ],
        },
        "cases": {
            "total": review["total"],
            "approved": review["approved"],
            "pending": review["pending"],
            "rejected": review["rejected"],
            "regions": [
                {"region": k, "count": v}
                for k, v in sorted(region_count.items(), key=lambda kv: (-kv[1], kv[0]))
            ],
            "source_total": src_total,
            "avg_sources": round(src_total / len(approved), 1) if approved else 0,
            "items": [
                {
                    "id": c["id"],
                    "title": c.get("title") or "",
                    "region": (c.get("region") or "").strip(),
                    "sources": len(c.get("sources") or []),
                }
                for c in approved
            ],
        },
    }
