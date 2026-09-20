from __future__ import annotations

from flask import Blueprint, Flask, jsonify, request

from app.admin_console.errors import (
    ProviderAccessDeniedError,
    ProviderConflictError,
    ProviderNotFoundError,
    ProviderUnavailableError,
    ProviderValidationError,
)
from app.db import get_db
from app.session_manager import load_session


admin_console_bp = Blueprint(
    "admin_console",
    __name__,
    url_prefix="/api/admin",
)


def require_admin_session(*, roles: set[str]) -> dict:
    session = load_session(required=True, allowed_states={"active"})
    # `load_session` runs a session-cleanup DELETE that opens a deferred
    # transaction and only commits it when rows were removed, so the
    # connection can still hold an empty transaction here. 05's domain
    # functions open `BEGIN IMMEDIATE` themselves, which fails inside an
    # open transaction, so the empty transaction is closed the same way 05's
    # `_student_session` closes it before calling into a domain function.
    get_db().commit()
    if session["role"] not in roles:
        raise ProviderAccessDeniedError(
            "无管理权限",
            code="admin_access_denied",
            details={},
        )
    return session


def _preset_expected_version():
    """Optional optimistic-lock token carried by a preset DELETE request."""
    raw = request.args.get("expected_version")
    if raw is None:
        payload = request.get_json(silent=True)
        if isinstance(payload, dict):
            raw = payload.get("expected_version")
    return raw


def _admin_actor(session: dict) -> dict:
    """Build the actor from the 01 session only.

    A client supplied role or id is never read here: the session is the only
    authorization source, so a forged body cannot widen an action.
    """
    return {"id": int(session["id"]), "role": str(session["role"])}


def _admin_filters(*names: str) -> dict:
    """Read the declared filter keys from the query string, ignoring the rest."""
    filters: dict = {}
    for name in names:
        value = request.args.get(name)
        if value is not None:
            filters[name] = value
    return filters


@admin_console_bp.get("/dashboard")
def super_admin_dashboard():
    from app.admin_console.dashboard import get_super_admin_dashboard

    require_admin_session(roles={"super_admin"})
    return jsonify(
        success=True,
        dashboard=get_super_admin_dashboard(),
    )


@admin_console_bp.get("/content-dashboard")
def content_operations_dashboard():
    from app.admin_console.dashboard import (
        get_content_operations_dashboard,
    )

    require_admin_session(roles={"admin", "super_admin"})
    return jsonify(
        success=True,
        dashboard=get_content_operations_dashboard(),
    )


@admin_console_bp.get("/accounts")
def list_accounts_route():
    from app.admin_console.accounts import list_accounts

    require_admin_session(roles={"super_admin"})
    return jsonify(
        success=True,
        accounts=list_accounts(
            role=request.args.get("role"),
            keyword=request.args.get("keyword"),
        ),
    )


@admin_console_bp.get("/accounts/<int:user_id>")
def get_account_route(user_id: int):
    from app.admin_console.accounts import get_account

    require_admin_session(roles={"super_admin"})
    return jsonify(success=True, account=get_account(user_id))


@admin_console_bp.post("/accounts")
def create_account_route():
    from app.admin_console.accounts import create_managed_account

    session = require_admin_session(roles={"super_admin"})
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        payload = {}
    account = create_managed_account(int(session["id"]), payload)
    return jsonify(success=True, account=account), 201


@admin_console_bp.post("/accounts/<int:user_id>/status")
def set_account_status_route(user_id: int):
    from app.admin_console.accounts import set_account_enabled

    session = require_admin_session(roles={"super_admin"})
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        payload = {}
    account = set_account_enabled(
        int(session["id"]),
        user_id,
        payload.get("enabled"),
    )
    return jsonify(success=True, account=account)


@admin_console_bp.post("/accounts/<int:user_id>/password-reset")
def reset_account_password_route(user_id: int):
    from app.admin_console.accounts import reset_account_password

    session = require_admin_session(roles={"super_admin"})
    result = reset_account_password(int(session["id"]), user_id)
    return jsonify(success=True, **result)


@admin_console_bp.get("/review")
def review_queue_route():
    from app.admin_console.content_review_service import list_review_queue

    require_admin_session(roles={"admin", "super_admin"})
    return jsonify(
        success=True,
        **list_review_queue(request.args.get("content_type")),
    )


@admin_console_bp.post("/review/<content_type>/<content_id>/approve")
def approve_review_route(content_type: str, content_id: str):
    from app.admin_console.content_review_service import approve_review

    session = require_admin_session(roles={"admin", "super_admin"})
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        payload = {}
    item = approve_review(
        {"id": int(session["id"]), "role": str(session["role"])},
        content_type=content_type,
        content_id=content_id,
        expected_version=payload.get("expected_version"),
    )
    return jsonify(success=True, item=item)


@admin_console_bp.post("/review/<content_type>/<content_id>/reject")
def reject_review_route(content_type: str, content_id: str):
    from app.admin_console.content_review_service import reject_review

    session = require_admin_session(roles={"admin", "super_admin"})
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        payload = {}
    item = reject_review(
        {"id": int(session["id"]), "role": str(session["role"])},
        content_type=content_type,
        content_id=content_id,
        expected_version=payload.get("expected_version"),
        opinion=payload.get("opinion"),
    )
    return jsonify(success=True, item=item)


@admin_console_bp.get("/presets/handcraft_crafts")
def list_handcraft_craft_presets_route():
    from app.admin_console.presets import list_craft_presets

    require_admin_session(roles={"admin", "super_admin"})
    items = list_craft_presets()
    return jsonify(success=True, items=items, count=len(items))


@admin_console_bp.post("/presets/handcraft_crafts")
def create_handcraft_craft_preset_route():
    from app.admin_console.presets import create_craft_preset

    session = require_admin_session(roles={"admin", "super_admin"})
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        payload = {}
    item = create_craft_preset(int(session["id"]), payload)
    return jsonify(success=True, item=item), 201


@admin_console_bp.put("/presets/handcraft_crafts/<craft_key>")
def update_handcraft_craft_preset_route(craft_key: str):
    from app.admin_console.presets import update_craft_preset

    session = require_admin_session(roles={"admin", "super_admin"})
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        payload = {}
    item = update_craft_preset(int(session["id"]), craft_key, payload)
    return jsonify(success=True, item=item)


@admin_console_bp.delete("/presets/handcraft_crafts/<craft_key>")
def delete_handcraft_craft_preset_route(craft_key: str):
    from app.admin_console.presets import disable_craft_preset

    session = require_admin_session(roles={"admin", "super_admin"})
    item = disable_craft_preset(
        int(session["id"]),
        craft_key,
        _preset_expected_version(),
    )
    return jsonify(success=True, item=item)


@admin_console_bp.get("/presets/success_cases")
def list_success_case_presets_route():
    from app.admin_console.presets import list_case_presets

    require_admin_session(roles={"admin", "super_admin"})
    items = list_case_presets()
    return jsonify(success=True, items=items, count=len(items))


@admin_console_bp.post("/presets/success_cases")
def create_success_case_preset_route():
    from app.admin_console.presets import create_case_preset

    session = require_admin_session(roles={"admin", "super_admin"})
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        payload = {}
    item = create_case_preset(int(session["id"]), payload)
    return jsonify(success=True, item=item), 201


@admin_console_bp.put("/presets/success_cases/<case_id>")
def update_success_case_preset_route(case_id: str):
    from app.admin_console.presets import update_case_preset

    session = require_admin_session(roles={"admin", "super_admin"})
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        payload = {}
    item = update_case_preset(int(session["id"]), case_id, payload)
    return jsonify(success=True, item=item)


@admin_console_bp.delete("/presets/success_cases/<case_id>")
def delete_success_case_preset_route(case_id: str):
    from app.admin_console.presets import disable_case_preset

    session = require_admin_session(roles={"admin", "super_admin"})
    item = disable_case_preset(
        int(session["id"]),
        case_id,
        _preset_expected_version(),
    )
    return jsonify(success=True, item=item)


@admin_console_bp.get("/presets/assistant_knowledge")
def list_assistant_knowledge_presets_route():
    from app.admin_console.presets import list_knowledge_presets

    require_admin_session(roles={"admin", "super_admin"})
    items = list_knowledge_presets()
    return jsonify(success=True, items=items, count=len(items))


@admin_console_bp.post("/presets/assistant_knowledge")
def create_assistant_knowledge_preset_route():
    from app.admin_console.presets import create_knowledge_preset

    session = require_admin_session(roles={"admin", "super_admin"})
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        payload = {}
    item = create_knowledge_preset(int(session["id"]), payload)
    return jsonify(success=True, item=item), 201


@admin_console_bp.put("/presets/assistant_knowledge/<knowledge_id>")
def update_assistant_knowledge_preset_route(knowledge_id: str):
    from app.admin_console.presets import update_knowledge_preset

    session = require_admin_session(roles={"admin", "super_admin"})
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        payload = {}
    item = update_knowledge_preset(int(session["id"]), knowledge_id, payload)
    return jsonify(success=True, item=item)


@admin_console_bp.delete("/presets/assistant_knowledge/<knowledge_id>")
def delete_assistant_knowledge_preset_route(knowledge_id: str):
    from app.admin_console.presets import disable_knowledge_preset

    session = require_admin_session(roles={"admin", "super_admin"})
    item = disable_knowledge_preset(
        int(session["id"]),
        knowledge_id,
        _preset_expected_version(),
    )
    return jsonify(success=True, item=item)


@admin_console_bp.get("/rewards")
def list_rewards_route():
    from app.admin_console.rewards import list_rewards_admin

    require_admin_session(roles={"admin", "super_admin"})
    items = list_rewards_admin()
    return jsonify(success=True, items=items, count=len(items))


@admin_console_bp.post("/rewards")
def create_reward_route():
    from app.admin_console.rewards import create_reward

    session = require_admin_session(roles={"admin", "super_admin"})
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        payload = {}
    reward = create_reward(int(session["id"]), payload)
    return jsonify(success=True, reward=reward), 201


@admin_console_bp.put("/rewards/<reward_id>")
def update_reward_route(reward_id: str):
    from app.admin_console.rewards import update_reward

    session = require_admin_session(roles={"admin", "super_admin"})
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        payload = {}
    reward = update_reward(
        int(session["id"]),
        reward_id,
        payload.get("expected_version"),
        payload,
    )
    return jsonify(success=True, reward=reward)


@admin_console_bp.post("/rewards/<reward_id>/online")
def set_reward_online_route(reward_id: str):
    from app.admin_console.rewards import set_reward_online

    session = require_admin_session(roles={"admin", "super_admin"})
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        payload = {}
    # An omitted flag means "put it online", matching the route name.
    reward = set_reward_online(
        int(session["id"]),
        reward_id,
        payload.get("expected_version"),
        payload.get("online", True),
    )
    return jsonify(success=True, reward=reward)


@admin_console_bp.get("/redemptions")
def list_redemptions_route():
    from app.admin_console.rewards import list_redemptions

    session = require_admin_session(roles={"admin", "super_admin"})
    items = list_redemptions(
        _admin_actor(session),
        _admin_filters(
            "user",
            "reward",
            "status",
            "fulfillment_status",
            "created_from",
            "created_to",
        ),
    )
    return jsonify(success=True, items=items, count=len(items))


@admin_console_bp.get("/redemptions/<int:redemption_id>")
def get_redemption_route(redemption_id: int):
    from app.admin_console.rewards import get_redemption_detail

    session = require_admin_session(roles={"admin", "super_admin"})
    redemption = get_redemption_detail(
        _admin_actor(session),
        redemption_id,
    )
    # The redemption context is the response body itself, so the console
    # reads `user`, `points_ledger` and the redemption fields directly.
    return jsonify(success=True, **redemption)


@admin_console_bp.get("/fulfillments")
def list_fulfillments_route():
    from app.admin_console.rewards import list_fulfillments

    session = require_admin_session(roles={"admin", "super_admin"})
    items = list_fulfillments(
        _admin_actor(session),
        _admin_filters(
            "user",
            "reward",
            "status",
            "fulfillment_status",
            "created_from",
            "created_to",
        ),
    )
    return jsonify(success=True, items=items, count=len(items))


def _fulfillment_action_response(fulfillment_id: int, action: str):
    from app.admin_console.rewards import apply_fulfillment_action

    session = require_admin_session(roles={"admin", "super_admin"})
    result = apply_fulfillment_action(
        _admin_actor(session),
        fulfillment_id,
        action,
    )
    return jsonify(success=True, fulfillment=result)


@admin_console_bp.post("/fulfillments/<int:fulfillment_id>/issue")
def issue_fulfillment_route(fulfillment_id: int):
    return _fulfillment_action_response(fulfillment_id, "issue")


@admin_console_bp.post("/fulfillments/<int:fulfillment_id>/cancel")
def cancel_fulfillment_route(fulfillment_id: int):
    return _fulfillment_action_response(fulfillment_id, "cancel")


@admin_console_bp.post("/fulfillments/<int:fulfillment_id>/verify")
def verify_fulfillment_route(fulfillment_id: int):
    return _fulfillment_action_response(fulfillment_id, "verify")


@admin_console_bp.get("/announcements")
def list_announcements_route():
    from app.admin_console.system_announcements import list_announcements

    # Super admin only: the permission matrix keeps announcements invisible
    # and unoperable for an ordinary admin, so the guard runs before any
    # announcement row is read.
    require_admin_session(roles={"super_admin"})
    items = list_announcements()
    return jsonify(success=True, items=items, count=len(items))


@admin_console_bp.post("/announcements")
def create_announcement_route():
    from app.admin_console.system_announcements import create_announcement

    session = require_admin_session(roles={"super_admin"})
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        payload = {}
    announcement = create_announcement(int(session["id"]), payload)
    return jsonify(success=True, announcement=announcement), 201


@admin_console_bp.post("/announcements/<announcement_id>/publish")
def publish_announcement_route(announcement_id: str):
    from app.admin_console.system_announcements import publish_announcement

    session = require_admin_session(roles={"super_admin"})
    result = publish_announcement(int(session["id"]), announcement_id)
    return jsonify(success=True, **result)


def _error_response(error, status: int):
    return (
        jsonify(
            success=False,
            code=error.code,
            message=error.message,
            details=error.details,
        ),
        status,
    )


def _handle_validation(error: ProviderValidationError):
    return _error_response(error, 400)


def _handle_access_denied(error: ProviderAccessDeniedError):
    return _error_response(error, 403)


def _handle_not_found(error: ProviderNotFoundError):
    return _error_response(error, 404)


def _handle_conflict(error: ProviderConflictError):
    return _error_response(error, 409)


def _handle_unavailable(error: ProviderUnavailableError):
    return _error_response(error, 503)


def register_admin_console_error_handlers(app: Flask) -> None:
    app.register_error_handler(
        ProviderValidationError,
        _handle_validation,
    )
    app.register_error_handler(
        ProviderAccessDeniedError,
        _handle_access_denied,
    )
    app.register_error_handler(
        ProviderNotFoundError,
        _handle_not_found,
    )
    app.register_error_handler(
        ProviderConflictError,
        _handle_conflict,
    )
    app.register_error_handler(
        ProviderUnavailableError,
        _handle_unavailable,
    )


__all__ = [
    "admin_console_bp",
    "register_admin_console_error_handlers",
    "require_admin_session",
]
