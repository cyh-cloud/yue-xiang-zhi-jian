from __future__ import annotations

import json
from datetime import datetime
from zoneinfo import ZoneInfo

from app.agri_skills.errors import AgriNotFoundError, AgriValidationError
from app.handcraft_inheritance.points import (
    get_effective_policy,
    refund_points_in_transaction,
)
from app.handcraft_inheritance.providers import get_reward_catalog_provider


PLATFORM_TIMEZONE = ZoneInfo("Asia/Shanghai")
ADMIN_ROLES = {"admin", "super_admin"}
VALID_FULFILLMENT_ROLES = {*ADMIN_ROLES, "student"}


def _get_db():
    from app.db import get_db

    return get_db()


def emit_fulfillment_issued(**payload):
    from app.messaging.events import emit_fulfillment_issued as emit

    return emit(**payload)


def emit_fulfillment_cancelled(**payload):
    from app.messaging.events import emit_fulfillment_cancelled as emit

    return emit(**payload)


def _now_iso() -> str:
    return datetime.now(PLATFORM_TIMEZONE).isoformat(timespec="seconds")


def _require_positive_int(value: object, message: str) -> int:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or value <= 0
    ):
        raise AgriValidationError(message)
    return value


def _require_admin_role(role: object) -> str:
    if role not in ADMIN_ROLES:
        raise AgriValidationError("无管理权限")
    return str(role)


def _require_fulfillment_role(role: object) -> str:
    if role not in VALID_FULFILLMENT_ROLES:
        raise AgriValidationError("无操作权限")
    return str(role)


def _load_fulfillment(db, fulfillment_id: int):
    return db.execute(
        """
        SELECT
            f.id,
            f.redemption_id,
            f.user_id,
            f.status,
            f.issued_at,
            f.verified_at,
            f.canceled_at,
            f.created_at,
            f.updated_at,
            r.reward_id,
            r.reward_name,
            r.points_cost,
            r.request_id,
            r.status AS redemption_status,
            r.created_at AS redemption_created_at,
            r.updated_at AS redemption_updated_at,
            rs.reservation_id,
            rs.status AS reservation_status
        FROM fulfillments f
        JOIN redemptions r ON r.id = f.redemption_id
        LEFT JOIN reward_stock_reservations rs
          ON rs.redemption_id = r.id
        WHERE f.id = ?
        """,
        (fulfillment_id,),
    ).fetchone()


def _notification_payload(row, operation: str) -> dict:
    event_type = (
        "cancelled" if operation == "cancel_pending" else "issued"
    )
    payload = {
        "event_id": (
            f"handcraft-fulfillment:{int(row['id'])}:{operation}"
        ),
        "student_id": int(row["user_id"]),
        "fulfillment_id": str(int(row["id"])),
        "prize_name": str(row["reward_name"]),
    }
    if event_type == "cancelled":
        payload["restored_points"] = int(row["points_cost"])
    return payload


def _result(
    row,
    *,
    changed: bool,
    restored_points: int = 0,
) -> dict:
    return {
        "fulfillment_id": int(row["id"]),
        "redemption_id": int(row["redemption_id"]),
        "user_id": int(row["user_id"]),
        "status": str(row["status"]),
        "changed": changed,
        "issued_at": row["issued_at"],
        "verified_at": row["verified_at"],
        "canceled_at": row["canceled_at"],
        "points_cost": int(row["points_cost"]),
        "restored_points": restored_points,
        "outbox_id": None,
        "notification_type": None,
        "notification": None,
    }


def _enqueue_outbox(
    db,
    row,
    *,
    operation: str,
    restored_points: int = 0,
) -> int:
    event_type = (
        "cancelled" if operation == "cancel_pending" else "issued"
    )
    notification = _notification_payload(row, operation)
    if event_type == "cancelled":
        notification["restored_points"] = restored_points
    db.execute(
        """
        INSERT INTO fulfillment_notification_outbox (
            fulfillment_id, event_type, event_id, payload_json,
            status, attempts, last_error, created_at, sent_at
        )
        VALUES (?, ?, ?, ?, 'pending', 0, NULL, ?, NULL)
        ON CONFLICT (fulfillment_id, event_type) DO NOTHING
        """,
        (
            int(row["id"]),
            event_type,
            str(notification["event_id"]),
            json.dumps(notification, ensure_ascii=False),
            _now_iso(),
        ),
    )
    outbox = db.execute(
        """
        SELECT id
        FROM fulfillment_notification_outbox
        WHERE fulfillment_id = ? AND event_type = ?
        """,
        (int(row["id"]), event_type),
    ).fetchone()
    return int(outbox["id"])


def _load_outbox(db, outbox_id: int):
    return db.execute(
        """
        SELECT *
        FROM fulfillment_notification_outbox
        WHERE id = ?
        """,
        (outbox_id,),
    ).fetchone()


def _record_outbox_failure(outbox_id: int, error: Exception) -> None:
    with _get_db() as db:
        db.execute(
            """
            UPDATE fulfillment_notification_outbox
            SET attempts = attempts + 1,
                last_error = ?
            WHERE id = ? AND status = 'pending'
            """,
            (str(error)[:500], outbox_id),
        )


def _mark_outbox_sent(outbox_id: int) -> bool:
    with _get_db() as db:
        cursor = db.execute(
            """
            UPDATE fulfillment_notification_outbox
            SET status = 'sent',
                attempts = attempts + 1,
                sent_at = ?,
                last_error = NULL
            WHERE id = ? AND status = 'pending'
            """,
            (_now_iso(), outbox_id),
        )
        return cursor.rowcount == 1


def deliver_fulfillment_outbox(
    outbox_id: int,
    *,
    emit_callback=None,
) -> dict:
    outbox_id = _require_positive_int(
        outbox_id,
        "通知发件箱标识必须是正整数",
    )
    row = _load_outbox(_get_db(), outbox_id)
    if row is None:
        raise AgriNotFoundError("通知发件箱记录不存在")
    if row["status"] == "sent":
        return {"sent": 0, "already_sent": 1, "failed": 0}

    payload = json.loads(row["payload_json"])
    try:
        if emit_callback is None:
            if row["event_type"] == "issued":
                emit_fulfillment_issued(**payload)
            else:
                emit_fulfillment_cancelled(**payload)
        else:
            emit_callback(payload)
    except Exception as error:
        _record_outbox_failure(outbox_id, error)
        raise

    sent = 1 if _mark_outbox_sent(outbox_id) else 0
    return {
        "sent": sent,
        "already_sent": 0 if sent else 1,
        "failed": 0,
    }


def issue_fulfillment(
    fulfillment_id: int,
    *,
    role: str,
    emit_notification: bool = True,
) -> dict:
    fulfillment_id = _require_positive_int(
        fulfillment_id,
        "履约单标识必须是正整数",
    )
    _require_admin_role(role)
    now = _now_iso()

    with _get_db() as db:
        db.execute("BEGIN IMMEDIATE")
        row = _load_fulfillment(db, fulfillment_id)
        if row is None:
            raise AgriNotFoundError("履约单不存在")

        changed = False
        if row["status"] == "pending":
            if row["redemption_status"] != "pending":
                raise AgriValidationError("当前履约状态不可发放")
            cursor = db.execute(
                """
                UPDATE fulfillments
                SET status = 'issued',
                    issued_at = ?,
                    updated_at = ?
                WHERE id = ? AND status = 'pending'
                """,
                (now, now, fulfillment_id),
            )
            if cursor.rowcount != 1:
                raise AgriValidationError("当前履约状态不可发放")
            cursor = db.execute(
                """
                UPDATE redemptions
                SET status = 'issued', updated_at = ?
                WHERE id = ? AND status = 'pending'
                """,
                (now, int(row["redemption_id"])),
            )
            if cursor.rowcount != 1:
                raise AgriValidationError("当前履约状态不可发放")
            changed = True
        elif row["status"] != "issued":
            raise AgriValidationError("当前履约状态不可发放")

        row = _load_fulfillment(db, fulfillment_id)
        outbox_id = _enqueue_outbox(
            db,
            row,
            operation="issue",
        )

    result = _result(row, changed=changed)
    notification = _notification_payload(row, "issue")
    result["outbox_id"] = outbox_id
    result["notification_type"] = "issued"
    result["notification"] = notification
    if emit_notification:
        deliver_fulfillment_outbox(outbox_id)
    return result


def manual_verify_fulfillment(
    fulfillment_id: int,
    *,
    role: str,
) -> dict:
    fulfillment_id = _require_positive_int(
        fulfillment_id,
        "履约单标识必须是正整数",
    )
    _require_admin_role(role)
    now = _now_iso()

    with _get_db() as db:
        db.execute("BEGIN IMMEDIATE")
        row = _load_fulfillment(db, fulfillment_id)
        if row is None:
            raise AgriNotFoundError("履约单不存在")

        changed = False
        if row["status"] == "issued":
            cursor = db.execute(
                """
                UPDATE fulfillments
                SET status = 'verified',
                    verified_at = ?,
                    updated_at = ?
                WHERE id = ? AND status = 'issued'
                """,
                (now, now, fulfillment_id),
            )
            if cursor.rowcount != 1:
                raise AgriValidationError("当前履约状态不可手工核销")
            cursor = db.execute(
                """
                UPDATE redemptions
                SET status = 'verified', updated_at = ?
                WHERE id = ? AND status IN ('pending', 'issued')
                """,
                (now, int(row["redemption_id"])),
            )
            if cursor.rowcount != 1:
                raise AgriValidationError("当前履约状态不可手工核销")
            changed = True
        elif row["status"] != "verified":
            raise AgriValidationError("当前履约状态不可手工核销")

        row = _load_fulfillment(db, fulfillment_id)

    return _result(row, changed=changed)


def student_verify_fulfillment(
    fulfillment_id: int,
    user_id: int,
) -> dict:
    fulfillment_id = _require_positive_int(
        fulfillment_id,
        "履约单标识必须是正整数",
    )
    user_id = _require_positive_int(user_id, "学员标识必须是正整数")
    now = _now_iso()

    with _get_db() as db:
        db.execute("BEGIN IMMEDIATE")
        row = _load_fulfillment(db, fulfillment_id)
        if row is None:
            raise AgriNotFoundError("履约单不存在")
        if int(row["user_id"]) != user_id:
            raise AgriValidationError("无权操作该履约单")

        changed = False
        if row["status"] == "issued":
            if row["redemption_status"] != "issued":
                raise AgriValidationError("当前履约状态不可核销")
            cursor = db.execute(
                """
                UPDATE fulfillments
                SET status = 'verified',
                    verified_at = ?,
                    updated_at = ?
                WHERE id = ? AND status = 'issued'
                """,
                (now, now, fulfillment_id),
            )
            if cursor.rowcount != 1:
                raise AgriValidationError("当前履约状态不可核销")
            cursor = db.execute(
                """
                UPDATE redemptions
                SET status = 'verified', updated_at = ?
                WHERE id = ? AND status = 'issued'
                """,
                (now, int(row["redemption_id"])),
            )
            if cursor.rowcount != 1:
                raise AgriValidationError("当前履约状态不可核销")
            changed = True
        elif row["status"] != "verified":
            raise AgriValidationError("当前履约状态不可核销")

        row = _load_fulfillment(db, fulfillment_id)

    return _result(row, changed=changed)


def _release_reservation(db, row) -> bool:
    reservation_id = row["reservation_id"]
    if reservation_id is None:
        reservation_id = str(int(row["redemption_id"]))
    return bool(
        get_reward_catalog_provider().release_stock(
            str(reservation_id)
        )
    )


def cancel_pending_fulfillment(
    fulfillment_id: int,
    *,
    role: str,
    actor_user_id: int | None = None,
    emit_notification: bool = True,
) -> dict:
    fulfillment_id = _require_positive_int(
        fulfillment_id,
        "履约单标识必须是正整数",
    )
    role = _require_fulfillment_role(role)
    if role == "student":
        actor_user_id = _require_positive_int(
            actor_user_id,
            "学员标识必须是正整数",
        )

    db = _get_db()
    preview = _load_fulfillment(db, fulfillment_id)
    if preview is None:
        raise AgriNotFoundError("履约单不存在")
    if role == "student" and int(preview["user_id"]) != actor_user_id:
        raise AgriValidationError("无权操作该履约单")
    if preview["status"] not in {"pending", "canceled"}:
        raise AgriValidationError("当前履约状态不可取消")

    preview_spend = None
    if preview["status"] == "pending":
        preview_spend = db.execute(
            """
            SELECT id
            FROM points_transactions
            WHERE user_id = ?
              AND transaction_type = 'spend'
              AND source_module = 'handcraft'
              AND source_event_id = ?
            """,
            (
                int(preview["user_id"]),
                f"redemption:{preview['request_id']}",
            ),
        ).fetchone()
    policy = (
        get_effective_policy()
        if preview_spend is not None
        else None
    )
    now = _now_iso()
    with db:
        db.execute("BEGIN IMMEDIATE")
        row = _load_fulfillment(db, fulfillment_id)
        if row is None:
            raise AgriNotFoundError("履约单不存在")
        if role == "student" and int(row["user_id"]) != actor_user_id:
            raise AgriValidationError("无权操作该履约单")

        changed = False
        restored_points = 0
        if row["status"] == "pending":
            if row["redemption_status"] != "pending":
                raise AgriValidationError("当前履约状态不可取消")

            spend = db.execute(
                """
                SELECT id
                FROM points_transactions
                WHERE user_id = ?
                  AND transaction_type = 'spend'
                  AND source_module = 'handcraft'
                  AND source_event_id = ?
                """,
                (
                    int(row["user_id"]),
                    f"redemption:{row['request_id']}",
                ),
            ).fetchone()
            reservation_exists = row["reservation_id"] is not None
            if spend is not None:
                if policy is None:
                    raise AgriValidationError("履约状态已变化，请重试")
                refund_points_in_transaction(
                    db,
                    int(row["user_id"]),
                    int(row["points_cost"]),
                    "handcraft",
                    f"fulfillment-cancel:{fulfillment_id}",
                    int(spend["id"]),
                    now,
                    policy,
                )
                restored_points = int(row["points_cost"])
            elif reservation_exists:
                raise AgriValidationError("消费流水不存在")

            cursor = db.execute(
                """
                UPDATE fulfillments
                SET status = 'canceled',
                    canceled_at = ?,
                    updated_at = ?
                WHERE id = ? AND status = 'pending'
                """,
                (now, now, fulfillment_id),
            )
            if cursor.rowcount != 1:
                raise AgriValidationError("当前履约状态不可取消")
            cursor = db.execute(
                """
                UPDATE redemptions
                SET status = 'canceled',
                    canceled_at = ?,
                    updated_at = ?
                WHERE id = ? AND status = 'pending'
                """,
                (now, now, int(row["redemption_id"])),
            )
            if cursor.rowcount != 1:
                raise AgriValidationError("当前履约状态不可取消")

            if reservation_exists:
                if not _release_reservation(db, row):
                    raise AgriValidationError("库存回滚失败")
            changed = True
        elif row["status"] == "canceled":
            refund = db.execute(
                """
                SELECT delta
                FROM points_transactions
                WHERE user_id = ?
                  AND transaction_type = 'refund'
                  AND source_module = 'handcraft'
                  AND source_event_id = ?
                """,
                (
                    int(row["user_id"]),
                    f"fulfillment-cancel:{fulfillment_id}",
                ),
            ).fetchone()
            restored_points = int(refund["delta"]) if refund else 0
        else:
            raise AgriValidationError("当前履约状态不可取消")

        row = _load_fulfillment(db, fulfillment_id)
        outbox_id = _enqueue_outbox(
            db,
            row,
            operation="cancel_pending",
            restored_points=restored_points,
        )

    result = _result(
        row,
        changed=changed,
        restored_points=restored_points,
    )
    notification = _notification_payload(
        row,
        "cancel_pending",
    )
    notification["restored_points"] = restored_points
    result["outbox_id"] = outbox_id
    result["notification_type"] = "cancelled"
    result["notification"] = notification
    if emit_notification:
        deliver_fulfillment_outbox(outbox_id)
    return result


def retry_fulfillment_notification(
    fulfillment_id: int,
    *,
    role: str,
) -> dict:
    fulfillment_id = _require_positive_int(
        fulfillment_id,
        "履约单标识必须是正整数",
    )
    _require_admin_role(role)
    db = _get_db()
    row = _load_fulfillment(db, fulfillment_id)
    if row is None:
        raise AgriNotFoundError("履约单不存在")
    pending_rows = db.execute(
        """
        SELECT id
        FROM fulfillment_notification_outbox
        WHERE fulfillment_id = ? AND status = 'pending'
        ORDER BY id
        """,
        (fulfillment_id,),
    ).fetchall()
    sent = 0
    failed = 0
    for outbox in pending_rows:
        try:
            result = deliver_fulfillment_outbox(int(outbox["id"]))
            sent += int(result["sent"])
        except Exception:
            failed += 1

    restored_points = 0
    if row["status"] == "canceled":
        refund = db.execute(
            """
            SELECT delta
            FROM points_transactions
            WHERE user_id = ?
              AND transaction_type = 'refund'
              AND source_module = 'handcraft'
              AND source_event_id = ?
            """,
            (
                int(row["user_id"]),
                f"fulfillment-cancel:{fulfillment_id}",
            ),
        ).fetchone()
        restored_points = int(refund["delta"]) if refund else 0

    result = _result(
        row,
        changed=False,
        restored_points=restored_points,
    )
    result["outbox"] = {
        "attempted": len(pending_rows),
        "sent": sent,
        "failed": failed,
    }
    return result


def retry_pending_fulfillment_notifications(
    limit: int = 100,
) -> dict:
    limit = _require_positive_int(limit, "重试批量必须是正整数")
    rows = _get_db().execute(
        """
        SELECT id
        FROM fulfillment_notification_outbox
        WHERE status = 'pending'
        ORDER BY created_at, id
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    sent = 0
    failed = 0
    for row in rows:
        try:
            result = deliver_fulfillment_outbox(int(row["id"]))
            sent += int(result["sent"])
        except Exception:
            failed += 1
    return {
        "attempted": len(rows),
        "sent": sent,
        "failed": failed,
    }


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


def _serialize_student_item(row) -> dict:
    return {
        "fulfillment": {
            "id": int(row["id"]),
            "redemption_id": int(row["redemption_id"]),
            "status": str(row["status"]),
            "issued_at": row["issued_at"],
            "verified_at": row["verified_at"],
            "canceled_at": row["canceled_at"],
            "created_at": str(row["created_at"]),
            "updated_at": str(row["updated_at"]),
        },
        "redemption": {
            "id": int(row["redemption_id"]),
            "reward_id": str(row["reward_id"]),
            "reward_name": str(row["reward_name"]),
            "points_cost": int(row["points_cost"]),
            "request_id": str(row["request_id"]),
            "status": str(row["redemption_status"]),
            "created_at": str(row["redemption_created_at"]),
            "updated_at": str(row["redemption_updated_at"]),
        },
        "stock_reservation": {
            "reservation_id": row["reservation_id"],
            "status": row["reservation_status"],
        },
        "status": str(row["status"]),
        "restored_points": int(row["restored_points"] or 0),
    }


def list_student_fulfillments(user_id: int) -> list[dict]:
    user_id = _require_positive_int(user_id, "学员标识必须是正整数")
    rows = _get_db().execute(
        """
        SELECT
            f.id,
            f.redemption_id,
            f.user_id,
            f.status,
            f.issued_at,
            f.verified_at,
            f.canceled_at,
            f.created_at,
            f.updated_at,
            r.reward_id,
            r.reward_name,
            r.points_cost,
            r.request_id,
            r.status AS redemption_status,
            r.created_at AS redemption_created_at,
            r.updated_at AS redemption_updated_at,
            rs.reservation_id,
            rs.status AS reservation_status,
            COALESCE(refund.delta, 0) AS restored_points
        FROM fulfillments f
        JOIN redemptions r ON r.id = f.redemption_id
        LEFT JOIN reward_stock_reservations rs
          ON rs.redemption_id = r.id
        LEFT JOIN points_transactions refund
          ON refund.user_id = f.user_id
         AND refund.transaction_type = 'refund'
         AND refund.source_module = 'handcraft'
         AND refund.source_event_id = (
             'fulfillment-cancel:' || CAST(f.id AS TEXT)
         )
        WHERE f.user_id = ?
        ORDER BY f.created_at DESC, f.id DESC
        """,
        (user_id,),
    ).fetchall()
    return [_serialize_student_item(row) for row in rows]


def _capabilities(role: str) -> dict:
    is_super_admin = role == "super_admin"
    return {
        "view_user_details": True,
        "view_complete_redemption_records": True,
        "view_points_flow": True,
        "issue_fulfillment": True,
        "cancel_pending_fulfillment": True,
        "manual_verify_fulfillment": True,
        "configure_points_rules": is_super_admin,
        "manage_accounts": is_super_admin,
        "manage_rewards": True,
    }


def list_admin_fulfillments(role: str) -> list[dict]:
    role = _require_admin_role(role)
    rows = _get_db().execute(
        """
        SELECT
            f.id,
            f.redemption_id,
            f.user_id,
            f.status,
            f.issued_at,
            f.verified_at,
            f.canceled_at,
            f.created_at,
            f.updated_at,
            r.reward_id,
            r.reward_name,
            r.points_cost,
            r.request_id,
            r.status AS redemption_status,
            r.created_at AS redemption_created_at,
            r.updated_at AS redemption_updated_at,
            rs.reservation_id,
            rs.status AS reservation_status,
            COALESCE(refund.delta, 0) AS restored_points,
            u.username,
            u.name,
            u.role AS user_role,
            COALESCE(sp.contact, '') AS contact
        FROM fulfillments f
        JOIN redemptions r ON r.id = f.redemption_id
        JOIN users u ON u.id = f.user_id
        LEFT JOIN student_profiles sp ON sp.user_id = f.user_id
        LEFT JOIN reward_stock_reservations rs
          ON rs.redemption_id = r.id
        LEFT JOIN points_transactions refund
          ON refund.user_id = f.user_id
         AND refund.transaction_type = 'refund'
         AND refund.source_module = 'handcraft'
         AND refund.source_event_id = (
             'fulfillment-cancel:' || CAST(f.id AS TEXT)
         )
        ORDER BY f.created_at DESC, f.id DESC
        """
    ).fetchall()
    capabilities = _capabilities(role)
    records = []
    for row in rows:
        points_flow = _get_db().execute(
            """
            SELECT *
            FROM points_transactions
            WHERE user_id = ?
              AND source_module = 'handcraft'
              AND source_event_id IN (?, ?)
            ORDER BY created_at, id
            """,
            (
                int(row["user_id"]),
                f"redemption:{row['request_id']}",
                f"fulfillment-cancel:{int(row['id'])}",
            ),
        ).fetchall()
        records.append(
            {
                "user": {
                    "id": int(row["user_id"]),
                    "username": str(row["username"]),
                    "name": str(row["name"]),
                    "role": str(row["user_role"]),
                    "contact": str(row["contact"]),
                },
                "redemption": {
                    "id": int(row["redemption_id"]),
                    "reward_id": str(row["reward_id"]),
                    "reward_name": str(row["reward_name"]),
                    "points_cost": int(row["points_cost"]),
                    "request_id": str(row["request_id"]),
                    "status": str(row["redemption_status"]),
                    "created_at": str(row["redemption_created_at"]),
                    "updated_at": str(row["redemption_updated_at"]),
                },
                "fulfillment": {
                    "id": int(row["id"]),
                    "status": str(row["status"]),
                    "issued_at": row["issued_at"],
                    "verified_at": row["verified_at"],
                    "canceled_at": row["canceled_at"],
                    "created_at": str(row["created_at"]),
                    "updated_at": str(row["updated_at"]),
                },
                "stock_reservation": {
                    "reservation_id": row["reservation_id"],
                    "status": row["reservation_status"],
                },
                "restored_points": int(row["restored_points"] or 0),
                "points_flow": [
                    _serialize_transaction(transaction)
                    for transaction in points_flow
                ],
                "capabilities": dict(capabilities),
            }
        )
    return records
