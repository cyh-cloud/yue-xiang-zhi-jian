from __future__ import annotations

import os
import re
import sqlite3

from flask import current_app
from werkzeug.security import generate_password_hash

from app.admin_console.audit import record_admin_audit
from app.admin_console.errors import (
    ProviderConflictError,
    ProviderNotFoundError,
    ProviderUnavailableError,
    ProviderValidationError,
)
from app.admin_console.time_utils import platform_now_iso
from app.auth.validators import validate_registration
from app.db import get_db
from app.messaging.events import emit_password_reset


MANAGED_ROLES = frozenset(
    {"enterprise", "government", "admin", "super_admin"}
)
ACCOUNT_ROLES = frozenset(
    {"student", "teacher", "enterprise", "government", "admin", "super_admin"}
)
MANAGED_USERNAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{2,31}$")


def _account_payload(row: sqlite3.Row) -> dict:
    return {
        "id": int(row["id"]),
        "username": str(row["username"]),
        "name": str(row["name"]),
        "role": str(row["role"]),
        "is_enabled": bool(row["is_enabled"]),
        "created_at": str(row["created_at"]),
        "updated_at": str(row["updated_at"]),
    }


def _validation_error(errors: dict[str, str]) -> ProviderValidationError:
    return ProviderValidationError(
        "账户信息不正确",
        code="account_validation_failed",
        details=errors,
    )


def _not_found() -> ProviderNotFoundError:
    return ProviderNotFoundError(
        "账户不存在",
        code="account_not_found",
        details={},
    )


def configured_initial_password() -> str | None:
    value = current_app.config.get("INITIAL_SUPER_ADMIN_PASSWORD")
    if value is None:
        value = os.environ.get("INITIAL_SUPER_ADMIN_PASSWORD")
    normalized = str(value or "")
    return normalized or None


def list_accounts(
    role: str | None = None,
    keyword: str | None = None,
) -> list[dict]:
    normalized_role = str(role or "").strip() or None
    if normalized_role is not None and normalized_role not in ACCOUNT_ROLES:
        raise _validation_error({"role": "角色不正确"})

    normalized_keyword = str(keyword or "").strip()
    clauses: list[str] = []
    parameters: list[str] = []
    if normalized_role is not None:
        clauses.append("role = ?")
        parameters.append(normalized_role)
    if normalized_keyword:
        clauses.append("(username LIKE ? OR name LIKE ?)")
        pattern = f"%{normalized_keyword}%"
        parameters.extend((pattern, pattern))

    where_clause = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = get_db().execute(
        f"""
        SELECT
            id, username, name, role, is_enabled, created_at, updated_at
        FROM users
        {where_clause}
        ORDER BY created_at DESC, id DESC
        """,
        parameters,
    ).fetchall()
    return [_account_payload(row) for row in rows]


def get_account(user_id: int) -> dict:
    if (
        isinstance(user_id, bool)
        or not isinstance(user_id, int)
        or user_id <= 0
    ):
        raise _not_found()
    row = get_db().execute(
        """
        SELECT
            id, username, name, role, is_enabled, created_at, updated_at
        FROM users
        WHERE id = ?
        """,
        (user_id,),
    ).fetchone()
    if row is None:
        raise _not_found()
    return _account_payload(row)


def _validated_managed_payload(payload: dict) -> dict[str, str]:
    if not isinstance(payload, dict):
        raise _validation_error({"payload": "请求内容格式不正确"})

    role = str(payload.get("role") or "").strip()
    if role not in MANAGED_ROLES:
        raise _validation_error({"role": "该角色不支持管理"})

    username = str(payload.get("username") or "").strip()
    password = str(payload.get("password") or "")
    name = str(payload.get("name") or "").strip()
    errors = validate_registration(
        {
            "role": "student",
            "username": username,
            "password": password,
            "confirm_password": password,
            "name": name,
        }
    )
    if (
        errors.get("username") == "用户名格式不正确"
        and MANAGED_USERNAME_PATTERN.fullmatch(username)
    ):
        errors.pop("username")
    if errors:
        raise _validation_error(errors)
    return {
        "role": role,
        "username": username,
        "password": password,
        "name": name,
    }


def create_managed_account(actor_id: int, payload: dict) -> dict:
    values = _validated_managed_payload(payload)
    now = platform_now_iso()
    try:
        with get_db() as db:
            cursor = db.execute(
                """
                INSERT INTO users (
                    username, password_hash, name, role, is_enabled,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, 1, ?, ?)
                """,
                (
                    values["username"],
                    generate_password_hash(values["password"]),
                    values["name"],
                    values["role"],
                    now,
                    now,
                ),
            )
            user_id = int(cursor.lastrowid)
            record_admin_audit(
                db,
                actor_id=actor_id,
                action="create_account",
                target_type="user",
                target_id=str(user_id),
                before=None,
                after={
                    "role": values["role"],
                    "username": values["username"],
                },
                result="success",
            )
    except sqlite3.IntegrityError as error:
        raise ProviderConflictError(
            "用户名已被占用",
            code="username_conflict",
            details={"username": "用户名已被占用"},
        ) from error
    return get_account(user_id)


def set_account_enabled(
    actor_id: int,
    user_id: int,
    enabled: bool,
) -> dict:
    if not isinstance(enabled, bool):
        raise _validation_error({"enabled": "必须是布尔值"})

    now = platform_now_iso()
    with get_db() as db:
        row = db.execute(
            "SELECT id, is_enabled FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if row is None:
            raise _not_found()
        before = {"is_enabled": bool(row["is_enabled"])}
        db.execute(
            """
            UPDATE users
            SET is_enabled = ?, updated_at = ?
            WHERE id = ?
            """,
            (int(enabled), now, user_id),
        )
        record_admin_audit(
            db,
            actor_id=actor_id,
            action="enable_account" if enabled else "disable_account",
            target_type="user",
            target_id=str(user_id),
            before=before,
            after={"is_enabled": enabled},
            result="success",
        )
    return get_account(user_id)


def reset_account_password(actor_id: int, user_id: int) -> dict:
    initial_password = configured_initial_password()
    if initial_password is None or len(initial_password) < 8:
        raise ProviderUnavailableError(
            "未配置有效的初始密码",
            code="initial_password_unavailable",
            details={},
        )

    with get_db() as db:
        row = db.execute(
            """
            SELECT id, password_version
            FROM users
            WHERE id = ?
            """,
            (user_id,),
        ).fetchone()
        if row is None:
            raise _not_found()

        previous_version = int(row["password_version"])
        password_version = previous_version + 1
        event_id = f"admin-password-reset:{user_id}:{password_version}"
        now = platform_now_iso()
        db.execute(
            """
            UPDATE users
            SET password_hash = ?, password_version = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                generate_password_hash(initial_password),
                password_version,
                now,
                user_id,
            ),
        )
        record_admin_audit(
            db,
            actor_id=actor_id,
            action="reset_password",
            target_type="user",
            target_id=str(user_id),
            before={"password_version": previous_version},
            after={"password_version": password_version},
            result="success",
        )
        emit_password_reset(event_id=event_id, user_id=user_id)

    return {
        "event_id": event_id,
        "account": get_account(user_id),
    }


__all__ = [
    "ACCOUNT_ROLES",
    "MANAGED_ROLES",
    "configured_initial_password",
    "create_managed_account",
    "get_account",
    "list_accounts",
    "reset_account_password",
    "set_account_enabled",
]
