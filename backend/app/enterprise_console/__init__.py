from __future__ import annotations

from flask import Flask

from app.enterprise_console.applications import (
    APPLICATION_STATUSES,
    APPLICATION_SORTS,
    CLOSED_STATUS_LABEL,
    MANUAL_STATUSES,
    STATUS_LABELS,
    change_application_status,
    get_application,
    list_applications,
    record_application_submission,
    serialize_application,
)
from app.enterprise_console.dashboard import (
    get_dashboard,
    get_employment_statistics_snapshot,
)
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
from app.enterprise_console.messaging_provider import (
    EnterpriseMessagingProvider,
)
from app.enterprise_console.providers import (
    DatabaseJobApplicationIntakeProvider,
    DatabaseJobApplicationStatusProvider,
    DatabaseJobPositionProvider,
    DatabaseEmploymentStatisticsProvider,
    EmploymentStatisticsProvider,
    JobApplicationStatusProvider,
    get_employment_statistics_provider,
    get_job_application_intake_provider,
    get_job_application_status_provider,
    get_job_position_provider,
    set_employment_statistics_provider,
    set_job_application_intake_provider,
    set_job_application_status_provider,
    set_job_position_provider,
)
from app.enterprise_console.review import (
    ContentReviewProvider,
    UnavailableContentReviewProvider,
    get_content_review_provider,
    set_content_review_provider,
)
from app.enterprise_console.routes import (
    enterprise_console_bp,
    register_enterprise_console_error_handlers,
)
from app.enterprise_console.seed import (
    seed_enterprise_console_fixtures,
)


def install_default_enterprise_services(app: Flask) -> None:
    if "job_position_provider" not in app.extensions:
        set_job_position_provider(app, DatabaseJobPositionProvider())
    if "job_application_intake_provider" not in app.extensions:
        set_job_application_intake_provider(
            app,
            DatabaseJobApplicationIntakeProvider(),
        )
    if "job_application_status_provider" not in app.extensions:
        set_job_application_status_provider(
            app,
            DatabaseJobApplicationStatusProvider(),
        )
    if "content_review_provider" not in app.extensions:
        set_content_review_provider(app, UnavailableContentReviewProvider())
    if "government_employment_statistics_provider" not in app.extensions:
        set_employment_statistics_provider(
            app,
            DatabaseEmploymentStatisticsProvider(),
        )


__all__ = [
    "APPLICATION_STATUSES",
    "APPLICATION_SORTS",
    "CLOSED_STATUS_LABEL",
    "ContentReviewProvider",
    "DatabaseJobApplicationIntakeProvider",
    "DatabaseJobApplicationStatusProvider",
    "DatabaseEmploymentStatisticsProvider",
    "EmploymentStatisticsProvider",
    "EnterpriseMessagingProvider",
    "JobApplicationStatusProvider",
    "JOB_REVIEW_CONTENT_TYPE",
    "JOB_REVIEW_STATUSES",
    "JOB_TEXT_LIMITS",
    "JOB_TRANSITIONS",
    "MANUAL_STATUSES",
    "STATUS_LABELS",
    "change_application_status",
    "create_job",
    "edit_job",
    "enterprise_console_bp",
    "get_application",
    "get_content_review_provider",
    "get_dashboard",
    "get_employment_statistics_provider",
    "get_employment_statistics_snapshot",
    "get_job",
    "get_job_application_intake_provider",
    "get_job_application_status_provider",
    "get_job_position_provider",
    "install_default_enterprise_services",
    "list_applications",
    "list_jobs",
    "record_application_submission",
    "register_enterprise_console_error_handlers",
    "serialize_job",
    "serialize_application",
    "seed_enterprise_console_fixtures",
    "set_job_application_intake_provider",
    "set_job_application_status_provider",
    "set_content_review_provider",
    "set_employment_statistics_provider",
    "set_job_position_provider",
    "sync_job_review_projection",
]
