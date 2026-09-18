from __future__ import annotations

from app.db import get_db


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


def record_handcraft_learning_outcome(
    user_id: int,
    outcome_type: str,
    source_key: str,
    created_at: str,
    summary: str,
    *,
    source_id: int | None = None,
    score: int | None = None,
    is_formal: bool = False,
) -> None:
    get_db().execute(
        """
        INSERT INTO handcraft_learning_outcomes (
            user_id, outcome_type, source_key, source_id, created_at,
            source_available, summary, score, is_formal, archive_written
        )
        VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?, 0)
        ON CONFLICT (user_id, outcome_type, source_key) DO NOTHING
        """,
        (
            user_id,
            outcome_type,
            source_key,
            source_id,
            created_at,
            summary,
            score,
            int(is_formal),
        ),
    )


def _course_id_from_source_key(
    outcome_type: str,
    source_key: str,
) -> int | None:
    prefix = "course_quiz:" if outcome_type == "course_quiz" else "course:"
    if not source_key.startswith(prefix):
        return None
    value = source_key[len(prefix):].split(":", 1)[0]
    return int(value) if value.isdigit() else None


def _craft_key_from_source_key(source_key: str) -> str | None:
    parts = source_key.split(":", 2)
    return parts[1] if len(parts) >= 2 and parts[1] else None


def _backfill_course_outcomes(user_id: int) -> None:
    db = get_db()
    owns_transaction = not db.in_transaction
    try:
        progress_rows = db.execute(
            """
            SELECT
                progress.course_id,
                progress.last_viewed_at,
                progress.updated_at,
                progress.completed_at,
                courses.title
            FROM agri_course_progress AS progress
            JOIN courses ON courses.id = progress.course_id
            WHERE progress.user_id = ? AND courses.direction = 'handcraft'
            """,
            (user_id,),
        ).fetchall()
        for row in progress_rows:
            viewed_at = row["last_viewed_at"] or row["updated_at"]
            record_handcraft_learning_outcome(
                user_id,
                "course_view",
                f"course:{int(row['course_id'])}:view",
                str(viewed_at),
                str(row["title"]),
                source_id=int(row["course_id"]),
            )
            if row["completed_at"] is not None:
                record_handcraft_learning_outcome(
                    user_id,
                    "course_completion",
                    f"course:{int(row['course_id'])}:completion",
                    str(row["completed_at"]),
                    str(row["title"]),
                    source_id=int(row["course_id"]),
                )

        attempt_rows = db.execute(
            """
            SELECT attempts.id, attempts.course_id, attempts.score,
                   attempts.is_formal, attempts.created_at, courses.title
            FROM agri_course_quiz_attempts AS attempts
            JOIN courses ON courses.id = attempts.course_id
            WHERE attempts.user_id = ? AND courses.direction = 'handcraft'
            """,
            (user_id,),
        ).fetchall()
        for row in attempt_rows:
            record_handcraft_learning_outcome(
                user_id,
                "course_quiz",
                f"course_quiz:{int(row['course_id'])}:{int(row['id'])}",
                str(row["created_at"]),
                str(row["title"]),
                source_id=int(row["id"]),
                score=int(row["score"]),
                is_formal=bool(row["is_formal"]),
            )
        if owns_transaction:
            db.commit()
    except Exception:
        if owns_transaction:
            db.rollback()
        raise


def list_handcraft_learning_outcomes(user_id: int) -> list[dict]:
    from app.handcraft_inheritance.course_learning import (
        list_handcraft_courses,
    )
    from app.handcraft_inheritance.crafts import get_craft

    _backfill_course_outcomes(user_id)
    available_course_ids = {
        int(course["id"]) for course in list_handcraft_courses(user_id)
    }
    rows = get_db().execute(
        """
        SELECT *
        FROM handcraft_learning_outcomes
        WHERE user_id = ?
        ORDER BY created_at, outcome_type, source_key, id
        """,
        (user_id,),
    ).fetchall()

    outcomes = []
    for row in rows:
        outcome_type = str(row["outcome_type"])
        source_key = str(row["source_key"])
        if outcome_type.startswith("course"):
            course_id = _course_id_from_source_key(
                outcome_type,
                source_key,
            )
            source_available = (
                course_id in available_course_ids
                if course_id is not None
                else False
            )
        else:
            craft_key = _craft_key_from_source_key(source_key)
            try:
                source_available = bool(
                    craft_key is not None
                    and get_craft(craft_key)["available"]
                )
            except Exception:
                source_available = False
        outcomes.append(
            _outcome(
                outcome_type,
                int(
                    row["source_id"]
                    if row["source_id"] is not None
                    else row["id"]
                ),
                str(row["created_at"]),
                str(row["summary"]),
                (
                    int(row["score"])
                    if row["score"] is not None
                    else None
                ),
                bool(row["is_formal"]),
            )
        )
        outcomes[-1]["source_available"] = source_available
    return outcomes
