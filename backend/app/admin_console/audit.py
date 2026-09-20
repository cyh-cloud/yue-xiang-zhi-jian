from __future__ import annotations

import json
import sqlite3

from app.admin_console.time_utils import platform_now_iso


def record_admin_audit(
    db: sqlite3.Connection,
    *,
    actor_id: int,
    action: str,
    target_type: str,
    target_id: str,
    before: dict | None,
    after: dict | None,
    result: str,
) -> int:
    cursor = db.execute(
        """
        INSERT INTO admin_audit_log (
            actor_id, action, target_type, target_id,
            before_json, after_json, result, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            actor_id,
            action,
            target_type,
            target_id,
            None if before is None else json.dumps(before, ensure_ascii=False),
            None if after is None else json.dumps(after, ensure_ascii=False),
            result,
            platform_now_iso(),
        ),
    )
    return int(cursor.lastrowid)
