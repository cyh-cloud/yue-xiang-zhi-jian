import os
import unittest
from unittest.mock import patch

from app.config import build_config


class TestBuildConfig(unittest.TestCase):
    def test_production_requires_a_non_default_secret_key(self):
        for secret_key in (None, "", "dev-only-change-me"):
            environment = {
                "FLASK_ENV": "production",
                "SESSION_COOKIE_SECURE": "true",
            }
            if secret_key is not None:
                environment["SECRET_KEY"] = secret_key

            with self.subTest(secret_key=secret_key):
                with patch.dict(os.environ, environment, clear=True):
                    with self.assertRaisesRegex(
                        RuntimeError,
                        "Production SECRET_KEY must be set to a non-default value",
                    ):
                        build_config()

    def test_production_requires_secure_session_cookies(self):
        with patch.dict(
            os.environ,
            {
                "FLASK_ENV": "production",
                "SECRET_KEY": "production-secret",
                "SESSION_COOKIE_SECURE": "false",
            },
            clear=True,
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "Production SESSION_COOKIE_SECURE must be true",
            ):
                build_config()

    def test_production_accepts_non_default_secret_and_secure_cookies(self):
        with patch.dict(
            os.environ,
            {
                "FLASK_ENV": "production",
                "SECRET_KEY": "production-secret",
                "SESSION_COOKIE_SECURE": "true",
            },
            clear=True,
        ):
            config = build_config()

        self.assertEqual(config["SECRET_KEY"], "production-secret")
        self.assertIs(config["SESSION_COOKIE_SECURE"], True)

    def test_non_production_preserves_local_and_testing_defaults(self):
        with patch.dict(os.environ, {"FLASK_ENV": "development"}, clear=True):
            config = build_config()

        self.assertEqual(config["SECRET_KEY"], "dev-only-change-me")
        self.assertIs(config["SESSION_COOKIE_SECURE"], False)

    def test_tts_timeout_defaults_for_empty_and_invalid_values(self):
        cases = (
            (None, 30.0),
            ("", 30.0),
            ("not-a-number", 30.0),
            ("12.5", 12.5),
        )

        for value, expected in cases:
            environment = {}
            if value is not None:
                environment["AI_TTS_TIMEOUT_SECONDS"] = value
            with self.subTest(value=value):
                with patch.dict(os.environ, environment, clear=True):
                    config = build_config()
                self.assertEqual(
                    config["AI_TTS_TIMEOUT_SECONDS"],
                    expected,
                )


if __name__ == "__main__":
    unittest.main()
