import tempfile
import unittest
from pathlib import Path

from app import create_app
from app.agri_skills.ai_client import NullAiClient, get_ai_client, set_ai_client
from app.db import get_db


class TestAgriFoundation(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(Path(self.temp_dir.name) / "test.db"),
                "SECRET_KEY": "test-only-secret",
                "AI_API_URL": "",
                "AI_API_KEY": "",
                "AI_MODEL": "test-model",
            }
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_agri_tables_exist(self):
        expected = {
            "agri_product_selections",
            "agri_product_subscriptions",
            "agri_qa_conversations",
            "agri_qa_turns",
            "agri_diagnosis_sessions",
            "agri_diagnosis_answers",
            "agri_diagnosis_followups",
            "agri_self_tests",
            "agri_self_test_attempts",
            "agri_course_progress",
            "agri_course_quiz_attempts",
        }
        with self.app.app_context():
            names = {
                row["name"]
                for row in get_db().execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
        self.assertTrue(expected.issubset(names))

    def test_default_ai_client_is_replaceable(self):
        with self.app.app_context():
            self.assertIsInstance(get_ai_client(), NullAiClient)
        replacement = NullAiClient()
        set_ai_client(self.app, replacement)
        with self.app.app_context():
            self.assertIs(get_ai_client(), replacement)


if __name__ == "__main__":
    unittest.main()
