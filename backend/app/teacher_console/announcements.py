from __future__ import annotations

import json
from uuid import uuid4

from app.db import get_db
from app.messaging.broadcasts import emit_teaching_announcement
from app.teacher_console.errors import (
    ProviderAccessDeniedError,
    ProviderConflictError,
    ProviderValidationError,
)
from app.teacher_console.time_utils import now_shanghai_iso


def _validation_error(
    message: str,
    *,
    field: str | None = None,
) -> ProviderValidationError:
    details = {"field": field} if field is not None else {}
    return ProviderValidationError(
        message,
        code="teaching_announcement_validation_failed",
        details=details,
    )


def _require_positive_int(value, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise _validation_error(f"{field} 必须为正整数", field=field)
    return value


def _required_text(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise _validation_error(f"{field} 必须为文本", field=field)
    normalized = value.strip()
    if not normalized:
        raise _validation_error(f"{field} 不能为空", field=field)
    return normalized


def _delivery_result(row) -> dict:
    try:
        result = json.loads(row["delivery_result_json"] or "{}")
    except (TypeError, ValueError):
        return {}
    return result if isinstance(result, dict) else {}


def _announcement_payload(row) -> dict:
    return {
        "announcement_id": str(row["announcement_id"]),
        "teacher_id": int(row["teacher_id"]),
        "title": str(row["title"]),
        "body": str(row["body"]),
        "event_id": str(row["event_id"]),
        "delivery_status": str(row["delivery_status"]),
        "delivery_result": _delivery_result(row),
        "created_at": str(row["created_at"]),
    }


def _get_announcement(announcement_id: str) -> dict:
    row = get_db().execute(
        """
        SELECT
            announcement_id,
            teacher_id,
            title,
            body,
            event_id,
            delivery_status,
            delivery_result_json,
            created_at
        FROM teacher_announcements
        WHERE announcement_id = ?
        """,
        (announcement_id,),
    ).fetchone()
    if row is None:
        raise _validation_error("公告不存在")
    return _announcement_payload(row)


def _record_delivery_event(
    announcement_id: str,
    status: str,
    result: dict,
) -> None:
    encoded_result = json.dumps(
        result,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    now = now_shanghai_iso()
    db = get_db()
    with db:
        db.execute(
            """
            UPDATE teacher_announcements
            SET delivery_status = ?,
                delivery_result_json = ?
            WHERE announcement_id = ?
            """,
            (status, encoded_result, announcement_id),
        )
        db.execute(
            """
            INSERT INTO teacher_announcement_delivery_events (
                announcement_id, status, result_json, created_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (announcement_id, status, encoded_result, now),
        )


def publish_teaching_announcement(
    teacher_id: int,
    title: object,
    body: object,
) -> dict:
    normalized_teacher_id = _require_positive_int(
        teacher_id,
        field="teacher_id",
    )
    normalized_title = _required_text(title, "标题")
    normalized_body = _required_text(body, "正文")
    announcement_id = f"teaching-{uuid4().hex}"
    event_id = f"{announcement_id}:v1"
    now = now_shanghai_iso()
    db = get_db()
    with db:
        cursor = db.execute(
            """
            INSERT INTO teacher_announcements (
                announcement_id,
                teacher_id,
                title,
                body,
                event_id,
                delivery_status,
                delivery_result_json,
                created_at
            )
            SELECT ?, id, ?, ?, ?, 'pending', '{}', ?
            FROM users
            WHERE id = ? AND role = 'teacher' AND is_enabled = 1
            """,
            (
                announcement_id,
                normalized_title,
                normalized_body,
                event_id,
                now,
                normalized_teacher_id,
            ),
        )
        if cursor.rowcount != 1:
            raise ProviderAccessDeniedError(
                "教师身份无效",
                code="teaching_announcement_access_denied",
                details={"teacher_id": normalized_teacher_id},
            )

    try:
        result = emit_teaching_announcement(
            event_id=event_id,
            teacher_id=normalized_teacher_id,
            announcement_id=announcement_id,
            title=normalized_title,
            body=normalized_body,
        )
    except Exception:
        _record_delivery_event(announcement_id, "failed", {})
        raise

    _record_delivery_event(announcement_id, "sent", result)
    return _get_announcement(announcement_id)


def list_teaching_announcements(teacher_id: int) -> list[dict]:
    normalized_teacher_id = _require_positive_int(
        teacher_id,
        field="teacher_id",
    )
    rows = get_db().execute(
        """
        SELECT
            announcement_id,
            teacher_id,
            title,
            body,
            event_id,
            delivery_status,
            delivery_result_json,
            created_at
        FROM teacher_announcements
        WHERE teacher_id = ?
        ORDER BY id DESC
        """,
        (normalized_teacher_id,),
    ).fetchall()
    return [_announcement_payload(row) for row in rows]


def update_teaching_announcement(
    teacher_id: int,
    announcement_id: str,
    title: object,
    body: object,
) -> dict:
    raise ProviderConflictError(
        "已群发公告不可修改",
        code="teaching_announcement_immutable",
        details={"announcement_id": str(announcement_id)},
    )
