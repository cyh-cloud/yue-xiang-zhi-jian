from __future__ import annotations

import json
import re
from datetime import datetime

from app.agri_skills.ai_client import get_ai_client
from app.agri_skills.errors import AiUnavailableError
from app.ai_companion.constants import (
    AI_UNAVAILABLE_MESSAGE,
    KNOWLEDGE_UNAVAILABLE_MESSAGE,
)
from app.ai_companion.errors import (
    AiCompanionAiUnavailableError,
    AiCompanionKnowledgeUnavailableError,
)
from app.ai_companion.knowledge_provider import (
    get_assistant_feature_knowledge_provider,
)


ANSWER_CALL_POINT = "ai_companion_feature_answer"
# 只允许这些字段进入 AI 提示词，其余来源字段一律不下发。
KNOWLEDGE_FIELDS = (
    "knowledge_id",
    "title",
    "body",
    "feature_key",
    "jump_target",
    "version",
    "updated_at",
)
MAX_CANDIDATES = 5
_TEXT_FIELDS = ("knowledge_id", "title", "body", "feature_key")
_LATIN_TOKEN_PATTERN = re.compile(r"[0-9a-z]+")
_CJK_RUN_PATTERN = re.compile(r"[\u4e00-\u9fff]+")


def _valid_text(value) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _normalize_enabled(value) -> bool | None:
    """只接受 bool 或 SQLite 的 0/1，其余形状视为非法。"""
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    return None


def _normalize_jump_target(value) -> str | None:
    """外部地址或非法值归一为 None，但不因此作废整条知识。"""
    if not isinstance(value, str):
        return None
    target = value.strip()
    if not target.startswith("/") or target.startswith("//"):
        return None
    return target


def _has_timezone(value: str) -> bool:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() is not None


def validate_knowledge_entry(entry) -> dict | None:
    """校验单条知识条目，非法结构返回 None，外部 jump_target 归一为 None。"""
    if not isinstance(entry, dict):
        return None
    texts = {name: _valid_text(entry.get(name)) for name in _TEXT_FIELDS}
    if any(text is None for text in texts.values()):
        return None
    version = entry.get("version")
    if isinstance(version, bool) or not isinstance(version, int) or version <= 0:
        return None
    updated_at = _valid_text(entry.get("updated_at"))
    if updated_at is None or not _has_timezone(updated_at):
        return None
    is_enabled = _normalize_enabled(entry.get("is_enabled"))
    if is_enabled is None:
        return None
    return {
        **texts,
        "jump_target": _normalize_jump_target(entry.get("jump_target")),
        "is_enabled": is_enabled,
        "version": version,
        "updated_at": updated_at,
    }


def load_enabled_entries() -> list[dict]:
    """读取知识来源；来源不可用、空、或任一结构非法都返回空来源。"""
    try:
        entries = get_assistant_feature_knowledge_provider().list_entries(
            enabled_only=True
        )
    except Exception as error:
        # 含 011 占位 provider 抛出的 ProviderUnavailableError；来源问题一律
        # 归为知识不可用，不能与 AI 失败混为一类。
        raise AiCompanionKnowledgeUnavailableError(
            KNOWLEDGE_UNAVAILABLE_MESSAGE
        ) from error
    if not isinstance(entries, list):
        return []
    validated: list[dict] = []
    for entry in entries:
        normalized = validate_knowledge_entry(entry)
        if normalized is None:
            return []
        validated.append(normalized)
    # provider 可能不理会 enabled_only，这里再按归一后的开关过滤一次。
    return [entry for entry in validated if entry["is_enabled"]]


def _tokenize(text) -> set[str]:
    """小写字母数字整词 + CJK 二元组。"""
    normalized = str(text or "").lower()
    tokens = set(_LATIN_TOKEN_PATTERN.findall(normalized))
    for run in _CJK_RUN_PATTERN.findall(normalized):
        tokens.update(
            run[index : index + 2] for index in range(len(run) - 1)
        )
    return tokens


def rank_knowledge_entries(question: str, entries: list[dict]) -> list[dict]:
    """按 token 重叠度排序，最多返回 5 条正分候选。"""
    question_tokens = _tokenize(question)
    if not question_tokens:
        return []
    scored: list[tuple[int, str, dict]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        entry_tokens = (
            _tokenize(entry.get("title"))
            | _tokenize(entry.get("body"))
            | _tokenize(entry.get("feature_key"))
        )
        score = len(question_tokens & entry_tokens)
        if score > 0:
            scored.append((-score, str(entry.get("knowledge_id") or ""), entry))
    scored.sort(key=lambda item: (item[0], item[1]))
    return [item[2] for item in scored[:MAX_CANDIDATES]]


def answer_platform_question(question: str) -> dict:
    """基于白名单字段调用 AI 生成平台使用答疑，并附带首个候选的站内跳转。"""
    candidates = rank_knowledge_entries(question, load_enabled_entries())
    if not candidates:
        raise AiCompanionKnowledgeUnavailableError(KNOWLEDGE_UNAVAILABLE_MESSAGE)
    knowledge = [
        {field: candidate.get(field) for field in KNOWLEDGE_FIELDS}
        for candidate in candidates
    ]
    messages = [
        {
            "role": "system",
            "content": (
                "你是粤乡智匠平台的使用答疑助手，只能依据给定的功能说明条目回答"
                "平台使用问题，不要编造条目之外的功能、入口或路径。只返回 JSON："
                "{\"answer\": \"...\"}，answer 用简体中文，不超过 200 字。"
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "question": str(question or "").strip(),
                    "entries": knowledge,
                },
                ensure_ascii=False,
            ),
        },
    ]
    try:
        payload = get_ai_client().complete_json(
            messages,
            call_point=ANSWER_CALL_POINT,
        )
        if not isinstance(payload, dict):
            raise ValueError("AI response payload must be a JSON object")
        answer = payload.get("answer")
        if not isinstance(answer, str) or not answer.strip():
            raise ValueError("AI response answer must be a non-empty string")
    except (AiUnavailableError, TypeError, ValueError) as error:
        raise AiCompanionAiUnavailableError(AI_UNAVAILABLE_MESSAGE) from error
    return {
        "answer": answer.strip(),
        "jump_target": candidates[0].get("jump_target"),
    }
