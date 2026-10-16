#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""积分域：学员积分余额与流水。

T05 从 database.py 按领域切分抽出，SQL 语义与返回结构与拆分前逐字节一致。
"""

import json
from datetime import datetime
from db_connection import get_connection

# 本模块的数据归属这个能力域。backend/core/permissions.py 的 CAPABILITIES
# 与 tools/check_architecture.py（T02 起按能力表判权）都以此为准：谁 import
# 本模块，谁就必须持 point.manage（读操作受 point.read 管）。
CAPABILITY = 'point'


def get_points(user_id):
    """获取积分"""
    conn = get_connection()
    row = conn.execute("SELECT * FROM points WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    if row:
        return {'balance': row['balance'], 'history': json.loads(row['history'])}
    return {'balance': 0, 'history': []}

# ---- 需要真事务的「多语句单连接」名单（REFACTOR-PLAN 3.4，T11 落成注释）----
# 24 处「多语句单连接」里只有 5 处需要原子性，名单如下。当前 SQLite 默认行为
# （autocommit + 单连接）下它们已经是对的；写在这里是为了避免后续有人在中间
# 插一条不相关语句，把「读余额后写」变成两步竞态。
#   1. points.update_points（本函数）：先读余额，再按余额算新值后写回；
#   2. reviews.set_review_status：改自己的 content_reviews，再分派写别人的表；
#   3. users.delete_user_by_admin：一次删三张表；
#   4. users.register_user：写 users 后建积分行；
#   5. employment.save_resume：upsert 两段（查存在性 → 插或改）。
# students.add_student 原先在本名单里（先查最大学号、再插入，撞主键重试）。
# 它已改成一条 INSERT 内取号（见 students._INSERT_STUDENT_SQL），不再有
# 「读改写」的两步竞态，故移出。
# 其余多语句函数是「两条独立 write 恰好放在一个函数里」，不构成事务需求。
TRANSACTION_CRITICAL = (
    'update_points', 'set_review_status',
    'delete_user_by_admin', 'register_user', 'save_resume',
)


def update_points(user_id, delta, action="操作"):
    """更新积分

    ⚠️ 需要真事务（见上方 TRANSACTION_CRITICAL）：先 SELECT 读余额，
       再按余额算新值写回。中间不得插入任何不相关语句。
    """
    conn = get_connection()
    row = conn.execute("SELECT * FROM points WHERE user_id = ?", (user_id,)).fetchone()
    if not row:
        conn.execute("INSERT INTO points (user_id, balance, history) VALUES (?, ?, ?)",
                     (user_id, max(0, delta), json.dumps([{"action": action, "points": delta, "date": datetime.now().strftime('%Y-%m-%d')}])))
        conn.commit()
        conn.close()
        return max(0, delta)

    new_balance = row['balance'] + delta
    if new_balance < 0:
        conn.close()
        return -1  # 余额不足

    history = json.loads(row['history'])
    history.append({"action": action, "points": delta, "date": datetime.now().strftime('%Y-%m-%d')})
    conn.execute("UPDATE points SET balance = ?, history = ? WHERE user_id = ?",
                 (new_balance, json.dumps(history), user_id))
    conn.commit()
    conn.close()
    return new_balance


# ==================== 证书 ====================
