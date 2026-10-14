#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""粤乡智匠 - SQLite数据库层（对外契约层）

本文件把数据层的基础设施与领域业务函数重新导出，让 `import database` 加
`database.xxx()` 的外部调用面在「后端按领域拆分」期间保持不变：app.py、
api/index.py、run.py、_serve.py、e2e/serve.py、test_app.py 全部只认这个名字。

职责已经搬走的四块（详见各模块自己的文档字符串）：

  连接工厂        db_connection.py   全数据层唯一的 sqlite3.connect 调用点
  建表定义        db_schema.py       全仓库唯一一份建表语句
  口令散列        db_credentials.py  播种与认证共用
  播种逻辑        db_seed_*.py       按领域归组，由本文件的 init_db() 显式按序调用

init_db() 是唯一的编排入口：建表 + 补列 + 播种。播种顺序是有意义的，
不要重排：账号必须先于演示岗位（演示岗位挂在 enterprise_demo 名下），
政策必须在案例审核之前（案例审核只补记录，政策签名重灌会重建 policies 全表）。

本文件剩下的业务查询函数是 T05 按领域切分的对象，本票据不动它们。
"""

import json

# ---- 基础设施：连接工厂 / 建表定义 / 口令散列 ----
# 下面每一行都带 noqa: F401：这些符号在本文件里不再被调用，只为把
# database.xxx 这个名字对外保留下来（外部一律 import database + 属性访问）。
from db_connection import DB_DIR, DB_PATH, get_connection  # noqa: F401
from db_credentials import hash_password, verify_password  # noqa: F401
from db_schema import SCHEMA_SQL, apply_schema  # noqa: F401

from db_domains.announcements import (  # noqa: F401
    add_system_announcement,
    delete_system_announcement,
    get_active_system_announcement_ids,
    get_system_announcements,
)
from db_domains.auth import (  # noqa: F401
    authenticate_user,
    create_session,
    delete_session,
    get_session,
)
from db_domains.certificates import get_certificates  # noqa: F401
from db_domains.community import (  # noqa: F401
    add_comment,
    create_discussion,
    get_comments,
    get_discussion,
    get_discussions,
    soft_delete_comment,
    soft_delete_discussion,
)
from db_domains.courses import (  # noqa: F401
    add_course_material,
    create_course,
    create_model_3d,
    delete_course,
    delete_course_material,
    delete_model_3d,
    get_course,
    get_course_materials,
    get_courses,
    get_models_3d,
    update_course,
)
from db_domains.employment import (  # noqa: F401
    ENTERPRISE_JOB_CATEGORIES,
    RESUME_FIELDS,
    add_job_intent,
    apply_for_job,
    count_pending_job_listings,
    count_unread_job_applications,
    get_application_counts,
    get_employment_stats,
    get_job_application_ids,
    get_job_by_id,
    get_job_category_counts,
    get_job_intents,
    get_job_listings,
    get_job_listings_base,
    get_job_listings_filtered,
    get_learner_profile,
    get_resume,
    get_saved_jobs,
    get_similar_jobs,
    get_user_applications,
    mark_resume_ai_used,
    parse_salary_bounds,
    remove_job_intent,
    save_job,
    save_resume,
    unsave_job,
)
from db_domains.farming import (  # noqa: F401
    clear_farming_reminder_log,
    get_due_farming_tasks,
    get_farming_category_labels,
    get_farming_phenophases,
    get_farming_product,
    get_farming_products,
    get_farming_source_map,
    get_farming_sources,
    get_farming_subscribers,
    get_farming_subscriptions,
    get_farming_task_by_id,
    get_farming_tasks,
    has_farming_reminder_sent,
    is_farming_subscribed,
    mark_farming_reminder_sent,
    set_farming_subscription,
)
from db_domains.messages import (  # noqa: F401
    count_unread_conversations,
    get_inbox,
    get_messages,
    get_unread_count,
    mark_all_messages_read,
    mark_messages_read,
    send_message,
)
from db_domains.notifications import (  # noqa: F401
    clear_read_notifications,
    clear_read_refs,
    create_notification,
    create_notification_for_all_students,
    get_notifications,
    get_read_refs,
    get_total_unread_count,
    get_unread_notification_count,
    mark_notifications_read,
    mark_ref_read,
    mark_refs_read,
)
from db_domains.points import get_points, update_points  # noqa: F401
from db_domains.policies import (  # noqa: F401
    create_policy,
    delete_policy,
    get_all_government_policies,
    get_government_overview,
    get_government_policies,
    get_policy_by_id,
    update_policy,
)
from db_domains.procurements import (  # noqa: F401
    create_procurement,
    delete_procurement,
    get_procurements,
    update_procurement,
)
from db_domains.resources import (  # noqa: F401
    CASE_REVIEW_TYPE,
    default_policy_summary,
    get_case_notes,
    get_case_review_stats,
    get_policy_notes,
    get_success_cases,
    normalize_policy_category,
    policy_sources_to_json,
)
from db_domains.reviews import (  # noqa: F401
    approve_review,
    count_reviews_by_status,
    create_content_review,
    get_pending_reviews,
    get_review_by_content,
    get_reviews_by_status,
    reject_review,
    revoke_review,
    set_review_status,
)
from db_domains.students import (  # noqa: F401
    add_student,
    delete_student,
    get_linkable_student_accounts,
    get_student,
    get_students,
    set_student_account,
    update_student,
)
from db_domains.teaching import (  # noqa: F401
    TRAINING_DESCRIPTIONS,
    TRAINING_TITLE_FMTS,
    LIVE_ASSIGNMENT_DIRECTION,
    LIVE_ASSIGNMENT_TITLE_FMT,
    create_announcement,
    delete_announcement,
    get_announcements,
    get_all_trainings,
    get_analytics_data,
    get_dashboard_stats,
    get_live_trainings,
    get_or_create_live_assignment,
    get_or_create_training_assignment,
    get_roster_completion,
    get_trainings,
    grade_submission,
    save_live_training,
)
from db_domains.users import (  # noqa: F401
    change_password,
    count_super_admins,
    count_user_relations,
    delete_user_by_admin,
    get_admin_overview,
    get_all_users,
    get_user_by_id,
    get_user_by_username,
    register_user,
    set_user_status,
    update_user_by_admin,
    update_user_profile,
)

# ---- 播种：按领域归组，每个模块只负责自己那几张表 ----
from db_seed_accounts import ensure_demo_accounts, seed_demo_accounts  # noqa: F401
from db_seed_cases import CASE_REVIEW_TYPE, seed_case_reviews  # noqa: F401
from db_seed_demo_jobs import (  # noqa: F401
    DEMO_JOBS,
    DEMO_JOBS_SEED_KEY,
    DEMO_JOB_ENTERPRISE_ID,
    create_review_with_cursor,
    demo_jobs_signature,
    seed_demo_jobs,
)
from db_seed_farming import seed_farming  # noqa: F401
from db_seed_policies import (  # noqa: F401
    POLICIES_DATA,
    POLICIES_SEED_VERSION,
    POLICY_SOURCES,
    policies_signature,
    refresh_policies,
    seed_government_policies,
    seed_policies,
)
from db_seed_portal import seed_carousels, seed_portal_content  # noqa: F401


def init_db():
    """初始化数据库：建表 + 填充种子数据

    首次执行建表并播种；重复执行幂等（种子按内容签名或存在性判断，不翻倍、
    不覆盖已审核结论、不清真实企业数据）。部署入口与测试入口都只调这一个函数。
    """
    conn = get_connection()
    cursor = conn.cursor()

    # 建表 + 给既有库补列（定义只在 db_schema.py 一处）
    apply_schema(cursor)

    # 检查是否已有种子数据
    count = cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if count == 0:
        # 顺序与原 _seed_data() 逐行对应：账号 -> policies -> government_policies
        # -> 轮播/公告/讨论。三者互不读对方，换序不会改变结果，但保持一致便于逐行比对。
        seed_demo_accounts(cursor)
        seed_policies(cursor)
        seed_government_policies(cursor)
        seed_portal_content(cursor)
    else:
        # 已有数据时，刷新政策内容（保证政策详情是最新的）
        refresh_policies(cursor)
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
            seed_government_policies(cursor)
        # 如果轮播图为空，填充默认数据
        car_count = cursor.execute("SELECT COUNT(*) FROM carousels").fetchone()[0]
        if car_count == 0:
            seed_carousels(cursor)
        # 如果缺少新角色演示账户，补充创建
        ensure_demo_accounts(cursor)

    # 农时日历种子数据（幂等，两个分支都需保证存在）
    seed_farming(cursor)

    # 预置政策：按内容签名自动重灌（幂等；只重建 author_id='gov_demo' 的预置行，不动自建政策）
    refresh_policies(cursor)

    # 成功案例：把 cases_data.py 里新增的案例补一条**待审核**记录（幂等，不覆盖已有审核结果）
    seed_case_reviews(cursor)

    # 演示企业岗位（用户 2026-10-06 拍板）：让「投递」链路有可演示的载体。
    # 只动 is_demo=1 的行，真实企业岗位与其投递/收藏不受影响。
    seed_demo_jobs(cursor)

    # 废弃表清理已移入 db_schema.apply_schema()：内容落库（ADR 0002）把 success_cases
    # 翻回正式表后，原先那条 DROP 会在每次 init_db() 时把它连同灌进去的内容一起删掉。
    # 「哪些表不该存在」与「哪些表该存在」是同一份真相，故只在 db_schema 一处裁决。

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
