import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import create_app
from app.db import get_db
from app.enterprise_console import jobs, providers
from app.enterprise_console.errors import ProviderError
from app.enterprise_console.providers import set_job_position_provider


class ReplacementJobPositionProvider:
    def list_published_positions(self):
        return [{"job_id": "replacement-job"}]

    def get_published_position(self, *, job_id):
        return {"job_id": job_id} if job_id == "replacement-job" else None


class TestEnterpriseJobPositionProvider(unittest.TestCase):
    FROZEN_FIELDS = {
        "job_id",
        "enterprise_id",
        "enterprise_name",
        "title",
        "salary",
        "location",
        "category_id",
        "category_name",
        "description",
        "review_status",
        "version",
        "published_at",
        "updated_at",
    }

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
            db = get_db()
            self.enterprise_id = self._insert_user(
                db,
                username="enterprise-1",
                name="YueXiang Cooperative",
            )
            self.category_id = self._insert_category(
                db,
                name="Agriculture Technician",
            )
            self._insert_job(
                db,
                job_id="job-new",
                title="Senior Agriculture Technician",
                salary="8000-10000",
                location="Guangzhou",
                description="Maintain smart irrigation systems.",
                review_status="approved",
                version=3,
                published_at="2026-09-19T12:00:00+08:00",
                updated_at="2026-09-19T12:30:00+08:00",
            )
            self._insert_job(
                db,
                job_id="job-old",
                title="Ecommerce Operations Assistant",
                salary="6500-8000",
                location="Shenzhen",
                description="Support online store operations.",
                review_status="approved",
                version=2,
                published_at="2026-09-18T12:00:00+08:00",
                updated_at="2026-09-18T12:30:00+08:00",
            )
            self._insert_job(
                db,
                job_id="job-pending",
                title="Pending Position",
                salary="5000-7000",
                location="Foshan",
                description="Pending review.",
                review_status="pending",
                version=1,
                published_at="2026-09-21T12:00:00+08:00",
                updated_at="2026-09-19T12:30:00+08:00",
            )
            self._insert_job(
                db,
                job_id="job-rejected",
                title="Rejected Position",
                salary="5000-7000",
                location="Dongguan",
                description="Rejected review.",
                review_status="rejected",
                version=1,
                published_at="2026-09-21T12:00:00+08:00",
                updated_at="2026-09-19T12:30:00+08:00",
            )
            self._insert_job(
                db,
                job_id="job-deleted",
                title="Deleted Position",
                salary="5000-7000",
                location="Zhuhai",
                description="Deleted after approval.",
                review_status="approved",
                version=2,
                published_at="2026-09-22T12:00:00+08:00",
                updated_at="2026-09-19T12:30:00+08:00",
                deleted_at="2026-09-19T13:00:00+08:00",
            )
            self._insert_job(
                db,
                job_id="job-null-published",
                title="Missing Publication",
                salary="5000-7000",
                location="Jiangmen",
                description="Approved without publication time.",
                review_status="approved",
                version=2,
                published_at=None,
                updated_at="2026-09-19T12:30:00+08:00",
            )
            self._insert_job(
                db,
                job_id="job-blank-published",
                title="Blank Publication",
                salary="5000-7000",
                location="Zhaoqing",
                description="Approved with blank publication time.",
                review_status="approved",
                version=2,
                published_at="   ",
                updated_at="2026-09-19T12:30:00+08:00",
            )
            self._insert_job(
                db,
                job_id="job-invalid-title",
                title="   ",
                salary="5000-7000",
                location="Huizhou",
                description="Invalid title must be omitted.",
                review_status="approved",
                version=2,
                published_at="2026-09-23T12:00:00+08:00",
                updated_at="2026-09-19T12:30:00+08:00",
            )
            db.commit()

    def tearDown(self):
        self.temp_dir.cleanup()

    @staticmethod
    def _insert_user(db, *, username, name):
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
            VALUES (?, ?, ?, 'enterprise', 1, ?, ?)
            """,
            (
                username,
                "test-password-hash",
                name,
                timestamp,
                timestamp,
            ),
        ).lastrowid

    @staticmethod
    def _insert_category(db, *, name):
        return db.execute(
            """
            INSERT INTO interest_tags (
                group_key,
                name,
                sort_order,
                is_active
            )
            VALUES ('job', ?, 0, 1)
            """,
            (name,),
        ).lastrowid

    def _insert_job(
        self,
        db,
        *,
        job_id,
        title,
        salary,
        location,
        description,
        review_status,
        version,
        published_at,
        updated_at,
        deleted_at=None,
    ):
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
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                self.enterprise_id,
                title,
                salary,
                location,
                self.category_id,
                "Agriculture Technician",
                description,
                review_status,
                version,
                published_at,
                deleted_at,
                "2026-09-19T10:00:00+08:00",
                updated_at,
            ),
        )

    def test_list_published_positions_filters_orders_and_frozen_shape(self):
        provider = providers.DatabaseJobPositionProvider()

        with self.app.app_context():
            positions = provider.list_published_positions()
            self.assertEqual(
                [item["job_id"] for item in positions],
                ["job-new", "job-old"],
            )

        expected = {
            "job_id": "job-old",
            "enterprise_id": self.enterprise_id,
            "enterprise_name": "YueXiang Cooperative",
            "title": "Ecommerce Operations Assistant",
            "salary": "6500-8000",
            "location": "Shenzhen",
            "category_id": self.category_id,
            "category_name": "Agriculture Technician",
            "description": "Support online store operations.",
            "review_status": "approved",
            "version": 2,
            "published_at": "2026-09-18T12:00:00+08:00",
            "updated_at": "2026-09-18T12:30:00+08:00",
        }
        self.assertEqual(positions[1], expected)
        self.assertEqual(set(positions[1]), self.FROZEN_FIELDS)
        self.assertNotIn("id", positions[1])
        self.assertIsInstance(positions[1]["enterprise_id"], int)
        self.assertIsInstance(positions[1]["category_id"], int)
        self.assertIsInstance(positions[1]["version"], int)

    def test_get_published_position_rejects_every_non_visible_state(self):
        provider = providers.DatabaseJobPositionProvider()

        with self.app.app_context():
            position = provider.get_published_position(job_id="job-old")
            self.assertEqual(position["title"], "Ecommerce Operations Assistant")
            self.assertEqual(set(position), self.FROZEN_FIELDS)

            for job_id in (
                "job-new-but-not-authorized",
                "job-pending",
                "job-rejected",
                "job-deleted",
                "job-null-published",
                "job-blank-published",
                "job-invalid-title",
                "",
            ):
                with self.subTest(job_id=job_id):
                    self.assertIsNone(
                        provider.get_published_position(job_id=job_id)
                    )

    def test_default_registration_uses_database_provider(self):
        with self.app.app_context():
            provider = providers.get_job_position_provider()
            self.assertIsInstance(
                provider,
                providers.DatabaseJobPositionProvider,
            )
            self.assertEqual(
                [
                    item["job_id"]
                    for item in provider.list_published_positions()
                ],
                ["job-new", "job-old"],
            )

    def test_replacement_provider_uses_single_registration_slot(self):
        replacement = ReplacementJobPositionProvider()

        set_job_position_provider(self.app, replacement)

        with self.app.app_context():
            self.assertIs(
                providers.get_job_position_provider(),
                replacement,
            )

    def test_database_errors_are_wrapped_as_provider_errors(self):
        provider = providers.DatabaseJobPositionProvider()

        with patch(
            "app.enterprise_console.jobs.get_db",
            side_effect=sqlite3.OperationalError("database unavailable"),
        ):
            with self.app.app_context():
                operations = (
                    lambda: provider.list_published_positions(),
                    lambda: provider.get_published_position(job_id="job-old"),
                )
                for operation in operations:
                    with self.subTest(operation=operation):
                        with self.assertRaises(ProviderError) as raised:
                            operation()
                        self.assertEqual(
                            raised.exception.code,
                            "provider_unavailable",
                        )


if __name__ == "__main__":
    unittest.main()
