from __future__ import annotations

import json


AI_FIELD_ALLOWLISTS = {
    "speech_to_text": {"audio", "filename"},
    "qa_answer": {"question", "conversation_summary"},
    "qa_followups": {"question", "answer"},
    "diagnosis_turn": {
        "product_name",
        "affected_part",
        "symptoms",
        "round_no",
        "prior_questions",
        "prior_answers",
        "source_conclusion",
        "followup_status",
        "followup_note",
    },
    "selftest_generate": {"diagnosis_text"},
    "selftest_grade": {"questions", "answers"},
    "course_quiz_grade": {"course_summary", "questions", "answers"},
}

SENSITIVE_KEYS = {
    "username",
    "user_id",
    "student_id",
    "contact",
    "phone",
    "password",
    "token",
    "session",
    "credential",
}


def allowed_context(call_point: str, context: dict) -> dict:
    allowed = AI_FIELD_ALLOWLISTS[call_point]
    return {key: value for key, value in context.items() if key in allowed}


def build_ai_messages(call_point: str, context: dict) -> list[dict]:
    sanitized = allowed_context(call_point, context)
    return [
        {"role": "system", "content": f"农业技能任务：{call_point}"},
        {
            "role": "user",
            "content": json.dumps(sanitized, ensure_ascii=False),
        },
    ]


def redact_ai_log(value):
    if isinstance(value, dict):
        return {
            key: (
                "[REDACTED]"
                if key.lower() in SENSITIVE_KEYS
                else redact_ai_log(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_ai_log(item) for item in value]
    return value
