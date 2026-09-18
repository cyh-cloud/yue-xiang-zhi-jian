from __future__ import annotations

from flask import Flask

from app.enterprise_console.jobs import (
    JOB_REVIEW_CONTENT_TYPE,
    JOB_REVIEW_STATUSES,
    JOB_TEXT_LIMITS,
    JOB_TRANSITIONS,
    create_job,
    edit_job,
    get_job,
    list_jobs,
    serialize_job,
    sync_job_review_projection,
)
from app.enterprise_console.providers import (
    DatabaseJobPositionProvider,
    EmptyJobApplicationIntakeProvider,
    get_job_application_intake_provider,
    get_job_position_provider,
    set_job_application_intake_provider,
    set_job_position_provider,
)
from app.enterprise_console.review import (
    ContentReviewProvider,
    UnavailableContentReviewProvider,
    get_content_review_provider,
    set_content_review_provider,
)


def install_default_enterprise_services(app: Flask) -> None:
    if "job_position_provider" not in app.extensions:
        set_job_position_provider(app, DatabaseJobPositionProvider())
    if "job_application_intake_provider" not in app.extensions:
        set_job_application_intake_provider(
            app,
            EmptyJobApplicationIntakeProvider(),
        )
    if "content_review_provider" not in app.extensions:
        set_content_review_provider(app, UnavailableContentReviewProvider())


__all__ = [
    "ContentReviewProvider",
    "JOB_REVIEW_CONTENT_TYPE",
    "JOB_REVIEW_STATUSES",
    "JOB_TEXT_LIMITS",
    "JOB_TRANSITIONS",
    "create_job",
    "edit_job",
    "get_content_review_provider",
    "get_job",
    "get_job_application_intake_provider",
    "get_job_position_provider",
    "install_default_enterprise_services",
    "list_jobs",
    "serialize_job",
    "set_job_application_intake_provider",
    "set_content_review_provider",
    "set_job_position_provider",
    "sync_job_review_projection",
]
