"""Shared job source and location relation writes."""

from __future__ import annotations

import json


def upsert_job_relations(
    conn,
    job_id,
    item,
    *,
    now,
    require_location=False,
):
    """Persist the source and locations, optionally rejecting empty location."""
    _upsert_job_source(conn, job_id, item, now=now)
    locations = _job_locations(item)
    if not locations and require_location:
        raise ValueError("job location is required")
    for index, location in enumerate(locations):
        _upsert_job_location(
            conn,
            job_id,
            item,
            location,
            is_primary=1 if index == 0 else 0,
        )


def _upsert_job_source(conn, job_id, item, *, now):
    conn.execute(
        """
        INSERT INTO std_job_sources (
            job_id, source_id, source_item_id, source_url, long_term_url,
            detail_url, detail_url_status, locator, rights_status,
            attribution_required, attribution_text, rights_evidence_url,
            is_primary, retrieved_at, content_hash, extra
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(job_id, source_id, source_url) DO UPDATE SET
            source_item_id=excluded.source_item_id,
            long_term_url=excluded.long_term_url,
            detail_url=excluded.detail_url,
            detail_url_status=excluded.detail_url_status,
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
            job_id,
            item["source_id"],
            item["source_item_id"],
            item["source_url"],
            item["long_term_url"],
            item.get("detail_url"),
            item["detail_url_status"],
            item.get("locator"),
            item["rights_status"],
            1 if item.get("attribution_required") else 0,
            item.get("attribution_text"),
            item.get("rights_evidence_url"),
            1,
            now,
            item.get("content_hash"),
            json.dumps(item.get("extra") or {}, ensure_ascii=False),
        ),
    )


def _upsert_job_location(conn, job_id, item, location, *, is_primary):
    existing = conn.execute(
        """
        SELECT id FROM std_job_locations
        WHERE job_id = ?
          AND province IS ?
          AND city IS ?
          AND county IS ?
          AND location_raw IS ?
        """,
        (
            job_id,
            location["province"],
            location["city"],
            location["county"],
            location["location_raw"],
        ),
    ).fetchone()
    values = (
        item["source_id"],
        item.get("source_item_id"),
        item["source_url"],
        item["long_term_url"],
        item.get("detail_url"),
        item["detail_url_status"],
        item.get("locator"),
        item["rights_status"],
        1 if item.get("attribution_required") else 0,
        item.get("attribution_text"),
        item.get("rights_evidence_url"),
        location["location_raw"],
        location["province"],
        location["city"],
        location["county"],
        is_primary,
        json.dumps(
            {
                **(item.get("extra") or {}),
                **(location.get("extra") or {}),
            },
            ensure_ascii=False,
        ),
    )
    if existing is None:
        conn.execute(
            """
            INSERT INTO std_job_locations (
                job_id, source_id, source_item_id, source_url, long_term_url,
                detail_url, detail_url_status, locator, rights_status,
                attribution_required, attribution_text, rights_evidence_url,
                location_raw, province, city, county, is_primary, extra
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (job_id, *values),
        )
        return
    conn.execute(
        """
        UPDATE std_job_locations
        SET source_id = ?,
            source_item_id = ?,
            source_url = ?,
            long_term_url = ?,
            detail_url = ?,
            detail_url_status = ?,
            locator = ?,
            rights_status = ?,
            attribution_required = ?,
            attribution_text = ?,
            rights_evidence_url = ?,
            location_raw = ?,
            province = ?,
            city = ?,
            county = ?,
            is_primary = ?,
            extra = ?
        WHERE id = ?
        """,
        (*values, existing[0]),
    )


def _job_locations(item):
    extra = item.get("extra") or {}
    configured = extra.get("locations")
    if isinstance(configured, list) and configured:
        locations = [_normalize_location(value) for value in configured]
    else:
        raw = _clean(extra.get("location_raw"))
        if raw and "|" in raw:
            locations = [
                _normalize_location(part)
                for part in raw.split("|")
                if _clean(part)
            ]
        else:
            locations = [
                _normalize_location(
                    {
                        "location_raw": raw,
                        "province": extra.get("province"),
                        "city": extra.get("city"),
                        "county": extra.get("county"),
                    }
                )
            ]
    deduplicated = []
    seen = set()
    for location in locations:
        if not any(
            location[key]
            for key in ("location_raw", "province", "city", "county")
        ):
            continue
        key = (
            location["province"],
            location["city"],
            location["county"],
            location["location_raw"],
        )
        if key in seen:
            continue
        seen.add(key)
        deduplicated.append(location)
    return deduplicated


def _normalize_location(value):
    if isinstance(value, str):
        value = {"location_raw": value}
    value = value or {}
    return {
        "location_raw": _clean(value.get("location_raw")),
        "province": _clean(value.get("province")),
        "city": _clean(value.get("city")),
        "county": _clean(value.get("county")),
        "extra": value.get("extra") or {},
    }


def _clean(value):
    text = str(value).strip() if value is not None else ""
    return text or None
