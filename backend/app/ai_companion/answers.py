from __future__ import annotations

import json
import re

from app.agri_skills.ai_client import get_ai_client
from app.agri_skills.errors import AiUnavailableError
from app.ai_companion.constants import AI_UNAVAILABLE_MESSAGE, REFUSAL_MESSAGE
from app.ai_companion.errors import AiCompanionAiUnavailableError


LEARNING_MODULES = {
    "agriculture": ("农业技能", "/student/agri-skills/qa"),
    "ecommerce": ("电商训练", "/student/ecommerce-training"),
    "handcraft": ("非遗传承", "/student/handcraft-inheritance"),
    "employment": ("就业对接", "/student/employment"),
    "local_resources": ("本土资源", "/student/local-resources"),
}

LEARNING_GUIDANCE_CALL_POINT = "ai_companion_learning_guidance"
MAX_BULLETS = 5
MAX_BULLET_LENGTH = 120

# 纯文本建议表：命中后只作为拒绝答案里的操作提示，绝不作为跳转目标返回。
BUSINESS_PROXY_GUIDANCE = (
    ("投简历|投递", "请使用就业对接中的岗位投递入口。"),
    ("兑换|奖品|积分商城", "请进入积分商城自行兑换。"),
    ("审核", "审核只能由具备权限的管理人员执行。"),
    ("发消息|私信", "请使用消息中心自行发送。"),
    ("修改资料|个人资料", "请进入个人资料页面自行修改。"),
    ("删除内容", "请使用对应内容管理入口或联系管理员。"),
)


def _learning_messages(question: str) -> list[dict]:
    modules = {key: label for key, (label, _) in LEARNING_MODULES.items()}
    return [
        {
            "role": "system",
            "content": (
                "你是粤乡智匠平台学生的学习助手，针对学习问题给出可执行的学习要点，"
                "并选出最相关的学习模块。只返回 JSON："
                "{\"bullets\": [\"...\"], \"module_key\": \"...\"}；"
                "bullets 为 1-5 条简体中文要点，每条不超过 120 字；"
                "module_key 只能取给定模块的 key。"
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "question": str(question or "").strip(),
                    "modules": modules,
                },
                ensure_ascii=False,
            ),
        },
    ]


def _validate_guidance(payload) -> tuple[list[str], str]:
    if not isinstance(payload, dict):
        raise ValueError("AI response payload must be a JSON object")
    bullets = payload.get("bullets")
    module_key = payload.get("module_key")
    if not isinstance(bullets, list) or not 1 <= len(bullets) <= MAX_BULLETS:
        raise ValueError("bullets must be a list of 1-5 items")
    for bullet in bullets:
        if not isinstance(bullet, str) or not bullet.strip():
            raise ValueError("each bullet must be a non-empty string")
        if len(bullet) > MAX_BULLET_LENGTH:
            raise ValueError("bullet exceeds the maximum length")
    if module_key not in LEARNING_MODULES:
        raise ValueError("module_key must be a known learning module")
    return bullets, module_key


def generate_learning_guidance(question: str, role: str) -> dict:
    """生成有界的学习要点引导；AI 失败或输出畸形一律归为 AI 不可用。"""
    try:
        payload = get_ai_client().complete_json(
            _learning_messages(question),
            call_point=LEARNING_GUIDANCE_CALL_POINT,
        )
        bullets, module_key = _validate_guidance(payload)
    except (AiUnavailableError, TypeError, ValueError) as error:
        raise AiCompanionAiUnavailableError(AI_UNAVAILABLE_MESSAGE) from error
    target = LEARNING_MODULES[module_key][1]
    return {
        "answer": "\n".join(f"- {bullet}" for bullet in bullets),
        "bullets": bullets,
        "module_key": module_key,
        "jump_target": target if role == "student" else None,
    }


def build_refusal_answer(question: str, rule_prefiltered: bool) -> dict:
    """固定拒绝语加一条操作提示；绝不返回跳转目标，也不使用已完成措辞。"""
    text = str(question or "")
    suggestion = next(
        (
            guidance
            for pattern, guidance in BUSINESS_PROXY_GUIDANCE
            if re.search(pattern, text)
        ),
        None,
    )
    if suggestion is None:
        suggestion = (
            "请使用对应功能入口或联系管理员。"
            if rule_prefiltered
            else "该问题超出 AI 学伴范围，请联系管理员或使用对应功能。"
        )
    return {
        "answer": f"{REFUSAL_MESSAGE}\n{suggestion}",
        "jump_target": None,
    }
