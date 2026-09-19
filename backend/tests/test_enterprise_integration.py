from __future__ import annotations

import inspect
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from app import create_app
from app.db import get_db
from app.enterprise_console import (
    seed_enterprise_console_fixtures,
)
from app.enterprise_console.applications import (
    change_application_status,
    get_application,
    list_applications,
)
from app.enterprise_console.dashboard import get_dashboard
from app.enterprise_console.jobs import (
    JOB_REVIEW_CONTENT_TYPE,
    create_job,
    delete_job,
    edit_job,
    list_jobs,
    sync_job_review_projection,
)
from app.enterprise_console.providers import (
    JobApplicationIntakeProvider,
    get_job_application_intake_provider,
    get_job_position_provider,
    set_job_application_intake_provider,
    set_job_position_provider,
)
from app.enterprise_console.review import (
    ContentReviewProvider,
    get_content_review_provider,
    set_content_review_provider,
)
from app.messaging.relationships import (
    list_allowed_contacts,
    messaging_relationship,
)
from app.seed import seed_interest_tags
from app.seed_dev import seed_local_data


class FakeReviewProvider:
    def __init__(self):
        self.records = {}
        self.calls = []

    def submit_for_review(
        self,
        *,
        content_type,
        content_id,
        submitter_id,
        expected_version,
        payload,
    ):
        record = {
            "content_type": content_type,
            "content_id": content_id,
            "submitter_id": submitter_id,
            "review_status": "pending",
            "version": expected_version,
            "rejection_opinion": None,
            "published_at": None,
        }
        self.records[content_id] = record
        self.calls.append(
            (
                "submit",
                content_id,
                submitter_id,
                expected_version,
                dict(payload),
            )
        )
        return dict(record)

    def get_review_status(self, *, content_type, content_id):
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
        record.update(
            {
                "review_status": "approved",
                "version": expected_version + 1,
                "rejection_opinion": None,
                "published_at": "2026-09-19T12:00:00+08:00",
            }
        )
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
        record.update(
            {
                "review_status": "rejected",
                "version": expected_version + 1,
                "rejection_opinion": opinion,
                "published_at": None,
            }
        )
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
        record = dict(self.records[content_id])
        record.update(
            {
                "review_status": "pending",
                "version": expected_version + 1,
                "rejection_opinion": None,
                "published_at": None,
            }
        )
        self.records[content_id] = record
        self.calls.append(
            (
                "edit",
                content_id,
                submitter_id,
                expected_version,
                dict(payload),
            )
        )
        return dict(record)


class Plain07JobConsumer:
    def __init__(self, provider):
        self.provider = provider

    def index(self):
        return {
            record["job_id"]: record
            for record in self.provider.list_published_positions()
        }

    def detail(self, job_id):
        return self.provider.get_published_position(job_id=job_id)


class ReplacementPositionProvider:
    def list_published_positions(self):
        return [
            {
                "job_id": "job-replaced",
                "enterprise_id": 7,
                "enterprise_name": "替换企业",
                "title": "替换岗位",
                "salary": "10k-12k",
                "location": "广州",
                "category_id": 9,
                "category_name": "农业技术员",
                "description": "替换 provider 返回。",
                "review_status": "approved",
                "version": 3,
                "published_at": "2026-09-19T12:00:00+08:00",
                "updated_at": "2026-09-19T12:00:00+08:00",
            }
        ]

    def get_published_position(self, *, job_id):
        if job_id != "job-replaced":
            return None
        return self.list_published_positions()[0]


class ReplacementApplicationProvider:
    def __init__(self):
        self.calls = []

    def submit_application(
        self,
        *,
        job_id: str,
        student_id: int,
        resume_snapshot: dict,
        skill_profile_snapshot: dict | None,
        idempotency_key: str,
    ) -> dict:
        self.calls.append(
            {
                "job_id": job_id,
                "student_id": student_id,
                "resume_snapshot": resume_snapshot,
                "skill_profile_snapshot": skill_profile_snapshot,
                "idempotency_key": idempotency_key,
            }
        )
        return {
            "application_id": "application-replaced",
            "job_id": job_id,
            "enterprise_id": 7,
            "student_id": student_id,
            "student_name": "替换学员",
            "job_title": "替换岗位",
            "resume_snapshot": resume_snapshot,
            "skill_profile": skill_profile_snapshot,
            "skill_profile_attached": skill_profile_snapshot is not None,
            "status": "pending",
            "status_version": 1,
            "position_closed": False,
            "effective_status": "pending",
            "submitted_at": "2026-09-19T12:00:00+08:00",
        }


class TestEnterpriseIntegration(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = str(
            Path(self.temp_dir.name) / "enterprise-integration.db"
        )
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": self.database_path,
                "SECRET_KEY": "test-only-secret",
            }
        )
        self.review_provider = FakeReviewProvider()
        set_content_review_provider(self.app, self.review_provider)

        with self.app.app_context():
            db = get_db()
            seed_interest_tags(db)
            self.category_id = int(
                db.execute(
                    """
                    SELECT id
                    FROM interest_tags
                    WHERE group_key = 'job' AND name = '农业技术员'
                    """
                ).fetchone()["id"]
            )
            self.enterprise_id = self._insert_user(
                db,
                username="integration-enterprise",
                name="整合测试企业",
                role="enterprise",
            )
            self.other_enterprise_id = self._insert_user(
                db,
                username="integration-enterprise-2",
                name="第二整合企业",
                role="enterprise",
            )
            self.student_ids = [
                self._insert_user(
                    db,
                    username=f"integration-student-{index}",
                    name=f"整合学员{index}",
                    role="student",
                )
                for index in range(1, 4)
            ]
            db.commit()

    def tearDown(self):
        self.temp_dir.cleanup()

    @staticmethod
    def _insert_user(db, *, username, name, role):
        timestamp = "2026-09-19T10:00:00+08:00"
        return int(
            db.execute(
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
        )

    def _payload(self, *, title="农业技术员"):
        return {
            "title": title,
            "salary": "8k-10k",
            "location": "广州",
            "category_id": self.category_id,
            "description": "负责农业技术指导与现场记录。",
        }

    def _create_job(self, *, title="农业技术员"):
        return create_job(self.enterprise_id, self._payload(title=title))

    def _approve(self, job):
        self.review_provider.approve(
            content_type=JOB_REVIEW_CONTENT_TYPE,
            content_id=job["job_id"],
            submitter_id=self.enterprise_id,
            reviewer_id=9001,
            reviewer_role="admin",
            expected_version=job["version"],
        )
        return sync_job_review_projection(job["job_id"])

    def _reject(self, job, opinion):
        self.review_provider.reject(
            content_type=JOB_REVIEW_CONTENT_TYPE,
            content_id=job["job_id"],
            submitter_id=self.enterprise_id,
            reviewer_id=9001,
            reviewer_role="admin",
            expected_version=job["version"],
            opinion=opinion,
        )
        return sync_job_review_projection(job["job_id"])

    def test_plain_07_consumer_reads_only_approved_provider_records(self):
        with self.app.app_context():
            job = self._create_job(title="已上架农业技术员")
            consumer = Plain07JobConsumer(get_job_position_provider())

            self.assertEqual(consumer.index(), {})
            self.assertIsNone(consumer.detail(job["job_id"]))

            approved = self._approve(job)
            record = consumer.detail(job["job_id"])

            self.assertEqual(approved["review_status"], "approved")
            self.assertIsNotNone(record)
            self.assertEqual(
                set(record),
                {
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
                },
            )
            self.assertEqual(record["job_id"], job["job_id"])
            self.assertEqual(record["category_id"], self.category_id)
            self.assertEqual(consumer.index()[job["job_id"]], record)

            edited = edit_job(
                self.enterprise_id,
                job["job_id"],
                approved["version"],
                self._payload(title="编辑后下架的农业技术员"),
            )
            self.assertEqual(edited["review_status"], "pending")
            self.assertEqual(consumer.index(), {})
            self.assertIsNone(consumer.detail(job["job_id"]))

            self._approve(edited)
            self.assertIn(job["job_id"], consumer.index())

    def test_rejected_job_resubmits_with_cleared_opinion_and_version(self):
        with self.app.app_context():
            job = self._create_job()
            rejected = self._reject(job, "请补充岗位职责。")

            self.assertEqual(rejected["review_status"], "rejected")
            self.assertEqual(rejected["version"], 2)
            self.assertEqual(
                rejected["rejection_opinion"],
                "请补充岗位职责。",
            )

            resubmitted = edit_job(
                self.enterprise_id,
                job["job_id"],
                rejected["version"],
                self._payload(title="补充职责后的农业技术员"),
            )

            self.assertEqual(resubmitted["review_status"], "pending")
            self.assertEqual(resubmitted["version"], 3)
            self.assertIsNone(resubmitted["rejection_opinion"])
            self.assertIsNone(resubmitted["published_at"])

    def test_application_intake_filters_status_and_deduplicates_notifications(
        self,
    ):
        with self.app.app_context():
            job = self._approve(self._create_job())
            provider = get_job_application_intake_provider()
            first = provider.submit_application(
                job_id=job["job_id"],
                student_id=self.student_ids[0],
                resume_snapshot={"education": "本科"},
                skill_profile_snapshot={
                    "items": [{"title": "农业技术竞赛"}]
                },
                idempotency_key="07-plain-request-1",
            )
            repeated = provider.submit_application(
                job_id=job["job_id"],
                student_id=self.student_ids[0],
                resume_snapshot={"education": "本科"},
                skill_profile_snapshot={
                    "items": [{"title": "农业技术竞赛"}]
                },
                idempotency_key="07-plain-request-1",
            )
            second = provider.submit_application(
                job_id=job["job_id"],
                student_id=self.student_ids[1],
                resume_snapshot={"education": "大专"},
                skill_profile_snapshot=None,
                idempotency_key="07-plain-request-2",
            )

            self.assertEqual(first["application_id"], repeated["application_id"])
            self.assertTrue(first["skill_profile_attached"])
            self.assertFalse(second["skill_profile_attached"])
            self.assertEqual(
                len(
                    list_applications(
                        self.enterprise_id,
                        {
                            "job_id": job["job_id"],
                            "status": "pending",
                            "sort": "submitted_asc",
                        },
                    )
                ),
                2,
            )

            db = get_db()
            self.assertEqual(
                db.execute(
                    """
                    SELECT COUNT(*)
                    FROM system_notifications
                    WHERE recipient_id = ?
                      AND event_type = 'application_submitted'
                    """,
                    (self.enterprise_id,),
                ).fetchone()[0],
                2,
            )

            changed = change_application_status(
                self.enterprise_id,
                first["application_id"],
                first["status_version"],
                "intent",
            )
            unchanged = change_application_status(
                self.enterprise_id,
                first["application_id"],
                changed["application"]["status_version"],
                "intent",
            )

            self.assertTrue(changed["changed"])
            self.assertFalse(unchanged["changed"])
            self.assertEqual(
                db.execute(
                    """
                    SELECT COUNT(*)
                    FROM system_notifications
                    WHERE recipient_id = ?
                      AND event_type = 'application_status'
                    """,
                    (self.student_ids[0],),
                ).fetchone()[0],
                1,
            )

    def test_delete_preserves_history_dashboard_and_messaging_relationship(
        self,
    ):
        with self.app.app_context():
            job = self._approve(self._create_job())
            provider = get_job_application_intake_provider()
            pending = provider.submit_application(
                job_id=job["job_id"],
                student_id=self.student_ids[0],
                resume_snapshot={"education": "本科"},
                skill_profile_snapshot=None,
                idempotency_key="delete-pending",
            )
            handled = provider.submit_application(
                job_id=job["job_id"],
                student_id=self.student_ids[1],
                resume_snapshot={"education": "大专"},
                skill_profile_snapshot={"items": [{"title": "客服实践"}]},
                idempotency_key="delete-handled",
            )
            changed = change_application_status(
                self.enterprise_id,
                handled["application_id"],
                handled["status_version"],
                "viewed",
            )["application"]

            deleted = delete_job(
                self.enterprise_id,
                job["job_id"],
                expected_version=job["version"],
            )

            self.assertEqual(deleted["closed_application_count"], 1)
            self.assertEqual(deleted["historical_application_count"], 1)
            self.assertEqual(deleted["notification_count"], 1)
            pending_detail = get_application(
                self.enterprise_id,
                pending["application_id"],
            )
            handled_detail = get_application(
                self.enterprise_id,
                handled["application_id"],
            )
            self.assertTrue(pending_detail["position_closed"])
            self.assertEqual(pending_detail["effective_status"], "closed")
            self.assertTrue(handled_detail["position_closed"])
            self.assertEqual(handled_detail["status"], "viewed")
            self.assertEqual(changed["status_version"], 2)
            self.assertEqual(
                get_dashboard(self.enterprise_id),
                {
                    "active_job_count": 0,
                    "received_resume_count": 2,
                },
            )
            self.assertEqual(
                messaging_relationship(
                    self.student_ids[0],
                    self.enterprise_id,
                ),
                "application",
            )
            contact_ids = {
                contact["id"]
                for contact in list_allowed_contacts(self.enterprise_id)
            }
            self.assertEqual(
                contact_ids,
                {self.student_ids[0], self.student_ids[1]},
            )
            self.assertEqual(list_jobs(self.enterprise_id), [])

    def test_review_slot_is_single_and_09_never_emits_review_notifications(
        self,
    ):
        with patch(
            "app.messaging.events.emit_review_result"
        ) as emit_review_result:
            with self.app.app_context():
                job = self._create_job()
                approved = self._approve(job)
                edit_job(
                    self.enterprise_id,
                    job["job_id"],
                    approved["version"],
                    self._payload(title="无重复审核通知"),
                )

                self.assertIs(
                    get_content_review_provider(),
                    self.review_provider,
                )
                self.assertEqual(
                    sum(
                        key == "content_review_provider"
                        for key in self.app.extensions
                    ),
                    1,
                )

        emit_review_result.assert_not_called()

    def test_job_position_provider_replacement_preserves_consumer_shape(
        self,
    ):
        replacement = ReplacementPositionProvider()
        set_job_position_provider(self.app, replacement)

        with self.app.app_context():
            consumer = Plain07JobConsumer(get_job_position_provider())
            expected = replacement.list_published_positions()[0]

            self.assertIs(get_job_position_provider(), replacement)
            self.assertEqual(consumer.index(), {"job-replaced": expected})
            self.assertEqual(consumer.detail("job-replaced"), expected)
            self.assertIsNone(consumer.detail("job-missing"))

    def test_application_intake_replacement_preserves_07_contract(self):
        replacement = ReplacementApplicationProvider()
        set_job_application_intake_provider(self.app, replacement)

        with self.app.app_context():
            provider = get_job_application_intake_provider()
            result = provider.submit_application(
                job_id="job-replaced",
                student_id=self.student_ids[0],
                resume_snapshot={"education": "本科"},
                skill_profile_snapshot=None,
                idempotency_key="replacement-request",
            )
            application_count = get_db().execute(
                "SELECT COUNT(*) FROM job_applications"
            ).fetchone()[0]
            protocol_signature = inspect.signature(
                JobApplicationIntakeProvider.submit_application
            )
            replacement_signature = inspect.signature(
                ReplacementApplicationProvider.submit_application
            )

        self.assertIs(provider, replacement)
        self.assertEqual(replacement_signature, protocol_signature)
        self.assertEqual(result["application_id"], "application-replaced")
        self.assertEqual(application_count, 0)
        self.assertEqual(
            replacement.calls,
            [
                {
                    "job_id": "job-replaced",
                    "student_id": self.student_ids[0],
                    "resume_snapshot": {"education": "本科"},
                    "skill_profile_snapshot": None,
                    "idempotency_key": "replacement-request",
                }
            ],
        )

    def test_create_app_does_not_seed_demo_console_data(self):
        with self.app.app_context():
            job_count = get_db().execute(
                "SELECT COUNT(*) FROM job_positions"
            ).fetchone()[0]
            demo_count = get_db().execute(
                """
                SELECT COUNT(*)
                FROM job_positions
                WHERE job_id LIKE 'job-demo-%'
                """
            ).fetchone()[0]

        self.assertEqual(job_count, 0)
        self.assertEqual(demo_count, 0)

    def test_demo_fixture_is_idempotent_and_does_not_create_notifications(
        self,
    ):
        with self.app.app_context():
            db = get_db()
            self._insert_user(
                db,
                username="enterprise_demo",
                name="本地企业",
                role="enterprise",
            )
            self._insert_user(
                db,
                username="student_demo",
                name="本地学员",
                role="student",
            )
            db.commit()

            first = seed_enterprise_console_fixtures(db)
            db.commit()
            second = seed_enterprise_console_fixtures(db)
            db.commit()

            self.assertEqual(first, second)
            self.assertEqual(first["jobs"], 3)
            self.assertEqual(first["applications"], 5)
            self.assertEqual(
                db.execute(
                    "SELECT COUNT(*) FROM job_positions"
                ).fetchone()[0],
                3,
            )
            self.assertEqual(
                db.execute(
                    "SELECT COUNT(*) FROM job_applications"
                ).fetchone()[0],
                5,
            )
            statuses = {
                row["status"]
                for row in db.execute(
                    "SELECT status FROM job_applications"
                )
            }
            self.assertEqual(
                statuses,
                {"pending", "viewed", "intent", "unsuitable"},
            )
            self.assertEqual(
                db.execute(
                    """
                    SELECT COUNT(*)
                    FROM job_applications
                    WHERE status = 'pending'
                      AND position_closed_at IS NOT NULL
                    """
                ).fetchone()[0],
                1,
            )
            self.assertEqual(
                db.execute(
                    """
                    SELECT COUNT(*)
                    FROM job_applications
                    WHERE skill_profile_attached = 1
                    """
                ).fetchone()[0],
                2,
            )
            self.assertEqual(
                db.execute(
                    """
                    SELECT COUNT(*)
                    FROM enterprise_notification_outbox
                    """
                ).fetchone()[0],
                0,
            )
            self.assertEqual(
                db.execute(
                    "SELECT COUNT(*) FROM system_notifications"
                ).fetchone()[0],
                0,
            )

    def test_seed_local_data_wires_demo_fixtures_idempotently(self):
        environment = {
            "DEV_SEED_PASSWORD": "local-password",
            "SECRET_KEY": "local-secret",
        }
        with patch.dict(os.environ, environment, clear=True):
            first = seed_local_data(self.database_path)
            second = seed_local_data(self.database_path)

        self.assertEqual(first["enterprise_jobs"], 3)
        self.assertEqual(first["enterprise_applications"], 5)
        self.assertEqual(second["enterprise_jobs"], 3)
        self.assertEqual(second["enterprise_applications"], 5)

        with self.app.app_context():
            db = get_db()
            self.assertEqual(
                db.execute(
                    "SELECT COUNT(*) FROM job_positions"
                ).fetchone()[0],
                3,
            )
            self.assertEqual(
                db.execute(
                    "SELECT COUNT(*) FROM job_applications"
                ).fetchone()[0],
                5,
            )
            self.assertEqual(
                db.execute(
                    "SELECT COUNT(*) FROM system_notifications"
                ).fetchone()[0],
                0,
            )

    def test_provider_and_filters_cover_target_scale(self):
        with self.app.app_context():
            db = get_db()
            extra_students = [
                self._insert_user(
                    db,
                    username=f"scale-student-{index}",
                    name=f"规模学员{index}",
                    role="student",
                )
                for index in range(1, 21)
            ]
            students_by_enterprise = {
                self.enterprise_id: extra_students[:10],
                self.other_enterprise_id: extra_students[10:],
            }
            timestamp = "2026-09-19T10:00:00+08:00"
            jobs = []
            for enterprise_id, prefix in (
                (self.enterprise_id, 1000),
                (self.other_enterprise_id, 2000),
            ):
                for offset in range(250):
                    job_id = f"scale-job-{prefix + offset}"
                    jobs.append(
                        (
                            job_id,
                            enterprise_id,
                            f"目标规模职位 {prefix + offset}",
                            "8k-10k",
                            "广州",
                            self.category_id,
                            "农业技术员",
                            "用于目标规模性能验证。",
                            "approved",
                            1,
                            timestamp,
                            timestamp,
                            timestamp,
                        )
                    )
            db.executemany(
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
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                jobs,
            )

            applications = []
            for enterprise_id, job_prefix in (
                (self.enterprise_id, 1000),
                (self.other_enterprise_id, 2000),
            ):
                students = students_by_enterprise[enterprise_id]
                for index in range(2500):
                    application_id = (
                        f"scale-application-{enterprise_id}-{index}"
                    )
                    job_id = (
                        f"scale-job-{job_prefix + (index % 250)}"
                    )
                    student_id = students[index // 250]
                    applications.append(
                        (
                            application_id,
                            job_id,
                            enterprise_id,
                            student_id,
                            f"规模学员{student_id}",
                            f"目标规模职位 {job_id}",
                            json.dumps(
                                {"education": "本科"},
                                ensure_ascii=False,
                            ),
                            "pending",
                            1,
                            application_id,
                            timestamp,
                            timestamp,
                        )
                    )
            db.executemany(
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
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                applications,
            )
            db.commit()

            started = time.monotonic()
            published = get_job_position_provider().list_published_positions()
            filtered = list_applications(
                self.enterprise_id,
                {"sort": "submitted_desc"},
            )
            dashboard = get_dashboard(self.enterprise_id)
            elapsed = time.monotonic() - started

            self.assertEqual(len(published), 500)
            self.assertEqual(len(filtered), 2500)
            self.assertEqual(dashboard["received_resume_count"], 2500)
            self.assertLess(elapsed, 2.0)


if __name__ == "__main__":
    unittest.main()
