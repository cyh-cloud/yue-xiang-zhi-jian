import tempfile
import unittest
from pathlib import Path

from app import create_app
from app.agri_skills.ai_context import AI_FIELD_ALLOWLISTS
from app.db import get_db
from app.seed import seed_courses


class TestEcommerceFoundation(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(Path(self.temp_dir.name) / "test.db"),
                "SECRET_KEY": "test-only-secret",
            }
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_tables_and_course_duration_column_exist(self):
        with self.app.app_context():
            db = get_db()
            names = {
                row["name"]
                for row in db.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
            self.assertTrue(
                {
                    "ecommerce_live_script_versions",
                    "ecommerce_simulation_trainings",
                    "ecommerce_copy_training_sessions",
                    "ecommerce_store_plans",
                    "ecommerce_customer_sessions",
                    "ecommerce_customer_turns",
                }.issubset(names)
            )
            columns = {
                row["name"]
                for row in db.execute("PRAGMA table_info(courses)")
            }
            self.assertIn("duration_seconds", columns)

    def test_fixed_ecommerce_course_fixture(self):
        with self.app.app_context():
            rows = get_db().execute(
                """
                SELECT id, direction, status, duration_seconds
                FROM courses
                WHERE id BETWEEN 1001 AND 1005
                ORDER BY id
                """
            ).fetchall()
        self.assertEqual([row["id"] for row in rows], [1001, 1002, 1003, 1004, 1005])
        self.assertEqual(rows[0]["direction"], "ecommerce")
        self.assertEqual(rows[2]["status"], "pending")
        self.assertEqual(rows[3]["direction"], "agriculture")
        self.assertIsNone(rows[4]["duration_seconds"])

    def test_ai_allowlists_are_registered(self):
        expected = {
            "live_script_generate",
            "simulation_score",
            "copy_case_generate",
            "copy_reference_critique",
            "copy_revised_generate",
            "copy_optimization_critique",
            "store_plan_generate",
            "customer_message_generate",
            "customer_reply_analyze",
            "customer_summary",
        }
        self.assertTrue(expected.issubset(AI_FIELD_ALLOWLISTS))

    def test_default_seed_courses_have_valid_duration(self):
        with self.app.app_context():
            seed_courses(get_db())
            rows = get_db().execute(
                """
                SELECT duration_seconds
                FROM courses
                WHERE title IN (
                    '荔枝保果与采收管理',
                    '水稻绿色种植基础',
                    '农产品直播运营入门',
                    '竹编基础与产品设计'
                )
                """
            ).fetchall()

        self.assertEqual(len(rows), 4)
        self.assertTrue(
            all(row["duration_seconds"] == 300 for row in rows)
        )


if __name__ == "__main__":
    unittest.main()
