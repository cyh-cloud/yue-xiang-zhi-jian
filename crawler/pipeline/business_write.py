"""Real business writes for converted crawler candidates.

Only the jobs domain is implemented. The crawler database remains the owner of
batch and conflict audit, while the business database owns the reviewable rows.
SQLite ATTACH keeps both writes in one transaction when using run_batch.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass, field


JOBS_TARGET_TABLE = "recruitments"
JOBS_SOURCE_TABLE = "recruitment_sources"

_JOB_FIELDS = (
    "title",
    "org",
    "region",
    "category",
    "job_type",
    "headcount",
    "education",
    "experience",
    "salary",
    "description",
    "publish_date",
    "signup_start",
    "deadline",
    "signup_way",
    "contact",
    "sort_order",
)
_PROTECTED_EXTRA_FIELDS = frozenset(
    {"review_status", "publish_status", "reviewed_by", "reviewed_at"}
)


@dataclass
class JobWriteStats:
    inserted_count: int = 0
    updated_count: int = 0
    skipped_count: int = 0
    conflicts: list = field(default_factory=list)
    items: list = field(default_factory=list)


def _json_object(value):
    if isinstance(value, dict):
        return dict(value)
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _json_text(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _fingerprint(fields, sources):
    payload = {
        "fields": {key: fields.get(key) for key in _JOB_FIELDS},
        "sources": sorted(
            (
                {
                    "title": source.get("title"),
                    "media": source.get("media"),
                    "date": source.get("date"),
                    "url": source.get("url"),
                    "source_id": source.get("source_id"),
                    "source_item_id": source.get("source_item_id"),
                }
                for source in sources
            ),
            key=lambda item: _json_text(item),
        ),
    }
    return hashlib.sha256(_json_text(payload).encode("utf-8")).hexdigest()


def _business_key(row):
    source_id = (row.get("source_id") or "").strip()
    item_id = (row.get("source_item_id") or "").strip()
    if not item_id:
        url = (row.get("source_url") or "").strip()
        item_id = hashlib.sha256(url.encode("utf-8")).hexdigest()[:20]
    return f"job-{source_id}-{item_id}"


def _date_value(value):
    return (value or "").strip()[:10]


def _join_text(*values):
    parts = []
    for value in values:
        text = (value or "").strip()
        if text and text not in parts:
            parts.append(text)
    return "\n\n".join(parts)


def _source_name(row, registry):
    source = registry.get(row.get("source_id")) or {}
    return source.get("name") or row.get("source_id") or ""


def _job_fields(row, registry):
    extra = _json_object(row.get("extra"))
    location = (row.get("location_raw") or "").strip()
    region = location or (row.get("province") or "").strip() or (
        row.get("city") or ""
    ).strip()
    return {
        "title": (row.get("title") or "").strip(),
        "org": (row.get("company_name") or "").strip(),
        "region": region,
        "category": (row.get("company_industry") or extra.get("company_industry") or "").strip(),
        "job_type": (row.get("employment_type") or "").strip(),
        "headcount": (
            "" if row.get("headcount") is None else str(row.get("headcount")).strip()
        ),
        "education": (row.get("education_raw") or "").strip(),
        "experience": (row.get("experience_raw") or "").strip(),
        "salary": (row.get("salary_raw") or "").strip(),
        "description": _join_text(
            row.get("description"),
            row.get("requirements"),
        ),
        "publish_date": _date_value(row.get("published_at")),
        "signup_start": "",
        "deadline": _date_value(row.get("deadline_at")),
        "signup_way": "",
        "contact": "",
        "sort_order": 0,
    }


def _job_sources(row, registry):
    extra = _json_object(row.get("extra"))
    source_id = row.get("source_id") or ""
    item_id = row.get("source_item_id") or ""
    source_name = _source_name(row, registry)
    sources = []
    seen = set()
    relations = row.get("source_relations") or [
        {
            "source_id": source_id,
            "source_item_id": item_id,
            "source_url": row.get("source_url"),
            "detail_url": row.get("detail_url"),
            "retrieved_at": row.get("retrieved_at"),
            "content_hash": row.get("content_hash"),
            "rights_status": row.get("rights_status"),
            "attribution_required": row.get("attribution_required"),
            "attribution_text": row.get("attribution_text"),
            "rights_evidence_url": row.get("rights_evidence_url"),
        }
    ]
    for relation in relations:
        url = relation.get("detail_url") or relation.get("source_url") or ""
        relation_item_id = relation.get("source_item_id") or item_id
        title = f"{source_name} ({relation_item_id})"
        identity = (title, url)
        if identity in seen:
            continue
        seen.add(identity)
        sources.append(
            {
                "title": title,
                "media": source_name,
                "date": _date_value(row.get("published_at")),
                "url": url,
                "sort_order": 0,
                "source_id": relation.get("source_id") or source_id,
                "source_item_id": relation_item_id,
                "source_url": relation.get("source_url") or url,
                "detail_url": relation.get("detail_url") or url,
                "retrieved_at": relation.get("retrieved_at"),
                "content_hash": relation.get("content_hash"),
                "rights_status": relation.get("rights_status"),
                "attribution_required": bool(
                    relation.get("attribution_required")
                ),
                "attribution_text": relation.get("attribution_text"),
                "rights_evidence_url": relation.get("rights_evidence_url"),
            }
        )
    return sources


def _job_extra(row, batch, batch_id, imported_at, fields, fingerprint):
    extra = _json_object(row.get("extra"))
    return {
        "review_status": "pending_review",
        "publish_status": "draft",
        "content_domain": "jobs",
        "import_batch_id": batch_id,
        "import_batch_key": batch["batch_key"],
        "imported_at": imported_at,
        "converter_version": batch["converter_version"],
        "source_id": row.get("source_id") or "",
        "source_item_id": row.get("source_item_id") or "",
        "source_url": row.get("source_url") or "",
        "detail_url": row.get("detail_url") or row.get("source_url") or "",
        "content_hash": row.get("content_hash") or "",
        "import_content_fingerprint": fingerprint,
        "confidence": row.get("confidence") or "",
        "rights_status": row.get("rights_status") or "",
        "attribution_required": bool(row.get("attribution_required")),
        "attribution_text": row.get("attribution_text") or "",
        "rights_evidence_url": row.get("rights_evidence_url") or "",
        "crawler_status": row.get("status") or "",
        "location_raw": row.get("location_raw") or "",
        "province": row.get("province") or "",
        "city": row.get("city") or "",
        "company_url": extra.get("company_url") or "",
        "company_industry": extra.get("company_industry") or "",
        "company_size": extra.get("company_size") or "",
        "company_nature": extra.get("company_nature") or "",
        "published_at": row.get("published_at") or "",
        "deadline_at": row.get("deadline_at") or "",
        "listed_relative_time": extra.get("listed_relative_time") or "",
        "fields": fields,
    }


def _merge_extra(existing, incoming):
    merged = dict(existing)
    for key, value in incoming.items():
        if key in _PROTECTED_EXTRA_FIELDS and key in merged:
            continue
        merged[key] = value
    manual_fields = existing.get("manual_fields")
    if isinstance(manual_fields, list):
        merged["manual_fields"] = manual_fields
    return merged


def _source_extra(source, batch, batch_id, imported_at):
    return {
        "content_domain": "jobs",
        "import_batch_id": batch_id,
        "import_batch_key": batch["batch_key"],
        "imported_at": imported_at,
        "source_id": source["source_id"],
        "source_item_id": source["source_item_id"],
        "source_url": source["source_url"],
        "detail_url": source["detail_url"],
        "retrieved_at": source.get("retrieved_at") or "",
        "content_hash": source.get("content_hash") or "",
        "rights_status": source.get("rights_status") or "",
        "attribution_required": bool(source.get("attribution_required")),
        "attribution_text": source.get("attribution_text") or "",
        "rights_evidence_url": source.get("rights_evidence_url") or "",
    }


def _manual_conflicts(existing, incoming, key, manual_fields, row):
    conflicts = []
    for field in _JOB_FIELDS:
        if field not in manual_fields:
            continue
        old = existing.get(field)
        new = incoming.get(field)
        if old == new:
            continue
        conflicts.append(
            {
                "target_table": JOBS_TARGET_TABLE,
                "target_key": key,
                "field": field,
                "existing_value": old,
                "incoming_value": new,
                "existing_source_id": row.get("source_id"),
                "existing_source_url": row.get("source_url"),
                "existing_retrieved_at": row.get("retrieved_at"),
                "incoming_source_id": row.get("source_id"),
                "incoming_source_url": row.get("source_url"),
                "incoming_retrieved_at": row.get("retrieved_at"),
                "reason": "manual_field_locked",
            }
        )
    return conflicts


def _validate_business_schema(conn):
    missing = [
        table
        for table in (JOBS_TARGET_TABLE, JOBS_SOURCE_TABLE)
        if conn.execute(
            "SELECT 1 FROM business.sqlite_master WHERE type = 'table' AND name = ?",
            (table,),
        ).fetchone()
        is None
    ]
    if missing:
        raise ValueError(
            "business database is missing required tables: "
            + ", ".join(missing)
        )


def attach_business_database(conn, path):
    """Attach an existing business database without applying crawler schema."""
    conn.execute("ATTACH DATABASE ? AS business", (str(path),))
    _validate_business_schema(conn)
    conn.execute("PRAGMA business.busy_timeout = 8000")


def _existing_source(conn, key, title):
    row = conn.execute(
        "SELECT title, media, date, url, sort_order, extra "
        "FROM business.recruitment_sources "
        "WHERE recruit_key = ? AND title = ?",
        (key, title),
    ).fetchone()
    return dict(row) if row else None


def _source_values(source, extra):
    return (
        source["title"],
        source["media"],
        source["date"],
        source["url"],
        source["sort_order"],
        _json_text(extra),
    )


def _source_changed(existing, source, extra):
    if existing is None:
        return True
    expected = _source_values(source, extra)
    current = (
        existing["title"],
        existing["media"],
        existing["date"],
        existing["url"],
        existing["sort_order"],
        existing["extra"],
    )
    return current != expected


def _upsert_sources(conn, key, sources, batch, batch_id, imported_at):
    changed = False
    for source in sources:
        extra = _source_extra(source, batch, batch_id, imported_at)
        existing = _existing_source(conn, key, source["title"])
        if not _source_changed(existing, source, extra):
            continue
        conn.execute(
            """
            INSERT INTO business.recruitment_sources (
                recruit_key, title, media, date, url, sort_order, extra
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(recruit_key, title) DO UPDATE SET
                media = excluded.media,
                date = excluded.date,
                url = excluded.url,
                sort_order = excluded.sort_order,
                extra = excluded.extra
            """,
            (key, *_source_values(source, extra)),
        )
        changed = True
    return changed


def _existing_recruitment(conn, key):
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM business.recruitments WHERE key = ?", (key,)
    ).fetchone()
    return dict(row) if row else None


def _changed_fields(existing, incoming):
    changes = {}
    for field in _JOB_FIELDS:
        existing_value = existing.get(field)
        if existing_value is None:
            existing_value = ""
        if existing_value != incoming.get(field):
            changes[field] = incoming.get(field)
    return changes


def _insert_recruitment(conn, key, fields, extra):
    columns = ("key",) + _JOB_FIELDS + ("extra",)
    values = (key,) + tuple(fields[field] for field in _JOB_FIELDS) + (
        _json_text(extra),
    )
    conn.execute(
        "INSERT INTO business.recruitments (%s) VALUES (%s)"
        % (", ".join(columns), ", ".join("?" for _ in columns)),
        values,
    )


def _update_recruitment(conn, key, fields, extra):
    assignments = [f'"{field}" = ?' for field in _JOB_FIELDS]
    assignments.append("extra = ?")
    conn.execute(
        "UPDATE business.recruitments SET %s WHERE key = ?"
        % ", ".join(assignments),
        tuple(fields[field] for field in _JOB_FIELDS) + (_json_text(extra), key),
    )


def _audit_item(operation, key, row, extra):
    return {
        "target_table": JOBS_TARGET_TABLE,
        "target_key": key,
        "operation": operation,
        "status": {
            "insert": "inserted",
            "update": "updated",
            "skip": "skipped",
        }[operation],
        "source_id": row.get("source_id"),
        "source_item_id": row.get("source_item_id"),
        "content_hash": row.get("content_hash"),
        "extra": extra,
    }


def write_jobs(conn, entity_plan, batch, batch_id, imported_at, registry):
    """Upsert planned jobs into the attached business database."""
    stats = JobWriteStats()
    for row in entity_plan["rows"]:
        key = row.get("business_key") or _business_key(row)
        incoming = _job_fields(row, registry)
        sources = _job_sources(row, registry)
        existing = _existing_recruitment(conn, key)

        if existing is None:
            fingerprint = _fingerprint(incoming, sources)
            extra = _job_extra(
                row, batch, batch_id, imported_at, incoming, fingerprint
            )
            _insert_recruitment(conn, key, incoming, extra)
            _upsert_sources(conn, key, sources, batch, batch_id, imported_at)
            stats.inserted_count += 1
            stats.items.append(
                _audit_item(
                    "insert",
                    key,
                    row,
                    {
                        "business_key": key,
                        "import_content_fingerprint": fingerprint,
                        "sources": [source["url"] for source in sources],
                    },
                )
            )
            continue

        existing_extra = _json_object(existing.get("extra"))
        manual_fields = existing_extra.get("manual_fields")
        manual_fields = set(manual_fields) if isinstance(manual_fields, list) else set()
        conflicts = _manual_conflicts(
            existing, incoming, key, manual_fields, row
        )
        stats.conflicts.extend(conflicts)

        effective = dict(incoming)
        for field in manual_fields:
            if field in effective and field in existing:
                effective[field] = existing.get(field)
        fingerprint = _fingerprint(effective, sources)
        sources_changed = (
            existing_extra.get("import_content_fingerprint") != fingerprint
        )
        changes = _changed_fields(existing, effective)
        sources_present = all(
            _existing_source(conn, key, source["title"]) is not None
            for source in sources
        )

        if (
            not changes
            and existing_extra.get("import_content_fingerprint") == fingerprint
            and sources_present
        ):
            if conflicts:
                stats.items.append(
                    _audit_item(
                        "skip",
                        key,
                        row,
                        {
                            "business_key": key,
                            "reason": "manual_field_locked",
                        },
                    )
                )
            else:
                stats.skipped_count += 1
                stats.items.append(
                    _audit_item(
                        "skip",
                        key,
                        row,
                        {
                            "business_key": key,
                            "reason": "content_unchanged",
                        },
                    )
                )
            continue

        extra = _merge_extra(
            existing_extra,
            _job_extra(
                row, batch, batch_id, imported_at, effective, fingerprint
            ),
        )
        if conflicts:
            stats.skipped_count += 1
            stats.items.append(
                _audit_item(
                    "skip",
                    key,
                    row,
                    {
                        "business_key": key,
                        "reason": "manual_field_locked",
                        "manual_fields": sorted(manual_fields),
                    },
                )
            )
            continue
        sources_updated = _upsert_sources(
            conn, key, sources, batch, batch_id, imported_at
        )
        if changes or sources_changed or sources_updated:
            _update_recruitment(conn, key, effective, extra)
            stats.updated_count += 1
            stats.items.append(
                _audit_item(
                    "update",
                    key,
                    row,
                    {
                        "business_key": key,
                        "updated_fields": sorted(changes),
                        "import_content_fingerprint": fingerprint,
                        "sources": [source["url"] for source in sources],
                    },
                )
            )
        else:
            stats.skipped_count += 1
            stats.items.append(
                _audit_item(
                    "skip",
                    key,
                    row,
                    {
                        "business_key": key,
                        "reason": "content_unchanged",
                    },
                )
            )
    return stats
