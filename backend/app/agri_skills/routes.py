from __future__ import annotations

import json

from flask import Blueprint, Response, jsonify, request, stream_with_context

from app.agri_skills.errors import (
    AgriNotFoundError,
    AgriSkillError,
    AgriValidationError,
)
from app.agri_skills.qa import (
    answer_qa_once,
    create_qa_conversation,
    get_qa_thread,
    list_qa_conversations,
    persist_qa_turn,
    stream_qa_answer,
)
from app.session_manager import abort_session_required, load_session


agri_skills_bp = Blueprint(
    "agri_skills",
    __name__,
    url_prefix="/api/agri-skills",
)


def _student_session() -> dict:
    session = load_session(required=True, allowed_states={"active"})
    if session["role"] != "student":
        abort_session_required()
    return session


def _not_found_response(error: AgriNotFoundError):
    return jsonify(success=False, message=error.message), 404


def _validation_response(error: AgriValidationError):
    return jsonify(success=False, errors=error.details), 400


def _sse(event: str, payload: dict) -> str:
    data = json.dumps(payload, ensure_ascii=False)
    return f"event: {event}\ndata: {data}\n\n"


@agri_skills_bp.post("/qa/conversations")
def post_qa_conversation():
    session = _student_session()
    payload = request.get_json(silent=True) or {}
    try:
        conversation = create_qa_conversation(
            int(session["id"]),
            str(payload.get("question", "")),
            str(payload.get("input_mode", "text")),
        )
    except AgriValidationError as error:
        return _validation_response(error)
    return jsonify(success=True, conversation=conversation), 201


@agri_skills_bp.get("/qa/conversations")
def get_qa_conversations():
    session = _student_session()
    return jsonify(
        success=True,
        conversations=list_qa_conversations(int(session["id"])),
    )


@agri_skills_bp.get("/qa/conversations/<int:conversation_id>")
def get_qa_conversation(conversation_id: int):
    session = _student_session()
    try:
        thread = get_qa_thread(int(session["id"]), conversation_id)
    except AgriNotFoundError as error:
        return _not_found_response(error)
    return jsonify(success=True, **thread)


@agri_skills_bp.post(
    "/qa/conversations/<int:conversation_id>/messages/stream"
)
def stream_qa_message(conversation_id: int):
    session = _student_session()
    try:
        get_qa_thread(int(session["id"]), conversation_id)
    except AgriNotFoundError as error:
        return _not_found_response(error)

    payload = request.get_json(silent=True) or {}
    question = str(payload.get("question", "")).strip()
    input_mode = str(payload.get("input_mode", "text"))
    if not question:
        return jsonify(
            success=False,
            errors={"question": "问题不能为空"},
        ), 400

    def generate():
        chunks: list[str] = []
        try:
            for event in stream_qa_answer(conversation_id, question):
                if event["type"] == "chunk":
                    chunks.append(event["content"])
                    yield _sse("chunk", event)
                elif event["type"] == "complete":
                    thread = persist_qa_turn(
                        user_id=int(session["id"]),
                        conversation_id=conversation_id,
                        question=question,
                        answer="".join(chunks),
                        input_mode=input_mode,
                        answer_mode="ai",
                        suggestions=event["suggestions"],
                    )
                    yield _sse("complete", {"turn": thread["turns"][-1]})
                elif event["type"] == "replace":
                    thread = persist_qa_turn(
                        user_id=int(session["id"]),
                        conversation_id=conversation_id,
                        question=question,
                        answer=event["answer"],
                        input_mode=input_mode,
                        answer_mode="local_kb",
                        suggestions=[],
                    )
                    yield _sse("replace", {"turn": thread["turns"][-1]})
        except AgriSkillError as error:
            yield _sse("error", {"message": error.message})

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@agri_skills_bp.post("/qa/conversations/<int:conversation_id>/messages")
def post_qa_message(conversation_id: int):
    session = _student_session()
    payload = request.get_json(silent=True) or {}
    question = str(payload.get("question", "")).strip()
    input_mode = str(payload.get("input_mode", "text"))
    if not question:
        return jsonify(
            success=False,
            errors={"question": "问题不能为空"},
        ), 400

    try:
        thread = answer_qa_once(
            int(session["id"]),
            conversation_id,
            question,
            input_mode,
        )
    except AgriNotFoundError as error:
        return _not_found_response(error)
    except AgriValidationError as error:
        return _validation_response(error)
    return jsonify(success=True, turn=thread["turns"][-1]), 201
