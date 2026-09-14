from __future__ import annotations

from flask import Blueprint, jsonify, request

from app.profiles.service import (
    InvalidStudentProfileError,
    get_student_profile,
    update_student_profile,
)
from app.session_manager import abort_session_required, load_session


student_profile_bp = Blueprint(
    "student_profile",
    __name__,
    url_prefix="/api/student",
)


@student_profile_bp.get("/profile")
def get_profile():
    session = load_session(required=True, allowed_states={"active"})
    if session["role"] != "student":
        abort_session_required()

    return jsonify(
        success=True,
        profile=get_student_profile(int(session["id"])),
    )


@student_profile_bp.put("/profile")
def put_profile():
    session = load_session(required=True, allowed_states={"active"})
    if session["role"] != "student":
        abort_session_required()

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        payload = {}

    try:
        profile = update_student_profile(int(session["id"]), payload)
    except InvalidStudentProfileError as error:
        return jsonify(success=False, errors=error.errors), 400

    return jsonify(success=True, profile=profile)
