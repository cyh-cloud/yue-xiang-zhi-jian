from __future__ import annotations

import copy
import json

from app.agri_skills.ai_client import get_ai_client
from app.agri_skills.ai_context import build_ai_messages
from app.agri_skills.errors import (
    AgriNotFoundError,
    AgriValidationError,
    AiUnavailableError,
)
from app.db import get_db
from app.ecommerce_training.presets import SIMULATION_SCENES
from app.session_manager import utc_now_iso


AI_UNAVAILABLE_MESSAGE = "AI 服务暂时不可用"
DIMENSION_KEYS = ("pacing", "emotion", "interaction", "selling_point")


def list_simulation_scenes() -> list[dict]:
    return [
        {
            "key": scene_key,
            "label": scene["label"],
            "segments": copy.deepcopy(scene["segments"]),
        }
        for scene_key, scene in SIMULATION_SCENES.items()
    ]


def _require_scene(scene_key: str) -> dict:
    scene = (
        SIMULATION_SCENES.get(scene_key)
        if isinstance(scene_key, str)
        else None
    )
    if scene is None:
        raise AgriValidationError("模拟场景不存在")
    return scene


def _serialize_row(row) -> dict:
    segments = json.loads(row["segments_json"])
    stored_scores = (
        json.loads(row["scores_json"]) if row["scores_json"] is not None else None
    )
    scene = SIMULATION_SCENES.get(row["scene_key"], {})
    return {
        "id": int(row["id"]),
        "scene_key": str(row["scene_key"]),
        "scene_label": str(scene.get("label", "")),
        "segments": segments,
        "status": str(row["status"]),
        "scores": stored_scores["scores"] if stored_scores else None,
        "suggestions": stored_scores["suggestions"] if stored_scores else None,
        "total_score": (
            int(row["total_score"]) if row["total_score"] is not None else None
        ),
        "created_at": str(row["created_at"]),
        "updated_at": str(row["updated_at"]),
        "completed_at": (
            str(row["completed_at"]) if row["completed_at"] is not None else None
        ),
    }


def _get_training_row(user_id: int, training_id: int):
    row = get_db().execute(
        """
        SELECT id, user_id, scene_key, segments_json, status, scores_json,
               total_score, created_at, updated_at, completed_at
        FROM ecommerce_simulation_trainings
        WHERE id = ? AND user_id = ?
        """,
        (training_id, user_id),
    ).fetchone()
    if row is None:
        raise AgriNotFoundError("模拟训练不存在")
    return row


def get_simulation(user_id: int, training_id: int) -> dict:
    return _serialize_row(_get_training_row(user_id, training_id))


def start_simulation(user_id: int, scene_key: str) -> dict:
    scene = _require_scene(scene_key)
    segments = [
        {
            "key": segment["key"],
            "label": segment["label"],
            "text": "",
        }
        for segment in scene["segments"]
    ]
    now = utc_now_iso()
    db = get_db()
    with db:
        cursor = db.execute(
            """
            INSERT INTO ecommerce_simulation_trainings (
                user_id, scene_key, segments_json, status, scores_json,
                total_score, created_at, updated_at, completed_at
            )
            VALUES (?, ?, ?, 'draft', NULL, NULL, ?, ?, NULL)
            """,
            (
                user_id,
                scene_key,
                json.dumps(segments, ensure_ascii=False),
                now,
                now,
            ),
        )
    return get_simulation(user_id, int(cursor.lastrowid))


def save_simulation_segment(
    user_id: int,
    training_id: int,
    segment_key: str,
    text: str,
) -> dict:
    row = _get_training_row(user_id, training_id)
    if row["status"] != "draft":
        raise AgriValidationError("训练已完成，不能修改")
    if not isinstance(text, str) or not text.strip():
        raise AgriValidationError("环节内容不能为空")

    segments = json.loads(row["segments_json"])
    target = next(
        (
            segment
            for segment in segments
            if segment.get("key") == segment_key
        ),
        None,
    )
    if target is None:
        raise AgriValidationError("模拟环节不存在")
    if str(target.get("text", "")).strip():
        raise AgriValidationError("该环节已提交")

    target["text"] = text.strip()
    db = get_db()
    with db:
        db.execute(
            """
            UPDATE ecommerce_simulation_trainings
            SET segments_json = ?, updated_at = ?
            WHERE id = ? AND user_id = ? AND status = 'draft'
            """,
            (
                json.dumps(segments, ensure_ascii=False),
                utc_now_iso(),
                training_id,
                user_id,
            ),
        )
    return get_simulation(user_id, training_id)


def _validate_scores(payload: dict) -> tuple[dict, dict]:
    if not isinstance(payload, dict):
        raise AiUnavailableError(AI_UNAVAILABLE_MESSAGE)

    scores = payload.get("scores")
    suggestions = payload.get("suggestions")
    keys = set(DIMENSION_KEYS)
    if not isinstance(scores, dict) or set(scores) != keys:
        raise AiUnavailableError(AI_UNAVAILABLE_MESSAGE)
    if not isinstance(suggestions, dict) or set(suggestions) != keys:
        raise AiUnavailableError(AI_UNAVAILABLE_MESSAGE)

    normalized_scores = {}
    normalized_suggestions = {}
    for key in DIMENSION_KEYS:
        score = scores[key]
        raw_suggestion = suggestions[key]
        if not isinstance(raw_suggestion, str):
            raise AiUnavailableError(AI_UNAVAILABLE_MESSAGE)
        suggestion = raw_suggestion.strip()
        if (
            not isinstance(score, int)
            or isinstance(score, bool)
            or not 0 <= score <= 100
            or not suggestion
        ):
            raise AiUnavailableError(AI_UNAVAILABLE_MESSAGE)
        normalized_scores[key] = score
        normalized_suggestions[key] = suggestion
    return normalized_scores, normalized_suggestions


def score_simulation(user_id: int, training_id: int) -> dict:
    row = _get_training_row(user_id, training_id)
    if row["status"] == "completed":
        return _serialize_row(row)

    scene = _require_scene(row["scene_key"])
    expected_keys = [segment["key"] for segment in scene["segments"]]
    segments = json.loads(row["segments_json"])
    actual_keys = [segment.get("key") for segment in segments]
    if (
        actual_keys != expected_keys
        or any(
            not isinstance(segment.get("text"), str)
            or not segment["text"].strip()
            for segment in segments
        )
    ):
        raise AgriValidationError("请完成全部训练环节")

    request = {
        "scene_label": scene["label"],
        "segments": [
            {
                "key": segment["key"],
                "label": segment["label"],
                "text": segment["text"].strip(),
            }
            for segment in segments
        ],
    }
    try:
        response = get_ai_client().complete_json(
            build_ai_messages("simulation_score", request),
            call_point="simulation_score",
        )
    except AiUnavailableError as error:
        raise AiUnavailableError(AI_UNAVAILABLE_MESSAGE) from error

    scores, suggestions = _validate_scores(response)
    total_score = round(sum(scores.values()) / len(DIMENSION_KEYS))
    now = utc_now_iso()
    db = get_db()
    with db:
        updated = db.execute(
            """
            UPDATE ecommerce_simulation_trainings
            SET status = 'completed', scores_json = ?, total_score = ?,
                updated_at = ?, completed_at = ?
            WHERE id = ? AND user_id = ? AND status = 'draft'
            """,
            (
                json.dumps(
                    {
                        "scores": scores,
                        "suggestions": suggestions,
                    },
                    ensure_ascii=False,
                ),
                total_score,
                now,
                now,
                training_id,
                user_id,
            ),
        )
        if updated.rowcount != 1:
            return _serialize_row(_get_training_row(user_id, training_id))
    return get_simulation(user_id, training_id)


def list_simulations(user_id: int) -> list[dict]:
    rows = get_db().execute(
        """
        SELECT id, user_id, scene_key, segments_json, status, scores_json,
               total_score, created_at, updated_at, completed_at
        FROM ecommerce_simulation_trainings
        WHERE user_id = ?
        ORDER BY id DESC
        """,
        (user_id,),
    ).fetchall()
    return [_serialize_row(row) for row in rows]
