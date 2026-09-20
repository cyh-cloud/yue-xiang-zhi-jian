from __future__ import annotations

from app.enterprise_console.providers import (
    get_job_application_intake_provider,
    get_job_application_status_provider,
)
from app.job_matching.constants import APPLICATION_LABELS
from app.job_matching.errors import AlreadyAppliedError, JobUnavailableError
from app.job_matching.jobs import get_published_job
from app.job_matching.resumes import build_resume_snapshot
from app.job_matching.skill_profile import build_skill_profile_snapshot


_CLOSED_LABEL = APPLICATION_LABELS["closed"]


def submit_job_application(
    student_id: int,
    job_id: str,
    attach_skill_profile: bool,
) -> dict:
    if get_published_job(student_id, job_id) is None:
        raise JobUnavailableError("岗位已关闭或暂不可投递")

    resume_snapshot = build_resume_snapshot(student_id)
    applications = list_my_applications(student_id)
    if any(item["job_id"] == job_id for item in applications):
        raise AlreadyAppliedError("已投递该岗位")

    skill_profile_snapshot = (
        build_skill_profile_snapshot(student_id)
        if attach_skill_profile
        else None
    )
    applications = list_my_applications(student_id)
    if any(item["job_id"] == job_id for item in applications):
        raise AlreadyAppliedError("已投递该岗位")

    return get_job_application_intake_provider().submit_application(
        job_id=job_id,
        student_id=student_id,
        resume_snapshot=resume_snapshot,
        skill_profile_snapshot=skill_profile_snapshot,
        idempotency_key=f"007:{student_id}:{job_id}",
    )


def list_my_applications(student_id: int) -> list[dict]:
    records = get_job_application_status_provider().list_student_applications(
        student_id=student_id
    )
    return [_normalize_application(record) for record in records]


def get_my_application(
    student_id: int,
    application_id: str,
) -> dict | None:
    record = get_job_application_status_provider().get_student_application(
        student_id=student_id,
        application_id=application_id,
    )
    return _normalize_application(record) if record else None


def _normalize_application(record: dict) -> dict:
    status = str(record["effective_status"])
    return {
        **record,
        "status_label": (
            _CLOSED_LABEL
            if status == "closed"
            else APPLICATION_LABELS.get(status, status)
        ),
        "show_closed_marker": bool(record["position_closed"]),
    }


__all__ = [
    "get_my_application",
    "list_my_applications",
    "submit_job_application",
]
