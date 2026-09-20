from __future__ import annotations

import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from werkzeug.security import generate_password_hash

from app import create_app
from app.db import get_db
from app.enterprise_console.applications import (
    close_applications_for_deleted_job,
)
from app.enterprise_console.errors import (
    ProviderAccessDeniedError,
    ProviderConflictError,
    ProviderNotFoundError,
    ProviderValidationError,
)
from app.enterprise_console.providers import (
    DatabaseJobApplicationIntakeProvider,
    DatabaseJobApplicationStatusProvider,
    DatabaseJobPositionProvider,
    get_job_application_intake_provider,
    get_job_application_status_provider,
    get_job_position_provider,
    set_job_application_intake_provider,
    set_job_application_status_provider,
    set_job_position_provider,
)
from app.job_matching import skill_profile


JOB = {
    "job_id": "job-1",
    "enterprise_id": 1,
    "enterprise_name": "荔乡电商",
    "title": "电商运营",
    "salary": "7k-9k",
    "location": "佛山",
    "category_id": 10,
    "category_name": "电商运营",
    "description": "负责直播运营。",
    "review_status": "approved",
    "version": 1,
    "published_at": "2026-09-20T09:00:00+08:00",
    "updated_at": "2026-09-20T09:00:00+08:00",
}

OTHER_JOB = {
    **JOB,
    "job_id": "job-2",
    "title": "农产品运营",
    "category_id": 11,
    "published_at": "2026-09-20T08:00:00+08:00",
}

RESUME_PAYLOAD = {
    "education_experiences": [],
    "work_experiences": [
        {
            "company": "示范农场",
            "role": "运营助理",
            "start_date": "2025-07",
            "end_date": "",
            "description": "",
        }
    ],
    "skills": ["直播运营"],
}

APPLICATION_SNAPSHOT = {
    "resume_version": 1,
    "saved_at": "2026-09-20T10:00:00+08:00",
    "education_experiences": [],
    "work_experiences": [],
    "skills": ["直播运营"],
}


def handcraft_outcome(
    source_id: int,
    *,
    title: str | None = None,
    occurred_at: str = "2026-09-20T10:00:00+08:00",
) -> dict:
    return {
        "outcome_type": "course_view",
        "source_id": source_id,
        "created_at": occurred_at,
        "source_available": True,
        "summary": title or f"手工课程学习记录 {source_id}",
        "score": None,
        "is_formal": False,
        "archive_written": False,
    }


def application_record(
    *,
    application_id: str = "application-1",
    student_id: int = 1,
    job_id: str = "job-1",
    status: str = "pending",
    effective_status: str | None = None,
    effective_status_label: str | None = None,
    position_closed: bool = False,
) -> dict:
    resolved_status = status if effective_status is None else effective_status
    resolved_label = (
        {
            "pending": "待处理",
            "viewed": "已查看",
            "intent": "意向沟通",
            "unsuitable": "不合适",
            "closed": "岗位已关闭",
        }.get(resolved_status, resolved_status)
        if effective_status_label is None
        else effective_status_label
    )
    return {
        "application_id": application_id,
        "job_id": job_id,
        "enterprise_id": 1,
        "enterprise_name": "荔乡电商",
        "student_id": student_id,
        "student_name": "就业验收学员",
        "job_title": "电商运营",
        "status": status,
        "status_version": 1,
        "position_closed": position_closed,
        "position_closed_at": (
            "2026-09-20T11:00:00+08:00" if position_closed else None
        ),
        "effective_status": resolved_status,
        "effective_status_label": resolved_label,
        "submitted_at": "2026-09-20T10:10:00+08:00",
    }


class RecordingJobPositionProvider:
    def __init__(self, jobs: list[dict]):
        self.jobs = {job["job_id"]: job for job in jobs}
        self.list_calls = 0
        self.get_calls = []

    def list_published_positions(self) -> list[dict]:
        self.list_calls += 1
        return list(self.jobs.values())

    def get_published_position(self, *, job_id: str) -> dict | None:
        self.get_calls.append(job_id)
        return self.jobs.get(job_id)

    def remove(self, job_id: str) -> None:
        self.jobs.pop(job_id, None)


class RecordingStatusProvider:
    def __init__(self):
        self.applications = []
        self.list_calls = []
        self.get_calls = []

    def list_student_applications(self, *, student_id: int) -> list[dict]:
        self.list_calls.append(student_id)
        return [
            record
            for record in self.applications
            if record["student_id"] == student_id
        ]

    def get_student_application(
        self,
        *,
        student_id: int,
        application_id: str,
    ) -> dict | None:
        self.get_calls.append((student_id, application_id))
        return next(
            (
                record
                for record in self.applications
                if record["student_id"] == student_id
                and record["application_id"] == application_id
            ),
            None,
        )


class RecordingIntakeProvider:
    def __init__(self, application: dict):
        self.application = application
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
        return self.application


class RaisingJobPositionProvider:
    def __init__(self, error: Exception):
        self.error = error

    def list_published_positions(self) -> list[dict]:
        raise self.error

    def get_published_position(self, *, job_id: str) -> dict | None:
        raise self.error


class FakeAiClient:
    def __init__(self):
        self.calls = []

    def complete_json(self, messages, *, call_point):
        self.calls.append(
            {
                "messages": messages,
                "call_point": call_point,
            }
        )
        return {
            "suggestions": ["补充量化成果"],
            "rewritten_resume": None,
        }


class JobMatchingIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(
                    Path(self.temp_dir.name) / "integration.db"
                ),
                "SECRET_KEY": "task-18-test-secret",
                "SESSION_HOURS": 24,
                "SESSION_COOKIE_SECURE": False,
            }
        )
        self.enterprise_id = self._create_user(
            "integration-enterprise",
            "荔乡电商",
            "enterprise",
        )
        self.student_id = self._create_user(
            "integration-student",
            "就业验收学员",
            "student",
        )
        with self.app.app_context():
            db = get_db()
            db.execute(
                """
                INSERT INTO student_profiles (
                    user_id, contact, learning_direction, updated_at
                )
                VALUES (?, '', 'ecommerce', ?)
                """,
                (self.student_id, "2026-09-20T09:00:00+08:00"),
            )
            db.execute(
                """
                INSERT INTO resumes (user_id, created_at)
                VALUES (?, ?)
                """,
                (self.student_id, "2026-09-20T09:00:00+08:00"),
            )
            db.commit()

        self.client = self.login_student()
        self.job_provider = RecordingJobPositionProvider([JOB])
        self.status_provider = RecordingStatusProvider()
        self.intake_provider = RecordingIntakeProvider(
            application_record(student_id=self.student_id)
        )
        set_job_position_provider(self.app, self.job_provider)
        set_job_application_status_provider(
            self.app,
            self.status_provider,
        )
        set_job_application_intake_provider(
            self.app,
            self.intake_provider,
        )

        self.skill_outcomes = [handcraft_outcome(1)]
        self.source_patches = [
            patch.object(
                skill_profile,
                "list_learning_outcomes",
                return_value=[],
            ),
            patch.object(
                skill_profile,
                "list_ecommerce_learning_outcomes",
                return_value=[],
            ),
            patch.object(
                skill_profile,
                "list_handcraft_learning_outcomes",
                side_effect=self._read_handcraft_outcomes,
            ),
        ]
        for source_patch in self.source_patches:
            source_patch.start()
            self.addCleanup(source_patch.stop)

    def _read_handcraft_outcomes(self, _student_id: int) -> list[dict]:
        return [dict(outcome) for outcome in self.skill_outcomes]

    def _create_user(
        self,
        username: str,
        name: str,
        role: str,
    ) -> int:
        with self.app.app_context():
            cursor = get_db().execute(
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
                    generate_password_hash("password8"),
                    name,
                    role,
                    "2026-09-20T09:00:00+08:00",
                    "2026-09-20T09:00:00+08:00",
                ),
            )
            get_db().commit()
        return int(cursor.lastrowid)

    def _login(self, username: str):
        client = self.app.test_client()
        response = client.post(
            "/api/auth/login",
            json={"username": username, "password": "password8"},
        )
        self.assertEqual(response.status_code, 200)
        return client

    def login_student(self):
        return self._login("integration-student")

    def login_enterprise(self):
        return self._login("integration-enterprise")

    def save_resume(self) -> dict:
        response = self.client.put(
            "/api/job-matching/resume",
            json={"expected_version": 0, **RESUME_PAYLOAD},
        )
        self.assertEqual(response.status_code, 200)
        return response.get_json()["resume"]

    def _use_database_providers(self) -> None:
        set_job_position_provider(
            self.app,
            DatabaseJobPositionProvider(),
        )
        set_job_application_status_provider(
            self.app,
            DatabaseJobApplicationStatusProvider(),
        )
        set_job_application_intake_provider(
            self.app,
            DatabaseJobApplicationIntakeProvider(),
        )

    def _job_tag_id(self) -> int:
        with self.app.app_context():
            row = get_db().execute(
                """
                SELECT id
                FROM interest_tags
                WHERE group_key = 'job' AND is_active = 1
                ORDER BY id
                LIMIT 1
                """
            ).fetchone()
            if row is not None:
                return int(row["id"])
            return int(
                get_db().execute(
                    """
                    INSERT INTO interest_tags (
                        group_key, name, sort_order, is_active
                    )
                    VALUES ('job', '就业验收类别', 0, 1)
                    """
                ).lastrowid
            )

    def _insert_database_job(
        self,
        job_id: str = "db-job-1",
        *,
        title: str = "数据库岗位",
        category_id: int | None = None,
    ) -> None:
        with self.app.app_context():
            db = get_db()
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
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'approved', 1, ?, ?, ?)
                """,
                (
                    job_id,
                    self.enterprise_id,
                    title,
                    "8k-10k",
                    "广州",
                    category_id or self._job_tag_id(),
                    "就业验收类别",
                    "负责就业对接与运营。",
                    "2026-09-20T09:00:00+08:00",
                    "2026-09-20T09:00:00+08:00",
                    "2026-09-20T09:00:00+08:00",
                ),
            )
            db.commit()

    def _insert_database_application(
        self,
        *,
        application_id: str = "db-application-1",
        job_id: str = "db-job-1",
        status: str = "pending",
        position_closed_at: str | None = None,
    ) -> None:
        with self.app.app_context():
            db = get_db()
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
                    self.student_id,
                    "就业验收学员",
                    "数据库岗位",
                    json.dumps(APPLICATION_SNAPSHOT, ensure_ascii=False),
                    status,
                    position_closed_at,
                    (
                        "position_deleted"
                        if position_closed_at is not None
                        else None
                    ),
                    f"integration:{application_id}",
                    "2026-09-20T10:00:00+08:00",
                    "2026-09-20T10:00:00+08:00",
                ),
            )
            db.commit()

    def test_job_matching_end_to_end(self):
        self.login_student()
        saved = self.client.put(
            "/api/job-matching/resume",
            json={
                "expected_version": 0,
                "education_experiences": [],
                "work_experiences": [
                    {
                        "company": "示范农场",
                        "role": "运营助理",
                        "start_date": "2025-07",
                        "end_date": "2026-06",
                        "description": "负责直播记录。",
                    }
                ],
                "skills": ["直播运营"],
            },
        ).get_json()["resume"]
        self.assertEqual(saved["version"], 1)

        jobs = self.client.get("/api/job-matching/jobs").get_json()
        job_id = jobs["recommended_jobs"][0]["job_id"]
        profile = self.client.get(
            "/api/job-matching/skill-profile"
        ).get_json()["profile"]
        visible_id = profile["items"][0]["item_id"]
        self.client.put(
            "/api/job-matching/skill-profile/visibility",
            json={"visible_item_ids": [visible_id]},
        )

        submitted = self.client.post(
            f"/api/job-matching/jobs/{job_id}/applications",
            json={"attach_skill_profile": True},
        )
        self.assertEqual(submitted.status_code, 201)
        self.assertEqual(
            self.intake_provider.calls[0]["resume_snapshot"][
                "resume_version"
            ],
            1,
        )
        self.assertEqual(
            self.intake_provider.calls[0]["skill_profile_snapshot"][
                "schema_version"
            ],
            1,
        )

    def test_real_resume_save_and_submission_close_session_probe_transaction(
        self,
    ):
        client = self.login_student()

        saved = client.put(
            "/api/job-matching/resume",
            json={"expected_version": 0, **RESUME_PAYLOAD},
        )
        submitted = client.post(
            "/api/job-matching/jobs/job-1/applications",
            json={"attach_skill_profile": False},
        )

        self.assertEqual(saved.status_code, 200)
        self.assertEqual(saved.get_json()["resume"]["version"], 1)
        self.assertEqual(submitted.status_code, 201)
        self.assertEqual(len(self.intake_provider.calls), 1)

    def test_all_three_09_providers_can_be_replaced_without_consumer_changes(
        self,
    ):
        self.save_resume()

        listed = self.client.get("/api/job-matching/jobs")
        detail = self.client.get("/api/job-matching/jobs/job-1")
        applications = self.client.get("/api/job-matching/applications")
        submitted = self.client.post(
            "/api/job-matching/jobs/job-1/applications",
            json={"attach_skill_profile": False},
        )

        self.assertEqual(listed.status_code, 200)
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(applications.status_code, 200)
        self.assertEqual(submitted.status_code, 201)
        with self.app.app_context():
            self.assertIs(
                get_job_position_provider(),
                self.job_provider,
            )
            self.assertIs(
                get_job_application_intake_provider(),
                self.intake_provider,
            )
            self.assertIs(
                get_job_application_status_provider(),
                self.status_provider,
            )

        self.assertEqual(self.job_provider.list_calls, 1)
        self.assertEqual(
            self.job_provider.get_calls,
            ["job-1", "job-1"],
        )
        self.assertEqual(
            self.status_provider.list_calls,
            [self.student_id, self.student_id, self.student_id],
        )
        self.assertEqual(len(self.intake_provider.calls), 1)
        call = self.intake_provider.calls[0]
        self.assertEqual(
            set(call),
            {
                "job_id",
                "student_id",
                "resume_snapshot",
                "skill_profile_snapshot",
                "idempotency_key",
            },
        )
        self.assertEqual(call["job_id"], "job-1")
        self.assertEqual(call["student_id"], self.student_id)
        self.assertEqual(call["resume_snapshot"]["resume_version"], 1)
        self.assertIsNone(call["skill_profile_snapshot"])
        self.assertEqual(
            call["idempotency_key"],
            f"007:{self.student_id}:job-1",
        )

    def test_provider_boundary_errors_keep_codes_and_hide_internal_text(self):
        cases = (
            (
                ProviderValidationError("internal provider validation"),
                400,
                "provider_validation_error",
                "就业服务输入不正确",
            ),
            (
                ProviderNotFoundError("internal provider not found"),
                404,
                "provider_not_found",
                "就业服务数据不存在",
            ),
            (
                ProviderConflictError("internal provider conflict"),
                409,
                "provider_conflict",
                "就业服务状态冲突，请刷新后重试",
            ),
            (
                ProviderAccessDeniedError("internal access denied"),
                403,
                "provider_access_denied",
                "无权访问该就业服务数据",
            ),
        )

        for error, status, code, message in cases:
            with self.subTest(code=code):
                set_job_position_provider(
                    self.app,
                    RaisingJobPositionProvider(error),
                )

                response = self.client.get("/api/job-matching/jobs")
                body = response.get_json()

                self.assertEqual(response.status_code, status)
                self.assertEqual(body["code"], code)
                self.assertEqual(body["message"], message)
                self.assertEqual(body["errors"], {})
                self.assertNotIn("internal", body["message"])
                self.assertNotIn("internal", str(body["errors"]))

    def test_07_never_calls_02_application_notification_directly(self):
        self.save_resume()

        with (
            patch(
                "app.messaging.events.emit_application_submitted",
                create=True,
            ) as messaging_emitter,
            patch(
                "app.enterprise_console.notifications."
                "emit_application_submitted",
                create=True,
            ) as enterprise_emitter,
        ):
            response = self.client.post(
                "/api/job-matching/jobs/job-1/applications",
                json={"attach_skill_profile": False},
            )

        self.assertEqual(response.status_code, 201)
        messaging_emitter.assert_not_called()
        enterprise_emitter.assert_not_called()
        self.assertEqual(len(self.intake_provider.calls), 1)

    def test_ai_client_is_reached_only_from_resume_optimize(self):
        self.save_resume()
        fake_ai = FakeAiClient()

        with patch(
            "app.job_matching.resume_ai.get_ai_client",
            return_value=fake_ai,
        ) as get_ai_client:
            self.client.get("/api/job-matching/jobs")
            self.client.get("/api/job-matching/applications")
            self.client.get("/api/job-matching/favorites")
            self.client.get("/api/job-matching/skill-profile")
            self.client.post(
                "/api/job-matching/jobs/job-1/applications",
                json={"attach_skill_profile": False},
            )
            self.assertEqual(get_ai_client.call_count, 0)

            optimized = self.client.post(
                "/api/job-matching/resume/optimize",
                json={"expected_version": 1},
            )

        self.assertEqual(optimized.status_code, 200)
        get_ai_client.assert_called_once_with()
        self.assertEqual(len(fake_ai.calls), 1)
        self.assertEqual(
            fake_ai.calls[0]["call_point"],
            "resume_optimize",
        )

    def test_hidden_skill_item_id_never_enters_intake_snapshot(self):
        self.skill_outcomes = [
            handcraft_outcome(1, title="企业可见成果"),
            handcraft_outcome(2, title="隐藏成果"),
        ]
        self.save_resume()
        profile = self.client.get(
            "/api/job-matching/skill-profile"
        ).get_json()["profile"]
        visible_id = profile["items"][0]["item_id"]
        hidden_id = profile["items"][1]["item_id"]
        self.client.put(
            "/api/job-matching/skill-profile/visibility",
            json={"visible_item_ids": [visible_id]},
        )

        response = self.client.post(
            "/api/job-matching/jobs/job-1/applications",
            json={"attach_skill_profile": True},
        )

        self.assertEqual(response.status_code, 201)
        snapshot = self.intake_provider.calls[0]["skill_profile_snapshot"]
        self.assertEqual(
            [item["item_id"] for item in snapshot["items"]],
            [visible_id],
        )
        self.assertNotIn(
            hidden_id,
            json.dumps(
                self.intake_provider.calls[0],
                ensure_ascii=False,
            ),
        )

    def test_removed_job_disappears_while_favorite_remains_closed(self):
        self.save_resume()
        added = self.client.post(
            "/api/job-matching/favorites/job-1"
        )
        self.assertEqual(added.status_code, 200)
        self.assertFalse(added.get_json()["favorite"]["closed"])

        self.job_provider.remove("job-1")

        listed = self.client.get("/api/job-matching/jobs")
        detail = self.client.get("/api/job-matching/jobs/job-1")
        submission = self.client.post(
            "/api/job-matching/jobs/job-1/applications",
            json={"attach_skill_profile": False},
        )
        favorites = self.client.get("/api/job-matching/favorites")

        body = listed.get_json()
        self.assertEqual(
            [job["job_id"] for job in body["jobs"]],
            [],
        )
        self.assertEqual(
            [job["job_id"] for job in body["recommended_jobs"]],
            [],
        )
        self.assertEqual(detail.status_code, 404)
        self.assertEqual(detail.get_json()["code"], "job_unavailable")
        self.assertEqual(submission.status_code, 409)
        self.assertEqual(submission.get_json()["code"], "job_unavailable")
        self.assertEqual(self.intake_provider.calls, [])
        closed = favorites.get_json()["favorites"][0]
        self.assertTrue(closed["closed"])
        self.assertEqual(closed["job_id"], "job-1")
        self.assertEqual(closed["title_snapshot"], JOB["title"])
        self.assertEqual(
            closed["enterprise_name_snapshot"],
            JOB["enterprise_name"],
        )

    def test_application_status_change_flows_through_student_read(self):
        self._use_database_providers()
        self._insert_database_job()
        self._insert_database_application()

        before = self.client.get("/api/job-matching/applications")
        self.assertEqual(before.status_code, 200)
        self.assertEqual(
            before.get_json()["applications"][0]["effective_status"],
            "pending",
        )

        enterprise_client = self.login_enterprise()
        changed = enterprise_client.patch(
            "/api/enterprise/applications/db-application-1/status",
            json={"expected_version": 1, "status": "intent"},
        )
        self.assertEqual(changed.status_code, 200)
        self.assertTrue(changed.get_json()["changed"])

        after = self.client.get("/api/job-matching/applications")
        record = after.get_json()["applications"][0]
        self.assertEqual(record["status"], "intent")
        self.assertEqual(record["effective_status"], "intent")
        self.assertEqual(record["status_label"], "意向沟通")
        self.assertFalse(record["show_closed_marker"])

    def test_closed_handled_application_preserves_human_status(self):
        self._use_database_providers()
        self._insert_database_job()
        self._insert_database_application(status="unsuitable")

        with self.app.app_context():
            db = get_db()
            job_row = db.execute(
                "SELECT * FROM job_positions WHERE job_id = ?",
                ("db-job-1",),
            ).fetchone()
            result = close_applications_for_deleted_job(
                db,
                job_row,
                "2026-09-20T12:00:00+08:00",
            )
            db.commit()

        self.assertEqual(result["closed_application_count"], 0)
        self.assertEqual(result["historical_application_count"], 1)
        response = self.client.get("/api/job-matching/applications")
        record = response.get_json()["applications"][0]
        self.assertEqual(record["status"], "unsuitable")
        self.assertEqual(record["effective_status"], "unsuitable")
        self.assertEqual(record["status_label"], "不合适")
        self.assertTrue(record["position_closed"])
        self.assertTrue(record["show_closed_marker"])
        self.assertNotEqual(record["status_label"], "岗位已关闭")

    def test_07_has_no_direct_enterprise_table_writes(self):
        backend_root = Path(__file__).resolve().parents[1]
        source = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (backend_root / "app/job_matching").glob("*.py")
        )
        for forbidden in (
            "INSERT INTO job_applications",
            "UPDATE job_applications",
            "DELETE FROM job_applications",
            "FROM job_applications",
            "FROM job_positions",
        ):
            self.assertNotIn(forbidden, source)

    def test_only_resume_ai_calls_model(self):
        backend_root = Path(__file__).resolve().parents[1]
        offenders = []
        for path in (backend_root / "app/job_matching").glob("*.py"):
            text = path.read_text(encoding="utf-8")
            if (
                path.name != "resume_ai.py"
                and any(
                    token in text
                    for token in (
                        "get_ai_client",
                        "complete_json",
                        "set_ai_client",
                    )
                )
            ):
                offenders.append(path.name)
        self.assertEqual(offenders, [])

    def test_target_scale_read_paths_complete_under_two_seconds(self):
        self._use_database_providers()
        self.skill_outcomes = [
            handcraft_outcome(
                index,
                title=f"目标规模学习记录 {index}",
            )
            for index in range(1, 201)
        ]
        category_id = self._job_tag_id()
        job_rows = []
        for index in range(500):
            job_rows.append(
                (
                    f"perf-job-{index:04d}",
                    self.enterprise_id,
                    f"目标规模岗位 {index}",
                    "8k-10k",
                    "广州",
                    category_id,
                    "目标规模类别",
                    "负责就业对接和运营工作。",
                    "approved",
                    1,
                    f"2026-09-{(index % 28) + 1:02d}T09:00:00+08:00",
                    "2026-09-20T09:00:00+08:00",
                    "2026-09-20T09:00:00+08:00",
                )
            )

        other_students = [
            self._create_user(
                f"perf-student-{index}",
                f"目标规模学员 {index}",
                "student",
            )
            for index in range(1, 10)
        ]
        student_ids = [self.student_id, *other_students]
        application_rows = []
        resume_json = json.dumps(
            APPLICATION_SNAPSHOT,
            ensure_ascii=False,
        )
        for index in range(5000):
            student_id = student_ids[index // 500]
            job_index = index % 500
            application_id = f"perf-application-{index:05d}"
            application_rows.append(
                (
                    application_id,
                    f"perf-job-{job_index:04d}",
                    self.enterprise_id,
                    student_id,
                    f"目标规模学员 {student_id}",
                    f"目标规模岗位 {job_index}",
                    resume_json,
                    "pending",
                    1,
                    application_id,
                    "2026-09-20T10:00:00+08:00",
                    "2026-09-20T10:00:00+08:00",
                )
            )

        with self.app.app_context():
            db = get_db()
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
                job_rows,
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
                VALUES (?, ?, ?, ?, ?, ?, ?, NULL, 0, ?, ?, NULL, NULL, ?, ?, ?)
                """,
                application_rows,
            )
            db.commit()
            self.assertEqual(
                int(
                    db.execute(
                        "SELECT COUNT(*) AS total FROM job_applications"
                    ).fetchone()["total"]
                ),
                5000,
            )

        read_paths = (
            ("jobs_and_recommendations", "/api/job-matching/jobs"),
            ("my_applications", "/api/job-matching/applications"),
            ("skill_profile", "/api/job-matching/skill-profile"),
        )
        timings = {}
        payloads = {}
        for name, path in read_paths:
            started = time.perf_counter()
            response = self.client.get(path)
            elapsed = time.perf_counter() - started
            timings[name] = elapsed
            self.assertEqual(response.status_code, 200, name)
            payloads[name] = response.get_json()
            self.assertLess(
                elapsed,
                2.0,
                f"{name} took {elapsed:.3f}s",
            )

        self.assertEqual(
            len(payloads["jobs_and_recommendations"]["jobs"]),
            500,
        )
        self.assertEqual(
            len(
                payloads["jobs_and_recommendations"][
                    "recommended_jobs"
                ]
            ),
            500,
        )
        self.assertEqual(
            len(payloads["my_applications"]["applications"]),
            500,
        )
        self.assertEqual(
            len(payloads["skill_profile"]["profile"]["items"]),
            200,
        )
        print(
            "target-scale read timings: "
            + ", ".join(
                f"{name}={elapsed:.4f}s"
                for name, elapsed in timings.items()
            )
        )


if __name__ == "__main__":
    unittest.main()
