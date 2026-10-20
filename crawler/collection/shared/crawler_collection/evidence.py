"""Raw evidence interface. Persistence lands in ticket 03."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field


SENSITIVE_HEADERS = frozenset(
    {
        "authorization",
        "cookie",
        "proxy-authorization",
        "set-cookie",
        "x-amz-credential",
        "x-amz-signature",
    }
)


def sanitize_headers(headers):
    return {
        str(key).lower(): (
            "[redacted]" if str(key).lower() in SENSITIVE_HEADERS else str(value)
        )
        for key, value in (headers or {}).items()
    }


def sha256_bytes(body):
    return hashlib.sha256(body).hexdigest()


@dataclass(frozen=True)
class RawEvidence:
    source_id: str
    request_url: str
    final_url: str
    body: bytes
    content_type: str
    status_code: int | None = 200
    source_url: str | None = None
    long_term_url: str | None = None
    detail_url: str | None = None
    detail_url_status: str = "missing"
    fetch_url: str | None = None
    locator: str | None = None
    access_level: str = "public"
    rights_status: str = "unknown"
    attribution_required: bool = False
    attribution_text: str | None = None
    rights_evidence_url: str | None = None
    retrieved_at: str | None = None
    started_at: str | None = None
    fetch_status: str = "ok"
    error_message: str | None = None
    request_headers: dict = field(default_factory=dict)
    response_headers: dict = field(default_factory=dict)
    robots_decision: str = "unknown"
    run_id: str | None = None
    declared_size: int | None = None
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.detail_url_status == "direct" and not (
            self.detail_url or ""
        ).strip():
            raise ValueError("detail_url is required when status is direct")
        if self.detail_url_status == "missing" and not (
            self.locator or self.request_url
        ).strip():
            raise ValueError("locator is required when status is missing")

    @property
    def sha256(self):
        return sha256_bytes(self.body)

    def to_mapping(self):
        payload = asdict(self)
        payload.pop("body")
        payload["request_headers"] = sanitize_headers(self.request_headers)
        payload["response_headers"] = sanitize_headers(self.response_headers)
        payload["byte_size"] = len(self.body)
        payload["sha256"] = self.sha256
        return payload
