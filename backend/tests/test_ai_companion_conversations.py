import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from app import create_app
from app.ai_companion.repository import (
    create_or_append_exchange,
    get_conversation,
    list_conversations,
)
from app.db import get_db


class AiCompanionConversationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(Path(self.temp_dir.name) / "test.db"),
                "SECRET_KEY": "test-only-secret",
            }
        )
        self.user_id = self._insert_user("student-self", "student")

    def tearDown(self):
        self.temp_dir.cleanup()

    def _insert_user(self, username, role):
        timestamp = "2026-09-21T10:00:00+08:00"
        with self.app.app_context():
            db = get_db()
            cursor = db.execute(
                """
                INSERT INTO users (
                    username,
                    password_hash,
                    name,
                    role,
                    is_enabled,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, 1, ?, ?)
                """,
                (
                    username,
                    "test-password-hash",
                    username,
                    role,
                    timestamp,
                    timestamp,
                ),
            )
            db.commit()
            return int(cursor.lastrowid)

    def test_only_owner_can_list_and_read_conversation(self):
        first = self._insert_user("student01", "student")
        second = self._insert_user("student02", "student")
        with self.app.app_context():
            created = create_or_append_exchange(
                user_id=first,
                question="怎么投简历",
                answer="进入就业对接投递。",
                intent="platform_usage",
                jump_target="/student/employment/jobs",
                client_request_id="request-1",
            )
            self.assertEqual(len(list_conversations(first)), 1)
            self.assertEqual(list_conversations(second), [])
            self.assertIsNone(
                get_conversation(second, created["conversation_id"])
            )

    def test_retry_with_same_request_id_returns_original_exchange(self):
        with self.app.app_context():
            first = create_or_append_exchange(
                user_id=self.user_id,
                question="怎么投简历",
                answer="进入就业对接投递。",
                intent="platform_usage",
                jump_target="/student/employment/jobs",
                client_request_id="same-request",
            )
            second = create_or_append_exchange(
                user_id=self.user_id,
                question="怎么投简历",
                answer="进入就业对接投递。",
                intent="platform_usage",
                jump_target="/student/employment/jobs",
                client_request_id="same-request",
            )
            self.assertEqual(
                first["conversation_id"],
                second["conversation_id"],
            )
            self.assertEqual(
                first["user_message"]["message_id"],
                second["user_message"]["message_id"],
            )

    def test_same_request_id_is_scoped_per_user(self):
        first = self._insert_user("student01", "student")
        second = self._insert_user("student02", "student")
        with self.app.app_context():
            first_result = create_or_append_exchange(
                user_id=first,
                question="问题一",
                answer="回答一",
                intent="learning_question",
                jump_target=None,
                client_request_id="shared-request-id",
            )
            second_result = create_or_append_exchange(
                user_id=second,
                question="问题二",
                answer="回答二",
                intent="learning_question",
                jump_target=None,
                client_request_id="shared-request-id",
            )
            self.assertNotEqual(
                first_result["conversation_id"],
                second_result["conversation_id"],
            )

    def test_retention_drops_oldest_conversation_and_messages(self):
        base = datetime(2026, 4, 1, tzinfo=timezone(timedelta(hours=8)))
        timestamps = [
            (base + timedelta(minutes=index)).isoformat()
            for index in range(101)
        ]
        with patch(
            "app.ai_companion.repository._now",
            side_effect=timestamps[:101],
        ):
            with self.app.app_context():
                for index in range(101):
                    create_or_append_exchange(
                        user_id=self.user_id,
                        question=f"问题 {index}",
                        answer=f"回答 {index}",
                        intent="learning_question",
                        jump_target=None,
                        client_request_id=f"request-{index}",
                    )
                conversations = list_conversations(self.user_id)
            self.assertEqual(len(conversations), 100)
            self.assertNotIn(
                "问题 0",
                {item["title"] for item in conversations},
            )

    def test_conversation_is_limited_to_two_hundred_messages(self):
        with self.app.app_context():
            created = create_or_append_exchange(
                user_id=self.user_id,
                question="问题 0",
                answer="回答 0",
                intent="learning_question",
                jump_target=None,
                client_request_id="request-0",
            )
            conversation_id = created["conversation_id"]
            for index in range(1, 101):
                create_or_append_exchange(
                    user_id=self.user_id,
                    question=f"问题 {index}",
                    answer=f"回答 {index}",
                    intent="learning_question",
                    jump_target=None,
                    client_request_id=f"request-{index}",
                    conversation_id=conversation_id,
                )
            detail = get_conversation(self.user_id, conversation_id)
            self.assertEqual(len(detail["messages"]), 200)
            self.assertEqual(detail["messages"][0]["content"], "问题 1")


if __name__ == "__main__":
    unittest.main()
