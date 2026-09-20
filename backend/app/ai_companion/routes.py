from __future__ import annotations

from flask import Blueprint, Flask, jsonify, request

from app.ai_companion.constants import AI_COMPANION_ROLES, ASR_FAILURE_MESSAGE
from app.ai_companion.errors import (
    AiCompanionAiUnavailableError,
    AiCompanionForbiddenError,
    AiCompanionKnowledgeUnavailableError,
    AiCompanionNotFoundError,
    AiCompanionRecognitionError,
    AiCompanionValidationError,
)
from app.ai_companion.knowledge_provider import (
    UnavailableAssistantFeatureKnowledgeProvider,
    set_assistant_feature_knowledge_provider,
)
from app.ai_companion.repository import get_conversation, list_conversations
from app.ai_companion.service import answer_question
from app.ai_companion.speech import transcribe_question
from app.session_manager import load_session


ROLE_FORBIDDEN_MESSAGE = "当前角色不可使用 AI 学伴"
CONVERSATION_NOT_FOUND_MESSAGE = "会话不存在"


ai_companion_bp = Blueprint(
    "ai_companion",
    __name__,
    url_prefix="/api/ai-companion",
)


def install_default_ai_companion_services(app: Flask) -> None:
    if "assistant_feature_knowledge_provider" not in app.extensions:
        set_assistant_feature_knowledge_provider(
            app,
            UnavailableAssistantFeatureKnowledgeProvider(),
        )


def _companion_session() -> dict:
    session = load_session(required=True, allowed_states={"active"})
    if session["role"] not in AI_COMPANION_ROLES:
        raise AiCompanionForbiddenError(ROLE_FORBIDDEN_MESSAGE)
    return session


def _handle_validation(error: AiCompanionValidationError):
    return jsonify(success=False, message=error.message), 400


def _handle_forbidden(_error: AiCompanionForbiddenError):
    return jsonify(success=False, message=ROLE_FORBIDDEN_MESSAGE), 403


def _handle_not_found(_error: AiCompanionNotFoundError):
    return jsonify(success=False, message=CONVERSATION_NOT_FOUND_MESSAGE), 404


def _handle_recognition(_error: AiCompanionRecognitionError):
    return jsonify(success=False, message=ASR_FAILURE_MESSAGE), 422


def _handle_knowledge_unavailable(
    _error: AiCompanionKnowledgeUnavailableError,
):
    return jsonify(success=False, message="暂无法回答，请稍后再试"), 422


def _handle_ai_unavailable(_error: AiCompanionAiUnavailableError):
    return jsonify(success=False, message="AI 服务暂时不可用"), 503


def register_ai_companion_error_handlers(app: Flask) -> None:
    app.register_error_handler(AiCompanionValidationError, _handle_validation)
    app.register_error_handler(AiCompanionForbiddenError, _handle_forbidden)
    app.register_error_handler(AiCompanionNotFoundError, _handle_not_found)
    app.register_error_handler(
        AiCompanionRecognitionError,
        _handle_recognition,
    )
    app.register_error_handler(
        AiCompanionKnowledgeUnavailableError,
        _handle_knowledge_unavailable,
    )
    app.register_error_handler(
        AiCompanionAiUnavailableError,
        _handle_ai_unavailable,
    )


@ai_companion_bp.post("/messages")
def create_message():
    session = _companion_session()
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        payload = {}
    result = answer_question(
        user_id=int(session["id"]),
        role=session["role"],
        question=payload.get("question"),
        client_request_id=payload.get("client_request_id"),
        conversation_id=payload.get("conversation_id"),
    )
    return jsonify(
        success=True,
        conversation_id=result["conversation_id"],
        user_message=result["user_message"],
        assistant_message=result["assistant_message"],
        bullets=result.get("bullets", []),
        module_key=result.get("module_key"),
        jump_target=result.get("jump_target"),
    )


@ai_companion_bp.get("/conversations")
def list_conversations_route():
    session = _companion_session()
    return jsonify(
        success=True,
        conversations=list_conversations(int(session["id"])),
    )


@ai_companion_bp.get("/conversations/<conversation_id>")
def get_conversation_route(conversation_id: str):
    session = _companion_session()
    conversation = get_conversation(int(session["id"]), conversation_id)
    if conversation is None:
        raise AiCompanionNotFoundError(CONVERSATION_NOT_FOUND_MESSAGE)
    return jsonify(success=True, conversation=conversation)


@ai_companion_bp.post("/speech/transcriptions")
def transcribe_speech():
    _companion_session()
    audio_file = request.files.get("audio")
    if audio_file is None:
        raise AiCompanionRecognitionError(ASR_FAILURE_MESSAGE)
    audio = audio_file.read()
    if not audio:
        raise AiCompanionRecognitionError(ASR_FAILURE_MESSAGE)
    text = transcribe_question(audio, audio_file.filename or "")
    return jsonify(success=True, text=text)
