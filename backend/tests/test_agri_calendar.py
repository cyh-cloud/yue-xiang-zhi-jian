import tempfile
import unittest
from pathlib import Path

from app import create_app
from app.agri_skills.calendar import (
    get_calendar,
    get_selected_product,
    list_products,
    set_selected_product,
)
from app.agri_skills.errors import PresetContentUnavailableError
from app.db import get_db


class TestAgriCalendar(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(Path(self.temp_dir.name) / "test.db"),
                "SECRET_KEY": "test-only-secret",
            }
        )
        with self.app.app_context():
            db = get_db()
            cursor = db.execute(
                """
                INSERT INTO users (
                    username, password_hash, name, role, is_enabled,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, 'student', 1, ?, ?)
                """,
                (
                    "student01",
                    "test-password-hash",
                    "林晓",
                    "2026-09-15T00:00:00+00:00",
                    "2026-09-15T00:00:00+00:00",
                ),
            )
            self.student_id = int(cursor.lastrowid)
            db.commit()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_default_product_uses_last_selection_then_first_catalog_item(self):
        expected_products = [
            {"key": "litchi", "name": "荔枝", "sort_order": 1},
            {"key": "longan", "name": "龙眼", "sort_order": 2},
            {"key": "aquaculture", "name": "水产", "sort_order": 3},
        ]
        with self.app.app_context():
            self.assertEqual(list_products(), expected_products)
            self.assertEqual(get_selected_product(self.student_id), "litchi")

            set_selected_product(self.student_id, "longan")

            self.assertEqual(get_selected_product(self.student_id), "longan")

    def test_product_and_month_empty_states_are_distinct(self):
        with self.app.app_context():
            with self.assertRaisesRegex(
                PresetContentUnavailableError, "暂无该产品农时数据"
            ):
                get_calendar("missing-product", 4)

            result = get_calendar("litchi", 2)

            self.assertEqual(result["month"], 2)
            self.assertEqual(result["empty_state"], "当月无该产品农时")
            self.assertEqual(result["tasks"], [])
            self.assertEqual(result["management"], [])
            self.assertEqual(result["solar_terms"], [])
            self.assertEqual(result["reminder"], "")

    def test_calendar_returns_exact_content_for_existing_month(self):
        cases = [
            (
                4,
                {
                    "tasks": ["保果施肥", "检查蒂蛀虫"],
                    "management": ["保持果园通风", "雨后及时排水"],
                    "solar_terms": ["清明", "谷雨"],
                    "reminder": "荔枝正值保果关键期",
                },
            ),
            (
                5,
                {
                    "tasks": ["疏果", "病虫害巡查"],
                    "management": ["控制夏梢", "关注强降雨"],
                    "solar_terms": ["立夏", "小满"],
                    "reminder": "注意果实膨大期水分管理",
                },
            ),
        ]

        with self.app.app_context():
            for month, expected in cases:
                with self.subTest(month=month):
                    result = get_calendar("litchi", month)

                    self.assertEqual(result["product"]["key"], "litchi")
                    self.assertEqual(result["month"], month)
                    self.assertEqual(result["empty_state"], None)
                    for key, value in expected.items():
                        self.assertEqual(result[key], value)


if __name__ == "__main__":
    unittest.main()
