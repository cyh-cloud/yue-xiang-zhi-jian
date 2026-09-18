from __future__ import annotations

from datetime import datetime, timezone

from app.agri_skills.errors import AgriValidationError
from app.db import get_db


HEARTBEAT_INTERVAL_SECONDS = 30
IDLE_CUTOFF_SECONDS = 180
MAX_SEGMENT_SECONDS = 7200
VALID_SOURCE_TYPES = {"craft", "ar", "course"}


def _now_epoch() -> float:
    return datetime.now(timezone.utc).timestamp()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _require_positive_int(value: object, message: str) -> int:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or value <= 0
    ):
        raise AgriValidationError(message)
    return value


def _require_nonnegative_int(value: object, message: str) -> int:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or value < 0
    ):
        raise AgriValidationError(message)
    return value


def _require_text(value: object, message: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise AgriValidationError(message)
    return normalized


def _validate_source(source_type: object, source_key: object) -> tuple[str, str]:
    normalized_type = str(source_type or "").strip()
    if normalized_type not in VALID_SOURCE_TYPES:
        raise AgriValidationError("学习来源类型不正确")
    return (
        normalized_type,
        _require_text(source_key, "学习来源标识不能为空"),
    )


def _serialize(row) -> dict:
    return {
        "segment_id": int(row["id"]),
        "segment_no": int(row["segment_no"]),
        "heartbeat_seq": int(row["last_heartbeat_seq"]),
        "active_seconds": int(row["accumulated_seconds"]),
        "settled_seconds": int(row["settled_seconds"]),
        "closed": row["closed_at"] is not None,
    }


def _create_segment(
    db,
    user_id: int,
    source_type: str,
    source_key: str,
    heartbeat_seq: int,
    now_epoch: float,
) -> dict:
    next_segment = db.execute(
        """
        SELECT COALESCE(MAX(segment_no), 0) + 1 AS segment_no
        FROM handcraft_active_learning_sessions
        WHERE user_id = ? AND source_type = ? AND source_key = ?
        """,
        (user_id, source_type, source_key),
    ).fetchone()["segment_no"]
    now_iso = _now_iso()
    cursor = db.execute(
        """
        INSERT INTO handcraft_active_learning_sessions (
            user_id, source_type, source_key, segment_no,
            started_at, last_heartbeat_at, last_heartbeat_epoch,
            last_heartbeat_seq, accumulated_seconds, settled_seconds,
            closed_at, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 0, NULL, ?, ?)
        """,
        (
            user_id,
            source_type,
            source_key,
            int(next_segment),
            now_iso,
            now_iso,
            now_epoch,
            heartbeat_seq,
            now_iso,
            now_iso,
        ),
    )
    row = db.execute(
        """
        SELECT *
        FROM handcraft_active_learning_sessions
        WHERE id = ?
        """,
        (int(cursor.lastrowid),),
    ).fetchone()
    return _serialize(row)


def heartbeat(
    user_id: int,
    source_type: str,
    source_key: str,
    *,
    segment_id: int | None = None,
    heartbeat_seq: int = 0,
    now_epoch: float | None = None,
) -> dict:
    user_id = _require_positive_int(user_id, "学员标识必须是正整数")
    source_type, source_key = _validate_source(source_type, source_key)
    heartbeat_seq = _require_nonnegative_int(
        heartbeat_seq,
        "心跳序号必须是非负整数",
    )
    if segment_id is not None:
        segment_id = _require_positive_int(
            segment_id,
            "学习段标识必须是正整数",
        )
    current_epoch = _now_epoch() if now_epoch is None else float(now_epoch)
    db = get_db()

    with db:
        db.execute("BEGIN IMMEDIATE")
        if segment_id is None:
            return {
                **_create_segment(
                    db,
                    user_id,
                    source_type,
                    source_key,
                    heartbeat_seq,
                    current_epoch,
                ),
                "restarted": False,
                "duplicate": False,
            }

        row = db.execute(
            """
            SELECT *
            FROM handcraft_active_learning_sessions
            WHERE id = ?
              AND user_id = ?
              AND source_type = ?
              AND source_key = ?
            """,
            (segment_id, user_id, source_type, source_key),
        ).fetchone()
        if row is None:
            raise AgriValidationError("学习段不存在")

        if row["closed_at"] is not None:
            return {
                **_create_segment(
                    db,
                    user_id,
                    source_type,
                    source_key,
                    heartbeat_seq,
                    current_epoch,
                ),
                "restarted": True,
                "duplicate": False,
            }

        if heartbeat_seq <= int(row["last_heartbeat_seq"]):
            return {
                **_serialize(row),
                "restarted": False,
                "duplicate": True,
            }

        gap_seconds = max(
            0.0,
            current_epoch - float(row["last_heartbeat_epoch"]),
        )
        if gap_seconds > IDLE_CUTOFF_SECONDS:
            db.execute(
                """
                UPDATE handcraft_active_learning_sessions
                SET closed_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (_now_iso(), _now_iso(), segment_id),
            )
            return {
                **_create_segment(
                    db,
                    user_id,
                    source_type,
                    source_key,
                    heartbeat_seq,
                    current_epoch,
                ),
                "restarted": True,
                "duplicate": False,
            }

        credited_seconds = min(
            HEARTBEAT_INTERVAL_SECONDS,
            int(gap_seconds),
        )
        accumulated_seconds = min(
            MAX_SEGMENT_SECONDS,
            int(row["accumulated_seconds"]) + credited_seconds,
        )
        db.execute(
            """
            UPDATE handcraft_active_learning_sessions
            SET last_heartbeat_at = ?,
                last_heartbeat_epoch = ?,
                last_heartbeat_seq = ?,
                accumulated_seconds = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                _now_iso(),
                current_epoch,
                heartbeat_seq,
                accumulated_seconds,
                _now_iso(),
                segment_id,
            ),
        )
        updated = db.execute(
            """
            SELECT *
            FROM handcraft_active_learning_sessions
            WHERE id = ?
            """,
            (segment_id,),
        ).fetchone()
        return {
            **_serialize(updated),
            "restarted": False,
            "duplicate": False,
        }


def claim_active_seconds(
    user_id: int,
    source_type: str,
    source_key: str,
    segment_id: object,
    *,
    close_segment: bool,
) -> int:
    if segment_id is None or str(segment_id).strip() == "":
        return 0
    if isinstance(segment_id, bool):
        raise AgriValidationError("学习段标识必须是正整数")
    try:
        normalized_segment_id = int(segment_id)
    except (TypeError, ValueError):
        raise AgriValidationError("学习段标识必须是正整数") from None
    normalized_segment_id = _require_positive_int(
        normalized_segment_id,
        "学习段标识必须是正整数",
    )
    user_id = _require_positive_int(user_id, "学员标识必须是正整数")
    source_type, source_key = _validate_source(source_type, source_key)
    db = get_db()

    with db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute(
            """
            SELECT *
            FROM handcraft_active_learning_sessions
            WHERE id = ?
              AND user_id = ?
              AND source_type = ?
              AND source_key = ?
            """,
            (
                normalized_segment_id,
                user_id,
                source_type,
                source_key,
            ),
        ).fetchone()
        if row is None:
            return 0
        accumulated_seconds = int(row["accumulated_seconds"])
        if close_segment:
            if row["closed_at"] is None:
                now = _now_iso()
                db.execute(
                    """
                    UPDATE handcraft_active_learning_sessions
                    SET closed_at = ?,
                        settled_seconds = accumulated_seconds,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (now, now, normalized_segment_id),
                )
            return accumulated_seconds

        claimed_seconds = max(
            0,
            accumulated_seconds - int(row["settled_seconds"]),
        )
        if claimed_seconds:
            db.execute(
                """
                UPDATE handcraft_active_learning_sessions
                SET settled_seconds = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    accumulated_seconds,
                    _now_iso(),
                    normalized_segment_id,
                ),
            )
        return claimed_seconds


__all__ = [
    "HEARTBEAT_INTERVAL_SECONDS",
    "IDLE_CUTOFF_SECONDS",
    "MAX_SEGMENT_SECONDS",
    "claim_active_seconds",
    "heartbeat",
]
