import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from app import create_app
from app.db import get_db
from app.messaging.notification_service import (
    NotificationValidationError,
    emit_notification,
    emit_notifications,
    list_notifications,
    mark_notification_sources_unavailable,
)
from app.messaging.service import clear_read_items, mark_notification_read


class TestNotificationService(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(Path(self.temp_dir.name) / "test.db"),
                "SECRET_KEY": "test-only-secret",
            }
        )
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

    def test_same_event_key_is_delivered_once(self):
        with self.app.app_context():
            first = emit_notification(
                recipient_id=self.student_id,
                event_key="review_approved:submission-4",
                event_type="review_approved",
                title="审核通过",
                body="课程视频已通过并上架",
                source_type="course_video",
                source_id="88",
            )
            second = emit_notification(
                recipient_id=self.student_id,
                event_key="review_approved:submission-4",
                event_type="review_approved",
                title="审核通过",
                body="课程视频已通过并上架",
                source_type="course_video",
                source_id="88",
            )
            notifications = list_notifications(self.student_id)

        self.assertEqual(first["id"], second["id"])
        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0]["source_type"], "course_video")
        self.assertEqual(notifications[0]["source_id"], "88")
        self.assertTrue(notifications[0]["source_available"])
        self.assertFalse(notifications[0]["read"])

    def test_new_event_key_creates_new_notification(self):
        common = {
            "recipient_id": self.student_id,
            "event_type": "review_approved",
            "title": "审核通过",
            "body": "课程视频已通过并上架",
        }
        with self.app.app_context():
            first = emit_notification(
                event_key="review_approved:submission-4",
                **common,
            )
            second = emit_notification(
                event_key="review_approved:submission-5",
                **common,
            )
            notifications = list_notifications(self.student_id)

        self.assertNotEqual(first["id"], second["id"])
        self.assertEqual(
            [item["id"] for item in notifications],
            [second["id"], first["id"]],
        )

    def test_blank_required_fields_are_rejected_without_writing(self):
        common = {
            "recipient_id": self.student_id,
            "event_key": "event:1",
            "event_type": "event",
            "title": "标题",
            "body": "正文",
        }
        invalid_values = {
            "event_key": " \n\t ",
            "event_type": "",
            "title": " ",
            "body": "\t",
        }

        with self.app.app_context():
            for field, value in invalid_values.items():
                with self.subTest(field=field):
                    with self.assertRaises(NotificationValidationError):
                        emit_notification(**(common | {field: value}))

            notifications = list_notifications(self.student_id)

        self.assertEqual(notifications, [])

    def test_notification_is_visible_only_to_its_recipient(self):
        with self.app.app_context():
            emit_notification(
                recipient_id=self.student_id,
                event_key="account_reset:student",
                event_type="account_reset",
                title="密码已重置",
                body="请联系管理员获取临时密码",
            )
            recipient_notifications = list_notifications(self.student_id)
            unrelated_notifications = list_notifications(self.other_student_id)

        self.assertEqual(len(recipient_notifications), 1)
        self.assertEqual(unrelated_notifications, [])

    def test_emit_notifications_deduplicates_repeated_recipient_ids(self):
        with self.app.app_context():
            result = emit_notifications(
                recipient_ids=[
                    self.student_id,
                    self.student_id,
                    self.other_student_id,
                ],
                event_key="announcement:2026-09",
                event_type="announcement",
                title="系统公告",
                body="平台功能已更新",
            )
            first_recipient = list_notifications(self.student_id)
            second_recipient = list_notifications(self.other_student_id)

        self.assertEqual(result["created_count"], 2)
        self.assertEqual(result["unique_recipient_count"], 2)
        self.assertEqual(len(result["notifications"]), 2)
        self.assertEqual(len(first_recipient), 1)
        self.assertEqual(len(second_recipient), 1)

    def test_list_notifications_excludes_cleared_rows_and_includes_read_state(self):
        common = {
            "recipient_id": self.student_id,
            "event_type": "event",
            "title": "标题",
            "body": "正文",
        }
        with self.app.app_context():
            first = emit_notification(event_key="event:1", **common)
            second = emit_notification(event_key="event:2", **common)
            third = emit_notification(event_key="event:3", **common)
            mark_notification_read(self.student_id, first["id"])
            clear_read_items(self.student_id)
            mark_notification_read(self.student_id, third["id"])
            notifications = list_notifications(self.student_id)

        self.assertEqual(
            [item["id"] for item in notifications],
            [third["id"], second["id"]],
        )
        self.assertEqual(
            [item["read"] for item in notifications],
            [True, False],
        )

    def test_mark_notification_sources_unavailable_updates_matching_rows(self):
        common = {
            "event_type": "review_approved",
            "title": "审核通过",
            "body": "内容已上架",
        }
        with self.app.app_context():
            matching = emit_notification(
                recipient_id=self.student_id,
                event_key="review:1",
                source_type="course_video",
                source_id="88",
                **common,
            )
            matching_for_other = emit_notification(
                recipient_id=self.other_student_id,
                event_key="review:1",
                source_type="course_video",
                source_id="88",
                **common,
            )
            other_source_type = emit_notification(
                recipient_id=self.student_id,
                event_key="review:2",
                source_type="job_position",
                source_id="88",
                **common,
            )
            other_source_id = emit_notification(
                recipient_id=self.student_id,
                event_key="review:3",
                source_type="course_video",
                source_id="89",
                **common,
            )

            affected = mark_notification_sources_unavailable(
                source_type="course_video",
                source_id="88",
            )
            repeated_affected = mark_notification_sources_unavailable(
                source_type="course_video",
                source_id="88",
            )
            student_notifications = {
                item["id"]: item
                for item in list_notifications(self.student_id)
            }
            other_notifications = list_notifications(self.other_student_id)

        self.assertEqual(affected, 2)
        self.assertEqual(repeated_affected, 0)
        self.assertFalse(student_notifications[matching["id"]]["source_available"])
        self.assertTrue(
            student_notifications[other_source_type["id"]]["source_available"]
        )
        self.assertTrue(
            student_notifications[other_source_id["id"]]["source_available"]
        )
        self.assertEqual(len(other_notifications), 1)
        self.assertFalse(other_notifications[0]["source_available"])
        self.assertEqual(
            other_notifications[0]["id"],
            matching_for_other["id"],
        )


if __name__ == "__main__":
    unittest.main()
