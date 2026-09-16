from __future__ import annotations

import json

from app.agri_skills.ai_client import get_ai_client
from app.agri_skills.ai_context import build_ai_messages
from app.agri_skills.errors import (
    AgriNotFoundError,
    AgriValidationError,
    AiUnavailableError,
)
from app.agri_skills.providers import (
    get_course_provider,
    is_eligible_course,
    list_provider_courses,
)
from app.courses.service import list_published_courses as list_published_course_rows
from app.db import get_db
from app.session_manager import utc_now_iso


AI_UNAVAILABLE_MESSAGE = "AI 服务暂时不可用"
COURSE_QUIZ_QUESTION_TYPES = {"single_choice", "true_false"}
PLACEHOLDER_COURSE_DURATION_SECONDS = 300


def _course_table_columns() -> set[str]:
    return {
        str(row["name"])
        for row in get_db().execute("PRAGMA table_info(courses)").fetchall()
    }


class DatabaseAgriCourseProvider:
    def list_published_courses(
        self,
        student_id: int,
        direction: str,
    ) -> list[dict]:
        courses = list_published_course_rows(student_id, direction)
        return [self._hydrate_course(course) for course in courses]

    def list_published_agriculture_courses(self, student_id: int) -> list[dict]:
        return self.list_published_courses(student_id, "agriculture")

    def get_course(self, course_id: int) -> dict | None:
        row = get_db().execute(
            """
            SELECT *
            FROM courses
            WHERE id = ?
              AND status = 'published'
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
        if "duration_seconds" not in columns:
            duration = PLACEHOLDER_COURSE_DURATION_SECONDS
        else:
            duration_value = course.get("duration_seconds")
            try:
                duration = int(duration_value)
            except (TypeError, ValueError):
                duration = None
            if (
                isinstance(duration_value, bool)
                or duration is None
                or duration <= 0
            ):
                duration = None
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


def list_courses(student_id: int, direction: str) -> list[dict]:
    return [
        course
        for course in list_provider_courses(student_id, direction)
        if is_eligible_course(course, direction)
    ]


def list_agriculture_courses(student_id: int) -> list[dict]:
    return list_courses(student_id, "agriculture")


def _is_legacy_course_provider(provider: object) -> bool:
    return not callable(getattr(provider, "list_published_courses", None))


def _require_course(course_id: int, direction: str) -> dict:
    provider = get_course_provider()
    course = provider.get_course(course_id)
    if not isinstance(course, dict):
        raise AgriNotFoundError("课程不存在")
    if _is_legacy_course_provider(provider) and "direction" not in course:
        course = {**course, "direction": "agriculture"}
    if not is_eligible_course(course, direction):
        raise AgriNotFoundError("课程不存在")
    return course


def list_recommendations(
    student_id: int,
    direction: str = "agriculture",
) -> list[dict]:
    has_duration = "duration_seconds" in _course_table_columns()
    duration_projection = (
        "c.duration_seconds"
        if has_duration
        else str(PLACEHOLDER_COURSE_DURATION_SECONDS)
    )
    duration_filter = (
        "\n              AND c.duration_seconds > 0" if has_duration else ""
    )
    rows = get_db().execute(
        f"""
        WITH ranked AS (
            SELECT
                c.id,
                c.title,
                c.direction,
                c.summary,
                c.teacher_name,
                c.published_at,
                {duration_projection} AS duration_seconds,
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
              AND c.direction = :direction
              {duration_filter}
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
        {"student_id": student_id, "direction": direction},
    ).fetchall()
    courses = [
        {
            "id": int(row["id"]),
            "title": str(row["title"]),
            "direction": str(row["direction"]),
            "summary": str(row["summary"]),
            "teacher_name": str(row["teacher_name"]),
            "published_at": row["published_at"],
            "duration_seconds": row["duration_seconds"],
            "tag_match_count": int(row["tag_match_count"]),
            "last_viewed_at": row["last_viewed_at"],
            "progress_percent": int(row["progress_percent"] or 0),
            "completed_at": row["completed_at"],
        }
        for row in rows
    ]
    return [
        course
        for course in courses
        if is_eligible_course(course, direction)
    ]


def get_course_progress(
    user_id: int,
    course_id: int,
    direction: str = "agriculture",
) -> dict:
    _require_course(course_id, direction)

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
    direction: str = "agriculture",
) -> dict:
    course = _require_course(course_id, direction)

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
                    + MIN(
                        excluded.watched_seconds,
                        MAX(
                            0,
                            excluded.furthest_position_seconds
                            - agri_course_progress.furthest_position_seconds
                        )
                    ),
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
    return get_course_progress(user_id, course_id, direction)


def _normalize_course_quiz(quiz: dict | None) -> list[dict] | None:
    if not isinstance(quiz, dict):
        return None
    if quiz.get("enabled") is False or quiz.get("is_enabled") is False:
        return None

    raw_questions = quiz.get("questions")
    if not isinstance(raw_questions, list) or not raw_questions:
        return None

    questions = []
    seen_ids = set()
    for raw_question in raw_questions:
        if not isinstance(raw_question, dict):
            return None

        question_id = str(raw_question.get("id", "")).strip()
        question_type = raw_question.get(
            "type",
            raw_question.get("question_type"),
        )
        prompt = str(raw_question.get("prompt", "")).strip()
        options = raw_question.get("options")
        answer = str(raw_question.get("answer", "")).strip()
        if (
            not question_id
            or question_id in seen_ids
            or question_type not in COURSE_QUIZ_QUESTION_TYPES
            or not prompt
            or not isinstance(options, list)
            or not options
            or not answer
        ):
            return None

        normalized_options = [str(option) for option in options]
        if answer not in normalized_options:
            return None
        questions.append(
            {
                "id": question_id,
                "type": question_type,
                "prompt": prompt,
                "options": normalized_options,
                "answer": answer,
            }
        )
        seen_ids.add(question_id)
    return questions


def _load_available_course_quiz(
    user_id: int,
    course_id: int,
    direction: str,
) -> tuple[dict, list[dict]] | None:
    try:
        course = _require_course(course_id, direction)
    except AgriNotFoundError:
        return None

    progress = get_db().execute(
        """
        SELECT completed_at
        FROM agri_course_progress
        WHERE user_id = ? AND course_id = ?
        """,
        (user_id, course_id),
    ).fetchone()
    if progress is None or progress["completed_at"] is None:
        return None

    questions = _normalize_course_quiz(
        get_course_provider().get_quiz(course_id)
    )
    if questions is None:
        return None
    return course, questions


def _public_quiz_questions(questions: list[dict]) -> list[dict]:
    return [
        {
            "id": question["id"],
            "type": question["type"],
            "prompt": question["prompt"],
            "options": list(question["options"]),
        }
        for question in questions
    ]


def get_course_quiz(
    user_id: int,
    course_id: int,
    direction: str = "agriculture",
) -> dict | None:
    available = _load_available_course_quiz(
        user_id,
        course_id,
        direction,
    )
    if available is None:
        return None
    _, questions = available
    return {
        "course_id": course_id,
        "questions": _public_quiz_questions(questions),
    }


def _validate_course_quiz_answers(
    questions: list[dict],
    answers: dict,
) -> dict:
    if not isinstance(answers, dict):
        raise AgriValidationError("测验答案格式不正确")

    expected_ids = {question["id"] for question in questions}
    if set(answers) != expected_ids:
        raise AgriValidationError("测验答案不完整")

    normalized = {}
    for question in questions:
        question_id = question["id"]
        answer = answers[question_id]
        if not isinstance(answer, str) or answer not in question["options"]:
            raise AgriValidationError("测验答案不在选项中")
        normalized[question_id] = answer
    return normalized


def _validate_course_quiz_grade(
    payload: dict,
    questions: list[dict],
) -> tuple[int, list[dict]]:
    if not isinstance(payload, dict):
        raise AiUnavailableError(AI_UNAVAILABLE_MESSAGE)

    score = payload.get("score")
    if (
        not isinstance(score, int)
        or isinstance(score, bool)
        or not 0 <= score <= 100
    ):
        raise AiUnavailableError(AI_UNAVAILABLE_MESSAGE)

    graded_questions = payload.get("questions")
    if (
        not isinstance(graded_questions, list)
        or len(graded_questions) != len(questions)
    ):
        raise AiUnavailableError(AI_UNAVAILABLE_MESSAGE)

    grades_by_id = {}
    for graded_question in graded_questions:
        if not isinstance(graded_question, dict):
            raise AiUnavailableError(AI_UNAVAILABLE_MESSAGE)
        question_id = str(graded_question.get("id", "")).strip()
        correct = graded_question.get("correct")
        explanation = str(graded_question.get("explanation", "")).strip()
        if (
            not question_id
            or question_id in grades_by_id
            or not isinstance(correct, bool)
            or not explanation
        ):
            raise AiUnavailableError(AI_UNAVAILABLE_MESSAGE)
        grades_by_id[question_id] = {
            "correct": correct,
            "explanation": explanation,
        }

    if set(grades_by_id) != {question["id"] for question in questions}:
        raise AiUnavailableError(AI_UNAVAILABLE_MESSAGE)

    normalized = []
    for question in questions:
        grade = grades_by_id[question["id"]]
        normalized.append(
            {
                "id": question["id"],
                "type": question["type"],
                "prompt": question["prompt"],
                "options": list(question["options"]),
                "correct": grade["correct"],
                "explanation": grade["explanation"],
            }
        )
    return score, normalized


def submit_course_quiz(
    user_id: int,
    course_id: int,
    answers: dict,
    direction: str = "agriculture",
) -> dict:
    available = _load_available_course_quiz(
        user_id,
        course_id,
        direction,
    )
    if available is None:
        raise AgriNotFoundError("暂无可用测验")
    course, questions = available
    normalized_answers = _validate_course_quiz_answers(questions, answers)

    try:
        payload = get_ai_client().complete_json(
            build_ai_messages(
                "course_quiz_grade",
                {
                    "course_summary": str(course.get("summary", "")).strip(),
                    "questions": questions,
                    "answers": normalized_answers,
                },
            ),
            call_point="course_quiz_grade",
        )
    except AiUnavailableError as error:
        raise AiUnavailableError(AI_UNAVAILABLE_MESSAGE) from error

    score, graded_questions = _validate_course_quiz_grade(payload, questions)
    result = {"score": score, "questions": graded_questions}
    now = utc_now_iso()

    with get_db() as db:
        db.execute(
            """
            UPDATE agri_course_quiz_attempts
            SET is_formal = 0
            WHERE user_id = ? AND course_id = ?
            """,
            (user_id, course_id),
        )
        cursor = db.execute(
            """
            INSERT INTO agri_course_quiz_attempts (
                user_id, course_id, answers_json, result_json,
                score, is_formal, created_at
            )
            VALUES (?, ?, ?, ?, ?, 1, ?)
            """,
            (
                user_id,
                course_id,
                json.dumps(normalized_answers, ensure_ascii=False),
                json.dumps(result, ensure_ascii=False),
                score,
                now,
            ),
        )

    return {
        "id": int(cursor.lastrowid),
        "course_id": course_id,
        "score": score,
        "is_formal": True,
        "questions": graded_questions,
        "created_at": now,
    }
