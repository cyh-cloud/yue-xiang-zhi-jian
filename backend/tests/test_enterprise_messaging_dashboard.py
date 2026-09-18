import tempfile
import unittest
from pathlib import Path

from app import create_app
from app.db import get_db
from app.enterprise_console import (
    EnterpriseMessagingProvider,
    get_dashboard,
)
from app.enterprise_console.dashboard import (
    get_platform_active_job_count,
    get_platform_cumulative_application_count,
)
from app.enterprise_console.errors import EnterpriseValidationError
from app.enterprise_console.jobs import delete_job
from app.messaging.relationships import messaging_relationship
from app.messaging.source_provider import NullMessagingSourceProvider


class TestEnterpriseMessagingDashboard(unittest.TestCase):
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

    @staticmethod
    def _insert_category(db):
        return db.execute(
            """
            INSERT INTO interest_tags (
                group_key,
                name,
                sort_order,
                is_active
            )
            VALUES ('job', 'Messaging Dashboard', 0, 1)
            """
        ).lastrowid

    @staticmethod
    def _insert_job(
        db,
        *,
        job_id,
        enterprise_id,
        category_id,
        review_status="approved",
        published_at="2026-09-19T11:00:00+08:00",
        deleted_at=None,
    ):
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
                ?, ?, ?, '8000-10000', 'Guangzhou', ?,
                'Messaging Dashboard', 'Test position', ?, 1, ?, ?, ?, ?
            )
            """,
            (
                job_id,
                enterprise_id,
                job_id,
                category_id,
                review_status,
                published_at,
                deleted_at,
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
        status="pending",
        position_closed_at=None,
    ):
        timestamp = "2026-09-19T12:00:00+08:00"
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
                status,
                status_version,
                position_closed_at,
                close_reason,
                idempotency_key,
                submitted_at,
                updated_at
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, '{}', ?, 1, ?, ?, ?, ?, ?
            )
            """,
            (
                application_id,
                job_id,
                enterprise_id,
                student_id,
                f"student-{student_id}",
                job_id,
                status,
                position_closed_at,
                "position_deleted" if position_closed_at else None,
                application_id,
                timestamp,
                timestamp,
            ),
        )

    def test_relationships_are_scoped_and_duplicate_students_are_deduplicated(
        self,
    ):
        with self.app.app_context():
            db = get_db()
            enterprise_a = self._insert_user(
                db,
                username="enterprise-a",
                role="enterprise",
            )
            enterprise_b = self._insert_user(
                db,
                username="enterprise-b",
                role="enterprise",
            )
            student_a = self._insert_user(
                db,
                username="student-a",
                role="student",
            )
            student_b = self._insert_user(
                db,
                username="student-b",
                role="student",
            )
            category_id = self._insert_category(db)

            for job_id, enterprise_id in (
                ("job-a-1", enterprise_a),
                ("job-a-2", enterprise_a),
                ("job-b-1", enterprise_b),
                ("job-b-2", enterprise_b),
            ):
                self._insert_job(
                    db,
                    job_id=job_id,
                    enterprise_id=enterprise_id,
                    category_id=category_id,
                )

            self._insert_application(
                db,
                application_id="application-a-1",
                job_id="job-a-1",
                enterprise_id=enterprise_a,
                student_id=student_a,
            )
            self._insert_application(
                db,
                application_id="application-a-2",
                job_id="job-a-2",
                enterprise_id=enterprise_a,
                student_id=student_a,
            )
            self._insert_application(
                db,
                application_id="application-b-1",
                job_id="job-b-1",
                enterprise_id=enterprise_b,
                student_id=student_a,
            )
            self._insert_application(
                db,
                application_id="application-b-2",
                job_id="job-b-2",
                enterprise_id=enterprise_b,
                student_id=student_b,
            )
            db.commit()

            provider = EnterpriseMessagingProvider()
            self.assertTrue(
                issubclass(
                    EnterpriseMessagingProvider,
                    NullMessagingSourceProvider,
                )
            )
            self.assertIsInstance(provider, NullMessagingSourceProvider)
            self.assertTrue(
                provider.has_application_relationship(
                    student_a,
                    enterprise_a,
                )
            )
            self.assertFalse(
                provider.has_application_relationship(
                    student_b,
                    enterprise_a,
                )
            )
            self.assertEqual(
                provider.list_applied_enterprise_ids(student_a),
                [enterprise_a, enterprise_b],
            )
            self.assertEqual(
                provider.list_applied_enterprise_ids(student_b),
                [enterprise_b],
            )
            self.assertEqual(
                provider.list_applicant_student_ids(enterprise_a),
                [student_a],
            )
            self.assertEqual(
                provider.list_applicant_student_ids(enterprise_b),
                [student_a, student_b],
            )
            self.assertEqual(provider.list_policy_subscriber_ids("policy"), [])
            self.assertEqual(provider.list_product_subscriber_ids("product"), [])

    def test_registered_relationship_survives_job_deletion(self):
        with self.app.app_context():
            db = get_db()
            enterprise_a = self._insert_user(
                db,
                username="enterprise-a",
                role="enterprise",
            )
            enterprise_b = self._insert_user(
                db,
                username="enterprise-b",
                role="enterprise",
            )
            student_a = self._insert_user(
                db,
                username="student-a",
                role="student",
            )
            student_b = self._insert_user(
                db,
                username="student-b",
                role="student",
            )
            category_id = self._insert_category(db)
            self._insert_job(
                db,
                job_id="job-a",
                enterprise_id=enterprise_a,
                category_id=category_id,
            )
            self._insert_job(
                db,
                job_id="job-b",
                enterprise_id=enterprise_b,
                category_id=category_id,
            )
            self._insert_application(
                db,
                application_id="application-a",
                job_id="job-a",
                enterprise_id=enterprise_a,
                student_id=student_a,
            )
            self._insert_application(
                db,
                application_id="application-b",
                job_id="job-b",
                enterprise_id=enterprise_b,
                student_id=student_b,
            )
            db.commit()

            deleted = delete_job(
                enterprise_a,
                "job-a",
                expected_version=1,
            )
            self.assertTrue(deleted["deleted"])

        with self.app.app_context():
            self.assertEqual(
                messaging_relationship(student_a, enterprise_a),
                "application",
            )
            self.assertEqual(
                messaging_relationship(enterprise_a, student_a),
                "application",
            )
            self.assertIsNone(
                messaging_relationship(student_b, enterprise_a)
            )
            provider = EnterpriseMessagingProvider()
            self.assertTrue(
                provider.has_application_relationship(
                    student_a,
                    enterprise_a,
                )
            )
            self.assertEqual(
                provider.list_applicant_student_ids(enterprise_a),
                [student_a],
            )

    def test_dashboard_counts_only_current_enterprise_and_keeps_platform_metrics(
        self,
    ):
        with self.app.app_context():
            db = get_db()
            enterprise_a = self._insert_user(
                db,
                username="enterprise-a",
                role="enterprise",
            )
            enterprise_b = self._insert_user(
                db,
                username="enterprise-b",
                role="enterprise",
            )
            student_ids = [
                self._insert_user(
                    db,
                    username=f"student-{index}",
                    role="student",
                )
                for index in range(1, 7)
            ]
            category_id = self._insert_category(db)

            for job_id, enterprise_id in (
                ("job-a-active-1", enterprise_a),
                ("job-a-active-2", enterprise_a),
                ("job-b-active-1", enterprise_b),
                ("job-b-active-2", enterprise_b),
            ):
                self._insert_job(
                    db,
                    job_id=job_id,
                    enterprise_id=enterprise_id,
                    category_id=category_id,
                )
            for job_id, review_status, published_at, deleted_at in (
                (
                    "job-a-deleted",
                    "approved",
                    "2026-09-19T11:00:00+08:00",
                    "2026-09-19T13:00:00+08:00",
                ),
                (
                    "job-a-no-publication",
                    "approved",
                    None,
                    None,
                ),
                (
                    "job-a-blank-publication",
                    "approved",
                    "   ",
                    None,
                ),
                (
                    "job-a-pending",
                    "pending",
                    "2026-09-19T11:00:00+08:00",
                    None,
                ),
                (
                    "job-a-rejected",
                    "rejected",
                    "2026-09-19T11:00:00+08:00",
                    None,
                ),
            ):
                self._insert_job(
                    db,
                    job_id=job_id,
                    enterprise_id=enterprise_a,
                    category_id=category_id,
                    review_status=review_status,
                    published_at=published_at,
                    deleted_at=deleted_at,
                )

            applications = (
                (
                    "application-a-1",
                    "job-a-active-1",
                    enterprise_a,
                    student_ids[0],
                    "pending",
                    None,
                ),
                (
                    "application-a-2",
                    "job-a-active-2",
                    enterprise_a,
                    student_ids[1],
                    "viewed",
                    None,
                ),
                (
                    "application-a-3",
                    "job-a-active-1",
                    enterprise_a,
                    student_ids[2],
                    "intent",
                    None,
                ),
                (
                    "application-a-4",
                    "job-a-active-2",
                    enterprise_a,
                    student_ids[3],
                    "unsuitable",
                    None,
                ),
                (
                    "application-a-5",
                    "job-a-deleted",
                    enterprise_a,
                    student_ids[4],
                    "pending",
                    "2026-09-19T13:00:00+08:00",
                ),
                (
                    "application-b-1",
                    "job-b-active-1",
                    enterprise_b,
                    student_ids[5],
                    "pending",
                    None,
                ),
            )
            for (
                application_id,
                job_id,
                enterprise_id,
                student_id,
                status,
                position_closed_at,
            ) in applications:
                self._insert_application(
                    db,
                    application_id=application_id,
                    job_id=job_id,
                    enterprise_id=enterprise_id,
                    student_id=student_id,
                    status=status,
                    position_closed_at=position_closed_at,
                )
            db.commit()

            self.assertEqual(
                get_dashboard(enterprise_a),
                {
                    "active_job_count": 2,
                    "received_resume_count": 5,
                },
            )
            self.assertEqual(
                get_dashboard(enterprise_b),
                {
                    "active_job_count": 2,
                    "received_resume_count": 1,
                },
            )
            self.assertEqual(
                get_dashboard(999999),
                {
                    "active_job_count": 0,
                    "received_resume_count": 0,
                },
            )
            self.assertEqual(get_platform_active_job_count(), 4)
            self.assertEqual(
                get_platform_cumulative_application_count(),
                6,
            )

    def test_dashboard_rejects_invalid_enterprise_identifiers(self):
        with self.app.app_context():
            for enterprise_id in (True, 0, -1, 1.0, "1", None):
                with self.subTest(enterprise_id=enterprise_id):
                    with self.assertRaises(EnterpriseValidationError):
                        get_dashboard(enterprise_id)


if __name__ == "__main__":
    unittest.main()
