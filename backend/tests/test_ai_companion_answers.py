import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from app import create_app
from app.agri_skills.ai_client import set_ai_client
from app.ai_companion.answers import (
    build_refusal_answer,
    generate_learning_guidance,
)
from app.ai_companion.errors import AiCompanionAiUnavailableError


class AiCompanionAnswersTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(Path(self.temp_dir.name) / "test.db"),
                "SECRET_KEY": "test-only-secret",
            }
        )
        self.ai = Mock()
        set_ai_client(self.app, self.ai)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_learning_guidance_is_bounded_and_role_aware(self):
        self.ai.complete_json.return_value = {
            "bullets": ["先确认品种和树龄", "进入农业技能查看当地农时", "在 AI 问答补充地区和天气"],
            "module_key": "agriculture",
        }
        with self.app.app_context():
            student = generate_learning_guidance("荔枝什么时候套袋", "student")
            teacher = generate_learning_guidance("荔枝什么时候套袋", "teacher")
        self.assertEqual(len(student["bullets"]), 3)
        self.assertEqual(student["jump_target"], "/student/agri-skills/qa")
        self.assertIsNone(teacher["jump_target"])

    def test_learning_guidance_rejects_unknown_module_or_long_answer(self):
        self.ai.complete_json.return_value = {
            "bullets": ["一", "二", "三", "四", "五", "六"],
            "module_key": "unknown",
        }
        with self.app.app_context():
            with self.assertRaises(AiCompanionAiUnavailableError):
                generate_learning_guidance("学习问题", "student")

    def test_refusal_never_uses_completion_language(self):
        result = build_refusal_answer("帮我投简历", True)
        self.assertIn("不代办", result["answer"])
        self.assertIn("就业对接", result["answer"])
        self.assertNotIn("已完成", result["answer"])
        self.assertNotIn("已提交", result["answer"])
        self.assertNotIn("已处理", result["answer"])
        self.assertIsNone(result["jump_target"])

    def test_refusal_uses_action_specific_text_guidance(self):
        self.assertIn(
            "积分商城",
            build_refusal_answer("帮我兑换奖品", True)["answer"],
        )
        self.assertIn(
            "消息中心",
            build_refusal_answer("帮我发消息", True)["answer"],
        )


if __name__ == "__main__":
    unittest.main()
