from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from werkzeug.security import check_password_hash, generate_password_hash

from app.auth.validators import validate_registration
from app.db import get_db
from app.session_manager import (
    issue_session,
    revoke_current_session,
    role_default_path,
)


class DuplicateUsernameError(Exception):
    pass


class InvalidRegistrationError(ValueError):
    def __init__(self, errors: dict[str, str]) -> None:
        super().__init__("Invalid registration payload")
        self.errors = errors


class DisabledAccountError(Exception):
    pass


def _user_payload(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "username": row["username"],
        "name": row["name"],
        "role": row["role"],
    }


def authenticate(username: str, password: str, session_hours: int) -> dict | None:
    normalized_username = str(username).strip()
    row = get_db().execute(
        "SELECT * FROM users WHERE username = ?",
        (normalized_username,),
    ).fetchone()
    if row is None or not check_password_hash(row["password_hash"], str(password)):
        return None
    if not row["is_enabled"]:
        raise DisabledAccountError

    revoke_current_session()
    session_token = issue_session(int(row["id"]), "active", session_hours)
    return {
        "session_token": session_token,
        "user": _user_payload(row),
        "default_path": role_default_path(row["role"]),
    }


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
