#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""采购域：农产品求购信息。

T05 从 database.py 按领域切分抽出，SQL 语义与返回结构与拆分前逐字节一致。
"""

from db_connection import get_connection

# 本模块的数据归属这个能力域。backend/core/permissions.py 的 CAPABILITIES
# 与 tools/check_architecture.py（T02 起按能力表判权）都以此为准：谁 import
# 本模块，谁就必须持 procurement.manage（读操作受 procurement.read 管）。
CAPABILITY = 'procurement'


def set_procurement_review_status(proc_id, review_status):
    """采购域的审核窄接口：只改 procurements 自己的 review_status。

    由审核域的 set_review_status() 按内容类型分派调用。
    """
    conn = get_connection()
    conn.execute("UPDATE procurements SET review_status=? WHERE id=?",
                 (review_status, proc_id))
    conn.commit()
    conn.close()


def create_procurement(product_name, enterprise_id, specification='', quantity='',
                       price_range='', delivery_location='', deadline='',
                       contact_info='', description=''):
    """企业发布求购"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO procurements (product_name, specification, quantity, price_range, "
        "delivery_location, deadline, contact_info, description, enterprise_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (product_name, specification, quantity, price_range, delivery_location,
         deadline, contact_info, description, enterprise_id))
    conn.commit()
    proc_id = cursor.lastrowid
    conn.close()
    # 延迟导入：审核域反过来要按内容类型分派到本模块，顶层导入会成环。
    from db_domains.reviews import create_content_review
    create_content_review('procurement', proc_id, enterprise_id)
    return proc_id

def get_procurements(enterprise_id=None, status=None, published_only=True):
    """获取求购列表"""
    conn = get_connection()
    query = "SELECT p.* FROM procurements p WHERE 1=1"
    params = []
    if enterprise_id:
        query += " AND p.enterprise_id = ?"
        params.append(enterprise_id)
    if status:
        query += " AND p.status = ?"
        params.append(status)
    if published_only:
        query += " AND p.review_status = 'approved'"
    query += " ORDER BY p.created_at DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    out = [dict(r) for r in rows]
    # T05：企业名与地区改由 users 域的展示窄接口补齐，本域 SQL 只碰 procurements
    from db_domains.users import get_enterprise_display
    display = get_enterprise_display([r['enterprise_id'] for r in out])
    for r in out:
        info = display.get(r['enterprise_id']) or {}
        r['company_name'] = info.get('company_name', '')
        r['enterprise_region'] = info.get('region', '')
    return out

def update_procurement(proc_id, **kwargs):
    """更新求购"""
    conn = get_connection()
    allowed = {'product_name', 'specification', 'quantity', 'price_range',
               'delivery_location', 'deadline', 'contact_info', 'description', 'status'}
    updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
    if updates:
        set_clause = ', '.join(f"{k}=?" for k in updates)
        params = list(updates.values()) + [proc_id]
        conn.execute(f"UPDATE procurements SET {set_clause} WHERE id=?", params)
        conn.commit()
    conn.close()
    return True

def delete_procurement(proc_id):
    """删除求购"""
    conn = get_connection()
    conn.execute("DELETE FROM procurements WHERE id = ?", (proc_id,))
    conn.execute("DELETE FROM content_reviews WHERE content_type='procurement' AND content_id=?", (proc_id,))
    conn.commit()
    conn.close()
    return True


# ==================== 新闻资讯（2026-10-07 整体下架） ====================
# 用户拍板：政府端「新闻资讯」整块去掉。
# 依据（实测）：`news_articles` 的**唯一消费者就是政府端那一个页面** ——
#   · 写入只有 `/api/government/news`（POST，仅 government 角色）；
#   · 公开的 `/api/resources/news` + `/<id>` 虽然存在，但 script.js / index.html **零调用**
#     → 学员端 / 教师端 / 管理端 / 企业端**没有任何入口**能看到资讯，
#       也就是说政务人员发出去的资讯只有他自己看得见（纯单向黑洞）。
# 故连同 4 条政府端路由 + 2 条公开路由 + 下面 5 个函数一并移除。
# ⚠️ `news_articles` 表**保留**（不做 DROP，历史数据仍在），只是不再有任何读写入口。
#    若将来要把资讯真正推到学员端，从这里恢复读写即可。


# ==================== 政府政策 ====================
