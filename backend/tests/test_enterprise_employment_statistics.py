import tempfile
import unittest
from pathlib import Path

from app import create_app
from app.db import get_db
from app.enterprise_console import (
    DatabaseEmploymentStatisticsProvider,
    get_employment_statistics_provider,
    get_employment_statistics_snapshot,
    install_default_enterprise_services,
    set_employment_statistics_provider,
)


class UnavailableEmploymentStatisticsProvider:
    def get_active_job_count(self):
        return None

    def get_cumulative_application_count(self):
        return None


class TestEnterpriseEmploymentStatistics(unittest.TestCase):
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
            VALUES ('job', 'Employment Statistics', 0, 1)
            """
        ).lastrowid

    @staticmethod
    def _insert_job(
        db,
        *,
        job_id,
        enterprise_id,
        category_id,
        review_status,
        published_at,
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
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 2, ?, ?, ?, ?)
            """,
            (
                job_id,
                enterprise_id,
                "Employment Statistics Position",
                "8000-10000",
                "Guangzhou",
                category_id,
                "Employment Statistics",
                "Test position",
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
    ):
        timestamp = "2026-09-19T10:00:00+08:00"
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
                idempotency_key,
                submitted_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, '{}', 'pending', 1, ?, ?, ?)
            """,
            (
                application_id,
                job_id,
                enterprise_id,
                student_id,
                f"Student {student_id}",
                "Employment Statistics Position",
                application_id,
                timestamp,
                timestamp,
            ),
        )

    def _seed_two_enterprise_platform(self, db):
        enterprise_a_id = self._insert_user(
            db,
            username="enterprise-a",
            role="enterprise",
        )
        enterprise_b_id = self._insert_user(
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
            for index in range(1, 6)
        ]
        category_id = self._insert_category(db)

        self._insert_job(
            db,
            job_id="job-a-active",
            enterprise_id=enterprise_a_id,
            category_id=category_id,
            review_status="approved",
            published_at="2026-09-19T12:00:00+08:00",
        )
        self._insert_job(
            db,
            job_id="job-b-active-1",
            enterprise_id=enterprise_b_id,
            category_id=category_id,
            review_status="approved",
            published_at="2026-09-19T12:00:00+08:00",
        )
        self._insert_job(
            db,
            job_id="job-b-active-2",
            enterprise_id=enterprise_b_id,
            category_id=category_id,
            review_status="approved",
            published_at="2026-09-19T12:00:00+08:00",
        )
        self._insert_job(
            db,
            job_id="job-pending",
            enterprise_id=enterprise_a_id,
            category_id=category_id,
            review_status="pending",
            published_at="2026-09-19T12:00:00+08:00",
        )
        self._insert_job(
            db,
            job_id="job-rejected",
            enterprise_id=enterprise_a_id,
            category_id=category_id,
            review_status="rejected",
            published_at="2026-09-19T12:00:00+08:00",
        )
        self._insert_job(
            db,
            job_id="job-deleted",
            enterprise_id=enterprise_b_id,
            category_id=category_id,
            review_status="approved",
            published_at="2026-09-19T12:00:00+08:00",
            deleted_at="2026-09-19T13:00:00+08:00",
        )
        self._insert_job(
            db,
            job_id="job-null-published",
            enterprise_id=enterprise_b_id,
            category_id=category_id,
            review_status="approved",
            published_at=None,
        )
        self._insert_job(
            db,
            job_id="job-blank-published",
            enterprise_id=enterprise_b_id,
            category_id=category_id,
            review_status="approved",
            published_at="   ",
        )

        applications = (
            ("application-a-1", "job-a-active", enterprise_a_id),
            ("application-a-2", "job-a-active", enterprise_a_id),
            ("application-b-1", "job-b-active-1", enterprise_b_id),
            ("application-b-2", "job-b-active-2", enterprise_b_id),
            ("application-b-3", "job-b-active-2", enterprise_b_id),
        )
        for index, (
            application_id,
            job_id,
            enterprise_id,
        ) in enumerate(applications):
            self._insert_application(
                db,
                application_id=application_id,
                job_id=job_id,
                enterprise_id=enterprise_id,
                student_id=student_ids[index],
            )
        db.commit()

    def test_empty_platform_reports_zero_counts_as_available_source(self):
        with self.app.app_context():
            provider = DatabaseEmploymentStatisticsProvider()

            self.assertIsInstance(
                get_employment_statistics_provider(),
                DatabaseEmploymentStatisticsProvider,
            )
            self.assertEqual(provider.get_active_job_count(), 0)
            self.assertEqual(
                provider.get_cumulative_application_count(),
                0,
            )
            self.assertEqual(
                get_employment_statistics_snapshot(),
                {
                    "active_job_count": 0,
                    "cumulative_application_count": 0,
                    "available": True,
                },
            )

    def test_counts_are_platform_wide_and_aggregate_two_enterprises(self):
        with self.app.app_context():
            self._seed_two_enterprise_platform(get_db())
            provider = DatabaseEmploymentStatisticsProvider()

            self.assertEqual(provider.get_active_job_count(), 3)
            self.assertEqual(
                provider.get_cumulative_application_count(),
                5,
            )
            self.assertEqual(
                get_employment_statistics_snapshot(),
                {
                    "active_job_count": 3,
                    "cumulative_application_count": 5,
                    "available": True,
                },
            )

    def test_unavailable_provider_preserves_none_contract(self):
        unavailable = UnavailableEmploymentStatisticsProvider()
        set_employment_statistics_provider(self.app, unavailable)

        with self.app.app_context():
            self.assertIs(
                self.app.extensions.get(
                    "government_employment_statistics_provider"
                ),
                unavailable,
            )
            self.assertNotIn(
                "employment_statistics_provider",
                self.app.extensions,
            )
            self.assertIs(
                get_employment_statistics_provider(),
                unavailable,
            )
            self.assertEqual(
                get_employment_statistics_snapshot(),
                {
                    "active_job_count": None,
                    "cumulative_application_count": None,
                    "available": False,
                },
            )

    def test_default_install_preserves_provider_in_real_slot(self):
        unavailable = UnavailableEmploymentStatisticsProvider()
        self.app.extensions.pop(
            "employment_statistics_provider",
            None,
        )
        self.app.extensions[
            "government_employment_statistics_provider"
        ] = unavailable

        install_default_enterprise_services(self.app)

        self.assertIs(
            self.app.extensions.get(
                "government_employment_statistics_provider"
            ),
            unavailable,
        )
        self.assertNotIn(
            "employment_statistics_provider",
            self.app.extensions,
        )

    def test_provider_exposes_only_the_frozen_consumer_methods(self):
        provider = DatabaseEmploymentStatisticsProvider()
        public_methods = {
            name
            for name in dir(provider)
            if not name.startswith("_")
            and callable(getattr(provider, name))
        }

        self.assertEqual(
            public_methods,
            {
                "get_active_job_count",
                "get_cumulative_application_count",
            },
        )


if __name__ == "__main__":
    unittest.main()
