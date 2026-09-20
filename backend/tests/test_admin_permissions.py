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
            "/api/admin/dashboard",
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

        response = self.app.test_client().get("/api/admin/dashboard")

        self.assertEqual(response.status_code, 401)
        self.assertFalse(response.get_json()["success"])

    def test_super_admin_session_is_accepted(self):
        user_id = self._create_user("super-admin", "super_admin")
        self._register_permission_route({"super_admin"})
        client = self._login("super-admin")

        response = client.get("/api/admin/dashboard")

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
            "/api/admin/dashboard",
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
                    "/api/admin/dashboard"
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


if __name__ == "__main__":
    import unittest

    unittest.main()
