from __future__ import annotations

import sqlite3
from pathlib import Path

from flask import current_app, g


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
    db.commit()


def close_db(error: BaseException | None = None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()
