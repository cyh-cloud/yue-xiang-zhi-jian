from __future__ import annotations

from flask import Blueprint, jsonify, request

from app.government_console.errors import (
    ProviderAccessDeniedError,
    ProviderConflictError,
    ProviderError,
    ProviderValidationError,
)
from app.government_console.policy import (
    delete_policy,
    list_policies,
    publish_policy,
    relist_policy,
    unpublish_policy,
)
from app.session_manager import load_session


government_bp = Blueprint(
    "government_console",
    __name__,
    url_prefix="/api/government",
)


def _government_session() -> dict:
    session = load_session(required=True, allowed_states={"active"})
    if session["role"] != "government":
        raise ProviderAccessDeniedError("仅政府账户可访问政务工作台")
    return session


def _json_object_payload() -> dict:
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise ProviderValidationError("请求格式不正确")
    return payload


@government_bp.errorhandler(ProviderError)
def handle_provider_error(error: ProviderError):
    status = {
        "validation_error": 400,
        "not_found": 404,
        "conflict": 409,
        "unavailable": 503,
        "access_denied": 403,
    }.get(error.code, 500)
    return jsonify(
        success=False,
        message=error.message,
        details=error.details,
    ), status


@government_bp.get("/policies")
def list_policies_route():
    _government_session()
    return jsonify(
        success=True,
        policies=list_policies(
            status=request.args.get("status") or None,
            category_code=request.args.get("category") or None,
        ),
    )


@government_bp.post("/policies")
def publish_policy_route():
    session = _government_session()
    payload = _json_object_payload()
    policy = publish_policy(
        actor_id=int(session["id"]),
        request_id=payload.get("request_id"),
        title=payload.get("title"),
        content=payload.get("content"),
        category_code=payload.get("category_code"),
    )
    if policy is None:
        raise ProviderConflictError("政策发布请求已失效")
    return jsonify(success=True, policy=policy), 201


@government_bp.post("/policies/<policy_id>/unpublish")
def unpublish_policy_route(policy_id: str):
    _government_session()
    payload = _json_object_payload()
    return jsonify(
        success=True,
        policy=unpublish_policy(
            policy_id,
            expected_version=payload.get("expected_version"),
        ),
    )


@government_bp.post("/policies/<policy_id>/relist")
def relist_policy_route(policy_id: str):
    _government_session()
    payload = _json_object_payload()
    return jsonify(
        success=True,
        policy=relist_policy(
            policy_id,
            expected_version=payload.get("expected_version"),
        ),
    )


@government_bp.delete("/policies/<policy_id>")
def delete_policy_route(policy_id: str):
    _government_session()
    payload = _json_object_payload()
    delete_policy(
        policy_id,
        expected_version=payload.get("expected_version"),
    )
    return jsonify(success=True)
