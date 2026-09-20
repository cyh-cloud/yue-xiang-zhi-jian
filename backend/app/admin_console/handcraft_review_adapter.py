from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from app.admin_console.content_review_provider import (
    DatabaseContentReviewProvider,
)
from app.admin_console.errors import (
    ProviderAccessDeniedError,
    ProviderConflictError,
    ProviderError,
    ProviderNotFoundError,
    ProviderUnavailableError,
    ProviderValidationError,
)
from app.agri_skills.errors import (
    AgriAccessError,
    AgriNotFoundError,
    AgriValidationError,
)
from app.handcraft_inheritance.providers import (
    get_teaching_video_provider,
    normalize_video_review_status,
)


VIDEO_CONTENT_TYPE = "handcraft_teaching_video"
DATABASE_CONTENT_TYPES = frozenset({"course_video", "job_position"})
REVIEWER_ROLES = frozenset({"admin", "super_admin"})
SHANGHAI = ZoneInfo("Asia/Shanghai")


def _validation_error(
    message: str,
    code: str,
    **details,
) -> ProviderValidationError:
    return ProviderValidationError(message, code=code, details=details)


def _positive_int(value: object, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise _validation_error(
            f"{field} must be a positive integer",
            "review_validation_failed",
            field=field,
        )
    return value


def _content_id(value: object) -> str:
    if not isinstance(value, str):
        raise _validation_error(
            "content_id must be text",
            "review_content_id_invalid",
            field="content_id",
        )
    normalized = value.strip()
    if not normalized:
        raise _validation_error(
            "content_id must not be empty",
            "review_content_id_invalid",
            field="content_id",
        )
    return normalized


def _require_video_type(content_type: object) -> str:
    if content_type != VIDEO_CONTENT_TYPE:
        raise _validation_error(
            "content_type is not supported by the handcraft adapter",
            "review_type_invalid",
            content_type=content_type,
        )
    return VIDEO_CONTENT_TYPE


def _payload(value: object) -> dict:
    if not isinstance(value, dict):
        raise _validation_error(
            "payload must be an object",
            "review_payload_invalid",
            field="payload",
        )
    return dict(value)


def _editable_payload(value: object) -> dict:
    payload = _payload(value)
    if "craft_key" in payload:
        raise _validation_error(
            "craft_key is read-only",
            "review_field_read_only",
            field="craft_key",
        )
    payload.pop("source_available", None)
    return payload


def _normalized_opinion(value: object) -> str:
    if not isinstance(value, str):
        raise _validation_error(
            "opinion must be text",
            "review_opinion_invalid",
            field="opinion",
        )
    normalized = value.strip()
    if not 1 <= len(normalized) <= 500:
        raise _validation_error(
            "opinion length must be between 1 and 500 characters",
            "review_opinion_invalid",
            field="opinion",
            min_length=1,
            max_length=500,
        )
    return normalized


def _normalize_timestamp(value: object) -> object:
    if value is None or value == "":
        return value
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value).strip()
        if not text:
            return value
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return value
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=SHANGHAI)
    return parsed.astimezone(SHANGHAI).isoformat()


def _normalize_video(
    record: dict,
    *,
    content_id: str | None = None,
) -> dict:
    if not isinstance(record, dict):
        raise ProviderUnavailableError(
            "非遗视频数据不可用",
            code="review_source_unavailable",
            details={},
        )

    normalized = dict(record)
    normalized_status = normalized.get("review_status")
    if normalized_status in {None, ""}:
        normalized_status = normalized.get("status")
    normalized.pop("status", None)
    normalized_id = str(
        normalized.get("video_id") or content_id or ""
    ).strip()
    submitter_id = normalized.get("submitter_id")
    if submitter_id is None:
        submitter_id = normalized.get("owner_id")
    if submitter_id is None:
        submitter_id = normalized.get("teacher_id")

    normalized.update(
        {
            "content_type": VIDEO_CONTENT_TYPE,
            "content_id": normalized_id,
            "submitter_id": submitter_id,
            "review_status": normalize_video_review_status(
                normalized_status
            ),
            "version": normalized.get("version"),
        }
    )
    normalized.setdefault("rejection_opinion", None)
    normalized.setdefault("published_at", None)
    normalized.setdefault("created_at", None)
    normalized.setdefault("updated_at", None)
    for key in tuple(normalized):
        if key.endswith("_at"):
            normalized[key] = _normalize_timestamp(normalized[key])
    return normalized


def _map_05_error(error: Exception) -> ProviderError:
    message = str(error)
    if isinstance(error, AgriNotFoundError):
        return ProviderNotFoundError(
            message,
            code="review_not_found",
            details={"source_error": type(error).__name__},
        )
    if isinstance(error, AgriAccessError) or any(
        marker in message
        for marker in ("无管理权限", "仅教师", "只能编辑本人")
    ):
        return ProviderAccessDeniedError(
            message,
            code="review_access_denied",
            details={"source_error": type(error).__name__},
        )
    if isinstance(error, AgriValidationError):
        if any(
            marker in message
            for marker in ("版本", "状态不可", "状态已变化")
        ):
            return ProviderConflictError(
                message,
                code="review_state_conflict",
                details={"source_error": type(error).__name__},
            )
        return ProviderValidationError(
            message,
            code="review_validation_failed",
            details={"source_error": type(error).__name__},
        )
    return ProviderUnavailableError(
        "非遗视频审核服务暂不可用",
        code="review_source_unavailable",
        details={"source_error": type(error).__name__},
    )


class HandcraftTeachingVideoReviewAdapter:
    def submit_for_review(
        self,
        *,
        content_type: str,
        content_id: str,
        submitter_id: int,
        expected_version: int,
        payload: dict,
    ) -> dict:
        _require_video_type(content_type)
        normalized_id = _content_id(content_id)
        normalized_submitter = _positive_int(
            submitter_id,
            field="submitter_id",
        )
        normalized_version = _positive_int(
            expected_version,
            field="expected_version",
        )
        normalized_payload = _editable_payload(payload)
        current = self._read_video(normalized_id)
        if current is None:
            raise ProviderConflictError(
                "非遗视频首次提交暂不支持",
                code="review_submission_unsupported",
                details={"content_id": normalized_id},
            )

        current_status = current["review_status"]
        if current_status == "rejected":
            raise ProviderConflictError(
                "非遗视频驳回后重新提交暂不支持",
                code="review_state_conflict",
                details={
                    "content_id": normalized_id,
                    "review_status": current_status,
                },
            )
        if current_status not in {"pending", "approved"}:
            raise ProviderConflictError(
                "当前视频状态不支持提交审核",
                code="review_state_conflict",
                details={
                    "content_id": normalized_id,
                    "review_status": current_status,
                },
            )

        current_version = current.get("version")
        if (
            isinstance(current_version, bool)
            or not isinstance(current_version, int)
            or current_version != normalized_version
        ):
            raise ProviderConflictError(
                "审核版本已变化",
                code="review_version_conflict",
                details={
                    "content_id": normalized_id,
                    "expected_version": normalized_version,
                    "actual_version": current_version,
                },
            )

        changed_fields = self._changed_fields(current, normalized_payload)
        if not changed_fields:
            return current

        action = self._edit_action(
            normalized_id,
            normalized_submitter,
            normalized_version,
            normalized_payload,
        )
        result = self._call_05(action)
        result_status = result.get(
            "review_status",
            result.get("status"),
        )
        merged = {**current, **result}
        if result_status not in {None, ""}:
            merged["review_status"] = result_status
            merged.pop("status", None)
        return _normalize_video(
            merged,
            content_id=normalized_id,
        )

    def get_review_status(
        self,
        *,
        content_type: str,
        content_id: str,
    ) -> dict | None:
        _require_video_type(content_type)
        return self._read_video(_content_id(content_id))

    def approve(
        self,
        *,
        content_type: str,
        content_id: str,
        submitter_id: int,
        reviewer_id: int,
        reviewer_role: str,
        expected_version: int,
    ) -> dict:
        _require_video_type(content_type)
        normalized_id = _content_id(content_id)
        normalized_submitter = _positive_int(
            submitter_id,
            field="submitter_id",
        )
        normalized_reviewer = _positive_int(
            reviewer_id,
            field="reviewer_id",
        )
        if reviewer_role not in REVIEWER_ROLES:
            raise ProviderAccessDeniedError(
                "无审核权限",
                code="review_access_denied",
                details={"reviewer_role": reviewer_role},
            )
        normalized_version = _positive_int(
            expected_version,
            field="expected_version",
        )
        result = self._call_05(
            {
                "video_id": normalized_id,
                "action": "approve",
                "version": normalized_version,
                "submitter_id": normalized_submitter,
                "reviewer_id": normalized_reviewer,
                "reviewer_role": reviewer_role,
            }
        )
        return _normalize_video(
            {
                **result,
                "submitter_id": normalized_submitter,
                "rejection_opinion": None,
            },
            content_id=normalized_id,
        )

    def reject(
        self,
        *,
        content_type: str,
        content_id: str,
        submitter_id: int,
        reviewer_id: int,
        reviewer_role: str,
        expected_version: int,
        opinion: str,
    ) -> dict:
        _require_video_type(content_type)
        normalized_id = _content_id(content_id)
        normalized_submitter = _positive_int(
            submitter_id,
            field="submitter_id",
        )
        normalized_reviewer = _positive_int(
            reviewer_id,
            field="reviewer_id",
        )
        if reviewer_role not in REVIEWER_ROLES:
            raise ProviderAccessDeniedError(
                "无审核权限",
                code="review_access_denied",
                details={"reviewer_role": reviewer_role},
            )
        normalized_version = _positive_int(
            expected_version,
            field="expected_version",
        )
        normalized_opinion = _normalized_opinion(opinion)
        result = self._call_05(
            {
                "video_id": normalized_id,
                "action": "reject",
                "version": normalized_version,
                "submitter_id": normalized_submitter,
                "reviewer_id": normalized_reviewer,
                "reviewer_role": reviewer_role,
                "opinion": normalized_opinion,
            }
        )
        return _normalize_video(
            {
                **result,
                "submitter_id": normalized_submitter,
                "rejection_opinion": normalized_opinion,
            },
            content_id=normalized_id,
        )

    def edit(
        self,
        *,
        content_type: str,
        content_id: str,
        submitter_id: int,
        expected_version: int,
        payload: dict,
    ) -> dict:
        _require_video_type(content_type)
        normalized_id = _content_id(content_id)
        normalized_submitter = _positive_int(
            submitter_id,
            field="submitter_id",
        )
        normalized_version = _positive_int(
            expected_version,
            field="expected_version",
        )
        normalized_payload = _editable_payload(payload)
        result = self._call_05(
            self._edit_action(
                normalized_id,
                normalized_submitter,
                normalized_version,
                normalized_payload,
            )
        )
        return _normalize_video(
            {
                **result,
                "submitter_id": normalized_submitter,
            },
            content_id=normalized_id,
        )

    def list_review_items(self, content_type: str) -> list[dict]:
        _require_video_type(content_type)
        try:
            videos = get_teaching_video_provider().list_videos()
        except ProviderError:
            raise
        except Exception as error:
            raise _map_05_error(error) from error
        if not isinstance(videos, list):
            raise ProviderUnavailableError(
                "非遗视频列表不可用",
                code="review_source_unavailable",
                details={},
            )
        return [
            _normalize_video(video)
            for video in videos
            if isinstance(video, dict)
        ]

    def _read_video(self, content_id: str) -> dict | None:
        try:
            video = get_teaching_video_provider().get_video(content_id)
        except ProviderError:
            raise
        except Exception as error:
            raise _map_05_error(error) from error
        if video is None:
            return None
        if not isinstance(video, dict):
            raise ProviderUnavailableError(
                "非遗视频数据不可用",
                code="review_source_unavailable",
                details={"content_id": content_id},
            )
        return _normalize_video(video, content_id=content_id)

    @staticmethod
    def _changed_fields(current: dict, payload: dict) -> set[str]:
        changed = set()
        for field in ("title", "media_url"):
            if field not in payload:
                continue
            current_value = current.get(field)
            next_value = payload[field]
            if isinstance(current_value, str) and isinstance(next_value, str):
                differs = current_value.strip() != next_value.strip()
            else:
                differs = current_value != next_value
            if differs:
                changed.add(field)
        return changed

    @staticmethod
    def _edit_action(
        content_id: str,
        submitter_id: int,
        expected_version: int,
        payload: dict,
    ) -> dict:
        action = {
            "video_id": content_id,
            "action": "edit",
            "actor_role": "teacher",
            "actor_id": submitter_id,
            "submitter_id": submitter_id,
            "version": expected_version,
        }
        for field in ("title", "media_url"):
            if field in payload:
                action[field] = payload[field]
        return action

    @staticmethod
    def _call_05(action: dict) -> dict:
        from app.handcraft_inheritance.admin_actions import (
            apply_video_review,
        )

        try:
            result = apply_video_review(dict(action))
        except ProviderError:
            raise
        except Exception as error:
            raise _map_05_error(error) from error
        if not isinstance(result, dict):
            raise ProviderUnavailableError(
                "非遗视频审核服务暂不可用",
                code="review_source_unavailable",
                details={},
            )
        return dict(result)


class CompositeContentReviewProvider:
    def __init__(
        self,
        *,
        database_provider: DatabaseContentReviewProvider | None = None,
        handcraft_adapter: HandcraftTeachingVideoReviewAdapter | None = None,
    ) -> None:
        self.database_provider = (
            database_provider
            if database_provider is not None
            else DatabaseContentReviewProvider()
        )
        self.handcraft_adapter = (
            handcraft_adapter
            if handcraft_adapter is not None
            else HandcraftTeachingVideoReviewAdapter()
        )

    def submit_for_review(
        self,
        *,
        content_type: str,
        content_id: str,
        submitter_id: int,
        expected_version: int,
        payload: dict,
    ) -> dict:
        return self._delegate(content_type).submit_for_review(
            content_type=content_type,
            content_id=content_id,
            submitter_id=submitter_id,
            expected_version=expected_version,
            payload=payload,
        )

    def get_review_status(
        self,
        *,
        content_type: str,
        content_id: str,
    ) -> dict | None:
        return self._delegate(content_type).get_review_status(
            content_type=content_type,
            content_id=content_id,
        )

    def approve(
        self,
        *,
        content_type: str,
        content_id: str,
        submitter_id: int,
        reviewer_id: int,
        reviewer_role: str,
        expected_version: int,
    ) -> dict:
        return self._delegate(content_type).approve(
            content_type=content_type,
            content_id=content_id,
            submitter_id=submitter_id,
            reviewer_id=reviewer_id,
            reviewer_role=reviewer_role,
            expected_version=expected_version,
        )

    def reject(
        self,
        *,
        content_type: str,
        content_id: str,
        submitter_id: int,
        reviewer_id: int,
        reviewer_role: str,
        expected_version: int,
        opinion: str,
    ) -> dict:
        return self._delegate(content_type).reject(
            content_type=content_type,
            content_id=content_id,
            submitter_id=submitter_id,
            reviewer_id=reviewer_id,
            reviewer_role=reviewer_role,
            expected_version=expected_version,
            opinion=opinion,
        )

    def edit(
        self,
        *,
        content_type: str,
        content_id: str,
        submitter_id: int,
        expected_version: int,
        payload: dict,
    ) -> dict:
        return self._delegate(content_type).edit(
            content_type=content_type,
            content_id=content_id,
            submitter_id=submitter_id,
            expected_version=expected_version,
            payload=payload,
        )

    def list_review_items(
        self,
        content_type: str | None = None,
    ) -> list[dict]:
        if content_type is None:
            return [
                *self.database_provider.list_review_items(),
                *self.handcraft_adapter.list_review_items(
                    VIDEO_CONTENT_TYPE
                ),
            ]
        return self._delegate(content_type).list_review_items(content_type)

    def _delegate(self, content_type: object):
        if content_type in DATABASE_CONTENT_TYPES:
            return self.database_provider
        if content_type == VIDEO_CONTENT_TYPE:
            return self.handcraft_adapter
        raise _validation_error(
            "content_type is not supported",
            "review_type_invalid",
            content_type=content_type,
        )
