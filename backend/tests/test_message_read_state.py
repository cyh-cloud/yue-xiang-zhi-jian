import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from app import create_app
from app.db import get_db
from app.messaging.service import (
    MessageNotFoundError,
    clear_read_items,
    get_conversation_messages,
    get_message_summary,
    list_conversations,
    mark_all_read,
    mark_notification_read,
    mark_private_message_read,
    send_private_message,
)


class TestMessageReadState(unittest.TestCase):
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
        self.student_id = self.create_user("student", "学员甲", "student")
        self.other_student_id = self.create_user(
            "student-other",
            "学员乙",
            "student",
        )

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

    def test_sending_only_increments_recipient_unread(self):
        with self.app.app_context():
            send_private_message(self.teacher_id, self.student_id, "请查看")
            teacher_summary = get_message_summary(self.teacher_id)
            student_summary = get_message_summary(self.student_id)

        self.assertEqual(teacher_summary["unread_total"], 0)
        self.assertEqual(student_summary["unread_private"], 1)
        self.assertEqual(student_summary["unread_total"], 1)

    def test_single_read_changes_only_one_item_and_persists_across_contexts(self):
        with self.app.app_context():
            sent = send_private_message(
                self.teacher_id,
                self.student_id,
                "请查看",
            )
            summary = mark_private_message_read(
                self.student_id,
                sent["message"]["id"],
            )

        with self.app.app_context():
            persisted = get_message_summary(self.student_id)

        self.assertEqual(summary["unread_private"], 0)
        self.assertEqual(summary["unread_total"], 0)
        self.assertEqual(persisted, summary)

    def test_clear_read_keeps_unread_and_hides_only_current_account(self):
        with self.app.app_context():
            read = send_private_message(
                self.teacher_id,
                self.student_id,
                "已读",
            )
            unread = send_private_message(
                self.teacher_id,
                self.student_id,
                "未读",
            )
            mark_private_message_read(
                self.student_id,
                read["message"]["id"],
            )
            result = clear_read_items(self.student_id)
            student_thread = get_conversation_messages(
                self.student_id,
                read["conversation"]["id"],
            )
            teacher_thread = get_conversation_messages(
                self.teacher_id,
                read["conversation"]["id"],
            )
            summary = get_message_summary(self.student_id)

        self.assertEqual(result["cleared_private"], 1)
        self.assertEqual(result["cleared_notifications"], 0)
        self.assertEqual(result["unread_total"], 1)
        self.assertEqual(
            [item["id"] for item in student_thread["messages"]],
            [unread["message"]["id"]],
        )
        self.assertEqual(
            [item["id"] for item in teacher_thread["messages"]],
            [read["message"]["id"], unread["message"]["id"]],
        )
        self.assertEqual(summary["unread_private"], 1)

    def test_new_message_after_clear_reopens_thread_with_only_new_item_visible(self):
        with self.app.app_context():
            first = send_private_message(
                self.teacher_id,
                self.student_id,
                "旧消息",
            )
            mark_private_message_read(
                self.student_id,
                first["message"]["id"],
            )
            clear_read_items(self.student_id)
            conversations_before = list_conversations(self.student_id)

            second = send_private_message(
                self.teacher_id,
                self.student_id,
                "新消息",
            )
            conversations_after = list_conversations(self.student_id)
            thread = get_conversation_messages(
                self.student_id,
                first["conversation"]["id"],
            )

        self.assertEqual(conversations_before, [])
        self.assertEqual(len(conversations_after), 1)
        self.assertEqual(conversations_after[0]["unread_count"], 1)
        self.assertEqual(
            [item["id"] for item in thread["messages"]],
            [second["message"]["id"]],
        )

    def test_clear_read_handles_notifications_without_clearing_unread(self):
        now = "2026-09-15T00:00:00+00:00"
        with self.app.app_context():
            db = get_db()
            db.executemany(
                """
                INSERT INTO system_notifications (
                    recipient_id, event_key, event_type, title, body,
                    created_at, read_at
                )
                VALUES (?, ?, 'test', '标题', '正文', ?, ?)
                """,
                [
                    (self.student_id, "read-event", now, now),
                    (self.student_id, "unread-event", now, None),
                ],
            )
            db.commit()

        with self.app.app_context():
            result = clear_read_items(self.student_id)
            summary = get_message_summary(self.student_id)
            rows = get_db().execute(
                """
                SELECT event_key, cleared_at
                FROM system_notifications
                WHERE recipient_id = ?
                ORDER BY event_key
                """,
                (self.student_id,),
            ).fetchall()

        self.assertEqual(result["cleared_notifications"], 1)
        self.assertEqual(summary["unread_notifications"], 1)
        self.assertIsNotNone(rows[0]["cleared_at"])
        self.assertIsNone(rows[1]["cleared_at"])

    def test_mark_all_read_clears_unread_for_only_current_account(self):
        now = "2026-09-15T00:00:00+00:00"
        with self.app.app_context():
            send_private_message(
                self.teacher_id,
                self.student_id,
                "学员消息一",
            )
            send_private_message(
                self.teacher_id,
                self.student_id,
                "学员消息二",
            )
            send_private_message(
                self.teacher_id,
                self.other_student_id,
                "其他学员消息",
            )
            db = get_db()
            db.execute(
                """
                INSERT INTO system_notifications (
                    recipient_id, event_key, event_type, title, body, created_at
                )
                VALUES (?, 'student-event', 'test', '标题', '正文', ?)
                """,
                (self.student_id, now),
            )
            db.execute(
                """
                INSERT INTO system_notifications (
                    recipient_id, event_key, event_type, title, body, created_at
                )
                VALUES (?, 'other-event', 'test', '标题', '正文', ?)
                """,
                (self.other_student_id, now),
            )
            db.commit()

            summary = mark_all_read(self.student_id)
            student_rows = db.execute(
                """
                SELECT read_at
                FROM private_message_views
                WHERE user_id = ? AND cleared_at IS NULL
                """,
                (self.student_id,),
            ).fetchall()
            notification_rows = db.execute(
                """
                SELECT read_at
                FROM system_notifications
                WHERE recipient_id = ? AND cleared_at IS NULL
                """,
                (self.student_id,),
            ).fetchall()
            other_summary = get_message_summary(self.other_student_id)

        self.assertEqual(summary["unread_total"], 0)
        self.assertTrue(all(row["read_at"] is not None for row in student_rows))
        self.assertTrue(
            all(row["read_at"] is not None for row in notification_rows)
        )
        self.assertEqual(other_summary["unread_private"], 1)
        self.assertEqual(other_summary["unread_notifications"], 1)

    def test_mark_notification_read_updates_only_matching_recipient(self):
        now = "2026-09-15T00:00:00+00:00"
        with self.app.app_context():
            db = get_db()
            cursor = db.execute(
                """
                INSERT INTO system_notifications (
                    recipient_id, event_key, event_type, title, body, created_at
                )
                VALUES (?, 'student-event', 'test', '标题', '正文', ?)
                """,
                (self.student_id, now),
            )
            notification_id = int(cursor.lastrowid)
            db.commit()

            summary = mark_notification_read(
                self.student_id,
                notification_id,
            )
            read_at = db.execute(
                """
                SELECT read_at
                FROM system_notifications
                WHERE id = ?
                """,
                (notification_id,),
            ).fetchone()["read_at"]

        self.assertEqual(summary["unread_notifications"], 0)
        self.assertIsNotNone(read_at)

    def test_mark_read_rejects_missing_or_foreign_items(self):
        now = "2026-09-15T00:00:00+00:00"
        with self.app.app_context():
            sent = send_private_message(
                self.teacher_id,
                self.student_id,
                "仅学员",
            )
            db = get_db()
            cursor = db.execute(
                """
                INSERT INTO system_notifications (
                    recipient_id, event_key, event_type, title, body, created_at
                )
                VALUES (?, 'student-event', 'test', '标题', '正文', ?)
                """,
                (self.student_id, now),
            )
            notification_id = int(cursor.lastrowid)
            db.commit()

            with self.assertRaises(MessageNotFoundError):
                mark_private_message_read(
                    self.other_student_id,
                    sent["message"]["id"],
                )
            with self.assertRaises(MessageNotFoundError):
                mark_private_message_read(
                    self.student_id,
                    sent["message"]["id"] + 1000,
                )
            with self.assertRaises(MessageNotFoundError):
                mark_notification_read(
                    self.other_student_id,
                    notification_id,
                )
            with self.assertRaises(MessageNotFoundError):
                mark_notification_read(
                    self.student_id,
                    notification_id + 1000,
                )


if __name__ == "__main__":
    unittest.main()
