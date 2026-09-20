import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from app import create_app
from app.agri_skills.ai_client import set_ai_client
from app.agri_skills.errors import AiUnavailableError
from app.ai_companion.errors import AiCompanionAiUnavailableError
from app.ai_companion.intent import (
    classify_intent,
    detect_business_proxy,
    resolve_intent,
)


class AiCompanionIntentTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(Path(self.temp_dir.name) / "test.db"),
            }
        )
        self.ai = Mock()
        set_ai_client(self.app, self.ai)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_business_proxy_prefilter_matrix(self):
        examples = (
            "帮我投简历",
            "替我兑换奖品",
            "代我审核这个职位",
            "帮我发消息给老师",
            "替我修改个人资料",
            "帮我删除这条内容",
        )
        for question in examples:
            with self.subTest(question=question):
                self.assertTrue(detect_business_proxy(question))

    def test_rule_prefilter_does_not_call_ai(self):
        with self.app.app_context():
            intent, prefiltered = resolve_intent("帮我兑换这个奖品")
        self.assertEqual(intent, "out_of_scope")
        self.assertTrue(prefiltered)
        self.ai.complete_json.assert_not_called()

    def test_ai_classifies_remaining_three_intents(self):
        for expected in (
            "platform_usage",
            "learning_question",
            "out_of_scope",
        ):
            self.ai.complete_json.return_value = {"intent": expected}
            with self.subTest(expected=expected):
                with self.app.app_context():
                    self.assertEqual(classify_intent("测试问题"), expected)

    def test_unknown_intent_and_ai_failure_are_unavailable(self):
        self.ai.complete_json.return_value = {"intent": "unknown"}
        with self.app.app_context():
            with self.assertRaises(AiCompanionAiUnavailableError):
                classify_intent("测试问题")

        self.ai.complete_json.side_effect = AiUnavailableError("down")
        with self.app.app_context():
            with self.assertRaises(AiCompanionAiUnavailableError):
                classify_intent("测试问题")


if __name__ == "__main__":
    unittest.main()
