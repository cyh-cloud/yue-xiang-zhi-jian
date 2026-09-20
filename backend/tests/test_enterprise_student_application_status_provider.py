import inspect
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import create_app
from app.db import get_db
from app.enterprise_console.errors import ProviderUnavailableError
from app.enterprise_console.providers import (
    DatabaseJobApplicationStatusProvider,
    JobApplicationStatusProvider,
    configure_enterprise_providers,
    get_job_application_status_provider,
    set_job_application_status_provider,
)


class ReplacementStatusProvider:
    def list_student_applications(self, *, student_id):
        return [{"application_id": "application-1", "student_id": student_id}]

    def get_student_application(self, *, student_id, application_id):
        return None


class StudentApplicationStatusProviderTests(unittest.TestCase):
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
            self.student_one = self._insert_user(
                db,
                username="student-1",
                name="学员一",
                role="student",
            )
            self.student_two = self._insert_user(
                db,
                username="student-2",
                name="学员二",
                role="student",
            )
            self.category_id = db.execute(
                """
                INSERT INTO interest_tags (
                    group_key, name, sort_order, is_active
                )
                VALUES ('job', '学员申请状态测试类别', 0, 1)
                """
            ).lastrowid
            for job_id, title in (
                ("job-new", "岗位新"),
                ("job-old", "岗位旧"),
                ("job-other", "岗位其他"),
            ):
                self._insert_job(db, job_id=job_id, title=title)

            self._insert_application(
                db,
                application_id="application-new",
                job_id="job-new",
                student_id=self.student_one,
                student_name="学员一",
                status="pending",
                position_closed_at="2026-09-19T13:00:00+08:00",
                submitted_at="2026-09-19T12:00:00+08:00",
                idempotency_key="request-new",
            )
            self._insert_application(
                db,
                application_id="application-old",
                job_id="job-old",
                student_id=self.student_one,
                student_name="学员一",
                status="unsuitable",
                position_closed_at="2026-09-19T13:00:00+08:00",
                submitted_at="2026-09-19T11:00:00+08:00",
                idempotency_key="request-old",
            )
            self._insert_application(
                db,
                application_id="application-other",
                job_id="job-other",
                student_id=self.student_two,
                student_name="学员二",
                status="pending",
                position_closed_at=None,
                submitted_at="2026-09-19T10:00:00+08:00",
                idempotency_key="request-other",
            )
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

    def _insert_job(self, db, *, job_id, title):
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
                created_at,
                updated_at
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, 'approved', 2, ?, ?, ?
            )
            """,
            (
                job_id,
                self.enterprise_id,
                title,
                "8000-10000",
                "广州",
                self.category_id,
                "农业技术员",
                "负责田间管理与技术推广",
                "2026-09-19T12:00:00+08:00",
                timestamp,
                timestamp,
            ),
        )

    def _insert_application(
        self,
        db,
        *,
        application_id,
        job_id,
        student_id,
        student_name,
        status,
        position_closed_at,
        submitted_at,
        idempotency_key,
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
            VALUES (?, ?, ?, ?, ?, ?, ?, NULL, 0, ?, 1, ?, ?, ?, ?, ?)
            """,
            (
                application_id,
                job_id,
                self.enterprise_id,
                student_id,
                student_name,
                f"{student_name}的申请岗位",
                json.dumps(
                    {"summary": f"{student_name}的简历"},
                    ensure_ascii=False,
                ),
                status,
                position_closed_at,
                (
                    "position_deleted"
                    if position_closed_at is not None
                    else None
                ),
                idempotency_key,
                submitted_at,
                submitted_at,
            ),
        )

    def test_protocol_and_database_signature_match(self):
        self.assertEqual(
            inspect.signature(
                DatabaseJobApplicationStatusProvider.list_student_applications
            ),
            inspect.signature(
                JobApplicationStatusProvider.list_student_applications
            ),
        )
        self.assertEqual(
            inspect.signature(
                DatabaseJobApplicationStatusProvider.get_student_application
            ),
            inspect.signature(
                JobApplicationStatusProvider.get_student_application
            ),
        )

    def test_replacement_uses_single_slot(self):
        provider = ReplacementStatusProvider()
        set_job_application_status_provider(self.app, provider)
        with self.app.app_context():
            self.assertIs(get_job_application_status_provider(), provider)

    def test_configure_and_default_installation(self):
        provider = ReplacementStatusProvider()
        configure_enterprise_providers(
            self.app,
            job_application_status_provider=provider,
        )
        with self.app.app_context():
            self.assertIs(get_job_application_status_provider(), provider)

    def test_default_provider_is_database_backed(self):
        with self.app.app_context():
            self.assertIsInstance(
                get_job_application_status_provider(),
                DatabaseJobApplicationStatusProvider,
            )

    def test_database_errors_are_wrapped(self):
        provider = DatabaseJobApplicationStatusProvider()
        with patch(
            "app.enterprise_console.applications."
            "list_student_application_records",
            side_effect=sqlite3.OperationalError("database unavailable"),
        ):
            with self.app.app_context():
                with self.assertRaises(ProviderUnavailableError) as raised:
                    provider.list_student_applications(student_id=1)

        self.assertEqual(raised.exception.code, "provider_unavailable")
        self.assertEqual(
            raised.exception.message,
            "Application status data is unavailable",
        )
        self.assertEqual(raised.exception.details, {})

    def test_list_isolated_by_student_and_sorted(self):
        with self.app.app_context():
            records = (
                DatabaseJobApplicationStatusProvider()
                .list_student_applications(student_id=self.student_one)
            )

        self.assertEqual(
            [item["application_id"] for item in records],
            ["application-new", "application-old"],
        )
        self.assertNotIn(
            "application-other",
            {item["application_id"] for item in records},
        )
        self.assertEqual(
            {item["student_id"] for item in records},
            {self.student_one},
        )

    def test_get_returns_none_for_another_students_application(self):
        with self.app.app_context():
            result = (
                DatabaseJobApplicationStatusProvider()
                .get_student_application(
                    student_id=self.student_one,
                    application_id="application-other",
                )
            )

        self.assertIsNone(result)

    def test_closed_status_projection_preserves_business_status(self):
        with self.app.app_context():
            provider = DatabaseJobApplicationStatusProvider()
            closed_pending = provider.get_student_application(
                student_id=self.student_one,
                application_id="application-new",
            )
            closed_handled = provider.get_student_application(
                student_id=self.student_one,
                application_id="application-old",
            )

        self.assertEqual(closed_pending["status"], "pending")
        self.assertTrue(closed_pending["position_closed"])
        self.assertEqual(closed_pending["effective_status"], "closed")
        self.assertEqual(
            closed_pending["effective_status_label"],
            "岗位已关闭",
        )
        self.assertEqual(closed_handled["status"], "unsuitable")
        self.assertEqual(closed_handled["effective_status"], "unsuitable")
        self.assertTrue(closed_handled["position_closed"])

    def test_student_record_includes_provider_fields_only(self):
        with self.app.app_context():
            record = (
                DatabaseJobApplicationStatusProvider()
                .get_student_application(
                    student_id=self.student_one,
                    application_id="application-new",
                )
            )

        required_fields = {
            "application_id",
            "job_id",
            "enterprise_id",
            "enterprise_name",
            "student_id",
            "student_name",
            "job_title",
            "status",
            "status_version",
            "position_closed",
            "position_closed_at",
            "effective_status",
            "effective_status_label",
            "submitted_at",
        }
        self.assertTrue(required_fields.issubset(record))
        self.assertEqual(record["enterprise_name"], "企业一")
        self.assertTrue(
            {
                "id",
                "close_reason",
                "idempotency_key",
                "updated_at",
            }.isdisjoint(record)
        )


if __name__ == "__main__":
    unittest.main()
