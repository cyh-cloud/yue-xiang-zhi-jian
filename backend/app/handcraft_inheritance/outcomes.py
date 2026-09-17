from __future__ import annotations


def _outcome(
    outcome_type: str,
    source_id: int,
    created_at: str,
    summary: str,
    score: int | None = None,
    is_formal: bool = False,
) -> dict:
    return {
        "outcome_type": outcome_type,
        "source_id": source_id,
        "created_at": created_at,
        "source_available": True,
        "summary": summary,
        "score": score,
        "is_formal": is_formal,
        "archive_written": False,
    }


def list_handcraft_learning_outcomes(user_id: int) -> list[dict]:
    from app.handcraft_inheritance.course_learning import (
        get_handcraft_course_progress,
        list_handcraft_course_quiz_attempts,
        list_handcraft_courses,
    )

    outcomes = []
    for course in list_handcraft_courses(user_id):
        course_id = int(course["id"])
        progress = get_handcraft_course_progress(user_id, course_id)
        progress_at = progress.get("last_viewed_at") or progress.get(
            "updated_at"
        )
        if progress_at is not None:
            completed_at = progress.get("completed_at")
            outcomes.append(
                _outcome(
                    (
                        "course_completion"
                        if completed_at is not None
                        else "course_view"
                    ),
                    course_id,
                    str(completed_at or progress_at),
                    str(course["title"]),
                )
            )

        outcomes.extend(
            _outcome(
                "course_quiz",
                int(attempt["id"]),
                str(attempt["created_at"]),
                str(course["title"]),
                int(attempt["score"]),
                bool(attempt["is_formal"]),
            )
            for attempt in list_handcraft_course_quiz_attempts(
                user_id,
                course_id,
            )
        )

    return sorted(
        outcomes,
        key=lambda outcome: (
            outcome["created_at"],
            outcome["outcome_type"],
            outcome["source_id"],
        ),
    )
