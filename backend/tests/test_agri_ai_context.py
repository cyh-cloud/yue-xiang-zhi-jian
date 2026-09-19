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
    def test_agri_allowlists_are_preserved(self):
        expected = {
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
                "course_direction",
            },
            "teacher_quiz_generate": {
                "course_summary",
                "course_direction",
            },
            "handcraft_ar_guidance_generate": {
                "craft_key",
                "craft_name",
                "project_label",
            },
        }
        for call_point, fields in expected.items():
            self.assertEqual(AI_FIELD_ALLOWLISTS[call_point], fields)

    def test_course_quiz_domain_uses_course_direction(self):
        agriculture = build_ai_messages(
            "course_quiz_grade",
            {"course_summary": "农业课程"},
        )
        ecommerce = build_ai_messages(
            "course_quiz_grade",
            {
                "course_summary": "电商课程",
                "course_direction": "ecommerce",
            },
        )
        handcraft = build_ai_messages(
            "course_quiz_grade",
            {
                "course_summary": "广绣课程",
                "course_direction": "handcraft",
            },
        )

        self.assertEqual(
            agriculture[0]["content"],
            "农业技能任务：course_quiz_grade",
        )
        self.assertEqual(
            ecommerce[0]["content"],
            "电商运营实训任务：course_quiz_grade",
        )
        self.assertEqual(
            handcraft[0]["content"],
            "手工传承任务：course_quiz_grade",
        )

    def test_teacher_quiz_generation_uses_agriculture_fallback(self):
        messages = build_ai_messages(
            "teacher_quiz_generate",
            {
                "course_summary": "荔枝保果课程",
                "course_direction": "agriculture",
                "teacher_id": 7,
                "course_id": 1,
                "media_url": "https://media.example.test/course.mp4",
            },
        )

        self.assertEqual(
            messages[0]["content"],
            "农业技能任务：teacher_quiz_generate",
        )
        self.assertEqual(
            json.loads(messages[1]["content"]),
            {
                "course_summary": "荔枝保果课程",
                "course_direction": "agriculture",
            },
        )

    def test_handcraft_ar_guidance_uses_handcraft_domain(self):
        messages = build_ai_messages(
            "handcraft_ar_guidance_generate",
            {
                "craft_key": "guangxiu",
                "craft_name": "广绣",
                "project_label": "绣制花瓣",
            },
        )

        self.assertEqual(
            messages[0]["content"],
            "手工传承任务：handcraft_ar_guidance_generate",
        )

    def test_handcraft_payloads_only_include_allowlisted_fields(self):
        cases = (
            (
                "handcraft_ar_guidance_generate",
                {
                    "craft_key": "guangxiu",
                    "craft_name": "广绣",
                    "project_label": "绣制花瓣",
                    "username": "student01",
                    "contact": "13800000000",
                    "user_id": 99,
                    "token": "plain-token",
                    "other_student_id": 100,
                    "unexpected_field": "must-not-send",
                },
                {
                    "craft_key": "guangxiu",
                    "craft_name": "广绣",
                    "project_label": "绣制花瓣",
                },
            ),
            (
                "course_quiz_grade",
                {
                    "course_direction": "handcraft",
                    "course_summary": "广绣基础课程",
                    "questions": [
                        {
                            "id": "q1",
                            "prompt": "题目",
                            "options": ["A", "B"],
                        }
                    ],
                    "answers": {"q1": "A"},
                    "username": "student01",
                    "contact": "13800000000",
                    "user_id": 99,
                    "token": "plain-token",
                    "student_id": 100,
                    "unexpected_field": "must-not-send",
                },
                {
                    "course_direction": "handcraft",
                    "course_summary": "广绣基础课程",
                    "questions": [
                        {
                            "id": "q1",
                            "prompt": "题目",
                            "options": ["A", "B"],
                        }
                    ],
                    "answers": {"q1": "A"},
                },
            ),
        )
        forbidden_values = (
            "student01",
            "13800000000",
            "99",
            "plain-token",
            "100",
            "must-not-send",
        )

        for call_point, context, expected in cases:
            with self.subTest(call_point=call_point):
                messages = build_ai_messages(call_point, context)
                payload = json.loads(messages[1]["content"])

                self.assertEqual(payload, expected)
                serialized = json.dumps(messages, ensure_ascii=False)
                for forbidden in forbidden_values:
                    self.assertNotIn(forbidden, serialized)

    def test_call_domains_separate_agriculture_and_ecommerce(self):
        agriculture = build_ai_messages(
            "qa_answer",
            {"question": "荔枝落果怎么办"},
        )
        ecommerce = build_ai_messages(
            "live_script_generate",
            {
                "product_name": "荔枝干",
                "selling_points": ["香甜"],
                "price_text": "39.9 元",
                "style": "enthusiastic",
            },
        )

        self.assertEqual(
            agriculture[0]["content"],
            "农业技能任务：qa_answer",
        )
        self.assertEqual(
            ecommerce[0]["content"],
            "电商运营实训任务：live_script_generate",
        )

    def test_ecommerce_allowlists_are_exact_and_strip_sensitive_fields(self):
        expected = {
            "live_script_generate": {
                "product_name",
                "selling_points",
                "price_text",
                "style",
            },
            "simulation_score": {"scene_label", "segments"},
            "copy_case_generate": {"product_type", "scene"},
            "copy_reference_critique": {
                "case_text",
                "defect_categories",
                "learner_critique",
            },
            "copy_revised_generate": {
                "optimized_prompt",
                "case_text",
            },
            "copy_optimization_critique": {
                "original_copy",
                "revised_copy",
                "optimized_prompt",
            },
            "store_plan_generate": {
                "store_type",
                "platform",
                "style_preference",
            },
            "customer_message_generate": {
                "scenario",
                "goal_criteria",
                "prior_turns",
                "turn_no",
            },
            "customer_reply_analyze": {
                "scenario",
                "goal_criteria",
                "customer_message",
                "student_reply",
            },
            "customer_summary": {
                "scenario",
                "goal_criteria",
                "turns",
            },
        }
        sensitive_fields = {
            "username": "student01",
            "contact": "13800000000",
            "password": "plain-password",
            "token": "plain-token",
            "api_key": "plain-api-key",
        }

        for call_point, fields in expected.items():
            with self.subTest(call_point=call_point):
                self.assertEqual(AI_FIELD_ALLOWLISTS[call_point], fields)
                context = {
                    **{field: f"allowed-{field}" for field in fields},
                    **sensitive_fields,
                }

                messages = build_ai_messages(call_point, context)

                self.assertEqual(
                    json.loads(messages[1]["content"]),
                    {field: f"allowed-{field}" for field in fields},
                )
                serialized = json.dumps(messages, ensure_ascii=False)
                for sensitive_value in sensitive_fields.values():
                    self.assertNotIn(sensitive_value, serialized)

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

    def test_allowlist_recursively_drops_nested_sensitive_fields(self):
        messages = build_ai_messages(
            "qa_answer",
            {
                "question": "荔枝落果怎么办",
                "conversation_summary": {
                    "prior_topic": "落果",
                    "username": "student01",
                    "profile": {
                        "user_id": 7,
                        "contact": "13800000000",
                        "note": "保留",
                    },
                },
            },
        )

        self.assertEqual(
            json.loads(messages[1]["content"]),
            {
                "question": "荔枝落果怎么办",
                "conversation_summary": {
                    "prior_topic": "落果",
                    "profile": {"note": "保留"},
                },
            },
        )

    def test_redaction_removes_credentials_and_contacts_recursively(self):
        value = redact_ai_log(
            {
                "PASSWORD": "secret",
                "Contact": "13800000000",
                "api_key": "api-key-value",
                "question": "荔枝",
                "nested": [
                    {
                        "authorization": "Bearer token",
                        "secret": "shared-secret",
                        "session": "session-id",
                        "answer": "保持",
                    },
                    {"token": "token-value"},
                ],
            }
        )

        self.assertEqual(
            value,
            {
                "PASSWORD": "[REDACTED]",
                "Contact": "[REDACTED]",
                "api_key": "[REDACTED]",
                "question": "荔枝",
                "nested": [
                    {
                        "authorization": "[REDACTED]",
                        "secret": "[REDACTED]",
                        "session": "[REDACTED]",
                        "answer": "保持",
                    },
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

    def test_upstream_failure_logs_only_bounded_non_content_metadata(self):
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
                "content": "PROMPT-CONTENT-MUST-NOT-BE-LOGGED",
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
        self.assertIn("'operation': 'complete_json'", output)
        self.assertIn("'message_count': 1", output)
        self.assertNotIn("PROMPT-CONTENT-MUST-NOT-BE-LOGGED", output)

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

    def test_duplicate_top_level_json_field_is_unavailable(self):
        transport = httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "content": '{"score": 90, "score": 80}',
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
            with self.assertRaises(AiUnavailableError) as raised:
                client.complete_json([], call_point="selftest_grade")

        self.assertEqual(str(raised.exception), "AI 服务暂时不可用")

    def test_duplicate_nested_json_field_is_unavailable(self):
        transport = httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "content": (
                                    '{"questions": ['
                                    '{"id": "q1", "id": "q2"}'
                                    "]}"
                                ),
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
            with self.assertRaises(AiUnavailableError) as raised:
                client.complete_json([], call_point="selftest_grade")

        self.assertEqual(str(raised.exception), "AI 服务暂时不可用")

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
