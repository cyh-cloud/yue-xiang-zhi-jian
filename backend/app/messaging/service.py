from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from app.db import get_db
from app.messaging.relationships import messaging_relationship


class MessageValidationError(ValueError):
    def __init__(self, errors: dict[str, str]) -> None:
        super().__init__("Invalid message")
        self.errors = errors


class MessagingAccessDeniedError(PermissionError):
    pass


class ConversationNotFoundError(LookupError):
    pass


class MessageNotFoundError(LookupError):
    pass


def validate_message_body(body: object) -> str:
    normalized = str(body or "").strip()
    if not normalized:
        raise MessageValidationError({"body": "消息内容不能为空"})
    return normalized


def validate_recipient_id(recipient_id: object) -> int:
    if type(recipient_id) is not int or recipient_id <= 0:
        raise MessageValidationError({"recipient_id": "接收人必须是正整数"})
    return recipient_id


def _ordered_pair(user_a_id: int, user_b_id: int) -> tuple[int, int]:
    low, high = sorted((user_a_id, user_b_id))
    return low, high


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_conversation(
    conversation_id: int,
    viewer_id: int,
) -> sqlite3.Row:
    row = get_db().execute(
        """
        SELECT
            c.id,
            c.participant_low_id,
            c.participant_high_id,
            c.created_at,
            c.updated_at,
            viewer.role AS viewer_role,
            participant.id AS participant_id,
            participant.name AS participant_name,
            participant.role AS participant_role
        FROM message_conversations c
        JOIN users viewer ON viewer.id = ?
        JOIN users participant
          ON participant.id = CASE
              WHEN c.participant_low_id = viewer.id
              THEN c.participant_high_id
              ELSE c.participant_low_id
          END
        WHERE c.id = ?
          AND (
              c.participant_low_id = viewer.id
              OR c.participant_high_id = viewer.id
          )
        """,
        (viewer_id, conversation_id),
    ).fetchone()
    if row is None:
        raise ConversationNotFoundError("Conversation not found")
    return row


def _other_participant_id(conversation, viewer_id: int) -> int:
    low_id = int(conversation["participant_low_id"])
    high_id = int(conversation["participant_high_id"])
    return high_id if viewer_id == low_id else low_id


def _relationship_for_roles(
    viewer_role: str,
    participant_role: str,
) -> str | None:
    roles = {viewer_role, participant_role}
    if roles == {"teacher", "student"}:
        return "teacher_student"
    if roles == {"student", "enterprise"}:
        return "application"
    return None


def _message_payload(row: sqlite3.Row) -> dict:
    return {
        "id": int(row["id"]),
        "conversation_id": int(row["conversation_id"]),
        "sender_id": int(row["sender_id"]),
        "body": str(row["body"]),
        "created_at": str(row["created_at"]),
        "read": row["read_at"] is not None,
    }


def _latest_visible_message(
    conversation_id: int,
    user_id: int,
) -> sqlite3.Row | None:
    return get_db().execute(
        """
        SELECT
            pm.id,
            pm.conversation_id,
            pm.sender_id,
            pm.body,
            pm.created_at,
            pmv.read_at
        FROM private_messages pm
        JOIN private_message_views pmv
          ON pmv.message_id = pm.id
         AND pmv.user_id = ?
         AND pmv.cleared_at IS NULL
        WHERE pm.conversation_id = ?
        ORDER BY pm.created_at DESC, pm.id DESC
        LIMIT 1
        """,
        (user_id, conversation_id),
    ).fetchone()


def _conversation_payload(conversation_id: int, viewer_id: int) -> dict:
    conversation = _load_conversation(conversation_id, viewer_id)
    latest_message = _latest_visible_message(conversation_id, viewer_id)
    unread_count = get_db().execute(
        """
        SELECT COUNT(*) AS count
        FROM private_messages pm
        JOIN private_message_views pmv ON pmv.message_id = pm.id
        WHERE pm.conversation_id = ?
          AND pmv.user_id = ?
          AND pmv.read_at IS NULL
          AND pmv.cleared_at IS NULL
        """,
        (conversation_id, viewer_id),
    ).fetchone()["count"]
    return {
        "id": int(conversation["id"]),
        "participant": {
            "id": int(conversation["participant_id"]),
            "name": str(conversation["participant_name"]),
            "role": str(conversation["participant_role"]),
            "relationship": _relationship_for_roles(
                str(conversation["viewer_role"]),
                str(conversation["participant_role"]),
            ),
        },
        "last_message": (
            _message_payload(latest_message)
            if latest_message is not None
            else None
        ),
        "unread_count": int(unread_count),
        "updated_at": str(conversation["updated_at"]),
    }


def _insert_message(
    conversation_id: int,
    sender_id: int,
    recipient_id: int,
    body: str,
    created_at: str,
) -> dict:
    db = get_db()
    cursor = db.execute(
        """
        INSERT INTO private_messages (
            conversation_id, sender_id, body, created_at
        )
        VALUES (?, ?, ?, ?)
        """,
        (conversation_id, sender_id, body, created_at),
    )
    message_id = int(cursor.lastrowid)
    db.executemany(
        """
        INSERT INTO private_message_views (
            message_id, user_id, read_at, cleared_at
        )
        VALUES (?, ?, ?, NULL)
        """,
        (
            (message_id, sender_id, created_at),
            (message_id, recipient_id, None),
        ),
    )
    db.execute(
        """
        UPDATE message_conversations
        SET updated_at = ?
        WHERE id = ?
        """,
        (created_at, conversation_id),
    )
    row = db.execute(
        """
        SELECT
            pm.id,
            pm.conversation_id,
            pm.sender_id,
            pm.body,
            pm.created_at,
            pmv.read_at
        FROM private_messages pm
        JOIN private_message_views pmv
          ON pmv.message_id = pm.id
         AND pmv.user_id = ?
        WHERE pm.id = ?
        """,
        (sender_id, message_id),
    ).fetchone()
    return _message_payload(row)


def send_private_message(
    sender_id: int,
    recipient_id: int,
    body: object,
) -> dict:
    normalized_body = validate_message_body(body)
    recipient_id = validate_recipient_id(recipient_id)
    if messaging_relationship(sender_id, recipient_id) is None:
        raise MessagingAccessDeniedError(
            "Current relationship does not allow private messaging"
        )

    low_id, high_id = _ordered_pair(sender_id, recipient_id)
    created_at = _utc_now_iso()
    db = get_db()

    with db:
        db.execute(
            """
            INSERT INTO message_conversations (
                participant_low_id, participant_high_id, created_at, updated_at
            )
            VALUES (?, ?, ?, ?)
            ON CONFLICT (participant_low_id, participant_high_id) DO NOTHING
            """,
            (low_id, high_id, created_at, created_at),
        )
        conversation = db.execute(
            """
            SELECT id
            FROM message_conversations
            WHERE participant_low_id = ?
              AND participant_high_id = ?
            """,
            (low_id, high_id),
        ).fetchone()
        if conversation is None:
            raise RuntimeError("Failed to create or select conversation")
        conversation_id = int(conversation["id"])

        message = _insert_message(
            conversation_id,
            sender_id,
            recipient_id,
            normalized_body,
            created_at,
        )

    return {
        "conversation": _conversation_payload(conversation_id, sender_id),
        "message": message,
    }


def reply_to_conversation(
    sender_id: int,
    conversation_id: int,
    body: object,
) -> dict:
    db = get_db()
    conversation = _load_conversation(conversation_id, sender_id)
    normalized_body = validate_message_body(body)
    recipient_id = _other_participant_id(conversation, sender_id)
    created_at = _utc_now_iso()

    with db:
        message = _insert_message(
            conversation_id,
            sender_id,
            recipient_id,
            normalized_body,
            created_at,
        )

    return {
        "conversation": _conversation_payload(conversation_id, sender_id),
        "message": message,
    }


def list_conversations(user_id: int) -> list[dict]:
    rows = get_db().execute(
        """
        SELECT c.id
        FROM message_conversations c
        WHERE (
            c.participant_low_id = ?
            OR c.participant_high_id = ?
        )
          AND EXISTS (
              SELECT 1
              FROM private_messages pm
              JOIN private_message_views pmv ON pmv.message_id = pm.id
              WHERE pm.conversation_id = c.id
                AND pmv.user_id = ?
                AND pmv.cleared_at IS NULL
          )
        ORDER BY c.updated_at DESC, c.id DESC
        """,
        (user_id, user_id, user_id),
    ).fetchall()
    return [
        _conversation_payload(int(row["id"]), user_id)
        for row in rows
    ]


def get_conversation_messages(
    user_id: int,
    conversation_id: int,
) -> dict:
    _load_conversation(conversation_id, user_id)
    rows = get_db().execute(
        """
        SELECT
            pm.id,
            pm.conversation_id,
            pm.sender_id,
            pm.body,
            pm.created_at,
            pmv.read_at
        FROM private_messages pm
        JOIN private_message_views pmv
          ON pmv.message_id = pm.id
         AND pmv.user_id = ?
         AND pmv.cleared_at IS NULL
        WHERE pm.conversation_id = ?
        ORDER BY pm.created_at ASC, pm.id ASC
        """,
        (user_id, conversation_id),
    ).fetchall()
    return {
        "conversation": _conversation_payload(conversation_id, user_id),
        "messages": [_message_payload(row) for row in rows],
    }


def get_message_summary(user_id: int) -> dict:
    db = get_db()
    unread_private = db.execute(
        """
        SELECT COUNT(*) AS count
        FROM private_message_views
        WHERE user_id = ? AND read_at IS NULL AND cleared_at IS NULL
        """,
        (user_id,),
    ).fetchone()["count"]
    unread_notifications = db.execute(
        """
        SELECT COUNT(*) AS count
        FROM system_notifications
        WHERE recipient_id = ? AND read_at IS NULL AND cleared_at IS NULL
        """,
        (user_id,),
    ).fetchone()["count"]
    return {
        "unread_private": int(unread_private),
        "unread_notifications": int(unread_notifications),
        "unread_total": int(unread_private) + int(unread_notifications),
    }


def mark_private_message_read(user_id: int, message_id: int) -> dict:
    db = get_db()
    view = db.execute(
        """
        SELECT read_at, cleared_at
        FROM private_message_views
        WHERE message_id = ? AND user_id = ?
        """,
        (message_id, user_id),
    ).fetchone()
    if view is None or view["cleared_at"] is not None:
        raise MessageNotFoundError("Message not found")

    if view["read_at"] is None:
        with db:
            db.execute(
                """
                UPDATE private_message_views
                SET read_at = ?
                WHERE message_id = ?
                  AND user_id = ?
                  AND read_at IS NULL
                  AND cleared_at IS NULL
                """,
                (_utc_now_iso(), message_id, user_id),
            )
    return get_message_summary(user_id)


def mark_notification_read(user_id: int, notification_id: int) -> dict:
    db = get_db()
    notification = db.execute(
        """
        SELECT read_at, cleared_at
        FROM system_notifications
        WHERE id = ? AND recipient_id = ?
        """,
        (notification_id, user_id),
    ).fetchone()
    if notification is None or notification["cleared_at"] is not None:
        raise MessageNotFoundError("Notification not found")

    if notification["read_at"] is None:
        with db:
            db.execute(
                """
                UPDATE system_notifications
                SET read_at = ?
                WHERE id = ?
                  AND recipient_id = ?
                  AND read_at IS NULL
                  AND cleared_at IS NULL
                """,
                (_utc_now_iso(), notification_id, user_id),
            )
    return get_message_summary(user_id)


def mark_all_read(user_id: int) -> dict:
    db = get_db()
    read_at = _utc_now_iso()
    with db:
        db.execute(
            """
            UPDATE private_message_views
            SET read_at = ?
            WHERE user_id = ?
              AND read_at IS NULL
              AND cleared_at IS NULL
            """,
            (read_at, user_id),
        )
        db.execute(
            """
            UPDATE system_notifications
            SET read_at = ?
            WHERE recipient_id = ?
              AND read_at IS NULL
              AND cleared_at IS NULL
            """,
            (read_at, user_id),
        )
    return get_message_summary(user_id)


def clear_read_items(user_id: int) -> dict:
    db = get_db()
    cleared_at = _utc_now_iso()
    with db:
        private_result = db.execute(
            """
            UPDATE private_message_views
            SET cleared_at = ?
            WHERE user_id = ?
              AND read_at IS NOT NULL
              AND cleared_at IS NULL
            """,
            (cleared_at, user_id),
        )
        notification_result = db.execute(
            """
            UPDATE system_notifications
            SET cleared_at = ?
            WHERE recipient_id = ?
              AND read_at IS NOT NULL
              AND cleared_at IS NULL
            """,
            (cleared_at, user_id),
        )
    return {
        "cleared_private": int(private_result.rowcount),
        "cleared_notifications": int(notification_result.rowcount),
        "unread_total": get_message_summary(user_id)["unread_total"],
    }
