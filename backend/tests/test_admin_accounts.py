from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from werkzeug.security import check_password_hash, generate_password_hash

from app import create_app
from app.db import get_db


class AdminAccountTests(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "test.db"
        self.app = self._create_app()

    def tearDown(self):
        self.temp_dir.cleanup()

    def _create_app(self, *, initial_password: str = ""):
        return create_app(
            {
                "TESTING": True,
                "PROPAGATE_EXCEPTIONS": False,
                "DATABASE_PATH": str(self.database_path),
                "SECRET_KEY": "test-only-secret",
                "SESSION_HOURS": 24,
                "SESSION_COOKIE_SECURE": False,
                "INITIAL_SUPER_ADMIN_PASSWORD": initial_password,
            }
        )

    def _create_user(
        self,
        username: str,
        role: str,
        *,
        name: str | None = None,
        password: str = "password8",
    ) -> int:
        with self.app.app_context():
            cursor = get_db().execute(
                """
                INSERT INTO users (
                    username, password_hash, name, role, is_enabled,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, 1, ?, ?)
                """,
                (
                    username,
                    generate_password_hash(password),
                    name or f"{role}-{username}",
                    role,
                    "2026-09-20T10:00:00+08:00",
                    "2026-09-20T10:00:00+08:00",
                ),
            )
            user_id = int(cursor.lastrowid)
            get_db().commit()
        return user_id

    def _login(self, username: str, password: str = "password8"):
        client = self.app.test_client()
        response = client.post(
            "/api/auth/login",
            json={"username": username, "password": password},
        )
        return client, response

    def test_create_disable_enable_reset_and_login_with_initial_password(self):
        actor_id = self._create_user("root-admin", "super_admin")
        client, login = self._login("root-admin")
        self.assertEqual(login.status_code, 200)

        created_response = client.post(
            "/api/admin/accounts",
            json={
                "role": "enterprise",
                "username": "enterprise-new",
                "name": "新企业",
                "password": "password8",
                "actor_id": actor_id + 100,
            },
        )
        self.assertEqual(created_response.status_code, 201)
        created = created_response.get_json()["account"]
        self.assertEqual(created["role"], "enterprise")
        self.assertTrue(created["is_enabled"])
        self.assertNotIn("password", created)
        self.assertNotIn("password_hash", created)

        _, enterprise_login = self._login("enterprise-new")
        self.assertEqual(enterprise_login.status_code, 200)

        disabled_response = client.post(
            f"/api/admin/accounts/{created['id']}/status",
            json={"enabled": False, "actor_id": actor_id + 100},
        )
        self.assertEqual(disabled_response.status_code, 200)
        self.assertFalse(disabled_response.get_json()["account"]["is_enabled"])
        _, disabled_login = self._login("enterprise-new")
        self.assertEqual(disabled_login.status_code, 403)

        enabled_response = client.post(
            f"/api/admin/accounts/{created['id']}/status",
            json={"enabled": True},
        )
        self.assertEqual(enabled_response.status_code, 200)
        _, enabled_login = self._login("enterprise-new")
        self.assertEqual(enabled_login.status_code, 200)

        self.app.config["INITIAL_SUPER_ADMIN_PASSWORD"] = "resetpass8"
        reset_response = client.post(
            f"/api/admin/accounts/{created['id']}/password-reset",
            json={"actor_id": actor_id + 100},
        )
        self.assertEqual(reset_response.status_code, 200)
        reset = reset_response.get_json()
        self.assertTrue(reset["success"])
        self.assertEqual(
            reset["event_id"],
            f"admin-password-reset:{created['id']}:2",
        )
        self.assertNotIn("password", reset)
        self.assertNotIn("password_hash", reset)

        _, old_password_login = self._login("enterprise-new")
        self.assertEqual(old_password_login.status_code, 401)
        _, new_password_login = self._login(
            "enterprise-new",
            "resetpass8",
        )
        self.assertEqual(new_password_login.status_code, 200)

        with self.app.app_context():
            notification = get_db().execute(
                """
                SELECT event_type, event_key
                FROM system_notifications
                WHERE recipient_id = ?
                """,
                (created["id"],),
            ).fetchone()
            audits = get_db().execute(
                """
                SELECT action, actor_id, before_json, after_json
                FROM admin_audit_log
                WHERE target_type = 'user' AND target_id = ?
                ORDER BY id
                """,
                (str(created["id"]),),
            ).fetchall()

        self.assertEqual(notification["event_type"], "password_reset")
        self.assertEqual(
            notification["event_key"],
            f"password_reset:{reset['event_id']}",
        )
        self.assertEqual(
            [row["action"] for row in audits],
            ["create_account", "disable_account", "enable_account", "reset_password"],
        )
        self.assertTrue(all(row["actor_id"] == actor_id for row in audits))
        self.assertNotIn("password", audits[0]["after_json"])
        self.assertNotIn("password_hash", audits[0]["after_json"])

    def test_password_reset_survives_notification_failure_then_retries(self):
        actor_id = self._create_user("root-admin", "super_admin")
        target_id = self._create_user(
            "enterprise-reset",
            "enterprise",
            password="password8",
        )
        self.app.config["INITIAL_SUPER_ADMIN_PASSWORD"] = "resetpass8"
        client, _ = self._login("root-admin")

        # The first delivery fails, yet the reset is committed: the version is
        # bumped and the new password logs in; only the shared outbox row is
        # left pending, so the failure is never surfaced as an error.
        with patch(
            "app.messaging.events.emit_password_reset",
            side_effect=OSError("gateway unreachable"),
        ):
            response = client.post(
                f"/api/admin/accounts/{target_id}/password-reset",
                json={"actor_id": actor_id + 100},
            )
        self.assertEqual(response.status_code, 200)
        reset = response.get_json()
        self.assertTrue(reset["success"])
        self.assertEqual(
            reset["event_id"],
            f"admin-password-reset:{target_id}:2",
        )

        _, old_login = self._login("enterprise-reset", "password8")
        self.assertEqual(old_login.status_code, 401)
        _, new_login = self._login("enterprise-reset", "resetpass8")
        self.assertEqual(new_login.status_code, 200)

        with self.app.app_context():
            row = get_db().execute(
                """
                SELECT status, attempts, event_id
                FROM admin_notification_outbox
                WHERE event_type = 'password_reset'
                """,
            ).fetchone()
        self.assertEqual(row["status"], "pending")
        self.assertEqual(row["attempts"], 1)
        self.assertEqual(row["event_id"], reset["event_id"])

        # After the deliverer recovers, the shared retry delivers it exactly
        # once on the frozen event id.
        from app.admin_console.outbox import retry_admin_notifications

        with self.app.app_context():
            summary = retry_admin_notifications()
        self.assertEqual(summary["delivered"], 1)

        with self.app.app_context():
            row = get_db().execute(
                """
                SELECT status, attempts
                FROM admin_notification_outbox
                WHERE event_type = 'password_reset'
                """,
            ).fetchone()
            notifications = get_db().execute(
                """
                SELECT COUNT(*) AS count
                FROM system_notifications
                WHERE recipient_id = ? AND event_type = 'password_reset'
                """,
                (target_id,),
            ).fetchone()["count"]
        self.assertEqual(row["status"], "sent")
        self.assertEqual(row["attempts"], 2)
        self.assertEqual(notifications, 1)

    def test_account_list_and_detail_apply_role_keyword_filters_without_secrets(self):
        actor_id = self._create_user("root-admin", "super_admin")
        enterprise_id = self._create_user(
            "alpha-enterprise",
            "enterprise",
            name="岭南农业",
        )
        self._create_user(
            "beta-government",
            "government",
            name="岭南政务",
        )
        client, _ = self._login("root-admin")

        response = client.get(
            "/api/admin/accounts?role=enterprise&keyword=岭南"
        )
        self.assertEqual(response.status_code, 200)
        accounts = response.get_json()["accounts"]
        self.assertEqual([account["id"] for account in accounts], [enterprise_id])
        self.assertEqual(
            set(accounts[0]),
            {
                "id",
                "username",
                "name",
                "role",
                "is_enabled",
                "created_at",
                "updated_at",
            },
        )

        detail = client.get(f"/api/admin/accounts/{enterprise_id}")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.get_json()["account"]["username"], "alpha-enterprise")
        self.assertNotIn("password_hash", detail.get_json()["account"])
        self.assertEqual(
            client.get(f"/api/admin/accounts/{actor_id + 1000}").status_code,
            404,
        )

    def test_account_list_rejects_non_managed_role_filters_and_hides_them(self):
        actor_id = self._create_user("root-admin", "super_admin")
        self._create_user("student-account", "student")
        self._create_user("teacher-account", "teacher")
        client, _ = self._login("root-admin")

        response = client.get("/api/admin/accounts")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [account["id"] for account in response.get_json()["accounts"]],
            [actor_id],
        )

        for role in ("student", "teacher"):
            with self.subTest(role=role):
                response = client.get(
                    f"/api/admin/accounts?role={role}"
                )
                self.assertEqual(response.status_code, 400)
                self.assertEqual(
                    response.get_json()["details"],
                    {"role": "角色不正确"},
                )

    def test_non_managed_account_detail_is_not_visible(self):
        self._create_user("root-admin", "super_admin")
        student_id = self._create_user("student-account", "student")
        teacher_id = self._create_user("teacher-account", "teacher")
        client, _ = self._login("root-admin")

        for user_id in (student_id, teacher_id):
            with self.subTest(user_id=user_id):
                response = client.get(f"/api/admin/accounts/{user_id}")
                self.assertEqual(response.status_code, 404)
                self.assertEqual(
                    response.get_json()["code"],
                    "account_not_found",
                )

    def test_non_managed_account_status_is_not_mutable(self):
        self._create_user("root-admin", "super_admin")
        target_ids = (
            self._create_user("student-account", "student"),
            self._create_user("teacher-account", "teacher"),
        )
        client, _ = self._login("root-admin")

        for user_id in target_ids:
            with self.subTest(user_id=user_id):
                response = client.post(
                    f"/api/admin/accounts/{user_id}/status",
                    json={"enabled": False},
                )
                self.assertEqual(response.status_code, 404)

        with self.app.app_context():
            enabled_states = [
                get_db().execute(
                    "SELECT is_enabled FROM users WHERE id = ?",
                    (user_id,),
                ).fetchone()["is_enabled"]
                for user_id in target_ids
            ]
            audit_count = get_db().execute(
                """
                SELECT COUNT(*) AS count
                FROM admin_audit_log
                WHERE target_type = 'user'
                """
            ).fetchone()["count"]
        self.assertEqual(enabled_states, [1, 1])
        self.assertEqual(audit_count, 0)

    def test_non_managed_account_password_is_not_reset(self):
        self._create_user("root-admin", "super_admin")
        target_ids = (
            self._create_user("student-account", "student"),
            self._create_user("teacher-account", "teacher"),
        )
        client, _ = self._login("root-admin")
        self.app.config["INITIAL_SUPER_ADMIN_PASSWORD"] = "resetpass8"

        with self.app.app_context():
            before_hashes = [
                get_db().execute(
                    "SELECT password_hash FROM users WHERE id = ?",
                    (user_id,),
                ).fetchone()["password_hash"]
                for user_id in target_ids
            ]

        for user_id in target_ids:
            with self.subTest(user_id=user_id):
                response = client.post(
                    f"/api/admin/accounts/{user_id}/password-reset"
                )
                self.assertEqual(response.status_code, 404)

        with self.app.app_context():
            after_hashes = [
                get_db().execute(
                    "SELECT password_hash FROM users WHERE id = ?",
                    (user_id,),
                ).fetchone()["password_hash"]
                for user_id in target_ids
            ]
            notification_count = get_db().execute(
                """
                SELECT COUNT(*) AS count
                FROM system_notifications
                WHERE event_type = 'password_reset'
                """
            ).fetchone()["count"]
            audit_count = get_db().execute(
                """
                SELECT COUNT(*) AS count
                FROM admin_audit_log
                WHERE action = 'reset_password'
                """
            ).fetchone()["count"]
        self.assertEqual(after_hashes, before_hashes)
        self.assertEqual(notification_count, 0)
        self.assertEqual(audit_count, 0)

    def test_ordinary_admin_is_denied_without_account_existence_leakage(self):
        self._create_user("ordinary-admin", "admin")
        target_id = self._create_user("target-enterprise", "enterprise")
        client, login = self._login("ordinary-admin")
        self.assertEqual(login.status_code, 200)

        requests = (
            ("get", "/api/admin/accounts", None),
            ("get", f"/api/admin/accounts/{target_id}", None),
            ("get", f"/api/admin/accounts/{target_id + 1000}", None),
            (
                "post",
                "/api/admin/accounts",
                {
                    "role": "enterprise",
                    "username": "not-created",
                    "name": "不应创建",
                    "password": "password8",
                },
            ),
            (
                "post",
                f"/api/admin/accounts/{target_id}/status",
                {"enabled": False},
            ),
            (
                "post",
                f"/api/admin/accounts/{target_id + 1000}/status",
                {"enabled": False},
            ),
            (
                "post",
                f"/api/admin/accounts/{target_id}/password-reset",
                None,
            ),
            (
                "post",
                f"/api/admin/accounts/{target_id + 1000}/password-reset",
                None,
            ),
        )
        responses = []
        for method, path, payload in requests:
            response = getattr(client, method)(path, json=payload)
            self.assertEqual(response.status_code, 403, (method, path))
            self.assertEqual(
                response.get_json(),
                {
                    "success": False,
                    "code": "admin_access_denied",
                    "message": "无管理权限",
                    "details": {},
                },
            )
            responses.append(response.get_json())

        self.assertEqual(responses[1], responses[2])
        self.assertEqual(responses[4], responses[5])
        self.assertEqual(responses[6], responses[7])
        with self.app.app_context():
            account_count = get_db().execute(
                "SELECT COUNT(*) AS count FROM users WHERE username = ?",
                ("not-created",),
            ).fetchone()["count"]
            target_enabled = get_db().execute(
                "SELECT is_enabled FROM users WHERE id = ?",
                (target_id,),
            ).fetchone()["is_enabled"]
        self.assertEqual(account_count, 0)
        self.assertEqual(target_enabled, 1)

    def test_create_validates_role_username_name_password_and_uniqueness(self):
        self._create_user("root-admin", "super_admin")
        client, _ = self._login("root-admin")

        valid = client.post(
            "/api/admin/accounts",
            json={
                "role": "government",
                "username": "government-valid",
                "name": "政务账号",
                "password": "password8",
            },
        )
        self.assertEqual(valid.status_code, 201)

        cases = (
            (
                {
                    "role": "student",
                    "username": "student-role",
                    "name": "非法角色",
                    "password": "password8",
                },
                400,
                "role",
            ),
            (
                {
                    "role": "enterprise",
                    "username": "a",
                    "name": "短用户名",
                    "password": "password8",
                },
                400,
                "username",
            ),
            (
                {
                    "role": "enterprise",
                    "username": "missing-name",
                    "name": "   ",
                    "password": "password8",
                },
                400,
                "name",
            ),
            (
                {
                    "role": "enterprise",
                    "username": "short-password",
                    "name": "短密码",
                    "password": "short",
                },
                400,
                "password",
            ),
            (
                {
                    "role": "government",
                    "username": "government-valid",
                    "name": "重复账号",
                    "password": "password8",
                },
                409,
                "username",
            ),
        )
        for payload, expected_status, expected_detail in cases:
            with self.subTest(username=payload["username"]):
                response = client.post("/api/admin/accounts", json=payload)
                self.assertEqual(response.status_code, expected_status)
                self.assertIn(expected_detail, response.get_json()["details"])

        with self.app.app_context():
            count = get_db().execute(
                """
                SELECT COUNT(*) AS count
                FROM users
                WHERE username IN (
                    'student-role', 'a', 'missing-name',
                    'short-password', 'government-valid'
                )
                """
            ).fetchone()["count"]
        self.assertEqual(count, 1)

    def test_account_management_has_no_physical_delete_route(self):
        self._create_user("root-admin", "super_admin")
        target_id = self._create_user("target-enterprise", "enterprise")
        client, _ = self._login("root-admin")

        response = client.delete(f"/api/admin/accounts/{target_id}")

        self.assertEqual(response.status_code, 405)
        with self.app.app_context():
            count = get_db().execute(
                "SELECT COUNT(*) AS count FROM users WHERE id = ?",
                (target_id,),
            ).fetchone()["count"]
        self.assertEqual(count, 1)

    def test_initial_super_admin_seed_is_hashed_idempotent_and_non_overwriting(self):
        with patch.dict(
            os.environ,
            {"INITIAL_SUPER_ADMIN_PASSWORD": "seedpass8"},
            clear=False,
        ):
            app = create_app(
                {
                    "TESTING": True,
                    "DATABASE_PATH": str(self.database_path),
                    "SECRET_KEY": "test-only-secret",
                }
            )

        with app.app_context():
            rows = get_db().execute(
                """
                SELECT id, username, password_hash
                FROM users
                WHERE role = 'super_admin'
                """
            ).fetchall()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["username"], "superadmin")
            self.assertNotEqual(rows[0]["password_hash"], "seedpass8")
            self.assertTrue(
                check_password_hash(rows[0]["password_hash"], "seedpass8")
            )
            seeded_id = int(rows[0]["id"])
            get_db().execute(
                "UPDATE users SET password_hash = ? WHERE id = ?",
                (generate_password_hash("changed-password"), seeded_id),
            )
            get_db().commit()

        with patch.dict(
            os.environ,
            {"INITIAL_SUPER_ADMIN_PASSWORD": "replacement8"},
            clear=False,
        ):
            second_app = create_app(
                {
                    "TESTING": True,
                    "DATABASE_PATH": str(self.database_path),
                    "SECRET_KEY": "test-only-secret",
                }
            )

        with second_app.app_context():
            rows = get_db().execute(
                """
                SELECT id, password_hash
                FROM users
                WHERE role = 'super_admin'
                """
            ).fetchall()
            self.assertEqual(len(rows), 1)
            self.assertEqual(int(rows[0]["id"]), seeded_id)
            self.assertTrue(
                check_password_hash(
                    rows[0]["password_hash"],
                    "changed-password",
                )
            )
            self.assertFalse(
                check_password_hash(
                    rows[0]["password_hash"],
                    "replacement8",
                )
            )


if __name__ == "__main__":
    import unittest

    unittest.main()
