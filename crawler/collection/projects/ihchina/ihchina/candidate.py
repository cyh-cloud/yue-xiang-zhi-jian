"""ihchina candidate field mapping."""

import json

from crawler.collection.shared.crawler_collection.candidate import (
    upsert_candidate,
)
from crawler.collection.shared.crawler_collection.evidence import sha256_bytes


FIELDS = (
    "ich_code",
    "name",
    "project_serial",
    "source_project_num",
    "category",
    "project_type",
    "announcement_batch",
    "announcement_year",
    "declaration_region",
    "protection_unit",
    "province",
    "city",
    "county",
    "description_html",
    "description_text",
    "source_modified_at",
)


def write_candidate(conn, item, *, now):
    extra = item["extra"]
    upsert_candidate(
        conn,
        item,
        table="std_ich_projects",
        fields=FIELDS,
        values=(
            extra.get("ich_code"),
            item["title"],
            extra.get("project_serial"),
            extra.get("source_project_num"),
            extra.get("category"),
            extra.get("project_type"),
            extra.get("announcement_batch"),
            extra.get("announcement_year"),
            extra.get("declaration_region"),
            extra.get("protection_unit"),
            extra.get("province"),
            extra.get("city"),
            extra.get("county"),
            extra.get("description_html"),
            item.get("body_text"),
            extra.get("source_modified_at"),
        ),
        now=now,
    )
    _write_related_entities(conn, item, extra=extra, now=now)


def _write_related_entities(conn, item, *, extra, now):
    project = conn.execute(
        "SELECT id FROM std_ich_projects "
        "WHERE source_id = ? AND source_item_id = ?",
        (item["source_id"], item["source_item_id"]),
    ).fetchone()
    if project is None:
        return
    project_id = project[0]
    rights = {
        "rights_status": item["rights_status"],
        "attribution_required": item["attribution_required"],
        "attribution_text": item["attribution_text"],
        "rights_evidence_url": item["rights_evidence_url"],
    }

    for inheritor in extra.get("inheritors") or []:
        source_url = inheritor.get("source_url") or item["source_url"]
        inheritor_hash = sha256_bytes(
            json.dumps(inheritor, ensure_ascii=False, sort_keys=True).encode(
                "utf-8"
            )
        )
        conn.execute(
            """
            INSERT INTO std_ich_inheritors (
                project_id, source_id, source_item_id, source_url,
                long_term_url, detail_url, detail_url_status, locator,
                rights_status, attribution_required, attribution_text,
                rights_evidence_url, name, gender, birth_date, ethnicity,
                category, ich_code, project_name, declaration_region,
                biography_text, retrieved_at, content_hash, confidence, extra
            ) VALUES (?, ?, ?, ?, ?, ?, 'direct', ?, ?, ?, ?, ?, ?, ?, ?,
                      ?, ?, ?, ?, ?, ?, ?, ?, 'medium', ?)
            ON CONFLICT(source_id, source_item_id) DO UPDATE SET
                project_id=excluded.project_id,
                source_url=excluded.source_url,
                long_term_url=excluded.long_term_url,
                detail_url=excluded.detail_url,
                detail_url_status=excluded.detail_url_status,
                locator=excluded.locator,
                rights_status=excluded.rights_status,
                attribution_required=excluded.attribution_required,
                attribution_text=excluded.attribution_text,
                rights_evidence_url=excluded.rights_evidence_url,
                name=excluded.name,
                gender=excluded.gender,
                birth_date=excluded.birth_date,
                ethnicity=excluded.ethnicity,
                category=excluded.category,
                ich_code=excluded.ich_code,
                project_name=excluded.project_name,
                declaration_region=excluded.declaration_region,
                biography_text=excluded.biography_text,
                retrieved_at=excluded.retrieved_at,
                content_hash=excluded.content_hash,
                extra=excluded.extra
            """,
            (
                project_id,
                item["source_id"],
                inheritor.get("source_item_id"),
                source_url,
                source_url,
                source_url,
                source_url,
                rights["rights_status"],
                1 if rights["attribution_required"] else 0,
                rights["attribution_text"],
                rights["rights_evidence_url"],
                inheritor.get("name"),
                inheritor.get("gender"),
                inheritor.get("birth_date"),
                inheritor.get("ethnicity"),
                inheritor.get("category"),
                inheritor.get("ich_code"),
                inheritor.get("project_name"),
                inheritor.get("declaration_region"),
                inheritor.get("biography_text"),
                now,
                inheritor_hash,
                json.dumps(inheritor, ensure_ascii=False),
            ),
        )

    for related in extra.get("related_projects") or []:
        related_source_item_id = related.get("source_item_id")
        related_row = conn.execute(
            "SELECT id FROM std_ich_projects "
            "WHERE source_id = ? AND source_item_id = ?",
            (item["source_id"], related_source_item_id),
        ).fetchone()
        related_url = related.get("source_url") or item["source_url"]
        relation_type = related.get("category") or "related"
        conn.execute(
            """
            INSERT INTO std_ich_related_items (
                source_id, subject_project_id, related_project_id,
                related_source_item_id, relation_type, source_url,
                long_term_url, detail_url, detail_url_status, locator,
                rights_status, attribution_required, attribution_text,
                rights_evidence_url, retrieved_at, content_hash, extra
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'direct', ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(
                source_id, subject_project_id, related_source_item_id,
                relation_type
            ) DO UPDATE SET
                related_project_id=excluded.related_project_id,
                source_url=excluded.source_url,
                long_term_url=excluded.long_term_url,
                detail_url=excluded.detail_url,
                detail_url_status=excluded.detail_url_status,
                locator=excluded.locator,
                rights_status=excluded.rights_status,
                attribution_required=excluded.attribution_required,
                attribution_text=excluded.attribution_text,
                rights_evidence_url=excluded.rights_evidence_url,
                retrieved_at=excluded.retrieved_at,
                content_hash=excluded.content_hash,
                extra=excluded.extra
            """,
            (
                item["source_id"],
                project_id,
                related_row[0] if related_row else None,
                related_source_item_id,
                relation_type,
                related_url,
                related_url,
                related_url,
                f"related_projects:{related_source_item_id}",
                rights["rights_status"],
                1 if rights["attribution_required"] else 0,
                rights["attribution_text"],
                rights["rights_evidence_url"],
                now,
                sha256_bytes(
                    json.dumps(
                        related, ensure_ascii=False, sort_keys=True
                    ).encode("utf-8")
                ),
                json.dumps(related, ensure_ascii=False),
            ),
        )

    for media in extra.get("media_links") or []:
        media_url = media["media_url"]
        conn.execute(
            """
            INSERT INTO std_ich_media_links (
                project_id, source_id, source_item_id, source_url,
                long_term_url, detail_url, detail_url_status, locator,
                media_url, media_type, availability, rights_status,
                attribution_required, attribution_text, rights_evidence_url,
                retrieved_at, extra
            ) VALUES (?, ?, ?, ?, ?, ?, 'direct', ?, ?, ?, 'unknown',
                      ?, ?, ?, ?, ?, ?)
            ON CONFLICT(project_id, media_url) DO UPDATE SET
                source_url=excluded.source_url,
                long_term_url=excluded.long_term_url,
                detail_url=excluded.detail_url,
                detail_url_status=excluded.detail_url_status,
                locator=excluded.locator,
                media_type=excluded.media_type,
                availability=excluded.availability,
                rights_status=excluded.rights_status,
                attribution_required=excluded.attribution_required,
                attribution_text=excluded.attribution_text,
                rights_evidence_url=excluded.rights_evidence_url,
                retrieved_at=excluded.retrieved_at,
                extra=excluded.extra
            """,
            (
                project_id,
                item["source_id"],
                item["source_item_id"],
                item["source_url"],
                item["long_term_url"],
                item["detail_url"],
                f"media_links:{media_url}",
                media_url,
                media.get("media_type"),
                rights["rights_status"],
                1 if rights["attribution_required"] else 0,
                rights["attribution_text"],
                rights["rights_evidence_url"],
                now,
                json.dumps(media, ensure_ascii=False),
            ),
        )
