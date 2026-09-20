from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.ai_companion.constants import (
    CONVERSATION_RETENTION_DAYS,
    MAX_CONVERSATIONS,
    MAX_MESSAGES_PER_CONVERSATION,
)
from app.ai_companion.errors import (
    AiCompanionNotFoundError,
    AiCompanionValidationError,
)
from app.db import get_db


SHANGHAI_ZONE = ZoneInfo("Asia/Shanghai")
MAX_TITLE_LENGTH = 80
CONVERSATION_NOT_FOUND_MESSAGE = "会话不存在"
CLIENT_REQUEST_ID_REQUIRED_MESSAGE = "客户端请求标识不能为空"


def _now() -> str:
    # 保留微秒：同一次交换的两条消息共用该时间戳，需要与相邻交换区分开。
    return datetime.now(SHANGHAI_ZONE).isoformat()


def _build_title(question: str) -> str:
    return question.strip()[:MAX_TITLE_LENGTH]


def _conversation_record(row) -> dict:
    return {
        "conversation_id": row["conversation_id"],
        "title": row["title"],
        "last_intent": row["last_intent"],
        "jump_target": row["jump_target"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _message_record(row) -> dict:
    return {
        "message_id": row["message_id"],
        "role": row["role"],
        "content": row["content"],
        "intent": row["intent"],
        "jump_target": row["jump_target"],
        "created_at": row["created_at"],
    }


def _find_owned_conversation_id(db, conversation_id: str, user_id: int) -> str | None:
    row = db.execute(
        """
        SELECT conversation_id
        FROM ai_companion_conversations
        WHERE conversation_id = ? AND user_id = ?
        """,
        (conversation_id, user_id),
    ).fetchone()
    return None if row is None else row["conversation_id"]


def _insert_conversation(
    db,
    user_id: int,
    question: str,
    intent: str,
    jump_target: str | None,
    timestamp: str,
) -> str:
    conversation_id = uuid4().hex
    db.execute(
        """
        INSERT INTO ai_companion_conversations (
            conversation_id,
            user_id,
            title,
            last_intent,
            jump_target,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            conversation_id,
            user_id,
            _build_title(question),
            intent,
            jump_target,
            timestamp,
            timestamp,
        ),
    )
    return conversation_id


def _insert_message(
    db,
    conversation_id: str,
    user_id: int,
    role: str,
    content: str,
    intent: str,
    jump_target: str | None,
    client_request_id: str | None,
    timestamp: str,
) -> str:
    message_id = uuid4().hex
    db.execute(
        """
        INSERT INTO ai_companion_messages (
            message_id,
            conversation_id,
            user_id,
            role,
            content,
            intent,
            jump_target,
            client_request_id,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            message_id,
            conversation_id,
            user_id,
            role,
            content,
            intent,
            jump_target,
            client_request_id,
            timestamp,
        ),
    )
    return message_id


def _prune_conversation_messages(db, conversation_id: str) -> None:
    db.execute(
        """
        DELETE FROM ai_companion_messages
        WHERE conversation_id = ?
          AND rowid NOT IN (
              SELECT rowid
              FROM ai_companion_messages
              WHERE conversation_id = ?
              ORDER BY rowid DESC
              LIMIT ?
          )
        """,
        (conversation_id, conversation_id, MAX_MESSAGES_PER_CONVERSATION),
    )


def _prune_user_conversations(db, user_id: int, timestamp: str) -> None:
    cutoff = (
        datetime.fromisoformat(timestamp)
        - timedelta(days=CONVERSATION_RETENTION_DAYS)
    ).isoformat()
    db.execute(
        """
        DELETE FROM ai_companion_conversations
        WHERE user_id = ?
          AND updated_at < ?
        """,
        (user_id, cutoff),
    )
    db.execute(
        """
        DELETE FROM ai_companion_conversations
        WHERE user_id = ?
          AND conversation_id NOT IN (
              SELECT conversation_id
              FROM ai_companion_conversations
              WHERE user_id = ?
              ORDER BY updated_at DESC, conversation_id DESC
              LIMIT ?
          )
        """,
        (user_id, user_id, MAX_CONVERSATIONS),
    )


def create_or_append_exchange(
    user_id: int,
    question: str,
    answer: str,
    intent: str,
    jump_target: str | None,
    client_request_id: str,
    conversation_id: str | None = None,
) -> dict:
    if not client_request_id or not client_request_id.strip():
        raise AiCompanionValidationError(CLIENT_REQUEST_ID_REQUIRED_MESSAGE)

    replayed = find_exchange_by_request(user_id, client_request_id)
    if replayed is not None:
        return replayed

    # 每次创建只取一次时间戳，两条消息与会话更新共用，保证留存判定确定。
    timestamp = _now()

    # try 包在 with 外层：with 的 __exit__ 先回滚，重复提交被唯一索引拒掉时
    # 不会留下没有消息的孤儿会话；此时按既有记录重放。
    try:
        with get_db() as db:
            if conversation_id is None:
                conversation_id = _insert_conversation(
                    db,
                    user_id=user_id,
                    question=question,
                    intent=intent,
                    jump_target=jump_target,
                    timestamp=timestamp,
                )
            elif _find_owned_conversation_id(db, conversation_id, user_id) is None:
                raise AiCompanionNotFoundError(CONVERSATION_NOT_FOUND_MESSAGE)

            user_message_id = _insert_message(
                db,
                conversation_id=conversation_id,
                user_id=user_id,
                role="user",
                content=question,
                intent=intent,
                jump_target=jump_target,
                client_request_id=client_request_id,
                timestamp=timestamp,
            )
            assistant_message_id = _insert_message(
                db,
                conversation_id=conversation_id,
                user_id=user_id,
                role="assistant",
                content=answer,
                intent=intent,
                jump_target=jump_target,
                client_request_id=None,
                timestamp=timestamp,
            )
            db.execute(
                """
                UPDATE ai_companion_conversations
                SET last_intent = ?, jump_target = ?, updated_at = ?
                WHERE conversation_id = ?
                """,
                (intent, jump_target, timestamp, conversation_id),
            )
            _prune_conversation_messages(db, conversation_id)
            _prune_user_conversations(db, user_id, timestamp)
    except sqlite3.IntegrityError:
        replayed = find_exchange_by_request(user_id, client_request_id)
        if replayed is None:
            raise
        return replayed

    return {
        "conversation_id": conversation_id,
        "user_message": _message_record(
            {
                "message_id": user_message_id,
                "role": "user",
                "content": question,
                "intent": intent,
                "jump_target": jump_target,
                "created_at": timestamp,
            }
        ),
        "assistant_message": _message_record(
            {
                "message_id": assistant_message_id,
                "role": "assistant",
                "content": answer,
                "intent": intent,
                "jump_target": jump_target,
                "created_at": timestamp,
            }
        ),
    }


def list_conversations(user_id: int) -> list[dict]:
    db = get_db()
    rows = db.execute(
        """
        SELECT conversation_id, title, last_intent, jump_target,
               created_at, updated_at
        FROM ai_companion_conversations
        WHERE user_id = ?
        ORDER BY updated_at DESC, conversation_id DESC
        """,
        (user_id,),
    ).fetchall()
    return [_conversation_record(row) for row in rows]


def get_conversation(user_id: int, conversation_id: str) -> dict | None:
    db = get_db()
    row = db.execute(
        """
        SELECT conversation_id, title, last_intent, jump_target,
               created_at, updated_at
        FROM ai_companion_conversations
        WHERE conversation_id = ? AND user_id = ?
        """,
        (conversation_id, user_id),
    ).fetchone()
    if row is None:
        return None
    messages = db.execute(
        """
        SELECT message_id, role, content, intent, jump_target, created_at
        FROM ai_companion_messages
        WHERE conversation_id = ? AND user_id = ?
        ORDER BY rowid
        """,
        (conversation_id, user_id),
    ).fetchall()
    record = _conversation_record(row)
    # rowid 即写入顺序：同一次交换的两条消息时间戳相同，不能只用 created_at 排序。
    record["messages"] = [_message_record(message) for message in messages]
    return record


def find_exchange_by_request(user_id: int, client_request_id: str) -> dict | None:
    if not client_request_id:
        return None
    db = get_db()
    user_row = db.execute(
        """
        SELECT rowid, message_id, conversation_id, role, content, intent,
               jump_target, created_at
        FROM ai_companion_messages
        WHERE user_id = ? AND client_request_id = ? AND role = 'user'
        """,
        (user_id, client_request_id),
    ).fetchone()
    if user_row is None:
        return None
    assistant_row = db.execute(
        """
        SELECT message_id, role, content, intent, jump_target, created_at
        FROM ai_companion_messages
        WHERE conversation_id = ?
          AND role = 'assistant'
          AND rowid > ?
        ORDER BY rowid
        LIMIT 1
        """,
        (user_row["conversation_id"], user_row["rowid"]),
    ).fetchone()
    return {
        "conversation_id": user_row["conversation_id"],
        "user_message": _message_record(user_row),
        "assistant_message": (
            None if assistant_row is None else _message_record(assistant_row)
        ),
    }
