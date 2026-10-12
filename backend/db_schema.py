#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""建表定义与幂等升级。全仓库只有这一份 CREATE TABLE。

拆分前建表语句内联在 database.py 的 init_db() 里（33 张表加 5 个索引），
与连接、播种、业务查询搅在一个 567 行的函数中。现在收敛到本模块：

  - SCHEMA_SQL：表与索引的定义，只用 `CREATE TABLE IF NOT EXISTS`，重复执行安全；
  - apply_schema()：建表 + 给既有库补列的幂等升级。

升级逻辑必须和建表放在一起：`CREATE TABLE IF NOT EXISTS` 对已存在的表不会补列，
老库的新列全靠这段 ALTER TABLE。两者拆到两处，就会出现「建表改了、升级忘了改」，
新库有列、老库没列，且没有任何报错。
"""

SCHEMA_SQL = """
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
"""


def apply_schema(cursor):
    """建表 + 给既有库补列。定义只此一份，init_db() 只调它。"""
    cursor.executescript(SCHEMA_SQL)

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
