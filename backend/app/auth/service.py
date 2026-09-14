from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from werkzeug.security import generate_password_hash

from app.auth.validators import validate_registration
from app.db import get_db
from app.session_manager import issue_session


class DuplicateUsernameError(Exception):
    pass


class InvalidRegistrationError(ValueError):
    def __init__(self, errors: dict[str, str]) -> None:
        super().__init__("Invalid registration payload")
        self.errors = errors


def register_account(payload: dict, session_hours: int) -> dict:
    errors = validate_registration(payload)
    if errors:
        raise InvalidRegistrationError(errors)

    role = str(payload["role"])
    username = str(payload["username"]).strip()
    password = str(payload["password"])
    name = str(payload["name"]).strip()
    now = datetime.now(timezone.utc).isoformat()
    db = get_db()

    with db:
        try:
            cursor = db.execute(
                """
                INSERT INTO users (
                    username, password_hash, name, role, is_enabled, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, 1, ?, ?)
                """,
                (username, generate_password_hash(password), name, role, now, now),
            )
        except sqlite3.IntegrityError as error:
            raise DuplicateUsernameError from error

        user_id = int(cursor.lastrowid)

        if role == "student":
            db.execute(
                """
                INSERT INTO student_profiles (user_id, learning_direction, updated_at)
                VALUES (?, 'comprehensive', ?)
                """,
                (user_id, now),
            )
            db.execute(
                "INSERT INTO resumes (user_id, created_at) VALUES (?, ?)",
                (user_id, now),
            )

        session_state = "pending" if role == "student" else "active"
        session_token = issue_session(user_id, session_state, session_hours)

    return {
        "next_step": "interest-tags" if role == "student" else "portal",
        "session_token": session_token,
        "user": {
            "id": user_id,
            "username": username,
            "name": name,
            "role": role,
        },
    }
