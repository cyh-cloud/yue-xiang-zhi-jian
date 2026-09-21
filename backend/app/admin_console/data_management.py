from __future__ import annotations

import sqlite3

from app.admin_console.audit import record_admin_audit
from app.admin_console.errors import (
    ProviderConflictError,
    ProviderNotFoundError,
    ProviderValidationError,
)
from app.admin_console.time_utils import platform_now_iso
from app.db import get_db
from app.handcraft_inheritance.providers import (
    get_active_teaching_video,
    list_active_teaching_videos,
)


CONTENT_TYPES = frozenset(
    {
        "policy",
        "news",
        "course",
        "job",
        "handcraft_video",
        "comment",
        "preset",
    }
)


def _validation(
    message: str,
    code: str = "data_management_validation_failed",
    **details,
) -> ProviderValidationError:
    return ProviderValidationError(message, code=code, details=details)


def _not_found(message: str, code: str, **details) -> ProviderNotFoundError:
    return ProviderNotFoundError(message, code=code, details=details)


def _conflict(message: str, code: str, **details) -> ProviderConflictError:
    return ProviderConflictError(message, code=code, details=details)


def _content_type(value: object) -> str:
    if not isinstance(value, str) or value not in CONTENT_TYPES:
        raise _validation(
            "内容类型不正确",
            "content_type_invalid",
            content_type=value,
        )
    return value


def _expected_version(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise _validation(
            "expected_version 必须是正整数",
            field="expected_version",
        )
    return value


def _required_text(value: object, field: str, *, maximum: int) -> str:
    if not isinstance(value, str):
        raise _validation(f"{field} 必须是文本", field=field)
    normalized = value.strip()
    if not normalized:
        raise _validation(f"{field} 不能为空", field=field)
    if len(normalized) > maximum:
        raise _validation(
            f"{field} 长度不能超过 {maximum} 个字符",
            field=field,
            max_length=maximum,
        )
    return normalized


def _require_version(current: int, expected: int, *, code: str, **details) -> None:
    if current != expected:
        raise _conflict(
            "内容版本已变化，请刷新后重试",
            code,
            expected_version=expected,
            current_version=current,
            **details,
        )


def _begin(db: sqlite3.Connection) -> None:
    """Open the write transaction before any read that guards a write."""
    if db.in_transaction:
        db.commit()
    db.execute("BEGIN IMMEDIATE")


def _parse_course_id(content_id: object) -> int:
    try:
        return int(str(content_id).strip())
    except (TypeError, ValueError):
        raise _not_found(
            "课程不存在",
            "course_not_found",
            content_id=str(content_id),
        ) from None


# --- row loaders (raw, so a tombstone is still visible to the mutators) -----


def _policy_row(db: sqlite3.Connection, policy_id: str) -> sqlite3.Row | None:
    return db.execute(
        "SELECT * FROM government_policies WHERE id = ?",
        (policy_id,),
    ).fetchone()


def _news_row(db: sqlite3.Connection, news_id: str) -> sqlite3.Row | None:
    return db.execute(
        "SELECT * FROM government_news WHERE id = ?",
        (news_id,),
    ).fetchone()


def _course_row(db: sqlite3.Connection, course_id: int) -> sqlite3.Row | None:
    return db.execute(
        "SELECT * FROM courses WHERE id = ?",
        (course_id,),
    ).fetchone()


def _job_row(db: sqlite3.Connection, job_id: str) -> sqlite3.Row | None:
    return db.execute(
        "SELECT * FROM job_positions WHERE job_id = ?",
        (job_id,),
    ).fetchone()


def _video_row(db: sqlite3.Connection, video_id: str) -> sqlite3.Row | None:
    return db.execute(
        "SELECT * FROM heritage_videos WHERE video_id = ?",
        (video_id,),
    ).fetchone()


def _comment_row(db: sqlite3.Connection, comment_id: str) -> sqlite3.Row | None:
    return db.execute(
        "SELECT * FROM content_comments WHERE comment_id = ?",
        (comment_id,),
    ).fetchone()


# --- payload serializers -----------------------------------------------------


def _policy_payload(row: sqlite3.Row) -> dict:
    return {
        "content_type": "policy",
        "id": str(row["id"]),
        "title": str(row["title"]),
        "content": str(row["content"]),
        "category_code": str(row["category_code"]),
        "status": str(row["status"]),
        "view_count": int(row["view_count"]),
        "version": int(row["version"]),
        "published_at": row["published_at"],
        "updated_at": str(row["updated_at"]),
    }


def _news_payload(row: sqlite3.Row) -> dict:
    return {
        "content_type": "news",
        "id": str(row["id"]),
        "title": str(row["title"]),
        "content": str(row["content"]),
        "category_code": str(row["category_code"]),
        "view_count": int(row["view_count"]),
        "version": int(row["version"]),
        "published_at": row["published_at"],
        "updated_at": str(row["updated_at"]),
    }


def _course_payload(row: sqlite3.Row) -> dict:
    return {
        "content_type": "course",
        "id": int(row["id"]),
        "title": str(row["title"]),
        "direction": str(row["direction"]),
        "status": str(row["status"]),
        "teacher_id": row["teacher_id"],
        "teacher_name": str(row["teacher_name"] or ""),
        "version": int(row["version"]),
        "published_at": row["published_at"],
        "deleted_at": row["deleted_at"],
        "updated_at": str(row["updated_at"]),
    }


def _job_payload(row: sqlite3.Row) -> dict:
    return {
        "content_type": "job",
        "job_id": str(row["job_id"]),
        "title": str(row["title"]),
        "enterprise_id": int(row["enterprise_id"]),
        "review_status": str(row["review_status"]),
        "version": int(row["version"]),
        "published_at": row["published_at"],
        "deleted_at": row["deleted_at"],
        "updated_at": str(row["updated_at"]),
    }


def _video_payload(row: sqlite3.Row) -> dict:
    return {
        "content_type": "handcraft_video",
        "video_id": str(row["video_id"]),
        "craft_key": str(row["craft_key"]),
        "title": str(row["title"]),
        "review_status": str(row["review_status"]),
        "version": int(row["version"]),
        "published_at": row["published_at"],
        "deleted_at": row["deleted_at"],
        "updated_at": str(row["updated_at"]),
    }


def _comment_payload(row: sqlite3.Row) -> dict:
    return {
        "content_type": "comment",
        "comment_id": str(row["comment_id"]),
        "target_content_type": str(row["content_type"]),
        "target_content_id": str(row["content_id"]),
        "author_id": int(row["author_id"]),
        "body": str(row["body"]),
        "is_visible": bool(row["is_visible"]),
        "created_at": str(row["created_at"]),
        "updated_at": str(row["updated_at"]),
    }


# --- read surface ------------------------------------------------------------


def list_managed_content(content_type: str, filters: dict) -> list[dict]:
    normalized_type = _content_type(content_type)
    resolved = filters if isinstance(filters, dict) else {}
    db = get_db()
    if normalized_type == "policy":
        rows = db.execute(
            """
            SELECT * FROM government_policies
            ORDER BY published_at DESC, id ASC
            """
        ).fetchall()
        items = [_policy_payload(row) for row in rows]
    elif normalized_type == "news":
        rows = db.execute(
            """
            SELECT * FROM government_news
            ORDER BY published_at DESC, id ASC
            """
        ).fetchall()
        items = [_news_payload(row) for row in rows]
    elif normalized_type == "course":
        rows = db.execute(
            """
            SELECT * FROM courses
            WHERE deleted_at IS NULL
            ORDER BY updated_at DESC, id DESC
            """
        ).fetchall()
        items = [_course_payload(row) for row in rows]
    elif normalized_type == "job":
        rows = db.execute(
            """
            SELECT * FROM job_positions
            WHERE deleted_at IS NULL
            ORDER BY updated_at DESC, id DESC
            """
        ).fetchall()
        items = [_job_payload(row) for row in rows]
    elif normalized_type == "handcraft_video":
        # 05's `_active_video_payload` has no `content_type` key, so the list
        # projection would not match the get projection built from
        # `_video_payload`. The key is added here instead of in 05 because this
        # console owns the managed read surface; every provider field is kept.
        items = [
            {"content_type": "handcraft_video", **video}
            for video in list_active_teaching_videos()
        ]
    elif normalized_type == "comment":
        rows = db.execute(
            """
            SELECT * FROM content_comments
            ORDER BY created_at DESC, id DESC
            """
        ).fetchall()
        items = [_comment_payload(row) for row in rows]
    else:  # preset
        items = _list_preset_rows()
    return _apply_filters(items, resolved)


def _apply_filters(items: list[dict], filters: dict) -> list[dict]:
    status = filters.get("status")
    if status:
        items = [item for item in items if item.get("status") == status]
    review_status = filters.get("review_status")
    if review_status:
        items = [
            item
            for item in items
            if item.get("review_status") == review_status
        ]
    is_visible = filters.get("is_visible")
    if is_visible is not None:
        wanted = str(is_visible) in {"1", "true", "True"}
        items = [item for item in items if item.get("is_visible") is wanted]
    keyword = filters.get("keyword")
    if keyword:
        needle = str(keyword).strip().lower()
        items = [
            item
            for item in items
            if needle in str(item.get("title") or item.get("name") or "").lower()
        ]
    return items


def get_managed_content(content_type: str, content_id: str) -> dict | None:
    normalized_type = _content_type(content_type)
    db = get_db()
    if normalized_type == "policy":
        row = _policy_row(db, content_id)
        return _policy_payload(row) if row is not None else None
    if normalized_type == "news":
        row = _news_row(db, content_id)
        return _news_payload(row) if row is not None else None
    if normalized_type == "course":
        row = db.execute(
            "SELECT * FROM courses WHERE id = ? AND deleted_at IS NULL",
            (_parse_course_id(content_id),),
        ).fetchone()
        return _course_payload(row) if row is not None else None
    if normalized_type == "job":
        row = db.execute(
            """
            SELECT * FROM job_positions
            WHERE job_id = ? AND deleted_at IS NULL
            """,
            (content_id,),
        ).fetchone()
        return _job_payload(row) if row is not None else None
    if normalized_type == "handcraft_video":
        video = get_active_teaching_video(content_id)
        return _video_payload(_VideoRowAdapter(video)) if video else None
    if normalized_type == "comment":
        row = _comment_row(db, content_id)
        return _comment_payload(row) if row is not None else None
    return _get_preset(content_id)


class _VideoRowAdapter:
    """Adapt a provider video dict back into a row-like accessor."""

    def __init__(self, video: dict) -> None:
        self._video = video

    def __getitem__(self, key: str):
        return self._video[key]


def correct_managed_content(
    actor_id: int,
    content_type: str,
    content_id: str,
    expected_version: int,
    payload: dict,
) -> dict:
    normalized_type = _content_type(content_type)
    normalized_version = _expected_version(expected_version)
    data = payload if isinstance(payload, dict) else {}
    handler = _CORRECT_HANDLERS.get(normalized_type)
    if handler is None:
        raise _validation(
            "该内容类型不支持纠错",
            "content_correct_unsupported",
            content_type=normalized_type,
        )
    return handler(actor_id, content_id, normalized_version, data)


def unpublish_managed_content(
    actor_id: int,
    content_type: str,
    content_id: str,
    expected_version: int,
) -> dict:
    normalized_type = _content_type(content_type)
    normalized_version = _expected_version(expected_version)
    handler = _UNPUBLISH_HANDLERS.get(normalized_type)
    if handler is None:
        raise _validation(
            "该内容类型不支持下线",
            "content_unpublish_unsupported",
            content_type=normalized_type,
        )
    return handler(actor_id, content_id, normalized_version)


def delete_managed_content(
    actor_id: int,
    content_type: str,
    content_id: str,
    expected_version: int,
) -> dict:
    normalized_type = _content_type(content_type)
    normalized_version = _expected_version(expected_version)
    handler = _DELETE_HANDLERS[normalized_type]
    return handler(actor_id, content_id, normalized_version)


# --- policy ------------------------------------------------------------------


def _correct_policy(
    actor_id: int,
    policy_id: str,
    expected_version: int,
    payload: dict,
) -> dict:
    title = _required_text(payload.get("title"), "title", maximum=200)
    content = _required_text(payload.get("content"), "content", maximum=20000)
    db = get_db()
    _begin(db)
    try:
        before = _policy_row(db, policy_id)
        if before is None:
            raise _not_found("政策不存在", "policy_not_found", policy_id=policy_id)
        _require_version(
            int(before["version"]),
            expected_version,
            code="policy_version_conflict",
            policy_id=policy_id,
        )
        now = platform_now_iso()
        # Correction edits only the copy and never re-emits a publication
        # event nor touches status, so a corrected active policy stays active.
        cursor = db.execute(
            """
            UPDATE government_policies
            SET title = ?, content = ?, version = version + 1, updated_at = ?
            WHERE id = ? AND version = ?
            """,
            (title, content, now, policy_id, expected_version),
        )
        if cursor.rowcount != 1:
            raise _conflict(
                "政策已被其他管理员修改",
                "policy_version_conflict",
                policy_id=policy_id,
            )
        after = _policy_row(db, policy_id)
        record_admin_audit(
            db,
            actor_id=actor_id,
            action="correct_policy",
            target_type="policy",
            target_id=policy_id,
            before=_policy_payload(before),
            after=_policy_payload(after),
            result="success",
        )
    except Exception:
        db.rollback()
        raise
    db.commit()
    return _policy_payload(after)


def _unpublish_policy(
    actor_id: int,
    policy_id: str,
    expected_version: int,
) -> dict:
    db = get_db()
    _begin(db)
    try:
        before = _policy_row(db, policy_id)
        if before is None:
            raise _not_found("政策不存在", "policy_not_found", policy_id=policy_id)
        if str(before["status"]) != "active":
            raise _conflict(
                "政策当前状态不允许下线",
                "policy_state_conflict",
                policy_id=policy_id,
                status=str(before["status"]),
            )
        _require_version(
            int(before["version"]),
            expected_version,
            code="policy_version_conflict",
            policy_id=policy_id,
        )
        now = platform_now_iso()
        cursor = db.execute(
            """
            UPDATE government_policies
            SET status = 'unpublished', version = version + 1, updated_at = ?
            WHERE id = ? AND version = ? AND status = 'active'
            """,
            (now, policy_id, expected_version),
        )
        if cursor.rowcount != 1:
            raise _conflict(
                "政策已被其他管理员修改",
                "policy_version_conflict",
                policy_id=policy_id,
            )
        after = _policy_row(db, policy_id)
        record_admin_audit(
            db,
            actor_id=actor_id,
            action="unpublish_policy",
            target_type="policy",
            target_id=policy_id,
            before=_policy_payload(before),
            after=_policy_payload(after),
            result="success",
        )
    except Exception:
        db.rollback()
        raise
    db.commit()
    return _policy_payload(after)


def _delete_policy(
    actor_id: int,
    policy_id: str,
    expected_version: int,
) -> dict:
    db = get_db()
    _begin(db)
    try:
        before = _policy_row(db, policy_id)
        if before is None:
            raise _not_found("政策不存在", "policy_not_found", policy_id=policy_id)
        _require_version(
            int(before["version"]),
            expected_version,
            code="policy_version_conflict",
            policy_id=policy_id,
        )
        cursor = db.execute(
            "DELETE FROM government_policies WHERE id = ? AND version = ?",
            (policy_id, expected_version),
        )
        if cursor.rowcount != 1:
            raise _conflict(
                "政策已被其他管理员修改",
                "policy_version_conflict",
                policy_id=policy_id,
            )
        db.execute(
            """
            DELETE FROM government_view_events
            WHERE content_type = 'policy' AND content_id = ?
            """,
            (policy_id,),
        )
        record_admin_audit(
            db,
            actor_id=actor_id,
            action="delete_policy",
            target_type="policy",
            target_id=policy_id,
            before=_policy_payload(before),
            after=None,
            result="success",
        )
    except Exception:
        db.rollback()
        raise
    db.commit()
    return {"content_type": "policy", "id": policy_id, "deleted": True}


# --- news --------------------------------------------------------------------


def _correct_news(
    actor_id: int,
    news_id: str,
    expected_version: int,
    payload: dict,
) -> dict:
    title = _required_text(payload.get("title"), "title", maximum=200)
    content = _required_text(payload.get("content"), "content", maximum=20000)
    db = get_db()
    _begin(db)
    try:
        before = _news_row(db, news_id)
        if before is None:
            raise _not_found("新闻不存在", "news_not_found", news_id=news_id)
        _require_version(
            int(before["version"]),
            expected_version,
            code="news_version_conflict",
            news_id=news_id,
        )
        now = platform_now_iso()
        cursor = db.execute(
            """
            UPDATE government_news
            SET title = ?, content = ?, version = version + 1, updated_at = ?
            WHERE id = ? AND version = ?
            """,
            (title, content, now, news_id, expected_version),
        )
        if cursor.rowcount != 1:
            raise _conflict(
                "新闻已被其他管理员修改",
                "news_version_conflict",
                news_id=news_id,
            )
        after = _news_row(db, news_id)
        record_admin_audit(
            db,
            actor_id=actor_id,
            action="correct_news",
            target_type="news",
            target_id=news_id,
            before=_news_payload(before),
            after=_news_payload(after),
            result="success",
        )
    except Exception:
        db.rollback()
        raise
    db.commit()
    return _news_payload(after)


def _delete_news(
    actor_id: int,
    news_id: str,
    expected_version: int,
) -> dict:
    db = get_db()
    _begin(db)
    try:
        before = _news_row(db, news_id)
        if before is None:
            raise _not_found("新闻不存在", "news_not_found", news_id=news_id)
        _require_version(
            int(before["version"]),
            expected_version,
            code="news_version_conflict",
            news_id=news_id,
        )
        cursor = db.execute(
            "DELETE FROM government_news WHERE id = ? AND version = ?",
            (news_id, expected_version),
        )
        if cursor.rowcount != 1:
            raise _conflict(
                "新闻已被其他管理员修改",
                "news_version_conflict",
                news_id=news_id,
            )
        db.execute(
            """
            DELETE FROM government_view_events
            WHERE content_type = 'news' AND content_id = ?
            """,
            (news_id,),
        )
        record_admin_audit(
            db,
            actor_id=actor_id,
            action="delete_news",
            target_type="news",
            target_id=news_id,
            before=_news_payload(before),
            after=None,
            result="success",
        )
    except Exception:
        db.rollback()
        raise
    db.commit()
    return {"content_type": "news", "id": news_id, "deleted": True}


# --- course ------------------------------------------------------------------


def _correct_course(
    actor_id: int,
    content_id: str,
    expected_version: int,
    payload: dict,
) -> dict:
    course_id = _parse_course_id(content_id)
    title = _required_text(payload.get("title"), "title", maximum=200)
    summary = _required_text(payload.get("summary"), "summary", maximum=2000)
    db = get_db()
    _begin(db)
    try:
        before = _course_row(db, course_id)
        if before is None or before["deleted_at"] is not None:
            raise _not_found(
                "课程不存在", "course_not_found", course_id=course_id
            )
        _require_version(
            int(before["version"]),
            expected_version,
            code="course_version_conflict",
            course_id=course_id,
        )
        now = platform_now_iso()
        cursor = db.execute(
            """
            UPDATE courses
            SET title = ?, summary = ?, version = version + 1, updated_at = ?
            WHERE id = ? AND version = ? AND deleted_at IS NULL
            """,
            (title, summary, now, course_id, expected_version),
        )
        if cursor.rowcount != 1:
            raise _conflict(
                "课程已被其他管理员修改",
                "course_version_conflict",
                course_id=course_id,
            )
        after = _course_row(db, course_id)
        record_admin_audit(
            db,
            actor_id=actor_id,
            action="correct_course",
            target_type="course",
            target_id=str(course_id),
            before=_course_payload(before),
            after=_course_payload(after),
            result="success",
        )
    except Exception:
        db.rollback()
        raise
    db.commit()
    return _course_payload(after)


def _unpublish_course(
    actor_id: int,
    content_id: str,
    expected_version: int,
) -> dict:
    course_id = _parse_course_id(content_id)
    db = get_db()
    _begin(db)
    try:
        before = _course_row(db, course_id)
        if before is None or before["deleted_at"] is not None:
            raise _not_found(
                "课程不存在", "course_not_found", course_id=course_id
            )
        if str(before["status"]) != "published":
            raise _conflict(
                "课程当前状态不允许下线",
                "course_state_conflict",
                course_id=course_id,
                status=str(before["status"]),
            )
        _require_version(
            int(before["version"]),
            expected_version,
            code="course_version_conflict",
            course_id=course_id,
        )
        now = platform_now_iso()
        cursor = db.execute(
            """
            UPDATE courses
            SET status = 'offline', version = version + 1, updated_at = ?
            WHERE id = ? AND version = ? AND status = 'published'
              AND deleted_at IS NULL
            """,
            (now, course_id, expected_version),
        )
        if cursor.rowcount != 1:
            raise _conflict(
                "课程已被其他管理员修改",
                "course_version_conflict",
                course_id=course_id,
            )
        after = _course_row(db, course_id)
        record_admin_audit(
            db,
            actor_id=actor_id,
            action="unpublish_course",
            target_type="course",
            target_id=str(course_id),
            before=_course_payload(before),
            after=_course_payload(after),
            result="success",
        )
    except Exception:
        db.rollback()
        raise
    db.commit()
    return _course_payload(after)


def _tombstone_course(
    actor_id: int,
    content_id: str,
    expected_version: int,
) -> dict:
    course_id = _parse_course_id(content_id)
    db = get_db()
    _begin(db)
    try:
        before = _course_row(db, course_id)
        if before is None or before["deleted_at"] is not None:
            raise _not_found(
                "课程不存在", "course_not_found", course_id=course_id
            )
        _require_version(
            int(before["version"]),
            expected_version,
            code="course_version_conflict",
            course_id=course_id,
        )
        now = platform_now_iso()
        # Soft delete: the row (and its learning-progress children) survives;
        # `status = 'offline'` keeps the unfilterable student course provider
        # from serving a tombstoned course, and `deleted_at` drops it from the
        # admin queue, dashboard and this console's own reads.
        cursor = db.execute(
            """
            UPDATE courses
            SET status = 'offline', deleted_at = ?, version = version + 1,
                updated_at = ?
            WHERE id = ? AND version = ? AND deleted_at IS NULL
            """,
            (now, now, course_id, expected_version),
        )
        if cursor.rowcount != 1:
            raise _conflict(
                "课程已被其他管理员修改",
                "course_version_conflict",
                course_id=course_id,
            )
        # Drop the review projection so the deleted course cannot leak
        # through `content_review_records` in the dashboard's direct pending
        # count, which this task cannot rewrite.
        db.execute(
            """
            DELETE FROM content_review_records
            WHERE content_type = 'course_video' AND content_id = ?
            """,
            (str(course_id),),
        )
        after = _course_row(db, course_id)
        record_admin_audit(
            db,
            actor_id=actor_id,
            action="delete_course",
            target_type="course",
            target_id=str(course_id),
            before=_course_payload(before),
            after=_course_payload(after),
            result="success",
        )
    except Exception:
        db.rollback()
        raise
    db.commit()
    return _course_payload(after)


# --- job ---------------------------------------------------------------------


def _correct_job(
    actor_id: int,
    job_id: str,
    expected_version: int,
    payload: dict,
) -> dict:
    title = _required_text(payload.get("title"), "title", maximum=200)
    description = _required_text(
        payload.get("description"), "description", maximum=8000
    )
    db = get_db()
    _begin(db)
    try:
        before = _job_row(db, job_id)
        if before is None or before["deleted_at"] is not None:
            raise _not_found("职位不存在", "job_not_found", job_id=job_id)
        _require_version(
            int(before["version"]),
            expected_version,
            code="job_version_conflict",
            job_id=job_id,
        )
        now = platform_now_iso()
        cursor = db.execute(
            """
            UPDATE job_positions
            SET title = ?, description = ?, version = version + 1,
                updated_at = ?
            WHERE job_id = ? AND version = ? AND deleted_at IS NULL
            """,
            (title, description, now, job_id, expected_version),
        )
        if cursor.rowcount != 1:
            raise _conflict(
                "职位已被其他管理员修改",
                "job_version_conflict",
                job_id=job_id,
            )
        after = _job_row(db, job_id)
        record_admin_audit(
            db,
            actor_id=actor_id,
            action="correct_job",
            target_type="job",
            target_id=job_id,
            before=_job_payload(before),
            after=_job_payload(after),
            result="success",
        )
    except Exception:
        db.rollback()
        raise
    db.commit()
    return _job_payload(after)


def _unpublish_job(
    actor_id: int,
    job_id: str,
    expected_version: int,
) -> dict:
    db = get_db()
    _begin(db)
    try:
        before = _job_row(db, job_id)
        if before is None or before["deleted_at"] is not None:
            raise _not_found("职位不存在", "job_not_found", job_id=job_id)
        if str(before["review_status"]) != "approved":
            raise _conflict(
                "职位当前状态不允许下线",
                "job_state_conflict",
                job_id=job_id,
                review_status=str(before["review_status"]),
            )
        _require_version(
            int(before["version"]),
            expected_version,
            code="job_version_conflict",
            job_id=job_id,
        )
        now = platform_now_iso()
        cursor = db.execute(
            """
            UPDATE job_positions
            SET review_status = 'pending', published_at = NULL,
                version = version + 1, updated_at = ?
            WHERE job_id = ? AND version = ? AND deleted_at IS NULL
            """,
            (now, job_id, expected_version),
        )
        if cursor.rowcount != 1:
            raise _conflict(
                "职位已被其他管理员修改",
                "job_version_conflict",
                job_id=job_id,
            )
        after = _job_row(db, job_id)
        record_admin_audit(
            db,
            actor_id=actor_id,
            action="unpublish_job",
            target_type="job",
            target_id=job_id,
            before=_job_payload(before),
            after=_job_payload(after),
            result="success",
        )
    except Exception:
        db.rollback()
        raise
    db.commit()
    return _job_payload(after)


def _tombstone_job(
    actor_id: int,
    job_id: str,
    expected_version: int,
) -> dict:
    db = get_db()
    _begin(db)
    try:
        before = _job_row(db, job_id)
        if before is None or before["deleted_at"] is not None:
            raise _not_found("职位不存在", "job_not_found", job_id=job_id)
        _require_version(
            int(before["version"]),
            expected_version,
            code="job_version_conflict",
            job_id=job_id,
        )
        now = platform_now_iso()
        cursor = db.execute(
            """
            UPDATE job_positions
            SET deleted_at = ?, version = version + 1, updated_at = ?
            WHERE job_id = ? AND version = ? AND deleted_at IS NULL
            """,
            (now, now, job_id, expected_version),
        )
        if cursor.rowcount != 1:
            raise _conflict(
                "职位已被其他管理员修改",
                "job_version_conflict",
                job_id=job_id,
            )
        db.execute(
            """
            DELETE FROM content_review_records
            WHERE content_type = 'job_position' AND content_id = ?
            """,
            (job_id,),
        )
        after = _job_row(db, job_id)
        record_admin_audit(
            db,
            actor_id=actor_id,
            action="delete_job",
            target_type="job",
            target_id=job_id,
            before=_job_payload(before),
            after=_job_payload(after),
            result="success",
        )
    except Exception:
        db.rollback()
        raise
    db.commit()
    return _job_payload(after)


# --- handcraft video ---------------------------------------------------------


def _correct_video(
    actor_id: int,
    video_id: str,
    expected_version: int,
    payload: dict,
) -> dict:
    title = _required_text(payload.get("title"), "title", maximum=200)
    db = get_db()
    _begin(db)
    try:
        before = _video_row(db, video_id)
        if before is None or before["deleted_at"] is not None:
            raise _not_found(
                "视频不存在", "video_not_found", video_id=video_id
            )
        _require_version(
            int(before["version"]),
            expected_version,
            code="video_version_conflict",
            video_id=video_id,
        )
        now = platform_now_iso()
        cursor = db.execute(
            """
            UPDATE heritage_videos
            SET title = ?, version = version + 1, updated_at = ?
            WHERE video_id = ? AND version = ? AND deleted_at IS NULL
            """,
            (title, now, video_id, expected_version),
        )
        if cursor.rowcount != 1:
            raise _conflict(
                "视频已被其他管理员修改",
                "video_version_conflict",
                video_id=video_id,
            )
        after = _video_row(db, video_id)
        record_admin_audit(
            db,
            actor_id=actor_id,
            action="correct_handcraft_video",
            target_type="handcraft_video",
            target_id=video_id,
            before=_video_payload(before),
            after=_video_payload(after),
            result="success",
        )
    except Exception:
        db.rollback()
        raise
    db.commit()
    return _video_payload(after)


def _unpublish_video(
    actor_id: int,
    video_id: str,
    expected_version: int,
) -> dict:
    db = get_db()
    _begin(db)
    try:
        before = _video_row(db, video_id)
        if before is None or before["deleted_at"] is not None:
            raise _not_found(
                "视频不存在", "video_not_found", video_id=video_id
            )
        if str(before["review_status"]) != "approved":
            raise _conflict(
                "视频当前状态不允许下线",
                "video_state_conflict",
                video_id=video_id,
                review_status=str(before["review_status"]),
            )
        _require_version(
            int(before["version"]),
            expected_version,
            code="video_version_conflict",
            video_id=video_id,
        )
        now = platform_now_iso()
        cursor = db.execute(
            """
            UPDATE heritage_videos
            SET review_status = 'pending', published_at = NULL,
                version = version + 1, updated_at = ?
            WHERE video_id = ? AND version = ? AND deleted_at IS NULL
            """,
            (now, video_id, expected_version),
        )
        if cursor.rowcount != 1:
            raise _conflict(
                "视频已被其他管理员修改",
                "video_version_conflict",
                video_id=video_id,
            )
        after = _video_row(db, video_id)
        record_admin_audit(
            db,
            actor_id=actor_id,
            action="unpublish_handcraft_video",
            target_type="handcraft_video",
            target_id=video_id,
            before=_video_payload(before),
            after=_video_payload(after),
            result="success",
        )
    except Exception:
        db.rollback()
        raise
    db.commit()
    return _video_payload(after)


def _tombstone_video(
    actor_id: int,
    video_id: str,
    expected_version: int,
) -> dict:
    db = get_db()
    _begin(db)
    try:
        before = _video_row(db, video_id)
        if before is None or before["deleted_at"] is not None:
            raise _not_found(
                "视频不存在", "video_not_found", video_id=video_id
            )
        _require_version(
            int(before["version"]),
            expected_version,
            code="video_version_conflict",
            video_id=video_id,
        )
        # Soft delete: the row survives for history, but 05's student read
        # path (`list_student_videos`, `get_video_playback`) filters on
        # `review_status = 'approved'` alone and never looks at `deleted_at`,
        # so a tombstone that only set `deleted_at` would still be listed and
        # played for learners. Moving the row to the `offline` enum and
        # clearing `published_at` closes that hole, while `deleted_at` drops it
        # from the admin list, queue and dashboard.
        now = platform_now_iso()
        cursor = db.execute(
            """
            UPDATE heritage_videos
            SET review_status = 'offline', published_at = NULL,
                deleted_at = ?, version = version + 1, updated_at = ?
            WHERE video_id = ? AND version = ? AND deleted_at IS NULL
            """,
            (now, now, video_id, expected_version),
        )
        if cursor.rowcount != 1:
            raise _conflict(
                "视频已被其他管理员修改",
                "video_version_conflict",
                video_id=video_id,
            )
        db.execute(
            """
            DELETE FROM content_review_records
            WHERE content_type = 'handcraft_teaching_video' AND content_id = ?
            """,
            (video_id,),
        )
        after = _video_row(db, video_id)
        record_admin_audit(
            db,
            actor_id=actor_id,
            action="delete_handcraft_video",
            target_type="handcraft_video",
            target_id=video_id,
            before=_video_payload(before),
            after=_video_payload(after),
            result="success",
        )
    except Exception:
        db.rollback()
        raise
    db.commit()
    return _video_payload(after)


# --- comment -----------------------------------------------------------------


def _hide_comment(
    actor_id: int,
    comment_id: str,
    expected_version: int,
) -> dict:
    db = get_db()
    row = _comment_row(db, comment_id)
    if row is None:
        raise _not_found(
            "评论不存在", "comment_not_found", comment_id=comment_id
        )
    if not bool(row["is_visible"]):
        raise _conflict(
            "评论已被隐藏",
            "comment_already_hidden",
            comment_id=comment_id,
        )
    from app.admin_console.moderation import delete_comment

    result = delete_comment(actor_id, comment_id)
    return {
        "content_type": "comment",
        "comment_id": comment_id,
        "is_visible": False,
        "deleted": True,
        "changed": bool(result.get("changed", True)),
    }


# --- preset (six managed families) -------------------------------------------


PRESET_CATEGORIES = frozenset(
    {
        "agri_products",
        "agri_calendar",
        "pest_knowledge",
        "handcraft_crafts",
        "success_cases",
        "assistant_knowledge",
    }
)

# A fixed order keeps the union projection stable for the console.
PRESET_CATEGORY_ORDER = (
    "agri_products",
    "agri_calendar",
    "pest_knowledge",
    "handcraft_crafts",
    "success_cases",
    "assistant_knowledge",
)

# Every family spells its stable key differently, so the union projection and
# the addressing of one row need to know each spelling.
PRESET_ID_FIELDS = {
    "agri_products": "product_key",
    "agri_calendar": "item_id",
    "pest_knowledge": "item_id",
    "handcraft_crafts": "craft_key",
    # A success case keeps 06's frozen read shape, which spells its stable id
    # `id` instead of `case_id`.
    "success_cases": "id",
    "assistant_knowledge": "knowledge_id",
}

# `handcraft_crafts` is the family this console started from, and it keeps its
# bare `craft_key`: the craft-only projection, its routes and its tests already
# address a craft that way, so prefixing it would break them for no gain. Every
# other family encodes `<family>:<stable_id>`, which keeps one mixed list
# addressable while resolving back to exactly one family on the way in.
PRESET_ID_SEPARATOR = ":"
PRESET_BARE_CATEGORY = "handcraft_crafts"


def _preset_family_apis() -> dict[str, tuple]:
    """Map each preset family to its list and logical-disable entry points.

    Both halves stay in `presets.py`: the console reads through the same
    projections the consumer modules read, and a delete still delegates to the
    Task 21/22 disable that owns the optimistic lock, the stable-id retention
    and the before/after audit row.
    """
    from app.admin_console.presets import (
        disable_agri_calendar_preset,
        disable_agri_product_preset,
        disable_case_preset,
        disable_craft_preset,
        disable_knowledge_preset,
        disable_pest_knowledge_preset,
        list_agri_calendar_presets,
        list_agri_product_presets,
        list_case_presets,
        list_craft_presets,
        list_knowledge_presets,
        list_pest_knowledge_presets,
    )

    return {
        "agri_products": (
            list_agri_product_presets,
            disable_agri_product_preset,
        ),
        "agri_calendar": (
            list_agri_calendar_presets,
            disable_agri_calendar_preset,
        ),
        "pest_knowledge": (
            list_pest_knowledge_presets,
            disable_pest_knowledge_preset,
        ),
        "handcraft_crafts": (list_craft_presets, disable_craft_preset),
        "success_cases": (list_case_presets, disable_case_preset),
        "assistant_knowledge": (
            list_knowledge_presets,
            disable_knowledge_preset,
        ),
    }


def _encode_preset_id(category: str, stable_id: str) -> str:
    if category == PRESET_BARE_CATEGORY:
        return stable_id
    return f"{category}{PRESET_ID_SEPARATOR}{stable_id}"


def _decode_preset_id(content_id: object) -> tuple[str, str]:
    """Split a preset content id into its family and bare stable id."""
    raw = str(content_id or "").strip()
    if PRESET_ID_SEPARATOR not in raw:
        # No prefix means the craft family, which never carried one.
        return PRESET_BARE_CATEGORY, raw
    category, _, stable_id = raw.partition(PRESET_ID_SEPARATOR)
    if category in PRESET_CATEGORIES and stable_id:
        return category, stable_id
    raise _not_found("预置内容不存在", "preset_not_found", content_id=raw)


def _preset_label(entry: dict) -> str:
    for field in ("name", "title", "pest_name"):
        value = entry.get(field)
        if value:
            return str(value)
    # A calendar row has no label of its own: it is one month of one product.
    product_key = entry.get("product_key")
    if product_key is not None and entry.get("month") is not None:
        return f"{product_key} {entry['month']}月"
    return ""


def _preset_row(category: str, entry: dict) -> dict:
    stable_id = str(entry[PRESET_ID_FIELDS[category]])
    row = {
        "content_type": "preset",
        "preset_category": category,
        "id": _encode_preset_id(category, stable_id),
        "stable_id": stable_id,
        # Each family spells its label differently, so the union projection
        # normalizes it to `name` for the console table and the keyword filter.
        "name": _preset_label(entry),
        "sort_order": int(entry["sort_order"]),
        "is_enabled": bool(entry["is_enabled"]),
        "version": int(entry["version"]),
        "updated_at": str(entry["updated_at"]),
    }
    if category == PRESET_BARE_CATEGORY:
        row["craft_key"] = stable_id
    return row


def _list_preset_rows() -> list[dict]:
    apis = _preset_family_apis()
    rows: list[dict] = []
    for category in PRESET_CATEGORY_ORDER:
        entries = apis[category][0]()
        rows.extend(_preset_row(category, entry) for entry in entries)
    return rows


def _preset_entry(category: str, stable_id: str) -> dict | None:
    entries = _preset_family_apis()[category][0]()
    field = PRESET_ID_FIELDS[category]
    return next(
        (entry for entry in entries if str(entry[field]) == stable_id),
        None,
    )


def _get_preset(content_id: object) -> dict | None:
    """Read one preset row of any family, disabled rows included."""
    category, stable_id = _decode_preset_id(content_id)
    entry = _preset_entry(category, stable_id)
    if entry is None:
        return None
    # The union keys come first so a family field can never shadow them; the
    # family entry follows so the detail projection keeps every domain field.
    return {**_preset_row(category, entry), **entry}


def _disable_preset(
    actor_id: int,
    content_id: str,
    expected_version: int,
) -> dict:
    category, stable_id = _decode_preset_id(content_id)
    disabler = _preset_family_apis()[category][1]
    # Delegates to the family's logical disable, which owns the optimistic
    # lock, the stable-id retention and the before/after audit row.
    return disabler(actor_id, stable_id, expected_version)


_CORRECT_HANDLERS = {
    "policy": _correct_policy,
    "news": _correct_news,
    "course": _correct_course,
    "job": _correct_job,
    "handcraft_video": _correct_video,
}

_UNPUBLISH_HANDLERS = {
    "policy": _unpublish_policy,
    "course": _unpublish_course,
    "job": _unpublish_job,
    "handcraft_video": _unpublish_video,
    "preset": _disable_preset,
}

_DELETE_HANDLERS = {
    "policy": _delete_policy,
    "news": _delete_news,
    "course": _tombstone_course,
    "job": _tombstone_job,
    "handcraft_video": _tombstone_video,
    "comment": _hide_comment,
    "preset": _disable_preset,
}


__all__ = [
    "CONTENT_TYPES",
    "correct_managed_content",
    "delete_managed_content",
    "get_managed_content",
    "list_managed_content",
    "unpublish_managed_content",
]
