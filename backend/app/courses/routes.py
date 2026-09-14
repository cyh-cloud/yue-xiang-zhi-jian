from __future__ import annotations

from flask import Blueprint, jsonify, request

from app.courses.service import COURSE_DIRECTIONS, list_published_courses
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

    direction = request.args.get("direction", "").strip()
    if direction not in COURSE_DIRECTIONS:
        return jsonify(
            success=False,
            errors={"direction": "学习方向不正确"},
        ), 400

    return jsonify(
        success=True,
        courses=list_published_courses(int(session["id"]), direction),
    )
