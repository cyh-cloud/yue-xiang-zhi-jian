from __future__ import annotations

from flask import Blueprint, Flask


job_matching_bp = Blueprint(
    "job_matching",
    __name__,
    url_prefix="/api/job-matching",
)


def install_default_job_matching_services(app: Flask) -> None:
    """Install job-matching service dependencies."""
