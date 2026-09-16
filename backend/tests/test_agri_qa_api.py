import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from werkzeug.security import generate_password_hash

from app import create_app
from app.agri_skills.ai_client import set_ai_client
from app.agri_skills.errors import AiUnavailableError
from app.agri_skills.qa import create_qa_conversation
from app.db import get_db


class TestAgriQaApi(unittest.TestCase):
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
            }
        )

        self.student_id = self._create_user("student01", "student")
        self.other_student_id = self._create_user("student02", "student")
        self.student_client = self._login("student01")
        self.other_client = self._login("student02")

        with self.app.app_context():
            conversation = create_qa_conversation(
                self.student_id,
                "荔枝如何保果",
                "text",
            )
            self.conversation_id = conversation["id"]

        self.fake_ai = Mock()
        self.fake_ai.stream_chat.return_value = iter(["春季", "保果"])
        self.fake_ai.complete_json.return_value = {
            "suggestions": ["如何施肥", "如何排水", "如何防虫"],
        }
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

    @staticmethod
    def _sse_events(body: str) -> list[tuple[str, dict]]:
        events = []
        for block in body.strip().split("\n\n"):
            lines = block.splitlines()
            event = next(
                line.removeprefix("event: ")
                for line in lines
                if line.startswith("event: ")
            )
            data = next(
                line.removeprefix("data: ")
                for line in lines
                if line.startswith("data: ")
            )
            events.append((event, json.loads(data)))
        return events

    def test_student_can_create_and_list_qa_conversation(self):
        created = self.student_client.post(
            "/api/agri-skills/qa/conversations",
            json={"question": "荔枝蒂蛀虫怎么防", "input_mode": "text"},
        )
        self.assertEqual(created.status_code, 201)
        conversation_id = created.get_json()["conversation"]["id"]

        listed = self.student_client.get(
            "/api/agri-skills/qa/conversations"
        )

        self.assertEqual(listed.status_code, 200)
        self.assertEqual(
            [item["id"] for item in listed.get_json()["conversations"]],
            [conversation_id, self.conversation_id],
        )

    def test_stream_emits_exact_chunk_and_complete_events(self):
        response = self.student_client.post(
            (
                "/api/agri-skills/qa/conversations/"
                f"{self.conversation_id}/messages/stream"
            ),
            json={"question": "荔枝如何保果"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.mimetype.startswith("text/event-stream"))
        events = self._sse_events(response.get_data(as_text=True))
        self.assertEqual(
            [event for event, _ in events],
            ["chunk", "chunk", "complete"],
        )
        self.assertEqual(
            [payload["content"] for _, payload in events[:-1]],
            ["春季", "保果"],
        )
        turn = events[-1][1]["turn"]
        self.assertEqual(turn["question"], "荔枝如何保果")
        self.assertEqual(turn["answer"], "春季保果")
        self.assertEqual(turn["answer_mode"], "ai")
        self.assertEqual(
            turn["suggestions"],
            ["如何施肥", "如何排水", "如何防虫"],
        )

    def test_stream_complete_event_preserves_followup_failure(self):
        self.fake_ai.complete_json.side_effect = AiUnavailableError(
            "AI 服务暂时不可用"
        )

        response = self.student_client.post(
            (
                "/api/agri-skills/qa/conversations/"
                f"{self.conversation_id}/messages/stream"
            ),
            json={"question": "荔枝如何保果"},
        )

        self.assertEqual(response.status_code, 200)
        events = self._sse_events(response.get_data(as_text=True))
        self.assertEqual(
            [event for event, _ in events],
            ["chunk", "chunk", "complete"],
        )
        payload = events[-1][1]
        self.assertEqual(
            payload["suggestion_error"],
            "AI 服务暂时不可用",
        )
        self.assertEqual(payload["turn"]["suggestions"], [])

    def test_stream_replaces_partial_ai_output_with_local_answer(self):
        def failed_stream(messages, *, call_point):
            yield "不完整"
            raise AiUnavailableError("AI service request failed")

        self.fake_ai.stream_chat.side_effect = failed_stream
        response = self.student_client.post(
            (
                "/api/agri-skills/qa/conversations/"
                f"{self.conversation_id}/messages/stream"
            ),
            json={"question": "荔枝蒂蛀虫导致落果"},
        )

        self.assertEqual(response.status_code, 200)
        events = self._sse_events(response.get_data(as_text=True))
        self.assertEqual([event for event, _ in events], ["chunk", "replace"])
        turn = events[-1][1]["turn"]
        self.assertEqual(turn["answer_mode"], "local_kb")
        self.assertIn("离线知识库回答", turn["answer"])
        self.assertEqual(turn["suggestions"], [])

    def test_stream_emits_error_when_ai_and_local_knowledge_are_unavailable(self):
        self.fake_ai.stream_chat.side_effect = AiUnavailableError(
            "AI 服务暂时不可用"
        )
        response = self.student_client.post(
            (
                "/api/agri-skills/qa/conversations/"
                f"{self.conversation_id}/messages/stream"
            ),
            json={"question": "完全无关的问题"},
        )

        self.assertEqual(response.status_code, 200)
        events = self._sse_events(response.get_data(as_text=True))
        self.assertEqual(
            events,
            [
                (
                    "error",
                    {"message": "暂无法回答，建议稍后再试"},
                )
            ],
        )

    def test_non_stream_route_persists_local_fallback(self):
        self.fake_ai.stream_chat.side_effect = AiUnavailableError(
            "AI 服务暂时不可用"
        )
        response = self.student_client.post(
            (
                "/api/agri-skills/qa/conversations/"
                f"{self.conversation_id}/messages"
            ),
            json={"question": "荔枝蒂蛀虫导致落果", "input_mode": "text"},
        )

        self.assertEqual(response.status_code, 201)
        turn = response.get_json()["turn"]
        self.assertEqual(turn["answer_mode"], "local_kb")
        self.assertIn("离线知识库回答", turn["answer"])
        self.assertEqual(turn["suggestions"], [])
        self.fake_ai.complete_json.assert_not_called()

        thread = self.student_client.get(
            f"/api/agri-skills/qa/conversations/{self.conversation_id}"
        )
        self.assertEqual(
            thread.get_json()["turns"][-1]["answer_mode"],
            "local_kb",
        )

    def test_other_student_cannot_read_thread(self):
        response = self.other_client.get(
            f"/api/agri-skills/qa/conversations/{self.conversation_id}"
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.get_json(),
            {"success": False, "message": "问答记录不存在"},
        )

    def test_other_student_cannot_trigger_stream_or_ai(self):
        response = self.other_client.post(
            (
                "/api/agri-skills/qa/conversations/"
                f"{self.conversation_id}/messages/stream"
            ),
            json={"question": "越权问题", "input_mode": "text"},
        )

        self.assertEqual(response.status_code, 404)
        self.fake_ai.stream_chat.assert_not_called()
        self.fake_ai.complete_json.assert_not_called()

    def test_other_student_cannot_trigger_non_stream_ai(self):
        response = self.other_client.post(
            (
                "/api/agri-skills/qa/conversations/"
                f"{self.conversation_id}/messages"
            ),
            json={"question": "越权问题", "input_mode": "text"},
        )

        self.assertEqual(response.status_code, 404)
        self.fake_ai.stream_chat.assert_not_called()
        self.fake_ai.complete_json.assert_not_called()


if __name__ == "__main__":
    unittest.main()
