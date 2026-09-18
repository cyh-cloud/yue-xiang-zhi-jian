from __future__ import annotations

import sqlite3
from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.db import get_db
from app.government_console.constants import NEWS_CATEGORIES
from app.government_console.errors import (
    ProviderConflictError,
    ProviderNotFoundError,
    ProviderValidationError,
)
from app.messaging.broadcasts import emit_policy_published


PLATFORM_TIMEZONE = ZoneInfo("Asia/Shanghai")


def publish_news(
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
    )
    existing = _find_publication_request("news", normalized["request_id"])
    if existing is not None:
        news = get_news(existing["content_id"])
        if news is None:
            raise ProviderConflictError("新闻发布请求已失效")
        return news
    return _insert_published_news(actor_id, normalized)


def list_news(*, category_code: str | None = None) -> list[dict]:
    normalized_category = _validate_category_filter(category_code)
    sql = """
        SELECT
            id, title, content, category_code, view_count, version,
            published_at, updated_at
        FROM government_news
        WHERE 1 = 1
    """
    params: list[object] = []
    if normalized_category is not None:
        sql += " AND category_code = ?"
        params.append(normalized_category)
    sql += " ORDER BY published_at DESC, id ASC"
    return [
        _news_payload(row)
        for row in get_db().execute(sql, params).fetchall()
    ]


def delete_news(news_id: str, *, expected_version: int) -> None:
    normalized_news_id = _validate_news_id(news_id)
    normalized_version = _validate_expected_version(expected_version)
    db = get_db()
    try:
        result = db.execute(
            """
            DELETE FROM government_news
            WHERE id = ? AND version = ?
            """,
            (normalized_news_id, normalized_version),
        )
        if result.rowcount != 1:
            db.rollback()
            raise ProviderNotFoundError("新闻不存在或版本已变化")

        db.execute(
            """
            DELETE FROM government_view_events
            WHERE content_type = 'news' AND content_id = ?
            """,
            (normalized_news_id,),
        )
        db.commit()
    except Exception:
        db.rollback()
        raise


def get_news(news_id: str) -> dict | None:
    if not isinstance(news_id, str) or not news_id.strip():
        return None
    row = get_db().execute(
        """
        SELECT
            id, title, content, category_code, view_count, version,
            published_at, updated_at
        FROM government_news
        WHERE id = ?
        """,
        (news_id.strip(),),
    ).fetchone()
    return _news_payload(row) if row is not None else None


def _insert_published_news(actor_id: int, normalized: dict) -> dict:
    now = shanghai_now_iso()
    news_id = f"news-{uuid4().hex}"
    db = get_db()
    try:
        db.execute(
            """
            INSERT INTO government_news (
                id, title, content, category_code, view_count, version,
                created_by, published_at, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, 0, 1, ?, ?, ?, ?)
            """,
            (
                news_id,
                normalized["title"],
                normalized["content"],
                normalized["category_code"],
                actor_id,
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
            VALUES ('news', ?, ?, ?)
            """,
            (normalized["request_id"], news_id, now),
        )
        db.commit()
    except sqlite3.IntegrityError:
        db.rollback()
        existing = _find_publication_request(
            "news",
            normalized["request_id"],
        )
        if existing is None:
            raise ProviderConflictError("新闻发布请求冲突")
        news = get_news(existing["content_id"])
        if news is None:
            raise ProviderConflictError("新闻发布请求已失效")
        return news
    except Exception:
        db.rollback()
        raise
    news = get_news(news_id)
    if news is None:
        raise ProviderConflictError("新闻发布失败")
    return news


def shanghai_now_iso() -> str:
    return datetime.now(PLATFORM_TIMEZONE).isoformat(timespec="seconds")


def _validate_publication_input(
    *,
    actor_id: object,
    request_id: object,
    title: object,
    content: object,
    category_code: object,
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
        "新闻类别不能为空",
    )
    if normalized_category not in NEWS_CATEGORIES:
        raise ProviderValidationError(
            "新闻类别不正确",
            details={"category_code": "不属于新闻类别"},
        )
    return {
        "actor_id": actor_id,
        "request_id": _required_text(
            request_id,
            "request_id",
            "新闻发布请求标识不能为空",
        ),
        "title": _required_text(
            title,
            "title",
            "新闻标题不能为空",
        ),
        "content": _required_text(
            content,
            "content",
            "新闻正文不能为空",
        ),
        "category_code": normalized_category,
    }


def _required_text(value: object, field: str, message: str) -> str:
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


def _validate_news_id(news_id: object) -> str:
    return _required_text(
        news_id,
        "news_id",
        "新闻标识不能为空",
    )


def _validate_expected_version(expected_version: object) -> int:
    if (
        isinstance(expected_version, bool)
        or not isinstance(expected_version, int)
        or expected_version <= 0
    ):
        raise ProviderValidationError(
            "新闻版本不正确",
            details={"expected_version": "必须是正整数"},
        )
    return expected_version


def _validate_category_filter(category_code: object) -> str | None:
    if category_code is None:
        return None
    if (
        not isinstance(category_code, str)
        or category_code not in NEWS_CATEGORIES
    ):
        raise ProviderValidationError(
            "新闻类别筛选不正确",
            details={"category_code": "不属于新闻类别"},
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


def _news_payload(row: sqlite3.Row) -> dict:
    category_code = str(row["category_code"])
    return {
        "id": str(row["id"]),
        "title": str(row["title"]),
        "content": str(row["content"]),
        "category_code": category_code,
        "category_label": NEWS_CATEGORIES[category_code],
        "view_count": int(row["view_count"]),
        "version": int(row["version"]),
        "published_at": str(row["published_at"]),
        "updated_at": str(row["updated_at"]),
    }
