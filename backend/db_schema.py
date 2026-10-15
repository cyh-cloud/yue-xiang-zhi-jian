#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""建表定义与幂等升级。全仓库只有这一份 CREATE TABLE。

拆分前建表语句内联在 database.py 的 init_db() 里（33 张表加 5 个索引），
与连接、播种、业务查询搅在一个 567 行的函数中。现在收敛到本模块：

  - SCHEMA_SQL：表、索引与视图的定义，只用 `CREATE ... IF NOT EXISTS`，重复执行安全；
  - apply_schema()：建表 + 给既有库补列的幂等升级。

升级逻辑必须和建表放在一起：`CREATE TABLE IF NOT EXISTS` 对已存在的表不会补列，
老库的新列全靠这段 ALTER TABLE。两者拆到两处，就会出现「建表改了、升级忘了改」，
新库有列、老库没列，且没有任何报错。

内容落库（ADR 0002）后本模块同时持有 5 个跨域读取视图的定义：视图与建表同住，
JOIN 只有一份，域路由只 SELECT * FROM v_xxx，域间 Python import 边为零。
"""

import re

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
            created_at TEXT DEFAULT (datetime('now','localtime')),
            extra TEXT NOT NULL DEFAULT '{}'
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
            reviewed_at TEXT DEFAULT NULL,
            extra TEXT NOT NULL DEFAULT '{}'
        );

        CREATE TABLE IF NOT EXISTS user_sessions (
            session_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            login_time REAL NOT NULL,
            expires_at REAL NOT NULL,
            extra TEXT NOT NULL DEFAULT '{}'
        );

        CREATE TABLE IF NOT EXISTS points (
            user_id TEXT PRIMARY KEY,
            balance INTEGER DEFAULT 0,
            history TEXT DEFAULT '[]',
            extra TEXT NOT NULL DEFAULT '{}'
        );

        CREATE TABLE IF NOT EXISTS certificates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            name TEXT NOT NULL,
            status TEXT DEFAULT 'locked',
            progress INTEGER DEFAULT 0,
            date TEXT DEFAULT '',
            extra TEXT NOT NULL DEFAULT '{}'
        );

        CREATE TABLE IF NOT EXISTS students (
            id TEXT PRIMARY KEY,
            user_id TEXT DEFAULT '',
            name TEXT NOT NULL,
            class_name TEXT DEFAULT '',
            direction TEXT DEFAULT '',
            progress INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active',
            created_at TEXT DEFAULT (datetime('now','localtime')),
            extra TEXT NOT NULL DEFAULT '{}'
        );

        CREATE TABLE IF NOT EXISTS announcements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            category TEXT DEFAULT '通知',
            pinned INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            extra TEXT NOT NULL DEFAULT '{}'
        );

        CREATE TABLE IF NOT EXISTS assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            direction TEXT DEFAULT '',
            deadline TEXT DEFAULT '',
            total_score INTEGER DEFAULT 100,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            extra TEXT NOT NULL DEFAULT '{}'
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
            extra TEXT NOT NULL DEFAULT '{}',
            UNIQUE(assignment_id, student_id)
        );

        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id TEXT NOT NULL,
            receiver_id TEXT NOT NULL,
            content TEXT NOT NULL,
            is_read INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            extra TEXT NOT NULL DEFAULT '{}'
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
            created_at TEXT DEFAULT (datetime('now','localtime')),
            extra TEXT NOT NULL DEFAULT '{}'
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
            extra TEXT NOT NULL DEFAULT '{}',
            PRIMARY KEY (user_id, source, ref_id)
         );

        CREATE TABLE IF NOT EXISTS job_applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            job_id INTEGER NOT NULL,
            status TEXT DEFAULT 'pending',
            applied_at TEXT DEFAULT (datetime('now','localtime')),
            extra TEXT NOT NULL DEFAULT '{}'
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
            source TEXT DEFAULT '',
            extra TEXT NOT NULL DEFAULT '{}'
        );

        -- 迁移记录表。migrations/0001_content_to_db.py 靠它判断「这库跑没跑过」，
        -- 否则重复执行会把运营改过的内容按代码再刷一遍。记录与建表同住：表定义
        -- 全仓库只有这一份，脚本不另建表。version 是脚本文件名里的序号，
        -- extra 存本次执行的清理与写入摘要（脏数据清理记录就在那里，不静默丢弃）。
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version    TEXT PRIMARY KEY,
            name       TEXT NOT NULL,
            applied_at TEXT DEFAULT (datetime('now','localtime')),
            extra TEXT NOT NULL DEFAULT '{}'
        );

        CREATE TABLE IF NOT EXISTS job_listings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            company TEXT NOT NULL,
            salary TEXT DEFAULT '',
            requirements TEXT DEFAULT '[]',
            description TEXT DEFAULT '',
            extra TEXT NOT NULL DEFAULT '{}'
        );

        CREATE TABLE IF NOT EXISTS saved_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            job_id INTEGER NOT NULL,
            saved_at TEXT DEFAULT (datetime('now','localtime')),
            extra TEXT NOT NULL DEFAULT '{}',
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
            updated_at TEXT DEFAULT (datetime('now','localtime')),
            extra TEXT NOT NULL DEFAULT '{}'
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
            extra TEXT NOT NULL DEFAULT '{}',
            UNIQUE(user_id, recruit_key)
        );

        CREATE TABLE IF NOT EXISTS carousels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            image_url TEXT NOT NULL,
            link_url TEXT DEFAULT '',
            sort_order INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            extra TEXT NOT NULL DEFAULT '{}'
        );

        CREATE TABLE IF NOT EXISTS system_announcements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            is_pinned INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_by TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now','localtime')),
            extra TEXT NOT NULL DEFAULT '{}'
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
            created_at TEXT DEFAULT (datetime('now','localtime')),
            extra TEXT NOT NULL DEFAULT '{}'
        );

        CREATE TABLE IF NOT EXISTS course_materials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER NOT NULL,
            material_type TEXT NOT NULL,
            file_name TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_size INTEGER DEFAULT 0,
            sort_order INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            extra TEXT NOT NULL DEFAULT '{}'
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
            created_at TEXT DEFAULT (datetime('now','localtime')),
            extra TEXT NOT NULL DEFAULT '{}'
        );

        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_type TEXT NOT NULL,
            target_id INTEGER NOT NULL,
            user_id TEXT NOT NULL,
            content TEXT NOT NULL,
            is_deleted INTEGER DEFAULT 0,
            deleted_by TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now','localtime')),
            extra TEXT NOT NULL DEFAULT '{}'
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
            created_at TEXT DEFAULT (datetime('now','localtime')),
            extra TEXT NOT NULL DEFAULT '{}'
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
            created_at TEXT DEFAULT (datetime('now','localtime')),
            extra TEXT NOT NULL DEFAULT '{}'
        );

        CREATE TABLE IF NOT EXISTS news_articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            category TEXT DEFAULT 'news',
            author_id TEXT NOT NULL,
            is_published INTEGER DEFAULT 1,
            view_count INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            extra TEXT NOT NULL DEFAULT '{}'
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
            updated_at TEXT DEFAULT (datetime('now','localtime')),
            extra TEXT NOT NULL DEFAULT '{}'
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
            created_at  TEXT DEFAULT (datetime('now','localtime')),
            extra TEXT NOT NULL DEFAULT '{}'
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
            extra TEXT NOT NULL DEFAULT '{}',
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
            -- verified_by / verified_at：谁在何时复核的。is_verified 只记结果，
            -- 这两列让它可追溯、可按时间筛出该重新核的条目（见 apply_schema 的补列段）。
            verified_by TEXT NOT NULL DEFAULT '',
            verified_at TEXT NOT NULL DEFAULT '',
            is_active   INTEGER DEFAULT 1,
            sort_order  INTEGER DEFAULT 0,
            extra TEXT NOT NULL DEFAULT '{}',
            FOREIGN KEY (product_id) REFERENCES farming_products(id) ON DELETE CASCADE,
            FOREIGN KEY (phase_id)   REFERENCES farming_phenophases(id) ON DELETE SET NULL
        );

        -- ④ 订阅关系（user_id 存 username，与项目既有约定一致）
        CREATE TABLE IF NOT EXISTS farming_subscriptions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     TEXT NOT NULL,
            product_id  TEXT NOT NULL,
            created_at  TEXT DEFAULT (datetime('now','localtime')),
            extra TEXT NOT NULL DEFAULT '{}',
            UNIQUE(user_id, product_id)
        );

        -- ⑤ 提醒发送日志（登录时补发的判重依据）
        CREATE TABLE IF NOT EXISTS farming_reminder_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     TEXT NOT NULL,
            product_id  TEXT NOT NULL,
            period      TEXT NOT NULL,
            sent_at     TEXT DEFAULT (datetime('now','localtime')),
            extra TEXT NOT NULL DEFAULT '{}',
            UNIQUE(user_id, product_id, period)
        );

        -- ⑥ 数据来源登记表（来源方向 = 机构 + 文件类型）
        --    doc_no 一律先落「待核」：具体标准号/文号须由农技人员核实后补填，
        --    代码侧不得凭空编造标准号，故本表只做"来源方向"登记。
        CREATE TABLE IF NOT EXISTS farming_sources (
            key         TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            org         TEXT DEFAULT '',
            doc_type    TEXT DEFAULT '',
            doc_no      TEXT DEFAULT '',
            url         TEXT DEFAULT '',
            sort_order  INTEGER DEFAULT 0,
            extra TEXT NOT NULL DEFAULT '{}'
        );

        CREATE INDEX IF NOT EXISTS idx_farming_tasks_month    ON farming_tasks(product_id, month);
        CREATE INDEX IF NOT EXISTS idx_farming_tasks_md       ON farming_tasks(product_id, task_md);
        CREATE INDEX IF NOT EXISTS idx_farming_phases_product ON farming_phenophases(product_id);
        CREATE INDEX IF NOT EXISTS idx_farming_subs_user      ON farming_subscriptions(user_id);
        CREATE INDEX IF NOT EXISTS idx_farming_log_lookup     ON farming_reminder_log(user_id, product_id, period);

        -- ==================== 内容落库（ADR 0002）====================
        -- 以下 20 张表承接原代码里的六份内容数据模块与六份路由内内容常量（ADR 0002
        -- 已把那些模块整体删除）。命名沿用既有风格：
        -- snake_case 复数、is_ 前缀布尔、_at 后缀时间、JSON 数组存 TEXT。
        -- 每张表同样带 extra 预留列，不建索引。

        -- 农时分类标签（替代 FARMING_CATEGORY_LABELS）
        CREATE TABLE IF NOT EXISTS farming_categories (
            key        TEXT PRIMARY KEY,
            label      TEXT NOT NULL,
            color      TEXT DEFAULT '',
            sort_order INTEGER DEFAULT 0,
            extra TEXT NOT NULL DEFAULT '{}'
        );

        -- 病虫害速查的作物层（替代 PEST_KNOWLEDGE 的键）
        CREATE TABLE IF NOT EXISTS pest_crops (
            id         TEXT PRIMARY KEY,
            name       TEXT NOT NULL,
            icon       TEXT DEFAULT '',
            summary    TEXT DEFAULT '',
            sort_order INTEGER DEFAULT 0,
            extra TEXT NOT NULL DEFAULT '{}'
        );

        -- 病虫害条目（替代 PEST_KNOWLEDGE[].common_diseases 的元素）
        -- 五个 JSON 列存数组文本，读取侧由兼容层解析。
        CREATE TABLE IF NOT EXISTS pest_entries (
            id          TEXT PRIMARY KEY,
            crop_id     TEXT NOT NULL,
            disease     TEXT NOT NULL,
            alias       TEXT DEFAULT '',
            kind        TEXT DEFAULT '',
            pathogen    TEXT DEFAULT '',
            part        TEXT DEFAULT '',
            severity    TEXT DEFAULT '',
            symptoms    TEXT DEFAULT '[]',
            occurrence  TEXT DEFAULT '',
            treatment   TEXT DEFAULT '[]',
            prevention  TEXT DEFAULT '[]',
            registered  TEXT DEFAULT '[]',
            chem_table  TEXT DEFAULT '[]',
            safety_note TEXT DEFAULT '',
            is_verified INTEGER DEFAULT 0,
            verified_by TEXT NOT NULL DEFAULT '',
            verified_at TEXT NOT NULL DEFAULT '',
            sort_order  INTEGER DEFAULT 0,
            extra TEXT NOT NULL DEFAULT '{}',
            FOREIGN KEY (crop_id) REFERENCES pest_crops(id) ON DELETE CASCADE
        );

        -- 病虫害资料来源（替代 PEST_SOURCES）
        CREATE TABLE IF NOT EXISTS pest_sources (
            key        TEXT PRIMARY KEY,
            name       TEXT NOT NULL,
            org        TEXT DEFAULT '',
            doc_type   TEXT DEFAULT '',
            doc_no     TEXT DEFAULT '',
            date       TEXT DEFAULT '',
            url        TEXT DEFAULT '',
            sort_order INTEGER DEFAULT 0,
            extra TEXT NOT NULL DEFAULT '{}'
        );

        -- 条目与来源的多对多（替代 entry['sources']）
        CREATE TABLE IF NOT EXISTS pest_entry_sources (
            entry_id   TEXT NOT NULL,
            source_key TEXT NOT NULL,
            sort_order INTEGER DEFAULT 0,
            extra TEXT NOT NULL DEFAULT '{}',
            PRIMARY KEY (entry_id, source_key),
            FOREIGN KEY (entry_id)   REFERENCES pest_entries(id)  ON DELETE CASCADE,
            FOREIGN KEY (source_key) REFERENCES pest_sources(key) ON DELETE CASCADE
        );

        -- 实拍图清单（替代 PEST_IMAGES）：一条条目最多一张图，故 entry_id 作主键
        CREATE TABLE IF NOT EXISTS pest_images (
            entry_id   TEXT PRIMARY KEY,
            file       TEXT DEFAULT '',
            credit     TEXT DEFAULT '',
            license    TEXT DEFAULT '',
            caption    TEXT DEFAULT '',
            source_url TEXT DEFAULT '',
            shot_date  TEXT DEFAULT '',
            note       TEXT DEFAULT '',
            extra TEXT NOT NULL DEFAULT '{}',
            FOREIGN KEY (entry_id) REFERENCES pest_entries(id) ON DELETE CASCADE
        );

        -- 招募公告（替代 RECRUIT_DATA）
        CREATE TABLE IF NOT EXISTS recruitments (
            key          TEXT PRIMARY KEY,
            title        TEXT NOT NULL,
            org          TEXT DEFAULT '',
            region       TEXT DEFAULT '',
            category     TEXT DEFAULT '',
            job_type     TEXT DEFAULT '',
            headcount    TEXT DEFAULT '',
            education    TEXT DEFAULT '',
            experience   TEXT DEFAULT '',
            salary       TEXT DEFAULT '',
            description  TEXT DEFAULT '',
            publish_date TEXT DEFAULT '',
            signup_start TEXT DEFAULT '',
            deadline     TEXT DEFAULT '',
            signup_way   TEXT DEFAULT '',
            contact      TEXT DEFAULT '',
            sort_order   INTEGER DEFAULT 0,
            extra TEXT NOT NULL DEFAULT '{}'
        );

        -- 公告来源（替代 RECRUIT_DATA[].sources）
        CREATE TABLE IF NOT EXISTS recruitment_sources (
            recruit_key TEXT NOT NULL,
            title       TEXT DEFAULT '',
            media       TEXT DEFAULT '',
            date        TEXT DEFAULT '',
            url         TEXT DEFAULT '',
            sort_order  INTEGER DEFAULT 0,
            extra TEXT NOT NULL DEFAULT '{}',
            PRIMARY KEY (recruit_key, title),
            FOREIGN KEY (recruit_key) REFERENCES recruitments(key) ON DELETE CASCADE
        );

        -- 成功案例主表（替代 SUCCESS_CASES 的元素）
        CREATE TABLE IF NOT EXISTS success_cases (
            id           INTEGER PRIMARY KEY,
            title        TEXT NOT NULL,
            region       TEXT DEFAULT '',
            location     TEXT DEFAULT '',
            background   TEXT DEFAULT '',
            description  TEXT DEFAULT '',
            quote        TEXT DEFAULT '',
            quote_author TEXT DEFAULT '',
            sort_order   INTEGER DEFAULT 0,
            extra TEXT NOT NULL DEFAULT '{}'
        );

        -- 案例数据指标（替代 case['stats']）
        CREATE TABLE IF NOT EXISTS case_stats (
            case_id    INTEGER NOT NULL,
            label      TEXT DEFAULT '',
            value      TEXT DEFAULT '',
            icon       TEXT DEFAULT '',
            sort_order INTEGER DEFAULT 0,
            extra TEXT NOT NULL DEFAULT '{}',
            FOREIGN KEY (case_id) REFERENCES success_cases(id) ON DELETE CASCADE
        );

        -- 案例里程碑（替代 case['milestones']）
        CREATE TABLE IF NOT EXISTS case_milestones (
            case_id    INTEGER NOT NULL,
            period     TEXT DEFAULT '',
            title      TEXT DEFAULT '',
            "desc"     TEXT DEFAULT '',
            sort_order INTEGER DEFAULT 0,
            extra TEXT NOT NULL DEFAULT '{}',
            FOREIGN KEY (case_id) REFERENCES success_cases(id) ON DELETE CASCADE
        );

        -- 案例来源（替代 case['sources']）
        CREATE TABLE IF NOT EXISTS case_sources (
            case_id    INTEGER NOT NULL,
            title      TEXT DEFAULT '',
            media      TEXT DEFAULT '',
            date       TEXT DEFAULT '',
            url        TEXT DEFAULT '',
            sort_order INTEGER DEFAULT 0,
            extra TEXT NOT NULL DEFAULT '{}',
            FOREIGN KEY (case_id) REFERENCES success_cases(id) ON DELETE CASCADE
        );

        -- 案例借鉴点（替代 case['lessons']）
        CREATE TABLE IF NOT EXISTS case_lessons (
            case_id    INTEGER NOT NULL,
            text       TEXT DEFAULT '',
            sort_order INTEGER DEFAULT 0,
            extra TEXT NOT NULL DEFAULT '{}',
            FOREIGN KEY (case_id) REFERENCES success_cases(id) ON DELETE CASCADE
        );

        -- 方言知识（替代 DIALECTS_DATA）
        CREATE TABLE IF NOT EXISTS dialects (
            id               TEXT PRIMARY KEY,
            name             TEXT NOT NULL,
            region           TEXT DEFAULT '',
            emoji            TEXT DEFAULT '',
            areas            TEXT DEFAULT '',
            speakers         TEXT DEFAULT '',
            greeting         TEXT DEFAULT '',
            greeting_meaning TEXT DEFAULT '',
            features         TEXT DEFAULT '[]',
            sort_order       INTEGER DEFAULT 0,
            extra TEXT NOT NULL DEFAULT '{}'
        );

        -- 方言短语（替代 dialect['phrases']）
        CREATE TABLE IF NOT EXISTS dialect_phrases (
            dialect_id TEXT NOT NULL,
            dialect    TEXT DEFAULT '',
            mandarin   TEXT DEFAULT '',
            pinyin     TEXT DEFAULT '',
            sort_order INTEGER DEFAULT 0,
            extra TEXT NOT NULL DEFAULT '{}',
            FOREIGN KEY (dialect_id) REFERENCES dialects(id) ON DELETE CASCADE
        );

        -- 方言快捷问题（替代 dialect['quick_questions']）
        CREATE TABLE IF NOT EXISTS dialect_quick_questions (
            dialect_id TEXT NOT NULL,
            question   TEXT DEFAULT '',
            sort_order INTEGER DEFAULT 0,
            extra TEXT NOT NULL DEFAULT '{}',
            FOREIGN KEY (dialect_id) REFERENCES dialects(id) ON DELETE CASCADE
        );

        -- 手工技艺（替代 CRAFTS_KNOWLEDGE 的技艺层）
        CREATE TABLE IF NOT EXISTS crafts (
            id         TEXT PRIMARY KEY,
            name       TEXT NOT NULL,
            origin     TEXT DEFAULT '',
            history    TEXT DEFAULT '',
            level      TEXT DEFAULT '',
            sort_order INTEGER DEFAULT 0,
            extra TEXT NOT NULL DEFAULT '{}'
        );

        -- 技艺步骤（替代 craft['steps']）
        CREATE TABLE IF NOT EXISTS craft_steps (
            craft_id   TEXT NOT NULL,
            title      TEXT DEFAULT '',
            "desc"     TEXT DEFAULT '',
            tips       TEXT DEFAULT '',
            sort_order INTEGER DEFAULT 0,
            extra TEXT NOT NULL DEFAULT '{}',
            FOREIGN KEY (craft_id) REFERENCES crafts(id) ON DELETE CASCADE
        );

        -- 采购指南分类（替代 purchase_guide['categories']）
        CREATE TABLE IF NOT EXISTS craft_purchase_categories (
            craft_id   TEXT NOT NULL,
            key        TEXT NOT NULL,
            label      TEXT DEFAULT '',
            "desc"     TEXT DEFAULT '',
            sort_order INTEGER DEFAULT 0,
            extra TEXT NOT NULL DEFAULT '{}',
            PRIMARY KEY (craft_id, key),
            FOREIGN KEY (craft_id) REFERENCES crafts(id) ON DELETE CASCADE
        );

        -- 采购条目（替代 category['items']）
        CREATE TABLE IF NOT EXISTS craft_purchase_items (
            craft_id     TEXT NOT NULL,
            category_key TEXT NOT NULL,
            name         TEXT DEFAULT '',
            price        TEXT DEFAULT '',
            spec         TEXT DEFAULT '',
            tip          TEXT DEFAULT '',
            "where"      TEXT DEFAULT '',
            sort_order   INTEGER DEFAULT 0,
            extra TEXT NOT NULL DEFAULT '{}',
            FOREIGN KEY (craft_id) REFERENCES crafts(id) ON DELETE CASCADE
        );

        -- 采购预算（替代 purchase_guide['budget']）：一门技艺一份，故 craft_id 作主键
        CREATE TABLE IF NOT EXISTS craft_budgets (
            craft_id    TEXT PRIMARY KEY,
            starter     TEXT DEFAULT '',
            advanced    TEXT DEFAULT '',
            buying_tips TEXT DEFAULT '',
            extra TEXT NOT NULL DEFAULT '{}',
            FOREIGN KEY (craft_id) REFERENCES crafts(id) ON DELETE CASCADE
        );

        -- ==================== 跨域读取视图（ADR 0002）====================
        -- 域路由只 SELECT * FROM v_xxx，域间 Python import 边为零。定义与建表同住一处。
        -- 本票据只建视图，查询方在 T11 切换；此处保证「视图可查且与直连 SQL 等价」。

        -- 企业看申请人：投递 + 岗位 + 用户 + 简历四表 JOIN（原 enterprise/routes.py:139-160）
        CREATE VIEW IF NOT EXISTS v_enterprise_applications AS
            SELECT ja.id, ja.user_id, ja.job_id, ja.status, ja.applied_at,
                   jl.title as job_title,
                   u.name as applicant_name, u.phone as applicant_phone,
                   u.email as applicant_email, u.bio as applicant_bio,
                   r.title as resume_title, r.region as resume_region,
                   r.education as resume_education, r.work_years as resume_work_years,
                   r.phone as resume_phone, r.email as resume_email,
                   r.self_eval as resume_self_eval, r.skills as resume_skills,
                   r.experience as resume_experience, r.updated_at as resume_updated_at
            FROM job_applications ja
            JOIN job_listings jl ON ja.job_id = jl.id
            JOIN users u ON ja.user_id = u.username
            LEFT JOIN resumes r ON r.user_id = ja.user_id;

        -- 企业岗位统计：按企业分组的岗位与投递计数（原 enterprise/routes.py:199-208）
        -- ⚠️ total_jobs 这个名字延续原路由的口径：它数的是**审核通过**的在招职位，
        --    不是该企业的岗位总数。原路由里「未通过审核的单列」叫 pending_jobs。
        --    COALESCE 是 fail-safe：历史行 review_status 为 NULL 也按「未通过」计。
        CREATE VIEW IF NOT EXISTS v_enterprise_job_stats AS
            SELECT jl.enterprise_id as enterprise_id,
                   SUM(CASE WHEN jl.review_status = 'approved' THEN 1 ELSE 0 END) as total_jobs,
                   SUM(CASE WHEN COALESCE(jl.review_status, '') != 'approved' THEN 1 ELSE 0 END) as pending_jobs,
                   COUNT(ja.id) as total_apps
            FROM job_listings jl
            LEFT JOIN job_applications ja ON ja.job_id = jl.id
            GROUP BY jl.enterprise_id;

        -- 首页统计：跨三个域的三次计数（原 public/routes.py:28-33）
        CREATE VIEW IF NOT EXISTS v_home_stats AS
            SELECT
                (SELECT COUNT(*) FROM students) as farmers,
                (SELECT COUNT(*) FROM courses) as courses,
                (SELECT COUNT(*) FROM job_listings) as jobs;

        -- 批改时取提交上下文：提交 JOIN 作业（原 teaching_support/routes.py:110-112）
        CREATE VIEW IF NOT EXISTS v_submission_context AS
            SELECT s.id as submission_id, s.assignment_id, s.student_id,
                   s.status as submission_status, s.submitted_at,
                   a.title as assignment_title, a.direction as assignment_direction
            FROM assignment_submissions s
            JOIN assignments a ON a.id = s.assignment_id;

        -- 审核详情取 3D 模型（原 admin/routes.py:216-218）
        CREATE VIEW IF NOT EXISTS v_reviewable_models AS
            SELECT * FROM models_3d;
"""

# 本模块建表语句覆盖的全部表名。存在的唯一理由：让下面的「清理废弃表」
# 不会误删刚刚才建出来的表。success_cases 就这样被误删过：内容落库
# （ADR 0002）把它从「已废弃」翻回正式表，database.py 里那条 DROP 却照旧执行，
# 每次 init_db() 都把它连同灌进去的内容一起删掉。真相只有一份，故在这里比对。
SCHEMA_TABLES = frozenset(re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)", SCHEMA_SQL))

# 已下线、确认不再需要的表。历史版本在这些表里留过编造数据，启动时清掉，
# 保证旧库不残留。**新表不要加进来**：进来就会被每次 init_db() 删掉。
DEPRECATED_TABLES = ('attendance_records', 'attendances')


def apply_schema(cursor):
    """建表 + 给既有库补列 + 清理已下线的废弃表。定义只此一份，init_db() 只调它。

    第三件事（DROP 废弃表）也必须在建表之后、由本模块做：历史上「哪些表不该存在」
    与「哪些表该存在」是同一份真相，分开两处就会出现「建表加了、清库忘了加」。
    2026-10-15 起 success_cases 从「已废弃」翻回「内容落库后的正式表」
    （ADR 0002），故它出现在 DEPRECATED_TABLES 之外，不再被DROP。
    """
    cursor.executescript(SCHEMA_SQL)

    # 清理已下线的废弃表。这段原先住在 database.py 的 init_db() 里，与建表定义
    # 分居两处，于是出现「schema 说这张表在、启动又说它不在」的矛盾：内容落库
    # （ADR 0002）把 success_cases 从「已废弃」翻回正式表后，那条 DROP 会在每次
    # init_db() 时把它连同 T05 灌进去的内容一起删掉。哪些表不该存在与哪些表该
    # 存在是同一份真相，故收回到本模块，并在 DEPRECATED_TABLES 里显式排除。
    for _tbl in DEPRECATED_TABLES:
        if _tbl not in SCHEMA_TABLES:
            cursor.execute("DROP TABLE IF EXISTS %s" % _tbl)

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

    # 扩展 farming_tasks / pest_entries：补 verified_by / verified_at
    # （ADR 0002 / REFACTOR-PLAN 4.5）。这是既有 is_verified 的必然延伸：
    # 原来只记「核过了」，不记谁核的、什么时候核的，后台无法显示复核人，
    # 也无法按时间找出该重新核的条目。
    # 两列 NOT NULL 带默认值，既有行的补列不会失败，也不会改变既有语义。
    for _tbl in ('farming_tasks', 'pest_entries'):
        _cols = {row[1] for row in cursor.execute("PRAGMA table_info(%s)" % _tbl).fetchall()}
        for _col in ('verified_by', 'verified_at'):
            if _cols and _col not in _cols:
                cursor.execute(
                    "ALTER TABLE %s ADD COLUMN %s TEXT NOT NULL DEFAULT ''" % (_tbl, _col))

    # 扩展 policies / government_policies：新增 source 列（存"来源列表"JSON，供前端展示出处）
    for _tbl in ('policies', 'government_policies'):
        _cols = {row[1] for row in cursor.execute("PRAGMA table_info(%s)" % _tbl).fetchall()}
        if _cols and 'source' not in _cols:
            cursor.execute("ALTER TABLE %s ADD COLUMN source TEXT DEFAULT ''" % _tbl)
        if _cols and 'summary' not in _cols:
            cursor.execute("ALTER TABLE %s ADD COLUMN summary TEXT DEFAULT ''" % _tbl)
        if _cols and 'date' not in _cols:
            cursor.execute("ALTER TABLE %s ADD COLUMN date TEXT DEFAULT ''" % _tbl)
