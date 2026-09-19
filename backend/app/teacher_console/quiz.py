from __future__ import annotations

import json

from app.agri_skills.ai_client import get_ai_client
from app.agri_skills.ai_context import build_ai_messages
from app.db import get_db
from app.teacher_console.course_service import (
    COURSE_DIRECTIONS,
    _get_local_teacher_course,
    edit_course,
    get_teacher_course,
    resolve_teacher_visible_status,
)
from app.teacher_console.errors import (
    ProviderConflictError,
    ProviderUnavailableError,
    ProviderValidationError,
)
from app.teacher_console.review_adapter import CourseReviewAdapter
from app.teacher_console.time_utils import now_shanghai_iso


AI_UNAVAILABLE_MESSAGE = "AI 服务暂时不可用"
QUESTION_TYPES = {"single_choice", "true_false"}


def _provider_unavailable() -> ProviderUnavailableError:
    return ProviderUnavailableError(
        AI_UNAVAILABLE_MESSAGE,
        code="ai_unavailable",
        details={},
    )


def _validation_error(message: str) -> ProviderValidationError:
    return ProviderValidationError(
        message,
        code="quiz_validation_failed",
        details={},
    )


def _normalize_questions(value) -> list[dict]:
    if not isinstance(value, list) or not 3 <= len(value) <= 5:
        raise ValueError("quiz questions must contain 3 to 5 items")

    questions = []
    question_ids = set()
    for question in value:
        if not isinstance(question, dict):
            raise ValueError("quiz question must be an object")

        question_id = question.get("id")
        if not isinstance(question_id, str) or not question_id.strip():
            raise ValueError("quiz question id must be non-empty text")
        question_id = question_id.strip()
        if question_id in question_ids:
            raise ValueError("quiz question ids must be unique")

        question_type = question.get("type")
        if question_type not in QUESTION_TYPES:
            raise ValueError("quiz question type is invalid")

        prompt = question.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("quiz prompt must be non-empty text")

        options = question.get("options")
        if not isinstance(options, list) or not options:
            raise ValueError("quiz options must be a non-empty list")
        normalized_options = []
        for option in options:
            if not isinstance(option, str) or not option.strip():
                raise ValueError("quiz options must be non-empty text")
            normalized_options.append(option.strip())

        answer = question.get("answer")
        if (
            not isinstance(answer, str)
            or answer.strip() not in normalized_options
        ):
            raise ValueError("quiz answer must exist in options")

        questions.append(
            {
                "id": question_id,
                "type": question_type,
                "prompt": prompt.strip(),
                "options": normalized_options,
                "answer": answer.strip(),
            }
        )
        question_ids.add(question_id)

    return questions


def _normalize_quiz_questions(value, *, enabled: bool) -> list[dict]:
    if not isinstance(value, list):
        raise _validation_error("测验题目必须为列表")
    if not enabled:
        return []
    try:
        return _normalize_questions(value)
    except (TypeError, ValueError) as error:
        raise _validation_error("测验配置无效") from error


def _normalize_scoring_rule(value) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _validation_error("评分规则不能为空")
    return value.strip()


def generate_course_quiz(
    teacher_id: int,
    course_id: int,
    *,
    summary: str,
    direction: str,
) -> dict:
    get_teacher_course(teacher_id, course_id)
    if not isinstance(summary, str) or not summary.strip():
        raise _validation_error("课程简介不能为空")
    if direction not in COURSE_DIRECTIONS:
        raise _validation_error("学习方向无效")
    try:
        payload = get_ai_client().complete_json(
            build_ai_messages(
                "teacher_quiz_generate",
                {
                    "course_summary": summary,
                    "course_direction": direction,
                },
            ),
            call_point="teacher_quiz_generate",
        )
        if not isinstance(payload, dict):
            raise ValueError("AI quiz payload must be an object")
        questions = _normalize_questions(payload.get("questions"))
    except Exception as error:
        raise _provider_unavailable() from error
    return {"questions": questions}


def get_teacher_course_quiz(
    teacher_id: int,
    course_id: int,
) -> dict | None:
    _get_local_teacher_course(teacher_id, course_id)
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
    try:
        questions = json.loads(row["questions_json"] or "[]")
    except (TypeError, ValueError) as error:
        raise _validation_error("已保存的测验配置无效") from error
    if not isinstance(questions, list):
        raise _validation_error("已保存的测验配置无效")
    return {
        "enabled": bool(row["enabled"]),
        "scoring_rule": str(row["scoring_rule"] or ""),
        "questions": questions,
    }


def _course_payload(course: dict) -> dict:
    return {
        "title": course["title"],
        "direction": course["direction"],
        "summary": course["summary"],
        "content_tags": list(course["content_tags"]),
        "duration_seconds": course["duration_seconds"],
        "media_source_type": course["media_source_type"],
        "media_url": course["media_url"],
    }


def _visible_status(course: dict) -> str:
    review = CourseReviewAdapter().read(int(course["id"]))
    if review is not None and not isinstance(review, dict):
        raise _validation_error("审核服务返回无效数据")
    return resolve_teacher_visible_status(
        course,
        review.get("review_status") if isinstance(review, dict) else None,
    )


def _write_draft_quiz(
    course: dict,
    expected_version: int,
    quiz: dict,
) -> None:
    now = now_shanghai_iso()
    db = get_db()
    with db:
        cursor = db.execute(
            """
            UPDATE courses
            SET version = version + 1,
                updated_at = ?
            WHERE id = ?
              AND teacher_id = ?
              AND status = 'draft'
              AND version = ?
            """,
            (
                now,
                int(course["id"]),
                int(course["teacher_id"]),
                expected_version,
            ),
        )
        if cursor.rowcount != 1:
            raise ProviderConflictError(
                "课程版本或状态已变化",
                code="course_version_conflict",
                details={"course_id": int(course["id"])},
            )
        db.execute(
            """
            INSERT INTO course_quizzes (
                course_id, enabled, scoring_rule, questions_json, updated_at
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(course_id) DO UPDATE SET
                enabled = excluded.enabled,
                scoring_rule = excluded.scoring_rule,
                questions_json = excluded.questions_json,
                updated_at = excluded.updated_at
            """,
            (
                int(course["id"]),
                1 if quiz["enabled"] else 0,
                quiz["scoring_rule"],
                json.dumps(quiz["questions"], ensure_ascii=False),
                now,
            ),
        )


def save_course_quiz(
    teacher_id: int,
    course_id: int,
    expected_version: int,
    enabled: bool,
    questions,
    scoring_rule: str = "all_correct",
) -> dict:
    if (
        isinstance(expected_version, bool)
        or not isinstance(expected_version, int)
        or expected_version <= 0
    ):
        raise _validation_error("expected_version 必须为正整数")
    if not isinstance(enabled, bool):
        raise _validation_error("enabled 必须为布尔值")

    course = get_teacher_course(teacher_id, course_id)
    actual_version = int(course["version"])
    if actual_version != expected_version:
        raise ProviderConflictError(
            "课程版本已变化",
            code="course_version_conflict",
            details={
                "course_id": int(course["id"]),
                "expected_version": expected_version,
                "actual_version": actual_version,
            },
        )

    quiz = {
        "enabled": enabled,
        "scoring_rule": _normalize_scoring_rule(scoring_rule),
        "questions": _normalize_quiz_questions(
            questions,
            enabled=enabled,
        ),
    }
    current = get_teacher_course_quiz(teacher_id, course_id)
    if current == quiz:
        return current

    if _visible_status(course) == "draft":
        _write_draft_quiz(course, expected_version, quiz)
    else:
        edit_course(
            teacher_id,
            course_id,
            expected_version,
            _course_payload(course),
            quiz_override=quiz,
        )

    return get_teacher_course_quiz(teacher_id, course_id)
