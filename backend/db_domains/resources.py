#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本土资源域：成功案例与政策的口径、来源与查询。

T05 从 database.py 按领域切分抽出，SQL 语义与返回结构与拆分前逐字节一致。
"""

import json
import re
from db_connection import get_connection

# 本模块的数据归属这个能力域。backend/core/permissions.py 的 CAPABILITIES
# 与 tools/check_architecture.py（T02 起按能力表判权）都以此为准：谁 import
# 本模块，谁就必须持 resource.manage（读操作受 resource.read 管）。
CAPABILITY = 'resource'

# 成功案例的审核类型标识（走通用 content_reviews 链路，与 course/job/procurement/model_3d 同级）
CASE_REVIEW_TYPE = 'success_case'


def get_success_cases(only_approved=True):
    """获取成功案例

    内容唯一事实源 = cases_data.py（不读数据库）。
    按 domain_data.resources.cases_data 的既有约定：改完重启服务即生效，无需 init_db()。

    ⚠️ 审核：案例需经**超级管理员**审核通过才对学员端可见。
    审核状态复用 `content_reviews`（`content_type='success_case'`、`content_id=案例 id`），
    由 `_seed_case_reviews()` 在 init_db() 时为每条案例补一条 pending 记录。
    `only_approved=False` 仅给管理端/自检用（看到含未通过的全部案例）。
    """
    from domain_data.resources import cases_data
    cases = cases_data.get_cases()
    if not only_approved:
        return cases
    conn = get_connection()
    rows = conn.execute(
        "SELECT content_id FROM content_reviews WHERE content_type = ? AND status = 'approved'",
        (CASE_REVIEW_TYPE,)).fetchall()
    conn.close()
    approved = {r['content_id'] for r in rows}
    return [c for c in cases if c['id'] in approved]

def get_case_review_stats():
    """案例审核统计（供前端区分"审核中"与"加载失败"，避免把待审当成没数据）。"""
    from domain_data.resources import cases_data
    cases = cases_data.get_cases()
    valid = {c['id'] for c in cases}
    total = len(cases)

    conn = get_connection()
    rows = conn.execute(
        "SELECT content_id, status, COUNT(*) AS n FROM content_reviews "
        "WHERE content_type = ? GROUP BY content_id, status",
        (CASE_REVIEW_TYPE,)).fetchall()
    conn.close()

    stat = {'approved': 0, 'pending': 0, 'rejected': 0}
    covered = 0
    for r in rows:
        if r['content_id'] not in valid:
            continue          # 已被 cases_data 删掉的案例，不计入
        covered += r['n']
        if r['status'] in stat:
            # 查询按 (content_id, status) 分组 —— 这里必须**累加**，不能赋值
            stat[r['status']] += r['n']

    stat['total'] = total
    # 还没有任何审核记录的案例（如刚加进 cases_data.py、尚未跑过 init_db）一律按待审计。
    # （cases_data 现位于 domain_data/resources/cases_data.py）
    # ⚠️ 这里必须用 total - covered（未被覆盖的数），不能只减 approved/rejected ——
    #    否则已计入 pending 的行会被重复统计（混合状态时 pending 虚高）。
    stat['pending'] += max(0, total - covered)
    return {'case_review': stat}

def get_case_notes():
    """案例页口径说明文案（与内容同源，避免前端硬编码漂移）。"""
    from domain_data.resources import cases_data
    return {
        "source_note": cases_data.CASE_SOURCE_NOTE,
        "lessons_note": cases_data.LESSONS_NOTE,
    }

def get_policy_notes():
    """政策页口径说明文案（来源说明 + 免责声明，与内容同源）。"""
    from domain_data.resources import policies_data
    return policies_data.get_policy_notes()


# ---- 政策分类归一化 ----
# ⚠️ 政府端发布表单里「综合」那一项的 value 是**英文** general
#    （government.html: `<option value="general">综合</option>`），
#    而后端原先不做任何归一化、直接入库。
#    学员端的分类筛选按钮与标签配色都按**中文**分类走 →
#    结果是：学员会看到一张标签写着英文「general」、底色还是「补贴」绿的政策卡片，
#    而且点任何分类筛选都找不到它（界面看起来像这条政策凭空消失了）。
#    历史库里已经可能存有 general，故在 getter 收口处（_attach_policy_sources）也归一化一次。
_POLICY_CATEGORY_ALIASES = {
    'general': '综合',
    'other': '综合',
    '综合': '综合',
    '其他': '综合',
}

def normalize_policy_category(value):
    """把政策分类归一化成面向学员的中文分类。

    未知分类**原样返回**（不臆造、不强行塞进已有分类）——
    真实出现了新分类时，前端会按数据动态生成对应的筛选项。
    """
    v = str(value or '').strip()
    if not v:
        return '综合'
    return _POLICY_CATEGORY_ALIASES.get(v.lower(), v)

def _attach_policy_sources(d):
    """把 policy 行的 source 字段（JSON 文本）解析成 sources 列表，供前端直接渲染出处。"""
    raw = d.pop('source', '') or ''
    try:
        d['sources'] = json.loads(raw) if raw else []
    except (ValueError, TypeError):
        d['sources'] = []
    # 分类归一化也放在这里：本函数是**所有**政策 getter 的公共收口
    # （get_policies / get_government_policies / get_all_government_policies / get_policy_by_id），
    # 在这里统一处理，历史脏数据（category='general'）无需迁移即可被修正。
    d['category'] = normalize_policy_category(d.get('category'))
    return d


# ---- 政府端政策输入归一化 ----
# 政府端表单收的是「人写的文本」，落库前统一转成学员端渲染器认识的形状。
# ⚠️ 这三个函数是**唯一**的转换入口：create_policy / update_policy 都从这里过，
#    别在 app.py 里另写一份（历史坑：写入侧与读取侧对同一列的理解不一致）。

def policy_sources_to_json(text):
    """把「资料来源」文本框转成 source 列要的 JSON 数组。

    约定：一行一条来源，写作 `来源名称` 或 `来源名称 | URL`。
    · 空输入 → `[]`（**宁缺勿编**：学员端据此不显示「文号与数据均可溯源」的口径说明，
      因为那条口径是对来源区块的背书，没有来源就不成立）；
    · URL 必须是 http(s)，否则只留名称（前端也能渲染成纯文本）。
    """
    items = []
    for line in str(text or '').splitlines():
        line = line.strip()
        if not line:
            continue
        parts = [x.strip() for x in line.split('|')]
        title = parts[0]
        if not title:
            continue
        item = {'title': title}
        url = parts[1] if len(parts) > 1 else ''
        if re.match(r'^https?://', url, re.I):
            item['url'] = url
        items.append(item)
    return json.dumps(items, ensure_ascii=False)

def default_policy_summary(content, limit=60):
    """摘要留空时，从**正文自己**取首段（不是另写一句通用话术）。

    跳过 `【小标题】` 行与 `•`/`-` 列表符号行，取第一段真正的正文；
    超长才省略号。正文为空则返回空串 —— 此时学员端卡片不渲染摘要行（不用占位充数）。
    """
    for line in str(content or '').splitlines():
        s = line.strip().lstrip('•-').strip()
        if not s or (s.startswith('【') and s.endswith('】')):
            continue
        return s[:limit] + ('…' if len(s) > limit else '')
    return ''

# ==================== 教师仪表板 ====================
