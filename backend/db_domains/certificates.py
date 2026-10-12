#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""证书域：学员证书及其完成度。

T05 从 database.py 按领域切分抽出，SQL 语义与返回结构与拆分前逐字节一致。
"""

from db_connection import get_connection


def get_cert_progress_for(user_id):
    """证书域窄接口：某账号的全部证书进度与状态。

    教学支撑域算名册完成度时用，不再直查 certificates 表。
    """
    conn = get_connection()
    rows = conn.execute(
        "SELECT progress, status FROM certificates WHERE user_id = ?", (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_certificates(user_id):
    """获取用户证书"""
    conn = get_connection()
    rows = conn.execute("SELECT * FROM certificates WHERE user_id = ?", (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ==================== 学员 ====================
