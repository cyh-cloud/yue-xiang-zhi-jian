import json
import unittest

import httpx
from flask import Flask

from app.agri_skills.ai_context import (
    AI_FIELD_ALLOWLISTS,
    build_ai_messages,
    redact_ai_log,
)
from app.agri_skills import install_default_agri_services
from app.agri_skills.ai_client import OpenAiCompatibleAiClient
from app.agri_skills.errors import AiUnavailableError


class StaticStreamTransport(httpx.BaseTransport):
    def __init__(self, lines: list[bytes], status_code: int = 200):
        self.lines = lines
        self.status_code = status_code

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            self.status_code,
            content=b"".join(self.lines),
            request=request,
        )


class TestAgriAiContext(unittest.TestCase):
    def test_allowlists_match_each_ai_call_point(self):
        self.assertEqual(
            AI_FIELD_ALLOWLISTS,
            {
                "speech_to_text": {"audio", "filename"},
                "qa_answer": {"question", "conversation_summary"},
                "qa_followups": {"question", "answer"},
                "diagnosis_turn": {
                    "product_name",
                    "affected_part",
                    "symptoms",
                    "round_no",
                    "prior_questions",
                    "prior_answers",
                    "source_conclusion",
                    "followup_status",
                    "followup_note",
                },
                "selftest_generate": {"diagnosis_text"},
                "selftest_grade": {"questions", "answers"},
                "course_quiz_grade": {
                    "course_summary",
                    "questions",
                    "answers",
                },
            },
        )

    def test_allowlist_drops_account_and_other_student_fields(self):
        messages = build_ai_messages(
            "qa_answer",
            {
                "question": "荔枝落果怎么办",
                "username": "student01",
                "contact": "13800000000",
                "other_student_question": "不应发送",
            },
        )

        serialized = json.dumps(messages, ensure_ascii=False)
        self.assertIn("荔枝落果怎么办", serialized)
        self.assertNotIn("student01", serialized)
        self.assertNotIn("13800000000", serialized)
        self.assertNotIn("不应发送", serialized)
        self.assertEqual(
            messages,
            [
                {"role": "system", "content": "农业技能任务：qa_answer"},
                {
                    "role": "user",
                    "content": json.dumps(
                        {"question": "荔枝落果怎么办"},
                        ensure_ascii=False,
                    ),
                },
            ],
        )

    def test_redaction_removes_credentials_and_contacts_recursively(self):
        value = redact_ai_log(
            {
                "PASSWORD": "secret",
                "Contact": "13800000000",
                "question": "荔枝",
                "nested": [
                    {"session": "session-id", "answer": "保持"},
                    {"token": "token-value"},
                ],
            }
        )

        self.assertEqual(
            value,
            {
                "PASSWORD": "[REDACTED]",
                "Contact": "[REDACTED]",
                "question": "荔枝",
                "nested": [
                    {"session": "[REDACTED]", "answer": "保持"},
                    {"token": "[REDACTED]"},
                ],
            },
        )


class TestOpenAiCompatibleAiClient(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)

    def test_http_client_streams_sse_lines(self):
        transport = StaticStreamTransport(
            [
                b'data: {"choices":[{"delta":{"content":"\xe8\x8d\x94"}}]}\n\n',
                b'data: {"choices":[{"delta":{"content":"\xe6\x9e\x9d"}}]}\n\n',
                b"data: [DONE]\n\n",
            ]
        )
        client = OpenAiCompatibleAiClient(
            api_url="https://example.test/chat/completions",
            api_key="key",
            model="model",
            timeout=5,
            transport=transport,
        )

        self.assertEqual(
            list(client.stream_chat([], call_point="qa_answer")),
            ["荔", "枝"],
        )

    def test_http_client_completes_json_from_fenced_content(self):
        transport = httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "content": '```json\n{"score": 90}\n```',
                            }
                        }
                    ]
                },
                request=request,
            )
        )
        client = OpenAiCompatibleAiClient(
            api_url="https://example.test/chat/completions",
            api_key="key",
            model="model",
            timeout=5,
            transport=transport,
        )

        self.assertEqual(
            client.complete_json([], call_point="selftest_grade"),
            {"score": 90},
        )

    def test_http_client_requires_configuration(self):
        client = OpenAiCompatibleAiClient(
            api_url="",
            api_key="",
            model="model",
            timeout=5,
        )

        with self.assertRaisesRegex(
            AiUnavailableError,
            "AI service is not configured",
        ):
            list(client.stream_chat([], call_point="qa_answer"))

        with self.assertRaisesRegex(
            AiUnavailableError,
            "AI service is not configured",
        ):
            client.complete_json([], call_point="qa_answer")

    def test_upstream_http_failure_is_wrapped_and_logged_redacted(self):
        transport = httpx.MockTransport(
            lambda request: httpx.Response(
                502,
                text="upstream unavailable",
                request=request,
            )
        )
        client = OpenAiCompatibleAiClient(
            api_url="https://example.test/chat/completions",
            api_key="key",
            model="model",
            timeout=5,
            transport=transport,
        )
        messages = [
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "question": "荔枝",
                        "password": "top-secret",
                        "contact": "13800000000",
                    },
                    ensure_ascii=False,
                ),
            }
        ]

        with self.app.app_context():
            with self.assertLogs(self.app.logger.name, level="WARNING") as logs:
                with self.assertRaises(AiUnavailableError):
                    client.complete_json(
                        messages,
                        call_point="selftest_grade",
                    )

        output = "\n".join(logs.output)
        self.assertIn("AI call failed for selftest_grade", output)
        self.assertIn("[REDACTED]", output)
        self.assertNotIn("top-secret", output)
        self.assertNotIn("13800000000", output)

    def test_malformed_stream_response_is_wrapped(self):
        client = OpenAiCompatibleAiClient(
            api_url="https://example.test/chat/completions",
            api_key="key",
            model="model",
            timeout=5,
            transport=StaticStreamTransport([b"data: not-json\n\n"]),
        )

        with self.app.app_context():
            with self.assertRaises(AiUnavailableError):
                list(client.stream_chat([], call_point="qa_answer"))

    def test_malformed_json_completion_is_wrapped(self):
        transport = httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "content": "not-json",
                            }
                        }
                    ]
                },
                request=request,
            )
        )
        client = OpenAiCompatibleAiClient(
            api_url="https://example.test/chat/completions",
            api_key="key",
            model="model",
            timeout=5,
            transport=transport,
        )

        with self.app.app_context():
            with self.assertRaises(AiUnavailableError):
                client.complete_json([], call_point="selftest_grade")

    def test_default_service_installs_configured_http_client(self):
        self.app.config.update(
            {
                "AI_API_URL": "https://example.test/chat/completions",
                "AI_API_KEY": "key",
                "AI_MODEL": "model",
                "AI_TIMEOUT_SECONDS": 5,
            }
        )

        install_default_agri_services(self.app)

        self.assertIsInstance(
            self.app.extensions["agri_ai_client"],
            OpenAiCompatibleAiClient,
        )


if __name__ == "__main__":
    unittest.main()
