"""The serializable contract between a Spider and the shared Pipeline."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, timezone
from typing import Any


CANDIDATE_STATUSES = frozenset({"candidate", "blocked", "deferred"})
DETAIL_URL_STATUSES = frozenset({"direct", "missing"})
FORBIDDEN_ITEM_FIELDS = frozenset(
    {"response", "selector", "connection", "cookie", "authorization"}
)


@dataclass
class CollectionItem:
    source_id: str
    source_item_id: str
    source_url: str
    long_term_url: str
    detail_url: str | None
    detail_url_status: str
    run_id: str
    mode: str
    rights_status: str
    locator: str | None = None
    fetch_url: str | None = None
    title: str | None = None
    body_text: str | None = None
    published_at: str | None = None
    attribution_required: bool = False
    attribution_text: str | None = None
    rights_evidence_url: str | None = None
    content_type: str | None = None
    content_hash: str | None = None
    parser_version: str = "1"
    retrieved_at: str | None = None
    source_index: int | None = None
    candidate_status: str = "candidate"
    candidate_reason: str | None = None
    raw_evidence_id: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)


def item_from_mapping(payload, *, source_id, response, list_item=None):
    merged = dict(list_item or {})
    merged.update(payload or {})
    merged.setdefault("source_id", source_id)
    merged.setdefault("run_id", "live")
    merged.setdefault("mode", "live")
    merged.setdefault("rights_status", "attribution-required")
    merged.setdefault("retrieved_at", datetime.now(timezone.utc).isoformat())
    merged.setdefault(
        "raw_evidence_id", response.meta.get("raw_evidence_id")
    )
    merged.setdefault(
        "content_hash", response.meta.get("raw_evidence_id")
    )
    known = {field.name for field in fields(CollectionItem)}
    extra = dict(merged.get("extra") or {})
    unknown = {
        key: value
        for key, value in merged.items()
        if key not in known and key != "extra"
    }
    extra.update(unknown)
    merged = {key: value for key, value in merged.items() if key in known}
    merged["extra"] = extra
    return CollectionItem(**merged)


def validate_item(item: CollectionItem | dict) -> dict[str, Any]:
    payload = asdict(item) if isinstance(item, CollectionItem) else dict(item)
    payload.setdefault("candidate_status", "candidate")
    payload.setdefault("candidate_reason", None)
    payload.setdefault("parser_version", "1")
    payload.setdefault("extra", {})
    payload.setdefault("locator", None)
    payload.setdefault("fetch_url", None)
    payload.setdefault("title", None)
    payload.setdefault("body_text", None)
    payload.setdefault("published_at", None)
    payload.setdefault("attribution_required", False)
    payload.setdefault("attribution_text", None)
    payload.setdefault("rights_evidence_url", None)
    payload.setdefault("content_type", None)
    payload.setdefault("content_hash", None)
    payload.setdefault("retrieved_at", None)
    payload.setdefault("source_index", None)
    payload.setdefault("raw_evidence_id", None)
    required = (
        "source_id",
        "source_item_id",
        "source_url",
        "long_term_url",
        "run_id",
        "mode",
        "rights_status",
    )
    for name in required:
        if not str(payload.get(name) or "").strip():
            raise ValueError(f"{name} is required")

    status = str(payload.get("detail_url_status") or "").strip()
    if status not in DETAIL_URL_STATUSES:
        raise ValueError(
            "detail_url_status must be either 'direct' or 'missing'"
        )
    if status == "direct" and not str(payload.get("detail_url") or "").strip():
        raise ValueError("detail_url is required when detail_url_status is direct")
    if status == "missing" and not str(payload.get("locator") or "").strip():
        raise ValueError("locator is required when detail_url_status is missing")

    candidate_status = str(payload.get("candidate_status") or "").strip()
    if candidate_status not in CANDIDATE_STATUSES:
        raise ValueError(
            "candidate_status must be candidate, blocked, or deferred"
        )

    forbidden = FORBIDDEN_ITEM_FIELDS.intersection(
        key.lower() for key in payload
    )
    if forbidden:
        raise ValueError(
            "non-serializable fields are not allowed: "
            + ", ".join(sorted(forbidden))
        )
    return payload
