from __future__ import annotations

import logging
from uuid import uuid4

from app.agri_skills.ai_client import get_ai_client
from app.agri_skills.ai_context import build_ai_messages
from app.agri_skills.errors import AgriValidationError, AiUnavailableError
from app.db import get_db
from app.handcraft_inheritance.active_learning import claim_active_seconds
from app.handcraft_inheritance.crafts import get_craft
from app.handcraft_inheritance.outcomes import (
    record_handcraft_learning_outcome,
)
from app.handcraft_inheritance.points import record_duration_points
from app.session_manager import utc_now_iso


AI_UNAVAILABLE_MESSAGE = "AI 服务暂时不可用"
CALL_POINT = "handcraft_ar_guidance_generate"
LOGGER = logging.getLogger(__name__)
REQUIRED_LIST_FIELDS = (
    "tool_preparation",
    "operating_points",
    "common_errors",
)
STEP_FIELDS = {"step_no", "title", "instruction"}


def _required_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _string_list(value: object) -> list[str] | None:
    if not isinstance(value, list) or not value:
        return None
    normalized = []
    for item in value:
        text = _required_text(item)
        if text is None:
            return None
        normalized.append(text)
    return normalized


def _normalize_guidance(payload: object, craft: dict) -> dict:
    if not isinstance(payload, dict):
        raise AiUnavailableError(AI_UNAVAILABLE_MESSAGE)

    craft_key = _required_text(payload.get("craft_key"))
    if craft_key != craft["craft_key"]:
        raise AiUnavailableError(AI_UNAVAILABLE_MESSAGE)

    result = {"craft_key": craft_key}
    for field in REQUIRED_LIST_FIELDS:
        values = _string_list(payload.get(field))
        if values is None:
            raise AiUnavailableError(AI_UNAVAILABLE_MESSAGE)
        result[field] = values

    raw_steps = payload.get("steps")
    if not isinstance(raw_steps, list) or not raw_steps:
        raise AiUnavailableError(AI_UNAVAILABLE_MESSAGE)

    steps = []
    for expected_step_no, raw_step in enumerate(raw_steps, start=1):
        if not isinstance(raw_step, dict) or set(raw_step) != STEP_FIELDS:
            raise AiUnavailableError(AI_UNAVAILABLE_MESSAGE)
        step_no = raw_step.get("step_no")
        title = _required_text(raw_step.get("title"))
        instruction = _required_text(raw_step.get("instruction"))
        if (
            not isinstance(step_no, int)
            or isinstance(step_no, bool)
            or step_no != expected_step_no
            or title is None
            or instruction is None
        ):
            raise AiUnavailableError(AI_UNAVAILABLE_MESSAGE)
        steps.append(
            {
                "step_no": step_no,
                "title": title,
                "instruction": instruction,
            }
        )
    result["steps"] = steps
    return result


def generate_ar_guidance(
    user_id: int,
    craft_key: str,
    project_label: str,
    active_seconds: object = None,
    event_id: object = None,
    *,
    segment_id: object = None,
) -> dict:
    if segment_id is None and isinstance(active_seconds, str):
        segment_id = active_seconds
    # Legacy duration/event arguments are intentionally ignored.
    del active_seconds, event_id
    if (
        not isinstance(user_id, int)
        or isinstance(user_id, bool)
        or user_id <= 0
    ):
        raise AgriValidationError("学员标识必须是正整数")

    craft = get_craft(craft_key)
    if not craft["available"]:
        raise AgriValidationError("请选择有效技艺")

    normalized_project_label = _required_text(project_label)
    if normalized_project_label is None:
        raise AgriValidationError("手工项目不能为空")

    context = {
        "craft_key": craft["craft_key"],
        "craft_name": craft["name"],
        "project_label": normalized_project_label,
    }
    try:
        payload = get_ai_client().complete_json(
            build_ai_messages(CALL_POINT, context),
            call_point=CALL_POINT,
        )
        result = _normalize_guidance(payload, craft)
    except Exception as error:
        raise AiUnavailableError(
            AI_UNAVAILABLE_MESSAGE,
            details=context,
        ) from error

    created_at = utc_now_iso()
    normalized_segment_id = (
        str(segment_id).strip()
        if segment_id is not None and str(segment_id).strip()
        else None
    )
    source_key = (
        f"ar:{craft['craft_key']}:segment:{normalized_segment_id}"
        if normalized_segment_id is not None
        else f"ar:{craft['craft_key']}:{uuid4().hex}"
    )
    with get_db():
        record_handcraft_learning_outcome(
            user_id,
            "ar_usage",
            source_key,
            created_at,
            f"{craft['name']} · {normalized_project_label}",
        )

    active_seconds = claim_active_seconds(
        user_id,
        "ar",
        craft["craft_key"],
        segment_id,
        close_segment=True,
    )
    if active_seconds > 0:
        try:
            points_result = record_duration_points(
                user_id,
                "handcraft",
                craft["craft_key"],
                active_seconds,
                utc_now_iso(),
                f"ar:segment-{normalized_segment_id}",
            )
        except Exception as error:
            LOGGER.warning(
                "AR active-use points recording failed: %s",
                type(error).__name__,
            )
        else:
            if (
                isinstance(points_result, dict)
                and points_result.get("status") == "failed"
            ):
                LOGGER.warning(
                    "AR active-use points recording failed: %s",
                    "failed_result",
                )
    return result
