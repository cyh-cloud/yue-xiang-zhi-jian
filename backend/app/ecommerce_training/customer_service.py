from __future__ import annotations

import copy
import json
import logging

from app.agri_skills.ai_client import get_ai_client
from app.agri_skills.ai_context import build_ai_messages
from app.agri_skills.errors import (
    AgriNotFoundError,
    AgriValidationError,
    AiUnavailableError,
)
from app.db import get_db
from app.ecommerce_training.presets import CUSTOMER_SCENARIOS
from app.handcraft_inheritance.points import record_training_points
from app.session_manager import utc_now_iso


AI_UNAVAILABLE_MESSAGE = "AI 服务暂时不可用"
LOGGER = logging.getLogger(__name__)
GOAL_STATUSES = ("reached", "not_reached")
SUMMARY_KEYS = (
    "overall_performance",
    "main_problems",
    "prioritized_improvements",
    "goal_completion",
)


def list_customer_scenarios() -> list[dict]:
    return [
        {
            "key": scenario_key,
            "label": scenario["label"],
            "criteria": copy.deepcopy(scenario["criteria"]),
        }
        for scenario_key, scenario in CUSTOMER_SCENARIOS.items()
    ]


def _require_scenario(scenario_key: str) -> dict:
    scenario = (
        CUSTOMER_SCENARIOS.get(scenario_key)
        if isinstance(scenario_key, str)
        else None
    )
    if not isinstance(scenario, dict):
        raise AgriValidationError("客服场景不存在")

    label = scenario.get("label")
    criteria = scenario.get("criteria")
    if (
        not isinstance(label, str)
        or not label.strip()
        or not isinstance(criteria, list)
        or len(criteria) < 2
        or not all(
            isinstance(criterion, str) and criterion.strip()
            for criterion in criteria
        )
        or len(set(criteria)) != len(criteria)
    ):
        raise AgriValidationError("客服场景目标无效")

    return {
        "label": label.strip(),
        "criteria": list(criteria),
    }


def _require_text(value, message: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AgriValidationError(message)
    return value.strip()


def _call_ai(call_point: str, context: dict) -> dict:
    try:
        return get_ai_client().complete_json(
            build_ai_messages(call_point, context),
            call_point=call_point,
        )
    except AiUnavailableError as error:
        raise AiUnavailableError(AI_UNAVAILABLE_MESSAGE) from error


def _validate_customer_message(payload: dict) -> str:
    if not isinstance(payload, dict):
        raise AiUnavailableError(AI_UNAVAILABLE_MESSAGE)
    message = payload.get("customer_message")
    if not isinstance(message, str) or not message.strip():
        raise AiUnavailableError(AI_UNAVAILABLE_MESSAGE)
    return message.strip()


def _validate_analysis(payload: dict, criteria: list[str]) -> dict:
    if not isinstance(payload, dict):
        raise AiUnavailableError(AI_UNAVAILABLE_MESSAGE)

    normalized = {}
    for key in ("problem", "evidence", "suggestion"):
        value = payload.get(key)
        if not isinstance(value, str) or not value.strip():
            raise AiUnavailableError(AI_UNAVAILABLE_MESSAGE)
        normalized[key] = value.strip()

    raw_criteria = payload.get("criteria")
    if (
        not isinstance(raw_criteria, dict)
        or set(raw_criteria) != set(criteria)
        or not all(
            isinstance(raw_criteria.get(criterion), bool)
            for criterion in criteria
        )
    ):
        raise AiUnavailableError(AI_UNAVAILABLE_MESSAGE)

    goal_status = payload.get("goal_status")
    if goal_status not in GOAL_STATUSES:
        raise AiUnavailableError(AI_UNAVAILABLE_MESSAGE)

    normalized["criteria"] = {
        criterion: raw_criteria[criterion]
        for criterion in criteria
    }
    normalized["goal_status"] = goal_status
    return normalized


def _normalize_summary_part(value):
    if isinstance(value, str):
        if not value.strip():
            raise AiUnavailableError(AI_UNAVAILABLE_MESSAGE)
        return value.strip()
    if isinstance(value, list):
        if not value:
            raise AiUnavailableError(AI_UNAVAILABLE_MESSAGE)
        return [_normalize_summary_part(item) for item in value]
    if isinstance(value, dict):
        if not value:
            raise AiUnavailableError(AI_UNAVAILABLE_MESSAGE)
        return {
            key: _normalize_summary_part(item)
            for key, item in value.items()
        }
    raise AiUnavailableError(AI_UNAVAILABLE_MESSAGE)


def _validate_summary(payload: dict) -> dict:
    if not isinstance(payload, dict) or set(payload) != set(SUMMARY_KEYS):
        raise AiUnavailableError(AI_UNAVAILABLE_MESSAGE)
    return {
        key: _normalize_summary_part(payload[key])
        for key in SUMMARY_KEYS
    }


def _serialize_turn(row) -> dict:
    return {
        "id": int(row["id"]),
        "turn_no": int(row["turn_no"]),
        "customer_message": str(row["customer_message"]),
        "student_reply": (
            str(row["student_reply"])
            if row["student_reply"] is not None
            else None
        ),
        "analysis": (
            json.loads(row["analysis_json"])
            if row["analysis_json"] is not None
            else None
        ),
        "created_at": str(row["created_at"]),
    }


def _turn_context(row) -> dict:
    return {
        "turn_no": int(row["turn_no"]),
        "customer_message": str(row["customer_message"]),
        "student_reply": (
            str(row["student_reply"])
            if row["student_reply"] is not None
            else None
        ),
        "analysis": (
            json.loads(row["analysis_json"])
            if row["analysis_json"] is not None
            else None
        ),
    }


def _get_turn_rows(session_id: int):
    return get_db().execute(
        """
        SELECT id, turn_no, customer_message, student_reply,
               analysis_json, created_at
        FROM ecommerce_customer_turns
        WHERE session_id = ?
        ORDER BY turn_no ASC, id ASC
        """,
        (session_id,),
    ).fetchall()


def _serialize_session(row, turns=None) -> dict:
    turn_rows = _get_turn_rows(int(row["id"])) if turns is None else turns
    scenario_key = str(row["scenario_key"])
    scenario = CUSTOMER_SCENARIOS.get(scenario_key, {})
    return {
        "id": int(row["id"]),
        "scenario_key": scenario_key,
        "scenario_label": str(scenario.get("label", "")),
        "goal_criteria": json.loads(row["goal_criteria_json"]),
        "status": str(row["status"]),
        "end_suggested": bool(row["end_suggested"]),
        "turns": [_serialize_turn(turn) for turn in turn_rows],
        "summary": (
            json.loads(row["summary_json"])
            if row["summary_json"] is not None
            else None
        ),
        "confirmed_at": (
            str(row["confirmed_at"])
            if row["confirmed_at"] is not None
            else None
        ),
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
        SELECT id, user_id, scenario_key, goal_criteria_json, status,
               end_suggested, confirmed_at, summary_json, created_at,
               updated_at, completed_at
        FROM ecommerce_customer_sessions
        WHERE id = ? AND user_id = ?
        """,
        (session_id, user_id),
    ).fetchone()
    if row is None:
        raise AgriNotFoundError("客服模拟训练不存在")
    return row


def get_customer_session(user_id: int, session_id: int) -> dict:
    return _serialize_session(_get_session_row(user_id, session_id))


def list_customer_sessions(user_id: int) -> list[dict]:
    rows = get_db().execute(
        """
        SELECT id, user_id, scenario_key, goal_criteria_json, status,
               end_suggested, confirmed_at, summary_json, created_at,
               updated_at, completed_at
        FROM ecommerce_customer_sessions
        WHERE user_id = ?
        ORDER BY id DESC
        """,
        (user_id,),
    ).fetchall()
    return [_serialize_session(row) for row in rows]


def start_customer_session(user_id: int, scenario_key: str) -> dict:
    scenario = _require_scenario(scenario_key)
    response = _call_ai(
        "customer_message_generate",
        {
            "scenario": scenario["label"],
            "goal_criteria": scenario["criteria"],
            "prior_turns": [],
            "turn_no": 1,
        },
    )
    customer_message = _validate_customer_message(response)

    now = utc_now_iso()
    db = get_db()
    with db:
        cursor = db.execute(
            """
            INSERT INTO ecommerce_customer_sessions (
                user_id, scenario_key, goal_criteria_json, status,
                end_suggested, confirmed_at, summary_json, created_at,
                updated_at, completed_at
            )
            VALUES (?, ?, ?, 'active', 0, NULL, NULL, ?, ?, NULL)
            """,
            (
                user_id,
                scenario_key,
                json.dumps(scenario["criteria"], ensure_ascii=False),
                now,
                now,
            ),
        )
        session_id = int(cursor.lastrowid)
        db.execute(
            """
            INSERT INTO ecommerce_customer_turns (
                session_id, turn_no, customer_message, student_reply,
                analysis_json, created_at
            )
            VALUES (?, 1, ?, NULL, NULL, ?)
            """,
            (session_id, customer_message, now),
        )

    return get_customer_session(user_id, session_id)


def submit_customer_reply(
    user_id: int,
    session_id: int,
    reply: str,
) -> dict:
    row = _get_session_row(user_id, session_id)
    if row["status"] == "completed":
        raise AgriValidationError("客服模拟训练已结束")
    if bool(row["end_suggested"]):
        raise AgriValidationError("请确认结束训练")

    reply = _require_text(reply, "学员回复不能为空")
    latest = get_db().execute(
        """
        SELECT id, turn_no, customer_message, student_reply,
               analysis_json, created_at
        FROM ecommerce_customer_turns
        WHERE session_id = ?
        ORDER BY turn_no DESC, id DESC
        LIMIT 1
        """,
        (session_id,),
    ).fetchone()
    if latest is None:
        raise AgriValidationError("当前没有待回复的客户消息")
    if latest["analysis_json"] is not None:
        raise AgriValidationError("请先获取下一条客户消息")

    db = get_db()
    with db:
        db.execute(
            """
            UPDATE ecommerce_customer_turns
            SET student_reply = ?
            WHERE id = ? AND analysis_json IS NULL
            """,
            (reply, latest["id"]),
        )

    scenario = _require_scenario(str(row["scenario_key"]))
    response = _call_ai(
        "customer_reply_analyze",
        {
            "scenario": scenario["label"],
            "goal_criteria": scenario["criteria"],
            "customer_message": str(latest["customer_message"]),
            "student_reply": reply,
        },
    )
    analysis = _validate_analysis(response, scenario["criteria"])
    end_suggested = (
        analysis["goal_status"] == "reached"
        and all(analysis["criteria"].values())
    )

    now = utc_now_iso()
    with db:
        updated = db.execute(
            """
            UPDATE ecommerce_customer_turns
            SET analysis_json = ?
            WHERE id = ? AND analysis_json IS NULL
            """,
            (
                json.dumps(analysis, ensure_ascii=False),
                latest["id"],
            ),
        )
        if updated.rowcount != 1:
            return get_customer_session(user_id, session_id)
        db.execute(
            """
            UPDATE ecommerce_customer_sessions
            SET status = ?, end_suggested = ?, updated_at = ?
            WHERE id = ? AND user_id = ? AND status != 'completed'
            """,
            (
                "goal_reached" if end_suggested else "active",
                1 if end_suggested else 0,
                now,
                session_id,
                user_id,
            ),
        )

    return get_customer_session(user_id, session_id)


def generate_next_customer_message(user_id: int, session_id: int) -> dict:
    row = _get_session_row(user_id, session_id)
    if row["status"] != "active" or bool(row["end_suggested"]):
        raise AgriValidationError("当前不能生成下一条客户消息")

    turn_rows = _get_turn_rows(session_id)
    if not turn_rows:
        raise AgriValidationError("当前没有待回复的客户消息")
    latest = turn_rows[-1]
    if (
        latest["student_reply"] is None
        or not str(latest["student_reply"]).strip()
        or latest["analysis_json"] is None
    ):
        raise AgriValidationError("请先完成当前回复分析")

    scenario = _require_scenario(str(row["scenario_key"]))
    next_turn_no = int(latest["turn_no"]) + 1
    response = _call_ai(
        "customer_message_generate",
        {
            "scenario": scenario["label"],
            "goal_criteria": scenario["criteria"],
            "prior_turns": [
                _turn_context(turn)
                for turn in turn_rows
            ],
            "turn_no": next_turn_no,
        },
    )
    customer_message = _validate_customer_message(response)

    now = utc_now_iso()
    db = get_db()
    with db:
        db.execute(
            """
            INSERT INTO ecommerce_customer_turns (
                session_id, turn_no, customer_message, student_reply,
                analysis_json, created_at
            )
            VALUES (?, ?, ?, NULL, NULL, ?)
            """,
            (
                session_id,
                next_turn_no,
                customer_message,
                now,
            ),
        )
        db.execute(
            """
            UPDATE ecommerce_customer_sessions
            SET updated_at = ?
            WHERE id = ? AND user_id = ? AND status = 'active'
            """,
            (now, session_id, user_id),
        )

    return get_customer_session(user_id, session_id)


def end_customer_session(user_id: int, session_id: int) -> dict:
    row = _get_session_row(user_id, session_id)
    if row["status"] == "completed":
        return _serialize_session(row)
    if not bool(row["end_suggested"]):
        raise AgriValidationError("目标尚未达成，不能结束训练")

    scenario = _require_scenario(str(row["scenario_key"]))
    turns = _get_turn_rows(session_id)
    response = _call_ai(
        "customer_summary",
        {
            "scenario": scenario["label"],
            "goal_criteria": scenario["criteria"],
            "turns": [_turn_context(turn) for turn in turns],
        },
    )
    summary = _validate_summary(response)

    now = utc_now_iso()
    db = get_db()
    with db:
        updated = db.execute(
            """
            UPDATE ecommerce_customer_sessions
            SET status = 'completed', summary_json = ?, confirmed_at = ?,
                updated_at = ?, completed_at = ?
            WHERE id = ? AND user_id = ? AND status != 'completed'
            """,
            (
                json.dumps(summary, ensure_ascii=False),
                now,
                now,
                now,
                session_id,
                user_id,
            ),
        )
        if updated.rowcount != 1:
            return get_customer_session(user_id, session_id)

    completed = get_customer_session(user_id, session_id)
    try:
        record_training_points(
            user_id,
            "ecommerce",
            "customer_service",
            f"customer-service:{session_id}",
            str(completed["completed_at"]),
        )
    except Exception as error:
        LOGGER.warning(
            "Customer-service points recording failed: %s",
            type(error).__name__,
        )
    return completed
