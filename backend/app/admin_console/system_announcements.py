from __future__ import annotations

import json
import logging
import re
import sqlite3
from datetime import datetime, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.admin_console.audit import record_admin_audit
from app.admin_console.errors import (
    ProviderNotFoundError,
    ProviderValidationError,
)
from app.admin_console.outbox import (
    deliver_admin_notification,
    enqueue_admin_notification,
)
from app.admin_console.time_utils import platform_now_iso
from app.db import get_db
# `system_announcements` stays the announcement emit seam: the shared outbox
# resolves this module global at delivery time, so a test that patches it still
# governs announcement delivery (FR-111).
from app.messaging.events import emit_system_announcement  # noqa: F401


LOGGER = logging.getLogger(__name__)

# The roles 01 defines on `users.role`; an announcement may only target them.
PLATFORM_ROLES = frozenset(
    {"student", "teacher", "enterprise", "government", "admin", "super_admin"}
)
PLATFORM_ROLE_VALUES = tuple(sorted(PLATFORM_ROLES))
ANNOUNCEMENT_KEY_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
TITLE_MAX_LENGTH = 60
BODY_MAX_LENGTH = 2000
OUTBOX_EVENT_TYPE = "system_announcement"
ANNOUNCEMENT_COLUMNS = """
    announcement_id, title, body, target_roles_json, status, event_id,
    created_by, created_at, published_at
"""
PLATFORM_TIMEZONE = ZoneInfo("Asia/Shanghai")
TIME_FLOOR = datetime.min.replace(tzinfo=timezone.utc)


def _fetch_all(sql: str, parameters: tuple = ()) -> list[sqlite3.Row]:
    return get_db().execute(sql, parameters).fetchall()


def _delivery_summary(*, delivered: int, recipient_count: int, failed: int) -> dict:
    return {
        "delivered": delivered,
        "recipient_count": recipient_count,
        "failed": failed,
    }


def _validation(
    message: str,
    *,
    code: str = "announcement_validation_failed",
    **details,
) -> ProviderValidationError:
    return ProviderValidationError(message, code=code, details=details)


def _not_found(announcement_id: str) -> ProviderNotFoundError:
    return ProviderNotFoundError(
        "公告不存在",
        code="announcement_not_found",
        details={"announcement_id": announcement_id},
    )


def _required_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _bounded_text(value: object, *, field: str, maximum: int) -> str:
    normalized = _required_text(value)
    if normalized is None:
        raise _validation(f"{field} 不能为空", field=field)
    if len(normalized) > maximum:
        raise _validation(
            f"{field} 长度不能超过 {maximum} 个字符",
            field=field,
            max_length=maximum,
        )
    return normalized


def _target_roles(value: object) -> list[str]:
    if not isinstance(value, list):
        raise _validation(
            "目标角色必须是数组",
            field="target_roles",
            allowed=list(PLATFORM_ROLE_VALUES),
        )
    if not value:
        raise _validation(
            "目标角色不能为空",
            field="target_roles",
            allowed=list(PLATFORM_ROLE_VALUES),
        )
    roles: list[str] = []
    unknown: list[str] = []
    for item in value:
        normalized = item.strip() if isinstance(item, str) else None
        if normalized is None or normalized not in PLATFORM_ROLES:
            unknown.append(str(item))
        elif normalized not in roles:
            roles.append(normalized)
    if unknown:
        raise _validation(
            "目标角色不正确",
            field="target_roles",
            unknown=unknown,
            allowed=list(PLATFORM_ROLE_VALUES),
        )
    return sorted(roles)


def _announcement_key(value: object) -> str:
    normalized = _required_text(value)
    if normalized is None or ANNOUNCEMENT_KEY_PATTERN.fullmatch(normalized) is None:
        raise _validation("公告标识格式不正确", field="announcement_id")
    return normalized


def _announcement_payload(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise _validation("请求内容格式不正确", field="payload")
    return {
        "title": _bounded_text(
            payload.get("title"),
            field="title",
            maximum=TITLE_MAX_LENGTH,
        ),
        "body": _bounded_text(
            payload.get("body"),
            field="body",
            maximum=BODY_MAX_LENGTH,
        ),
        "target_roles": _target_roles(payload.get("target_roles")),
    }


def _parse_timestamp(value: object) -> datetime | None:
    """Read one ISO 8601 stamp as an aware datetime, or `None`.

    Announcements are written with `+08:00`, but a row can carry a UTC `Z`
    stamp from another writer and raw text is never comparable across
    offsets. An unparseable value stays `None` instead of raising, so one
    bad row cannot break the whole history.
    """
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if normalized.endswith(("Z", "z")):
        normalized = f"{normalized[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=PLATFORM_TIMEZONE)
    return parsed


def _sort_time(value: object) -> datetime:
    return _parse_timestamp(value) or TIME_FLOOR


def _normalized_time(value: object) -> object:
    """Render one stored stamp as canonical `+08:00` ISO 8601 text."""
    if value is None or value == "":
        return value
    parsed = _parse_timestamp(value)
    if parsed is None:
        return value
    return parsed.astimezone(PLATFORM_TIMEZONE).isoformat()


def _stored_roles(value: object) -> list[str]:
    try:
        decoded = json.loads(value) if isinstance(value, str) else value
    except (TypeError, ValueError):
        return []
    if not isinstance(decoded, list):
        return []
    return [str(item) for item in decoded]


def _serialize_announcement(row: sqlite3.Row) -> dict:
    return {
        "announcement_id": str(row["announcement_id"]),
        "title": str(row["title"]),
        "body": str(row["body"]),
        "target_roles": _stored_roles(row["target_roles_json"]),
        "status": str(row["status"]),
        "event_id": str(row["event_id"]),
        "created_by": int(row["created_by"]),
        "created_at": _normalized_time(row["created_at"]),
        "published_at": _normalized_time(row["published_at"]),
    }


def _announcement(announcement_id: str) -> dict:
    row = get_db().execute(
        f"""
        SELECT {ANNOUNCEMENT_COLUMNS}
        FROM system_announcements
        WHERE announcement_id = ?
        """,
        (announcement_id,),
    ).fetchone()
    if row is None:
        raise _not_found(announcement_id)
    return _serialize_announcement(row)


def _begin_exclusive(db: sqlite3.Connection) -> None:
    """Take the write lock before the announcement row is read.

    `require_admin_session` runs a session cleanup DELETE that leaves an
    empty deferred transaction open on the connection, and a deferred
    transaction does not serialize writers: two super admins could both
    read `draft` and both publish. Committing the pending work and opening
    `BEGIN IMMEDIATE` is what makes the second publish observe the first
    one's commit.
    """
    if db.in_transaction:
        db.commit()
    db.execute("BEGIN IMMEDIATE")


def create_announcement(actor_id: int, payload: dict) -> dict:
    """Write one draft announcement and audit it (FR-115, FR-116, FR-117).

    The draft already carries the stable `announcement_id` and the stable
    `event_id` the later publish reuses, so the 02 idempotency key never
    depends on when the publish happens.
    """
    values = _announcement_payload(payload)
    announcement_id = f"announcement-{uuid4().hex}"
    event_id = f"{announcement_id}:publish"
    now = platform_now_iso()
    db = get_db()
    _begin_exclusive(db)
    try:
        db.execute(
            """
            INSERT INTO system_announcements (
                announcement_id, title, body, target_roles_json, status,
                event_id, created_by, created_at, published_at
            )
            VALUES (?, ?, ?, ?, 'draft', ?, ?, ?, NULL)
            """,
            (
                announcement_id,
                values["title"],
                values["body"],
                json.dumps(values["target_roles"], ensure_ascii=False),
                event_id,
                actor_id,
                now,
            ),
        )
        record_admin_audit(
            db,
            actor_id=actor_id,
            action="create_announcement",
            target_type="system_announcement",
            target_id=announcement_id,
            before=None,
            after={
                "title": values["title"],
                "target_roles": values["target_roles"],
                "status": "draft",
            },
            result="success",
        )
    except Exception:
        db.rollback()
        raise
    db.commit()
    return _announcement(announcement_id)


def _active_recipient_ids(db: sqlite3.Connection, roles: list[str]) -> list[int]:
    """Active accounts for the target roles, ordered by id.

    The recipients are resolved inside the write transaction so the outbox
    payload names exactly the accounts this publish was aimed at, and a
    later retry re-reads that list instead of re-querying the roles.
    """
    placeholders = ", ".join("?" for _ in roles)
    rows = db.execute(
        f"""
        SELECT id
        FROM users
        WHERE is_enabled = 1 AND role IN ({placeholders})
        ORDER BY id
        """,
        tuple(roles),
    ).fetchall()
    return [int(row["id"]) for row in rows]


def _outbox_payload(announcement: dict, recipient_ids: list[int]) -> dict:
    """Everything a delivery or a later retry needs, with no 011 re-read."""
    return {
        "announcement_id": announcement["announcement_id"],
        "event_id": announcement["event_id"],
        "title": announcement["title"],
        "body": announcement["body"],
        "recipient_ids": recipient_ids,
    }


def publish_announcement(actor_id: int, announcement_id: str) -> dict:
    """Publish one announcement through 02 and audit it (FR-113, FR-116).

    The `status='published'` update and the single outbox row are written
    in one `BEGIN IMMEDIATE` transaction, and the 02 broadcast runs only
    after that transaction commits. A delivery failure therefore leaves
    the announcement published and the outbox row pending for a retry
    instead of rolling the publish back. Publishing an already published
    announcement is a no-op: no second outbox row and no second
    user-visible notification, and the history is never deleted.
    """
    key = _announcement_key(announcement_id)
    db = get_db()
    _begin_exclusive(db)
    try:
        row = db.execute(
            f"""
            SELECT {ANNOUNCEMENT_COLUMNS}
            FROM system_announcements
            WHERE announcement_id = ?
            """,
            (key,),
        ).fetchone()
        if row is None:
            raise _not_found(key)
        announcement = _serialize_announcement(row)
        if announcement["status"] == "published":
            db.commit()
            return {
                "changed": False,
                "announcement": announcement,
                "delivery": _delivery_summary(
                    delivered=0,
                    recipient_count=0,
                    failed=0,
                ),
            }
        recipient_ids = _active_recipient_ids(db, announcement["target_roles"])
        outbox_id = enqueue_admin_notification(
            db,
            event_type=OUTBOX_EVENT_TYPE,
            event_id=announcement["event_id"],
            payload=_outbox_payload(announcement, recipient_ids),
        )
        db.execute(
            """
            UPDATE system_announcements
            SET status = 'published', published_at = ?
            WHERE announcement_id = ?
            """,
            (platform_now_iso(), key),
        )
        record_admin_audit(
            db,
            actor_id=actor_id,
            action="publish_announcement",
            target_type="system_announcement",
            target_id=key,
            before={"status": "draft"},
            after={
                "status": "published",
                "recipient_count": len(recipient_ids),
            },
            result="success",
        )
    except Exception:
        db.rollback()
        raise
    db.commit()
    return {
        "changed": True,
        "announcement": _announcement(key),
        "delivery": deliver_announcement_notification(outbox_id),
    }


def list_announcements() -> list[dict]:
    """Every announcement, newest first, drafts included (FR-107, FR-117).

    The order is computed on parsed timestamps so it does not depend on the
    stored offset, and `announcement_id ASC` breaks ties to keep the
    history stable across calls. Nothing is ever deleted, so a published
    announcement keeps its place in this list.
    """
    records = [
        _serialize_announcement(row)
        for row in _fetch_all(
            f"""
            SELECT {ANNOUNCEMENT_COLUMNS}
            FROM system_announcements
            """
        )
    ]
    ordered = sorted(
        records,
        key=lambda record: str(record["announcement_id"]),
    )
    ordered.sort(
        key=lambda record: _sort_time(record["created_at"]),
        reverse=True,
    )
    return ordered




def deliver_announcement_notification(outbox_id: int) -> dict:
    """Deliver one queued announcement broadcast after the business commit.

    011 keeps this entry point importable for its existing callers and tests;
    it now delegates to the shared outbox, which is the only place 011 talks
    to 02 for announcements. Delivery failures are recorded on the outbox row
    and reported through the summary instead of raised, so an already
    committed publish survives them (FR-113). An announcement published with
    no matching recipient reaches a terminal ``failed`` state, while a
    transient failure leaves the row ``pending`` for
    :func:`outbox.retry_admin_notifications`.
    """
    return deliver_admin_notification(outbox_id)


__all__ = [
    "create_announcement",
    "deliver_announcement_notification",
    "list_announcements",
    "publish_announcement",
]
