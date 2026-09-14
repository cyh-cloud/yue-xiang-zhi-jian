import tempfile
import unittest
from pathlib import Path

from app import create_app
from app.db import get_db


class TestFoundation(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(Path(self.temp_dir.name) / "test.db"),
                "SECRET_KEY": "test-only-secret",
            }
        )
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_health_endpoint_returns_success(self):
        response = self.client.get("/api/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"success": True, "status": "ok"})

    def test_schema_contains_core_tables(self):
        with self.app.app_context():
            names = {
                row["name"]
                for row in get_db().execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }

        expected = {
            "users",
            "sessions",
            "student_profiles",
            "interest_tags",
            "student_interest_tags",
            "onboarding_states",
            "resumes",
            "courses",
            "course_interest_tags",
        }
        self.assertTrue(expected.issubset(names))
