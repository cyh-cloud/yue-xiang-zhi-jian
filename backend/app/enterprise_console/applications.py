from __future__ import annotations

import json
import uuid
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.db import get_db
from app.enterprise_console.errors import (
    EnterpriseConflictError,
    EnterpriseNotFoundError,
    EnterpriseValidationError,
    ProviderConflictError,
    ProviderNotFoundError,
    ProviderUnavailableError,
    ProviderValidationError,
)
from app.enterprise_console.notifications import (
    deliver_after_commit,
    enqueue_enterprise_notification,
)

APPLICATION_STATUSES = {"pending", "viewed", "intent", "unsuitable"}
MANUAL_STATUSES = {"viewed", "intent", "unsuitable"}
STATUS_LABELS = {
    "pending": "待处理",
    "viewed": "已查看",
    "intent": "意向沟通",
    "unsuitable": "不合适",
}
CLOSED_STATUS_LABEL = "岗位已关闭"
APPLICATION_SORTS = {"submitted_desc", "submitted_asc"}
PLATFORM_TIMEZONE = ZoneInfo("Asia/Shanghai")


def _now_iso() -> str:
    return datetime.now(PLATFORM_TIMEZONE).isoformat(timespec="seconds")


def _enterprise_validation_error(
    field: str,
    message: str,
) -> EnterpriseValidationError:
    return EnterpriseValidationError(message, details={field: message})


def _provider_validation_error(
    field: str,
    message: str,
) -> ProviderValidationError:
    return ProviderValidationError(message, details={field: message})


def _normalize_enterprise_id(enterprise_id: int) -> int:
    if (
        isinstance(enterprise_id, bool)
        or not isinstance(enterprise_id, int)
        or enterprise_id <= 0
    ):
        raise _enterprise_validation_error(
            "enterprise_id",
            "Enterprise ID is invalid",
        )
    return enterprise_id


def _normalize_application_id(application_id: str) -> str:
    if not isinstance(application_id, str) or not application_id.strip():
        raise _enterprise_validation_error(
            "application_id",
            "Application ID is invalid",
        )
    return application_id.strip()


def _normalize_expected_version(expected_version: int) -> int:
    if (
        isinstance(expected_version, bool)
        or not isinstance(expected_version, int)
        or expected_version <= 0
    ):
        raise _enterprise_validation_error(
            "expected_version",
            "expected_version must be a positive integer",
        )
    return expected_version


def _normalize_student_id(student_id: int) -> int:
    if (
        isinstance(student_id, bool)
        or not isinstance(student_id, int)
        or student_id <= 0
    ):
        raise _provider_validation_error(
            "student_id",
            "student_id must be a positive integer",
        )
    return student_id


def _normalize_text(value, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _provider_validation_error(
            field,
            f"{field} is required",
        )
    return value.strip()


def _serialize_snapshot(snapshot: dict, field: str) -> str:
    try:
        return json.dumps(snapshot, ensure_ascii=False)
    except (TypeError, ValueError) as error:
        raise _provider_validation_error(
            field,
            f"{field} must be JSON serializable",
        ) from error


def _normalize_skill_profile(snapshot: dict | None) -> str | None:
    if snapshot is None:
        return None
    if not isinstance(snapshot, dict):
        raise _provider_validation_error(
            "skill_profile_snapshot",
            "skill_profile_snapshot must be an object",
        )
    if not snapshot:
        return None

    items = snapshot.get("items")
    if items is None or items == []:
        return None
    if not isinstance(items, list):
        raise _provider_validation_error(
            "skill_profile_snapshot",
            "skill profile items must be a list",
        )
    if any(not isinstance(item, dict) for item in items):
        raise _provider_validation_error(
            "skill_profile_snapshot",
            "skill profile items must contain objects",
        )
    return _serialize_snapshot(snapshot, "skill_profile_snapshot")


def _find_student(db, student_id: int):
    return db.execute(
        """
        SELECT id, name
        FROM users
        WHERE id = ? AND role = 'student'
        """,
        (student_id,),
    ).fetchone()


def _find_job(db, job_id: str):
    return db.execute(
        """
        SELECT
            job_id,
            enterprise_id,
            title,
            review_status,
            published_at,
            deleted_at
        FROM job_positions
        WHERE job_id = ?
        """,
        (job_id,),
    ).fetchone()


def _validate_visible_job(row) -> None:
    if (
        row["review_status"] != "approved"
        or row["deleted_at"] is not None
        or not isinstance(row["published_at"], str)
        or not row["published_at"].strip()
    ):
        raise ProviderConflictError("岗位当前不可投递")


def _find_idempotent_application(
    db,
    enterprise_id: int,
    idempotency_key: str,
):
    return db.execute(
        """
        SELECT *
        FROM job_applications
        WHERE enterprise_id = ? AND idempotency_key = ?
        """,
        (enterprise_id, idempotency_key),
    ).fetchone()


def _find_student_job_application(
    db,
    student_id: int,
    job_id: str,
):
    return db.execute(
        """
        SELECT *
        FROM job_applications
        WHERE student_id = ? AND job_id = ?
        """,
        (student_id, job_id),
    ).fetchone()


def _parse_snapshot(value, field: str):
    if value is None:
        return None
    try:
        snapshot = json.loads(value)
    except (TypeError, ValueError) as error:
        raise ProviderUnavailableError(
            f"{field} is unavailable"
        ) from error
    if not isinstance(snapshot, dict):
        raise ProviderUnavailableError(f"{field} is unavailable")
    return snapshot


def serialize_application(row) -> dict:
    if row is None:
        raise EnterpriseNotFoundError("Application was not found")

    data = dict(row)
    status = str(data["status"])
    position_closed_at = data.get("position_closed_at")
    position_closed = (
        isinstance(position_closed_at, str)
        and bool(position_closed_at.strip())
    )
    effective_status = (
        "closed"
        if position_closed and status == "pending"
        else status
    )
    skill_profile_attached = bool(
        data.get("skill_profile_attached")
    )
    skill_profile = (
        _parse_snapshot(
            data.get("skill_profile_snapshot_json"),
            "Skill profile snapshot",
        )
        if skill_profile_attached
        else None
    )

    return {
        "application_id": str(data["application_id"]),
        "job_id": str(data["job_id"]),
        "enterprise_id": int(data["enterprise_id"]),
        "student_id": int(data["student_id"]),
        "student_name": str(data["student_name"]),
        "job_title": str(data["job_title_snapshot"]),
        "resume_snapshot": _parse_snapshot(
            data["resume_snapshot_json"],
            "Resume snapshot",
        ),
        "skill_profile": skill_profile,
        "skill_profile_attached": skill_profile_attached,
        "status": status,
        "status_label": STATUS_LABELS.get(status, status),
        "status_version": int(data["status_version"]),
        "position_closed": position_closed,
        "position_closed_at": position_closed_at,
        "effective_status": effective_status,
        "effective_status_label": (
            CLOSED_STATUS_LABEL
            if effective_status == "closed"
            else STATUS_LABELS.get(status, status)
        ),
        "submitted_at": str(data["submitted_at"]),
    }


def record_application_submission(
    *,
    job_id: str,
    student_id: int,
    resume_snapshot: dict,
    skill_profile_snapshot: dict | None,
    idempotency_key: str,
) -> dict:
    normalized_job_id = _normalize_text(job_id, "job_id")
    normalized_student_id = _normalize_student_id(student_id)
    normalized_key = _normalize_text(
        idempotency_key,
        "idempotency_key",
    )
    if not isinstance(resume_snapshot, dict) or not resume_snapshot:
        raise _provider_validation_error(
            "resume_snapshot",
            "resume_snapshot must be a non-empty object",
        )
    resume_json = _serialize_snapshot(
        resume_snapshot,
        "resume_snapshot",
    )
    skill_json = _normalize_skill_profile(skill_profile_snapshot)

    db = get_db()
    outbox_id = None
    application = None

    with db:
        db.execute("BEGIN IMMEDIATE")
        student = _find_student(db, normalized_student_id)
        if student is None:
            raise _provider_validation_error(
                "student_id",
                "Student was not found",
            )

        job = _find_job(db, normalized_job_id)
        if job is None:
            raise ProviderNotFoundError("Job was not found")
        _validate_visible_job(job)
        enterprise_id = int(job["enterprise_id"])

        existing = _find_idempotent_application(
            db,
            enterprise_id,
            normalized_key,
        )
        if existing is not None:
            if (
                int(existing["student_id"]) != normalized_student_id
                or str(existing["job_id"]) != normalized_job_id
            ):
                raise ProviderConflictError(
                    "Idempotency key was reused for another request"
                )
            application = serialize_application(existing)
        else:
            duplicate = _find_student_job_application(
                db,
                normalized_student_id,
                normalized_job_id,
            )
            if duplicate is not None:
                application = serialize_application(duplicate)
            else:
                application_id = f"application-{uuid.uuid4().hex}"
                now = _now_iso()
                student_name = str(student["name"])
                job_title = str(job["title"])
                db.execute(
                    """
                    INSERT INTO job_applications (
                        application_id,
                        job_id,
                        enterprise_id,
                        student_id,
                        student_name,
                        job_title_snapshot,
                        resume_snapshot_json,
                        skill_profile_snapshot_json,
                        skill_profile_attached,
                        status,
                        status_version,
                        position_closed_at,
                        close_reason,
                        idempotency_key,
                        submitted_at,
                        updated_at
                    )
                    VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        'pending', 1, NULL, NULL, ?, ?, ?
                    )
                    """,
                    (
                        application_id,
                        normalized_job_id,
                        enterprise_id,
                        normalized_student_id,
                        student_name,
                        job_title,
                        resume_json,
                        skill_json,
                        int(skill_json is not None),
                        normalized_key,
                        now,
                        now,
                    ),
                )
                outbox_id = enqueue_enterprise_notification(
                    db,
                    event_type="application_submitted",
                    event_id=f"application_submitted:{application_id}",
                    payload={
                        "enterprise_id": enterprise_id,
                        "student_id": normalized_student_id,
                        "application_id": application_id,
                        "student_name": student_name,
                        "job_title": job_title,
                    },
                )
                row = db.execute(
                    """
                    SELECT *
                    FROM job_applications
                    WHERE application_id = ?
                    """,
                    (application_id,),
                ).fetchone()
                application = serialize_application(row)

    if outbox_id is not None:
        deliver_after_commit(outbox_id)
    return application


def _normalize_filter_job_id(value) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise _enterprise_validation_error(
            "job_id",
            "Job ID is invalid",
        )
    return value.strip()


def _normalize_filter_status(value) -> str | None:
    if value in (None, ""):
        return None
    if not isinstance(value, str) or value not in APPLICATION_STATUSES:
        raise _enterprise_validation_error(
            "status",
            "Application status is invalid",
        )
    return value


def _normalize_filter_date(value, field: str) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime) or not isinstance(value, date):
        raise _enterprise_validation_error(
            field,
            f"{field} must be a date",
        )
    return value


def _day_boundary(value: date) -> str:
    return datetime.combine(
        value,
        time.min,
        tzinfo=PLATFORM_TIMEZONE,
    ).isoformat(timespec="seconds")


def list_applications(
    enterprise_id: int,
    filters: dict | None = None,
) -> list[dict]:
    normalized_enterprise_id = _normalize_enterprise_id(enterprise_id)
    if filters is None:
        filters = {}
    if not isinstance(filters, dict):
        raise _enterprise_validation_error(
            "filters",
            "Application filters must be an object",
        )

    job_id = _normalize_filter_job_id(filters.get("job_id"))
    status = _normalize_filter_status(filters.get("status"))
    submitted_from = _normalize_filter_date(
        filters.get("submitted_from"),
        "submitted_from",
    )
    submitted_to = _normalize_filter_date(
        filters.get("submitted_to"),
        "submitted_to",
    )
    if (
        submitted_from is not None
        and submitted_to is not None
        and submitted_to < submitted_from
    ):
        raise _enterprise_validation_error(
            "submitted_to",
            "submitted_to must not be earlier than submitted_from",
        )

    sort = filters.get("sort")
    if sort is None:
        sort = "submitted_desc"
    if not isinstance(sort, str) or sort not in APPLICATION_SORTS:
        raise _enterprise_validation_error(
            "sort",
            "Application sort is invalid",
        )

    clauses = ["ja.enterprise_id = ?"]
    parameters = [normalized_enterprise_id]
    if job_id is not None:
        clauses.append("ja.job_id = ?")
        parameters.append(job_id)
    if status is not None:
        clauses.append("ja.status = ?")
        parameters.append(status)
    if submitted_from is not None:
        clauses.append("julianday(ja.submitted_at) >= julianday(?)")
        parameters.append(_day_boundary(submitted_from))
    if submitted_to is not None:
        clauses.append("julianday(ja.submitted_at) < julianday(?)")
        parameters.append(
            _day_boundary(submitted_to + timedelta(days=1))
        )

    direction = "DESC" if sort == "submitted_desc" else "ASC"
    rows = get_db().execute(
        f"""
        SELECT ja.*
        FROM job_applications ja
        WHERE {' AND '.join(clauses)}
        ORDER BY
            julianday(ja.submitted_at) {direction},
            ja.application_id ASC
        """,
        parameters,
    ).fetchall()
    return [serialize_application(row) for row in rows]


def _owned_application(
    db,
    enterprise_id: int,
    application_id: str,
):
    return db.execute(
        """
        SELECT *
        FROM job_applications
        WHERE application_id = ? AND enterprise_id = ?
        """,
        (application_id, enterprise_id),
    ).fetchone()


def _status_history(db, application_id: str) -> list[dict]:
    rows = db.execute(
        """
        SELECT
            sequence_no,
            previous_status,
            new_status,
            actor_enterprise_id,
            event_id,
            created_at
        FROM job_application_status_history
        WHERE application_id = ?
        ORDER BY sequence_no ASC
        """,
        (application_id,),
    ).fetchall()
    return [
        {
            "sequence_no": int(row["sequence_no"]),
            "previous_status": str(row["previous_status"]),
            "new_status": str(row["new_status"]),
            "actor_enterprise_id": int(row["actor_enterprise_id"]),
            "event_id": str(row["event_id"]),
            "created_at": str(row["created_at"]),
        }
        for row in rows
    ]


def get_application(
    enterprise_id: int,
    application_id: str,
) -> dict:
    normalized_enterprise_id = _normalize_enterprise_id(enterprise_id)
    normalized_application_id = _normalize_application_id(
        application_id
    )
    db = get_db()
    row = _owned_application(
        db,
        normalized_enterprise_id,
        normalized_application_id,
    )
    if row is None:
        raise EnterpriseNotFoundError("Application was not found")

    application = serialize_application(row)
    application["status_history"] = _status_history(
        db,
        normalized_application_id,
    )
    return application


def _require_status_version(row, expected_version: int) -> None:
    if int(row["status_version"]) != expected_version:
        raise ProviderConflictError("Application status version conflict")


def change_application_status(
    enterprise_id: int,
    application_id: str,
    expected_version: int,
    status: str,
) -> dict:
    normalized_enterprise_id = _normalize_enterprise_id(enterprise_id)
    normalized_application_id = _normalize_application_id(
        application_id
    )
    normalized_version = _normalize_expected_version(expected_version)
    db = get_db()
    outbox_id = None
    result = None

    with db:
        db.execute("BEGIN IMMEDIATE")
        row = _owned_application(
            db,
            normalized_enterprise_id,
            normalized_application_id,
        )
        if row is None:
            raise EnterpriseNotFoundError("Application was not found")
        _require_status_version(row, normalized_version)
        if row["position_closed_at"] is not None:
            raise EnterpriseConflictError(
                "岗位已关闭，申请状态不可再变更"
            )
        if (
            not isinstance(status, str)
            or status not in MANUAL_STATUSES
        ):
            raise _enterprise_validation_error(
                "status",
                "申请状态不正确",
            )

        if status == row["status"]:
            result = {
                "application": serialize_application(row),
                "changed": False,
            }
        else:
            next_version = int(row["status_version"]) + 1
            now = _now_iso()
            event_id = (
                f"application_status:{normalized_application_id}:"
                f"v{next_version}:{status}"
            )
            cursor = db.execute(
                """
                UPDATE job_applications
                SET status = ?,
                    status_version = ?,
                    updated_at = ?
                WHERE application_id = ?
                  AND enterprise_id = ?
                  AND status_version = ?
                  AND position_closed_at IS NULL
                """,
                (
                    status,
                    next_version,
                    now,
                    normalized_application_id,
                    normalized_enterprise_id,
                    normalized_version,
                ),
            )
            if cursor.rowcount != 1:
                raise ProviderConflictError(
                    "Application status version conflict"
                )
            db.execute(
                """
                INSERT INTO job_application_status_history (
                    application_id,
                    sequence_no,
                    previous_status,
                    new_status,
                    actor_enterprise_id,
                    event_id,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    normalized_application_id,
                    next_version,
                    str(row["status"]),
                    status,
                    normalized_enterprise_id,
                    event_id,
                    now,
                ),
            )
            outbox_id = enqueue_enterprise_notification(
                db,
                event_type="application_status",
                event_id=event_id,
                payload={
                    "student_id": int(row["student_id"]),
                    "application_id": normalized_application_id,
                    "status": STATUS_LABELS[status],
                },
            )
            updated = _owned_application(
                db,
                normalized_enterprise_id,
                normalized_application_id,
            )
            result = {
                "application": serialize_application(updated),
                "changed": True,
            }

    if outbox_id is not None:
        deliver_after_commit(outbox_id)
    return result


def close_applications_for_deleted_job(db, job_row, now: str) -> dict:
    rows = db.execute(
        """
        SELECT *
        FROM job_applications
        WHERE job_id = ?
        ORDER BY id
        """,
        (str(job_row["job_id"]),),
    ).fetchall()
    closed = 0
    historical = 0
    notification_count = 0
    outbox_ids = []
    for row in rows:
        if row["position_closed_at"] is not None:
            continue
        next_version = int(row["status_version"]) + 1
        db.execute(
            """
            UPDATE job_applications
            SET position_closed_at = ?,
                close_reason = 'position_deleted',
                status_version = ?,
                updated_at = ?
            WHERE application_id = ? AND position_closed_at IS NULL
            """,
            (
                now,
                next_version,
                now,
                str(row["application_id"]),
            ),
        )
        if row["status"] == "pending":
            closed += 1
            event_id = (
                f"position_closed:{job_row['job_id']}:"
                f"{row['application_id']}"
            )
            outbox_ids.append(
                enqueue_enterprise_notification(
                    db,
                    event_type="position_closed",
                    event_id=event_id,
                    payload={
                        "student_ids": [int(row["student_id"])],
                        "position_id": str(job_row["job_id"]),
                        "job_title": str(row["job_title_snapshot"]),
                    },
                )
            )
            notification_count += 1
        else:
            historical += 1
    return {
        "closed_application_count": closed,
        "historical_application_count": historical,
        "notification_count": notification_count,
        "outbox_ids": outbox_ids,
    }


__all__ = [
    "APPLICATION_STATUSES",
    "APPLICATION_SORTS",
    "CLOSED_STATUS_LABEL",
    "MANUAL_STATUSES",
    "PLATFORM_TIMEZONE",
    "STATUS_LABELS",
    "change_application_status",
    "close_applications_for_deleted_job",
    "get_application",
    "list_applications",
    "record_application_submission",
    "serialize_application",
]
