from __future__ import annotations

from flask import Blueprint, Flask, jsonify, request

from app.agri_skills.errors import (
    AgriAccessError,
    AgriNotFoundError,
    AgriValidationError,
    AiUnavailableError,
)
from app.ecommerce_training.copy_training import (
    create_copy_training as _create_copy_training,
    generate_optimization_critique as _generate_optimization_critique,
    generate_revised_copy as _generate_revised_copy,
    get_copy_training as _get_copy_training,
    list_copy_trainings as _list_copy_trainings,
    submit_copy_critique as _submit_copy_critique,
)
from app.ecommerce_training.course_learning import (
    get_ecommerce_course_progress as _get_ecommerce_course_progress,
    get_ecommerce_course_quiz as _get_ecommerce_course_quiz,
    list_ecommerce_courses as _list_ecommerce_courses,
    list_ecommerce_course_quiz_attempts as _list_ecommerce_quiz_attempts,
    list_ecommerce_recommendations as _list_ecommerce_recommendations,
    submit_ecommerce_course_quiz as _submit_ecommerce_course_quiz,
    update_ecommerce_course_progress as _update_ecommerce_course_progress,
)
from app.ecommerce_training.customer_service import (
    end_customer_session as _end_customer_session,
    generate_next_customer_message as _generate_next_customer_message,
    get_customer_session as _get_customer_session,
    list_customer_scenarios as _list_customer_scenarios,
    list_customer_sessions as _list_customer_sessions,
    start_customer_session as _start_customer_session,
    submit_customer_reply as _submit_customer_reply,
)
from app.ecommerce_training.live_script import (
    generate_live_script as _generate_live_script,
    get_live_script as _get_live_script,
    list_live_scripts as _list_live_scripts,
)
from app.ecommerce_training.presets import (
    COPY_DEFECT_CATEGORIES,
    COPY_PRODUCT_TYPES,
    COPY_TRAINING_SCENES,
)
from app.ecommerce_training.simulation import (
    get_simulation as _get_simulation,
    list_simulation_scenes as _list_simulation_scenes,
    list_simulations as _list_simulations,
    save_simulation_segment as _save_simulation_segment,
    score_simulation as _score_simulation,
    start_simulation as _start_simulation,
)
from app.ecommerce_training.store_guidance import (
    generate_store_plan as _generate_store_plan,
    get_store_plan as _get_store_plan,
    list_store_plans as _list_store_plans,
)
from app.session_manager import abort_session_required, load_session


ecommerce_training_bp = Blueprint(
    "ecommerce_training",
    __name__,
    url_prefix="/api/ecommerce-training",
)

def _student_session() -> dict:
    session = load_session(required=True, allowed_states={"active"})
    if session["role"] != "student":
        abort_session_required()
    return session


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


def _handle_validation(error: AgriValidationError):
    return jsonify(
        success=False,
        message=error.message,
        errors=error.details,
    ), 400


def _handle_not_found(error: AgriNotFoundError | AgriAccessError):
    return jsonify(success=False, message=error.message), 404


def _handle_ai_unavailable(_error: AiUnavailableError):
    return jsonify(
        success=False,
        message="AI 服务暂时不可用",
    ), 503


def register_ecommerce_training_error_handlers(app: Flask) -> None:
    app.register_error_handler(AgriValidationError, _handle_validation)
    app.register_error_handler(AgriNotFoundError, _handle_not_found)
    app.register_error_handler(AgriAccessError, _handle_not_found)
    app.register_error_handler(AiUnavailableError, _handle_ai_unavailable)


@ecommerce_training_bp.post("/live-scripts")
def create_live_script_route():
    session = _student_session()
    version = _generate_live_script(
        int(session["id"]),
        _json_object_payload(),
    )
    return jsonify(success=True, version=version), 201


@ecommerce_training_bp.get("/live-scripts")
def list_live_scripts_route():
    session = _student_session()
    return jsonify(
        success=True,
        versions=_list_live_scripts(int(session["id"])),
    )


@ecommerce_training_bp.get("/live-scripts/<int:version_id>")
def get_live_script_route(version_id: int):
    session = _student_session()
    return jsonify(
        success=True,
        version=_get_live_script(int(session["id"]), version_id),
    )


@ecommerce_training_bp.get("/simulations/scenes")
def list_simulation_scenes_route():
    _student_session()
    return jsonify(
        success=True,
        scenes=_list_simulation_scenes(),
    )


@ecommerce_training_bp.post("/simulations")
def start_simulation_route():
    session = _student_session()
    payload = _json_object_payload()
    training = _start_simulation(
        int(session["id"]),
        payload.get("scene_key"),
    )
    return jsonify(success=True, training=training), 201


@ecommerce_training_bp.get("/simulations")
def list_simulations_route():
    session = _student_session()
    return jsonify(
        success=True,
        trainings=_list_simulations(int(session["id"])),
    )


@ecommerce_training_bp.get("/simulations/<int:training_id>")
def get_simulation_route(training_id: int):
    session = _student_session()
    return jsonify(
        success=True,
        training=_get_simulation(int(session["id"]), training_id),
    )


@ecommerce_training_bp.put(
    "/simulations/<int:training_id>/segments/<segment_key>"
)
def save_simulation_segment_route(
    training_id: int,
    segment_key: str,
):
    session = _student_session()
    payload = _json_object_payload()
    training = _save_simulation_segment(
        int(session["id"]),
        training_id,
        segment_key,
        payload.get("text"),
    )
    return jsonify(success=True, training=training)


@ecommerce_training_bp.post("/simulations/<int:training_id>/score")
def score_simulation_route(training_id: int):
    session = _student_session()
    _json_object_payload()
    training = _score_simulation(int(session["id"]), training_id)
    return jsonify(success=True, training=training)


@ecommerce_training_bp.get("/copy-training/catalog")
def get_copy_training_catalog_route():
    _student_session()
    return jsonify(
        success=True,
        catalog={
            "product_types": list(COPY_PRODUCT_TYPES),
            "scenes": list(COPY_TRAINING_SCENES),
            "defect_categories": list(COPY_DEFECT_CATEGORIES),
        },
    )


@ecommerce_training_bp.post("/copy-training")
def create_copy_training_route():
    session = _student_session()
    payload = _json_object_payload()
    copy_session = _create_copy_training(
        int(session["id"]),
        payload.get("product_type"),
        payload.get("scene"),
    )
    return jsonify(success=True, session=copy_session), 201


@ecommerce_training_bp.get("/copy-training")
def list_copy_trainings_route():
    session = _student_session()
    return jsonify(
        success=True,
        sessions=_list_copy_trainings(int(session["id"])),
    )


@ecommerce_training_bp.get("/copy-training/<int:session_id>")
def get_copy_training_route(session_id: int):
    session = _student_session()
    return jsonify(
        success=True,
        session=_get_copy_training(int(session["id"]), session_id),
    )


@ecommerce_training_bp.post(
    "/copy-training/<int:session_id>/critique"
)
def submit_copy_critique_route(session_id: int):
    session = _student_session()
    payload = _json_object_payload()
    copy_session = _submit_copy_critique(
        int(session["id"]),
        session_id,
        payload.get("critique"),
    )
    return jsonify(success=True, session=copy_session)


@ecommerce_training_bp.post("/copy-training/<int:session_id>/copy")
def generate_revised_copy_route(session_id: int):
    session = _student_session()
    payload = _json_object_payload()
    copy_session = _generate_revised_copy(
        int(session["id"]),
        session_id,
        payload.get("optimized_prompt"),
    )
    return jsonify(success=True, session=copy_session)


@ecommerce_training_bp.post(
    "/copy-training/<int:session_id>/optimization"
)
def generate_optimization_critique_route(session_id: int):
    session = _student_session()
    _json_object_payload()
    copy_session = _generate_optimization_critique(
        int(session["id"]),
        session_id,
    )
    return jsonify(success=True, session=copy_session)


@ecommerce_training_bp.post("/store-plans")
def create_store_plan_route():
    session = _student_session()
    plan = _generate_store_plan(
        int(session["id"]),
        _json_object_payload(),
    )
    return jsonify(success=True, plan=plan), 201


@ecommerce_training_bp.get("/store-plans")
def list_store_plans_route():
    session = _student_session()
    return jsonify(
        success=True,
        plans=_list_store_plans(int(session["id"])),
    )


@ecommerce_training_bp.get("/store-plans/<int:plan_id>")
def get_store_plan_route(plan_id: int):
    session = _student_session()
    return jsonify(
        success=True,
        plan=_get_store_plan(int(session["id"]), plan_id),
    )


@ecommerce_training_bp.get("/customer-service/scenarios")
def list_customer_scenarios_route():
    _student_session()
    return jsonify(
        success=True,
        scenarios=_list_customer_scenarios(),
    )


@ecommerce_training_bp.post("/customer-service/sessions")
def start_customer_session_route():
    session = _student_session()
    payload = _json_object_payload()
    customer_session = _start_customer_session(
        int(session["id"]),
        payload.get("scenario_key"),
    )
    return jsonify(success=True, session=customer_session), 201


@ecommerce_training_bp.get("/customer-service/sessions")
def list_customer_sessions_route():
    session = _student_session()
    return jsonify(
        success=True,
        sessions=_list_customer_sessions(int(session["id"])),
    )


@ecommerce_training_bp.get(
    "/customer-service/sessions/<int:session_id>"
)
def get_customer_session_route(session_id: int):
    session = _student_session()
    return jsonify(
        success=True,
        session=_get_customer_session(int(session["id"]), session_id),
    )


@ecommerce_training_bp.post(
    "/customer-service/sessions/<int:session_id>/replies"
)
def submit_customer_reply_route(session_id: int):
    session = _student_session()
    payload = _json_object_payload()
    customer_session = _submit_customer_reply(
        int(session["id"]),
        session_id,
        payload.get("reply"),
    )
    return jsonify(success=True, session=customer_session)


@ecommerce_training_bp.post(
    "/customer-service/sessions/<int:session_id>/next-message"
)
def generate_next_customer_message_route(session_id: int):
    session = _student_session()
    _json_object_payload()
    customer_session = _generate_next_customer_message(
        int(session["id"]),
        session_id,
    )
    return jsonify(success=True, session=customer_session)


@ecommerce_training_bp.post(
    "/customer-service/sessions/<int:session_id>/end"
)
def end_customer_session_route(session_id: int):
    session = _student_session()
    _json_object_payload()
    customer_session = _end_customer_session(
        int(session["id"]),
        session_id,
    )
    return jsonify(success=True, session=customer_session)


@ecommerce_training_bp.get("/courses")
def list_ecommerce_courses_route():
    session = _student_session()
    return jsonify(
        success=True,
        courses=_list_ecommerce_courses(int(session["id"])),
    )


@ecommerce_training_bp.get("/recommendations")
def list_ecommerce_recommendations_route():
    session = _student_session()
    return jsonify(
        success=True,
        courses=_list_ecommerce_recommendations(int(session["id"])),
    )


@ecommerce_training_bp.get("/courses/<int:course_id>/progress")
def get_ecommerce_course_progress_route(course_id: int):
    session = _student_session()
    return jsonify(
        success=True,
        progress=_get_ecommerce_course_progress(
            int(session["id"]),
            course_id,
        ),
    )


@ecommerce_training_bp.put("/courses/<int:course_id>/progress")
def update_ecommerce_course_progress_route(course_id: int):
    session = _student_session()
    payload = _json_object_payload()
    progress = _update_ecommerce_course_progress(
        int(session["id"]),
        course_id,
        payload.get("position_seconds"),
        payload.get("watched_delta_seconds", 0),
    )
    return jsonify(success=True, progress=progress)


@ecommerce_training_bp.get("/courses/<int:course_id>/quiz")
def get_ecommerce_course_quiz_route(course_id: int):
    session = _student_session()
    quiz = _get_ecommerce_course_quiz(int(session["id"]), course_id)
    if quiz is None:
        raise AgriNotFoundError("暂无可用测验")
    return jsonify(success=True, quiz=quiz)


@ecommerce_training_bp.get("/courses/<int:course_id>/quiz/attempts")
def list_ecommerce_course_quiz_attempts_route(course_id: int):
    session = _student_session()
    return jsonify(
        success=True,
        attempts=_list_ecommerce_quiz_attempts(
            int(session["id"]),
            course_id,
        ),
    )


@ecommerce_training_bp.post("/courses/<int:course_id>/quiz")
def submit_ecommerce_course_quiz_route(course_id: int):
    session = _student_session()
    payload = _json_object_payload()
    answers = payload.get("answers")
    attempt = _submit_ecommerce_course_quiz(
        int(session["id"]),
        course_id,
        answers if isinstance(answers, dict) else {},
    )
    return jsonify(success=True, attempt=attempt), 201
