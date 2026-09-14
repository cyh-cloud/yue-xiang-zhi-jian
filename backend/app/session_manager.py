from __future__ import annotations

import hashlib
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Never
from urllib.parse import urlencode

from flask import Response, abort, current_app, jsonify, request

from app.db import get_db


SESSION_COOKIE_NAME = "yx_session"
SESSION_STATES = {"pending", "active"}
ROLE_DEFAULT_PATHS = {
    "student": "/student",
    "teacher": "/teacher",
    "enterprise": "/enterprise",
    "government": "/government",
    "super_admin": "/admin",
    "admin": "/admin",
}


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def role_default_path(role: str) -> str:
    try:
        return ROLE_DEFAULT_PATHS[role]
    except KeyError as error:
        raise ValueError(f"Unsupported user role: {role}") from error


def abort_session_required() -> Never:
    target = request.args.get("next") or request.full_path
    if target.endswith("?"):
        target = target[:-1]
    redirect = f"/login?{urlencode({'redirect': target})}"
    response = jsonify(
        success=False,
        message="未登录或会话已过期",
        redirect=redirect,
    )
    response.status_code = 401
    clear_session_cookie(response)
    abort(response)


def abort_disabled_account() -> Never:
    response = jsonify(
        success=False,
        message="账户已被禁用，请联系管理员",
    )
    response.status_code = 403
    clear_session_cookie(response)
    abort(response)


def clear_session_cookie(response: Response) -> Response:
    response.delete_cookie(
        SESSION_COOKIE_NAME,
        path="/",
        secure=bool(current_app.config.get("SESSION_COOKIE_SECURE", False)),
        httponly=True,
        samesite="Lax",
    )
    return response


def revoke_current_session() -> None:
    raw_token = request.cookies.get(SESSION_COOKIE_NAME)
    if not raw_token:
        return

    db = get_db()
    db.execute(
        "DELETE FROM sessions WHERE token_hash = ?",
        (_hash_token(raw_token),),
    )
    db.commit()


def load_session(
    required: bool = True,
    allowed_states: set[str] | None = None,
) -> dict | None:
    raw_token = request.cookies.get(SESSION_COOKIE_NAME)
    if not raw_token:
        if required:
            abort_session_required()
        return None

    token_hash = _hash_token(raw_token)
    row = get_db().execute(
        """
        SELECT s.token_hash, s.state, s.expires_at, u.*
        FROM sessions s
        JOIN users u ON u.id = s.user_id
        WHERE s.token_hash = ?
        """,
        (token_hash,),
    ).fetchone()
    if row is None:
        if required:
            abort_session_required()
        return None
    if row["expires_at"] <= utc_now_iso():
        get_db().execute(
            "DELETE FROM sessions WHERE token_hash = ?",
            (token_hash,),
        )
        get_db().commit()
        if required:
            abort_session_required()
        return None
    if not row["is_enabled"]:
        get_db().execute(
            "DELETE FROM sessions WHERE token_hash = ?",
            (token_hash,),
        )
        get_db().commit()
        abort_disabled_account()
    if allowed_states and row["state"] not in allowed_states:
        if required:
            abort_session_required()
        return None
    return dict(row)


def issue_session(user_id: int, state: str, session_hours: int) -> str:
    if state not in SESSION_STATES:
        raise ValueError(f"Unsupported session state: {state}")
    if session_hours <= 0:
        raise ValueError("session_hours must be positive")

    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=session_hours)
    db = get_db()
    owns_transaction = not db.in_transaction

    try:
        db.execute(
            """
            INSERT INTO sessions (token_hash, user_id, state, expires_at, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                _hash_token(token),
                user_id,
                state,
                expires_at.isoformat(),
                now.isoformat(),
            ),
        )
        if owns_transaction:
            db.commit()
    except sqlite3.Error:
        if owns_transaction:
            db.rollback()
        raise

    return token


def apply_session_cookie(
    response: Response, token: str, max_age: int
) -> Response:
    response.set_cookie(
        SESSION_COOKIE_NAME,
        token,
        max_age=max_age,
        httponly=True,
        secure=bool(current_app.config.get("SESSION_COOKIE_SECURE", False)),
        samesite="Lax",
        path="/",
    )
    return response
