from __future__ import annotations

import hmac

from flask import Blueprint, Flask, current_app, jsonify, request

from app.agri_skills.errors import (
    AgriAccessError,
    AgriNotFoundError,
    AgriValidationError,
    AiUnavailableError,
)
from app.db import get_db
from app.handcraft_inheritance.ar_guidance import (
    generate_ar_guidance as _generate_ar_guidance,
)
from app.handcraft_inheritance.course_learning import (
    get_handcraft_course_progress as _get_handcraft_course_progress,
    get_handcraft_course_quiz as _get_handcraft_course_quiz,
    list_handcraft_courses as _list_handcraft_courses,
    list_handcraft_course_quiz_attempts as
    _list_handcraft_course_quiz_attempts,
    list_handcraft_recommendations as _list_handcraft_recommendations,
    submit_handcraft_course_quiz as _submit_handcraft_course_quiz,
    update_handcraft_course_progress as _update_handcraft_course_progress,
)
from app.handcraft_inheritance.crafts import (
    complete_craft_step as _complete_craft_step,
    get_craft as _get_craft,
    get_craft_progress as _get_craft_progress,
    list_crafts as _list_crafts,
)
from app.handcraft_inheritance.fulfillment import (
    cancel_pending_fulfillment as _cancel_pending_fulfillment,
    list_student_fulfillments as _list_student_fulfillments,
    retry_pending_fulfillment_notifications as
    _retry_pending_fulfillment_notifications,
    student_verify_fulfillment as _student_verify_fulfillment,
)
from app.handcraft_inheritance.points import (
    get_points_account as _get_points_account,
    get_points_daily_status as _get_points_daily_status,
    get_points_ledger as _get_points_ledger,
    process_pending_events as _process_pending_events,
    run_expiry_settlement as _run_expiry_settlement,
)
from app.handcraft_inheritance.rewards import (
    REDEMPTION_CONFLICT_MESSAGE,
    list_redemptions as _list_redemptions,
    list_rewards as _list_rewards,
    redeem_reward as _redeem_reward,
)
from app.handcraft_inheritance.videos import (
    list_student_videos as _list_student_videos,
)
from app.session_manager import abort_session_required, load_session


handcraft_inheritance_bp = Blueprint(
    "handcraft_inheritance",
    __name__,
    url_prefix="/api/handcraft-inheritance",
)

_CONFLICT_MESSAGES = {
    REDEMPTION_CONFLICT_MESSAGE,
    "履约状态已变化，请重试",
    "当前履约状态不可取消",
    "库存回滚失败",
}


def _student_session() -> dict:
    session = load_session(required=True, allowed_states={"active"})
    if session["role"] != "student":
        abort_session_required()
    # load_session may leave an empty session-cleanup transaction open.
    get_db().commit()
    return session


def _json_object_payload() -> dict:
    payload = request.get_json(silent=True)
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise AgriValidationError(
            "请求体格式不正确",
            details={"body": "请求体必须是 JSON 对象"},
        )
    return payload


def _handle_validation(error: AgriValidationError):
    status = 409 if error.message in _CONFLICT_MESSAGES else 400
    return jsonify(
        success=False,
        message=error.message,
        errors=error.details,
    ), status


def _handle_not_found(error: AgriNotFoundError | AgriAccessError):
    return jsonify(success=False, message=error.message), 404


def _handle_ai_unavailable(_error: AiUnavailableError):
    return jsonify(
        success=False,
        message="AI 服务暂时不可用",
    ), 503


def register_handcraft_inheritance_error_handlers(app: Flask) -> None:
    app.register_error_handler(AgriValidationError, _handle_validation)
    app.register_error_handler(AgriNotFoundError, _handle_not_found)
    app.register_error_handler(AgriAccessError, _handle_not_found)
    app.register_error_handler(AiUnavailableError, _handle_ai_unavailable)


@handcraft_inheritance_bp.get("/crafts")
def list_crafts_route():
    _student_session()
    return jsonify(success=True, crafts=_list_crafts())


@handcraft_inheritance_bp.get("/crafts/<craft_key>")
def get_craft_route(craft_key: str):
    _student_session()
    return jsonify(success=True, craft=_get_craft(craft_key))


@handcraft_inheritance_bp.get("/crafts/<craft_key>/progress")
def get_craft_progress_route(craft_key: str):
    session = _student_session()
    return jsonify(
        success=True,
        progress=_get_craft_progress(
            int(session["id"]),
            craft_key,
        ),
    )


@handcraft_inheritance_bp.post(
    "/crafts/<craft_key>/steps/<int:step_no>/complete"
)
def complete_craft_step_route(craft_key: str, step_no: int):
    session = _student_session()
    payload = _json_object_payload()
    return jsonify(
        success=True,
        progress=_complete_craft_step(
            int(session["id"]),
            craft_key,
            step_no,
            payload.get("active_seconds"),
            payload.get("event_id"),
        ),
    )


@handcraft_inheritance_bp.get("/videos")
def list_student_videos_route():
    _student_session()
    craft_key = request.args.get("craft_key", "").strip()
    if not craft_key:
        raise AgriValidationError("技艺标识不能为空")
    return jsonify(
        success=True,
        videos=_list_student_videos(craft_key),
    )


@handcraft_inheritance_bp.post("/ar-guidance")
def generate_ar_guidance_route():
    session = _student_session()
    payload = _json_object_payload()
    return jsonify(
        success=True,
        guidance=_generate_ar_guidance(
            int(session["id"]),
            payload.get("craft_key"),
            payload.get("project_label"),
            payload.get("active_seconds"),
            payload.get("event_id"),
        ),
    )


@handcraft_inheritance_bp.get("/points")
def get_points_account_route():
    session = _student_session()
    user_id = int(session["id"])
    _process_pending_events(user_id)
    account = _get_points_account(user_id)
    account.update(_get_points_daily_status(user_id))
    return jsonify(
        success=True,
        account=account,
    )


@handcraft_inheritance_bp.get("/points/ledger")
def get_points_ledger_route():
    session = _student_session()
    user_id = int(session["id"])
    _process_pending_events(user_id)
    return jsonify(
        success=True,
        ledger=_get_points_ledger(user_id),
    )


@handcraft_inheritance_bp.get("/rewards")
def list_rewards_route():
    session = _student_session()
    return jsonify(
        success=True,
        rewards=_list_rewards(int(session["id"])),
    )


@handcraft_inheritance_bp.get("/redemptions")
def list_redemptions_route():
    session = _student_session()
    user_id = int(session["id"])
    return jsonify(
        success=True,
        redemptions=_list_redemptions(user_id),
        fulfillments=_list_student_fulfillments(user_id),
    )


@handcraft_inheritance_bp.post("/redemptions")
def redeem_reward_route():
    session = _student_session()
    payload = _json_object_payload()
    return jsonify(
        success=True,
        redemption=_redeem_reward(
            int(session["id"]),
            payload.get("reward_id"),
            payload.get("request_id"),
        ),
    ), 201


@handcraft_inheritance_bp.post(
    "/redemptions/<int:redemption_id>/cancel"
)
def cancel_redemption_route(redemption_id: int):
    session = _student_session()
    user_id = int(session["id"])
    fulfillment = _student_fulfillment_id(user_id, redemption_id)
    if fulfillment is None:
        raise AgriNotFoundError("兑换记录不存在")
    return jsonify(
        success=True,
        cancellation=_cancel_pending_fulfillment(
            fulfillment,
            role="student",
            actor_user_id=user_id,
        ),
    )


@handcraft_inheritance_bp.post(
    "/redemptions/<int:redemption_id>/verify"
)
def verify_redemption_route(redemption_id: int):
    session = _student_session()
    user_id = int(session["id"])
    fulfillment = _student_fulfillment_id(user_id, redemption_id)
    if fulfillment is None:
        raise AgriNotFoundError("兑换记录不存在")
    return jsonify(
        success=True,
        verification=_student_verify_fulfillment(
            fulfillment,
            user_id,
        ),
    )


def _student_fulfillment_id(
    user_id: int,
    redemption_id: int,
) -> int | None:
    return next(
        (
            item["fulfillment"]["id"]
            for item in _list_student_fulfillments(user_id)
            if item["redemption"]["id"] == redemption_id
        ),
        None,
    )


@handcraft_inheritance_bp.get("/courses")
def list_handcraft_courses_route():
    session = _student_session()
    return jsonify(
        success=True,
        courses=_list_handcraft_courses(int(session["id"])),
    )


@handcraft_inheritance_bp.get("/recommendations")
def list_handcraft_recommendations_route():
    session = _student_session()
    return jsonify(
        success=True,
        courses=_list_handcraft_recommendations(int(session["id"])),
    )


@handcraft_inheritance_bp.get("/courses/<int:course_id>/progress")
def get_handcraft_course_progress_route(course_id: int):
    session = _student_session()
    return jsonify(
        success=True,
        progress=_get_handcraft_course_progress(
            int(session["id"]),
            course_id,
        ),
    )


@handcraft_inheritance_bp.put("/courses/<int:course_id>/progress")
def update_handcraft_course_progress_route(course_id: int):
    session = _student_session()
    payload = _json_object_payload()
    return jsonify(
        success=True,
        progress=_update_handcraft_course_progress(
            int(session["id"]),
            course_id,
            payload.get("position_seconds"),
            payload.get("watched_delta_seconds", 0),
        ),
    )


@handcraft_inheritance_bp.get("/courses/<int:course_id>/quiz")
def get_handcraft_course_quiz_route(course_id: int):
    session = _student_session()
    quiz = _get_handcraft_course_quiz(int(session["id"]), course_id)
    if quiz is None:
        raise AgriNotFoundError("暂无可用测验")
    return jsonify(success=True, quiz=quiz)


@handcraft_inheritance_bp.get(
    "/courses/<int:course_id>/quiz/attempts"
)
def list_handcraft_course_quiz_attempts_route(course_id: int):
    session = _student_session()
    return jsonify(
        success=True,
        attempts=_list_handcraft_course_quiz_attempts(
            int(session["id"]),
            course_id,
        ),
    )


@handcraft_inheritance_bp.post("/courses/<int:course_id>/quiz")
def submit_handcraft_course_quiz_route(course_id: int):
    session = _student_session()
    payload = _json_object_payload()
    answers = payload.get("answers")
    return jsonify(
        success=True,
        attempt=_submit_handcraft_course_quiz(
            int(session["id"]),
            course_id,
            answers if isinstance(answers, dict) else {},
        ),
    ), 201


def _internal_expiry_token() -> str:
    token = request.headers.get("X-Points-Expiry-Token", "").strip()
    if token:
        return token

    authorization = request.headers.get("Authorization", "")
    scheme, separator, value = authorization.partition(" ")
    if separator and scheme.lower() == "bearer":
        return value.strip()
    return ""


@handcraft_inheritance_bp.post("/internal/points-expiry/run")
def run_points_expiry_settlement_route():
    expected = str(current_app.config.get("POINTS_EXPIRY_TOKEN", ""))
    provided = _internal_expiry_token()
    if not expected or not hmac.compare_digest(provided, expected):
        return jsonify(success=False, message="未授权"), 401

    batch_size = int(
        current_app.config.get("POINTS_EXPIRY_BATCH_SIZE", 100)
    )
    settlement = _run_expiry_settlement(batch_size=batch_size)
    fulfillment_notifications = (
        _retry_pending_fulfillment_notifications(limit=batch_size)
    )
    return jsonify(
        success=True,
        **settlement,
        fulfillment_notifications=fulfillment_notifications,
    )
