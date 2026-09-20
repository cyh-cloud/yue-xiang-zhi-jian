from __future__ import annotations

from flask import Blueprint, Flask, jsonify, request

from app.admin_console.errors import (
    ProviderAccessDeniedError,
    ProviderConflictError,
    ProviderNotFoundError,
    ProviderUnavailableError,
    ProviderValidationError,
)
from app.session_manager import load_session


admin_console_bp = Blueprint(
    "admin_console",
    __name__,
    url_prefix="/api/admin",
)


def require_admin_session(*, roles: set[str]) -> dict:
    session = load_session(required=True, allowed_states={"active"})
    if session["role"] not in roles:
        raise ProviderAccessDeniedError(
            "无管理权限",
            code="admin_access_denied",
            details={},
        )
    return session


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
