from __future__ import annotations

import json
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.agri_skills.errors import AgriValidationError
from app.handcraft_inheritance.providers import get_points_policy_provider


PLATFORM_TIMEZONE = ZoneInfo("Asia/Shanghai")
MAX_SEGMENT_SECONDS = 7200
DURATION_EVENT_SEPARATOR = "|"


class PointsPolicyUnavailable(AgriValidationError):
    pass


def _get_db():
    from app.db import get_db

    return get_db()


def _platform_now() -> datetime:
    return datetime.now(PLATFORM_TIMEZONE)


def _parse_platform_time(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        raise AgriValidationError("时间格式不正确")
    if parsed.tzinfo is None:
        raise AgriValidationError("时间必须包含时区")
    return parsed.astimezone(PLATFORM_TIMEZONE)


def _normalize_event_time(value: str | datetime | None) -> tuple[datetime, str]:
    parsed = _parse_platform_time(value or _platform_now())
    if parsed > _platform_now() + timedelta(minutes=5):
        raise AgriValidationError("学习事件时间不能晚于当前时间")
    return parsed, parsed.isoformat(timespec="seconds")


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


def _normalize_policy(
    policy: object,
    *,
    source_available: bool,
) -> dict:
    if not isinstance(policy, dict):
        raise AgriValidationError("积分规则格式不正确")
    seconds_per_point = _require_positive_int(
        policy.get("seconds_per_point"),
        "积分折算比率必须是正整数",
    )
    daily_limit = _require_positive_int(
        policy.get("daily_limit"),
        "每日上限必须是正整数",
    )
    expiry_mode = policy.get("expiry_mode")
    if expiry_mode not in {"permanent", "natural_year"}:
        raise AgriValidationError("积分有效期规则不正确")
    raw_weights = policy.get("training_weights")
    if not isinstance(raw_weights, dict):
        raise AgriValidationError("训练积分权重格式不正确")
    training_weights = {}
    for event_type, weight in raw_weights.items():
        normalized_type = _require_text(event_type, "训练类型不能为空")
        training_weights[normalized_type] = _require_positive_int(
            weight,
            "训练积分权重必须是正整数",
        )
    if "default" not in training_weights:
        raise AgriValidationError("积分规则缺少默认训练权重")
    return {
        "version": _require_text(policy.get("version"), "规则版本不能为空"),
        "seconds_per_point": seconds_per_point,
        "training_weights": training_weights,
        "daily_limit": daily_limit,
        "expiry_mode": expiry_mode,
        "is_demo": bool(policy.get("is_demo", False)),
        "source_available": source_available,
    }


def get_effective_policy() -> dict:
    provider = get_points_policy_provider()
    try:
        policy = _normalize_policy(
            provider.get_policy(),
            source_available=True,
        )
    except Exception as error:
        with _get_db() as db:
            row = db.execute(
                """
                SELECT policy_json
                FROM points_policy_snapshots
                ORDER BY observed_at DESC, id DESC
                LIMIT 1
                """
            ).fetchone()
        if row is None:
            raise PointsPolicyUnavailable(
                "积分规则暂不可用，请稍后重试"
            ) from error
        try:
            return _normalize_policy(
                json.loads(row["policy_json"]),
                source_available=False,
            )
        except Exception as snapshot_error:
            raise PointsPolicyUnavailable(
                "积分规则暂不可用，请稍后重试"
            ) from snapshot_error

    with _get_db() as db:
        db.execute(
            """
            INSERT INTO points_policy_snapshots (
                version, policy_json, observed_at
            )
            VALUES (?, ?, ?)
            """,
            (
                policy["version"],
                json.dumps(policy, ensure_ascii=False),
                _platform_now().isoformat(timespec="seconds"),
            ),
        )
    return policy


def _serialize_transaction(row) -> dict:
    return {
        "id": int(row["id"]),
        "user_id": int(row["user_id"]),
        "transaction_type": str(row["transaction_type"]),
        "source_module": str(row["source_module"]),
        "source_event_id": str(row["source_event_id"]),
        "delta": int(row["delta"]),
        "balance_after": int(row["balance_after"]),
        "metadata": json.loads(row["metadata_json"]),
        "created_at": str(row["created_at"]),
    }


def _existing_transaction(
    db,
    user_id: int,
    transaction_type: str,
    source_module: str,
    source_event_id: str,
) -> dict | None:
    row = db.execute(
        """
        SELECT *
        FROM points_transactions
        WHERE user_id = ?
          AND transaction_type = ?
          AND source_module = ?
          AND source_event_id = ?
        """,
        (
            user_id,
            transaction_type,
            source_module,
            source_event_id,
        ),
    ).fetchone()
    return _serialize_transaction(row) if row else None


def _award_transaction_for_event(db, event) -> dict | None:
    row = db.execute(
        """
        SELECT *
        FROM points_transactions
        WHERE user_id = ?
          AND transaction_type = 'award'
          AND source_module = ?
          AND source_event_id = ?
        """,
        (
            int(event["user_id"]),
            str(event["source_module"]),
            str(event["source_event_id"]),
        ),
    ).fetchone()
    return _serialize_transaction(row) if row else None


def _event_result(
    db,
    event,
    *,
    status: str,
    transaction: dict | None = None,
    error: str | None = None,
) -> dict:
    account = db.execute(
        """
        SELECT balance
        FROM points_accounts
        WHERE user_id = ?
        """,
        (int(event["user_id"]),),
    ).fetchone()
    return {
        "event_id": int(event["id"]),
        "status": status,
        "awarded": (
            int(transaction["delta"])
            if transaction is not None
            else 0
        ),
        "balance_after": int(account["balance"]) if account else 0,
        "transaction": transaction,
        "error": error,
    }


def _existing_refund_for_spend(
    db,
    user_id: int,
    spend_transaction_id: int,
) -> dict | None:
    rows = db.execute(
        """
        SELECT *
        FROM points_transactions
        WHERE user_id = ? AND transaction_type = 'refund'
        ORDER BY id
        """,
        (user_id,),
    ).fetchall()
    for row in rows:
        metadata = json.loads(row["metadata_json"])
        if int(metadata.get("spend_transaction_id", 0)) == spend_transaction_id:
            return _serialize_transaction(row)
    return None


def _ensure_account(db, user_id: int, updated_at: str) -> None:
    db.execute(
        """
        INSERT OR IGNORE INTO points_accounts (
            user_id, balance, updated_at
        )
        VALUES (?, 0, ?)
        """,
        (user_id, updated_at),
    )


def get_points_account(user_id: int) -> dict:
    user_id = _require_positive_int(user_id, "学员标识必须是正整数")
    row = _get_db().execute(
        """
        SELECT user_id, balance, updated_at
        FROM points_accounts
        WHERE user_id = ?
        """,
        (user_id,),
    ).fetchone()
    if row is None:
        return {"user_id": user_id, "balance": 0, "updated_at": None}
    return {
        "user_id": int(row["user_id"]),
        "balance": int(row["balance"]),
        "updated_at": str(row["updated_at"]),
    }


def get_points_ledger(user_id: int) -> list[dict]:
    user_id = _require_positive_int(user_id, "学员标识必须是正整数")
    rows = _get_db().execute(
        """
        SELECT *
        FROM points_transactions
        WHERE user_id = ?
        ORDER BY created_at DESC, id DESC
        """,
        (user_id,),
    ).fetchall()
    return [_serialize_transaction(row) for row in rows]


def enqueue_learning_event(
    user_id: int,
    source_module: str,
    event_type: str,
    source_event_id: str,
    occurred_at: str,
    duration_seconds: int | None = None,
) -> dict:
    user_id = _require_positive_int(user_id, "学员标识必须是正整数")
    source_module = _require_text(source_module, "来源模块不能为空")
    event_type = _require_text(event_type, "事件类型不能为空")
    source_event_id = _require_text(source_event_id, "来源事件标识不能为空")
    _, normalized_time = _normalize_event_time(occurred_at)
    if duration_seconds is not None:
        duration_seconds = _require_nonnegative_int(
            duration_seconds,
            "学习时长必须是非负整数",
        )
        if duration_seconds > MAX_SEGMENT_SECONDS:
            raise AgriValidationError("单次学习段不能超过 120 分钟")

    with _get_db() as db:
        cursor = db.execute(
            """
            INSERT OR IGNORE INTO points_event_inbox (
                user_id, source_module, event_type, source_event_id,
                occurred_at, duration_seconds, status, error, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, 'pending', NULL, ?)
            """,
            (
                user_id,
                source_module,
                event_type,
                source_event_id,
                normalized_time,
                duration_seconds,
                normalized_time,
            ),
        )
        event_id = (
            int(cursor.lastrowid)
            if cursor.rowcount == 1
            else None
        )
        row = db.execute(
            """
            SELECT *
            FROM points_event_inbox
            WHERE user_id = ?
              AND source_module = ?
              AND event_type = ?
              AND source_event_id = ?
            """,
            (
                user_id,
                source_module,
                event_type,
                source_event_id,
            ),
        ).fetchone()
        if event_id is None:
            event_id = int(row["id"])
        transaction = _award_transaction_for_event(db, row)
        return _event_result(
            db,
            row,
            status=str(row["status"]),
            transaction=transaction,
            error=row["error"],
        )


def _daily_awarded_points(
    db,
    user_id: int,
    occurred_at: str,
) -> int:
    day = _parse_platform_time(occurred_at).date()
    start = datetime.combine(day, time.min, PLATFORM_TIMEZONE)
    end = start + timedelta(days=1)
    row = db.execute(
        """
        SELECT COALESCE(SUM(delta), 0) AS total
        FROM points_transactions
        WHERE user_id = ?
          AND transaction_type = 'award'
          AND created_at >= ?
          AND created_at < ?
        """,
        (
            user_id,
            start.isoformat(timespec="seconds"),
            end.isoformat(timespec="seconds"),
        ),
    ).fetchone()
    return int(row["total"])


def _expires_at(occurred_at: str, policy: dict) -> str | None:
    if policy["expiry_mode"] == "permanent":
        return None
    occurred = _parse_platform_time(occurred_at)
    return datetime(
        occurred.year,
        12,
        31,
        23,
        59,
        59,
        tzinfo=PLATFORM_TIMEZONE,
    ).isoformat(timespec="seconds")


def _credit_points(
    db,
    *,
    user_id: int,
    amount: int,
    source_module: str,
    source_event_id: str,
    occurred_at: str,
    policy: dict,
    metadata: dict | None = None,
) -> dict:
    existing = _existing_transaction(
        db,
        user_id,
        "award",
        source_module,
        source_event_id,
    )
    if existing is not None:
        return existing

    _ensure_account(db, user_id, occurred_at)
    account = db.execute(
        """
        SELECT balance
        FROM points_accounts
        WHERE user_id = ?
        """,
        (user_id,),
    ).fetchone()
    balance_after = int(account["balance"]) + amount
    cursor = db.execute(
        """
        INSERT INTO points_transactions (
            user_id, transaction_type, source_module, source_event_id,
            delta, balance_after, metadata_json, created_at
        )
        VALUES (?, 'award', ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            source_module,
            source_event_id,
            amount,
            balance_after,
            json.dumps(metadata or {}, ensure_ascii=False),
            occurred_at,
        ),
    )
    transaction_id = int(cursor.lastrowid)
    db.execute(
        """
        INSERT INTO points_lots (
            user_id, award_transaction_id, original_points,
            remaining_points, expires_at, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            transaction_id,
            amount,
            amount,
            _expires_at(occurred_at, policy),
            occurred_at,
        ),
    )
    db.execute(
        """
        UPDATE points_accounts
        SET balance = ?, updated_at = ?
        WHERE user_id = ?
        """,
        (balance_after, occurred_at, user_id),
    )
    return {
        "id": transaction_id,
        "transaction_type": "award",
        "delta": amount,
        "balance_after": balance_after,
        "source_module": source_module,
        "source_event_id": source_event_id,
        "created_at": occurred_at,
    }


def _duration_source_parts(source_event_id: str) -> tuple[str, str]:
    source_key, separator, event_id = source_event_id.partition(
        DURATION_EVENT_SEPARATOR
    )
    if not separator or not source_key or not event_id:
        return source_event_id, source_event_id
    return source_key, event_id


def _award_duration_event(db, event, policy: dict) -> dict | None:
    source_key, _ = _duration_source_parts(str(event["source_event_id"]))
    duration_seconds = int(event["duration_seconds"])
    if duration_seconds > MAX_SEGMENT_SECONDS:
        raise AgriValidationError("单次学习段不能超过 120 分钟")
    row = db.execute(
        """
        SELECT accumulated_seconds, awarded_units
               , consumed_units
        FROM points_learning_accruals
        WHERE user_id = ? AND source_module = ? AND source_key = ?
        """,
        (int(event["user_id"]), str(event["source_module"]), source_key),
    ).fetchone()
    previous_seconds = int(row["accumulated_seconds"]) if row else 0
    previous_units = int(row["awarded_units"]) if row else 0
    previous_consumed = int(row["consumed_units"]) if row else 0
    accumulated_seconds = previous_seconds + duration_seconds
    total_units = accumulated_seconds // int(policy["seconds_per_point"])
    pending_units = max(0, total_units - previous_consumed)
    daily_awarded = _daily_awarded_points(
        db,
        int(event["user_id"]),
        str(event["occurred_at"]),
    )
    award_now = min(
        pending_units,
        max(0, int(policy["daily_limit"]) - daily_awarded),
    )
    next_awarded_units = previous_units + award_now
    next_consumed_units = previous_consumed + pending_units
    db.execute(
        """
        INSERT INTO points_learning_accruals (
            user_id, source_module, source_key,
            accumulated_seconds, awarded_units, consumed_units, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (user_id, source_module, source_key) DO UPDATE SET
            accumulated_seconds = excluded.accumulated_seconds,
            awarded_units = excluded.awarded_units,
            consumed_units = excluded.consumed_units,
            updated_at = excluded.updated_at
        """,
        (
            int(event["user_id"]),
            str(event["source_module"]),
            source_key,
            accumulated_seconds,
            next_awarded_units,
            next_consumed_units,
            str(event["occurred_at"]),
        ),
    )
    if award_now <= 0:
        return None
    return _credit_points(
        db,
        user_id=int(event["user_id"]),
        amount=award_now,
        source_module=str(event["source_module"]),
        source_event_id=str(event["source_event_id"]),
        occurred_at=str(event["occurred_at"]),
        policy=policy,
        metadata={"learning_source_key": source_key},
    )


def _award_training_event(db, event, policy: dict) -> dict | None:
    event_type = str(event["event_type"])
    weight = int(
        policy["training_weights"].get(
            event_type,
            policy["training_weights"]["default"],
        )
    )
    daily_awarded = _daily_awarded_points(
        db,
        int(event["user_id"]),
        str(event["occurred_at"]),
    )
    award_now = min(
        weight,
        max(0, int(policy["daily_limit"]) - daily_awarded),
    )
    if award_now <= 0:
        return None
    return _credit_points(
        db,
        user_id=int(event["user_id"]),
        amount=award_now,
        source_module=str(event["source_module"]),
        source_event_id=str(event["source_event_id"]),
        occurred_at=str(event["occurred_at"]),
        policy=policy,
        metadata={"event_type": event_type},
    )


def _process_event(db, event, policy: dict) -> dict | None:
    if event["duration_seconds"] is None:
        return _award_training_event(db, event, policy)
    return _award_duration_event(db, event, policy)


def process_pending_events(user_id: int, limit: int = 100) -> list[dict]:
    user_id = _require_positive_int(user_id, "学员标识必须是正整数")
    limit = _require_positive_int(limit, "处理数量必须是正整数")
    db = _get_db()
    try:
        policy = get_effective_policy()
    except PointsPolicyUnavailable:
        pending = db.execute(
            """
            SELECT *
            FROM points_event_inbox
            WHERE user_id = ? AND status = 'pending'
            ORDER BY occurred_at, id
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
        return [
            _event_result(db, event, status="pending")
            for event in pending
        ]

    pending = db.execute(
        """
        SELECT *
        FROM points_event_inbox
        WHERE user_id = ? AND status = 'pending'
        ORDER BY occurred_at, id
        LIMIT ?
        """,
        (user_id, limit),
    ).fetchall()
    processed = []
    for event in pending:
        try:
            with db:
                db.execute("BEGIN IMMEDIATE")
                fresh = db.execute(
                    """
                    SELECT status
                    FROM points_event_inbox
                    WHERE id = ?
                    """,
                    (int(event["id"]),),
                ).fetchone()
                if fresh is not None and fresh["status"] == "pending":
                    transaction = _process_event(db, event, policy)
                    db.execute(
                        """
                        UPDATE points_event_inbox
                        SET status = 'processed',
                            error = NULL,
                            processed_at = ?
                        WHERE id = ? AND status = 'pending'
                        """,
                        (
                            _platform_now().isoformat(timespec="seconds"),
                            int(event["id"]),
                        ),
                    )
                    result = _event_result(
                        db,
                        event,
                        status="processed",
                        transaction=transaction,
                    )
                else:
                    result = _event_result(
                        db,
                        event,
                        status=(
                            str(fresh["status"]) if fresh else "failed"
                        ),
                        transaction=_award_transaction_for_event(db, event),
                    )
            processed.append(result)
        except Exception as error:
            with db:
                db.execute(
                    """
                    UPDATE points_event_inbox
                    SET status = 'failed',
                        error = ?,
                        processed_at = ?
                    WHERE id = ?
                    """,
                    (
                        str(error),
                        _platform_now().isoformat(timespec="seconds"),
                        int(event["id"]),
                    ),
                )
            processed.append(
                _event_result(
                    db,
                    event,
                    status="failed",
                    error=str(error),
                )
            )
    return processed


def record_duration_points(
    user_id: int,
    source_module: str,
    source_key: str,
    duration_seconds: int,
    occurred_at: str,
    event_id: str,
) -> dict:
    source_key = _require_text(source_key, "学习来源不能为空")
    event_id = _require_text(event_id, "事件标识不能为空")
    encoded_event_id = (
        f"{source_key}{DURATION_EVENT_SEPARATOR}{event_id}"
    )
    enqueued = enqueue_learning_event(
        user_id,
        source_module,
        "duration",
        encoded_event_id,
        occurred_at,
        duration_seconds,
    )
    if enqueued["status"] != "pending":
        return enqueued
    results = process_pending_events(user_id)
    result = next(
        (
            item
            for item in results
            if item["event_id"] == enqueued["event_id"]
        ),
        None,
    )
    return result or enqueued


def record_training_points(
    user_id: int,
    source_module: str,
    event_type: str,
    source_event_id: str,
    occurred_at: str,
) -> dict:
    enqueued = enqueue_learning_event(
        user_id,
        source_module,
        event_type,
        source_event_id,
        occurred_at,
    )
    if enqueued["status"] != "pending":
        return enqueued
    results = process_pending_events(user_id)
    result = next(
        (
            item
            for item in results
            if item["event_id"] == enqueued["event_id"]
        ),
        None,
    )
    return result or enqueued


def spend_points_in_transaction(
    db,
    user_id: int,
    amount: int,
    source_module: str,
    source_event_id: str,
    normalized_time: str,
) -> dict:
    existing = _existing_transaction(
        db,
        user_id,
        "spend",
        source_module,
        source_event_id,
    )
    if existing is not None:
        return existing
    _ensure_account(db, user_id, normalized_time)
    account = db.execute(
        """
        SELECT balance
        FROM points_accounts
        WHERE user_id = ?
        """,
        (user_id,),
    ).fetchone()
    balance = int(account["balance"])
    if balance < amount:
        raise AgriValidationError("积分不足")
    lots = db.execute(
        """
        SELECT id, remaining_points
        FROM points_lots
        WHERE user_id = ?
          AND remaining_points > 0
          AND (expires_at IS NULL OR expires_at > ?)
        ORDER BY created_at, id
        """,
        (user_id, normalized_time),
    ).fetchall()
    if sum(int(row["remaining_points"]) for row in lots) < amount:
        raise AgriValidationError("积分不足")

    balance_after = balance - amount
    cursor = db.execute(
        """
        INSERT INTO points_transactions (
            user_id, transaction_type, source_module, source_event_id,
            delta, balance_after, metadata_json, created_at
        )
        VALUES (?, 'spend', ?, ?, ?, ?, '{}', ?)
        """,
        (
            user_id,
            source_module,
            source_event_id,
            -amount,
            balance_after,
            normalized_time,
        ),
    )
    transaction_id = int(cursor.lastrowid)
    remaining = amount
    for lot in lots:
        if remaining <= 0:
            break
        lot_points = min(remaining, int(lot["remaining_points"]))
        cursor = db.execute(
            """
            UPDATE points_lots
            SET remaining_points = remaining_points - ?
            WHERE id = ? AND remaining_points >= ?
            """,
            (lot_points, int(lot["id"]), lot_points),
        )
        if cursor.rowcount != 1:
            raise AgriValidationError("积分批次已变化")
        db.execute(
            """
            INSERT INTO points_allocations (
                transaction_id, lot_id, points
            )
            VALUES (?, ?, ?)
            """,
            (transaction_id, int(lot["id"]), lot_points),
        )
        remaining -= lot_points
    if remaining != 0:
        raise AgriValidationError("积分批次不足")
    db.execute(
        """
        UPDATE points_accounts
        SET balance = ?, updated_at = ?
        WHERE user_id = ?
        """,
        (balance_after, normalized_time, user_id),
    )
    return {
        "id": transaction_id,
        "transaction_type": "spend",
        "delta": -amount,
        "balance_after": balance_after,
        "source_module": source_module,
        "source_event_id": source_event_id,
        "created_at": normalized_time,
    }


def spend_points(
    user_id: int,
    amount: int,
    source_module: str,
    source_event_id: str,
    occurred_at: str | None = None,
) -> dict:
    user_id = _require_positive_int(user_id, "学员标识必须是正整数")
    amount = _require_positive_int(amount, "消费积分必须是正整数")
    source_module = _require_text(source_module, "来源模块不能为空")
    source_event_id = _require_text(source_event_id, "来源事件标识不能为空")
    _, normalized_time = _normalize_event_time(occurred_at)
    get_effective_policy()

    with _get_db() as db:
        db.execute("BEGIN IMMEDIATE")
        return spend_points_in_transaction(
            db,
            user_id,
            amount,
            source_module,
            source_event_id,
            normalized_time,
        )


def refund_points(
    user_id: int,
    amount: int,
    source_module: str,
    source_event_id: str,
    spend_transaction_id: int,
    occurred_at: str | None = None,
) -> dict:
    user_id = _require_positive_int(user_id, "学员标识必须是正整数")
    amount = _require_positive_int(amount, "回退积分必须是正整数")
    source_module = _require_text(source_module, "来源模块不能为空")
    source_event_id = _require_text(source_event_id, "来源事件标识不能为空")
    spend_transaction_id = _require_positive_int(
        spend_transaction_id,
        "消费流水标识必须是正整数",
    )
    _, normalized_time = _normalize_event_time(occurred_at)
    policy = get_effective_policy()

    with _get_db() as db:
        db.execute("BEGIN IMMEDIATE")
        spend = db.execute(
            """
            SELECT id, delta
            FROM points_transactions
            WHERE id = ?
              AND user_id = ?
              AND transaction_type = 'spend'
            """,
            (spend_transaction_id, user_id),
        ).fetchone()
        if spend is None:
            raise AgriValidationError("消费流水不存在")
        if amount != -int(spend["delta"]):
            raise AgriValidationError("回退金额与原消费不一致")
        existing = _existing_transaction(
            db,
            user_id,
            "refund",
            source_module,
            source_event_id,
        )
        if existing is not None:
            return existing
        existing_spend_refund = _existing_refund_for_spend(
            db,
            user_id,
            spend_transaction_id,
        )
        if existing_spend_refund is not None:
            return existing_spend_refund
        allocations = db.execute(
            """
            SELECT
                pa.lot_id,
                pa.points,
                l.original_points,
                l.remaining_points,
                l.expires_at
            FROM points_allocations pa
            JOIN points_lots l ON l.id = pa.lot_id
            WHERE pa.transaction_id = ?
            ORDER BY l.created_at, l.id
            """,
            (spend_transaction_id,),
        ).fetchall()
        allocated = sum(int(row["points"]) for row in allocations)
        if allocated < amount:
            raise AgriValidationError("回退积分超过原消费")

        _ensure_account(db, user_id, normalized_time)
        account = db.execute(
            """
            SELECT balance
            FROM points_accounts
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()
        balance_after = int(account["balance"]) + amount
        cursor = db.execute(
            """
            INSERT INTO points_transactions (
                user_id, transaction_type, source_module, source_event_id,
                delta, balance_after, metadata_json, created_at
            )
            VALUES (?, 'refund', ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                source_module,
                source_event_id,
                amount,
                balance_after,
                json.dumps(
                    {"spend_transaction_id": spend_transaction_id},
                    ensure_ascii=False,
                ),
                normalized_time,
            ),
        )
        transaction_id = int(cursor.lastrowid)
        remaining = amount
        expired_restore = 0
        for allocation in allocations:
            if remaining <= 0:
                break
            restore = min(remaining, int(allocation["points"]))
            if (
                allocation["expires_at"] is not None
                and str(allocation["expires_at"]) <= normalized_time
            ):
                expired_restore += restore
                remaining -= restore
                continue
            db.execute(
                """
                UPDATE points_lots
                SET remaining_points = MIN(
                    original_points,
                    remaining_points + ?
                )
                WHERE id = ?
                """,
                (restore, int(allocation["lot_id"])),
            )
            db.execute(
                """
                INSERT INTO points_allocations (
                    transaction_id, lot_id, points
                )
                VALUES (?, ?, ?)
                """,
                (transaction_id, int(allocation["lot_id"]), restore),
            )
            remaining -= restore
        if expired_restore > 0:
            cursor = db.execute(
                """
                INSERT INTO points_lots (
                    user_id, award_transaction_id, original_points,
                    remaining_points, expires_at, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    transaction_id,
                    expired_restore,
                    expired_restore,
                    _expires_at(normalized_time, policy),
                    normalized_time,
                ),
            )
            db.execute(
                """
                INSERT INTO points_allocations (
                    transaction_id, lot_id, points
                )
                VALUES (?, ?, ?)
                """,
                (transaction_id, int(cursor.lastrowid), expired_restore),
            )
        db.execute(
            """
            UPDATE points_accounts
            SET balance = ?, updated_at = ?
            WHERE user_id = ?
            """,
            (balance_after, normalized_time, user_id),
        )

    return {
        "id": transaction_id,
        "transaction_type": "refund",
        "delta": amount,
        "balance_after": balance_after,
        "source_module": source_module,
        "source_event_id": source_event_id,
        "created_at": normalized_time,
    }


def settle_user_expiry(
    user_id: int,
    now: str | None = None,
) -> dict:
    user_id = _require_positive_int(user_id, "学员标识必须是正整数")
    policy = get_effective_policy()
    if policy["expiry_mode"] == "permanent":
        return {"points_cleared": 0, "lots": 0, "transaction_id": None}
    _, normalized_now = _normalize_event_time(now)

    with _get_db() as db:
        db.execute("BEGIN IMMEDIATE")
        lots = db.execute(
            """
            SELECT id, remaining_points
            FROM points_lots
            WHERE user_id = ?
              AND expires_at IS NOT NULL
              AND expires_at <= ?
              AND remaining_points > 0
            ORDER BY expires_at, id
            """,
            (user_id, normalized_now),
        ).fetchall()
        points_cleared = sum(int(row["remaining_points"]) for row in lots)
        if points_cleared == 0:
            return {
                "points_cleared": 0,
                "lots": 0,
                "transaction_id": None,
            }
        _ensure_account(db, user_id, normalized_now)
        account = db.execute(
            """
            SELECT balance
            FROM points_accounts
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()
        balance_after = max(0, int(account["balance"]) - points_cleared)
        source_event_id = f"expiry:{user_id}:{normalized_now}"
        existing = _existing_transaction(
            db,
            user_id,
            "expire",
            "points",
            source_event_id,
        )
        if existing is not None:
            return {
                "points_cleared": 0,
                "lots": 0,
                "transaction_id": existing["id"],
            }
        cursor = db.execute(
            """
            INSERT INTO points_transactions (
                user_id, transaction_type, source_module, source_event_id,
                delta, balance_after, metadata_json, created_at
            )
            VALUES (?, 'expire', 'points', ?, ?, ?, '{}', ?)
            """,
            (
                user_id,
                source_event_id,
                -points_cleared,
                balance_after,
                normalized_now,
            ),
        )
        transaction_id = int(cursor.lastrowid)
        for lot in lots:
            lot_points = int(lot["remaining_points"])
            db.execute(
                """
                UPDATE points_lots
                SET remaining_points = 0
                WHERE id = ? AND remaining_points = ?
                """,
                (int(lot["id"]), lot_points),
            )
            db.execute(
                """
                INSERT INTO points_allocations (
                    transaction_id, lot_id, points
                )
                VALUES (?, ?, ?)
                """,
                (transaction_id, int(lot["id"]), lot_points),
            )
        db.execute(
            """
            UPDATE points_accounts
            SET balance = ?, updated_at = ?
            WHERE user_id = ?
            """,
            (balance_after, normalized_now, user_id),
        )

    return {
        "points_cleared": points_cleared,
        "lots": len(lots),
        "transaction_id": transaction_id,
    }
