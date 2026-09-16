from __future__ import annotations

import json
import re

from app.agri_skills.ai_client import get_ai_client
from app.agri_skills.ai_context import build_ai_messages
from app.agri_skills.errors import (
    AgriNotFoundError,
    AgriValidationError,
    AiUnavailableError,
)
from app.agri_skills.presets import get_preset_provider
from app.db import get_db
from app.session_manager import utc_now_iso


INPUT_MODES = {"text", "voice"}
ANSWER_MODES = {"ai", "local_kb"}
NO_LOCAL_MATCH_MESSAGE = "暂无法回答，建议稍后再试"


def _normalize_question(question: str) -> str:
    return re.sub(r"\s+", "", question.strip().lower())


def select_local_knowledge_entry(question: str) -> dict:
    normalized = _normalize_question(question)
    candidates = []
    for entry in get_preset_provider().list_pest_entries():
        fields = [
            entry["pest_name"],
            *entry["product_names"],
            *entry["symptoms"],
            *entry["aliases"],
        ]
        matches = [
            field
            for field in fields
            if _normalize_question(str(field)) in normalized
        ]
        if matches:
            candidates.append(
                {
                    "entry": entry,
                    "match_count": len(matches),
                    "matched_length": max(
                        len(_normalize_question(str(item)))
                        for item in matches
                    ),
                    "sort_order": int(entry["sort_order"]),
                }
            )
    if not candidates:
        raise AiUnavailableError(NO_LOCAL_MATCH_MESSAGE)
    candidates.sort(
        key=lambda item: (
            -item["match_count"],
            -item["matched_length"],
            item["sort_order"],
            str(item["entry"]["id"]),
        )
    )
    return candidates[0]["entry"]


def format_local_answer(entry: dict) -> str:
    return f"离线知识库回答\n{entry['pest_name']}：{entry['answer']}"


def stream_qa_answer(conversation_id: int, question: str):
    del conversation_id
    try:
        chunks: list[str] = []
        messages = build_ai_messages("qa_answer", {"question": question})
        for chunk in get_ai_client().stream_chat(
            messages,
            call_point="qa_answer",
        ):
            if chunk:
                text = str(chunk)
                chunks.append(text)
                yield {"type": "chunk", "content": text}

        answer = "".join(chunks)
        if not answer.strip():
            raise AiUnavailableError("AI service returned an empty answer")

        try:
            followups = get_ai_client().complete_json(
                build_ai_messages(
                    "qa_followups",
                    {"question": question, "answer": answer},
                ),
                call_point="qa_followups",
            )
            if not isinstance(followups, dict):
                raise AiUnavailableError("Invalid follow-up response")
            raw_suggestions = followups.get("suggestions", [])
            if not isinstance(raw_suggestions, list):
                raise AiUnavailableError("Invalid follow-up response")
            suggestions = [
                str(item).strip()
                for item in raw_suggestions
                if str(item).strip()
            ]
        except (AiUnavailableError, TypeError, ValueError):
            suggestions = []

        suggestion_error = (
            None if len(suggestions) == 3 else "AI 服务暂时不可用"
        )
        if suggestion_error:
            suggestions = []
        yield {
            "type": "complete",
            "answer": answer,
            "answer_mode": "ai",
            "suggestions": suggestions,
            "suggestion_error": suggestion_error,
        }
    except AiUnavailableError:
        entry = select_local_knowledge_entry(question)
        yield {
            "type": "replace",
            "answer": format_local_answer(entry),
            "answer_mode": "local_kb",
            "suggestions": [],
        }


def create_qa_conversation(
    user_id: int,
    question: str,
    input_mode: str,
) -> dict:
    title = str(question).strip()
    if not title:
        raise AgriValidationError(
            "问题不能为空",
            details={"question": "问题不能为空"},
        )
    if input_mode not in INPUT_MODES:
        raise AgriValidationError(
            "输入方式无效",
            details={"input_mode": "输入方式无效"},
        )

    now = utc_now_iso()
    with get_db():
        cursor = get_db().execute(
            """
            INSERT INTO agri_qa_conversations (
                user_id, title, created_at, updated_at
            ) VALUES (?, ?, ?, ?)
            """,
            (user_id, title, now, now),
        )
        conversation_id = int(cursor.lastrowid)

    return {
        "id": conversation_id,
        "title": title,
        "created_at": now,
        "updated_at": now,
    }


def _deserialize_suggestions(value: str) -> list[str]:
    try:
        suggestions = json.loads(value)
    except (TypeError, ValueError):
        return []
    if not isinstance(suggestions, list):
        return []
    return [str(item) for item in suggestions]


def get_qa_thread(user_id: int, conversation_id: int) -> dict:
    conversation = get_db().execute(
        """
        SELECT id, title, created_at, updated_at
        FROM agri_qa_conversations
        WHERE id = ? AND user_id = ?
        """,
        (conversation_id, user_id),
    ).fetchone()
    if conversation is None:
        raise AgriNotFoundError("问答记录不存在")

    turns = get_db().execute(
        """
        SELECT
            id, question, answer, input_mode, answer_mode,
            suggestions_json, created_at
        FROM agri_qa_turns
        WHERE conversation_id = ?
        ORDER BY created_at, id
        """,
        (conversation_id,),
    ).fetchall()
    return {
        "conversation": dict(conversation),
        "turns": [
            {
                "id": int(turn["id"]),
                "question": str(turn["question"]),
                "answer": str(turn["answer"]),
                "input_mode": str(turn["input_mode"]),
                "answer_mode": str(turn["answer_mode"]),
                "suggestions": _deserialize_suggestions(
                    str(turn["suggestions_json"])
                ),
                "created_at": str(turn["created_at"]),
            }
            for turn in turns
        ],
    }


def list_qa_conversations(user_id: int) -> list[dict]:
    rows = get_db().execute(
        """
        SELECT id, title, created_at, updated_at
        FROM agri_qa_conversations
        WHERE user_id = ?
        ORDER BY updated_at DESC, id DESC
        """,
        (user_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def persist_qa_turn(
    *,
    user_id: int,
    conversation_id: int,
    question: str,
    answer: str,
    input_mode: str,
    answer_mode: str,
    suggestions: list[str],
) -> dict:
    get_qa_thread(user_id, conversation_id)
    if input_mode not in INPUT_MODES:
        raise AgriValidationError(
            "输入方式无效",
            details={"input_mode": "输入方式无效"},
        )
    if answer_mode not in ANSWER_MODES:
        raise AgriValidationError(
            "回答方式无效",
            details={"answer_mode": "回答方式无效"},
        )

    now = utc_now_iso()
    normalized_suggestions = [str(item) for item in suggestions]
    with get_db():
        get_db().execute(
            """
            INSERT INTO agri_qa_turns (
                conversation_id, question, answer, input_mode,
                answer_mode, suggestions_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                conversation_id,
                str(question).strip(),
                str(answer),
                input_mode,
                answer_mode,
                json.dumps(normalized_suggestions, ensure_ascii=False),
                now,
            ),
        )
        get_db().execute(
            """
            UPDATE agri_qa_conversations
            SET updated_at = ?
            WHERE id = ? AND user_id = ?
            """,
            (now, conversation_id, user_id),
        )
    return get_qa_thread(user_id, conversation_id)


def answer_qa_once(
    user_id: int,
    conversation_id: int,
    question: str,
    input_mode: str,
) -> dict:
    get_qa_thread(user_id, conversation_id)
    chunks: list[str] = []
    for event in stream_qa_answer(conversation_id, question):
        if event["type"] == "chunk":
            chunks.append(event["content"])
        elif event["type"] == "complete":
            return persist_qa_turn(
                user_id=user_id,
                conversation_id=conversation_id,
                question=question,
                answer="".join(chunks),
                input_mode=input_mode,
                answer_mode="ai",
                suggestions=event["suggestions"],
            )
        elif event["type"] == "replace":
            return persist_qa_turn(
                user_id=user_id,
                conversation_id=conversation_id,
                question=question,
                answer=event["answer"],
                input_mode=input_mode,
                answer_mode="local_kb",
                suggestions=[],
            )
    raise AiUnavailableError("AI 服务暂时不可用")
