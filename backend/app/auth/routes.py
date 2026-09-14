from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from app.auth.service import DuplicateUsernameError, register_account
from app.auth.validators import validate_registration
from app.session_manager import apply_session_cookie


auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@auth_bp.post("/register")
def register():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        payload = {}

    errors = validate_registration(payload)
    if errors:
        return jsonify(success=False, errors=errors), 400

    session_hours = int(current_app.config["SESSION_HOURS"])
    try:
        result = register_account(payload, session_hours)
    except DuplicateUsernameError:
        return jsonify(
            success=False, errors={"username": "用户名已被占用"}
        ), 409

    response = jsonify(
        success=True,
        next_step=result["next_step"],
        user=result["user"],
    )
    apply_session_cookie(
        response,
        result["session_token"],
        max_age=session_hours * 60 * 60,
    )
    return response, 201
