from __future__ import annotations

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
from app.ecommerce_training.presets import LIVE_SCRIPT_STYLES
from app.handcraft_inheritance.points import record_training_points
from app.session_manager import utc_now_iso


AI_UNAVAILABLE_MESSAGE = "AI 服务暂时不可用"
SCRIPT_KEYS = ("opening", "product_intro", "interaction", "closing")
LOGGER = logging.getLogger(__name__)


def _validate_payload(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise AgriValidationError("请求参数不正确")

    raw_selling_points = payload.get("selling_points", [])
    if isinstance(raw_selling_points, str):
        raw_selling_points = [raw_selling_points]
    elif not isinstance(raw_selling_points, (list, tuple)):
        raw_selling_points = []

    product_name = str(payload.get("product_name", "")).strip()
    selling_points = [
        str(value).strip()
        for value in raw_selling_points
        if str(value).strip()
    ]
    price_text = payload.get("price_text", "")
    price_text = "" if price_text is None else str(price_text).strip()
    style = str(payload.get("style", "")).strip()

    if not product_name:
        raise AgriValidationError("商品名称不能为空")
    if not selling_points:
        raise AgriValidationError("至少填写一个卖点")
    if style not in LIVE_SCRIPT_STYLES:
        raise AgriValidationError("直播风格不正确")

    return {
        "product_name": product_name,
        "selling_points": selling_points,
        "price_text": price_text,
        "style": style,
    }


def _validate_script(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise AiUnavailableError(AI_UNAVAILABLE_MESSAGE)

    script = {}
    for key in SCRIPT_KEYS:
        value = payload.get(key)
        if not isinstance(value, str) or not value.strip():
            raise AiUnavailableError(AI_UNAVAILABLE_MESSAGE)
        script[key] = value.strip()
    return script


def _serialize_row(row) -> dict:
    return {
        "id": int(row["id"]),
        "product_name": str(row["product_name"]),
        "selling_points": json.loads(row["selling_points_json"]),
        "price_text": str(row["price_text"]),
        "style": str(row["style"]),
        "script": json.loads(row["script_json"]),
        "is_current": bool(row["is_current"]),
        "created_at": str(row["created_at"]),
    }


def generate_live_script(user_id: int, payload: dict) -> dict:
    request = _validate_payload(payload)
    try:
        response = get_ai_client().complete_json(
            build_ai_messages("live_script_generate", request),
            call_point="live_script_generate",
        )
    except AiUnavailableError as error:
        raise AiUnavailableError(AI_UNAVAILABLE_MESSAGE) from error

    script = _validate_script(response)
    db = get_db()
    with db:
        db.execute(
            """
            UPDATE ecommerce_live_script_versions
            SET is_current = 0
            WHERE user_id = ?
            """,
            (user_id,),
        )
        cursor = db.execute(
            """
            INSERT INTO ecommerce_live_script_versions (
                user_id, product_name, selling_points_json, price_text,
                style, script_json, is_current, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, 1, ?)
            """,
            (
                user_id,
                request["product_name"],
                json.dumps(request["selling_points"], ensure_ascii=False),
                request["price_text"],
                request["style"],
                json.dumps(script, ensure_ascii=False),
                utc_now_iso(),
            ),
        )
        row = db.execute(
            """
            SELECT id, product_name, selling_points_json, price_text,
                   style, script_json, is_current, created_at
            FROM ecommerce_live_script_versions
            WHERE id = ? AND user_id = ?
            """,
            (cursor.lastrowid, user_id),
        ).fetchone()

    if row is None:
        raise AgriNotFoundError("直播话术版本不存在")
    version = _serialize_row(row)
    try:
        record_training_points(
            user_id,
            "ecommerce",
            "live_script",
            f"live-script:{version['id']}",
            version["created_at"],
        )
    except Exception as error:
        LOGGER.warning(
            "Live-script points recording failed: %s",
            type(error).__name__,
        )
    return version


def list_live_scripts(user_id: int) -> list[dict]:
    rows = get_db().execute(
        """
        SELECT id, product_name, selling_points_json, price_text,
               style, script_json, is_current, created_at
        FROM ecommerce_live_script_versions
        WHERE user_id = ?
        ORDER BY id DESC
        """,
        (user_id,),
    ).fetchall()
    return [_serialize_row(row) for row in rows]


def get_live_script(user_id: int, version_id: int) -> dict:
    row = get_db().execute(
        """
        SELECT id, product_name, selling_points_json, price_text,
               style, script_json, is_current, created_at
        FROM ecommerce_live_script_versions
        WHERE id = ? AND user_id = ?
        """,
        (version_id, user_id),
    ).fetchone()
    if row is None:
        raise AgriNotFoundError("直播话术版本不存在")
    return _serialize_row(row)
