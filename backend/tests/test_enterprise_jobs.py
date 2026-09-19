import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import create_app
from app.db import get_db
from app.enterprise_console.errors import (
    EnterpriseNotFoundError,
    EnterpriseValidationError,
    ProviderConflictError,
    ProviderUnavailableError,
    ProviderValidationError,
)
from app.enterprise_console.jobs import (
    create_job,
    edit_job,
    get_job,
    list_jobs,
    sync_job_review_projection,
)
from app.enterprise_console.review import set_content_review_provider


class FakeReviewProvider:
    def __init__(self):
        self.records = {}
        self.calls = []
        self.submit_error = None
        self.edit_error = None
        self.get_error = None

    def submit_for_review(
        self,
        *,
        content_type,
        content_id,
        submitter_id,
        expected_version,
        payload,
    ):
        if self.submit_error is not None:
            raise self.submit_error
        record = {
            "content_type": content_type,
            "content_id": content_id,
            "review_status": "pending",
            "version": expected_version,
            "submitter_id": submitter_id,
            "rejection_opinion": None,
            "published_at": None,
        }
        self.records[content_id] = record
        self.calls.append(
            {
                "operation": "submit",
                "content_type": content_type,
                "content_id": content_id,
                "submitter_id": submitter_id,
                "expected_version": expected_version,
                "payload": dict(payload),
            }
        )
        return dict(record)

    def get_review_status(self, *, content_type, content_id):
        if self.get_error is not None:
            raise self.get_error
        record = self.records.get(content_id)
        return dict(record) if record is not None else None

    def approve(
        self,
        *,
        content_type,
        content_id,
        submitter_id,
        reviewer_id,
        reviewer_role,
        expected_version,
    ):
        record = dict(self.records[content_id])
        record["review_status"] = "approved"
        record["version"] = expected_version + 1
        record["published_at"] = "2026-09-18T12:00:00+08:00"
        record["rejection_opinion"] = None
        self.records[content_id] = record
        return dict(record)

    def reject(
        self,
        *,
        content_type,
        content_id,
        submitter_id,
        reviewer_id,
        reviewer_role,
        expected_version,
        opinion,
    ):
        record = dict(self.records[content_id])
        record["review_status"] = "rejected"
        record["version"] = expected_version + 1
        record["published_at"] = None
        record["rejection_opinion"] = opinion
        self.records[content_id] = record
        return dict(record)

    def edit(
        self,
        *,
        content_type,
        content_id,
        submitter_id,
        expected_version,
        payload,
    ):
        if self.edit_error is not None:
            raise self.edit_error
        record = dict(self.records[content_id])
        record["review_status"] = "pending"
        record["version"] = expected_version + 1
        record["published_at"] = None
        record["rejection_opinion"] = None
        self.records[content_id] = record
        self.calls.append(
            {
                "operation": "edit",
                "content_type": content_type,
                "content_id": content_id,
                "submitter_id": submitter_id,
                "expected_version": expected_version,
                "payload": dict(payload),
            }
        )
        return dict(record)


class TestEnterpriseJobs(unittest.TestCase):
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
                role="enterprise",
            )
            self.other_enterprise_id = self._insert_user(
                db,
                username="enterprise-2",
                role="enterprise",
            )
            self.category_id = self._insert_category(
                db,
                name="Agriculture Technician",
            )
            self.other_category_id = self._insert_category(
                db,
                name="Ecommerce Operator",
            )
            db.commit()

        self.provider = FakeReviewProvider()
        set_content_review_provider(self.app, self.provider)

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

    @staticmethod
    def _insert_category(db, *, name, is_active=1):
        return db.execute(
            """
            INSERT INTO interest_tags (
                group_key,
                name,
                sort_order,
                is_active
            )
            VALUES ('job', ?, 0, ?)
            """,
            (name, is_active),
        ).lastrowid

    def _payload(self, **overrides):
        payload = {
            "title": "Agriculture Technician",
            "salary": "6000-8000",
            "location": "Guangzhou",
            "category_id": self.category_id,
            "description": "Maintain agricultural equipment.",
        }
        payload.update(overrides)
        return payload

    def _approved_job(self):
        job = create_job(self.enterprise_id, self._payload())
        self.provider.approve(
            content_type="job_position",
            content_id=job["job_id"],
            submitter_id=self.enterprise_id,
            reviewer_id=9001,
            reviewer_role="admin",
            expected_version=job["version"],
        )
        return sync_job_review_projection(job["job_id"])

    def _rejected_job(self):
        job = create_job(self.enterprise_id, self._payload())
        self.provider.reject(
            content_type="job_position",
            content_id=job["job_id"],
            submitter_id=self.enterprise_id,
            reviewer_id=9001,
            reviewer_role="admin",
            expected_version=job["version"],
            opinion="Please add concrete responsibilities.",
        )
        return sync_job_review_projection(job["job_id"])

    def test_create_job_persists_pending_projection_and_exact_review_payload(self):
        with self.app.app_context():
            job = create_job(self.enterprise_id, self._payload())
            stored = get_db().execute(
                """
                SELECT job_id, enterprise_id, title, salary, location,
                       category_id, category_name, description,
                       review_status, version, rejection_opinion,
                       published_at, deleted_at
                FROM job_positions
                WHERE job_id = ?
                """,
                (job["job_id"],),
            ).fetchone()

            self.assertIsInstance(job["job_id"], str)
            self.assertTrue(job["job_id"])
            self.assertEqual(job["review_status"], "pending")
            self.assertEqual(job["version"], 1)
            self.assertEqual(job["published_at"], None)
            self.assertEqual(job["rejection_opinion"], None)
            self.assertEqual(dict(stored)["category_name"], "Agriculture Technician")
            self.assertEqual([job], list_jobs(self.enterprise_id))

        self.assertEqual(len(self.provider.calls), 1)
        call = self.provider.calls[0]
        self.assertEqual(call["operation"], "submit")
        self.assertEqual(call["content_type"], "job_position")
        self.assertEqual(call["submitter_id"], self.enterprise_id)
        self.assertEqual(call["expected_version"], 1)
        self.assertEqual(
            call["payload"],
            {
                "title": "Agriculture Technician",
                "salary": "6000-8000",
                "location": "Guangzhou",
                "category": self.category_id,
                "description": "Maintain agricultural equipment.",
            },
        )
        self.assertEqual(
            set(call["payload"]),
            {"title", "salary", "location", "category", "description"},
        )

    def test_pending_edit_advances_version_and_stays_pending(self):
        with self.app.app_context():
            job = create_job(self.enterprise_id, self._payload())
            edited = edit_job(
                self.enterprise_id,
                job["job_id"],
                job["version"],
                self._payload(title="Senior Agriculture Technician"),
            )

            self.assertEqual(edited["title"], "Senior Agriculture Technician")
            self.assertEqual(edited["review_status"], "pending")
            self.assertEqual(edited["version"], 2)
            self.assertIsNone(edited["published_at"])
            self.assertIsNone(edited["rejection_opinion"])
            self.assertEqual(edited, get_job(self.enterprise_id, job["job_id"]))

        edit_call = self.provider.calls[-1]
        self.assertEqual(edit_call["operation"], "edit")
        self.assertEqual(edit_call["expected_version"], 1)
        self.assertEqual(
            edit_call["payload"],
            {
                "title": "Senior Agriculture Technician",
                "salary": "6000-8000",
                "location": "Guangzhou",
                "category": self.category_id,
                "description": "Maintain agricultural equipment.",
            },
        )

    def test_pending_edit_without_changes_is_a_provider_free_noop(self):
        with self.app.app_context():
            job = create_job(self.enterprise_id, self._payload())
            before = get_job(self.enterprise_id, job["job_id"])
            call_count = len(self.provider.calls)

            edited = edit_job(
                self.enterprise_id,
                job["job_id"],
                job["version"],
                self._payload(),
            )

            self.assertEqual(edited, before)
            self.assertEqual(get_job(self.enterprise_id, job["job_id"]), before)

        self.assertEqual(len(self.provider.calls), call_count)

    def test_review_sync_projects_approval_with_publication_time(self):
        with self.app.app_context():
            job = self._approved_job()

            self.assertEqual(job["review_status"], "approved")
            self.assertEqual(job["version"], 2)
            self.assertEqual(job["published_at"], "2026-09-18T12:00:00+08:00")
            self.assertIsNone(job["rejection_opinion"])

    def test_review_sync_projects_rejection_and_opinion(self):
        with self.app.app_context():
            job = self._rejected_job()

            self.assertEqual(job["review_status"], "rejected")
            self.assertEqual(job["version"], 2)
            self.assertIsNone(job["published_at"])
            self.assertEqual(
                job["rejection_opinion"],
                "Please add concrete responsibilities.",
            )

    def test_editing_approved_job_returns_to_pending_and_unpublishes(self):
        with self.app.app_context():
            approved = self._approved_job()
            edited = edit_job(
                self.enterprise_id,
                approved["job_id"],
                approved["version"],
                self._payload(title="Updated Approved Job"),
            )

            self.assertEqual(edited["review_status"], "pending")
            self.assertEqual(edited["version"], 3)
            self.assertEqual(edited["title"], "Updated Approved Job")
            self.assertIsNone(edited["published_at"])
            self.assertIsNone(edited["rejection_opinion"])

    def test_editing_rejected_job_clears_opinion_and_returns_to_pending(self):
        with self.app.app_context():
            rejected = self._rejected_job()
            edited = edit_job(
                self.enterprise_id,
                rejected["job_id"],
                rejected["version"],
                self._payload(title="Resubmitted Job"),
            )

            self.assertEqual(edited["review_status"], "pending")
            self.assertEqual(edited["version"], 3)
            self.assertEqual(edited["title"], "Resubmitted Job")
            self.assertIsNone(edited["published_at"])
            self.assertIsNone(edited["rejection_opinion"])

    def test_old_expected_version_does_not_change_persisted_job(self):
        with self.app.app_context():
            job = create_job(self.enterprise_id, self._payload())
            edit_job(
                self.enterprise_id,
                job["job_id"],
                job["version"],
                self._payload(title="Current Title"),
            )
            before = get_db().execute(
                """
                SELECT review_status, version, title
                FROM job_positions
                WHERE job_id = ?
                """,
                (job["job_id"],),
            ).fetchone()
            call_count = len(self.provider.calls)

            with self.assertRaises(ProviderConflictError):
                edit_job(
                    self.enterprise_id,
                    job["job_id"],
                    1,
                    self._payload(title="Stale Title"),
                )

            after = get_db().execute(
                """
                SELECT review_status, version, title
                FROM job_positions
                WHERE job_id = ?
                """,
                (job["job_id"],),
            ).fetchone()

            self.assertEqual(dict(after), dict(before))
            self.assertEqual(len(self.provider.calls), call_count)

    def test_unavailable_provider_rolls_back_create(self):
        self.provider.submit_error = ProviderUnavailableError(
            "review unavailable"
        )

        with self.app.app_context():
            before = get_db().execute(
                "SELECT COUNT(*) FROM job_positions"
            ).fetchone()[0]

            with self.assertRaises(ProviderUnavailableError):
                create_job(self.enterprise_id, self._payload())

            after = get_db().execute(
                "SELECT COUNT(*) FROM job_positions"
            ).fetchone()[0]
            self.assertEqual(after, before)

    def test_unavailable_provider_rolls_back_edit(self):
        with self.app.app_context():
            job = create_job(self.enterprise_id, self._payload())
            before = get_db().execute(
                """
                SELECT review_status, version, title, published_at,
                       rejection_opinion
                FROM job_positions
                WHERE job_id = ?
                """,
                (job["job_id"],),
            ).fetchone()

        self.provider.edit_error = ProviderUnavailableError(
            "review unavailable"
        )

        with self.app.app_context():
            with self.assertRaises(ProviderUnavailableError):
                edit_job(
                    self.enterprise_id,
                    job["job_id"],
                    job["version"],
                    self._payload(title="Must Not Persist"),
                )

            after = get_db().execute(
                """
                SELECT review_status, version, title, published_at,
                       rejection_opinion
                FROM job_positions
                WHERE job_id = ?
                """,
                (job["job_id"],),
            ).fetchone()
            self.assertEqual(dict(after), dict(before))

    def test_job_operations_do_not_send_review_notifications(self):
        with patch(
            "app.messaging.events.emit_review_result"
        ) as emit_review_result:
            with self.app.app_context():
                job = create_job(self.enterprise_id, self._payload())
                edit_job(
                    self.enterprise_id,
                    job["job_id"],
                    job["version"],
                    self._payload(title="Edited Without Review Notice"),
                )
                self.provider.approve(
                    content_type="job_position",
                    content_id=job["job_id"],
                    submitter_id=self.enterprise_id,
                    reviewer_id=9001,
                    reviewer_role="admin",
                    expected_version=2,
                )
                sync_job_review_projection(job["job_id"])

        emit_review_result.assert_not_called()

    def test_jobs_are_scoped_to_the_owning_enterprise(self):
        with self.app.app_context():
            job = create_job(self.enterprise_id, self._payload())

            self.assertEqual(list_jobs(self.other_enterprise_id), [])
            with self.assertRaises(EnterpriseNotFoundError):
                get_job(self.other_enterprise_id, job["job_id"])
            with self.assertRaises(EnterpriseNotFoundError):
                edit_job(
                    self.other_enterprise_id,
                    job["job_id"],
                    job["version"],
                    self._payload(title="Cross Tenant"),
                )

    def test_payload_validation_rejects_blank_and_inactive_fields(self):
        with self.app.app_context():
            db = get_db()
            before = db.execute(
                "SELECT COUNT(*) FROM job_positions"
            ).fetchone()[0]

            with self.assertRaises(EnterpriseValidationError):
                create_job(
                    self.enterprise_id,
                    self._payload(title="   "),
                )

            inactive_category_id = self._insert_category(
                db,
                name="Inactive Category",
                is_active=0,
            )
            db.commit()
            with self.assertRaises(EnterpriseValidationError):
                create_job(
                    self.enterprise_id,
                    self._payload(category_id=inactive_category_id),
                )

            after = db.execute(
                "SELECT COUNT(*) FROM job_positions"
            ).fetchone()[0]
            self.assertEqual(after, before)

    def test_review_projection_rejects_mismatched_content_id(self):
        with self.app.app_context():
            job = create_job(self.enterprise_id, self._payload())
            record = dict(self.provider.records[job["job_id"]])
            record["content_id"] = "different-job"
            self.provider.records[job["job_id"]] = record

            with self.assertRaises(ProviderValidationError):
                sync_job_review_projection(job["job_id"])

            stored = get_db().execute(
                """
                SELECT review_status, version
                FROM job_positions
                WHERE job_id = ?
                """,
                (job["job_id"],),
            ).fetchone()
            self.assertEqual(
                dict(stored),
                {"review_status": "pending", "version": 1},
            )


if __name__ == "__main__":
    unittest.main()
