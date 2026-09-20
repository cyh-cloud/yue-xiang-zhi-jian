from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from app.agri_skills.outcomes import list_learning_outcomes
from app.db import get_db
from app.ecommerce_training.course_learning import (
    list_ecommerce_learning_outcomes,
)
from app.handcraft_inheritance.outcomes import (
    list_handcraft_learning_outcomes,
)
from app.job_matching.constants import SKILL_CATEGORIES
from app.job_matching.errors import JobMatchingValidationError


LOGGER = logging.getLogger(__name__)

CATEGORY_BY_AGRI_KIND = {
    "diagnostic_self_test": "quiz_score",
    "course_quiz": "quiz_score",
}

CATEGORY_BY_ECOMMERCE_KIND = {
    "live_script": "live_script",
    "simulation_training": "simulation_training",
    "course_quiz": "quiz_score",
    "course_completion": "learning_record",
}

CATEGORY_BY_HANDCRAFT_TYPE = {
    "course_quiz": "quiz_score",
    "course_view": "learning_record",
    "course_completion": "learning_record",
    "craft_step": "learning_record",
    "ar_usage": "learning_record",
}


def _now_iso() -> str:
    return datetime.now(
        ZoneInfo("Asia/Shanghai")
    ).isoformat(timespec="seconds")


def _category_summary(items: list[dict]) -> dict:
    summary = {category: 0 for category in SKILL_CATEGORIES}
    for item in items:
        summary[item["category"]] += 1
    return summary


def _base_item(
    source_module: str,
    source_type: str,
    source_id: int,
    category: str,
    title: str,
    summary: str,
    score,
    is_formal: bool,
    occurred_at: str,
    source_available: bool = True,
) -> dict:
    return {
        "item_id": f"{source_module}:{source_type}:{int(source_id)}",
        "category": category,
        "source_module": source_module,
        "source_type": source_type,
        "title": title,
        "summary": summary,
        "score": score,
        "is_formal": bool(is_formal),
        "occurred_at": occurred_at,
        "source_available": bool(source_available),
    }


def _unknown_source(source_module: str, source_type: str) -> None:
    LOGGER.warning(
        "Unknown skill outcome source type %s from %s",
        source_type,
        source_module,
    )


def _agri_items(student_id: int) -> list[dict]:
    items = []
    for row in list_learning_outcomes(student_id):
        source_type = str(row["kind"])
        category = CATEGORY_BY_AGRI_KIND.get(source_type)
        if category is None:
            _unknown_source("agriculture", source_type)
            continue

        if source_type == "diagnostic_self_test":
            title = "诊断自测"
            summary = f"诊断会话 {row['diagnosis_session_id']}"
        else:
            title = "课后测验"
            summary = f"课程 {row['course_id']}"
        items.append(
            _base_item(
                "agriculture",
                source_type,
                int(row["source_id"]),
                category,
                title,
                summary,
                row["score"],
                row["is_formal"],
                str(row["created_at"]),
            )
        )
    return items


def _ecommerce_items(student_id: int) -> list[dict]:
    items = []
    for row in list_ecommerce_learning_outcomes(student_id):
        source_type = str(row["kind"])
        category = CATEGORY_BY_ECOMMERCE_KIND.get(source_type)
        if category is None:
            _unknown_source("ecommerce", source_type)
            continue

        title = str(row["summary"])
        items.append(
            _base_item(
                "ecommerce",
                source_type,
                int(row["source_id"]),
                category,
                title,
                title,
                row["score"],
                row["is_formal"],
                str(row["created_at"]),
                bool(row.get("source_available", True)),
            )
        )
    return items


def _handcraft_items(student_id: int) -> list[dict]:
    items = []
    for row in list_handcraft_learning_outcomes(student_id):
        source_type = str(row["outcome_type"])
        category = CATEGORY_BY_HANDCRAFT_TYPE.get(source_type)
        if category is None:
            _unknown_source("handcraft", source_type)
            continue

        title = str(row["summary"])
        items.append(
            _base_item(
                "handcraft",
                source_type,
                int(row["source_id"]),
                category,
                title,
                title,
                row["score"],
                row["is_formal"],
                str(row["created_at"]),
                bool(row.get("source_available", True)),
            )
        )
    return items


def _dedupe_key(item: dict) -> str:
    if item["source_type"] == "course_quiz":
        return f"course_quiz:{item['item_id'].rsplit(':', 1)[-1]}"
    return item["item_id"]


def _source_precedence(item: dict) -> int:
    if item["source_module"] == "ecommerce":
        return 0
    if item["source_module"] == "handcraft":
        return 1
    return 2


def _parse_iso(value: object) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("occurred_at must include a timezone")
    return parsed


def _safe_source(reader, student_id: int) -> list[dict]:
    try:
        items = reader(student_id)
        valid_items = []
        for item in items:
            try:
                _parse_iso(item["occurred_at"])
            except (KeyError, TypeError, ValueError):
                item_id = (
                    item.get("item_id", "unknown")
                    if isinstance(item, dict)
                    else "unknown"
                )
                LOGGER.warning(
                    "Invalid skill outcome timestamp for %s",
                    item_id,
                )
                continue
            valid_items.append(item)
        return valid_items
    except Exception:
        LOGGER.exception("Skill outcome source failed")
        return []


def list_skill_outcomes(student_id: int) -> list[dict]:
    grouped = {}
    for item in (
        _safe_source(_agri_items, student_id)
        + _safe_source(_ecommerce_items, student_id)
        + _safe_source(_handcraft_items, student_id)
    ):
        key = _dedupe_key(item)
        current = grouped.get(key)
        if (
            current is None
            or _source_precedence(item) < _source_precedence(current)
        ):
            grouped[key] = item
    return sorted(
        grouped.values(),
        key=lambda item: (
            _parse_iso(item["occurred_at"]),
            item["category"],
            item["item_id"],
        ),
    )


def get_skill_profile(student_id: int) -> dict:
    visible_ids = {
        str(row["item_id"])
        for row in get_db().execute(
            """
            SELECT item_id
            FROM skill_visibility_settings
            WHERE user_id = ? AND visible = 1
            """,
            (student_id,),
        ).fetchall()
    }
    items = [
        {**item, "visible": item["item_id"] in visible_ids}
        for item in list_skill_outcomes(student_id)
    ]
    return {
        "items": items,
        "visible_item_ids": [
            item["item_id"] for item in items if item["visible"]
        ],
        "summary": _category_summary(items),
    }


def set_skill_visibility(
    student_id: int,
    visible_item_ids: list[str],
) -> dict:
    all_items = list_skill_outcomes(student_id)
    known_ids = {item["item_id"] for item in all_items}
    if (
        not isinstance(visible_item_ids, list)
        or any(not isinstance(value, str) for value in visible_item_ids)
    ):
        raise JobMatchingValidationError("可见成果格式不正确")
    normalized = list(
        dict.fromkeys(value.strip() for value in visible_item_ids)
    )
    unknown = set(normalized).difference(known_ids)
    if unknown:
        raise JobMatchingValidationError(
            "可见成果不存在",
            details={"item_ids": sorted(unknown)},
        )
    now = _now_iso()
    with get_db() as db:
        db.execute(
            "DELETE FROM skill_visibility_settings WHERE user_id = ?",
            (student_id,),
        )
        db.executemany(
            """
            INSERT INTO skill_visibility_settings (
                user_id, item_id, visible, updated_at
            ) VALUES (?, ?, 1, ?)
            """,
            ((student_id, item_id, now) for item_id in normalized),
        )
    return get_skill_profile(student_id)


def build_skill_profile_snapshot(student_id: int) -> dict | None:
    profile = get_skill_profile(student_id)
    items = [
        {key: value for key, value in item.items() if key != "visible"}
        for item in profile["items"]
        if item["visible"] and item["source_available"]
    ]
    if not items:
        return None
    return {
        "schema_version": 1,
        "generated_at": _now_iso(),
        "items": items,
        "summary": _category_summary(items),
    }
