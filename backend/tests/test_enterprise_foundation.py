import sqlite3
import tempfile
import unittest
from pathlib import Path

from app import create_app
from app.db import get_db
from app.enterprise_console.errors import ProviderUnavailableError
from app.enterprise_console.providers import (
    DatabaseJobApplicationIntakeProvider,
    EmptyJobApplicationIntakeProvider,
    EmptyJobPositionProvider,
    configure_enterprise_providers,
    get_job_application_intake_provider,
    get_job_position_provider,
    set_job_application_intake_provider,
    set_job_position_provider,
)
from app.enterprise_console.review import (
    UnavailableContentReviewProvider,
    get_content_review_provider,
    set_content_review_provider,
)


class ReplacementJobProvider:
    def list_published_positions(self):
        return [{"job_id": "job-1"}]

    def get_published_position(self, *, job_id):
        return {"job_id": job_id} if job_id == "job-1" else None


class ReplacementReviewProvider:
    def submit_for_review(self, **kwargs):
        return {"review_status": "pending", "version": 1}

    def get_review_status(self, **kwargs):
        return None

    def approve(self, **kwargs):
        return {"review_status": "approved", "version": 2}

    def reject(self, **kwargs):
        return {"review_status": "rejected", "version": 2}

    def edit(self, **kwargs):
        return {"review_status": "pending", "version": 2}


class ReplacementApplicationProvider:
    def submit_application(self, **kwargs):
        return {"application_id": "application-1", **kwargs}


class TestEnterpriseFoundation(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(Path(self.temp_dir.name) / "test.db"),
                "SECRET_KEY": "test-only-secret",
            }
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    @staticmethod
    def _unique_index_columns(connection, table_name):
        indexes = connection.execute(
            f"PRAGMA index_list('{table_name}')"
        ).fetchall()
        return {
            tuple(
                row["name"]
                for row in connection.execute(
                    f"PRAGMA index_info('{index['name']}')"
                )
            )
            for index in indexes
            if index["unique"]
        }

    @staticmethod
    def _index_columns(connection, index_name):
        return tuple(
            row["name"]
            for row in connection.execute(
                f"PRAGMA index_info('{index_name}')"
            )
        )

    @staticmethod
    def _insert_user(connection, *, username, role):
        timestamp = "2026-09-19T10:00:00+08:00"
        cursor = connection.execute(
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

    @staticmethod
    def _insert_job_position(
        connection,
        *,
        job_id,
        enterprise_id,
        category_id,
    ):
        timestamp = "2026-09-19T10:00:00+08:00"
        connection.execute(
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
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                enterprise_id,
                "Test Position",
                "10000",
                "Guangzhou",
                category_id,
                "Test Job Category",
                "Test Description",
                "pending",
                1,
                timestamp,
                timestamp,
            ),
        )

    @staticmethod
    def _insert_job_application(
        connection,
        *,
        application_id,
        job_id,
        enterprise_id,
        student_id,
        idempotency_key,
    ):
        timestamp = "2026-09-19T10:00:00+08:00"
        connection.execute(
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
                idempotency_key,
                submitted_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                application_id,
                job_id,
                enterprise_id,
                student_id,
                "Test Student",
                "Test Position",
                "{}",
                "pending",
                idempotency_key,
                timestamp,
                timestamp,
            ),
        )

    @staticmethod
    def _insert_status_history(
        connection,
        *,
        application_id,
        sequence_no,
        actor_enterprise_id,
        event_id,
    ):
        connection.execute(
            """
            INSERT INTO job_application_status_history (
                application_id,
                sequence_no,
                previous_status,
                new_status,
                actor_enterprise_id,
                event_id,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                application_id,
                sequence_no,
                "pending",
                "viewed",
                actor_enterprise_id,
                event_id,
                "2026-09-19T10:00:00+08:00",
            ),
        )

    @staticmethod
    def _insert_outbox_event(
        connection,
        *,
        event_type,
        event_id,
    ):
        connection.execute(
            """
            INSERT INTO enterprise_notification_outbox (
                event_type,
                event_id,
                payload_json,
                created_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                event_type,
                event_id,
                "{}",
                "2026-09-19T10:00:00+08:00",
            ),
        )

    def _create_foundation_fixture(self, connection):
        enterprise_id = self._insert_user(
            connection,
            username="enterprise-1",
            role="enterprise",
        )
        student_1_id = self._insert_user(
            connection,
            username="student-1",
            role="student",
        )
        student_2_id = self._insert_user(
            connection,
            username="student-2",
            role="student",
        )
        category_id = connection.execute(
            """
            INSERT INTO interest_tags (
                group_key,
                name,
                sort_order,
                is_active
            )
            VALUES ('job', 'Test Job Category', 0, 1)
            """
        ).lastrowid

        self._insert_job_position(
            connection,
            job_id="job-1",
            enterprise_id=enterprise_id,
            category_id=category_id,
        )
        self._insert_job_position(
            connection,
            job_id="job-2",
            enterprise_id=enterprise_id,
            category_id=category_id,
        )
        self._insert_job_application(
            connection,
            application_id="application-1",
            job_id="job-1",
            enterprise_id=enterprise_id,
            student_id=student_1_id,
            idempotency_key="application-key-1",
        )
        self._insert_status_history(
            connection,
            application_id="application-1",
            sequence_no=1,
            actor_enterprise_id=enterprise_id,
            event_id="history-event-1",
        )
        self._insert_outbox_event(
            connection,
            event_type="application_submitted",
            event_id="outbox-event-1",
        )
        connection.commit()

        return {
            "enterprise_id": enterprise_id,
            "student_1_id": student_1_id,
            "student_2_id": student_2_id,
            "category_id": category_id,
        }

    def test_enterprise_tables_exist(self):
        expected = {
            "job_positions",
            "job_applications",
            "job_application_status_history",
            "enterprise_notification_outbox",
        }
        with self.app.app_context():
            names = {
                row["name"]
                for row in get_db().execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
        self.assertTrue(expected.issubset(names))

    def test_enterprise_schema_enforces_uniqueness(self):
        with self.app.app_context():
            db = get_db()
            fixture = self._create_foundation_fixture(db)
            position_indexes = self._unique_index_columns(
                db,
                "job_positions",
            )
            application_indexes = self._unique_index_columns(
                db,
                "job_applications",
            )
            history_indexes = self._unique_index_columns(
                db,
                "job_application_status_history",
            )
            outbox_indexes = self._unique_index_columns(
                db,
                "enterprise_notification_outbox",
            )

            self.assertIn(("job_id",), position_indexes)
            self.assertIn(("application_id",), application_indexes)
            self.assertIn(("student_id", "job_id"), application_indexes)
            self.assertIn(
                ("enterprise_id", "idempotency_key"),
                application_indexes,
            )
            self.assertIn(
                ("application_id", "sequence_no"),
                history_indexes,
            )
            self.assertIn(("event_id",), history_indexes)
            self.assertIn(("event_type", "event_id"), outbox_indexes)

            conflicts = (
                (
                    "job_positions.job_id",
                    lambda: self._insert_job_position(
                        db,
                        job_id="job-1",
                        enterprise_id=fixture["enterprise_id"],
                        category_id=fixture["category_id"],
                    ),
                ),
                (
                    "job_applications.application_id",
                    lambda: self._insert_job_application(
                        db,
                        application_id="application-1",
                        job_id="job-2",
                        enterprise_id=fixture["enterprise_id"],
                        student_id=fixture["student_2_id"],
                        idempotency_key="application-key-2",
                    ),
                ),
                (
                    "job_applications(student_id, job_id)",
                    lambda: self._insert_job_application(
                        db,
                        application_id="application-2",
                        job_id="job-1",
                        enterprise_id=fixture["enterprise_id"],
                        student_id=fixture["student_1_id"],
                        idempotency_key="application-key-2",
                    ),
                ),
                (
                    "job_applications(enterprise_id, idempotency_key)",
                    lambda: self._insert_job_application(
                        db,
                        application_id="application-3",
                        job_id="job-2",
                        enterprise_id=fixture["enterprise_id"],
                        student_id=fixture["student_2_id"],
                        idempotency_key="application-key-1",
                    ),
                ),
                (
                    "job_application_status_history("
                    "application_id, sequence_no)",
                    lambda: self._insert_status_history(
                        db,
                        application_id="application-1",
                        sequence_no=1,
                        actor_enterprise_id=fixture["enterprise_id"],
                        event_id="history-event-2",
                    ),
                ),
                (
                    "job_application_status_history.event_id",
                    lambda: self._insert_status_history(
                        db,
                        application_id="application-1",
                        sequence_no=2,
                        actor_enterprise_id=fixture["enterprise_id"],
                        event_id="history-event-1",
                    ),
                ),
                (
                    "enterprise_notification_outbox("
                    "event_type, event_id)",
                    lambda: self._insert_outbox_event(
                        db,
                        event_type="application_submitted",
                        event_id="outbox-event-1",
                    ),
                ),
            )

            for constraint, insert_conflict in conflicts:
                with self.subTest(constraint=constraint):
                    try:
                        with self.assertRaises(sqlite3.IntegrityError):
                            insert_conflict()
                    finally:
                        db.rollback()

    def test_enterprise_schema_enforces_foreign_keys(self):
        with self.app.app_context():
            db = get_db()
            fixture = self._create_foundation_fixture(db)
            self.assertEqual(
                1,
                db.execute("PRAGMA foreign_keys").fetchone()[0],
            )

            conflicts = (
                (
                    "job_positions.enterprise_id",
                    lambda: self._insert_job_position(
                        db,
                        job_id="job-missing-enterprise",
                        enterprise_id=fixture["enterprise_id"] + 10000,
                        category_id=fixture["category_id"],
                    ),
                ),
                (
                    "job_positions.category_id",
                    lambda: self._insert_job_position(
                        db,
                        job_id="job-missing-category",
                        enterprise_id=fixture["enterprise_id"],
                        category_id=fixture["category_id"] + 10000,
                    ),
                ),
                (
                    "job_applications.job_id",
                    lambda: self._insert_job_application(
                        db,
                        application_id="application-missing-job",
                        job_id="missing-job",
                        enterprise_id=fixture["enterprise_id"],
                        student_id=fixture["student_1_id"],
                        idempotency_key="missing-job-key",
                    ),
                ),
                (
                    "job_application_status_history.actor_enterprise_id",
                    lambda: self._insert_status_history(
                        db,
                        application_id="application-1",
                        sequence_no=2,
                        actor_enterprise_id=fixture["enterprise_id"] + 10000,
                        event_id="history-missing-actor",
                    ),
                ),
            )

            for foreign_key, insert_invalid in conflicts:
                with self.subTest(foreign_key=foreign_key):
                    try:
                        with self.assertRaises(
                            sqlite3.IntegrityError
                        ) as raised:
                            insert_invalid()
                        self.assertIn(
                            "FOREIGN KEY constraint failed",
                            str(raised.exception),
                        )
                    finally:
                        db.rollback()

    def test_enterprise_schema_indexes_have_planned_column_order(self):
        expected = {
            "idx_job_positions_enterprise_status": (
                "enterprise_id",
                "deleted_at",
                "review_status",
                "updated_at",
                "id",
            ),
            "idx_job_positions_public": (
                "deleted_at",
                "review_status",
                "published_at",
                "job_id",
            ),
            "idx_job_applications_enterprise": (
                "enterprise_id",
                "submitted_at",
                "application_id",
            ),
            "idx_job_applications_job_status": (
                "job_id",
                "status",
                "submitted_at",
                "application_id",
            ),
            "idx_enterprise_outbox_pending": (
                "status",
                "created_at",
                "id",
            ),
        }
        with self.app.app_context():
            db = get_db()
            for index_name, expected_columns in expected.items():
                with self.subTest(index=index_name):
                    self.assertEqual(
                        expected_columns,
                        self._index_columns(db, index_name),
                    )
            self.assertIn(
                ("application_id", "sequence_no"),
                self._unique_index_columns(
                    db,
                    "job_application_status_history",
                )
            )

    def test_enterprise_schema_rejects_invalid_outbox_event_type(self):
        with self.app.app_context():
            with self.assertRaises(sqlite3.IntegrityError):
                get_db().execute(
                    """
                    INSERT INTO enterprise_notification_outbox (
                        event_type,
                        event_id,
                        payload_json,
                        created_at
                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        "invalid_event",
                        "event-1",
                        "{}",
                        "2026-09-19T10:00:00+08:00",
                    ),
                )

    def test_default_providers_are_installed(self):
        with self.app.app_context():
            self.assertIsInstance(
                get_job_position_provider(),
                EmptyJobPositionProvider,
            )
            self.assertIsInstance(
                get_job_application_intake_provider(),
                DatabaseJobApplicationIntakeProvider,
            )
            self.assertIsInstance(
                get_content_review_provider(),
                UnavailableContentReviewProvider,
            )

    def test_default_providers_expose_placeholder_behavior(self):
        with self.app.app_context():
            position_provider = get_job_position_provider()
            self.assertEqual(
                [],
                position_provider.list_published_positions(),
            )
            self.assertIsNone(
                position_provider.get_published_position(
                    job_id="missing-job",
                )
            )

            with self.assertRaises(ProviderUnavailableError):
                EmptyJobApplicationIntakeProvider().submit_application(
                    job_id="job-1",
                    student_id=1,
                    resume_snapshot={"summary": "resume"},
                    skill_profile_snapshot=None,
                    idempotency_key="application-1",
                )
            with self.assertRaises(ProviderUnavailableError):
                get_content_review_provider().get_review_status()

    def test_providers_are_replaceable(self):
        job_provider = ReplacementJobProvider()
        application_provider = ReplacementApplicationProvider()
        review_provider = ReplacementReviewProvider()
        set_job_position_provider(self.app, job_provider)
        set_job_application_intake_provider(
            self.app,
            application_provider,
        )
        set_content_review_provider(self.app, review_provider)

        with self.app.app_context():
            self.assertIs(get_job_position_provider(), job_provider)
            self.assertIs(
                get_job_application_intake_provider(),
                application_provider,
            )
            self.assertIs(get_content_review_provider(), review_provider)

    def test_configure_enterprise_providers_installs_all_providers(self):
        job_provider = ReplacementJobProvider()
        application_provider = ReplacementApplicationProvider()
        review_provider = ReplacementReviewProvider()

        configure_enterprise_providers(
            self.app,
            job_position_provider=job_provider,
            job_application_intake_provider=application_provider,
            content_review_provider=review_provider,
        )

        with self.app.app_context():
            self.assertIs(get_job_position_provider(), job_provider)
            self.assertIs(
                get_job_application_intake_provider(),
                application_provider,
            )
            self.assertIs(get_content_review_provider(), review_provider)


if __name__ == "__main__":
    unittest.main()
