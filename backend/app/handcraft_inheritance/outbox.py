from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from app.agri_skills.errors import AgriNotFoundError, AgriValidationError


LOGGER = logging.getLogger(__name__)
OUTBOX_EVENT_TYPES = {
    "redemption_succeeded",
    "review_approved",
    "review_rejected",
}


def _get_db():
    from app.db import get_db

    return get_db()


def emit_redemption_succeeded(**payload):
    from app.messaging.events import emit_redemption_succeeded as emit

    return emit(**payload)


def emit_review_result(**payload):
    from app.messaging.events import emit_review_result as emit

    return emit(**payload)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _require_positive_int(value: object, message: str) -> int:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or value <= 0
    ):
        raise AgriValidationError(message)
    return value


def _require_event(event_type: object, event_id: object) -> tuple[str, str]:
    normalized_type = str(event_type or "").strip()
    if normalized_type not in OUTBOX_EVENT_TYPES:
        raise AgriValidationError("通知事件类型不正确")
    normalized_id = str(event_id or "").strip()
    if not normalized_id:
        raise AgriValidationError("通知事件标识不能为空")
    return normalized_type, normalized_id


def enqueue_handcraft_notification(
    db,
    *,
    event_type: str,
    payload: dict,
) -> int:
    normalized_type, event_id = _require_event(
        event_type,
        payload.get("event_id"),
    )
    if not isinstance(payload, dict):
        raise AgriValidationError("通知内容格式不正确")
    db.execute(
        """
        INSERT INTO handcraft_notification_outbox (
            event_type, event_id, payload_json, status,
            attempts, last_error, created_at, sent_at
        )
        VALUES (?, ?, ?, 'pending', 0, NULL, ?, NULL)
        ON CONFLICT (event_type, event_id) DO NOTHING
        """,
        (
            normalized_type,
            event_id,
            json.dumps(payload, ensure_ascii=False),
            _now_iso(),
        ),
    )
    row = db.execute(
        """
        SELECT id
        FROM handcraft_notification_outbox
        WHERE event_type = ? AND event_id = ?
        """,
        (normalized_type, event_id),
    ).fetchone()
    return int(row["id"])


def _load_outbox(outbox_id: int):
    return _get_db().execute(
        """
        SELECT *
        FROM handcraft_notification_outbox
        WHERE id = ?
        """,
        (outbox_id,),
    ).fetchone()


def _record_outbox_failure(outbox_id: int, error: Exception) -> None:
    with _get_db() as db:
        db.execute(
            """
            UPDATE handcraft_notification_outbox
            SET attempts = attempts + 1,
                last_error = ?
            WHERE id = ? AND status = 'pending'
            """,
            (str(error)[:500], outbox_id),
        )


def _mark_outbox_sent(outbox_id: int) -> bool:
    with _get_db() as db:
        cursor = db.execute(
            """
            UPDATE handcraft_notification_outbox
            SET status = 'sent',
                attempts = attempts + 1,
                sent_at = ?,
                last_error = NULL
            WHERE id = ? AND status = 'pending'
            """,
            (_now_iso(), outbox_id),
        )
        return cursor.rowcount == 1


def deliver_handcraft_outbox(
    outbox_id: int,
    *,
    emit_callback=None,
) -> dict:
    outbox_id = _require_positive_int(
        outbox_id,
        "通知发件箱标识必须是正整数",
    )
    row = _load_outbox(outbox_id)
    if row is None:
        raise AgriNotFoundError("通知发件箱记录不存在")
    if row["status"] == "sent":
        return {"sent": 0, "already_sent": 1, "failed": 0}

    payload = json.loads(row["payload_json"])
    try:
        if emit_callback is not None:
            emit_callback(payload)
        elif row["event_type"] == "redemption_succeeded":
            emit_redemption_succeeded(**payload)
        else:
            emit_review_result(**payload)
    except Exception as error:
        _record_outbox_failure(outbox_id, error)
        raise

    sent = 1 if _mark_outbox_sent(outbox_id) else 0
    return {
        "sent": sent,
        "already_sent": 0 if sent else 1,
        "failed": 0,
    }


def deliver_after_commit(outbox_id: int) -> dict:
    try:
        return deliver_handcraft_outbox(outbox_id)
    except Exception as error:
        LOGGER.warning(
            "Handcraft notification delivery deferred: %s",
            type(error).__name__,
        )
        return {"sent": 0, "already_sent": 0, "failed": 1}


def retry_pending_handcraft_notifications(limit: int = 100) -> dict:
    limit = _require_positive_int(limit, "重试批量必须是正整数")
    rows = _get_db().execute(
        """
        SELECT id
        FROM handcraft_notification_outbox
        WHERE status = 'pending'
        ORDER BY created_at, id
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    sent = 0
    failed = 0
    for row in rows:
        try:
            result = deliver_handcraft_outbox(int(row["id"]))
            sent += int(result["sent"])
        except Exception:
            failed += 1
    return {
        "attempted": len(rows),
        "sent": sent,
        "failed": failed,
    }


__all__ = [
    "deliver_after_commit",
    "deliver_handcraft_outbox",
    "emit_redemption_succeeded",
    "emit_review_result",
    "enqueue_handcraft_notification",
    "retry_pending_handcraft_notifications",
]
