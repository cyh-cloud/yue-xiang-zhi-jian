import hashlib
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from werkzeug.security import generate_password_hash

from app import create_app
from app.db import get_db


class TestLoginSession(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(Path(self.temp_dir.name) / "test.db"),
                "SECRET_KEY": "test-only-secret",
                "SESSION_HOURS": 24,
                "SESSION_COOKIE_SECURE": False,
            }
        )
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def create_user(
        self,
        *,
        username: str,
        role: str = "student",
        password: str = "password8",
        is_enabled: bool = True,
    ) -> int:
        now = datetime.now(timezone.utc).isoformat()
        with self.app.app_context():
            cursor = get_db().execute(
                """
                INSERT INTO users (
                    username, password_hash, name, role, is_enabled,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    username,
                    generate_password_hash(password),
                    f"{role}-{username}",
                    role,
                    int(is_enabled),
                    now,
                    now,
                ),
            )
            get_db().commit()
        return int(cursor.lastrowid)

    def test_all_roles_route_to_expected_portal(self):
        cases = {
            "student": "/student",
            "teacher": "/teacher",
            "enterprise": "/enterprise",
            "government": "/government",
            "super_admin": "/admin",
            "admin": "/admin",
        }
        for role, expected in cases.items():
            with self.subTest(role=role):
                self.create_user(role=role, username=f"{role}01")
                response = self.client.post(
                    "/api/auth/login",
                    json={"username": f"{role}01", "password": "password8"},
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.get_json()["default_path"], expected)

    def test_unknown_username_and_wrong_password_share_message(self):
        self.create_user(username="student01")
        responses = [
            self.client.post(
                "/api/auth/login",
                json={"password": "password8"},
            ),
            self.client.post(
                "/api/auth/login",
                json={"username": "missing", "password": "password8"},
            ),
            self.client.post(
                "/api/auth/login",
                json={"username": "student01", "password": "wrongpass"},
            ),
        ]
        for response in responses:
            self.assertEqual(response.status_code, 401)
            self.assertEqual(
                response.get_json()["message"],
                "用户名或密码错误",
            )

    def test_disabled_account_has_distinct_message(self):
        self.create_user(username="disabled01", is_enabled=False)

        response = self.client.post(
            "/api/auth/login",
            json={"username": "disabled01", "password": "password8"},
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.get_json()["message"],
            "账户已被禁用，请联系管理员",
        )

    def test_login_creates_active_hashed_session_and_cookie(self):
        user_id = self.create_user(username="student01")

        response = self.client.post(
            "/api/auth/login",
            json={"username": "student01", "password": "password8"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json()["user"],
            {
                "id": user_id,
                "username": "student01",
                "name": "student-student01",
                "role": "student",
            },
        )
        set_cookie = response.headers["Set-Cookie"]
        self.assertIn("yx_session=", set_cookie)
        self.assertIn("HttpOnly", set_cookie)
        self.assertIn("SameSite=Lax", set_cookie)
        self.assertIn("Max-Age=86400", set_cookie)
        self.assertNotIn("Secure", set_cookie)
        raw_token = set_cookie.split("yx_session=", 1)[1].split(";", 1)[0]
        with self.app.app_context():
            session = get_db().execute(
                "SELECT token_hash, state FROM sessions WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        self.assertEqual(session["state"], "active")
        self.assertEqual(
            session["token_hash"],
            hashlib.sha256(raw_token.encode("utf-8")).hexdigest(),
        )
        self.assertNotEqual(session["token_hash"], raw_token)

    def test_login_revokes_previous_cookie_session(self):
        self.create_user(username="student01")
        first = self.client.post(
            "/api/auth/login",
            json={"username": "student01", "password": "password8"},
        )
        first_token = first.headers["Set-Cookie"].split("yx_session=", 1)[1].split(
            ";", 1
        )[0]

        second = self.client.post(
            "/api/auth/login",
            json={"username": "student01", "password": "password8"},
        )

        self.assertEqual(second.status_code, 200)
        with self.app.app_context():
            sessions = get_db().execute(
                "SELECT token_hash FROM sessions WHERE user_id = 1"
            ).fetchall()
        self.assertEqual(len(sessions), 1)
        self.assertNotEqual(
            sessions[0]["token_hash"],
            hashlib.sha256(first_token.encode("utf-8")).hexdigest(),
        )

    def test_active_session_returns_user_and_default_path(self):
        self.create_user(username="teacher01", role="teacher")
        self.client.post(
            "/api/auth/login",
            json={"username": "teacher01", "password": "password8"},
        )

        response = self.client.get("/api/auth/session")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json(),
            {
                "success": True,
                "state": "active",
                "user": {
                    "id": 1,
                    "username": "teacher01",
                    "name": "teacher-teacher01",
                    "role": "teacher",
                },
                "default_path": "/teacher",
            },
        )

    def test_pending_student_session_recovers_interest_tag_step(self):
        response = self.client.post(
            "/api/auth/register",
            json={
                "role": "student",
                "username": "student01",
                "password": "password8",
                "confirm_password": "password8",
                "name": "林晓",
            },
        )
        self.assertEqual(response.status_code, 201)

        session = self.client.get("/api/auth/session")

        self.assertEqual(session.status_code, 200)
        self.assertEqual(session.get_json()["state"], "pending")
        self.assertEqual(session.get_json()["next_step"], "interest-tags")
        self.assertEqual(
            session.get_json()["default_path"],
            "/register/interest-tags",
        )
        self.assertEqual(session.get_json()["user"]["role"], "student")

    def test_pending_session_cannot_open_protected_portal(self):
        self.client.post(
            "/api/auth/register",
            json={
                "role": "student",
                "username": "student01",
                "password": "password8",
                "confirm_password": "password8",
                "name": "林晓",
            },
        )

        response = self.client.get("/api/student/profile")

        self.assertEqual(response.status_code, 401)

    def test_expired_session_redirects_with_original_target(self):
        response = self.client.get(
            "/api/student/profile?next=/student/courses"
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.get_json()["redirect"],
            "/login?redirect=%2Fstudent%2Fcourses",
        )

    def test_expired_cookie_is_rejected(self):
        self.create_user(username="student01")
        self.client.post(
            "/api/auth/login",
            json={"username": "student01", "password": "password8"},
        )
        with self.app.app_context():
            get_db().execute(
                "UPDATE sessions SET expires_at = ?",
                ("2000-01-01T00:00:00+00:00",),
            )
            get_db().commit()

        response = self.client.get("/api/auth/session")

        self.assertEqual(response.status_code, 401)
        self.assertIn("redirect", response.get_json())

    def test_session_validation_removes_all_expired_rows(self):
        self.create_user(username="expired01")
        self.create_user(username="expired02")
        active_user_id = self.create_user(username="active01")
        for username in ("expired01", "expired02"):
            separate_client = self.app.test_client()
            separate_client.post(
                "/api/auth/login",
                json={"username": username, "password": "password8"},
            )
        self.client.post(
            "/api/auth/login",
            json={"username": "active01", "password": "password8"},
        )

        with self.app.app_context():
            get_db().execute(
                """
                UPDATE sessions
                SET expires_at = '2000-01-01T00:00:00+00:00'
                WHERE user_id IN (
                    SELECT id FROM users WHERE username IN ('expired01', 'expired02')
                )
                """,
            )
            get_db().commit()

        response = self.client.get("/api/auth/session")

        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            expired_count = get_db().execute(
                """
                SELECT COUNT(*) AS count
                FROM sessions
                WHERE expires_at <= '2000-01-01T00:00:00+00:00'
                """
            ).fetchone()["count"]
            active_count = get_db().execute(
                "SELECT COUNT(*) AS count FROM sessions WHERE user_id = ?",
                (active_user_id,),
            ).fetchone()["count"]
        self.assertEqual(expired_count, 0)
        self.assertEqual(active_count, 1)

    def test_disabled_account_invalidates_existing_session(self):
        self.create_user(username="student01")
        self.client.post(
            "/api/auth/login",
            json={"username": "student01", "password": "password8"},
        )
        with self.app.app_context():
            get_db().execute(
                "UPDATE users SET is_enabled = 0 WHERE username = 'student01'"
            )
            get_db().commit()

        response = self.client.get("/api/student/profile")

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.get_json()["message"],
            "账户已被禁用，请联系管理员",
        )
        with self.app.app_context():
            count = get_db().execute(
                "SELECT COUNT(*) AS count FROM sessions"
            ).fetchone()["count"]
        self.assertEqual(count, 0)

    def test_logout_revokes_session_and_clears_cookie(self):
        self.create_user(username="student01")
        self.client.post(
            "/api/auth/login",
            json={"username": "student01", "password": "password8"},
        )

        response = self.client.post("/api/auth/logout")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"success": True})
        self.assertIn("yx_session=;", response.headers["Set-Cookie"])
        self.assertIn("Max-Age=0", response.headers["Set-Cookie"])
        self.assertEqual(self.client.get("/api/auth/session").status_code, 401)
        with self.app.app_context():
            count = get_db().execute(
                "SELECT COUNT(*) AS count FROM sessions"
            ).fetchone()["count"]
        self.assertEqual(count, 0)

    def test_secure_cookie_flag_uses_application_config(self):
        self.app.config["SESSION_COOKIE_SECURE"] = True
        self.create_user(username="student01")

        response = self.client.post(
            "/api/auth/login",
            json={"username": "student01", "password": "password8"},
        )

        self.assertIn("Secure", response.headers["Set-Cookie"])


if __name__ == "__main__":
    unittest.main()
