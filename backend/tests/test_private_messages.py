import tempfile
import unittest
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from unittest.mock import patch

from app import create_app
from app.db import get_db
from app.messaging.service import (
    ConversationNotFoundError,
    MessageValidationError,
    MessagingAccessDeniedError,
    get_conversation_messages,
    list_conversations,
    reply_to_conversation,
    send_private_message,
    validate_message_body,
)
from app.messaging.source_provider import (
    NullMessagingSourceProvider,
    set_messaging_source_provider,
)


class FakeMessagingSourceProvider(NullMessagingSourceProvider):
    def __init__(self):
        self.applications: set[tuple[int, int]] = set()

    def has_application_relationship(
        self, student_id: int, enterprise_id: int
    ) -> bool:
        return (student_id, enterprise_id) in self.applications


class ConversationLookupBarrier:
    def __init__(
        self,
        connection,
        barrier: Barrier,
    ) -> None:
        self.connection = connection
        self.barrier = barrier
        self.lookup_released = False
        self.insert_seen = False

    def execute(self, sql: str, parameters=()):
        if sql.lstrip().upper().startswith("INSERT"):
            self.insert_seen = True
        if (
            "FROM message_conversations" in sql
            and "participant_low_id = ?" in sql
            and not self.lookup_released
            and not self.insert_seen
        ):
            self.lookup_released = True
            self.barrier.wait()
        return self.connection.execute(sql, parameters)

    def __enter__(self):
        self.connection.__enter__()
        return self

    def __exit__(self, *args):
        return self.connection.__exit__(*args)

    def __getattr__(self, name):
        return getattr(self.connection, name)


class TestPrivateMessages(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(Path(self.temp_dir.name) / "test.db"),
                "SECRET_KEY": "test-only-secret",
            }
        )

        self.teacher_id = self.create_user("teacher", "教师甲", "teacher")
        self.other_teacher_id = self.create_user(
            "teacher-other",
            "教师乙",
            "teacher",
        )
        self.student_id = self.create_user("student", "学员甲", "student")
        self.student_a_id = self.create_user("student-a", "学员乙", "student")
        self.student_b_id = self.create_user("student-b", "学员丙", "student")
        self.enterprise_id = self.create_user(
            "enterprise",
            "企业甲",
            "enterprise",
        )

        self.source_provider = FakeMessagingSourceProvider()
        set_messaging_source_provider(self.app, self.source_provider)

    def tearDown(self):
        self.temp_dir.cleanup()

    def create_user(self, username: str, name: str, role: str) -> int:
        now = datetime.now(timezone.utc).isoformat()
        with self.app.app_context():
            cursor = get_db().execute(
                """
                INSERT INTO users (
                    username, password_hash, name, role, is_enabled,
                    created_at, updated_at
                )
                VALUES (?, 'hash', ?, ?, 1, ?, ?)
                """,
                (username, name, role, now, now),
            )
            get_db().commit()
        return int(cursor.lastrowid)

    def test_message_body_is_trimmed_and_whitespace_is_rejected(self):
        self.assertEqual(validate_message_body("  内容  "), "内容")

        with self.assertRaises(MessageValidationError) as error:
            validate_message_body(" \n\t ")
        self.assertEqual(
            error.exception.errors,
            {"body": "消息内容不能为空"},
        )

    def test_prohibited_message_creates_no_rows(self):
        with self.app.app_context():
            with self.assertRaises(MessagingAccessDeniedError):
                send_private_message(
                    self.student_a_id,
                    self.student_b_id,
                    "不允许",
                )

        with self.app.app_context():
            self.assertEqual(
                get_db().execute(
                    "SELECT COUNT(*) AS count FROM message_conversations"
                ).fetchone()["count"],
                0,
            )
            self.assertEqual(
                get_db().execute(
                    "SELECT COUNT(*) AS count FROM private_messages"
                ).fetchone()["count"],
                0,
            )

    def test_repeated_send_reuses_one_conversation(self):
        with self.app.app_context():
            first = send_private_message(
                self.teacher_id,
                self.student_id,
                "第一条",
            )
            second = send_private_message(
                self.teacher_id,
                self.student_id,
                "第二条",
            )
            thread = get_conversation_messages(
                self.student_id,
                first["conversation"]["id"],
            )

        self.assertEqual(
            first["conversation"]["id"],
            second["conversation"]["id"],
        )
        self.assertEqual(
            [item["body"] for item in thread["messages"]],
            ["第一条", "第二条"],
        )

    def test_concurrent_first_messages_reuse_one_conversation(self):
        lookup_barrier = Barrier(2, timeout=5)

        def send(sender_id: int, recipient_id: int, body: str) -> dict:
            with self.app.app_context():
                return send_private_message(
                    sender_id,
                    recipient_id,
                    body,
                )

        with patch(
            "app.messaging.service.get_db",
            side_effect=lambda: ConversationLookupBarrier(
                get_db(),
                lookup_barrier,
            ),
        ):
            with ThreadPoolExecutor(max_workers=2) as executor:
                teacher_send = executor.submit(
                    send,
                    self.teacher_id,
                    self.student_id,
                    "老师同时发起",
                )
                student_send = executor.submit(
                    send,
                    self.student_id,
                    self.teacher_id,
                    "学员同时发起",
                )
                results = [teacher_send.result(), student_send.result()]

        conversation_ids = {
            result["conversation"]["id"] for result in results
        }
        self.assertEqual(len(conversation_ids), 1)
        conversation_id = next(iter(conversation_ids))

        with self.app.app_context():
            counts = get_db().execute(
                """
                SELECT
                    (SELECT COUNT(*) FROM message_conversations) AS conversations,
                    (SELECT COUNT(*) FROM private_messages) AS messages
                """
            ).fetchone()
            thread = get_conversation_messages(
                self.teacher_id,
                conversation_id,
            )

        self.assertEqual(int(counts["conversations"]), 1)
        self.assertEqual(int(counts["messages"]), 2)
        self.assertEqual(
            {item["body"] for item in thread["messages"]},
            {"老师同时发起", "学员同时发起"},
        )

    def test_thread_order_and_read_state_are_per_user(self):
        with self.app.app_context():
            first = send_private_message(
                self.teacher_id,
                self.student_id,
                " 第一条 ",
            )
            second = send_private_message(
                self.teacher_id,
                self.student_id,
                "第二条",
            )
            student_thread = get_conversation_messages(
                self.student_id,
                first["conversation"]["id"],
            )
            teacher_thread = get_conversation_messages(
                self.teacher_id,
                first["conversation"]["id"],
            )
            views = get_db().execute(
                """
                SELECT message_id, user_id, read_at
                FROM private_message_views
                WHERE message_id IN (?, ?)
                ORDER BY message_id, user_id
                """,
                (first["message"]["id"], second["message"]["id"]),
            ).fetchall()

        self.assertEqual(
            [item["id"] for item in student_thread["messages"]],
            [first["message"]["id"], second["message"]["id"]],
        )
        self.assertEqual(
            [item["body"] for item in student_thread["messages"]],
            ["第一条", "第二条"],
        )
        self.assertEqual(
            [item["read"] for item in student_thread["messages"]],
            [False, False],
        )
        self.assertEqual(
            [item["read"] for item in teacher_thread["messages"]],
            [True, True],
        )
        self.assertEqual(
            student_thread["conversation"]["participant"]["id"],
            self.teacher_id,
        )
        self.assertEqual(
            {
                int(row["user_id"]): row["read_at"]
                for row in views
                if int(row["message_id"]) == int(first["message"]["id"])
            },
            {
                self.teacher_id: first["message"]["created_at"],
                self.student_id: None,
            },
        )

    def test_enterprise_can_start_and_student_can_reply(self):
        self.source_provider.applications.add(
            (self.student_id, self.enterprise_id)
        )

        with self.app.app_context():
            sent = send_private_message(
                self.enterprise_id,
                self.student_id,
                "申请沟通",
            )
            reply = reply_to_conversation(
                self.student_id,
                sent["conversation"]["id"],
                "收到",
            )
            thread = get_conversation_messages(
                self.enterprise_id,
                sent["conversation"]["id"],
            )

        self.assertEqual(
            [item["body"] for item in thread["messages"]],
            ["申请沟通", "收到"],
        )
        self.assertEqual(
            reply["conversation"]["id"],
            sent["conversation"]["id"],
        )
        self.assertEqual(
            thread["conversation"]["participant"]["relationship"],
            "application",
        )

    def test_existing_thread_reply_survives_relationship_removal(self):
        self.source_provider.applications.add(
            (self.student_id, self.enterprise_id)
        )

        with self.app.app_context():
            sent = send_private_message(
                self.student_id,
                self.enterprise_id,
                "投递沟通",
            )

        self.source_provider.applications.clear()

        with self.app.app_context():
            reply = reply_to_conversation(
                self.enterprise_id,
                sent["conversation"]["id"],
                "关系关闭后仍可回复",
            )
            with self.assertRaises(MessagingAccessDeniedError):
                send_private_message(
                    self.enterprise_id,
                    self.student_a_id,
                    "关系关闭后不能新建会话",
                )
            thread = get_conversation_messages(
                self.student_id,
                sent["conversation"]["id"],
            )

        self.assertEqual(reply["message"]["body"], "关系关闭后仍可回复")
        self.assertEqual(
            [item["body"] for item in thread["messages"]],
            ["投递沟通", "关系关闭后仍可回复"],
        )
        with self.app.app_context():
            self.assertEqual(
                get_db().execute(
                    "SELECT COUNT(*) AS count FROM message_conversations"
                ).fetchone()["count"],
                1,
            )

    def test_non_participant_cannot_view_or_reply(self):
        with self.app.app_context():
            sent = send_private_message(
                self.teacher_id,
                self.student_id,
                "仅限会话双方",
            )
            conversation_id = sent["conversation"]["id"]

            with self.assertRaises(ConversationNotFoundError):
                get_conversation_messages(
                    self.other_teacher_id,
                    conversation_id,
                )
            with self.assertRaises(ConversationNotFoundError):
                reply_to_conversation(
                    self.other_teacher_id,
                    conversation_id,
                    "越权回复",
                )

    def test_list_conversations_returns_latest_visible_message_and_unread_count(self):
        self.source_provider.applications.add(
            (self.student_id, self.enterprise_id)
        )

        with self.app.app_context():
            first = send_private_message(
                self.teacher_id,
                self.student_id,
                "老师第一条",
            )
            send_private_message(
                self.teacher_id,
                self.student_id,
                "老师第二条",
            )
            second = send_private_message(
                self.enterprise_id,
                self.student_id,
                "企业消息",
            )
            conversations = list_conversations(self.student_id)

        self.assertEqual(
            [item["id"] for item in conversations],
            [
                second["conversation"]["id"],
                first["conversation"]["id"],
            ],
        )
        self.assertEqual(
            [item["last_message"]["body"] for item in conversations],
            ["企业消息", "老师第二条"],
        )
        self.assertEqual(
            [item["unread_count"] for item in conversations],
            [1, 2],
        )
        self.assertEqual(
            conversations[0]["participant"]["id"],
            self.enterprise_id,
        )


if __name__ == "__main__":
    unittest.main()
