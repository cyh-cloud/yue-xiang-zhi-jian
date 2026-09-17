from __future__ import annotations

# Future reward providers must reserve/release stock through the caller's
# SQLite transaction, or provide an idempotent compensating operation when
# the transaction rolls back.

import json
from datetime import datetime
from zoneinfo import ZoneInfo

from app.agri_skills.errors import AgriNotFoundError, AgriValidationError
from app.handcraft_inheritance.points import (
    get_effective_policy,
    get_points_account,
    spend_points_in_transaction,
)
from app.handcraft_inheritance.providers import get_reward_catalog_provider


PLATFORM_TIMEZONE = ZoneInfo("Asia/Shanghai")
REDEMPTION_CONFLICT_MESSAGE = "库存或积分已变化，请刷新后重试"


def _get_db():
    from app.db import get_db

    return get_db()


def _positive_int(value: object, message: str) -> int:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or value <= 0
    ):
        raise AgriValidationError(message)
    return value


def _required_text(value: object, message: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise AgriValidationError(message)
    return normalized


def _now_iso() -> str:
    return datetime.now(PLATFORM_TIMEZONE).isoformat(timespec="seconds")


def emit_redemption_succeeded(**payload):
    from app.messaging.events import emit_redemption_succeeded as emit

    return emit(**payload)


def _find_reward(reward_id: str) -> dict | None:
    return next(
        (
            dict(reward)
            for reward in get_reward_catalog_provider().list_rewards()
            if str(reward.get("reward_id", "")) == reward_id
        ),
        None,
    )


def _reward_numbers(reward: dict) -> tuple[int, int]:
    try:
        stock = int(reward.get("stock"))
        points_cost = int(reward.get("points_cost"))
    except (TypeError, ValueError):
        raise AgriValidationError("奖品配置不可用") from None
    if (
        isinstance(reward.get("stock"), bool)
        or isinstance(reward.get("points_cost"), bool)
        or stock < 0
        or points_cost <= 0
    ):
        raise AgriValidationError("奖品配置不可用")
    return stock, points_cost


def _validate_reward(reward: dict | None, balance: int) -> None:
    if reward is None:
        raise AgriNotFoundError("奖品不存在")
    if (
        reward.get("source_available") is False
        or reward.get("is_online") is False
    ):
        raise AgriValidationError("奖品已下架")
    stock, points_cost = _reward_numbers(reward)
    if stock <= 0:
        raise AgriValidationError("已抢完")
    if balance < points_cost:
        raise AgriValidationError(
            f"积分不足，还差 {points_cost - balance} 分"
        )


def list_rewards(user_id: int) -> list[dict]:
    user_id = _positive_int(user_id, "学员标识必须是正整数")
    balance = int(get_points_account(user_id)["balance"])
    rewards = []
    for raw_reward in get_reward_catalog_provider().list_rewards():
        reward = dict(raw_reward)
        source_available = reward.get("source_available") is not False
        is_online = reward.get("is_online") is not False
        try:
            stock, points_cost = _reward_numbers(reward)
        except AgriValidationError:
            reward.update(
                {
                    "affordable": False,
                    "can_redeem": False,
                    "unavailable_reason": "奖品配置不可用",
                }
            )
            rewards.append(reward)
            continue
        reason = None
        if not source_available or not is_online:
            reason = "奖品已下架"
        elif stock <= 0:
            reason = "已抢完"
        elif balance < points_cost:
            reason = f"积分不足，还差 {points_cost - balance} 分"
        reward.update(
            {
                "affordable": balance >= points_cost,
                "can_redeem": reason is None,
                "unavailable_reason": reason,
            }
        )
        rewards.append(reward)
    return rewards


def _serialize_redemption(row) -> dict:
    return {
        "id": int(row["id"]),
        "user_id": int(row["user_id"]),
        "reward_id": str(row["reward_id"]),
        "reward_name": str(row["reward_name"]),
        "reward": json.loads(row["reward_snapshot_json"]),
        "points_cost": int(row["points_cost"]),
        "request_id": str(row["request_id"]),
        "status": str(row["status"]),
        "reservation_status": (
            str(row["reservation_status"])
            if row["reservation_status"] is not None
            else None
        ),
        "created_at": str(row["created_at"]),
        "updated_at": str(row["updated_at"]),
        "canceled_at": row["canceled_at"],
    }


def list_redemptions(user_id: int) -> list[dict]:
    user_id = _positive_int(user_id, "学员标识必须是正整数")
    rows = _get_db().execute(
        """
        SELECT
            r.*,
            rs.status AS reservation_status
        FROM redemptions r
        LEFT JOIN reward_stock_reservations rs
          ON rs.redemption_id = r.id
        WHERE r.user_id = ?
        ORDER BY r.created_at DESC, r.id DESC
        """,
        (user_id,),
    ).fetchall()
    return [_serialize_redemption(row) for row in rows]


def _existing_redemption(
    db,
    user_id: int,
    request_id: str,
) -> dict | None:
    row = db.execute(
        """
        SELECT
            r.*,
            rs.status AS reservation_status
        FROM redemptions r
        LEFT JOIN reward_stock_reservations rs
          ON rs.redemption_id = r.id
        WHERE r.user_id = ? AND r.request_id = ?
        """,
        (user_id, request_id),
    ).fetchone()
    return _serialize_redemption(row) if row is not None else None


def _notification_payload(user_id: int, redemption: dict) -> dict:
    return {
        "event_id": (
            f"handcraft-redemption:{redemption['id']}:succeeded"
        ),
        "student_id": user_id,
        "redemption_id": str(redemption["id"]),
        "points_spent": int(redemption["points_cost"]),
        "prize_name": str(redemption["reward_name"]),
    }


def redeem_reward(
    user_id: int,
    reward_id: str,
    request_id: str,
) -> dict:
    user_id = _positive_int(user_id, "学员标识必须是正整数")
    reward_id = _required_text(reward_id, "奖品标识不能为空")
    request_id = _required_text(request_id, "请求标识不能为空")
    db = _get_db()
    existing = _existing_redemption(db, user_id, request_id)
    if existing is not None:
        emit_redemption_succeeded(**_notification_payload(user_id, existing))
        return existing

    get_effective_policy()
    preliminary_balance = int(get_points_account(user_id)["balance"])
    preliminary_reward = _find_reward(reward_id)
    if preliminary_reward is not None:
        preliminary_stock, _ = _reward_numbers(preliminary_reward)
    else:
        preliminary_stock = None
    if preliminary_stock is not None and preliminary_stock <= 0:
        reservation = db.execute(
            """
            SELECT 1
            FROM reward_stock_reservations
            WHERE reward_id = ? AND status = 'reserved'
            LIMIT 1
            """,
            (reward_id,),
        ).fetchone()
        if reservation is not None:
            raise AgriValidationError(REDEMPTION_CONFLICT_MESSAGE)
    _validate_reward(preliminary_reward, preliminary_balance)
    normalized_time = _now_iso()

    with db:
        db.execute("BEGIN IMMEDIATE")
        existing = _existing_redemption(db, user_id, request_id)
        if existing is not None:
            redemption = existing
        else:
            reward = dict(preliminary_reward)
            account = get_points_account(user_id, settle=False)
            _validate_reward(reward, int(account["balance"]))
            cursor = db.execute(
                """
                INSERT INTO redemptions (
                    user_id, reward_id, reward_name, reward_snapshot_json,
                    points_cost, request_id, status, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?)
                """,
                (
                    user_id,
                    reward_id,
                    str(reward["name"]),
                    json.dumps(reward, ensure_ascii=False),
                    int(reward["points_cost"]),
                    request_id,
                    normalized_time,
                    normalized_time,
                ),
            )
            redemption_id = int(cursor.lastrowid)
            db.execute(
                """
                INSERT INTO fulfillments (
                    redemption_id, user_id, status, created_at, updated_at
                )
                VALUES (?, ?, 'pending', ?, ?)
                """,
                (
                    redemption_id,
                    user_id,
                    normalized_time,
                    normalized_time,
                ),
            )
            reservation_token = get_reward_catalog_provider().reserve_stock(
                reward_id,
                1,
                str(redemption_id),
            )
            if not reservation_token:
                raise AgriValidationError(REDEMPTION_CONFLICT_MESSAGE)
            try:
                spend_points_in_transaction(
                    db,
                    user_id,
                    int(reward["points_cost"]),
                    "handcraft",
                    f"redemption:{request_id}",
                    normalized_time,
                )
                row = db.execute(
                    """
                    SELECT
                        r.*,
                        rs.status AS reservation_status
                    FROM redemptions r
                    LEFT JOIN reward_stock_reservations rs
                      ON rs.redemption_id = r.id
                    WHERE r.id = ?
                    """,
                    (redemption_id,),
                ).fetchone()
                redemption = _serialize_redemption(row)
            except Exception as error:
                try:
                    get_reward_catalog_provider().release_stock(
                        reservation_token
                    )
                except Exception:
                    pass
                raise AgriValidationError(
                    REDEMPTION_CONFLICT_MESSAGE
                ) from error

        notification = _notification_payload(user_id, redemption)

    emit_redemption_succeeded(**notification)
    return redemption
