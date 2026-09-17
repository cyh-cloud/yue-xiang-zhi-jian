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
from app.ecommerce_training.presets import STORE_PLATFORMS
from app.session_manager import utc_now_iso


AI_UNAVAILABLE_MESSAGE = "AI 服务暂时不可用"
STORE_PLATFORM_KEYS = set(STORE_PLATFORMS)
PLAN_KEYS = (
    "home_layout",
    "color_scheme",
    "detail_structure",
    "navigation",
)


def _required_text(value, message: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AgriValidationError(message)
    return value.strip()


def _validate_payload(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise AgriValidationError("请求参数不正确")

    store_type = _required_text(
        payload.get("store_type"),
        "店铺类型不能为空",
    )
    platform = payload.get("platform")
    if platform not in STORE_PLATFORM_KEYS:
        raise AgriValidationError("店铺平台不支持，请重新选择")
    style_preference = _required_text(
        payload.get("style_preference"),
        "风格偏好不能为空",
    )
    return {
        "store_type": store_type,
        "platform": platform,
        "style_preference": style_preference,
    }


def _validate_plan(payload: dict) -> dict:
    if not isinstance(payload, dict) or set(payload) != set(PLAN_KEYS):
        raise AiUnavailableError(AI_UNAVAILABLE_MESSAGE)

    plan = {}
    for key in PLAN_KEYS:
        value = payload[key]
        if (
            value is None
            or (isinstance(value, str) and not value.strip())
            or (isinstance(value, (list, dict)) and not value)
        ):
            raise AiUnavailableError(AI_UNAVAILABLE_MESSAGE)
        plan[key] = value
    return plan


def _serialize_row(row) -> dict:
    return {
        "id": int(row["id"]),
        "store_type": str(row["store_type"]),
        "platform": str(row["platform"]),
        "style_preference": str(row["style_preference"]),
        "plan": json.loads(row["plan_json"]),
        "created_at": str(row["created_at"]),
    }


def generate_store_plan(user_id: int, payload: dict) -> dict:
    request = _validate_payload(payload)
    try:
        response = get_ai_client().complete_json(
            build_ai_messages("store_plan_generate", request),
            call_point="store_plan_generate",
        )
    except AiUnavailableError as error:
        raise AiUnavailableError(AI_UNAVAILABLE_MESSAGE) from error
    plan = _validate_plan(response)
    db = get_db()
    with db:
        cursor = db.execute(
            """
            INSERT INTO ecommerce_store_plans (
                user_id, store_type, platform, style_preference,
                plan_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                request["store_type"],
                request["platform"],
                request["style_preference"],
                json.dumps(plan, ensure_ascii=False),
                utc_now_iso(),
            ),
        )
    row = db.execute(
        """
        SELECT id, store_type, platform, style_preference, plan_json,
               created_at
        FROM ecommerce_store_plans
        WHERE id = ? AND user_id = ?
        """,
        (cursor.lastrowid, user_id),
    ).fetchone()
    if row is None:
        raise AgriNotFoundError("店铺装修方案不存在")
    return _serialize_row(row)


def list_store_plans(user_id: int) -> list[dict]:
    rows = get_db().execute(
        """
        SELECT id, store_type, platform, style_preference, plan_json,
               created_at
        FROM ecommerce_store_plans
        WHERE user_id = ?
        ORDER BY id DESC
        """,
        (user_id,),
    ).fetchall()
    return [_serialize_row(row) for row in rows]


def get_store_plan(user_id: int, plan_id: int) -> dict:
    row = get_db().execute(
        """
        SELECT id, store_type, platform, style_preference, plan_json,
               created_at
        FROM ecommerce_store_plans
        WHERE id = ? AND user_id = ?
        """,
        (plan_id, user_id),
    ).fetchone()
    if row is None:
        raise AgriNotFoundError("店铺装修方案不存在")
    return _serialize_row(row)
