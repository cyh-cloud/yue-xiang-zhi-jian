from __future__ import annotations

from uuid import uuid4

from app.agri_skills.providers import get_course_provider
from app.db import get_db
from app.handcraft_inheritance.providers import get_teaching_video_provider
from app.teacher_console.errors import (
    ProviderAccessDeniedError,
    ProviderConflictError,
    ProviderNotFoundError,
    ProviderValidationError,
)
from app.teacher_console.time_utils import now_shanghai_iso


CONTENT_TYPES = {"course_video", "handcraft_teaching_video"}


def _validation_error(
    message: str,
    *,
    field: str | None = None,
) -> ProviderValidationError:
    details = {"field": field} if field is not None else {}
    return ProviderValidationError(
        message,
        code="comment_validation_failed",
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


def _optional_content_id(value: object) -> str | None:
    if value is None:
        return None
    return _required_text(value, "content_id")


def _comment_payload(row) -> dict:
    parent_comment_id = row["parent_comment_id"]
    return {
        "comment_id": str(row["comment_id"]),
        "content_type": str(row["content_type"]),
        "content_id": str(row["content_id"]),
        "author_id": int(row["author_id"]),
        "parent_comment_id": (
            str(parent_comment_id)
            if parent_comment_id is not None
            else None
        ),
        "body": str(row["body"]),
        "is_teacher_reply": bool(row["is_teacher_reply"]),
        "created_at": str(row["created_at"]),
        "updated_at": str(row["updated_at"]),
    }


def _load_comment(comment_id: str):
    return get_db().execute(
        """
        SELECT
            comment_id,
            content_type,
            content_id,
            author_id,
            parent_comment_id,
            body,
            is_teacher_reply,
            is_visible,
            created_at,
            updated_at
        FROM content_comments
        WHERE comment_id = ?
        """,
        (comment_id,),
    ).fetchone()


def _course_id_from_content(content_id: str) -> int:
    try:
        course_id = int(content_id)
    except (TypeError, ValueError):
        raise ProviderConflictError(
            "目标课程当前不可回复",
            code="comment_target_unavailable",
            details={"content_id": content_id},
        ) from None
    if course_id <= 0:
        raise ProviderConflictError(
            "目标课程当前不可回复",
            code="comment_target_unavailable",
            details={"content_id": content_id},
        )
    return course_id


def _video_is_replyable(video: object) -> bool:
    return (
        isinstance(video, dict)
        and video.get("review_status") == "approved"
        and bool(video.get("source_available"))
    )


def _owned_course_ids(teacher_id: int) -> set[str]:
    rows = get_db().execute(
        """
        SELECT id
        FROM courses
        WHERE teacher_id = ?
        """,
        (teacher_id,),
    ).fetchall()
    return {str(int(row["id"])) for row in rows}


def _video_is_visible(video_id: str) -> bool:
    return _video_is_replyable(
        get_teaching_video_provider().get_video(video_id)
    )


def _require_target_visible(
    content_type: str,
    content_id: str,
) -> None:
    if content_type == "course_video":
        course_id = _course_id_from_content(content_id)
        if get_course_provider().get_course(course_id) is None:
            raise ProviderConflictError(
                "目标课程当前不可评论",
                code="comment_target_unavailable",
                details={"content_id": content_id},
            )
    elif content_type == "handcraft_teaching_video":
        if not _video_is_visible(content_id):
            raise ProviderConflictError(
                "目标非遗视频当前不可评论",
                code="comment_target_unavailable",
                details={"content_id": content_id},
            )
    else:
        raise _validation_error("内容类型无效", field="content_type")


def list_teacher_comments(
    teacher_id: int,
    content_type: str | None = None,
    content_id: str | None = None,
) -> list[dict]:
    normalized_teacher_id = _require_positive_int(
        teacher_id,
        field="teacher_id",
    )
    if content_type is not None and content_type not in CONTENT_TYPES:
        raise _validation_error("内容类型无效", field="content_type")
    normalized_content_id = _optional_content_id(content_id)

    owned_course_ids = _owned_course_ids(normalized_teacher_id)
    rows = get_db().execute(
        """
        SELECT
            comment_id,
            content_type,
            content_id,
            author_id,
            parent_comment_id,
            body,
            is_teacher_reply,
            is_visible,
            created_at,
            updated_at
        FROM content_comments
        WHERE is_visible = 1
        ORDER BY id ASC
        """
    ).fetchall()

    comments = []
    video_visibility: dict[str, bool] = {}
    for row in rows:
        row_content_type = str(row["content_type"])
        row_content_id = str(row["content_id"])
        if content_type is not None and row_content_type != content_type:
            continue
        if (
            normalized_content_id is not None
            and row_content_id != normalized_content_id
        ):
            continue

        if row_content_type == "course_video":
            if row_content_id not in owned_course_ids:
                continue
        elif row_content_type == "handcraft_teaching_video":
            if row_content_id not in video_visibility:
                video_visibility[row_content_id] = _video_is_visible(
                    row_content_id
                )
            if not video_visibility[row_content_id]:
                continue
        else:
            continue
        comments.append(_comment_payload(row))
    return comments


def reply_to_comment(
    teacher_id: int,
    comment_id: str,
    body: object,
) -> dict:
    normalized_teacher_id = _require_positive_int(
        teacher_id,
        field="teacher_id",
    )
    normalized_comment_id = _required_text(comment_id, "comment_id")
    normalized_body = _required_text(body, "回复内容")
    parent = _load_comment(normalized_comment_id)
    if parent is None or not bool(parent["is_visible"]):
        raise ProviderNotFoundError(
            "评论不存在",
            code="comment_not_found",
            details={"comment_id": normalized_comment_id},
        )

    parent_content_type = str(parent["content_type"])
    parent_content_id = str(parent["content_id"])
    if parent_content_type == "course_video":
        course_id = _course_id_from_content(parent_content_id)
        owner = get_db().execute(
            """
            SELECT teacher_id
            FROM courses
            WHERE id = ?
            """,
            (course_id,),
        ).fetchone()
        if (
            owner is None
            or int(owner["teacher_id"] or 0) != normalized_teacher_id
        ):
            raise ProviderAccessDeniedError(
                "只能回复本人课程的评论",
                code="comment_access_denied",
                details={"comment_id": normalized_comment_id},
            )
        if get_course_provider().get_course(course_id) is None:
            raise ProviderConflictError(
                "目标课程当前不可回复",
                code="comment_target_unavailable",
                details={"comment_id": normalized_comment_id},
            )
    elif parent_content_type == "handcraft_teaching_video":
        video = get_teaching_video_provider().get_video(parent_content_id)
        if not _video_is_replyable(video):
            raise ProviderConflictError(
                "目标非遗视频当前不可回复",
                code="comment_target_unavailable",
                details={"comment_id": normalized_comment_id},
            )
    else:
        raise ProviderConflictError(
            "目标内容当前不可回复",
            code="comment_target_unavailable",
            details={"comment_id": normalized_comment_id},
        )

    now = now_shanghai_iso()
    reply_id = f"reply-{uuid4().hex}"
    db = get_db()
    with db:
        db.execute(
            """
            INSERT INTO content_comments (
                comment_id, content_type, content_id, author_id,
                parent_comment_id, body, is_teacher_reply,
                is_visible, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, 1, 1, ?, ?)
            """,
            (
                reply_id,
                parent_content_type,
                parent_content_id,
                normalized_teacher_id,
                normalized_comment_id,
                normalized_body,
                now,
                now,
            ),
        )
    return _comment_payload(_load_comment(reply_id))


def list_content_comments(
    content_type: str,
    content_id: str,
) -> list[dict]:
    normalized_content_type = _required_text(
        content_type,
        "content_type",
    )
    normalized_content_id = _required_text(content_id, "content_id")
    if normalized_content_type not in CONTENT_TYPES:
        raise _validation_error("内容类型无效", field="content_type")
    _require_target_visible(
        normalized_content_type,
        normalized_content_id,
    )

    rows = get_db().execute(
        """
        SELECT
            comment_id,
            content_type,
            content_id,
            author_id,
            parent_comment_id,
            body,
            is_teacher_reply,
            is_visible,
            created_at,
            updated_at
        FROM content_comments
        WHERE content_type = ?
          AND content_id = ?
          AND is_visible = 1
        ORDER BY id ASC
        """,
        (normalized_content_type, normalized_content_id),
    ).fetchall()
    return [_comment_payload(row) for row in rows]


def create_learner_comment(
    student_id: int,
    content_type: str,
    content_id: str,
    body: object,
) -> dict:
    normalized_student_id = _require_positive_int(
        student_id,
        field="student_id",
    )
    normalized_content_type = _required_text(
        content_type,
        "content_type",
    )
    normalized_content_id = _required_text(content_id, "content_id")
    normalized_body = _required_text(body, "评论内容")
    if normalized_content_type not in CONTENT_TYPES:
        raise _validation_error("内容类型无效", field="content_type")
    _require_target_visible(
        normalized_content_type,
        normalized_content_id,
    )

    now = now_shanghai_iso()
    comment_id = f"comment-{uuid4().hex}"
    db = get_db()
    with db:
        db.execute(
            """
            INSERT INTO content_comments (
                comment_id, content_type, content_id, author_id,
                body, is_teacher_reply, is_visible, created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, 0, 1, ?, ?)
            """,
            (
                comment_id,
                normalized_content_type,
                normalized_content_id,
                normalized_student_id,
                normalized_body,
                now,
                now,
            ),
        )
    return _comment_payload(_load_comment(comment_id))
