from __future__ import annotations

import sqlite3

from werkzeug.security import generate_password_hash

from app.admin_console.accounts import configured_initial_password
from app.admin_console.errors import ProviderUnavailableError
from app.admin_console.time_utils import platform_now_iso
from app.db import get_db


INITIAL_SUPER_ADMIN_USERNAME = "superadmin"


def seed_initial_super_admin() -> int | None:
    db = get_db()
    existing_super_admin = db.execute(
        """
        SELECT id
        FROM users
        WHERE role = 'super_admin'
        ORDER BY id
        LIMIT 1
        """
    ).fetchone()
    if existing_super_admin is not None:
        return None

    initial_password = configured_initial_password()
    if initial_password is None:
        return None
    if len(initial_password) < 8:
        raise ProviderUnavailableError(
            "初始超级管理员密码长度不能少于8位",
            code="initial_super_admin_password_invalid",
            details={},
        )

    if db.execute(
        "SELECT 1 FROM users WHERE username = ?",
        (INITIAL_SUPER_ADMIN_USERNAME,),
    ).fetchone():
        return None

    now = platform_now_iso()
    try:
        with db:
            cursor = db.execute(
                """
                INSERT INTO users (
                    username, password_hash, name, role, is_enabled,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, 'super_admin', 1, ?, ?)
                """,
                (
                    INITIAL_SUPER_ADMIN_USERNAME,
                    generate_password_hash(initial_password),
                    "超级管理员",
                    now,
                    now,
                ),
            )
            user_id = int(cursor.lastrowid)
    except sqlite3.IntegrityError:
        return None
    return user_id


__all__ = ["INITIAL_SUPER_ADMIN_USERNAME", "seed_initial_super_admin"]
