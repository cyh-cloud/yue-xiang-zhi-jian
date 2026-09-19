from __future__ import annotations

import sqlite3
from datetime import date

from flask import Blueprint, Flask, jsonify, request

from app.db import get_db
from app.enterprise_console.applications import (
    change_application_status as _change_application_status,
)
from app.enterprise_console.applications import (
    get_application as _get_application,
)
from app.enterprise_console.applications import (
    list_applications as _list_applications,
)
from app.enterprise_console.dashboard import (
    get_dashboard as _get_dashboard,
)
from app.enterprise_console.errors import (
    EnterpriseConflictError,
    EnterpriseNotFoundError,
    EnterpriseValidationError,
    ProviderAccessDeniedError,
    ProviderConflictError,
    ProviderError,
    ProviderNotFoundError,
    ProviderUnavailableError,
    ProviderValidationError,
)
from app.enterprise_console.jobs import create_job as _create_job
from app.enterprise_console.jobs import delete_job as _delete_job
from app.enterprise_console.jobs import edit_job as _edit_job
from app.enterprise_console.jobs import get_job as _get_job
from app.enterprise_console.jobs import list_jobs as _list_jobs
from app.enterprise_console.jobs import (
    sync_job_review_projection as _sync_job_review_projection,
)
from app.session_manager import abort_session_required, load_session


JOB_PAYLOAD_FIELDS = (
    "title",
    "salary",
    "location",
    "category_id",
    "description",
)

enterprise_console_bp = Blueprint(
    "enterprise_console",
    __name__,
    url_prefix="/api/enterprise",
)


def _enterprise_session() -> dict:
    session = load_session(required=True, allowed_states={"active"})
    if session["role"] != "enterprise":
        abort_session_required()
    get_db().commit()
    return session


def _json_object_payload() -> dict:
    payload = request.get_json(silent=True)
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise EnterpriseValidationError(
            "请求体格式不正确",
            details={"body": "请求体必须是 JSON 对象"},
        )
    return payload


def _editable_job_payload(payload: dict) -> dict:
    return {
        field: payload.get(field)
        for field in JOB_PAYLOAD_FIELDS
    }


def _optional_query(name: str) -> str | None:
    value = request.args.get(name)
    if value is None:
        return None
    value = value.strip()
    return value or None


def _query_date(name: str) -> date | None:
    value = _optional_query(name)
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise EnterpriseValidationError(
            "筛选日期格式不正确",
            details={name: "日期必须使用 YYYY-MM-DD"},
        ) from error


def _error_response(message: str, errors: dict):
    return jsonify(
        success=False,
        message=message,
        errors=errors,
    )


def _handle_validation(
    error: EnterpriseValidationError | ProviderValidationError,
):
    return _error_response(error.message, error.details), 400


def _handle_not_found(
    error: EnterpriseNotFoundError | ProviderNotFoundError,
):
    return _error_response(error.message, error.details), 404


def _handle_access_denied(error: ProviderAccessDeniedError):
    return _error_response(error.message, error.details), 403


def _handle_conflict(
    error: EnterpriseConflictError | ProviderConflictError,
):
    return _error_response(error.message, error.details), 409


def _handle_unavailable(error: ProviderUnavailableError | ProviderError):
    return _error_response(error.message, error.details), 503


def _handle_database_unavailable(_error: sqlite3.Error):
    return _error_response("企业数据暂不可用", {}), 503


def register_enterprise_console_error_handlers(app: Flask) -> None:
    app.register_error_handler(
        EnterpriseValidationError,
        _handle_validation,
    )
    app.register_error_handler(
        ProviderValidationError,
        _handle_validation,
    )
    app.register_error_handler(
        EnterpriseNotFoundError,
        _handle_not_found,
    )
    app.register_error_handler(
        ProviderNotFoundError,
        _handle_not_found,
    )
    app.register_error_handler(
        ProviderAccessDeniedError,
        _handle_access_denied,
    )
    app.register_error_handler(
        EnterpriseConflictError,
        _handle_conflict,
    )
    app.register_error_handler(
        ProviderConflictError,
        _handle_conflict,
    )
    app.register_error_handler(
        ProviderUnavailableError,
        _handle_unavailable,
    )
    app.register_error_handler(ProviderError, _handle_unavailable)
    app.register_error_handler(
        sqlite3.Error,
        _handle_database_unavailable,
    )


@enterprise_console_bp.get("/dashboard")
def get_dashboard_route():
    session = _enterprise_session()
    dashboard = _get_dashboard(int(session["id"]))
    return jsonify(success=True, dashboard=dashboard)


@enterprise_console_bp.get("/jobs")
def list_jobs_route():
    session = _enterprise_session()
    review_status = _optional_query("review_status")
    if review_status == "all":
        review_status = None
    jobs = _list_jobs(int(session["id"]), review_status)
    return jsonify(success=True, jobs=jobs)


@enterprise_console_bp.post("/jobs")
def create_job_route():
    session = _enterprise_session()
    payload = _json_object_payload()
    job = _create_job(
        int(session["id"]),
        _editable_job_payload(payload),
    )
    return jsonify(success=True, job=job), 201


@enterprise_console_bp.get("/jobs/<job_id>")
def get_job_route(job_id: str):
    session = _enterprise_session()
    enterprise_id = int(session["id"])
    _get_job(enterprise_id, job_id)
    _sync_job_review_projection(job_id)
    job = _get_job(enterprise_id, job_id)
    return jsonify(success=True, job=job)


@enterprise_console_bp.put("/jobs/<job_id>")
def edit_job_route(job_id: str):
    session = _enterprise_session()
    payload = _json_object_payload()
    job = _edit_job(
        int(session["id"]),
        job_id,
        payload.get("expected_version"),
        _editable_job_payload(payload),
    )
    return jsonify(success=True, job=job)


@enterprise_console_bp.delete("/jobs/<job_id>")
def delete_job_route(job_id: str):
    session = _enterprise_session()
    payload = _json_object_payload()
    expected_version = payload.get("expected_version")
    if expected_version is None:
        deleted = _delete_job(int(session["id"]), job_id)
    else:
        deleted = _delete_job(
            int(session["id"]),
            job_id,
            expected_version=expected_version,
        )
    return jsonify(success=True, deleted=deleted)


@enterprise_console_bp.get("/applications")
def list_applications_route():
    session = _enterprise_session()
    filters = {}
    for name in ("job_id", "status", "sort"):
        value = _optional_query(name)
        if value is not None:
            filters[name] = value
    for name in ("submitted_from", "submitted_to"):
        value = _query_date(name)
        if value is not None:
            filters[name] = value
    applications = _list_applications(int(session["id"]), filters)
    return jsonify(success=True, applications=applications)


@enterprise_console_bp.get(
    "/applications/<application_id>"
)
def get_application_route(application_id: str):
    session = _enterprise_session()
    application = _get_application(
        int(session["id"]),
        application_id,
    )
    return jsonify(success=True, application=application)


@enterprise_console_bp.patch(
    "/applications/<application_id>/status"
)
def change_application_status_route(application_id: str):
    session = _enterprise_session()
    payload = _json_object_payload()
    result = _change_application_status(
        int(session["id"]),
        application_id,
        payload.get("expected_version"),
        payload.get("status"),
    )
    return jsonify(
        success=True,
        application=result["application"],
        changed=result["changed"],
    )


__all__ = [
    "enterprise_console_bp",
    "register_enterprise_console_error_handlers",
]
