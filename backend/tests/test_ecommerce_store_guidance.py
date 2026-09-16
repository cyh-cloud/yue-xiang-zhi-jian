import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from app import create_app
from app.agri_skills.ai_client import set_ai_client
from app.agri_skills.errors import (
    AgriNotFoundError,
    AgriValidationError,
    AiUnavailableError,
)
from app.db import get_db
from app.ecommerce_training.store_guidance import (
    generate_store_plan,
    get_store_plan,
    list_store_plans,
)


class TestEcommerceStoreGuidance(unittest.TestCase):
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
            self.student_id = self._insert_student(db, "student01")
            self.other_student_id = self._insert_student(db, "student02")
            db.commit()

        self.ai = Mock()
        set_ai_client(self.app, self.ai)

    def tearDown(self):
        self.temp_dir.cleanup()

    @staticmethod
    def _insert_student(db, username: str) -> int:
        cursor = db.execute(
            """
            INSERT INTO users (
                username, password_hash, name, role, is_enabled,
                created_at, updated_at
            )
            VALUES (?, ?, ?, 'student', 1, ?, ?)
            """,
            (
                username,
                "test-password-hash",
                username,
                "2026-09-16T00:00:00+00:00",
                "2026-09-16T00:00:00+00:00",
            ),
        )
        return int(cursor.lastrowid)

    @staticmethod
    def _payload() -> dict:
        return {
            "store_type": "农产品旗舰店",
            "platform": "taobao",
            "style_preference": "温暖、可靠",
        }

    @staticmethod
    def _plan_fixture() -> dict:
        return {
            "home_layout": ["顶部活动区", "商品分组"],
            "color_scheme": {
                "primary": "#E43D30",
                "accent": "#F7C948",
            },
            "detail_structure": ["卖点", "参数", "售后"],
            "navigation": ["首页", "新品", "优惠", "客服"],
        }

    def test_generate_persists_plan_inputs_and_history(self):
        payload = self._payload()
        self.ai.complete_json.return_value = self._plan_fixture()

        with self.app.app_context():
            plan = generate_store_plan(self.student_id, payload)
            loaded = get_store_plan(self.student_id, plan["id"])
            history = list_store_plans(self.student_id)

        self.assertEqual(
            set(plan["plan"]),
            {
                "home_layout",
                "color_scheme",
                "detail_structure",
                "navigation",
            },
        )
        self.assertEqual(plan["store_type"], payload["store_type"])
        self.assertEqual(plan["platform"], payload["platform"])
        self.assertEqual(
            plan["style_preference"],
            payload["style_preference"],
        )
        self.assertEqual(plan["plan"], self._plan_fixture())
        self.assertEqual(loaded, plan)
        self.assertEqual(history, [plan])

    def test_invalid_input_is_rejected_before_ai_and_creates_no_plan(self):
        cases = (
            {**self._payload(), "store_type": None},
            {**self._payload(), "store_type": " "},
            {**self._payload(), "style_preference": None},
            {**self._payload(), "style_preference": " "},
            {**self._payload(), "platform": "unknown"},
        )

        with self.app.app_context():
            for payload in cases:
                with self.subTest(payload=payload):
                    with self.assertRaises(AgriValidationError):
                        generate_store_plan(self.student_id, payload)

            self.assertEqual(list_store_plans(self.student_id), [])

        self.ai.complete_json.assert_not_called()

    def test_ai_failure_is_exact_and_creates_no_plan(self):
        payload = self._payload()
        original_payload = payload.copy()
        self.ai.complete_json.side_effect = AiUnavailableError(
            "raw provider error"
        )

        with self.app.app_context():
            with self.assertRaisesRegex(
                AiUnavailableError,
                "^AI 服务暂时不可用$",
            ):
                generate_store_plan(self.student_id, payload)

            self.assertEqual(list_store_plans(self.student_id), [])

        self.assertEqual(payload, original_payload)

    def test_malformed_plan_is_exact_failure_and_creates_no_plan(self):
        valid_plan = self._plan_fixture()
        cases = (
            None,
            {key: valid_plan[key] for key in valid_plan if key != "navigation"},
            {**valid_plan, "home_layout": None},
            {**valid_plan, "home_layout": " "},
            {**valid_plan, "home_layout": []},
            {**valid_plan, "color_scheme": {}},
            {**valid_plan, "extra_section": ["not allowed"]},
        )

        with self.app.app_context():
            for response in cases:
                with self.subTest(response=response):
                    self.ai.complete_json.return_value = response
                    with self.assertRaisesRegex(
                        AiUnavailableError,
                        "^AI 服务暂时不可用$",
                    ):
                        generate_store_plan(self.student_id, self._payload())

            self.assertEqual(list_store_plans(self.student_id), [])

    def test_history_preserves_each_success_and_enforces_ownership(self):
        self.ai.complete_json.return_value = self._plan_fixture()

        with self.app.app_context():
            first = generate_store_plan(
                self.student_id,
                {**self._payload(), "platform": "pinduoduo"},
            )
            second = generate_store_plan(
                self.student_id,
                {**self._payload(), "platform": "douyin_shop"},
            )
            history = list_store_plans(self.student_id)

            with self.assertRaises(AgriNotFoundError):
                get_store_plan(self.other_student_id, first["id"])

            self.assertEqual(
                list_store_plans(self.other_student_id),
                [],
            )

        self.assertEqual(
            [item["id"] for item in history],
            [second["id"], first["id"]],
        )
        self.assertEqual(
            [item["platform"] for item in history],
            ["douyin_shop", "pinduoduo"],
        )
        self.assertEqual(history[0], second)
        self.assertEqual(history[1], first)


if __name__ == "__main__":
    unittest.main()
