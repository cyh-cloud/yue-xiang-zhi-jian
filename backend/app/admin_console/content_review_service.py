from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app.admin_console.errors import (
    ProviderAccessDeniedError,
    ProviderNotFoundError,
    ProviderUnavailableError,
    ProviderValidationError,
)
from app.content_review.providers import get_content_review_provider


CONTENT_TYPES = (
    "course_video",
    "job_position",
    "handcraft_teaching_video",
)
CONTENT_TYPE_SET = frozenset(CONTENT_TYPES)
REVIEWER_ROLES = frozenset({"admin", "super_admin"})
SHANGHAI = ZoneInfo("Asia/Shanghai")


def _content_type(value: str | None) -> str | None:
    if value is not None and value not in CONTENT_TYPE_SET:
        raise ProviderValidationError(
            "内容类型不正确",
            code="review_type_invalid",
            details={"content_type": value},
        )
    return value


def _updated_at(value: object) -> datetime:
    if value is None or not str(value).strip():
        return datetime.min.replace(tzinfo=timezone.utc)

    text = str(value).strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as error:
        raise ProviderUnavailableError(
            "审核更新时间格式无效",
            code="review_source_unavailable",
            details={"updated_at": text},
        ) from error

    if parsed.tzinfo is None or parsed.utcoffset() is None:
        parsed = parsed.replace(tzinfo=SHANGHAI)
    return parsed.astimezone(timezone.utc)


def _counts(rows: list[dict]) -> dict[str, int]:
    counts = {content_type: 0 for content_type in CONTENT_TYPES}
    for item in rows:
        content_type = item.get("content_type")
        if (
            content_type in counts
            and item.get("review_status") == "pending"
        ):
            counts[content_type] += 1
    return counts


def _actor(value: dict) -> tuple[int, str]:
    if not isinstance(value, dict):
        raise ProviderAccessDeniedError(
            "无审核权限",
            code="review_access_denied",
            details={},
        )

    actor_id = value.get("id")
    if (
        isinstance(actor_id, bool)
        or not isinstance(actor_id, int)
        or actor_id <= 0
    ):
        raise ProviderAccessDeniedError(
            "无审核权限",
            code="review_access_denied",
            details={},
        )

    role = value.get("role")
    if role not in REVIEWER_ROLES:
        raise ProviderAccessDeniedError(
            "无审核权限",
            code="review_access_denied",
            details={"reviewer_role": role},
        )
    return actor_id, role


def _opinion(value: object) -> str:
    if not isinstance(value, str):
        raise ProviderValidationError(
            "驳回意见必须是文本",
            code="review_opinion_invalid",
            details={"field": "opinion"},
        )
    normalized = value.strip()
    if not 1 <= len(normalized) <= 500:
        raise ProviderValidationError(
            "驳回意见长度必须为 1 至 500 个字符",
            code="review_opinion_invalid",
            details={
                "field": "opinion",
                "min_length": 1,
                "max_length": 500,
            },
        )
    return normalized


def _review_record(content_type: str, content_id: str) -> dict:
    record = get_content_review_provider().get_review_status(
        content_type=content_type,
        content_id=content_id,
    )
    if record is None:
        raise ProviderNotFoundError(
            "审核记录不存在",
            code="review_not_found",
            details={
                "content_type": content_type,
                "content_id": content_id,
            },
        )
    return record


def list_review_queue(content_type: str | None = None) -> dict:
    normalized_type = _content_type(content_type)
    rows = list(
        get_content_review_provider().list_review_items(normalized_type)
    )
    rows.sort(
        key=lambda item: (
            _updated_at(item.get("updated_at")),
            str(item.get("content_type", "")),
            str(item.get("content_id", "")),
        )
    )
    return {"items": rows, "counts": _counts(rows)}


def approve_review(
    actor: dict,
    *,
    content_type: str,
    content_id: str,
    expected_version: int,
) -> dict:
    reviewer_id, reviewer_role = _actor(actor)
    normalized_type = _content_type(content_type)
    record = _review_record(normalized_type, content_id)
    return get_content_review_provider().approve(
        content_type=normalized_type,
        content_id=content_id,
        submitter_id=record["submitter_id"],
        reviewer_id=reviewer_id,
        reviewer_role=reviewer_role,
        expected_version=expected_version,
    )


def reject_review(
    actor: dict,
    *,
    content_type: str,
    content_id: str,
    expected_version: int,
    opinion: str,
) -> dict:
    reviewer_id, reviewer_role = _actor(actor)
    normalized_type = _content_type(content_type)
    normalized_opinion = _opinion(opinion)
    record = _review_record(normalized_type, content_id)
    return get_content_review_provider().reject(
        content_type=normalized_type,
        content_id=content_id,
        submitter_id=record["submitter_id"],
        reviewer_id=reviewer_id,
        reviewer_role=reviewer_role,
        expected_version=expected_version,
        opinion=normalized_opinion,
    )


__all__ = [
    "approve_review",
    "list_review_queue",
    "reject_review",
]
