"""Comment patrol listing and silent deletion for 011.

011's moderation surface reads the shared `content_comments` table that 08
owns. The only write is `is_visible = 0`, which is exactly the predicate
08's `list_content_comments` and `list_teacher_comments` already filter
on, so a hidden comment leaves the student and teacher read paths on their
very next request. That is what makes the deletion silent.

Silence is a hard requirement (FR-072, SC-010): the author of a deleted
comment is never told. This module therefore never imports anything from
`app.messaging`, writes no outbox row, and emits no notification event.

`comment_reports` and `feedback_records` already exist in the schema but
belong to Task 19; this module deliberately leaves them alone.
"""

from __future__ import annotations

import sqlite3
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
COMMENT_ID_MAX_LENGTH = 128
CONTENT_ID_MAX_LENGTH = 128
KEYWORD_MAX_LENGTH = 64
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200

PLATFORM_TIMEZONE = ZoneInfo("Asia/Shanghai")
TIME_FLOOR = datetime.min.replace(tzinfo=PLATFORM_TIMEZONE)

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
    ordered = sorted(records, key=lambda record: record["comment_id"])
    ordered.sort(
        key=lambda record: _sort_time(record["created_at"]),
        reverse=True,
    )
    return ordered


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


__all__ = [
    "delete_comment",
    "list_moderation_comments",
    "processed_comment_count",
]
