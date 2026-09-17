import sqlite3
import tempfile
import unittest
from pathlib import Path

from app import create_app
from app.agri_skills.ai_context import AI_FIELD_ALLOWLISTS
from app.agri_skills.course_learning import DatabaseAgriCourseProvider
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

    def test_legacy_course_duration_is_backfilled_during_migration(self):
        legacy_path = Path(self.temp_dir.name) / "legacy.db"
        connection = sqlite3.connect(legacy_path)
        connection.execute(
            """
            CREATE TABLE courses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                direction TEXT NOT NULL,
                status TEXT NOT NULL,
                published_at TEXT,
                summary TEXT NOT NULL DEFAULT '',
                teacher_name TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO courses (
                id, title, direction, status, published_at, summary,
                teacher_name, created_at, updated_at
            )
            VALUES (
                42, 'Legacy agriculture', 'agriculture', 'published',
                '2026-09-01T00:00:00+00:00', 'Legacy summary',
                'Legacy teacher', '2026-09-01T00:00:00+00:00',
                '2026-09-01T00:00:00+00:00'
            )
            """
        )
        connection.commit()
        connection.close()

        legacy_app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(legacy_path),
                "SECRET_KEY": "test-only-secret",
            }
        )

        with legacy_app.app_context():
            row = get_db().execute(
                "SELECT duration_seconds FROM courses WHERE id = 42"
            ).fetchone()

        self.assertEqual(row["duration_seconds"], 300)

    def test_fixed_ecommerce_course_fixture(self):
        with self.app.app_context():
            db = get_db()
            rows = db.execute(
                """
                SELECT id, direction, status, duration_seconds
                FROM courses
                WHERE id BETWEEN 1001 AND 1005
                ORDER BY id
                """
            ).fetchall()
            tag_rows = db.execute(
                """
                SELECT c.id, t.name, t.is_active
                FROM courses c
                JOIN course_interest_tags ct ON ct.course_id = c.id
                JOIN interest_tags t ON t.id = ct.tag_id
                WHERE c.id IN (1001, 1002)
                ORDER BY c.id
                """
            ).fetchall()
            provider = DatabaseAgriCourseProvider()
            quiz = provider.get_quiz(1001)
            no_quiz = provider.get_quiz(1002)

        self.assertEqual([row["id"] for row in rows], [1001, 1002, 1003, 1004, 1005])
        self.assertEqual(rows[0]["status"], "published")
        self.assertEqual(rows[1]["status"], "published")
        self.assertGreater(rows[0]["duration_seconds"], 0)
        self.assertGreater(rows[1]["duration_seconds"], 0)
        self.assertEqual(
            [
                (row["id"], row["name"], row["is_active"])
                for row in tag_rows
            ],
            [
                (1001, "电商直播", 1),
                (1002, "电商运营", 1),
            ],
        )
        self.assertEqual(
            quiz,
            {
                "enabled": True,
                "scoring_rule": "每题按 AI 判分，满分 100 分。",
                "questions": [
                    {
                        "id": "ecommerce-1001-q1",
                        "type": "single_choice",
                        "prompt": "完成课程学习至少需要达到多少进度？",
                        "options": ["60%", "80%", "100%"],
                        "answer": "80%",
                    }
                ],
            },
        )
        self.assertIsNone(no_quiz)
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
