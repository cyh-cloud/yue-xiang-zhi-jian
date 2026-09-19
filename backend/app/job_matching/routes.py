from __future__ import annotations

from flask import Blueprint, Flask, jsonify, request

from app.agri_skills.errors import AiUnavailableError
from app.db import get_db
from app.enterprise_console.errors import ProviderUnavailableError
from app.job_matching.applications import (
    get_my_application,
    list_my_applications,
    submit_job_application,
)
from app.job_matching.constants import AI_UNAVAILABLE_MESSAGE
from app.job_matching.errors import (
    AlreadyAppliedError,
    JobMatchingValidationError,
    JobUnavailableError,
    ResumeConflictError,
    ResumeRequiredError,
)
from app.job_matching.favorites import (
    add_favorite,
    list_favorites,
    remove_favorite,
)
from app.job_matching.jobs import (
    get_published_job,
    list_published_jobs,
)
from app.job_matching.resume_ai import (
    adopt_resume_optimization,
    discard_resume_optimization,
    optimize_resume,
)
from app.job_matching.resumes import get_resume, save_resume
from app.job_matching.skill_profile import (
    get_skill_profile,
    set_skill_visibility,
)
from app.session_manager import abort_session_required, load_session


RESUME_PAYLOAD_FIELDS = (
    "education_experiences",
    "work_experiences",
    "skills",
)

job_matching_bp = Blueprint(
    "job_matching",
    __name__,
    url_prefix="/api/job-matching",
)


def _student_session() -> dict:
    session = load_session(required=True, allowed_states={"active"})
    if session["role"] != "student":
        abort_session_required()
    db = get_db()
    if db.in_transaction:
        db.commit()
    return session


def _json_object_payload() -> dict:
    payload = request.get_json(silent=True)
    if payload is None:
        if request.get_data(cache=True):
            raise JobMatchingValidationError(
                "请求体格式不正确",
                details={"body": "请求体必须是 JSON 对象"},
            )
        return {}
    if not isinstance(payload, dict):
        raise JobMatchingValidationError(
            "请求体格式不正确",
            details={"body": "请求体必须是 JSON 对象"},
        )
    return payload


def _expected_version(payload: dict) -> int:
    expected_version = payload.get("expected_version")
    if (
        not isinstance(expected_version, int)
        or isinstance(expected_version, bool)
    ):
        raise JobMatchingValidationError(
            "expected_version 格式不正确",
            details={"expected_version": "必须是整数"},
        )
    return expected_version


def _handle_validation(error: JobMatchingValidationError):
    return jsonify(
        success=False,
        code=error.code,
        message=error.message,
        errors=error.details,
    ), 400


def _handle_resume_conflict(error: ResumeConflictError):
    return jsonify(
        success=False,
        code=error.code,
        message=error.message,
        errors=error.details,
    ), 409


def _handle_resume_required(error: ResumeRequiredError):
    return jsonify(
        success=False,
        code=error.code,
        message="请先创建并保存简历",
        errors=error.details,
    ), 409


def _handle_already_applied(error: AlreadyAppliedError):
    return jsonify(
        success=False,
        code=error.code,
        message="已投递该岗位",
        errors=error.details,
    ), 409


def _handle_job_unavailable(error: JobUnavailableError):
    return jsonify(
        success=False,
        code=error.code,
        message="岗位已关闭或暂不可投递",
        errors=error.details,
    ), 409


@job_matching_bp.errorhandler(AiUnavailableError)
def _handle_ai_unavailable(_error: AiUnavailableError):
    return jsonify(
        success=False,
        code="ai_unavailable",
        message=AI_UNAVAILABLE_MESSAGE,
        errors={},
    ), 503


@job_matching_bp.errorhandler(ProviderUnavailableError)
def _handle_provider_unavailable(_error: ProviderUnavailableError):
    return jsonify(
        success=False,
        code="provider_unavailable",
        message="就业服务暂时不可用",
        errors={},
    ), 503


def register_job_matching_error_handlers(app: Flask) -> None:
    app.register_error_handler(
        JobMatchingValidationError,
        _handle_validation,
    )
    app.register_error_handler(ResumeConflictError, _handle_resume_conflict)
    app.register_error_handler(ResumeRequiredError, _handle_resume_required)
    app.register_error_handler(AlreadyAppliedError, _handle_already_applied)
    app.register_error_handler(JobUnavailableError, _handle_job_unavailable)


@job_matching_bp.get("/resume")
def get_resume_route():
    session = _student_session()
    return jsonify(
        success=True,
        resume=get_resume(int(session["id"])),
    )


@job_matching_bp.put("/resume")
def save_resume_route():
    session = _student_session()
    payload = _json_object_payload()
    resume = save_resume(
        int(session["id"]),
        {
            field: payload.get(field)
            for field in RESUME_PAYLOAD_FIELDS
        },
        _expected_version(payload),
    )
    return jsonify(success=True, resume=resume)


@job_matching_bp.post("/resume/optimize")
def optimize_resume_route():
    session = _student_session()
    payload = _json_object_payload()
    offer = optimize_resume(
        int(session["id"]),
        _expected_version(payload),
    )
    return jsonify(success=True, offer=offer)


@job_matching_bp.post(
    "/resume/optimizations/<offer_id>/adopt"
)
def adopt_resume_optimization_route(offer_id: str):
    session = _student_session()
    payload = _json_object_payload()
    resume = adopt_resume_optimization(
        int(session["id"]),
        offer_id,
        _expected_version(payload),
    )
    return jsonify(success=True, resume=resume)


@job_matching_bp.post(
    "/resume/optimizations/<offer_id>/discard"
)
def discard_resume_optimization_route(offer_id: str):
    session = _student_session()
    offer = discard_resume_optimization(
        int(session["id"]),
        offer_id,
    )
    return jsonify(success=True, offer=offer)


@job_matching_bp.get("/skill-profile")
def get_skill_profile_route():
    session = _student_session()
    return jsonify(
        success=True,
        profile=get_skill_profile(int(session["id"])),
    )


@job_matching_bp.put("/skill-profile/visibility")
def set_skill_visibility_route():
    session = _student_session()
    payload = _json_object_payload()
    profile = set_skill_visibility(
        int(session["id"]),
        payload.get("visible_item_ids"),
    )
    return jsonify(success=True, profile=profile)


@job_matching_bp.get("/jobs")
def list_jobs_route():
    session = _student_session()
    result = list_published_jobs(int(session["id"]))
    return jsonify(success=True, **result)


@job_matching_bp.get("/jobs/<job_id>")
def get_job_route(job_id: str):
    session = _student_session()
    job = get_published_job(int(session["id"]), job_id)
    if job is None:
        return jsonify(
            success=False,
            code="job_unavailable",
            message="岗位已关闭或暂不可投递",
            errors={},
        ), 404
    return jsonify(success=True, job=job)


@job_matching_bp.post("/jobs/<job_id>/applications")
def submit_application_route(job_id: str):
    session = _student_session()
    payload = _json_object_payload()
    application = submit_job_application(
        int(session["id"]),
        job_id,
        bool(payload.get("attach_skill_profile", False)),
    )
    return jsonify(success=True, application=application), 201


@job_matching_bp.get("/applications")
def list_applications_route():
    session = _student_session()
    return jsonify(
        success=True,
        applications=list_my_applications(int(session["id"])),
    )


@job_matching_bp.get("/applications/<application_id>")
def get_application_route(application_id: str):
    session = _student_session()
    application = get_my_application(
        int(session["id"]),
        application_id,
    )
    if application is None:
        return jsonify(
            success=False,
            code="application_not_found",
            message="申请不存在",
            errors={},
        ), 404
    return jsonify(success=True, application=application)


@job_matching_bp.get("/favorites")
def list_favorites_route():
    session = _student_session()
    return jsonify(
        success=True,
        favorites=list_favorites(int(session["id"])),
    )


@job_matching_bp.post("/favorites/<job_id>")
def add_favorite_route(job_id: str):
    session = _student_session()
    return jsonify(
        success=True,
        favorite=add_favorite(int(session["id"]), job_id),
    )


@job_matching_bp.delete("/favorites/<job_id>")
def remove_favorite_route(job_id: str):
    session = _student_session()
    return jsonify(
        success=True,
        favorite=remove_favorite(int(session["id"]), job_id),
    )


__all__ = [
    "job_matching_bp",
    "register_job_matching_error_handlers",
]
