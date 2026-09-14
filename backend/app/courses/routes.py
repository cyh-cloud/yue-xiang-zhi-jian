from __future__ import annotations

from flask import Blueprint, jsonify, request

from app.courses.service import list_published_courses
from app.session_manager import abort_session_required, load_session


student_courses_bp = Blueprint(
    "student_courses",
    __name__,
    url_prefix="/api/student",
)


@student_courses_bp.get("/courses")
def get_courses():
    session = load_session(required=True, allowed_states={"active"})
    if session["role"] != "student":
        abort_session_required()

    direction = request.args.get("direction", "")
    return jsonify(
        success=True,
        courses=list_published_courses(int(session["id"]), direction),
    )
