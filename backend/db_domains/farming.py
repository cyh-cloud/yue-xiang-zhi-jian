#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""农业培训域：农时日历的作物、生育期、农事任务、订阅与提醒。

T05 从 database.py 按领域切分抽出，SQL 语义与返回结构与拆分前逐字节一致。
"""

import sqlite3
from db_connection import get_connection

import os
import sys

import repo_paths


def get_farming_products(active_only=True):
    """返回农产品目录列表"""
    conn = get_connection()
    sql = "SELECT * FROM farming_products"
    if active_only:
        sql += " WHERE is_active = 1"
    sql += " ORDER BY sort_order, id"
    rows = [dict(r) for r in conn.execute(sql).fetchall()]
    conn.close()
    return rows

def get_farming_product(product_id):
    """按 id 取单个农产品（含停用状态），不存在返回 None"""
    conn = get_connection()
    row = conn.execute("SELECT * FROM farming_products WHERE id = ?", (product_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def get_farming_sources():
    """返回数据来源登记表（key -> 来源方向）。doc_no 可能为「待核」。"""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM farming_sources ORDER BY sort_order, key").fetchall()
    except sqlite3.OperationalError:
        rows = []          # 旧库尚未建表时降级为空
    conn.close()
    return [dict(r) for r in rows]

def get_farming_source_map():
    """返回 {source_key: 来源对象} 映射，供接口把任务的 source_key 展开成可读信息。"""
    return {s['key']: s for s in get_farming_sources()}

def get_farming_category_labels():
    """返回 {分类key: 中文标签}，来自种子数据模块"""
    # T05/T06：路径基准跟随 T02 改为仓库根，模块搬进子目录后不能再从 __file__ 推导
    if repo_paths.REPO_ROOT not in sys.path:
        sys.path.insert(0, repo_paths.REPO_ROOT)
    try:
        from domain_data.agriculture import farming_data as fd
        return dict(getattr(fd, 'FARMING_CATEGORY_LABELS', {}) or {})
    except Exception:
        return {}

def get_farming_phenophases(product_id=None):
    """返回物候期列表（可按产品过滤）"""
    conn = get_connection()
    if product_id:
        rows = conn.execute(
            "SELECT * FROM farming_phenophases WHERE product_id = ? ORDER BY sort_order, id",
            (product_id,)).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM farming_phenophases ORDER BY product_id, sort_order, id").fetchall()
    out = [dict(r) for r in rows]
    conn.close()
    return out

def get_farming_tasks(product_id, month=None):
    """返回某产品的农事任务（可按月过滤）。phase 以名称形式一并返回，便于前端直接渲染。"""
    conn = get_connection()
    sql = """SELECT t.*, p.name AS phase_name, p.color AS phase_color
             FROM farming_tasks t
             LEFT JOIN farming_phenophases p ON p.id = t.phase_id
             WHERE t.product_id = ? AND t.is_active = 1"""
    params = [product_id]
    if month is not None:
        sql += " AND t.month = ?"
        params.append(int(month))
    sql += " ORDER BY t.month, t.sort_order, t.id"
    rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
    conn.close()
    return rows

def get_farming_task_by_id(task_id):
    """按 id 取单条任务（含物候期名称）"""
    conn = get_connection()
    row = conn.execute(
        """SELECT t.*, p.name AS phase_name, p.color AS phase_color
           FROM farming_tasks t
           LEFT JOIN farming_phenophases p ON p.id = t.phase_id
           WHERE t.id = ?""", (task_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


# ---------- 订阅 ----------

def get_farming_subscriptions(user_id):
    """返回某用户订阅的产品 id 列表"""
    conn = get_connection()
    rows = conn.execute(
        "SELECT product_id FROM farming_subscriptions WHERE user_id = ? ORDER BY id",
        (user_id,)).fetchall()
    conn.close()
    return [r[0] for r in rows]

def is_farming_subscribed(user_id, product_id):
    conn = get_connection()
    row = conn.execute(
        "SELECT 1 FROM farming_subscriptions WHERE user_id = ? AND product_id = ? LIMIT 1",
        (user_id, product_id)).fetchone()
    conn.close()
    return row is not None

def set_farming_subscription(user_id, product_id, subscribe=True):
    """订阅/退订。返回操作后的订阅状态。"""
    conn = get_connection()
    if subscribe:
        conn.execute(
            "INSERT OR IGNORE INTO farming_subscriptions (user_id, product_id) VALUES (?, ?)",
            (user_id, product_id))
    else:
        conn.execute(
            "DELETE FROM farming_subscriptions WHERE user_id = ? AND product_id = ?",
            (user_id, product_id))
    conn.commit()
    conn.close()
    return bool(subscribe)

def get_farming_subscribers(product_id):
    """返回订阅某产品的用户 id 列表（供管理/推送使用）"""
    conn = get_connection()
    rows = conn.execute(
        "SELECT user_id FROM farming_subscriptions WHERE product_id = ? ORDER BY id",
        (product_id,)).fetchall()
    conn.close()
    return [r[0] for r in rows]


# ---------- 提醒补发 ----------

def has_farming_reminder_sent(user_id, product_id, period):
    conn = get_connection()
    row = conn.execute(
        """SELECT 1 FROM farming_reminder_log
           WHERE user_id = ? AND product_id = ? AND period = ? LIMIT 1""",
        (user_id, product_id, period)).fetchone()
    conn.close()
    return row is not None

def mark_farming_reminder_sent(user_id, product_id, period):
    conn = get_connection()
    conn.execute(
        """INSERT OR IGNORE INTO farming_reminder_log (user_id, product_id, period)
           VALUES (?, ?, ?)""",
        (user_id, product_id, period))
    conn.commit()
    conn.close()

def clear_farming_reminder_log(user_id, product_id, period=None):
    """清除某用户在某作物上的提醒发送记录。

    退订时调用：幂等键是 (user_id, product_id, period)，日志一旦存在就永久跳过当期，
    若退订时不清理，用户「退订 → 重新订阅」在当月将静默收不到提醒。
    清除后语义为「重新订阅 = 重新开始接收」。
    """
    conn = get_connection()
    if period is None:
        conn.execute(
            "DELETE FROM farming_reminder_log WHERE user_id = ? AND product_id = ?",
            (user_id, product_id))
    else:
        conn.execute(
            "DELETE FROM farming_reminder_log WHERE user_id = ? AND product_id = ? AND period = ?",
            (user_id, product_id, period))
    conn.commit()
    conn.close()

def get_due_farming_tasks(product_id, year, month, until_day=None):
    """取某产品在指定年月、且已到期的任务。

    - until_day 为空 -> 该月全部任务（含尚未指定日期的，供列表展示）
    - until_day 有值 -> 仅 task_md 落在 1..until_day 之间的任务（供补发提醒，避免预告未来任务）
    """
    tasks = get_farming_tasks(product_id, month=month)
    if until_day is None:
        return tasks
    prefix = '%02d-' % month
    out = []
    for t in tasks:
        md = t.get('task_md')
        if not md or not md.startswith(prefix):
            continue
        try:
            day = int(md[3:5])
        except ValueError:
            continue
        if day <= int(until_day):
            out.append(t)
    return out


# ==================== 认证 ====================
