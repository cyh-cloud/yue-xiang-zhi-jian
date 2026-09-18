from __future__ import annotations

from app.db import get_db


COURSE_DIRECTIONS = {"agriculture", "ecommerce", "handcraft"}


def list_published_courses(user_id: int, direction: str) -> list[dict]:
    rows = get_db().execute(
        """
        SELECT
            c.id,
            c.title,
            c.direction,
            c.status,
            c.summary,
            c.teacher_name,
            c.duration_seconds,
            c.media_url,
            c.published_at,
            CASE WHEN EXISTS (
                SELECT 1
                FROM course_interest_tags cit
                JOIN student_interest_tags sit
                  ON sit.tag_id = cit.tag_id
                WHERE cit.course_id = c.id
                  AND sit.user_id = ?
            ) THEN 1 ELSE 0 END AS interest_match
        FROM courses c
        WHERE c.status = 'published'
          AND c.direction = ?
        ORDER BY interest_match DESC, c.published_at DESC, c.id DESC
        """,
        (user_id, direction),
    ).fetchall()
    return [
        {
            "id": int(row["id"]),
            "title": str(row["title"]),
            "direction": str(row["direction"]),
            "status": str(row["status"]),
            "summary": str(row["summary"]),
            "teacher_name": str(row["teacher_name"]),
            "duration_seconds": row["duration_seconds"],
            "media_url": row["media_url"],
            "published_at": row["published_at"],
            "interest_match": bool(row["interest_match"]),
        }
        for row in rows
    ]
