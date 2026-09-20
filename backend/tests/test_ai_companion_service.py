import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from app import create_app
from app.agri_skills.ai_client import set_ai_client
from app.agri_skills.errors import AgriValidationError, AiUnavailableError
from app.ai_companion.errors import (
    AiCompanionAiUnavailableError,
    AiCompanionForbiddenError,
    AiCompanionRecognitionError,
    AiCompanionValidationError,
)
from app.ai_companion.knowledge_provider import (
    set_assistant_feature_knowledge_provider,
)
from app.ai_companion.repository import get_conversation, list_conversations
from app.ai_companion.service import answer_question
from app.ai_companion.speech import transcribe_question
from app.db import get_db


class FakeKnowledgeProvider:
    def __init__(self, entries, error=None):
        self.entries = entries
        self.error = error

    def list_entries(self, enabled_only=True):
        if self.error:
            raise self.error
        return self.entries if enabled_only else list(self.entries)


class AiCompanionServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(Path(self.temp_dir.name) / "test.db"),
                "SECRET_KEY": "test-only-secret",
            }
        )
        # 冻结的拒绝分支在 with 块之外调用 list_conversations，需常驻应用上下文；
        # 与 tests/test_teacher_reports.py 的 setUp/tearDown 模式一致。
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.ai = Mock()
        set_ai_client(self.app, self.ai)
        self.user_id = self._insert_user("student-self", "student")

    def tearDown(self):
        self.app_context.pop()
        self.temp_dir.cleanup()

    def _insert_user(self, username, role):
        timestamp = "2026-09-21T10:00:00+08:00"
        with self.app.app_context():
            db = get_db()
            cursor = db.execute(
                """
                INSERT INTO users (
                    username,
                    password_hash,
                    name,
                    role,
                    is_enabled,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, 1, ?, ?)
                """,
                (
                    username,
                    "test-password-hash",
                    username,
                    role,
                    timestamp,
                    timestamp,
                ),
            )
            db.commit()
            return int(cursor.lastrowid)

    def entry(
        self,
        knowledge_id,
        title,
        body,
        jump_target,
        *,
        is_enabled=1,
    ):
        return {
            "knowledge_id": knowledge_id,
            "title": title,
            "body": body,
            "feature_key": knowledge_id.removeprefix("knowledge-"),
            "jump_target": jump_target,
            "is_enabled": is_enabled,
            "version": 1,
            "updated_at": "2026-09-20T10:00:00+08:00",
        }

    def job_entry(self):
        return self.entry(
            "knowledge-job",
            "如何投递简历",
            "进入就业对接",
            "/student/employment/jobs",
        )

    def test_platform_branch_persists_knowledge_answer(self):
        set_assistant_feature_knowledge_provider(
            self.app,
            FakeKnowledgeProvider([self.job_entry()]),
        )
        self.ai.complete_json.side_effect = [
            {"intent": "platform_usage"},
            {"answer": "进入就业对接后选择岗位投递。"},
        ]
        with self.app.app_context():
            result = answer_question(
                user_id=self.user_id,
                role="student",
                question="怎么投简历",
                client_request_id="request-1",
            )
        self.assertEqual(result["assistant_message"]["intent"], "platform_usage")
        self.assertEqual(
            result["assistant_message"]["jump_target"],
            "/student/employment/jobs",
        )

    def test_business_proxy_refusal_does_not_call_ai_or_repository_writes(self):
        with self.app.app_context():
            result = answer_question(
                user_id=self.user_id,
                role="student",
                question="帮我投简历",
                client_request_id="request-2",
            )
        self.assertEqual(result["assistant_message"]["intent"], "out_of_scope")
        self.ai.complete_json.assert_not_called()
        self.assertEqual(len(list_conversations(self.user_id)), 1)

    def test_unknown_role_and_invalid_question_are_rejected(self):
        with self.app.app_context():
            with self.assertRaises(AiCompanionForbiddenError):
                answer_question(
                    user_id=self.user_id,
                    role="admin",
                    question="怎么投简历",
                    client_request_id="request-3",
                )
            with self.assertRaises(AiCompanionValidationError):
                answer_question(
                    user_id=self.user_id,
                    role="student",
                    question=" ",
                    client_request_id="request-4",
                )

    def test_asr_reuses_shared_client_and_maps_errors(self):
        self.ai.transcribe.return_value = "荔枝什么时候套袋"
        with self.app.app_context():
            self.assertEqual(
                transcribe_question(b"audio", "question.webm"),
                "荔枝什么时候套袋",
            )
        self.ai.transcribe.assert_called_once_with(
            b"audio",
            "question.webm",
            call_point="speech_to_text",
        )

        self.ai.transcribe.side_effect = AgriValidationError("noise")
        with self.app.app_context():
            with self.assertRaises(AiCompanionRecognitionError):
                transcribe_question(b"noise", "noise.webm")

        self.ai.transcribe.side_effect = AiUnavailableError("down")
        with self.app.app_context():
            with self.assertRaises(AiCompanionAiUnavailableError):
                transcribe_question(b"audio", "question.webm")

    def test_learning_branch_returns_bullets_and_role_aware_jump(self):
        self.ai.complete_json.side_effect = [
            {"intent": "learning_question"},
            {"bullets": ["要点一", "要点二"], "module_key": "agriculture"},
        ]
        with self.app.app_context():
            student = answer_question(
                user_id=self.user_id,
                role="student",
                question="荔枝怎么修剪",
                client_request_id="learning-student",
            )
        self.assertEqual(student["bullets"], ["要点一", "要点二"])
        self.assertEqual(student["module_key"], "agriculture")
        self.assertEqual(student["jump_target"], "/student/agri-skills/qa")
        self.assertEqual(
            student["assistant_message"]["intent"],
            "learning_question",
        )

        teacher_id = self._insert_user("teacher-self", "teacher")
        self.ai.complete_json.side_effect = [
            {"intent": "learning_question"},
            {"bullets": ["要点一", "要点二"], "module_key": "agriculture"},
        ]
        with self.app.app_context():
            teacher = answer_question(
                user_id=teacher_id,
                role="teacher",
                question="荔枝怎么修剪",
                client_request_id="learning-teacher",
            )
        self.assertEqual(teacher["bullets"], ["要点一", "要点二"])
        self.assertIsNone(teacher["jump_target"])

    def test_replay_returns_same_result_without_second_ai_call(self):
        # 单元素 side_effect：重放若再次调用 AI 会抛 StopIteration，配合 call_count
        # 断言锁死 Medium-1 的“重放不再推理”契约。
        self.ai.complete_json.side_effect = [{"intent": "out_of_scope"}]
        with self.app.app_context():
            first = answer_question(
                user_id=self.user_id,
                role="student",
                question="今天天气怎么样",
                client_request_id="replay-request",
            )
            second = answer_question(
                user_id=self.user_id,
                role="student",
                question="今天天气怎么样",
                client_request_id="replay-request",
            )
        self.assertEqual(first["answer"], second["answer"])
        self.assertEqual(first["jump_target"], second["jump_target"])
        self.assertEqual(first["conversation_id"], second["conversation_id"])
        self.assertEqual(
            first["user_message"]["message_id"],
            second["user_message"]["message_id"],
        )
        self.assertEqual(
            first["assistant_message"]["message_id"],
            second["assistant_message"]["message_id"],
        )
        self.assertEqual(self.ai.complete_json.call_count, 1)

    def test_append_to_existing_conversation_keeps_same_thread(self):
        self.ai.complete_json.side_effect = [
            {"intent": "out_of_scope"},
            {"intent": "out_of_scope"},
        ]
        with self.app.app_context():
            first = answer_question(
                user_id=self.user_id,
                role="student",
                question="今天天气怎么样",
                client_request_id="append-request-1",
            )
            conversation_id = first["conversation_id"]
            answer_question(
                user_id=self.user_id,
                role="student",
                question="明天会下雨吗",
                client_request_id="append-request-2",
                conversation_id=conversation_id,
            )
            detail = get_conversation(self.user_id, conversation_id)
        self.assertEqual(len(detail["messages"]), 4)
        self.assertEqual(detail["messages"][0]["role"], "user")
        self.assertEqual(detail["messages"][3]["role"], "assistant")


if __name__ == "__main__":
    unittest.main()
