"""Comment patrol listing and silent deletion for 011.

011's moderation surface reads the shared `content_comments` table that 08
owns. The only write is `is_visible = 0`, which is exactly the predicate
08's `list_content_comments` and `list_teacher_comments` already filter
on, so a hidden comment leaves the student and teacher read paths on their
very next request. That is what makes the deletion silent.

Silence is a hard requirement (FR-072, SC-010): the author of a deleted
comment is never told. This module therefore never imports anything from
`app.messaging`, writes no outbox row, and emits no notification event.

The same silence covers the two queues that sit on top of that deletion:
resolving a `comment_reports` row and handling a `feedback_records` row
both stay inside the console. A reporter is never told what happened to
their report and a submitter is never told their feedback was read.
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from app.admin_console.audit import record_admin_audit
from app.admin_console.errors import (
    ProviderNotFoundError,
    ProviderValidationError,
)
from app.admin_console.time_utils import platform_now_iso
from app.db import get_db


# The CHECK constraint on `content_comments.content_type`; a filter value
# outside this set can never match a row, so it is refused instead of
# silently returning an empty list.
COMMENT_CONTENT_TYPES = frozenset(
    {"course_video", "handcraft_teaching_video"}
)
COMMENT_CONTENT_TYPE_VALUES = tuple(sorted(COMMENT_CONTENT_TYPES))
VISIBLE_FLAG_VALUES = {"1": True, "0": False, "true": True, "false": False}
VISIBLE_FLAG_ALLOWED = ("1", "0", "true", "false")
REPORT_STATUSES = frozenset({"pending", "confirmed", "rejected"})
REPORT_STATUS_VALUES = tuple(sorted(REPORT_STATUSES))
FEEDBACK_STATUSES = frozenset({"pending", "processed", "closed"})
FEEDBACK_STATUS_VALUES = tuple(sorted(FEEDBACK_STATUSES))
REPORT_ID_MAX_LENGTH = 128
FEEDBACK_ID_MAX_LENGTH = 128
REASON_MAX_LENGTH = 500
BODY_MAX_LENGTH = 2000
IDEMPOTENCY_KEY_MAX_LENGTH = 128
RESULT_MAX_LENGTH = 500
COMMENT_ID_MAX_LENGTH = 128
CONTENT_ID_MAX_LENGTH = 128
KEYWORD_MAX_LENGTH = 64
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200

PLATFORM_TIMEZONE = ZoneInfo("Asia/Shanghai")
TIME_FLOOR = datetime.min.replace(tzinfo=PLATFORM_TIMEZONE)
# SQLite binds a Python int as an 8-byte signed INTEGER and raises
# OverflowError outside that range, which a query-string filter could
# otherwise turn into a 500.
SQLITE_MAX_INTEGER = 2**63 - 1

# One code for every rejected filter value, so the console can tell a bad
# query string from a bad body without branching on the message text.
_FILTER_INVALID = "moderation_filter_invalid"

MODERATION_COLUMNS = """
    c.comment_id,
    c.content_type,
    c.content_id,
    c.author_id,
    c.parent_comment_id,
    c.body,
    c.is_teacher_reply,
    c.is_visible,
    c.created_at,
    c.updated_at,
    u.username AS author_username,
    u.name AS author_name
"""
# Only the two display columns of `users` are joined: a patrolling admin
# needs to recognise the author, and nothing else on that row belongs in a
# moderation queue.
MODERATION_JOINS = """
    FROM content_comments c
    LEFT JOIN users u ON u.id = c.author_id
"""
REPORT_COLUMNS = """
    r.report_id,
    r.comment_id,
    r.reporter_id,
    r.reason,
    r.status,
    r.resolver_id,
    r.result,
    r.created_at,
    r.updated_at,
    r.resolved_at,
    ru.username AS reporter_username,
    ru.name AS reporter_name,
    su.username AS resolver_username,
    su.name AS resolver_name,
    c.is_visible AS comment_is_visible
"""
# Both `users` joins are display-only: the queue has to name who reported
# the comment and who resolved the report, and nothing else on either row
# belongs in a moderation queue. `content_comments` is joined for the same
# reason `MODERATION_JOINS` is, so a patrolling admin can see whether the
# reported comment is still in the read paths.
REPORT_JOINS = """
    FROM comment_reports r
    LEFT JOIN users ru ON ru.id = r.reporter_id
    LEFT JOIN users su ON su.id = r.resolver_id
    LEFT JOIN content_comments c ON c.comment_id = r.comment_id
"""
FEEDBACK_COLUMNS = """
    f.feedback_id,
    f.submitter_id,
    f.body,
    f.status,
    f.idempotency_key,
    f.handler_id,
    f.result,
    f.created_at,
    f.updated_at,
    fu.username AS submitter_username,
    fu.name AS submitter_name,
    hu.username AS handler_username,
    hu.name AS handler_name
"""
FEEDBACK_JOINS = """
    FROM feedback_records f
    LEFT JOIN users fu ON fu.id = f.submitter_id
    LEFT JOIN users hu ON hu.id = f.handler_id
"""


def _fetch_all(sql: str, parameters: tuple = ()) -> list[sqlite3.Row]:
    return get_db().execute(sql, parameters).fetchall()


def _fetch_one(sql: str, parameters: tuple = ()) -> sqlite3.Row | None:
    return get_db().execute(sql, parameters).fetchone()


def _required_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _validation(
    message: str,
    *,
    code: str = "moderation_validation_failed",
    **details,
) -> ProviderValidationError:
    return ProviderValidationError(message, code=code, details=details)


def _not_found(comment_id: str) -> ProviderNotFoundError:
    return ProviderNotFoundError(
        "评论不存在",
        code="comment_not_found",
        details={"comment_id": comment_id},
    )


def _bounded_text(
    value: object,
    *,
    field: str,
    maximum: int,
    code: str = _FILTER_INVALID,
) -> str:
    normalized = _required_text(value)
    if normalized is None:
        raise _validation(
            f"{field} 不能为空",
            code=code,
            field=field,
        )
    if len(normalized) > maximum:
        raise _validation(
            f"{field} 长度不能超过 {maximum} 个字符",
            code=code,
            field=field,
            max_length=maximum,
        )
    return normalized


def _positive_integer(value: object, *, field: str) -> int:
    if isinstance(value, bool):
        raise _validation(f"{field} 必须是正整数", code=_FILTER_INVALID, field=field)
    if isinstance(value, int):
        number = value
    elif isinstance(value, str) and value.strip().isdigit():
        number = int(value.strip())
    else:
        raise _validation(f"{field} 必须是正整数", code=_FILTER_INVALID, field=field)
    # Every INTEGER filter (`author_id`, `reporter_id`, `submitter_id`) is
    # bound straight into SQLite, which rejects anything outside the signed
    # 64-bit range with an OverflowError rather than a validation error.
    if number > SQLITE_MAX_INTEGER:
        raise _validation(
            f"{field} 超出允许范围",
            code=_FILTER_INVALID,
            field=field,
            maximum=SQLITE_MAX_INTEGER,
        )
    if number <= 0:
        raise _validation(f"{field} 必须是正整数", code=_FILTER_INVALID, field=field)
    return number


def _non_negative_integer(value: object, *, field: str) -> int:
    if isinstance(value, bool):
        raise _validation(
            f"{field} 必须是非负整数",
            code=_FILTER_INVALID,
            field=field,
        )
    if isinstance(value, int):
        number = value
    elif isinstance(value, str) and value.strip().isdigit():
        number = int(value.strip())
    else:
        raise _validation(
            f"{field} 必须是非负整数",
            code=_FILTER_INVALID,
            field=field,
        )
    if number < 0:
        raise _validation(
            f"{field} 必须是非负整数",
            code=_FILTER_INVALID,
            field=field,
        )
    return number


def _visible_flag(value: object, *, field: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        text = str(value)
    elif isinstance(value, str):
        text = value.strip().lower()
    else:
        text = ""
    if text not in VISIBLE_FLAG_VALUES:
        raise _validation(
            "可见状态筛选值不正确",
            code="moderation_filter_invalid",
            field=field,
            value=value,
            allowed=list(VISIBLE_FLAG_ALLOWED),
        )
    return VISIBLE_FLAG_VALUES[text]


def _filter_text(filters: dict, field: str) -> str | None:
    value = filters.get(field)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise _validation(
            "筛选条件格式不正确",
            code="moderation_filter_invalid",
            field=field,
        )
    normalized = str(value).strip()
    return normalized or None


def _timestamp_boundary(value: object, *, field: str) -> datetime:
    normalized = _required_text(value)
    if normalized is None:
        raise _validation(f"{field} 不能为空", code=_FILTER_INVALID, field=field)
    try:
        parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except ValueError as error:
        raise _validation(
            f"{field} 必须是带时区的 ISO 8601 时间",
            code=_FILTER_INVALID,
            field=field,
        ) from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise _validation(f"{field} 必须带时区", code=_FILTER_INVALID, field=field)
    return parsed.astimezone(PLATFORM_TIMEZONE)


def _parse_stored_timestamp(value: object) -> datetime | None:
    """Parse a stored stamp, treating a naive one as Shanghai time.

    08 writes Shanghai stamps, but a row written by another path can carry
    a UTC `Z` offset. Sorting on the raw text would interleave the two, so
    every ordering and range decision goes through this parser instead.
    """
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value).strip()
        if not text:
            return None
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=PLATFORM_TIMEZONE)
    return parsed


def _sort_time(value: object) -> datetime:
    return _parse_stored_timestamp(value) or TIME_FLOOR


def _begin_exclusive(db: sqlite3.Connection) -> None:
    """Take the write lock before the row that guards the write is read.

    `load_session` runs a `DELETE FROM sessions WHERE expires_at <= ?` that
    implicitly opens a deferred transaction holding no write lock, and
    `require_admin_session` calls it for every admin request. A deferred
    transaction does not serialize writers, so two admins could both pass
    the visibility check and then deadlock on commit. Committing the
    pending work and opening `BEGIN IMMEDIATE` is what actually serializes
    them, and it is the same helper `rewards` and `system_announcements`
    define for themselves.
    """
    if db.in_transaction:
        db.commit()
    db.execute("BEGIN IMMEDIATE")


def _comment_filters(filters: object) -> dict:
    if not isinstance(filters, dict):
        raise _validation(
            "筛选条件格式不正确",
            code=_FILTER_INVALID,
            field="filters",
        )
    resolved: dict = {}

    content_type = _filter_text(filters, "content_type")
    if content_type is not None:
        if content_type not in COMMENT_CONTENT_TYPES:
            raise _validation(
                "内容类型筛选值不正确",
                code=_FILTER_INVALID,
                field="content_type",
                value=content_type,
                allowed=list(COMMENT_CONTENT_TYPE_VALUES),
            )
        resolved["content_type"] = content_type

    content_id = _filter_text(filters, "content_id")
    if content_id is not None:
        resolved["content_id"] = _bounded_text(
            content_id,
            field="content_id",
            maximum=CONTENT_ID_MAX_LENGTH,
        )

    author_id = _filter_text(filters, "author_id")
    if author_id is not None:
        resolved["author_id"] = _positive_integer(author_id, field="author_id")

    keyword = _filter_text(filters, "keyword")
    if keyword is not None:
        resolved["keyword"] = _bounded_text(
            keyword,
            field="keyword",
            maximum=KEYWORD_MAX_LENGTH,
        )

    is_visible = _filter_text(filters, "is_visible")
    if is_visible is not None:
        resolved["is_visible"] = _visible_flag(is_visible, field="is_visible")

    created_from = _filter_text(filters, "created_from")
    if created_from is not None:
        resolved["created_from"] = _timestamp_boundary(
            created_from,
            field="created_from",
        )
    created_to = _filter_text(filters, "created_to")
    if created_to is not None:
        resolved["created_to"] = _timestamp_boundary(
            created_to,
            field="created_to",
        )
    if (
        "created_from" in resolved
        and "created_to" in resolved
        and resolved["created_from"] > resolved["created_to"]
    ):
        raise _validation(
            "筛选时间范围不正确",
            code=_FILTER_INVALID,
            field="created_from",
        )

    limit = _filter_text(filters, "limit")
    if limit is None:
        resolved["limit"] = DEFAULT_PAGE_SIZE
    else:
        resolved["limit"] = _positive_integer(limit, field="limit")
        if resolved["limit"] > MAX_PAGE_SIZE:
            raise _validation(
                f"limit 不能超过 {MAX_PAGE_SIZE}",
                code=_FILTER_INVALID,
                field="limit",
                max_length=MAX_PAGE_SIZE,
            )

    offset = _filter_text(filters, "offset")
    resolved["offset"] = (
        0 if offset is None else _non_negative_integer(offset, field="offset")
    )
    return resolved


def _moderation_conditions(resolved: dict) -> tuple[str, tuple]:
    parts: list[str] = []
    parameters: list = []
    if "content_type" in resolved:
        parts.append("c.content_type = ?")
        parameters.append(resolved["content_type"])
    if "content_id" in resolved:
        parts.append("c.content_id = ?")
        parameters.append(resolved["content_id"])
    if "author_id" in resolved:
        parts.append("c.author_id = ?")
        parameters.append(resolved["author_id"])
    if "is_visible" in resolved:
        parts.append("c.is_visible = ?")
        parameters.append(1 if resolved["is_visible"] else 0)
    if "keyword" in resolved:
        pattern = f"%{resolved['keyword']}%"
        parts.append(
            "(c.body LIKE ? OR u.username LIKE ? OR u.name LIKE ?)"
        )
        parameters.extend([pattern, pattern, pattern])
    if not parts:
        return "", ()
    return "WHERE " + " AND ".join(parts), tuple(parameters)


def _within_range(value: object, resolved: dict) -> bool:
    if "created_from" not in resolved and "created_to" not in resolved:
        return True
    parsed = _parse_stored_timestamp(value)
    if parsed is None:
        return False
    if "created_from" in resolved and parsed < resolved["created_from"]:
        return False
    if "created_to" in resolved and parsed > resolved["created_to"]:
        return False
    return True


def _ordered_by_created_desc(records: list[dict]) -> list[dict]:
    """Sort by parsed time descending with `comment_id` ascending as the tie.

    Two passes keep the tie-breaker correct: the first pass fixes
    `comment_id ASC`, the second is a stable sort on the parsed timestamp,
    so equal timestamps keep their comment_id order. The timestamp is
    parsed rather than compared as text because 08 and 011 write the same
    instant in different offsets.
    """
    return _ordered_by_created_desc_with(records, tie_breaker="comment_id")


def _ordered_by_created_desc_with(
    records: list[dict],
    *,
    tie_breaker: str,
) -> list[dict]:
    """The same two-pass ordering for any queue, keyed by its primary id.

    The report and feedback queues need the identical discipline, and the
    tie-breaker has to be the row's own id, so the passes are shared here
    rather than copied per list function.
    """
    ordered = sorted(records, key=lambda record: record[tie_breaker])
    ordered.sort(
        key=lambda record: _sort_time(record["created_at"]),
        reverse=True,
    )
    return ordered


def _status_filter(
    value: object,
    *,
    field: str,
    allowed: frozenset[str],
    allowed_values: tuple[str, ...],
) -> str:
    normalized = _filter_text({"status": value}, "status")
    if normalized is None:
        raise _validation(
            "状态筛选值不能为空",
            code=_FILTER_INVALID,
            field=field,
        )
    if normalized not in allowed:
        raise _validation(
            "状态筛选值不正确",
            code=_FILTER_INVALID,
            field=field,
            value=normalized,
            allowed=list(allowed_values),
        )
    return normalized


def _report_filters(filters: object) -> dict:
    if not isinstance(filters, dict):
        raise _validation(
            "筛选条件格式不正确",
            code=_FILTER_INVALID,
            field="filters",
        )
    resolved: dict = {}

    status = _filter_text(filters, "status")
    if status is not None:
        resolved["status"] = _status_filter(
            status,
            field="status",
            allowed=REPORT_STATUSES,
            allowed_values=REPORT_STATUS_VALUES,
        )

    comment_id = _filter_text(filters, "comment_id")
    if comment_id is not None:
        resolved["comment_id"] = _bounded_text(
            comment_id,
            field="comment_id",
            maximum=COMMENT_ID_MAX_LENGTH,
        )

    reporter_id = _filter_text(filters, "reporter_id")
    if reporter_id is not None:
        resolved["reporter_id"] = _positive_integer(
            reporter_id,
            field="reporter_id",
        )

    created_from = _filter_text(filters, "created_from")
    if created_from is not None:
        resolved["created_from"] = _timestamp_boundary(
            created_from,
            field="created_from",
        )
    created_to = _filter_text(filters, "created_to")
    if created_to is not None:
        resolved["created_to"] = _timestamp_boundary(
            created_to,
            field="created_to",
        )
    if (
        "created_from" in resolved
        and "created_to" in resolved
        and resolved["created_from"] > resolved["created_to"]
    ):
        raise _validation(
            "筛选时间范围不正确",
            code=_FILTER_INVALID,
            field="created_from",
        )

    limit = _filter_text(filters, "limit")
    if limit is None:
        resolved["limit"] = DEFAULT_PAGE_SIZE
    else:
        resolved["limit"] = _positive_integer(limit, field="limit")
        if resolved["limit"] > MAX_PAGE_SIZE:
            raise _validation(
                f"limit 不能超过 {MAX_PAGE_SIZE}",
                code=_FILTER_INVALID,
                field="limit",
                max_length=MAX_PAGE_SIZE,
            )

    offset = _filter_text(filters, "offset")
    resolved["offset"] = (
        0 if offset is None else _non_negative_integer(offset, field="offset")
    )
    return resolved


def _feedback_filters(filters: object) -> dict:
    if not isinstance(filters, dict):
        raise _validation(
            "筛选条件格式不正确",
            code=_FILTER_INVALID,
            field="filters",
        )
    resolved: dict = {}

    status = _filter_text(filters, "status")
    if status is not None:
        resolved["status"] = _status_filter(
            status,
            field="status",
            allowed=FEEDBACK_STATUSES,
            allowed_values=FEEDBACK_STATUS_VALUES,
        )

    submitter_id = _filter_text(filters, "submitter_id")
    if submitter_id is not None:
        resolved["submitter_id"] = _positive_integer(
            submitter_id,
            field="submitter_id",
        )

    created_from = _filter_text(filters, "created_from")
    if created_from is not None:
        resolved["created_from"] = _timestamp_boundary(
            created_from,
            field="created_from",
        )
    created_to = _filter_text(filters, "created_to")
    if created_to is not None:
        resolved["created_to"] = _timestamp_boundary(
            created_to,
            field="created_to",
        )
    if (
        "created_from" in resolved
        and "created_to" in resolved
        and resolved["created_from"] > resolved["created_to"]
    ):
        raise _validation(
            "筛选时间范围不正确",
            code=_FILTER_INVALID,
            field="created_from",
        )

    limit = _filter_text(filters, "limit")
    if limit is None:
        resolved["limit"] = DEFAULT_PAGE_SIZE
    else:
        resolved["limit"] = _positive_integer(limit, field="limit")
        if resolved["limit"] > MAX_PAGE_SIZE:
            raise _validation(
                f"limit 不能超过 {MAX_PAGE_SIZE}",
                code=_FILTER_INVALID,
                field="limit",
                max_length=MAX_PAGE_SIZE,
            )

    offset = _filter_text(filters, "offset")
    resolved["offset"] = (
        0 if offset is None else _non_negative_integer(offset, field="offset")
    )
    return resolved


def _serialize_report(row: sqlite3.Row) -> dict:
    reporter_username = row["reporter_username"]
    reporter_name = row["reporter_name"]
    resolver_username = row["resolver_username"]
    resolver_name = row["resolver_name"]
    resolver_id = row["resolver_id"]
    resolved_at = row["resolved_at"]
    result = row["result"]
    return {
        "report_id": str(row["report_id"]),
        "comment_id": str(row["comment_id"]),
        "reporter_id": int(row["reporter_id"]),
        "reporter": {
            "username": str(reporter_username or ""),
            "name": str(reporter_name or ""),
        },
        "reason": str(row["reason"]),
        "status": str(row["status"]),
        "resolver_id": (
            int(resolver_id) if resolver_id is not None else None
        ),
        "resolver": {
            "username": str(resolver_username or ""),
            "name": str(resolver_name or ""),
        },
        "result": str(result) if result is not None else None,
        "comment_is_visible": (
            bool(row["comment_is_visible"])
            if row["comment_is_visible"] is not None
            else None
        ),
        "created_at": str(row["created_at"]),
        "updated_at": str(row["updated_at"]),
        "resolved_at": str(resolved_at) if resolved_at is not None else None,
    }


def _serialize_feedback(row: sqlite3.Row) -> dict:
    """The one canonical feedback shape, shared by intake and the console.

    07 and 12 consume the provider slot and the console reads the same
    queue, so both answers are built here: a field added once is visible to
    both, and neither side has to guess at a second shape.
    """
    submitter_username = row["submitter_username"]
    submitter_name = row["submitter_name"]
    handler_username = row["handler_username"]
    handler_name = row["handler_name"]
    handler_id = row["handler_id"]
    result = row["result"]
    return {
        "feedback_id": str(row["feedback_id"]),
        "submitter_id": int(row["submitter_id"]),
        "submitter": {
            "username": str(submitter_username or ""),
            "name": str(submitter_name or ""),
        },
        "body": str(row["body"]),
        "status": str(row["status"]),
        "idempotency_key": str(row["idempotency_key"]),
        "handler_id": int(handler_id) if handler_id is not None else None,
        "handler": {
            "username": str(handler_username or ""),
            "name": str(handler_name or ""),
        },
        "result": str(result) if result is not None else None,
        "created_at": str(row["created_at"]),
        "updated_at": str(row["updated_at"]),
    }


def _serialize_comment(row: sqlite3.Row) -> dict:
    parent_comment_id = row["parent_comment_id"]
    return {
        "comment_id": str(row["comment_id"]),
        "content_type": str(row["content_type"]),
        "content_id": str(row["content_id"]),
        "author_id": int(row["author_id"]),
        "author": {
            "username": str(row["author_username"] or ""),
            "name": str(row["author_name"] or ""),
        },
        "parent_comment_id": (
            str(parent_comment_id) if parent_comment_id is not None else None
        ),
        "body": str(row["body"]),
        "is_teacher_reply": bool(row["is_teacher_reply"]),
        "is_visible": bool(row["is_visible"]),
        "created_at": str(row["created_at"]),
        "updated_at": str(row["updated_at"]),
    }


def list_moderation_comments(filters: dict) -> list[dict]:
    """Patrol queue over both commentable content types (FR-071).

    Hidden comments stay in the queue: an admin who is reviewing past
    decisions needs to see what was already taken down. The time range is
    applied on parsed stamps and the ordering is decided in Python, so a
    `+08:00` row and a UTC `Z` row never interleave.
    """
    resolved = _comment_filters(filters)
    where, parameters = _moderation_conditions(resolved)
    rows = _fetch_all(
        f"""
        SELECT {MODERATION_COLUMNS}
        {MODERATION_JOINS}
        {where}
        """,
        parameters,
    )
    records = [
        _serialize_comment(row)
        for row in rows
        if _within_range(row["created_at"], resolved)
    ]
    ordered = _ordered_by_created_desc(records)
    start = resolved["offset"]
    return ordered[start : start + resolved["limit"]]


def delete_comment(actor_id: int, comment_id: str) -> dict:
    """Silently hide one comment and record the decision (FR-072).

    The visibility flag and the audit row are written inside one
    transaction, so a decision is never half-recorded. No notification
    event is emitted on any path: the author of a hidden comment is never
    told, which is the whole point of "silent".

    A comment that is already hidden reports `changed: False` instead of
    raising. Task 19's report resolution calls this function and has to
    count a confirmed report exactly once, and a second DELETE from a
    double-submitted console must not look like a new decision either.
    """
    normalized = _bounded_text(
        comment_id,
        field="comment_id",
        maximum=COMMENT_ID_MAX_LENGTH,
        code="moderation_validation_failed",
    )
    with get_db() as db:
        _begin_exclusive(db)
        row = db.execute(
            """
            SELECT comment_id, content_type, content_id, author_id,
                   is_visible, updated_at
            FROM content_comments
            WHERE comment_id = ?
            """,
            (normalized,),
        ).fetchone()
        if row is None:
            raise _not_found(normalized)
        if not bool(row["is_visible"]):
            return {
                "comment_id": normalized,
                "is_visible": False,
                "changed": False,
                "updated_at": str(row["updated_at"]),
            }
        now = platform_now_iso()
        db.execute(
            """
            UPDATE content_comments
            SET is_visible = 0, updated_at = ?
            WHERE comment_id = ?
            """,
            (now, normalized),
        )
        record_admin_audit(
            db,
            actor_id=actor_id,
            action="delete_comment",
            target_type="content_comment",
            target_id=normalized,
            before={
                "is_visible": True,
                "content_type": str(row["content_type"]),
                "content_id": str(row["content_id"]),
                "author_id": int(row["author_id"]),
                "updated_at": str(row["updated_at"]),
            },
            after={
                "is_visible": False,
                "content_type": str(row["content_type"]),
                "content_id": str(row["content_id"]),
                "author_id": int(row["author_id"]),
                "updated_at": now,
            },
            result="success",
        )
    return {
        "comment_id": normalized,
        "is_visible": False,
        "changed": True,
        "updated_at": now,
    }


def processed_comment_count() -> int:
    """How many comments moderation has taken out of the read paths.

    `content_comments` carries no "moderated by" column and 011 may not add
    one (Task 1 froze the schema), so the only truthful signal is the flag
    08 already filters on: a row with `is_visible = 0` is a comment a
    moderator hid and the student and teacher read paths no longer return.
    The count therefore moves only when a real row changes state, and a
    repeat DELETE cannot inflate it because `delete_comment` reports
    `changed: False` the second time.
    """
    row = _fetch_one(
        "SELECT COUNT(*) AS count FROM content_comments WHERE is_visible = 0"
    )
    return int(row["count"])


def list_reports(filters: dict) -> list[dict]:
    """Report queue over every reported comment (FR-071).

    A report on an already hidden comment stays in the queue: the admin has
    to see which reports are still waiting, and hiding the comment is not
    the same as answering the reporter's report. `comment_is_visible` is
    what tells the two apart.
    """
    resolved = _report_filters(filters)
    # Clause and parameter are appended together, so a new filter cannot
    # leave one list out of step with the other.
    parts: list[str] = []
    parameters: list = []
    for clause, field in (
        ("r.status = ?", "status"),
        ("r.comment_id = ?", "comment_id"),
        ("r.reporter_id = ?", "reporter_id"),
    ):
        if field in resolved:
            parts.append(clause)
            parameters.append(resolved[field])
    where = "WHERE " + " AND ".join(parts) if parts else ""
    rows = _fetch_all(
        f"""
        SELECT {REPORT_COLUMNS}
        {REPORT_JOINS}
        {where}
        """,
        tuple(parameters),
    )
    records = [
        _serialize_report(row)
        for row in rows
        if _within_range(row["created_at"], resolved)
    ]
    ordered = _ordered_by_created_desc_with(
        records,
        tie_breaker="report_id",
    )
    start = resolved["offset"]
    return ordered[start : start + resolved["limit"]]


def resolve_report(
    actor_id: int,
    report_id: str,
    confirmed: bool,
    result: str,
) -> dict:
    """Answer one report, deleting the comment only when it is confirmed.

    The two outcomes differ in exactly one place. A confirmed report hides
    the reported comment through `delete_comment`, which is the silent path
    Task 18 already proved emits nothing; a rejected one leaves visibility
    untouched. Both write the resolution onto the report row.

    Idempotence is reported, not raised: a report that is already
    `confirmed` or `rejected` answers `changed: False` with HTTP 200, the
    same contract `delete_comment` and `publish_announcement` use, because a
    double-submitted console must not look like a second decision. The
    ordering matters for that: `delete_comment` runs before the report row
    is written, so the second submission is the one that stops, never the
    first half of a decision.

    A report whose comment has already disappeared still resolves. The
    comment is gone, which is the outcome a confirmation asks for, and
    refusing the report because the row vanished would strand it as
    `pending` forever.
    """
    normalized = _bounded_text(
        report_id,
        field="report_id",
        maximum=REPORT_ID_MAX_LENGTH,
        code="moderation_validation_failed",
    )
    if not isinstance(confirmed, bool):
        raise _validation(
            "处理结论必须是布尔值",
            code="moderation_validation_failed",
            field="confirmed",
        )
    normalized_result = _bounded_text(
        result,
        field="result",
        maximum=RESULT_MAX_LENGTH,
        code="moderation_validation_failed",
    )
    status = "confirmed" if confirmed else "rejected"

    # The deletion runs first and in its own transaction. It takes the write
    # lock itself, so opening one here would only make it fail.
    deletion = _delete_reported_comment(normalized, actor_id) if confirmed else None

    now = platform_now_iso()
    with get_db() as db:
        _begin_exclusive(db)
        row = db.execute(
            f"""
            SELECT {REPORT_COLUMNS}
            {REPORT_JOINS}
            WHERE r.report_id = ?
            """,
            (normalized,),
        ).fetchone()
        if row is None:
            raise _report_not_found(normalized)
        if str(row["status"]) != "pending":
            # Already answered by an earlier submission, so the count, the
            # audit trail and the row all stay exactly as they were.
            return _resolved_report(row, changed=False)
        db.execute(
            """
            UPDATE comment_reports
            SET status = ?, resolver_id = ?, result = ?, resolved_at = ?,
                updated_at = ?
            WHERE report_id = ?
            """,
            (
                status,
                actor_id,
                normalized_result,
                now,
                now,
                normalized,
            ),
        )
        record_admin_audit(
            db,
            actor_id=actor_id,
            action="resolve_comment_report",
            target_type="comment_report",
            target_id=normalized,
            before={
                "status": str(row["status"]),
                "comment_id": str(row["comment_id"]),
                "reporter_id": int(row["reporter_id"]),
                "reason": str(row["reason"]),
                "resolver_id": (
                    int(row["resolver_id"])
                    if row["resolver_id"] is not None
                    else None
                ),
                "result": (
                    str(row["result"]) if row["result"] is not None else None
                ),
            },
            after={
                "status": status,
                "comment_id": str(row["comment_id"]),
                "reporter_id": int(row["reporter_id"]),
                "reason": str(row["reason"]),
                "resolver_id": actor_id,
                "result": normalized_result,
                "comment_deleted": bool(
                    deletion is not None and deletion["changed"]
                ),
                "comment_already_hidden": bool(
                    deletion is not None and not deletion["changed"]
                ),
            },
            result="success",
        )
        # The pre-update row is a snapshot, so the answer is read back from
        # the table rather than patched together from the request.
        resolved_row = db.execute(
            f"""
            SELECT {REPORT_COLUMNS}
            {REPORT_JOINS}
            WHERE r.report_id = ?
            """,
            (normalized,),
        ).fetchone()
    return _resolved_report(resolved_row, changed=True)


def _delete_reported_comment(report_id: str, actor_id: int) -> dict | None:
    """Hide the comment a confirmed report names, if that row still exists.

    A report can outlive its comment: another path may have removed the row
    and `comment_reports` carries no foreign key back to it. The report
    still resolves in that case, because the outcome a confirmation asks for
    is already true, and stranding it as `pending` would leave the reporter
    permanently unanswered.
    """
    row = _fetch_one(
        """
        SELECT r.comment_id AS comment_id,
               c.comment_id IS NOT NULL AS comment_exists
        FROM comment_reports r
        LEFT JOIN content_comments c ON c.comment_id = r.comment_id
        WHERE r.report_id = ?
        """,
        (report_id,),
    )
    if row is None or not row["comment_exists"]:
        return None
    return delete_comment(actor_id, str(row["comment_id"]))


def _resolved_report(row: sqlite3.Row, *, changed: bool) -> dict:
    report = _serialize_report(row)
    report["changed"] = changed
    return report


def _report_not_found(report_id: str) -> ProviderNotFoundError:
    return ProviderNotFoundError(
        "举报不存在",
        code="comment_report_not_found",
        details={"report_id": report_id},
    )


def processed_report_count() -> int:
    """How many reports the console has answered.

    "Only when the status changes from `pending`" is what the stored rows
    already say: a report leaves `pending` exactly once, because the only
    writer is `resolve_report` and it refuses a row that is not `pending`
    any more. Counting the non-pending rows therefore cannot double-count a
    repeated submission, and it needs no counter column that Task 1's frozen
    schema does not have.
    """
    row = _fetch_one(
        """
        SELECT COUNT(*) AS count
        FROM comment_reports
        WHERE status <> 'pending'
        """
    )
    return int(row["count"])


def submit_feedback(
    *,
    submitter_id: int,
    body: str,
    idempotency_key: str,
) -> dict:
    """Intake one feedback record for the 07/12 provider slot.

    Idempotence is the whole contract: `(submitter_id, idempotency_key)` is
    unique on the table, so a retried submission returns the record that is
    already stored instead of writing a second one. The lookup runs first,
    inside the write lock, so the unique index is only the last line of
    defence rather than the mechanism a caller has to survive.

    Intake is silent like everything else here. No notification event, no
    outbox row, and no message to the submitter: the console answers the
    record later through `update_feedback`.
    """
    if (
        isinstance(submitter_id, bool)
        or not isinstance(submitter_id, int)
        or submitter_id <= 0
        or submitter_id > SQLITE_MAX_INTEGER
    ):
        raise _validation(
            "反馈提交人标识不正确",
            code="moderation_validation_failed",
            field="submitter_id",
        )
    normalized_body = _bounded_text(
        body,
        field="body",
        maximum=BODY_MAX_LENGTH,
        code="moderation_validation_failed",
    )
    normalized_key = _bounded_text(
        idempotency_key,
        field="idempotency_key",
        maximum=IDEMPOTENCY_KEY_MAX_LENGTH,
        code="moderation_validation_failed",
    )
    with get_db() as db:
        # The lookup happens under the write lock, so two concurrent
        # submissions of the same key serialize here instead of racing to
        # the unique index.
        _begin_exclusive(db)
        existing = db.execute(
            f"""
            SELECT {FEEDBACK_COLUMNS}
            {FEEDBACK_JOINS}
            WHERE f.submitter_id = ? AND f.idempotency_key = ?
            """,
            (submitter_id, normalized_key),
        ).fetchone()
        if existing is not None:
            return _serialize_feedback(existing)
        now = platform_now_iso()
        feedback_id = f"feedback-{uuid.uuid4().hex}"
        db.execute(
            """
            INSERT INTO feedback_records (
                feedback_id, submitter_id, body, status, idempotency_key,
                created_at, updated_at
            )
            VALUES (?, ?, ?, 'pending', ?, ?, ?)
            """,
            (
                feedback_id,
                submitter_id,
                normalized_body,
                normalized_key,
                now,
                now,
            ),
        )
        row = db.execute(
            f"""
            SELECT {FEEDBACK_COLUMNS}
            {FEEDBACK_JOINS}
            WHERE f.feedback_id = ?
            """,
            (feedback_id,),
        ).fetchone()
    return _serialize_feedback(row)


def list_feedback(filters: dict) -> list[dict]:
    """Feedback intake queue, newest first.

    The queue is read-only here: writing a feedback row is the provider
    slot's job, so 07 and 12 submit through `submit_feedback` and the
    console only answers what arrived.
    """
    resolved = _feedback_filters(filters)
    parts: list[str] = []
    parameters: list = []
    for clause, field in (
        ("f.status = ?", "status"),
        ("f.submitter_id = ?", "submitter_id"),
    ):
        if field in resolved:
            parts.append(clause)
            parameters.append(resolved[field])
    where = "WHERE " + " AND ".join(parts) if parts else ""
    rows = _fetch_all(
        f"""
        SELECT {FEEDBACK_COLUMNS}
        {FEEDBACK_JOINS}
        {where}
        """,
        tuple(parameters),
    )
    records = [
        _serialize_feedback(row)
        for row in rows
        if _within_range(row["created_at"], resolved)
    ]
    ordered = _ordered_by_created_desc_with(
        records,
        tie_breaker="feedback_id",
    )
    start = resolved["offset"]
    return ordered[start : start + resolved["limit"]]


def update_feedback(
    actor_id: int,
    feedback_id: str,
    status: str,
    result: str,
) -> dict:
    """Move one feedback row along its three-state machine and record it.

    `pending` -> `processed` -> `closed`, with a direct `closed` allowed so a
    duplicate or a spam submission can be shut without being worked. The
    status is the only thing the state machine owns: the row keeps its
    submitter, body and arrival time untouched, and the handler, the result
    text and `updated_at` are what this write adds.

    A status that equals the stored one reports `changed: False` with no
    audit row, matching `delete_comment` and `resolve_report`, so a
    double-submitted console cannot inflate the audit trail.
    """
    normalized = _bounded_text(
        feedback_id,
        field="feedback_id",
        maximum=FEEDBACK_ID_MAX_LENGTH,
        code="moderation_validation_failed",
    )
    if not isinstance(status, str) or status not in FEEDBACK_STATUSES:
        raise _validation(
            "反馈状态不正确",
            code="moderation_validation_failed",
            field="status",
            value=status,
            allowed=list(FEEDBACK_STATUS_VALUES),
        )
    normalized_result = _bounded_text(
        result,
        field="result",
        maximum=RESULT_MAX_LENGTH,
        code="moderation_validation_failed",
    )
    with get_db() as db:
        _begin_exclusive(db)
        row = db.execute(
            f"""
            SELECT {FEEDBACK_COLUMNS}
            {FEEDBACK_JOINS}
            WHERE f.feedback_id = ?
            """,
            (normalized,),
        ).fetchone()
        if row is None:
            raise _feedback_not_found(normalized)
        if str(row["status"]) == status:
            return _updated_feedback(row, changed=False)
        now = platform_now_iso()
        db.execute(
            """
            UPDATE feedback_records
            SET status = ?, handler_id = ?, result = ?, updated_at = ?
            WHERE feedback_id = ?
            """,
            (status, actor_id, normalized_result, now, normalized),
        )
        record_admin_audit(
            db,
            actor_id=actor_id,
            action="update_feedback",
            target_type="feedback_record",
            target_id=normalized,
            before={
                "status": str(row["status"]),
                "submitter_id": int(row["submitter_id"]),
                "handler_id": (
                    int(row["handler_id"])
                    if row["handler_id"] is not None
                    else None
                ),
                "result": (
                    str(row["result"]) if row["result"] is not None else None
                ),
            },
            after={
                "status": status,
                "submitter_id": int(row["submitter_id"]),
                "handler_id": actor_id,
                "result": normalized_result,
            },
            result="success",
        )
        updated_row = db.execute(
            f"""
            SELECT {FEEDBACK_COLUMNS}
            {FEEDBACK_JOINS}
            WHERE f.feedback_id = ?
            """,
            (normalized,),
        ).fetchone()
    return _updated_feedback(updated_row, changed=True)


def _updated_feedback(row: sqlite3.Row, *, changed: bool) -> dict:
    feedback = _serialize_feedback(row)
    feedback["changed"] = changed
    return feedback


def _feedback_not_found(feedback_id: str) -> ProviderNotFoundError:
    return ProviderNotFoundError(
        "反馈不存在",
        code="feedback_not_found",
        details={"feedback_id": feedback_id},
    )


__all__ = [
    "delete_comment",
    "list_moderation_comments",
    "list_feedback",
    "list_reports",
    "processed_comment_count",
    "processed_report_count",
    "resolve_report",
    "submit_feedback",
    "update_feedback",
]
