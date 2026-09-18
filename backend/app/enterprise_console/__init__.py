from __future__ import annotations

from flask import Flask

from app.enterprise_console.providers import (
    EmptyJobApplicationIntakeProvider,
    EmptyJobPositionProvider,
    get_job_application_intake_provider,
    get_job_position_provider,
    set_job_application_intake_provider,
    set_job_position_provider,
)
from app.enterprise_console.review import (
    UnavailableContentReviewProvider,
    get_content_review_provider,
    set_content_review_provider,
)


def install_default_enterprise_services(app: Flask) -> None:
    if "job_position_provider" not in app.extensions:
        set_job_position_provider(app, EmptyJobPositionProvider())
    if "job_application_intake_provider" not in app.extensions:
        set_job_application_intake_provider(
            app,
            EmptyJobApplicationIntakeProvider(),
        )
    if "content_review_provider" not in app.extensions:
        set_content_review_provider(app, UnavailableContentReviewProvider())


__all__ = [
    "get_content_review_provider",
    "get_job_application_intake_provider",
    "get_job_position_provider",
    "install_default_enterprise_services",
    "set_job_application_intake_provider",
    "set_content_review_provider",
    "set_job_position_provider",
]
