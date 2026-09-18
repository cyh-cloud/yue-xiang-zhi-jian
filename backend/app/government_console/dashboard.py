from __future__ import annotations

from collections.abc import Iterator

from app.db import get_db
from app.government_console.providers import (
    get_employment_statistics_provider,
)


FORBIDDEN_DASHBOARD_KEYS = frozenset(
    {
        "total_users",
        "role_distribution",
        "region_distribution",
        "direction_distribution",
        "user_details",
        "course_count",
        "learning_behavior_count",
        "progress",
        "completion_rate",
        "certificate_count",
    }
)


def walk_keys(value: object) -> Iterator[str]:
    if isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from walk_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_keys(child)


def assert_dashboard_boundary(dashboard: dict) -> None:
    forbidden = FORBIDDEN_DASHBOARD_KEYS.intersection(walk_keys(dashboard))
    if forbidden:
        raise AssertionError(
            "Government dashboard contains forbidden keys: "
            + ", ".join(sorted(forbidden))
        )


def get_government_dashboard() -> dict:
    db = get_db()
    policy = db.execute(
        """
        SELECT
            SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) AS active_count,
            SUM(CASE WHEN status = 'unpublished' THEN 1 ELSE 0 END) AS unpublished_count,
            COALESCE(SUM(view_count), 0) AS view_count
        FROM government_policies
        """
    ).fetchone()
    news = db.execute(
        """
        SELECT COUNT(*) AS total_count, COALESCE(SUM(view_count), 0) AS view_count
        FROM government_news
        """
    ).fetchone()
    provider = get_employment_statistics_provider()
    active_jobs = provider.get_active_job_count()
    applications = provider.get_cumulative_application_count()
    return {
        "employment": {
            "active_job_count": active_jobs,
            "cumulative_application_count": applications,
            "available": active_jobs is not None and applications is not None,
        },
        "policy": {
            "active_count": int(policy["active_count"] or 0),
            "unpublished_count": int(policy["unpublished_count"] or 0),
            "total_count": int(policy["active_count"] or 0)
            + int(policy["unpublished_count"] or 0),
            "view_count": int(policy["view_count"] or 0),
        },
        "news": {
            "total_count": int(news["total_count"] or 0),
            "view_count": int(news["view_count"] or 0),
        },
    }
