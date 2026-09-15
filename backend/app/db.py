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
