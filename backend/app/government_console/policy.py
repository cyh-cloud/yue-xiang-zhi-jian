from __future__ import annotations

import sqlite3
from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.db import get_db
from app.government_console.constants import POLICY_CATEGORIES
from app.government_console.errors import (
    ProviderConflictError,
    ProviderNotFoundError,
    ProviderValidationError,
)
from app.messaging.broadcasts import emit_policy_published
from app.messaging.notification_service import (
    mark_notification_sources_unavailable,
)


PLATFORM_TIMEZONE = ZoneInfo("Asia/Shanghai")


def publish_policy(
    *,
    actor_id: int,
    request_id: str,
    title: str,
    content: str,
    category_code: str,
) -> dict:
    normalized = _validate_publication_input(
        actor_id=actor_id,
        request_id=request_id,
        title=title,
        content=content,
        category_code=category_code,
        categories=POLICY_CATEGORIES,
    )
    existing = _find_publication_request(
        "policy",
        normalized["request_id"],
    )
    if existing is not None:
        return get_policy(existing["content_id"])

    now = shanghai_now_iso()
    policy_id = f"policy-{uuid4().hex}"
    db = get_db()
    try:
        db.execute(
            """
            INSERT INTO government_policies (
                id, title, content, category_code, status, view_count,
                version, created_by, published_at, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, 'active', 0, 1, ?, ?, ?, ?)
            """,
            (
                policy_id,
                normalized["title"],
                normalized["content"],
                normalized["category_code"],
                normalized["actor_id"],
                now,
                now,
                now,
            ),
        )
        db.execute(
            """
            INSERT INTO government_publication_requests (
                content_type, request_id, content_id, created_at
            )
            VALUES ('policy', ?, ?, ?)
            """,
            (normalized["request_id"], policy_id, now),
        )
        emit_policy_published(
            event_id=f"policy:{normalized['request_id']}",
            policy_id=policy_id,
            title=normalized["title"],
            category=POLICY_CATEGORIES[normalized["category_code"]],
        )
        db.commit()
    except sqlite3.IntegrityError:
        db.rollback()
        existing = _find_publication_request(
            "policy",
            normalized["request_id"],
        )
        if existing is None:
            raise ProviderConflictError("政策发布请求冲突")
        return get_policy(existing["content_id"])
    except Exception:
        db.rollback()
        raise
    return get_policy(policy_id)


def list_policies(
    *,
    status: str | None = None,
    category_code: str | None = None,
) -> list[dict]:
    normalized_status = _validate_status_filter(status)
    normalized_category = _validate_category_filter(category_code)
    sql = """
        SELECT
            id, title, content, category_code, status, view_count, version,
            published_at, updated_at
        FROM government_policies
        WHERE 1 = 1
    """
    params: list[object] = []
    if normalized_status is not None:
        sql += " AND status = ?"
        params.append(normalized_status)
    if normalized_category is not None:
        sql += " AND category_code = ?"
        params.append(normalized_category)
    sql += " ORDER BY published_at DESC, id ASC"
    return [
        _policy_payload(row)
        for row in get_db().execute(sql, params).fetchall()
    ]


def list_published_policies(
    category_code: str | None = None,
) -> list[dict]:
    normalized_category = _validate_category_filter(category_code)
    sql = """
        SELECT
            id, title, content, category_code, published_at, updated_at,
            version
        FROM government_policies
        WHERE status = 'active'
    """
    params: list[object] = []
    if normalized_category is not None:
        sql += " AND category_code = ?"
        params.append(normalized_category)
    sql += " ORDER BY published_at DESC, id ASC"
    return [
        _published_policy_payload(row)
        for row in get_db().execute(sql, params).fetchall()
    ]


def get_published_policy(policy_id: str) -> dict | None:
    if not isinstance(policy_id, str) or not policy_id.strip():
        return None
    row = get_db().execute(
        """
        SELECT
            id, title, content, category_code, published_at, updated_at,
            version
        FROM government_policies
        WHERE id = ? AND status = 'active'
        """,
        (policy_id.strip(),),
    ).fetchone()
    return _published_policy_payload(row) if row is not None else None


def unpublish_policy(policy_id: str, *, expected_version: int) -> dict:
    return _transition_policy(
        policy_id,
        expected_version=expected_version,
        expected_status="active",
        new_status="unpublished",
    )


def relist_policy(policy_id: str, *, expected_version: int) -> dict:
    return _transition_policy(
        policy_id,
        expected_version=expected_version,
        expected_status="unpublished",
        new_status="active",
    )


def delete_policy(policy_id: str, *, expected_version: int) -> None:
    normalized_policy_id = _validate_policy_id(policy_id)
    normalized_version = _validate_expected_version(expected_version)
    db = get_db()
    try:
        result = db.execute(
            """
            DELETE FROM government_policies
            WHERE id = ? AND version = ?
            """,
            (normalized_policy_id, normalized_version),
        )
        if result.rowcount != 1:
            db.rollback()
            if _policy_exists(normalized_policy_id):
                raise ProviderConflictError("政策状态已变化，请刷新后重试")
            raise ProviderNotFoundError("政策不存在")

        db.execute(
            """
            DELETE FROM government_view_events
            WHERE content_type = 'policy' AND content_id = ?
            """,
            (normalized_policy_id,),
        )
        mark_notification_sources_unavailable(
            source_type="policy",
            source_id=normalized_policy_id,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise


def get_policy(policy_id: str) -> dict | None:
    if not isinstance(policy_id, str) or not policy_id.strip():
        return None
    row = get_db().execute(
        """
        SELECT
            id, title, content, category_code, status, view_count, version,
            published_at, updated_at
        FROM government_policies
        WHERE id = ?
        """,
        (policy_id.strip(),),
    ).fetchone()
    return _policy_payload(row) if row is not None else None


def shanghai_now_iso() -> str:
    return datetime.now(PLATFORM_TIMEZONE).isoformat(timespec="seconds")


def normalize_shanghai_iso(value: object) -> str:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=PLATFORM_TIMEZONE)
    return parsed.astimezone(PLATFORM_TIMEZONE).isoformat(timespec="seconds")


def _transition_policy(
    policy_id: str,
    *,
    expected_version: int,
    expected_status: str,
    new_status: str,
) -> dict:
    normalized_policy_id = _validate_policy_id(policy_id)
    normalized_version = _validate_expected_version(expected_version)
    db = get_db()
    result = db.execute(
        """
        UPDATE government_policies
        SET status = ?, version = version + 1, updated_at = ?
        WHERE id = ? AND version = ? AND status = ?
        """,
        (
            new_status,
            shanghai_now_iso(),
            normalized_policy_id,
            normalized_version,
            expected_status,
        ),
    )
    if result.rowcount != 1:
        db.rollback()
        if _policy_exists(normalized_policy_id):
            raise ProviderConflictError("政策状态已变化，请刷新后重试")
        raise ProviderNotFoundError("政策不存在")
    db.commit()
    policy = get_policy(normalized_policy_id)
    if policy is None:
        raise ProviderConflictError("政策状态更新失败")
    return policy


def _validate_publication_input(
    *,
    actor_id: object,
    request_id: object,
    title: object,
    content: object,
    category_code: object,
    categories: dict[str, str],
) -> dict:
    if (
        isinstance(actor_id, bool)
        or not isinstance(actor_id, int)
        or actor_id <= 0
    ):
        raise ProviderValidationError(
            "政府用户标识不正确",
            details={"actor_id": "必须是正整数"},
        )
    normalized_category = _required_text(
        category_code,
        "category_code",
        "政策类别不能为空",
    )
    if normalized_category not in categories:
        raise ProviderValidationError(
            "政策类别不正确",
            details={"category_code": "不属于政策类别"},
        )
    return {
        "actor_id": actor_id,
        "request_id": _required_text(
            request_id,
            "request_id",
            "政策发布请求标识不能为空",
        ),
        "title": _required_text(
            title,
            "title",
            "政策标题不能为空",
        ),
        "content": _required_text(
            content,
            "content",
            "政策正文不能为空",
        ),
        "category_code": normalized_category,
    }


def _required_text(
    value: object,
    field: str,
    message: str,
) -> str:
    if not isinstance(value, str):
        raise ProviderValidationError(
            message,
            details={field: "必须是文本"},
        )
    normalized = value.strip()
    if not normalized:
        raise ProviderValidationError(
            message,
            details={field: "不能为空"},
        )
    return normalized


def _validate_policy_id(policy_id: object) -> str:
    return _required_text(
        policy_id,
        "policy_id",
        "政策标识不能为空",
    )


def _validate_expected_version(expected_version: object) -> int:
    if (
        isinstance(expected_version, bool)
        or not isinstance(expected_version, int)
        or expected_version <= 0
    ):
        raise ProviderValidationError(
            "政策版本不正确",
            details={"expected_version": "必须是正整数"},
        )
    return expected_version


def _validate_status_filter(status: object) -> str | None:
    if status is None:
        return None
    if not isinstance(status, str) or status not in {
        "active",
        "unpublished",
    }:
        raise ProviderValidationError(
            "政策状态筛选不正确",
            details={"status": "只支持 active 或 unpublished"},
        )
    return status


def _validate_category_filter(category_code: object) -> str | None:
    if category_code is None:
        return None
    if (
        not isinstance(category_code, str)
        or category_code not in POLICY_CATEGORIES
    ):
        raise ProviderValidationError(
            "政策类别筛选不正确",
            details={"category_code": "不属于政策类别"},
        )
    return category_code


def _find_publication_request(
    content_type: str,
    request_id: str,
) -> sqlite3.Row | None:
    return get_db().execute(
        """
        SELECT content_id
        FROM government_publication_requests
        WHERE content_type = ? AND request_id = ?
        """,
        (content_type, request_id),
    ).fetchone()


def _policy_exists(policy_id: str) -> bool:
    return (
        get_db()
        .execute(
            "SELECT 1 FROM government_policies WHERE id = ?",
            (policy_id,),
        )
        .fetchone()
        is not None
    )


def _policy_payload(row: sqlite3.Row) -> dict:
    category_code = str(row["category_code"])
    return {
        "id": str(row["id"]),
        "title": str(row["title"]),
        "content": str(row["content"]),
        "category_code": category_code,
        "category_label": POLICY_CATEGORIES[category_code],
        "status": str(row["status"]),
        "view_count": int(row["view_count"]),
        "version": int(row["version"]),
        "published_at": str(row["published_at"]),
        "updated_at": str(row["updated_at"]),
    }


def _published_policy_payload(row: sqlite3.Row) -> dict:
    category_code = str(row["category_code"])
    return {
        "id": str(row["id"]),
        "title": str(row["title"]),
        "content": str(row["content"]),
        "category_code": category_code,
        "category_label": POLICY_CATEGORIES[category_code],
        "published_at": normalize_shanghai_iso(row["published_at"]),
        "updated_at": normalize_shanghai_iso(row["updated_at"]),
        "version": int(row["version"]),
    }
