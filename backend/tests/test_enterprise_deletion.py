import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from app import create_app
from app.db import get_db
from app.enterprise_console import applications, jobs
from app.enterprise_console.errors import (
    EnterpriseConflictError,
    ProviderConflictError,
)
from app.messaging.notification_service import list_notifications


class TestEnterpriseDeletion(unittest.TestCase):
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
                name="企业一",
                role="enterprise",
            )
            self.student_ids = [
                self._insert_user(
                    db,
                    username=f"student-{index}",
                    name=f"学员{index}",
                    role="student",
                )
                for index in range(1, 5)
            ]
            self.category_id = db.execute(
                """
                INSERT INTO interest_tags (
                    group_key, name, sort_order, is_active
                )
                VALUES ('job', '删除测试类别', 0, 1)
                """
            ).lastrowid
            db.commit()

    def tearDown(self):
        self.temp_dir.cleanup()

    @staticmethod
    def _insert_user(db, *, username, name, role):
        timestamp = "2026-09-19T10:00:00+08:00"
        return db.execute(
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
                name,
                role,
                timestamp,
                timestamp,
            ),
        ).lastrowid

    def _insert_job(self, db, *, job_id, title="农业技术员"):
        timestamp = "2026-09-19T10:00:00+08:00"
        db.execute(
            """
            INSERT INTO job_positions (
                job_id,
                enterprise_id,
                title,
                salary,
                location,
                category_id,
                category_name,
                description,
                review_status,
                version,
                published_at,
                deleted_at,
                created_at,
                updated_at
            )
            VALUES (
                ?, ?, ?, '8000-10000', '广州', ?, '删除测试类别',
                '负责田间管理与技术推广', 'approved', 1, ?, NULL, ?, ?
            )
            """,
            (
                job_id,
                self.enterprise_id,
                title,
                self.category_id,
                timestamp,
                timestamp,
                timestamp,
            ),
        )

    @staticmethod
    def _insert_application(
        db,
        *,
        application_id,
        job_id,
        enterprise_id,
        student_id,
        status,
        status_version,
        submitted_at,
    ):
        db.execute(
            """
            INSERT INTO job_applications (
                application_id,
                job_id,
                enterprise_id,
                student_id,
                student_name,
                job_title_snapshot,
                resume_snapshot_json,
                skill_profile_snapshot_json,
                skill_profile_attached,
                status,
                status_version,
                position_closed_at,
                close_reason,
                idempotency_key,
                submitted_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, NULL, 0, ?, ?, NULL, NULL, ?, ?, ?)
            """,
            (
                application_id,
                job_id,
                enterprise_id,
                student_id,
                f"学员{student_id}",
                "删除前职位标题",
                json.dumps(
                    {"summary": f"学员{student_id}的简历"},
                    ensure_ascii=False,
                ),
                status,
                status_version,
                f"deletion-{application_id}",
                submitted_at,
                submitted_at,
            ),
        )

    def _application_row(self, application_id):
        return get_db().execute(
            """
            SELECT *
            FROM job_applications
            WHERE application_id = ?
            """,
            (application_id,),
        ).fetchone()

    def _notifications_by_type(self, student_id):
        counts = {}
        for notification in list_notifications(student_id):
            event_type = notification["event_type"]
            counts[event_type] = counts.get(event_type, 0) + 1
        return counts

    def test_delete_without_applications_is_idempotent(self):
        job_id = "job-no-applications"
        with self.app.app_context():
            db = get_db()
            self._insert_job(db, job_id=job_id)
            db.commit()

            first = jobs.delete_job(
                self.enterprise_id,
                job_id,
                expected_version=1,
            )
            repeated = jobs.delete_job(
                self.enterprise_id,
                job_id,
                expected_version=1,
            )

            self.assertEqual(
                first,
                {
                    "deleted": True,
                    "changed": True,
                    "closed_application_count": 0,
                    "historical_application_count": 0,
                    "notification_count": 0,
                },
            )
            self.assertEqual(
                repeated,
                {
                    "deleted": True,
                    "changed": False,
                    "closed_application_count": 0,
                    "historical_application_count": 0,
                    "notification_count": 0,
                },
            )
            self.assertEqual(jobs.list_jobs(self.enterprise_id), [])
            self.assertEqual(jobs.list_published_position_records(), [])
            outbox_count = db.execute(
                """
                SELECT COUNT(*)
                FROM enterprise_notification_outbox
                """
            ).fetchone()[0]
            self.assertEqual(outbox_count, 0)

    def test_delete_pending_only_closes_and_notifies_once(self):
        job_id = "job-pending-only"
        application_id = "application-pending-only"
        with self.app.app_context():
            db = get_db()
            self._insert_job(db, job_id=job_id)
            self._insert_application(
                db,
                application_id=application_id,
                job_id=job_id,
                enterprise_id=self.enterprise_id,
                student_id=self.student_ids[0],
                status="pending",
                status_version=1,
                submitted_at="2026-09-19T11:00:00+08:00",
            )
            db.commit()

            result = jobs.delete_job(
                self.enterprise_id,
                job_id,
                expected_version=1,
            )
            stored = self._application_row(application_id)
            detail = applications.get_application(
                self.enterprise_id,
                application_id,
            )
            repeated = jobs.delete_job(
                self.enterprise_id,
                job_id,
                expected_version=1,
            )

            self.assertEqual(
                result,
                {
                    "deleted": True,
                    "changed": True,
                    "closed_application_count": 1,
                    "historical_application_count": 0,
                    "notification_count": 1,
                },
            )
            self.assertEqual(stored["status"], "pending")
            self.assertEqual(stored["status_version"], 2)
            self.assertIsNotNone(stored["position_closed_at"])
            self.assertEqual(stored["close_reason"], "position_deleted")
            self.assertTrue(detail["position_closed"])
            self.assertEqual(detail["effective_status"], "closed")
            self.assertEqual(
                self._notifications_by_type(self.student_ids[0]),
                {"position_closed": 1},
            )
            with self.assertRaises(EnterpriseConflictError):
                applications.change_application_status(
                    self.enterprise_id,
                    application_id,
                    2,
                    "viewed",
                )
            with self.assertRaises(ProviderConflictError):
                applications.change_application_status(
                    self.enterprise_id,
                    application_id,
                    1,
                    "intent",
                )
            self.assertEqual(
                repeated,
                {
                    "deleted": True,
                    "changed": False,
                    "closed_application_count": 0,
                    "historical_application_count": 0,
                    "notification_count": 0,
                },
            )
            self.assertEqual(
                self._notifications_by_type(self.student_ids[0]),
                {"position_closed": 1},
            )

    def test_delete_handled_only_preserves_statuses_without_notices(self):
        job_id = "job-handled-only"
        handled = (
            ("application-viewed", self.student_ids[0], "viewed"),
            ("application-intent", self.student_ids[1], "intent"),
            (
                "application-unsuitable",
                self.student_ids[2],
                "unsuitable",
            ),
        )
        with self.app.app_context():
            db = get_db()
            self._insert_job(db, job_id=job_id)
            for application_id, student_id, status in handled:
                self._insert_application(
                    db,
                    application_id=application_id,
                    job_id=job_id,
                    enterprise_id=self.enterprise_id,
                    student_id=student_id,
                    status=status,
                    status_version=2,
                    submitted_at="2026-09-19T11:00:00+08:00",
                )
            db.commit()

            result = jobs.delete_job(
                self.enterprise_id,
                job_id,
                expected_version=1,
            )

            self.assertEqual(
                result,
                {
                    "deleted": True,
                    "changed": True,
                    "closed_application_count": 0,
                    "historical_application_count": 3,
                    "notification_count": 0,
                },
            )
            for application_id, student_id, status in handled:
                stored = self._application_row(application_id)
                detail = applications.get_application(
                    self.enterprise_id,
                    application_id,
                )
                self.assertEqual(stored["status"], status)
                self.assertEqual(stored["status_version"], 3)
                self.assertIsNotNone(stored["position_closed_at"])
                self.assertEqual(
                    stored["close_reason"],
                    "position_deleted",
                )
                self.assertTrue(detail["position_closed"])
                self.assertEqual(detail["effective_status"], status)
                self.assertEqual(
                    self._notifications_by_type(student_id),
                    {},
                )
                with self.assertRaises(EnterpriseConflictError):
                    applications.change_application_status(
                        self.enterprise_id,
                        application_id,
                        3,
                        "viewed" if status != "viewed" else "intent",
                    )

    def test_delete_mixed_matrix_and_history_filter_snapshot(self):
        job_id = "job-mixed"
        applications_data = (
            ("application-mixed-pending", self.student_ids[0], "pending", 1),
            ("application-mixed-viewed", self.student_ids[1], "viewed", 2),
            ("application-mixed-intent", self.student_ids[2], "intent", 2),
            (
                "application-mixed-unsuitable",
                self.student_ids[3],
                "unsuitable",
                2,
            ),
        )
        with self.app.app_context():
            db = get_db()
            self._insert_job(
                db,
                job_id=job_id,
                title="删除前职位标题",
            )
            for application_id, student_id, status, version in applications_data:
                self._insert_application(
                    db,
                    application_id=application_id,
                    job_id=job_id,
                    enterprise_id=self.enterprise_id,
                    student_id=student_id,
                    status=status,
                    status_version=version,
                    submitted_at="2026-09-19T11:00:00+08:00",
                )
            db.commit()

            result = jobs.delete_job(
                self.enterprise_id,
                job_id,
                expected_version=1,
            )
            filtered = applications.list_applications(
                self.enterprise_id,
                {"job_id": job_id},
            )
            pending = self._application_row(
                "application-mixed-pending"
            )
            stored_handled = {
                application_id: self._application_row(application_id)
                for application_id, _, status, _ in applications_data
                if status != "pending"
            }

            self.assertEqual(
                result,
                {
                    "deleted": True,
                    "changed": True,
                    "closed_application_count": 1,
                    "historical_application_count": 3,
                    "notification_count": 1,
                },
            )
            self.assertEqual(jobs.list_jobs(self.enterprise_id), [])
            self.assertEqual(jobs.list_published_position_records(), [])
            self.assertEqual(pending["status"], "pending")
            self.assertEqual(pending["status_version"], 2)
            self.assertIsNotNone(pending["position_closed_at"])
            for application_id, _, status, _ in applications_data:
                if status == "pending":
                    continue
                self.assertEqual(
                    stored_handled[application_id]["status"],
                    status,
                )
                self.assertEqual(
                    stored_handled[application_id]["status_version"],
                    3,
                )
                self.assertIsNotNone(
                    stored_handled[application_id]["position_closed_at"]
                )
            self.assertEqual(len(filtered), 4)
            self.assertEqual(
                {row["job_title"] for row in filtered},
                {"删除前职位标题"},
            )
            self.assertEqual(
                self._notifications_by_type(self.student_ids[0]),
                {"position_closed": 1},
            )
            for student_id in self.student_ids[1:]:
                self.assertEqual(
                    self._notifications_by_type(student_id),
                    {},
                )

    def test_status_change_wins_when_it_acquires_lock_first(self):
        job_id = "job-concurrent"
        application_id = "application-concurrent"
        with self.app.app_context():
            db = get_db()
            self._insert_job(db, job_id=job_id)
            self._insert_application(
                db,
                application_id=application_id,
                job_id=job_id,
                enterprise_id=self.enterprise_id,
                student_id=self.student_ids[0],
                status="pending",
                status_version=1,
                submitted_at="2026-09-19T11:00:00+08:00",
            )
            db.commit()

        status_entered = threading.Event()
        release_status = threading.Event()
        errors = []
        results = {}
        original_now = applications._now_iso

        def delayed_now():
            status_entered.set()
            if not release_status.wait(timeout=5):
                raise TimeoutError("Timed out waiting to commit status")
            return original_now()

        def change_status():
            try:
                with self.app.app_context():
                    results["status"] = (
                        applications.change_application_status(
                            self.enterprise_id,
                            application_id,
                            1,
                            "viewed",
                        )
                    )
            except Exception as error:
                errors.append(error)

        def delete_job():
            try:
                with self.app.app_context():
                    results["delete"] = jobs.delete_job(
                        self.enterprise_id,
                        job_id,
                        expected_version=1,
                    )
            except Exception as error:
                errors.append(error)

        with patch.object(
            applications,
            "_now_iso",
            side_effect=delayed_now,
        ):
            status_thread = threading.Thread(target=change_status)
            status_thread.start()
            self.assertTrue(status_entered.wait(timeout=5))

            delete_thread = threading.Thread(target=delete_job)
            delete_thread.start()
            time.sleep(0.05)
            release_status.set()

            status_thread.join(timeout=5)
            delete_thread.join(timeout=5)

        self.assertFalse(status_thread.is_alive())
        self.assertFalse(delete_thread.is_alive())
        self.assertEqual(errors, [])
        self.assertTrue(results["status"]["changed"])
        self.assertEqual(
            results["delete"]["historical_application_count"],
            1,
        )
        with self.app.app_context():
            stored = self._application_row(application_id)
            self.assertEqual(stored["status"], "viewed")
            self.assertEqual(stored["status_version"], 3)
            self.assertIsNotNone(stored["position_closed_at"])
            self.assertEqual(
                self._notifications_by_type(self.student_ids[0]),
                {"application_status": 1},
            )

    def test_notification_delivery_failure_does_not_rollback_deletion(self):
        job_id = "job-delivery-failure"
        application_id = "application-delivery-failure"
        with self.app.app_context():
            db = get_db()
            self._insert_job(db, job_id=job_id)
            self._insert_application(
                db,
                application_id=application_id,
                job_id=job_id,
                enterprise_id=self.enterprise_id,
                student_id=self.student_ids[0],
                status="pending",
                status_version=1,
                submitted_at="2026-09-19T11:00:00+08:00",
            )
            db.commit()

            with patch(
                "app.messaging.events.emit_position_closed",
                side_effect=RuntimeError("notification service unavailable"),
            ), self.assertLogs(
                "app.enterprise_console.notifications",
                level="ERROR",
            ):
                result = jobs.delete_job(
                    self.enterprise_id,
                    job_id,
                    expected_version=1,
                )

            stored_job = db.execute(
                """
                SELECT deleted_at
                FROM job_positions
                WHERE job_id = ?
                """,
                (job_id,),
            ).fetchone()
            stored_application = self._application_row(application_id)
            outbox = db.execute(
                """
                SELECT status, attempts
                FROM enterprise_notification_outbox
                WHERE event_type = 'position_closed'
                """
            ).fetchone()

            self.assertTrue(result["changed"])
            self.assertIsNotNone(stored_job["deleted_at"])
            self.assertIsNotNone(stored_application["position_closed_at"])
            self.assertEqual(outbox["status"], "pending")
            self.assertEqual(outbox["attempts"], 1)
            self.assertEqual(
                self._notifications_by_type(self.student_ids[0]),
                {},
            )


if __name__ == "__main__":
    unittest.main()
