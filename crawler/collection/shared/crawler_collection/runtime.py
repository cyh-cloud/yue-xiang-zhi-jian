"""Shared collection runtime. All writes stop at the crawler database."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

from .admission import evaluate_admission
from .database import CollectionDatabase
from .evidence import RawEvidence, sanitize_headers, sha256_bytes
from .items import validate_item
from crawler.pipeline import database as crawler_database


DEFAULT_MAX_DOWNLOAD_BYTES = 100 * 1024 * 1024


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

    def persist_raw(self, evidence: RawEvidence):
        self.download_root.mkdir(parents=True, exist_ok=True)
        body = bytes(evidence.body)
        digest = sha256_bytes(body)
        host = urlparse(evidence.request_url).netloc or "fixture.local"
        domain_dir = self.download_root / host
        domain_dir.mkdir(parents=True, exist_ok=True)
        file_name = evidence.metadata.get("file_name") or "response.bin"
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
            target.write_bytes(body)
            file_path = target.relative_to(self.download_root).as_posix()
            download_status = "saved"
            oversize_note = None

        request_headers = sanitize_headers(evidence.request_headers)
        response_headers = sanitize_headers(evidence.response_headers)
        conn = self.database.connect()
        try:
            cursor = conn.execute(
                """
                INSERT INTO raw_fetches (
                    source_id, request_url, final_url, source_url,
                    long_term_url, detail_url_status, locator,
                    request_headers, status_code, content_type,
                    response_headers, body_bytes, body_sha256, body_path,
                    body_saved, access_level, rights_status,
                    attribution_required, robots_decision, fetch_status,
                    started_at, retrieved_at, metadata_json, created_at
                ) VALUES (?, ?, ?, ?, ?, 'missing', 'fixture', ?, ?, ?, ?,
                          ?, ?, ?, ?, 'public', 'unknown', 0, ?, 'ok',
                          '2026-01-01T00:00:00+00:00',
                          '2026-01-01T00:00:00+00:00', ?, 
                          '2026-01-01T00:00:00+00:00')
                """,
                (
                    evidence.source_id,
                    evidence.request_url,
                    evidence.final_url,
                    evidence.request_url,
                    evidence.request_url,
                    json.dumps(request_headers),
                    evidence.status_code,
                    evidence.content_type,
                    json.dumps(response_headers),
                    len(body),
                    digest,
                    file_path,
                    0 if oversize else 1,
                    evidence.robots_decision,
                    json.dumps(evidence.metadata, ensure_ascii=False),
                ),
            )
            raw_id = cursor.lastrowid
            conn.execute(
                """
                INSERT INTO raw_files (
                    raw_fetch_id, source_id, source_url, long_term_url,
                    detail_url_status, locator, rights_status,
                    attribution_required, rights_evidence_url, file_url,
                    final_url, file_path, file_name, mime_type, file_ext,
                    byte_size, sha256, access_level, download_status,
                    oversize_note, media_metadata, retrieved_at, created_at
                ) VALUES (?, ?, ?, ?, 'missing', 'fixture', 'unknown', 0,
                          NULL, ?, ?, ?, ?, ?, ?, ?, ?, 'public', ?, ?, ?,
                          '2026-01-01T00:00:00+00:00',
                          '2026-01-01T00:00:00+00:00')
                """,
                (
                    raw_id,
                    evidence.source_id,
                    evidence.request_url,
                    evidence.request_url,
                    evidence.request_url,
                    evidence.final_url,
                    file_path,
                    file_name,
                    evidence.content_type,
                    Path(file_name).suffix or None,
                    len(body),
                    digest,
                    download_status,
                    oversize_note,
                    json.dumps(evidence.metadata, ensure_ascii=False),
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return raw_id

    def write_item(self, item, *, raw_evidence_id, admission=None):
        payload = validate_item(item)
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
                    payload["retrieved_at"] or "2026-01-01T00:00:00+00:00",
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
            self._upsert_candidate(conn, payload)
            conn.commit()
        finally:
            conn.close()
        return {"candidate_status": "candidate", "candidate_reason": None}

    def _upsert_candidate(self, conn, item):
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
            "candidate",
            None,
            "2026-01-01T00:00:00+00:00",
            "2026-01-01T00:00:00+00:00",
            "2026-01-01T00:00:00+00:00",
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
