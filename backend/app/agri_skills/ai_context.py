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
    "live_script_generate": {"product_name", "selling_points", "price_text", "style"},
    "simulation_score": {"scene_label", "segments"},
    "copy_case_generate": {"product_type", "scene"},
    "copy_reference_critique": {"case_text", "defect_categories", "learner_critique"},
    "copy_revised_generate": {"optimized_prompt", "case_text"},
    "copy_optimization_critique": {"original_copy", "revised_copy", "optimized_prompt"},
    "store_plan_generate": {"store_type", "platform", "style_preference"},
    "customer_message_generate": {"scenario", "goal_criteria", "prior_turns", "turn_no"},
    "customer_reply_analyze": {"scenario", "goal_criteria", "customer_message", "student_reply"},
    "customer_summary": {"scenario", "goal_criteria", "turns"},
}

ECOMMERCE_AI_CALL_POINTS = {
    "live_script_generate",
    "simulation_score",
    "copy_case_generate",
    "copy_reference_critique",
    "copy_revised_generate",
    "copy_optimization_critique",
    "store_plan_generate",
    "customer_message_generate",
    "customer_reply_analyze",
    "customer_summary",
}

AI_CALL_DOMAINS = {
    call_point: (
        "电商运营实训任务"
        if call_point in ECOMMERCE_AI_CALL_POINTS
        else "农业技能任务"
    )
    for call_point in AI_FIELD_ALLOWLISTS
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
    "api_key",
    "secret",
    "authorization",
}


def _sanitize_allowed_value(value):
    if isinstance(value, dict):
        return {
            key: _sanitize_allowed_value(item)
            for key, item in value.items()
            if not isinstance(key, str) or key.lower() not in SENSITIVE_KEYS
        }
    if isinstance(value, list):
        return [_sanitize_allowed_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_sanitize_allowed_value(item) for item in value)
    return value


def allowed_context(call_point: str, context: dict) -> dict:
    allowed = AI_FIELD_ALLOWLISTS[call_point]
    return {
        key: _sanitize_allowed_value(value)
        for key, value in context.items()
        if key in allowed
    }


def build_ai_messages(call_point: str, context: dict) -> list[dict]:
    sanitized = allowed_context(call_point, context)
    return [
        {
            "role": "system",
            "content": f"{AI_CALL_DOMAINS[call_point]}：{call_point}",
        },
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
