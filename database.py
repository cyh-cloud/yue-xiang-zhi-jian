#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
粤乡智匠 - SQLite数据库层
"""

import sqlite3
import hashlib
import uuid
import time
import json
import os
import re
import sys
from datetime import datetime

# Vercel 环境使用 /tmp（可写但非持久），本地环境使用 data/ 目录
if os.environ.get('VERCEL') or os.environ.get('VERCEL_ENV'):
    DB_DIR = '/tmp'
else:
    DB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
DB_PATH = os.path.join(DB_DIR, 'yuexiang.db')


def get_connection():
    """获取数据库连接"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=8000")  # 并发写入时最多等 8s，避免瞬时 "database is locked"
    return conn


def hash_password(password, salt=None):
    """哈希密码"""
    if salt is None:
        salt = uuid.uuid4().hex
    hashed = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"{salt}${hashed}"


def verify_password(stored, password):
    """验证密码"""
    salt, hashed = stored.split('$', 1)
    return hash_password(password, salt) == stored


def init_db():
    """初始化数据库：建表 + 填充种子数据"""
    conn = get_connection()
    cursor = conn.cursor()

    # 建表
    cursor.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            name TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'student',
            email TEXT DEFAULT '',
            phone TEXT DEFAULT '',
            avatar_url TEXT DEFAULT '',
            bio TEXT DEFAULT '',
            company_name TEXT DEFAULT '',
            region TEXT DEFAULT '',
            status TEXT DEFAULT 'active',
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS content_reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content_type TEXT NOT NULL,
            content_id INTEGER NOT NULL,
            submitter_id TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            review_comment TEXT DEFAULT '',
            reviewed_by TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now','localtime')),
            reviewed_at TEXT DEFAULT NULL
        );

        CREATE TABLE IF NOT EXISTS user_sessions (
            session_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            login_time REAL NOT NULL,
            expires_at REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS points (
            user_id TEXT PRIMARY KEY,
            balance INTEGER DEFAULT 0,
            history TEXT DEFAULT '[]'
        );

        CREATE TABLE IF NOT EXISTS certificates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            name TEXT NOT NULL,
            status TEXT DEFAULT 'locked',
            progress INTEGER DEFAULT 0,
            date TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS students (
            id TEXT PRIMARY KEY,
            user_id TEXT DEFAULT '',
            name TEXT NOT NULL,
            class_name TEXT DEFAULT '',
            direction TEXT DEFAULT '',
            progress INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active',
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS announcements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            category TEXT DEFAULT '通知',
            pinned INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            direction TEXT DEFAULT '',
            deadline TEXT DEFAULT '',
            total_score INTEGER DEFAULT 100,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS assignment_submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assignment_id INTEGER NOT NULL,
            student_id TEXT NOT NULL,
            content TEXT DEFAULT '',
            score INTEGER DEFAULT NULL,
            feedback TEXT DEFAULT '',
            status TEXT DEFAULT 'pending',
            submitted_at TEXT DEFAULT (datetime('now','localtime')),
            graded_at TEXT DEFAULT NULL,
            UNIQUE(assignment_id, student_id)
        );

        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id TEXT NOT NULL,
            receiver_id TEXT NOT NULL,
            content TEXT NOT NULL,
            is_read INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            type TEXT DEFAULT 'system',
            title TEXT NOT NULL,
            content TEXT DEFAULT '',
            is_read INTEGER DEFAULT 0,
            link_type TEXT DEFAULT '',
            link_id INTEGER DEFAULT NULL,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );

        -- 已读状态旁路表：给**自身没有已读字段**的通知来源补按用户的已读记录。
        -- notifications / messages 两张表自带 is_read，不需要进这里；
        -- system_announcements 是全局公告（不能往共享表上加按用户的列），
        -- job_applications 的表语义是「投递记录」而非「消息」，也不该塞已读列。
        -- 没有这张表，「全部已读 / 未读筛选 / 点击归档」就只能覆盖 4 个数据源里的 2 个。
        CREATE TABLE IF NOT EXISTS notification_reads (
            user_id TEXT NOT NULL,
            source  TEXT NOT NULL,
            ref_id  TEXT NOT NULL,
            read_at TEXT DEFAULT (datetime('now','localtime')),
            PRIMARY KEY (user_id, source, ref_id)
         );

        CREATE TABLE IF NOT EXISTS job_applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            job_id INTEGER NOT NULL,
            status TEXT DEFAULT 'pending',
            applied_at TEXT DEFAULT (datetime('now','localtime'))
        );

        -- 注：success_cases 表已废弃。成功案例内容统一由 cases_data.py 提供（唯一事实源），
        -- 不再落库，避免"改种子数据但旧库不刷新"以及编造数据残留两类问题。

        CREATE TABLE IF NOT EXISTS policies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            category TEXT DEFAULT 'general',
            date TEXT DEFAULT '',
            summary TEXT DEFAULT '',
            source TEXT DEFAULT ''
        );

        -- 通用"内容签名"元数据表（预置内容变更后自动重灌，见 _refresh_policies / _seed_farming）
        CREATE TABLE IF NOT EXISTS seed_meta (
            key        TEXT PRIMARY KEY,
            value      TEXT NOT NULL,
            updated_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS job_listings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            company TEXT NOT NULL,
            salary TEXT DEFAULT '',
            requirements TEXT DEFAULT '[]',
            description TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS saved_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            job_id INTEGER NOT NULL,
            saved_at TEXT DEFAULT (datetime('now','localtime')),
            UNIQUE(user_id, job_id)
        );

        -- 在线简历：一人一份（user_id 唯一）。事实来源 = 学员自填 + 平台真实学习数据，
        -- AI 只做「组织与表达」，不得生成平台没有的事实（详见 app.py 的简历生成接口）。
        CREATE TABLE IF NOT EXISTS resumes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT UNIQUE NOT NULL,
            title TEXT DEFAULT '',            -- 求职意向岗位
            region TEXT DEFAULT '',           -- 期望工作地区
            education TEXT DEFAULT '',        -- 学历（学员自填）
            work_years TEXT DEFAULT '',       -- 工作/实践年限（学员自填）
            phone TEXT DEFAULT '',
            email TEXT DEFAULT '',
            self_eval TEXT DEFAULT '',        -- 自我评价（AI 可起草）
            skills TEXT DEFAULT '',           -- 专业技能（AI 可起草）
            experience TEXT DEFAULT '[]',     -- 工作/实践经历 JSON 数组（学员自填，AI 可润色单条描述）
            ai_used INTEGER DEFAULT 0,        -- 是否使用过 AI 辅助（前端如实标注）
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime'))
        );

        -- 公开招聘公告的「求职意向登记」。
        -- ⚠️ 平台**不是**官方报名系统：这里只记录学员的意向与准备情况，
        --    报名一律由学员按公告原文自行完成（recruit_key 是 jobs_data.py 里的字符串 key）。
        CREATE TABLE IF NOT EXISTS job_intents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            recruit_key TEXT NOT NULL,
            note TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now','localtime')),
            UNIQUE(user_id, recruit_key)
        );

        CREATE TABLE IF NOT EXISTS carousels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            image_url TEXT NOT NULL,
            link_url TEXT DEFAULT '',
            sort_order INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS system_announcements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            is_pinned INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_by TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            category TEXT DEFAULT '',
            teacher_id TEXT NOT NULL,
            cover_url TEXT DEFAULT '',
            review_status TEXT DEFAULT 'pending',
            is_published INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS course_materials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER NOT NULL,
            material_type TEXT NOT NULL,
            file_name TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_size INTEGER DEFAULT 0,
            sort_order INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS models_3d (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            craft_type TEXT DEFAULT '',
            file_path TEXT NOT NULL,
            file_name TEXT NOT NULL,
            file_size INTEGER DEFAULT 0,
            thumbnail_url TEXT DEFAULT '',
            teacher_id TEXT NOT NULL,
            review_status TEXT DEFAULT 'pending',
            is_published INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_type TEXT NOT NULL,
            target_id INTEGER NOT NULL,
            user_id TEXT NOT NULL,
            content TEXT NOT NULL,
            is_deleted INTEGER DEFAULT 0,
            deleted_by TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS discussions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            category TEXT DEFAULT 'general',
            user_id TEXT NOT NULL,
            is_pinned INTEGER DEFAULT 0,
            is_deleted INTEGER DEFAULT 0,
            view_count INTEGER DEFAULT 0,
            comment_count INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS procurements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_name TEXT NOT NULL,
            specification TEXT DEFAULT '',
            quantity TEXT DEFAULT '',
            price_range TEXT DEFAULT '',
            delivery_location TEXT DEFAULT '',
            deadline TEXT DEFAULT '',
            contact_info TEXT DEFAULT '',
            description TEXT DEFAULT '',
            enterprise_id TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            review_status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS news_articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            category TEXT DEFAULT 'news',
            author_id TEXT NOT NULL,
            is_published INTEGER DEFAULT 1,
            view_count INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS government_policies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            category TEXT DEFAULT 'general',
            author_id TEXT NOT NULL,
            is_published INTEGER DEFAULT 1,
            date TEXT DEFAULT '',
            summary TEXT DEFAULT '',
            source TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime'))
        );

        -- ==================== 农时智能日历（v2 重构） ====================
        -- ① 农产品目录
        CREATE TABLE IF NOT EXISTS farming_products (
            id          TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            icon        TEXT DEFAULT 'seedling',
            summary     TEXT DEFAULT '',
            region      TEXT DEFAULT '广东',
            sort_order  INTEGER DEFAULT 0,
            is_active   INTEGER DEFAULT 1,
            created_at  TEXT DEFAULT (datetime('now','localtime'))
        );

        -- ② 物候期（月粒度，支持跨年区间）
        CREATE TABLE IF NOT EXISTS farming_phenophases (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id  TEXT NOT NULL,
            name        TEXT NOT NULL,
            start_month INTEGER NOT NULL,
            end_month   INTEGER NOT NULL,
            color       TEXT DEFAULT '#1f5e43',
            description TEXT DEFAULT '',
            sort_order  INTEGER DEFAULT 0,
            FOREIGN KEY (product_id) REFERENCES farming_products(id) ON DELETE CASCADE
        );

        -- ③ 农事任务（年周期模板：task_md 为 MM-DD，逐年复现）
        CREATE TABLE IF NOT EXISTS farming_tasks (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id  TEXT NOT NULL,
            phase_id    INTEGER,
            title       TEXT NOT NULL,
            category    TEXT NOT NULL,
            priority    TEXT DEFAULT 'medium',
            task_md     TEXT,
            month       INTEGER NOT NULL,
            icon        TEXT DEFAULT 'tasks',
            description TEXT DEFAULT '',
            tip         TEXT DEFAULT '',
            -- source_key: 指向 farming_sources.key，登记该条日期所依据的技术资料方向
            -- date_basis: 该日期成立的农艺逻辑（供农技人员复核、供用户理解为什么是这个时间）
            source_key  TEXT DEFAULT '',
            date_basis  TEXT DEFAULT '',
            -- is_verified: 该条 task_md 日期是否已由农技人员复核确认。
            --   0 = 按农时规律推算的参考日期（前端显示「约」并挂全局提示条）
            --   1 = 已人工复核，可视作权威日期
            is_verified INTEGER DEFAULT 0,
            is_active   INTEGER DEFAULT 1,
            sort_order  INTEGER DEFAULT 0,
            FOREIGN KEY (product_id) REFERENCES farming_products(id) ON DELETE CASCADE,
            FOREIGN KEY (phase_id)   REFERENCES farming_phenophases(id) ON DELETE SET NULL
        );

        -- ④ 订阅关系（user_id 存 username，与项目既有约定一致）
        CREATE TABLE IF NOT EXISTS farming_subscriptions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     TEXT NOT NULL,
            product_id  TEXT NOT NULL,
            created_at  TEXT DEFAULT (datetime('now','localtime')),
            UNIQUE(user_id, product_id)
        );

        -- ⑤ 提醒发送日志（登录时补发的判重依据）
        CREATE TABLE IF NOT EXISTS farming_reminder_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     TEXT NOT NULL,
            product_id  TEXT NOT NULL,
            period      TEXT NOT NULL,
            sent_at     TEXT DEFAULT (datetime('now','localtime')),
            UNIQUE(user_id, product_id, period)
        );

        -- ⑥ 种子数据元信息（内容签名，用于判断是否需要重灌种植日历数据）
        --    仅比行数无法发现"条数不变但内容变了"（如 task_md 补日期），故改用内容签名
        CREATE TABLE IF NOT EXISTS farming_seed_meta (
            key         TEXT PRIMARY KEY,
            value       TEXT NOT NULL,
            updated_at  TEXT DEFAULT (datetime('now','localtime'))
        );

        -- ⑦ 数据来源登记表（来源方向 = 机构 + 文件类型）
        --    doc_no 一律先落「待核」：具体标准号/文号须由农技人员核实后补填，
        --    代码侧不得凭空编造标准号，故本表只做"来源方向"登记。
        CREATE TABLE IF NOT EXISTS farming_sources (
            key         TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            org         TEXT DEFAULT '',
            doc_type    TEXT DEFAULT '',
            doc_no      TEXT DEFAULT '',
            url         TEXT DEFAULT '',
            sort_order  INTEGER DEFAULT 0
        );

        CREATE INDEX IF NOT EXISTS idx_farming_tasks_month    ON farming_tasks(product_id, month);
        CREATE INDEX IF NOT EXISTS idx_farming_tasks_md       ON farming_tasks(product_id, task_md);
        CREATE INDEX IF NOT EXISTS idx_farming_phases_product ON farming_phenophases(product_id);
        CREATE INDEX IF NOT EXISTS idx_farming_subs_user      ON farming_subscriptions(user_id);
        CREATE INDEX IF NOT EXISTS idx_farming_log_lookup     ON farming_reminder_log(user_id, product_id, period);
    ''')

    # 扩展 users 表结构（兼容已有数据库）
    user_cols = {row[1] for row in cursor.execute("PRAGMA table_info(users)").fetchall()}
    user_new_cols = {
        'phone': "TEXT DEFAULT ''",
        'avatar_url': "TEXT DEFAULT ''",
        'bio': "TEXT DEFAULT ''",
        'company_name': "TEXT DEFAULT ''",
        'region': "TEXT DEFAULT ''",
        'status': "TEXT DEFAULT 'active'",
    }
    for col, typedef in user_new_cols.items():
        if col not in user_cols:
            cursor.execute(f"ALTER TABLE users ADD COLUMN {col} {typedef}")

    # 扩展 job_listings 表结构
    existing_cols = {row[1] for row in cursor.execute("PRAGMA table_info(job_listings)").fetchall()}
    job_new_cols = {
        'location': "TEXT DEFAULT ''",
        'category': "TEXT DEFAULT ''",
        'job_type': "TEXT DEFAULT '全职'",
        'education': "TEXT DEFAULT ''",
        'experience': "TEXT DEFAULT ''",
        'company_size': "TEXT DEFAULT ''",
        'industry': "TEXT DEFAULT ''",
        'company_logo': "TEXT DEFAULT ''",
        'posted_at': "TEXT DEFAULT ''",
        'enterprise_id': "TEXT DEFAULT ''",
        'review_status': "TEXT DEFAULT 'approved'",
        # 演示岗位标记：1 = 平台预置的演示岗位（前端必须打「演示数据」角标）。
        # 与真实企业发布岗位严格区分，便于一键识别与清理。
        'is_demo': "INTEGER DEFAULT 0",
    }
    for col, typedef in job_new_cols.items():
        if col not in existing_cols:
            cursor.execute(f"ALTER TABLE job_listings ADD COLUMN {col} {typedef}")

    # 扩展 farming_tasks 表结构（兼容既有数据库：CREATE TABLE IF NOT EXISTS 不会补列）
    farming_cols = {row[1] for row in cursor.execute("PRAGMA table_info(farming_tasks)").fetchall()}
    farming_new_cols = {
        'is_verified': "INTEGER DEFAULT 0",
        'source_key':  "TEXT DEFAULT ''",
        'date_basis':  "TEXT DEFAULT ''",
    }
    for col, typedef in farming_new_cols.items():
        if farming_cols and col not in farming_cols:
            cursor.execute("ALTER TABLE farming_tasks ADD COLUMN %s %s" % (col, typedef))

    # 扩展 policies / government_policies：新增 source 列（存"来源列表"JSON，供前端展示出处）
    for _tbl in ('policies', 'government_policies'):
        _cols = {row[1] for row in cursor.execute("PRAGMA table_info(%s)" % _tbl).fetchall()}
        if _cols and 'source' not in _cols:
            cursor.execute("ALTER TABLE %s ADD COLUMN source TEXT DEFAULT ''" % _tbl)
        if _cols and 'summary' not in _cols:
            cursor.execute("ALTER TABLE %s ADD COLUMN summary TEXT DEFAULT ''" % _tbl)
        if _cols and 'date' not in _cols:
            cursor.execute("ALTER TABLE %s ADD COLUMN date TEXT DEFAULT ''" % _tbl)

    # 检查是否已有种子数据
    count = cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if count == 0:
        _seed_data(cursor)
    else:
        # 已有数据时，刷新政策内容（保证政策详情是最新的）
        _refresh_policies(cursor)
        # 一次性清理历史遗留的"演示岗位"。
        # 旧版在 job_listings 里预置了 30 条**编造**岗位（假公司名/假薪资），
        # 现架构已改为：公开招聘信息走 jobs_data.py（策展、带来源），企业岗位走企业端发布+审核。
        # 这些演示行会冒充"真实在招职位"（学员可申请、还留真实姓名电话），必须移除。
        # 判定依据：企业端发布的行 enterprise_id 恒为**非空**的用户名，
        # 只有旧预置行是空串 —— 该条件精确命中预置行，不会误删企业数据。
        demo_ids = [r[0] for r in cursor.execute(
            "SELECT id FROM job_listings WHERE enterprise_id IS NULL OR enterprise_id = ''").fetchall()]
        if demo_ids:
            _qm = ','.join('?' * len(demo_ids))
            cursor.execute("DELETE FROM job_applications WHERE job_id IN (%s)" % _qm, demo_ids)
            cursor.execute("DELETE FROM saved_jobs WHERE job_id IN (%s)" % _qm, demo_ids)
            cursor.execute("DELETE FROM job_listings WHERE id IN (%s)" % _qm, demo_ids)
        # 如果政府政策表为空，填充初始数据
        gp_count = cursor.execute("SELECT COUNT(*) FROM government_policies").fetchone()[0]
        if gp_count == 0:
            _seed_government_policies(cursor)
        # 如果轮播图为空，填充默认数据
        car_count = cursor.execute("SELECT COUNT(*) FROM carousels").fetchone()[0]
        if car_count == 0:
            _seed_carousels(cursor)
        # 如果缺少新角色演示账户，补充创建
        _ensure_demo_accounts(cursor)

    # 农时日历种子数据（幂等，两个分支都需保证存在）
    _seed_farming(cursor)

    # 预置政策：按内容签名自动重灌（幂等；只重建 author_id='gov_demo' 的预置行，不动自建政策）
    _refresh_policies(cursor)

    # 成功案例：把 cases_data.py 里新增的案例补一条**待审核**记录（幂等，不覆盖已有审核结果）
    _seed_case_reviews(cursor)

    # 演示企业岗位（用户 2026-10-06 拍板）：让「投递」链路有可演示的载体。
    # 只动 is_demo=1 的行，真实企业岗位与其投递/收藏不受影响。
    _seed_demo_jobs(cursor)

    # 清理历史版本遗留的 success_cases 表（含 3 条编造案例）。
    # 该表已废弃，内容改由 cases_data.py 提供，此处仅做一次性清库，保证编造数据不残留。
    cursor.execute("DROP TABLE IF EXISTS success_cases")

    # 清理已下架的「签到考勤」（2026-10-07 用户拍板：学员端从未实现签到，
    # 教师端也没有入口，整套是死功能）。建表语句已从 init_db 的建表脚本移除，
    # 这里做一次性清库，避免旧库里那张永远 open、0 人签到的表继续残留。
    cursor.execute("DROP TABLE IF EXISTS attendance_records")
    cursor.execute("DROP TABLE IF EXISTS attendances")

    # 一次性迁移（2026-10-07）：assignment_submissions.score 的语义由
    # 「系统规则分」改为「教师批改分」（见 save_live_training 的说明）。
    # 历史上 status 还是 submitted/pending（从未被教师批改过）的行，其 score 其实是
    # 提交时算出的规则分 —— 若原样留着，教师端会把旧规则分显示成「我的评分」，
    # 学员端也会以为是老师给的成绩。这里把它们搬进 content.rule_score、score 置 NULL。
    # 幂等：迁完 score 即 NULL，不会再被这条查询命中。
    _legacy = cursor.execute(
        "SELECT id, content, score FROM assignment_submissions "
        "WHERE score IS NOT NULL AND (status IS NULL OR status IN ('submitted', 'pending'))"
    ).fetchall()
    for _r in _legacy:
        try:
            _d = json.loads(_r['content'] or '{}')
        except Exception:
            _d = {}
        if not isinstance(_d, dict):
            _d = {}
        _d.setdefault('rule_score', _r['score'])
        cursor.execute("UPDATE assignment_submissions SET content = ?, score = NULL WHERE id = ?",
                       (json.dumps(_d, ensure_ascii=False), _r['id']))

    conn.commit()
    conn.close()


# 政策数据常量，供 _seed_data / _refresh_policies / _seed_government_policies 共用。
# ⚠️ 内容事实源 = policies_data.py（改完重启服务即生效，靠 seed_meta 内容签名自动重灌预置政策）。
#    本文件不再内联政策正文 —— 历史版本在此内联的 5 篇政策含编造案例与未核实电话，已整体移除。
import policies_data as _policy_src

POLICIES_DATA = [
    (p['title'], p['content'], p['category'], p['date'], p.get('summary', ''))
    for p in _policy_src.POLICIES
]

# 预置政策的「写入结构」版本号。改动写入的列（新增/删除字段）时**必须 +1**，
# 否则老库里的行不会重建，新列会一直为空（详见 _policies_signature 的说明）。
POLICIES_SEED_VERSION = 2

# 标题 -> 来源列表，播种时一并写入 source 字段
POLICY_SOURCES = {p['title']: p['sources'] for p in _policy_src.POLICIES}


def _policy_source_json(title):
    """把某条政策的来源列表序列化为 JSON 文本（存进 source 字段）。"""
    return json.dumps(POLICY_SOURCES.get(title, []), ensure_ascii=False)

# 注：旧版此处有 JOBS_DATA（30 条**编造**的演示岗位，假公司名/假薪资），已整体移除。
#     编造岗位会冒充真实在招职位 —— 学员会点「申请」，还会留下真实姓名与电话。
#     现在两条数据源分工：
#       · 公开招聘信息 → jobs_data.py（策展内容、带官方来源、不落库、不做站内申请）
#       · 企业岗位     → 企业端发布 → 内容审核 → 学员端只展示 review_status='approved'
#     旧库中的遗留预置行由 init_db() 一次性清理（判定：enterprise_id 为空串）。


def _seed_data(cursor):
    """填充种子数据"""
    # 用户
    admin_pw = hash_password('admin123')
    gov_pw = hash_password('123456')
    enterprise_pw = hash_password('123456')
    teacher_pw = hash_password('123456')
    student_pw = hash_password('123456')
    cursor.execute("INSERT INTO users (username, password_hash, name, role) VALUES (?, ?, ?, ?)",
                   ('admin_demo', admin_pw, '系统管理员', 'super_admin'))
    cursor.execute("INSERT INTO users (username, password_hash, name, role, region) VALUES (?, ?, ?, ?, ?)",
                   ('gov_demo', gov_pw, '王主任', 'government', '广东省农业农村厅'))
    cursor.execute("INSERT INTO users (username, password_hash, name, role, company_name, region) VALUES (?, ?, ?, ?, ?, ?)",
                   ('enterprise_demo', enterprise_pw, '陈经理', 'enterprise', '广州鲜果汇电商有限公司', '广州'))
    cursor.execute("INSERT INTO users (username, password_hash, name, role) VALUES (?, ?, ?, ?)",
                   ('teacher_demo', teacher_pw, '张老师', 'teacher'))
    cursor.execute("INSERT INTO users (username, password_hash, name, role) VALUES (?, ?, ?, ?)",
                   ('student_demo', student_pw, '李同学', 'student'))

    # 积分
    cursor.execute("INSERT INTO points (user_id, balance, history) VALUES (?, ?, ?)",
                   ('student_demo', 1250, json.dumps([
                       {"action": "完成课程", "points": 50, "date": "2024-06-10"},
                       {"action": "通过考试", "points": 100, "date": "2024-06-08"}
                   ])))
    for uid in ('admin_demo', 'gov_demo', 'enterprise_demo', 'teacher_demo'):
        cursor.execute("INSERT INTO points (user_id, balance, history) VALUES (?, ?, ?)",
                       (uid, 0, '[]'))

    # 证书
    for uid in ('student_demo', 'teacher_demo'):
        cursor.execute("INSERT INTO certificates (user_id, name, status, progress, date) VALUES (?, ?, ?, ?, ?)",
                       (uid, '荔枝种植技术员', 'earned', 100, '2024-05-20'))
        cursor.execute("INSERT INTO certificates (user_id, name, status, progress) VALUES (?, ?, ?, ?)",
                       (uid, '电商运营师', 'in_progress', 75))
        cursor.execute("INSERT INTO certificates (user_id, name, status) VALUES (?, ?, ?)",
                       (uid, '广绣工艺师', 'locked'))

    # 学员
    cursor.execute("INSERT INTO students (id, user_id, name, class_name, direction, progress, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
                   ('STU001', 'student_demo', '张小明', '2024春季班', '荔枝种植', 85, 'active'))
    cursor.execute("INSERT INTO students (id, user_id, name, class_name, direction, progress, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
                   ('STU002', '', '李小红', '2024春季班', '电商运营', 62, 'active'))

    # 注：成功案例不再入库 —— 见 cases_data.py（唯一事实源）。
    # 历史版本此处曾写入 3 条编造案例（"梅州某村电商转型之路" 等），已整体移除。

    # 政策（使用共用常量；source 存"来源列表"JSON）
    for title, content, cat, date, summary in POLICIES_DATA:
        cursor.execute("INSERT INTO policies (title, content, category, date, summary, source) VALUES (?, ?, ?, ?, ?, ?)",
                       (title, content, cat, date, summary, _policy_source_json(title)))

    # 注：不再写入演示岗位（见文件上方说明与 jobs_data.py）。

    # 政府政策（存到 government_policies 表）
    for title, content, cat, date, summary in POLICIES_DATA:
        cursor.execute("INSERT INTO government_policies (title, content, category, author_id, date, summary, source) VALUES (?, ?, ?, ?, ?, ?, ?)",
                       (title, content, cat, 'gov_demo', date, summary, _policy_source_json(title)))

    # 轮播图种子数据
    carousels = [
        ("粤乡智匠正式上线", "https://placehold.co/1200x400/10b981/white?text=粤乡智匠", "", 0),
        ("乡村振兴政策解读", "https://placehold.co/1200x400/00b4d8/white?text=政策解读", "/resources", 1),
        ("非遗技艺传承计划", "https://placehold.co/1200x400/8b5cf6/white?text=非遗传承", "/crafts", 2),
    ]
    for title, img, link, sort in carousels:
        cursor.execute("INSERT INTO carousels (title, image_url, link_url, sort_order) VALUES (?, ?, ?, ?)",
                       (title, img, link, sort))

    # 系统公告种子数据
    cursor.execute("INSERT INTO system_announcements (title, content, is_pinned, created_by) VALUES (?, ?, ?, ?)",
                   ('欢迎使用粤乡智匠平台', '粤乡智匠是基于AI实训系统的农村本土人才赋能平台，致力于为广东乡村振兴培养实用型人才。', 1, 'admin_demo'))

    # 讨论区种子数据
    cursor.execute("INSERT INTO discussions (title, content, category, user_id) VALUES (?, ?, ?, ?)",
                   ('荔枝种植经验交流', '各位种植荔枝的老乡，今年荔枝花期管理有什么心得？欢迎分享！', 'agriculture', 'student_demo'))
    cursor.execute("INSERT INTO discussions (title, content, category, user_id) VALUES (?, ?, ?, ?)",
                   ('电商直播新手问答', '刚开始做直播带货，想请教各位前辈有什么注意事项？', 'ecommerce', 'student_demo'))


def _seed_government_policies(cursor):
    """已有数据库时，补充政府政策数据"""
    for title, content, cat, date, summary in POLICIES_DATA:
        cursor.execute("INSERT INTO government_policies (title, content, category, author_id, date, summary, source) VALUES (?, ?, ?, ?, ?, ?, ?)",
                       (title, content, cat, 'gov_demo', date, summary, _policy_source_json(title)))


def _seed_carousels(cursor):
    """已有数据库时，补充默认轮播图"""
    carousels = [
        ("粤乡智匠正式上线", "https://placehold.co/1200x400/10b981/white?text=粤乡智匠", "", 0),
        ("乡村振兴政策解读", "https://placehold.co/1200x400/00b4d8/white?text=政策解读", "/resources", 1),
        ("非遗技艺传承计划", "https://placehold.co/1200x400/8b5cf6/white?text=非遗传承", "/crafts", 2),
    ]
    for title, img, link, sort in carousels:
        cursor.execute("INSERT INTO carousels (title, image_url, link_url, sort_order) VALUES (?, ?, ?, ?)",
                       (title, img, link, sort))


def _policies_signature():
    """预置政策的内容签名：任一政策的 标题/正文/分类/日期/摘要 变了，签名就变。

    ⚠️ 还要带上 POLICIES_SEED_VERSION —— 当"写入哪些列"变了（例如新增 summary/date 字段），
    即使正文一字未改，也必须让签名变化、把老库里的行重建一遍，否则新列在旧库里恒为空。
    """
    h = hashlib.md5()
    h.update(('seedver:%s\x1e' % POLICIES_SEED_VERSION).encode('utf-8'))
    for title, content, cat, date, summary in POLICIES_DATA:
        h.update(('%s\x1f%s\x1f%s\x1f%s\x1f%s\x1e' % (title, content, cat, date, summary)).encode('utf-8'))
    return h.hexdigest()


def _refresh_policies(cursor):
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
    signature = _policies_signature()
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


def _seed_case_reviews(cursor):
    """为「本地成功案例」补审核记录（幂等）。

    案例内容在 `cases_data.py`（不落库），但**审核状态必须落库**，
    否则重启后审核结果就丢了。这里复用通用 `content_reviews` 表：
      · 案例在库里没有审核记录 → 新增一条 `pending`（提交者 = admin_demo，即内容发布方）；
      · 已有记录（任何状态）→ **原样保留**，绝不把已通过的案例打回待审；
      · cases_data.py 里已删掉的案例 → 连带清掉其审核记录，避免脏数据。

    即：**新增案例需要超级管理员审核通过，才会出现在学员端首页**。
    """
    import cases_data
    valid_ids = {c['id'] for c in cases_data.get_cases()}

    rows = cursor.execute(
        "SELECT id, content_id FROM content_reviews WHERE content_type = ?",
        (CASE_REVIEW_TYPE,)).fetchall()
    existing = {r['content_id'] for r in rows}

    # 清理已不存在的案例残留记录
    for r in rows:
        if r['content_id'] not in valid_ids:
            cursor.execute("DELETE FROM content_reviews WHERE id = ?", (r['id'],))

    for cid in sorted(valid_ids - existing):
        cursor.execute(
            "INSERT INTO content_reviews (content_type, content_id, submitter_id, status) "
            "VALUES (?, ?, 'admin_demo', 'pending')",
            (CASE_REVIEW_TYPE, cid))


def _ensure_demo_accounts(cursor):
    """已有数据库时，补充缺少的新角色演示账户"""
    demo_accounts = [
        ('admin_demo', 'admin123', '系统管理员', 'super_admin', ''),
        ('gov_demo', '123456', '王主任', 'government', '广东省农业农村厅'),
        ('enterprise_demo', '123456', '陈经理', 'enterprise', '广州'),
    ]
    for username, password, name, role, region in demo_accounts:
        existing = cursor.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        if not existing:
            pw_hash = hash_password(password)
            cursor.execute(
                "INSERT INTO users (username, password_hash, name, role, region) VALUES (?, ?, ?, ?, ?)",
                (username, pw_hash, name, role, region))
            cursor.execute("INSERT INTO points (user_id, balance, history) VALUES (?, 0, '[]')", (username,))


# ==================== 演示企业岗位（2026-10-06 建；2026-10-07 改接企业端 + 审核链路）====================
# 背景：企业岗位表在移除 30 条编造岗位后归零 → 「我的投递」没有真实载体、链路跑不通。
# 用户 2026-10-06 决定放**少量、明确标注为演示**的岗位；2026-10-07 进一步要求
# 「**必须与真实链路一致**：由企业端发布，管理员审核通过后才在学员端显示」。
#
# ⚠️ 与「不编造」红线的关系：这些行**不是**冒充真实招聘信息，而是**显式声明为演示**：
#    ① 公司名带「（演示）」后缀；② job_listings.is_demo = 1；③ 前端强制打「演示数据」角标；
#    ④ 描述正文里写明「本岗位为平台演示数据，仅用于展示投递流程」。
#    四重标注确保学员不可能把它误认为真实在招岗位。
#
# ⚠️ 与真实链路的关系（2026-10-07 起）：
#    · 归属账号 = `DEMO_JOB_ENTERPRISE_ID`（**真实企业演示账号 `enterprise_demo`**，
#      不再是早期那个 `'__demo__'` sentinel）→ 企业端「岗位管理」里能看到、能编辑、能删除；
#    · 新建行 `review_status = 'pending'` 并**同时写一条 content_reviews**，
#      **必须由管理员审核通过后**才会出现在学员端（与真实企业发布的岗位走同一道门禁）；
#    · 已有行**只更新内容字段，绝不改写 `review_status`** —— 否则管理员驳回后
#      一重启就被种子逻辑重置（与政策侧踩过的「种子逻辑静默覆盖数据」同类）。
DEMO_JOBS = [
    {
        'key': 'demo-ec-operator',
        'title': '农产品电商运营专员',
        'company': '粤乡优品农业发展有限公司（演示）',
        'salary': '5K-8K',
        'location': '广州',
        'category': '电商运营',
        'job_type': '全职',
        'education': '大专',
        'experience': '1-3年',
        'company_size': '50-200人',
        'industry': '农产品电商',
        'requirements': [
            '熟悉主流电商平台的店铺运营与活动提报',
            '具备基础数据复盘能力，能看懂转化率、客单价等指标',
            '有生鲜或农产品类目经验者优先',
        ],
        'description': '负责公司农产品线上店铺的日常运营、活动策划与数据复盘。'
                       '（本岗位为平台演示数据，仅用于展示站内投递流程，非真实招聘信息）',
    },
    {
        'key': 'demo-lychee-tech',
        'title': '荔枝种植技术员',
        'company': '茂名荔乡种植专业合作社（演示）',
        'salary': '4K-6K',
        'location': '茂名',
        'category': '农业技术',
        'job_type': '全职',
        'education': '中专',
        'experience': '不限',
        'company_size': '20-50人',
        'industry': '种植业',
        'requirements': [
            '掌握荔枝栽培管理与主要病虫害防治基本知识',
            '能适应田间地头工作环境',
            '有农技推广或果园管理经验者优先',
        ],
        'description': '负责合作社荔枝园的日常栽培管理、物候期记录与技术归档。'
                       '（本岗位为平台演示数据，仅用于展示站内投递流程，非真实招聘信息）',
    },
]

# 演示岗位的归属账号 = **真实存在的企业演示账号**（由 `_ensure_demo_accounts` 创建：
# `enterprise_demo` / 123456 / 陈经理）。2026-10-07 用户要求「演示岗位要跟企业端挂钩」，
# 故由 sentinel `'__demo__'` 改为真实账号 —— 这样它在企业端「岗位管理」里可见可管，
# 审核也走同一个链路。
# ⚠️ 不要改回 sentinel：企业端列表查询是 `WHERE enterprise_id = <当前登录企业>`。
DEMO_JOB_ENTERPRISE_ID = 'enterprise_demo'

DEMO_JOBS_SEED_KEY = 'demo_jobs_seed'


def _demo_jobs_signature():
    """演示岗位内容签名：内容有变才重建，避免每次启动都写库。"""
    payload = json.dumps(
        [[j['key'], j['title'], j['company'], j['salary'], j['location'], j['category'],
          j['job_type'], j['education'], j['experience'], j['company_size'], j['industry'],
          j['requirements'], j['description']] for j in DEMO_JOBS],
        ensure_ascii=False, sort_keys=True)
    return hashlib.sha1(payload.encode('utf-8')).hexdigest()


def _create_review_with_cursor(cursor, content_type, content_id, submitter_id):
    """在既有事务里补一条待审记录。

    与 `create_content_review()` 等价，只是复用调用方已开的连接/事务 ——
    种子函数在 `init_db()` 里跑，不能中途另开连接（会撞 SQLite 写锁）。
    """
    cursor.execute(
        "INSERT INTO content_reviews (content_type, content_id, submitter_id, status) "
        "VALUES (?, ?, ?, 'pending')",
        (content_type, content_id, submitter_id))


def _seed_demo_jobs(cursor):
    """灌入/更新演示企业岗位（幂等，按内容签名驱动）。

    ⚠️ 四条红线：
      1. **只动 `is_demo = 1` 的行** —— 真实企业发布的岗位、以及学员对它们的投递/收藏完全不受影响。
      2. **按标题就地更新，不删后重建** —— 删后重建会换 id，学员已有的 job_applications
         会变成指向不存在岗位的孤儿记录（与「_refresh_policies 静默抹数据」同一类坑）。
      3. **绝不覆盖 `review_status`** —— 那是管理员的审核结论，种子逻辑无权改写。
         只有「一次性迁移」与「首次新建」两种情形才会把它置为 `pending`。
      4. 仅当某个演示岗位**确实已从 DEMO_JOBS 中移除**时，才连带清理它的投递/收藏记录。

    2026-10-07 变更（用户要求「演示数据要跟企业端挂钩」）：
      由「平台预置 + 直接 approved」改为「**挂真实企业演示账号 + 走同一条审核链路**」。
    """
    signature = _demo_jobs_signature()
    row = cursor.execute("SELECT value FROM seed_meta WHERE key = ?", (DEMO_JOBS_SEED_KEY,)).fetchone()

    # ① 一次性迁移（幂等）：早期版本把演示岗位挂在 sentinel '__demo__' 名下、并直接写成
    #    approved，完全绕过了审核链路。现在改挂真实企业演示账号，并回退成「待审核」。
    #    ⚠️ 只命中 `is_demo = 1` 的行（真实企业岗位的 is_demo 恒为 0），
    #    且改完 enterprise_id 后该条件即不再成立 → 再次启动**不会**把管理员后来的
    #    审核结论又打回 pending。
    cursor.execute(
        "UPDATE job_listings SET enterprise_id = ?, review_status = 'pending' "
        "WHERE is_demo = 1 AND (enterprise_id IS NULL OR enterprise_id = '' "
        "                       OR enterprise_id = '__demo__')",
        (DEMO_JOB_ENTERPRISE_ID,))

    # ② 补齐审核记录：没有 content_reviews 的演示岗位在管理端审核列表里不出现，
    #    「企业发布 → 平台审核」这条链路就是断的（迁移过来的老行本来就没有记录）。
    #    这一步放在签名短路**之前**，否则老库改不动（签名相同会直接 return）。
    missing = cursor.execute(
        "SELECT id FROM job_listings WHERE is_demo = 1 AND id NOT IN ("
        "  SELECT content_id FROM content_reviews WHERE content_type = 'job')").fetchall()
    for r in missing:
        _create_review_with_cursor(cursor, 'job', r[0], DEMO_JOB_ENTERPRISE_ID)

    if row and row[0] == signature:
        return

    wanted_titles = {j['title'] for j in DEMO_JOBS}
    existing = {
        r['title']: r['id']
        for r in cursor.execute(
            "SELECT id, title FROM job_listings WHERE is_demo = 1").fetchall()
    }

    for job in DEMO_JOBS:
        reqs = json.dumps(job['requirements'], ensure_ascii=False)
        prev_id = existing.get(job['title'])
        if prev_id:
            # ⚠️ 这里**不写 review_status**：pending / approved / rejected 一律保持原样
            cursor.execute("""
                UPDATE job_listings
                   SET company = ?, salary = ?, requirements = ?, description = ?,
                       location = ?, category = ?, job_type = ?, education = ?,
                       experience = ?, company_size = ?, industry = ?,
                       enterprise_id = ?, is_demo = 1
                 WHERE id = ?
            """, (job['company'], job['salary'], reqs, job['description'],
                  job['location'], job['category'], job['job_type'], job['education'],
                  job['experience'], job['company_size'], job['industry'],
                  DEMO_JOB_ENTERPRISE_ID, prev_id))
        else:
            # 新建 = 企业「刚发布」的状态：待审核，学员端不可见
            cursor.execute("""
                INSERT INTO job_listings
                    (title, company, salary, requirements, description, location, category,
                     job_type, education, experience, company_size, industry,
                     posted_at, enterprise_id, review_status, is_demo)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        datetime('now','localtime'), ?, 'pending', 1)
            """, (job['title'], job['company'], job['salary'], reqs, job['description'],
                  job['location'], job['category'], job['job_type'], job['education'],
                  job['experience'], job['company_size'], job['industry'],
                  DEMO_JOB_ENTERPRISE_ID))
            prev_id = cursor.lastrowid
            _create_review_with_cursor(cursor, 'job', prev_id, DEMO_JOB_ENTERPRISE_ID)

    # 已被移出 DEMO_JOBS 的演示岗位：连带清掉指向它的投递/收藏/审核记录，避免孤儿
    stale_ids = [jid for title, jid in existing.items() if title not in wanted_titles]
    if stale_ids:
        _qm = ','.join('?' * len(stale_ids))
        cursor.execute("DELETE FROM job_applications WHERE job_id IN (%s)" % _qm, stale_ids)
        cursor.execute("DELETE FROM saved_jobs WHERE job_id IN (%s)" % _qm, stale_ids)
        cursor.execute("DELETE FROM content_reviews WHERE content_type = 'job' AND content_id IN (%s)" % _qm, stale_ids)
        cursor.execute("DELETE FROM job_listings WHERE id IN (%s)" % _qm, stale_ids)

    cursor.execute(
        "INSERT OR REPLACE INTO seed_meta (key, value, updated_at) VALUES (?, ?, datetime('now','localtime'))",
        (DEMO_JOBS_SEED_KEY, signature))


# ==================== 农时智能日历 种子数据 ====================

def _farming_seed_signature(sources, products, phases, tasks):
    """计算种子数据内容签名（sha1）。

    仅比行数无法发现"条数不变但内容变了"的情况（例如为已有任务补 task_md、
    修正物候期月份区间、补齐 source_key / date_basis）。此处对全部字段做规范化
    JSON 序列化后取 sha1，内容有任何变化都会导致签名不同，从而触发重灌。
    """
    payload = {
        'sources': [
            [s['key'], s.get('name', ''), s.get('org', ''), s.get('doc_type', ''),
             s.get('doc_no', ''), s.get('url', '')]
            for s in sources
        ],
        'products': [
            [p['id'], p.get('name', ''), p.get('icon', 'seedling'),
             p.get('summary', ''), p.get('region', '广东'), p.get('sort_order', 0)]
            for p in products
        ],
        'phases': [
            [ph['product_id'], ph.get('name', ''), ph.get('start_month'),
             ph.get('end_month'), ph.get('color', ''), ph.get('description', ''),
             ph.get('sort_order', 0)]
            for ph in phases
        ],
        'tasks': [
            [t['product_id'], t.get('phase'), t.get('title', ''), t.get('category', ''),
             t.get('priority', 'medium'), t.get('task_md'), t.get('month'),
             t.get('icon', 'tasks'), t.get('description', ''), t.get('tip', ''),
             t.get('is_verified', 0), t.get('source_key', ''),
             t.get('date_basis', '')]
            for t in tasks
        ],
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return hashlib.sha1(raw.encode('utf-8')).hexdigest()


def _seed_farming(cursor):
    """写入农时日历种子数据（幂等，按内容签名判断是否需要重灌）。

    - 数据源：同目录 farming_data.py
    - 仅当数据模块的**内容签名**与 farming_seed_meta 中记录的不一致时才重写，
      避免每次启动都产生写放大；同时可捕获"条数不变但内容变了"的更新
    - 重写时先删后插：farming_subscriptions / farming_reminder_log 不含外键指向任务 id，
      且均以 (user_id, product_id[, period]) 为业务键，因此用户订阅数据不受影响
    """
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)
    try:
        import farming_data as fd
    except Exception:
        return  # 数据模块缺失时静默跳过，不阻断建库

    sources = getattr(fd, 'FARMING_SOURCES', [])
    products = getattr(fd, 'FARMING_PRODUCTS', [])
    phases = getattr(fd, 'FARMING_PHENOPHASES', [])
    tasks = getattr(fd, 'FARMING_TASKS', [])
    if not (products and phases and tasks):
        return

    signature = _farming_seed_signature(sources, products, phases, tasks)
    row = cursor.execute(
        "SELECT value FROM farming_seed_meta WHERE key = 'farming_seed'").fetchone()
    if row and row[0] == signature:
        return  # 内容未变化，跳过

    # ① 数据来源登记表（整体替换：来源集合只随数据模块变化）
    cursor.execute("DELETE FROM farming_sources")
    for idx, s in enumerate(sources):
        cursor.execute(
            """INSERT INTO farming_sources (key, name, org, doc_type, doc_no, url, sort_order)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (s['key'], s.get('name', ''), s.get('org', ''), s.get('doc_type', ''),
             s.get('doc_no', '') or '待核', s.get('url', ''), idx))

    # ② 产品目录（upsert，不动订阅）
    for p in products:
        cursor.execute(
            """INSERT INTO farming_products (id, name, icon, summary, region, sort_order, is_active)
               VALUES (?, ?, ?, ?, ?, ?, 1)
               ON CONFLICT(id) DO UPDATE SET
                   name=excluded.name, icon=excluded.icon, summary=excluded.summary,
                   region=excluded.region, sort_order=excluded.sort_order, is_active=1""",
            (p['id'], p['name'], p.get('icon', 'seedling'), p.get('summary', ''),
             p.get('region', '广东'), p.get('sort_order', 0)))

    # ③ 物候期（按产品删后重建）
    for p in products:
        cursor.execute("DELETE FROM farming_phenophases WHERE product_id = ?", (p['id'],))
    for ph in phases:
        cursor.execute(
            """INSERT INTO farming_phenophases
                   (product_id, name, start_month, end_month, color, description, sort_order)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (ph['product_id'], ph['name'], ph['start_month'], ph['end_month'],
             ph.get('color', '#1f5e43'), ph.get('description', ''), ph.get('sort_order', 0)))

    # ④ 任务（按产品删后重建；phase 名称 -> phase_id）
    phase_map = {}
    for r in cursor.execute("SELECT id, product_id, name FROM farming_phenophases").fetchall():
        phase_map[(r[1], r[2])] = r[0]

    for p in products:
        cursor.execute("DELETE FROM farming_tasks WHERE product_id = ?", (p['id'],))
    for idx, t in enumerate(tasks):
        phase_id = phase_map.get((t['product_id'], t.get('phase')))
        cursor.execute(
            """INSERT INTO farming_tasks
                   (product_id, phase_id, title, category, priority, task_md, month,
                    icon, description, tip, is_verified, source_key, date_basis,
                    is_active, sort_order)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)""",
            (t['product_id'], phase_id, t['title'], t['category'],
             t.get('priority', 'medium'), t.get('task_md'), t['month'],
             t.get('icon', 'tasks'), t.get('description', ''), t.get('tip', ''),
             int(t.get('is_verified', 0) or 0), t.get('source_key', '') or '',
             t.get('date_basis', '') or '', idx))

    # ⑤ 记录本次签名
    cursor.execute(
        """INSERT INTO farming_seed_meta (key, value, updated_at)
           VALUES ('farming_seed', ?, datetime('now','localtime'))
           ON CONFLICT(key) DO UPDATE SET
               value=excluded.value, updated_at=excluded.updated_at""",
        (signature,))



# ==================== 农时智能日历 数据访问 ====================

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
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)
    try:
        import farming_data as fd
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

def get_user_by_id(user_id):
    """根据用户ID获取完整用户信息"""
    conn = get_connection()
    row = conn.execute("SELECT id, username, name, role, email, created_at FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_username(username):
    """根据用户名获取用户信息"""
    conn = get_connection()
    row = conn.execute("SELECT id, username, name, role, email, created_at FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_user_profile(user_id, name=None, email=None):
    """更新用户资料（姓名、邮箱）"""
    conn = get_connection()
    updates = []
    params = []
    if name is not None:
        updates.append("name = ?")
        params.append(name)
    if email is not None:
        updates.append("email = ?")
        params.append(email)
    if not updates:
        conn.close()
        return False
    params.append(user_id)
    conn.execute(f"UPDATE users SET {', '.join(updates)} WHERE id = ?", params)
    conn.commit()
    conn.close()
    return True


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

def get_certificates(user_id):
    """获取用户证书"""
    conn = get_connection()
    rows = conn.execute("SELECT * FROM certificates WHERE user_id = ?", (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ==================== 学员 ====================

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


def get_linkable_student_accounts():
    """可被名册关联的学员账号：role='student' 且尚未被任何名册行占用。

    已被占用的账号不出现，避免一个账号挂到两个学员上（统计会串）。
    """
    conn = get_connection()
    rows = conn.execute(
        "SELECT u.username, u.name FROM users u "
        "WHERE u.role = 'student' AND u.username NOT IN "
        "      (SELECT user_id FROM students WHERE user_id IS NOT NULL AND user_id != '') "
        "ORDER BY u.username"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


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
        u = conn.execute("SELECT username, role FROM users WHERE username = ?", (username,)).fetchone()
        if not u:
            conn.close()
            return False, f'账号 {username} 不存在'
        if u['role'] != 'student':
            conn.close()
            return False, f'账号 {username} 不是学员角色，不能关联'
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

def create_announcement(title, content, category='通知', pinned=0):
    conn = get_connection()
    cursor = conn.execute("INSERT INTO announcements (title, content, category, pinned) VALUES (?, ?, ?, ?)",
                          (title, content, category, pinned))
    conn.commit()
    aid = cursor.lastrowid
    conn.close()
    return aid

def get_announcements(limit=50):
    conn = get_connection()
    rows = conn.execute("SELECT * FROM announcements ORDER BY pinned DESC, created_at DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def delete_announcement(ann_id):
    conn = get_connection()
    result = conn.execute("DELETE FROM announcements WHERE id = ?", (ann_id,))
    conn.commit()
    deleted = result.rowcount > 0
    conn.close()
    return deleted


# ==================== 实训批改（原「作业管理」） ====================
# 2026-10-07 用户拍板：**「发布作业」整块下架**。
# ⚠️ `assignments` 表**必须保留** —— 它现在的唯一用途是承载三种电商实训的题目
#    （`TRAINING_TITLE_FMTS` 用 title 前缀反推 kind，见下方「直播带货实训（EC7）」段），
#    `get_or_create_*_assignment` / `grade_submission` 都依赖它。
#    删掉的只是「教师手动建作业/看作业」这条链路：
#    create_assignment / get_assignments / get_assignment / submit_assignment /
#    get_student_submissions（经核查前端零调用）。
def grade_submission(submission_id, score, feedback=''):
    conn = get_connection()
    conn.execute("UPDATE assignment_submissions SET score = ?, feedback = ?, status = 'graded', graded_at = datetime('now','localtime') WHERE id = ?",
                 (score, feedback, submission_id))
    conn.commit()
    updated = conn.execute("SELECT changes()").fetchone()[0] > 0
    conn.close()
    return updated


# ---- 直播带货实训（EC7）：复用既有作业链路，不新建数据表 --------------------
# 设计取舍：一次直播实训 = 一条 assignment_submissions。
#  · 每个作物复用一个实训题目，避免每提交一次就往教师端塞一条新作业；
#  · assignment_submissions 有 UNIQUE(assignment_id, student_id)，故同一学员同一作物
#    只保留**最新一次**提交，历史尝试次数记在 content 的 JSON 里（attempts）。
LIVE_ASSIGNMENT_DIRECTION = 'ecommerce'
LIVE_ASSIGNMENT_TITLE_FMT = '直播带货实训 · {}'

# 2026-10-05 文案 / 客服闭环：三种实训共用同一套题目/提交机制，只用 title 前缀区分 kind。
# title 前缀即 records 接口的过滤依据 —— 改前缀必须同步改 app.py 的 kind 校验与前端。
TRAINING_TITLE_FMTS = {
    'live': LIVE_ASSIGNMENT_TITLE_FMT,
    'copy': '商品文案实训 · {}',
    'cs':   '客服对练实训 · {}',
}
TRAINING_DESCRIPTIONS = {
    'live': '{product} 直播带货实训：提交学员自己的话术稿，并附朗读实录分析。'
            '指标由规则分析给出、可复现；教师可复核。',
    'copy': '{product} 商品文案实训：AI 只出初稿，学员改写后提交自己的版本。'
            '具体认证/数据/价格必须用真实信息，不得编造；教师可复核。',
    'cs':   '{product} 客服对练实训：学员扮演客服逐轮回复模拟客户，提交完整对话记录'
            '与规则评分明细；教师可复核。',
}


def get_or_create_training_assignment(product, kind='live'):
    """按 kind + 作物取/建实训题目，返回 assignment_id。"""
    fmt = TRAINING_TITLE_FMTS.get(kind)
    if not fmt:
        raise ValueError('unknown training kind: %r' % kind)
    title = fmt.format(product)
    conn = get_connection()
    row = conn.execute(
        "SELECT id FROM assignments WHERE title = ? AND direction = ? LIMIT 1",
        (title, LIVE_ASSIGNMENT_DIRECTION)
    ).fetchone()
    if row:
        conn.close()
        return row['id']
    cur = conn.execute(
        "INSERT INTO assignments (title, description, direction, deadline, total_score) "
        "VALUES (?, ?, ?, '', 100)",
        (title, TRAINING_DESCRIPTIONS.get(kind, '').format(product=product),
         LIVE_ASSIGNMENT_DIRECTION)
    )
    conn.commit()
    aid = cur.lastrowid
    conn.close()
    return aid


def get_or_create_live_assignment(product):
    """按作物取/建实训题目，返回 assignment_id。"""
    return get_or_create_training_assignment(product, 'live')


def save_live_training(assignment_id, student_id, payload, rule_score=None):
    """写入/更新一次实训提交。

    ⚠️ score 列语义 = **教师批改分**，只由 grade_submission() 写。
       系统规则分存进 content 的 rule_score，**不再写进 score**。
       2026-10-07 前这里是 `SET score = ?` 直接写规则分，造成三个后果：
         ① 教师端出现「85 分 + 待批改」「0 分 + 待批改」这种自相矛盾的行；
         ② 教师批改后学员重新提交，教师给的分被规则分**静默覆盖**；
         ③ 评语被清空、graded_at 归零，而没人告诉教师批改结果已经失效。
       现在重新提交的规则：
         · 从未批改过 → status 保持 'submitted'（待批改），score/feedback 本来就是空；
         · 已批改过   → **保留** score / feedback / graded_at，status 改 'resubmitted'
                        （已重新提交·待复核），教师端会醒目提示。
    返回 (提交 id, 累计尝试次数)。
    """
    conn = get_connection()
    row = conn.execute(
        "SELECT id, content, status, score, feedback FROM assignment_submissions "
        "WHERE assignment_id = ? AND student_id = ?",
        (assignment_id, student_id)
    ).fetchone()
    attempts = 1
    if row:
        try:
            attempts = int(json.loads(row['content'] or '{}').get('attempts', 0)) + 1
        except Exception:
            attempts = 1
    payload = dict(payload or {})
    payload['attempts'] = attempts
    try:
        payload['rule_score'] = int(rule_score or 0)
    except (TypeError, ValueError):
        payload['rule_score'] = 0
    content_json = json.dumps(payload, ensure_ascii=False)
    if row:
        prev_status = (row['status'] or 'submitted')
        # 判据用「有没有教师批改结果」而不是 status 字符串：
        # 历史数据里 status 可能被老逻辑重置过，而 score 一旦有值就是教师给的。
        already_graded = (row['score'] is not None) or (prev_status == 'graded')
        new_status = 'resubmitted' if already_graded else 'submitted'
        conn.execute(
            "UPDATE assignment_submissions SET content = ?, status = ?, "
            "submitted_at = datetime('now','localtime') WHERE id = ?",
            (content_json, new_status, row['id'])
        )
        conn.commit()
        sid = row['id']
    else:
        cur = conn.execute(
            "INSERT INTO assignment_submissions (assignment_id, student_id, content, score, status) "
            "VALUES (?, ?, ?, NULL, 'submitted')",
            (assignment_id, student_id, content_json)
        )
        conn.commit()
        sid = cur.lastrowid
    conn.close()
    return sid, attempts


def get_trainings(student_id, kind=None):
    """取某学员的实训记录（每个作物各一条）。

    kind 为 None 时返回全部电商实训（三种混合）；否则按 title 前缀过滤。
    """
    conn = get_connection()
    if kind and kind in TRAINING_TITLE_FMTS:
        rows = conn.execute(
            "SELECT s.*, a.title AS assignment_title FROM assignment_submissions s "
            "LEFT JOIN assignments a ON s.assignment_id = a.id "
            "WHERE s.student_id = ? AND a.direction = ? AND a.title LIKE ? "
            "ORDER BY s.submitted_at DESC",
            (student_id, LIVE_ASSIGNMENT_DIRECTION,
             TRAINING_TITLE_FMTS[kind].format('%'))
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT s.*, a.title AS assignment_title FROM assignment_submissions s "
            "LEFT JOIN assignments a ON s.assignment_id = a.id "
            "WHERE s.student_id = ? AND a.direction = ? ORDER BY s.submitted_at DESC",
            (student_id, LIVE_ASSIGNMENT_DIRECTION)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_live_trainings(student_id):
    """取某学员的全部直播实训记录（每个作物各一条）。"""
    return get_trainings(student_id, 'live')


def get_all_trainings():
    """教师端：全部学员的电商实训提交（按提交时间倒序）。

    复用既有作业链路（assignments + assignment_submissions），
    kind 由作业标题前缀反推（见 TRAINING_TITLE_FMTS），不改表结构。

    另带出**名册姓名**：assignment_submissions.student_id 存的是 username（如 student_demo），
    教师端直接显示登录名不好认人（2026-10-07）。
    ⚠️ 姓名用**标量子查询**取，不用 LEFT JOIN —— 名册允许同一 user_id 出现多行时
       JOIN 会让同一条提交重复出现。
    """
    conn = get_connection()
    rows = conn.execute(
        "SELECT s.*, a.title AS assignment_title, "
        "       (SELECT st.name FROM students st "
        "         WHERE st.user_id = s.student_id AND st.user_id != '' LIMIT 1) AS student_name "
        "FROM assignment_submissions s "
        "LEFT JOIN assignments a ON s.assignment_id = a.id "
        "WHERE a.direction = ? ORDER BY s.submitted_at DESC"
        , (LIVE_ASSIGNMENT_DIRECTION,)
    ).fetchall()
    conn.close()
    out = []
    for r in rows:
        item = dict(r)
        title = item.get('assignment_title') or ''
        item['kind'] = ''
        for k, fmt in TRAINING_TITLE_FMTS.items():
            if title.startswith(fmt.format('')):
                item['kind'] = k
                break
        out.append(item)
    return out


# ==================== 学情分析 ====================

def get_roster_completion():
    """名册每位学员的「证书真实完成度」。

    口径（2026-10-07 用户拍板：学情分析 / AI 教学报告 / 仪表板统计不再使用
    students.progress 这个**手填**字段）：
      · 完成度 = 该学员名下 certificates.progress 的平均值（0-100 整数）；
      · 没有任何证书记录 → completion = 0 且 has_cert_data = 0
        （统计里单独说明「暂无证书记录」，不冒充「0% 完成」）；
      · 证书按 user_id（= username）归属，未关联账号的名册行必然没有证书记录。
    """
    conn = get_connection()
    rows = conn.execute("SELECT id, name, direction, user_id, status FROM students ORDER BY id").fetchall()
    out = []
    for r in rows:
        uid = r['user_id'] or ''
        certs = []
        if uid:
            certs = conn.execute(
                "SELECT progress, status FROM certificates WHERE user_id = ?", (uid,)).fetchall()
        earned = sum(1 for c in certs if c['status'] == 'earned')
        has_data = len(certs) > 0
        completion = int(round(sum((c['progress'] or 0) for c in certs) / len(certs))) if has_data else 0
        out.append({
            'id': r['id'], 'name': r['name'], 'direction': r['direction'] or '未分类',
            'user_id': uid, 'status': r['status'],
            'has_account': bool(uid), 'has_cert_data': has_data,
            'cert_total': len(certs), 'cert_earned': earned,
            'completion': completion,
        })
    conn.close()
    return out


def get_analytics_data():
    """学情分析数据 —— 口径：**证书真实完成度**（见 get_roster_completion）。

    2026-10-07 修正：原实现直接聚合 students.progress（教师手填、学员端没有任何
    入口会更新它），画出来的「进度分布」与学员真实学习情况无关。
    """
    roster = get_roster_completion()
    ranges = [(0, 20, '0-20%'), (21, 40, '21-40%'), (41, 60, '41-60%'), (61, 80, '61-80%'), (81, 100, '81-100%')]
    progress_dist = []
    for low, high, label in ranges:
        count = sum(1 for r in roster if r['has_cert_data'] and low <= r['completion'] <= high)
        progress_dist.append({'label': label, 'count': count})

    no_cert = [r for r in roster if not r['has_cert_data']]

    by_dir = {}
    for r in roster:
        by_dir.setdefault(r['direction'], []).append(r)
    direction_dist = [{'direction': d, 'count': len(v)} for d, v in by_dir.items()]
    direction_progress = [{
        'direction': d,
        'student_count': len(v),
        'avg_progress': round(sum(x['completion'] for x in v) / len(v), 1),
        'cert_earned': sum(x['cert_earned'] for x in v),
        'no_cert_count': sum(1 for x in v if not x['has_cert_data']),
    } for d, v in by_dir.items()]

    return {
        'basis': 'certificates',
        'basis_label': '证书真实完成度（学员名下证书进度的平均值）',
        'roster_count': len(roster),
        'no_cert_count': len(no_cert),
        'progress_distribution': progress_dist,
        'direction_distribution': direction_dist,
        'direction_progress': direction_progress
    }


# ==================== 消息系统 ====================

def send_message(sender_id, receiver_id, content):
    # messages.id 是 INTEGER PRIMARY KEY AUTOINCREMENT，**不能**塞 uuid 字符串
    # （SQLite 会报 datatype mismatch）。落库后取自增主键返回，供前端轮询去重。
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO messages (sender_id, receiver_id, content) VALUES (?, ?, ?)",
        (sender_id, receiver_id, content)
    )
    mid = cur.lastrowid
    conn.commit()
    conn.close()
    return mid


def get_messages(user1_id, user2_id, limit=50):
    conn = get_connection()
    rows = conn.execute(
        """SELECT * FROM messages
           WHERE (sender_id = ? AND receiver_id = ?) OR (sender_id = ? AND receiver_id = ?)
           ORDER BY created_at DESC LIMIT ?""",
        (user1_id, user2_id, user2_id, user1_id, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in reversed(rows)]


def get_inbox(user_id):
    """会话列表（按最近一条消息分组）。

    ⚠️ messages 表的 sender_id / receiver_id 全站是 **username**（与 user_id 红线一致）。
    原实现拿它去 JOIN students.id（名册号 STU001…）必然 JOIN 不上 → 对方名字
    只能显示成裸用户名（student_demo / teacher_demo）。现在按优先级解析：
    名册（students.user_id = username）→ 账号表（users.name）→ 才回退用户名。
    """
    conn = get_connection()
    rows = conn.execute(
        """SELECT m.* FROM messages m
           WHERE m.id IN (
               SELECT MAX(id) FROM messages
               WHERE sender_id = ? OR receiver_id = ?
               GROUP BY CASE WHEN sender_id = ? THEN receiver_id ELSE sender_id END
           )
           ORDER BY m.created_at DESC""",
        (user_id, user_id, user_id)
    ).fetchall()

    def _resolve_name(other_id):
        if not other_id:
            return other_id or ''
        r = conn.execute("SELECT name FROM students WHERE user_id = ? LIMIT 1", (other_id,)).fetchone()
        if r and r['name']:
            return r['name']
        r = conn.execute("SELECT name FROM users WHERE username = ?", (other_id,)).fetchone()
        if r and r['name']:
            return r['name']
        return other_id

    # ⚠️ 下面的循环必须发生在 conn.close() **之前**：_resolve_name 是闭包，
    #   里面还要用同一个 conn 去查 students / users。原先 close 写在循环前，
    #   导致「只要收件箱里有一条消息」就会抛
    #   `ProgrammingError: Cannot operate on a closed database` → /api/messages/inbox 恒 500。
    #   库里没有消息时 rows 为空、闭包不被调用，所以这个 bug 长期不暴露（2026-10-09）。
    result = []
    for r in rows:
        d = dict(r)
        other_id = d['receiver_id'] if d['sender_id'] == user_id else d['sender_id']
        d['other_id'] = other_id
        d['other_name'] = _resolve_name(other_id)
        d['is_mine'] = d['sender_id'] == user_id
        result.append(d)
    conn.close()
    return result


def get_unread_count(user_id):
    conn = get_connection()
    count = conn.execute(
        "SELECT COUNT(*) FROM messages WHERE receiver_id = ? AND is_read = 0",
        (user_id,)
    ).fetchone()[0]
    conn.close()
    return count


def mark_messages_read(sender_id, receiver_id):
    conn = get_connection()
    conn.execute(
        "UPDATE messages SET is_read = 1 WHERE sender_id = ? AND receiver_id = ? AND is_read = 0",
        (sender_id, receiver_id)
    )
    conn.commit()
    conn.close()


# ==================== 系统通知 ====================

def create_notification(user_id, ntype, title, content='', link_type='', link_id=None):
    conn = get_connection()
    conn.execute(
        "INSERT INTO notifications (user_id, type, title, content, link_type, link_id) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, ntype, title, content, link_type, link_id)
    )
    conn.commit()
    conn.close()


def create_notification_for_all_students(ntype, title, content='', link_type='', link_id=None):
    """给所有**已关联平台账号**的学员发站内通知。

    ⚠️ notifications.user_id 的语义是全站统一的 username（见全局红线）。
    名册表 students 有自己的 id（STU001…）与可选的 user_id（= username）。
    早期实现误把 students.id 当作收件人写入，导致真实登录学员收不到任何通知
    （2026-10-07 修复）。没有关联账号的名册行直接跳过，不写无人认领的脏行。
    """
    conn = get_connection()
    rows = conn.execute("SELECT user_id FROM students WHERE user_id != ''").fetchall()
    for r in rows:
        conn.execute(
            "INSERT INTO notifications (user_id, type, title, content, link_type, link_id) VALUES (?, ?, ?, ?, ?, ?)",
            (r['user_id'], ntype, title, content, link_type, link_id)
        )
    conn.commit()
    conn.close()


def get_notifications(user_id, limit=20):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM notifications WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
        (user_id, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_unread_notification_count(user_id):
    conn = get_connection()
    count = conn.execute(
        "SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0",
        (user_id,)
    ).fetchone()[0]
    conn.close()
    return count


def mark_notifications_read(user_id):
    conn = get_connection()
    conn.execute(
        "UPDATE notifications SET is_read = 1 WHERE user_id = ? AND is_read = 0",
        (user_id,)
    )
    conn.commit()
    conn.close()


def clear_read_notifications(user_id):
    conn = get_connection()
    conn.execute(
        "DELETE FROM notifications WHERE user_id = ? AND is_read = 1",
        (user_id,)
    )
    conn.commit()
    conn.close()

# ---- 已读旁路表（system_announcements / job_applications 两个无 is_read 的来源）----

def get_read_refs(user_id, source):
    """取某用户在某来源上已读的 ref_id 列表。"""
    conn = get_connection()
    rows = conn.execute(
        "SELECT ref_id FROM notification_reads WHERE user_id = ? AND source = ?",
        (user_id, source)
    ).fetchall()
    conn.close()
    return [r[0] for r in rows]

def mark_ref_read(user_id, source, ref_id):
    conn = get_connection()
    conn.execute(
        "INSERT OR IGNORE INTO notification_reads (user_id, source, ref_id) VALUES (?, ?, ?)",
        (user_id, source, str(ref_id))
    )
    conn.commit()
    conn.close()

def mark_refs_read(user_id, source, ref_ids):
    """批量标记已读（「全部已读」用）。ref_ids 为空时不做任何写入。"""
    conn = get_connection()
    for rid in ref_ids:
        conn.execute(
            "INSERT OR IGNORE INTO notification_reads (user_id, source, ref_id) VALUES (?, ?, ?)",
            (user_id, source, str(rid))
        )
    conn.commit()
    conn.close()

def clear_read_refs(user_id, source):
    conn = get_connection()
    conn.execute(
        "DELETE FROM notification_reads WHERE user_id = ? AND source = ?",
        (user_id, source)
    )
    conn.commit()
    conn.close()

def mark_all_messages_read(user_id):
    """把「别人发给我的」所有私信标为已读（全部已读用）。"""
    conn = get_connection()
    conn.execute(
        "UPDATE messages SET is_read = 1 WHERE receiver_id = ? AND is_read = 0",
        (user_id,)
    )
    conn.commit()
    conn.close()

def get_job_application_ids(user_id):
    """该用户全部投递记录 id（「全部已读」要把它们逐个标已读）。"""
    conn = get_connection()
    rows = conn.execute(
        "SELECT id FROM job_applications WHERE user_id = ?", (user_id,)
    ).fetchall()
    conn.close()
    return [str(r[0]) for r in rows]

def get_active_system_announcement_ids():
    """在投的系统公告 id（全局来源，不随用户变化）。"""
    conn = get_connection()
    rows = conn.execute(
        "SELECT id FROM system_announcements WHERE is_active = 1"
    ).fetchall()
    conn.close()
    return [str(r[0]) for r in rows]

def get_total_unread_count(user_id):
    """消息中心四个数据源的未读总数。

    红点与「未读」页签都按这个口径，避免出现「红点有数、未读页签是空的」。
    """
    conn = get_connection()
    notif = conn.execute(
        "SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0",
        (user_id,)
    ).fetchone()[0]
    msgs = conn.execute(
        # 私信按**会话**数而不是按消息条数：消息中心「互动」条目是一行一个会话，
        # 按条数会让红点比可见条目多出一截（实测 15 对 9）。口径与 get_inbox 一致。
        """SELECT COUNT(*) FROM messages m
           WHERE m.receiver_id = ? AND m.is_read = 0
             AND m.id IN (
                 SELECT MAX(id) FROM messages
                 WHERE sender_id = ? OR receiver_id = ?
                 GROUP BY CASE WHEN sender_id = ? THEN receiver_id ELSE sender_id END
             )""",
        (user_id, user_id, user_id, user_id)
    ).fetchone()[0]
    apps = conn.execute(
        """SELECT COUNT(*) FROM job_applications a
           WHERE a.user_id = ?
             AND NOT EXISTS (SELECT 1 FROM notification_reads r
                             WHERE r.user_id = a.user_id
                               AND r.source = 'job_application'
                               AND r.ref_id = CAST(a.id AS TEXT))""",
        (user_id,)
    ).fetchone()[0]
    anns = conn.execute(
        """SELECT COUNT(*) FROM system_announcements s
           WHERE s.is_active = 1
             AND NOT EXISTS (SELECT 1 FROM notification_reads r
                             WHERE r.user_id = ?
                               AND r.source = 'system_announcement'
                               AND r.ref_id = CAST(s.id AS TEXT))""",
        (user_id,)
    ).fetchone()[0]
    conn.close()
    return notif + msgs + apps + anns


# ==================== 就业 ====================

def get_job_listings():
    """获取岗位列表"""
    conn = get_connection()
    rows = conn.execute("SELECT * FROM job_listings").fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d['requirements'] = json.loads(d['requirements'])
        result.append(d)
    return result


def apply_for_job(user_id, job_id):
    """申请职位。

    返回值（三态，勿再当布尔用）：
      'ok'          —— 申请成功
      'dup'         —— 已申请过
      'unavailable' —— 职位不存在，或**未通过审核**（企业发布后处于 pending）

    ⚠️ 必须校验 review_status：申请会写进 job_applications 并给学员加积分，
    若允许对未审核/不存在的岗位申请，等于绕过了审核门禁（2026-10-06 修复）。
    """
    conn = get_connection()
    row = conn.execute("SELECT review_status FROM job_listings WHERE id = ?", (job_id,)).fetchone()
    if not row or (row['review_status'] or '') != 'approved':
        conn.close()
        return 'unavailable'
    existing = conn.execute("SELECT 1 FROM job_applications WHERE user_id = ? AND job_id = ?",
                            (user_id, job_id)).fetchone()
    if existing:
        conn.close()
        return 'dup'
    conn.execute("INSERT INTO job_applications (user_id, job_id) VALUES (?, ?)", (user_id, job_id))
    conn.commit()
    conn.close()
    return 'ok'


def get_job_by_id(job_id):
    """获取单条职位详情"""
    conn = get_connection()
    row = conn.execute("SELECT * FROM job_listings WHERE id = ?", (job_id,)).fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    d['requirements'] = json.loads(d['requirements'])
    return d


#### 企业岗位分类（学员端下拉 + 条数统计的口径来源）####
# ⚠️ 必须与 index.html 里 `#emp-category-filter` 的静态 <optgroup label="企业招聘岗位"> 保持一致
#    （静态项只是老后端/无脚本时的回退）。这里刻意把「当前 0 条」的分类也列出来，
#    前端会标成「（暂无）」—— 直接把死分类从下拉里藏掉，反而让人以为平台不支持这类岗位。
ENTERPRISE_JOB_CATEGORIES = ['农业技术', '电商运营', '手工工艺', '乡村旅游', '物流仓储']


#### 薪资区间解析（学员端薪资筛选用） ####
# 把「5K-8K」「5000-8000」「1万-1.5万」「2040元/月」里的数字抠出来。
# ⚠️ 只认 **≥100** 的数：否则「试用期2个月」里的 2 会被当成薪资，
#    把一条本来解析不出薪资的文本变成 (2, 2) 的假区间。
_SALARY_NUM_RE = re.compile(r'(\d+(?:\.\d+)?)\s*([kK千万元]?)')
_SALARY_MIN_ABS = 100.0


def parse_salary_bounds(text):
    """把一段薪资文本解析成 `(下界, 上界)`，解析不出来返回 None。

    · `5K-8K`      -> (5000, 8000)
    · `4K-6K`      -> (4000, 6000)
    · `5000-8000`  -> (5000, 8000)
    · `1万-1.5万`   -> (10000, 15000)
    · `12000+`     -> (12000, None)   ← 上界未知
    · `2040元/月`   -> (2040, 2040)
    · `面议` / 空 / 含数字但都不像薪资 -> None
    """
    if text is None:
        return None
    nums = []
    for m in _SALARY_NUM_RE.finditer(str(text)):
        v = float(m.group(1))
        unit = m.group(2)
        if unit in ('k', 'K', '千'):
            v *= 1000
        elif unit == '万':
            v *= 10000
        if v >= _SALARY_MIN_ABS:
            nums.append(v)
    if not nums:
        return None
    if len(nums) == 1:
        # `12000+` / `5K以上` 这类开放上界；其余单值按「恰好这个数」处理
        if '+' in str(text) or '以上' in str(text):
            return (nums[0], None)
        return (nums[0], nums[0])
    return (min(nums), max(nums))


def _salary_matches(job_salary, want_bounds):
    """岗位薪资与筛选区间必须有**长度大于 0 的交集**才算命中。

    ⚠️ 旧实现是 `salary LIKE '%5000%'`，而 `job_listings.salary` 存的是 `5K-8K`
    → **永远匹配不上**，学员选任意薪资都会得到 0 条（2026-10-07 实测）。

    为什么不用「端点相触也算」：三个可选区间是 3K-5K / 5K-8K / 8K-12K，彼此共用端点。
    若把 5K 既算进「3K-5K」又算进「5K-8K」，学员选「3K-5K」会看到一张写着「5K-8K」的
    卡片 —— 薪资数字明晃晃地对不上（卡片本身会显示薪资），比漏掉更让人困惑。
    所以：区间有真实重叠才命中。
    解析不出薪资（如「面议」）的岗位**不参与薪资筛选**，不静默算成 0。
    """
    if not want_bounds:
        return True
    jb = parse_salary_bounds(job_salary)
    if not jb:
        return False
    jmin, jmax = jb
    wmin, wmax = want_bounds

    if jmin == jmax:            # 岗位只给了一个确切数字（如「2040元/月」）
        return jmin >= wmin if wmax is None else (wmin <= jmin <= wmax)
    if jmax is None:            # 岗位「X 以上」
        return True if wmax is None else (jmin < wmax)
    if wmax is None:            # 筛选「X 以上」
        return jmax > wmin
    return max(jmin, wmin) < min(jmax, wmax)


def get_job_listings_base(keyword=None, location=None, salary_range=None):
    """企业岗位基础集合：应用 关键词 / 地点 / 薪资，**不应用分类**。

    分类单独一步做，是为了让前端的下拉能显示「每个分类各有多少条」
    —— 若在这里就把 category 过滤掉，统计永远只剩当前选中项（条数全是 1）。
    """
    conn = get_connection()
    query = "SELECT * FROM job_listings WHERE review_status = 'approved'"
    params = []
    if keyword:
        query += " AND (title LIKE ? OR company LIKE ? OR description LIKE ?)"
        params.extend([f'%{keyword}%', f'%{keyword}%', f'%{keyword}%'])
    if location:
        query += " AND location = ?"
        params.append(location)
    query += " ORDER BY posted_at DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()

    want = parse_salary_bounds(salary_range) if salary_range else None
    result = []
    for r in rows:
        d = dict(r)
        if not _salary_matches(d.get('salary'), want):
            continue
        d['requirements'] = json.loads(d['requirements'])
        result.append(d)
    return result


def get_job_category_counts(keyword=None, location=None, salary_range=None):
    """`{分类: 条数}`，口径与 `get_job_listings_base()` 完全一致（不含分类过滤）。"""
    counts = {}
    for j in get_job_listings_base(keyword, location, salary_range):
        cat = (j.get('category') or '').strip() or '未分类'
        counts[cat] = counts.get(cat, 0) + 1
    return counts


def get_job_listings_filtered(keyword=None, location=None, salary_range=None, category=None):
    """按条件筛选职位（**学员端公开接口专用**）。

    ⚠️ 这里必须过滤 `review_status='approved'`：企业发布的岗位初始为 `pending`，
    只有管理员审核通过后才应出现在学员端。此前 SQL 是 `WHERE 1=1`，
    导致**未审核岗位发布即可见**、内容审核形同虚设（2026-10-06 修复）。
    历史遗留行的 review_status 默认即 `'approved'`，不受影响；
    取值用 `= 'approved'`（fail-closed：万一为 NULL 也不会漏出）。
    """
    result = get_job_listings_base(keyword, location, salary_range)
    if category:
        result = [j for j in result if (j.get('category') or '') == category]
    return result


def count_pending_job_listings():
    """尚未通过审核（待审 / 已驳回）的企业岗位条数。

    学员端拿不到这些岗位，所以当它们在库里占满全部企业岗位时，
    列表会出现「一条企业岗都没有」的现象。前端需要据此说明
    「不是平台没有岗位，而是岗位正在审核中」——
    否则学员只会看到一句「未找到匹配的职位」，以为平台是空的。
    """
    conn = get_connection()
    n = conn.execute(
        "SELECT COUNT(*) FROM job_listings WHERE COALESCE(review_status, '') != 'approved'"
    ).fetchone()[0]
    conn.close()
    return n


def get_similar_jobs(job_id, category, limit=3):
    """获取同分类相似职位（同样只返回已通过审核的，避免从"相似职位"绕出未审核岗位）"""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM job_listings WHERE category = ? AND id != ? AND review_status = 'approved' LIMIT ?",
        (category, job_id, limit)).fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d['requirements'] = json.loads(d['requirements'])
        result.append(d)
    return result


def save_job(user_id, job_id):
    """收藏职位"""
    conn = get_connection()
    try:
        conn.execute("INSERT INTO saved_jobs (user_id, job_id) VALUES (?, ?)", (user_id, job_id))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        conn.close()
        return False


def unsave_job(user_id, job_id):
    """取消收藏"""
    conn = get_connection()
    conn.execute("DELETE FROM saved_jobs WHERE user_id = ? AND job_id = ?", (user_id, job_id))
    conn.commit()
    conn.close()
    return True


def get_saved_jobs(user_id):
    """获取用户收藏的职位ID列表"""
    conn = get_connection()
    rows = conn.execute("SELECT job_id FROM saved_jobs WHERE user_id = ?", (user_id,)).fetchall()
    conn.close()
    return [r['job_id'] for r in rows]


def get_user_applications(user_id, status_filter=None):
    """获取用户投递记录（含职位详情）"""
    conn = get_connection()
    if status_filter and status_filter != 'all':
        rows = conn.execute("""
            SELECT ja.id, ja.user_id, ja.job_id, ja.status, ja.applied_at,
                   jl.title, jl.company, jl.salary, jl.location, jl.category, jl.enterprise_id
            FROM job_applications ja
            JOIN job_listings jl ON ja.job_id = jl.id
            WHERE ja.user_id = ? AND ja.status = ?
            ORDER BY ja.applied_at DESC
        """, (user_id, status_filter)).fetchall()
    else:
        rows = conn.execute("""
            SELECT ja.id, ja.user_id, ja.job_id, ja.status, ja.applied_at,
                   jl.title, jl.company, jl.salary, jl.location, jl.category, jl.enterprise_id
            FROM job_applications ja
            JOIN job_listings jl ON ja.job_id = jl.id
            WHERE ja.user_id = ?
            ORDER BY ja.applied_at DESC
        """, (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_application_counts(user_id):
    """获取各状态投递计数"""
    conn = get_connection()
    total = conn.execute("SELECT COUNT(*) FROM job_applications WHERE user_id = ?", (user_id,)).fetchone()[0]
    pending = conn.execute("SELECT COUNT(*) FROM job_applications WHERE user_id = ? AND status = 'pending'", (user_id,)).fetchone()[0]
    approved = conn.execute("SELECT COUNT(*) FROM job_applications WHERE user_id = ? AND status = 'approved'", (user_id,)).fetchone()[0]
    rejected = conn.execute("SELECT COUNT(*) FROM job_applications WHERE user_id = ? AND status = 'rejected'", (user_id,)).fetchone()[0]
    conn.close()
    return {'total': total, 'pending': pending, 'approved': approved, 'rejected': rejected}


def get_employment_stats(user_id):
    """获取就业模块快捷统计"""
    conn = get_connection()
    applied = conn.execute("SELECT COUNT(*) FROM job_applications WHERE user_id = ?", (user_id,)).fetchone()[0]
    saved = conn.execute("SELECT COUNT(*) FROM saved_jobs WHERE user_id = ?", (user_id,)).fetchone()[0]
    intents = conn.execute("SELECT COUNT(*) FROM job_intents WHERE user_id = ?", (user_id,)).fetchone()[0]
    conn.close()
    return {'applied': applied, 'saved': saved, 'intents': intents, 'messages': 0}


# ==================== 就业对接：能力档案 / 在线简历 / 求职意向 ====================

# 简历可写字段白名单。`ai_used` 刻意不在其中 —— 它只能由 AI 生成接口置位，
# 否则学员可以传 ai_used=0 伪装成「完全自己写的」。
RESUME_FIELDS = ('title', 'region', 'education', 'work_years', 'phone', 'email',
                 'self_eval', 'skills', 'experience')


def get_learner_profile(user_id):
    """聚合学员的**真实**学习数据，作为「能力档案」与 AI 简历的唯一素材来源。

    ⚠️ 每一项都必须来自库里真实存在的数据，**代码不得补默认值凑数**：
    这些数据会原样交给 AI 当写作素材，凭空补的默认值等于让 AI 编造。
    某项没有数据就返回空列表 / 0，由前端决定「暂无」怎么呈现（宁缺勿编）。
    """
    conn = get_connection()
    profile = {
        'basic': {}, 'certificates': [], 'points': 0,
        'learning': None, 'training': [],
    }

    u = conn.execute(
        "SELECT username, name, email, phone, bio, region FROM users WHERE username = ?",
        (user_id,)).fetchone()
    if u:
        profile['basic'] = {
            'username': u['username'], 'name': u['name'] or '',
            'email': u['email'] or '', 'phone': u['phone'] or '',
            'bio': u['bio'] or '', 'region': u['region'] or '',
        }

    # 证书：只有 status='earned' 才算「已获得」，其余如实带出状态
    #（否则 AI 会把「进行中 75%」的证书写成「已获得」，属于事实性错误）
    for r in conn.execute(
            "SELECT name, status, progress, date FROM certificates WHERE user_id = ? ORDER BY id",
            (user_id,)):
        profile['certificates'].append({
            'name': r['name'], 'status': r['status'],
            'earned': (r['status'] == 'earned'),
            'progress': r['progress'] or 0, 'date': r['date'] or '',
        })

    p = conn.execute("SELECT balance FROM points WHERE user_id = ?", (user_id,)).fetchone()
    if p:
        profile['points'] = p['balance'] or 0

    # 学习进度：历史数据里 students.user_id 常为空串，故用姓名兜底匹配
    name = profile['basic'].get('name') or ''
    st = conn.execute(
        "SELECT direction, progress FROM students "
        "WHERE user_id = ? OR (name <> '' AND name = ?) LIMIT 1",
        (user_id, name)).fetchone()
    if st:
        profile['learning'] = {'direction': st['direction'] or '',
                               'progress': st['progress'] or 0}

    # 实训成绩：assignment_submissions.student_id 存的是 username。
    # ⚠️ score 列 = **教师批改分**（2026-10-07 起语义变更，系统规则分存 content.rule_score）。
    #    未批改时为 NULL → scored=False，让 AI 说「待老师批改」，绝不能把规则分或 0 说成成绩。
    for r in conn.execute("""
            SELECT a.title, s.score, s.status, s.submitted_at
              FROM assignment_submissions s
              LEFT JOIN assignments a ON s.assignment_id = a.id
             WHERE s.student_id = ?
             ORDER BY s.submitted_at DESC LIMIT 10
    """, (user_id,)):
        score = r['score']
        graded = isinstance(score, int)
        profile['training'].append({
            'title': (r['title'] or '实训作业'),
            'score': score if graded else None,
            'scored': graded,
            'status': r['status'] or '',
            'submitted_at': r['submitted_at'] or '',
        })

    conn.close()
    return profile


def get_resume(user_id):
    """读取学员的在线简历（没有则返回 None）。experience 解析为列表。"""
    conn = get_connection()
    row = conn.execute("SELECT * FROM resumes WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    try:
        d['experience'] = json.loads(d.get('experience') or '[]')
    except Exception:
        d['experience'] = []
    return d


def save_resume(user_id, data):
    """新增或更新在线简历（一人一份），返回保存后的记录。

    ⚠️ 只接受 RESUME_FIELDS 白名单字段（防越权改写 user_id / ai_used）。
    ⚠️ 更新时用 UPDATE 而非「先删后插」，否则 id 会变、创建时间会丢。
    """
    existing = get_resume(user_id)
    payload = {}
    for k in RESUME_FIELDS:
        if k not in data:
            continue
        v = data[k]
        if k == 'experience':
            clean = []
            for item in (v if isinstance(v, list) else [])[:20]:
                if not isinstance(item, dict):
                    continue
                clean.append({
                    'company': str(item.get('company') or '')[:100],
                    'position': str(item.get('position') or '')[:100],
                    'period': str(item.get('period') or '')[:50],
                    'desc': str(item.get('desc') or '')[:2000],
                })
            payload[k] = json.dumps(clean, ensure_ascii=False)
        else:
            payload[k] = str(v or '')[:5000]

    conn = get_connection()
    if not existing:
        cols = ['user_id'] + list(payload.keys())
        vals = [user_id] + list(payload.values())
        conn.execute(
            "INSERT INTO resumes (%s) VALUES (%s)" % (', '.join(cols), ', '.join('?' * len(cols))),
            vals)
    elif payload:
        sets = ', '.join('%s = ?' % c for c in payload)
        conn.execute(
            "UPDATE resumes SET %s, updated_at = datetime('now','localtime') WHERE user_id = ?" % sets,
            list(payload.values()) + [user_id])
    conn.commit()
    conn.close()
    return get_resume(user_id)


def mark_resume_ai_used(user_id):
    """把简历标记为「使用过 AI 辅助」。前端据此如实提示，不隐瞒 AI 参与。"""
    conn = get_connection()
    row = conn.execute("SELECT id FROM resumes WHERE user_id = ?", (user_id,)).fetchone()
    if row:
        conn.execute("UPDATE resumes SET ai_used = 1, updated_at = datetime('now','localtime') "
                     "WHERE user_id = ?", (user_id,))
    else:
        conn.execute("INSERT INTO resumes (user_id, ai_used) VALUES (?, 1)", (user_id,))
    conn.commit()
    conn.close()


def add_job_intent(user_id, recruit_key, note=''):
    """登记对某条公开招聘公告的求职意向（幂等，重复登记只更新备注）。

    返回 True 表示新建、False 表示更新已有。
    ⚠️ 这里**只记录意向**，不代表报名成功 —— 报名由学员按公告原文自行完成。
    """
    conn = get_connection()
    row = conn.execute("SELECT id FROM job_intents WHERE user_id = ? AND recruit_key = ?",
                       (user_id, recruit_key)).fetchone()
    if row:
        conn.execute("UPDATE job_intents SET note = ? WHERE id = ?",
                     (str(note or '')[:500], row['id']))
        created = False
    else:
        conn.execute("INSERT INTO job_intents (user_id, recruit_key, note) VALUES (?, ?, ?)",
                     (user_id, recruit_key, str(note or '')[:500]))
        created = True
    conn.commit()
    conn.close()
    return created


def remove_job_intent(user_id, recruit_key):
    """取消求职意向登记。返回 True 表示确有记录被删除。"""
    conn = get_connection()
    cur = conn.execute("DELETE FROM job_intents WHERE user_id = ? AND recruit_key = ?",
                       (user_id, recruit_key))
    affected = cur.rowcount
    conn.commit()
    conn.close()
    return affected > 0


def get_job_intents(user_id):
    """获取学员登记的全部求职意向（按登记时间倒序）。"""
    conn = get_connection()
    rows = conn.execute(
        "SELECT recruit_key, note, created_at FROM job_intents "
        "WHERE user_id = ? ORDER BY created_at DESC, id DESC", (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ==================== 资源 ====================

# 成功案例的审核类型标识（走通用 content_reviews 链路，与 course/job/procurement/model_3d 同级）
CASE_REVIEW_TYPE = 'success_case'


def get_success_cases(only_approved=True):
    """获取成功案例

    内容唯一事实源 = cases_data.py（不读数据库）。
    按 pest_data.py 的既有约定：改完 cases_data.py 重启服务即生效，无需 init_db()。

    ⚠️ 审核：案例需经**超级管理员**审核通过才对学员端可见。
    审核状态复用 `content_reviews`（`content_type='success_case'`、`content_id=案例 id`），
    由 `_seed_case_reviews()` 在 init_db() 时为每条案例补一条 pending 记录。
    `only_approved=False` 仅给管理端/自检用（看到含未通过的全部案例）。
    """
    import cases_data
    cases = cases_data.get_cases()
    if not only_approved:
        return cases
    conn = get_connection()
    rows = conn.execute(
        "SELECT content_id FROM content_reviews WHERE content_type = ? AND status = 'approved'",
        (CASE_REVIEW_TYPE,)).fetchall()
    conn.close()
    approved = {r['content_id'] for r in rows}
    return [c for c in cases if c['id'] in approved]


def get_case_review_stats():
    """案例审核统计（供前端区分"审核中"与"加载失败"，避免把待审当成没数据）。"""
    import cases_data
    cases = cases_data.get_cases()
    valid = {c['id'] for c in cases}
    total = len(cases)

    conn = get_connection()
    rows = conn.execute(
        "SELECT content_id, status, COUNT(*) AS n FROM content_reviews "
        "WHERE content_type = ? GROUP BY content_id, status",
        (CASE_REVIEW_TYPE,)).fetchall()
    conn.close()

    stat = {'approved': 0, 'pending': 0, 'rejected': 0}
    covered = 0
    for r in rows:
        if r['content_id'] not in valid:
            continue          # 已被 cases_data 删掉的案例，不计入
        covered += r['n']
        if r['status'] in stat:
            # 查询按 (content_id, status) 分组 —— 这里必须**累加**，不能赋值
            stat[r['status']] += r['n']

    stat['total'] = total
    # 还没有任何审核记录的案例（如刚加进 cases_data.py、尚未跑过 init_db）一律按待审计。
    # ⚠️ 这里必须用 total - covered（未被覆盖的数），不能只减 approved/rejected ——
    #    否则已计入 pending 的行会被重复统计（混合状态时 pending 虚高）。
    stat['pending'] += max(0, total - covered)
    return {'case_review': stat}


def get_case_notes():
    """案例页口径说明文案（与内容同源，避免前端硬编码漂移）。"""
    import cases_data
    return {
        "source_note": cases_data.CASE_SOURCE_NOTE,
        "lessons_note": cases_data.LESSONS_NOTE,
    }


def get_policy_notes():
    """政策页口径说明文案（来源说明 + 免责声明，与内容同源）。"""
    import policies_data
    return policies_data.get_policy_notes()


# ---- 政策分类归一化 ----
# ⚠️ 政府端发布表单里「综合」那一项的 value 是**英文** general
#    （government.html: `<option value="general">综合</option>`），
#    而后端原先不做任何归一化、直接入库。
#    学员端的分类筛选按钮与标签配色都按**中文**分类走 →
#    结果是：学员会看到一张标签写着英文「general」、底色还是「补贴」绿的政策卡片，
#    而且点任何分类筛选都找不到它（界面看起来像这条政策凭空消失了）。
#    历史库里已经可能存有 general，故在 getter 收口处（_attach_policy_sources）也归一化一次。
_POLICY_CATEGORY_ALIASES = {
    'general': '综合',
    'other': '综合',
    '综合': '综合',
    '其他': '综合',
}


def normalize_policy_category(value):
    """把政策分类归一化成面向学员的中文分类。

    未知分类**原样返回**（不臆造、不强行塞进已有分类）——
    真实出现了新分类时，前端会按数据动态生成对应的筛选项。
    """
    v = str(value or '').strip()
    if not v:
        return '综合'
    return _POLICY_CATEGORY_ALIASES.get(v.lower(), v)


def _attach_policy_sources(d):
    """把 policy 行的 source 字段（JSON 文本）解析成 sources 列表，供前端直接渲染出处。"""
    raw = d.pop('source', '') or ''
    try:
        d['sources'] = json.loads(raw) if raw else []
    except (ValueError, TypeError):
        d['sources'] = []
    # 分类归一化也放在这里：本函数是**所有**政策 getter 的公共收口
    # （get_policies / get_government_policies / get_all_government_policies / get_policy_by_id），
    # 在这里统一处理，历史脏数据（category='general'）无需迁移即可被修正。
    d['category'] = normalize_policy_category(d.get('category'))
    return d


# ---- 政府端政策输入归一化 ----
# 政府端表单收的是「人写的文本」，落库前统一转成学员端渲染器认识的形状。
# ⚠️ 这三个函数是**唯一**的转换入口：create_policy / update_policy 都从这里过，
#    别在 app.py 里另写一份（历史坑：写入侧与读取侧对同一列的理解不一致）。

def policy_sources_to_json(text):
    """把「资料来源」文本框转成 source 列要的 JSON 数组。

    约定：一行一条来源，写作 `来源名称` 或 `来源名称 | URL`。
    · 空输入 → `[]`（**宁缺勿编**：学员端据此不显示「文号与数据均可溯源」的口径说明，
      因为那条口径是对来源区块的背书，没有来源就不成立）；
    · URL 必须是 http(s)，否则只留名称（前端也能渲染成纯文本）。
    """
    items = []
    for line in str(text or '').splitlines():
        line = line.strip()
        if not line:
            continue
        parts = [x.strip() for x in line.split('|')]
        title = parts[0]
        if not title:
            continue
        item = {'title': title}
        url = parts[1] if len(parts) > 1 else ''
        if re.match(r'^https?://', url, re.I):
            item['url'] = url
        items.append(item)
    return json.dumps(items, ensure_ascii=False)


def default_policy_summary(content, limit=60):
    """摘要留空时，从**正文自己**取首段（不是另写一句通用话术）。

    跳过 `【小标题】` 行与 `•`/`-` 列表符号行，取第一段真正的正文；
    超长才省略号。正文为空则返回空串 —— 此时学员端卡片不渲染摘要行（不用占位充数）。
    """
    for line in str(content or '').splitlines():
        s = line.strip().lstrip('•-').strip()
        if not s or (s.startswith('【') and s.endswith('】')):
            continue
        return s[:limit] + ('…' if len(s) > limit else '')
    return ''


def get_policies():
    """获取政策"""
    conn = get_connection()
    rows = conn.execute("SELECT * FROM policies").fetchall()
    conn.close()
    return [_attach_policy_sources(dict(r)) for r in rows]


# ==================== 教师仪表板 ====================

def get_dashboard_stats():
    """获取教师仪表板统计（口径：教师名册表 students + 证书真实完成度）。

    2026-10-07 修正（两处）：
    ① 原实现把 certificates **全表**（含教师本人等非学员的证书）当作「学员已获证书」，
       现改为只统计名册中**已关联平台账号**（students.user_id = username）的学员证书；
       完成率 = 名册中至少获得 1 张证书的学员占比。
    ② avg_score（界面文案「平均进度」）原取 students.progress 的平均值 —— 那是**手填**
       字段，学员端没有任何入口会更新它。现改用证书真实完成度（见 get_roster_completion）。
    """
    roster = get_roster_completion()
    total = len(roster)
    earned = sum(r['cert_earned'] for r in roster)
    with_cert = sum(1 for r in roster if r['cert_earned'] > 0)
    with_data = [r for r in roster if r['has_cert_data']]
    avg_completion = (sum(r['completion'] for r in with_data) / len(with_data)) if with_data else 0
    return {
        "total_students": total,
        "certificates_earned": earned,
        "completion_rate": int(with_cert / total * 100) if total > 0 else 0,
        "avg_score": int(round(avg_completion)),
        "no_cert_count": total - len(with_data)
    }

# ==================== 用户注册和管理 ====================

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


def get_user_by_id(user_id):
    """根据用户名获取用户信息"""
    conn = get_connection()
    user = conn.execute("SELECT * FROM users WHERE username = ?", (user_id,)).fetchone()
    conn.close()
    return dict(user) if user else None


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


# 「业务关联」= 删掉用户后会变成跨表孤儿、而删除逻辑本身**不会**清理的表。
# ⚠️ user_sessions / points 由 delete_user_by_admin 自己清理，不计入。
# ⚠️ students.user_id 是最要命的一条：它是名册收件人与证书归属的唯一依据。
_USER_RELATION_SPECS = [
    ("students", "user_id", "名册记录"),
    ("certificates", "user_id", "证书"),
    ("job_applications", "user_id", "岗位投递"),
    ("resumes", "user_id", "简历"),
    ("notifications", "user_id", "通知"),
    ("discussions", "user_id", "讨论帖"),
    ("comments", "user_id", "评论"),
    ("messages", "sender_id", "发出的消息"),
    ("messages", "receiver_id", "收到的消息"),
    ("farming_subscriptions", "user_id", "农事订阅"),
    ("farming_reminder_log", "user_id", "农事提醒记录"),
    ("job_intents", "user_id", "求职意向"),
    ("saved_jobs", "user_id", "收藏的岗位"),
    ("assignment_submissions", "student_id", "作业提交"),
    ("content_reviews", "submitter_id", "提交的内容审核"),
    ("content_reviews", "reviewed_by", "处理过的审核"),
    ("government_policies", "author_id", "发布的政策"),
    ("job_listings", "enterprise_id", "发布的岗位"),
    ("models_3d", "teacher_id", "上传的3D模型"),
    ("courses", "teacher_id", "创建的课程"),
    ("system_announcements", "created_by", "发布的公告"),
]


def count_user_relations(username):
    """统计用户在各业务表里的引用条数，用于「能不能删」的判断。

    返回 {'total': int, 'items': [{'table','column','label','count'}]}（只含 count>0 的项）。

    只统计**真实存在的列**：不同库的表结构有差异，缺列的表静默跳过，
    不让一次 schema 漂移把整个删除功能打挂。
    """
    conn = get_connection()
    items = []
    total = 0
    for table, column, label in _USER_RELATION_SPECS:
        try:
            cols = [r[1] for r in conn.execute("PRAGMA table_info(%s)" % table)]
        except Exception:
            continue
        if column not in cols:
            continue
        try:
            n = conn.execute(
                "SELECT COUNT(*) FROM %s WHERE %s = ?" % (table, column), (username,)).fetchone()[0]
        except Exception:
            continue
        if n:
            items.append({"table": table, "column": column, "label": label, "count": n})
            total += n
    conn.close()
    items.sort(key=lambda x: -x["count"])
    return {"total": total, "items": items}


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

    ⚠️ 三条硬约束：
      1. **只输出真实可算的口径**。在线人数 / 日活 / 近 N 天趋势 / 平均审核时长
         一律不输出 —— 我们没有在线状态表、没有埋点、没有访问日志，
         硬凑出来的数字就是编造。宁可少几张卡。
      2. **成功案例正文不落库**（内容在 cases_data.py），本函数不查表，
         cases 条数由路由层用 `cases_data.get_cases()` 补。
      3. 查不到的项给 **None 而不是 0**，前端 None 时整张卡不渲染（不补 0）。
    """
    conn = get_connection()

    def _cnt(table, where=None, col=None):
        """计数；表/列不存在或查询失败一律返回 None（前端据此不渲染该卡）。"""
        try:
            if col is not None:
                cols = [r[1] for r in conn.execute("PRAGMA table_info(%s)" % table)]
                if col not in cols:
                    return None
            sql = "SELECT COUNT(*) AS n FROM %s" % table
            if where:
                sql += " WHERE " + where
            return conn.execute(sql).fetchone()["n"]
        except Exception:
            return None

    ov = {"users": {}, "reviews": {}, "content": {}}

    ov["users"]["total"] = _cnt("users")
    try:
        for r in conn.execute("SELECT role, COUNT(*) AS n FROM users GROUP BY role"):
            ov["users"][r["role"]] = r["n"]
    except Exception:
        pass
    ov["users"]["suspended"] = _cnt("users", "status='suspended'")

    for st in ("pending", "approved", "rejected"):
        ov["reviews"][st] = _cnt("content_reviews", "status='%s'" % st)

    ov["reviews"]["oldest_pending_at"] = None
    ov["reviews"]["oldest_pending_days"] = None
    try:
        row = conn.execute(
            "SELECT MIN(created_at) AS t FROM content_reviews WHERE status='pending'").fetchone()
        t = row["t"] if row else None
        if t:
            ov["reviews"]["oldest_pending_at"] = t
            try:
                ov["reviews"]["oldest_pending_days"] = (
                    datetime.now() - datetime.strptime(str(t)[:19], "%Y-%m-%d %H:%M:%S")).days
            except Exception:
                pass
    except Exception:
        pass

    ov["content"]["jobs"] = _cnt("job_listings")
    ov["content"]["jobs_published"] = _cnt("job_listings", "review_status='approved'", "review_status")
    ov["content"]["models"] = _cnt("models_3d")
    ov["content"]["policies"] = _cnt("government_policies")
    ov["content"]["policies_published"] = _cnt("government_policies", "is_published=1", "is_published")
    ov["content"]["courses"] = _cnt("courses")

    conn.close()
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
    cur.execute("DELETE FROM user_sessions WHERE user_id = ?", (user_id,))
    cur.execute("DELETE FROM points WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    return n


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

def create_content_review(content_type, content_id, submitter_id):
    """创建内容审核记录"""
    conn = get_connection()
    conn.execute(
        "INSERT INTO content_reviews (content_type, content_id, submitter_id) VALUES (?, ?, ?)",
        (content_type, content_id, submitter_id))
    conn.commit()
    conn.close()


def get_pending_reviews(content_type=None):
    """获取待审核列表"""
    conn = get_connection()
    if content_type:
        rows = conn.execute(
            "SELECT * FROM content_reviews WHERE status = 'pending' AND content_type = ? ORDER BY created_at DESC",
            (content_type,)).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM content_reviews WHERE status = 'pending' ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def approve_review(review_id, reviewer_id):
    """审核通过"""
    conn = get_connection()
    # ⚠️ 必须清掉 review_comment：一条记录可能「先驳回、再撤销、后通过」，
    #    若不清，已通过的卡片上会残留上一轮的驳回理由（2026-10-08 复验时
    #    在 success_case#1 上实测到「理由: 自审：临时驳回」，出现在「已通过」状态
    #    下极易被误读为「通过了但有驳回意见」）。
    conn.execute(
        "UPDATE content_reviews SET status='approved', reviewed_by=?, review_comment='', "
        "reviewed_at=datetime('now','localtime') WHERE id=?",
        (reviewer_id, review_id))
    review = conn.execute("SELECT * FROM content_reviews WHERE id=?", (review_id,)).fetchone()
    if review:
        ct, cid = review['content_type'], review['content_id']
        # 注：success_case 不需要回写目标表 —— 案例内容在 cases_data.py，
        #     「是否可见」完全由这张 content_reviews 的 status 决定（见 get_success_cases）。
        if ct == 'course':
            conn.execute("UPDATE courses SET review_status='approved', is_published=1 WHERE id=?", (cid,))
        elif ct == 'job':
            conn.execute("UPDATE job_listings SET review_status='approved' WHERE id=?", (cid,))
        elif ct == 'procurement':
            conn.execute("UPDATE procurements SET review_status='approved' WHERE id=?", (cid,))
        elif ct == 'model_3d':
            conn.execute("UPDATE models_3d SET review_status='approved', is_published=1 WHERE id=?", (cid,))
    conn.commit()
    conn.close()


def reject_review(review_id, reviewer_id, comment=''):
    """审核拒绝。

    ⚠️ 必须与 `approve_review()` **对称地回写目标表的 `review_status`** ——
       此前只改 content_reviews，导致岗位被驳回后企业端一直显示「待审核」，
       企业会以为还在排队等审（2026-10-07 修）。`success_case` 仍不需要回写，
       它的可见性完全由本表的 status 决定（见 `get_success_cases`）。
    """
    conn = get_connection()
    conn.execute(
        "UPDATE content_reviews SET status='rejected', reviewed_by=?, review_comment=?, reviewed_at=datetime('now','localtime') WHERE id=?",
        (reviewer_id, comment, review_id))
    review = conn.execute("SELECT * FROM content_reviews WHERE id=?", (review_id,)).fetchone()
    if review:
        ct, cid = review['content_type'], review['content_id']
        if ct == 'course':
            conn.execute("UPDATE courses SET review_status='rejected' WHERE id=?", (cid,))
        elif ct == 'job':
            conn.execute("UPDATE job_listings SET review_status='rejected' WHERE id=?", (cid,))
        elif ct == 'procurement':
            conn.execute("UPDATE procurements SET review_status='rejected' WHERE id=?", (cid,))
        elif ct == 'model_3d':
            conn.execute("UPDATE models_3d SET review_status='rejected' WHERE id=?", (cid,))
    conn.commit()
    conn.close()


def get_reviews_by_status(status=None, content_type=None, sort='modified'):
    """按状态取审核记录（status 为空 = 全部）。

    2026-10-08 新增：管理端「内容审核」需要回看已通过 / 已驳回的历史，
    而 `get_pending_reviews()` 的 SQL 写死 `status='pending'`，历史记录一条都
    查不出来 —— 页面里那套「已通过/已驳回」徽标分支因此永远走不到。

    sort（2026-10-10 新增，管理端排序下拉框）：
      · 'modified'（默认）按「最后修改时间」倒序，取最近一次审核动作的
        reviewed_at；没审过、或撤销后 reviewed_at 被清空的，退回 created_at；
      · 'created' 按提交时间倒序。
    两者都用 id 兜底拆同秒戳（种子数据常在同一秒创建多条，只按时间排会随机）。
    """
    conn = get_connection()
    sql = "SELECT * FROM content_reviews WHERE 1=1"
    params = []
    if status:
        sql += " AND status = ?"
        params.append(status)
    if content_type:
        sql += " AND content_type = ?"
        params.append(content_type)
    if sort == 'created':
        sql += " ORDER BY created_at DESC, id DESC"
    else:
        sql += " ORDER BY COALESCE(reviewed_at, created_at) DESC, id DESC"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def count_reviews_by_status(content_type=None):
    """各状态的审核记录条数（供页签显示数量）。三个 key 恒存在，缺失补 0。"""
    conn = get_connection()
    sql = "SELECT status, COUNT(*) AS n FROM content_reviews"
    params = []
    if content_type:
        sql += " WHERE content_type = ?"
        params.append(content_type)
    sql += " GROUP BY status"
    out = {r["status"]: r["n"] for r in conn.execute(sql, params).fetchall()}
    conn.close()
    for k in ("pending", "approved", "rejected"):
        out.setdefault(k, 0)
    return out


def revoke_review(review_id):
    """撤销审核：approved / rejected 退回 pending，并**对称回写**目标表。

    回写规则与 approve_review / reject_review 保持一致（success_case 不回写，
    它的可见性完全由 content_reviews.status 决定）。

    返回 'ok' / 'not_found'（没有这条记录）/ 'not_reviewed'（本来就是 pending）。
    """
    conn = get_connection()
    row = conn.execute("SELECT * FROM content_reviews WHERE id = ?", (review_id,)).fetchone()
    if not row:
        conn.close()
        return "not_found"
    if row["status"] == "pending":
        conn.close()
        return "not_reviewed"
    conn.execute(
        "UPDATE content_reviews SET status='pending', reviewed_by='', review_comment='', "
        "reviewed_at=NULL WHERE id=?", (review_id,))
    ct, cid = row["content_type"], row["content_id"]
    if ct == 'course':
        conn.execute("UPDATE courses SET review_status='pending' WHERE id=?", (cid,))
    elif ct == 'job':
        conn.execute("UPDATE job_listings SET review_status='pending' WHERE id=?", (cid,))
    elif ct == 'procurement':
        conn.execute("UPDATE procurements SET review_status='pending' WHERE id=?", (cid,))
    elif ct == 'model_3d':
        conn.execute("UPDATE models_3d SET review_status='pending' WHERE id=?", (cid,))
    conn.commit()
    conn.close()
    return "ok"


def get_review_by_content(content_type, content_id):
    """获取内容的审核记录"""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM content_reviews WHERE content_type=? AND content_id=? ORDER BY id DESC LIMIT 1",
        (content_type, content_id)).fetchone()
    conn.close()
    return dict(row) if row else None



# ==================== 系统公告 ====================

def get_system_announcements(active_only=True):
    """获取系统公告"""
    conn = get_connection()
    if active_only:
        rows = conn.execute(
            "SELECT * FROM system_announcements WHERE is_active=1 ORDER BY is_pinned DESC, created_at DESC"
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM system_announcements ORDER BY is_pinned DESC, created_at DESC"
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_system_announcement(title, content, is_pinned=0, created_by=''):
    """新增系统公告"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO system_announcements (title, content, is_pinned, created_by) VALUES (?, ?, ?, ?)",
        (title, content, is_pinned, created_by))
    conn.commit()
    ann_id = cursor.lastrowid
    conn.close()
    return ann_id


def delete_system_announcement(ann_id):
    """删除系统公告（软删除）"""
    conn = get_connection()
    conn.execute("UPDATE system_announcements SET is_active=0 WHERE id=?", (ann_id,))
    conn.commit()
    conn.close()
    return True


# ==================== 课程 ====================

def create_course(title, description, category, teacher_id, cover_url=''):
    """教师创建课程"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO courses (title, description, category, teacher_id, cover_url) VALUES (?, ?, ?, ?, ?)",
        (title, description, category, teacher_id, cover_url))
    conn.commit()
    course_id = cursor.lastrowid
    conn.close()
    # 创建审核记录
    create_content_review('course', course_id, teacher_id)
    return course_id


def get_courses(teacher_id=None, published_only=True):
    """获取课程列表"""
    conn = get_connection()
    query = "SELECT * FROM courses WHERE 1=1"
    params = []
    if teacher_id:
        query += " AND teacher_id = ?"
        params.append(teacher_id)
    if published_only:
        query += " AND is_published = 1"
    query += " ORDER BY created_at DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_course(course_id):
    """获取单个课程"""
    conn = get_connection()
    row = conn.execute("SELECT * FROM courses WHERE id = ?", (course_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_course(course_id, **kwargs):
    """更新课程"""
    conn = get_connection()
    allowed = {'title', 'description', 'category', 'cover_url'}
    updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
    if updates:
        set_clause = ', '.join(f"{k}=?" for k in updates)
        params = list(updates.values()) + [course_id]
        conn.execute(f"UPDATE courses SET {set_clause} WHERE id=?", params)
        conn.commit()
    conn.close()
    return True


def delete_course(course_id):
    """删除课程及关联素材"""
    conn = get_connection()
    conn.execute("DELETE FROM course_materials WHERE course_id = ?", (course_id,))
    conn.execute("DELETE FROM courses WHERE id = ?", (course_id,))
    conn.execute("DELETE FROM content_reviews WHERE content_type='course' AND content_id=?", (course_id,))
    conn.commit()
    conn.close()
    return True


# ==================== 课程素材 ====================

def add_course_material(course_id, material_type, file_name, file_path, file_size=0):
    """添加课程素材"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO course_materials (course_id, material_type, file_name, file_path, file_size) VALUES (?, ?, ?, ?, ?)",
        (course_id, material_type, file_name, file_path, file_size))
    conn.commit()
    mat_id = cursor.lastrowid
    conn.close()
    return mat_id


def get_course_materials(course_id):
    """获取课程素材列表"""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM course_materials WHERE course_id = ? ORDER BY sort_order", (course_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_course_material(mat_id):
    """删除课程素材"""
    conn = get_connection()
    row = conn.execute("SELECT file_path FROM course_materials WHERE id = ?", (mat_id,)).fetchone()
    conn.execute("DELETE FROM course_materials WHERE id = ?", (mat_id,))
    conn.commit()
    conn.close()
    return row['file_path'] if row else None


# ==================== 3D 模型 ====================

def create_model_3d(title, description, craft_type, file_path, file_name, file_size, teacher_id, thumbnail_url=''):
    """上传3D模型"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO models_3d (title, description, craft_type, file_path, file_name, file_size, thumbnail_url, teacher_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (title, description, craft_type, file_path, file_name, file_size, thumbnail_url, teacher_id))
    conn.commit()
    model_id = cursor.lastrowid
    conn.close()
    create_content_review('model_3d', model_id, teacher_id)
    return model_id


def get_models_3d(teacher_id=None, published_only=True):
    """获取3D模型列表"""
    conn = get_connection()
    query = "SELECT * FROM models_3d WHERE 1=1"
    params = []
    if teacher_id:
        query += " AND teacher_id = ?"
        params.append(teacher_id)
    if published_only:
        query += " AND is_published = 1"
    query += " ORDER BY created_at DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_model_3d(model_id):
    """删除3D模型"""
    conn = get_connection()
    row = conn.execute("SELECT file_path FROM models_3d WHERE id = ?", (model_id,)).fetchone()
    conn.execute("DELETE FROM models_3d WHERE id = ?", (model_id,))
    conn.execute("DELETE FROM content_reviews WHERE content_type='model_3d' AND content_id=?", (model_id,))
    conn.commit()
    conn.close()
    return row['file_path'] if row else None


# ==================== 评论 ====================

def add_comment(target_type, target_id, user_id, content):
    """添加评论"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO comments (target_type, target_id, user_id, content) VALUES (?, ?, ?, ?)",
        (target_type, target_id, user_id, content))
    conn.commit()
    comment_id = cursor.lastrowid
    # 更新讨论区评论计数
    if target_type == 'discussion':
        conn.execute("UPDATE discussions SET comment_count = comment_count + 1 WHERE id = ?", (target_id,))
        conn.commit()
    conn.close()
    return comment_id


def get_comments(target_type, target_id):
    """获取评论列表"""
    conn = get_connection()
    rows = conn.execute(
        """SELECT c.*, u.name as user_name, u.avatar_url
           FROM comments c LEFT JOIN users u ON c.user_id = u.username
           WHERE c.target_type = ? AND c.target_id = ? AND c.is_deleted = 0
           ORDER BY c.created_at ASC""",
        (target_type, target_id)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def soft_delete_comment(comment_id, deleted_by=''):
    """软删除评论"""
    conn = get_connection()
    conn.execute("UPDATE comments SET is_deleted=1, deleted_by=? WHERE id=?", (deleted_by, comment_id))
    conn.commit()
    conn.close()
    return True


# ==================== 讨论区 ====================

def create_discussion(title, content, category, user_id):
    """创建讨论帖"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO discussions (title, content, category, user_id) VALUES (?, ?, ?, ?)",
        (title, content, category, user_id))
    conn.commit()
    disc_id = cursor.lastrowid
    conn.close()
    return disc_id


def get_discussions(category=None, page=1, page_size=20):
    """获取讨论区列表（分页）"""
    conn = get_connection()
    query = "SELECT d.*, u.name as user_name FROM discussions d LEFT JOIN users u ON d.user_id = u.username WHERE d.is_deleted = 0"
    params = []
    if category:
        query += " AND d.category = ?"
        params.append(category)
    query += " ORDER BY d.is_pinned DESC, d.created_at DESC LIMIT ? OFFSET ?"
    params.extend([page_size, (page - 1) * page_size])
    rows = conn.execute(query, params).fetchall()
    total = conn.execute(
        "SELECT COUNT(*) FROM discussions WHERE is_deleted = 0" +
        (f" AND category = ?" if category else ""),
        (category,) if category else ()).fetchone()[0]
    conn.close()
    return [dict(r) for r in rows], total


def get_discussion(disc_id):
    """获取讨论详情"""
    conn = get_connection()
    conn.execute("UPDATE discussions SET view_count = view_count + 1 WHERE id = ?", (disc_id,))
    row = conn.execute(
        "SELECT d.*, u.name as user_name FROM discussions d LEFT JOIN users u ON d.user_id = u.username WHERE d.id = ?",
        (disc_id,)).fetchone()
    conn.commit()
    conn.close()
    return dict(row) if row else None


def soft_delete_discussion(disc_id):
    """软删除讨论帖"""
    conn = get_connection()
    conn.execute("UPDATE discussions SET is_deleted = 1 WHERE id = ?", (disc_id,))
    conn.commit()
    conn.close()
    return True


# ==================== 农产品求购 ====================

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
    create_content_review('procurement', proc_id, enterprise_id)
    return proc_id


def get_procurements(enterprise_id=None, status=None, published_only=True):
    """获取求购列表"""
    conn = get_connection()
    query = "SELECT p.*, u.company_name, u.region as enterprise_region FROM procurements p LEFT JOIN users u ON p.enterprise_id = u.username WHERE 1=1"
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
    return [dict(r) for r in rows]


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

def create_policy(title, content, category, author_id,
                  summary='', date='', source_text=''):
    """发布政策（政府端）。

    ⚠️ summary / date / source 必须一起写入（原实现只写 4 列）：
       学员端政策卡片会渲染「摘要」与「发布日期」两行，任一为空就整行不渲染；
       政府端刚发布的政策于是成了一张**没有摘要、没有日期、也没有资料来源**的残缺卡片，
       夹在 5 条预置政策（各有 32–42 字摘要 + 日期 + 4 条来源）中间格外突兀，
       点进详情还会看到「文号与数据均可溯源」这句**它并不具备**的背书。
    · summary 留空 → 取正文首段（default_policy_summary）；
    · date 留空 → 由调用方传当天（app.py），这里不再兜底，避免藏住"没填"这件事；
    · source_text 是表单原文（一行一条），在这里转成 source 列要的 JSON。
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO government_policies "
        "(title, content, category, author_id, summary, date, source) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (title, content, category, author_id,
         summary or default_policy_summary(content), date,
         policy_sources_to_json(source_text)))
    conn.commit()
    policy_id = cursor.lastrowid
    conn.close()
    return policy_id


def get_government_policies(category=None):
    """获取政府政策列表"""
    conn = get_connection()
    query = "SELECT * FROM government_policies WHERE is_published = 1"
    params = []
    if category:
        query += " AND category = ?"
        params.append(category)
    # 排序：政策发布日期优先；未填日期的（政府端新发布的）退回按发布时间
    query += " ORDER BY COALESCE(NULLIF(date, ''), substr(created_at, 1, 10)) DESC, id DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [_attach_policy_sources(dict(r)) for r in rows]


def get_all_government_policies():
    """获取所有政府政策（含未发布，政府端使用）"""
    conn = get_connection()
    rows = conn.execute("SELECT * FROM government_policies ORDER BY created_at DESC").fetchall()
    conn.close()
    return [_attach_policy_sources(dict(r)) for r in rows]


def get_policy_by_id(policy_id):
    """获取政策详情"""
    conn = get_connection()
    row = conn.execute("SELECT * FROM government_policies WHERE id = ?", (policy_id,)).fetchone()
    conn.close()
    return _attach_policy_sources(dict(row)) if row else None


def update_policy(policy_id, source_text=None, **kwargs):
    """更新政策。

    `source_text` 单独取值（表单原文，一行一条）：它不直接写库，
    而是经 policy_sources_to_json 转成 source 列要的 JSON。
    其它字段仍走白名单 —— 未知键一律忽略，不允许客户端改 author_id / created_at。
    """
    conn = get_connection()
    allowed = {'title', 'content', 'category', 'is_published', 'summary', 'date'}
    updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
    if source_text is not None:
        updates['source'] = policy_sources_to_json(source_text)
    if updates:
        updates['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        set_clause = ', '.join(f"{k}=?" for k in updates)
        params = list(updates.values()) + [policy_id]
        conn.execute(f"UPDATE government_policies SET {set_clause} WHERE id=?", params)
        conn.commit()
    conn.close()
    return True


def delete_policy(policy_id):
    """删除政策"""
    conn = get_connection()
    conn.execute("DELETE FROM government_policies WHERE id = ?", (policy_id,))
    conn.commit()
    conn.close()
    return True


# ==================== 政府端工作概览 ====================
# ⚠️ 口径红线（2026-10-07 用户拍板后重做）：
#   政府端概览只呈现**政务侧自己产生、且可核**的信息：政策发布情况 + 本地成功案例。
#   原先的「总用户 / 培训学员 / 岗位数 / 内容生产 / 已获证书 / 讨论帖 / 地区分布 / 培训方向」
#   全部移出，原因：
#     · 岗位数属企业侧数据 → 企业端「工作台」(/api/enterprise/stats)
#     · 培训口径原用 students.progress（**手填**字段；教师端口径是证书真实完成度，两者会打架）
#     · 「地区分布」按 users.region，实际多为空串，「广东省农业农村厅」等机构名还会混进来
#     · 证书/讨论帖在真实数据量下多为 0，硬拼成"大屏"只会显得空


def get_government_overview():
    """政府端工作概览：政策发布情况 + 本地成功案例。

    ⚠️ 政策必须区分「本级发布」与「平台预置」：
      预置政策是用 `gov_demo` 这个账号身份灌进去的（见 `_refresh_policies`），
      只按 author_id 分不开 —— 若直接 COUNT，平台预置的 5 条会被算成本级发布的政绩。
      这里复用与 `_refresh_policies` 相同的**预置标题白名单**（POLICIES_DATA）做区分。

    案例口径与学员端一致：只统计 `content_reviews` 中 status='approved' 的
    （未通过审核的案例，政府端同样不应看到）。
    """
    conn = get_connection()
    preset_titles = {p[0] for p in POLICIES_DATA}
    rows = conn.execute(
        "SELECT title, category, is_published FROM government_policies"
    ).fetchall()
    conn.close()

    own = {"total": 0, "published": 0, "unpublished": 0}
    preset = {"total": 0, "published": 0, "unpublished": 0}
    categories = {}
    for r in rows:
        bucket = preset if r["title"] in preset_titles else own
        bucket["total"] += 1
        if r["is_published"]:
            bucket["published"] += 1
        else:
            bucket["unpublished"] += 1
        cat = (r["category"] or "").strip() or "未分类"
        categories[cat] = categories.get(cat, 0) + 1

    review = get_case_review_stats()["case_review"]
    approved = get_success_cases(only_approved=True)

    region_count = {}
    for c in approved:
        reg = (c.get("region") or "").strip() or "未标注地区"
        region_count[reg] = region_count.get(reg, 0) + 1
    src_total = sum(len(c.get("sources") or []) for c in approved)

    return {
        "policies": {
            "own": own,
            "preset": preset,
            "categories": [
                {"category": k, "count": v}
                for k, v in sorted(categories.items(), key=lambda kv: (-kv[1], kv[0]))
            ],
        },
        "cases": {
            "total": review["total"],
            "approved": review["approved"],
            "pending": review["pending"],
            "rejected": review["rejected"],
            "regions": [
                {"region": k, "count": v}
                for k, v in sorted(region_count.items(), key=lambda kv: (-kv[1], kv[0]))
            ],
            "source_total": src_total,
            "avg_sources": round(src_total / len(approved), 1) if approved else 0,
            "items": [
                {
                    "id": c["id"],
                    "title": c.get("title") or "",
                    "region": (c.get("region") or "").strip(),
                    "sources": len(c.get("sources") or []),
                }
                for c in approved
            ],
        },
    }
