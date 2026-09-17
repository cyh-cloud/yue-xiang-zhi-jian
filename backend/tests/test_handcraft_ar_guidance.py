import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import create_app
from app.agri_skills.ai_client import set_ai_client
from app.agri_skills.errors import AgriValidationError, AiUnavailableError
from app.db import get_db


class FakeAiClient:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def complete_json(self, messages, *, call_point):
        self.calls.append(
            {
                "messages": messages,
                "call_point": call_point,
            }
        )
        if self.error is not None:
            raise self.error
        return self.response


class TestHandcraftArGuidance(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(Path(self.temp_dir.name) / "test.db"),
                "SECRET_KEY": "test-only-secret",
            }
        )
        with self.app.app_context():
            db = get_db()
            db.execute(
                """
                INSERT INTO users (
                    id, username, password_hash, name, role, is_enabled,
                    created_at, updated_at
                )
                VALUES (
                    1, 'student01', 'hash', '学员', 'student', 1,
                    '2026-09-18T00:00:00+08:00',
                    '2026-09-18T00:00:00+08:00'
                )
                """
            )
            db.commit()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_success_returns_strict_fr_077_guidance(self):
        response = {
            "craft_key": "guangxiu",
            "tool_preparation": [" 绣线 ", "绣针"],
            "operating_points": ["先固定图案"],
            "common_errors": ["针脚不匀"],
            "steps": [
                {
                    "step_no": 1,
                    "title": " 起针 ",
                    "instruction": " 从背面起针 ",
                },
                {
                    "step_no": 2,
                    "title": "收针",
                    "instruction": "完成背面收线",
                },
            ],
            "unexpected": "must be removed",
        }
        client = FakeAiClient(response)
        set_ai_client(self.app, client)

        with self.app.app_context():
            with patch(
                "app.handcraft_inheritance.ar_guidance."
                "record_duration_points"
            ) as record:
                from app.handcraft_inheritance.ar_guidance import (
                    generate_ar_guidance,
                )

                result = generate_ar_guidance(1, "guangxiu", " 绣制花瓣 ")

        self.assertEqual(
            result,
            {
                "craft_key": "guangxiu",
                "tool_preparation": ["绣线", "绣针"],
                "operating_points": ["先固定图案"],
                "common_errors": ["针脚不匀"],
                "steps": [
                    {
                        "step_no": 1,
                        "title": "起针",
                        "instruction": "从背面起针",
                    },
                    {
                        "step_no": 2,
                        "title": "收针",
                        "instruction": "完成背面收线",
                    },
                ],
            },
        )
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(
            client.calls[0]["call_point"],
            "handcraft_ar_guidance_generate",
        )
        self.assertEqual(
            json.loads(client.calls[0]["messages"][1]["content"]),
            {
                "craft_key": "guangxiu",
                "craft_name": "广绣",
                "project_label": "绣制花瓣",
            },
        )
        record.assert_not_called()

    def test_invalid_craft_or_project_never_calls_ai_or_enqueues_points(self):
        client = FakeAiClient({"craft_key": "guangxiu"})
        set_ai_client(self.app, client)

        with self.app.app_context():
            from app.handcraft_inheritance.ar_guidance import (
                generate_ar_guidance,
            )

            cases = (
                (1, "missing", "绣制花瓣"),
                (1, "guangxiu", "   "),
                (True, "guangxiu", "绣制花瓣"),
            )
            for user_id, craft_key, project_label in cases:
                with self.subTest(
                    user_id=user_id,
                    craft_key=craft_key,
                    project_label=project_label,
                ):
                    with patch(
                        "app.handcraft_inheritance.ar_guidance."
                        "record_duration_points"
                    ) as record:
                        with self.assertRaises(AgriValidationError):
                            generate_ar_guidance(
                                user_id,
                                craft_key,
                                project_label,
                            )
                        record.assert_not_called()

        self.assertEqual(client.calls, [])

    def test_malformed_ai_responses_are_unavailable_without_points(self):
        invalid_responses = (
            {},
            {"craft_key": "chaoshan-woodcarving"},
            {
                "craft_key": "guangxiu",
                "tool_preparation": [],
                "operating_points": ["操作"],
                "common_errors": ["错误"],
                "steps": [
                    {
                        "step_no": 1,
                        "title": "步骤",
                        "instruction": "说明",
                    }
                ],
            },
            {
                "craft_key": "guangxiu",
                "tool_preparation": ["工具"],
                "operating_points": ["操作"],
                "common_errors": ["错误"],
                "steps": [
                    {
                        "step_no": 1,
                        "title": "步骤",
                        "instruction": "说明",
                    },
                    {
                        "step_no": 1,
                        "title": "重复",
                        "instruction": "重复",
                    },
                ],
            },
            {
                "craft_key": "guangxiu",
                "tool_preparation": ["工具"],
                "operating_points": ["操作"],
                "common_errors": ["错误"],
                "steps": [
                    {
                        "step_no": 1,
                        "title": "",
                        "instruction": "说明",
                    }
                ],
            },
            {
                "craft_key": "guangxiu",
                "tool_preparation": ["工具"],
                "operating_points": ["操作"],
                "common_errors": ["错误"],
                "steps": [
                    {
                        "step_no": 1,
                        "title": "步骤",
                        "instruction": "说明",
                        "extra": "unsupported",
                    }
                ],
            },
            "not-an-object",
        )

        with self.app.app_context():
            from app.handcraft_inheritance.ar_guidance import (
                generate_ar_guidance,
            )

            for response in invalid_responses:
                with self.subTest(response=response):
                    set_ai_client(self.app, FakeAiClient(response))
                    with patch(
                        "app.handcraft_inheritance.ar_guidance."
                        "record_duration_points"
                    ) as record:
                        with self.assertRaises(AiUnavailableError) as raised:
                            generate_ar_guidance(
                                1,
                                "guangxiu",
                                "绣制花瓣",
                            )
                        record.assert_not_called()

                    self.assertEqual(
                        str(raised.exception),
                        "AI 服务暂时不可用",
                    )
                    self.assertEqual(
                        raised.exception.details,
                        {
                            "craft_key": "guangxiu",
                            "craft_name": "广绣",
                            "project_label": "绣制花瓣",
                        },
                    )

    def test_timeout_is_normalized_without_points_write(self):
        set_ai_client(
            self.app,
            FakeAiClient(error=TimeoutError("upstream timed out")),
        )

        with self.app.app_context():
            from app.handcraft_inheritance.ar_guidance import (
                generate_ar_guidance,
            )

            with patch(
                "app.handcraft_inheritance.ar_guidance."
                "record_duration_points"
            ) as record:
                with self.assertRaises(AiUnavailableError) as raised:
                    generate_ar_guidance(1, "guangxiu", "绣制花瓣")
                record.assert_not_called()

        self.assertEqual(str(raised.exception), "AI 服务暂时不可用")
        self.assertEqual(
            raised.exception.details,
            {
                "craft_key": "guangxiu",
                "craft_name": "广绣",
                "project_label": "绣制花瓣",
            },
        )

    def test_active_time_records_duration_with_stable_caller_event_id(self):
        response = {
            "craft_key": "guangxiu",
            "tool_preparation": ["绣线"],
            "operating_points": ["先定位"],
            "common_errors": ["针脚不匀"],
            "steps": [
                {
                    "step_no": 1,
                    "title": "起针",
                    "instruction": "从背面起针",
                }
            ],
        }
        set_ai_client(self.app, FakeAiClient(response))

        with self.app.app_context():
            from app.handcraft_inheritance.ar_guidance import (
                generate_ar_guidance,
            )

            with patch(
                "app.handcraft_inheritance.ar_guidance."
                "record_duration_points",
                return_value={"status": "processed"},
            ) as record:
                generate_ar_guidance(
                    1,
                    "guangxiu",
                    "绣制花瓣",
                    active_seconds=600,
                    event_id="ar-session-1",
                )

        record.assert_called_once()
        args = record.call_args.args
        self.assertEqual(args[:4], (1, "handcraft", "guangxiu", 600))
        self.assertIsInstance(args[4], str)
        self.assertTrue(args[4].strip())
        self.assertEqual(args[5], "ar-session-1")

    def test_success_persists_one_points_event_and_failure_writes_none(self):
        valid_response = {
            "craft_key": "guangxiu",
            "tool_preparation": ["绣线"],
            "operating_points": ["先定位"],
            "common_errors": ["针脚不匀"],
            "steps": [
                {
                    "step_no": 1,
                    "title": "起针",
                    "instruction": "从背面起针",
                }
            ],
        }

        with self.app.app_context():
            from app.handcraft_inheritance.ar_guidance import (
                generate_ar_guidance,
            )

            set_ai_client(self.app, FakeAiClient(valid_response))
            generate_ar_guidance(
                1,
                "guangxiu",
                "绣制花瓣",
                active_seconds=600,
                event_id="ar-session-1",
            )
            rows = [
                dict(row)
                for row in get_db().execute(
                    """
                    SELECT source_module, event_type, source_event_id,
                           duration_seconds, status
                    FROM points_event_inbox
                    ORDER BY id
                    """
                ).fetchall()
            ]

            set_ai_client(self.app, FakeAiClient({}))
            with self.assertRaises(AiUnavailableError):
                generate_ar_guidance(
                    1,
                    "guangxiu",
                    "绣制花瓣",
                    active_seconds=600,
                    event_id="failed-generation",
                )
            event_count = get_db().execute(
                "SELECT COUNT(*) AS count FROM points_event_inbox"
            ).fetchone()["count"]

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["source_module"], "handcraft")
        self.assertEqual(rows[0]["event_type"], "duration")
        self.assertEqual(rows[0]["source_event_id"], "guangxiu|ar-session-1")
        self.assertEqual(rows[0]["duration_seconds"], 600)
        self.assertEqual(rows[0]["status"], "processed")
        self.assertEqual(event_count, 1)

    def test_repeated_stable_event_id_records_one_duration_event(self):
        response = {
            "craft_key": "guangxiu",
            "tool_preparation": ["绣线"],
            "operating_points": ["先定位"],
            "common_errors": ["针脚不匀"],
            "steps": [
                {
                    "step_no": 1,
                    "title": "起针",
                    "instruction": "从背面起针",
                }
            ],
        }
        set_ai_client(self.app, FakeAiClient(response))

        with self.app.app_context():
            from app.handcraft_inheritance.ar_guidance import (
                generate_ar_guidance,
            )

            for _ in range(2):
                generate_ar_guidance(
                    1,
                    "guangxiu",
                    "绣制花瓣",
                    active_seconds=600,
                    event_id="same-ar-session",
                )
            rows = [
                dict(row)
                for row in get_db().execute(
                    """
                    SELECT event_type, source_event_id, duration_seconds
                    FROM points_event_inbox
                    """
                ).fetchall()
            ]

        self.assertEqual(
            rows,
            [
                {
                    "event_type": "duration",
                    "source_event_id": "guangxiu|same-ar-session",
                    "duration_seconds": 600,
                }
            ],
        )

    def test_invalid_active_time_arguments_do_not_call_ai_or_record_points(self):
        client = FakeAiClient({"craft_key": "guangxiu"})
        set_ai_client(self.app, client)

        with self.app.app_context():
            from app.handcraft_inheritance.ar_guidance import (
                generate_ar_guidance,
            )

            cases = (
                (-1, "negative"),
                (True, "boolean"),
                (7201, "too-long"),
                (600, None),
                (600, ""),
                (600, "   "),
                (600, 123),
            )
            for active_seconds, event_id in cases:
                with self.subTest(
                    active_seconds=active_seconds,
                    event_id=event_id,
                ):
                    with patch(
                        "app.handcraft_inheritance.ar_guidance."
                        "record_duration_points"
                    ) as record:
                        with self.assertRaises(AgriValidationError):
                            generate_ar_guidance(
                                1,
                                "guangxiu",
                                "绣制花瓣",
                                active_seconds=active_seconds,
                                event_id=event_id,
                            )
                        record.assert_not_called()

        self.assertEqual(client.calls, [])

    def test_points_record_failure_warns_without_blocking_or_leaking_context(self):
        response = {
            "craft_key": "guangxiu",
            "tool_preparation": ["绣线"],
            "operating_points": ["先定位"],
            "common_errors": ["针脚不匀"],
            "steps": [
                {
                    "step_no": 1,
                    "title": "起针",
                    "instruction": "从背面起针",
                }
            ],
        }
        set_ai_client(self.app, FakeAiClient(response))

        with self.app.app_context():
            from app.handcraft_inheritance.ar_guidance import (
                generate_ar_guidance,
            )

            with patch(
                "app.handcraft_inheritance.ar_guidance."
                "record_duration_points",
                side_effect=RuntimeError(
                    "student01 13800000000 绣制花瓣 ar-sensitive"
                ),
            ), self.assertLogs(
                "app.handcraft_inheritance.ar_guidance",
                level="WARNING",
            ) as logs:
                result = generate_ar_guidance(
                    1,
                    "guangxiu",
                    "绣制花瓣",
                    active_seconds=600,
                    event_id="ar-sensitive",
                )

        self.assertEqual(result["craft_key"], "guangxiu")
        self.assertEqual(result["steps"][0]["step_no"], 1)
        output = "\n".join(logs.output)
        self.assertIn("AR active-use points recording failed", output)
        self.assertIn("RuntimeError", output)
        for sensitive in (
            "student01",
            "13800000000",
            "绣制花瓣",
            "ar-sensitive",
        ):
            self.assertNotIn(sensitive, output)

    def test_failed_points_result_warns_without_blocking_success(self):
        response = {
            "craft_key": "guangxiu",
            "tool_preparation": ["绣线"],
            "operating_points": ["先定位"],
            "common_errors": ["针脚不匀"],
            "steps": [
                {
                    "step_no": 1,
                    "title": "起针",
                    "instruction": "从背面起针",
                }
            ],
        }
        set_ai_client(self.app, FakeAiClient(response))

        with self.app.app_context():
            from app.handcraft_inheritance.ar_guidance import (
                generate_ar_guidance,
            )

            with patch(
                "app.handcraft_inheritance.ar_guidance."
                "record_duration_points",
                return_value={
                    "status": "failed",
                    "error": "student01 ar-sensitive",
                },
            ), self.assertLogs(
                "app.handcraft_inheritance.ar_guidance",
                level="WARNING",
            ) as logs:
                result = generate_ar_guidance(
                    1,
                    "guangxiu",
                    "绣制花瓣",
                    active_seconds=600,
                    event_id="ar-sensitive",
                )

        self.assertEqual(result["craft_key"], "guangxiu")
        output = "\n".join(logs.output)
        self.assertIn("AR active-use points recording failed", output)
        self.assertIn("failed_result", output)
        self.assertNotIn("student01", output)
        self.assertNotIn("ar-sensitive", output)


if __name__ == "__main__":
    unittest.main()
