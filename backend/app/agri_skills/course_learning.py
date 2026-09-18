from __future__ import annotations

import json
from datetime import datetime

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
        row = get_db().execute(
            """
            SELECT enabled, scoring_rule, questions_json
            FROM course_quizzes
            WHERE course_id = ?
            """,
            (course_id,),
        ).fetchone()
        if row is None:
            return None
        return {
            "enabled": bool(row["enabled"]),
            "scoring_rule": str(row["scoring_rule"]),
            "questions": json.loads(row["questions_json"]),
        }

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


def _list_provider_recommendations(
    student_id: int,
    direction: str,
) -> list[dict]:
    courses = list_courses(student_id, direction)
    provider = get_course_provider()
    if direction == "agriculture" and _is_legacy_course_provider(provider):
        from app.teacher_console.providers import (
            DatabaseTeacherCourseProvider,
        )

        legacy_courses = DatabaseTeacherCourseProvider().list_published_courses(
            student_id,
            direction,
        )
        by_id = {
            int(course["id"]): course
            for course in legacy_courses
        }
        by_id.update(
            {
                int(course["id"]): course
                for course in courses
            }
        )
        courses = list(by_id.values())

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
    progress_by_course = {
        int(row["course_id"]): dict(row)
        for row in get_db().execute(
            """
            SELECT course_id, last_viewed_at, progress_percent, completed_at
            FROM agri_course_progress
            WHERE user_id = ?
            """,
            (student_id,),
        ).fetchall()
    }

    recommendations = []
    for course in courses:
        course_id = int(course["id"])
        progress = progress_by_course.get(course_id)
        if progress is not None and progress["completed_at"] is not None:
            continue
        tag_ids = list(course.get("tag_ids", []))
        recommendations.append(
            {
                "id": course_id,
                "title": str(course["title"]),
                "direction": str(course["direction"]),
                "status": str(course.get("status") or "published"),
                "summary": str(course["summary"]),
                "teacher_name": str(course["teacher_name"]),
                "published_at": str(course["published_at"]),
                "duration_seconds": int(course["duration_seconds"]),
                "media_url": course.get("media_url"),
                "tag_ids": tag_ids,
                "content_tags": list(course.get("content_tags", [])),
                "tag_match_count": len(
                    set(tag_ids).intersection(student_tag_ids)
                ),
                "last_viewed_at": (
                    progress["last_viewed_at"] if progress else None
                ),
                "progress_percent": (
                    int(progress["progress_percent"] or 0)
                    if progress
                    else 0
                ),
                "completed_at": progress["completed_at"] if progress else None,
            }
        )

    recommendations.sort(key=lambda item: int(item["id"]))
    recommendations.sort(
        key=lambda item: _course_time(item.get("published_at")),
        reverse=True,
    )
    recommendations.sort(
        key=lambda item: int(item.get("progress_percent", 0)),
        reverse=True,
    )
    recommendations.sort(
        key=lambda item: str(item.get("last_viewed_at") or ""),
        reverse=True,
    )
    recommendations.sort(
        key=lambda item: item.get("last_viewed_at") is not None,
        reverse=True,
    )
    recommendations.sort(
        key=lambda item: int(item.get("tag_match_count", 0)),
        reverse=True,
    )
    return recommendations


def _course_time(value: object) -> datetime:
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def list_recommendations(
    student_id: int,
    direction: str = "agriculture",
) -> list[dict]:
    return _list_provider_recommendations(student_id, direction)


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
            "quiz_available": False,
        }
    progress = dict(row)
    progress["quiz_available"] = (
        row["completed_at"] is not None
        and _normalize_course_quiz(
            get_course_provider().get_quiz(course_id),
            strict=direction in {"ecommerce", "handcraft"},
        )
        is not None
    )
    return progress


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


def _normalize_course_quiz(
    quiz: dict | None,
    *,
    strict: bool = True,
) -> list[dict] | None:
    if not isinstance(quiz, dict):
        return None
    if strict:
        scoring_rule = quiz.get("scoring_rule")
        if (
            quiz.get("enabled") is not True
            or not isinstance(scoring_rule, str)
            or not scoring_rule.strip()
        ):
            return None
    elif quiz.get("enabled") is False or quiz.get("is_enabled") is False:
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
            or not all(
                isinstance(option, str) and bool(option.strip())
                for option in options
            )
        ):
            return None

        normalized_options = [option.strip() for option in options]
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
        get_course_provider().get_quiz(course_id),
        strict=direction in {"ecommerce", "handcraft"},
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


def list_course_quiz_attempts(
    user_id: int,
    course_id: int,
    direction: str = "agriculture",
) -> list[dict]:
    _require_course(course_id, direction)
    rows = get_db().execute(
        """
        SELECT id, user_id, course_id, answers_json, result_json, score,
               is_formal, created_at
        FROM agri_course_quiz_attempts
        WHERE user_id = ? AND course_id = ?
        ORDER BY created_at DESC, id DESC
        """,
        (user_id, course_id),
    ).fetchall()

    attempts = []
    for index, row in enumerate(rows):
        result = json.loads(row["result_json"])
        attempts.append(
            {
                "id": int(row["id"]),
                "course_id": int(row["course_id"]),
                "answers": json.loads(row["answers_json"]),
                "score": int(row["score"]),
                "questions": result.get("questions", []),
                "is_formal": bool(row["is_formal"]),
                "is_current": bool(row["is_formal"]),
                "is_latest": index == 0,
                "created_at": str(row["created_at"]),
            }
        )
    return attempts


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

    ai_context = {
        "course_summary": str(course.get("summary", "")).strip(),
        "questions": questions,
        "answers": normalized_answers,
    }
    if direction != "agriculture":
        ai_context["course_direction"] = direction

    try:
        payload = get_ai_client().complete_json(
            build_ai_messages(
                "course_quiz_grade",
                ai_context,
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
        "is_current": True,
        "is_latest": True,
        "questions": graded_questions,
        "created_at": now,
    }
