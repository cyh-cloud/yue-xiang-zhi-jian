from __future__ import annotations

import json

from app.db import get_db
from app.teacher_console.errors import (
    ProviderAccessDeniedError,
    ProviderConflictError,
    ProviderNotFoundError,
    ProviderValidationError,
)
from app.teacher_console.media import validate_media_reference
from app.teacher_console.time_utils import (
    now_shanghai_iso,
    parse_provider_time,
)


COURSE_DIRECTIONS = {"agriculture", "ecommerce", "handcraft"}
COURSE_STATUSES = {"draft", "pending", "published", "offline"}
MEDIA_SOURCE_TYPES = {"local_upload", "external_url"}
REQUIRED_COURSE_FIELDS = {
    "title",
    "direction",
    "summary",
    "content_tags",
    "duration_seconds",
    "media_source_type",
    "media_url",
}


def _validation_error(
    message: str,
    *,
    field: str | None = None,
) -> ProviderValidationError:
    details = {"field": field} if field is not None else {}
    return ProviderValidationError(
        message,
        code="course_validation_failed",
        details=details,
    )


def _require_positive_int(value, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise _validation_error(f"{field} 必须为正整数", field=field)
    return value


def _require_text(value, *, field: str) -> str:
    if not isinstance(value, str):
        raise _validation_error(f"{field} 必须为文本", field=field)
    normalized = value.strip()
    if not normalized:
        raise _validation_error(f"{field} 不能为空", field=field)
    return normalized


def _normalize_direction(value) -> str:
    direction = _require_text(value, field="direction")
    if direction not in COURSE_DIRECTIONS:
        raise _validation_error("学习方向无效", field="direction")
    return direction


def _normalize_content_tags(value) -> list[str]:
    if not isinstance(value, list):
        raise _validation_error("content_tags 必须为列表", field="content_tags")

    tags: list[str] = []
    seen: set[str] = set()
    for tag in value:
        if not isinstance(tag, str):
            raise _validation_error(
                "内容标签必须为文本",
                field="content_tags",
            )
        normalized = tag.strip()
        if not normalized:
            raise _validation_error(
                "内容标签不能为空",
                field="content_tags",
            )
        if normalized not in seen:
            seen.add(normalized)
            tags.append(normalized)
    return tags


def _normalize_duration(value) -> int:
    return _require_positive_int(value, field="duration_seconds")


def _normalize_media_source_type(value) -> str:
    source_type = _require_text(value, field="media_source_type")
    if source_type not in MEDIA_SOURCE_TYPES:
        raise _validation_error(
            "媒体来源类型无效",
            field="media_source_type",
        )
    return source_type


def _validate_course_payload(payload: dict, *, partial: bool = False) -> dict:
    if not isinstance(payload, dict):
        raise _validation_error("课程数据必须为对象")

    if not partial:
        missing = sorted(REQUIRED_COURSE_FIELDS - payload.keys())
        if missing:
            raise _validation_error(
                "课程字段不完整",
                field=missing[0],
            )

    values: dict = {}
    if "title" in payload:
        values["title"] = _require_text(payload["title"], field="title")
    if "direction" in payload:
        values["direction"] = _normalize_direction(payload["direction"])
    if "summary" in payload:
        values["summary"] = _require_text(payload["summary"], field="summary")
    if "content_tags" in payload:
        values["content_tags"] = _normalize_content_tags(
            payload["content_tags"]
        )
    if "duration_seconds" in payload:
        values["duration_seconds"] = _normalize_duration(
            payload["duration_seconds"]
        )
    if "media_source_type" in payload:
        values["media_source_type"] = _normalize_media_source_type(
            payload["media_source_type"]
        )
    if "media_url" in payload:
        values["media_url"] = _require_text(
            payload["media_url"],
            field="media_url",
        )

    if not partial:
        values["media_url"] = validate_media_reference(
            values["media_source_type"],
            values["media_url"],
        )
    return values


def _sync_catalog_tag_ids(
    db,
    course_id: int,
    content_tags: list[str],
) -> list[int]:
    db.execute(
        "DELETE FROM course_interest_tags WHERE course_id = ?",
        (course_id,),
    )
    if not content_tags:
        return []

    placeholders = ", ".join("?" for _ in content_tags)
    rows = db.execute(
        f"""
        SELECT id
        FROM interest_tags
        WHERE is_active = 1
          AND group_key IN ('crop', 'skill')
          AND name IN ({placeholders})
        ORDER BY id
        """,
        tuple(content_tags),
    ).fetchall()
    tag_ids = [int(row["id"]) for row in rows]
    db.executemany(
        """
        INSERT INTO course_interest_tags (course_id, tag_id)
        VALUES (?, ?)
        """,
        ((course_id, tag_id) for tag_id in tag_ids),
    )
    return tag_ids


def _course_dict(db, row) -> dict:
    course = dict(row)
    try:
        content_tags = json.loads(course.get("content_tags_json") or "[]")
    except (TypeError, ValueError):
        content_tags = []
    if not isinstance(content_tags, list):
        content_tags = []
    course["content_tags"] = [
        str(tag) for tag in content_tags if isinstance(tag, str)
    ]
    course["tag_ids"] = [
        int(tag_row["tag_id"])
        for tag_row in db.execute(
            """
            SELECT tag_id
            FROM course_interest_tags
            WHERE course_id = ?
            ORDER BY tag_id
            """,
            (course["id"],),
        ).fetchall()
    ]
    return course


def create_teacher_course(teacher_id: int, payload: dict) -> dict:
    normalized_teacher_id = _require_positive_int(
        teacher_id,
        field="teacher_id",
    )
    values = _validate_course_payload(payload)
    now = now_shanghai_iso()
    db = get_db()
    with db:
        cursor = db.execute(
            """
            INSERT INTO courses (
                title, direction, status, duration_seconds, media_url,
                published_at, summary, teacher_name, teacher_id,
                media_source_type, content_tags_json, version,
                rejection_opinion, submitted_at, created_at, updated_at
            )
            SELECT ?, ?, 'draft', ?, ?, NULL, ?, name, ?, ?, ?, 1,
                   NULL, NULL, ?, ?
            FROM users
            WHERE id = ? AND role = 'teacher' AND is_enabled = 1
            """,
            (
                values["title"],
                values["direction"],
                values["duration_seconds"],
                values["media_url"],
                values["summary"],
                normalized_teacher_id,
                values["media_source_type"],
                json.dumps(values["content_tags"], ensure_ascii=False),
                now,
                now,
                normalized_teacher_id,
            ),
        )
        if cursor.rowcount != 1:
            raise ProviderAccessDeniedError(
                "教师身份无效",
                code="course_access_denied",
                details={"teacher_id": normalized_teacher_id},
            )
        course_id = int(cursor.lastrowid)
        _sync_catalog_tag_ids(db, course_id, values["content_tags"])

    return get_teacher_course(normalized_teacher_id, course_id)


def update_teacher_course_draft(
    teacher_id: int,
    course_id: int,
    expected_version: int,
    payload: dict,
) -> dict:
    normalized_teacher_id = _require_positive_int(
        teacher_id,
        field="teacher_id",
    )
    normalized_course_id = _require_positive_int(course_id, field="course_id")
    normalized_expected_version = _require_positive_int(
        expected_version,
        field="expected_version",
    )
    changes = _validate_course_payload(payload, partial=True)
    current = get_teacher_course(
        normalized_teacher_id,
        normalized_course_id,
    )
    if current["status"] != "draft":
        raise ProviderConflictError(
            "仅草稿课程可以直接编辑",
            code="course_status_conflict",
            details={
                "course_id": normalized_course_id,
                "status": current["status"],
            },
        )
    if current["version"] != normalized_expected_version:
        raise ProviderConflictError(
            "课程版本已变化",
            code="course_version_conflict",
            details={
                "course_id": normalized_course_id,
                "expected_version": normalized_expected_version,
                "actual_version": current["version"],
            },
        )

    merged = {**current, **changes}
    values = _validate_course_payload(merged)
    now = now_shanghai_iso()
    db = get_db()
    with db:
        cursor = db.execute(
            """
            UPDATE courses
            SET title = ?,
                direction = ?,
                duration_seconds = ?,
                media_url = ?,
                summary = ?,
                media_source_type = ?,
                content_tags_json = ?,
                version = version + 1,
                updated_at = ?
            WHERE id = ?
              AND teacher_id = ?
              AND status = 'draft'
              AND version = ?
            """,
            (
                values["title"],
                values["direction"],
                values["duration_seconds"],
                values["media_url"],
                values["summary"],
                values["media_source_type"],
                json.dumps(values["content_tags"], ensure_ascii=False),
                now,
                normalized_course_id,
                normalized_teacher_id,
                normalized_expected_version,
            ),
        )
        if cursor.rowcount != 1:
            raise ProviderConflictError(
                "课程版本或状态已变化",
                code="course_version_conflict",
                details={"course_id": normalized_course_id},
            )
        _sync_catalog_tag_ids(
            db,
            normalized_course_id,
            values["content_tags"],
        )

    return get_teacher_course(normalized_teacher_id, normalized_course_id)


def get_teacher_course(teacher_id: int, course_id: int) -> dict:
    normalized_teacher_id = _require_positive_int(
        teacher_id,
        field="teacher_id",
    )
    normalized_course_id = _require_positive_int(course_id, field="course_id")
    db = get_db()
    row = db.execute(
        "SELECT * FROM courses WHERE id = ?",
        (normalized_course_id,),
    ).fetchone()
    if row is None:
        raise ProviderNotFoundError(
            "课程不存在",
            code="course_not_found",
            details={"course_id": normalized_course_id},
        )
    if int(row["teacher_id"] or 0) != normalized_teacher_id:
        raise ProviderAccessDeniedError(
            "无权访问该课程",
            code="course_access_denied",
            details={"course_id": normalized_course_id},
        )
    return _course_dict(db, row)


def list_teacher_courses(
    teacher_id: int,
    direction=None,
    status=None,
) -> list[dict]:
    normalized_teacher_id = _require_positive_int(
        teacher_id,
        field="teacher_id",
    )
    conditions = ["teacher_id = ?"]
    parameters: list[object] = [normalized_teacher_id]

    if direction is not None:
        conditions.append("direction = ?")
        parameters.append(_normalize_direction(direction))
    if status is not None:
        normalized_status = _require_text(status, field="status")
        if normalized_status not in COURSE_STATUSES:
            raise _validation_error("课程状态无效", field="status")
        conditions.append("status = ?")
        parameters.append(normalized_status)

    db = get_db()
    rows = db.execute(
        f"""
        SELECT *
        FROM courses
        WHERE {" AND ".join(conditions)}
        """,
        tuple(parameters),
    ).fetchall()
    courses = [_course_dict(db, row) for row in rows]
    courses.sort(
        key=lambda course: (
            parse_provider_time(course["updated_at"]),
            int(course["id"]),
        ),
        reverse=True,
    )
    return courses
