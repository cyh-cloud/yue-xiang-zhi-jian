import hashlib
import json
import mimetypes
import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse


TEXT_CONTENT_TYPES = {
    "application/json",
    "application/xml",
    "text/csv",
    "text/html",
    "text/plain",
}
SENSITIVE_HEADERS = {
    "authorization",
    "cookie",
    "proxy-authorization",
    "set-cookie",
    "x-amz-credential",
    "x-amz-signature",
}


@dataclass(frozen=True)
class RawEvidence:
    source_id: str
    key: str
    request_url: str
    final_url: str
    source_url: str
    long_term_url: str
    detail_url: str | None
    detail_url_status: str
    fetch_url: str | None
    locator: str | None
    body: bytes
    content_type: str
    file_url: str | None = None
    file_name: str | None = None
    status_code: int | None = 200
    request_headers: dict = field(default_factory=dict)
    response_headers: dict = field(default_factory=dict)
    access_level: str = "public"
    rights_status: str = "unknown"
    attribution_required: bool = False
    attribution_text: str | None = None
    rights_evidence_url: str | None = None
    robots_decision: str = "unknown"
    fetch_status: str = "ok"
    error_message: str | None = None
    duration_ms: int | None = 0
    declared_size: int | None = None
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        validate_detail_locator(
            self.detail_url_status,
            self.detail_url,
            self.locator,
        )


def validate_detail_locator(detail_url_status, detail_url=None, locator=None):
    status = (detail_url_status or "").strip()
    if status not in {"direct", "missing"}:
        raise ValueError(
            "detail_url_status must be either 'direct' or 'missing'"
        )
    if status == "missing" and not (locator or "").strip():
        raise ValueError("locator is required when detail_url_status is missing")


def sha256_bytes(body):
    return hashlib.sha256(body).hexdigest()


def sanitize_headers(headers):
    sanitized = {}
    for key, value in (headers or {}).items():
        lowered = str(key).lower()
        sanitized[lowered] = (
            "[redacted]" if lowered in SENSITIVE_HEADERS else str(value)
        )
    return sanitized


def guess_content_type(file_name, default="application/octet-stream"):
    guessed, _ = mimetypes.guess_type(file_name or "")
    return guessed or default


def _safe_name(value):
    name = Path(value or "response.bin").name
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)


def _relative(path, root):
    return path.relative_to(root).as_posix()


def _write_oversize_note(domain_dir, evidence, max_bytes):
    note = domain_dir / "OVERSIZE.md"
    with note.open("a", encoding="utf-8") as handle:
        handle.write(
            f"- {evidence.request_url}: actual {len(evidence.body)} bytes "
            f"exceeds {max_bytes} bytes\n"
        )
    return note


def persist_raw_evidence(conn, evidence, download_root, max_bytes, retrieved_at):
    validate_detail_locator(
        evidence.detail_url_status,
        evidence.detail_url,
        evidence.locator,
    )
    body = bytes(evidence.body)
    digest = sha256_bytes(body)
    parsed = urlparse(evidence.request_url)
    domain = parsed.netloc or "fixture.local"
    domain_dir = Path(download_root) / domain
    domain_dir.mkdir(parents=True, exist_ok=True)

    content_type = evidence.content_type or guess_content_type(evidence.file_name)
    extension = Path(evidence.file_name or urlparse(evidence.request_url).path).suffix
    file_name = _safe_name(
        evidence.file_name or f"response-{digest[:12]}{extension or '.bin'}"
    )
    declared_size = (
        int(evidence.declared_size)
        if evidence.declared_size is not None
        else None
    )
    actual_size = len(body)
    oversize = actual_size > max_bytes or (
        declared_size is not None and declared_size > max_bytes
    )
    if oversize:
        note = _write_oversize_note(domain_dir, evidence, max_bytes)
        body_path = _relative(note, download_root)
        saved = 0
        download_status = "oversize"
    else:
        target = domain_dir / file_name
        if target.exists() and target.read_bytes() != body:
            target = domain_dir / f"{digest[:12]}-{file_name}"
        target.write_bytes(body)
        body_path = _relative(target, download_root)
        file_name = target.name
        saved = 1
        download_status = "saved"

    body_text = None
    if (
        saved
        and content_type.split(";", 1)[0].strip().lower() in TEXT_CONTENT_TYPES
        and len(body) <= 1024 * 1024
    ):
        body_text = body.decode("utf-8", errors="replace")

    request_headers = sanitize_headers(evidence.request_headers)
    response_headers = sanitize_headers(evidence.response_headers)
    metadata = dict(evidence.metadata)
    metadata.setdefault("evidence_key", evidence.key)
    cursor = conn.execute(
        """
        INSERT INTO raw_fetches (
            source_id, job_key, request_url, final_url, source_url,
            long_term_url, detail_url, detail_url_status, fetch_url, locator,
            request_method, request_headers, status_code, content_type,
            response_headers, body_bytes, body_sha256, body_path, body_text,
            body_saved, access_level, rights_status, attribution_required,
            attribution_text, rights_evidence_url, robots_decision,
            fetch_status, error_message, started_at, retrieved_at,
            duration_ms, metadata_json, created_at
        ) VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'GET', ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        """,
        (
            evidence.source_id,
            evidence.metadata.get("job_key"),
            evidence.request_url,
            evidence.final_url or evidence.request_url,
            evidence.source_url or evidence.request_url,
            evidence.long_term_url or evidence.source_url or evidence.request_url,
            evidence.detail_url,
            evidence.detail_url_status,
            evidence.fetch_url,
            evidence.locator,
            json.dumps(request_headers, ensure_ascii=False, sort_keys=True),
            evidence.status_code,
            content_type,
            json.dumps(response_headers, ensure_ascii=False, sort_keys=True),
            actual_size,
            digest,
            body_path,
            body_text,
            saved,
            evidence.access_level,
            evidence.rights_status,
            1 if evidence.attribution_required else 0,
            evidence.attribution_text,
            evidence.rights_evidence_url,
            evidence.robots_decision,
            evidence.fetch_status,
            evidence.error_message,
            retrieved_at,
            retrieved_at,
            evidence.duration_ms,
            json.dumps(metadata, ensure_ascii=False, sort_keys=True),
            retrieved_at,
        ),
    )
    raw_fetch_id = cursor.lastrowid
    media_metadata = {
        "fixture_path": metadata.get("fixture_path"),
        "fixture_sha256": metadata.get("fixture_sha256"),
        "page": metadata.get("page"),
        "media_kind": metadata.get("media_kind"),
    }
    conn.execute(
        """
        INSERT INTO raw_files (
            raw_fetch_id, source_id, source_url, long_term_url, detail_url,
            detail_url_status, fetch_url, locator, rights_status,
            attribution_required, attribution_text, rights_evidence_url,
            file_url, final_url, file_path, file_name, mime_type, file_ext,
            byte_size, sha256, access_level, download_status, oversize_note,
            media_metadata, retrieved_at, created_at
        ) VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?
        )
        """,
        (
            raw_fetch_id,
            evidence.source_id,
            evidence.source_url or evidence.request_url,
            evidence.long_term_url or evidence.source_url or evidence.request_url,
            evidence.detail_url,
            evidence.detail_url_status,
            evidence.fetch_url,
            evidence.locator,
            evidence.rights_status,
            1 if evidence.attribution_required else 0,
            evidence.attribution_text,
            evidence.rights_evidence_url,
            evidence.file_url
            or evidence.fetch_url
            or evidence.request_url,
            evidence.final_url or evidence.request_url,
            body_path,
            file_name,
            content_type,
            extension.lower() or None,
            actual_size,
            digest,
            evidence.access_level,
            download_status,
            (
                f"actual {actual_size} bytes"
                + (
                    f"; declared {declared_size} bytes"
                    if declared_size is not None
                    else ""
                )
                + f" exceeds {max_bytes} bytes"
                if oversize
                else None
            ),
            json.dumps(media_metadata, ensure_ascii=False, sort_keys=True),
            retrieved_at,
            retrieved_at,
        ),
    )
    return raw_fetch_id
