from __future__ import annotations

from app.db import get_db
from app.enterprise_console.providers import (
    get_employment_statistics_provider,
)


def get_platform_active_job_count() -> int:
    row = get_db().execute(
        """
        SELECT COUNT(*) AS total
        FROM job_positions
        WHERE review_status = 'approved'
          AND deleted_at IS NULL
          AND published_at IS NOT NULL
          AND trim(published_at) <> ''
        """
    ).fetchone()
    return int(row["total"])


def get_platform_cumulative_application_count() -> int:
    row = get_db().execute(
        "SELECT COUNT(*) AS total FROM job_applications"
    ).fetchone()
    return int(row["total"])


def get_employment_statistics_snapshot() -> dict:
    provider = get_employment_statistics_provider()
    active = provider.get_active_job_count()
    applications = provider.get_cumulative_application_count()
    return {
        "active_job_count": active,
        "cumulative_application_count": applications,
        "available": active is not None and applications is not None,
    }
