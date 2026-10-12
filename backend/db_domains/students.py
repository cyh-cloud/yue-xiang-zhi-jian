#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""学员域：名册的增删改查与账号绑定。

T05 从 database.py 按领域切分抽出，SQL 语义与返回结构与拆分前逐字节一致。
"""

from db_connection import get_connection


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

    ⚠️ 名册行与平台账号是**两套数据**：不传 user_id 就只是一行名册记录，
       该学员无法登录、收不到通知、其证书也不会进入教师端统计。
       调用方（app.add_student）负责在需要时关联/创建账号。
    """
    conn = get_connection()
    # 生成ID
    last = conn.execute("SELECT id FROM students ORDER BY id DESC LIMIT 1").fetchone()
    if last:
        num = int(last['id'].replace('STU', '')) + 1
    else:
        num = 1
    sid = f"STU{num:03d}"
    conn.execute("INSERT INTO students (id, user_id, name, class_name, direction, progress, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
                 (sid, user_id or '', name, class_name, direction, 0, 'active'))
    conn.commit()
    conn.close()
    return sid

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
        if role != 'student':
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
