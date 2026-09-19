from __future__ import annotations

import sqlite3

from app.db import get_db
from app.government_console.errors import (
    ProviderNotFoundError,
    ProviderValidationError,
)
from app.government_console.policy import shanghai_now_iso


def record_policy_view(policy_id: str, view_event_id: str) -> int:
    return _record_view(
        content_type="policy",
        content_id=policy_id,
        event_id=view_event_id,
        update_sql="""
            UPDATE government_policies
            SET view_count = view_count + 1, updated_at = ?
            WHERE id = ? AND status = 'active'
        """,
        lookup_sql="""
            SELECT view_count
            FROM government_policies
            WHERE id = ? AND status = 'active'
        """,
    )


def record_news_view(news_id: str, view_event_id: str) -> int:
    return _record_view(
        content_type="news",
        content_id=news_id,
        event_id=view_event_id,
        update_sql="""
            UPDATE government_news
            SET view_count = view_count + 1, updated_at = ?
            WHERE id = ?
        """,
        lookup_sql="""
            SELECT view_count
            FROM government_news
            WHERE id = ?
        """,
    )


def _record_view(
    *,
    content_type: str,
    content_id: str,
    event_id: str,
    update_sql: str,
    lookup_sql: str,
) -> int:
    if not isinstance(event_id, str) or not event_id.strip():
        raise ProviderValidationError("浏览事件标识不能为空")

    db = get_db()
    try:
        db.execute(
            """
            INSERT INTO government_view_events (
                content_type, content_id, view_event_id, created_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                content_type,
                content_id,
                event_id.strip(),
                shanghai_now_iso(),
            ),
        )
    except sqlite3.IntegrityError:
        row = db.execute(lookup_sql, (content_id,)).fetchone()
        db.rollback()
        if row is None:
            raise ProviderNotFoundError("内容不存在") from None
        return int(row["view_count"])

    result = db.execute(
        update_sql,
        (shanghai_now_iso(), content_id),
    )
    if result.rowcount != 1:
        db.rollback()
        raise ProviderNotFoundError("内容不存在或不可见")

    row = db.execute(lookup_sql, (content_id,)).fetchone()
    db.commit()
    return int(row["view_count"])
