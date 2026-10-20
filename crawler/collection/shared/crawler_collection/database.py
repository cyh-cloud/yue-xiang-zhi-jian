"""Crawler database writer boundary. Business database modules are forbidden."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .evidence import RawEvidence
from .items import validate_item
from .schema import ensure_schema


FORBIDDEN_IMPORT_PREFIXES = (
    "backend",
    "crawler.pipeline.converter",
    "crawler.pipeline.database",
)


class CollectionDatabase:
    def __init__(self, path):
        self.path = Path(path)

    def connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path)
        conn.execute("PRAGMA foreign_keys = ON")
        ensure_schema(conn)
        return conn

    def append_raw(self, evidence: RawEvidence):
        conn = self.connect()
        try:
            with conn:
                return self._append_raw(conn, evidence)
        finally:
            conn.close()

    def _append_raw(self, conn, evidence):
            cursor = conn.execute(
                """
                INSERT INTO raw_fetches (
                    source_id, run_id, request_url, final_url, source_url,
                    long_term_url, detail_url_status, locator,
                    request_headers, status_code, content_type,
                    response_headers, body_bytes, body_sha256, body_text,
                    body_saved, access_level, rights_status,
                    attribution_required, robots_decision, fetch_status,
                    started_at, retrieved_at, metadata_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'missing', ?, ?, ?, ?, ?, ?, ?, NULL,
                          0, ?, ?, 0, ?, ?, ?, ?, ?, ?)
                """,
                (
                    evidence.source_id,
                    evidence.run_id or "legacy",
                    evidence.request_url,
                    evidence.final_url,
                    evidence.request_url,
                    evidence.request_url,
                    "fixture",
                    json.dumps(evidence.request_headers),
                    evidence.status_code,
                    evidence.content_type,
                    json.dumps(evidence.response_headers),
                    len(evidence.body),
                    evidence.sha256,
                    evidence.access_level or "unknown",
                    evidence.rights_status or "unknown",
                    evidence.robots_decision,
                    evidence.fetch_status,
                    "2026-01-01T00:00:00+00:00",
                    "2026-01-01T00:00:00+00:00",
                    json.dumps(evidence.metadata),
                    "2026-01-01T00:00:00+00:00",
                ),
            )
            return cursor.lastrowid

    def write_stage(self, item, *, raw_evidence_id):
        payload = validate_item(item)
        conn = self.connect()
        try:
            with conn:
                return self._write_stage(conn, payload, raw_evidence_id)
        finally:
            conn.close()

    def _write_stage(self, conn, payload, raw_evidence_id):
            cursor = conn.execute(
                """
                INSERT INTO stage_source_items (
                    raw_fetch_id, source_id, run_id, source_item_id, source_url,
                    long_term_url, detail_url, detail_url_status, fetch_url,
                    locator, rights_status, attribution_required,
                    attribution_text, rights_evidence_url, title,
                    retrieved_at, content_hash, parser_version, extra
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_id, source_item_id) DO UPDATE SET
                    raw_fetch_id=excluded.raw_fetch_id,
                    run_id=excluded.run_id,
                    source_url=excluded.source_url,
                    long_term_url=excluded.long_term_url,
                    detail_url=excluded.detail_url,
                    detail_url_status=excluded.detail_url_status,
                    fetch_url=excluded.fetch_url,
                    locator=excluded.locator,
                    rights_status=excluded.rights_status,
                    attribution_required=excluded.attribution_required,
                    attribution_text=excluded.attribution_text,
                    rights_evidence_url=excluded.rights_evidence_url,
                    title=excluded.title,
                    retrieved_at=excluded.retrieved_at,
                    content_hash=excluded.content_hash,
                    parser_version=excluded.parser_version,
                    extra=excluded.extra
                """,
                (
                    raw_evidence_id,
                    payload["source_id"],
                    payload["run_id"],
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
            return cursor.lastrowid

    def write_candidate(self, item):
        """Ticket 03 completes candidate normalization and upsert by entity."""
        return validate_item(item)
