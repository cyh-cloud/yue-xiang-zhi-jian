import sqlite3
import tempfile
import unittest
from pathlib import Path

from app import create_app
from app.db import get_db


class TestMessagingFoundation(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(Path(self.temp_dir.name) / "test.db"),
                "SECRET_KEY": "test-only-secret",
            }
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_messaging_tables_and_indexes_exist(self):
        with self.app.app_context():
            db = get_db()
            tables = {
                row["name"]
                for row in db.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
            indexes = {
                row["name"]
                for row in db.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'index'"
                )
            }
        self.assertTrue(
            {
                "message_conversations",
                "private_messages",
                "private_message_views",
                "system_notifications",
            }.issubset(tables)
        )
        self.assertTrue(
            {
                "idx_private_messages_conversation",
                "idx_private_views_unread",
                "idx_notifications_unread",
            }.issubset(indexes)
        )

    def test_conversation_requires_ordered_unique_pair(self):
        now = "2026-09-15T00:00:00+00:00"
        with self.app.app_context():
            db = get_db()
            db.executemany(
                """
                INSERT INTO users (
                    username, password_hash, name, role, is_enabled,
                    created_at, updated_at
                )
                VALUES (?, 'hash', ?, 'student', 1, ?, ?)
                """,
                [("s1", "学员一", now, now), ("s2", "学员二", now, now)],
            )
            db.execute(
                """
                INSERT INTO message_conversations (
                    participant_low_id, participant_high_id, created_at, updated_at
                )
                VALUES (1, 2, ?, ?)
                """,
                (now, now),
            )
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute(
                    """
                    INSERT INTO message_conversations (
                        participant_low_id, participant_high_id, created_at, updated_at
                    )
                    VALUES (2, 1, ?, ?)
                    """,
                    (now, now),
                )


if __name__ == "__main__":
    unittest.main()
