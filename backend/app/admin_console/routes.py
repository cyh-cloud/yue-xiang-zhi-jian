from __future__ import annotations

from flask import Blueprint, Flask, jsonify

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
