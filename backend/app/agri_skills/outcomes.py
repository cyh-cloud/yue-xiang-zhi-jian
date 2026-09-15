from __future__ import annotations

from app.db import get_db


def list_learning_outcomes(
    user_id: int,
    kind: str | None = None,
) -> list[dict]:
    if kind not in {None, "diagnostic_self_test", "course_quiz"}:
        raise ValueError("Unsupported learning outcome kind")

    outcomes = []
    if kind in {None, "diagnostic_self_test"}:
        outcomes.extend(
            {
                "kind": "diagnostic_self_test",
                "source_id": int(row["id"]),
                "diagnosis_session_id": int(row["diagnosis_session_id"]),
                "course_id": None,
                "score": int(row["score"]),
                "is_formal": False,
                "created_at": str(row["created_at"]),
            }
            for row in get_db().execute(
                """
                SELECT a.id, t.diagnosis_session_id, a.score, a.created_at
                FROM agri_self_test_attempts a
                JOIN agri_self_tests t ON t.id = a.self_test_id
                WHERE a.user_id = ?
                ORDER BY a.created_at, a.id
                """,
                (user_id,),
            ).fetchall()
        )

    outcomes.sort(key=lambda item: (item["created_at"], item["source_id"]))
    return outcomes
