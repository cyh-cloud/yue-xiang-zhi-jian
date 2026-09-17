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

from app.agri_skills.ai_client import get_ai_client
from app.agri_skills.calendar import (
    get_calendar,
    get_selected_product,
    list_product_subscriptions,
    list_products,
    set_selected_product,
    subscribe_product,
    unsubscribe_product,
)
from app.agri_skills.course_learning import (
    get_course_progress,
    get_course_quiz,
    list_agriculture_courses,
    list_course_quiz_attempts,
    list_recommendations,
    submit_course_quiz,
    update_course_progress,
)
from app.agri_skills.diagnosis import (
    abandon_diagnosis,
    add_followup,
    answer_diagnosis,
    create_diagnosis,
    create_diagnosis_from_followup,
    get_diagnosis,
    list_diagnoses,
    start_diagnosis,
)
from app.agri_skills.errors import (
    AgriNotFoundError,
    AgriSkillError,
    AgriValidationError,
    AiUnavailableError,
    PresetContentUnavailableError,
)
from app.agri_skills.qa import (
    NO_LOCAL_MATCH_MESSAGE,
    answer_qa_once,
    create_qa_conversation,
    get_qa_thread,
    list_qa_conversations,
    persist_qa_turn,
    stream_qa_answer,
)
from app.agri_skills.self_test import generate_self_test, submit_self_test
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


def _json_object_payload() -> dict:
    payload = request.get_json(silent=True)
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise AgriValidationError(
            "请求体格式不正确",
            details={"body": "请求体必须是 JSON 对象"},
        )
    return payload


def _parse_followup_id(payload: dict) -> int:
    raw_followup_id = payload.get("followup_id", 0)
    if (
        isinstance(raw_followup_id, bool)
        or (
            isinstance(raw_followup_id, float)
            and not raw_followup_id.is_integer()
        )
    ):
        followup_id = 0
    else:
        try:
            followup_id = int(raw_followup_id)
        except (TypeError, ValueError):
            followup_id = 0
    if followup_id <= 0:
        raise AgriValidationError(
            "复诊记录无效",
            details={"followup_id": "复诊记录无效"},
        )
    return followup_id


@agri_skills_bp.errorhandler(AgriValidationError)
def handle_validation(error):
    return jsonify(
        success=False,
        message=error.message,
        errors=error.details,
    ), 400


@agri_skills_bp.errorhandler(AgriNotFoundError)
def handle_not_found(error):
    return jsonify(success=False, message=error.message), 404


@agri_skills_bp.errorhandler(AiUnavailableError)
def handle_ai_unavailable(error):
    return jsonify(
        success=False,
        message=(
            NO_LOCAL_MATCH_MESSAGE
            if error.message == NO_LOCAL_MATCH_MESSAGE
            else "AI 服务暂时不可用"
        ),
    ), 503


@agri_skills_bp.get("/products")
def get_products():
    _student_session()
    return jsonify(success=True, products=list_products())


@agri_skills_bp.post("/speech/transcriptions")
def transcribe_speech():
    _student_session()
    audio_file = request.files.get("audio")
    if audio_file is None or not audio_file.filename:
        return jsonify(
            success=False,
            message="未能识别，请重试或改用文字输入",
        ), 422
    audio = audio_file.read()
    if not audio:
        return jsonify(
            success=False,
            message="未能识别，请重试或改用文字输入",
        ), 422
    try:
        text = get_ai_client().transcribe(
            audio,
            audio_file.filename,
            call_point="speech_to_text",
        )
    except AgriValidationError:
        return jsonify(
            success=False,
            message="未能识别，请重试或改用文字输入",
        ), 422
    return jsonify(success=True, text=text)


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


@agri_skills_bp.get("/courses")
def get_agri_courses():
    session = _student_session()
    return jsonify(
        success=True,
        courses=list_agriculture_courses(int(session["id"])),
    )


@agri_skills_bp.get("/recommendations")
def get_agri_recommendations():
    session = _student_session()
    return jsonify(
        success=True,
        courses=list_recommendations(int(session["id"])),
    )


@agri_skills_bp.get("/courses/<int:course_id>/progress")
def get_progress_route(course_id: int):
    session = _student_session()
    return jsonify(
        success=True,
        progress=get_course_progress(int(session["id"]), course_id),
    )


@agri_skills_bp.put("/courses/<int:course_id>/progress")
def put_progress_route(course_id: int):
    session = _student_session()
    payload = _json_object_payload()
    progress = update_course_progress(
        int(session["id"]),
        course_id,
        payload.get("position_seconds"),
        payload.get("watched_delta_seconds", 0),
    )
    return jsonify(success=True, progress=progress)


@agri_skills_bp.get("/courses/<int:course_id>/quiz")
def get_quiz_route(course_id: int):
    session = _student_session()
    quiz = get_course_quiz(int(session["id"]), course_id)
    if quiz is None:
        return jsonify(success=False, message="暂无可用测验"), 404
    return jsonify(success=True, quiz=quiz)


@agri_skills_bp.get("/courses/<int:course_id>/quiz/attempts")
def list_quiz_attempts_route(course_id: int):
    session = _student_session()
    return jsonify(
        success=True,
        attempts=list_course_quiz_attempts(
            int(session["id"]),
            course_id,
            direction="agriculture",
        ),
    )


@agri_skills_bp.post("/courses/<int:course_id>/quiz")
def post_quiz_route(course_id: int):
    session = _student_session()
    payload = _json_object_payload()
    attempt = submit_course_quiz(
        int(session["id"]),
        course_id,
        payload.get("answers")
        if isinstance(payload.get("answers"), dict)
        else {},
    )
    return jsonify(success=True, attempt=attempt), 201


@agri_skills_bp.post("/diagnoses")
def post_diagnosis():
    session = _student_session()
    payload = request.get_json(silent=True) or {}
    diagnosis = create_diagnosis(
        int(session["id"]),
        str(payload.get("product_key", "")).strip(),
        str(payload.get("affected_part", "")).strip(),
        payload.get("symptoms")
        if isinstance(payload.get("symptoms"), list)
        else [],
    )
    return jsonify(success=True, session=diagnosis), 201


@agri_skills_bp.get("/diagnoses")
def get_diagnoses():
    session = _student_session()
    return jsonify(
        success=True,
        diagnoses=list_diagnoses(int(session["id"])),
    )


@agri_skills_bp.get("/diagnoses/<int:session_id>")
def get_diagnosis_route(session_id: int):
    session = _student_session()
    diagnosis = get_diagnosis(int(session["id"]), session_id)
    return jsonify(success=True, session=diagnosis)


@agri_skills_bp.post("/diagnoses/<int:session_id>/start")
def post_diagnosis_start(session_id: int):
    session = _student_session()
    diagnosis = start_diagnosis(int(session["id"]), session_id)
    return jsonify(success=True, session=diagnosis)


@agri_skills_bp.post("/diagnoses/<int:session_id>/answers")
def post_diagnosis_answer(session_id: int):
    session = _student_session()
    payload = request.get_json(silent=True) or {}
    result = answer_diagnosis(
        int(session["id"]),
        session_id,
        str(payload.get("answer", "")),
        str(payload.get("input_mode", "text")),
    )
    return jsonify(success=True, **result)


@agri_skills_bp.post("/diagnoses/<int:session_id>/abandon")
def post_diagnosis_abandon(session_id: int):
    session = _student_session()
    return jsonify(
        success=True,
        session=abandon_diagnosis(int(session["id"]), session_id),
    )


@agri_skills_bp.post("/diagnoses/<int:session_id>/followups")
def post_followup(session_id: int):
    session = _student_session()
    payload = request.get_json(silent=True) or {}
    followup = add_followup(
        int(session["id"]),
        session_id,
        str(payload.get("outcome", "")),
        payload.get("note", ""),
    )
    return jsonify(success=True, followup=followup), 201


@agri_skills_bp.post("/diagnoses/<int:session_id>/repeat")
def post_repeat_diagnosis(session_id: int):
    session = _student_session()
    payload = request.get_json(silent=True) or {}
    diagnosis = create_diagnosis_from_followup(
        int(session["id"]),
        session_id,
        _parse_followup_id(payload),
    )
    return jsonify(success=True, session=diagnosis), 201


@agri_skills_bp.post("/diagnoses/<int:session_id>/self-test")
def post_self_test(session_id: int):
    session = _student_session()
    test = generate_self_test(int(session["id"]), session_id)
    return jsonify(success=True, self_test=test), 201


@agri_skills_bp.post("/self-tests/<int:self_test_id>/submit")
def post_self_test_submit(self_test_id: int):
    session = _student_session()
    payload = request.get_json(silent=True) or {}
    result = submit_self_test(
        int(session["id"]),
        self_test_id,
        payload.get("answers")
        if isinstance(payload.get("answers"), dict)
        else {},
    )
    return jsonify(success=True, result=result)


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
                    yield _sse(
                        "complete",
                        {
                            "turn": thread["turns"][-1],
                            "suggestion_error": event.get(
                                "suggestion_error"
                            ),
                        },
                    )
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
