from __future__ import annotations

import sqlite3
from collections.abc import Callable, Iterator
from typing import TypeVar

from app.db import get_db
from app.enterprise_console.providers import (
    get_employment_statistics_provider,
)


FORBIDDEN_ADMIN_DASHBOARD_KEYS = frozenset(
    {
        "total_users",
        "role_distribution",
        "student_total",
        "student_count",
        "user_details",
        "average_progress",
        "completion_rate",
        "quiz_attempt_count",
        "quiz_average_score",
        "training_progress",
        "learning_behavior_count",
    }
)

ROLE_KEYS = (
    "student",
    "teacher",
    "enterprise",
    "government",
    "admin",
    "super_admin",
)

_T = TypeVar("_T")


def _unavailable() -> dict:
    return {"available": False, "value": None}


def _safe_metric(operation: Callable[[], _T]) -> _T | dict:
    try:
        return operation()
    except (sqlite3.Error, RuntimeError):
        return _unavailable()


def _scalar_count(sql: str, parameters: tuple = ()) -> int:
    row = get_db().execute(sql, parameters).fetchone()
    return int(row[0])


def _pending_count(content_type: str) -> int | dict:
    return _safe_metric(
        lambda: _scalar_count(
            """
            SELECT COUNT(*)
            FROM content_review_records
            WHERE content_type = ? AND review_status = 'pending'
            """,
            (content_type,),
        )
    )


def _published_course_count() -> int | dict:
    return _safe_metric(
        lambda: _scalar_count(
            """
            SELECT COUNT(*)
            FROM courses
            WHERE status = 'published'
            """
        )
    )


def _active_job_count() -> int | dict:
    def load_count() -> int | dict:
        value = get_employment_statistics_provider().get_active_job_count()
        if value is None:
            return _unavailable()
        return int(value)

    return _safe_metric(load_count)


def _processed_comment_count() -> int | dict:
    return _safe_metric(
        lambda: _scalar_count(
            "SELECT COUNT(*) FROM content_comments WHERE is_visible = 0"
        )
    )


def _processed_report_count() -> int | dict:
    return _safe_metric(
        lambda: _scalar_count(
            """
            SELECT COUNT(*)
            FROM comment_reports
            WHERE status IN ('confirmed', 'rejected')
            """
        )
    )


def _processed_feedback_count() -> int | dict:
    return _safe_metric(
        lambda: _scalar_count(
            """
            SELECT COUNT(*)
            FROM feedback_records
            WHERE status IN ('processed', 'closed')
            """
        )
    )


def _reward_stock_total() -> int | dict:
    return _safe_metric(
        lambda: _scalar_count(
            "SELECT COALESCE(SUM(stock), 0) FROM admin_rewards"
        )
    )


def _pending_fulfillment_count() -> int | dict:
    return _safe_metric(
        lambda: _scalar_count(
            "SELECT COUNT(*) FROM fulfillments WHERE status = 'pending'"
        )
    )


def _user_metrics() -> dict:
    def load_metrics() -> dict:
        rows = get_db().execute(
            """
            SELECT role, COUNT(*) AS total
            FROM users
            GROUP BY role
            """
        ).fetchall()
        counts = {role: 0 for role in ROLE_KEYS}
        for row in rows:
            role = str(row["role"])
            if role in counts:
                counts[role] = int(row["total"])
        return {
            "total_users": sum(counts.values()),
            "role_distribution": counts,
            "student_count": counts["student"],
        }

    result = _safe_metric(load_metrics)
    if "available" in result:
        return {
            "total_users": result,
            "role_distribution": dict(result),
            "student_count": dict(result),
        }
    return result


def _policy_metrics() -> dict:
    def load_metrics() -> dict:
        row = get_db().execute(
            """
            SELECT COUNT(*) AS total_count,
                   COALESCE(SUM(view_count), 0) AS view_count
            FROM government_policies
            """
        ).fetchone()
        return {
            "policy_count": int(row["total_count"]),
            "policy_view_count": int(row["view_count"]),
        }

    result = _safe_metric(load_metrics)
    if "available" in result:
        return {
            "policy_count": result,
            "policy_view_count": dict(result),
        }
    return result


def _news_metrics() -> dict:
    def load_metrics() -> dict:
        row = get_db().execute(
            """
            SELECT COUNT(*) AS total_count,
                   COALESCE(SUM(view_count), 0) AS view_count
            FROM government_news
            """
        ).fetchone()
        return {
            "news_count": int(row["total_count"]),
            "news_view_count": int(row["view_count"]),
        }

    result = _safe_metric(load_metrics)
    if "available" in result:
        return {
            "news_count": result,
            "news_view_count": dict(result),
        }
    return result


def _points_issued() -> int | dict:
    return _safe_metric(
        lambda: _scalar_count(
            """
            SELECT COALESCE(SUM(delta), 0)
            FROM points_transactions
            WHERE transaction_type = 'award'
            """
        )
    )


def _redemption_count() -> int | dict:
    return _safe_metric(
        lambda: _scalar_count("SELECT COUNT(*) FROM redemptions")
    )


def walk_keys(value: object) -> Iterator[str]:
    if isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from walk_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_keys(child)


def assert_admin_dashboard_boundary(dashboard: dict) -> None:
    forbidden = FORBIDDEN_ADMIN_DASHBOARD_KEYS.intersection(
        walk_keys(dashboard)
    )
    if forbidden:
        raise AssertionError(
            "Content operations dashboard contains forbidden keys: "
            + ", ".join(sorted(forbidden))
        )


def get_content_operations_dashboard() -> dict:
    dashboard = {
        "pending_review": {
            "course_video": _pending_count("course_video"),
            "job_position": _pending_count("job_position"),
            "handcraft_teaching_video": _pending_count(
                "handcraft_teaching_video"
            ),
        },
        "published_course_count": _published_course_count(),
        "active_job_count": _active_job_count(),
        "comment_processed_count": _processed_comment_count(),
        "report_processed_count": _processed_report_count(),
        "feedback_processed_count": _processed_feedback_count(),
        "reward_stock": _reward_stock_total(),
        "pending_fulfillment_count": _pending_fulfillment_count(),
    }
    assert_admin_dashboard_boundary(dashboard)
    return dashboard


def get_super_admin_dashboard() -> dict:
    dashboard = get_content_operations_dashboard()
    dashboard.update(_user_metrics())
    dashboard.update(_policy_metrics())
    dashboard.update(_news_metrics())
    dashboard["points_issued"] = _points_issued()
    dashboard["redemption_count"] = _redemption_count()
    return dashboard


__all__ = [
    "FORBIDDEN_ADMIN_DASHBOARD_KEYS",
    "assert_admin_dashboard_boundary",
    "get_content_operations_dashboard",
    "get_super_admin_dashboard",
    "walk_keys",
]
