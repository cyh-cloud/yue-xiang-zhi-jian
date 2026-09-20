from __future__ import annotations

import re

from app.agri_skills.ai_client import get_ai_client
from app.agri_skills.errors import AiUnavailableError
from app.ai_companion.constants import AI_UNAVAILABLE_MESSAGE, INTENTS
from app.ai_companion.errors import AiCompanionAiUnavailableError


AGENCY_PHRASES = ("帮我", "替我", "代我", "帮忙")
BUSINESS_ACTIONS = (
    "投简历",
    "投递",
    "兑换",
    "审核",
    "发消息",
    "修改资料",
    "删除内容",
    "报名",
    "支付",
)
_WHITESPACE_PATTERN = re.compile(r"\s+")


def _normalize_question(question: str) -> str:
    return _WHITESPACE_PATTERN.sub("", str(question or ""))


def _contains_action(text: str, action: str) -> bool:
    """动作短语按序匹配，允许被口语词打断。

    例如"修改资料"命中"替我修改个人资料"，"删除内容"命中"帮我删除这条内容"。
    """
    cursor = 0
    for character in action:
        cursor = text.find(character, cursor)
        if cursor < 0:
            return False
        cursor += 1
    return True


def detect_business_proxy(question: str) -> bool:
    """命中"机构/代办短语 + 业务动作"时判定为业务代办请求。"""
    normalized = _normalize_question(question)
    has_agency_phrase = any(
        phrase in normalized for phrase in AGENCY_PHRASES
    )
    has_business_action = any(
        _contains_action(normalized, action) for action in BUSINESS_ACTIONS
    )
    return has_agency_phrase and has_business_action


def classify_intent(question: str) -> str:
    """调用 AI 把问题分类为平台使用、学习提问或超范围三类之一。"""
    messages = [
        {
            "role": "system",
            "content": (
                "把用户问题分类为 platform_usage、learning_question 或 "
                "out_of_scope。只返回 JSON：{\"intent\": \"...\"}。"
            ),
        },
        {"role": "user", "content": str(question or "").strip()},
    ]
    try:
        payload = get_ai_client().complete_json(
            messages,
            call_point="ai_companion_intent",
        )
        if not isinstance(payload, dict):
            raise ValueError("AI response payload must be a JSON object")
        intent = payload.get("intent")
        if intent not in INTENTS:
            raise ValueError("AI response intent is not supported")
    except (AiUnavailableError, TypeError, ValueError) as error:
        raise AiCompanionAiUnavailableError(AI_UNAVAILABLE_MESSAGE) from error
    return intent


def resolve_intent(question: str) -> tuple[str, bool]:
    """业务代办请求直接拒绝，其余交给 AI 分类。"""
    if detect_business_proxy(question):
        return "out_of_scope", True
    return classify_intent(question), False
