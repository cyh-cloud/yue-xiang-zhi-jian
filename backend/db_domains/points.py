#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""积分域：学员积分余额与流水。

T05 从 database.py 按领域切分抽出，SQL 语义与返回结构与拆分前逐字节一致。
"""

import json
from datetime import datetime
from db_connection import get_connection

# 本模块的数据归属这个能力域。机械检查（tools/check_architecture.py）与
# backend/core/permissions.py 的 CAPABILITIES 都以此为准：谁 import 本模块，
# 谁就必须持 ${cap}.manage（读操作受 ${cap}.read 管）。
CAPABILITY = 'point'


def get_points(user_id):
    """获取积分"""
    conn = get_connection()
    row = conn.execute("SELECT * FROM points WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    if row:
        return {'balance': row['balance'], 'history': json.loads(row['history'])}
    return {'balance': 0, 'history': []}

def update_points(user_id, delta, action="操作"):
    """更新积分"""
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
