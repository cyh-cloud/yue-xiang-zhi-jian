from __future__ import annotations

import json
from copy import deepcopy

from app.agri_skills.errors import AgriValidationError
from app.db import get_db
from app.handcraft_inheritance.points import record_duration_points
from app.handcraft_inheritance.providers import get_craft_preset_provider
from app.session_manager import utc_now_iso


CRAFT_CONTENT_UNAVAILABLE = "技艺内容不可用"
CRAFT_DUPLICATE_UNAVAILABLE = "技艺内容来源重复"
EXPECTED_CRAFT_KEYS = (
    "guangxiu",
    "chaoshan-woodcarving",
    "shiwan-ceramics",
    "yangjiang-lacquerware",
)
CRAFT_SORT_ORDERS = {
    craft_key: index
    for index, craft_key in enumerate(EXPECTED_CRAFT_KEYS, start=1)
}
MATERIAL_GUIDE_FIELDS = (
    "name",
    "reference_price",
    "purchase_channel",
    "precautions",
    "taobao_keyword",
)
REQUIRED_STEP_COUNT = 6


def _unavailable_craft(
    craft_key: str | None = None,
    *,
    reason: str = CRAFT_CONTENT_UNAVAILABLE,
) -> dict:
    normalized_key = str(craft_key or "").strip() or None
    return {
        "craft_key": normalized_key,
        "name": None,
        "sort_order": CRAFT_SORT_ORDERS.get(normalized_key),
        "introduction": "",
        "is_demo": False,
        "source_available": False,
        "status": "unavailable",
        "available": False,
        "unavailable_reason": reason,
        "steps": [],
        "material_guide": [],
    }


def _required_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _normalize_step(raw_step: object) -> dict | None:
    if not isinstance(raw_step, dict):
        return None
    step_no = raw_step.get("step_no")
    step_key = _required_text(raw_step.get("step_key"))
    title = _required_text(raw_step.get("title"))
    description = _required_text(raw_step.get("description"))
    raw_tips = raw_step.get("tips")
    if (
        not isinstance(step_no, int)
        or isinstance(step_no, bool)
        or step_key is None
        or title is None
        or description is None
        or not isinstance(raw_tips, (list, tuple))
    ):
        return None
    tips = [
        normalized
        for tip in raw_tips
        if (normalized := _required_text(tip)) is not None
    ]
    if not tips or len(tips) != len(raw_tips):
        return None
    return {
        "step_key": step_key,
        "step_no": step_no,
        "title": title,
        "description": description,
        "tips": tips,
    }


def _normalize_material(raw_material: object) -> dict | None:
    if not isinstance(raw_material, dict):
        return None
    normalized = {}
    for field in MATERIAL_GUIDE_FIELDS:
        value = _required_text(raw_material.get(field))
        if value is None:
            return None
        normalized[field] = value
    return normalized


def _normalize_craft(raw_craft: object) -> dict:
    if not isinstance(raw_craft, dict):
        return _unavailable_craft()

    craft_key = _required_text(raw_craft.get("craft_key"))
    if craft_key not in EXPECTED_CRAFT_KEYS:
        return _unavailable_craft(craft_key)
    if raw_craft.get("source_available") is False:
        return _unavailable_craft(craft_key)

    name = _required_text(raw_craft.get("name"))
    introduction = _required_text(raw_craft.get("introduction"))
    sort_order = raw_craft.get("sort_order")
    raw_steps = raw_craft.get("steps")
    raw_materials = raw_craft.get("material_guide")
    if (
        name is None
        or introduction is None
        or not isinstance(sort_order, int)
        or isinstance(sort_order, bool)
        or sort_order <= 0
        or not isinstance(raw_steps, (list, tuple))
        or len(raw_steps) != REQUIRED_STEP_COUNT
        or not isinstance(raw_materials, (list, tuple))
        or not raw_materials
    ):
        return _unavailable_craft(craft_key)

    steps = []
    step_keys = set()
    for raw_step in raw_steps:
        step = _normalize_step(raw_step)
        if step is None or step["step_key"] in step_keys:
            return _unavailable_craft(craft_key)
        steps.append(step)
        step_keys.add(step["step_key"])
    if [step["step_no"] for step in steps] != list(
        range(1, REQUIRED_STEP_COUNT + 1)
    ):
        return _unavailable_craft(craft_key)

    materials = []
    for raw_material in raw_materials:
        material = _normalize_material(raw_material)
        if material is None:
            return _unavailable_craft(craft_key)
        materials.append(material)

    return {
        "craft_key": craft_key,
        "name": name,
        "sort_order": sort_order,
        "introduction": introduction,
        "is_demo": bool(raw_craft.get("is_demo", False)),
        "source_available": True,
        "status": "available",
        "available": True,
        "unavailable_reason": None,
        "steps": steps,
        "material_guide": materials,
    }


def list_crafts() -> list[dict]:
    try:
        raw_crafts = get_craft_preset_provider().list_crafts()
    except Exception:
        return [_unavailable_craft(craft_key) for craft_key in EXPECTED_CRAFT_KEYS]
    if not isinstance(raw_crafts, (list, tuple)):
        return [_unavailable_craft(craft_key) for craft_key in EXPECTED_CRAFT_KEYS]

    crafts_by_key = {}
    duplicate_keys = set()
    for raw_craft in raw_crafts:
        raw_key = (
            _required_text(raw_craft.get("craft_key"))
            if isinstance(raw_craft, dict)
            else None
        )
        if raw_key not in EXPECTED_CRAFT_KEYS:
            continue
        if raw_key in crafts_by_key or raw_key in duplicate_keys:
            duplicate_keys.add(raw_key)
            crafts_by_key.pop(raw_key, None)
            continue
        crafts_by_key[raw_key] = _normalize_craft(raw_craft)

    crafts = [
        _unavailable_craft(
            craft_key,
            reason=CRAFT_DUPLICATE_UNAVAILABLE,
        )
        if craft_key in duplicate_keys
        else crafts_by_key.get(craft_key, _unavailable_craft(craft_key))
        for craft_key in EXPECTED_CRAFT_KEYS
    ]
    crafts.sort(
        key=lambda craft: (
            craft["sort_order"] or CRAFT_SORT_ORDERS[craft["craft_key"]],
            craft["craft_key"],
        )
    )
    return deepcopy(crafts)


def get_craft(craft_key: str) -> dict:
    normalized_key = _required_text(craft_key)
    if normalized_key not in EXPECTED_CRAFT_KEYS:
        return _unavailable_craft(normalized_key)
    for craft in list_crafts():
        if craft["craft_key"] == normalized_key:
            return deepcopy(craft)
    return _unavailable_craft(normalized_key)


def get_material_guide(craft_key: str) -> dict:
    craft = get_craft(craft_key)
    return {
        "craft_key": craft["craft_key"],
        "name": craft["name"],
        "status": craft["status"],
        "available": craft["available"],
        "source_available": craft["source_available"],
        "unavailable_reason": craft["unavailable_reason"],
        "material_guide": deepcopy(craft["material_guide"]),
        "steps": [],
    }


def _require_positive_int(value: object, message: str) -> int:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or value <= 0
    ):
        raise AgriValidationError(message)
    return value


def _completed_steps(progress_row) -> list[int]:
    if progress_row is None:
        return []
    try:
        raw_steps = json.loads(progress_row["completed_steps_json"])
    except (TypeError, ValueError):
        return []
    if not isinstance(raw_steps, list):
        return []
    completed = []
    for expected, step_no in enumerate(raw_steps, start=1):
        if (
            not isinstance(step_no, int)
            or isinstance(step_no, bool)
            or step_no != expected
        ):
            break
        completed.append(step_no)
    return completed


def _serialize_progress(
    user_id: int,
    craft: dict,
    progress_row,
) -> dict:
    completed = _completed_steps(progress_row)
    completed_count = len(completed)
    is_completed = completed_count == REQUIRED_STEP_COUNT
    return {
        "user_id": user_id,
        "craft_key": craft["craft_key"],
        "status": craft["status"],
        "available": craft["available"],
        "unavailable_reason": craft["unavailable_reason"],
        "completed_steps": completed,
        "completed_step_count": completed_count,
        "resume_step_no": (
            None
            if not craft["available"] or is_completed
            else completed_count + 1
        ),
        "is_completed": is_completed,
        "updated_at": (
            str(progress_row["updated_at"]) if progress_row is not None else None
        ),
    }


def _progress_result(
    progress: dict,
    *,
    accepted: bool,
    status: str,
    reason: str | None,
    step_no: int,
) -> dict:
    return {
        **progress,
        "accepted": accepted,
        "status": status,
        "reason": reason,
        "step_no": step_no,
        "points_source_event_id": None,
        "points_event": None,
        "points_status": "not_enqueued",
    }


def _points_source_event_id(
    craft_key: str,
    step_no: int,
    event_id: str,
) -> str:
    return f"{craft_key}|{step_no}:{event_id.strip()}"


def get_craft_progress(user_id: int, craft_key: str) -> dict:
    user_id = _require_positive_int(user_id, "学员标识必须是正整数")
    craft = get_craft(craft_key)
    row = get_db().execute(
        """
        SELECT completed_steps_json, resume_step_no, updated_at
        FROM heritage_craft_progress
        WHERE user_id = ? AND craft_key = ?
        """,
        (user_id, craft["craft_key"]),
    ).fetchone()
    return _serialize_progress(user_id, craft, row)


def complete_craft_step(
    user_id: int,
    craft_key: str,
    step_no: int,
    active_seconds: int,
    event_id: str,
) -> dict:
    user_id = _require_positive_int(user_id, "学员标识必须是正整数")
    if (
        not isinstance(step_no, int)
        or isinstance(step_no, bool)
        or not 1 <= step_no <= REQUIRED_STEP_COUNT
    ):
        raise AgriValidationError("步骤编号必须是 1 到 6 的整数")
    if (
        not isinstance(active_seconds, int)
        or isinstance(active_seconds, bool)
        or active_seconds < 0
    ):
        raise AgriValidationError("学习时长必须是非负整数")
    if active_seconds > 7200:
        raise AgriValidationError("单次学习段不能超过 120 分钟")
    if not isinstance(event_id, str) or not event_id.strip():
        raise AgriValidationError("学习事件标识不能为空")

    craft = get_craft(craft_key)
    if not craft["available"]:
        return _progress_result(
            get_craft_progress(user_id, craft["craft_key"]),
            accepted=False,
            status="unavailable",
            reason=craft["unavailable_reason"],
            step_no=step_no,
        )

    now = utc_now_iso()
    with get_db() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute(
            """
            SELECT completed_steps_json, resume_step_no, updated_at
            FROM heritage_craft_progress
            WHERE user_id = ? AND craft_key = ?
            """,
            (user_id, craft["craft_key"]),
        ).fetchone()
        completed = _completed_steps(row)
        completed_count = len(completed)
        if step_no <= completed_count:
            progress = _serialize_progress(user_id, craft, row)
            return _progress_result(
                progress,
                accepted=False,
                status="already_completed",
                reason="步骤已完成",
                step_no=step_no,
            )
        expected_step_no = completed_count + 1
        if step_no != expected_step_no:
            progress = _serialize_progress(user_id, craft, row)
            return _progress_result(
                progress,
                accepted=False,
                status="out_of_order",
                reason=f"请先完成步骤 {expected_step_no}",
                step_no=step_no,
            )

        completed.append(step_no)
        resume_step_no = (
            None if len(completed) == REQUIRED_STEP_COUNT else len(completed) + 1
        )
        db.execute(
            """
            INSERT INTO heritage_craft_progress (
                user_id, craft_key, completed_steps_json,
                resume_step_no, updated_at
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT (user_id, craft_key) DO UPDATE SET
                completed_steps_json = excluded.completed_steps_json,
                resume_step_no = excluded.resume_step_no,
                updated_at = excluded.updated_at
            """,
            (
                user_id,
                craft["craft_key"],
                json.dumps(completed, separators=(",", ":")),
                resume_step_no,
                now,
            ),
        )
        updated_row = db.execute(
            """
            SELECT completed_steps_json, resume_step_no, updated_at
            FROM heritage_craft_progress
            WHERE user_id = ? AND craft_key = ?
            """,
            (user_id, craft["craft_key"]),
        ).fetchone()
        progress = _serialize_progress(user_id, craft, updated_row)
        result = _progress_result(
            progress,
            accepted=True,
            status="completed",
            reason=None,
            step_no=step_no,
        )

    source_event_id = _points_source_event_id(
        craft["craft_key"],
        step_no,
        event_id,
    )
    result["points_source_event_id"] = source_event_id
    try:
        points_event = record_duration_points(
            user_id,
            "handcraft",
            craft["craft_key"],
            active_seconds,
            now,
            f"{step_no}:{event_id.strip()}",
        )
        result["points_event"] = points_event
        result["points_status"] = points_event["status"]
        result["points_error"] = points_event.get("error")
    except Exception as error:
        result["points_status"] = "failed"
        result["points_error"] = str(error)
    return result
