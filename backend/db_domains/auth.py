#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""认证域：登录校验与会话生命周期。

T05 从 database.py 按领域切分抽出，SQL 语义与返回结构与拆分前逐字节一致。
"""

import time
import uuid
from db_connection import get_connection

# 本模块的数据归属这个能力域。机械检查（tools/check_architecture.py）与
# backend/core/permissions.py 的 CAPABILITIES 都以此为准：谁 import 本模块，
# 谁就必须持 ${cap}.manage（读操作受 ${cap}.read 管）。
CAPABILITY = 'auth'
from db_credentials import verify_password


def authenticate_user(username, password):
    """验证用户登录"""
    conn = get_connection()
    user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    if user and verify_password(user['password_hash'], password):
        return dict(user)
    return None

def create_session(user_id):
    """创建会话"""
    session_id = str(uuid.uuid4())
    now = time.time()
    expires = now + 86400  # 24小时
    conn = get_connection()
    conn.execute("INSERT INTO user_sessions (session_id, user_id, login_time, expires_at) VALUES (?, ?, ?, ?)",
                 (session_id, user_id, now, expires))
    conn.commit()
    conn.close()
    return session_id

def get_session(session_id):
    """获取会话"""
    conn = get_connection()
    session = conn.execute("SELECT * FROM user_sessions WHERE session_id = ?", (session_id,)).fetchone()
    if session and time.time() < session['expires_at']:
        user = conn.execute("SELECT * FROM users WHERE username = ?", (session['user_id'],)).fetchone()
        conn.close()
        if user:
            return {
                'user_id': user['username'],
                'name': user['name'],
                'role': user['role']
            }
    conn.close()
    return None

def delete_session(session_id):
    """删除会话"""
    conn = get_connection()
    conn.execute("DELETE FROM user_sessions WHERE session_id = ?", (session_id,))
    conn.commit()
    conn.close()


# ==================== 用户资料 ====================
