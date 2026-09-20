from __future__ import annotations

import re
import sqlite3
from uuid import uuid4

from app.admin_console.audit import record_admin_audit
from app.admin_console.errors import (
    ProviderConflictError,
    ProviderNotFoundError,
    ProviderValidationError,
)
from app.admin_console.time_utils import platform_now_iso
from app.db import get_db
from app.handcraft_inheritance.presets import (
    PLACEHOLDER_REWARDS,
    PlaceholderRewardCatalogProvider,
)


STABLE_KEY_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
REWARD_NAME_MAX_LENGTH = 60
REWARD_COLUMNS = """
    r.reward_id, r.name, r.points_cost, r.stock, r.is_online,
    r.source_available, r.is_demo, r.version, r.created_at, r.updated_at
"""
REWARD_RESERVED_JOINS = """
    LEFT JOIN (
        SELECT reward_id, SUM(quantity) AS reserved
        FROM admin_reward_reservations
        WHERE status = 'reserved'
        GROUP BY reward_id
    ) admin_reserved ON admin_reserved.reward_id = r.reward_id
    LEFT JOIN (
        SELECT reward_id, SUM(quantity) AS reserved
        FROM reward_stock_reservations
        WHERE status = 'reserved'
        GROUP BY reward_id
    ) redemption_reserved
        ON redemption_reserved.reward_id = r.reward_id
"""
REWARD_ORDER = "ORDER BY r.is_online DESC, r.points_cost ASC, r.reward_id ASC"
RESERVATION_COLUMNS = """
    reservation_id, reward_id, quantity, status, created_at, released_at
"""


def _fetch_all(sql: str, parameters: tuple = ()) -> list[sqlite3.Row]:
    return get_db().execute(sql, parameters).fetchall()


def _fetch_one(sql: str, parameters: tuple = ()) -> sqlite3.Row | None:
    return get_db().execute(sql, parameters).fetchone()


def _required_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _validation(
    message: str,
    *,
    code: str = "reward_validation_failed",
    **details,
) -> ProviderValidationError:
    return ProviderValidationError(message, code=code, details=details)


def _not_found(
    message: str,
    code: str,
    **details,
) -> ProviderNotFoundError:
    return ProviderNotFoundError(message, code=code, details=details)


def _conflict(
    message: str,
    code: str,
    **details,
) -> ProviderConflictError:
    return ProviderConflictError(message, code=code, details=details)


def _bounded_text(value: object, *, field: str, maximum: int) -> str:
    normalized = _required_text(value)
    if normalized is None:
        raise _validation(f"{field} 不能为空", field=field)
    if len(normalized) > maximum:
        raise _validation(
            f"{field} 长度不能超过 {maximum} 个字符",
            field=field,
            max_length=maximum,
        )
    return normalized


def _integer(value: object, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise _validation(f"{field} 必须是整数", field=field)
    return value


def _positive_integer(value: object, *, field: str) -> int:
    number = _integer(value, field=field)
    if number <= 0:
        raise _validation(f"{field} 必须是正整数", field=field)
    return number


def _stock_integer(value: object, *, field: str) -> int:
    number = _integer(value, field=field)
    if number < 0:
        raise _validation(f"{field} 不能小于 0", field=field)
    return number


def _flag(value: object, *, field: str, default: bool) -> bool:
    if value is None:
        return default
    if not isinstance(value, bool):
        raise _validation(f"{field} 必须是布尔值", field=field)
    return value


def _stable_key(value: object, *, field: str) -> str:
    normalized = _required_text(value)
    if normalized is None or STABLE_KEY_PATTERN.fullmatch(normalized) is None:
        raise _validation(f"{field} 格式不正确", field=field)
    return normalized


def _expected_version(value: object) -> int:
    return _positive_integer(value, field="expected_version")


def _begin_exclusive(db: sqlite3.Connection) -> None:
    """Open the write transaction before the version and stock checks.

    `load_session` runs a `DELETE FROM sessions WHERE expires_at <= ?` that
    implicitly opens a deferred transaction holding no write lock, and it is
    invoked twice per admin request. A deferred transaction only keeps other
    writers from committing, so two admins could both pass the version check
    and then deadlock on commit; committing the pending work and starting
    `BEGIN IMMEDIATE` is what actually serializes them. Only the admin
    service functions use this, because 05 never calls them from inside its
    own transaction.
    """
    if db.in_transaction:
        db.commit()
    db.execute("BEGIN IMMEDIATE")


def _begin_stock(db: sqlite3.Connection) -> bool:
    """Take the write lock for a stock move and report transaction ownership.

    Returns True when this call opened the transaction and therefore has to
    commit or roll it back. 05's `redeem_reward` and `fulfillment.py` both
    run `BEGIN IMMEDIATE` before calling into the provider, and the
    reservation has to join that transaction: committing it here would
    persist a redemption whose point spend still fails, and the caller's
    rollback would no longer remove the reservation row. When no transaction
    is open the write lock is taken before the stock SELECT, so a direct
    caller gets the same serialization the admin write paths get.
    """
    if db.in_transaction:
        return False
    db.execute("BEGIN IMMEDIATE")
    return True


def _reserved_quantity(db: sqlite3.Connection, reward_id: str) -> int:
    row = db.execute(
        """
        SELECT
            COALESCE((
                SELECT SUM(quantity)
                FROM admin_reward_reservations
                WHERE reward_id = ? AND status = 'reserved'
            ), 0)
            + COALESCE((
                SELECT SUM(quantity)
                FROM reward_stock_reservations
                WHERE reward_id = ? AND status = 'reserved'
            ), 0) AS reserved
        """,
        (reward_id, reward_id),
    ).fetchone()
    return int(row["reserved"])


def _serialize_catalog_reward(row: sqlite3.Row) -> dict:
    """Learner facing shape: `stock` is what is still redeemable.

    05's `_validate_reward` compares `stock <= 0` and `list_rewards` maps it
    to `已抢完`, so the value handed to the consumer is the available stock,
    not the configured total. Booleans are real `bool` because 05 tests
    `is False` / `is not False` on `is_online` and `source_available`.
    """
    reserved = int(row["reserved"] or 0)
    return {
        "reward_id": str(row["reward_id"]),
        "name": str(row["name"]),
        "points_cost": int(row["points_cost"]),
        "stock": max(0, int(row["stock"]) - reserved),
        "is_online": bool(row["is_online"]),
        "is_demo": bool(row["is_demo"]),
        "source_available": bool(row["source_available"]),
        "version": int(row["version"]),
        "created_at": str(row["created_at"]),
        "updated_at": str(row["updated_at"]),
    }


def _serialize_admin_reward(row: sqlite3.Row) -> dict:
    """Console facing shape: `stock` is the configured total on the row."""
    reserved = int(row["reserved"] or 0)
    stock = int(row["stock"])
    return {
        "reward_id": str(row["reward_id"]),
        "name": str(row["name"]),
        "points_cost": int(row["points_cost"]),
        "stock": stock,
        "reserved": reserved,
        "available": max(0, stock - reserved),
        "is_online": bool(row["is_online"]),
        "is_demo": bool(row["is_demo"]),
        "source_available": bool(row["source_available"]),
        "version": int(row["version"]),
        "created_at": str(row["created_at"]),
        "updated_at": str(row["updated_at"]),
    }


class DatabaseRewardCatalogProvider(PlaceholderRewardCatalogProvider):
    """Authoritative reward catalog and stock read from `admin_rewards`.

    The `PlaceholderRewardCatalogProvider` base class is retained only as a
    compatibility shim: the frozen `tests/test_handcraft_presets.py` asserts
    the installed provider `isinstance(provider,
    PlaceholderRewardCatalogProvider)`. No placeholder content is ever served
    from here; `list_rewards`, `reserve_stock` and `release_stock` never call
    `super()`, and the in-memory placeholder stock the base class builds is
    never read. `admin_rewards` is the single authoritative source once 011
    owns the slot, and `seed_demo_rewards` turns the four 05 demo rewards into
    real manageable rows on first start, so the mall shows exactly what the
    admin console can edit instead of content 011 cannot reach.
    """

    def list_rewards(self) -> list[dict]:
        rows = _fetch_all(
            f"""
            SELECT {REWARD_COLUMNS},
                COALESCE(admin_reserved.reserved, 0)
                    + COALESCE(redemption_reserved.reserved, 0) AS reserved
            FROM admin_rewards r
            {REWARD_RESERVED_JOINS}
            {REWARD_ORDER}
            """
        )
        return [_serialize_catalog_reward(row) for row in rows]

    def reserve_stock(
        self,
        reward_id: str,
        quantity: int,
        reservation_id: str,
    ) -> str | None:
        return reserve_reward_stock(
            reward_id,
            quantity,
            reservation_id,
            require_online=True,
        )

    def release_stock(self, reservation_id: str) -> bool:
        return release_reward_stock(reservation_id)


def _redemption_id(db: sqlite3.Connection, reservation_id: str) -> int | None:
    """Resolve a reservation token to a 05 redemption, as 05's placeholder does.

    05 always passes `str(redemption_id)`, and the optional `redemption:`
    prefix is accepted so an external caller can name the redemption
    explicitly. A token that is not all digits, or that names a redemption
    which does not exist, cannot be stored in `reward_stock_reservations`
    because that table has a mandatory foreign key to `redemptions`.
    """
    normalized = str(reservation_id).strip()
    if normalized.startswith("redemption:"):
        normalized = normalized.split(":", 1)[1]
    if not normalized.isdigit():
        return None
    row = db.execute(
        """
        SELECT id
        FROM redemptions
        WHERE id = ?
        """,
        (int(normalized),),
    ).fetchone()
    return int(row["id"]) if row is not None else None


def _find_reservation(
    db: sqlite3.Connection,
    reservation_id: str,
) -> dict | None:
    row = db.execute(
        f"""
        SELECT 'admin_reward_reservations' AS source, {RESERVATION_COLUMNS}
        FROM admin_reward_reservations
        WHERE reservation_id = ?
        """,
        (reservation_id,),
    ).fetchone()
    if row is None:
        row = db.execute(
            f"""
            SELECT 'reward_stock_reservations' AS source, {RESERVATION_COLUMNS}
            FROM reward_stock_reservations
            WHERE reservation_id = ?
            """,
            (reservation_id,),
        ).fetchone()
    return dict(row) if row is not None else None


def _reserve_within_transaction(
    db: sqlite3.Connection,
    reward_id: str,
    quantity: int,
    reservation_id: str,
    *,
    require_online: bool,
) -> str | None:
    existing = _find_reservation(db, reservation_id)
    if existing is not None:
        if (
            existing["status"] == "reserved"
            and str(existing["reward_id"]) == reward_id
            and int(existing["quantity"]) == quantity
        ):
            return reservation_id
        return None

    row = db.execute(
        """
        SELECT reward_id, stock, is_online
        FROM admin_rewards
        WHERE reward_id = ?
        """,
        (reward_id,),
    ).fetchone()
    if row is None:
        return None
    if require_online and not row["is_online"]:
        return None
    if max(0, int(row["stock"]) - _reserved_quantity(db, reward_id)) < quantity:
        return None

    now = platform_now_iso()
    redemption_id = _redemption_id(db, reservation_id)
    if redemption_id is not None:
        # 05 reads this table directly for redemption and fulfillment views,
        # so a redemption backed reservation has to live there.
        try:
            db.execute(
                """
                INSERT INTO reward_stock_reservations (
                    reservation_id, redemption_id, reward_id, quantity, status,
                    created_at
                )
                VALUES (?, ?, ?, ?, 'reserved', ?)
                """,
                (reservation_id, redemption_id, reward_id, quantity, now),
            )
        except sqlite3.IntegrityError:
            # 05 declares `redemption_id` UNIQUE, so a second token for the
            # same redemption is a refusal, not a crash: the redemption is
            # already holding its stock.
            return None
    else:
        db.execute(
            """
            INSERT INTO admin_reward_reservations (
                reservation_id, reward_id, quantity, status, created_at
            )
            VALUES (?, ?, ?, 'reserved', ?)
            """,
            (reservation_id, reward_id, quantity, now),
        )
    return reservation_id


def reserve_reward_stock(
    reward_id: str,
    quantity: int,
    reservation_id: str,
    *,
    require_online: bool = True,
) -> str | None:
    """Reserve stock and return the reservation token, or `None` when refused.

    Refusal is silent by contract: 05's `redeem_reward` maps a falsy token to
    its own conflict message, and the provider protocol has no error channel
    for stock. Re-reserving the same token with the same reward and quantity
    is idempotent, a mismatched re-reserve is refused, and a released token
    is never resurrected.
    """
    normalized_reward_id = _required_text(reward_id)
    normalized_reservation_id = _required_text(reservation_id)
    if normalized_reward_id is None or normalized_reservation_id is None:
        return None
    if (
        isinstance(quantity, bool)
        or not isinstance(quantity, int)
        or quantity <= 0
    ):
        return None

    db = get_db()
    owns_transaction = _begin_stock(db)
    try:
        result = _reserve_within_transaction(
            db,
            normalized_reward_id,
            quantity,
            normalized_reservation_id,
            require_online=require_online,
        )
    except Exception:
        if owns_transaction:
            db.rollback()
        raise
    if owns_transaction:
        db.commit()
    return result


def release_reward_stock(reservation_id: str) -> bool:
    """Mark a reservation released without deleting the audit trail.

    Idempotent: an already released token returns True, an unknown token
    returns False.
    """
    normalized = _required_text(reservation_id)
    if normalized is None:
        return False

    db = get_db()
    owns_transaction = _begin_stock(db)
    try:
        result = _release_within_transaction(db, normalized)
    except Exception:
        if owns_transaction:
            db.rollback()
        raise
    if owns_transaction:
        db.commit()
    return result


def _release_within_transaction(
    db: sqlite3.Connection,
    reservation_id: str,
) -> bool:
    existing = _find_reservation(db, reservation_id)
    if existing is None:
        return False
    if existing["status"] == "released":
        return True
    cursor = db.execute(
        f"""
        UPDATE {existing["source"]}
        SET status = 'released', released_at = ?
        WHERE reservation_id = ? AND status = 'reserved'
        """,
        (platform_now_iso(), reservation_id),
    )
    return cursor.rowcount == 1


def list_rewards_admin() -> list[dict]:
    rows = _fetch_all(
        f"""
        SELECT {REWARD_COLUMNS},
            COALESCE(admin_reserved.reserved, 0)
                + COALESCE(redemption_reserved.reserved, 0) AS reserved
        FROM admin_rewards r
        {REWARD_RESERVED_JOINS}
        {REWARD_ORDER}
        """
    )
    return [_serialize_admin_reward(row) for row in rows]


def list_reward_reservations(reward_id: str | None = None) -> list[dict]:
    """Read every reservation from both tables for the fulfillment views.

    Ordering is by stable reservation id on purpose: 011 writes `+08:00`
    timestamps while 05's placeholder wrote UTC `Z` values into
    `reward_stock_reservations`, so ordering the merged list by timestamp
    text would mix two offsets.
    """
    normalized = _required_text(reward_id)
    parameters: tuple = ()
    where = ""
    if normalized is not None:
        where = "WHERE reward_id = ?"
        parameters = (normalized,)
    rows = _fetch_all(
        f"""
        SELECT 'admin_reward_reservations' AS source, {RESERVATION_COLUMNS}
        FROM admin_reward_reservations
        {where}
        UNION ALL
        SELECT 'reward_stock_reservations' AS source, {RESERVATION_COLUMNS}
        FROM reward_stock_reservations
        {where}
        ORDER BY reservation_id ASC
        """,
        parameters + parameters,
    )
    return [dict(row) for row in rows]


def _reward_payload(
    payload: dict,
    *,
    existing: sqlite3.Row | None = None,
) -> dict:
    if not isinstance(payload, dict):
        raise _validation("请求内容格式不正确", field="payload")
    if existing is None:
        supplied_id = payload.get("reward_id")
        reward_id = (
            _stable_key(supplied_id, field="reward_id")
            if supplied_id is not None
            else f"reward-{uuid4().hex}"
        )
        online_default = True
        source_default = True
    else:
        reward_id = str(existing["reward_id"])
        supplied_id = payload.get("reward_id")
        if supplied_id is not None and _required_text(supplied_id) != reward_id:
            raise _validation(
                "reward_id 与请求路径不一致，不可修改",
                code="reward_id_mismatch",
                field="reward_id",
                current=reward_id,
            )
        online_default = bool(existing["is_online"])
        source_default = bool(existing["source_available"])

    values: dict = {
        "reward_id": reward_id,
        "name": _bounded_text(
            payload.get("name"),
            field="name",
            maximum=REWARD_NAME_MAX_LENGTH,
        ),
        "points_cost": _positive_integer(
            payload.get("points_cost"),
            field="points_cost",
        ),
        "is_online": _flag(
            payload.get("is_online"),
            field="is_online",
            default=online_default,
        ),
        "source_available": _flag(
            payload.get("source_available"),
            field="source_available",
            default=source_default,
        ),
    }
    supplied_stock = payload.get("stock")
    if supplied_stock is None and existing is not None:
        values["stock"] = int(existing["stock"])
    else:
        values["stock"] = _stock_integer(supplied_stock, field="stock")
    return values


def _admin_reward(reward_id: str) -> dict:
    row = _fetch_one(
        f"""
        SELECT {REWARD_COLUMNS},
            COALESCE(admin_reserved.reserved, 0)
                + COALESCE(redemption_reserved.reserved, 0) AS reserved
        FROM admin_rewards r
        {REWARD_RESERVED_JOINS}
        WHERE r.reward_id = ?
        """,
        (reward_id,),
    )
    if row is None:
        raise _not_found(
            "奖品不存在",
            "reward_not_found",
            reward_id=reward_id,
        )
    return _serialize_admin_reward(row)


def create_reward(actor_id: int, payload: dict) -> dict:
    values = _reward_payload(payload)
    now = platform_now_iso()
    try:
        with get_db() as db:
            db.execute(
                """
                INSERT INTO admin_rewards (
                    reward_id, name, points_cost, stock, is_online,
                    source_available, is_demo, version, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, 0, 1, ?, ?)
                """,
                (
                    values["reward_id"],
                    values["name"],
                    values["points_cost"],
                    values["stock"],
                    int(values["is_online"]),
                    int(values["source_available"]),
                    now,
                    now,
                ),
            )
            record_admin_audit(
                db,
                actor_id=actor_id,
                action="create_reward",
                target_type="reward",
                target_id=values["reward_id"],
                before=None,
                after={
                    "name": values["name"],
                    "points_cost": values["points_cost"],
                    "stock": values["stock"],
                    "is_online": values["is_online"],
                },
                result="success",
            )
    except sqlite3.IntegrityError as error:
        raise _conflict(
            "奖品标识已存在",
            "reward_conflict",
            reward_id=values["reward_id"],
        ) from error
    return _admin_reward(values["reward_id"])


def update_reward(
    actor_id: int,
    reward_id: str,
    expected_version: object,
    payload: dict,
) -> dict:
    key = _stable_key(reward_id, field="reward_id")
    locked_version = _expected_version(expected_version)
    db = get_db()
    _begin_exclusive(db)
    try:
        row = db.execute(
            """
            SELECT reward_id, name, points_cost, stock, is_online,
                   source_available, version
            FROM admin_rewards
            WHERE reward_id = ?
            """,
            (key,),
        ).fetchone()
        if row is None:
            raise _not_found(
                "奖品不存在",
                "reward_not_found",
                reward_id=key,
            )
        values = _reward_payload(payload, existing=row)
        current_version = int(row["version"])
        if current_version != locked_version:
            raise _conflict(
                "奖品已被其他管理员修改",
                "reward_version_conflict",
                reward_id=key,
                expected_version=locked_version,
                current_version=current_version,
            )
        reserved = _reserved_quantity(db, key)
        if values["stock"] < reserved:
            raise _validation(
                "库存不能小于待发放履约已预留数量",
                code="reward_stock_below_reserved",
                reward_id=key,
                reserved=reserved,
                stock=values["stock"],
            )
        now = platform_now_iso()
        cursor = db.execute(
            """
            UPDATE admin_rewards
            SET name = ?, points_cost = ?, stock = ?, is_online = ?,
                source_available = ?, version = ?, updated_at = ?
            WHERE reward_id = ? AND version = ?
            """,
            (
                values["name"],
                values["points_cost"],
                values["stock"],
                int(values["is_online"]),
                int(values["source_available"]),
                current_version + 1,
                now,
                key,
                current_version,
            ),
        )
        if cursor.rowcount != 1:
            raise _conflict(
                "奖品已被其他管理员修改",
                "reward_version_conflict",
                reward_id=key,
                expected_version=locked_version,
                current_version=current_version,
            )
        record_admin_audit(
            db,
            actor_id=actor_id,
            action="update_reward",
            target_type="reward",
            target_id=key,
            before={
                "version": current_version,
                "name": row["name"],
                "points_cost": int(row["points_cost"]),
                "stock": int(row["stock"]),
            },
            after={
                "version": current_version + 1,
                "name": values["name"],
                "points_cost": values["points_cost"],
                "stock": values["stock"],
            },
            result="success",
        )
    except Exception:
        db.rollback()
        raise
    db.commit()
    return _admin_reward(key)


def set_reward_online(
    actor_id: int,
    reward_id: str,
    expected_version: object,
    online: object,
) -> dict:
    key = _stable_key(reward_id, field="reward_id")
    locked_version = _expected_version(expected_version)
    flag = _flag(online, field="online", default=True)
    db = get_db()
    _begin_exclusive(db)
    try:
        row = db.execute(
            """
            SELECT reward_id, is_online, version
            FROM admin_rewards
            WHERE reward_id = ?
            """,
            (key,),
        ).fetchone()
        if row is None:
            raise _not_found(
                "奖品不存在",
                "reward_not_found",
                reward_id=key,
            )
        current_version = int(row["version"])
        if current_version != locked_version:
            raise _conflict(
                "奖品已被其他管理员修改",
                "reward_version_conflict",
                reward_id=key,
                expected_version=locked_version,
                current_version=current_version,
            )
        if bool(row["is_online"]) == flag:
            db.commit()
            return _admin_reward(key)
        cursor = db.execute(
            """
            UPDATE admin_rewards
            SET is_online = ?, version = version + 1, updated_at = ?
            WHERE reward_id = ? AND version = ?
            """,
            (int(flag), platform_now_iso(), key, current_version),
        )
        if cursor.rowcount != 1:
            raise _conflict(
                "奖品已被其他管理员修改",
                "reward_version_conflict",
                reward_id=key,
                expected_version=locked_version,
                current_version=current_version,
            )
        record_admin_audit(
            db,
            actor_id=actor_id,
            action="set_reward_online" if flag else "set_reward_offline",
            target_type="reward",
            target_id=key,
            before={"is_online": bool(row["is_online"]), "version": current_version},
            after={"is_online": flag, "version": current_version + 1},
            result="success",
        )
    except Exception:
        db.rollback()
        raise
    db.commit()
    return _admin_reward(key)


def seed_demo_rewards(connection) -> None:
    """Seed the 05 demo rewards as real, manageable admin rows.

    The content is read from 05's `PLACEHOLDER_REWARDS`, which stays the
    single source of truth for the demo text. `ON CONFLICT(reward_id) DO
    NOTHING` keeps admin edits and offline toggles across restarts, so the
    seed only fills an empty slot instead of overwriting the console.
    """
    now = platform_now_iso()
    rows = []
    for reward in PLACEHOLDER_REWARDS:
        rows.append(
            (
                str(reward["reward_id"]),
                str(reward["name"]),
                int(reward["points_cost"]),
                int(reward["stock"]),
                now,
                now,
            )
        )
    connection.executemany(
        """
        INSERT INTO admin_rewards (
            reward_id, name, points_cost, stock, is_online, source_available,
            is_demo, version, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, 1, 1, 1, 1, ?, ?)
        ON CONFLICT(reward_id) DO NOTHING
        """,
        rows,
    )


__all__ = [
    "DatabaseRewardCatalogProvider",
    "create_reward",
    "list_reward_reservations",
    "list_rewards_admin",
    "release_reward_stock",
    "reserve_reward_stock",
    "seed_demo_rewards",
    "set_reward_online",
    "update_reward",
]
