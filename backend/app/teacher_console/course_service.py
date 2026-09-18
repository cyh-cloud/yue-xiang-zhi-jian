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
from app.teacher_console.review_adapter import CourseReviewAdapter
from app.teacher_console.time_utils import (
    now_shanghai_iso,
    parse_provider_time,
)


COURSE_DIRECTIONS = {"agriculture", "ecommerce", "handcraft"}
COURSE_STATUSES = {"draft", "pending", "published", "offline"}
REVIEWABLE_COURSE_STATUSES = {
    "pending",
    "published",
    "rejected",
    "offline",
}
SUBMITTABLE_COURSE_STATUSES = {"draft", "rejected"}
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

    tag_ids = _catalog_tag_ids(db, content_tags)
    db.executemany(
        """
        INSERT INTO course_interest_tags (course_id, tag_id)
        VALUES (?, ?)
        """,
        ((course_id, tag_id) for tag_id in tag_ids),
    )
    return tag_ids


def _catalog_tag_ids(db, content_tags: list[str]) -> list[int]:
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
    return [int(row["id"]) for row in rows]


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


def resolve_teacher_visible_status(
    course: dict,
    review_status: str | None,
) -> str:
    if course.get("teacher_id") is None and course.get("status") == "published":
        return "published"
    if course.get("status") == "draft":
        return "draft"
    if course.get("status") == "offline":
        return "offline"
    if review_status == "approved":
        return "published"
    if review_status == "rejected":
        return "rejected"
    return "pending"


def _review_status(course_id: int) -> str | None:
    review = CourseReviewAdapter().read(course_id)
    if review is None:
        return None
    if not isinstance(review, dict):
        raise ProviderValidationError(
            "审核服务返回无效数据",
            code="review_response_invalid",
            details={"course_id": course_id},
        )
    return review.get("review_status")


def _parse_provider_result(
    review_result: dict,
    *,
    course_id: int,
) -> tuple[int, str]:
    if not isinstance(review_result, dict):
        raise ProviderValidationError(
            "审核服务返回无效数据",
            code="review_response_invalid",
            details={"course_id": course_id},
        )

    version = review_result.get("version")
    review_status = review_result.get("review_status")
    if (
        isinstance(version, bool)
        or not isinstance(version, int)
        or version <= 0
        or review_status not in {"pending", "approved", "rejected", "offline"}
    ):
        raise ProviderValidationError(
            "审核服务返回无效数据",
            code="review_response_invalid",
            details={"course_id": course_id},
        )
    return version, review_status


def _require_pending_result(
    review_result: dict,
    *,
    course: dict,
) -> tuple[int, str]:
    version, review_status = _parse_provider_result(
        review_result,
        course_id=int(course["id"]),
    )
    if review_status != "pending":
        raise ProviderConflictError(
            "审核服务未返回待审核状态",
            code="course_review_status_conflict",
            details={
                "course_id": int(course["id"]),
                "review_status": review_status,
            },
        )
    if version < int(course["version"]):
        raise ProviderConflictError(
            "审核服务返回的版本已过期",
            code="course_version_conflict",
            details={
                "course_id": int(course["id"]),
                "expected_version": int(course["version"]),
                "provider_version": version,
            },
        )
    return version, review_status


def _validate_quiz_config(value, *, field: str) -> dict:
    if not isinstance(value, dict):
        raise _validation_error(f"{field} 必须为对象", field=field)
    enabled = value.get("enabled", False)
    scoring_rule = value.get("scoring_rule", "")
    questions = value.get("questions", [])
    if not isinstance(enabled, bool):
        raise _validation_error(
            f"{field}.enabled 必须为布尔值",
            field=field,
        )
    if not isinstance(scoring_rule, str):
        raise _validation_error(
            f"{field}.scoring_rule 必须为文本",
            field=field,
        )
    if not isinstance(questions, list):
        raise _validation_error(
            f"{field}.questions 必须为列表",
            field=field,
        )

    if enabled:
        if not scoring_rule.strip():
            raise _validation_error(
                "启用测验时必须填写评分规则",
                field=field,
            )
        if not 3 <= len(questions) <= 5:
            raise _validation_error(
                "启用测验时必须包含 3 到 5 道题",
                field=field,
            )

        question_ids: set[str] = set()
        for question in questions:
            if not isinstance(question, dict):
                raise _validation_error(
                    "测验题目必须为对象",
                    field=field,
                )
            question_id = question.get("id")
            if (
                not isinstance(question_id, str)
                or not question_id.strip()
            ):
                raise _validation_error(
                    "测验题目 ID 必须为非空文本",
                    field=field,
                )
            normalized_question_id = question_id.strip()
            if normalized_question_id in question_ids:
                raise _validation_error(
                    "测验题目 ID 不能重复",
                    field=field,
                )
            question_ids.add(normalized_question_id)

            question_type = question.get("type")
            if (
                not isinstance(question_type, str)
                or question_type not in {"single_choice", "true_false"}
            ):
                raise _validation_error(
                    "测验题型无效",
                    field=field,
                )

            prompt = question.get("prompt")
            if not isinstance(prompt, str) or not prompt.strip():
                raise _validation_error(
                    "测验题干不能为空",
                    field=field,
                )

            options = question.get("options")
            if not isinstance(options, list) or not options:
                raise _validation_error(
                    "测验选项不能为空",
                    field=field,
                )
            for option in options:
                if not isinstance(option, str) or not option.strip():
                    raise _validation_error(
                        "测验选项必须为非空文本",
                        field=field,
                    )

            answer = question.get("answer")
            if not isinstance(answer, str) or answer not in options:
                raise _validation_error(
                    "测验答案必须存在于选项中",
                    field=field,
                )

    return {
        "enabled": enabled,
        "scoring_rule": scoring_rule,
        "questions": questions,
    }


def _normalize_quiz_override(value) -> dict | None:
    if value is None:
        return None
    return _validate_quiz_config(value, field="quiz_override")


def _load_quiz_config(course: dict) -> dict:
    override = course.get("quiz_config")
    if isinstance(override, dict):
        return _validate_quiz_config(override, field="quiz_config")

    course_id = _require_positive_int(course.get("id"), field="id")
    row = get_db().execute(
        """
        SELECT enabled, scoring_rule, questions_json
        FROM course_quizzes
        WHERE course_id = ?
        """,
        (course_id,),
    ).fetchone()
    if row is None:
        return _validate_quiz_config(
            {
                "enabled": False,
                "scoring_rule": "",
                "questions": [],
            },
            field="quiz_config",
        )

    try:
        questions = json.loads(row["questions_json"] or "[]")
    except (TypeError, ValueError):
        questions = []
    if not isinstance(questions, list):
        questions = []
    return _validate_quiz_config(
        {
            "enabled": bool(row["enabled"]),
            "scoring_rule": str(row["scoring_rule"] or ""),
            "questions": questions,
        },
        field="quiz_config",
    )


def review_payload(course: dict) -> dict:
    course_id = _require_positive_int(course.get("id"), field="id")
    tag_ids = course.get("tag_ids")
    if not isinstance(tag_ids, list):
        tag_ids = [
            int(row["tag_id"])
            for row in get_db().execute(
                """
                SELECT tag_id
                FROM course_interest_tags
                WHERE course_id = ?
                ORDER BY tag_id
                """,
                (course_id,),
            ).fetchall()
        ]

    return {
        "title": _require_text(course.get("title"), field="title"),
        "direction": _normalize_direction(course.get("direction")),
        "summary": _require_text(course.get("summary"), field="summary"),
        "tag_ids": [int(tag_id) for tag_id in tag_ids],
        "duration_seconds": _normalize_duration(
            course.get("duration_seconds")
        ),
        "media_url": _require_text(course.get("media_url"), field="media_url"),
        "quiz_config": _load_quiz_config(course),
    }


def _review_payload_for_values(
    db,
    course: dict,
    values: dict,
    quiz_override: dict | None,
) -> dict:
    payload_course = {
        **course,
        **values,
        "tag_ids": _catalog_tag_ids(db, values["content_tags"]),
    }
    if quiz_override is not None:
        payload_course["quiz_config"] = quiz_override
    return review_payload(payload_course)


def _write_quiz_override(
    db,
    course_id: int,
    quiz_override: dict,
    now: str,
) -> None:
    db.execute(
        """
        INSERT INTO course_quizzes (
            course_id, enabled, scoring_rule, questions_json, updated_at
        )
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(course_id) DO UPDATE SET
            enabled = excluded.enabled,
            scoring_rule = excluded.scoring_rule,
            questions_json = excluded.questions_json,
            updated_at = excluded.updated_at
        """,
        (
            course_id,
            1 if quiz_override["enabled"] else 0,
            quiz_override["scoring_rule"],
            json.dumps(
                quiz_override["questions"],
                ensure_ascii=False,
            ),
            now,
        ),
    )


def _apply_pending_transition(
    db,
    course: dict,
    values: dict,
    provider_version: int,
    quiz_override: dict | None,
    *,
    from_status: str,
    actor_id: int,
) -> None:
    now = now_shanghai_iso()
    cursor = db.execute(
        """
        UPDATE courses
        SET title = ?,
            direction = ?,
            status = 'pending',
            duration_seconds = ?,
            media_url = ?,
            published_at = NULL,
            summary = ?,
            media_source_type = ?,
            content_tags_json = ?,
            version = ?,
            rejection_opinion = NULL,
            submitted_at = ?,
            updated_at = ?
        WHERE id = ?
          AND version = ?
          AND status = ?
        """,
        (
            values["title"],
            values["direction"],
            values["duration_seconds"],
            values["media_url"],
            values["summary"],
            values["media_source_type"],
            json.dumps(values["content_tags"], ensure_ascii=False),
            provider_version,
            now,
            now,
            int(course["id"]),
            int(course["version"]),
            course["status"],
        ),
    )
    if cursor.rowcount != 1:
        raise ProviderConflictError(
            "课程版本或状态已变化",
            code="course_version_conflict",
            details={"course_id": int(course["id"])},
        )

    _sync_catalog_tag_ids(db, int(course["id"]), values["content_tags"])
    if quiz_override is not None:
        _write_quiz_override(
            db,
            int(course["id"]),
            quiz_override,
            now,
        )
    db.execute(
        """
        INSERT INTO teacher_course_status_history (
            course_id, from_status, to_status, actor_id,
            opinion, version, created_at
        )
        VALUES (?, ?, 'pending', ?, NULL, ?, ?)
        """,
        (
            int(course["id"]),
            from_status,
            actor_id,
            provider_version,
            now,
        ),
    )


def submit_course_for_review(
    teacher_id: int,
    course_id: int,
    expected_version: int,
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
    course = get_teacher_course(
        normalized_teacher_id,
        normalized_course_id,
    )
    if int(course["version"]) != normalized_expected_version:
        raise ProviderConflictError(
            "课程版本已变化",
            code="course_version_conflict",
            details={
                "course_id": normalized_course_id,
                "expected_version": normalized_expected_version,
                "actual_version": int(course["version"]),
            },
        )
    _load_quiz_config(course)
    visible_status = resolve_teacher_visible_status(
        course,
        _review_status(normalized_course_id),
    )
    if visible_status not in SUBMITTABLE_COURSE_STATUSES:
        raise ProviderConflictError(
            "当前课程状态不能提交审核",
            code="course_status_conflict",
            details={
                "course_id": normalized_course_id,
                "status": visible_status,
            },
        )

    values = _validate_course_payload(course)
    validate_media_reference(
        values["media_source_type"],
        values["media_url"],
        check_remote=True,
    )
    db = get_db()
    payload = _review_payload_for_values(db, course, values, None)
    adapter = CourseReviewAdapter()
    with db:
        result = adapter.submit(course, payload)
        provider_version, _ = _require_pending_result(
            result,
            course=course,
        )
        _apply_pending_transition(
            db,
            course,
            values,
            provider_version,
            None,
            from_status=visible_status,
            actor_id=normalized_teacher_id,
        )

    return get_teacher_course(normalized_teacher_id, normalized_course_id)


def edit_course(
    teacher_id: int,
    course_id: int,
    expected_version: int,
    payload: dict,
    *,
    quiz_override=None,
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
    course = get_teacher_course(
        normalized_teacher_id,
        normalized_course_id,
    )
    if int(course["version"]) != normalized_expected_version:
        raise ProviderConflictError(
            "课程版本已变化",
            code="course_version_conflict",
            details={
                "course_id": normalized_course_id,
                "expected_version": normalized_expected_version,
                "actual_version": int(course["version"]),
            },
        )
    normalized_quiz_override = _normalize_quiz_override(quiz_override)
    if normalized_quiz_override is None:
        _load_quiz_config(course)
    visible_status = resolve_teacher_visible_status(
        course,
        _review_status(normalized_course_id),
    )
    if visible_status not in REVIEWABLE_COURSE_STATUSES:
        raise ProviderConflictError(
            "当前课程状态不能编辑重审",
            code="course_status_conflict",
            details={
                "course_id": normalized_course_id,
                "status": visible_status,
            },
        )

    changes = _validate_course_payload(payload, partial=True)
    values = _validate_course_payload({**course, **changes})
    validate_media_reference(
        values["media_source_type"],
        values["media_url"],
        check_remote=True,
    )
    db = get_db()
    review_payload_value = _review_payload_for_values(
        db,
        course,
        values,
        normalized_quiz_override,
    )
    adapter = CourseReviewAdapter()
    with db:
        result = adapter.edit(course, review_payload_value)
        provider_version, _ = _require_pending_result(
            result,
            course=course,
        )
        _apply_pending_transition(
            db,
            course,
            values,
            provider_version,
            normalized_quiz_override,
            from_status=visible_status,
            actor_id=normalized_teacher_id,
        )

    return get_teacher_course(normalized_teacher_id, normalized_course_id)


def set_course_offline(
    teacher_id: int,
    course_id: int,
    expected_version: int,
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
    course = get_teacher_course(
        normalized_teacher_id,
        normalized_course_id,
    )
    if int(course["version"]) != normalized_expected_version:
        raise ProviderConflictError(
            "课程版本已变化",
            code="course_version_conflict",
            details={
                "course_id": normalized_course_id,
                "expected_version": normalized_expected_version,
                "actual_version": int(course["version"]),
            },
        )
    visible_status = resolve_teacher_visible_status(
        course,
        _review_status(normalized_course_id),
    )
    if visible_status != "published":
        raise ProviderConflictError(
            "仅已上架课程可以下架",
            code="course_status_conflict",
            details={
                "course_id": normalized_course_id,
                "status": visible_status,
            },
        )

    now = now_shanghai_iso()
    db = get_db()
    with db:
        cursor = db.execute(
            """
            UPDATE courses
            SET status = 'offline',
                published_at = NULL,
                updated_at = ?
            WHERE id = ?
              AND version = ?
              AND status = ?
            """,
            (
                now,
                normalized_course_id,
                normalized_expected_version,
                course["status"],
            ),
        )
        if cursor.rowcount != 1:
            raise ProviderConflictError(
                "课程版本或状态已变化",
                code="course_version_conflict",
                details={"course_id": normalized_course_id},
            )
        db.execute(
            """
            INSERT INTO teacher_course_status_history (
                course_id, from_status, to_status, actor_id,
                opinion, version, created_at
            )
            VALUES (?, 'published', 'offline', ?, NULL, ?, ?)
            """,
            (
                normalized_course_id,
                normalized_teacher_id,
                normalized_expected_version,
                now,
            ),
        )

    return get_teacher_course(normalized_teacher_id, normalized_course_id)


def request_course_relist(
    teacher_id: int,
    course_id: int,
    expected_version: int,
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
    course = get_teacher_course(
        normalized_teacher_id,
        normalized_course_id,
    )
    if int(course["version"]) != normalized_expected_version:
        raise ProviderConflictError(
            "课程版本已变化",
            code="course_version_conflict",
            details={
                "course_id": normalized_course_id,
                "expected_version": normalized_expected_version,
                "actual_version": int(course["version"]),
            },
        )
    _load_quiz_config(course)
    visible_status = resolve_teacher_visible_status(
        course,
        _review_status(normalized_course_id),
    )
    if visible_status != "offline":
        raise ProviderConflictError(
            "仅已下架课程可以重新上架审核",
            code="course_status_conflict",
            details={
                "course_id": normalized_course_id,
                "status": visible_status,
            },
        )

    values = _validate_course_payload(course)
    validate_media_reference(
        values["media_source_type"],
        values["media_url"],
        check_remote=True,
    )
    db = get_db()
    payload = _review_payload_for_values(db, course, values, None)
    adapter = CourseReviewAdapter()
    with db:
        result = adapter.submit(course, payload)
        provider_version, _ = _require_pending_result(
            result,
            course=course,
        )
        _apply_pending_transition(
            db,
            course,
            values,
            provider_version,
            None,
            from_status="offline",
            actor_id=normalized_teacher_id,
        )

    return get_teacher_course(normalized_teacher_id, normalized_course_id)
