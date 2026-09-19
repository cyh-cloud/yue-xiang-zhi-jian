from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.enterprise_console.providers import get_job_position_provider
from app.job_matching.errors import JobUnavailableError
from app.job_matching.skill_profile import list_skill_outcomes
from app.profiles.service import get_profile_preferences


JOB_FIELDS = (
    "job_id",
    "enterprise_id",
    "enterprise_name",
    "title",
    "salary",
    "location",
    "category_id",
    "category_name",
    "description",
    "review_status",
    "version",
    "published_at",
    "updated_at",
)

_PLATFORM_TIMEZONE = ZoneInfo("Asia/Shanghai")
_RECENT_LEARNING_WINDOW = timedelta(days=90)


def _parse_iso(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("ISO 8601 timestamps must include a timezone")
    return parsed


def _project_job(job: dict) -> dict:
    if not isinstance(job, dict):
        raise JobUnavailableError("岗位数据不可用")
    missing = [field for field in JOB_FIELDS if field not in job]
    if missing:
        raise JobUnavailableError(
            "岗位数据字段不完整",
            details={"missing": missing},
        )
    return {field: job[field] for field in JOB_FIELDS}


def _recommend_jobs(student_id: int, jobs: list[dict]) -> list[dict]:
    preferences = get_profile_preferences(student_id)
    job_tag_ids = set(preferences["interest_tag_ids"])
    outcomes = list_skill_outcomes(student_id)
    cutoff = datetime.now(_PLATFORM_TIMEZONE) - _RECENT_LEARNING_WINDOW
    recent = [
        outcome
        for outcome in outcomes
        if _parse_iso(outcome["occurred_at"]) >= cutoff
    ]
    latest_outcome = max(
        recent,
        key=lambda outcome: _parse_iso(outcome["occurred_at"]),
        default=None,
    )
    latest_learning_at = (
        latest_outcome["occurred_at"]
        if latest_outcome is not None
        else None
    )

    candidates = []
    for job in jobs:
        match_count = int(job["category_id"] in job_tag_ids)
        candidates.append(
            {
                **job,
                "category_match_count": match_count,
                "recent_learning": bool(recent),
                "latest_learning_at": latest_learning_at,
            }
        )

    candidates.sort(
        key=lambda job: (
            0 if job["category_match_count"] else 1,
            0 if job["recent_learning"] else 1,
            -(
                int(
                    _parse_iso(
                        job["latest_learning_at"]
                    ).timestamp()
                )
                if job["latest_learning_at"]
                else 0
            ),
            -int(_parse_iso(job["published_at"]).timestamp()),
            str(job["job_id"]),
        )
    )
    return candidates


def list_published_jobs(student_id: int) -> dict:
    jobs = [
        _project_job(job)
        for job in get_job_position_provider().list_published_positions()
    ]
    jobs.sort(
        key=lambda job: (
            _parse_iso(job["published_at"]),
            str(job["job_id"]),
        )
    )
    jobs.sort(
        key=lambda job: _parse_iso(job["published_at"]),
        reverse=True,
    )
    return {
        "jobs": jobs,
        "recommended_jobs": _recommend_jobs(student_id, jobs),
    }


def get_published_job(
    student_id: int,
    job_id: str,
) -> dict | None:
    job = get_job_position_provider().get_published_position(
        job_id=job_id
    )
    if job is None:
        return None
    return _project_job(job)


__all__ = [
    "JOB_FIELDS",
    "get_published_job",
    "list_published_jobs",
]
