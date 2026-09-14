from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from werkzeug.security import generate_password_hash

from app import create_app
from app.db import get_db
from app.seed import (
    DEFAULT_COURSES,
    DEFAULT_INTEREST_TAGS,
    seed_courses,
    seed_interest_tags,
)


ROLE_ACCOUNTS = (
    ("student", "DEV_SEED_STUDENT_USERNAME", "student_demo", "本地学员"),
    ("teacher", "DEV_SEED_TEACHER_USERNAME", "teacher_demo", "本地教师"),
    (
        "enterprise",
        "DEV_SEED_ENTERPRISE_USERNAME",
        "enterprise_demo",
        "本地企业",
    ),
    (
        "government",
        "DEV_SEED_GOVERNMENT_USERNAME",
        "government_demo",
        "本地政府人员",
    ),
    (
        "super_admin",
        "DEV_SEED_SUPER_ADMIN_USERNAME",
        "super_admin_demo",
        "本地超级管理员",
    ),
    ("admin", "DEV_SEED_ADMIN_USERNAME", "admin_demo", "本地管理员"),
)


def _require_environment(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise ValueError(f"{name} is required")
    return value


def _validate_environment() -> tuple[str, str]:
    if os.environ.get("FLASK_ENV", "").strip().lower() == "production":
        raise ValueError("Local seed refuses to run in production")
    return (
        _require_environment("DEV_SEED_PASSWORD"),
        _require_environment("SECRET_KEY"),
    )


def _seed_accounts(connection, password: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    password_hash = generate_password_hash(password)

    for role, username_env, default_username, display_name in ROLE_ACCOUNTS:
        username = os.environ.get(username_env, "").strip() or default_username
        username_owner = connection.execute(
            """
            SELECT id, role
            FROM users
            WHERE username = ?
            """,
            (username,),
        ).fetchone()
        if username_owner is not None and username_owner["role"] != role:
            raise ValueError(
                f"{username_env} conflicts with another existing role"
            )

        existing = connection.execute(
            """
            SELECT id
            FROM users
            WHERE role = ?
            ORDER BY id
            LIMIT 1
            """,
            (role,),
        ).fetchone()
        if username_owner is None and existing is None:
            cursor = connection.execute(
                """
                INSERT INTO users (
                    username, password_hash, name, role, is_enabled,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, 1, ?, ?)
                """,
                (
                    username,
                    password_hash,
                    display_name,
                    role,
                    now,
                    now,
                ),
            )
            user_id = int(cursor.lastrowid)
        else:
            owner = username_owner if username_owner is not None else existing
            user_id = int(owner["id"])
            connection.execute(
                """
                UPDATE users
                SET
                    username = ?,
                    password_hash = ?,
                    name = ?,
                    role = ?,
                    is_enabled = 1,
                    updated_at = ?
                WHERE id = ?
                """,
                (username, password_hash, display_name, role, now, user_id),
            )

        if role == "student":
            connection.execute(
                """
                INSERT INTO student_profiles (
                    user_id, learning_direction, updated_at
                )
                VALUES (?, 'comprehensive', ?)
                ON CONFLICT (user_id) DO NOTHING
                """,
                (user_id, now),
            )
            connection.execute(
                """
                INSERT INTO resumes (user_id, created_at)
                VALUES (?, ?)
                ON CONFLICT (user_id) DO NOTHING
                """,
                (user_id, now),
            )


def seed_local_data(database_path: str | Path | None = None) -> dict[str, int]:
    password, secret_key = _validate_environment()
    config: dict[str, object] = {"SECRET_KEY": secret_key}
    if database_path is not None:
        config["DATABASE_PATH"] = str(database_path)

    app = create_app(config)
    with app.app_context():
        connection = get_db()
        seed_interest_tags(connection)
        seed_courses(connection)
        _seed_accounts(connection, password)
        connection.commit()

    return {
        "accounts": len(ROLE_ACCOUNTS),
        "courses": len(DEFAULT_COURSES),
        "tags": len(DEFAULT_INTEREST_TAGS),
    }


def main() -> None:
    try:
        result = seed_local_data()
    except ValueError as error:
        print(f"Local seed refused: {error}", file=sys.stderr)
        raise SystemExit(1) from error

    print(
        "Local seed complete: "
        f"{result['accounts']} accounts, "
        f"{result['courses']} courses, "
        f"{result['tags']} tags."
    )


if __name__ == "__main__":
    main()
