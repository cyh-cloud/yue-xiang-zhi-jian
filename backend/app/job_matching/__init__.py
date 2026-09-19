from __future__ import annotations

from flask import Flask

from app.job_matching.routes import (
    job_matching_bp,
    register_job_matching_error_handlers,
)


def install_default_job_matching_services(app: Flask) -> None:
    """Install job-matching services.

    Job matching uses stateless domain services and the 09-owned provider
    registry, so there are no package-local dependencies to register.
    """


__all__ = [
    "install_default_job_matching_services",
    "job_matching_bp",
    "register_job_matching_error_handlers",
]
