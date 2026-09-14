import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from werkzeug.security import generate_password_hash

from app import create_app
from app.db import get_db


class TestOnboarding(unittest.TestCase):
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

    def create_user(self, username: str, role: str) -> int:
        now = datetime.now(timezone.utc).isoformat()
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
                    generate_password_hash("password8"),
                    f"{role}-{username}",
                    role,
                    now,
                    now,
                ),
            )
            get_db().commit()
        return int(cursor.lastrowid)

    def login_user(self, username: str, role: str) -> None:
        self.create_user(username, role)
        response = self.client.post(
            "/api/auth/login",
            json={"username": username, "password": "password8"},
        )
        self.assertEqual(response.status_code, 200)

    def test_first_login_requires_onboarding_without_recording_state(self):
        self.login_user("teacher01", "teacher")

        first = self.client.get("/api/onboarding/teacher")
        second = self.client.get("/api/onboarding/teacher")

        self.assertEqual(first.status_code, 200)
        self.assertEqual(
            first.get_json(),
            {"success": True, "required": True, "portal": "teacher"},
        )
        self.assertEqual(second.get_json()["required"], True)

    def test_complete_and_skip_suppress_future_prompt(self):
        for index, outcome in enumerate(("completed", "skipped"), start=1):
            with self.subTest(outcome=outcome):
                username = f"teacher0{index}"
                self.login_user(username, "teacher")

                response = self.client.post(
                    "/api/onboarding/teacher/complete",
                    json={"outcome": outcome},
                )

                self.assertEqual(response.status_code, 200)
                state = self.client.get("/api/onboarding/teacher")
                self.assertEqual(
                    state.get_json(),
                    {"success": True, "required": False, "portal": "teacher"},
                )
                self.client.post("/api/auth/logout")

    def test_completion_is_independent_per_user(self):
        self.login_user("teacher01", "teacher")
        completed = self.client.post(
            "/api/onboarding/teacher/complete",
            json={"outcome": "completed"},
        )
        self.assertEqual(completed.status_code, 200)

        self.client.post("/api/auth/logout")
        self.login_user("teacher02", "teacher")

        response = self.client.get("/api/onboarding/teacher")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["required"])

    def test_role_must_match_the_requested_portal(self):
        self.login_user("teacher01", "teacher")

        get_response = self.client.get("/api/onboarding/student")
        post_response = self.client.post(
            "/api/onboarding/student/complete",
            json={"outcome": "completed"},
        )

        self.assertEqual(get_response.status_code, 403)
        self.assertEqual(post_response.status_code, 403)

    def test_all_roles_map_to_their_exact_portals(self):
        roles = {
            "student": "student",
            "teacher": "teacher",
            "enterprise": "enterprise",
            "government": "government",
            "super_admin": "admin",
            "admin": "admin",
        }

        for index, (role, portal) in enumerate(roles.items(), start=1):
            with self.subTest(role=role):
                username = f"roleuser{index}"
                self.login_user(username, role)

                response = self.client.get(f"/api/onboarding/{portal}")

                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.get_json()["portal"], portal)
                self.client.post("/api/auth/logout")

    def test_invalid_outcome_does_not_record_completion(self):
        self.login_user("teacher01", "teacher")

        response = self.client.post(
            "/api/onboarding/teacher/complete",
            json={"outcome": "closed"},
        )

        self.assertEqual(response.status_code, 400)
        state = self.client.get("/api/onboarding/teacher")
        self.assertTrue(state.get_json()["required"])

    def test_active_session_is_required(self):
        get_response = self.client.get("/api/onboarding/teacher")
        post_response = self.client.post(
            "/api/onboarding/teacher/complete",
            json={"outcome": "completed"},
        )

        self.assertEqual(get_response.status_code, 401)
        self.assertEqual(post_response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
