import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from app import create_app
from app.db import get_db
from app.enterprise_console.applications import (
    change_application_status,
    get_application,
    list_applications,
    record_application_submission,
)
from app.enterprise_console.errors import (
    EnterpriseConflictError,
    EnterpriseNotFoundError,
    EnterpriseValidationError,
    ProviderConflictError,
    ProviderNotFoundError,
    ProviderValidationError,
)
from app.messaging.notification_service import list_notifications


class TestEnterpriseApplications(unittest.TestCase):
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
            self.other_enterprise_id = self._insert_user(
                db,
                username="enterprise-2",
                name="企业二",
                role="enterprise",
            )
            self.student_ids = [
                self._insert_user(
                    db,
                    username=f"student-{index}",
                    name=f"学员{index}",
                    role="student",
                )
                for index in range(1, 6)
            ]
            self.teacher_id = self._insert_user(
                db,
                username="teacher-1",
                name="教师",
                role="teacher",
            )
            self.category_id = db.execute(
                """
                INSERT INTO interest_tags (
                    group_key, name, sort_order, is_active
                )
                VALUES ('job', '申请测试类别', 0, 1)
                """
            ).lastrowid

            self._insert_job(
                db,
                job_id="job-approved",
                enterprise_id=self.enterprise_id,
                title="农业技术员",
                review_status="approved",
                published_at="2026-09-19T12:00:00+08:00",
            )
            self._insert_job(
                db,
                job_id="job-other",
                enterprise_id=self.enterprise_id,
                title="电商运营",
                review_status="approved",
                published_at="2026-09-18T12:00:00+08:00",
            )
            self._insert_job(
                db,
                job_id="job-enterprise-2",
                enterprise_id=self.other_enterprise_id,
                title="品牌运营",
                review_status="approved",
                published_at="2026-09-17T12:00:00+08:00",
            )
            for job_id, status, published_at, deleted_at in (
                (
                    "job-pending",
                    "pending",
                    "2026-09-20T12:00:00+08:00",
                    None,
                ),
                (
                    "job-rejected",
                    "rejected",
                    "2026-09-20T12:00:00+08:00",
                    None,
                ),
                (
                    "job-deleted",
                    "approved",
                    "2026-09-20T12:00:00+08:00",
                    "2026-09-20T12:00:00+08:00",
                ),
                (
                    "job-no-publication",
                    "approved",
                    None,
                    None,
                ),
            ):
                self._insert_job(
                    db,
                    job_id=job_id,
                    enterprise_id=self.enterprise_id,
                    title=f"不可投递-{job_id}",
                    review_status=status,
                    published_at=published_at,
                    deleted_at=deleted_at,
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

    def _insert_job(
        self,
        db,
        *,
        job_id,
        enterprise_id,
        title,
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
                title,
                "8000-10000",
                "广州",
                self.category_id,
                "农业技术员",
                "负责田间管理与技术推广",
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
        student_name,
        job_title,
        status,
        status_version,
        submitted_at,
        idempotency_key,
        position_closed_at=None,
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
            VALUES (?, ?, ?, ?, ?, ?, ?, NULL, 0, ?, ?, ?, NULL, ?, ?, ?)
            """,
            (
                application_id,
                job_id,
                enterprise_id,
                student_id,
                student_name,
                job_title,
                json.dumps(
                    {"summary": f"{student_name}的简历"},
                    ensure_ascii=False,
                ),
                status,
                status_version,
                position_closed_at,
                idempotency_key,
                submitted_at,
                submitted_at,
            ),
        )

    def _submit(
        self,
        *,
        job_id="job-approved",
        student_id=None,
        idempotency_key="request-1",
        resume_snapshot=None,
        skill_profile_snapshot=None,
    ):
        return record_application_submission(
            job_id=job_id,
            student_id=(
                self.student_ids[0]
                if student_id is None
                else student_id
            ),
            resume_snapshot=(
                {"education": ["A"], "skills": ["直播"]}
                if resume_snapshot is None
                else resume_snapshot
            ),
            skill_profile_snapshot=skill_profile_snapshot,
            idempotency_key=idempotency_key,
        )

    def test_submission_freezes_snapshots_and_creates_one_notice(self):
        resume = {"education": ["A"], "skills": ["直播"]}
        skills = {"items": [{"title": "直播训练", "score": 90}]}

        with self.app.app_context():
            application = self._submit(
                resume_snapshot=resume,
                skill_profile_snapshot=skills,
            )
            resume["education"].append("B")
            skills["items"].append({"title": "追加内容"})
            repeated = self._submit(
                resume_snapshot={"education": ["DIFFERENT"]},
                skill_profile_snapshot=None,
            )
            notices = list_notifications(self.enterprise_id)
            db = get_db()
            stored = db.execute(
                """
                SELECT
                    resume_snapshot_json,
                    skill_profile_snapshot_json,
                    (
                        SELECT COUNT(*)
                        FROM enterprise_notification_outbox
                    ) AS outbox_count
                FROM job_applications
                WHERE application_id = ?
                """,
                (application["application_id"],),
            ).fetchone()

        self.assertEqual(
            application["application_id"],
            repeated["application_id"],
        )
        self.assertEqual(
            application["resume_snapshot"],
            {"education": ["A"], "skills": ["直播"]},
        )
        self.assertEqual(
            application["skill_profile"],
            {"items": [{"title": "直播训练", "score": 90}]},
        )
        self.assertTrue(application["skill_profile_attached"])
        self.assertEqual(len(notices), 1)
        self.assertEqual(stored["outbox_count"], 1)
        self.assertIn("直播", stored["resume_snapshot_json"])
        self.assertNotIn("\\u76f4", stored["resume_snapshot_json"])

    def test_submission_rejects_invisible_jobs_and_invalid_students(self):
        with self.app.app_context():
            for job_id in (
                "job-pending",
                "job-rejected",
                "job-deleted",
                "job-no-publication",
            ):
                with self.subTest(job_id=job_id):
                    with self.assertRaises(ProviderConflictError):
                        self._submit(
                            job_id=job_id,
                            idempotency_key=f"key-{job_id}",
                        )

            with self.assertRaises(ProviderNotFoundError):
                self._submit(
                    job_id="job-missing",
                    idempotency_key="key-missing-job",
                )

            for student_id in (
                True,
                0,
                -1,
                "1",
                self.teacher_id,
                self.enterprise_id,
            ):
                with self.subTest(student_id=student_id):
                    with self.assertRaises(ProviderValidationError):
                        self._submit(
                            student_id=student_id,
                            idempotency_key=f"key-student-{student_id}",
                        )

            invalid_calls = (
                {"job_id": "   "},
                {"idempotency_key": "   "},
                {"resume_snapshot": {}},
                {"resume_snapshot": []},
            )
            for index, override in enumerate(invalid_calls):
                with self.subTest(override=override):
                    arguments = {
                        "idempotency_key": f"invalid-{index}",
                    }
                    arguments.update(override)
                    with self.assertRaises(ProviderValidationError):
                        self._submit(**arguments)

    def test_duplicate_student_job_returns_existing_without_notice(self):
        with self.app.app_context():
            first = self._submit(idempotency_key="first-key")
            repeated = self._submit(idempotency_key="second-key")
            notices = list_notifications(self.enterprise_id)
            count = get_db().execute(
                "SELECT COUNT(*) FROM job_applications"
            ).fetchone()[0]

        self.assertEqual(first["application_id"], repeated["application_id"])
        self.assertEqual(count, 1)
        self.assertEqual(len(notices), 1)

    def test_idempotency_key_reuse_with_different_request_is_rejected(self):
        with self.app.app_context():
            first = self._submit(idempotency_key="shared-key")

            with self.assertRaises(ProviderConflictError):
                self._submit(
                    job_id="job-other",
                    student_id=self.student_ids[1],
                    idempotency_key="shared-key",
                )

            count = get_db().execute(
                "SELECT COUNT(*) FROM job_applications"
            ).fetchone()[0]
            notices = list_notifications(self.enterprise_id)

        self.assertTrue(first["application_id"])
        self.assertEqual(count, 1)
        self.assertEqual(len(notices), 1)

    def test_empty_or_missing_skill_profile_is_not_attached(self):
        with self.app.app_context():
            missing = self._submit(
                student_id=self.student_ids[0],
                skill_profile_snapshot=None,
            )
            empty = self._submit(
                job_id="job-other",
                student_id=self.student_ids[1],
                idempotency_key="empty-profile",
                skill_profile_snapshot={"items": []},
            )
            no_items = self._submit(
                job_id="job-other",
                student_id=self.student_ids[2],
                idempotency_key="no-items",
                skill_profile_snapshot={"summary": "not a profile"},
            )

            missing_detail = get_application(
                self.enterprise_id,
                missing["application_id"],
            )
            empty_detail = get_application(
                self.enterprise_id,
                empty["application_id"],
            )
            no_items_detail = get_application(
                self.enterprise_id,
                no_items["application_id"],
            )

            with self.assertRaises(ProviderValidationError):
                self._submit(
                    student_id=self.student_ids[3],
                    idempotency_key="invalid-profile",
                    skill_profile_snapshot={"items": "invalid"},
                )

        for detail in (missing_detail, empty_detail, no_items_detail):
            self.assertIsNone(detail["skill_profile"])
            self.assertFalse(detail["skill_profile_attached"])

    def test_list_filters_dates_sort_and_enterprise_scope(self):
        with self.app.app_context():
            db = get_db()
            self._insert_application(
                db,
                application_id="application-start",
                job_id="job-approved",
                enterprise_id=self.enterprise_id,
                student_id=self.student_ids[0],
                student_name="学员1",
                job_title="农业技术员",
                status="pending",
                status_version=1,
                submitted_at="2026-09-01T00:00:00+08:00",
                idempotency_key="start",
            )
            self._insert_application(
                db,
                application_id="application-tie-z",
                job_id="job-approved",
                enterprise_id=self.enterprise_id,
                student_id=self.student_ids[1],
                student_name="学员2",
                job_title="农业技术员",
                status="pending",
                status_version=1,
                submitted_at="2026-09-15T10:00:00+08:00",
                idempotency_key="tie-z",
            )
            self._insert_application(
                db,
                application_id="application-tie-a",
                job_id="job-other",
                enterprise_id=self.enterprise_id,
                student_id=self.student_ids[2],
                student_name="学员3",
                job_title="电商运营",
                status="viewed",
                status_version=2,
                submitted_at="2026-09-15T10:00:00+08:00",
                idempotency_key="tie-a",
            )
            self._insert_application(
                db,
                application_id="application-intent",
                job_id="job-approved",
                enterprise_id=self.enterprise_id,
                student_id=self.student_ids[3],
                student_name="学员4",
                job_title="农业技术员",
                status="intent",
                status_version=2,
                submitted_at="2026-09-20T10:00:00+08:00",
                idempotency_key="intent",
            )
            self._insert_application(
                db,
                application_id="application-end",
                job_id="job-other",
                enterprise_id=self.enterprise_id,
                student_id=self.student_ids[4],
                student_name="学员5",
                job_title="电商运营",
                status="unsuitable",
                status_version=2,
                submitted_at="2026-09-30T23:59:59+08:00",
                idempotency_key="end",
            )
            self._insert_application(
                db,
                application_id="application-other-enterprise",
                job_id="job-enterprise-2",
                enterprise_id=self.other_enterprise_id,
                student_id=self.student_ids[0],
                student_name="学员1",
                job_title="品牌运营",
                status="pending",
                status_version=1,
                submitted_at="2026-09-25T10:00:00+08:00",
                idempotency_key="other-enterprise",
            )
            db.commit()

            default_rows = list_applications(self.enterprise_id, {})
            date_rows = list_applications(
                self.enterprise_id,
                {
                    "submitted_from": date(2026, 9, 15),
                    "submitted_to": date(2026, 9, 15),
                },
            )
            filtered = list_applications(
                self.enterprise_id,
                {
                    "job_id": "job-approved",
                    "status": "intent",
                    "submitted_from": date(2026, 9, 20),
                    "submitted_to": date(2026, 9, 20),
                    "sort": "submitted_asc",
                },
            )

        self.assertEqual(
            [row["application_id"] for row in default_rows],
            [
                "application-end",
                "application-intent",
                "application-tie-a",
                "application-tie-z",
                "application-start",
            ],
        )
        self.assertEqual(
            [row["application_id"] for row in date_rows],
            ["application-tie-a", "application-tie-z"],
        )
        self.assertEqual(
            [row["application_id"] for row in filtered],
            ["application-intent"],
        )

        with self.app.app_context():
            invalid_filters = (
                {
                    "submitted_from": date(2026, 9, 20),
                    "submitted_to": date(2026, 9, 19),
                },
                {"submitted_from": "2026-09-20"},
                {"status": "invalid"},
                {"status": ["intent"]},
                {"sort": "invalid"},
                {"sort": []},
            )
            for filters in invalid_filters:
                with self.subTest(filters=filters):
                    with self.assertRaises(EnterpriseValidationError):
                        list_applications(self.enterprise_id, filters)

            other_enterprise_rows = list_applications(
                self.other_enterprise_id,
                {},
            )
            self.assertEqual(
                [
                    row["application_id"]
                    for row in other_enterprise_rows
                ],
                ["application-other-enterprise"],
            )
            self.assertNotIn(
                "application-other-enterprise",
                {
                    row["application_id"]
                    for row in default_rows
                },
            )

    def test_detail_returns_snapshot_history_and_is_enterprise_scoped(self):
        with self.app.app_context():
            application = self._submit(
                skill_profile_snapshot={
                    "items": [{"title": "直播训练", "score": 90}]
                },
            )
            change_application_status(
                self.enterprise_id,
                application["application_id"],
                1,
                "viewed",
            )
            change_application_status(
                self.enterprise_id,
                application["application_id"],
                2,
                "intent",
            )
            detail = get_application(
                self.enterprise_id,
                application["application_id"],
            )

            with self.assertRaises(EnterpriseNotFoundError):
                get_application(
                    self.other_enterprise_id,
                    application["application_id"],
                )
            with self.assertRaises(EnterpriseNotFoundError):
                change_application_status(
                    self.other_enterprise_id,
                    application["application_id"],
                    3,
                    "unsuitable",
                )

        self.assertEqual(
            detail["resume_snapshot"],
            {"education": ["A"], "skills": ["直播"]},
        )
        self.assertEqual(
            detail["skill_profile"],
            {"items": [{"title": "直播训练", "score": 90}]},
        )
        self.assertEqual(detail["status"], "intent")
        self.assertEqual(detail["status_version"], 3)
        self.assertEqual(
            [
                (
                    item["sequence_no"],
                    item["previous_status"],
                    item["new_status"],
                )
                for item in detail["status_history"]
            ],
            [
                (2, "pending", "viewed"),
                (3, "viewed", "intent"),
            ],
        )

    def test_status_marking_updates_history_notifies_once_and_is_idempotent(self):
        with self.app.app_context():
            application = self._submit()
            application_id = application["application_id"]
            expected_version = 1
            expected_sequence = 2

            for status in ("viewed", "intent", "unsuitable", "viewed"):
                result = change_application_status(
                    self.enterprise_id,
                    application_id,
                    expected_version,
                    status,
                )
                self.assertTrue(result["changed"])
                self.assertEqual(result["application"]["status"], status)
                self.assertEqual(
                    result["application"]["status_version"],
                    expected_version + 1,
                )

                repeated = change_application_status(
                    self.enterprise_id,
                    application_id,
                    expected_version + 1,
                    status,
                )
                self.assertFalse(repeated["changed"])
                self.assertEqual(
                    repeated["application"]["status_version"],
                    expected_version + 1,
                )

                history_count = get_db().execute(
                    """
                    SELECT COUNT(*)
                    FROM job_application_status_history
                    WHERE application_id = ?
                    """,
                    (application_id,),
                ).fetchone()[0]
                self.assertEqual(history_count, expected_sequence - 1)
                self.assertEqual(
                    len(list_notifications(self.student_ids[0])),
                    expected_sequence - 1,
                )
                expected_version += 1
                expected_sequence += 1

            detail = get_application(
                self.enterprise_id,
                application_id,
            )

        self.assertEqual(
            [
                (item["previous_status"], item["new_status"])
                for item in detail["status_history"]
            ],
            [
                ("pending", "viewed"),
                ("viewed", "intent"),
                ("intent", "unsuitable"),
                ("unsuitable", "viewed"),
            ],
        )

    def test_pending_target_closed_application_and_stale_version_conflict(self):
        with self.app.app_context():
            application = self._submit()
            application_id = application["application_id"]

            with self.assertRaises(EnterpriseValidationError):
                change_application_status(
                    self.enterprise_id,
                    application_id,
                    1,
                    "pending",
                )
            with self.assertRaises(EnterpriseValidationError):
                change_application_status(
                    self.enterprise_id,
                    application_id,
                    1,
                    ["viewed"],
                )

            changed = change_application_status(
                self.enterprise_id,
                application_id,
                1,
                "viewed",
            )
            self.assertEqual(changed["application"]["status_version"], 2)

            with self.assertRaises(ProviderConflictError):
                change_application_status(
                    self.enterprise_id,
                    application_id,
                    1,
                    "intent",
                )

            db = get_db()
            db.execute(
                """
                UPDATE job_applications
                SET position_closed_at = ?, close_reason = ?
                WHERE application_id = ?
                """,
                (
                    "2026-09-20T12:00:00+08:00",
                    "job_deleted",
                    application_id,
                ),
            )
            db.commit()

            with self.assertRaises(EnterpriseConflictError):
                change_application_status(
                    self.enterprise_id,
                    application_id,
                    2,
                    "unsuitable",
                )

            detail = get_application(
                self.enterprise_id,
                application_id,
            )
            history_count = db.execute(
                """
                SELECT COUNT(*)
                FROM job_application_status_history
                WHERE application_id = ?
                """,
                (application_id,),
            ).fetchone()[0]
            notification_count = len(
                list_notifications(self.student_ids[0])
            )

        self.assertEqual(detail["status"], "viewed")
        self.assertTrue(detail["position_closed"])
        self.assertEqual(history_count, 1)
        self.assertEqual(notification_count, 1)


if __name__ == "__main__":
    unittest.main()
