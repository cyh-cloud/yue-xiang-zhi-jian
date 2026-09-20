from __future__ import annotations

import base64

from flask import Blueprint, jsonify, request

from app.local_resources.cases import get_local_resource_case_provider
from app.local_resources.catalog import (
    get_news,
    get_policy,
    list_news,
    list_policies,
)
from app.local_resources.dialect_assistant import complete_dialect_turn
from app.local_resources.errors import (
    LocalResourceAccessDeniedError,
    LocalResourceError,
    LocalResourceNotFoundError,
    LocalResourceValidationError,
)
from app.local_resources.subscriptions import (
    list_policy_subscriptions,
    set_policy_subscription,
)
from app.local_resources.views import (
    record_news_view,
    record_policy_view,
)
from app.session_manager import load_session


local_resources_bp = Blueprint(
    "local_resources",
    __name__,
    url_prefix="/api/local-resources",
)


def _student_session() -> dict:
    session = load_session(required=True, allowed_states={"active"})
    if session["role"] != "student":
        raise LocalResourceAccessDeniedError("仅学员可访问本土资源")
    return session


def _json_object_payload() -> dict:
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise LocalResourceValidationError(
            "请求格式不正确",
            details={"body": "请求体必须是 JSON 对象"},
        )
    return payload


@local_resources_bp.errorhandler(LocalResourceError)
def handle_local_resource_error(error: LocalResourceError):
    status = {
        "validation_error": 400,
        "not_found": 404,
        "conflict": 409,
        "unavailable": 503,
        "access_denied": 403,
    }[error.code]
    return jsonify(
        success=False,
        message=error.message,
        details=error.details,
    ), status


@local_resources_bp.get("/cases")
def list_cases_route():
    _student_session()
    cases = get_local_resource_case_provider().list_success_cases()
    return jsonify(success=True, cases=cases)


@local_resources_bp.get("/cases/<case_id>")
def get_case_route(case_id: str):
    _student_session()
    case = get_local_resource_case_provider().get_success_case(case_id)
    if case is None:
        raise LocalResourceNotFoundError("案例不存在")
    return jsonify(success=True, case=case)


@local_resources_bp.get("/policies")
def list_policies_route():
    _student_session()
    return jsonify(
        success=True,
        policies=list_policies(request.args.get("category")),
    )


@local_resources_bp.get("/policies/<policy_id>")
def get_policy_route(policy_id: str):
    _student_session()
    return jsonify(success=True, policy=get_policy(policy_id))


@local_resources_bp.get("/policy-subscriptions")
def list_policy_subscriptions_route():
    session = _student_session()
    return jsonify(
        success=True,
        subscriptions=list_policy_subscriptions(int(session["id"])),
    )


@local_resources_bp.post(
    "/policy-subscriptions/<category_code>"
)
def subscribe_policy_category_route(category_code: str):
    session = _student_session()
    return jsonify(
        success=True,
        subscription=set_policy_subscription(
            int(session["id"]),
            category_code,
            True,
        ),
    )


@local_resources_bp.delete(
    "/policy-subscriptions/<category_code>"
)
def unsubscribe_policy_category_route(category_code: str):
    session = _student_session()
    return jsonify(
        success=True,
        subscription=set_policy_subscription(
            int(session["id"]),
            category_code,
            False,
        ),
    )


@local_resources_bp.get("/news")
def list_news_route():
    _student_session()
    return jsonify(
        success=True,
        news=list_news(request.args.get("category")),
    )


@local_resources_bp.get("/news/<news_id>")
def get_news_route(news_id: str):
    _student_session()
    return jsonify(success=True, news=get_news(news_id))


@local_resources_bp.post("/policies/<policy_id>/views")
def record_policy_view_route(policy_id: str):
    _student_session()
    payload = _json_object_payload()
    return jsonify(
        success=True,
        view_count=record_policy_view(
            policy_id,
            payload.get("view_event_id"),
        ),
    )


@local_resources_bp.post("/news/<news_id>/views")
def record_news_view_route(news_id: str):
    _student_session()
    payload = _json_object_payload()
    return jsonify(
        success=True,
        view_count=record_news_view(
            news_id,
            payload.get("view_event_id"),
        ),
    )


@local_resources_bp.post("/dialect-assistant/turns")
def create_dialect_turn_route():
    session = _student_session()
    payload = _json_object_payload()
    turn = complete_dialect_turn(
        int(session["id"]),
        payload.get("dialect_code"),
        payload.get("question"),
    )
    return jsonify(
        success=True,
        turn={
            key: value
            for key, value in turn.items()
            if not key.startswith("audio_")
        },
        audio_base64=base64.b64encode(turn["audio_content"]).decode(
            "ascii"
        ),
        audio_content_type=turn["audio_content_type"],
    ), 201


__all__ = ["local_resources_bp"]
