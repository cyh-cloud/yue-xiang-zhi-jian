from __future__ import annotations

import json
from datetime import datetime
from zoneinfo import ZoneInfo

from flask import (
    Blueprint,
    Response,
    current_app,
    jsonify,
    request,
    stream_with_context,
)

from app.agri_skills.calendar import (
    get_calendar,
    get_selected_product,
    list_product_subscriptions,
    list_products,
    set_selected_product,
    subscribe_product,
    unsubscribe_product,
)
from app.agri_skills.errors import (
    AgriNotFoundError,
    AgriSkillError,
    AgriValidationError,
    PresetContentUnavailableError,
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


def _current_calendar_month() -> int:
    timezone_name = str(current_app.config["APP_TIMEZONE"])
    return datetime.now(ZoneInfo(timezone_name)).month


@agri_skills_bp.get("/products")
def get_products():
    _student_session()
    return jsonify(success=True, products=list_products())


@agri_skills_bp.get("/calendar")
def get_calendar_route():
    session = _student_session()
    product_key = request.args.get("product_key", "").strip()
    if not product_key:
        product_key = get_selected_product(int(session["id"]))
    raw_month = request.args.get("month")
    if raw_month is None:
        month = _current_calendar_month()
    else:
        try:
            month = int(raw_month)
        except ValueError:
            return jsonify(
                success=False,
                errors={"month": "月份必须是 1 至 12 的整数"},
            ), 400
    if not 1 <= month <= 12:
        return jsonify(
            success=False,
            errors={"month": "月份必须是 1 至 12 的整数"},
        ), 400
    try:
        calendar = get_calendar(product_key, month)
    except PresetContentUnavailableError as error:
        calendar = {
            "product_key": product_key,
            "month": month,
            "empty_state": str(error),
        }
    return jsonify(success=True, calendar=calendar)


@agri_skills_bp.put("/calendar/selection")
def put_calendar_selection():
    session = _student_session()
    payload = request.get_json(silent=True) or {}
    try:
        product_key = set_selected_product(
            int(session["id"]),
            str(payload.get("product_key", "")).strip(),
        )
    except AgriValidationError as error:
        return _validation_response(error)
    return jsonify(success=True, product_key=product_key)


@agri_skills_bp.get("/subscriptions")
def get_subscriptions():
    session = _student_session()
    return jsonify(
        success=True,
        subscriptions=list_product_subscriptions(int(session["id"])),
    )


@agri_skills_bp.post("/subscriptions/<product_key>")
def post_subscription(product_key: str):
    session = _student_session()
    try:
        subscription = subscribe_product(int(session["id"]), product_key)
    except AgriValidationError as error:
        return _validation_response(error)
    return jsonify(success=True, subscription=subscription)


@agri_skills_bp.delete("/subscriptions/<product_key>")
def delete_subscription(product_key: str):
    session = _student_session()
    return jsonify(
        success=True,
        subscription=unsubscribe_product(int(session["id"]), product_key),
    )


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
