import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import create_app
from app.db import get_db
from app.enterprise_console.errors import EnterpriseValidationError
from app.enterprise_console.notifications import (
    deliver_after_commit,
    deliver_enterprise_outbox,
    enqueue_enterprise_notification,
    retry_pending_enterprise_notifications,
)
from app.messaging.notification_service import list_notifications


class TestEnterpriseNotifications(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(
                    Path(self.temp_dir.name) / "test.db"
                ),
                "SECRET_KEY": "test-only-secret",
            }
        )
        with self.app.app_context():
            db = get_db()
            self.enterprise_id = self._insert_user(
                db,
                username="enterprise-1",
                role="enterprise",
            )
            self.student_id = self._insert_user(
                db,
                username="student-1",
                role="student",
            )
            db.commit()

    def tearDown(self):
        self.temp_dir.cleanup()

    @staticmethod
    def _insert_user(db, *, username, role):
        timestamp = "2026-09-19T10:00:00+08:00"
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
        return cursor.lastrowid

    def test_enqueue_is_idempotent_for_event_type_and_event_id(self):
        with self.app.app_context():
            db = get_db()
            first_id = enqueue_enterprise_notification(
                db,
                event_type="application_status",
                event_id="status-1",
                payload={
                    "student_id": self.student_id,
                    "application_id": "application-1",
                    "status": "意向沟通",
                },
            )
            second_id = enqueue_enterprise_notification(
                db,
                event_type="application_status",
                event_id="status-1",
                payload={
                    "student_id": self.student_id,
                    "application_id": "application-1",
                    "status": "已查看",
                },
            )
            db.commit()
            count = db.execute(
                """
                SELECT COUNT(*)
                FROM enterprise_notification_outbox
                WHERE event_type = ? AND event_id = ?
                """,
                ("application_status", "status-1"),
            ).fetchone()[0]

        self.assertEqual(first_id, second_id)
        self.assertEqual(count, 1)

    def test_enqueue_rejects_unknown_event_types(self):
        with self.app.app_context():
            with self.assertRaises(EnterpriseValidationError):
                enqueue_enterprise_notification(
                    get_db(),
                    event_type="unknown_event",
                    event_id="event-1",
                    payload={},
                )

    def test_event_types_map_to_matching_02_emitters(self):
        with self.app.app_context():
            db = get_db()
            submitted_id = enqueue_enterprise_notification(
                db,
                event_type="application_submitted",
                event_id="submitted-1",
                payload={
                    "enterprise_id": self.enterprise_id,
                    "student_id": self.student_id,
                    "application_id": "application-1",
                    "student_name": "张同学",
                    "job_title": "农业技术员",
                },
            )
            status_id = enqueue_enterprise_notification(
                db,
                event_type="application_status",
                event_id="status-1",
                payload={
                    "student_id": self.student_id,
                    "application_id": "application-1",
                    "status": "意向沟通",
                },
            )
            closed_id = enqueue_enterprise_notification(
                db,
                event_type="position_closed",
                event_id="closed-1",
                payload={
                    "student_ids": [self.student_id],
                    "position_id": "job-1",
                    "job_title": "农业技术员",
                },
            )
            db.commit()

        with (
            patch(
                "app.enterprise_console.notifications."
                "emit_application_submitted",
                return_value={"created": 1},
            ) as submitted,
            patch(
                "app.enterprise_console.notifications."
                "emit_application_status_changed",
                return_value={"created": 1},
            ) as status_changed,
            patch(
                "app.enterprise_console.notifications.emit_position_closed",
                return_value={"created": 1},
            ) as position_closed,
        ):
            with self.app.app_context():
                deliver_enterprise_outbox(submitted_id)
                deliver_enterprise_outbox(status_id)
                deliver_enterprise_outbox(closed_id)

        submitted.assert_called_once_with(
            event_id="submitted-1",
            enterprise_id=self.enterprise_id,
            student_id=self.student_id,
            application_id="application-1",
            student_name="张同学",
            job_title="农业技术员",
        )
        status_changed.assert_called_once_with(
            event_id="status-1",
            student_id=self.student_id,
            application_id="application-1",
            status="意向沟通",
        )
        position_closed.assert_called_once_with(
            event_id="closed-1",
            student_ids=[self.student_id],
            position_id="job-1",
            job_title="农业技术员",
        )

    def test_status_event_is_enqueued_and_delivered_once(self):
        with self.app.app_context():
            db = get_db()
            outbox_id = enqueue_enterprise_notification(
                db,
                event_type="application_status",
                event_id="status-1",
                payload={
                    "student_id": self.student_id,
                    "application_id": "application-1",
                    "status": "意向沟通",
                },
            )
            db.commit()
        with self.app.app_context():
            first = deliver_enterprise_outbox(outbox_id)
            second = deliver_enterprise_outbox(outbox_id)

            self.assertEqual(
                first,
                {"sent": 1, "already_sent": 0, "failed": 0},
            )
            self.assertEqual(
                second,
                {"sent": 0, "already_sent": 1, "failed": 0},
            )
            notices = list_notifications(self.student_id)
        self.assertEqual(len(notices), 1)
        self.assertIn("意向沟通", notices[0]["body"])

    def test_delivery_failure_keeps_pending_row(self):
        with self.app.app_context():
            db = get_db()
            outbox_id = enqueue_enterprise_notification(
                db,
                event_type="application_submitted",
                event_id="application-1",
                payload={
                    "enterprise_id": self.enterprise_id,
                    "student_id": self.student_id,
                    "application_id": "application-1",
                    "student_name": "张同学",
                    "job_title": "农业技术员",
                },
            )
            db.commit()

        with self.app.app_context():
            with patch(
                "app.enterprise_console.notifications."
                "emit_application_submitted",
                side_effect=RuntimeError("offline"),
            ):
                with self.assertRaises(RuntimeError):
                    deliver_enterprise_outbox(outbox_id)

            row = get_db().execute(
                """
                SELECT status, attempts
                FROM enterprise_notification_outbox
                WHERE id = ?
                """,
                (outbox_id,),
            ).fetchone()
        self.assertEqual(dict(row), {"status": "pending", "attempts": 1})

    def test_deliver_after_commit_returns_failure_without_raising(self):
        with self.app.app_context():
            db = get_db()
            outbox_id = enqueue_enterprise_notification(
                db,
                event_type="application_status",
                event_id="status-1",
                payload={
                    "student_id": self.student_id,
                    "application_id": "application-1",
                    "status": "意向沟通",
                },
            )
            db.commit()

        with self.app.app_context():
            with patch(
                "app.enterprise_console.notifications."
                "emit_application_status_changed",
                side_effect=RuntimeError("offline"),
            ):
                with self.assertLogs(
                    "app.enterprise_console.notifications",
                    level="ERROR",
                ) as captured_logs:
                    result = deliver_after_commit(outbox_id)

            row = get_db().execute(
                """
                SELECT status, attempts
                FROM enterprise_notification_outbox
                WHERE id = ?
                """,
                (outbox_id,),
            ).fetchone()

        self.assertEqual(
            result,
            {"sent": 0, "already_sent": 0, "failed": 1},
        )
        self.assertIn(
            f"outbox row {outbox_id}",
            captured_logs.output[0],
        )
        self.assertEqual(dict(row), {"status": "pending", "attempts": 1})

    def test_retry_sends_pending_rows_without_duplicates(self):
        with self.app.app_context():
            db = get_db()
            outbox_id = enqueue_enterprise_notification(
                db,
                event_type="position_closed",
                event_id="job-1:closed",
                payload={
                    "student_ids": [self.student_id],
                    "position_id": "job-1",
                    "job_title": "农业技术员",
                },
            )
            db.commit()
        with self.app.app_context():
            result = retry_pending_enterprise_notifications(limit=10)
            repeated = retry_pending_enterprise_notifications(limit=10)
            notices = list_notifications(self.student_id)

        self.assertEqual(result["sent"], 1)
        self.assertEqual(repeated["sent"], 0)
        self.assertEqual(len(notices), 1)

        with self.app.app_context():
            row = get_db().execute(
                """
                SELECT status, attempts
                FROM enterprise_notification_outbox
                WHERE id = ?
                """,
                (outbox_id,),
            ).fetchone()
        self.assertEqual(dict(row), {"status": "sent", "attempts": 1})


if __name__ == "__main__":
    unittest.main()
