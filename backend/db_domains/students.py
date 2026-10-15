#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""学员域：名册的增删改查与账号绑定。

T05 从 database.py 按领域切分抽出，SQL 语义与返回结构与拆分前逐字节一致。
"""

import sqlite3

from db_connection import get_connection

# 角色判定走共享层能力表（core.permissions），数据层不出现角色字面量
from core.permissions import is_student

# 本模块的数据归属这个能力域。backend/core/permissions.py 的 CAPABILITIES
# 与 tools/check_architecture.py（T02 起按能力表判权）都以此为准：谁 import
# 本模块，谁就必须持 student.manage（读操作受 student.read 管）。
CAPABILITY = 'student'


def _next_student_id(conn):
    """算出下一个可用学号：当前最大号 +1，撞了已占用的号就继续往后顺延。

    students.id 是 TEXT 主键，所以「最大号」必须按数值比：字符串序下 STU1000
    小于 STU999，直接 ORDER BY id DESC LIMIT 1 会把号取小，也会取到已存在的号。
    """
    row = conn.execute(
        "SELECT MAX(CAST(SUBSTR(id, 4) AS INTEGER)) FROM students "
        "WHERE id GLOB 'STU[0-9]*'").fetchone()
    num = (row[0] if row and row[0] is not None else 0) + 1
    sid = f"STU{num:03d}"
    # 取到的号可能已被占用（手工插入的号、历史脏数据、删行后跳号…）。逐个顺延
    # 到第一个空号；取号与插入之间被别人插走的极端情况由上层重试兜底。
    while conn.execute("SELECT 1 FROM students WHERE id = ?", (sid,)).fetchone():
        num += 1
        sid = f"STU{num:03d}"
    return sid


def get_students(search=None):
    """获取学员列表（按学号稳定排序）。

    ⚠️ 必须 ORDER BY：名册行的 rowid 会因删除/重建而变化，不加排序时
    教师端列表的展示顺序会「看起来随机」。
    """
    conn = get_connection()
    if search:
        rows = conn.execute("SELECT * FROM students WHERE name LIKE ? OR id LIKE ? OR direction LIKE ? "
                            "ORDER BY id",
                            (f'%{search}%', f'%{search}%', f'%{search}%')).fetchall()
    else:
        rows = conn.execute("SELECT * FROM students ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_student(student_id):
    """获取单个学员"""
    conn = get_connection()
    row = conn.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def add_student(name, class_name, direction, user_id=''):
    """添加学员（只写名册行）。

    ⚠️ 需要真事务（见 db_domains/points.py 的 TRANSACTION_CRITICAL 名单）：
       先查最大学号再插入，两步之间不得插入任何不相关语句。

    ⚠️ 名册行与平台账号是**两套数据**：不传 user_id 就只是一行名册记录，
       该学员无法登录、收不到通知、其证书也不会进入教师端统计。
       调用方（app.add_student）负责在需要时关联/创建账号。

    ⚠️ 学号生成是「取最大号 → 查重顺延 → 插入」，撞了主键就重取。原先的写法是
       `SELECT id ... ORDER BY id DESC LIMIT 1` 再 +1：字符串序下 STU1000 小于
       STU999，号会取小；两个并发请求还会算出同一个号，后写入的撞 students.id
       主键，IntegrityError 冒到前端就是 500。
    """
    for _ in range(5):
        conn = get_connection()
        try:
            sid = _next_student_id(conn)
            conn.execute("INSERT INTO students (id, user_id, name, class_name, direction, progress, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
                         (sid, user_id or '', name, class_name, direction, 0, 'active'))
            conn.commit()
            return sid
        except sqlite3.IntegrityError:
            # 号在取号之后、插入之前被别人占走了，重取一次
            conn.rollback()
        finally:
            conn.close()
    raise RuntimeError('学号生成失败：并发写入过多，请重试')

def get_roster_name_for(user_id):
    """学员域窄接口：单个账号在名册上的姓名，没有关联名册行返回 None。

    教学支撑域给实训提交记录带出人名时用（username 不好认人）。
    """
    if not user_id:
        return None
    conn = get_connection()
    row = conn.execute(
        "SELECT name FROM students WHERE user_id = ? AND user_id != '' LIMIT 1",
        (user_id,)).fetchone()
    conn.close()
    return row['name'] if row else None


def get_roster_rows_for_completion():
    """学员域窄接口：名册行的 id / 姓名 / 方向 / 账号 / 状态，供完成度统计拼装。"""
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, name, direction, user_id, status FROM students ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_linked_student_user_ids():
    """学员域窄接口：名册中已关联平台账号的 user_id 列表（username 语义）。

    通知域群发时据此取收件人，不再自己读 students 表。
    """
    conn = get_connection()
    rows = conn.execute(
        "SELECT user_id FROM students WHERE user_id IS NOT NULL AND user_id != ''").fetchall()
    conn.close()
    return [r['user_id'] for r in rows]


def get_roster_names_by_user_id(user_ids):
    """学员域的名字窄接口：{user_id: 名册上的姓名}。

    消息域解析会话对方显示名时用，优先级高于账号表的 name。
    一个账号只会关联一行名册，故同名列取第一条。
    """
    ids = [i for i in (user_ids or []) if i]
    if not ids:
        return {}
    conn = get_connection()
    placeholders = ','.join('?' * len(ids))
    rows = conn.execute(
        "SELECT user_id, name FROM students WHERE user_id IN (%s)" % placeholders,
        ids).fetchall()
    conn.close()
    return {r['user_id']: (r['name'] or '') for r in rows if r['name']}


def get_linkable_student_accounts():
    """可被名册关联的学员账号：role='student' 且尚未被任何名册行占用。

    已被占用的账号不出现，避免一个账号挂到两个学员上（统计会串）。

    T05：账号清单与占用情况分别向 users 域与本域取，再在内存里求差集，
    不再跨域 JOIN。
    """
    conn = get_connection()
    taken = {r['user_id'] for r in conn.execute(
        "SELECT user_id FROM students WHERE user_id IS NOT NULL AND user_id != ''").fetchall()}
    conn.close()
    from db_domains.users import get_linked_student_accounts
    return [a for a in get_linked_student_accounts() if a['username'] not in taken]

def set_student_account(student_id, username):
    """把名册行关联到平台账号；username 为空串 = 解除关联。

    返回 (是否成功, 提示语)。所有校验都在这里做，调用方不必重复判断。
    """
    conn = get_connection()
    row = conn.execute("SELECT id FROM students WHERE id = ?", (student_id,)).fetchone()
    if not row:
        conn.close()
        return False, '未找到学员'
    if username:
        conn.close()
        from db_domains.users import get_account_role
        role = get_account_role(username)
        if role is None:
            return False, f'账号 {username} 不存在'
        if not is_student(role):
            return False, f'账号 {username} 不是学员角色，不能关联'
        conn = get_connection()
        other = conn.execute("SELECT id FROM students WHERE user_id = ? AND id <> ?",
                             (username, student_id)).fetchone()
        if other:
            conn.close()
            return False, f'该账号已关联到名册 {other["id"]}，请先解除'
    conn.execute("UPDATE students SET user_id = ? WHERE id = ?", (username or '', student_id))
    conn.commit()
    conn.close()
    return True, (f'已关联账号 {username}' if username else '已解除账号关联')

def update_student(student_id, name=None, class_name=None, direction=None, progress=None, status=None):
    """编辑学员信息"""
    conn = get_connection()
    student = conn.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
    if not student:
        conn.close()
        return False
    updates = []
    params = []
    if name is not None:
        updates.append("name = ?")
        params.append(name)
    if class_name is not None:
        updates.append("class_name = ?")
        params.append(class_name)
    if direction is not None:
        updates.append("direction = ?")
        params.append(direction)
    if progress is not None:
        updates.append("progress = ?")
        params.append(int(progress))
    if status is not None:
        updates.append("status = ?")
        params.append(status)
    if updates:
        params.append(student_id)
        conn.execute(f"UPDATE students SET {', '.join(updates)} WHERE id = ?", params)
        conn.commit()
    conn.close()
    return True

def delete_student(student_id):
    """删除学员"""
    conn = get_connection()
    result = conn.execute("DELETE FROM students WHERE id = ?", (student_id,))
    conn.commit()
    deleted = result.rowcount > 0
    conn.close()
    return deleted


# ==================== 通知公告 ====================
