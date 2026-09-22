from __future__ import annotations

import tempfile
from pathlib import Path
from unittest import TestCase

from flask import jsonify, request
from werkzeug.security import generate_password_hash

from app import create_app
from app.admin_console.errors import (
    ProviderAccessDeniedError,
    ProviderConflictError,
    ProviderNotFoundError,
    ProviderUnavailableError,
    ProviderValidationError,
)
from app.db import get_db


class AdminPermissionsTests(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "PROPAGATE_EXCEPTIONS": False,
                "DATABASE_PATH": str(
                    Path(self.temp_dir.name) / "test.db"
                ),
                "SECRET_KEY": "test-only-secret",
                "SESSION_HOURS": 24,
                "SESSION_COOKIE_SECURE": False,
            }
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def _create_user(self, username: str, role: str) -> int:
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
                    f"{role}-{username}",
                    role,
                    "2026-09-20T10:00:00+08:00",
                    "2026-09-20T10:00:00+08:00",
                ),
            )
            user_id = int(cursor.lastrowid)
            get_db().commit()
        return user_id

    def _login(self, username: str):
        client = self.app.test_client()
        response = client.post(
            "/api/auth/login",
            json={"username": username, "password": "password8"},
        )
        self.assertEqual(response.status_code, 200)
        return client

    def _register_permission_route(self, roles: set[str]) -> None:
        def view():
            from app.admin_console.routes import require_admin_session

            session = require_admin_session(roles=roles)
            return jsonify(
                success=True,
                actor={
                    "id": int(session["id"]),
                    "role": session["role"],
                },
            )

        self.app.add_url_rule(
            "/api/admin/test-session-boundary",
            endpoint="test_admin_dashboard",
            view_func=view,
            methods=["GET", "POST"],
        )

    def _register_provider_error_route(self) -> None:
        def view():
            error_name = request.args["error"]
            error_type = {
                "validation": ProviderValidationError,
                "access_denied": ProviderAccessDeniedError,
                "not_found": ProviderNotFoundError,
                "conflict": ProviderConflictError,
                "unavailable": ProviderUnavailableError,
            }[error_name]
            raise error_type(
                f"{error_name} message",
                code=f"{error_name}_code",
                details={"kind": error_name},
            )

        self.app.add_url_rule(
            "/api/admin/test-provider-error",
            endpoint="test_admin_provider_error",
            view_func=view,
        )

    def test_admin_console_blueprint_is_registered(self):
        self.assertIn("admin_console", self.app.blueprints)
        self.assertEqual(
            self.app.blueprints["admin_console"].url_prefix,
            "/api/admin",
        )

    def test_anonymous_admin_request_is_rejected(self):
        self._register_permission_route({"super_admin"})

        response = self.app.test_client().get(
            "/api/admin/test-session-boundary"
        )

        self.assertEqual(response.status_code, 401)
        self.assertFalse(response.get_json()["success"])

    def test_super_admin_session_is_accepted(self):
        user_id = self._create_user("super-admin", "super_admin")
        self._register_permission_route({"super_admin"})
        client = self._login("super-admin")

        response = client.get("/api/admin/test-session-boundary")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json()["actor"],
            {"id": user_id, "role": "super_admin"},
        )

    def test_ordinary_admin_is_rejected_when_super_admin_is_required(self):
        user_id = self._create_user("ordinary-admin", "admin")
        self._register_permission_route({"super_admin"})
        client = self._login("ordinary-admin")

        response = client.post(
            "/api/admin/test-session-boundary",
            json={"role": "super_admin", "user_id": user_id + 100},
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.get_json(),
            {
                "success": False,
                "code": "admin_access_denied",
                "message": "无管理权限",
                "details": {},
            },
        )

    def test_admin_operations_accept_both_admin_roles(self):
        self._register_permission_route({"admin", "super_admin"})

        for username, role in (
            ("ordinary-admin", "admin"),
            ("super-admin", "super_admin"),
        ):
            user_id = self._create_user(username, role)
            with self.subTest(role=role):
                response = self._login(username).get(
                    "/api/admin/test-session-boundary"
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    response.get_json()["actor"],
                    {"id": user_id, "role": role},
                )

    def test_provider_errors_map_to_http_statuses_and_json_shape(self):
        self._create_user("super-admin", "super_admin")
        self._register_provider_error_route()
        client = self._login("super-admin")

        cases = (
            ("validation", 400),
            ("access_denied", 403),
            ("not_found", 404),
            ("conflict", 409),
            ("unavailable", 503),
        )
        for error_name, expected_status in cases:
            with self.subTest(error=error_name):
                response = client.get(
                    f"/api/admin/test-provider-error?error={error_name}"
                )

                self.assertEqual(response.status_code, expected_status)
                self.assertEqual(
                    response.get_json(),
                    {
                        "success": False,
                        "code": f"{error_name}_code",
                        "message": f"{error_name} message",
                        "details": {"kind": error_name},
                    },
                )


# --- permission matrix ------------------------------------------------------

# The acceptance baseline Task 28 pins. Account management, points policy,
# system announcements, the platform dashboard and every `/api/admin/content/*`
# verb stay super-admin-only; review, moderation, feedback, presets, rewards,
# redemptions, fulfillments and the content dashboard stay open to both admin
# roles. The tables below enumerate both groups verbatim so every row is
# asserted from both directions and a guard that is widened or narrowed turns
# the matching row red.

POLICY_ID = "policy-matrix-1"
NEWS_ID = "news-matrix-1"
FEEDBACK_ID = "feedback-matrix-1"
ANNOUNCEMENT_ID = "announcement-matrix-1"

CONTENT_TYPES = (
    "policy",
    "news",
    "course",
    "job",
    "handcraft_video",
    "comment",
    "preset",
)

CONTENT_VERBS = (
    ("get", "/api/admin/content/{content_type}", None),
    ("get", "/api/admin/content/{content_type}/{content_id}", None),
    (
        "put",
        "/api/admin/content/{content_type}/{content_id}",
        {"expected_version": 1, "title": "越权改写"},
    ),
    (
        "post",
        "/api/admin/content/{content_type}/{content_id}/unpublish",
        {"expected_version": 1},
    ),
    (
        "delete",
        "/api/admin/content/{content_type}/{content_id}",
        {"expected_version": 1},
    ),
)

PRESET_FAMILIES = (
    "handcraft_crafts",
    "success_cases",
    "assistant_knowledge",
    "agri_products",
    "agri_calendar",
    "pest_knowledge",
)

PRESET_VERBS = (
    ("get", "/api/admin/presets/{family}", None),
    ("post", "/api/admin/presets/{family}", {"name": "越权创建"}),
    ("put", "/api/admin/presets/{family}/matrix-item", {"expected_version": 1}),
    ("delete", "/api/admin/presets/{family}/matrix-item", {"expected_version": 1}),
)

# 008 and 009 answer a foreign-role session with `abort_session_required`
# (401) while 010 answers with an access-denied provider error (403). All
# three reject a console administrator, and the row counts asserted in
# `test_ordinary_admin_cannot_create_course_job_or_policy` are what proves no
# write landed regardless of which envelope the sibling console chose.
FOREIGN_CONSOLE_DENIAL_STATUS = {
    "/api/teacher/courses": 401,
    "/api/enterprise/jobs": 401,
    "/api/government/policies": 403,
}

DUAL_ROLE_READ_SHAPES = (
    ("/api/admin/content-dashboard", ("dashboard", "success"), None),
    ("/api/admin/review", ("counts", "items", "success"), "items"),
    ("/api/admin/comments", ("count", "items", "success"), "items"),
    ("/api/admin/reports", ("count", "items", "success"), "items"),
    ("/api/admin/feedback", ("count", "items", "success"), "items"),
    ("/api/admin/rewards", ("count", "items", "success"), "items"),
    ("/api/admin/redemptions", ("count", "items", "success"), "items"),
    ("/api/admin/fulfillments", ("count", "items", "success"), "items"),
) + tuple(
    (f"/api/admin/presets/{family}", ("count", "items", "success"), "items")
    for family in PRESET_FAMILIES
)

SUPER_ADMIN_READ_SHAPES = (
    ("/api/admin/dashboard", ("dashboard", "success"), None),
    ("/api/admin/accounts", ("accounts", "success"), "accounts"),
    ("/api/admin/points-policy", ("policy", "success"), None),
    ("/api/admin/announcements", ("count", "items", "success"), "items"),
    ("/api/admin/content/policy", ("count", "items", "success"), "items"),
    (f"/api/admin/content/policy/{POLICY_ID}", ("item", "success"), None),
)


def _content_routes() -> tuple:
    return tuple(
        (
            method,
            template.format(
                content_type=content_type,
                content_id=f"{content_type}-matrix-1",
            ),
            payload,
        )
        for content_type in CONTENT_TYPES
        for method, template, payload in CONTENT_VERBS
    )


def _preset_routes() -> tuple:
    return tuple(
        (method, template.format(family=family), payload)
        for family in PRESET_FAMILIES
        for method, template, payload in PRESET_VERBS
    )


def _super_admin_only_routes(target_user_id: int) -> tuple:
    rows = (
        ("get", "/api/admin/dashboard", None),
        ("get", "/api/admin/accounts", None),
        ("get", "/api/admin/accounts?keyword=matrix", None),
        ("get", f"/api/admin/accounts/{target_user_id}", None),
        (
            "post",
            "/api/admin/accounts",
            {
                "role": "enterprise",
                "username": "matrix-denied",
                "name": "越权创建",
                "password": "password8",
            },
        ),
        (
            "post",
            f"/api/admin/accounts/{target_user_id}/status",
            {"enabled": False},
        ),
        ("post", f"/api/admin/accounts/{target_user_id}/password-reset", None),
        ("get", "/api/admin/points-policy", None),
        ("put", "/api/admin/points-policy", {"expected_version": 1}),
        ("get", "/api/admin/announcements", None),
        (
            "post",
            "/api/admin/announcements",
            {"title": "越权公告", "body": "越权正文", "target_roles": ["student"]},
        ),
        ("post", f"/api/admin/announcements/{ANNOUNCEMENT_ID}/publish", None),
    )
    return rows + _content_routes()


def _dual_role_routes() -> tuple:
    rows = (
        ("get", "/api/admin/content-dashboard", None),
        ("get", "/api/admin/review", None),
        (
            "post",
            "/api/admin/review/course_video/course-matrix-1/approve",
            {"expected_version": 1},
        ),
        (
            "post",
            "/api/admin/review/course_video/course-matrix-1/reject",
            {"opinion": "越权驳回"},
        ),
        ("get", "/api/admin/comments", None),
        ("delete", "/api/admin/comments/comment-matrix-1", None),
        ("get", "/api/admin/reports", None),
        (
            "post",
            "/api/admin/reports/report-matrix-1/resolve",
            {"action": "hide"},
        ),
        ("get", "/api/admin/feedback", None),
        (
            "patch",
            f"/api/admin/feedback/{FEEDBACK_ID}",
            {"status": "closed", "result": "越权处理"},
        ),
        ("get", "/api/admin/rewards", None),
        ("post", "/api/admin/rewards", {"name": "越权奖品", "points_cost": 10}),
        ("put", "/api/admin/rewards/reward-matrix-1", {"expected_version": 1}),
        ("post", "/api/admin/rewards/reward-matrix-1/online", None),
        ("get", "/api/admin/redemptions", None),
        ("get", "/api/admin/redemptions/1", None),
        ("get", "/api/admin/fulfillments", None),
        ("post", "/api/admin/fulfillments/1/issue", None),
        ("post", "/api/admin/fulfillments/1/cancel", None),
        ("post", "/api/admin/fulfillments/1/verify", None),
    )
    return rows + _preset_routes()


def _request(client, method: str, path: str, payload):
    # A `json=None` body would still set an `application/json` content type on
    # the GET/DELETE reads, so the body is only attached when there is one.
    if payload is None:
        return getattr(client, method)(path)
    return getattr(client, method)(path, json=payload)


class AdminPermissionMatrixTests(TestCase):
    """Explicit positive and negative assertions for the 011 role matrix.

    The sibling test files already cover the session boundary, the points
    policy, the content five-route group and the announcements. This class
    keeps the whole matrix in one readable table instead of leaving it spread
    across those files, so a single run answers whether an ordinary admin can
    reach a surface it should not.
    """

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "PROPAGATE_EXCEPTIONS": False,
                "DATABASE_PATH": str(
                    Path(self.temp_dir.name) / "test.db"
                ),
                "SECRET_KEY": "test-only-secret",
                "SESSION_HOURS": 24,
                "SESSION_COOKIE_SECURE": False,
            }
        )
        with self.app.app_context():
            self.probe_user_id = self._create_user("matrix-student", "student")
            self._create_user("matrix-super-admin", "super_admin")
            self._create_user("matrix-admin", "admin")
            self._create_user("matrix-teacher", "teacher")
            self._create_user("matrix-enterprise", "enterprise")
            self._create_user("matrix-government", "government")
            self._seed_fixtures()
        self.super_admin = self._login("matrix-super-admin")
        self.admin = self._login("matrix-admin")
        self.anonymous = self.app.test_client()
        self.non_admin_clients = {
            role: self._login(f"matrix-{role}")
            for role in ("teacher", "enterprise", "student", "government")
        }
        self.super_admin_only = _super_admin_only_routes(self.probe_user_id)
        self.dual_role = _dual_role_routes()
        self.all_matrix_routes = self.super_admin_only + self.dual_role

    def tearDown(self):
        self.temp_dir.cleanup()

    # --- harness -------------------------------------------------------------

    def _create_user(self, username: str, role: str) -> int:
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
                    username,
                    role,
                    "2026-09-20T10:00:00+08:00",
                    "2026-09-20T10:00:00+08:00",
                ),
            )
            user_id = int(cursor.lastrowid)
            get_db().commit()
        return user_id

    def _login(self, username: str):
        # A brand new client every call: `abort_session_required` clears the
        # session cookie on the response, so a client that was once rejected
        # would otherwise be logged out and every later request would report
        # 401 for the wrong reason.
        client = self.app.test_client()
        response = client.post(
            "/api/auth/login",
            json={"username": username, "password": "password8"},
        )
        self.assertEqual(response.status_code, 200)
        return client

    def _seed_fixtures(self) -> None:
        db = get_db()
        db.execute(
            """
            INSERT INTO redemptions (
                id, user_id, reward_id, reward_name, reward_snapshot_json,
                points_cost, request_id, status, created_at, updated_at
            )
            VALUES (1, ?, 'reward-matrix', '矩阵探针奖品', '{}', 10,
                    'matrix-request-1', 'pending', ?, ?)
            """,
            (self.probe_user_id, "2026-09-21T10:00:00+08:00",
             "2026-09-21T10:00:00+08:00"),
        )
        db.execute(
            """
            INSERT INTO government_policies (
                id, title, content, category_code, status, version,
                created_by, published_at, created_at, updated_at
            )
            VALUES (?, '矩阵探针政策', '政策正文', 'general', 'active', 1,
                    1, ?, ?, ?)
            """,
            (POLICY_ID, "2026-09-21T10:00:00+08:00",
             "2026-09-21T10:00:00+08:00", "2026-09-21T10:00:00+08:00"),
        )
        db.execute(
            """
            INSERT INTO government_news (
                id, title, content, category_code, version,
                created_by, published_at, created_at, updated_at
            )
            VALUES (?, '矩阵探针资讯', '资讯正文', 'news', 1, 1, ?, ?, ?)
            """,
            (NEWS_ID, "2026-09-21T10:00:00+08:00",
             "2026-09-21T10:00:00+08:00", "2026-09-21T10:00:00+08:00"),
        )
        db.execute(
            """
            INSERT INTO feedback_records (
                feedback_id, submitter_id, body, status, idempotency_key,
                handler_id, result, created_at, updated_at
            )
            VALUES (?, ?, '矩阵探针反馈', 'pending', 'matrix-key-1',
                    NULL, NULL, ?, ?)
            """,
            (FEEDBACK_ID, self.probe_user_id, "2026-09-21T10:00:00+08:00",
             "2026-09-21T10:00:00+08:00"),
        )
        db.commit()

    def _count(self, table: str) -> int:
        with self.app.app_context():
            return int(
                get_db().execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            )

    def _row(self, sql: str, parameters: tuple = ()) -> tuple | None:
        with self.app.app_context():
            row = get_db().execute(sql, parameters).fetchone()
        return tuple(row) if row is not None else None

    # --- super-admin-only group ---------------------------------------------

    def test_super_admin_only_routes_reject_ordinary_admin(self):
        for method, path, payload in self.super_admin_only:
            with self.subTest(method=method, path=path):
                response = _request(self.admin, method, path, payload)
                self.assertEqual(response.status_code, 403, (method, path))
                body = response.get_json()
                self.assertFalse(body["success"])
                self.assertEqual(body["code"], "admin_access_denied")
                self.assertEqual(body["message"], "无管理权限")
                self.assertNotIn("items", body)
                self.assertNotIn("dashboard", body)
                self.assertNotIn("accounts", body)
                self.assertNotIn("policy", body)

    def test_super_admin_only_reads_stay_open_to_super_admin(self):
        for path, expected_keys, list_key in SUPER_ADMIN_READ_SHAPES:
            with self.subTest(path=path):
                response = self.super_admin.get(path)
                self.assertEqual(response.status_code, 200, path)
                body = response.get_json()
                self.assertTrue(body["success"])
                for key in expected_keys:
                    self.assertIn(key, body)
                if list_key is not None:
                    self.assertIsInstance(body[list_key], list)

    # --- dual-role group -----------------------------------------------------

    def test_dual_role_reads_accept_both_admin_roles(self):
        for label, client in (
            ("admin", self.admin),
            ("super_admin", self.super_admin),
        ):
            for path, expected_keys, list_key in DUAL_ROLE_READ_SHAPES:
                with self.subTest(role=label, path=path):
                    response = client.get(path)
                    self.assertEqual(response.status_code, 200, path)
                    body = response.get_json()
                    self.assertTrue(body["success"])
                    for key in expected_keys:
                        self.assertIn(key, body)
                    if list_key is not None:
                        self.assertIsInstance(body[list_key], list)

    def test_dual_role_writes_pass_the_role_guard_for_both_admin_roles(self):
        for label, client in (
            ("admin", self.admin),
            ("super_admin", self.super_admin),
        ):
            for method, path, payload in self.dual_role:
                if method == "get":
                    continue
                with self.subTest(role=label, method=method, path=path):
                    response = _request(client, method, path, payload)
                    self.assertNotIn(
                        response.status_code,
                        (401, 403),
                        (label, method, path),
                    )

    def test_ordinary_admin_reads_the_real_review_and_moderation_queues(self):
        review = self.admin.get("/api/admin/review")
        self.assertEqual(review.status_code, 200)
        body = review.get_json()
        self.assertTrue(body["success"])
        self.assertIsInstance(body["counts"], dict)
        self.assertIn("course_video", body["counts"])
        self.assertIn("job_position", body["counts"])
        self.assertIsInstance(body["items"], list)
        for item in body["items"]:
            self.assertIn("content_type", item)
            self.assertIn("content_id", item)

        moderation = self.admin.get("/api/admin/comments")
        self.assertEqual(moderation.status_code, 200)
        moderation_body = moderation.get_json()
        self.assertIsInstance(moderation_body["items"], list)
        self.assertEqual(
            moderation_body["count"], len(moderation_body["items"])
        )

    # --- matrix rows ---------------------------------------------------------

    def test_platform_dashboard_is_denied_while_content_dashboard_is_allowed(
        self,
    ):
        self.assertEqual(
            self.admin.get("/api/admin/dashboard").status_code, 403
        )
        self.assertEqual(
            self.admin.get("/api/admin/content-dashboard").status_code, 200
        )
        self.assertEqual(
            self.anonymous.get("/api/admin/dashboard").status_code, 401
        )
        self.assertEqual(
            self.super_admin.get("/api/admin/dashboard").status_code, 200
        )

    def test_ordinary_admin_cannot_create_course_job_or_policy(self):
        before = (
            self._count("courses"),
            self._count("job_positions"),
            self._count("government_policies"),
        )
        requests = (
            ("post", "/api/teacher/courses", {"title": "越权课程"}),
            ("post", "/api/enterprise/jobs", {"title": "越权岗位"}),
            (
                "post",
                "/api/government/policies",
                {"title": "越权政策", "content": "越权正文"},
            ),
        )
        for username in ("matrix-admin", "matrix-super-admin"):
            for method, path, payload in requests:
                # A fresh login per request: the first rejection clears the
                # session cookie, so reusing one client would make every
                # later status a 401 artefact instead of a real guard result.
                client = self._login(username)
                response = _request(client, method, path, payload)
                with self.subTest(role=username, method=method, path=path):
                    self.assertEqual(
                        response.status_code,
                        FOREIGN_CONSOLE_DENIAL_STATUS[path],
                    )
                    self.assertFalse(response.get_json()["success"])

        self.assertEqual(
            (
                self._count("courses"),
                self._count("job_positions"),
                self._count("government_policies"),
            ),
            before,
        )

    def test_ordinary_admin_reads_user_context_only_from_redemptions_and_fulfillments(
        self,
    ):
        redemptions = self.admin.get("/api/admin/redemptions/1")
        self.assertEqual(redemptions.status_code, 200)
        detail = redemptions.get_json()
        self.assertTrue(detail["success"])
        self.assertEqual(detail["id"], 1)
        self.assertEqual(detail["user"]["id"], self.probe_user_id)
        self.assertEqual(detail["user"]["role"], "student")
        self.assertEqual(detail["points_cost"], 10)
        self.assertIn("points_ledger", detail)
        self.assertNotIn("accounts", detail)
        self.assertNotIn("password", detail)

        self.assertEqual(
            self.admin.get("/api/admin/fulfillments").status_code, 200
        )
        self.assertEqual(
            self.admin.get("/api/admin/accounts").status_code, 403
        )
        self.assertEqual(
            self.admin.get("/api/admin/accounts?keyword=matrix").status_code, 403
        )
        self.assertEqual(
            self.admin.get(f"/api/admin/accounts/{self.probe_user_id}").status_code,
            403,
        )

    # --- anonymous and non-admin roles --------------------------------------

    def test_anonymous_requests_are_rejected_for_every_admin_route(self):
        for method, path, payload in self.all_matrix_routes:
            with self.subTest(method=method, path=path):
                response = _request(self.anonymous, method, path, payload)
                self.assertEqual(response.status_code, 401, (method, path))
                self.assertFalse(response.get_json()["success"])

    def test_non_admin_roles_are_denied_for_every_admin_route(self):
        for role, client in self.non_admin_clients.items():
            for method, path, payload in self.all_matrix_routes:
                with self.subTest(role=role, method=method, path=path):
                    response = _request(client, method, path, payload)
                    self.assertEqual(
                        response.status_code, 403, (role, method, path)
                    )
                    self.assertEqual(
                        response.get_json()["code"], "admin_access_denied"
                    )

    # --- data side effects ---------------------------------------------------

    def test_denied_accounts_write_creates_no_user(self):
        before = self._count("users")
        response = self.admin.post(
            "/api/admin/accounts",
            json={
                "role": "enterprise",
                "username": "matrix-denied",
                "name": "越权创建",
                "password": "password8",
            },
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(self._count("users"), before)
        self.assertIsNone(
            self._row("SELECT id FROM users WHERE username = 'matrix-denied'")
        )

    def test_denied_content_write_leaves_the_rows_untouched(self):
        before_policies = self._count("government_policies")
        before_policy_row = self._row(
            "SELECT title, content, version, status FROM government_policies"
            " WHERE id = ?",
            (POLICY_ID,),
        )
        before_news = self._count("government_news")

        corrected = self.admin.put(
            f"/api/admin/content/policy/{POLICY_ID}",
            json={
                "expected_version": 1,
                "title": "越权改写",
                "content": "越权正文",
            },
        )
        self.assertEqual(corrected.status_code, 403)
        self.assertEqual(self._count("government_policies"), before_policies)
        self.assertEqual(
            self._row(
                "SELECT title, content, version, status"
                " FROM government_policies WHERE id = ?",
                (POLICY_ID,),
            ),
            before_policy_row,
        )

        deleted = self.admin.delete(
            f"/api/admin/content/news/{NEWS_ID}",
            json={"expected_version": 1},
        )
        self.assertEqual(deleted.status_code, 403)
        self.assertEqual(self._count("government_news"), before_news)

    def test_denied_points_policy_write_keeps_the_stored_policy(self):
        before = self._row(
            "SELECT version, policy_json, updated_by FROM platform_points_policy"
        )
        response = self.admin.put(
            "/api/admin/points-policy",
            json={"expected_version": 1},
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            self._row(
                "SELECT version, policy_json, updated_by"
                " FROM platform_points_policy"
            ),
            before,
        )

    def test_denied_announcement_write_creates_no_announcement(self):
        before = self._count("system_announcements")
        response = self.admin.post(
            "/api/admin/announcements",
            json={
                "title": "越权公告",
                "body": "越权正文",
                "target_roles": ["student"],
            },
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(self._count("system_announcements"), before)

    def test_denied_dual_role_write_changes_no_reward_or_feedback(self):
        before_rewards = self._count("admin_rewards")
        response = self.non_admin_clients["teacher"].post(
            "/api/admin/rewards",
            json={"name": "越权奖品", "points_cost": 10},
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(self._count("admin_rewards"), before_rewards)

        before_feedback = self._row(
            "SELECT status, result, handler_id FROM feedback_records"
            " WHERE feedback_id = ?",
            (FEEDBACK_ID,),
        )
        response = self.non_admin_clients["student"].patch(
            f"/api/admin/feedback/{FEEDBACK_ID}",
            json={"status": "closed", "result": "越权处理"},
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            self._row(
                "SELECT status, result, handler_id FROM feedback_records"
                " WHERE feedback_id = ?",
                (FEEDBACK_ID,),
            ),
            before_feedback,
        )


if __name__ == "__main__":
    import unittest

    unittest.main()
