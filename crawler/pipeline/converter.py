import hashlib
import json
import os
import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path

from . import database, source_registry
from .publication import evaluate_publication


_SUPPORTED_DOMAINS = {"ich", "agri", "jobs", "dialects"}


@dataclass(frozen=True)
class BatchResult:
    batch_id: int | None
    status: str
    input_count: int
    inserted_count: int
    updated_count: int
    skipped_count: int
    conflict_count: int
    failed_count: int
    by_entity: dict = field(default_factory=dict)
    failures: tuple = ()


@dataclass(frozen=True)
class RollbackResult:
    batch_id: int
    status: str
    rolled_back_count: int
    skipped_count: int
    conflict_count: int


def _now():
    return datetime.now(timezone.utc).isoformat()


def _validate(domain, batch):
    if domain not in _SUPPORTED_DOMAINS:
        raise ValueError(f"unsupported domain: {domain}")
    if not isinstance(batch, dict):
        raise ValueError("batch must be a mapping")
    for key in ("batch_key", "converter_version", "target_database"):
        if not batch.get(key):
            raise ValueError(f"missing batch field: {key}")


def _rows(conn, entity, source_ids, std_entity_ids):
    clauses = []
    params = []
    if source_ids:
        placeholders = ",".join("?" for _ in source_ids)
        clauses.append(f"source_id IN ({placeholders})")
        params.extend(source_ids)
    if std_entity_ids:
        placeholders = ",".join("?" for _ in std_entity_ids)
        clauses.append(f"id IN ({placeholders})")
        params.extend(std_entity_ids)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    conn.row_factory = sqlite3.Row
    return [dict(row) for row in conn.execute(f"SELECT * FROM {entity}{where}", params)]


def _load_sources(conn):
    conn.row_factory = sqlite3.Row
    return {
        row["source_id"]: dict(row)
        for row in conn.execute("SELECT * FROM std_sources")
    }


def _priority_value(priority):
    return {"P0": 0, "P1": 100, "P2": 200}.get(priority, 1000)


def _source_priorities(db_sources, registry):
    source_ids = set(db_sources) | set(registry)
    return {
        source_id: _priority_value(
            (
                registry.get(source_id)
                or db_sources.get(source_id)
                or {}
            ).get("priority")
        )
        for source_id in source_ids
    }


def _sort_by_source_priority(rows, source_priorities):
    rows.sort(
        key=lambda row: (
            source_priorities.get(row["source_id"], 100),
            0 if row.get("confidence") == "high" else 1,
            row.get("retrieved_at") or "",
        )
    )


def _publishable_rows(rows, source_priorities, registry):
    _sort_by_source_priority(rows, source_priorities)
    publishable = []
    skipped = 0
    for row in rows:
        source = registry.get(row.get("source_id"))
        if source is None:
            skipped += 1
            continue
        source_decision = source_registry.evaluate_source(source)
        if not source_decision.allowed:
            skipped += 1
            continue
        decision = evaluate_publication(row)
        if decision.allowed:
            publishable.append(row)
        else:
            skipped += 1
    return publishable, skipped


def _ich_plan(conn, batch, source_priorities, registry):
    rows = _rows(
        conn,
        "std_ich_projects",
        batch.get("source_ids") or [],
        batch.get("std_entity_ids") or [],
    )
    rows, skipped = _publishable_rows(rows, source_priorities, registry)
    groups = {}
    for row in rows:
        key = (
            row.get("ich_code") or "",
            row.get("declaration_region") or "",
            row.get("name") or "",
        )
        groups.setdefault(key, []).append(row)

    projected = []
    conflicts = []
    for group in groups.values():
        primary = group[0]
        business_id = f"ich-{primary['source_item_id']}"
        projected.append(
            {
                "id": business_id,
                "name": primary["name"],
                "origin": primary.get("declaration_region") or "",
                "history": primary.get("description_text") or "",
                "level": "",
                "sort_order": None,
                "source_id": primary["source_id"],
                "source_url": primary["source_url"],
                "extra": {
                    "ich_code": primary.get("ich_code"),
                    "category": primary.get("category"),
                    "announcement_batch": primary.get("announcement_batch"),
                    "project_type": primary.get("project_type"),
                    "protection_unit": primary.get("protection_unit"),
                    "detail_url": primary.get("detail_url") or primary["source_url"],
                },
            }
        )
        for incoming in group[1:]:
            target_key = json.dumps(
                [
                    primary.get("ich_code") or "",
                    primary.get("declaration_region") or "",
                    primary.get("name") or "",
                ],
                ensure_ascii=False,
            )
            conflict = _field_conflict(
                primary, incoming, "description_text", target_key
            )
            if conflict:
                conflicts.append(conflict)

    return {
        "entity": "std_ich_projects",
        "input_count": len(rows),
        "common_count": sum(len(group) for group in groups.values()),
        "rows": projected,
        "conflicts": conflicts,
        "skipped": skipped,
    }


def _field_conflict(existing, incoming, field, target_key=""):
    old = existing.get(field)
    new = incoming.get(field)
    if old == new:
        return None
    return {
        "field": field,
        "target_key": target_key,
        "existing_source_id": existing["source_id"],
        "existing_source_url": existing["source_url"],
        "existing_retrieved_at": existing.get("retrieved_at"),
        "existing_value": old,
        "incoming_source_id": incoming["source_id"],
        "incoming_source_url": incoming["source_url"],
        "incoming_retrieved_at": incoming.get("retrieved_at"),
        "incoming_value": new,
    }


def _agri_region(row):
    region = (row.get("region") or "").strip()
    if region:
        return region
    scope = (row.get("origin_scope") or "").strip()
    if not scope:
        return ""
    return hashlib.sha256(scope.encode("utf-8")).hexdigest()[:16]


def _agri_plan(conn, batch, source_priorities, registry):
    rows = _rows(
        conn,
        "std_agri_products",
        batch.get("source_ids") or [],
        batch.get("std_entity_ids") or [],
    )
    rows, skipped = _publishable_rows(rows, source_priorities, registry)
    groups = {}
    for row in rows:
        key = (
            row.get("cert_type") or "",
            row.get("normalized_name") or "",
            row.get("province") or "",
            _agri_region(row),
        )
        groups.setdefault(key, []).append(row)

    projected = []
    conflicts = []
    for group in groups.values():
        primary = group[0]
        region = (primary.get("region") or primary.get("origin_scope") or "").strip()
        projected.append(
            {
                "cert_type": primary["cert_type"],
                "product_name": primary["product_name"],
                "product_name_raw": primary.get("product_name_raw") or "",
                "normalized_name": primary["normalized_name"],
                "category": primary.get("category") or "",
                "is_aquatic": primary.get("is_aquatic"),
                "province": primary.get("province") or "",
                "city": primary.get("city") or "",
                "county": primary.get("county") or "",
                "region": region,
                "origin_scope": primary.get("origin_scope") or "",
                "applicant": primary.get("applicant") or "",
                "protection_unit": primary.get("protection_unit") or "",
                "certificate_no": primary.get("certificate_no") or "",
                "certified_at": primary.get("certified_at") or "",
                "source_id": primary["source_id"],
                "source_url": primary["detail_url"],
                "source_item_id": primary["source_item_id"],
            }
        )
        for incoming in group[1:]:
            target_key = json.dumps(
                [
                    primary.get("cert_type") or "",
                    primary.get("normalized_name") or "",
                    primary.get("province") or "",
                    _agri_region(primary),
                ],
                ensure_ascii=False,
            )
            conflict = _field_conflict(
                primary, incoming, "applicant", target_key
            )
            if conflict:
                conflicts.append(conflict)

    return {
        "entity": "std_agri_products",
        "input_count": len(rows),
        "rows": projected,
        "conflicts": conflicts,
        "skipped": skipped,
    }


def _job_status(row, today):
    deadline = (row.get("deadline_at") or "").strip()
    if deadline:
        try:
            if date.fromisoformat(deadline[:10]) < today:
                return "expired"
        except ValueError:
            pass
    status_text = (row.get("status_text") or "").strip().lower()
    if any(marker in status_text for marker in ("已过期", "过期", "expired")):
        return "expired"
    return "active"


def _job_plan(conn, batch, source_priorities, registry):
    rows = _rows(
        conn,
        "std_jobs",
        batch.get("source_ids") or [],
        batch.get("std_entity_ids") or [],
    )
    rows, skipped = _publishable_rows(rows, source_priorities, registry)
    groups = {}
    for row in rows:
        natural_key = (
            row.get("source_id") or "",
            row.get("source_item_id") or "",
        )
        if not natural_key[1]:
            natural_key = (row.get("source_id") or "", row.get("source_url") or "")
        groups.setdefault(natural_key, []).append(row)

    today = date.today()
    projected = []
    for group in groups.values():
        primary = group[0]
        relations = []
        seen_relations = set()
        for row in group:
            relation_key = (row["source_url"], row["source_id"])
            if relation_key in seen_relations:
                continue
            seen_relations.add(relation_key)
            relations.append(
                {
                    "source_id": row["source_id"],
                    "source_item_id": row.get("source_item_id") or "",
                    "source_url": row["source_url"],
                    "is_primary": row is primary,
                    "retrieved_at": row.get("retrieved_at"),
                    "content_hash": row.get("content_hash"),
                }
            )
        projected.append(
            {
                "source_id": primary["source_id"],
                "source_item_id": primary.get("source_item_id") or "",
                "source_url": primary["source_url"],
                "title": primary["title"],
                "title_raw": primary.get("title_raw") or primary["title"],
                "company_name": primary.get("company_name") or "",
                "company_url": primary.get("company_url") or "",
                "location_raw": primary.get("location_raw") or "",
                "province": primary.get("province") or "",
                "city": primary.get("city") or "",
                "employment_type": primary.get("employment_type") or "",
                "salary_raw": primary.get("salary_raw") or "",
                "education_raw": primary.get("education_raw") or "",
                "experience_raw": primary.get("experience_raw") or "",
                "published_at": primary.get("published_at") or "",
                "deadline_at": primary.get("deadline_at") or "",
                "status": _job_status(primary, today),
                "content_hash": primary.get("content_hash"),
                "source_relations": relations,
            }
        )

    return {
        "entity": "std_jobs",
        "input_count": len(rows),
        "rows": projected,
        "conflicts": [],
        "skipped": skipped,
    }


def _dialect_plan(conn, batch, source_priorities, registry):
    source_ids = batch.get("source_ids") or []
    entity_ids = batch.get("std_entity_ids") or []
    points = _rows(conn, "std_dialect_points", source_ids, [])
    points_by_id = {}
    rejected_point_ids = set()
    for point in points:
        source = registry.get(point.get("source_id"))
        if source is None or not source_registry.evaluate_source(source).allowed:
            rejected_point_ids.add(point["id"])
            continue
        decision = evaluate_publication(point)
        if decision.allowed:
            points_by_id[point["id"]] = point
        else:
            rejected_point_ids.add(point["id"])
    lexemes = _rows(conn, "std_dialect_lexemes", [], entity_ids)
    candidate_lexemes = [
        row
        for row in lexemes
        if row.get("point_id") in points_by_id
        or row.get("point_id") in rejected_point_ids
    ]
    skipped = sum(
        1 for row in candidate_lexemes if row.get("point_id") in rejected_point_ids
    )
    publishable_lexemes = []
    for row in candidate_lexemes:
        if row.get("point_id") in rejected_point_ids:
            continue
        merged = dict(row)
        point = points_by_id[row["point_id"]]
        for key in ("rights_status", "publish_status"):
            if not merged.get(key):
                merged[key] = point.get(key)
        decision = evaluate_publication(merged)
        if decision.allowed:
            publishable_lexemes.append(row)
        else:
            skipped += 1
    lexemes = publishable_lexemes
    lexemes.sort(
        key=lambda row: (
            source_priorities.get(points_by_id[row["point_id"]]["source_id"], 100),
            0 if row.get("confidence") == "high" else 1,
            row.get("retrieved_at") or "",
        )
    )
    sources = _rows(conn, "std_dialect_lexeme_sources", [], [])
    sources_by_lexeme = {}
    for row in sources:
        sources_by_lexeme.setdefault(row["lexeme_id"], []).append(row)

    groups = {}
    for row in lexemes:
        key = (row["point_id"], row["lemma"])
        groups.setdefault(key, []).append(row)

    projected = []
    for group in groups.values():
        primary = group[0]
        point = points_by_id[primary["point_id"]]
        relations = []
        seen_relations = set()
        for row in group:
            for source in sources_by_lexeme.get(row["id"], []):
                relation_key = (
                    source["source_id"],
                    source.get("source_item_id") or "",
                    source["source_url"],
                )
                if relation_key in seen_relations:
                    continue
                seen_relations.add(relation_key)
                relations.append(
                    {
                        "source_id": source["source_id"],
                        "source_item_id": source.get("source_item_id") or "",
                        "source_url": source["source_url"],
                        "is_primary": bool(source.get("is_primary")),
                        "retrieved_at": source.get("retrieved_at"),
                        "content_hash": source.get("content_hash"),
                        "detail_url": point.get("detail_url") or point["source_url"],
                    }
                )
        projected.append(
            {
                "dialect_point": {
                    "source_id": point["source_id"],
                    "source_item_id": point.get("source_item_id") or "",
                    "source_url": point["source_url"],
                    "detail_url": point.get("detail_url") or point["source_url"],
                    "region_raw": point.get("region_raw") or "",
                    "province": point.get("province") or "",
                    "city": point.get("city") or "",
                    "county": point.get("county") or "",
                    "dialect_name": point.get("dialect_name") or "",
                    "content_hash": point.get("content_hash"),
                    "source_relations": [
                        {
                            "source_id": point["source_id"],
                            "source_item_id": point.get("source_item_id") or "",
                            "source_url": point["source_url"],
                            "is_primary": True,
                            "retrieved_at": point.get("retrieved_at"),
                            "content_hash": point.get("content_hash"),
                        }
                    ],
                },
                "point_id": point["id"],
                "lemma": primary["lemma"],
                "phonetic": primary.get("phonetic") or "",
                "definition": primary.get("definition") or "",
                "example": primary.get("example") or "",
                "audio_url": primary.get("audio_url") or "",
                "audio_status": primary.get("audio_status") or "unknown",
                "confidence": primary.get("confidence") or "medium",
                "content_hash": primary.get("content_hash"),
                "source_relations": relations,
            }
        )

    return {
        "entity": "std_dialect_lexemes",
        "input_count": len(lexemes),
        "rows": projected,
        "conflicts": [],
        "skipped": skipped,
    }


def _resolve_database_path(batch, crawler_database_path):
    return Path(
        crawler_database_path
        or batch.get("crawler_database_path")
        or os.environ.get("CRAWLER_DB")
        or "crawler/data/crawler.db"
    )


def _db_value(value):
    if value is None or isinstance(value, (str, int, float)):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _existing_batch_result(conn, batch_key):
    row = conn.execute(
        "SELECT * FROM import_batches WHERE batch_key = ?", (batch_key,)
    ).fetchone()
    if row is None:
        return None
    data = dict(row)
    return BatchResult(
        batch_id=data["id"],
        status=data["status"],
        input_count=data["input_count"],
        inserted_count=data["inserted_count"],
        updated_count=data["updated_count"],
        skipped_count=data["skipped_count"],
        conflict_count=data["conflict_count"],
        failed_count=data["failed_count"],
        by_entity={},
    )


def _persist_conflicts(conn, batch_id, domain, entity_plan, created_at):
    for conflict in entity_plan["conflicts"]:
        conn.execute(
            """
            INSERT INTO import_conflicts (
                batch_id, content_domain, target_table, target_key,
                target_field, existing_value, incoming_value,
                existing_source_id, existing_source_url, incoming_source_id,
                incoming_source_url, existing_retrieved_at,
                incoming_retrieved_at, reason, resolution, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'unresolved', ?)
            """,
            (
                batch_id,
                domain,
                entity_plan["entity"],
                conflict.get("target_key") or "",
                conflict["field"],
                _db_value(conflict.get("existing_value")),
                _db_value(conflict.get("incoming_value")),
                conflict.get("existing_source_id"),
                conflict.get("existing_source_url"),
                conflict.get("incoming_source_id"),
                conflict.get("incoming_source_url"),
                conflict.get("existing_retrieved_at"),
                conflict.get("incoming_retrieved_at"),
                "value_mismatch",
                created_at,
            ),
        )


def _persist_batch_items(conn, batch_id, domain, entity_plan, created_at):
    for row in entity_plan["rows"]:
        point = row.get("dialect_point") or {}
        source_id = row.get("source_id") or point.get("source_id")
        source_item_id = (
            row.get("source_item_id") or point.get("source_item_id")
        )
        target_key = json.dumps(
            [
                source_id,
                source_item_id,
                row.get("id"),
                row.get("lemma"),
                row.get("point_id"),
            ],
            ensure_ascii=False,
        )
        conn.execute(
            """
            INSERT INTO import_batch_items (
                batch_id, content_domain, target_table, target_key,
                operation, status, source_id, source_item_id,
                content_hash, created_at, extra
            ) VALUES (?, ?, ?, ?, 'insert', 'planned', ?, ?, ?, ?, ?)
            """,
            (
                batch_id,
                domain,
                entity_plan["entity"],
                target_key,
                source_id,
                source_item_id,
                row.get("content_hash"),
                created_at,
                json.dumps(row, ensure_ascii=False, default=str),
            ),
        )


def run_batch(
    domain,
    batch,
    *,
    crawler_database_path=None,
    source_registry_path=None,
):
    _validate(domain, batch)
    if batch.get("dry_run", True) is not True:
        raise NotImplementedError("only dry_run batches are implemented")

    db_path = _resolve_database_path(batch, crawler_database_path)
    conn = database.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        existing = _existing_batch_result(conn, batch["batch_key"])
        if existing is not None:
            return existing

        db_sources = _load_sources(conn)
        registry = source_registry.load_registry(source_registry_path)
        priorities = _source_priorities(db_sources, registry)
        started_at = _now()
        cursor = conn.execute(
            """
            INSERT INTO import_batches (
                batch_key, content_domain, started_at, status,
                target_database, converter_version, extra
            ) VALUES (?, ?, ?, 'running', ?, ?, ?)
            """,
            (
                batch["batch_key"],
                domain,
                started_at,
                batch["target_database"],
                batch["converter_version"],
                json.dumps(
                    {
                        "dry_run": True,
                        "source_ids": batch.get("source_ids") or [],
                        "std_entity_ids": batch.get("std_entity_ids") or [],
                    },
                    ensure_ascii=False,
                ),
            ),
        )
        batch_id = cursor.lastrowid

        if domain == "ich":
            entity_plan = _ich_plan(conn, batch, priorities, registry)
        elif domain == "agri":
            entity_plan = _agri_plan(conn, batch, priorities, registry)
        elif domain == "jobs":
            entity_plan = _job_plan(conn, batch, priorities, registry)
        else:
            entity_plan = _dialect_plan(conn, batch, priorities, registry)

        inserted = len(entity_plan["rows"])
        skipped = entity_plan.get("skipped", 0)
        input_count = entity_plan["input_count"] + skipped
        conflicts = len(entity_plan["conflicts"])
        failed = 0
        unexplained = input_count - inserted - conflicts - failed - skipped
        if unexplained:
            skipped += unexplained
        status = "partial" if conflicts or failed else "succeeded"

        _persist_conflicts(conn, batch_id, domain, entity_plan, started_at)
        _persist_batch_items(
            conn, batch_id, domain, entity_plan, started_at
        )
        conn.execute(
            """
            UPDATE import_batches SET
                finished_at = ?, status = ?, input_count = ?,
                inserted_count = ?, updated_count = 0, skipped_count = ?,
                conflict_count = ?, failed_count = ?
            WHERE id = ?
            """,
            (
                _now(),
                status,
                input_count,
                inserted,
                skipped,
                conflicts,
                failed,
                batch_id,
            ),
        )
        conn.commit()
        by_entity = {
            entity_plan["entity"]: {
                "input_count": input_count,
                "rows": entity_plan["rows"],
                "conflicts": entity_plan["conflicts"],
                "skipped_count": skipped,
            }
        }
        return BatchResult(
            batch_id=batch_id,
            status=status,
            input_count=input_count,
            inserted_count=inserted,
            updated_count=0,
            skipped_count=skipped,
            conflict_count=conflicts,
            failed_count=failed,
            by_entity=by_entity,
        )
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def rollback_batch(batch_id, *, crawler_database_path=None):
    db_path = Path(
        crawler_database_path
        or os.environ.get("CRAWLER_DB")
        or "crawler/data/crawler.db"
    )
    conn = database.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT * FROM import_batches WHERE id = ?", (batch_id,)
        ).fetchone()
        if row is None:
            raise ValueError(f"unknown batch: {batch_id}")
        batch = dict(row)
        if batch["status"] == "running":
            raise ValueError(f"batch {batch_id} is still running")
        if batch["status"] == "rolled_back":
            return RollbackResult(
                batch_id=batch_id,
                status="rolled_back",
                rolled_back_count=0,
                skipped_count=batch["skipped_count"],
                conflict_count=batch["conflict_count"],
            )
        planned_count = conn.execute(
            """
            SELECT COUNT(*) FROM import_batch_items
            WHERE batch_id = ? AND status = 'planned'
            """,
            (batch_id,),
        ).fetchone()[0]
        conn.execute(
            """
            UPDATE import_batches SET
                status = 'rolled_back',
                finished_at = ?,
                rollback_note = ?
            WHERE id = ?
            """,
            (
                _now(),
                "dry-run batch had no business writes; planned items skipped",
                batch_id,
            ),
        )
        conn.commit()
        return RollbackResult(
            batch_id=batch_id,
            status="rolled_back",
            rolled_back_count=0,
            skipped_count=planned_count,
            conflict_count=batch["conflict_count"],
        )
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
