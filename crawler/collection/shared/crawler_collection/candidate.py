"""Generic candidate writes. Site projects provide the field mapping."""

from __future__ import annotations

import json


def candidate_common_fields():
    return (
        "source_id",
        "source_item_id",
        "run_id",
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
        "extra",
    )


def candidate_common_values(item, *, now):
    return (
        item["source_id"],
        item["source_item_id"],
        item["run_id"],
        item["source_url"],
        item["long_term_url"],
        item["detail_url"],
        item["detail_url_status"],
        item["locator"],
        item["rights_status"],
        1 if item["attribution_required"] else 0,
        item["attribution_text"],
        item["rights_evidence_url"],
        item["content_hash"],
        item.get("confidence") or "medium",
        item.get("license_or_usage") or item["rights_status"],
        "draft",
        item.get("candidate_status") or "candidate",
        item.get("candidate_reason"),
        now,
        now,
        now,
        json.dumps(item.get("extra") or {}, ensure_ascii=False),
    )


def upsert_candidate(conn, item, *, table, fields, values, now):
    fields = tuple(fields)
    columns = candidate_common_fields() + fields
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
        candidate_common_values(item, now=now) + tuple(values),
    )
