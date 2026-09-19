import tempfile
import unittest
from pathlib import Path

from app import create_app
from app.db import get_db
from app.local_resources.constants import (
    DIALECTS,
    NEWS_LABELS,
    POLICY_LABELS,
)
from app.local_resources.errors import LocalResourceValidationError


class LocalResourceFoundationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(Path(self.temp_dir.name) / "test.db"),
                "AI_TTS_URL": "https://tts.example.test/speech",
                "AI_TTS_MODEL": "dialect-tts",
                "AI_TTS_VOICE_YUE": "voice-yue",
                "AI_TTS_VOICE_HAKKA": "voice-hak",
                "AI_TTS_VOICE_TEOCHEW": "voice-nan",
            }
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_exact_constant_maps(self):
        self.assertEqual(
            DIALECTS,
            {"yue": "粤语", "hak": "客家话", "nan": "潮汕话"},
        )
        self.assertEqual(
            list(POLICY_LABELS),
            [
                "subsidy",
                "ecommerce",
                "heritage",
                "training",
                "certification",
                "general",
                "entrepreneurship",
            ],
        )
        self.assertEqual(
            list(NEWS_LABELS),
            ["news", "disaster_warning", "policy_update"],
        )

    def test_config_values_are_loaded(self):
        self.assertEqual(
            self.app.config["AI_TTS_VOICE_HAKKA"],
            "voice-hak",
        )
        self.assertEqual(
            self.app.config["AI_TTS_TIMEOUT_SECONDS"],
            30.0,
        )

    def test_local_resource_tables_exist(self):
        with self.app.app_context():
            names = {
                row["name"]
                for row in get_db().execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
        self.assertIn("local_resource_dialect_turns", names)
        self.assertIn("local_resource_policy_subscriptions", names)
        self.assertIn("local_resource_success_cases", names)

    def test_error_details_are_stable(self):
        error = LocalResourceValidationError(
            "参数不正确",
            details={"dialect_code": "不支持"},
        )
        self.assertEqual(error.code, "validation_error")
        self.assertEqual(error.details, {"dialect_code": "不支持"})


if __name__ == "__main__":
    unittest.main()
