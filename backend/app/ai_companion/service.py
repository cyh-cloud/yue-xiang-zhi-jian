from __future__ import annotations

from app.ai_companion.answers import (
    build_refusal_answer,
    generate_learning_guidance,
)
from app.ai_companion.constants import AI_COMPANION_ROLES, MAX_QUESTION_LENGTH
from app.ai_companion.errors import (
    AiCompanionForbiddenError,
    AiCompanionValidationError,
)
from app.ai_companion.intent import resolve_intent
from app.ai_companion.knowledge import answer_platform_question
from app.ai_companion.repository import (
    create_or_append_exchange,
    find_exchange_by_request,
)


ROLE_FORBIDDEN_MESSAGE = "当前角色不可使用 AI 学伴"
QUESTION_EMPTY_MESSAGE = "问题不能为空"
QUESTION_TOO_LONG_MESSAGE = "问题过长，请缩短后重试"
REQUEST_ID_REQUIRED_MESSAGE = "请求标识不能为空"


def answer_question(
    user_id: int,
    role: str,
    question: str,
    client_request_id: str,
) -> dict:
    if role not in AI_COMPANION_ROLES:
        raise AiCompanionForbiddenError(ROLE_FORBIDDEN_MESSAGE)
    if not isinstance(question, str) or not question.strip():
        raise AiCompanionValidationError(QUESTION_EMPTY_MESSAGE)
    if len(question.strip()) > MAX_QUESTION_LENGTH:
        raise AiCompanionValidationError(QUESTION_TOO_LONG_MESSAGE)
    if not isinstance(client_request_id, str) or not client_request_id.strip():
        raise AiCompanionValidationError(REQUEST_ID_REQUIRED_MESSAGE)

    # 幂等重放：相同请求标识直接返回既有交换，避免重复推理与重复落库。
    replayed = find_exchange_by_request(user_id, client_request_id)
    if replayed is not None:
        return replayed

    intent, prefiltered = resolve_intent(question)
    if intent == "platform_usage":
        payload = answer_platform_question(question)
    elif intent == "learning_question":
        payload = generate_learning_guidance(question, role)
    else:
        payload = build_refusal_answer(question, prefiltered)

    jump_target = payload.get("jump_target")
    persisted = create_or_append_exchange(
        user_id=user_id,
        question=question,
        answer=payload["answer"],
        intent=intent,
        jump_target=jump_target,
        client_request_id=client_request_id,
    )

    result = {
        "answer": payload["answer"],
        "jump_target": jump_target,
        "conversation_id": persisted["conversation_id"],
        "user_message": persisted["user_message"],
        "assistant_message": persisted["assistant_message"],
    }
    if "bullets" in payload:
        result["bullets"] = payload["bullets"]
    if "module_key" in payload:
        result["module_key"] = payload["module_key"]
    return result
