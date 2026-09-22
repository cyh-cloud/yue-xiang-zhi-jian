from __future__ import annotations

import json
import logging
import sqlite3

from app.admin_console.errors import ProviderNotFoundError
from app.admin_console.time_utils import platform_now_iso
from app.db import get_db


LOGGER = logging.getLogger(__name__)

OUTBOX_EVENT_TYPE_ANNOUNCEMENT = "system_announcement"
OUTBOX_COLUMNS = "id, event_type, event_id, payload_json, status, attempts"


def emit_review_result(**payload) -> dict:
    """Hand one review result to 02 through the shared events module.

    The import runs at call time so a test that patches
    ``app.messaging.events.emit_review_result`` still governs delivery.
    """
    from app.messaging.events import emit_review_result as emit

    return emit(**payload)


def emit_password_reset(**payload) -> dict:
    """Hand one password-reset notice to 02; late import keeps it patchable."""
    from app.messaging.events import emit_password_reset as emit

    return emit(**payload)


def emit_system_announcement(**payload) -> dict:
    """Hand one announcement broadcast to 02.

    011 keeps the announcement emit seam on its own module: the wrapper
    resolves ``system_announcements.emit_system_announcement`` at call time, so
    a test that patches that module global still controls delivery. The payload
    keys map one-to-one onto the emit signature.
    """
    from app.admin_console.system_announcements import (
        emit_system_announcement as emit,
    )

    return emit(**payload)


# Each outbox event type resolves to the emit function it dispatches to, and
# the payload stored in the row already carries exactly that emit's arguments.
DELIVERERS = {
    "review_approved": emit_review_result,
    "review_rejected": emit_review_result,
    "password_reset": emit_password_reset,
    "system_announcement": emit_system_announcement,
}


def enqueue_admin_notification(
    db,
    *,
    event_type: str,
    event_id: str,
    payload: dict,
) -> int:
    """Write the one outbox row inside the caller's transaction.

    ``ON CONFLICT (event_type, event_id) DO NOTHING`` plus the following SELECT
    keeps the row count at one per event even when the insert is attempted
    twice, so the idempotency key lives in the database and not only in this
    function. Semantics are the ones Task 12 reserved the announcement helper
    for, now shared by every producer.
    """
    db.execute(
        """
        INSERT INTO admin_notification_outbox (
            event_type, event_id, payload_json, status, attempts, last_error,
            created_at, sent_at
        )
        VALUES (?, ?, ?, 'pending', 0, NULL, ?, NULL)
        ON CONFLICT (event_type, event_id) DO NOTHING
        """,
        (
            event_type,
            event_id,
            json.dumps(payload, ensure_ascii=False),
            platform_now_iso(),
        ),
    )
    row = db.execute(
        """
        SELECT id
        FROM admin_notification_outbox
        WHERE event_type = ? AND event_id = ?
        """,
        (event_type, event_id),
    ).fetchone()
    return int(row["id"])


def _load_outbox(outbox_id: int) -> sqlite3.Row | None:
    return get_db().execute(
        f"""
        SELECT {OUTBOX_COLUMNS}
        FROM admin_notification_outbox
        WHERE id = ?
        """,
        (outbox_id,),
    ).fetchone()


def _decode_outbox_payload(row: sqlite3.Row) -> dict | None:
    try:
        payload = json.loads(row["payload_json"])
    except (TypeError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def _delivery_summary(*, delivered: int, recipient_count: int, failed: int) -> dict:
    return {
        "delivered": delivered,
        "recipient_count": recipient_count,
        "failed": failed,
    }


def _outbox_not_found(outbox_id: int) -> ProviderNotFoundError:
    return ProviderNotFoundError(
        "通知任务不存在",
        code="announcement_outbox_not_found",
        details={"outbox_id": outbox_id},
    )


def _record_delivery_failure(outbox_id: int, *, error: str, terminal: bool) -> None:
    """Record one failed delivery attempt; accounting never raises upward.

    A retryable failure leaves the row ``pending`` and bumps ``attempts``. A
    terminal failure (an announcement whose recipient list was frozen empty at
    publish) also needs a final state, so it is written ``failed``. Every DB
    write is wrapped because an accounting error after a committed business
    change must surface as a log line, never as a raised exception that reads
    like the published work itself failed.
    """
    if terminal:
        statement = """
            UPDATE admin_notification_outbox
            SET status = 'failed', attempts = attempts + 1, last_error = ?
            WHERE id = ? AND status = 'pending'
        """
    else:
        statement = """
            UPDATE admin_notification_outbox
            SET attempts = attempts + 1, last_error = ?
            WHERE id = ? AND status = 'pending'
        """
    try:
        with get_db() as db:
            db.execute(statement, (error[:500], outbox_id))
    except sqlite3.Error as db_error:
        LOGGER.error(
            "Notification outbox %s failure accounting failed: %s",
            outbox_id,
            type(db_error).__name__,
        )


def _mark_delivery_sent(outbox_id: int) -> bool:
    try:
        with get_db() as db:
            cursor = db.execute(
                """
                UPDATE admin_notification_outbox
                SET status = 'sent', attempts = attempts + 1, sent_at = ?,
                    last_error = NULL
                WHERE id = ? AND status = 'pending'
                """,
                (platform_now_iso(), outbox_id),
            )
            return cursor.rowcount == 1
    except sqlite3.Error as db_error:
        LOGGER.error(
            "Notification outbox %s sent-mark accounting failed: %s",
            outbox_id,
            type(db_error).__name__,
        )
        return False


def _delivered_recipient_count(
    event_type: str,
    payload: dict,
    result: object,
) -> int:
    if event_type == OUTBOX_EVENT_TYPE_ANNOUNCEMENT:
        fallback = len([int(value) for value in payload.get("recipient_ids", [])])
        try:
            return int(result.get("created_count", fallback))  # type: ignore[union-attr]
        except (AttributeError, TypeError, ValueError):
            return fallback
    return 1


def _announcement_recipients(payload: dict) -> list[int]:
    return [int(value) for value in payload.get("recipient_ids", [])]


def deliver_admin_notification(outbox_id: int) -> dict:
    """Deliver one queued notification after its business transaction commits.

    A missing row is a boundary error. An already-sent row is a no-op. An
    unparseable payload, an unavailable deliverer, a frozen empty announcement
    recipient list, and the accounting writes themselves never raise: each is
    recorded on the outbox row and reported through the
    ``{delivered, recipient_count, failed}`` summary the frontend and existing
    tests already consume.
    """
    row = _load_outbox(outbox_id)
    if row is None:
        raise _outbox_not_found(outbox_id)
    if str(row["status"]) == "sent":
        return _delivery_summary(delivered=0, recipient_count=0, failed=0)

    outbox_id = int(row["id"])
    event_type = str(row["event_type"])
    deliverer = DELIVERERS.get(event_type)
    if deliverer is None:
        _record_delivery_failure(
            outbox_id,
            error=f"未知的通知事件类型：{event_type}",
            terminal=False,
        )
        return _delivery_summary(delivered=0, recipient_count=0, failed=1)

    payload = _decode_outbox_payload(row)
    if payload is None:
        _record_delivery_failure(
            outbox_id,
            error="通知内容格式不正确",
            terminal=False,
        )
        return _delivery_summary(delivered=0, recipient_count=0, failed=1)

    recipient_count = (
        len(_announcement_recipients(payload))
        if event_type == OUTBOX_EVENT_TYPE_ANNOUNCEMENT
        else 1
    )
    if event_type == OUTBOX_EVENT_TYPE_ANNOUNCEMENT and not recipient_count:
        # The recipient list is frozen at publish and a retry re-reads it as-is,
        # so an empty list can never become deliverable. Give it a terminal
        # failure now rather than a row that stays pending forever.
        _record_delivery_failure(
            outbox_id,
            error="发布时无可用收件人",
            terminal=True,
        )
        return _delivery_summary(delivered=0, recipient_count=0, failed=1)

    try:
        result = deliverer(**payload)
    except Exception as error:
        _record_delivery_failure(
            outbox_id,
            error=str(error) or type(error).__name__,
            terminal=False,
        )
        LOGGER.warning(
            "Notification delivery deferred for outbox %s (%s): %s",
            outbox_id,
            event_type,
            type(error).__name__,
        )
        return _delivery_summary(delivered=0, recipient_count=recipient_count, failed=1)

    _mark_delivery_sent(outbox_id)
    return _delivery_summary(
        delivered=1,
        recipient_count=_delivered_recipient_count(event_type, payload, result),
        failed=0,
    )


def retry_admin_notifications(limit: int = 100) -> dict:
    """Deliver pending outbox rows, oldest first; terminal rows are skipped.

    Only ``pending`` rows are scanned by id ascending, so a row already sent or
    already written ``failed`` is never re-delivered. Each pending row is handed
    to :func:`deliver_admin_notification`, which keeps the event id and the
    frozen payload intact. No new rows are created.
    """
    if not isinstance(limit, int) or isinstance(limit, bool) or limit <= 0:
        limit = 100
    rows = get_db().execute(
        """
        SELECT id, status
        FROM admin_notification_outbox
        WHERE status = 'pending'
        ORDER BY id ASC
        LIMIT ?
        """,
        (int(limit),),
    ).fetchall()
    delivered = 0
    failed = 0
    for row in rows:
        summary = deliver_admin_notification(int(row["id"]))
        delivered += int(summary.get("delivered", 0))
        failed += int(summary.get("failed", 0))
    return {
        "scanned": len(rows),
        "delivered": delivered,
        "failed": failed,
        "skipped": len(rows) - delivered - failed,
    }


__all__ = [
    "DELIVERERS",
    "deliver_admin_notification",
    "emit_password_reset",
    "emit_review_result",
    "emit_system_announcement",
    "enqueue_admin_notification",
    "retry_admin_notifications",
]
