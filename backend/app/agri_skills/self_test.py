from __future__ import annotations

import json

from app.agri_skills.ai_client import get_ai_client
from app.agri_skills.ai_context import build_ai_messages
from app.agri_skills.errors import (
    AgriNotFoundError,
    AgriValidationError,
    AiUnavailableError,
)
from app.db import get_db
from app.session_manager import utc_now_iso


AI_UNAVAILABLE_MESSAGE = "AI 服务暂时不可用"
SELF_TEST_QUESTION_TYPES = {"single_choice", "true_false"}


def validate_self_test(payload: dict) -> list[dict]:
    if not isinstance(payload, dict):
        payload = {}

    questions = payload.get("questions")
    if not isinstance(questions, list) or not 3 <= len(questions) <= 5:
        raise AgriValidationError("自测题目数量必须为 3 至 5")

    normalized = []
    for item in questions:
        if not isinstance(item, dict):
            raise AgriValidationError("自测题目结构不完整")

        question_type = item.get("type")
        prompt = str(item.get("prompt", "")).strip()
        options = item.get("options")
        answer = str(item.get("answer", "")).strip()
        if question_type not in SELF_TEST_QUESTION_TYPES:
            raise AgriValidationError("自测题型不正确")
        if (
            not prompt
            or not isinstance(options, list)
            or not options
            or not answer
        ):
            raise AgriValidationError("自测题目结构不完整")

        normalized_options = [str(option) for option in options]
        if answer not in normalized_options:
            raise AgriValidationError("自测答案不在选项中")
        normalized.append(
            {
                "type": question_type,
                "prompt": prompt,
                "options": normalized_options,
                "answer": answer,
            }
        )
    return normalized


def _public_questions(questions: list[dict]) -> list[dict]:
    return [
        {
            "type": question["type"],
            "prompt": question["prompt"],
            "options": list(question["options"]),
        }
        for question in questions
    ]


def _load_completed_diagnosis(user_id: int, session_id: int) -> str:
    row = get_db().execute(
        """
        SELECT status, conclusion_json
        FROM agri_diagnosis_sessions
        WHERE id = ? AND user_id = ?
        """,
        (session_id, user_id),
    ).fetchone()
    if row is None:
        raise AgriNotFoundError("诊断记录不存在")
    if str(row["status"]) != "completed":
        raise AgriValidationError("仅已完成诊断可生成自测")

    try:
        conclusion = json.loads(str(row["conclusion_json"]))
    except (TypeError, ValueError) as error:
        raise AgriValidationError("诊断结论不完整") from error
    if not isinstance(conclusion, dict):
        raise AgriValidationError("诊断结论不完整")

    cause = str(conclusion.get("cause", "")).strip()
    treatment = str(conclusion.get("treatment", "")).strip()
    if not cause or not treatment:
        raise AgriValidationError("诊断结论不完整")
    return f"病因分析：{cause}\n防治方案：{treatment}"


def generate_self_test(user_id: int, diagnosis_session_id: int) -> dict:
    diagnosis_text = _load_completed_diagnosis(user_id, diagnosis_session_id)

    questions = []
    attempts = 0
    last_error = None
    for attempt in (1, 2):
        attempts = attempt
        try:
            payload = get_ai_client().complete_json(
                build_ai_messages(
                    "selftest_generate",
                    {"diagnosis_text": diagnosis_text},
                ),
                call_point="selftest_generate",
            )
            questions = validate_self_test(payload)
            break
        except (AgriValidationError, AiUnavailableError) as error:
            last_error = error
    else:
        raise AiUnavailableError(AI_UNAVAILABLE_MESSAGE) from last_error

    now = utc_now_iso()
    with get_db():
        cursor = get_db().execute(
            """
            INSERT INTO agri_self_tests (
                diagnosis_session_id, questions_json, created_at
            )
            VALUES (?, ?, ?)
            """,
            (
                diagnosis_session_id,
                json.dumps(questions, ensure_ascii=False),
                now,
            ),
        )

    return {
        "id": int(cursor.lastrowid),
        "diagnosis_session_id": diagnosis_session_id,
        "generation_attempts": attempts,
        "questions": _public_questions(questions),
    }


def _load_self_test(user_id: int, self_test_id: int) -> list[dict]:
    row = get_db().execute(
        """
        SELECT t.questions_json
        FROM agri_self_tests AS t
        JOIN agri_diagnosis_sessions AS s
          ON s.id = t.diagnosis_session_id
        WHERE
          t.id = ?
          AND s.user_id = ?
          AND s.status = 'completed'
        """,
        (self_test_id, user_id),
    ).fetchone()
    if row is None:
        raise AgriNotFoundError("自测不存在")

    try:
        questions = json.loads(str(row["questions_json"]))
    except (TypeError, ValueError) as error:
        raise AgriValidationError("自测题目不完整") from error
    return validate_self_test({"questions": questions})


def _validate_grade_payload(
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
    if not isinstance(graded_questions, list):
        raise AiUnavailableError(AI_UNAVAILABLE_MESSAGE)
    if len(graded_questions) != len(questions):
        raise AiUnavailableError(AI_UNAVAILABLE_MESSAGE)

    normalized = []
    for question, graded_question in zip(questions, graded_questions):
        if not isinstance(graded_question, dict):
            raise AiUnavailableError(AI_UNAVAILABLE_MESSAGE)
        correct = graded_question.get("correct")
        explanation = str(graded_question.get("explanation", "")).strip()
        if not isinstance(correct, bool) or not explanation:
            raise AiUnavailableError(AI_UNAVAILABLE_MESSAGE)
        normalized.append(
            {
                "type": question["type"],
                "prompt": question["prompt"],
                "options": list(question["options"]),
                "correct": correct,
                "explanation": explanation,
            }
        )
    return score, normalized


def submit_self_test(
    user_id: int,
    self_test_id: int,
    answers: dict,
) -> dict:
    if not isinstance(answers, dict):
        raise AgriValidationError("自测答案格式不正确")
    questions = _load_self_test(user_id, self_test_id)

    try:
        payload = get_ai_client().complete_json(
            build_ai_messages(
                "selftest_grade",
                {"questions": questions, "answers": answers},
            ),
            call_point="selftest_grade",
        )
    except AiUnavailableError as error:
        raise AiUnavailableError(AI_UNAVAILABLE_MESSAGE) from error

    score, graded_questions = _validate_grade_payload(payload, questions)
    result = {"score": score, "questions": graded_questions}

    now = utc_now_iso()
    with get_db():
        cursor = get_db().execute(
            """
            INSERT INTO agri_self_test_attempts (
                self_test_id, user_id, answers_json, result_json,
                score, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                self_test_id,
                user_id,
                json.dumps(answers, ensure_ascii=False),
                json.dumps(result, ensure_ascii=False),
                score,
                now,
            ),
        )

    return {
        "attempt_id": int(cursor.lastrowid),
        "score": score,
        "questions": graded_questions,
    }
