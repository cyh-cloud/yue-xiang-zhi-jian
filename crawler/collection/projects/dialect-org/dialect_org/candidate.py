"""dialect-org point and lexeme candidate mapping."""

from __future__ import annotations

import json

from crawler.collection.shared.crawler_collection.candidate import (
    upsert_candidate,
)
from crawler.collection.shared.crawler_collection.evidence import sha256_bytes


POINT_FIELDS = (
    "region_raw",
    "province",
    "city",
    "county",
    "dialect_name",
    "point_note",
)


def write_candidate(conn, item, *, now):
    extra = item["extra"]
    upsert_candidate(
        conn,
        item,
        table="std_dialect_points",
        fields=POINT_FIELDS,
        values=(
            extra.get("region_raw") or "未知地区",
            extra.get("province"),
            extra.get("city"),
            extra.get("county"),
            extra.get("dialect_name"),
            extra.get("point_note"),
        ),
        now=now,
    )
    point_id = conn.execute(
        "SELECT id FROM std_dialect_points "
        "WHERE source_id = ? AND source_item_id = ?",
        (item["source_id"], item["source_item_id"]),
    ).fetchone()[0]
    lexeme = extra.get("lexeme") or {}
    if not lexeme.get("lemma"):
        return
    lexeme_hash = lexeme.get("content_hash") or sha256_bytes(
        json.dumps(
            {
                "lemma": lexeme.get("lemma"),
                "definition": lexeme.get("definition"),
                "audio_url": lexeme.get("audio_url"),
            },
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")
    )
    conn.execute(
        """
        INSERT INTO std_dialect_lexemes (
            point_id, source_id, source_item_id, run_id, source_url,
            long_term_url, detail_url, detail_url_status, fetch_url, locator,
            lemma, phonetic, definition, example, audio_url, audio_status,
            rights_status, attribution_required, attribution_text,
            rights_evidence_url, confidence, license_or_usage, publish_status,
            candidate_status, candidate_reason, retrieved_at, content_hash,
            extra
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                  ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(point_id, lemma) DO UPDATE SET
            run_id=excluded.run_id,
            phonetic=excluded.phonetic,
            definition=excluded.definition,
            example=excluded.example,
            audio_url=excluded.audio_url,
            audio_status=excluded.audio_status,
            candidate_status=excluded.candidate_status,
            candidate_reason=excluded.candidate_reason,
            retrieved_at=excluded.retrieved_at,
            content_hash=excluded.content_hash,
            extra=excluded.extra
        """,
        (
            point_id,
            item["source_id"],
            lexeme.get("source_item_id") or item["source_item_id"],
            item["run_id"],
            lexeme.get("source_url") or item["source_url"],
            lexeme.get("long_term_url") or item["long_term_url"],
            lexeme.get("detail_url") or item["detail_url"],
            lexeme.get("detail_url_status") or item["detail_url_status"],
            lexeme.get("fetch_url"),
            lexeme.get("locator") or item["locator"],
            lexeme["lemma"],
            lexeme.get("phonetic"),
            lexeme.get("definition"),
            lexeme.get("example"),
            lexeme.get("audio_url"),
            lexeme.get("audio_status") or "missing",
            lexeme.get("rights_status") or item["rights_status"],
            1
            if lexeme.get("attribution_required")
            or item["attribution_required"]
            else 0,
            lexeme.get("attribution_text") or item["attribution_text"],
            lexeme.get("rights_evidence_url")
            or item["rights_evidence_url"],
            lexeme.get("confidence") or "medium",
            lexeme.get("license_or_usage") or item["rights_status"],
            "draft",
            item.get("candidate_status") or "candidate",
            item.get("candidate_reason"),
            now,
            lexeme_hash,
            json.dumps(lexeme.get("extra") or {}, ensure_ascii=False),
        ),
    )
    lexeme_id = conn.execute(
        "SELECT id FROM std_dialect_lexemes WHERE point_id = ? AND lemma = ?",
        (point_id, lexeme["lemma"]),
    ).fetchone()[0]
    source_url = lexeme.get("source_url") or item["source_url"]
    long_term_url = (
        lexeme.get("long_term_url") or item["long_term_url"]
    )
    detail_url = lexeme.get("detail_url") or item["detail_url"]
    detail_url_status = (
        lexeme.get("detail_url_status") or item["detail_url_status"]
    )
    rights_status = lexeme.get("rights_status") or item["rights_status"]
    attribution_required = bool(
        lexeme.get("attribution_required")
        or item["attribution_required"]
    )
    attribution_text = (
        lexeme.get("attribution_text") or item["attribution_text"]
    )
    rights_evidence_url = (
        lexeme.get("rights_evidence_url") or item["rights_evidence_url"]
    )
    conn.execute(
        """
        INSERT INTO std_dialect_lexeme_sources (
            lexeme_id, source_id, source_item_id, source_url, long_term_url,
            detail_url, detail_url_status, fetch_url, locator, rights_status,
            attribution_required, attribution_text, rights_evidence_url,
            is_primary, retrieved_at, content_hash, extra
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
        ON CONFLICT(lexeme_id, source_id, source_item_id, source_url)
        DO UPDATE SET
            long_term_url=excluded.long_term_url,
            detail_url=excluded.detail_url,
            detail_url_status=excluded.detail_url_status,
            fetch_url=excluded.fetch_url,
            locator=excluded.locator,
            rights_status=excluded.rights_status,
            attribution_required=excluded.attribution_required,
            attribution_text=excluded.attribution_text,
            rights_evidence_url=excluded.rights_evidence_url,
            is_primary=excluded.is_primary,
            retrieved_at=excluded.retrieved_at,
            content_hash=excluded.content_hash,
            extra=excluded.extra
        """,
        (
            lexeme_id,
            lexeme.get("source_id") or item["source_id"],
            lexeme.get("source_item_id") or item["source_item_id"],
            source_url,
            long_term_url,
            detail_url,
            detail_url_status,
            lexeme.get("fetch_url"),
            lexeme.get("locator") or item["locator"],
            rights_status,
            1 if attribution_required else 0,
            attribution_text,
            rights_evidence_url,
            now,
            lexeme_hash,
            json.dumps(lexeme.get("extra") or {}, ensure_ascii=False),
        ),
    )
