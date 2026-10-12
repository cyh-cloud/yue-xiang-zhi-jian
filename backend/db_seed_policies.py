#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""政策域的播种与预置政策重灌。

三个入口按调用方区分：
  - seed_policies() / seed_government_policies()：全新库灌预置政策；
  - refresh_policies()：按内容签名重灌，全新库与既有库都要跑。

⚠️ 预置政策是用 `gov_demo` 这个账号的身份灌进去的，而政府端真实发布时
author_id 也是 `gov_demo` —— 两者完全一样。所以删除范围必须收窄到「预置标题白名单」，
只按 author_id 删会静默抹掉政府自己发布的政策（改一次 policies_data.py 就丢数据）。
"""

import hashlib
import json

from domain_data.resources import policies_data as _policy_src

# 政策数据常量，供 seed_policies / seed_government_policies / refresh_policies 共用。
# ⚠️ 内容事实源 = domain_data.resources.policies_data（改完重启服务即生效，
#    靠 seed_meta 内容签名自动重灌预置政策）。
#    本模块不再内联政策正文 —— 历史版本在此内联的 5 篇政策含编造案例与未核实电话，已整体移除。
POLICIES_DATA = [
    (p['title'], p['content'], p['category'], p['date'], p.get('summary', ''))
    for p in _policy_src.POLICIES
]

# 预置政策的「写入结构」版本号。改动写入的列（新增/删除字段）时**必须 +1**，
# 否则老库里的行不会重建，新列会一直为空（详见 policies_signature 的说明）。
POLICIES_SEED_VERSION = 2

# 标题 -> 来源列表，播种时一并写入 source 字段
POLICY_SOURCES = {p['title']: p['sources'] for p in _policy_src.POLICIES}


def _policy_source_json(title):
    """把某条政策的来源列表序列化为 JSON 文本（存进 source 字段）。"""
    return json.dumps(POLICY_SOURCES.get(title, []), ensure_ascii=False)


def seed_policies(cursor):
    """全新库：灌入预置政策到 policies 表。"""
    # 政策（使用共用常量；source 存"来源列表"JSON）
    for title, content, cat, date, summary in POLICIES_DATA:
        cursor.execute("INSERT INTO policies (title, content, category, date, summary, source) VALUES (?, ?, ?, ?, ?, ?)",
                       (title, content, cat, date, summary, _policy_source_json(title)))


def seed_government_policies(cursor):
    """已有数据库时，补充政府政策数据"""
    for title, content, cat, date, summary in POLICIES_DATA:
        cursor.execute("INSERT INTO government_policies (title, content, category, author_id, date, summary, source) VALUES (?, ?, ?, ?, ?, ?, ?)",
                       (title, content, cat, 'gov_demo', date, summary, _policy_source_json(title)))


def policies_signature():
    """预置政策的内容签名：任一政策的 标题/正文/分类/日期/摘要 变了，签名就变。

    ⚠️ 还要带上 POLICIES_SEED_VERSION —— 当"写入哪些列"变了（例如新增 summary/date 字段），
    即使正文一字未改，也必须让签名变化、把老库里的行重建一遍，否则新列在旧库里恒为空。
    """
    h = hashlib.md5()
    h.update(('seedver:%s\x1e' % POLICIES_SEED_VERSION).encode('utf-8'))
    for title, content, cat, date, summary in POLICIES_DATA:
        h.update(('%s\x1f%s\x1f%s\x1f%s\x1f%s\x1e' % (title, content, cat, date, summary)).encode('utf-8'))
    return h.hexdigest()


def refresh_policies(cursor):
    """按「内容签名」刷新**预置政策**。

    ⚠️ 为什么必须这么改（历史 bug）：
      旧实现用 `any(len(content) < 200 for ...)` 当刷新条件，而政策正文都远超 200 字
      → need_refresh 恒为 False → **改了 POLICIES_DATA 界面上永远不变**，
      表现为"改了政策却没生效"（极易误判成缓存问题）。

    现在的策略：
      · 用 seed_meta 记录上次灌入的签名；签名一致 → 直接返回（幂等，不会每次启动都 DELETE）；
      · 签名变化 → 只重建**预置政策**：policies 全表 + government_policies 中「作者=gov_demo 且标题属于预置集」的行；
      · **不会碰政府端自行发布或管理员创建的政策**（标题不在预置集内，予以保留）。

    ⚠️ 为什么删除条件必须带上「标题 IN 预置集」（历史 bug）：
      预置政策是**用 `gov_demo` 这个账号的身份**灌进去的，而政府端真实发布时
      `create_policy(..., author_id=user['username'])` 传的也是 `gov_demo`
      —— 两者 author_id 完全一样！若只按 `author_id='gov_demo'` 删，
      那么**用 gov_demo 账号发布的政策会在下次签名变化时被静默抹掉**
      （即改一次 policies_data.py 就丢数据，且无任何报错）。
      故删除范围收紧为「预置标题白名单」。
    """
    signature = policies_signature()
    row = cursor.execute("SELECT value FROM seed_meta WHERE key = 'policies_seed'").fetchone()
    if row and row[0] == signature:
        return

    cursor.execute("DELETE FROM policies")
    for title, content, cat, date, summary in POLICIES_DATA:
        cursor.execute("INSERT INTO policies (title, content, category, date, summary, source) VALUES (?, ?, ?, ?, ?, ?)",
                       (title, content, cat, date, summary, _policy_source_json(title)))

    # ⚠️ 删除范围必须限定在「预置标题白名单」内：
    #    预置行与 gov_demo 自己发布的行 author_id 相同，只按 author_id 删会误伤后者。
    preset_titles = tuple(p[0] for p in POLICIES_DATA)
    cursor.execute(
        "DELETE FROM government_policies WHERE author_id = 'gov_demo' AND title IN (%s)"
        % ','.join('?' * len(preset_titles)),
        preset_titles)
    for title, content, cat, date, summary in POLICIES_DATA:
        cursor.execute(
            "INSERT INTO government_policies (title, content, category, author_id, date, summary, source) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (title, content, cat, 'gov_demo', date, summary, _policy_source_json(title)))

    cursor.execute(
        "INSERT OR REPLACE INTO seed_meta (key, value, updated_at) VALUES ('policies_seed', ?, datetime('now','localtime'))",
        (signature,))
