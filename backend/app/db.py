from __future__ import annotations

import sqlite3
from pathlib import Path

from flask import current_app, g

from app.ecommerce_training.seed import seed_ecommerce_course_fixtures
from app.handcraft_inheritance.seed import seed_handcraft_fixtures
from app.seed import seed_interest_tags


SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    name TEXT NOT NULL,
    role TEXT NOT NULL CHECK (
        role IN ('student', 'teacher', 'enterprise', 'government', 'super_admin', 'admin')
    ),
    is_enabled INTEGER NOT NULL DEFAULT 1 CHECK (is_enabled IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    state TEXT NOT NULL CHECK (state IN ('pending', 'active')),
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);

CREATE TABLE IF NOT EXISTS student_profiles (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    contact TEXT NOT NULL DEFAULT '',
    learning_direction TEXT NOT NULL DEFAULT 'comprehensive' CHECK (
        learning_direction IN ('agriculture', 'ecommerce', 'handcraft', 'comprehensive')
    ),
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS interest_tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_key TEXT NOT NULL CHECK (group_key IN ('crop', 'skill', 'job')),
    name TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    UNIQUE (group_key, name)
);

CREATE TABLE IF NOT EXISTS student_interest_tags (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tag_id INTEGER NOT NULL REFERENCES interest_tags(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, tag_id)
);

CREATE TABLE IF NOT EXISTS onboarding_states (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    portal TEXT NOT NULL CHECK (
        portal IN ('student', 'teacher', 'enterprise', 'government', 'admin')
    ),
    outcome TEXT NOT NULL CHECK (outcome IN ('completed', 'skipped')),
    completed_at TEXT NOT NULL,
    PRIMARY KEY (user_id, portal)
);

CREATE TABLE IF NOT EXISTS resumes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    education_json TEXT NOT NULL DEFAULT '[]',
    work_experiences_json TEXT NOT NULL DEFAULT '[]',
    skills_json TEXT NOT NULL DEFAULT '[]',
    version INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS resume_revisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    resume_id INTEGER NOT NULL REFERENCES resumes(id) ON DELETE CASCADE,
    version INTEGER NOT NULL CHECK (version > 0),
    education_json TEXT NOT NULL,
    work_experiences_json TEXT NOT NULL,
    skills_json TEXT NOT NULL,
    saved_at TEXT NOT NULL,
    UNIQUE (resume_id, version)
);

CREATE TABLE IF NOT EXISTS resume_optimization_offers (
    offer_id TEXT PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    base_version INTEGER NOT NULL CHECK (base_version > 0),
    suggestions_json TEXT NOT NULL,
    rewritten_json TEXT,
    status TEXT NOT NULL CHECK (status IN ('offered', 'adopted', 'discarded')),
    created_at TEXT NOT NULL,
    resolved_at TEXT
);

CREATE TABLE IF NOT EXISTS skill_visibility_settings (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    item_id TEXT NOT NULL,
    visible INTEGER NOT NULL CHECK (visible IN (0, 1)),
    updated_at TEXT NOT NULL,
    PRIMARY KEY (user_id, item_id)
);

CREATE TABLE IF NOT EXISTS job_favorites (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    job_id TEXT NOT NULL,
    title_snapshot TEXT NOT NULL,
    enterprise_name_snapshot TEXT NOT NULL,
    salary_snapshot TEXT NOT NULL,
    location_snapshot TEXT NOT NULL,
    description_snapshot TEXT NOT NULL,
    favorited_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (user_id, job_id)
);

CREATE TABLE IF NOT EXISTS courses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    direction TEXT NOT NULL CHECK (
        direction IN ('agriculture', 'ecommerce', 'handcraft')
    ),
    status TEXT NOT NULL CHECK (status IN ('draft', 'pending', 'published', 'offline')),
    duration_seconds INTEGER,
    media_url TEXT,
    published_at TEXT,
    summary TEXT NOT NULL DEFAULT '',
    teacher_name TEXT NOT NULL DEFAULT '',
    teacher_id INTEGER REFERENCES users(id),
    version INTEGER NOT NULL DEFAULT 1,
    media_source_type TEXT,
    content_tags_json TEXT NOT NULL DEFAULT '[]',
    rejection_opinion TEXT,
    submitted_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_courses_catalog
    ON courses(status, direction, published_at DESC, id DESC);

CREATE TABLE IF NOT EXISTS course_interest_tags (
    course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    tag_id INTEGER NOT NULL REFERENCES interest_tags(id) ON DELETE CASCADE,
    PRIMARY KEY (course_id, tag_id)
);

CREATE TABLE IF NOT EXISTS course_quizzes (
    course_id INTEGER PRIMARY KEY REFERENCES courses(id) ON DELETE CASCADE,
    enabled INTEGER NOT NULL DEFAULT 0 CHECK (enabled IN (0, 1)),
    scoring_rule TEXT NOT NULL DEFAULT '',
    questions_json TEXT NOT NULL DEFAULT '[]',
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS teacher_announcements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    announcement_id TEXT NOT NULL UNIQUE,
    teacher_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    event_id TEXT NOT NULL UNIQUE,
    delivery_status TEXT NOT NULL CHECK (
        delivery_status IN ('pending', 'sent', 'failed')
    ),
    delivery_result_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS teacher_announcement_delivery_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    announcement_id TEXT NOT NULL
        REFERENCES teacher_announcements(announcement_id) ON DELETE CASCADE,
    status TEXT NOT NULL CHECK (status IN ('pending', 'sent', 'failed')),
    result_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS teacher_course_status_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    from_status TEXT NOT NULL,
    to_status TEXT NOT NULL,
    actor_id INTEGER NOT NULL REFERENCES users(id),
    opinion TEXT,
    version INTEGER NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS content_comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    comment_id TEXT NOT NULL UNIQUE,
    content_type TEXT NOT NULL CHECK (
        content_type IN ('course_video', 'handcraft_teaching_video')
    ),
    content_id TEXT NOT NULL CHECK (length(trim(content_id)) > 0),
    author_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    parent_comment_id TEXT REFERENCES content_comments(comment_id),
    body TEXT NOT NULL CHECK (length(trim(body)) > 0),
    is_teacher_reply INTEGER NOT NULL DEFAULT 0 CHECK (
        is_teacher_reply IN (0, 1)
    ),
    is_visible INTEGER NOT NULL DEFAULT 1 CHECK (is_visible IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS teacher_learning_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id TEXT NOT NULL UNIQUE,
    teacher_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    sections_json TEXT NOT NULL,
    stats_snapshot_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS message_conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    participant_low_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    participant_high_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    CHECK (participant_low_id < participant_high_id),
    UNIQUE (participant_low_id, participant_high_id)
);

CREATE TABLE IF NOT EXISTS private_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL
        REFERENCES message_conversations(id) ON DELETE CASCADE,
    sender_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    body TEXT NOT NULL CHECK (length(trim(body)) > 0),
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_private_messages_conversation
    ON private_messages(conversation_id, created_at, id);

CREATE TABLE IF NOT EXISTS private_message_views (
    message_id INTEGER NOT NULL REFERENCES private_messages(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    read_at TEXT,
    cleared_at TEXT,
    PRIMARY KEY (message_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_private_views_unread
    ON private_message_views(user_id, read_at, cleared_at);

CREATE TABLE IF NOT EXISTS system_notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recipient_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    event_key TEXT NOT NULL,
    event_type TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    source_type TEXT,
    source_id TEXT,
    source_available INTEGER NOT NULL DEFAULT 1 CHECK (source_available IN (0, 1)),
    created_at TEXT NOT NULL,
    read_at TEXT,
    cleared_at TEXT,
    UNIQUE (recipient_id, event_key)
);

CREATE INDEX IF NOT EXISTS idx_notifications_unread
    ON system_notifications(recipient_id, read_at, cleared_at, created_at DESC);

CREATE TABLE IF NOT EXISTS agri_product_selections (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    product_key TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agri_product_subscriptions (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    product_key TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (user_id, product_key)
);

CREATE INDEX IF NOT EXISTS idx_agri_product_subscriptions_active
    ON agri_product_subscriptions(product_key, is_active, user_id);

CREATE TABLE IF NOT EXISTS agri_qa_conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_agri_qa_conversations_user
    ON agri_qa_conversations(user_id, updated_at DESC, id DESC);

CREATE TABLE IF NOT EXISTS agri_qa_turns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL
        REFERENCES agri_qa_conversations(id) ON DELETE CASCADE,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    input_mode TEXT NOT NULL CHECK (input_mode IN ('text', 'voice')),
    answer_mode TEXT NOT NULL CHECK (answer_mode IN ('ai', 'local_kb')),
    suggestions_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_agri_qa_turns_conversation
    ON agri_qa_turns(conversation_id, created_at, id);

CREATE TABLE IF NOT EXISTS agri_diagnosis_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    product_key TEXT NOT NULL,
    affected_part TEXT NOT NULL,
    symptoms_json TEXT NOT NULL,
    status TEXT NOT NULL CHECK (
        status IN ('in_progress', 'completed', 'abandoned')
    ),
    round_count INTEGER NOT NULL DEFAULT 0 CHECK (round_count BETWEEN 0 AND 5),
    conclusion_json TEXT,
    limited INTEGER NOT NULL DEFAULT 0 CHECK (limited IN (0, 1)),
    pending_question TEXT,
    pending_question_round INTEGER CHECK (
        pending_question_round BETWEEN 1 AND 5
    ),
    source_session_id INTEGER REFERENCES agri_diagnosis_sessions(id),
    source_followup_id INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    abandoned_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_agri_diagnosis_user_status
    ON agri_diagnosis_sessions(user_id, status, updated_at DESC, id DESC);

CREATE TABLE IF NOT EXISTS agri_diagnosis_answers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL
        REFERENCES agri_diagnosis_sessions(id) ON DELETE CASCADE,
    round_no INTEGER NOT NULL CHECK (round_no BETWEEN 1 AND 5),
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    input_mode TEXT NOT NULL CHECK (input_mode IN ('text', 'voice')),
    ai_status TEXT NOT NULL CHECK (
        ai_status IN ('follow_up_required', 'conclusion_ready')
    ),
    created_at TEXT NOT NULL,
    UNIQUE (session_id, round_no)
);

CREATE TABLE IF NOT EXISTS agri_diagnosis_followups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL
        REFERENCES agri_diagnosis_sessions(id) ON DELETE CASCADE,
    outcome TEXT NOT NULL CHECK (outcome IN ('improved', 'unchanged', 'worsened')),
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_agri_followups_session
    ON agri_diagnosis_followups(session_id, created_at, id);

CREATE TABLE IF NOT EXISTS agri_self_tests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    diagnosis_session_id INTEGER NOT NULL UNIQUE
        REFERENCES agri_diagnosis_sessions(id) ON DELETE CASCADE,
    questions_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agri_self_test_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    self_test_id INTEGER NOT NULL REFERENCES agri_self_tests(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    answers_json TEXT NOT NULL,
    result_json TEXT NOT NULL,
    score INTEGER NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agri_course_progress (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    duration_seconds INTEGER NOT NULL CHECK (duration_seconds > 0),
    furthest_position_seconds INTEGER NOT NULL DEFAULT 0 CHECK (
        furthest_position_seconds >= 0
    ),
    resume_position_seconds INTEGER NOT NULL DEFAULT 0 CHECK (
        resume_position_seconds >= 0
    ),
    progress_percent INTEGER NOT NULL DEFAULT 0 CHECK (
        progress_percent BETWEEN 0 AND 100
    ),
    watched_seconds INTEGER NOT NULL DEFAULT 0 CHECK (watched_seconds >= 0),
    completed_at TEXT,
    last_viewed_at TEXT,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (user_id, course_id)
);

CREATE TABLE IF NOT EXISTS agri_course_quiz_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    answers_json TEXT NOT NULL,
    result_json TEXT NOT NULL,
    score INTEGER NOT NULL CHECK (score BETWEEN 0 AND 100),
    is_formal INTEGER NOT NULL DEFAULT 0 CHECK (is_formal IN (0, 1)),
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_agri_quiz_attempts_course
    ON agri_course_quiz_attempts(user_id, course_id, created_at DESC, id DESC);

CREATE TABLE IF NOT EXISTS ecommerce_live_script_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    product_name TEXT NOT NULL,
    selling_points_json TEXT NOT NULL,
    price_text TEXT NOT NULL DEFAULT '',
    style TEXT NOT NULL CHECK (style IN ('enthusiastic', 'professional', 'humorous')),
    script_json TEXT NOT NULL,
    is_current INTEGER NOT NULL DEFAULT 1 CHECK (is_current IN (0, 1)),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ecommerce_simulation_trainings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    scene_key TEXT NOT NULL,
    segments_json TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('draft', 'completed')),
    scores_json TEXT,
    total_score INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS ecommerce_copy_training_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    product_type TEXT NOT NULL,
    scene_key TEXT NOT NULL,
    status TEXT NOT NULL CHECK (
        status IN (
            'case_ready', 'critique_ready', 'copy_ready', 'completed'
        )
    ),
    case_json TEXT NOT NULL,
    learner_critique TEXT,
    reference_json TEXT,
    optimized_prompt TEXT,
    revised_copy TEXT,
    optimization_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS ecommerce_store_plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    store_type TEXT NOT NULL,
    platform TEXT NOT NULL,
    style_preference TEXT NOT NULL,
    plan_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ecommerce_customer_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    scenario_key TEXT NOT NULL,
    goal_criteria_json TEXT NOT NULL,
    status TEXT NOT NULL CHECK (
        status IN ('active', 'goal_reached', 'completed')
    ),
    end_suggested INTEGER NOT NULL DEFAULT 0 CHECK (end_suggested IN (0, 1)),
    confirmed_at TEXT,
    summary_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS ecommerce_customer_turns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL
        REFERENCES ecommerce_customer_sessions(id) ON DELETE CASCADE,
    turn_no INTEGER NOT NULL,
    customer_message TEXT NOT NULL,
    student_reply TEXT,
    analysis_json TEXT,
    created_at TEXT NOT NULL,
    UNIQUE (session_id, turn_no)
);

CREATE TABLE IF NOT EXISTS heritage_craft_progress (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    craft_key TEXT NOT NULL,
    completed_steps_json TEXT NOT NULL DEFAULT '[]',
    resume_step_no INTEGER CHECK (
        resume_step_no IS NULL OR resume_step_no BETWEEN 1 AND 6
    ),
    updated_at TEXT NOT NULL,
    PRIMARY KEY (user_id, craft_key)
);

CREATE TABLE IF NOT EXISTS handcraft_active_learning_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    source_type TEXT NOT NULL CHECK (
        source_type IN ('craft', 'ar', 'course')
    ),
    source_key TEXT NOT NULL,
    segment_no INTEGER NOT NULL CHECK (segment_no > 0),
    started_at TEXT NOT NULL,
    last_heartbeat_at TEXT NOT NULL,
    last_heartbeat_epoch REAL NOT NULL,
    last_heartbeat_seq INTEGER NOT NULL DEFAULT 0 CHECK (
        last_heartbeat_seq >= 0
    ),
    accumulated_seconds INTEGER NOT NULL DEFAULT 0 CHECK (
        accumulated_seconds BETWEEN 0 AND 7200
    ),
    settled_seconds INTEGER NOT NULL DEFAULT 0 CHECK (
        settled_seconds BETWEEN 0 AND accumulated_seconds
    ),
    closed_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (user_id, source_type, source_key, segment_no)
);

CREATE INDEX IF NOT EXISTS idx_active_learning_source
    ON handcraft_active_learning_sessions(
        user_id, source_type, source_key, id DESC
    );

CREATE TABLE IF NOT EXISTS heritage_videos (
    video_id TEXT PRIMARY KEY,
    craft_key TEXT NOT NULL,
    title TEXT NOT NULL,
    review_status TEXT NOT NULL CHECK (
        review_status IN ('pending', 'approved', 'rejected', 'offline')
    ),
    source_available INTEGER NOT NULL DEFAULT 1 CHECK (
        source_available IN (0, 1)
    ),
    media_url TEXT NOT NULL DEFAULT '',
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    rejection_opinion TEXT,
    published_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_heritage_videos_craft_status
    ON heritage_videos(craft_key, review_status, published_at DESC, video_id);

CREATE TABLE IF NOT EXISTS handcraft_learning_outcomes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    outcome_type TEXT NOT NULL,
    source_key TEXT NOT NULL,
    source_id INTEGER,
    created_at TEXT NOT NULL,
    source_available INTEGER NOT NULL DEFAULT 1 CHECK (
        source_available IN (0, 1)
    ),
    summary TEXT NOT NULL,
    score INTEGER,
    is_formal INTEGER NOT NULL DEFAULT 0 CHECK (is_formal IN (0, 1)),
    archive_written INTEGER NOT NULL DEFAULT 0 CHECK (
        archive_written IN (0, 1)
    ),
    UNIQUE (user_id, outcome_type, source_key)
);

CREATE INDEX IF NOT EXISTS idx_handcraft_outcomes_user_created
    ON handcraft_learning_outcomes(user_id, created_at, id);

CREATE TABLE IF NOT EXISTS points_accounts (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    balance INTEGER NOT NULL DEFAULT 0 CHECK (balance >= 0),
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS points_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    transaction_type TEXT NOT NULL CHECK (
        transaction_type IN ('award', 'spend', 'refund', 'expire')
    ),
    source_module TEXT NOT NULL,
    source_event_id TEXT NOT NULL,
    delta INTEGER NOT NULL CHECK (delta <> 0),
    balance_after INTEGER NOT NULL CHECK (balance_after >= 0),
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    UNIQUE (
        user_id, transaction_type, source_module, source_event_id
    )
);

CREATE INDEX IF NOT EXISTS idx_points_transactions_user_created
    ON points_transactions(user_id, created_at DESC, id DESC);

CREATE TABLE IF NOT EXISTS points_lots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    award_transaction_id INTEGER NOT NULL
        REFERENCES points_transactions(id) ON DELETE CASCADE,
    original_points INTEGER NOT NULL CHECK (original_points > 0),
    remaining_points INTEGER NOT NULL CHECK (
        remaining_points >= 0 AND remaining_points <= original_points
    ),
    expires_at TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_points_lots_user_expiry
    ON points_lots(user_id, expires_at, id);

CREATE TABLE IF NOT EXISTS points_allocations (
    transaction_id INTEGER NOT NULL
        REFERENCES points_transactions(id) ON DELETE CASCADE,
    lot_id INTEGER NOT NULL REFERENCES points_lots(id) ON DELETE CASCADE,
    points INTEGER NOT NULL CHECK (points > 0),
    PRIMARY KEY (transaction_id, lot_id)
);

CREATE TABLE IF NOT EXISTS points_event_inbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    source_module TEXT NOT NULL,
    event_type TEXT NOT NULL,
    source_event_id TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    duration_seconds INTEGER CHECK (
        duration_seconds IS NULL OR duration_seconds >= 0
    ),
    status TEXT NOT NULL DEFAULT 'pending' CHECK (
        status IN ('pending', 'processed', 'failed')
    ),
    error TEXT,
    processed_at TEXT,
    created_at TEXT NOT NULL,
    UNIQUE (user_id, source_module, event_type, source_event_id)
);

CREATE INDEX IF NOT EXISTS idx_points_event_inbox_status
    ON points_event_inbox(status, created_at, id);

CREATE TABLE IF NOT EXISTS points_learning_accruals (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    source_module TEXT NOT NULL,
    source_key TEXT NOT NULL,
    accumulated_seconds INTEGER NOT NULL DEFAULT 0 CHECK (
        accumulated_seconds >= 0
    ),
    awarded_units INTEGER NOT NULL DEFAULT 0 CHECK (awarded_units >= 0),
    consumed_units INTEGER NOT NULL DEFAULT 0 CHECK (consumed_units >= 0),
    updated_at TEXT NOT NULL,
    PRIMARY KEY (user_id, source_module, source_key)
);

CREATE TABLE IF NOT EXISTS points_policy_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version TEXT NOT NULL,
    policy_json TEXT NOT NULL,
    observed_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_points_policy_snapshots_observed
    ON points_policy_snapshots(observed_at DESC, id DESC);

CREATE TABLE IF NOT EXISTS points_notification_outbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL CHECK (event_type = 'points_expired'),
    event_id TEXT NOT NULL,
    transaction_id INTEGER NOT NULL
        REFERENCES points_transactions(id) ON DELETE CASCADE,
    payload_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (
        status IN ('pending', 'sent')
    ),
    created_at TEXT NOT NULL,
    sent_at TEXT,
    UNIQUE (event_type, event_id)
);

CREATE INDEX IF NOT EXISTS idx_points_notification_outbox_pending
    ON points_notification_outbox(status, user_id, id);

CREATE TABLE IF NOT EXISTS redemptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    reward_id TEXT NOT NULL,
    reward_name TEXT NOT NULL,
    reward_snapshot_json TEXT NOT NULL DEFAULT '{}',
    points_cost INTEGER NOT NULL CHECK (points_cost > 0),
    request_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK (
        status IN ('pending', 'issued', 'verified', 'canceled')
    ),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    canceled_at TEXT,
    UNIQUE (user_id, request_id)
);

CREATE INDEX IF NOT EXISTS idx_redemptions_user_created
    ON redemptions(user_id, created_at DESC, id DESC);

CREATE TABLE IF NOT EXISTS reward_stock_reservations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reservation_id TEXT NOT NULL UNIQUE,
    redemption_id INTEGER NOT NULL UNIQUE
        REFERENCES redemptions(id) ON DELETE CASCADE,
    reward_id TEXT NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    status TEXT NOT NULL CHECK (status IN ('reserved', 'released')),
    created_at TEXT NOT NULL,
    released_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_reward_stock_reservations_reward_status
    ON reward_stock_reservations(reward_id, status);

CREATE TABLE IF NOT EXISTS fulfillments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    redemption_id INTEGER NOT NULL UNIQUE
        REFERENCES redemptions(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status TEXT NOT NULL CHECK (
        status IN ('pending', 'issued', 'verified', 'canceled')
    ),
    issued_at TEXT,
    verified_at TEXT,
    canceled_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_fulfillments_user_status
    ON fulfillments(user_id, status, updated_at DESC, id DESC);

CREATE TABLE IF NOT EXISTS fulfillment_notification_outbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fulfillment_id INTEGER NOT NULL
        REFERENCES fulfillments(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL CHECK (
        event_type IN ('issued', 'cancelled')
    ),
    event_id TEXT NOT NULL UNIQUE,
    payload_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (
        status IN ('pending', 'sent')
    ),
    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    last_error TEXT,
    created_at TEXT NOT NULL,
    sent_at TEXT,
    UNIQUE (fulfillment_id, event_type)
);

CREATE INDEX IF NOT EXISTS idx_fulfillment_outbox_pending
    ON fulfillment_notification_outbox(status, created_at, id);

CREATE TABLE IF NOT EXISTS handcraft_notification_outbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL CHECK (
        event_type IN (
            'redemption_succeeded', 'review_approved', 'review_rejected'
        )
    ),
    event_id TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (
        status IN ('pending', 'sent')
    ),
    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    last_error TEXT,
    created_at TEXT NOT NULL,
    sent_at TEXT,
    UNIQUE (event_type, event_id)
);

CREATE INDEX IF NOT EXISTS idx_handcraft_notification_outbox_pending
    ON handcraft_notification_outbox(status, created_at, id);

CREATE TABLE IF NOT EXISTS job_positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL UNIQUE,
    enterprise_id INTEGER NOT NULL REFERENCES users(id),
    title TEXT NOT NULL,
    salary TEXT NOT NULL,
    location TEXT NOT NULL,
    category_id INTEGER NOT NULL REFERENCES interest_tags(id),
    category_name TEXT NOT NULL,
    description TEXT NOT NULL,
    review_status TEXT NOT NULL CHECK (
        review_status IN ('pending', 'approved', 'rejected')
    ),
    version INTEGER NOT NULL CHECK (version > 0),
    rejection_opinion TEXT,
    published_at TEXT,
    deleted_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_job_positions_enterprise_status
    ON job_positions(enterprise_id, deleted_at, review_status, updated_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_job_positions_public
    ON job_positions(deleted_at, review_status, published_at DESC, job_id);

CREATE TABLE IF NOT EXISTS job_applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id TEXT NOT NULL UNIQUE,
    job_id TEXT NOT NULL REFERENCES job_positions(job_id),
    enterprise_id INTEGER NOT NULL REFERENCES users(id),
    student_id INTEGER NOT NULL REFERENCES users(id),
    student_name TEXT NOT NULL,
    job_title_snapshot TEXT NOT NULL,
    resume_snapshot_json TEXT NOT NULL,
    skill_profile_snapshot_json TEXT,
    skill_profile_attached INTEGER NOT NULL DEFAULT 0 CHECK (
        skill_profile_attached IN (0, 1)
    ),
    status TEXT NOT NULL CHECK (
        status IN ('pending', 'viewed', 'intent', 'unsuitable')
    ),
    status_version INTEGER NOT NULL DEFAULT 1 CHECK (status_version > 0),
    position_closed_at TEXT,
    close_reason TEXT,
    idempotency_key TEXT NOT NULL,
    submitted_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (student_id, job_id),
    UNIQUE (enterprise_id, idempotency_key)
);

CREATE INDEX IF NOT EXISTS idx_job_applications_enterprise
    ON job_applications(
        enterprise_id, submitted_at DESC, application_id
    );

CREATE INDEX IF NOT EXISTS idx_job_applications_job_status
    ON job_applications(job_id, status, submitted_at DESC, application_id);

CREATE TABLE IF NOT EXISTS job_application_status_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id TEXT NOT NULL REFERENCES job_applications(application_id),
    sequence_no INTEGER NOT NULL CHECK (sequence_no > 0),
    previous_status TEXT NOT NULL,
    new_status TEXT NOT NULL,
    actor_enterprise_id INTEGER NOT NULL REFERENCES users(id),
    event_id TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    UNIQUE (application_id, sequence_no)
);

CREATE TABLE IF NOT EXISTS enterprise_notification_outbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL CHECK (
        event_type IN (
            'application_submitted',
            'application_status',
            'position_closed'
        )
    ),
    event_id TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (
        status IN ('pending', 'sent')
    ),
    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    last_error TEXT,
    created_at TEXT NOT NULL,
    sent_at TEXT,
    UNIQUE (event_type, event_id)
);

CREATE INDEX IF NOT EXISTS idx_enterprise_outbox_pending
    ON enterprise_notification_outbox(status, created_at, id);

CREATE TABLE IF NOT EXISTS government_policies (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    category_code TEXT NOT NULL CHECK (
        category_code IN (
            'subsidy', 'ecommerce', 'heritage', 'training',
            'certification', 'general', 'entrepreneurship'
        )
    ),
    status TEXT NOT NULL CHECK (status IN ('active', 'unpublished')),
    view_count INTEGER NOT NULL DEFAULT 0 CHECK (view_count >= 0),
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    created_by INTEGER NOT NULL REFERENCES users(id),
    published_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS government_news (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    category_code TEXT NOT NULL CHECK (
        category_code IN ('news', 'disaster_warning', 'policy_update')
    ),
    view_count INTEGER NOT NULL DEFAULT 0 CHECK (view_count >= 0),
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    created_by INTEGER NOT NULL REFERENCES users(id),
    published_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS government_publication_requests (
    content_type TEXT NOT NULL CHECK (content_type IN ('policy', 'news')),
    request_id TEXT NOT NULL,
    content_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (content_type, request_id)
);

CREATE TABLE IF NOT EXISTS government_view_events (
    content_type TEXT NOT NULL CHECK (content_type IN ('policy', 'news')),
    content_id TEXT NOT NULL,
    view_event_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (content_type, view_event_id)
);

CREATE TABLE IF NOT EXISTS local_resource_dialect_turns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    turn_id TEXT NOT NULL UNIQUE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    dialect_code TEXT NOT NULL CHECK (dialect_code IN ('yue', 'hak', 'nan')),
    recognized_text TEXT NOT NULL CHECK (length(trim(recognized_text)) > 0),
    dialect_answer TEXT NOT NULL CHECK (length(trim(dialect_answer)) > 0),
    mandarin_answer TEXT NOT NULL CHECK (length(trim(mandarin_answer)) > 0),
    status TEXT NOT NULL CHECK (status = 'completed'),
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_local_resource_dialect_user
    ON local_resource_dialect_turns(user_id, created_at DESC, id DESC);

CREATE TABLE IF NOT EXISTS local_resource_policy_subscriptions (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    category_code TEXT NOT NULL CHECK (
        category_code IN (
            'subsidy', 'ecommerce', 'heritage', 'training',
            'certification', 'general', 'entrepreneurship'
        )
    ),
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (user_id, category_code)
);

CREATE INDEX IF NOT EXISTS idx_local_resource_policy_subscribers
    ON local_resource_policy_subscriptions(category_code, is_active, user_id);

CREATE TABLE IF NOT EXISTS local_resource_success_cases (
    case_id TEXT PRIMARY KEY,
    title TEXT NOT NULL CHECK (length(trim(title)) > 0),
    summary TEXT NOT NULL CHECK (length(trim(summary)) > 0),
    background TEXT NOT NULL CHECK (length(trim(background)) > 0),
    journey TEXT NOT NULL CHECK (length(trim(journey)) > 0),
    lessons TEXT NOT NULL CHECK (length(trim(lessons)) > 0),
    sort_order INTEGER NOT NULL DEFAULT 0,
    published_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    is_demo INTEGER NOT NULL DEFAULT 1 CHECK (is_demo IN (0, 1))
);

CREATE INDEX IF NOT EXISTS idx_local_resource_cases_order
    ON local_resource_success_cases(sort_order, case_id);

CREATE TABLE IF NOT EXISTS ai_companion_conversations (
    conversation_id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title TEXT NOT NULL CHECK (length(trim(title)) > 0),
    last_intent TEXT NOT NULL CHECK (
        last_intent IN ('platform_usage', 'learning_question', 'out_of_scope')
    ),
    jump_target TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ai_companion_conversations_user
    ON ai_companion_conversations(
        user_id, updated_at DESC, conversation_id DESC
    );

CREATE TABLE IF NOT EXISTS ai_companion_messages (
    message_id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL
        REFERENCES ai_companion_conversations(conversation_id)
        ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL CHECK (length(trim(content)) > 0),
    intent TEXT CHECK (
        intent IS NULL OR
        intent IN ('platform_usage', 'learning_question', 'out_of_scope')
    ),
    jump_target TEXT,
    client_request_id TEXT,
    created_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_ai_companion_messages_request
    ON ai_companion_messages(user_id, client_request_id)
    WHERE client_request_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_ai_companion_messages_conversation
    ON ai_companion_messages(conversation_id, created_at, message_id);
"""


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        database_path = Path(current_app.config["DATABASE_PATH"])
        database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        g.db = connection
    return g.db


def _ensure_course_duration_column(db: sqlite3.Connection) -> None:
    columns = {row["name"] for row in db.execute("PRAGMA table_info(courses)")}
    if "duration_seconds" not in columns:
        db.execute("ALTER TABLE courses ADD COLUMN duration_seconds INTEGER")
        db.execute(
            """
            UPDATE courses
            SET duration_seconds = 300
            WHERE duration_seconds IS NULL
            """
        )


def _ensure_course_media_url_column(db: sqlite3.Connection) -> None:
    columns = {row["name"] for row in db.execute("PRAGMA table_info(courses)")}
    if "media_url" not in columns:
        db.execute("ALTER TABLE courses ADD COLUMN media_url TEXT")


def _ensure_points_consumed_units_column(
    db: sqlite3.Connection,
) -> None:
    columns = {
        row["name"]
        for row in db.execute(
            "PRAGMA table_info(points_learning_accruals)"
        )
    }
    if "consumed_units" not in columns:
        db.execute(
            """
            ALTER TABLE points_learning_accruals
            ADD COLUMN consumed_units INTEGER NOT NULL DEFAULT 0
            CHECK (consumed_units >= 0)
            """
        )
        db.execute(
            """
            UPDATE points_learning_accruals
            SET consumed_units = awarded_units
            """
        )


def _ensure_teacher_console_columns(db: sqlite3.Connection) -> None:
    columns = {row["name"] for row in db.execute("PRAGMA table_info(courses)")}
    additions = {
        "teacher_id": "INTEGER REFERENCES users(id)",
        "version": "INTEGER NOT NULL DEFAULT 1",
        "media_source_type": "TEXT",
        "content_tags_json": "TEXT NOT NULL DEFAULT '[]'",
        "rejection_opinion": "TEXT",
        "submitted_at": "TEXT",
    }
    for name, definition in additions.items():
        if name not in columns:
            db.execute(f"ALTER TABLE courses ADD COLUMN {name} {definition}")


def _ensure_job_matching_columns(db: sqlite3.Connection) -> None:
    columns = {
        row["name"] for row in db.execute("PRAGMA table_info(resumes)")
    }
    additions = {
        "education_json": "TEXT NOT NULL DEFAULT '[]'",
        "work_experiences_json": "TEXT NOT NULL DEFAULT '[]'",
        "skills_json": "TEXT NOT NULL DEFAULT '[]'",
        "version": "INTEGER NOT NULL DEFAULT 0",
        "updated_at": "TEXT",
    }
    for name, definition in additions.items():
        if name not in columns:
            db.execute(
                f"ALTER TABLE resumes ADD COLUMN {name} {definition}"
            )


def init_db(connection: sqlite3.Connection | None = None) -> None:
    db = connection or get_db()
    db.executescript(SCHEMA_SQL)
    _ensure_course_duration_column(db)
    _ensure_course_media_url_column(db)
    _ensure_points_consumed_units_column(db)
    _ensure_teacher_console_columns(db)
    _ensure_job_matching_columns(db)
    seed_interest_tags(db)
    seed_ecommerce_course_fixtures(db)
    seed_handcraft_fixtures(db)
    from app.local_resources.cases import seed_local_resource_cases

    seed_local_resource_cases(db)
    db.commit()


def close_db(error: BaseException | None = None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()
