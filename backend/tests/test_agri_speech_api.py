import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

import httpx
from werkzeug.security import generate_password_hash

from app import create_app
from app.agri_skills.ai_client import (
    OpenAiCompatibleAiClient,
    set_ai_client,
)
from app.agri_skills.errors import AgriValidationError, AiUnavailableError
from app.db import get_db


EMPTY_RECOGNITION_MESSAGE = "未能识别，请重试或改用文字输入"
AI_UNAVAILABLE_MESSAGE = "AI 服务暂时不可用"


class TestAgriSpeechApi(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(Path(self.temp_dir.name) / "test.db"),
                "SECRET_KEY": "test-only-secret",
                "SESSION_HOURS": 24,
                "SESSION_COOKIE_SECURE": False,
                "AI_API_URL": "",
                "AI_API_KEY": "",
                "AI_MODEL": "test-model",
                "AI_ASR_URL": "",
                "AI_ASR_MODEL": "test-asr-model",
            }
        )
        self._create_user("student01", "student")
        self._create_user("teacher01", "teacher")
        self.student_client = self._login("student01")
        self.teacher_client = self._login("teacher01")

        self.fake_ai = Mock()
        self.fake_ai.transcribe.return_value = "荔枝蒂蛀虫怎么防"
        set_ai_client(self.app, self.fake_ai)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _create_user(self, username: str, role: str) -> int:
        with self.app.app_context():
            cursor = get_db().execute(
                """
                INSERT INTO users (
                    username, password_hash, name, role, is_enabled,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, 1, ?, ?)
                """,
                (
                    username,
                    generate_password_hash("password8"),
                    username,
                    role,
                    "2026-09-15T00:00:00+00:00",
                    "2026-09-15T00:00:00+00:00",
                ),
            )
            get_db().commit()
            return int(cursor.lastrowid)

    def _login(self, username: str):
        client = self.app.test_client()
        response = client.post(
            "/api/auth/login",
            json={"username": username, "password": "password8"},
        )
        self.assertEqual(response.status_code, 200)
        return client

    def _post_audio(self, client=None, *, audio: bytes = b"fake", name="question.webm"):
        client = client or self.student_client
        return client.post(
            "/api/agri-skills/speech/transcriptions",
            data={"audio": (io.BytesIO(audio), name)},
            content_type="multipart/form-data",
        )

    def test_speech_returns_recognized_text(self):
        response = self._post_audio()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json(),
            {"success": True, "text": "荔枝蒂蛀虫怎么防"},
        )
        self.fake_ai.transcribe.assert_called_once_with(
            b"fake",
            "question.webm",
            call_point="speech_to_text",
        )

    def test_missing_audio_returns_exact_failure(self):
        response = self.student_client.post(
            "/api/agri-skills/speech/transcriptions",
            data={},
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.get_json(),
            {
                "success": False,
                "message": EMPTY_RECOGNITION_MESSAGE,
            },
        )
        self.fake_ai.transcribe.assert_not_called()

    def test_empty_audio_returns_exact_failure(self):
        response = self._post_audio(audio=b"")

        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.get_json(),
            {
                "success": False,
                "message": EMPTY_RECOGNITION_MESSAGE,
            },
        )
        self.fake_ai.transcribe.assert_not_called()

    def test_empty_recognition_returns_exact_failure(self):
        self.fake_ai.transcribe.side_effect = AgriValidationError(
            EMPTY_RECOGNITION_MESSAGE
        )

        response = self._post_audio(audio=b"empty")

        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.get_json(),
            {
                "success": False,
                "message": EMPTY_RECOGNITION_MESSAGE,
            },
        )

    def test_ai_unavailable_returns_fixed_message(self):
        self.fake_ai.transcribe.side_effect = AiUnavailableError(
            "AI service request failed"
        )

        response = self._post_audio(audio=b"upstream")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.get_json(),
            {
                "success": False,
                "message": AI_UNAVAILABLE_MESSAGE,
            },
        )

    def test_anonymous_and_teacher_cannot_transcribe(self):
        anonymous = self._post_audio(client=self.app.test_client())
        teacher = self._post_audio(client=self.teacher_client)

        self.assertEqual(anonymous.status_code, 401)
        self.assertEqual(teacher.status_code, 401)
        self.fake_ai.transcribe.assert_not_called()


class TestOpenAiCompatibleTranscription(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(Path(self.temp_dir.name) / "test.db"),
                "SECRET_KEY": "test-only-secret",
                "AI_API_URL": "",
                "AI_API_KEY": "",
                "AI_MODEL": "chat-model",
                "AI_ASR_URL": "https://example.test/audio/transcriptions",
                "AI_ASR_MODEL": "FunAudioLLM/SenseVoiceSmall",
            }
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_transcribe_uses_multipart_model_and_auth(self):
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["request"] = request
            return httpx.Response(
                200,
                json={"text": "  荔枝蒂蛀虫怎么防  "},
                request=request,
            )

        client = OpenAiCompatibleAiClient(
            api_url="https://example.test/chat/completions",
            api_key="asr-key",
            model="chat-model",
            timeout=5,
            transport=httpx.MockTransport(handler),
        )

        with self.app.app_context():
            text = client.transcribe(
                b"fake-audio",
                "question.webm",
                call_point="speech_to_text",
            )

        request = captured["request"]
        self.assertEqual(text, "荔枝蒂蛀虫怎么防")
        self.assertEqual(
            request.url,
            "https://example.test/audio/transcriptions",
        )
        self.assertEqual(request.headers["Authorization"], "Bearer asr-key")
        self.assertTrue(
            request.headers["Content-Type"].startswith(
                "multipart/form-data; boundary="
            )
        )
        self.assertIn(b'name="model"', request.content)
        self.assertIn(b"FunAudioLLM/SenseVoiceSmall", request.content)
        self.assertIn(b'name="file"', request.content)
        self.assertIn(b'filename="question.webm"', request.content)
        self.assertIn(b"fake-audio", request.content)

    def test_transcribe_wraps_upstream_failure(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(503, request=request)

        client = OpenAiCompatibleAiClient(
            api_url="https://example.test/chat/completions",
            api_key="asr-key",
            model="chat-model",
            timeout=5,
            transport=httpx.MockTransport(handler),
        )

        with self.app.app_context():
            with self.assertRaises(AiUnavailableError):
                client.transcribe(
                    b"fake-audio",
                    "question.webm",
                    call_point="speech_to_text",
                )

    def test_transcribe_rejects_empty_text(self):
        transport = httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={"text": "   "},
                request=request,
            )
        )
        client = OpenAiCompatibleAiClient(
            api_url="https://example.test/chat/completions",
            api_key="asr-key",
            model="chat-model",
            timeout=5,
            transport=transport,
        )

        with self.app.app_context():
            with self.assertRaisesRegex(
                AgriValidationError,
                EMPTY_RECOGNITION_MESSAGE,
            ):
                client.transcribe(
                    b"fake-audio",
                    "question.webm",
                    call_point="speech_to_text",
                )


if __name__ == "__main__":
    unittest.main()
