import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from werkzeug.security import generate_password_hash

from app import create_app
from app.admin_console.content_review_provider import (
    DatabaseContentReviewProvider,
)
from app.admin_console.errors import (
    ProviderAccessDeniedError,
    ProviderConflictError,
    ProviderNotFoundError,
    ProviderValidationError,
)
from app.admin_console.providers import configure_admin_providers
from app.db import get_db


COMMON_REVIEW_FIELDS = {
    "content_type",
    "content_id",
    "submitter_id",
    "review_status",
    "version",
    "rejection_opinion",
    "published_at",
    "created_at",
    "updated_at",
}


class AdminContentReviewTests(unittest.TestCase):
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
            self.teacher_id = self._insert_user(
                db,
                "teacher",
                "teacher",
            )
            self.enterprise_id = self._insert_user(
                db,
                "enterprise",
                "enterprise",
            )
            self.admin_id = self._insert_user(db, "admin", "admin")
            db.execute(
                """
                INSERT INTO interest_tags (
                    group_key, name, sort_order, is_active
                )
                VALUES ('job', '农业运营', 1, 1)
                """
            )
            self.category_id = int(
                db.execute(
                    """
                    SELECT id
                    FROM interest_tags
                    WHERE name = '农业运营'
                    """
                ).fetchone()["id"]
            )
            db.execute(
                """
                INSERT INTO courses (
                    id, title, direction, status, duration_seconds,
                    media_url, summary, teacher_name, teacher_id, version,
                    media_source_type, content_tags_json, created_at,
                    updated_at
                )
                VALUES (
                    41, '荔枝保果', 'agriculture', 'draft', 300,
                    'https://example.test/course.mp4', '课程简介',
                    'teacher', ?, 1, 'external_url', '[]',
                    '2026-09-20T09:00:00+08:00',
                    '2026-09-20T09:00:00+08:00'
                )
                """,
                (self.teacher_id,),
            )
            db.execute(
                """
                INSERT INTO job_positions (
                    job_id, enterprise_id, title, salary, location,
                    category_id, category_name, description, review_status,
                    version, created_at, updated_at
                )
                VALUES (
                    'job-1', ?, '农业技术员', '5000-7000', '广州',
                    ?, '农业运营', '负责农业技术指导', 'pending', 1,
                    '2026-09-20T09:00:00+08:00',
                    '2026-09-20T09:00:00+08:00'
                )
                """,
                (self.enterprise_id, self.category_id),
            )
            db.commit()
        self.provider = DatabaseContentReviewProvider()

    def tearDown(self):
        self.temp_dir.cleanup()

    @staticmethod
    def _insert_user(db, username, role):
        cursor = db.execute(
            """
            INSERT INTO users (
                username, password_hash, name, role, is_enabled,
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?, 1, ?, ?)
            """,
            (
                username,
                generate_password_hash("password8"),
                username,
                role,
                "2026-09-20T09:00:00+08:00",
                "2026-09-20T09:00:00+08:00",
            ),
        )
        return int(cursor.lastrowid)

    def _submit_job(self, payload=None):
        return self.provider.submit_for_review(
            content_type="job_position",
            content_id="job-1",
            submitter_id=self.enterprise_id,
            expected_version=1,
            payload=payload or {"title": "农业技术员"},
        )

    def _record_row(self, content_type, content_id):
        return get_db().execute(
            """
            SELECT *
            FROM content_review_records
            WHERE content_type = ? AND content_id = ?
            """,
            (content_type, content_id),
        ).fetchone()

    def _job_row(self):
        return get_db().execute(
            """
            SELECT *
            FROM job_positions
            WHERE job_id = 'job-1'
            """
        ).fetchone()

    def _outbox_rows(self):
        return get_db().execute(
            """
            SELECT *
            FROM admin_notification_outbox
            ORDER BY id
            """
        ).fetchall()

    def test_provider_registry_accepts_content_review_override(self):
        replacement = object()

        configure_admin_providers(self.app, content_review=replacement)

        self.assertIs(
            self.app.extensions["content_review_provider"],
            replacement,
        )

    def test_submit_requires_persisted_owning_record_and_common_shape(self):
        with self.app.app_context():
            course_count = int(
                get_db().execute("SELECT COUNT(*) FROM courses").fetchone()[0]
            )
            with self.assertRaises(ProviderNotFoundError):
                self.provider.submit_for_review(
                    content_type="course_video",
                    content_id="404",
                    submitter_id=self.teacher_id,
                    expected_version=1,
                    payload={"title": "不存在"},
                )

            self.assertEqual(
                get_db()
                .execute("SELECT COUNT(*) FROM courses")
                .fetchone()[0],
                course_count,
            )

            record = self.provider.submit_for_review(
                content_type="course_video",
                content_id="41",
                submitter_id=self.teacher_id,
                expected_version=1,
                payload={"title": "荔枝保果"},
            )

            self.assertEqual(set(record), COMMON_REVIEW_FIELDS)
            self.assertEqual(record["content_type"], "course_video")
            self.assertEqual(record["content_id"], "41")
            self.assertEqual(record["review_status"], "pending")
            self.assertEqual(record["version"], 1)
            self.assertIsNone(record["rejection_opinion"])
            self.assertIsNone(record["published_at"])

    def test_job_state_machine_updates_projection_and_clears_stale_fields(self):
        with self.app.app_context():
            pending = self._submit_job()
            rejected = self.provider.reject(
                content_type="job_position",
                content_id="job-1",
                submitter_id=self.enterprise_id,
                reviewer_id=self.admin_id,
                reviewer_role="admin",
                expected_version=pending["version"],
                opinion="  补充薪资范围  ",
            )
            self.assertEqual(rejected["review_status"], "rejected")
            self.assertEqual(rejected["version"], 2)
            self.assertEqual(rejected["rejection_opinion"], "补充薪资范围")
            self.assertIsNone(rejected["published_at"])

            rejected_job = self._job_row()
            self.assertEqual(rejected_job["review_status"], "rejected")
            self.assertEqual(rejected_job["version"], 2)
            self.assertEqual(
                rejected_job["rejection_opinion"],
                "补充薪资范围",
            )

            edited = self.provider.edit(
                content_type="job_position",
                content_id="job-1",
                submitter_id=self.enterprise_id,
                expected_version=rejected["version"],
                payload={"title": "农业技术员", "salary": "5000-7000"},
            )
            self.assertEqual(edited["review_status"], "pending")
            self.assertEqual(edited["version"], 3)
            self.assertIsNone(edited["rejection_opinion"])
            self.assertIsNone(edited["published_at"])

            approved = self.provider.approve(
                content_type="job_position",
                content_id="job-1",
                submitter_id=self.enterprise_id,
                reviewer_id=self.admin_id,
                reviewer_role="super_admin",
                expected_version=edited["version"],
            )
            self.assertEqual(approved["review_status"], "approved")
            self.assertEqual(approved["version"], 4)
            self.assertIsNotNone(approved["published_at"])
            self.assertIsNone(approved["rejection_opinion"])

            edited_again = self.provider.edit(
                content_type="job_position",
                content_id="job-1",
                submitter_id=self.enterprise_id,
                expected_version=approved["version"],
                payload={"title": "高级农业技术员"},
            )
            self.assertEqual(edited_again["review_status"], "pending")
            self.assertEqual(edited_again["version"], 5)
            self.assertIsNone(edited_again["published_at"])

            projected = self._job_row()
            self.assertEqual(projected["review_status"], "pending")
            self.assertEqual(projected["version"], 5)
            self.assertIsNone(projected["published_at"])
            self.assertIsNone(projected["rejection_opinion"])

    def test_rejected_resubmit_reopens_pending_even_with_same_payload(self):
        with self.app.app_context():
            payload = {"title": "农业技术员"}
            pending = self._submit_job(payload)
            rejected = self.provider.reject(
                content_type="job_position",
                content_id="job-1",
                submitter_id=self.enterprise_id,
                reviewer_id=self.admin_id,
                reviewer_role="admin",
                expected_version=pending["version"],
                opinion="补充职责",
            )

            resubmitted = self.provider.submit_for_review(
                content_type="job_position",
                content_id="job-1",
                submitter_id=self.enterprise_id,
                expected_version=rejected["version"],
                payload=payload,
            )

            self.assertEqual(resubmitted["review_status"], "pending")
            self.assertEqual(resubmitted["version"], 3)
            self.assertIsNone(resubmitted["rejection_opinion"])
            self.assertIsNone(resubmitted["published_at"])

    def test_noop_edit_returns_original_record_and_creates_no_round(self):
        with self.app.app_context():
            payload = {"title": "农业技术员"}
            submitted = self._submit_job(payload)

            unchanged = self.provider.edit(
                content_type="job_position",
                content_id="job-1",
                submitter_id=self.enterprise_id,
                expected_version=submitted["version"],
                payload=dict(payload),
            )

            self.assertEqual(unchanged, submitted)
            self.assertEqual(self._record_row("job_position", "job-1")["version"], 1)
            self.assertEqual(self._outbox_rows(), [])

    def test_reject_validates_trimmed_opinion_without_mutation(self):
        with self.app.app_context():
            submitted = self._submit_job()

            for opinion in ("", "   ", "x" * 501):
                with self.subTest(opinion=opinion):
                    with self.assertRaises(ProviderValidationError):
                        self.provider.reject(
                            content_type="job_position",
                            content_id="job-1",
                            submitter_id=self.enterprise_id,
                            reviewer_id=self.admin_id,
                            reviewer_role="admin",
                            expected_version=submitted["version"],
                            opinion=opinion,
                        )

                    current = self._record_row("job_position", "job-1")
                    self.assertEqual(current["review_status"], "pending")
                    self.assertEqual(current["version"], submitted["version"])

            self.assertEqual(self._outbox_rows(), [])

    def test_approve_sets_publication_and_delivers_exactly_once(self):
        with self.app.app_context():
            submitted = self._submit_job()

            with patch(
                "app.messaging.events.emit_review_result"
            ) as emit_review_result:
                approved = self.provider.approve(
                    content_type="job_position",
                    content_id="job-1",
                    submitter_id=self.enterprise_id,
                    reviewer_id=self.admin_id,
                    reviewer_role="admin",
                    expected_version=submitted["version"],
                )

            self.assertEqual(approved["review_status"], "approved")
            self.assertIsNotNone(approved["published_at"])
            emit_review_result.assert_called_once_with(
                event_id="review:job_position:job-1:v1:approve",
                submitter_id=self.enterprise_id,
                content_type="job_position",
                content_id="job-1",
                approved=True,
                opinion=None,
            )

            rows = self._outbox_rows()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["status"], "sent")
            self.assertEqual(
                rows[0]["event_id"],
                "review:job_position:job-1:v1:approve",
            )

    def test_notification_failure_does_not_rollback_approved_state(self):
        with self.app.app_context():
            submitted = self._submit_job()

            with patch(
                "app.messaging.events.emit_review_result",
                side_effect=RuntimeError("delivery unavailable"),
            ):
                approved = self.provider.approve(
                    content_type="job_position",
                    content_id="job-1",
                    submitter_id=self.enterprise_id,
                    reviewer_id=self.admin_id,
                    reviewer_role="admin",
                    expected_version=submitted["version"],
                )

            self.assertEqual(approved["review_status"], "approved")
            self.assertEqual(self._job_row()["review_status"], "approved")
            outbox = self._outbox_rows()[0]
            self.assertEqual(outbox["status"], "failed")
            self.assertEqual(outbox["attempts"], 1)
            self.assertIn("delivery unavailable", outbox["last_error"])

    def test_stale_version_conflicts_without_state_or_outbox_change(self):
        with self.app.app_context():
            submitted = self._submit_job()
            before = dict(self._record_row("job_position", "job-1"))

            with self.assertRaises(ProviderConflictError):
                self.provider.approve(
                    content_type="job_position",
                    content_id="job-1",
                    submitter_id=self.enterprise_id,
                    reviewer_id=self.admin_id,
                    reviewer_role="admin",
                    expected_version=submitted["version"] + 1,
                )

            after = dict(self._record_row("job_position", "job-1"))
            self.assertEqual(after, before)
            self.assertEqual(self._outbox_rows(), [])

    def test_invalid_content_type_and_reviewer_role_are_rejected(self):
        with self.app.app_context():
            submitted = self._submit_job()

            with self.assertRaises(ProviderValidationError):
                self.provider.approve(
                    content_type="handcraft_teaching_video",
                    content_id="video-1",
                    submitter_id=self.teacher_id,
                    reviewer_id=self.admin_id,
                    reviewer_role="admin",
                    expected_version=1,
                )

            with self.assertRaises(ProviderAccessDeniedError):
                self.provider.approve(
                    content_type="job_position",
                    content_id="job-1",
                    submitter_id=self.enterprise_id,
                    reviewer_id=self.admin_id,
                    reviewer_role="student",
                    expected_version=submitted["version"],
                )

    def test_list_review_items_is_deterministic_and_filters_domain_rows(self):
        with self.app.app_context():
            self._submit_job()
            self.provider.submit_for_review(
                content_type="course_video",
                content_id="41",
                submitter_id=self.teacher_id,
                expected_version=1,
                payload={"title": "荔枝保果"},
            )
            db = get_db()
            db.execute(
                """
                INSERT INTO content_review_records (
                    content_type, content_id, submitter_id, review_status,
                    version, payload_json, created_at, updated_at
                )
                VALUES (
                    'course_video', 'payload-only', ?, 'pending', 1, '{}',
                    '2026-09-20T09:00:00+08:00',
                    '2026-09-20T09:00:00+08:00'
                )
                """,
                (self.teacher_id,),
            )
            db.execute(
                """
                UPDATE content_review_records
                SET updated_at = CASE
                    WHEN content_type = 'course_video'
                         AND content_id = '41'
                    THEN '2026-09-20T09:00:00+08:00'
                    WHEN content_type = 'job_position'
                         AND content_id = 'job-1'
                    THEN '2026-09-20T10:00:00+08:00'
                    ELSE updated_at
                END
                WHERE (
                    content_type = 'course_video' AND content_id = '41'
                ) OR (
                    content_type = 'job_position' AND content_id = 'job-1'
                )
                """
            )
            db.commit()

            items = self.provider.list_review_items()

            self.assertEqual(
                [item["content_id"] for item in items],
                ["41", "job-1"],
            )
            self.assertEqual(
                {item["content_type"] for item in items},
                {"course_video", "job_position"},
            )
            self.assertEqual(
                self.provider.list_review_items("job_position")[0][
                    "content_id"
                ],
                "job-1",
            )
            self.assertTrue(
                {"title", "owner_id", "owner_name"}.issubset(items[0])
            )

            db.execute(
                """
                UPDATE job_positions
                SET deleted_at = '2026-09-20T11:00:00+08:00'
                WHERE job_id = 'job-1'
                """
            )
            db.commit()

            self.assertEqual(
                [
                    item["content_id"]
                    for item in self.provider.list_review_items(
                        "job_position"
                    )
                ],
                [],
            )

    def test_record_payload_is_canonical_and_get_status_reads_it(self):
        with self.app.app_context():
            record = self.provider.submit_for_review(
                content_type="job_position",
                content_id="job-1",
                submitter_id=self.enterprise_id,
                expected_version=1,
                payload={"salary": "5000-7000", "title": "农业技术员"},
            )

            row = self._record_row("job_position", "job-1")
            self.assertEqual(
                json.loads(row["payload_json"]),
                {"salary": "5000-7000", "title": "农业技术员"},
            )
            self.assertEqual(
                self.provider.get_review_status(
                    content_type="job_position",
                    content_id="job-1",
                ),
                record,
            )
            self.assertIsNone(
                self.provider.get_review_status(
                    content_type="job_position",
                    content_id="missing",
                )
            )


if __name__ == "__main__":
    unittest.main()
