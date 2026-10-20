"""Shared collection runtime. All writes stop at the crawler database."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from .admission import evaluate_admission
from .database import CollectionDatabase
from .evidence import RawEvidence, sanitize_headers, sha256_bytes
from .items import validate_item
from .registry import load_registry
from crawler.pipeline import database as crawler_database


DEFAULT_MAX_DOWNLOAD_BYTES = 100 * 1024 * 1024


def _now():
    return datetime.now(timezone.utc).isoformat()


def _insert_sql(table, values):
    columns = ", ".join(values)
    placeholders = ", ".join("?" for _ in values)
    return (
        f"INSERT INTO {table} ({columns}) VALUES ({placeholders})",
        tuple(values.values()),
    )


class CollectionRuntime:
    def __init__(
        self,
        *,
        database_path,
        download_root,
        registry_path=None,
        max_download_bytes=DEFAULT_MAX_DOWNLOAD_BYTES,
    ):
        self.database_path = Path(database_path)
        self.download_root = Path(download_root)
        self.registry_path = registry_path
        self.max_download_bytes = max_download_bytes
        self.database = CollectionDatabase(self.database_path)
        conn = crawler_database.connect(self.database_path)
        conn.close()

    def evidence_from_fixture(
        self, *, source_id, body, request_url, content_type, run_id
    ):
        return RawEvidence(
            source_id=source_id,
            request_url=request_url,
            final_url=request_url,
            source_url=request_url,
            long_term_url=request_url,
            locator=request_url,
            body=body,
            content_type=content_type,
            run_id=run_id,
            retrieved_at=_now(),
            started_at=_now(),
        )

    def persist_raw(self, evidence: RawEvidence):
        self.download_root.mkdir(parents=True, exist_ok=True)
        body = bytes(evidence.body)
        digest = sha256_bytes(body)
        host = urlparse(evidence.request_url).netloc or "fixture.local"
        domain_dir = self.download_root / host
        domain_dir.mkdir(parents=True, exist_ok=True)
        file_name = evidence.metadata.get("file_name") or (
            f"response-{digest[:12]}.bin"
        )
        file_name = Path(file_name).name
        declared_size = evidence.declared_size
        oversize = len(body) > self.max_download_bytes or (
            declared_size is not None
            and int(declared_size) > self.max_download_bytes
        )
        if oversize:
            note = domain_dir / "OVERSIZE.md"
            with note.open("a", encoding="utf-8") as handle:
                handle.write(
                    f"- {evidence.request_url}: actual {len(body)} bytes exceeds "
                    f"{self.max_download_bytes} bytes\n"
                )
            file_path = note.relative_to(self.download_root).as_posix()
            download_status = "oversize"
            oversize_note = (
                f"actual {len(body)} bytes exceeds "
                f"{self.max_download_bytes} bytes"
            )
        else:
            target = domain_dir / file_name
            if target.exists() and target.read_bytes() != body:
                target = domain_dir / f"{digest[:12]}-{file_name}"
            target.write_bytes(body)
            file_path = target.relative_to(self.download_root).as_posix()
            download_status = "saved"
            oversize_note = None

        request_headers = sanitize_headers(evidence.request_headers)
        response_headers = sanitize_headers(evidence.response_headers)
        registry = load_registry(self.registry_path)
        source = registry.get(evidence.source_id) or {}
        access_level = evidence.access_level or source.get("access") or "public"
        rights_status = evidence.rights_status
        if rights_status == "unknown":
            rights_status = source.get("rights_status") or "unknown"
        attribution_required = evidence.attribution_required or bool(
            source.get("attribution_required")
        )
        attribution_text = (
            evidence.attribution_text
            or source.get("attribution_text")
            or source.get("name")
        )
        rights_evidence_url = (
            evidence.rights_evidence_url
            or source.get("rights_evidence_url")
        )
        source_url = evidence.source_url or evidence.request_url
        long_term_url = evidence.long_term_url or source_url
        locator = evidence.locator or evidence.request_url
        retrieved_at = evidence.retrieved_at or _now()
        started_at = evidence.started_at or retrieved_at
        conn = self.database.connect()
        try:
            cursor = conn.execute(
                """
                INSERT INTO raw_fetches (
                    source_id, request_url, final_url, source_url,
                    long_term_url, detail_url, detail_url_status, fetch_url,
                    locator,
                    request_headers, status_code, content_type,
                    response_headers, body_bytes, body_sha256, body_path,
                    body_saved, access_level, rights_status,
                    attribution_required, robots_decision, fetch_status,
                    error_message, started_at, retrieved_at, metadata_json,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                          ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    evidence.source_id,
                    evidence.request_url,
                    evidence.final_url,
                    source_url,
                    long_term_url,
                    evidence.detail_url,
                    evidence.detail_url_status,
                    evidence.fetch_url,
                    locator,
                    json.dumps(request_headers),
                    evidence.status_code,
                    evidence.content_type,
                    json.dumps(response_headers),
                    len(body),
                    digest,
                    file_path,
                    0 if oversize else 1,
                    access_level,
                    rights_status,
                    1 if attribution_required else 0,
                    evidence.robots_decision,
                    evidence.fetch_status,
                    evidence.error_message,
                    started_at,
                    retrieved_at,
                    json.dumps(evidence.metadata, ensure_ascii=False),
                    retrieved_at,
                ),
            )
            raw_id = cursor.lastrowid
            raw_file_sql, raw_file_params = _insert_sql(
                "raw_files",
                {
                    "raw_fetch_id": raw_id,
                    "source_id": evidence.source_id,
                    "source_url": source_url,
                    "long_term_url": long_term_url,
                    "detail_url": evidence.detail_url,
                    "detail_url_status": evidence.detail_url_status,
                    "fetch_url": evidence.fetch_url,
                    "locator": locator,
                    "rights_status": rights_status,
                    "attribution_required": (
                        1 if attribution_required else 0
                    ),
                    "rights_evidence_url": rights_evidence_url,
                    "file_url": evidence.fetch_url or evidence.request_url,
                    "final_url": evidence.final_url,
                    "file_path": file_path,
                    "file_name": file_name,
                    "mime_type": evidence.content_type,
                    "file_ext": Path(file_name).suffix or None,
                    "byte_size": len(body),
                    "sha256": digest,
                    "access_level": access_level,
                    "download_status": download_status,
                    "oversize_note": oversize_note,
                    "media_metadata": json.dumps(
                        evidence.metadata, ensure_ascii=False
                    ),
                    "retrieved_at": retrieved_at,
                    "created_at": retrieved_at,
                },
            )
            conn.execute(raw_file_sql, raw_file_params)
            conn.commit()
        finally:
            conn.close()
        return raw_id

    def write_item(self, item, *, raw_evidence_id, admission=None):
        payload = validate_item(item)
        now = payload.get("retrieved_at") or _now()
        payload["retrieved_at"] = now
        decision = admission or evaluate_admission(
            item, registry_path=self.registry_path
        )
        conn = self.database.connect()
        try:
            conn.execute(
                """
                INSERT INTO stage_source_items (
                    raw_fetch_id, source_id, source_item_id, source_url,
                    long_term_url, detail_url, detail_url_status, fetch_url,
                    locator, rights_status, attribution_required,
                    attribution_text, rights_evidence_url, title,
                    retrieved_at, content_hash, parser_version, extra
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(raw_fetch_id, source_item_id) DO UPDATE SET
                    title=excluded.title,
                    extra=excluded.extra
                """,
                (
                    raw_evidence_id,
                    payload["source_id"],
                    payload["source_item_id"],
                    payload["source_url"],
                    payload["long_term_url"],
                    payload["detail_url"],
                    payload["detail_url_status"],
                    payload["fetch_url"],
                    payload["locator"],
                    payload["rights_status"],
                    1 if payload["attribution_required"] else 0,
                    payload["attribution_text"],
                    payload["rights_evidence_url"],
                    payload["title"] or payload["source_item_id"],
                    payload["retrieved_at"],
                    payload["content_hash"] or payload["source_item_id"],
                    payload["parser_version"],
                    json.dumps(payload["extra"], ensure_ascii=False),
                ),
            )
            if not decision.allowed:
                conn.commit()
                return {
                    "candidate_status": "blocked",
                    "candidate_reason": decision.reason,
                }
            self._upsert_candidate(conn, payload, now=now)
            conn.commit()
        finally:
            conn.close()
        return {"candidate_status": "candidate", "candidate_reason": None}

    def _upsert_candidate(self, conn, item, *, now):
        source_id = item["source_id"]
        if source_id in {"aqsc-moa", "cnipa"}:
            table = "std_agri_products"
            fields = (
                "cert_type",
                "product_name",
                "normalized_name",
            )
            values = (
                item["extra"].get("cert_type", "公告"),
                item["title"],
                item["title"],
            )
        elif source_id in {"nzrc", "nongmuhr"}:
            table = "std_jobs"
            fields = ("title",)
            values = (item["title"],)
        elif source_id == "dialect-org":
            table = "std_dialect_points"
            fields = ("region_raw",)
            values = (item["extra"].get("region_raw", "未知地区"),)
        elif source_id == "cass-linguistics":
            table = "std_research_articles"
            fields = ("title", "body_access")
            values = (item["title"], "public")
        elif source_id == "feiyiw":
            table = "std_ich_articles"
            fields = ("title",)
            values = (item["title"],)
        else:
            table = "std_ich_projects"
            fields = ("name",)
            values = (item["title"],)

        common_fields = (
            "source_id",
            "source_item_id",
            "source_url",
            "long_term_url",
            "detail_url",
            "detail_url_status",
            "locator",
            "rights_status",
            "attribution_required",
            "attribution_text",
            "rights_evidence_url",
            "content_hash",
            "confidence",
            "license_or_usage",
            "publish_status",
            "candidate_status",
            "candidate_reason",
            "retrieved_at",
            "first_seen_at",
            "last_seen_at",
        )
        common_values = (
            item["source_id"],
            item["source_item_id"],
            item["source_url"],
            item["long_term_url"],
            item["detail_url"],
            item["detail_url_status"],
            item["locator"],
            item["rights_status"],
            1 if item["attribution_required"] else 0,
            item["attribution_text"],
            item["rights_evidence_url"],
            item["content_hash"] or item["source_item_id"],
            "medium",
            item["rights_status"],
            "draft",
            item.get("candidate_status") or "candidate",
            item.get("candidate_reason"),
            now,
            now,
            now,
        )
        columns = common_fields + fields
        placeholders = ", ".join("?" for _ in columns)
        updates = ", ".join(
            f"{name}=excluded.{name}"
            for name in columns
            if name not in {"source_id", "source_item_id", "first_seen_at"}
        )
        conn.execute(
            f"""
            INSERT INTO {table} ({", ".join(columns)})
            VALUES ({placeholders})
            ON CONFLICT(source_id, source_item_id) DO UPDATE SET {updates}
            """,
            common_values + values,
        )
