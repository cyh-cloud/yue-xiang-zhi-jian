from __future__ import annotations

import json
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from app.db import get_db
from app.enterprise_console.errors import (
    EnterpriseNotFoundError,
    EnterpriseValidationError,
)

LOGGER = logging.getLogger(__name__)
PLATFORM_TIMEZONE = ZoneInfo("Asia/Shanghai")
OUTBOX_EVENT_TYPES = {
    "application_submitted",
    "application_status",
    "position_closed",
}


def _now_iso() -> str:
    return datetime.now(PLATFORM_TIMEZONE).isoformat(timespec="seconds")


def enqueue_enterprise_notification(
    db,
    *,
    event_type: str,
    event_id: str,
    payload: dict,
) -> int:
    normalized_type = str(event_type or "").strip()
    normalized_id = str(event_id or "").strip()
    if normalized_type not in OUTBOX_EVENT_TYPES:
        raise EnterpriseValidationError("通知事件类型不正确")
    if not normalized_id or not isinstance(payload, dict):
        raise EnterpriseValidationError("通知内容格式不正确")

    db.execute(
        """
        INSERT INTO enterprise_notification_outbox (
            event_type,
            event_id,
            payload_json,
            status,
            attempts,
            last_error,
            created_at,
            sent_at
        )
        VALUES (?, ?, ?, 'pending', 0, NULL, ?, NULL)
        ON CONFLICT (event_type, event_id) DO NOTHING
        """,
        (
            normalized_type,
            normalized_id,
            json.dumps(payload, ensure_ascii=False),
            _now_iso(),
        ),
    )
    row = db.execute(
        """
        SELECT id
        FROM enterprise_notification_outbox
        WHERE event_type = ? AND event_id = ?
        """,
        (normalized_type, normalized_id),
    ).fetchone()
    if row is None:
        raise EnterpriseNotFoundError("企业通知不存在")
    return int(row["id"])


def emit_application_submitted(**payload):
    from app.messaging.events import emit_application_submitted as emit

    return emit(**payload)


def emit_application_status_changed(**payload):
    from app.messaging.events import emit_application_status_changed as emit

    return emit(**payload)


def emit_position_closed(**payload):
    from app.messaging.events import emit_position_closed as emit

    return emit(**payload)


def _emit_for_event(event_type: str, *, event_id: str, payload: dict) -> dict:
    if event_type == "application_submitted":
        emitter = emit_application_submitted
    elif event_type == "application_status":
        emitter = emit_application_status_changed
    elif event_type == "position_closed":
        emitter = emit_position_closed
    else:
        raise EnterpriseValidationError("通知事件类型不正确")
    return emitter(event_id=event_id, **payload)


def deliver_enterprise_outbox(outbox_id: int) -> dict:
    db = get_db()
    row = db.execute(
        """
        SELECT id, event_type, event_id, payload_json, status
        FROM enterprise_notification_outbox
        WHERE id = ?
        """,
        (outbox_id,),
    ).fetchone()
    if row is None:
        raise EnterpriseNotFoundError("企业通知不存在")
    if row["status"] == "sent":
        return {"sent": 0, "already_sent": 1, "failed": 0}

    try:
        payload = json.loads(row["payload_json"])
        if not isinstance(payload, dict):
            raise EnterpriseValidationError("通知内容格式不正确")
        _emit_for_event(
            row["event_type"],
            event_id=row["event_id"],
            payload=payload,
        )
    except Exception as error:
        db.execute(
            """
            UPDATE enterprise_notification_outbox
            SET attempts = attempts + 1,
                last_error = ?
            WHERE id = ? AND status = 'pending'
            """,
            (str(error), outbox_id),
        )
        db.commit()
        raise

    cursor = db.execute(
        """
        UPDATE enterprise_notification_outbox
        SET status = 'sent',
            attempts = attempts + 1,
            last_error = NULL,
            sent_at = ?
        WHERE id = ? AND status = 'pending'
        """,
        (_now_iso(), outbox_id),
    )
    db.commit()
    if cursor.rowcount == 1:
        return {"sent": 1, "already_sent": 0, "failed": 0}
    return {"sent": 0, "already_sent": 1, "failed": 0}


def deliver_after_commit(outbox_id: int) -> dict:
    try:
        return deliver_enterprise_outbox(outbox_id)
    except Exception:
        LOGGER.exception(
            "Failed to deliver enterprise notification outbox row %s",
            outbox_id,
        )
        return {"sent": 0, "already_sent": 0, "failed": 1}


def retry_pending_enterprise_notifications(limit: int = 100) -> dict:
    normalized_limit = int(limit)
    if normalized_limit <= 0:
        return {"sent": 0, "already_sent": 0, "failed": 0}

    rows = get_db().execute(
        """
        SELECT id
        FROM enterprise_notification_outbox
        WHERE status = 'pending'
        ORDER BY created_at, id
        LIMIT ?
        """,
        (normalized_limit,),
    ).fetchall()

    result = {"sent": 0, "already_sent": 0, "failed": 0}
    for row in rows:
        delivery = deliver_after_commit(int(row["id"]))
        result["sent"] += delivery["sent"]
        result["already_sent"] += delivery["already_sent"]
        result["failed"] += delivery["failed"]
    return result
