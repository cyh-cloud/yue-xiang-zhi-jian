from __future__ import annotations

import json

from flask import Flask

from app.agri_skills.providers import set_course_provider
from app.db import get_db
from app.teacher_console.course_service import resolve_teacher_visible_status
from app.teacher_console.errors import ProviderValidationError
from app.teacher_console.review_adapter import CourseReviewAdapter
from app.teacher_console.time_utils import parse_provider_time


_PUBLIC_COURSE_FIELDS = (
    "id",
    "title",
    "direction",
    "status",
    "summary",
    "teacher_name",
    "published_at",
    "duration_seconds",
    "media_url",
    "tag_ids",
    "content_tags",
)


class DatabaseTeacherCourseProvider:
    def list_published_courses(
        self,
        student_id: int,
        direction: str,
    ) -> list[dict]:
        return [
            _public_course(course, include_interest_match=True)
            for course in self._list_direction(student_id, direction)
            if course["status"] == "published"
        ]

    def get_course(self, course_id: int) -> dict | None:
        row = get_db().execute(
            "SELECT * FROM courses WHERE id = ?",
            (course_id,),
        ).fetchone()
        if row is None:
            return None
        course = self._hydrate(dict(row))
        if course["status"] != "published":
            return None
        return _public_course(course)

    def get_quiz(self, course_id: int) -> dict | None:
        if self.get_course(course_id) is None:
            return None
        row = get_db().execute(
            "SELECT * FROM course_quizzes WHERE course_id = ?",
            (course_id,),
        ).fetchone()
        return _quiz_payload(row) if row is not None else None

    def _list_direction(
        self,
        student_id: int,
        direction: str,
    ) -> list[dict]:
        rows = get_db().execute(
            "SELECT * FROM courses WHERE direction = ?",
            (direction,),
        ).fetchall()
        student_tag_ids = {
            int(row["tag_id"])
            for row in get_db().execute(
                """
                SELECT tag_id
                FROM student_interest_tags
                WHERE user_id = ?
                """,
                (student_id,),
            ).fetchall()
        }
        courses = []
        for row in rows:
            course = self._hydrate(dict(row))
            course["interest_match"] = bool(
                set(course["tag_ids"]).intersection(student_tag_ids)
            )
            if course["status"] == "published":
                courses.append(course)
        courses.sort(
            key=lambda course: (
                bool(course["interest_match"]),
                parse_provider_time(course["published_at"]),
                int(course["id"]),
            ),
            reverse=True,
        )
        return courses

    def _hydrate(self, course: dict) -> dict:
        course_id = int(course["id"])
        content_tags = _content_tags(course)
        tag_ids = _tag_ids(get_db(), course_id, content_tags)
        review = CourseReviewAdapter().read(course_id)
        if review is not None and not isinstance(review, dict):
            raise ProviderValidationError(
                "审核服务返回无效数据",
                code="review_response_invalid",
                details={"course_id": course_id},
            )
        review_status = (
            review.get("review_status")
            if isinstance(review, dict)
            else None
        )
        status = resolve_teacher_visible_status(course, review_status)
        if status != "published":
            published_at = None
        elif course.get("teacher_id") is None:
            published_at = course.get("published_at")
        else:
            published_at = (
                review.get("published_at")
                if isinstance(review, dict)
                else None
            )
        if status == "published":
            try:
                parse_provider_time(published_at)
            except (TypeError, ValueError):
                status = "pending"
                published_at = None
        if (
            course.get("teacher_id") is None
            and not str(course.get("summary") or "").strip()
        ):
            course["summary"] = str(course.get("title") or "")

        return {
            **course,
            "id": course_id,
            "status": status,
            "published_at": published_at,
            "content_tags": content_tags,
            "tag_ids": tag_ids,
        }


def install_default_teacher_console_services(app: Flask) -> None:
    if "agri_course_provider" not in app.extensions:
        set_course_provider(app, DatabaseTeacherCourseProvider())


def _content_tags(course: dict) -> list[str]:
    try:
        content_tags = json.loads(course.get("content_tags_json") or "[]")
    except (TypeError, ValueError):
        content_tags = []
    if not isinstance(content_tags, list):
        return []
    return [str(tag) for tag in content_tags if isinstance(tag, str)]


def _public_course(
    course: dict,
    *,
    include_interest_match: bool = False,
) -> dict:
    public_course = {
        field: course.get(field)
        for field in _PUBLIC_COURSE_FIELDS
    }
    if include_interest_match:
        public_course["interest_match"] = bool(
            course.get("interest_match", False)
        )
    return public_course


def _tag_ids(db, course_id: int, content_tags: list[str]) -> list[int]:
    if content_tags:
        placeholders = ", ".join("?" for _ in content_tags)
        rows = db.execute(
            f"""
            SELECT id
            FROM interest_tags
            WHERE is_active = 1
              AND group_key IN ('crop', 'skill')
              AND name IN ({placeholders})
            ORDER BY id
            """,
            tuple(content_tags),
        ).fetchall()
        return [int(row["id"]) for row in rows]

    rows = db.execute(
        """
        SELECT cit.tag_id
        FROM course_interest_tags cit
        JOIN interest_tags it ON it.id = cit.tag_id
        WHERE cit.course_id = ?
          AND it.is_active = 1
          AND it.group_key IN ('crop', 'skill')
        ORDER BY cit.tag_id
        """,
        (course_id,),
    ).fetchall()
    return [int(row["tag_id"]) for row in rows]


def _quiz_payload(row) -> dict:
    try:
        questions = json.loads(row["questions_json"] or "[]")
    except (TypeError, ValueError):
        questions = []
    if not isinstance(questions, list):
        questions = []
    return {
        "enabled": bool(row["enabled"]),
        "scoring_rule": str(row["scoring_rule"] or ""),
        "questions": questions,
    }
