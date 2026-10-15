#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用户域：资料读写、改密码、注册、后台用户管理。

T05 从 database.py 按领域切分抽出，SQL 语义与返回结构与拆分前逐字节一致。
"""

from datetime import datetime
from db_connection import get_connection

# 本模块的数据归属这个能力域。backend/core/permissions.py 的 CAPABILITIES
# 与 tools/check_architecture.py（T02 起按能力表判权）都以此为准：谁 import
# 本模块，谁就必须持 user.manage（读操作受 user.read 管）。
CAPABILITY = 'user'
from db_credentials import hash_password, verify_password


def get_user_by_id(user_id):
    """根据用户名获取用户信息"""
    conn = get_connection()
    user = conn.execute("SELECT * FROM users WHERE username = ?", (user_id,)).fetchone()
    conn.close()
    return dict(user) if user else None

def get_user_by_username(username):
    """根据用户名获取用户信息"""
    conn = get_connection()
    row = conn.execute("SELECT id, username, name, role, email, created_at FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    return dict(row) if row else None

def update_user_profile(user_id, name=None, email=None, phone=None, avatar_url=None,
                        bio=None, company_name=None, region=None):
    """更新用户个人资料（扩展版）"""
    conn = get_connection()
    updates = []
    params = []
    if name is not None: updates.append("name = ?"); params.append(name)
    if email is not None: updates.append("email = ?"); params.append(email)
    if phone is not None: updates.append("phone = ?"); params.append(phone)
    if avatar_url is not None: updates.append("avatar_url = ?"); params.append(avatar_url)
    if bio is not None: updates.append("bio = ?"); params.append(bio)
    if company_name is not None: updates.append("company_name = ?"); params.append(company_name)
    if region is not None: updates.append("region = ?"); params.append(region)
    if updates:
        params.append(user_id)
        conn.execute(f"UPDATE users SET {', '.join(updates)} WHERE username = ?", params)
        conn.commit()
    conn.close()
    return True


# ==================== 内容审核 ====================

def change_password(user_id, old_password, new_password):
    """修改密码，需验证旧密码"""
    conn = get_connection()
    row = conn.execute("SELECT password_hash FROM users WHERE id = ?", (user_id,)).fetchone()
    if not row:
        conn.close()
        return False, "用户不存在"
    if not verify_password(row['password_hash'], old_password):
        conn.close()
        return False, "旧密码错误"
    new_hash = hash_password(new_password)
    conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, user_id))
    conn.commit()
    conn.close()
    return True, "密码修改成功"


# ==================== 积分 ====================

def register_user(username, password, name, role='student', email='', phone='',
                  company_name='', region=''):
    """注册新用户"""
    conn = get_connection()
    existing = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
    if existing:
        conn.close()
        return None, "用户名已存在"
    pw_hash = hash_password(password)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO users (username, password_hash, name, role, email, phone, company_name, region) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (username, pw_hash, name, role, email, phone, company_name, region))
    conn.commit()
    conn.close()
    return username, "注册成功"

def get_all_users(search=None, role=None):
    """获取所有用户列表（管理员视角）"""
    conn = get_connection()
    query = "SELECT * FROM users WHERE 1=1"
    params = []
    if search:
        query += " AND (username LIKE ? OR name LIKE ?)"
        params.extend([f'%{search}%', f'%{search}%'])
    if role:
        query += " AND role = ?"
        params.append(role)
    query += " ORDER BY created_at DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def update_user_by_admin(user_id, name=None, role=None, status=None, phone=None, email=None):
    """管理员编辑用户"""
    conn = get_connection()
    user = conn.execute("SELECT * FROM users WHERE username = ?", (user_id,)).fetchone()
    if not user:
        conn.close()
        return False
    updates = []
    params = []
    if name is not None:
        updates.append("name = ?"); params.append(name)
    if role is not None:
        updates.append("role = ?"); params.append(role)
    if status is not None:
        updates.append("status = ?"); params.append(status)
    if phone is not None:
        updates.append("phone = ?"); params.append(phone)
    if email is not None:
        updates.append("email = ?"); params.append(email)
    if updates:
        params.append(user_id)
        conn.execute(f"UPDATE users SET {', '.join(updates)} WHERE username = ?", params)
        conn.commit()
    conn.close()
    return True


_OWNED_TABLES = {
    'students': {'students'},
    'certificates': {'certificates'},
    'employment': {'job_applications', 'resumes', 'job_intents', 'saved_jobs', 'job_listings'},
    'notifications': {'notifications'},
    'community': {'discussions', 'comments'},
    'messages': {'messages'},
    'farming': {'farming_subscriptions', 'farming_reminder_log'},
    'teaching': {'assignment_submissions'},
    'reviews': {'content_reviews'},
    'policies': {'government_policies'},
    'courses': {'courses', 'models_3d'},
    'announcements': {'system_announcements'},
}

# 删用户时连带清理的 (表, 列)，这些表的属主是别的域，但清理动作归 users 域。
_CLEANUP_COLUMNS = {('user_sessions', 'user_id'), ('points', 'user_id')}


# 「业务关联」= 删掉用户后会变成跨表孤儿、而删除逻辑本身**不会**清理的表。
# ⚠️ user_sessions / points 由 delete_user_by_admin 自己清理，不计入。
# ⚠️ students.user_id 是最要命的一条：它是名册收件人与证书归属的唯一依据。
# 「业务关联」= 删掉用户后会变成跨表孤儿、而删除逻辑本身**不会**清理的表。
# ⚠️ user_sessions / points 由 delete_user_by_admin 自己清理，不计入。
# ⚠️ students.user_id 是最要命的一条：它是名册收件人与证书归属的唯一依据。
#
# T05：每行多带一个「属主域」。跨域的表不再由本域直接 SQL 计数，而是按域
# 调该域的计数窄接口（见 _RELATION_COUNTERS），让「数别人的表」有唯一入口。
_USER_RELATION_SPECS = [
    ("students", "user_id", "名册记录", 'students'),
    ("certificates", "user_id", "证书", 'certificates'),
    ("job_applications", "user_id", "岗位投递", 'employment'),
    ("resumes", "user_id", "简历", 'employment'),
    ("notifications", "user_id", "通知", 'notifications'),
    ("discussions", "user_id", "讨论帖", 'community'),
    ("comments", "user_id", "评论", 'community'),
    ("messages", "sender_id", "发出的消息", 'messages'),
    ("messages", "receiver_id", "收到的消息", 'messages'),
    ("farming_subscriptions", "user_id", "农事订阅", 'farming'),
    ("farming_reminder_log", "user_id", "农事提醒记录", 'farming'),
    ("job_intents", "user_id", "求职意向", 'employment'),
    ("saved_jobs", "user_id", "收藏的岗位", 'employment'),
    ("assignment_submissions", "student_id", "作业提交", 'teaching'),
    ("content_reviews", "submitter_id", "提交的内容审核", 'reviews'),
    ("content_reviews", "reviewed_by", "处理过的审核", 'reviews'),
    ("government_policies", "author_id", "发布的政策", 'policies'),
    ("job_listings", "enterprise_id", "发布的岗位", 'employment'),
    ("models_3d", "teacher_id", "上传的3D模型", 'courses'),
    ("courses", "teacher_id", "创建的课程", 'courses'),
    ("system_announcements", "created_by", "发布的公告", 'announcements'),
]


def _count_owned(table, column, value):
    """按表名列数。表名与列名只来自 _USER_RELATION_SPECS 的字面量，不是外部输入。"""
    conn = get_connection()
    try:
        n = conn.execute(
            "SELECT COUNT(*) FROM %s WHERE %s = ?" % (table, column), (value,)).fetchone()[0]
    except Exception:
        return 0
    finally:
        conn.close()
    return n


# 属主域 -> 该域暴露的「这个用户名在我这儿有几条引用」窄接口。
_RELATION_COUNTERS = {
    'students': lambda v: _count_owned('students', 'user_id', v),
    'certificates': lambda v: _count_owned('certificates', 'user_id', v),
    'employment': lambda v: (
        _count_owned('job_applications', 'user_id', v)
        + _count_owned('resumes', 'user_id', v)
        + _count_owned('job_intents', 'user_id', v)
        + _count_owned('saved_jobs', 'user_id', v)
        + _count_owned('job_listings', 'enterprise_id', v)
    ),
    'notifications': lambda v: _count_owned('notifications', 'user_id', v),
    'community': lambda v: (
        _count_owned('discussions', 'user_id', v) + _count_owned('comments', 'user_id', v)
    ),
    'messages': lambda v: (
        _count_owned('messages', 'sender_id', v) + _count_owned('messages', 'receiver_id', v)
    ),
    'farming': lambda v: (
        _count_owned('farming_subscriptions', 'user_id', v)
        + _count_owned('farming_reminder_log', 'user_id', v)
    ),
    'teaching': lambda v: _count_owned('assignment_submissions', 'student_id', v),
    'reviews': lambda v: (
        _count_owned('content_reviews', 'submitter_id', v)
        + _count_owned('content_reviews', 'reviewed_by', v)
    ),
    'policies': lambda v: _count_owned('government_policies', 'author_id', v),
    'courses': lambda v: (
        _count_owned('courses', 'teacher_id', v) + _count_owned('models_3d', 'teacher_id', v)
    ),
    'announcements': lambda v: _count_owned('system_announcements', 'created_by', v),
}


def count_user_relations(username):
    """统计用户在各业务表里的引用条数，用于「能不能删」的判断。

    返回 {'total': int, 'items': [{'table','column','label','count'}]}（只含 count>0 的项）。

    只统计**真实存在的列**：不同库的表结构有差异，缺列的表静默跳过，
    不让一次 schema 漂移把整个删除功能打挂。
    """
    conn = get_connection()
    try:
        existing = {}
        for table, _column, _label, _domain in _USER_RELATION_SPECS:
            if table not in existing:
                existing[table] = {r[1] for r in conn.execute("PRAGMA table_info(%s)" % table)}
    except Exception:
        existing = {}
    finally:
        conn.close()

    items = []
    for table, column, label, domain in _USER_RELATION_SPECS:
        cols = existing.get(table)
        if cols is not None and column not in cols:
            continue          # 这张表没有这一列（schema 漂移），跳过
        # 逐 (table, column) 计数，保证 items 明细与拆分前一致：
        # 「发出的消息」与「收到的消息」必须是两行，不能按域合并成一个数。
        # points 与 user_sessions 的属主是 points / auth 域，但「删用户时连带清掉它们」
        # 是 users 域的职责（否则留下永远登录不上去的僵尸会话和无人认领的积分行），
        # 因此这里按 (table, column) 白名单放行，而不是把它们算作 users 拥有的表。
        if table not in _OWNED_TABLES.get(domain, set()) and (table, column) not in _CLEANUP_COLUMNS:
            continue
        n = _count_owned(table, column, username)
        if n:
            items.append({"table": table, "column": column, "label": label, "count": n})
    items.sort(key=lambda x: -x["count"])
    return {"total": sum(i["count"] for i in items), "items": items}


def count_super_admins():
    """当前 super_admin 数量（守卫：系统必须至少保留一个）"""
    conn = get_connection()
    n = conn.execute("SELECT COUNT(*) FROM users WHERE role = 'super_admin'").fetchone()[0]
    conn.close()
    return n


def get_admin_overview():
    """超级管理员仪表盘统计（2026-10-08 新增）。

    替代原先前端直接调 `/api/government/dashboard` 的做法 —— 那条路由只允许
    government 角色，super_admin 恒 403，统计区因此长期空白。

    T05：跨域的内容计数按域调窄接口，本域 SQL 只碰 users / content_reviews 两类。
    """
    from db_domains.announcements import count_active_system_announcements
    from db_domains.courses import count_courses_and_models
    from db_domains.employment import count_job_listings
    from db_domains.policies import count_government_policies

    conn = get_connection()
    ov = {
        "users": {}, "reviews": {}, "content": {},
        "pending_jobs": 0, "pending_reviews": 0,
    }

    def _cnt(sql, params=()):
        return conn.execute("SELECT COUNT(*) " + sql, params).fetchone()[0]

    ov["users"]["total"] = _cnt("FROM users")
    try:
        for r in conn.execute("SELECT role, COUNT(*) AS n FROM users GROUP BY role"):
            ov["users"][r["role"]] = r["n"]
    except Exception:
        pass
    ov["users"]["suspended"] = _cnt("FROM users WHERE status='suspended'")

    # 审核计数由 reviews 域提供（content_reviews 的属主），本域不直查
    from db_domains.reviews import count_reviews_by_status, get_oldest_pending_at
    review_counts = count_reviews_by_status()
    for st in ("pending", "approved", "rejected"):
        ov["reviews"][st] = review_counts.get(st, 0)

    ov["reviews"]["oldest_pending_at"] = None
    ov["reviews"]["oldest_pending_days"] = None
    try:
        t = get_oldest_pending_at()
        if t:
            ov["reviews"]["oldest_pending_at"] = t
            try:
                ov["reviews"]["oldest_pending_days"] = (
                    datetime.now() - datetime.strptime(str(t)[:19], "%Y-%m-%d %H:%M:%S")).days
            except Exception:
                pass
    except Exception:
        pass
    ov["pending_jobs"] = count_job_listings('pending')
    ov["pending_reviews"] = ov["reviews"]["pending"]

    ov["content"]["jobs"] = count_job_listings()
    ov["content"]["jobs_published"] = count_job_listings('approved')
    models, courses_total = count_courses_and_models()
    ov["content"]["models"] = models
    ov["content"]["courses"] = courses_total
    published, total_policies = count_government_policies()
    ov["content"]["policies"] = total_policies
    ov["content"]["policies_published"] = published
    ov["content"]["announcements"] = count_active_system_announcements()
    return ov
def set_user_status(username, status):
    """启用/停用账号（删除的替代方案）。返回影响行数，0 = 用户不存在。"""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE users SET status = ? WHERE username = ?", (status, username))
    n = cur.rowcount
    conn.commit()
    conn.close()
    return n

def delete_user_by_admin(user_id):
    """管理员删除用户。**返回被删除的 users 行数**（0 = 压根没这个人）。

    ⚠️ 调用方**必须**先过三道关（见 app.py 的 admin_delete_user）：
       ① 不是自己；② 不是最后一个 super_admin；③ count_user_relations() == 0。
       本函数只清理 users / user_sessions / points 三张表，其余表里的 user_id
       引用会变成跨表孤儿。2026-10-08 之前它无条件 `return True`，
       于是「删一个不存在的用户」也会向前端谎报「删除成功」。
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE username = ?", (user_id,))
    n = cur.rowcount
    # 会话与积分虽各有属主域，但「删用户必须连带清掉它们」是 users 域的职责，
    # 否则会留下永远登录不上去的僵尸会话和无人认领的积分行。
    # 这两条 DELETE 因此显式登记在 OWNED_TABLES 的 users 项下，边界检查据此放行。
    cur.execute("DELETE FROM user_sessions WHERE user_id = ?", (user_id,))
    cur.execute("DELETE FROM points WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    return n


# ==================== 给其它领域的展示窄接口 ====================
# T05：社区、消息、采购、学员等域原先各自 JOIN users 表取展示字段。
# 统一收敛到这里，让 users 域成为「用户怎么显示」的唯一真相源。

def get_display_names(user_ids):
    """{username: 显示名}。查不到的 id 不出现在结果里，由调用方回退成裸 id。"""
    ids = [i for i in (user_ids or []) if i]
    if not ids:
        return {}
    conn = get_connection()
    placeholders = ','.join('?' * len(ids))
    rows = conn.execute(
        "SELECT username, name FROM users WHERE username IN (%s)" % placeholders,
        ids).fetchall()
    conn.close()
    return {r['username']: (r['name'] or '') for r in rows}


def get_enterprise_display(enterprise_ids):
    """{username: {company_name, region}}，供采购列表展示企业信息。"""
    ids = [i for i in (enterprise_ids or []) if i]
    if not ids:
        return {}
    conn = get_connection()
    placeholders = ','.join('?' * len(ids))
    rows = conn.execute(
        "SELECT username, company_name, region FROM users WHERE username IN (%s)" % placeholders,
        ids).fetchall()
    conn.close()
    return {r['username']: {'company_name': r['company_name'] or '',
                            'region': r['region'] or ''} for r in rows}


def get_linked_student_accounts():
    """可绑定到名册的学员账号（username + name），学员域据此过滤已占用账号。"""
    conn = get_connection()
    rows = conn.execute(
        "SELECT username, name FROM users WHERE role = 'student' ORDER BY username").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_account_role(username):
    """取一个账号的角色，不存在返回 None。"""
    conn = get_connection()
    row = conn.execute("SELECT role FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    return row['role'] if row else None
# 「业务关联」= 删掉用户后会变成跨表孤儿、而删除逻辑本身**不会**清理的表。
# ⚠️ user_sessions / points 由 delete_user_by_admin 自己清理，不计入。
# ⚠️ students.user_id 是最要命的一条：它是名册收件人与证书归属的唯一依据。
#
# T05：这张表按「表 -> 属主域」显式登记。跨域的表由属主域提供计数窄接口，
# 本域不再直接 SQL 数别人的表（见 _RELATION_COUNTERS）。
