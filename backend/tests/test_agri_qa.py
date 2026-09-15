import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from app import create_app
from app.agri_skills.ai_client import set_ai_client
from app.agri_skills.errors import (
    AgriNotFoundError,
    AiUnavailableError,
)
from app.agri_skills.qa import (
    answer_qa_once,
    create_qa_conversation,
    get_qa_thread,
    list_qa_conversations,
    persist_qa_turn,
    select_local_knowledge_entry,
    stream_qa_answer,
)
from app.db import get_db


class TestAgriQa(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(Path(self.temp_dir.name) / "test.db"),
                "SECRET_KEY": "test-only-secret",
                "AI_API_URL": "",
                "AI_API_KEY": "",
                "AI_MODEL": "test-model",
            }
        )
        with self.app.app_context():
            db = get_db()
            self.student_id = self._insert_student(db, "student01")
            self.other_student_id = self._insert_student(db, "student02")
            db.commit()

        self.ai = Mock()
        set_ai_client(self.app, self.ai)

    def tearDown(self):
        self.temp_dir.cleanup()

    @staticmethod
    def _insert_student(db, username: str) -> int:
        cursor = db.execute(
            """
            INSERT INTO users (
                username, password_hash, name, role, is_enabled,
                created_at, updated_at
            )
            VALUES (?, ?, ?, 'student', 1, ?, ?)
            """,
            (
                username,
                "test-password-hash",
                username,
                "2026-09-15T00:00:00+00:00",
                "2026-09-15T00:00:00+00:00",
            ),
        )
        return int(cursor.lastrowid)

    def _collect_stream(self, question: str) -> dict:
        with self.app.app_context():
            conversation = create_qa_conversation(
                self.student_id,
                question,
                "text",
            )
            chunks: list[str] = []
            for event in stream_qa_answer(conversation["id"], question):
                if event["type"] == "chunk":
                    chunks.append(event["content"])
                elif event["type"] == "complete":
                    return {**event, "answer": "".join(chunks)}
                elif event["type"] == "replace":
                    return event
        self.fail("Q&A stream ended without a terminal event")

    def test_local_knowledge_ranking_uses_match_count_then_keyword_length(self):
        with self.app.app_context():
            entry = select_local_knowledge_entry("荔枝蒂蛀虫导致落果")

        self.assertEqual(entry["id"], "litchi-stem-borer")

    def test_ai_unavailable_returns_labeled_local_answer_without_suggestions(self):
        self.ai.stream_chat.side_effect = AiUnavailableError("AI 服务暂时不可用")

        result = self._collect_stream("荔枝蒂蛀虫导致落果")

        self.assertEqual(result["answer_mode"], "local_kb")
        self.assertIn("离线知识库回答", result["answer"])
        self.assertIn("荔枝蒂蛀虫", result["answer"])
        self.assertEqual(result["suggestions"], [])
        self.ai.complete_json.assert_not_called()

    def test_no_local_match_returns_exact_message(self):
        self.ai.stream_chat.side_effect = AiUnavailableError("AI 服务暂时不可用")

        with self.assertRaisesRegex(
            AiUnavailableError,
            "暂无法回答，建议稍后再试",
        ):
            self._collect_stream("完全无关的问题")

    def test_ai_answer_requires_exactly_three_suggestions(self):
        self.ai.stream_chat.return_value = iter(["春季", "保果"])
        self.ai.complete_json.return_value = {
            "suggestions": ["如何施肥", "如何排水", "如何防虫"],
        }

        result = self._collect_stream("荔枝何时保果")

        self.assertEqual(result["answer"], "春季保果")
        self.assertEqual(result["answer_mode"], "ai")
        self.assertEqual(len(result["suggestions"]), 3)
        self.assertIsNone(result["suggestion_error"])

    def test_invalid_suggestion_output_returns_no_fabricated_suggestions(self):
        self.ai.stream_chat.return_value = iter(["春季", "保果"])
        self.ai.complete_json.return_value = {"suggestions": ["只给一条"]}

        result = self._collect_stream("荔枝何时保果")

        self.assertEqual(result["answer"], "春季保果")
        self.assertEqual(result["suggestions"], [])
        self.assertEqual(result["suggestion_error"], "AI 服务暂时不可用")

    def test_followup_failure_preserves_answer_without_fabricated_suggestions(self):
        self.ai.stream_chat.return_value = iter(["春季", "保果"])
        self.ai.complete_json.side_effect = AiUnavailableError(
            "AI 服务暂时不可用"
        )

        result = self._collect_stream("荔枝何时保果")

        self.assertEqual(result["answer"], "春季保果")
        self.assertEqual(result["suggestions"], [])
        self.assertEqual(result["suggestion_error"], "AI 服务暂时不可用")

    def test_partial_stream_failure_is_replaced_by_local_answer(self):
        def failed_stream(messages, *, call_point):
            yield "不完整"
            raise AiUnavailableError("AI service request failed")

        self.ai.stream_chat.side_effect = failed_stream

        result = self._collect_stream("荔枝蒂蛀虫导致落果")

        self.assertEqual(result["type"], "replace")
        self.assertEqual(result["answer_mode"], "local_kb")
        self.assertNotEqual(result["answer"], "不完整")
        self.assertEqual(result["suggestions"], [])

    def test_empty_ai_answer_uses_local_knowledge_fallback(self):
        self.ai.stream_chat.return_value = iter([" ", ""])

        result = self._collect_stream("荔枝蒂蛀虫导致落果")

        self.assertEqual(result["answer_mode"], "local_kb")
        self.assertIn("离线知识库回答", result["answer"])
        self.ai.complete_json.assert_not_called()

    def test_conversation_history_and_turn_are_persisted_in_order(self):
        with self.app.app_context():
            conversation = create_qa_conversation(
                self.student_id,
                "  荔枝落果怎么办  ",
                "text",
            )
            first = persist_qa_turn(
                user_id=self.student_id,
                conversation_id=conversation["id"],
                question="荔枝落果怎么办",
                answer="先检查蒂蛀虫。",
                input_mode="text",
                answer_mode="ai",
                suggestions=["如何用药", "何时复查", "是否疏果"],
            )
            second = persist_qa_turn(
                user_id=self.student_id,
                conversation_id=conversation["id"],
                question="如何用药",
                answer="请按登记药剂说明使用。",
                input_mode="voice",
                answer_mode="local_kb",
                suggestions=[],
            )
            listed = list_qa_conversations(self.student_id)
            thread = get_qa_thread(self.student_id, conversation["id"])

        self.assertEqual(conversation["title"], "荔枝落果怎么办")
        self.assertEqual([item["id"] for item in listed], [conversation["id"]])
        self.assertEqual(
            [turn["question"] for turn in thread["turns"]],
            ["荔枝落果怎么办", "如何用药"],
        )
        self.assertEqual(thread["turns"][0]["suggestions"], first["turns"][0]["suggestions"])
        self.assertEqual(thread["turns"][1]["input_mode"], "voice")
        self.assertEqual(thread["turns"][1]["answer_mode"], "local_kb")
        self.assertEqual(second["conversation"]["updated_at"], thread["conversation"]["updated_at"])

    def test_conversation_list_orders_by_latest_update(self):
        with self.app.app_context():
            first = create_qa_conversation(self.student_id, "第一问", "text")
            second = create_qa_conversation(self.student_id, "第二问", "text")
            persist_qa_turn(
                user_id=self.student_id,
                conversation_id=first["id"],
                question="第一问",
                answer="稍后更新的回答",
                input_mode="text",
                answer_mode="ai",
                suggestions=["一", "二", "三"],
            )
            listed = list_qa_conversations(self.student_id)

        self.assertEqual(
            [item["id"] for item in listed],
            [first["id"], second["id"]],
        )

    def test_other_student_cannot_read_or_persist_to_conversation(self):
        with self.app.app_context():
            conversation = create_qa_conversation(
                self.student_id,
                "荔枝落果怎么办",
                "text",
            )

            with self.assertRaises(AgriNotFoundError):
                get_qa_thread(self.other_student_id, conversation["id"])

            with self.assertRaises(AgriNotFoundError):
                persist_qa_turn(
                    user_id=self.other_student_id,
                    conversation_id=conversation["id"],
                    question="越权问题",
                    answer="越权回答",
                    input_mode="text",
                    answer_mode="ai",
                    suggestions=["一", "二", "三"],
                )

            turns = get_db().execute(
                "SELECT COUNT(*) AS count FROM agri_qa_turns"
            ).fetchone()

        self.assertEqual(turns["count"], 0)

    def test_answer_qa_once_persists_ai_turn(self):
        self.ai.stream_chat.return_value = iter(["春季", "保果"])
        self.ai.complete_json.return_value = {
            "suggestions": ["如何施肥", "如何排水", "如何防虫"],
        }

        with self.app.app_context():
            conversation = create_qa_conversation(
                self.student_id,
                "荔枝何时保果",
                "text",
            )
            thread = answer_qa_once(
                self.student_id,
                conversation["id"],
                "荔枝何时保果",
                "text",
            )

        turn = thread["turns"][0]
        self.assertEqual(turn["answer"], "春季保果")
        self.assertEqual(turn["answer_mode"], "ai")
        self.assertEqual(len(turn["suggestions"]), 3)


if __name__ == "__main__":
    unittest.main()
