import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from app import create_app
from app.agri_skills.ai_client import set_ai_client
from app.agri_skills.errors import AiUnavailableError
from app.db import get_db
from app.local_resources.dialect_assistant import (
    complete_dialect_turn,
    generate_dialect_answer,
)
from app.local_resources.errors import (
    LocalResourceAiUnavailableError,
    LocalResourceValidationError,
)
from app.local_resources.tts import TtsAudio, set_local_tts_client


class LocalResourceDialectTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(Path(self.temp_dir.name) / "test.db"),
                "AI_TTS_VOICE_YUE": "voice-yue",
                "AI_TTS_VOICE_HAKKA": "voice-hak",
                "AI_TTS_VOICE_TEOCHEW": "voice-nan",
            }
        )
        with self.app.app_context():
            cursor = get_db().execute(
                """
                INSERT INTO users (
                    username, password_hash, name, role, is_enabled,
                    created_at, updated_at
                ) VALUES (
                    'student01', 'hash', '学员甲', 'student', 1,
                    '2026-09-19T00:00:00+08:00',
                    '2026-09-19T00:00:00+08:00'
                )
                """
            )
            get_db().commit()
            self.user_id = int(cursor.lastrowid)
        self.ai = Mock()
        self.ai.complete_json.return_value = {
            "dialect_text": "呢个问题要睇种植时间。",
            "mandarin_text": "这个问题要看种植时间。",
        }
        set_ai_client(self.app, self.ai)

        class FakeTts:
            def synthesize(
                self,
                text,
                language_code,
                voice_code,
                *,
                call_point,
            ):
                self.kwargs = {
                    "text": text,
                    "language_code": language_code,
                    "voice_code": voice_code,
                    "call_point": call_point,
                }
                return TtsAudio(b"ID3audio", "audio/mpeg")

        self.tts = FakeTts()
        set_local_tts_client(self.app, self.tts)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_answer_uses_single_callpoint_and_exact_allowlist(self):
        with self.app.app_context():
            answer = generate_dialect_answer("yue", "几时种荔枝？")
        self.assertEqual(
            answer,
            {
                "dialect_text": "呢个问题要睇种植时间。",
                "mandarin_text": "这个问题要看种植时间。",
            },
        )
        self.assertEqual(self.ai.complete_json.call_count, 1)
        messages = self.ai.complete_json.call_args.args[0]
        rendered = repr(messages)
        self.assertIn("几时种荔枝？", rendered)
        self.assertIn("yue", rendered)
        self.assertNotIn("password", rendered)
        self.assertEqual(
            self.ai.complete_json.call_args.kwargs["call_point"],
            "local_resources_dialect_answer",
        )

    def test_complete_turn_persists_text_and_returns_audio_without_storing_it(
        self,
    ):
        with self.app.app_context():
            turn = complete_dialect_turn(
                self.user_id,
                "hak",
                "几时种水稻？",
            )
            row = get_db().execute(
                """
                SELECT *
                FROM local_resource_dialect_turns
                WHERE turn_id = ?
                """,
                (turn["id"],),
            ).fetchone()
        self.assertEqual(turn["audio_content"], b"ID3audio")
        self.assertEqual(turn["audio_content_type"], "audio/mpeg")
        self.assertEqual(row["dialect_code"], "hak")
        self.assertEqual(row["recognized_text"], "几时种水稻？")
        self.assertEqual(row["status"], "completed")
        self.assertNotIn("audio", row.keys())
        self.assertEqual(self.tts.kwargs["language_code"], "hak")
        self.assertEqual(self.tts.kwargs["voice_code"], "voice-hak")

    def test_ai_failure_has_no_fallback_and_no_turn(self):
        self.ai.complete_json.side_effect = AiUnavailableError("down")
        with self.app.app_context():
            with self.assertRaises(LocalResourceAiUnavailableError):
                complete_dialect_turn(
                    self.user_id,
                    "nan",
                    "问题",
                )
            count = get_db().execute(
                "SELECT COUNT(*) AS count FROM local_resource_dialect_turns"
            ).fetchone()["count"]
        self.assertEqual(count, 0)

    def test_tts_failure_has_no_turn(self):
        def fail_synthesis(**kwargs):
            del kwargs
            raise LocalResourceAiUnavailableError()

        self.tts.synthesize = fail_synthesis
        with self.app.app_context():
            with self.assertRaises(LocalResourceAiUnavailableError):
                complete_dialect_turn(
                    self.user_id,
                    "hak",
                    "问题",
                )
            count = get_db().execute(
                "SELECT COUNT(*) AS count FROM local_resource_dialect_turns"
            ).fetchone()["count"]
        self.assertEqual(count, 0)

    def test_invalid_answer_and_dialect_are_rejected(self):
        self.ai.complete_json.return_value = {
            "dialect_text": "",
            "mandarin_text": "对照",
        }
        with self.app.app_context():
            with self.assertRaises(LocalResourceAiUnavailableError):
                complete_dialect_turn(
                    self.user_id,
                    "yue",
                    "问题",
                )
            with self.assertRaises(LocalResourceValidationError):
                complete_dialect_turn(
                    self.user_id,
                    "mandarin",
                    "问题",
                )

    def test_non_dict_missing_and_blank_answers_are_unavailable(self):
        responses = [
            [],
            {"dialect_text": "方言回答"},
            {"dialect_text": "   ", "mandarin_text": "普通话回答"},
        ]
        with self.app.app_context():
            for payload in responses:
                with self.subTest(payload=payload):
                    self.ai.complete_json.return_value = payload
                    with self.assertRaises(LocalResourceAiUnavailableError):
                        generate_dialect_answer("yue", "问题")


if __name__ == "__main__":
    unittest.main()
