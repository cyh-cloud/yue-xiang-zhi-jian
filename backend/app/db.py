from __future__ import annotations

import sqlite3
from pathlib import Path

from flask import current_app, g

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
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS courses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    direction TEXT NOT NULL CHECK (
        direction IN ('agriculture', 'ecommerce', 'handcraft')
    ),
    status TEXT NOT NULL CHECK (status IN ('draft', 'pending', 'published', 'offline')),
    published_at TEXT,
    summary TEXT NOT NULL DEFAULT '',
    teacher_name TEXT NOT NULL DEFAULT '',
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


def init_db(connection: sqlite3.Connection | None = None) -> None:
    db = connection or get_db()
    db.executescript(SCHEMA_SQL)
    seed_interest_tags(db)
    db.commit()


def close_db(error: BaseException | None = None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()
