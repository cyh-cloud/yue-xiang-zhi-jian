import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from werkzeug.security import generate_password_hash

from app import create_app
from app.agri_skills.ai_client import set_ai_client
from app.agri_skills.errors import AgriValidationError, AiUnavailableError
from app.db import get_db


PASSWORD = "password8"
TIMESTAMP = "2026-09-21T10:00:00+08:00"


class AiCompanionApiTests(unittest.TestCase):
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
        self.ai = Mock()
        self.ai.transcribe.return_value = "识别文字"
        self.ai.complete_json.return_value = {"intent": "out_of_scope"}
        set_ai_client(self.app, self.ai)

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
                    generate_password_hash(PASSWORD),
                    username,
                    role,
                    TIMESTAMP,
                    TIMESTAMP,
                ),
            )
            get_db().commit()
            return int(cursor.lastrowid)

    def _login(self, role: str):
        self._create_user(f"{role}-user", role)
        client = self.app.test_client()
        response = client.post(
            "/api/auth/login",
            json={"username": f"{role}-user", "password": PASSWORD},
        )
        self.assertEqual(response.status_code, 200)
        return client

    def test_four_portal_roles_can_ask_questions(self):
        for role in ("student", "teacher", "enterprise", "government"):
            client = self._login(role)
            response = client.post(
                "/api/ai-companion/messages",
                json={
                    "question": "怎么投简历",
                    "client_request_id": f"{role}-request",
                },
            )
            self.assertEqual(response.status_code, 200)

    def test_anonymous_and_admin_roles_are_rejected(self):
        self.assertEqual(
            self.app.test_client().post(
                "/api/ai-companion/messages",
                json={"question": "怎么投简历", "client_request_id": "anon"},
            ).status_code,
            401,
        )
        for role in ("super_admin", "admin"):
            response = self._login(role).post(
                "/api/ai-companion/messages",
                json={"question": "怎么投简历", "client_request_id": role},
            )
            self.assertEqual(response.status_code, 403)

    def test_history_routes_are_owner_scoped(self):
        first = self._login("student")
        second = self._login("teacher")
        created = first.post(
            "/api/ai-companion/messages",
            json={"question": "怎么投简历", "client_request_id": "history-1"},
        ).get_json()
        conversation_id = created["conversation_id"]
        self.assertEqual(
            second.get(
                f"/api/ai-companion/conversations/{conversation_id}"
            ).status_code,
            404,
        )

    def test_speech_route_uses_shared_transcribe_contract(self):
        response = self._login("teacher").post(
            "/api/ai-companion/speech/transcriptions",
            data={"audio": (io.BytesIO(b"fake"), "question.webm")},
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"success": True, "text": "识别文字"})
        self.ai.transcribe.assert_called_once_with(
            b"fake",
            "question.webm",
            call_point="speech_to_text",
        )

    def test_speech_route_failure_matrix(self):
        teacher = self._login("teacher")
        missing = teacher.post(
            "/api/ai-companion/speech/transcriptions",
            data={},
            content_type="multipart/form-data",
        )
        empty = teacher.post(
            "/api/ai-companion/speech/transcriptions",
            data={"audio": (io.BytesIO(b""), "empty.webm")},
            content_type="multipart/form-data",
        )
        for response in (missing, empty):
            self.assertEqual(response.status_code, 422)
            self.assertEqual(
                response.get_json()["message"],
                "未能识别，请重说或改用文字",
            )

        self.ai.transcribe.side_effect = AgriValidationError("noise")
        noise = teacher.post(
            "/api/ai-companion/speech/transcriptions",
            data={"audio": (io.BytesIO(b"noise"), "noise.webm")},
            content_type="multipart/form-data",
        )
        self.assertEqual(noise.status_code, 422)
        self.assertEqual(
            noise.get_json()["message"],
            "未能识别，请重说或改用文字",
        )

        self.ai.transcribe.side_effect = AiUnavailableError("down")
        unavailable = teacher.post(
            "/api/ai-companion/speech/transcriptions",
            data={"audio": (io.BytesIO(b"audio"), "question.webm")},
            content_type="multipart/form-data",
        )
        self.assertEqual(unavailable.status_code, 503)
        self.assertEqual(
            unavailable.get_json()["message"],
            "AI 服务暂时不可用",
        )


if __name__ == "__main__":
    unittest.main()
