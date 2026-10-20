"""Crawler database writer boundary. Business database modules are forbidden."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .evidence import RawEvidence
from .items import validate_item


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
        return sqlite3.connect(self.path)

    def append_raw(self, evidence: RawEvidence):
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO raw_fetches (
                    source_id, request_url, final_url, source_url,
                    long_term_url, detail_url_status, locator,
                    request_headers, status_code, content_type,
                    response_headers, body_bytes, body_sha256, body_text,
                    body_saved, access_level, rights_status,
                    attribution_required, robots_decision, fetch_status,
                    started_at, retrieved_at, metadata_json, created_at
                ) VALUES (?, ?, ?, ?, ?, 'missing', ?, ?, ?, ?, ?, ?, ?, NULL,
                          0, 'public', 'unknown', 0, ?, 'ok', ?, ?, ?, ?)
                """,
                (
                    evidence.source_id,
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
                    evidence.robots_decision,
                    "2026-01-01T00:00:00+00:00",
                    "2026-01-01T00:00:00+00:00",
                    json.dumps(evidence.metadata),
                    "2026-01-01T00:00:00+00:00",
                ),
            )
            return cursor.lastrowid

    def write_stage(self, item, *, raw_evidence_id):
        payload = validate_item(item)
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO stage_source_items (
                    raw_fetch_id, source_id, source_item_id, source_url,
                    long_term_url, detail_url, detail_url_status, fetch_url,
                    locator, rights_status, attribution_required,
                    attribution_text, rights_evidence_url, title,
                    retrieved_at, content_hash, parser_version, extra
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            return cursor.lastrowid

    def write_candidate(self, item):
        """Ticket 03 completes candidate normalization and upsert by entity."""
        return validate_item(item)
