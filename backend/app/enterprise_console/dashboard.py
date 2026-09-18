from __future__ import annotations

from app.db import get_db
from app.enterprise_console.errors import EnterpriseValidationError
from app.enterprise_console.providers import (
    get_employment_statistics_provider,
)


def get_dashboard(enterprise_id: int) -> dict:
    if (
        isinstance(enterprise_id, bool)
        or not isinstance(enterprise_id, int)
        or enterprise_id <= 0
    ):
        raise EnterpriseValidationError("企业标识必须是正整数")
    db = get_db()
    active = db.execute(
        """
        SELECT COUNT(*) AS total
        FROM job_positions
        WHERE enterprise_id = ?
          AND review_status = 'approved'
          AND deleted_at IS NULL
          AND published_at IS NOT NULL
          AND trim(published_at) <> ''
        """,
        (enterprise_id,),
    ).fetchone()
    received = db.execute(
        """
        SELECT COUNT(*) AS total
        FROM job_applications
        WHERE enterprise_id = ?
        """,
        (enterprise_id,),
    ).fetchone()
    return {
        "active_job_count": int(active["total"]),
        "received_resume_count": int(received["total"]),
    }


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
