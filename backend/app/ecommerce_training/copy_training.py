from __future__ import annotations

import json

from app.agri_skills.ai_client import get_ai_client
from app.agri_skills.ai_context import build_ai_messages
from app.agri_skills.errors import (
    AgriNotFoundError,
    AgriValidationError,
    AiUnavailableError,
)
from app.db import get_db
from app.ecommerce_training.presets import (
    COPY_DEFECT_CATEGORIES,
    COPY_PRODUCT_TYPES,
    COPY_TRAINING_SCENES,
)
from app.session_manager import utc_now_iso


AI_UNAVAILABLE_MESSAGE = "AI 服务暂时不可用"
TRANSITIONS = {
    ("case_ready", "critique"): "critique_ready",
    ("critique_ready", "copy"): "copy_ready",
    ("copy_ready", "optimization"): "completed",
}
CALL_POINTS = {
    "case": "copy_case_generate",
    "critique": "copy_reference_critique",
    "copy": "copy_revised_generate",
    "optimization": "copy_optimization_critique",
}


def _validate_case(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise AiUnavailableError(AI_UNAVAILABLE_MESSAGE)

    text = payload.get("copy_text")
    categories = payload.get("defect_categories")
    if (
        not isinstance(text, str)
        or not text.strip()
        or not isinstance(categories, list)
        or not all(isinstance(category, str) for category in categories)
    ):
        raise AiUnavailableError(AI_UNAVAILABLE_MESSAGE)

    normalized_categories = sorted(set(categories))
    if (
        len(normalized_categories) < 2
        or not set(normalized_categories).issubset(COPY_DEFECT_CATEGORIES)
    ):
        raise AiUnavailableError(AI_UNAVAILABLE_MESSAGE)

    return {
        "copy_text": text.strip(),
        "defect_categories": normalized_categories,
    }


def _validate_reference(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise AiUnavailableError(AI_UNAVAILABLE_MESSAGE)

    critique = payload.get("reference_critique")
    score = payload.get("consistency_score")
    reason = payload.get("reason")
    if (
        not isinstance(critique, str)
        or not critique.strip()
        or not isinstance(score, int)
        or isinstance(score, bool)
        or not 0 <= score <= 100
        or not isinstance(reason, str)
        or not reason.strip()
    ):
        raise AiUnavailableError(AI_UNAVAILABLE_MESSAGE)

    return {
        "reference_critique": critique.strip(),
        "consistency_score": score,
        "reason": reason.strip(),
    }


def _validate_revised_copy(payload: dict) -> str:
    if not isinstance(payload, dict):
        raise AiUnavailableError(AI_UNAVAILABLE_MESSAGE)

    revised_copy = payload.get("revised_copy")
    if not isinstance(revised_copy, str) or not revised_copy.strip():
        raise AiUnavailableError(AI_UNAVAILABLE_MESSAGE)
    return revised_copy.strip()


def _validate_optimization(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise AiUnavailableError(AI_UNAVAILABLE_MESSAGE)

    differences = payload.get("differences")
    score = payload.get("optimization_score")
    evidence = payload.get("evidence")
    if (
        not isinstance(differences, list)
        or not differences
        or not all(
            isinstance(difference, str) and difference.strip()
            for difference in differences
        )
        or not isinstance(score, int)
        or isinstance(score, bool)
        or not 0 <= score <= 100
        or not isinstance(evidence, str)
        or not evidence.strip()
    ):
        raise AiUnavailableError(AI_UNAVAILABLE_MESSAGE)

    return {
        "differences": [difference.strip() for difference in differences],
        "optimization_score": score,
        "evidence": evidence.strip(),
    }


def _serialize_row(row) -> dict:
    stored_case = json.loads(row["case_json"])
    reference = (
        json.loads(row["reference_json"])
        if row["reference_json"] is not None
        else None
    )
    optimization = (
        json.loads(row["optimization_json"])
        if row["optimization_json"] is not None
        else None
    )
    case = {
        "copy_text": str(stored_case["copy_text"]),
        "is_teaching_case": True,
    }
    if row["status"] != "case_ready":
        case["defect_categories"] = list(
            stored_case["defect_categories"]
        )

    return {
        "id": int(row["id"]),
        "product_type": str(row["product_type"]),
        "scene": str(row["scene_key"]),
        "status": str(row["status"]),
        "case": case,
        "learner_critique": (
            str(row["learner_critique"])
            if row["learner_critique"] is not None
            else None
        ),
        "reference": reference,
        "optimized_prompt": (
            str(row["optimized_prompt"])
            if row["optimized_prompt"] is not None
            else None
        ),
        "revised_copy": (
            str(row["revised_copy"])
            if row["revised_copy"] is not None
            else None
        ),
        "optimization": optimization,
        "created_at": str(row["created_at"]),
        "updated_at": str(row["updated_at"]),
        "completed_at": (
            str(row["completed_at"])
            if row["completed_at"] is not None
            else None
        ),
    }


def _get_session_row(user_id: int, session_id: int):
    row = get_db().execute(
        """
        SELECT id, user_id, product_type, scene_key, status, case_json,
               learner_critique, reference_json, optimized_prompt,
               revised_copy, optimization_json, created_at, updated_at,
               completed_at
        FROM ecommerce_copy_training_sessions
        WHERE id = ? AND user_id = ?
        """,
        (session_id, user_id),
    ).fetchone()
    if row is None:
        raise AgriNotFoundError("文案训练不存在")
    return row


def _require_transition(row, step: str) -> str:
    target = TRANSITIONS.get((str(row["status"]), step))
    if target is None:
        raise AgriValidationError("训练步骤不正确")
    return target


def _require_text(value: str, message: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AgriValidationError(message)
    return value.strip()


def _call_ai(step: str, context: dict) -> dict:
    call_point = CALL_POINTS[step]
    try:
        return get_ai_client().complete_json(
            build_ai_messages(call_point, context),
            call_point=call_point,
        )
    except AiUnavailableError as error:
        raise AiUnavailableError(AI_UNAVAILABLE_MESSAGE) from error


def create_copy_training(
    user_id: int,
    product_type: str,
    scene: str,
) -> dict:
    product_type = _require_text(product_type, "商品类型不能为空")
    scene = _require_text(scene, "训练场景不能为空")
    if product_type not in COPY_PRODUCT_TYPES:
        raise AgriValidationError("商品类型不在预设目录内")
    if scene not in COPY_TRAINING_SCENES:
        raise AgriValidationError("训练场景不在预设目录内")
    response = _call_ai(
        "case",
        {
            "product_type": product_type,
            "scene": scene,
        },
    )
    case = _validate_case(response)
    now = utc_now_iso()
    db = get_db()
    with db:
        cursor = db.execute(
            """
            INSERT INTO ecommerce_copy_training_sessions (
                user_id, product_type, scene_key, status, case_json,
                learner_critique, reference_json, optimized_prompt,
                revised_copy, optimization_json, created_at, updated_at,
                completed_at
            )
            VALUES (?, ?, ?, 'case_ready', ?, NULL, NULL, NULL, NULL, NULL,
                    ?, ?, NULL)
            """,
            (
                user_id,
                product_type,
                scene,
                json.dumps(case, ensure_ascii=False),
                now,
                now,
            ),
        )
    return _serialize_row(_get_session_row(user_id, int(cursor.lastrowid)))


def submit_copy_critique(
    user_id: int,
    session_id: int,
    critique: str,
) -> dict:
    row = _get_session_row(user_id, session_id)
    _require_transition(row, "critique")
    critique = _require_text(critique, "学员评判不能为空")

    db = get_db()
    with db:
        db.execute(
            """
            UPDATE ecommerce_copy_training_sessions
            SET learner_critique = ?, updated_at = ?
            WHERE id = ? AND user_id = ? AND status = 'case_ready'
            """,
            (
                critique,
                utc_now_iso(),
                session_id,
                user_id,
            ),
        )

    case = json.loads(row["case_json"])
    response = _call_ai(
        "critique",
        {
            "case_text": case["copy_text"],
            "defect_categories": case["defect_categories"],
            "learner_critique": critique,
        },
    )
    reference = _validate_reference(response)
    now = utc_now_iso()
    with db:
        updated = db.execute(
            """
            UPDATE ecommerce_copy_training_sessions
            SET status = 'critique_ready', reference_json = ?,
                updated_at = ?
            WHERE id = ? AND user_id = ? AND status = 'case_ready'
            """,
            (
                json.dumps(reference, ensure_ascii=False),
                now,
                session_id,
                user_id,
            ),
        )
        if updated.rowcount != 1:
            return _serialize_row(_get_session_row(user_id, session_id))
    return _serialize_row(_get_session_row(user_id, session_id))


def generate_revised_copy(
    user_id: int,
    session_id: int,
    optimized_prompt: str,
) -> dict:
    row = _get_session_row(user_id, session_id)
    _require_transition(row, "copy")
    optimized_prompt = _require_text(
        optimized_prompt,
        "优化提示词不能为空",
    )

    db = get_db()
    with db:
        db.execute(
            """
            UPDATE ecommerce_copy_training_sessions
            SET optimized_prompt = ?, updated_at = ?
            WHERE id = ? AND user_id = ? AND status = 'critique_ready'
            """,
            (
                optimized_prompt,
                utc_now_iso(),
                session_id,
                user_id,
            ),
        )

    case = json.loads(row["case_json"])
    response = _call_ai(
        "copy",
        {
            "optimized_prompt": optimized_prompt,
            "case_text": case["copy_text"],
        },
    )
    revised_copy = _validate_revised_copy(response)
    now = utc_now_iso()
    with db:
        updated = db.execute(
            """
            UPDATE ecommerce_copy_training_sessions
            SET status = 'copy_ready', revised_copy = ?, updated_at = ?
            WHERE id = ? AND user_id = ? AND status = 'critique_ready'
            """,
            (
                revised_copy,
                now,
                session_id,
                user_id,
            ),
        )
        if updated.rowcount != 1:
            return _serialize_row(_get_session_row(user_id, session_id))
    return _serialize_row(_get_session_row(user_id, session_id))


def generate_optimization_critique(
    user_id: int,
    session_id: int,
) -> dict:
    row = _get_session_row(user_id, session_id)
    if row["status"] == "completed":
        return _serialize_row(row)
    _require_transition(row, "optimization")

    case = json.loads(row["case_json"])
    response = _call_ai(
        "optimization",
        {
            "original_copy": case["copy_text"],
            "revised_copy": str(row["revised_copy"]),
            "optimized_prompt": str(row["optimized_prompt"]),
        },
    )
    optimization = _validate_optimization(response)
    now = utc_now_iso()
    db = get_db()
    with db:
        updated = db.execute(
            """
            UPDATE ecommerce_copy_training_sessions
            SET status = 'completed', optimization_json = ?,
                updated_at = ?, completed_at = ?
            WHERE id = ? AND user_id = ? AND status = 'copy_ready'
            """,
            (
                json.dumps(optimization, ensure_ascii=False),
                now,
                now,
                session_id,
                user_id,
            ),
        )
        if updated.rowcount != 1:
            return _serialize_row(_get_session_row(user_id, session_id))
    return _serialize_row(_get_session_row(user_id, session_id))


def get_copy_training(user_id: int, session_id: int) -> dict:
    return _serialize_row(_get_session_row(user_id, session_id))


def list_copy_trainings(user_id: int) -> list[dict]:
    rows = get_db().execute(
        """
        SELECT id, user_id, product_type, scene_key, status, case_json,
               learner_critique, reference_json, optimized_prompt,
               revised_copy, optimization_json, created_at, updated_at,
               completed_at
        FROM ecommerce_copy_training_sessions
        WHERE user_id = ?
        ORDER BY id DESC
        """,
        (user_id,),
    ).fetchall()
    return [_serialize_row(row) for row in rows]
