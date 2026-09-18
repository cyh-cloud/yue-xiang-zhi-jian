from __future__ import annotations

import logging

from app.db import get_db
from app.agri_skills.course_learning import (
    get_course_progress,
    get_course_quiz,
    list_course_quiz_attempts,
    list_courses,
    list_recommendations,
    submit_course_quiz,
    update_course_progress,
)
from app.handcraft_inheritance.points import (
    MAX_SEGMENT_SECONDS,
    record_duration_points,
)
from app.handcraft_inheritance.outcomes import (
    record_handcraft_learning_outcome,
)


LOGGER = logging.getLogger(__name__)


def list_handcraft_courses(student_id: int) -> list[dict]:
    return list_courses(student_id, "handcraft")


def list_handcraft_recommendations(student_id: int) -> list[dict]:
    return list_recommendations(student_id, "handcraft")


def get_handcraft_course_progress(user_id: int, course_id: int) -> dict:
    return get_course_progress(
        user_id,
        course_id,
        direction="handcraft",
    )


def update_handcraft_course_progress(
    user_id: int,
    course_id: int,
    position_seconds: int,
    watched_delta_seconds: int,
) -> dict:
    before = get_handcraft_course_progress(user_id, course_id)
    progress = update_course_progress(
        user_id,
        course_id,
        position_seconds,
        watched_delta_seconds,
        direction="handcraft",
    )
    with get_db():
        title_row = get_db().execute(
            "SELECT title FROM courses WHERE id = ?",
            (course_id,),
        ).fetchone()
        title = (
            str(title_row["title"])
            if title_row is not None
            else f"手工课程 {course_id}"
        )
        viewed_at = str(
            progress.get("last_viewed_at") or progress["updated_at"]
        )
        record_handcraft_learning_outcome(
            user_id,
            "course_view",
            f"course:{course_id}:view",
            viewed_at,
            title,
            source_id=course_id,
        )
        if progress.get("completed_at") is not None:
            record_handcraft_learning_outcome(
                user_id,
                "course_completion",
                f"course:{course_id}:completion",
                str(progress["completed_at"]),
                title,
                source_id=course_id,
            )
    effective_delta = max(
        0,
        int(progress["watched_seconds"]) - int(before["watched_seconds"]),
    )
    if effective_delta > 0:
        try:
            record_duration_points(
                user_id,
                "handcraft",
                f"handcraft-course:{course_id}",
                min(effective_delta, MAX_SEGMENT_SECONDS),
                str(progress["updated_at"]),
                str(progress["watched_seconds"]),
            )
        except Exception as error:
            LOGGER.warning(
                "Handcraft course points recording failed: %s",
                type(error).__name__,
            )
    return progress


def get_handcraft_course_quiz(
    user_id: int,
    course_id: int,
) -> dict | None:
    return get_course_quiz(
        user_id,
        course_id,
        direction="handcraft",
    )


def list_handcraft_course_quiz_attempts(
    user_id: int,
    course_id: int,
) -> list[dict]:
    return list_course_quiz_attempts(
        user_id,
        course_id,
        direction="handcraft",
    )


def submit_handcraft_course_quiz(
    user_id: int,
    course_id: int,
    answers: dict,
) -> dict:
    attempt = submit_course_quiz(
        user_id,
        course_id,
        answers,
        direction="handcraft",
    )
    with get_db():
        title_row = get_db().execute(
            "SELECT title FROM courses WHERE id = ?",
            (course_id,),
        ).fetchone()
        title = (
            str(title_row["title"])
            if title_row is not None
            else f"手工课程 {course_id}"
        )
        record_handcraft_learning_outcome(
            user_id,
            "course_quiz",
            f"course_quiz:{course_id}:{int(attempt['id'])}",
            str(attempt["created_at"]),
            title,
            source_id=int(attempt["id"]),
            score=int(attempt["score"]),
            is_formal=bool(attempt["is_formal"]),
        )
    return attempt


def list_handcraft_learning_outcomes(user_id: int) -> list[dict]:
    from app.handcraft_inheritance.outcomes import (
        list_handcraft_learning_outcomes as project_outcomes,
    )

    return project_outcomes(user_id)
