import tempfile
import unittest
from pathlib import Path

from app import create_app
from app.profiles.service import (
    get_profile_preferences,
    update_student_profile,
)


class TestStudentProfile(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(Path(self.temp_dir.name) / "test.db"),
                "SECRET_KEY": "test-only-secret",
                "SESSION_HOURS": 24,
            }
        )
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def login_student(self, username: str, tag_ids: list[int] | None = None):
        registered = self.client.post(
            "/api/auth/register",
            json={
                "role": "student",
                "username": username,
                "password": "password8",
                "confirm_password": "password8",
                "name": "林晓",
            },
        )
        self.assertEqual(registered.status_code, 201)
        completed = self.client.post(
            "/api/auth/interest-tags",
            json={"tag_ids": tag_ids or []},
        )
        self.assertEqual(completed.status_code, 200)

    def test_profile_returns_default_direction_and_selected_tags(self):
        self.login_student("student01")

        response = self.client.get("/api/student/profile")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json()["profile"],
            {
                "name": "林晓",
                "contact": "",
                "learning_direction": "comprehensive",
                "tag_ids": [],
            },
        )

    def test_profile_update_persists_allowed_fields(self):
        self.login_student("student01")

        response = self.client.put(
            "/api/student/profile",
            json={
                "name": "  陈晓  ",
                "contact": "  13800000000  ",
                "learning_direction": "ecommerce",
                "tag_ids": [5, 6],
            },
        )

        self.assertEqual(response.status_code, 200)
        expected = {
            "name": "陈晓",
            "contact": "13800000000",
            "learning_direction": "ecommerce",
            "tag_ids": [5, 6],
        }
        self.assertEqual(response.get_json()["profile"], expected)
        self.assertEqual(
            self.client.get("/api/student/profile").get_json()["profile"],
            expected,
        )

    def test_profile_null_contact_is_cleared(self):
        self.login_student("student01")
        populated = self.client.put(
            "/api/student/profile",
            json={
                "name": "陈晓",
                "contact": "13800000000",
                "learning_direction": "comprehensive",
                "tag_ids": [],
            },
        )
        self.assertEqual(populated.status_code, 200)

        response = self.client.put(
            "/api/student/profile",
            json={
                "name": "陈晓",
                "contact": None,
                "learning_direction": "comprehensive",
                "tag_ids": [],
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["profile"]["contact"], "")
        persisted = self.client.get("/api/student/profile").get_json()["profile"]
        self.assertEqual(persisted["contact"], "")

    def test_downstream_contract_reads_latest_preferences(self):
        self.login_student("student01")

        with self.app.app_context():
            update_student_profile(
                1,
                {
                    "name": "陈晓",
                    "contact": "",
                    "learning_direction": "handcraft",
                    "tag_ids": [8],
                },
            )
            preferences = get_profile_preferences(1)

        self.assertEqual(
            preferences,
            {
                "user_id": 1,
                "learning_direction": "handcraft",
                "interest_tag_ids": [8],
                "interest_tag_names": ["手工艺"],
            },
        )

    def test_profile_rejects_unknown_direction(self):
        self.login_student("student01")

        response = self.client.put(
            "/api/student/profile",
            json={
                "name": "陈晓",
                "contact": "",
                "learning_direction": "unknown",
                "tag_ids": [],
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("learning_direction", response.get_json()["errors"])


if __name__ == "__main__":
    unittest.main()
