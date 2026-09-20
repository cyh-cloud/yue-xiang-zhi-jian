from __future__ import annotations

from app.agri_skills.ai_client import get_ai_client
from app.agri_skills.errors import AgriValidationError, AiUnavailableError
from app.ai_companion.constants import AI_UNAVAILABLE_MESSAGE, ASR_FAILURE_MESSAGE
from app.ai_companion.errors import (
    AiCompanionAiUnavailableError,
    AiCompanionRecognitionError,
)


SPEECH_TO_TEXT_CALL_POINT = "speech_to_text"


def transcribe_question(audio: bytes, filename: str) -> str:
    # 复用 003 的共享 ASR 客户端：不另建客户端、不读取 AI_ASR_*、不传方言。
    try:
        return get_ai_client().transcribe(
            audio,
            filename,
            call_point=SPEECH_TO_TEXT_CALL_POINT,
        )
    except AgriValidationError as error:
        raise AiCompanionRecognitionError(ASR_FAILURE_MESSAGE) from error
    except AiUnavailableError as error:
        raise AiCompanionAiUnavailableError(AI_UNAVAILABLE_MESSAGE) from error
