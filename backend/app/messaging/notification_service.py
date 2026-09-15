from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from app.db import get_db


class NotificationValidationError(ValueError):
    def __init__(self, errors: dict[str, str]) -> None:
        super().__init__("Invalid notification")
        self.errors = errors


def _required_text(value: object, field: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise NotificationValidationError({field: "不能为空"})
    return normalized


def _validated_recipient_id(recipient_id: object) -> int:
    if (
        isinstance(recipient_id, bool)
        or not isinstance(recipient_id, int)
        or recipient_id <= 0
    ):
        raise NotificationValidationError({"recipient_id": "必须是正整数"})
    return recipient_id


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _notification_payload(row: sqlite3.Row) -> dict:
    return {
        "id": int(row["id"]),
        "event_type": str(row["event_type"]),
        "title": str(row["title"]),
        "body": str(row["body"]),
        "source_type": row["source_type"],
        "source_id": row["source_id"],
        "source_available": bool(row["source_available"]),
        "created_at": str(row["created_at"]),
        "read": row["read_at"] is not None,
    }


def _persist_notification(
    *,
    recipient_id: int,
    event_key: str,
    event_type: str,
    title: str,
    body: str,
    source_type: str | None,
    source_id: str | None,
    source_available: bool,
    created_at: str,
) -> dict:
    db = get_db()
    db.execute(
        """
        INSERT INTO system_notifications (
            recipient_id, event_key, event_type, title, body,
            source_type, source_id, source_available, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (recipient_id, event_key) DO NOTHING
        """,
        (
            recipient_id,
            event_key,
            event_type,
            title,
            body,
            source_type,
            source_id,
            int(source_available),
            created_at,
        ),
    )
    row = db.execute(
        """
        SELECT
            id,
            event_type,
            title,
            body,
            source_type,
            source_id,
            source_available,
            created_at,
            read_at
        FROM system_notifications
        WHERE recipient_id = ? AND event_key = ?
        """,
        (recipient_id, event_key),
    ).fetchone()
    return _notification_payload(row)


def emit_notification(
    *,
    recipient_id: int,
    event_key: str,
    event_type: str,
    title: str,
    body: str,
    source_type: str | None = None,
    source_id: str | None = None,
    source_available: bool = True,
) -> dict:
    validated_recipient_id = _validated_recipient_id(recipient_id)
    normalized_event_key = _required_text(event_key, "event_key")
    normalized_event_type = _required_text(event_type, "event_type")
    normalized_title = _required_text(title, "title")
    normalized_body = _required_text(body, "body")
    normalized_source_type = _optional_text(source_type)
    normalized_source_id = _optional_text(source_id)

    with get_db():
        return _persist_notification(
            recipient_id=validated_recipient_id,
            event_key=normalized_event_key,
            event_type=normalized_event_type,
            title=normalized_title,
            body=normalized_body,
            source_type=normalized_source_type,
            source_id=normalized_source_id,
            source_available=bool(source_available),
            created_at=_utc_now_iso(),
        )


def emit_notifications(
    *,
    recipient_ids: list[int],
    event_key: str,
    event_type: str,
    title: str,
    body: str,
    source_type: str | None = None,
    source_id: str | None = None,
    source_available: bool = True,
) -> dict:
    normalized_event_key = _required_text(event_key, "event_key")
    normalized_event_type = _required_text(event_type, "event_type")
    normalized_title = _required_text(title, "title")
    normalized_body = _required_text(body, "body")
    normalized_source_type = _optional_text(source_type)
    normalized_source_id = _optional_text(source_id)
    unique_recipient_ids = list(
        dict.fromkeys(
            _validated_recipient_id(recipient_id)
            for recipient_id in recipient_ids
        )
    )
    created_at = _utc_now_iso()

    with get_db():
        records = [
            _persist_notification(
                recipient_id=recipient_id,
                event_key=normalized_event_key,
                event_type=normalized_event_type,
                title=normalized_title,
                body=normalized_body,
                source_type=normalized_source_type,
                source_id=normalized_source_id,
                source_available=bool(source_available),
                created_at=created_at,
            )
            for recipient_id in unique_recipient_ids
        ]

    return {
        "created_count": len(records),
        "unique_recipient_count": len(unique_recipient_ids),
        "notifications": records,
    }


def mark_notification_sources_unavailable(
    *,
    source_type: str,
    source_id: str,
) -> int:
    normalized_source_type = _required_text(source_type, "source_type")
    normalized_source_id = _required_text(source_id, "source_id")
    with get_db():
        result = get_db().execute(
            """
            UPDATE system_notifications
            SET source_available = 0
            WHERE source_type = ?
              AND source_id = ?
              AND source_available = 1
            """,
            (normalized_source_type, normalized_source_id),
        )
    return int(result.rowcount)


def list_notifications(user_id: int) -> list[dict]:
    rows = get_db().execute(
        """
        SELECT
            id,
            event_type,
            title,
            body,
            source_type,
            source_id,
            source_available,
            created_at,
            read_at
        FROM system_notifications
        WHERE recipient_id = ? AND cleared_at IS NULL
        ORDER BY created_at DESC, id DESC
        """,
        (user_id,),
    ).fetchall()
    return [_notification_payload(row) for row in rows]
