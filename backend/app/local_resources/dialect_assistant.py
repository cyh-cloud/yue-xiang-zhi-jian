from __future__ import annotations

from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.agri_skills.ai_client import get_ai_client
from app.agri_skills.errors import AiUnavailableError
from app.db import get_db
from app.local_resources.constants import DIALECTS
from app.local_resources.errors import (
    LocalResourceAiUnavailableError,
    LocalResourceValidationError,
)
from app.local_resources.tts import synthesize_dialect


PLATFORM_TIMEZONE = ZoneInfo("Asia/Shanghai")


def _now() -> str:
    return datetime.now(PLATFORM_TIMEZONE).isoformat(timespec="seconds")


def _build_messages(dialect_code: str, question: str) -> list[dict]:
    label = DIALECTS[dialect_code]
    return [
        {
            "role": "system",
            "content": (
                "你是广东本土资源方言助手。只根据用户问题生成简洁、"
                "可执行的回答。返回 JSON 对象，字段必须是 dialect_text "
                "和 mandarin_text。dialect_text 使用指定方言口语，"
                "mandarin_text 是准确普通话对照；两个字段都不得为空。"
            ),
        },
        {
            "role": "user",
            "content": (
                f"方言：{label}（{dialect_code}）\n"
                f"问题：{question}"
            ),
        },
    ]


def generate_dialect_answer(
    dialect_code: str,
    question: str,
) -> dict[str, str]:
    if dialect_code not in DIALECTS:
        raise LocalResourceValidationError(
            "方言代码不正确",
            details={"dialect_code": "不支持"},
        )
    normalized = str(question or "").strip()
    if not normalized:
        raise LocalResourceValidationError(
            "问题不能为空",
            details={"question": "不能为空"},
        )
    try:
        payload = get_ai_client().complete_json(
            _build_messages(dialect_code, normalized),
            call_point="local_resources_dialect_answer",
        )
    except (AiUnavailableError, TypeError, ValueError) as error:
        raise LocalResourceAiUnavailableError() from error
    if not isinstance(payload, dict):
        raise LocalResourceAiUnavailableError()
    dialect_text = payload.get("dialect_text")
    mandarin_text = payload.get("mandarin_text")
    if (
        not isinstance(dialect_text, str)
        or not dialect_text.strip()
        or not isinstance(mandarin_text, str)
        or not mandarin_text.strip()
    ):
        raise LocalResourceAiUnavailableError()
    return {
        "dialect_text": dialect_text.strip(),
        "mandarin_text": mandarin_text.strip(),
    }


def complete_dialect_turn(
    user_id: int,
    dialect_code: str,
    recognized_text: str,
) -> dict:
    answer = generate_dialect_answer(dialect_code, recognized_text)
    audio = synthesize_dialect(dialect_code, answer["dialect_text"])
    turn_id = f"dialect-{uuid4().hex}"
    created_at = _now()
    with get_db():
        get_db().execute(
            """
            INSERT INTO local_resource_dialect_turns (
                turn_id, user_id, dialect_code, recognized_text,
                dialect_answer, mandarin_answer, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'completed', ?)
            """,
            (
                turn_id,
                user_id,
                dialect_code,
                str(recognized_text).strip(),
                answer["dialect_text"],
                answer["mandarin_text"],
                created_at,
            ),
        )
    return {
        "id": turn_id,
        "dialect_code": dialect_code,
        "dialect_label": DIALECTS[dialect_code],
        "recognized_text": str(recognized_text).strip(),
        "dialect_answer": answer["dialect_text"],
        "mandarin_answer": answer["mandarin_text"],
        "status": "completed",
        "created_at": created_at,
        "audio_content": audio.content,
        "audio_content_type": audio.content_type,
    }
