from __future__ import annotations

import hashlib
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone

from flask import Response, current_app
from werkzeug.wrappers import Response as WerkzeugResponse

from app.db import get_db


SESSION_COOKIE_NAME = "yx_session"
SESSION_STATES = {"pending", "active"}


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


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
) -> WerkzeugResponse:
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
