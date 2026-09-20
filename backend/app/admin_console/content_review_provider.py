from __future__ import annotations

import json
import sqlite3

from app.admin_console.errors import (
    ProviderAccessDeniedError,
    ProviderConflictError,
    ProviderNotFoundError,
    ProviderValidationError,
)
from app.admin_console.time_utils import platform_now_iso
from app.db import get_db


CONTENT_TYPES = frozenset({"course_video", "job_position"})
REVIEWER_ROLES = frozenset({"admin", "super_admin"})
REVIEW_STATUSES = frozenset({"pending", "approved", "rejected"})
SAVEPOINT_NAME = "content_review_provider"


def _validation_error(message: str, code: str, **details) -> ProviderValidationError:
    return ProviderValidationError(message, code=code, details=details)


def _conflict_error(message: str, code: str, **details) -> ProviderConflictError:
    return ProviderConflictError(message, code=code, details=details)


def _positive_int(value: object, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise _validation_error(
            f"{field} 必须是正整数",
            "review_validation_failed",
            field=field,
        )
    return value


def _content_type(value: object) -> str:
    if not isinstance(value, str) or value not in CONTENT_TYPES:
        raise _validation_error(
            "内容类型不正确",
            "review_type_invalid",
            content_type=value,
        )
    return value


def _content_id(value: object) -> str:
    if not isinstance(value, str):
        raise _validation_error(
            "内容 ID 必须是文本",
            "review_content_id_invalid",
            field="content_id",
        )
    normalized = value.strip()
    if not normalized:
        raise _validation_error(
            "内容 ID 不能为空",
            "review_content_id_invalid",
            field="content_id",
        )
    return normalized


def _payload(value: object) -> dict:
    if not isinstance(value, dict):
        raise _validation_error(
            "审核载荷必须是对象",
            "review_payload_invalid",
            field="payload",
        )
    return dict(value)


def _payload_json(payload: dict) -> str:
    try:
        return json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as error:
        raise _validation_error(
            "审核载荷必须可序列化",
            "review_payload_invalid",
            field="payload",
        ) from error


def _serialize_record(row: sqlite3.Row) -> dict:
    return {
        "content_type": str(row["content_type"]),
        "content_id": str(row["content_id"]),
        "submitter_id": int(row["submitter_id"]),
        "review_status": str(row["review_status"]),
        "version": int(row["version"]),
        "rejection_opinion": row["rejection_opinion"],
        "published_at": row["published_at"],
        "created_at": str(row["created_at"]),
        "updated_at": str(row["updated_at"]),
    }


def _begin(db: sqlite3.Connection) -> bool:
    if db.in_transaction:
        db.execute(f"SAVEPOINT {SAVEPOINT_NAME}")
        return False
    db.execute("BEGIN IMMEDIATE")
    return True


def _finish(db: sqlite3.Connection, owns_transaction: bool) -> None:
    if owns_transaction:
        db.commit()
    else:
        db.execute(f"RELEASE SAVEPOINT {SAVEPOINT_NAME}")


def _rollback(db: sqlite3.Connection, owns_transaction: bool) -> None:
    if owns_transaction:
        db.rollback()
    else:
        db.execute(f"ROLLBACK TO SAVEPOINT {SAVEPOINT_NAME}")
        db.execute(f"RELEASE SAVEPOINT {SAVEPOINT_NAME}")


def emit_review_result(**payload) -> dict:
    from app.messaging.events import emit_review_result as emit

    return emit(**payload)


class DatabaseContentReviewProvider:
    def submit_for_review(
        self,
        *,
        content_type: str,
        content_id: str,
        submitter_id: int,
        expected_version: int,
        payload: dict,
    ) -> dict:
        normalized_type = _content_type(content_type)
        normalized_id = _content_id(content_id)
        normalized_submitter = _positive_int(
            submitter_id,
            field="submitter_id",
        )
        normalized_version = _positive_int(
            expected_version,
            field="expected_version",
        )
        normalized_payload = _payload(payload)
        payload_json = _payload_json(normalized_payload)

        db = get_db()
        owns_transaction = _begin(db)
        try:
            owner = self._load_owner(
                db,
                normalized_type,
                normalized_id,
                normalized_submitter,
            )
            self._require_owner_version(owner, normalized_version)
            existing = self._load_record(
                db,
                normalized_type,
                normalized_id,
            )
            now = platform_now_iso()

            if existing is None:
                db.execute(
                    """
                    INSERT INTO content_review_records (
                        content_type, content_id, submitter_id,
                        review_status, version, rejection_opinion,
                        published_at, payload_json, created_at, updated_at
                    )
                    VALUES (?, ?, ?, 'pending', ?, NULL, NULL, ?, ?, ?)
                    """,
                    (
                        normalized_type,
                        normalized_id,
                        normalized_submitter,
                        normalized_version,
                        payload_json,
                        now,
                        now,
                    ),
                )
            else:
                self._require_record_version(existing, normalized_version)
                current_status = str(existing["review_status"])
                if current_status not in REVIEW_STATUSES:
                    raise _conflict_error(
                        "审核状态无效",
                        "review_state_conflict",
                        content_type=normalized_type,
                        content_id=normalized_id,
                    )

                if (
                    current_status != "rejected"
                    and existing["payload_json"] == payload_json
                ):
                    _finish(db, owns_transaction)
                    return _serialize_record(existing)

                next_version = normalized_version + 1
                db.execute(
                    """
                    UPDATE content_review_records
                    SET submitter_id = ?,
                        review_status = 'pending',
                        version = ?,
                        rejection_opinion = NULL,
                        published_at = NULL,
                        payload_json = ?,
                        updated_at = ?
                    WHERE content_type = ? AND content_id = ?
                    """,
                    (
                        normalized_submitter,
                        next_version,
                        payload_json,
                        now,
                        normalized_type,
                        normalized_id,
                    ),
                )

            row = self._load_record(db, normalized_type, normalized_id)
            record = _serialize_record(row)
            if normalized_type == "job_position":
                self._sync_job_projection(db, record)
            _finish(db, owns_transaction)
            return record
        except Exception:
            _rollback(db, owns_transaction)
            raise

    def get_review_status(
        self,
        *,
        content_type: str,
        content_id: str,
    ) -> dict | None:
        normalized_type = _content_type(content_type)
        normalized_id = _content_id(content_id)
        row = self._load_record(
            get_db(),
            normalized_type,
            normalized_id,
        )
        return _serialize_record(row) if row is not None else None

    def approve(
        self,
        *,
        content_type: str,
        content_id: str,
        submitter_id: int,
        reviewer_id: int,
        reviewer_role: str,
        expected_version: int,
    ) -> dict:
        return self._transition(
            action="approve",
            content_type=content_type,
            content_id=content_id,
            submitter_id=submitter_id,
            reviewer_id=reviewer_id,
            reviewer_role=reviewer_role,
            expected_version=expected_version,
            opinion=None,
        )

    def reject(
        self,
        *,
        content_type: str,
        content_id: str,
        submitter_id: int,
        reviewer_id: int,
        reviewer_role: str,
        expected_version: int,
        opinion: str,
    ) -> dict:
        if not isinstance(opinion, str):
            raise _validation_error(
                "驳回意见必须是文本",
                "review_opinion_invalid",
                field="opinion",
            )
        normalized_opinion = opinion.strip()
        if not 1 <= len(normalized_opinion) <= 500:
            raise _validation_error(
                "驳回意见长度必须为 1 至 500 个字符",
                "review_opinion_invalid",
                field="opinion",
                min_length=1,
                max_length=500,
            )
        return self._transition(
            action="reject",
            content_type=content_type,
            content_id=content_id,
            submitter_id=submitter_id,
            reviewer_id=reviewer_id,
            reviewer_role=reviewer_role,
            expected_version=expected_version,
            opinion=normalized_opinion,
        )

    def edit(
        self,
        *,
        content_type: str,
        content_id: str,
        submitter_id: int,
        expected_version: int,
        payload: dict,
    ) -> dict:
        normalized_type = _content_type(content_type)
        normalized_id = _content_id(content_id)
        normalized_submitter = _positive_int(
            submitter_id,
            field="submitter_id",
        )
        normalized_version = _positive_int(
            expected_version,
            field="expected_version",
        )
        payload_json = _payload_json(_payload(payload))

        db = get_db()
        owns_transaction = _begin(db)
        try:
            owner = self._load_owner(
                db,
                normalized_type,
                normalized_id,
                normalized_submitter,
            )
            self._require_owner_version(owner, normalized_version)
            existing = self._load_record(
                db,
                normalized_type,
                normalized_id,
            )
            if existing is None:
                raise ProviderNotFoundError(
                    "审核记录不存在",
                    code="review_not_found",
                    details={
                        "content_type": normalized_type,
                        "content_id": normalized_id,
                    },
                )
            self._require_record_version(existing, normalized_version)

            if existing["payload_json"] == payload_json:
                _finish(db, owns_transaction)
                return _serialize_record(existing)

            now = platform_now_iso()
            db.execute(
                """
                UPDATE content_review_records
                SET submitter_id = ?,
                    review_status = 'pending',
                    version = ?,
                    rejection_opinion = NULL,
                    published_at = NULL,
                    payload_json = ?,
                    updated_at = ?
                WHERE content_type = ? AND content_id = ?
                """,
                (
                    normalized_submitter,
                    normalized_version + 1,
                    payload_json,
                    now,
                    normalized_type,
                    normalized_id,
                ),
            )
            row = self._load_record(db, normalized_type, normalized_id)
            record = _serialize_record(row)
            if normalized_type == "job_position":
                self._sync_job_projection(db, record)
            _finish(db, owns_transaction)
            return record
        except Exception:
            _rollback(db, owns_transaction)
            raise

    def list_review_items(
        self,
        content_type: str | None = None,
    ) -> list[dict]:
        if content_type is not None:
            content_type = _content_type(content_type)

        rows = get_db().execute(
            """
            SELECT *
            FROM content_review_records
            WHERE content_type IN ('course_video', 'job_position')
            ORDER BY updated_at ASC, content_type ASC, content_id ASC
            """
        ).fetchall()
        items = []
        for row in rows:
            record = _serialize_record(row)
            if content_type is not None and record["content_type"] != content_type:
                continue
            owner = self._load_owner_for_list(
                get_db(),
                record["content_type"],
                record["content_id"],
            )
            if owner is None:
                continue
            items.append({**record, **owner})
        return items

    def _transition(
        self,
        *,
        action: str,
        content_type: str,
        content_id: str,
        submitter_id: int,
        reviewer_id: int,
        reviewer_role: str,
        expected_version: int,
        opinion: str | None,
    ) -> dict:
        normalized_type = _content_type(content_type)
        normalized_id = _content_id(content_id)
        normalized_submitter = _positive_int(
            submitter_id,
            field="submitter_id",
        )
        normalized_reviewer = _positive_int(
            reviewer_id,
            field="reviewer_id",
        )
        if (
            not isinstance(reviewer_role, str)
            or reviewer_role not in REVIEWER_ROLES
        ):
            raise ProviderAccessDeniedError(
                "无审核权限",
                code="review_access_denied",
                details={"reviewer_role": reviewer_role},
            )
        normalized_version = _positive_int(
            expected_version,
            field="expected_version",
        )

        db = get_db()
        owns_transaction = _begin(db)
        try:
            owner = self._load_owner(
                db,
                normalized_type,
                normalized_id,
                normalized_submitter,
            )
            self._require_owner_version(owner, normalized_version)
            existing = self._load_record(
                db,
                normalized_type,
                normalized_id,
            )
            if existing is None:
                raise ProviderNotFoundError(
                    "审核记录不存在",
                    code="review_not_found",
                    details={
                        "content_type": normalized_type,
                        "content_id": normalized_id,
                    },
                )
            self._require_record_version(existing, normalized_version)
            if existing["review_status"] != "pending":
                raise _conflict_error(
                    "当前审核状态不允许该操作",
                    "review_state_conflict",
                    content_type=normalized_type,
                    content_id=normalized_id,
                    review_status=existing["review_status"],
                    action=action,
                )

            now = platform_now_iso()
            review_status = "approved" if action == "approve" else "rejected"
            published_at = now if action == "approve" else None
            next_version = normalized_version + 1
            db.execute(
                """
                UPDATE content_review_records
                SET submitter_id = ?,
                    review_status = ?,
                    version = ?,
                    rejection_opinion = ?,
                    published_at = ?,
                    updated_at = ?
                WHERE content_type = ? AND content_id = ?
                """,
                (
                    normalized_submitter,
                    review_status,
                    next_version,
                    opinion,
                    published_at,
                    now,
                    normalized_type,
                    normalized_id,
                ),
            )
            row = self._load_record(db, normalized_type, normalized_id)
            record = _serialize_record(row)
            if normalized_type == "course_video":
                self._sync_course_projection(db, record)
            else:
                self._sync_job_projection(db, record)

            event_id = (
                f"review:{normalized_type}:{normalized_id}:"
                f"v{normalized_version}:{action}"
            )
            event_type = (
                "review_approved" if action == "approve" else "review_rejected"
            )
            outbox_payload = {
                "event_id": event_id,
                "submitter_id": normalized_submitter,
                "content_type": normalized_type,
                "content_id": normalized_id,
                "approved": action == "approve",
                "opinion": opinion,
            }
            db.execute(
                """
                INSERT INTO admin_notification_outbox (
                    event_type, event_id, payload_json, created_at
                )
                VALUES (?, ?, ?, ?)
                ON CONFLICT (event_type, event_id) DO NOTHING
                """,
                (
                    event_type,
                    event_id,
                    _payload_json(outbox_payload),
                    now,
                ),
            )
            _finish(db, owns_transaction)
        except Exception:
            _rollback(db, owns_transaction)
            raise

        if owns_transaction:
            self._deliver_notification(
                event_id=event_id,
                submitter_id=normalized_submitter,
                content_type=normalized_type,
                content_id=normalized_id,
                approved=action == "approve",
                opinion=opinion,
            )
        return record

    @staticmethod
    def _load_record(
        db: sqlite3.Connection,
        content_type: str,
        content_id: str,
    ) -> sqlite3.Row | None:
        return db.execute(
            """
            SELECT *
            FROM content_review_records
            WHERE content_type = ? AND content_id = ?
            """,
            (content_type, content_id),
        ).fetchone()

    @staticmethod
    def _require_record_version(
        row: sqlite3.Row,
        expected_version: int,
    ) -> None:
        if int(row["version"]) != expected_version:
            raise _conflict_error(
                "审核版本已变化",
                "review_version_conflict",
                content_type=row["content_type"],
                content_id=row["content_id"],
                expected_version=expected_version,
                actual_version=int(row["version"]),
            )

    @classmethod
    def _load_owner(
        cls,
        db: sqlite3.Connection,
        content_type: str,
        content_id: str,
        submitter_id: int,
    ) -> sqlite3.Row:
        if content_type == "course_video":
            try:
                course_id = int(content_id)
            except ValueError:
                raise ProviderNotFoundError(
                    "课程不存在",
                    code="review_content_not_found",
                    details={"content_id": content_id},
                ) from None
            row = db.execute(
                f"""
                SELECT id, teacher_id, status, version
                FROM courses
                WHERE id = ?
                {cls._course_deleted_clause(db)}
                """,
                (course_id,),
            ).fetchone()
            owner_id = None if row is None else int(row["teacher_id"] or 0)
        else:
            row = db.execute(
                """
                SELECT job_id, enterprise_id, review_status, version,
                       deleted_at
                FROM job_positions
                WHERE job_id = ?
                """,
                (content_id,),
            ).fetchone()
            if row is not None and row["deleted_at"] is not None:
                row = None
            owner_id = None if row is None else int(row["enterprise_id"])

        if row is None:
            raise ProviderNotFoundError(
                "内容不存在",
                code="review_content_not_found",
                details={
                    "content_type": content_type,
                    "content_id": content_id,
                },
            )
        if owner_id != submitter_id:
            raise ProviderAccessDeniedError(
                "无权提交该内容审核",
                code="review_submitter_denied",
                details={
                    "content_type": content_type,
                    "content_id": content_id,
                },
            )
        return row

    @classmethod
    def _load_owner_for_list(
        cls,
        db: sqlite3.Connection,
        content_type: str,
        content_id: str,
    ) -> dict | None:
        if content_type == "course_video":
            try:
                course_id = int(content_id)
            except ValueError:
                return None
            row = db.execute(
                f"""
                SELECT c.id, c.title, c.teacher_id AS owner_id,
                       COALESCE(u.name, c.teacher_name, '') AS owner_name
                FROM courses AS c
                LEFT JOIN users AS u ON u.id = c.teacher_id
                WHERE c.id = ?
                {cls._course_deleted_clause(db, alias="c")}
                """,
                (course_id,),
            ).fetchone()
            if row is None:
                return None
            return {
                "title": str(row["title"]),
                "owner_id": (
                    None if row["owner_id"] is None else int(row["owner_id"])
                ),
                "owner_name": str(row["owner_name"] or ""),
            }

        row = db.execute(
            """
            SELECT jp.title, jp.enterprise_id AS owner_id,
                   COALESCE(u.name, '') AS owner_name
            FROM job_positions AS jp
            LEFT JOIN users AS u ON u.id = jp.enterprise_id
            WHERE jp.job_id = ?
              AND jp.deleted_at IS NULL
            """,
            (content_id,),
        ).fetchone()
        if row is None:
            return None
        return {
            "title": str(row["title"]),
            "owner_id": int(row["owner_id"]),
            "owner_name": str(row["owner_name"] or ""),
        }

    @staticmethod
    def _require_owner_version(
        owner: sqlite3.Row,
        expected_version: int,
    ) -> None:
        if int(owner["version"]) != expected_version:
            raise _conflict_error(
                "内容版本已变化",
                "review_version_conflict",
                expected_version=expected_version,
                actual_version=int(owner["version"]),
            )

    @staticmethod
    def _sync_course_projection(
        db: sqlite3.Connection,
        record: dict,
    ) -> None:
        db.execute(
            """
            UPDATE courses
            SET status = ?,
                version = ?,
                rejection_opinion = ?,
                published_at = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                (
                    "published"
                    if record["review_status"] == "approved"
                    else "pending"
                ),
                int(record["version"]),
                record["rejection_opinion"],
                record["published_at"],
                record["updated_at"],
                int(record["content_id"]),
            ),
        )

    @staticmethod
    def _course_deleted_clause(
        db: sqlite3.Connection,
        *,
        alias: str = "",
    ) -> str:
        columns = {
            str(row["name"])
            for row in db.execute("PRAGMA table_info(courses)").fetchall()
        }
        if "deleted_at" not in columns:
            return ""
        prefix = f"{alias}." if alias else ""
        return f"AND {prefix}deleted_at IS NULL"

    @staticmethod
    def _sync_job_projection(
        db: sqlite3.Connection,
        record: dict,
    ) -> None:
        db.execute(
            """
            UPDATE job_positions
            SET review_status = ?,
                version = ?,
                rejection_opinion = ?,
                published_at = ?,
                updated_at = ?
            WHERE job_id = ?
              AND deleted_at IS NULL
            """,
            (
                record["review_status"],
                int(record["version"]),
                record["rejection_opinion"],
                record["published_at"],
                record["updated_at"],
                record["content_id"],
            ),
        )

    @staticmethod
    def _deliver_notification(
        *,
        event_id: str,
        submitter_id: int,
        content_type: str,
        content_id: str,
        approved: bool,
        opinion: str | None,
    ) -> None:
        db = get_db()
        event_type = "review_approved" if approved else "review_rejected"
        try:
            emit_review_result(
                event_id=event_id,
                submitter_id=submitter_id,
                content_type=content_type,
                content_id=content_id,
                approved=approved,
                opinion=opinion,
            )
        except Exception as error:
            try:
                with db:
                    db.execute(
                        """
                        UPDATE admin_notification_outbox
                        SET status = 'failed',
                            attempts = attempts + 1,
                            last_error = ?
                        WHERE event_type = ? AND event_id = ?
                        """,
                        (str(error), event_type, event_id),
                    )
            except sqlite3.Error:
                pass
            return

        try:
            with db:
                db.execute(
                    """
                    UPDATE admin_notification_outbox
                    SET status = 'sent',
                        attempts = attempts + 1,
                        sent_at = ?
                    WHERE event_type = ? AND event_id = ?
                    """,
                    (platform_now_iso(), event_type, event_id),
                )
        except sqlite3.Error:
            pass
