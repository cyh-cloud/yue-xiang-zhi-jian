import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from werkzeug.security import generate_password_hash

from app import create_app
from app.db import get_db
from app.enterprise_console.errors import (
    ProviderAccessDeniedError,
    ProviderUnavailableError,
)
from app.enterprise_console.review import set_content_review_provider
from app.session_manager import SESSION_COOKIE_NAME, issue_session


ROUTES = (
    ("GET", "/api/enterprise/dashboard", None),
    ("GET", "/api/enterprise/jobs", None),
    ("POST", "/api/enterprise/jobs", {}),
    ("GET", "/api/enterprise/jobs/job-a", None),
    ("PUT", "/api/enterprise/jobs/job-a", {}),
    ("DELETE", "/api/enterprise/jobs/job-a", {}),
    ("GET", "/api/enterprise/applications", None),
    (
        "GET",
        "/api/enterprise/applications/application-a-1",
        None,
    ),
    (
        "PATCH",
        "/api/enterprise/applications/application-a-1/status",
        {},
    ),
)


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
        self.calls.append(("get", content_id, content_type))
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


class TestEnterpriseApi(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(
                    Path(self.temp_dir.name) / "test.db"
                ),
                "SECRET_KEY": "test-only-secret",
                "SESSION_HOURS": 24,
                "SESSION_COOKIE_SECURE": False,
            }
        )

        self.enterprise_a_id = self._create_user(
            "enterprise-a",
            "企业甲",
            "enterprise",
        )
        self.enterprise_b_id = self._create_user(
            "enterprise-b",
            "企业乙",
            "enterprise",
        )
        self.student_id = self._create_user(
            "student-a",
            "学员甲",
            "student",
        )
        self.other_student_id = self._create_user(
            "student-b",
            "学员乙",
            "student",
        )
        self.teacher_id = self._create_user(
            "teacher-a",
            "教师甲",
            "teacher",
        )
        self.admin_id = self._create_user(
            "admin-a",
            "管理员甲",
            "admin",
        )
        self.government_id = self._create_user(
            "government-a",
            "政府甲",
            "government",
        )
        self.super_admin_id = self._create_user(
            "super-admin-a",
            "超级管理员甲",
            "super_admin",
        )

        with self.app.app_context():
            db = get_db()
            self.category_id = db.execute(
                """
                INSERT INTO interest_tags (
                    group_key, name, sort_order, is_active
                )
                VALUES ('job', '企业接口测试类别', 0, 1)
                """
            ).lastrowid
            self._insert_job(
                db,
                job_id="job-a",
                enterprise_id=self.enterprise_a_id,
                title="企业甲岗位",
            )
            self._insert_job(
                db,
                job_id="job-b",
                enterprise_id=self.enterprise_b_id,
                title="企业乙岗位",
            )
            self._insert_application(
                db,
                application_id="application-a-1",
                job_id="job-a",
                enterprise_id=self.enterprise_a_id,
                student_id=self.student_id,
                student_name="学员甲",
                job_title="企业甲岗位",
                submitted_at="2026-09-01T10:00:00+08:00",
            )
            self._insert_application(
                db,
                application_id="application-a-2",
                job_id="job-a",
                enterprise_id=self.enterprise_a_id,
                student_id=self.other_student_id,
                student_name="学员乙",
                job_title="企业甲岗位",
                submitted_at="2026-09-15T10:00:00+08:00",
                status="viewed",
                status_version=2,
            )
            self._insert_application(
                db,
                application_id="application-b-1",
                job_id="job-b",
                enterprise_id=self.enterprise_b_id,
                student_id=self.student_id,
                student_name="学员甲",
                job_title="企业乙岗位",
                submitted_at="2026-09-20T10:00:00+08:00",
            )
            db.commit()

        self.review_provider = FakeReviewProvider()
        set_content_review_provider(self.app, self.review_provider)

        self.client = self._login("enterprise-a")
        self.other_enterprise_client = self._login("enterprise-b")
        self.non_enterprise_clients = {
            username: self._login(username)
            for username in (
                "student-a",
                "teacher-a",
                "admin-a",
                "government-a",
                "super-admin-a",
            )
        }

    def tearDown(self):
        self.temp_dir.cleanup()

    def _create_user(self, username, name, role):
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
                    "2026-09-19T10:00:00+08:00",
                    "2026-09-19T10:00:00+08:00",
                ),
            )
            user_id = int(cursor.lastrowid)
            get_db().commit()
        return user_id

    def _login(self, username):
        client = self.app.test_client()
        response = client.post(
            "/api/auth/login",
            json={"username": username, "password": "password8"},
        )
        self.assertEqual(response.status_code, 200)
        return client

    def _insert_job(
        self,
        db,
        *,
        job_id,
        enterprise_id,
        title,
        review_status="pending",
        version=1,
        published_at=None,
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
                rejection_opinion,
                published_at,
                deleted_at,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, NULL, ?, ?)
            """,
            (
                job_id,
                enterprise_id,
                title,
                "6k-8k",
                "广州",
                self.category_id,
                "企业接口测试类别",
                "负责田间管理",
                review_status,
                version,
                published_at,
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
        submitted_at,
        status="pending",
        status_version=1,
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
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, NULL, 0, ?, ?, NULL, NULL, ?, ?, ?
            )
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
                f"key-{application_id}",
                submitted_at,
                submitted_at,
            ),
        )

    def _job_payload(self, **overrides):
        payload = {
            "title": "农业技术员",
            "salary": "6k-8k",
            "location": "广州",
            "category_id": self.category_id,
            "description": "负责田间管理",
        }
        payload.update(overrides)
        return payload

    def test_blueprint_registers_only_the_exact_route_table(self):
        actual = {
            (
                rule.rule,
                frozenset(rule.methods - {"HEAD", "OPTIONS"}),
            )
            for rule in self.app.url_map.iter_rules()
            if rule.rule.startswith("/api/enterprise")
        }
        expected = {
            (path, frozenset({method}))
            for method, path in (
                ("GET", "/api/enterprise/dashboard"),
                ("GET", "/api/enterprise/jobs"),
                ("POST", "/api/enterprise/jobs"),
                ("GET", "/api/enterprise/jobs/<job_id>"),
                ("PUT", "/api/enterprise/jobs/<job_id>"),
                ("DELETE", "/api/enterprise/jobs/<job_id>"),
                ("GET", "/api/enterprise/applications"),
                (
                    "GET",
                    "/api/enterprise/applications/<application_id>",
                ),
                (
                    "PATCH",
                    (
                        "/api/enterprise/applications/"
                        "<application_id>/status"
                    ),
                ),
            )
        }
        self.assertEqual(actual, expected)

    def test_anonymous_and_non_enterprise_roles_cannot_access_routes(self):
        clients = {"anonymous": self.app.test_client()}
        clients.update(self.non_enterprise_clients)

        for method, path, payload in ROUTES:
            for client_name, client in clients.items():
                with self.subTest(
                    method=method,
                    path=path,
                    client=client_name,
                ):
                    response = client.open(
                        path,
                        method=method,
                        json=payload,
                    )

                    self.assertEqual(response.status_code, 401)
                    self.assertEqual(
                        response.get_json()["message"],
                        "未登录或会话已过期",
                    )
                    self.assertFalse(response.get_json()["success"])

    def test_pending_enterprise_session_cannot_access_routes(self):
        with self.app.app_context():
            token = issue_session(
                self.enterprise_a_id,
                "pending",
                24,
            )
        client = self.app.test_client()
        client.set_cookie(SESSION_COOKIE_NAME, token)

        response = client.get("/api/enterprise/dashboard")

        self.assertEqual(response.status_code, 401)
        self.assertFalse(response.get_json()["success"])

    def test_read_routes_are_session_scoped_and_sync_job_detail(self):
        dashboard_before = self.client.get(
            "/api/enterprise/dashboard"
        )
        jobs = self.client.get("/api/enterprise/jobs")
        applications = self.client.get(
            "/api/enterprise/applications"
        )

        self.assertEqual(dashboard_before.status_code, 200)
        self.assertEqual(
            dashboard_before.get_json()["dashboard"],
            {
                "active_job_count": 0,
                "received_resume_count": 2,
            },
        )
        self.assertEqual(jobs.status_code, 200)
        self.assertEqual(
            [job["job_id"] for job in jobs.get_json()["jobs"]],
            ["job-a"],
        )
        self.assertEqual(
            [
                application["application_id"]
                for application in applications.get_json()["applications"]
            ],
            ["application-a-2", "application-a-1"],
        )

        self.review_provider.records["job-a"] = {
            "content_type": "job_position",
            "content_id": "job-a",
            "submitter_id": self.enterprise_a_id,
            "review_status": "approved",
            "version": 2,
            "rejection_opinion": None,
            "published_at": "2026-09-19T12:00:00+08:00",
        }
        detail = self.client.get("/api/enterprise/jobs/job-a")
        dashboard_after = self.client.get(
            "/api/enterprise/dashboard"
        )

        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.get_json()["job"]["review_status"], "approved")
        self.assertEqual(detail.get_json()["job"]["version"], 2)
        self.assertEqual(
            dashboard_after.get_json()["dashboard"]["active_job_count"],
            1,
        )

    def test_application_query_filters_are_parsed_and_scoped(self):
        response = self.client.get(
            (
                "/api/enterprise/applications?"
                "job_id=job-a&status=pending&"
                "submitted_from=2026-09-01&"
                "submitted_to=2026-09-01&sort=submitted_asc"
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [
                application["application_id"]
                for application in response.get_json()["applications"]
            ],
            ["application-a-1"],
        )

        invalid = self.client.get(
            (
                "/api/enterprise/applications?"
                "submitted_from=not-a-date"
            )
        )
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(
            set(invalid.get_json()),
            {"success", "message", "errors"},
        )

    def test_job_create_edit_delete_use_session_identity(self):
        created = self.client.post(
            "/api/enterprise/jobs",
            json=self._job_payload(
                enterprise_id=self.enterprise_b_id,
                review_status="approved",
                version=99,
                status_version=99,
            ),
        )

        self.assertEqual(created.status_code, 201)
        created_job = created.get_json()["job"]
        self.assertEqual(
            created_job["enterprise_id"],
            self.enterprise_a_id,
        )
        self.assertEqual(created_job["review_status"], "pending")
        self.assertEqual(created_job["version"], 1)
        submit_call = self.review_provider.calls[-1]
        self.assertEqual(submit_call[0], "submit")
        self.assertEqual(submit_call[2], self.enterprise_a_id)

        edited = self.client.put(
            f"/api/enterprise/jobs/{created_job['job_id']}",
            json=self._job_payload(
                expected_version=1,
                title="高级农业技术员",
                enterprise_id=self.enterprise_b_id,
                review_status="approved",
                version=999,
                status_version=999,
            ),
        )

        self.assertEqual(edited.status_code, 200)
        edited_job = edited.get_json()["job"]
        self.assertEqual(edited_job["title"], "高级农业技术员")
        self.assertEqual(
            edited_job["enterprise_id"],
            self.enterprise_a_id,
        )
        self.assertEqual(edited_job["review_status"], "pending")
        self.assertEqual(edited_job["version"], 2)

        deleted = self.client.delete(
            f"/api/enterprise/jobs/{created_job['job_id']}",
            json={
                "expected_version": 2,
                "enterprise_id": self.enterprise_b_id,
                "review_status": "approved",
                "version": 999,
            },
        )

        self.assertEqual(deleted.status_code, 200)
        self.assertTrue(deleted.get_json()["deleted"]["deleted"])
        missing = self.client.get(
            f"/api/enterprise/jobs/{created_job['job_id']}"
        )
        self.assertEqual(missing.status_code, 404)

    def test_application_detail_and_status_use_session_identity(self):
        detail = self.client.get(
            "/api/enterprise/applications/application-a-1"
        )
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(
            detail.get_json()["application"]["enterprise_id"],
            self.enterprise_a_id,
        )

        changed = self.client.patch(
            (
                "/api/enterprise/applications/"
                "application-a-1/status"
            ),
            json={
                "expected_version": 1,
                "status": "intent",
                "enterprise_id": self.enterprise_b_id,
                "version": 999,
                "status_version": 999,
                "review_status": "approved",
            },
        )

        self.assertEqual(changed.status_code, 200)
        application = changed.get_json()["application"]
        self.assertEqual(application["status"], "intent")
        self.assertEqual(application["status_version"], 2)
        self.assertEqual(
            application["enterprise_id"],
            self.enterprise_a_id,
        )
        self.assertTrue(changed.get_json()["changed"])

    def test_cross_enterprise_objects_do_not_leak_existence(self):
        before_calls = list(self.review_provider.calls)
        foreign_job = self.client.get(
            "/api/enterprise/jobs/job-b"
        )
        missing_job = self.client.get(
            "/api/enterprise/jobs/job-missing"
        )

        self.assertEqual(foreign_job.status_code, 404)
        self.assertEqual(foreign_job.get_json(), missing_job.get_json())
        self.assertEqual(self.review_provider.calls, before_calls)

        foreign_edit = self.client.put(
            "/api/enterprise/jobs/job-b",
            json=self._job_payload(expected_version=1),
        )
        missing_edit = self.client.put(
            "/api/enterprise/jobs/job-missing",
            json=self._job_payload(expected_version=1),
        )
        self.assertEqual(foreign_edit.status_code, 404)
        self.assertEqual(foreign_edit.get_json(), missing_edit.get_json())

        foreign_delete = self.client.delete(
            "/api/enterprise/jobs/job-b",
            json={"expected_version": 1},
        )
        missing_delete = self.client.delete(
            "/api/enterprise/jobs/job-missing",
            json={"expected_version": 1},
        )
        self.assertEqual(foreign_delete.status_code, 404)
        self.assertEqual(
            foreign_delete.get_json(),
            missing_delete.get_json(),
        )

        foreign_detail = self.client.get(
            "/api/enterprise/applications/application-b-1"
        )
        missing_detail = self.client.get(
            "/api/enterprise/applications/application-missing"
        )
        self.assertEqual(foreign_detail.status_code, 404)
        self.assertEqual(
            foreign_detail.get_json(),
            missing_detail.get_json(),
        )

        foreign_status = self.client.patch(
            (
                "/api/enterprise/applications/"
                "application-b-1/status"
            ),
            json={"expected_version": 1, "status": "intent"},
        )
        missing_status = self.client.patch(
            (
                "/api/enterprise/applications/"
                "application-missing/status"
            ),
            json={"expected_version": 1, "status": "intent"},
        )
        self.assertEqual(foreign_status.status_code, 404)
        self.assertEqual(
            foreign_status.get_json(),
            missing_status.get_json(),
        )

    def test_error_mapping_returns_stable_envelopes(self):
        validation = self.client.post(
            "/api/enterprise/jobs",
            json={},
        )
        self.assertEqual(validation.status_code, 400)
        self._assert_error_envelope(validation)

        non_object = self.client.post(
            "/api/enterprise/jobs",
            json=["not", "an", "object"],
        )
        self.assertEqual(non_object.status_code, 400)
        self._assert_error_envelope(non_object)

        missing = self.client.get(
            "/api/enterprise/jobs/job-missing"
        )
        self.assertEqual(missing.status_code, 404)
        self._assert_error_envelope(missing)

        with patch(
            "app.enterprise_console.routes._list_jobs",
            side_effect=ProviderAccessDeniedError("禁止访问"),
        ):
            access_denied = self.client.get("/api/enterprise/jobs")
        self.assertEqual(access_denied.status_code, 403)
        self._assert_error_envelope(access_denied)

        conflict = self.client.put(
            "/api/enterprise/jobs/job-a",
            json=self._job_payload(expected_version=999),
        )
        self.assertEqual(conflict.status_code, 409)
        self._assert_error_envelope(conflict)

        with patch(
            "app.enterprise_console.routes._get_dashboard",
            side_effect=ProviderUnavailableError("数据暂不可用"),
        ):
            unavailable = self.client.get(
                "/api/enterprise/dashboard"
            )
        self.assertEqual(unavailable.status_code, 503)
        self._assert_error_envelope(unavailable)

        with patch(
            "app.enterprise_console.routes._get_dashboard",
            side_effect=sqlite3.OperationalError(
                "raw database exception secret"
            ),
        ):
            database_error = self.client.get(
                "/api/enterprise/dashboard"
            )
        self.assertEqual(database_error.status_code, 503)
        self._assert_error_envelope(database_error)
        self.assertNotIn(
            "raw database exception secret",
            database_error.get_data(as_text=True),
        )

    def _assert_error_envelope(self, response):
        payload = response.get_json()
        self.assertEqual(
            set(payload),
            {"success", "message", "errors"},
        )
        self.assertFalse(payload["success"])
        self.assertIsInstance(payload["message"], str)
        self.assertIsInstance(payload["errors"], dict)


if __name__ == "__main__":
    unittest.main()
