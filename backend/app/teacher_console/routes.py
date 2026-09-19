from __future__ import annotations

from flask import (
    Blueprint,
    Flask,
    current_app,
    jsonify,
    request,
    send_file,
)

from app.session_manager import abort_session_required, load_session
from app.teacher_console.announcements import (
    list_teaching_announcements,
    publish_teaching_announcement,
)
from app.teacher_console.comments import (
    list_teacher_comments,
    reply_to_comment,
)
from app.teacher_console.course_service import (
    create_teacher_course,
    edit_course,
    get_teacher_course,
    list_teacher_courses,
    request_course_relist,
    set_course_offline,
    submit_course_for_review,
    update_teacher_course_draft,
)
from app.teacher_console.dashboard import build_teacher_dashboard
from app.teacher_console.errors import (
    ProviderAccessDeniedError,
    ProviderConflictError,
    ProviderNotFoundError,
    ProviderUnavailableError,
    ProviderValidationError,
)
from app.teacher_console.media import course_media_path, save_course_video
from app.teacher_console.quiz import (
    generate_course_quiz,
    get_teacher_course_quiz,
    save_course_quiz,
)
from app.teacher_console.reports import (
    generate_teacher_report,
    get_teacher_report,
    list_teacher_reports,
)


teacher_console_bp = Blueprint(
    "teacher_console",
    __name__,
    url_prefix="/api/teacher",
)
teacher_media_bp = Blueprint("teacher_media", __name__)


def _teacher_session() -> dict:
    session = load_session(required=True, allowed_states={"active"})
    if session["role"] != "teacher":
        abort_session_required()
    return session


def _json_object_payload() -> dict:
    payload = request.get_json(silent=True)
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise ProviderValidationError(
            "请求体格式不正确",
            code="request_body_invalid",
            details={"body": "请求体必须是 JSON 对象"},
        )
    return payload


def _provider_error_response(error, status_code: int):
    return jsonify(
        success=False,
        message=error.message,
        errors=error.details,
    ), status_code


def _handle_validation(error: ProviderValidationError):
    return _provider_error_response(error, 400)


def _handle_not_found(error: ProviderNotFoundError):
    return _provider_error_response(error, 404)


def _handle_conflict(error: ProviderConflictError):
    return _provider_error_response(error, 409)


def _handle_access_denied(error: ProviderAccessDeniedError):
    return _provider_error_response(error, 403)


def _handle_unavailable(error: ProviderUnavailableError):
    return _provider_error_response(error, 503)


def register_teacher_console_error_handlers(app: Flask) -> None:
    app.register_error_handler(
        ProviderValidationError,
        _handle_validation,
    )
    app.register_error_handler(ProviderNotFoundError, _handle_not_found)
    app.register_error_handler(ProviderConflictError, _handle_conflict)
    app.register_error_handler(
        ProviderAccessDeniedError,
        _handle_access_denied,
    )
    app.register_error_handler(
        ProviderUnavailableError,
        _handle_unavailable,
    )


@teacher_console_bp.get("/courses")
def list_courses_route():
    session = _teacher_session()
    return jsonify(
        success=True,
        courses=list_teacher_courses(
            int(session["id"]),
            direction=request.args.get("direction"),
            status=request.args.get("status"),
        ),
    )


@teacher_console_bp.post("/courses")
def create_course_route():
    session = _teacher_session()
    payload = _json_object_payload()
    payload.pop("teacher_id", None)
    return jsonify(
        success=True,
        course=create_teacher_course(int(session["id"]), payload),
    ), 201


@teacher_console_bp.get("/courses/<int:course_id>")
def get_course_route(course_id: int):
    session = _teacher_session()
    return jsonify(
        success=True,
        course=get_teacher_course(int(session["id"]), course_id),
    )


@teacher_console_bp.put("/courses/<int:course_id>")
def update_course_route(course_id: int):
    session = _teacher_session()
    teacher_id = int(session["id"])
    payload = _json_object_payload()
    payload.pop("teacher_id", None)
    expected_version = payload.pop("expected_version", None)
    current = get_teacher_course(teacher_id, course_id)
    if current["status"] == "draft":
        course = update_teacher_course_draft(
            teacher_id,
            course_id,
            expected_version,
            payload,
        )
    else:
        course = edit_course(
            teacher_id,
            course_id,
            expected_version,
            payload,
        )
    return jsonify(
        success=True,
        course=course,
    )


@teacher_console_bp.post("/courses/<int:course_id>/submit")
def submit_course_route(course_id: int):
    session = _teacher_session()
    payload = _json_object_payload()
    payload.pop("teacher_id", None)
    return jsonify(
        success=True,
        course=submit_course_for_review(
            int(session["id"]),
            course_id,
            payload.get("expected_version"),
        ),
    )


@teacher_console_bp.post("/courses/<int:course_id>/offline")
def offline_course_route(course_id: int):
    session = _teacher_session()
    payload = _json_object_payload()
    payload.pop("teacher_id", None)
    return jsonify(
        success=True,
        course=set_course_offline(
            int(session["id"]),
            course_id,
            payload.get("expected_version"),
        ),
    )


@teacher_console_bp.post("/courses/<int:course_id>/relist")
def relist_course_route(course_id: int):
    session = _teacher_session()
    payload = _json_object_payload()
    payload.pop("teacher_id", None)
    return jsonify(
        success=True,
        course=request_course_relist(
            int(session["id"]),
            course_id,
            payload.get("expected_version"),
        ),
    )


@teacher_console_bp.post("/uploads/video")
def upload_video_route():
    session = _teacher_session()
    request.max_content_length = current_app.config[
        "MAX_VIDEO_UPLOAD_BYTES"
    ]
    file_storage = request.files.get("file")
    if file_storage is None:
        raise ProviderValidationError(
            "请选择视频文件",
            code="media_reference_invalid",
            details={"field": "file"},
        )
    return jsonify(
        success=True,
        media=save_course_video(file_storage, int(session["id"])),
    ), 201


@teacher_console_bp.get("/courses/<int:course_id>/quiz")
def get_course_quiz_route(course_id: int):
    session = _teacher_session()
    return jsonify(
        success=True,
        quiz=get_teacher_course_quiz(int(session["id"]), course_id),
    )


@teacher_console_bp.post("/courses/<int:course_id>/quiz")
def save_course_quiz_route(course_id: int):
    session = _teacher_session()
    payload = _json_object_payload()
    payload.pop("teacher_id", None)
    return jsonify(
        success=True,
        quiz=save_course_quiz(
            int(session["id"]),
            course_id,
            payload.get("expected_version"),
            payload.get("enabled"),
            payload.get("questions"),
            payload.get("scoring_rule", "all_correct"),
        ),
    )


@teacher_console_bp.post("/courses/<int:course_id>/quiz/generate")
def generate_course_quiz_route(course_id: int):
    session = _teacher_session()
    payload = _json_object_payload()
    payload.pop("teacher_id", None)
    return jsonify(
        success=True,
        quiz=generate_course_quiz(
            int(session["id"]),
            course_id,
            summary=payload.get("summary"),
            direction=payload.get("direction"),
        ),
    )


@teacher_console_bp.get("/announcements")
def list_announcements_route():
    session = _teacher_session()
    return jsonify(
        success=True,
        announcements=list_teaching_announcements(int(session["id"])),
    )


@teacher_console_bp.post("/announcements")
def publish_announcement_route():
    session = _teacher_session()
    payload = _json_object_payload()
    payload.pop("teacher_id", None)
    return jsonify(
        success=True,
        announcement=publish_teaching_announcement(
            int(session["id"]),
            payload.get("title"),
            payload.get("body"),
        ),
    ), 201


@teacher_console_bp.get("/comments")
def list_comments_route():
    session = _teacher_session()
    return jsonify(
        success=True,
        comments=list_teacher_comments(
            int(session["id"]),
            content_type=request.args.get("content_type"),
            content_id=request.args.get("content_id"),
        ),
    )


@teacher_console_bp.post("/comments/<comment_id>/replies")
def reply_to_comment_route(comment_id: str):
    session = _teacher_session()
    payload = _json_object_payload()
    payload.pop("teacher_id", None)
    return jsonify(
        success=True,
        comment=reply_to_comment(
            int(session["id"]),
            comment_id,
            payload.get("body"),
        ),
    ), 201


@teacher_console_bp.get("/dashboard")
def dashboard_route():
    session = _teacher_session()
    return jsonify(
        success=True,
        dashboard=build_teacher_dashboard(int(session["id"])),
    )


@teacher_console_bp.get("/reports")
def list_reports_route():
    session = _teacher_session()
    return jsonify(
        success=True,
        reports=list_teacher_reports(int(session["id"])),
    )


@teacher_console_bp.post("/reports")
def generate_report_route():
    session = _teacher_session()
    _json_object_payload()
    return jsonify(
        success=True,
        report=generate_teacher_report(int(session["id"])),
    ), 201


@teacher_console_bp.get("/reports/<report_id>")
def get_report_route(report_id: str):
    session = _teacher_session()
    return jsonify(
        success=True,
        report=get_teacher_report(int(session["id"]), report_id),
    )


@teacher_media_bp.get("/media/teacher-courses/<path:filename>")
def teacher_course_media_route(filename: str):
    return send_file(course_media_path(filename))
