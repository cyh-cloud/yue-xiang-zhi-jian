from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

from app.admin_console.audit import record_admin_audit
from app.admin_console.errors import (
    ProviderConflictError,
    ProviderNotFoundError,
    ProviderValidationError,
)
from app.admin_console.time_utils import platform_now_iso
from app.agri_skills.presets import PlaceholderPresetProvider
from app.db import get_db
from app.handcraft_inheritance.crafts import (
    CRAFT_SORT_ORDERS,
    EXPECTED_CRAFT_KEYS,
    MATERIAL_GUIDE_FIELDS,
    REQUIRED_STEP_COUNT,
)
from app.handcraft_inheritance.presets import PlaceholderCraftPresetProvider
from app.local_resources.cases import DatabaseLocalResourceCaseProvider


SHANGHAI = ZoneInfo("Asia/Shanghai")
STABLE_KEY_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
ASSISTANT_FEATURE_KEYS = (
    "agri_skills",
    "ai_companion",
    "course_catalog",
    "ecommerce_training",
    "handcraft_inheritance",
    "job_matching",
    "local_resources",
    "message_center",
    "points_mall",
    "student_profile",
)

CRAFT_COLUMNS = """
    craft_key, name, introduction, steps_json, material_guide_json,
    source_available, sort_order, is_demo, is_enabled, version,
    created_at, updated_at
"""
CASE_COLUMNS = """
    case_id, title, summary, background, journey, lessons, sort_order,
    published_at, updated_at, is_demo, is_enabled, version
"""
KNOWLEDGE_COLUMNS = """
    knowledge_id, title, body, feature_key, jump_target, is_enabled,
    sort_order, version, created_at, updated_at
"""


def _fetch_all(sql: str, parameters: tuple = ()) -> list[sqlite3.Row]:
    return get_db().execute(sql, parameters).fetchall()


def _fetch_one(sql: str, parameters: tuple = ()) -> sqlite3.Row | None:
    return get_db().execute(sql, parameters).fetchone()


def _required_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _parse_json_list(value: object) -> list:
    if isinstance(value, (list, tuple)):
        return list(value)
    if not isinstance(value, str) or not value.strip():
        return []
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return []
    return list(parsed) if isinstance(parsed, list) else []


def _json_fields(row: dict) -> dict:
    """Expand `*_json` text columns into their plain field names."""
    fields: dict = {}
    for key, value in row.items():
        if key.endswith("_json"):
            fields[key[: -len("_json")]] = _parse_json_list(value)
        else:
            fields[key] = value
    return fields


def _validation(
    message: str,
    *,
    code: str = "preset_validation_failed",
    **details,
) -> ProviderValidationError:
    return ProviderValidationError(message, code=code, details=details)


def _not_found(
    message: str,
    code: str,
    **details,
) -> ProviderNotFoundError:
    return ProviderNotFoundError(message, code=code, details=details)


def _begin(db: sqlite3.Connection) -> None:
    """Open the write transaction before any read that guards a write.

    `load_session` leaves a deferred transaction open on the request
    connection, and a deferred transaction holds no write lock, so it is
    committed away first. Without this the version SELECT below would run
    outside any write transaction and two admins could still both pass
    the optimistic check. The previous `with get_db() as db:` code
    committed that pending work on exit as well.
    """
    if db.in_transaction:
        db.commit()
    db.execute("BEGIN IMMEDIATE")


def _bounded_text(value: object, *, field: str, maximum: int) -> str:
    normalized = _required_text(value)
    if normalized is None:
        raise _validation(f"{field} 不能为空", field=field)
    if len(normalized) > maximum:
        raise _validation(
            f"{field} 长度不能超过 {maximum} 个字符",
            field=field,
            max_length=maximum,
        )
    return normalized


def _flag(value: object, *, field: str, default: bool) -> bool:
    if value is None:
        return default
    if not isinstance(value, bool):
        raise _validation(f"{field} 必须是布尔值", field=field)
    return value


def _integer(value: object, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise _validation(f"{field} 必须是整数", field=field)
    return value


def _optional_integer(value: object, *, field: str, default: int) -> int:
    if value is None:
        return default
    return _integer(value, field=field)


def _stable_key(value: object, *, field: str) -> str:
    normalized = _required_text(value)
    if normalized is None or STABLE_KEY_PATTERN.fullmatch(normalized) is None:
        raise _validation(f"{field} 格式不正确", field=field)
    return normalized


def _matching_stable_id(
    payload: dict,
    *,
    field: str,
    existing: sqlite3.Row,
) -> str:
    """Refuse a body-supplied stable ID that differs from the path."""
    current = str(existing[field])
    supplied = payload.get(field)
    if supplied is None:
        return current
    if _required_text(supplied) != current:
        raise _validation(
            f"{field} 与请求路径不一致，不可修改",
            code=f"{field}_mismatch",
            field=field,
            current=current,
        )
    return current


def _expected_version(value: object) -> int:
    version = _integer(value, field="expected_version")
    if version <= 0:
        raise _validation(
            "expected_version 必须是正整数",
            field="expected_version",
        )
    return version


def _optional_expected_version(value: object) -> int | None:
    """Read the optional optimistic-lock token used by the delete paths."""
    if value is None:
        return None
    if isinstance(value, str):
        normalized = value.strip()
        if not normalized:
            return None
        if not normalized.isdigit():
            raise _validation(
                "expected_version 必须是正整数",
                field="expected_version",
            )
        value = int(normalized)
    return _expected_version(value)


def _platform_timestamp(value: object, *, field: str) -> str:
    normalized = _required_text(value)
    if normalized is None:
        raise _validation(f"{field} 不能为空", field=field)
    try:
        parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except ValueError as error:
        raise _validation(
            f"{field} 必须是带时区的 ISO 8601 时间",
            field=field,
        ) from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise _validation(f"{field} 必须带时区", field=field)
    return parsed.astimezone(SHANGHAI).isoformat(timespec="seconds")


def _valid_step(raw_step: object) -> dict | None:
    """Apply the frozen 05 step completeness rule to one raw step."""
    if not isinstance(raw_step, dict):
        return None
    step_no = raw_step.get("step_no")
    step_key = _required_text(raw_step.get("step_key"))
    title = _required_text(raw_step.get("title"))
    description = _required_text(raw_step.get("description"))
    raw_tips = raw_step.get("tips")
    if (
        isinstance(step_no, bool)
        or not isinstance(step_no, int)
        or step_key is None
        or title is None
        or description is None
        or not isinstance(raw_tips, (list, tuple))
        or not raw_tips
    ):
        return None
    tips = []
    for raw_tip in raw_tips:
        normalized = _required_text(raw_tip)
        if normalized is None:
            return None
        tips.append(normalized)
    return {
        "step_key": step_key,
        "step_no": step_no,
        "title": title,
        "description": description,
        "tips": tips,
    }


def _valid_material(raw_material: object) -> bool:
    """Apply the frozen 05 material guide rule to one raw entry."""
    if not isinstance(raw_material, dict):
        return False
    return all(
        _required_text(raw_material.get(field)) is not None
        for field in MATERIAL_GUIDE_FIELDS
    )


def _craft_is_learnable(craft: dict) -> bool:
    """Mirror the frozen 05 `_normalize_craft` rule over the whole row.

    05 only reports `available`/`status = "available"` when the craft key is
    expected, the source is usable, the descriptive fields are non-empty,
    `sort_order` is a positive int, the steps are exactly six valid entries
    numbered 1..6 with unique keys, and `material_guide` is a non-empty list
    whose entries carry every `MATERIAL_GUIDE_FIELDS` value. Checking only the
    steps here is what let the console report `available: true` for a craft 05
    refuses to render, so the whole row has to be validated.
    """
    if not isinstance(craft, dict):
        return False
    if craft.get("craft_key") not in EXPECTED_CRAFT_KEYS:
        return False
    if craft.get("source_available") is False:
        return False
    if _required_text(craft.get("name")) is None:
        return False
    if _required_text(craft.get("introduction")) is None:
        return False
    sort_order = craft.get("sort_order")
    if (
        isinstance(sort_order, bool)
        or not isinstance(sort_order, int)
        or sort_order <= 0
    ):
        return False
    raw_steps = craft.get("steps")
    raw_materials = craft.get("material_guide")
    if (
        not isinstance(raw_steps, (list, tuple))
        or len(raw_steps) != REQUIRED_STEP_COUNT
        or not isinstance(raw_materials, (list, tuple))
        or not raw_materials
    ):
        return False
    normalized: list[dict] = []
    seen_keys: set[str] = set()
    for raw_step in raw_steps:
        step = _valid_step(raw_step)
        if step is None or step["step_key"] in seen_keys:
            return False
        seen_keys.add(step["step_key"])
        normalized.append(step)
    if [step["step_no"] for step in normalized] != list(
        range(1, REQUIRED_STEP_COUNT + 1)
    ):
        return False
    return all(_valid_material(material) for material in raw_materials)


def _validated_steps(value: object) -> list[dict]:
    if not isinstance(value, list):
        raise _validation("steps 必须是数组", field="steps")
    steps: list[dict] = []
    seen_numbers: set[int] = set()
    for index, raw_step in enumerate(value):
        if not isinstance(raw_step, dict):
            raise _validation(
                "steps 必须是对象数组",
                field="steps",
                index=index,
            )
        step_no = _integer(raw_step.get("step_no"), field="steps.step_no")
        if step_no <= 0:
            raise _validation(
                "steps.step_no 必须是正整数",
                field="steps.step_no",
                index=index,
            )
        if step_no in seen_numbers:
            raise _validation(
                "steps.step_no 不能重复",
                field="steps.step_no",
                index=index,
                step_no=step_no,
            )
        seen_numbers.add(step_no)
        raw_tips = raw_step.get("tips")
        if not isinstance(raw_tips, list):
            raise _validation(
                "steps.tips 必须是数组",
                field="steps.tips",
                index=index,
            )
        steps.append(
            {
                "step_key": _bounded_text(
                    raw_step.get("step_key"),
                    field="steps.step_key",
                    maximum=64,
                ),
                "step_no": step_no,
                "title": _bounded_text(
                    raw_step.get("title"),
                    field="steps.title",
                    maximum=60,
                ),
                "description": _bounded_text(
                    raw_step.get("description"),
                    field="steps.description",
                    maximum=1000,
                ),
                "tips": [
                    _bounded_text(tip, field="steps.tips", maximum=200)
                    for tip in raw_tips
                ],
            }
        )
    return steps


def _validated_material_guide(value: object) -> list[dict]:
    if not isinstance(value, list):
        raise _validation("material_guide 必须是数组", field="material_guide")
    materials: list[dict] = []
    for index, raw_material in enumerate(value):
        if not isinstance(raw_material, dict):
            raise _validation(
                "material_guide 必须是对象数组",
                field="material_guide",
                index=index,
            )
        materials.append(
            {
                field: _bounded_text(
                    raw_material.get(field),
                    field=f"material_guide.{field}",
                    maximum=200,
                )
                for field in MATERIAL_GUIDE_FIELDS
            }
        )
    return materials


def _serialize_craft(row: sqlite3.Row) -> dict:
    fields = _json_fields(dict(row))
    craft = {
        "craft_key": str(fields["craft_key"]),
        "name": str(fields["name"]),
        "introduction": str(fields["introduction"]),
        "steps": _parse_json_list(fields.get("steps")),
        "material_guide": _parse_json_list(fields.get("material_guide")),
        "is_demo": bool(fields["is_demo"]),
        "source_available": bool(fields["source_available"]),
        "available": False,
        "sort_order": int(fields["sort_order"]),
        "is_enabled": bool(fields["is_enabled"]),
        "version": int(fields["version"]),
        "created_at": str(fields["created_at"]),
        "updated_at": str(fields["updated_at"]),
    }
    # The learnability rule must see the normalized values, not the raw
    # SQLite integers, so it is evaluated on the serialized craft.
    craft["available"] = _craft_is_learnable(craft)
    return craft


def _serialize_case(row: sqlite3.Row) -> dict:
    """Mirror the frozen 06 `LocalResourceCaseProvider` read shape."""
    return {
        "id": str(row["case_id"]),
        "title": str(row["title"]),
        "summary": str(row["summary"]),
        "background": str(row["background"]),
        "journey": str(row["journey"]),
        "lessons": str(row["lessons"]),
        "published_at": str(row["published_at"]),
        "updated_at": str(row["updated_at"]),
        "is_demo": bool(row["is_demo"]),
    }


def _serialize_case_item(row: sqlite3.Row) -> dict:
    return {
        **_serialize_case(row),
        "sort_order": int(row["sort_order"]),
        "is_enabled": bool(row["is_enabled"]),
        "source_available": bool(row["is_enabled"]),
        "version": int(row["version"]),
    }


def _serialize_knowledge_entry(row: sqlite3.Row) -> dict:
    return {
        "knowledge_id": str(row["knowledge_id"]),
        "title": str(row["title"]),
        "body": str(row["body"]),
        "feature_key": str(row["feature_key"]),
        "jump_target": str(row["jump_target"]),
        "is_enabled": bool(row["is_enabled"]),
        "version": int(row["version"]),
        "updated_at": str(row["updated_at"]),
    }


def _serialize_knowledge_item(row: sqlite3.Row) -> dict:
    return {
        **_serialize_knowledge_entry(row),
        "sort_order": int(row["sort_order"]),
        "created_at": str(row["created_at"]),
    }


class DatabaseCraftPresetProvider(PlaceholderCraftPresetProvider):
    """Authoritative craft presets read from `admin_handcraft_crafts`.

    The `PlaceholderCraftPresetProvider` base class is retained only as a
    compatibility shim: the frozen `tests/test_handcraft_presets.py` asserts
    the installed provider `isinstance(provider,
    PlaceholderCraftPresetProvider)`. No placeholder content is ever served
    from here. `admin_handcraft_crafts` is the single authoritative source
    once 011 owns the slot, and `seed_craft_presets` turns the four 05 demo
    crafts into real manageable rows on first start, so an empty or fully
    disabled table means learners see no crafts at all instead of content
    the admin console cannot reach.
    """

    def _enabled_rows(self) -> list[sqlite3.Row]:
        return _fetch_all(
            f"""
            SELECT {CRAFT_COLUMNS}
            FROM admin_handcraft_crafts
            WHERE is_enabled = 1
            ORDER BY sort_order ASC, craft_key ASC
            """
        )

    def list_crafts(self) -> list[dict]:
        return [_serialize_craft(row) for row in self._enabled_rows()]

    def get_craft(self, craft_key: str) -> dict | None:
        row = _fetch_one(
            f"""
            SELECT {CRAFT_COLUMNS}
            FROM admin_handcraft_crafts
            WHERE craft_key = ?
            """,
            (craft_key,),
        )
        if row is None:
            return None
        if not row["is_enabled"]:
            return None
        return _serialize_craft(row)


class AdminDatabaseLocalResourceCaseProvider(DatabaseLocalResourceCaseProvider):
    """06 success case reads restricted to admin managed enabled cases.

    Extending the 06 database provider keeps the frozen consumer read shape
    and the registration slot intact; only the `is_enabled` filter is added.
    """

    def list_success_cases(self) -> list[dict]:
        rows = _fetch_all(
            """
            SELECT case_id, title, summary, background, journey, lessons,
                   published_at, updated_at, is_demo
            FROM local_resource_success_cases
            WHERE is_enabled = 1
            ORDER BY sort_order ASC, case_id ASC
            """
        )
        return [_serialize_case(row) for row in rows]

    def get_success_case(self, case_id: str) -> dict | None:
        row = _fetch_one(
            """
            SELECT case_id, title, summary, background, journey, lessons,
                   published_at, updated_at, is_demo
            FROM local_resource_success_cases
            WHERE case_id = ? AND is_enabled = 1
            """,
            (case_id,),
        )
        return _serialize_case(row) if row is not None else None


class DatabaseAssistantFeatureKnowledgeProvider:
    """AI companion feature knowledge read from the admin console table."""

    def list_entries(self, enabled_only: bool = True) -> list[dict]:
        where = "WHERE is_enabled = 1" if enabled_only else ""
        rows = _fetch_all(
            f"""
            SELECT knowledge_id, title, body, feature_key, jump_target,
                   is_enabled, version, updated_at
            FROM admin_assistant_feature_knowledge
            {where}
            ORDER BY sort_order ASC, knowledge_id ASC
            """
        )
        return [_serialize_knowledge_entry(row) for row in rows]


def _craft_payload(
    payload: dict,
    *,
    existing: sqlite3.Row | None = None,
) -> dict:
    if not isinstance(payload, dict):
        raise _validation("请求内容格式不正确", field="payload")
    if existing is None:
        craft_key = _stable_key(payload.get("craft_key"), field="craft_key")
        source_default = True
        enabled_default = True
    else:
        craft_key = _matching_stable_id(
            payload,
            field="craft_key",
            existing=existing,
        )
        source_default = bool(existing["source_available"])
        enabled_default = bool(existing["is_enabled"])
    return {
        "craft_key": craft_key,
        "name": _bounded_text(payload.get("name"), field="name", maximum=60),
        "introduction": _bounded_text(
            payload.get("introduction"),
            field="introduction",
            maximum=2000,
        ),
        "steps": _validated_steps(payload.get("steps")),
        "material_guide": _validated_material_guide(
            payload.get("material_guide")
        ),
        "source_available": _flag(
            payload.get("source_available"),
            field="source_available",
            default=source_default,
        ),
        "sort_order": _optional_integer(
            payload.get("sort_order"),
            field="sort_order",
            default=0,
        ),
        "is_enabled": _flag(
            payload.get("is_enabled"),
            field="is_enabled",
            default=enabled_default,
        ),
    }


def _case_payload(
    payload: dict,
    *,
    existing: sqlite3.Row | None = None,
) -> dict:
    if not isinstance(payload, dict):
        raise _validation("请求内容格式不正确", field="payload")
    if existing is None:
        case_id = _stable_key(payload.get("case_id"), field="case_id")
        published_at = payload.get("published_at")
        enabled_default = True
    else:
        case_id = _matching_stable_id(
            payload,
            field="case_id",
            existing=existing,
        )
        published_at = payload.get("published_at")
        if published_at is None:
            published_at = existing["published_at"]
        enabled_default = bool(existing["is_enabled"])
    return {
        "case_id": case_id,
        "title": _bounded_text(payload.get("title"), field="title", maximum=80),
        "summary": _bounded_text(
            payload.get("summary"),
            field="summary",
            maximum=200,
        ),
        "background": _bounded_text(
            payload.get("background"),
            field="background",
            maximum=1000,
        ),
        "journey": _bounded_text(
            payload.get("journey"),
            field="journey",
            maximum=1000,
        ),
        "lessons": _bounded_text(
            payload.get("lessons"),
            field="lessons",
            maximum=1000,
        ),
        "sort_order": _optional_integer(
            payload.get("sort_order"),
            field="sort_order",
            default=0,
        ),
        "published_at": _platform_timestamp(
            published_at,
            field="published_at",
        ),
        "is_enabled": _flag(
            payload.get("is_enabled"),
            field="is_enabled",
            default=enabled_default,
        ),
    }


def _knowledge_payload(
    payload: dict,
    *,
    existing: sqlite3.Row | None = None,
) -> dict:
    if not isinstance(payload, dict):
        raise _validation("请求内容格式不正确", field="payload")
    if existing is None:
        knowledge_id = _stable_key(
            payload.get("knowledge_id"),
            field="knowledge_id",
        )
        enabled_default = True
    else:
        knowledge_id = _matching_stable_id(
            payload,
            field="knowledge_id",
            existing=existing,
        )
        enabled_default = bool(existing["is_enabled"])

    feature_key = _required_text(payload.get("feature_key"))
    if feature_key is None and existing is not None:
        feature_key = str(existing["feature_key"])
    if feature_key not in ASSISTANT_FEATURE_KEYS:
        raise _validation(
            "feature_key 不在支持的功能范围内",
            field="feature_key",
            feature_key=feature_key,
            allowed=list(ASSISTANT_FEATURE_KEYS),
        )

    jump_target = _required_text(payload.get("jump_target"))
    if jump_target is None and existing is not None:
        jump_target = str(existing["jump_target"])
    jump_target = jump_target or ""
    if jump_target and (
        not jump_target.startswith("/")
        or jump_target.startswith("//")
        or len(jump_target) > 200
    ):
        raise _validation(
            "jump_target 必须是站内路径",
            field="jump_target",
        )

    return {
        "knowledge_id": knowledge_id,
        "title": _bounded_text(payload.get("title"), field="title", maximum=80),
        "body": _bounded_text(payload.get("body"), field="body", maximum=2000),
        "feature_key": feature_key,
        "jump_target": jump_target,
        "sort_order": _optional_integer(
            payload.get("sort_order"),
            field="sort_order",
            default=0,
        ),
        "is_enabled": _flag(
            payload.get("is_enabled"),
            field="is_enabled",
            default=enabled_default,
        ),
    }


def _craft_item(craft_key: str) -> dict:
    row = _fetch_one(
        f"""
        SELECT {CRAFT_COLUMNS}
        FROM admin_handcraft_crafts
        WHERE craft_key = ?
        """,
        (craft_key,),
    )
    if row is None:
        raise _not_found(
            "技艺内容不存在",
            "craft_preset_not_found",
            craft_key=craft_key,
        )
    return _serialize_craft(row)


def list_craft_presets() -> list[dict]:
    rows = _fetch_all(
        f"""
        SELECT {CRAFT_COLUMNS}
        FROM admin_handcraft_crafts
        ORDER BY sort_order ASC, craft_key ASC
        """
    )
    return [_serialize_craft(row) for row in rows]


def create_craft_preset(actor_id: int, payload: dict) -> dict:
    values = _craft_payload(payload)
    now = platform_now_iso()
    try:
        with get_db() as db:
            db.execute(
                """
                INSERT INTO admin_handcraft_crafts (
                    craft_key, name, introduction, steps_json,
                    material_guide_json, source_available, sort_order,
                    is_enabled, version, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                """,
                (
                    values["craft_key"],
                    values["name"],
                    values["introduction"],
                    json.dumps(values["steps"], ensure_ascii=False),
                    json.dumps(values["material_guide"], ensure_ascii=False),
                    int(values["source_available"]),
                    values["sort_order"],
                    int(values["is_enabled"]),
                    now,
                    now,
                ),
            )
            record_admin_audit(
                db,
                actor_id=actor_id,
                action="create_craft_preset",
                target_type="handcraft_craft",
                target_id=values["craft_key"],
                before=None,
                after={
                    "name": values["name"],
                    "is_enabled": values["is_enabled"],
                },
                result="success",
            )
    except sqlite3.IntegrityError as error:
        raise ProviderConflictError(
            "技艺键已存在",
            code="craft_preset_conflict",
            details={"craft_key": values["craft_key"]},
        ) from error
    return _craft_item(values["craft_key"])


def update_craft_preset(
    actor_id: int,
    craft_key: str,
    payload: dict,
) -> dict:
    key = _stable_key(craft_key, field="craft_key")
    expected_version = _expected_version(
        payload.get("expected_version") if isinstance(payload, dict) else None
    )
    db = get_db()
    _begin(db)
    try:
        row = db.execute(
            f"""
            SELECT {CRAFT_COLUMNS}
            FROM admin_handcraft_crafts
            WHERE craft_key = ?
            """,
            (key,),
        ).fetchone()
        if row is None:
            raise _not_found(
                "技艺内容不存在",
                "craft_preset_not_found",
                craft_key=key,
            )
        values = _craft_payload(payload, existing=row)
        current_version = int(row["version"])
        if current_version != expected_version:
            raise ProviderConflictError(
                "技艺内容已被其他管理员修改",
                code="craft_preset_version_conflict",
                details={
                    "craft_key": key,
                    "expected_version": expected_version,
                    "current_version": current_version,
                },
            )
        now = platform_now_iso()
        cursor = db.execute(
            """
            UPDATE admin_handcraft_crafts
            SET name = ?, introduction = ?, steps_json = ?,
                material_guide_json = ?, source_available = ?, sort_order = ?,
                is_enabled = ?, version = ?, updated_at = ?
            WHERE craft_key = ? AND version = ?
            """,
            (
                values["name"],
                values["introduction"],
                json.dumps(values["steps"], ensure_ascii=False),
                json.dumps(values["material_guide"], ensure_ascii=False),
                int(values["source_available"]),
                values["sort_order"],
                int(values["is_enabled"]),
                current_version + 1,
                now,
                key,
                current_version,
            ),
        )
        if cursor.rowcount != 1:
            raise ProviderConflictError(
                "技艺内容已被其他管理员修改",
                code="craft_preset_version_conflict",
                details={
                    "craft_key": key,
                    "expected_version": expected_version,
                    "current_version": current_version,
                },
            )
        record_admin_audit(
            db,
            actor_id=actor_id,
            action="update_craft_preset",
            target_type="handcraft_craft",
            target_id=key,
            before={"version": current_version, "name": row["name"]},
            after={"version": current_version + 1, "name": values["name"]},
            result="success",
        )
    except Exception:
        db.rollback()
        raise
    db.commit()
    return _craft_item(key)


def disable_craft_preset(
    actor_id: int,
    craft_key: str,
    expected_version: object = None,
) -> dict:
    key = _stable_key(craft_key, field="craft_key")
    locked_version = _optional_expected_version(expected_version)
    db = get_db()
    _begin(db)
    try:
        row = db.execute(
            f"""
            SELECT {CRAFT_COLUMNS}
            FROM admin_handcraft_crafts
            WHERE craft_key = ?
            """,
            (key,),
        ).fetchone()
        if row is None:
            raise _not_found(
                "技艺内容不存在",
                "craft_preset_not_found",
                craft_key=key,
            )
        if not row["is_enabled"]:
            db.commit()
            return _serialize_craft(row)
        current_version = int(row["version"])
        if locked_version is not None and current_version != locked_version:
            raise ProviderConflictError(
                "技艺内容已被其他管理员修改",
                code="craft_preset_version_conflict",
                details={
                    "craft_key": key,
                    "expected_version": locked_version,
                    "current_version": current_version,
                },
            )
        now = platform_now_iso()
        cursor = db.execute(
            """
            UPDATE admin_handcraft_crafts
            SET is_enabled = 0, version = version + 1, updated_at = ?
            WHERE craft_key = ? AND version = ?
            """,
            (now, key, current_version),
        )
        if cursor.rowcount != 1:
            raise ProviderConflictError(
                "技艺内容已被其他管理员修改",
                code="craft_preset_version_conflict",
                details={
                    "craft_key": key,
                    "expected_version": locked_version,
                    "current_version": current_version,
                },
            )
        record_admin_audit(
            db,
            actor_id=actor_id,
            action="disable_craft_preset",
            target_type="handcraft_craft",
            target_id=key,
            before={"is_enabled": True, "version": current_version},
            after={"is_enabled": False, "version": current_version + 1},
            result="success",
        )
    except Exception:
        db.rollback()
        raise
    db.commit()
    return _craft_item(key)


def _case_item(case_id: str) -> dict:
    row = _fetch_one(
        f"""
        SELECT {CASE_COLUMNS}
        FROM local_resource_success_cases
        WHERE case_id = ?
        """,
        (case_id,),
    )
    if row is None:
        raise _not_found(
            "成功案例不存在",
            "case_preset_not_found",
            case_id=case_id,
        )
    return _serialize_case_item(row)


def list_case_presets() -> list[dict]:
    rows = _fetch_all(
        f"""
        SELECT {CASE_COLUMNS}
        FROM local_resource_success_cases
        ORDER BY sort_order ASC, case_id ASC
        """
    )
    return [_serialize_case_item(row) for row in rows]


def create_case_preset(actor_id: int, payload: dict) -> dict:
    values = _case_payload(payload)
    now = platform_now_iso()
    try:
        with get_db() as db:
            db.execute(
                """
                INSERT INTO local_resource_success_cases (
                    case_id, title, summary, background, journey, lessons,
                    sort_order, published_at, updated_at, is_demo, is_enabled,
                    version
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, 1)
                """,
                (
                    values["case_id"],
                    values["title"],
                    values["summary"],
                    values["background"],
                    values["journey"],
                    values["lessons"],
                    values["sort_order"],
                    values["published_at"],
                    now,
                    int(values["is_enabled"]),
                ),
            )
            record_admin_audit(
                db,
                actor_id=actor_id,
                action="create_case_preset",
                target_type="success_case",
                target_id=values["case_id"],
                before=None,
                after={"title": values["title"]},
                result="success",
            )
    except sqlite3.IntegrityError as error:
        raise ProviderConflictError(
            "案例 ID 已存在",
            code="case_preset_conflict",
            details={"case_id": values["case_id"]},
        ) from error
    return _case_item(values["case_id"])


def update_case_preset(actor_id: int, case_id: str, payload: dict) -> dict:
    key = _stable_key(case_id, field="case_id")
    expected_version = _expected_version(
        payload.get("expected_version") if isinstance(payload, dict) else None
    )
    db = get_db()
    _begin(db)
    try:
        row = db.execute(
            f"""
            SELECT {CASE_COLUMNS}
            FROM local_resource_success_cases
            WHERE case_id = ?
            """,
            (key,),
        ).fetchone()
        if row is None:
            raise _not_found(
                "成功案例不存在",
                "case_preset_not_found",
                case_id=key,
            )
        if int(row["is_demo"]):
            raise _validation(
                "演示案例由平台种子维护，每次启动都会被还原；"
                "请新建案例后再编辑或停用",
                code="demo_case_not_editable",
                case_id=key,
            )
        values = _case_payload(payload, existing=row)
        current_version = int(row["version"])
        if current_version != expected_version:
            raise ProviderConflictError(
                "成功案例已被其他管理员修改",
                code="case_preset_version_conflict",
                details={
                    "case_id": key,
                    "expected_version": expected_version,
                    "current_version": current_version,
                },
            )
        now = platform_now_iso()
        cursor = db.execute(
            """
            UPDATE local_resource_success_cases
            SET title = ?, summary = ?, background = ?, journey = ?,
                lessons = ?, sort_order = ?, published_at = ?, updated_at = ?,
                is_enabled = ?, version = ?
            WHERE case_id = ? AND version = ?
            """,
            (
                values["title"],
                values["summary"],
                values["background"],
                values["journey"],
                values["lessons"],
                values["sort_order"],
                values["published_at"],
                now,
                int(values["is_enabled"]),
                current_version + 1,
                key,
                current_version,
            ),
        )
        if cursor.rowcount != 1:
            raise ProviderConflictError(
                "成功案例已被其他管理员修改",
                code="case_preset_version_conflict",
                details={
                    "case_id": key,
                    "expected_version": expected_version,
                    "current_version": current_version,
                },
            )
        record_admin_audit(
            db,
            actor_id=actor_id,
            action="update_case_preset",
            target_type="success_case",
            target_id=key,
            before={"version": current_version, "title": row["title"]},
            after={"version": current_version + 1, "title": values["title"]},
            result="success",
        )
    except Exception:
        db.rollback()
        raise
    db.commit()
    return _case_item(key)


def disable_case_preset(
    actor_id: int,
    case_id: str,
    expected_version: object = None,
) -> dict:
    key = _stable_key(case_id, field="case_id")
    locked_version = _optional_expected_version(expected_version)
    db = get_db()
    _begin(db)
    try:
        row = db.execute(
            f"""
            SELECT {CASE_COLUMNS}
            FROM local_resource_success_cases
            WHERE case_id = ?
            """,
            (key,),
        ).fetchone()
        if row is None:
            raise _not_found(
                "成功案例不存在",
                "case_preset_not_found",
                case_id=key,
            )
        if int(row["is_demo"]):
            raise _validation(
                "演示案例由平台种子维护，每次启动都会被还原；"
                "请新建案例后再编辑或停用",
                code="demo_case_not_editable",
                case_id=key,
            )
        if not row["is_enabled"]:
            db.commit()
            return _serialize_case_item(row)
        current_version = int(row["version"])
        if locked_version is not None and current_version != locked_version:
            raise ProviderConflictError(
                "成功案例已被其他管理员修改",
                code="case_preset_version_conflict",
                details={
                    "case_id": key,
                    "expected_version": locked_version,
                    "current_version": current_version,
                },
            )
        now = platform_now_iso()
        cursor = db.execute(
            """
            UPDATE local_resource_success_cases
            SET is_enabled = 0, version = version + 1, updated_at = ?
            WHERE case_id = ? AND version = ?
            """,
            (now, key, current_version),
        )
        if cursor.rowcount != 1:
            raise ProviderConflictError(
                "成功案例已被其他管理员修改",
                code="case_preset_version_conflict",
                details={
                    "case_id": key,
                    "expected_version": locked_version,
                    "current_version": current_version,
                },
            )
        record_admin_audit(
            db,
            actor_id=actor_id,
            action="disable_case_preset",
            target_type="success_case",
            target_id=key,
            before={"is_enabled": True, "version": current_version},
            after={"is_enabled": False, "version": current_version + 1},
            result="success",
        )
    except Exception:
        db.rollback()
        raise
    db.commit()
    return _case_item(key)


def _knowledge_item(knowledge_id: str) -> dict:
    row = _fetch_one(
        f"""
        SELECT {KNOWLEDGE_COLUMNS}
        FROM admin_assistant_feature_knowledge
        WHERE knowledge_id = ?
        """,
        (knowledge_id,),
    )
    if row is None:
        raise _not_found(
            "知识条目不存在",
            "knowledge_preset_not_found",
            knowledge_id=knowledge_id,
        )
    return _serialize_knowledge_item(row)


def list_knowledge_presets() -> list[dict]:
    rows = _fetch_all(
        f"""
        SELECT {KNOWLEDGE_COLUMNS}
        FROM admin_assistant_feature_knowledge
        ORDER BY sort_order ASC, knowledge_id ASC
        """
    )
    return [_serialize_knowledge_item(row) for row in rows]


def create_knowledge_preset(actor_id: int, payload: dict) -> dict:
    values = _knowledge_payload(payload)
    now = platform_now_iso()
    try:
        with get_db() as db:
            db.execute(
                """
                INSERT INTO admin_assistant_feature_knowledge (
                    knowledge_id, title, body, feature_key, jump_target,
                    is_enabled, sort_order, version, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                """,
                (
                    values["knowledge_id"],
                    values["title"],
                    values["body"],
                    values["feature_key"],
                    values["jump_target"],
                    int(values["is_enabled"]),
                    values["sort_order"],
                    now,
                    now,
                ),
            )
            record_admin_audit(
                db,
                actor_id=actor_id,
                action="create_knowledge_preset",
                target_type="assistant_knowledge",
                target_id=values["knowledge_id"],
                before=None,
                after={"title": values["title"]},
                result="success",
            )
    except sqlite3.IntegrityError as error:
        raise ProviderConflictError(
            "知识条目 ID 已存在",
            code="knowledge_preset_conflict",
            details={"knowledge_id": values["knowledge_id"]},
        ) from error
    return _knowledge_item(values["knowledge_id"])


def update_knowledge_preset(
    actor_id: int,
    knowledge_id: str,
    payload: dict,
) -> dict:
    key = _stable_key(knowledge_id, field="knowledge_id")
    expected_version = _expected_version(
        payload.get("expected_version") if isinstance(payload, dict) else None
    )
    db = get_db()
    _begin(db)
    try:
        row = db.execute(
            f"""
            SELECT {KNOWLEDGE_COLUMNS}
            FROM admin_assistant_feature_knowledge
            WHERE knowledge_id = ?
            """,
            (key,),
        ).fetchone()
        if row is None:
            raise _not_found(
                "知识条目不存在",
                "knowledge_preset_not_found",
                knowledge_id=key,
            )
        values = _knowledge_payload(payload, existing=row)
        current_version = int(row["version"])
        if current_version != expected_version:
            raise ProviderConflictError(
                "知识条目已被其他管理员修改",
                code="knowledge_preset_version_conflict",
                details={
                    "knowledge_id": key,
                    "expected_version": expected_version,
                    "current_version": current_version,
                },
            )
        now = platform_now_iso()
        cursor = db.execute(
            """
            UPDATE admin_assistant_feature_knowledge
            SET title = ?, body = ?, feature_key = ?, jump_target = ?,
                is_enabled = ?, sort_order = ?, version = ?, updated_at = ?
            WHERE knowledge_id = ? AND version = ?
            """,
            (
                values["title"],
                values["body"],
                values["feature_key"],
                values["jump_target"],
                int(values["is_enabled"]),
                values["sort_order"],
                current_version + 1,
                now,
                key,
                current_version,
            ),
        )
        if cursor.rowcount != 1:
            raise ProviderConflictError(
                "知识条目已被其他管理员修改",
                code="knowledge_preset_version_conflict",
                details={
                    "knowledge_id": key,
                    "expected_version": expected_version,
                    "current_version": current_version,
                },
            )
        record_admin_audit(
            db,
            actor_id=actor_id,
            action="update_knowledge_preset",
            target_type="assistant_knowledge",
            target_id=key,
            before={"version": current_version, "title": row["title"]},
            after={"version": current_version + 1, "title": values["title"]},
            result="success",
        )
    except Exception:
        db.rollback()
        raise
    db.commit()
    return _knowledge_item(key)


def disable_knowledge_preset(
    actor_id: int,
    knowledge_id: str,
    expected_version: object = None,
) -> dict:
    key = _stable_key(knowledge_id, field="knowledge_id")
    locked_version = _optional_expected_version(expected_version)
    db = get_db()
    _begin(db)
    try:
        row = db.execute(
            f"""
            SELECT {KNOWLEDGE_COLUMNS}
            FROM admin_assistant_feature_knowledge
            WHERE knowledge_id = ?
            """,
            (key,),
        ).fetchone()
        if row is None:
            raise _not_found(
                "知识条目不存在",
                "knowledge_preset_not_found",
                knowledge_id=key,
            )
        if not row["is_enabled"]:
            db.commit()
            return _serialize_knowledge_item(row)
        current_version = int(row["version"])
        if locked_version is not None and current_version != locked_version:
            raise ProviderConflictError(
                "知识条目已被其他管理员修改",
                code="knowledge_preset_version_conflict",
                details={
                    "knowledge_id": key,
                    "expected_version": locked_version,
                    "current_version": current_version,
                },
            )
        now = platform_now_iso()
        cursor = db.execute(
            """
            UPDATE admin_assistant_feature_knowledge
            SET is_enabled = 0, version = version + 1, updated_at = ?
            WHERE knowledge_id = ? AND version = ?
            """,
            (now, key, current_version),
        )
        if cursor.rowcount != 1:
            raise ProviderConflictError(
                "知识条目已被其他管理员修改",
                code="knowledge_preset_version_conflict",
                details={
                    "knowledge_id": key,
                    "expected_version": locked_version,
                    "current_version": current_version,
                },
            )
        record_admin_audit(
            db,
            actor_id=actor_id,
            action="disable_knowledge_preset",
            target_type="assistant_knowledge",
            target_id=key,
            before={"is_enabled": True, "version": current_version},
            after={"is_enabled": False, "version": current_version + 1},
            result="success",
        )
    except Exception:
        db.rollback()
        raise
    db.commit()
    return _knowledge_item(key)


ASSISTANT_KNOWLEDGE_SEED = (
    {
        "knowledge_id": "knowledge-job-application",
        "title": "如何投递简历",
        "body": (
            "进入就业对接的职位列表，打开职位详情并确认岗位要求后，"
            "使用当前简历和技能档案完成投递；投递记录可在我的投递中查看。"
        ),
        "feature_key": "job_matching",
        "jump_target": "/student/employment/jobs",
        "sort_order": 10,
    },
    {
        "knowledge_id": "knowledge-resume-profile",
        "title": "如何维护简历与技能档案",
        "body": (
            "在就业对接中打开简历编辑和技能档案，补充教育经历、"
            "工作经历与技能标签后保存，投递时随简历一起提交。"
        ),
        "feature_key": "job_matching",
        "jump_target": "/student/employment/resume",
        "sort_order": 20,
    },
    {
        "knowledge_id": "knowledge-points-mall",
        "title": "如何兑换积分奖品",
        "body": (
            "在非遗传承的积分商城选择奖品并确认积分成本后兑换，"
            "库存不足时无法兑换；兑换记录和履约进度可在积分页面查看。"
        ),
        "feature_key": "points_mall",
        "jump_target": "/student/handcraft-inheritance/rewards",
        "sort_order": 30,
    },
    {
        "knowledge_id": "knowledge-points-rules",
        "title": "积分如何获得与查看",
        "body": (
            "完成课程学习、非遗技艺步骤和训练任务会按平台积分规则获得积分，"
            "积分明细和到期情况在积分页面查看。"
        ),
        "feature_key": "points_mall",
        "jump_target": "/student/handcraft-inheritance/points",
        "sort_order": 40,
    },
    {
        "knowledge_id": "knowledge-agri-calendar",
        "title": "如何查看农事日历",
        "body": (
            "在农业技能中按产品查看当月农事任务、管理要点、"
            "节气和当月提示，用于安排种植和养殖节奏。"
        ),
        "feature_key": "agri_skills",
        "jump_target": "/student/agri-skills/calendar",
        "sort_order": 50,
    },
    {
        "knowledge_id": "knowledge-agri-diagnosis",
        "title": "如何提交病虫害诊断",
        "body": (
            "在农业技能的病虫害诊断中选择产品、描述症状并提交，"
            "系统按病虫害知识库给出防治建议，诊断历史可随时回看。"
        ),
        "feature_key": "agri_skills",
        "jump_target": "/student/agri-skills/diagnosis",
        "sort_order": 60,
    },
    {
        "knowledge_id": "knowledge-policy-subscription",
        "title": "如何订阅政策推送",
        "body": (
            "在本土资源的政策浏览中按分类订阅感兴趣的政策，"
            "有新政策发布时会通过消息中心收到通知。"
        ),
        "feature_key": "local_resources",
        "jump_target": "/student/local-resources/policies",
        "sort_order": 70,
    },
    {
        "knowledge_id": "knowledge-local-resources-cases",
        "title": "如何查看本土成功案例",
        "body": (
            "在本土资源的成功案例中查看背景、历程和经验启示，"
            "用于参考本地产业协作与品牌化做法。"
        ),
        "feature_key": "local_resources",
        "jump_target": "/student/local-resources/cases",
        "sort_order": 80,
    },
    {
        "knowledge_id": "knowledge-craft-learning",
        "title": "如何学习非遗技艺步骤",
        "body": (
            "在非遗传承中选择技艺，按步骤顺序学习并完成每一步，"
            "材料指南中列出参考价格、采购渠道和注意事项。"
        ),
        "feature_key": "handcraft_inheritance",
        "jump_target": "/student/handcraft-inheritance",
        "sort_order": 90,
    },
    {
        "knowledge_id": "knowledge-message-center",
        "title": "如何查看系统通知与私信",
        "body": (
            "审核结果、密码重置、履约发放等活动通知统一进入消息中心，"
            "可在消息中心查看未读和历史消息。"
        ),
        "feature_key": "message_center",
        "jump_target": "/messages",
        "sort_order": 100,
    },
    {
        "knowledge_id": "knowledge-ai-companion",
        "title": "AI 学伴可以回答哪些问题",
        "body": (
            "AI 学伴用于平台使用答疑和学习问题引导，不代替业务操作；"
            "涉及投递、兑换、审核等代办请求会被拒绝并提示对应入口。"
        ),
        "feature_key": "ai_companion",
        "jump_target": "",
        "sort_order": 110,
    },
)


def seed_assistant_feature_knowledge(connection) -> None:
    """Seed baseline feature knowledge without overwriting managed edits."""
    now = platform_now_iso()
    connection.executemany(
        """
        INSERT INTO admin_assistant_feature_knowledge (
            knowledge_id, title, body, feature_key, jump_target,
            is_enabled, sort_order, version, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, 1, ?, 1, ?, ?)
        ON CONFLICT(knowledge_id) DO NOTHING
        """,
        tuple(
            (
                entry["knowledge_id"],
                entry["title"],
                entry["body"],
                entry["feature_key"],
                entry["jump_target"],
                entry["sort_order"],
                now,
                now,
            )
            for entry in ASSISTANT_KNOWLEDGE_SEED
        ),
    )


def seed_craft_presets(connection) -> None:
    """Seed the 05 demo crafts as real, manageable admin rows.

    The content is read from 05's `PlaceholderCraftPresetProvider`, which stays
    the single source of truth for the demo text. `ON CONFLICT(craft_key) DO
    NOTHING` keeps admin edits and logical deletes across restarts, so the
    seed only fills an empty slot instead of overwriting the console.
    """
    now = platform_now_iso()
    rows = []
    for craft in PlaceholderCraftPresetProvider().list_crafts():
        craft_key = str(craft["craft_key"])
        sort_order = craft.get("sort_order")
        if (
            isinstance(sort_order, bool)
            or not isinstance(sort_order, int)
            or sort_order <= 0
        ):
            sort_order = CRAFT_SORT_ORDERS.get(craft_key, 0)
        rows.append(
            (
                craft_key,
                str(craft["name"]),
                str(craft["introduction"]),
                json.dumps(
                    [dict(step) for step in craft["steps"]],
                    ensure_ascii=False,
                ),
                json.dumps(
                    [dict(material) for material in craft["material_guide"]],
                    ensure_ascii=False,
                ),
                int(bool(craft.get("source_available", True))),
                int(sort_order),
                now,
                now,
            )
        )
    connection.executemany(
        """
        INSERT INTO admin_handcraft_crafts (
            craft_key, name, introduction, steps_json, material_guide_json,
            source_available, sort_order, is_demo, is_enabled, version,
            created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, 1, 1, 1, ?, ?)
        ON CONFLICT(craft_key) DO NOTHING
        """,
        rows,
    )


AGRI_PRODUCT_COLUMNS = """
    product_key, name, sort_order, is_enabled, version, created_at, updated_at
"""
AGRI_CALENDAR_COLUMNS = """
    item_id, product_key, month, tasks_json, management_json,
    solar_terms_json, reminder, sort_order, is_enabled, version,
    created_at, updated_at
"""
AGRI_PEST_COLUMNS = """
    item_id, sort_order, pest_name, product_names_json, symptoms_json,
    aliases_json, answer, is_enabled, version, created_at, updated_at
"""
AGRI_TEXT_LIST_LIMIT = 30
AGRI_TEXT_ITEM_MAXIMUM = 100


def _serialize_agri_product(row: sqlite3.Row) -> dict:
    """Mirror the frozen 03 product read shape (`key`, `name`, `sort_order`)."""
    return {
        "key": str(row["key"]),
        "name": str(row["name"]),
        "sort_order": int(row["sort_order"]),
    }


def _serialize_agri_product_item(row: sqlite3.Row) -> dict:
    return {
        "product_key": str(row["product_key"]),
        "name": str(row["name"]),
        "sort_order": int(row["sort_order"]),
        "is_enabled": bool(row["is_enabled"]),
        "version": int(row["version"]),
        "created_at": str(row["created_at"]),
        "updated_at": str(row["updated_at"]),
    }


def _serialize_agri_calendar_entry(row: sqlite3.Row) -> dict:
    """Mirror the frozen 03 `list_calendar_entries` read shape."""
    fields = _json_fields(dict(row))
    return {
        "month": int(fields["month"]),
        "tasks": list(fields["tasks"]),
        "management": list(fields["management"]),
        "solar_terms": list(fields["solar_terms"]),
        "reminder": str(fields["reminder"]),
    }


def _serialize_agri_calendar_item(row: sqlite3.Row) -> dict:
    fields = _json_fields(dict(row))
    return {
        "item_id": str(fields["item_id"]),
        "product_key": str(fields["product_key"]),
        "month": int(fields["month"]),
        "tasks": list(fields["tasks"]),
        "management": list(fields["management"]),
        "solar_terms": list(fields["solar_terms"]),
        "reminder": str(fields["reminder"]),
        "sort_order": int(fields["sort_order"]),
        "is_enabled": bool(fields["is_enabled"]),
        "version": int(fields["version"]),
        "created_at": str(fields["created_at"]),
        "updated_at": str(fields["updated_at"]),
    }


def _serialize_agri_pest_entry(row: sqlite3.Row) -> dict:
    """Mirror the frozen 03 `list_pest_entries` read shape."""
    fields = _json_fields(dict(row))
    return {
        "id": str(fields["id"]),
        "sort_order": int(fields["sort_order"]),
        "pest_name": str(fields["pest_name"]),
        "product_names": list(fields["product_names"]),
        "symptoms": list(fields["symptoms"]),
        "aliases": list(fields["aliases"]),
        "answer": str(fields["answer"]),
    }


def _serialize_agri_pest_item(row: sqlite3.Row) -> dict:
    fields = _json_fields(dict(row))
    return {
        "item_id": str(fields["item_id"]),
        "sort_order": int(fields["sort_order"]),
        "pest_name": str(fields["pest_name"]),
        "product_names": list(fields["product_names"]),
        "symptoms": list(fields["symptoms"]),
        "aliases": list(fields["aliases"]),
        "answer": str(fields["answer"]),
        "is_enabled": bool(fields["is_enabled"]),
        "version": int(fields["version"]),
        "created_at": str(fields["created_at"]),
        "updated_at": str(fields["updated_at"]),
    }


class DatabaseAgriPresetContentProvider:
    """03 preset content read from the 011 admin tables.

    Implements the frozen `PresetContentProvider` protocol field for field:
    reads are restricted to `is_enabled = 1` rows and every returned shape
    matches `PlaceholderPresetProvider`, so 03's calendar, diagnosis and
    offline Q&A consumers keep working unchanged once this provider owns
    the `agri_preset_provider` slot. `admin_agri_products`,
    `admin_agri_calendar` and `admin_pest_knowledge` are the single
    authoritative source, and `seed_agri_preset_content` turns 03's
    placeholder text into real manageable rows on first start.
    """

    def list_products(self) -> list[dict]:
        rows = _fetch_all(
            """
            SELECT product_key AS key, name, sort_order
            FROM admin_agri_products
            WHERE is_enabled = 1
            ORDER BY sort_order ASC, product_key ASC
            """
        )
        return [_serialize_agri_product(row) for row in rows]

    def get_product(self, product_key: str) -> dict | None:
        row = _fetch_one(
            """
            SELECT product_key AS key, name, sort_order
            FROM admin_agri_products
            WHERE product_key = ? AND is_enabled = 1
            """,
            (product_key,),
        )
        return _serialize_agri_product(row) if row is not None else None

    def get_calendar_entry(self, product_key: str, month: int) -> dict | None:
        row = _fetch_one(
            f"""
            SELECT {AGRI_CALENDAR_COLUMNS}
            FROM admin_agri_calendar
            WHERE product_key = ? AND month = ? AND is_enabled = 1
            """,
            (product_key, month),
        )
        if row is None:
            return None
        # `get_calendar_entry` mirrors the placeholder exactly: the four
        # content fields without `month`, because 03's `get_calendar`
        # supplies the requested month itself when it merges the entry.
        fields = _json_fields(dict(row))
        return {
            "tasks": list(fields["tasks"]),
            "management": list(fields["management"]),
            "solar_terms": list(fields["solar_terms"]),
            "reminder": str(fields["reminder"]),
        }

    def list_calendar_entries(self, product_key: str) -> list[dict]:
        rows = _fetch_all(
            f"""
            SELECT {AGRI_CALENDAR_COLUMNS}
            FROM admin_agri_calendar
            WHERE product_key = ? AND is_enabled = 1
            ORDER BY sort_order ASC, month ASC
            """,
            (product_key,),
        )
        return [_serialize_agri_calendar_entry(row) for row in rows]

    def list_pest_entries(self) -> list[dict]:
        rows = _fetch_all(
            """
            SELECT item_id AS id, sort_order, pest_name, product_names_json,
                   symptoms_json, aliases_json, answer
            FROM admin_pest_knowledge
            WHERE is_enabled = 1
            ORDER BY sort_order ASC, item_id ASC
            """
        )
        return [_serialize_agri_pest_entry(row) for row in rows]


def _valid_month(value: object) -> int:
    month = _integer(value, field="month")
    if not 1 <= month <= 12:
        raise _validation(
            "month 必须在 1 到 12 之间",
            field="month",
            month=month,
        )
    return month


def _validated_text_list(
    value: object,
    *,
    field: str,
    maximum: int = AGRI_TEXT_ITEM_MAXIMUM,
    limit: int = AGRI_TEXT_LIST_LIMIT,
) -> list[str]:
    if not isinstance(value, list):
        raise _validation(f"{field} 必须是数组", field=field)
    if len(value) > limit:
        raise _validation(
            f"{field} 最多 {limit} 项",
            field=field,
            max_items=limit,
        )
    items: list[str] = []
    for index, raw_item in enumerate(value):
        normalized = _required_text(raw_item)
        if normalized is None:
            raise _validation(
                f"{field} 不能包含空值",
                field=field,
                index=index,
            )
        if len(normalized) > maximum:
            raise _validation(
                f"{field} 单项目长度不能超过 {maximum} 个字符",
                field=field,
                index=index,
                max_length=maximum,
            )
        items.append(normalized)
    return items


def _agri_calendar_item_id(product_key: str, month: int) -> str:
    """Stable calendar ID, e.g. `calendar-litchi-4` for litchi in April."""
    return f"calendar-{product_key}-{month}"


def _agri_product_payload(
    payload: dict,
    *,
    existing: sqlite3.Row | None = None,
) -> dict:
    if not isinstance(payload, dict):
        raise _validation("请求内容格式不正确", field="payload")
    if existing is None:
        product_key = _stable_key(
            payload.get("product_key"),
            field="product_key",
        )
        enabled_default = True
    else:
        product_key = _matching_stable_id(
            payload,
            field="product_key",
            existing=existing,
        )
        enabled_default = bool(existing["is_enabled"])
    return {
        "product_key": product_key,
        "name": _bounded_text(payload.get("name"), field="name", maximum=60),
        "sort_order": _optional_integer(
            payload.get("sort_order"),
            field="sort_order",
            default=0,
        ),
        "is_enabled": _flag(
            payload.get("is_enabled"),
            field="is_enabled",
            default=enabled_default,
        ),
    }


def _agri_calendar_payload(
    payload: dict,
    *,
    existing: sqlite3.Row | None = None,
) -> dict:
    if not isinstance(payload, dict):
        raise _validation("请求内容格式不正确", field="payload")
    if existing is None:
        product_key = _stable_key(
            payload.get("product_key"),
            field="product_key",
        )
        month = _valid_month(payload.get("month"))
        enabled_default = True
        sort_order = _optional_integer(
            payload.get("sort_order"),
            field="sort_order",
            default=month,
        )
    else:
        product_key = _matching_stable_id(
            payload,
            field="product_key",
            existing=existing,
        )
        month = int(existing["month"])
        raw_month = payload.get("month")
        if raw_month is not None and _valid_month(raw_month) != month:
            # `product_key` and `month` form the stable `item_id`, so a PUT
            # may not move an entry to another month: that is a new entry
            # under a new stable ID, and this row keeps the old one.
            raise _validation(
                "month 与既有农时条目不一致，不可修改",
                code="month_mismatch",
                field="month",
                current=month,
            )
        enabled_default = bool(existing["is_enabled"])
        sort_order = _optional_integer(
            payload.get("sort_order"),
            field="sort_order",
            default=int(existing["sort_order"]),
        )
    return {
        "item_id": _agri_calendar_item_id(product_key, month),
        "product_key": product_key,
        "month": month,
        "tasks": _validated_text_list(payload.get("tasks"), field="tasks"),
        "management": _validated_text_list(
            payload.get("management"),
            field="management",
        ),
        "solar_terms": _validated_text_list(
            payload.get("solar_terms"),
            field="solar_terms",
        ),
        "reminder": _bounded_text(
            payload.get("reminder"),
            field="reminder",
            maximum=200,
        ),
        "sort_order": sort_order,
        "is_enabled": _flag(
            payload.get("is_enabled"),
            field="is_enabled",
            default=enabled_default,
        ),
    }


def _agri_pest_payload(
    payload: dict,
    *,
    existing: sqlite3.Row | None = None,
) -> dict:
    if not isinstance(payload, dict):
        raise _validation("请求内容格式不正确", field="payload")
    if existing is None:
        item_id = _stable_key(payload.get("item_id"), field="item_id")
        enabled_default = True
        sort_order = _optional_integer(
            payload.get("sort_order"),
            field="sort_order",
            default=0,
        )
    else:
        item_id = _matching_stable_id(
            payload,
            field="item_id",
            existing=existing,
        )
        enabled_default = bool(existing["is_enabled"])
        sort_order = _optional_integer(
            payload.get("sort_order"),
            field="sort_order",
            default=int(existing["sort_order"]),
        )
    return {
        "item_id": item_id,
        "sort_order": sort_order,
        "pest_name": _bounded_text(
            payload.get("pest_name"),
            field="pest_name",
            maximum=60,
        ),
        "product_names": _validated_text_list(
            payload.get("product_names"),
            field="product_names",
        ),
        "symptoms": _validated_text_list(
            payload.get("symptoms"),
            field="symptoms",
        ),
        "aliases": _validated_text_list(
            payload.get("aliases"),
            field="aliases",
        ),
        "answer": _bounded_text(
            payload.get("answer"),
            field="answer",
            maximum=2000,
        ),
        "is_enabled": _flag(
            payload.get("is_enabled"),
            field="is_enabled",
            default=enabled_default,
        ),
    }


def _agri_product_item(product_key: str) -> dict:
    row = _fetch_one(
        f"""
        SELECT {AGRI_PRODUCT_COLUMNS}
        FROM admin_agri_products
        WHERE product_key = ?
        """,
        (product_key,),
    )
    if row is None:
        raise _not_found(
            "农产品不存在",
            "agri_product_preset_not_found",
            product_key=product_key,
        )
    return _serialize_agri_product_item(row)


def list_agri_product_presets() -> list[dict]:
    rows = _fetch_all(
        f"""
        SELECT {AGRI_PRODUCT_COLUMNS}
        FROM admin_agri_products
        ORDER BY sort_order ASC, product_key ASC
        """
    )
    return [_serialize_agri_product_item(row) for row in rows]


def create_agri_product_preset(actor_id: int, payload: dict) -> dict:
    values = _agri_product_payload(payload)
    now = platform_now_iso()
    try:
        with get_db() as db:
            db.execute(
                """
                INSERT INTO admin_agri_products (
                    product_key, name, sort_order, is_enabled, version,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, 1, ?, ?)
                """,
                (
                    values["product_key"],
                    values["name"],
                    values["sort_order"],
                    int(values["is_enabled"]),
                    now,
                    now,
                ),
            )
            record_admin_audit(
                db,
                actor_id=actor_id,
                action="create_agri_product_preset",
                target_type="agri_product",
                target_id=values["product_key"],
                before=None,
                after={
                    "name": values["name"],
                    "is_enabled": values["is_enabled"],
                },
                result="success",
            )
    except sqlite3.IntegrityError as error:
        raise ProviderConflictError(
            "农产品键已存在",
            code="agri_product_preset_conflict",
            details={"product_key": values["product_key"]},
        ) from error
    return _agri_product_item(values["product_key"])


def update_agri_product_preset(
    actor_id: int,
    product_key: str,
    payload: dict,
) -> dict:
    key = _stable_key(product_key, field="product_key")
    expected_version = _expected_version(
        payload.get("expected_version") if isinstance(payload, dict) else None
    )
    db = get_db()
    _begin(db)
    try:
        row = db.execute(
            f"""
            SELECT {AGRI_PRODUCT_COLUMNS}
            FROM admin_agri_products
            WHERE product_key = ?
            """,
            (key,),
        ).fetchone()
        if row is None:
            raise _not_found(
                "农产品不存在",
                "agri_product_preset_not_found",
                product_key=key,
            )
        values = _agri_product_payload(payload, existing=row)
        current_version = int(row["version"])
        if current_version != expected_version:
            raise ProviderConflictError(
                "农产品已被其他管理员修改",
                code="agri_product_preset_version_conflict",
                details={
                    "product_key": key,
                    "expected_version": expected_version,
                    "current_version": current_version,
                },
            )
        now = platform_now_iso()
        cursor = db.execute(
            """
            UPDATE admin_agri_products
            SET name = ?, sort_order = ?, is_enabled = ?, version = ?,
                updated_at = ?
            WHERE product_key = ? AND version = ?
            """,
            (
                values["name"],
                values["sort_order"],
                int(values["is_enabled"]),
                current_version + 1,
                now,
                key,
                current_version,
            ),
        )
        if cursor.rowcount != 1:
            raise ProviderConflictError(
                "农产品已被其他管理员修改",
                code="agri_product_preset_version_conflict",
                details={
                    "product_key": key,
                    "expected_version": expected_version,
                    "current_version": current_version,
                },
            )
        record_admin_audit(
            db,
            actor_id=actor_id,
            action="update_agri_product_preset",
            target_type="agri_product",
            target_id=key,
            before={"version": current_version, "name": row["name"]},
            after={"version": current_version + 1, "name": values["name"]},
            result="success",
        )
    except Exception:
        db.rollback()
        raise
    db.commit()
    return _agri_product_item(key)


def disable_agri_product_preset(
    actor_id: int,
    product_key: str,
    expected_version: object = None,
) -> dict:
    key = _stable_key(product_key, field="product_key")
    locked_version = _optional_expected_version(expected_version)
    db = get_db()
    _begin(db)
    try:
        row = db.execute(
            f"""
            SELECT {AGRI_PRODUCT_COLUMNS}
            FROM admin_agri_products
            WHERE product_key = ?
            """,
            (key,),
        ).fetchone()
        if row is None:
            raise _not_found(
                "农产品不存在",
                "agri_product_preset_not_found",
                product_key=key,
            )
        if not row["is_enabled"]:
            db.commit()
            return _serialize_agri_product_item(row)
        current_version = int(row["version"])
        if locked_version is not None and current_version != locked_version:
            raise ProviderConflictError(
                "农产品已被其他管理员修改",
                code="agri_product_preset_version_conflict",
                details={
                    "product_key": key,
                    "expected_version": locked_version,
                    "current_version": current_version,
                },
            )
        now = platform_now_iso()
        cursor = db.execute(
            """
            UPDATE admin_agri_products
            SET is_enabled = 0, version = version + 1, updated_at = ?
            WHERE product_key = ? AND version = ?
            """,
            (now, key, current_version),
        )
        if cursor.rowcount != 1:
            raise ProviderConflictError(
                "农产品已被其他管理员修改",
                code="agri_product_preset_version_conflict",
                details={
                    "product_key": key,
                    "expected_version": locked_version,
                    "current_version": current_version,
                },
            )
        record_admin_audit(
            db,
            actor_id=actor_id,
            action="disable_agri_product_preset",
            target_type="agri_product",
            target_id=key,
            before={"is_enabled": True, "version": current_version},
            after={"is_enabled": False, "version": current_version + 1},
            result="success",
        )
    except Exception:
        db.rollback()
        raise
    db.commit()
    return _agri_product_item(key)


def _agri_calendar_item(item_id: str) -> dict:
    row = _fetch_one(
        f"""
        SELECT {AGRI_CALENDAR_COLUMNS}
        FROM admin_agri_calendar
        WHERE item_id = ?
        """,
        (item_id,),
    )
    if row is None:
        raise _not_found(
            "农时条目不存在",
            "agri_calendar_preset_not_found",
            item_id=item_id,
        )
    return _serialize_agri_calendar_item(row)


def list_agri_calendar_presets() -> list[dict]:
    rows = _fetch_all(
        f"""
        SELECT {AGRI_CALENDAR_COLUMNS}
        FROM admin_agri_calendar
        ORDER BY sort_order ASC, item_id ASC
        """
    )
    return [_serialize_agri_calendar_item(row) for row in rows]


def create_agri_calendar_preset(actor_id: int, payload: dict) -> dict:
    values = _agri_calendar_payload(payload)
    now = platform_now_iso()
    try:
        with get_db() as db:
            db.execute(
                """
                INSERT INTO admin_agri_calendar (
                    item_id, product_key, month, tasks_json, management_json,
                    solar_terms_json, reminder, sort_order, is_enabled,
                    version, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                """,
                (
                    values["item_id"],
                    values["product_key"],
                    values["month"],
                    json.dumps(values["tasks"], ensure_ascii=False),
                    json.dumps(values["management"], ensure_ascii=False),
                    json.dumps(values["solar_terms"], ensure_ascii=False),
                    values["reminder"],
                    values["sort_order"],
                    int(values["is_enabled"]),
                    now,
                    now,
                ),
            )
            record_admin_audit(
                db,
                actor_id=actor_id,
                action="create_agri_calendar_preset",
                target_type="agri_calendar",
                target_id=values["item_id"],
                before=None,
                after={
                    "product_key": values["product_key"],
                    "month": values["month"],
                    "is_enabled": values["is_enabled"],
                },
                result="success",
            )
    except sqlite3.IntegrityError as error:
        # The stable `item_id` and the UNIQUE (product_key, month) pair both
        # land here, so one conflict code covers a repeated month for the
        # same product whichever constraint fires first.
        raise ProviderConflictError(
            "该农产品当月农时已存在",
            code="agri_calendar_preset_conflict",
            details={
                "item_id": values["item_id"],
                "product_key": values["product_key"],
                "month": values["month"],
            },
        ) from error
    return _agri_calendar_item(values["item_id"])


def update_agri_calendar_preset(
    actor_id: int,
    item_id: str,
    payload: dict,
) -> dict:
    key = _stable_key(item_id, field="item_id")
    expected_version = _expected_version(
        payload.get("expected_version") if isinstance(payload, dict) else None
    )
    db = get_db()
    _begin(db)
    try:
        row = db.execute(
            f"""
            SELECT {AGRI_CALENDAR_COLUMNS}
            FROM admin_agri_calendar
            WHERE item_id = ?
            """,
            (key,),
        ).fetchone()
        if row is None:
            raise _not_found(
                "农时条目不存在",
                "agri_calendar_preset_not_found",
                item_id=key,
            )
        values = _agri_calendar_payload(payload, existing=row)
        current_version = int(row["version"])
        if current_version != expected_version:
            raise ProviderConflictError(
                "农时条目已被其他管理员修改",
                code="agri_calendar_preset_version_conflict",
                details={
                    "item_id": key,
                    "expected_version": expected_version,
                    "current_version": current_version,
                },
            )
        now = platform_now_iso()
        cursor = db.execute(
            """
            UPDATE admin_agri_calendar
            SET tasks_json = ?, management_json = ?, solar_terms_json = ?,
                reminder = ?, sort_order = ?, is_enabled = ?, version = ?,
                updated_at = ?
            WHERE item_id = ? AND version = ?
            """,
            (
                json.dumps(values["tasks"], ensure_ascii=False),
                json.dumps(values["management"], ensure_ascii=False),
                json.dumps(values["solar_terms"], ensure_ascii=False),
                values["reminder"],
                values["sort_order"],
                int(values["is_enabled"]),
                current_version + 1,
                now,
                key,
                current_version,
            ),
        )
        if cursor.rowcount != 1:
            raise ProviderConflictError(
                "农时条目已被其他管理员修改",
                code="agri_calendar_preset_version_conflict",
                details={
                    "item_id": key,
                    "expected_version": expected_version,
                    "current_version": current_version,
                },
            )
        record_admin_audit(
            db,
            actor_id=actor_id,
            action="update_agri_calendar_preset",
            target_type="agri_calendar",
            target_id=key,
            before={
                "version": current_version,
                "reminder": row["reminder"],
            },
            after={
                "version": current_version + 1,
                "reminder": values["reminder"],
            },
            result="success",
        )
    except Exception:
        db.rollback()
        raise
    db.commit()
    return _agri_calendar_item(key)


def disable_agri_calendar_preset(
    actor_id: int,
    item_id: str,
    expected_version: object = None,
) -> dict:
    key = _stable_key(item_id, field="item_id")
    locked_version = _optional_expected_version(expected_version)
    db = get_db()
    _begin(db)
    try:
        row = db.execute(
            f"""
            SELECT {AGRI_CALENDAR_COLUMNS}
            FROM admin_agri_calendar
            WHERE item_id = ?
            """,
            (key,),
        ).fetchone()
        if row is None:
            raise _not_found(
                "农时条目不存在",
                "agri_calendar_preset_not_found",
                item_id=key,
            )
        if not row["is_enabled"]:
            db.commit()
            return _serialize_agri_calendar_item(row)
        current_version = int(row["version"])
        if locked_version is not None and current_version != locked_version:
            raise ProviderConflictError(
                "农时条目已被其他管理员修改",
                code="agri_calendar_preset_version_conflict",
                details={
                    "item_id": key,
                    "expected_version": locked_version,
                    "current_version": current_version,
                },
            )
        now = platform_now_iso()
        cursor = db.execute(
            """
            UPDATE admin_agri_calendar
            SET is_enabled = 0, version = version + 1, updated_at = ?
            WHERE item_id = ? AND version = ?
            """,
            (now, key, current_version),
        )
        if cursor.rowcount != 1:
            raise ProviderConflictError(
                "农时条目已被其他管理员修改",
                code="agri_calendar_preset_version_conflict",
                details={
                    "item_id": key,
                    "expected_version": locked_version,
                    "current_version": current_version,
                },
            )
        record_admin_audit(
            db,
            actor_id=actor_id,
            action="disable_agri_calendar_preset",
            target_type="agri_calendar",
            target_id=key,
            before={"is_enabled": True, "version": current_version},
            after={"is_enabled": False, "version": current_version + 1},
            result="success",
        )
    except Exception:
        db.rollback()
        raise
    db.commit()
    return _agri_calendar_item(key)


def _agri_pest_item(item_id: str) -> dict:
    row = _fetch_one(
        f"""
        SELECT {AGRI_PEST_COLUMNS}
        FROM admin_pest_knowledge
        WHERE item_id = ?
        """,
        (item_id,),
    )
    if row is None:
        raise _not_found(
            "病虫害条目不存在",
            "pest_knowledge_preset_not_found",
            item_id=item_id,
        )
    return _serialize_agri_pest_item(row)


def list_pest_knowledge_presets() -> list[dict]:
    rows = _fetch_all(
        f"""
        SELECT {AGRI_PEST_COLUMNS}
        FROM admin_pest_knowledge
        ORDER BY sort_order ASC, item_id ASC
        """
    )
    return [_serialize_agri_pest_item(row) for row in rows]


def create_pest_knowledge_preset(actor_id: int, payload: dict) -> dict:
    values = _agri_pest_payload(payload)
    now = platform_now_iso()
    try:
        with get_db() as db:
            db.execute(
                """
                INSERT INTO admin_pest_knowledge (
                    item_id, sort_order, pest_name, product_names_json,
                    symptoms_json, aliases_json, answer, is_enabled, version,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                """,
                (
                    values["item_id"],
                    values["sort_order"],
                    values["pest_name"],
                    json.dumps(values["product_names"], ensure_ascii=False),
                    json.dumps(values["symptoms"], ensure_ascii=False),
                    json.dumps(values["aliases"], ensure_ascii=False),
                    values["answer"],
                    int(values["is_enabled"]),
                    now,
                    now,
                ),
            )
            record_admin_audit(
                db,
                actor_id=actor_id,
                action="create_pest_knowledge_preset",
                target_type="pest_knowledge",
                target_id=values["item_id"],
                before=None,
                after={
                    "pest_name": values["pest_name"],
                    "is_enabled": values["is_enabled"],
                },
                result="success",
            )
    except sqlite3.IntegrityError as error:
        raise ProviderConflictError(
            "病虫害条目 ID 已存在",
            code="pest_knowledge_preset_conflict",
            details={"item_id": values["item_id"]},
        ) from error
    return _agri_pest_item(values["item_id"])


def update_pest_knowledge_preset(
    actor_id: int,
    item_id: str,
    payload: dict,
) -> dict:
    key = _stable_key(item_id, field="item_id")
    expected_version = _expected_version(
        payload.get("expected_version") if isinstance(payload, dict) else None
    )
    db = get_db()
    _begin(db)
    try:
        row = db.execute(
            f"""
            SELECT {AGRI_PEST_COLUMNS}
            FROM admin_pest_knowledge
            WHERE item_id = ?
            """,
            (key,),
        ).fetchone()
        if row is None:
            raise _not_found(
                "病虫害条目不存在",
                "pest_knowledge_preset_not_found",
                item_id=key,
            )
        values = _agri_pest_payload(payload, existing=row)
        current_version = int(row["version"])
        if current_version != expected_version:
            raise ProviderConflictError(
                "病虫害条目已被其他管理员修改",
                code="pest_knowledge_preset_version_conflict",
                details={
                    "item_id": key,
                    "expected_version": expected_version,
                    "current_version": current_version,
                },
            )
        now = platform_now_iso()
        cursor = db.execute(
            """
            UPDATE admin_pest_knowledge
            SET sort_order = ?, pest_name = ?, product_names_json = ?,
                symptoms_json = ?, aliases_json = ?, answer = ?,
                is_enabled = ?, version = ?, updated_at = ?
            WHERE item_id = ? AND version = ?
            """,
            (
                values["sort_order"],
                values["pest_name"],
                json.dumps(values["product_names"], ensure_ascii=False),
                json.dumps(values["symptoms"], ensure_ascii=False),
                json.dumps(values["aliases"], ensure_ascii=False),
                values["answer"],
                int(values["is_enabled"]),
                current_version + 1,
                now,
                key,
                current_version,
            ),
        )
        if cursor.rowcount != 1:
            raise ProviderConflictError(
                "病虫害条目已被其他管理员修改",
                code="pest_knowledge_preset_version_conflict",
                details={
                    "item_id": key,
                    "expected_version": expected_version,
                    "current_version": current_version,
                },
            )
        record_admin_audit(
            db,
            actor_id=actor_id,
            action="update_pest_knowledge_preset",
            target_type="pest_knowledge",
            target_id=key,
            before={
                "version": current_version,
                "pest_name": row["pest_name"],
            },
            after={
                "version": current_version + 1,
                "pest_name": values["pest_name"],
            },
            result="success",
        )
    except Exception:
        db.rollback()
        raise
    db.commit()
    return _agri_pest_item(key)


def disable_pest_knowledge_preset(
    actor_id: int,
    item_id: str,
    expected_version: object = None,
) -> dict:
    key = _stable_key(item_id, field="item_id")
    locked_version = _optional_expected_version(expected_version)
    db = get_db()
    _begin(db)
    try:
        row = db.execute(
            f"""
            SELECT {AGRI_PEST_COLUMNS}
            FROM admin_pest_knowledge
            WHERE item_id = ?
            """,
            (key,),
        ).fetchone()
        if row is None:
            raise _not_found(
                "病虫害条目不存在",
                "pest_knowledge_preset_not_found",
                item_id=key,
            )
        if not row["is_enabled"]:
            db.commit()
            return _serialize_agri_pest_item(row)
        current_version = int(row["version"])
        if locked_version is not None and current_version != locked_version:
            raise ProviderConflictError(
                "病虫害条目已被其他管理员修改",
                code="pest_knowledge_preset_version_conflict",
                details={
                    "item_id": key,
                    "expected_version": locked_version,
                    "current_version": current_version,
                },
            )
        now = platform_now_iso()
        cursor = db.execute(
            """
            UPDATE admin_pest_knowledge
            SET is_enabled = 0, version = version + 1, updated_at = ?
            WHERE item_id = ? AND version = ?
            """,
            (now, key, current_version),
        )
        if cursor.rowcount != 1:
            raise ProviderConflictError(
                "病虫害条目已被其他管理员修改",
                code="pest_knowledge_preset_version_conflict",
                details={
                    "item_id": key,
                    "expected_version": locked_version,
                    "current_version": current_version,
                },
            )
        record_admin_audit(
            db,
            actor_id=actor_id,
            action="disable_pest_knowledge_preset",
            target_type="pest_knowledge",
            target_id=key,
            before={"is_enabled": True, "version": current_version},
            after={"is_enabled": False, "version": current_version + 1},
            result="success",
        )
    except Exception:
        db.rollback()
        raise
    db.commit()
    return _agri_pest_item(key)


def seed_agri_preset_content(connection) -> None:
    """Seed 03's placeholder agri content as manageable admin rows.

    The content is read from 03's `PlaceholderPresetProvider`, which stays
    the single source of truth for the demo text, so nothing is copied by
    hand. `ON CONFLICT ... DO NOTHING` keeps admin edits and logical
    deletes across restarts, so the seed only fills an empty slot instead
    of overwriting the console.
    """
    now = platform_now_iso()
    placeholder = PlaceholderPresetProvider()
    products = placeholder.list_products()
    connection.executemany(
        """
        INSERT INTO admin_agri_products (
            product_key, name, sort_order, is_enabled, version,
            created_at, updated_at
        )
        VALUES (?, ?, ?, 1, 1, ?, ?)
        ON CONFLICT(product_key) DO NOTHING
        """,
        [
            (
                str(product["key"]),
                str(product["name"]),
                int(product["sort_order"]),
                now,
                now,
            )
            for product in products
        ],
    )
    calendar_rows = []
    for product in products:
        product_key = str(product["key"])
        for entry in placeholder.list_calendar_entries(product_key):
            month = int(entry["month"])
            calendar_rows.append(
                (
                    _agri_calendar_item_id(product_key, month),
                    product_key,
                    month,
                    json.dumps(list(entry["tasks"]), ensure_ascii=False),
                    json.dumps(list(entry["management"]), ensure_ascii=False),
                    json.dumps(list(entry["solar_terms"]), ensure_ascii=False),
                    str(entry["reminder"]),
                    month,
                    now,
                    now,
                )
            )
    # `item_id` is a deterministic function of (product_key, month), so
    # ON CONFLICT(item_id) depends on that invariant: if the ID rule
    # changes, UNIQUE(product_key, month) can bypass it and init_db raises
    # IntegrityError.
    connection.executemany(
        """
        INSERT INTO admin_agri_calendar (
            item_id, product_key, month, tasks_json, management_json,
            solar_terms_json, reminder, sort_order, is_enabled, version,
            created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, 1, ?, ?)
        ON CONFLICT(item_id) DO NOTHING
        """,
        calendar_rows,
    )
    connection.executemany(
        """
        INSERT INTO admin_pest_knowledge (
            item_id, sort_order, pest_name, product_names_json,
            symptoms_json, aliases_json, answer, is_enabled, version,
            created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, 1, 1, ?, ?)
        ON CONFLICT(item_id) DO NOTHING
        """,
        [
            (
                str(pest["id"]),
                int(pest["sort_order"]),
                str(pest["pest_name"]),
                json.dumps(list(pest["product_names"]), ensure_ascii=False),
                json.dumps(list(pest["symptoms"]), ensure_ascii=False),
                json.dumps(list(pest["aliases"]), ensure_ascii=False),
                str(pest["answer"]),
                now,
                now,
            )
            for pest in placeholder.list_pest_entries()
        ],
    )


__all__ = [
    "AGRI_TEXT_ITEM_MAXIMUM",
    "AGRI_TEXT_LIST_LIMIT",
    "ASSISTANT_FEATURE_KEYS",
    "ASSISTANT_KNOWLEDGE_SEED",
    "AdminDatabaseLocalResourceCaseProvider",
    "DatabaseAgriPresetContentProvider",
    "DatabaseAssistantFeatureKnowledgeProvider",
    "DatabaseCraftPresetProvider",
    "create_agri_calendar_preset",
    "create_agri_product_preset",
    "create_case_preset",
    "create_craft_preset",
    "create_knowledge_preset",
    "create_pest_knowledge_preset",
    "disable_agri_calendar_preset",
    "disable_agri_product_preset",
    "disable_case_preset",
    "disable_craft_preset",
    "disable_knowledge_preset",
    "disable_pest_knowledge_preset",
    "list_agri_calendar_presets",
    "list_agri_product_presets",
    "list_case_presets",
    "list_craft_presets",
    "list_knowledge_presets",
    "list_pest_knowledge_presets",
    "seed_agri_preset_content",
    "seed_assistant_feature_knowledge",
    "seed_craft_presets",
    "update_agri_calendar_preset",
    "update_agri_product_preset",
    "update_case_preset",
    "update_craft_preset",
    "update_knowledge_preset",
    "update_pest_knowledge_preset",
    "_json_fields",
    "_required_text",
    "_serialize_agri_calendar_entry",
    "_serialize_agri_pest_entry",
    "_serialize_agri_product",
    "_serialize_case",
    "_serialize_craft",
    "_serialize_knowledge_entry",
]
