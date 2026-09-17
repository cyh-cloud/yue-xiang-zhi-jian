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
from app.ecommerce_training.live_script import (
    generate_live_script,
    get_live_script,
    list_live_scripts,
)


class TestEcommerceLiveScript(unittest.TestCase):
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
            "product_name": "荔枝干",
            "selling_points": "香甜、耐储存",
            "price_text": "39.9 元",
            "style": "enthusiastic",
        }

    def _script_fixture(self) -> dict:
        return {
            "opening": "欢迎来到直播间",
            "product_intro": "这款荔枝干香甜耐储存",
            "interaction": "扣一告诉我你的口味偏好",
            "closing": "现在下单享优惠",
        }

    def test_generate_persists_exact_script_and_original_input(self):
        payload = self._payload()
        self.ai.complete_json.return_value = self._script_fixture()

        with self.app.app_context():
            result = generate_live_script(self.student_id, payload)
            loaded = get_live_script(self.student_id, result["id"])

        self.assertEqual(result["product_name"], payload["product_name"])
        self.assertEqual(result["selling_points"], ["香甜、耐储存"])
        self.assertEqual(result["price_text"], payload["price_text"])
        self.assertEqual(result["style"], "enthusiastic")
        self.assertEqual(result["script"], self._script_fixture())
        self.assertTrue(result["is_current"])
        self.assertTrue(result["created_at"])
        self.assertEqual(loaded, result)

    def test_regeneration_retains_versions_and_only_latest_is_current(self):
        payload = self._payload()
        self.ai.complete_json.return_value = self._script_fixture()

        with self.app.app_context():
            first = generate_live_script(self.student_id, payload)
            second = generate_live_script(
                self.student_id,
                {**payload, "style": "professional"},
            )
            first_after_regeneration = get_live_script(
                self.student_id,
                first["id"],
            )
            history = list_live_scripts(self.student_id)

        self.assertNotEqual(second["id"], first["id"])
        self.assertFalse(first_after_regeneration["is_current"])
        self.assertTrue(second["is_current"])
        self.assertEqual([item["id"] for item in history], [second["id"], first["id"]])
        self.assertEqual(
            [item["is_current"] for item in history],
            [True, False],
        )
        self.assertEqual(history[1]["style"], "enthusiastic")
        self.assertEqual(history[0]["style"], "professional")

    def test_ai_failure_is_exact_and_does_not_create_a_version(self):
        payload = self._payload()
        original_payload = payload.copy()
        self.ai.complete_json.side_effect = AiUnavailableError("raw provider error")

        with self.app.app_context():
            with self.assertRaisesRegex(
                AiUnavailableError,
                "^AI 服务暂时不可用$",
            ):
                generate_live_script(self.student_id, payload)
            history = list_live_scripts(self.student_id)

        self.assertEqual(payload, original_payload)
        self.assertEqual(history, [])

    def test_malformed_ai_result_is_exact_failure_and_creates_no_version(self):
        self.ai.complete_json.return_value = {
            "opening": "欢迎来到直播间",
            "product_intro": " ",
            "interaction": "扣一告诉我你的口味偏好",
        }

        with self.app.app_context():
            with self.assertRaisesRegex(
                AiUnavailableError,
                "^AI 服务暂时不可用$",
            ):
                generate_live_script(self.student_id, self._payload())
            history = list_live_scripts(self.student_id)

        self.assertEqual(history, [])

    def test_other_student_cannot_read_a_version(self):
        self.ai.complete_json.return_value = self._script_fixture()

        with self.app.app_context():
            version = generate_live_script(self.other_student_id, self._payload())

            with self.assertRaises(AgriNotFoundError):
                get_live_script(self.student_id, version["id"])

            self.assertEqual(list_live_scripts(self.student_id), [])

    def test_validation_happens_before_ai_call(self):
        cases = (
            (
                {**self._payload(), "product_name": " "},
                "商品名称不能为空",
            ),
            (
                {**self._payload(), "selling_points": [" ", ""]},
                "至少填写一个卖点",
            ),
            (
                {**self._payload(), "style": "unknown"},
                "直播风格不正确",
            ),
        )

        with self.app.app_context():
            for payload, message in cases:
                with self.subTest(message=message):
                    with self.assertRaisesRegex(AgriValidationError, message):
                        generate_live_script(self.student_id, payload)

        self.ai.complete_json.assert_not_called()


if __name__ == "__main__":
    unittest.main()
