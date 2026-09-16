from __future__ import annotations

from app.agri_skills.course_learning import (
    get_course_progress,
    get_course_quiz,
    list_courses,
    list_recommendations,
    submit_course_quiz,
    update_course_progress,
)
from app.db import get_db
from app.ecommerce_training.presets import SIMULATION_SCENES


def list_ecommerce_courses(student_id: int) -> list[dict]:
    return list_courses(student_id, "ecommerce")


def list_ecommerce_recommendations(student_id: int) -> list[dict]:
    return list_recommendations(student_id, "ecommerce")


def get_ecommerce_course_progress(user_id: int, course_id: int) -> dict:
    return get_course_progress(
        user_id,
        course_id,
        direction="ecommerce",
    )


def update_ecommerce_course_progress(
    user_id: int,
    course_id: int,
    position_seconds: int,
    watched_delta_seconds: int,
) -> dict:
    return update_course_progress(
        user_id,
        course_id,
        position_seconds,
        watched_delta_seconds,
        direction="ecommerce",
    )


def get_ecommerce_course_quiz(
    user_id: int,
    course_id: int,
) -> dict | None:
    return get_course_quiz(
        user_id,
        course_id,
        direction="ecommerce",
    )


def submit_ecommerce_course_quiz(
    user_id: int,
    course_id: int,
    answers: dict,
) -> dict:
    return submit_course_quiz(
        user_id,
        course_id,
        answers,
        direction="ecommerce",
    )


def _outcome(
    kind: str,
    source_id: int,
    created_at: str,
    summary: str,
    score: int | None = None,
    is_formal: bool = False,
) -> dict:
    return {
        "kind": kind,
        "source_id": source_id,
        "created_at": created_at,
        "summary": summary,
        "score": score,
        "is_formal": is_formal,
        "archive_written": False,
    }


def _live_script_outcomes(user_id: int) -> list[dict]:
    rows = get_db().execute(
        """
        SELECT id, product_name, created_at
        FROM ecommerce_live_script_versions
        WHERE user_id = ?
        ORDER BY created_at, id
        """,
        (user_id,),
    ).fetchall()
    return [
        _outcome(
            "live_script",
            int(row["id"]),
            str(row["created_at"]),
            str(row["product_name"]),
        )
        for row in rows
    ]


def _simulation_outcomes(user_id: int) -> list[dict]:
    rows = get_db().execute(
        """
        SELECT id, scene_key, total_score, created_at, completed_at
        FROM ecommerce_simulation_trainings
        WHERE user_id = ? AND status = 'completed'
        ORDER BY completed_at, id
        """,
        (user_id,),
    ).fetchall()
    outcomes = []
    for row in rows:
        scene = SIMULATION_SCENES.get(str(row["scene_key"]), {})
        outcomes.append(
            _outcome(
                "simulation_training",
                int(row["id"]),
                str(row["completed_at"] or row["created_at"]),
                str(scene.get("label", row["scene_key"])),
                (
                    int(row["total_score"])
                    if row["total_score"] is not None
                    else None
                ),
            )
        )
    return outcomes


def _course_quiz_outcomes(user_id: int) -> list[dict]:
    rows = get_db().execute(
        """
        SELECT
            attempts.id,
            attempts.score,
            attempts.is_formal,
            attempts.created_at,
            courses.title AS course_title
        FROM agri_course_quiz_attempts AS attempts
        JOIN courses ON courses.id = attempts.course_id
        WHERE attempts.user_id = ?
          AND courses.direction = 'ecommerce'
        ORDER BY attempts.created_at, attempts.id
        """,
        (user_id,),
    ).fetchall()
    return [
        _outcome(
            "course_quiz",
            int(row["id"]),
            str(row["created_at"]),
            str(row["course_title"]),
            int(row["score"]),
            bool(row["is_formal"]),
        )
        for row in rows
    ]


def _course_completion_outcomes(user_id: int) -> list[dict]:
    rows = get_db().execute(
        """
        SELECT
            progress.course_id,
            progress.completed_at,
            courses.title AS course_title
        FROM agri_course_progress AS progress
        JOIN courses ON courses.id = progress.course_id
        WHERE progress.user_id = ?
          AND progress.completed_at IS NOT NULL
          AND courses.direction = 'ecommerce'
        ORDER BY progress.completed_at, progress.course_id
        """,
        (user_id,),
    ).fetchall()
    return [
        _outcome(
            "course_completion",
            int(row["course_id"]),
            str(row["completed_at"]),
            str(row["course_title"]),
        )
        for row in rows
    ]


def list_ecommerce_learning_outcomes(user_id: int) -> list[dict]:
    outcomes = []
    outcomes.extend(_live_script_outcomes(user_id))
    outcomes.extend(_simulation_outcomes(user_id))
    outcomes.extend(_course_quiz_outcomes(user_id))
    outcomes.extend(_course_completion_outcomes(user_id))
    return sorted(
        outcomes,
        key=lambda item: (
            item["created_at"],
            item["kind"],
            item["source_id"],
        ),
    )
