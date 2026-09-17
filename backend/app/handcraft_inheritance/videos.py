from __future__ import annotations

from copy import deepcopy

from app.agri_skills.errors import AgriValidationError
from app.db import get_db
from app.handcraft_inheritance.providers import (
    get_teaching_video_provider,
    set_video_review_provider,
)


VIDEO_UNAVAILABLE = "视频不可用"
VIDEO_MEDIA_UNAVAILABLE = "视频媒体来源不可用"
VIDEO_CONTRACT_MISMATCH = "视频媒体信息不一致"


def _required_craft_key(craft_key: object) -> str:
    normalized = str(craft_key or "").strip()
    if not normalized:
        raise AgriValidationError("技艺标识不能为空")
    return normalized


def _db_video(row) -> dict:
    return {
        "video_id": str(row["video_id"]),
        "craft_key": str(row["craft_key"]),
        "title": str(row["title"]),
        "review_status": str(row["review_status"]),
        "source_available": bool(row["source_available"]),
        "media_url": str(row["media_url"] or ""),
        "version": int(row["version"]),
        "rejection_opinion": row["rejection_opinion"],
        "published_at": row["published_at"],
        "created_at": str(row["created_at"]),
        "updated_at": str(row["updated_at"]),
    }


def _provider_video(video_id: str) -> dict | None:
    try:
        video = get_teaching_video_provider().get_video(video_id)
    except Exception:
        return None
    if not isinstance(video, dict):
        return None
    return deepcopy(video)


def _provider_source_available(provider_video: dict) -> bool | None:
    value = provider_video.get("source_available")
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in {0, 1}:
        return bool(value)
    return None


def _contract_error(db_video: dict, provider_video: dict | None) -> str | None:
    if provider_video is None:
        return VIDEO_MEDIA_UNAVAILABLE
    if str(provider_video.get("video_id", "")).strip() != db_video["video_id"]:
        return VIDEO_CONTRACT_MISMATCH
    if str(provider_video.get("craft_key", "")).strip() != db_video["craft_key"]:
        return VIDEO_CONTRACT_MISMATCH
    if str(provider_video.get("review_status", "")).strip() != db_video["review_status"]:
        return VIDEO_CONTRACT_MISMATCH
    if str(provider_video.get("media_url", "") or "").strip() != db_video["media_url"]:
        return VIDEO_CONTRACT_MISMATCH
    try:
        provider_version = int(provider_video.get("version"))
    except (TypeError, ValueError):
        return VIDEO_CONTRACT_MISMATCH
    if provider_version != db_video["version"]:
        return VIDEO_CONTRACT_MISMATCH
    return None


def _student_video_fields(video: dict) -> dict:
    return {
        key: value
        for key, value in video.items()
        if key != "rejection_opinion"
    }


def _unavailable_playback(
    db_video: dict | None,
    *,
    reason: str,
    video_id: str | None = None,
) -> dict:
    video = db_video or {}
    normalized_id = db_video["video_id"] if db_video is not None else video_id
    return {
        **_student_video_fields(video),
        "video_id": normalized_id,
        "craft_key": video.get("craft_key"),
        "title": video.get("title"),
        "review_status": video.get("review_status"),
        "source_available": bool(video.get("source_available", False)),
        "media_url": None,
        "playback_url": None,
        "version": video.get("version"),
        "is_demo": False,
        "available": False,
        "status": "unavailable",
        "unavailable_reason": reason,
    }


def get_video_playback(video_id: str) -> dict:
    normalized_id = str(video_id or "").strip()
    if not normalized_id:
        raise AgriValidationError("视频标识不能为空")
    row = get_db().execute(
        """
        SELECT *
        FROM heritage_videos
        WHERE video_id = ?
        """,
        (normalized_id,),
    ).fetchone()
    if row is None:
        return _unavailable_playback(
            None,
            reason=VIDEO_UNAVAILABLE,
            video_id=normalized_id,
        )

    db_video = _db_video(row)
    if db_video["review_status"] != "approved":
        return _unavailable_playback(
            db_video,
            reason=VIDEO_UNAVAILABLE,
        )
    if not db_video["source_available"] or not db_video["media_url"]:
        return _unavailable_playback(
            db_video,
            reason=VIDEO_MEDIA_UNAVAILABLE,
        )

    provider_video = _provider_video(normalized_id)
    contract_error = _contract_error(db_video, provider_video)
    if contract_error is not None:
        return _unavailable_playback(
            db_video,
            reason=contract_error,
        )
    provider_source_available = _provider_source_available(provider_video)
    if provider_source_available is None:
        return _unavailable_playback(
            db_video,
            reason=VIDEO_CONTRACT_MISMATCH,
        )
    if not provider_source_available:
        return _unavailable_playback(
            db_video,
            reason=VIDEO_MEDIA_UNAVAILABLE,
        )
    provider_media_url = str(provider_video.get("media_url", "") or "").strip()
    if not provider_media_url:
        return _unavailable_playback(
            db_video,
            reason=VIDEO_MEDIA_UNAVAILABLE,
        )

    return {
        **_student_video_fields(db_video),
        "is_demo": bool(provider_video.get("is_demo", False)),
        "playback_url": provider_media_url,
        "available": True,
        "status": "available",
        "unavailable_reason": None,
    }


def list_student_videos(craft_key: str) -> list[dict]:
    normalized_key = _required_craft_key(craft_key)
    rows = get_db().execute(
        """
        SELECT *
        FROM heritage_videos
        WHERE craft_key = ? AND review_status = 'approved'
        ORDER BY published_at DESC, video_id
        """,
        (normalized_key,),
    ).fetchall()
    return [
        playback
        for row in rows
        if (playback := get_video_playback(str(row["video_id"])))["available"]
    ]


def list_video_reviews() -> list[dict]:
    rows = get_db().execute(
        """
        SELECT *
        FROM heritage_videos
        ORDER BY updated_at DESC, video_id
        """
    ).fetchall()
    reviews = []
    for row in rows:
        db_video = _db_video(row)
        provider_video = _provider_video(db_video["video_id"])
        contract_error = _contract_error(db_video, provider_video)
        reviews.append(
            {
                **db_video,
                "provider_available": provider_video is not None,
                "contract_valid": contract_error is None,
                "status": (
                    "reviewable"
                    if contract_error is None
                    else "validation_error"
                ),
                "validation_error": contract_error,
            }
        )
    return reviews


def update_pending_video_contract(
    video_id: str,
    version: int,
    *,
    title: str | None = None,
    media_url: str | None = None,
    actor_id: int | None = None,
    submitter_id: int | None = None,
) -> dict:
    from app.handcraft_inheritance.admin_actions import apply_video_review

    normalized_id = str(video_id or "").strip()
    if not normalized_id:
        raise AgriValidationError("视频标识不能为空")
    action = {
        "video_id": normalized_id,
        "action": "edit",
        "actor_role": "teacher",
        "actor_id": actor_id,
        "submitter_id": submitter_id,
        "version": version,
    }
    if title is not None:
        action["title"] = title
    if media_url is not None:
        action["media_url"] = media_url

    result = apply_video_review(action)
    row = get_db().execute(
        """
        SELECT review_status, published_at
        FROM heritage_videos
        WHERE video_id = ?
        """,
        (normalized_id,),
    ).fetchone()
    if row is not None:
        result["review_status"] = str(row["review_status"])
        result["published_at"] = row["published_at"]
    return result
