import inspect
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import create_app
from app.db import get_db
from app.enterprise_console.errors import (
    ProviderError,
    ProviderUnavailableError,
    ProviderValidationError,
)
from app.enterprise_console.providers import (
    DatabaseJobApplicationIntakeProvider,
    JobApplicationIntakeProvider,
    get_job_application_intake_provider,
    set_job_application_intake_provider,
)


class ReplacementIntakeProvider:
    def __init__(self):
        self.calls = []

    def submit_application(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "application_id": "application-replacement",
            **kwargs,
        }


class TestEnterpriseApplicationProvider(unittest.TestCase):
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
            self.category_id = db.execute(
                """
                INSERT INTO interest_tags (
                    group_key, name, sort_order, is_active
                )
                VALUES ('job', '申请 provider 测试类别', 0, 1)
                """
            ).lastrowid
            self._insert_job(db, "job-1")
            db.commit()

    def tearDown(self):
        self.temp_dir.cleanup()

    @staticmethod
    def _insert_user(db, *, username, role):
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
                username,
                role,
                timestamp,
                timestamp,
            ),
        ).lastrowid

    def _insert_job(self, db, job_id):
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
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'approved', 2, ?, ?, ?)
            """,
            (
                job_id,
                self.enterprise_id,
                "农业技术员",
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

    def test_application_intake_provider_is_replaceable(self):
        replacement = ReplacementIntakeProvider()
        set_job_application_intake_provider(self.app, replacement)

        with self.app.app_context():
            result = get_job_application_intake_provider().submit_application(
                job_id="job-1",
                student_id=self.student_id,
                resume_snapshot={"education": ["A"]},
                skill_profile_snapshot=None,
                idempotency_key="07-request-1",
            )
            current_provider = get_job_application_intake_provider()

        self.assertIs(current_provider, replacement)
        self.assertEqual(
            result["application_id"],
            "application-replacement",
        )
        self.assertEqual(
            replacement.calls,
            [
                {
                    "job_id": "job-1",
                    "student_id": self.student_id,
                    "resume_snapshot": {"education": ["A"]},
                    "skill_profile_snapshot": None,
                    "idempotency_key": "07-request-1",
                }
            ],
        )

    def test_database_provider_delegates_with_frozen_signature(self):
        provider = DatabaseJobApplicationIntakeProvider()
        protocol_signature = inspect.signature(
            JobApplicationIntakeProvider.submit_application
        )
        provider_signature = inspect.signature(
            DatabaseJobApplicationIntakeProvider.submit_application
        )

        self.assertEqual(provider_signature, protocol_signature)

        with self.app.app_context():
            result = provider.submit_application(
                job_id="job-1",
                student_id=self.student_id,
                resume_snapshot={"education": ["A"]},
                skill_profile_snapshot=None,
                idempotency_key="07-request-1",
            )

        expected_fields = {
            "application_id",
            "job_id",
            "enterprise_id",
            "student_id",
            "student_name",
            "job_title",
            "resume_snapshot",
            "skill_profile",
            "skill_profile_attached",
            "status",
            "status_version",
            "position_closed",
            "effective_status",
            "submitted_at",
        }
        self.assertTrue(expected_fields.issubset(result))
        self.assertEqual(result["status"], "pending")
        self.assertEqual(result["effective_status"], "pending")

    def test_database_provider_preserves_validation_errors(self):
        provider = DatabaseJobApplicationIntakeProvider()

        with self.app.app_context():
            with self.assertRaises(ProviderValidationError):
                provider.submit_application(
                    job_id="job-1",
                    student_id=self.enterprise_id,
                    resume_snapshot={"education": ["A"]},
                    skill_profile_snapshot=None,
                    idempotency_key="07-request-1",
                )

    def test_database_errors_are_wrapped_as_provider_errors(self):
        provider = DatabaseJobApplicationIntakeProvider()

        with patch(
            "app.enterprise_console.applications."
            "record_application_submission",
            side_effect=sqlite3.OperationalError("database unavailable"),
        ):
            with self.app.app_context():
                with self.assertRaises(ProviderError) as raised:
                    provider.submit_application(
                        job_id="job-1",
                        student_id=self.student_id,
                        resume_snapshot={"education": ["A"]},
                        skill_profile_snapshot=None,
                        idempotency_key="07-request-1",
                    )

        self.assertIsInstance(raised.exception, ProviderUnavailableError)
        self.assertEqual(
            raised.exception.code,
            "provider_unavailable",
        )


if __name__ == "__main__":
    unittest.main()
