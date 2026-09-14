from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from app.auth.service import (
    DisabledAccountError,
    DuplicateUsernameError,
    authenticate,
    register_account,
)
from app.auth.validators import validate_registration
from app.db import get_db
from app.session_manager import (
    abort_session_required,
    apply_session_cookie,
    clear_session_cookie,
    load_session,
    revoke_current_session,
    role_default_path,
)
from app.tags.service import (
    InvalidInterestTagError,
    replace_student_tags,
)


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


@auth_bp.post("/login")
def login():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        payload = {}

    session_hours = int(current_app.config["SESSION_HOURS"])
    try:
        result = authenticate(
            payload.get("username", ""),
            payload.get("password", ""),
            session_hours,
        )
    except DisabledAccountError:
        return jsonify(
            success=False,
            message="账户已被禁用，请联系管理员",
        ), 403

    if result is None:
        return jsonify(
            success=False,
            message="用户名或密码错误",
        ), 401

    response = jsonify(
        success=True,
        user=result["user"],
        default_path=result["default_path"],
    )
    apply_session_cookie(
        response,
        result["session_token"],
        max_age=session_hours * 60 * 60,
    )
    return response


@auth_bp.post("/logout")
def logout():
    revoke_current_session()
    response = jsonify(success=True)
    clear_session_cookie(response)
    return response


@auth_bp.get("/session")
def get_session():
    session = load_session(required=False)
    if session is None:
        abort_session_required()

    user = {
        "id": session["id"],
        "username": session["username"],
        "name": session["name"],
        "role": session["role"],
    }
    if session["state"] == "pending" and session["role"] == "student":
        return jsonify(
            success=True,
            state="pending",
            user=user,
            next_step="interest-tags",
            default_path="/register/interest-tags",
        )
    if session["state"] == "active":
        return jsonify(
            success=True,
            state="active",
            user=user,
            default_path=role_default_path(session["role"]),
        )

    abort_session_required()


@auth_bp.post("/interest-tags")
def complete_interest_tags():
    session = load_session(required=True, allowed_states={"pending"})
    if session["role"] != "student":
        abort_session_required()

    payload = request.get_json(silent=True)
    tag_ids = payload.get("tag_ids") if isinstance(payload, dict) else None
    if not isinstance(tag_ids, list) or any(
        not isinstance(tag_id, int) or isinstance(tag_id, bool)
        for tag_id in tag_ids
    ):
        return jsonify(
            success=False,
            errors={"tag_ids": "兴趣标签格式不正确"},
        ), 400

    try:
        replace_student_tags(session["id"], tag_ids)
    except InvalidInterestTagError as error:
        return jsonify(success=False, errors=error.errors), 400

    db = get_db()
    db.execute(
        "UPDATE sessions SET state = 'active' WHERE token_hash = ?",
        (session["token_hash"],),
    )
    db.commit()

    user = {
        "id": session["id"],
        "username": session["username"],
        "name": session["name"],
        "role": session["role"],
    }
    return jsonify(
        success=True,
        user=user,
        default_path="/student",
    )
