import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from app import create_app
from app.db import get_db
from app.messaging.broadcasts import (
    emit_monthly_agriculture_reminder,
    emit_policy_published,
    emit_system_announcement,
    emit_teaching_announcement,
)
from app.messaging.notification_service import list_notifications
from app.messaging.source_provider import set_messaging_source_provider


class FakeMessagingSourceProvider:
    def __init__(self):
        self.policy_subscribers: dict[str, set[int]] = {}
        self.product_subscribers: dict[str, set[int]] = {}

    def has_application_relationship(
        self, student_id: int, enterprise_id: int
    ) -> bool:
        return False

    def list_applied_enterprise_ids(self, student_id: int) -> list[int]:
        return []

    def list_applicant_student_ids(self, enterprise_id: int) -> list[int]:
        return []

    def list_policy_subscriber_ids(self, category: str) -> list[int]:
        return sorted(self.policy_subscribers.get(category, set()))

    def list_product_subscriber_ids(self, product_key: str) -> list[int]:
        return sorted(self.product_subscribers.get(product_key, set()))


class TestNotificationBroadcasts(unittest.TestCase):
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
        self.teacher_id = self.create_user("teacher", "教师甲", "teacher")
        self.enterprise_id = self.create_user(
            "enterprise",
            "企业用户",
            "enterprise",
        )
        self.government_id = self.create_user(
            "government",
            "政府用户",
            "government",
        )
        self.super_admin_id = self.create_user(
            "super-admin",
            "超级管理员",
            "super_admin",
        )
        self.admin_id = self.create_user("admin", "管理员", "admin")
        self.student_ids = {self.student_id, self.other_student_id}
        self.all_user_ids = {
            self.student_id,
            self.other_student_id,
            self.teacher_id,
            self.enterprise_id,
            self.government_id,
            self.super_admin_id,
            self.admin_id,
        }

        self.provider = FakeMessagingSourceProvider()
        self.provider.policy_subscribers["创业支持"] = {self.student_id}
        self.provider.product_subscribers.update(
            {
                "tea": {self.student_id},
                "rice": {self.other_student_id},
            }
        )
        set_messaging_source_provider(self.app, self.provider)

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

    def recipient_ids(self, result: dict) -> set[int]:
        notification_ids = {
            notification["id"] for notification in result["notifications"]
        }
        with self.app.app_context():
            return {
                user_id
                for user_id in self.all_user_ids
                if notification_ids
                & {
                    notification["id"]
                    for notification in list_notifications(user_id)
                }
            }

    def test_system_announcement_reaches_every_existing_account(self):
        with self.app.app_context():
            result = emit_system_announcement(
                event_id="announcement-1",
                announcement_id="a1",
                title="系统维护",
                body="今晚进行维护",
            )

        self.assertEqual(result["unique_recipient_count"], len(self.all_user_ids))
        self.assertEqual(self.recipient_ids(result), self.all_user_ids)
        for notification in result["notifications"]:
            self.assertEqual(
                notification["event_type"],
                "system_announcement",
            )
            self.assertEqual(notification["source_type"], "announcement")
            self.assertEqual(notification["source_id"], "a1")
            self.assertEqual(notification["title"], "系统维护")
            self.assertEqual(notification["body"], "今晚进行维护")

    def test_teaching_announcement_reaches_students_only(self):
        with self.app.app_context():
            result = emit_teaching_announcement(
                event_id="teaching-1",
                teacher_id=self.teacher_id,
                announcement_id="t1",
                title="课程安排",
                body="本周课程调整",
            )

        self.assertEqual(self.recipient_ids(result), self.student_ids)
        for notification in result["notifications"]:
            self.assertEqual(
                notification["event_type"],
                "teaching_announcement",
            )
            self.assertEqual(notification["source_type"], "announcement")
            self.assertEqual(notification["source_id"], "t1")

    def test_policy_push_uses_active_subscribers(self):
        with self.app.app_context():
            result = emit_policy_published(
                event_id="policy-1",
                policy_id="p1",
                title="创业补贴",
                category="创业支持",
            )

        self.assertEqual(
            self.recipient_ids(result),
            {self.student_id},
        )
        notification = result["notifications"][0]
        self.assertEqual(notification["event_type"], "policy_published")
        self.assertEqual(notification["source_type"], "policy")
        self.assertEqual(notification["source_id"], "p1")
        self.assertIn("创业补贴", notification["title"])
        self.assertIn("创业支持", notification["body"])

    def test_unsubscribe_keeps_existing_notification_and_stops_future_push(self):
        with self.app.app_context():
            first = emit_policy_published(
                event_id="policy-1",
                policy_id="p1",
                title="创业补贴",
                category="创业支持",
            )

        self.assertEqual(
            self.recipient_ids(first),
            {self.student_id},
        )

        self.provider.policy_subscribers["创业支持"].remove(
            self.student_id
        )
        with self.app.app_context():
            second = emit_policy_published(
                event_id="policy-2",
                policy_id="p2",
                title="第二期补贴",
                category="创业支持",
            )
            notifications = list_notifications(self.student_id)

        self.assertEqual(self.recipient_ids(second), set())
        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0]["source_id"], "p1")

    def test_agriculture_reminder_uses_exact_product_subscriber(self):
        with self.app.app_context():
            result = emit_monthly_agriculture_reminder(
                event_id="reminder-1",
                product_key="tea",
                month="2026-09",
                body="茶园进入秋管关键期",
            )
            rice_result = emit_monthly_agriculture_reminder(
                event_id="reminder-rice",
                product_key="rice",
                month="2026-09",
                body="水稻进入灌浆期",
            )

        self.assertEqual(
            self.recipient_ids(result),
            {self.student_id},
        )
        notification = result["notifications"][0]
        self.assertEqual(
            notification["event_type"],
            "agriculture_reminder",
        )
        self.assertEqual(notification["source_type"], "agricultural_product")
        self.assertEqual(notification["source_id"], "tea")
        self.assertIn("tea", notification["title"] + notification["body"])
        self.assertIn("2026-09", notification["title"] + notification["body"])
        self.assertEqual(
            self.recipient_ids(rice_result),
            {self.other_student_id},
        )

    def test_product_unsubscribe_keeps_existing_notification_and_stops_future_push(
        self,
    ):
        with self.app.app_context():
            first = emit_monthly_agriculture_reminder(
                event_id="reminder-1",
                product_key="tea",
                month="2026-09",
                body="茶园进入秋管关键期",
            )

        self.assertEqual(self.recipient_ids(first), {self.student_id})

        self.provider.product_subscribers["tea"].remove(self.student_id)
        with self.app.app_context():
            second = emit_monthly_agriculture_reminder(
                event_id="reminder-2",
                product_key="tea",
                month="2026-10",
                body="茶园进入冬季管护期",
            )
            notifications = list_notifications(self.student_id)

        self.assertEqual(self.recipient_ids(second), set())
        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0]["source_id"], "tea")


if __name__ == "__main__":
    unittest.main()
