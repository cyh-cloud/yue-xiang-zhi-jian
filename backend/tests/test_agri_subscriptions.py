import tempfile
import unittest
from pathlib import Path

from app import create_app
from app.agri_skills.calendar import (
    list_product_subscriptions,
    list_product_subscriber_ids,
    subscribe_product,
    unsubscribe_product,
)
from app.db import get_db
from app.messaging.broadcasts import emit_monthly_agriculture_reminder
from app.messaging.notification_service import list_notifications
from app.messaging.source_provider import (
    NullMessagingSourceProvider,
    get_messaging_source_provider,
    register_messaging_source_provider,
)


class SecondSourceProvider(NullMessagingSourceProvider):
    def has_application_relationship(
        self, student_id: int, enterprise_id: int
    ) -> bool:
        return (student_id, enterprise_id) == (10, 20)


class TestAgriSubscriptions(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(Path(self.temp_dir.name) / "test.db"),
                "SECRET_KEY": "test-only-secret",
            }
        )
        with self.app.app_context():
            cursor = get_db().execute(
                """
                INSERT INTO users (
                    username, password_hash, name, role, is_enabled,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, 'student', 1, ?, ?)
                """,
                (
                    "student01",
                    "test-password-hash",
                    "林晓",
                    "2026-09-15T00:00:00+00:00",
                    "2026-09-15T00:00:00+00:00",
                ),
            )
            self.student_id = int(cursor.lastrowid)
            get_db().commit()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_subscribe_is_idempotent_and_unsubscribe_stops_future_delivery(self):
        with self.app.app_context():
            subscribe_product(self.student_id, "litchi")
            subscribe_product(self.student_id, "litchi")

            self.assertEqual(
                list_product_subscriber_ids("litchi"),
                [self.student_id],
            )

            unsubscribe_product(self.student_id, "litchi")

            self.assertEqual(list_product_subscriber_ids("litchi"), [])

    def test_unsubscribe_keeps_history_but_does_not_reactivate(self):
        with self.app.app_context():
            subscribe_product(self.student_id, "litchi")
            unsubscribe_product(self.student_id, "litchi")
            subscribe_product(self.student_id, "litchi")

            self.assertEqual(
                list_product_subscriptions(self.student_id),
                ["litchi"],
            )

    def test_monthly_reminder_uses_02_notification_channel(self):
        with self.app.app_context():
            subscribe_product(self.student_id, "litchi")

            result = emit_monthly_agriculture_reminder(
                event_id="2026-10-litchi",
                product_key="litchi",
                month="2026-10",
                body="保果与病虫害巡查",
            )

            self.assertEqual(result["created_count"], 1)
            self.assertEqual(
                list_notifications(self.student_id)[0]["event_type"],
                "agriculture_reminder",
            )

    def test_monthly_reminder_delivery_has_no_recipients_after_unsubscribe(self):
        with self.app.app_context():
            subscribe_product(self.student_id, "litchi")
            unsubscribe_product(self.student_id, "litchi")

            result = emit_monthly_agriculture_reminder(
                event_id="2026-10-litchi",
                product_key="litchi",
                month="2026-10",
                body="保果与病虫害巡查",
            )

            self.assertEqual(result["created_count"], 0)
            self.assertEqual(list_notifications(self.student_id), [])

    def test_later_provider_registration_preserves_product_subscriptions(self):
        with self.app.app_context():
            subscribe_product(self.student_id, "litchi")

            register_messaging_source_provider(
                self.app,
                SecondSourceProvider(),
            )
            provider = get_messaging_source_provider()

            self.assertEqual(
                provider.list_product_subscriber_ids("litchi"),
                [self.student_id],
            )
            self.assertTrue(provider.has_application_relationship(10, 20))


if __name__ == "__main__":
    unittest.main()
