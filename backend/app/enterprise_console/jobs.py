from __future__ import annotations

import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from app.db import get_db
from app.enterprise_console.errors import (
    EnterpriseNotFoundError,
    EnterpriseValidationError,
    ProviderConflictError,
    ProviderError,
    ProviderUnavailableError,
    ProviderValidationError,
)
from app.enterprise_console.review import get_content_review_provider

JOB_REVIEW_STATUSES = {"pending", "approved", "rejected"}
JOB_REVIEW_CONTENT_TYPE = "job_position"
JOB_TEXT_LIMITS = {
    "title": 100,
    "salary": 80,
    "location": 120,
    "description": 4000,
}
JOB_TRANSITIONS = {
    ("pending", "pending"): "edit",
    ("pending", "approved"): "approve",
    ("pending", "rejected"): "reject",
    ("approved", "pending"): "edit",
    ("rejected", "pending"): "edit",
}

_JOB_CONTENT_FIELDS = ("title", "salary", "location", "category_id", "description")
_JOB_SERIALIZED_FIELDS = (
    "job_id",
    "enterprise_id",
    "title",
    "salary",
    "location",
    "category_id",
    "category_name",
    "description",
    "review_status",
    "version",
    "rejection_opinion",
    "published_at",
    "deleted_at",
    "created_at",
    "updated_at",
)
_PUBLIC_POSITION_FIELDS = (
    "job_id",
    "enterprise_id",
    "enterprise_name",
    "title",
    "salary",
    "location",
    "category_id",
    "category_name",
    "description",
    "review_status",
    "version",
    "published_at",
    "updated_at",
)
_PUBLIC_POSITION_TEXT_FIELDS = (
    "job_id",
    "enterprise_name",
    "title",
    "salary",
    "location",
    "category_name",
    "description",
    "review_status",
    "published_at",
    "updated_at",
)
_PLATFORM_TIMEZONE = ZoneInfo("Asia/Shanghai")


def _now_iso() -> str:
    return datetime.now(_PLATFORM_TIMEZONE).isoformat(timespec="seconds")


def _validation_error(field: str, message: str) -> EnterpriseValidationError:
    return EnterpriseValidationError(message, details={field: message})


def _normalize_enterprise_id(enterprise_id: int) -> int:
    if (
        isinstance(enterprise_id, bool)
        or not isinstance(enterprise_id, int)
        or enterprise_id <= 0
    ):
        raise _validation_error("enterprise_id", "Enterprise ID is invalid")
    return enterprise_id


def _require_enterprise(db, enterprise_id: int) -> None:
    row = db.execute(
        """
        SELECT id
        FROM users
        WHERE id = ? AND role = 'enterprise'
        """,
        (enterprise_id,),
    ).fetchone()
    if row is None:
        raise EnterpriseNotFoundError("Enterprise was not found")


def _normalize_job_id(job_id: str) -> str:
    if not isinstance(job_id, str) or not job_id.strip():
        raise _validation_error("job_id", "Job ID is invalid")
    return job_id


def _normalize_payload(db, payload: dict, current_row=None) -> dict:
    if not isinstance(payload, dict):
        raise _validation_error("payload", "Job payload must be an object")

    normalized = {}
    for field in ("title", "salary", "location", "description"):
        value = payload.get(field)
        if not isinstance(value, str):
            raise _validation_error(field, f"{field} must be text")
        value = value.strip()
        if not value:
            raise _validation_error(field, f"{field} is required")
        if len(value) > JOB_TEXT_LIMITS[field]:
            raise _validation_error(
                field,
                f"{field} exceeds {JOB_TEXT_LIMITS[field]} characters",
            )
        normalized[field] = value

    category_id = payload.get("category_id")
    if (
        isinstance(category_id, bool)
        or not isinstance(category_id, int)
        or category_id <= 0
    ):
        raise _validation_error(
            "category_id",
            "category_id must be a positive integer",
        )

    category = db.execute(
        """
        SELECT id, name
        FROM interest_tags
        WHERE id = ? AND group_key = 'job' AND is_active = 1
        """,
        (category_id,),
    ).fetchone()
    if category is None:
        raise _validation_error(
            "category_id",
            "Job category does not exist or is inactive",
        )

    normalized["category_id"] = category_id
    if (
        current_row is not None
        and int(current_row["category_id"]) == category_id
    ):
        normalized["category_name"] = current_row["category_name"]
    else:
        normalized["category_name"] = category["name"]
    return normalized


def _review_payload(normalized: dict) -> dict:
    return {
        "title": normalized["title"],
        "salary": normalized["salary"],
        "location": normalized["location"],
        "category": normalized["category_id"],
        "description": normalized["description"],
    }


def _payload_has_changes(row, normalized: dict) -> bool:
    return any(
        row[field] != normalized[field]
        for field in _JOB_CONTENT_FIELDS
    )


def _provider_call(callback):
    try:
        return callback()
    except (
        ProviderValidationError,
        ProviderConflictError,
        ProviderUnavailableError,
    ):
        raise
    except ProviderError as error:
        raise ProviderUnavailableError(
            "Content review service is unavailable"
        ) from error


def _review_version(record: dict) -> int:
    version = record.get("version")
    if (
        isinstance(version, bool)
        or not isinstance(version, int)
        or version <= 0
    ):
        raise ProviderValidationError("Review version is invalid")
    return version


def _apply_review_record(
    db,
    job_id: str,
    record: dict,
    *,
    expected_status: str | None = None,
    minimum_version: int | None = None,
) -> dict:
    if not isinstance(record, dict):
        raise ProviderValidationError("Review record must be an object")
    if record.get("content_id") != job_id:
        raise ProviderValidationError("Review content ID does not match")
    if (
        record.get("content_type") is not None
        and record["content_type"] != JOB_REVIEW_CONTENT_TYPE
    ):
        raise ProviderValidationError("Review content type does not match")

    review_status = record.get("review_status")
    if review_status not in JOB_REVIEW_STATUSES:
        raise ProviderValidationError("Review status is invalid")
    if expected_status is not None and review_status != expected_status:
        raise ProviderValidationError(
            f"Review status must be {expected_status}"
        )

    version = _review_version(record)
    local = db.execute(
        """
        SELECT version
        FROM job_positions
        WHERE job_id = ?
        """,
        (job_id,),
    ).fetchone()
    if local is None:
        raise EnterpriseNotFoundError("Job was not found")
    local_version = int(local["version"])
    if version < local_version:
        raise ProviderConflictError("Review version moved backwards")
    if minimum_version is not None and version < minimum_version:
        raise ProviderConflictError("Review version did not advance")

    rejection_opinion = record.get("rejection_opinion")
    published_at = record.get("published_at")
    if review_status == "approved":
        if (
            not isinstance(published_at, str)
            or not published_at.strip()
        ):
            raise ProviderValidationError(
                "Approved review requires a publication time"
            )
        rejection_opinion = None
    elif review_status == "rejected":
        published_at = None
        if (
            not isinstance(rejection_opinion, str)
            or not rejection_opinion.strip()
        ):
            raise ProviderValidationError(
                "Rejected review requires an opinion"
            )
    else:
        published_at = None
        rejection_opinion = None

    updated_at = record.get("updated_at")
    if not isinstance(updated_at, str) or not updated_at.strip():
        updated_at = _now_iso()

    db.execute(
        """
        UPDATE job_positions
        SET review_status = ?,
            version = ?,
            rejection_opinion = ?,
            published_at = ?,
            updated_at = ?
        WHERE job_id = ?
        """,
        (
            review_status,
            version,
            rejection_opinion,
            published_at,
            updated_at,
            job_id,
        ),
    )
    return _serialize_row_by_id(db, job_id)


def _get_job_row(db, enterprise_id: int, job_id: str):
    return db.execute(
        """
        SELECT *
        FROM job_positions
        WHERE job_id = ?
          AND enterprise_id = ?
          AND deleted_at IS NULL
        """,
        (job_id, enterprise_id),
    ).fetchone()


def _owned_job(
    db,
    enterprise_id: int,
    job_id: str,
    *,
    include_deleted: bool = False,
):
    deleted_clause = "" if include_deleted else " AND deleted_at IS NULL"
    return db.execute(
        f"""
        SELECT *
        FROM job_positions
        WHERE job_id = ?
          AND enterprise_id = ?
          {deleted_clause}
        """,
        (job_id, enterprise_id),
    ).fetchone()


def _require_version(row, expected_version: int) -> None:
    if int(row["version"]) != expected_version:
        raise ProviderConflictError("Job version conflict")


def _get_job_row_by_id(db, job_id: str):
    return db.execute(
        """
        SELECT *
        FROM job_positions
        WHERE job_id = ?
        """,
        (job_id,),
    ).fetchone()


def _serialize_row_by_id(db, job_id: str) -> dict:
    row = _get_job_row_by_id(db, job_id)
    if row is None:
        raise EnterpriseNotFoundError("Job was not found")
    return serialize_job(row)


def serialize_job(row) -> dict:
    data = dict(row)
    return {
        field: data[field]
        for field in _JOB_SERIALIZED_FIELDS
    }


def _positive_int(value) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        normalized = int(value)
    except (TypeError, ValueError):
        return None
    return normalized if normalized > 0 else None


def _visible_position_payload(row) -> dict | None:
    if row is None:
        return None

    data = dict(row)
    if data.get("review_status") != "approved":
        return None
    enterprise_id = _positive_int(data.get("enterprise_id"))
    category_id = _positive_int(data.get("category_id"))
    version = _positive_int(data.get("version"))
    if enterprise_id is None or category_id is None or version is None:
        return None
    if any(
        not isinstance(data.get(field), str)
        or not data[field].strip()
        for field in _PUBLIC_POSITION_TEXT_FIELDS
    ):
        return None

    payload = {
        field: data.get(field)
        for field in _PUBLIC_POSITION_FIELDS
    }
    payload["enterprise_id"] = enterprise_id
    payload["category_id"] = category_id
    payload["version"] = version
    return payload


def list_published_position_records() -> list[dict]:
    rows = get_db().execute(
        """
        SELECT
            jp.job_id,
            jp.enterprise_id,
            u.name AS enterprise_name,
            jp.title,
            jp.salary,
            jp.location,
            jp.category_id,
            jp.category_name,
            jp.description,
            jp.review_status,
            jp.version,
            jp.published_at,
            jp.updated_at
        FROM job_positions jp
        JOIN users u ON u.id = jp.enterprise_id
        WHERE jp.review_status = 'approved'
          AND jp.deleted_at IS NULL
          AND jp.published_at IS NOT NULL
          AND trim(jp.published_at) <> ''
        ORDER BY jp.published_at DESC, jp.job_id ASC
        """
    ).fetchall()

    records = []
    for row in rows:
        record = _visible_position_payload(row)
        if record is not None:
            records.append(record)
    return records


def get_published_position_record(job_id: str) -> dict | None:
    normalized = str(job_id or "").strip()
    if not normalized:
        return None
    row = get_db().execute(
        """
        SELECT
            jp.job_id,
            jp.enterprise_id,
            u.name AS enterprise_name,
            jp.title,
            jp.salary,
            jp.location,
            jp.category_id,
            jp.category_name,
            jp.description,
            jp.review_status,
            jp.version,
            jp.published_at,
            jp.updated_at
        FROM job_positions jp
        JOIN users u ON u.id = jp.enterprise_id
        WHERE jp.job_id = ?
          AND jp.review_status = 'approved'
          AND jp.deleted_at IS NULL
          AND jp.published_at IS NOT NULL
          AND trim(jp.published_at) <> ''
        """,
        (normalized,),
    ).fetchone()
    return _visible_position_payload(row)


def create_job(enterprise_id: int, payload: dict) -> dict:
    normalized_enterprise_id = _normalize_enterprise_id(enterprise_id)
    db = get_db()
    job_id = f"job-{uuid.uuid4().hex}"
    now = _now_iso()

    with db:
        db.execute("BEGIN IMMEDIATE")
        _require_enterprise(db, normalized_enterprise_id)
        normalized = _normalize_payload(db, payload)
        db.execute(
            """
            INSERT INTO job_positions (
                job_id,
                enterprise_id,
                title,
                salary,
                location,
                category_id,
                category_name,
                description,
                review_status,
                version,
                rejection_opinion,
                published_at,
                deleted_at,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', 1, NULL, NULL, NULL, ?, ?)
            """,
            (
                job_id,
                normalized_enterprise_id,
                normalized["title"],
                normalized["salary"],
                normalized["location"],
                normalized["category_id"],
                normalized["category_name"],
                normalized["description"],
                now,
                now,
            ),
        )
        record = _provider_call(
            lambda: get_content_review_provider().submit_for_review(
                content_type=JOB_REVIEW_CONTENT_TYPE,
                content_id=job_id,
                submitter_id=normalized_enterprise_id,
                expected_version=1,
                payload=_review_payload(normalized),
            )
        )
        return _apply_review_record(
            db,
            job_id,
            record,
            expected_status="pending",
            minimum_version=1,
        )


def edit_job(
    enterprise_id: int,
    job_id: str,
    expected_version: int,
    payload: dict,
) -> dict:
    normalized_enterprise_id = _normalize_enterprise_id(enterprise_id)
    normalized_job_id = _normalize_job_id(job_id)
    if (
        isinstance(expected_version, bool)
        or not isinstance(expected_version, int)
        or expected_version <= 0
    ):
        raise _validation_error(
            "expected_version",
            "expected_version must be a positive integer",
        )

    db = get_db()
    with db:
        db.execute("BEGIN IMMEDIATE")
        row = _get_job_row(
            db,
            normalized_enterprise_id,
            normalized_job_id,
        )
        if row is None:
            raise EnterpriseNotFoundError("Job was not found")
        current_version = int(row["version"])
        if current_version != expected_version:
            raise ProviderConflictError("Job version conflict")

        normalized = _normalize_payload(db, payload, current_row=row)
        if not _payload_has_changes(row, normalized):
            return serialize_job(row)

        record = _provider_call(
            lambda: get_content_review_provider().edit(
                content_type=JOB_REVIEW_CONTENT_TYPE,
                content_id=normalized_job_id,
                submitter_id=normalized_enterprise_id,
                expected_version=current_version,
                payload=_review_payload(normalized),
            )
        )
        db.execute(
            """
            UPDATE job_positions
            SET title = ?,
                salary = ?,
                location = ?,
                category_id = ?,
                category_name = ?,
                description = ?,
                updated_at = ?
            WHERE job_id = ? AND enterprise_id = ?
            """,
            (
                normalized["title"],
                normalized["salary"],
                normalized["location"],
                normalized["category_id"],
                normalized["category_name"],
                normalized["description"],
                _now_iso(),
                normalized_job_id,
                normalized_enterprise_id,
            ),
        )
        _apply_review_record(
            db,
            normalized_job_id,
            record,
            expected_status="pending",
            minimum_version=current_version + 1,
        )
        return sync_job_review_projection(normalized_job_id)


def sync_job_review_projection(job_id: str) -> dict:
    normalized_job_id = _normalize_job_id(job_id)
    db = get_db()
    if db.in_transaction:
        return _sync_job_review_projection(db, normalized_job_id)

    with db:
        db.execute("BEGIN IMMEDIATE")
        return _sync_job_review_projection(db, normalized_job_id)


def _sync_job_review_projection(db, job_id: str) -> dict:
    row = _get_job_row_by_id(db, job_id)
    if row is None:
        raise EnterpriseNotFoundError("Job was not found")

    record = _provider_call(
        lambda: get_content_review_provider().get_review_status(
            content_type=JOB_REVIEW_CONTENT_TYPE,
            content_id=job_id,
        )
    )
    if record is None:
        return serialize_job(row)
    return _apply_review_record(db, job_id, record)


def list_jobs(
    enterprise_id: int,
    review_status: str | None = None,
) -> list[dict]:
    normalized_enterprise_id = _normalize_enterprise_id(enterprise_id)
    parameters = [normalized_enterprise_id]
    status_filter = ""
    if review_status not in (None, "all"):
        if review_status not in JOB_REVIEW_STATUSES:
            raise _validation_error(
                "review_status",
                "Review status is invalid",
            )
        status_filter = " AND review_status = ?"
        parameters.append(review_status)

    rows = get_db().execute(
        f"""
        SELECT *
        FROM job_positions
        WHERE enterprise_id = ?
          AND deleted_at IS NULL
          {status_filter}
        ORDER BY updated_at DESC, id DESC
        """,
        parameters,
    ).fetchall()
    return [serialize_job(row) for row in rows]


def get_job(enterprise_id: int, job_id: str) -> dict:
    normalized_enterprise_id = _normalize_enterprise_id(enterprise_id)
    normalized_job_id = _normalize_job_id(job_id)
    row = _get_job_row(
        get_db(),
        normalized_enterprise_id,
        normalized_job_id,
    )
    if row is None:
        raise EnterpriseNotFoundError("Job was not found")
    return serialize_job(row)


def delete_job(
    enterprise_id: int,
    job_id: str,
    expected_version: int | None = None,
) -> dict:
    normalized_enterprise_id = _normalize_enterprise_id(enterprise_id)
    normalized_job_id = _normalize_job_id(job_id)
    if expected_version is not None and (
        isinstance(expected_version, bool)
        or not isinstance(expected_version, int)
        or expected_version <= 0
    ):
        raise _validation_error(
            "expected_version",
            "expected_version must be a positive integer",
        )

    from app.enterprise_console.applications import (
        close_applications_for_deleted_job,
    )
    from app.enterprise_console.notifications import deliver_after_commit

    db = get_db()
    with db:
        db.execute("BEGIN IMMEDIATE")
        row = _owned_job(
            db,
            normalized_enterprise_id,
            normalized_job_id,
            include_deleted=True,
        )
        if row is None:
            raise EnterpriseNotFoundError("Job was not found")
        if row["deleted_at"] is not None:
            return {
                "deleted": True,
                "changed": False,
                "closed_application_count": 0,
                "historical_application_count": 0,
                "notification_count": 0,
            }
        if expected_version is not None:
            _require_version(row, expected_version)

        now = _now_iso()
        closure = close_applications_for_deleted_job(db, row, now)
        cursor = db.execute(
            """
            UPDATE job_positions
            SET deleted_at = ?, updated_at = ?
            WHERE job_id = ?
              AND enterprise_id = ?
              AND deleted_at IS NULL
            """,
            (
                now,
                now,
                normalized_job_id,
                normalized_enterprise_id,
            ),
        )
        if cursor.rowcount != 1:
            raise ProviderConflictError("职位状态已变化")
        result = {
            "deleted": True,
            "changed": True,
            "closed_application_count": (
                closure["closed_application_count"]
            ),
            "historical_application_count": (
                closure["historical_application_count"]
            ),
            "notification_count": closure["notification_count"],
        }

    for outbox_id in closure["outbox_ids"]:
        deliver_after_commit(outbox_id)
    return result


__all__ = [
    "JOB_REVIEW_CONTENT_TYPE",
    "JOB_REVIEW_STATUSES",
    "JOB_TEXT_LIMITS",
    "JOB_TRANSITIONS",
    "create_job",
    "delete_job",
    "edit_job",
    "get_job",
    "get_published_position_record",
    "list_jobs",
    "list_published_position_records",
    "serialize_job",
    "sync_job_review_projection",
]
