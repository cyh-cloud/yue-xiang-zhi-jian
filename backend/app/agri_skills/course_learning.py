from __future__ import annotations

from app.agri_skills.errors import AgriNotFoundError, AgriValidationError
from app.agri_skills.providers import get_course_provider
from app.courses.service import list_published_courses
from app.db import get_db
from app.session_manager import utc_now_iso


class DatabaseAgriCourseProvider:
    def list_published_agriculture_courses(
        self,
        student_id: int,
    ) -> list[dict]:
        courses = list_published_courses(student_id, "agriculture")
        return [self._hydrate_course(course) for course in courses]

    def get_course(self, course_id: int) -> dict | None:
        row = get_db().execute(
            """
            SELECT *
            FROM courses
            WHERE id = ?
              AND status = 'published'
              AND direction = 'agriculture'
            """,
            (course_id,),
        ).fetchone()
        return self._hydrate_course(dict(row)) if row else None

    def get_quiz(self, course_id: int) -> dict | None:
        return None

    def _hydrate_course(self, course: dict) -> dict:
        course_id = int(course["id"])
        columns = {
            str(row["name"])
            for row in get_db().execute("PRAGMA table_info(courses)").fetchall()
        }
        duration_value = course.get("duration_seconds")
        duration = (
            int(duration_value)
            if "duration_seconds" in columns and duration_value is not None
            else None
        )
        tag_ids = [
            int(row["tag_id"])
            for row in get_db().execute(
                """
                SELECT tag_id
                FROM course_interest_tags
                WHERE course_id = ?
                ORDER BY tag_id
                """,
                (course_id,),
            ).fetchall()
        ]
        return {
            **course,
            "id": course_id,
            "tag_ids": tag_ids,
            "duration_seconds": duration,
        }


def list_agriculture_courses(student_id: int) -> list[dict]:
    return get_course_provider().list_published_agriculture_courses(student_id)


def list_recommendations(student_id: int) -> list[dict]:
    rows = get_db().execute(
        """
        WITH ranked AS (
            SELECT
                c.id,
                c.title,
                c.summary,
                c.teacher_name,
                c.published_at,
                (
                    SELECT COUNT(DISTINCT cit.tag_id)
                    FROM course_interest_tags cit
                    JOIN student_interest_tags sit
                      ON sit.tag_id = cit.tag_id
                     AND sit.user_id = :student_id
                    WHERE cit.course_id = c.id
                ) AS tag_match_count,
                p.last_viewed_at,
                p.progress_percent,
                p.completed_at
            FROM courses c
            LEFT JOIN agri_course_progress p
              ON p.course_id = c.id
             AND p.user_id = :student_id
            WHERE c.status = 'published'
              AND c.direction = 'agriculture'
              AND p.completed_at IS NULL
        )
        SELECT *
        FROM ranked
        ORDER BY
            tag_match_count DESC,
            CASE WHEN last_viewed_at IS NOT NULL THEN 1 ELSE 0 END DESC,
            last_viewed_at DESC,
            progress_percent DESC,
            published_at DESC,
            id ASC
        """,
        {"student_id": student_id},
    ).fetchall()
    return [
        {
            "id": int(row["id"]),
            "title": str(row["title"]),
            "summary": str(row["summary"]),
            "teacher_name": str(row["teacher_name"]),
            "published_at": row["published_at"],
            "tag_match_count": int(row["tag_match_count"]),
            "last_viewed_at": row["last_viewed_at"],
            "progress_percent": int(row["progress_percent"] or 0),
            "completed_at": row["completed_at"],
        }
        for row in rows
    ]


def get_course_progress(user_id: int, course_id: int) -> dict:
    if get_course_provider().get_course(course_id) is None:
        raise AgriNotFoundError("课程不存在")

    row = get_db().execute(
        """
        SELECT *
        FROM agri_course_progress
        WHERE user_id = ? AND course_id = ?
        """,
        (user_id, course_id),
    ).fetchone()
    if row is None:
        return {
            "user_id": user_id,
            "course_id": course_id,
            "duration_seconds": None,
            "furthest_position_seconds": 0,
            "resume_position_seconds": 0,
            "progress_percent": 0,
            "watched_seconds": 0,
            "completed_at": None,
            "last_viewed_at": None,
            "updated_at": None,
        }
    return dict(row)


def update_course_progress(
    user_id: int,
    course_id: int,
    position_seconds: int,
    watched_delta_seconds: int,
) -> dict:
    course = get_course_provider().get_course(course_id)
    if course is None:
        raise AgriNotFoundError("课程不存在")

    duration_value = course.get("duration_seconds")
    if (
        not isinstance(duration_value, int)
        or isinstance(duration_value, bool)
        or duration_value <= 0
    ):
        raise AgriValidationError("课程时长不可用")
    if not isinstance(position_seconds, int) or isinstance(position_seconds, bool):
        raise AgriValidationError("观看位置必须是整数")
    if position_seconds < 0 or position_seconds > duration_value:
        raise AgriValidationError("观看位置超出有效范围")
    if (
        not isinstance(watched_delta_seconds, int)
        or isinstance(watched_delta_seconds, bool)
        or watched_delta_seconds < 0
    ):
        raise AgriValidationError("观看时长必须是非负整数")

    now = utc_now_iso()
    progress_percent = (position_seconds * 100) // duration_value
    completed_at = now if progress_percent >= 80 else None

    with get_db() as db:
        db.execute(
            """
            INSERT INTO agri_course_progress (
                user_id, course_id, duration_seconds,
                furthest_position_seconds, resume_position_seconds,
                progress_percent, watched_seconds, completed_at,
                last_viewed_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (user_id, course_id) DO UPDATE SET
                duration_seconds = excluded.duration_seconds,
                furthest_position_seconds = MAX(
                    agri_course_progress.furthest_position_seconds,
                    excluded.furthest_position_seconds
                ),
                resume_position_seconds = excluded.resume_position_seconds,
                progress_percent = MAX(
                    agri_course_progress.progress_percent,
                    excluded.progress_percent
                ),
                watched_seconds = agri_course_progress.watched_seconds
                    + excluded.watched_seconds,
                completed_at = COALESCE(
                    agri_course_progress.completed_at,
                    excluded.completed_at
                ),
                last_viewed_at = excluded.last_viewed_at,
                updated_at = excluded.updated_at
            """,
            (
                user_id,
                course_id,
                duration_value,
                position_seconds,
                position_seconds,
                progress_percent,
                watched_delta_seconds,
                completed_at,
                now,
                now,
            ),
        )
    return get_course_progress(user_id, course_id)
