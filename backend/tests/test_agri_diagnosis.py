import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from app import create_app
from app.agri_skills.ai_client import set_ai_client
from app.agri_skills.diagnosis import (
    abandon_diagnosis,
    answer_diagnosis,
    create_diagnosis,
    expire_inactive_diagnoses,
    get_diagnosis,
    start_diagnosis,
)
from app.agri_skills.errors import (
    AgriNotFoundError,
    AgriValidationError,
    AiUnavailableError,
)
from app.db import get_db


class TestAgriDiagnosis(unittest.TestCase):
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

    def _create_session(self, question: str = "请补充症状出现时间"):
        self.ai.complete_json.return_value = {
            "status": "follow_up_required",
            "question": question,
            "conclusion": None,
            "limited": False,
        }
        with self.app.app_context():
            return create_diagnosis(
                self.student_id,
                "litchi",
                "fruit",
                ["虫蛀"],
            )

    def test_point_selection_is_required_before_ai(self):
        with self.app.app_context():
            with self.assertRaises(AgriValidationError):
                create_diagnosis(self.student_id, "litchi", "", [])

        self.ai.complete_json.assert_not_called()

    def test_create_diagnosis_immediately_returns_first_ai_question(self):
        session = self._create_session()

        self.assertEqual(session["status"], "in_progress")
        self.assertEqual(session["pending_question_round"], 1)
        self.assertEqual(session["pending_question"], "请补充症状出现时间")
        self.assertEqual(session["round_count"], 0)
        self.assertEqual(session["symptoms"], ["虫蛀"])
        self.assertIsNone(session["conclusion"])

        call = self.ai.complete_json.call_args
        self.assertEqual(call.kwargs["call_point"], "diagnosis_turn")
        context = json.loads(call.args[0][1]["content"])
        self.assertEqual(context["round_no"], 1)
        self.assertEqual(context["prior_questions"], [])
        self.assertEqual(context["prior_answers"], [])

    def test_conclusion_ready_ends_before_round_five(self):
        session = self._create_session()
        self.ai.complete_json.return_value = {
            "status": "conclusion_ready",
            "question": None,
            "conclusion": {
                "cause": "果实受蒂蛀虫危害",
                "treatment": "清理落果并按登记药剂防治",
            },
            "limited": False,
        }

        with self.app.app_context():
            result = answer_diagnosis(
                self.student_id,
                session["id"],
                "果实有虫孔",
                "text",
            )

        self.assertEqual(result["session"]["status"], "completed")
        self.assertEqual(result["status"], "conclusion_ready")
        self.assertFalse(result["session"]["limited"])
        self.assertIn("cause", result["session"]["conclusion"])
        self.assertIn("treatment", result["session"]["conclusion"])
        self.assertEqual(result["session"]["round_count"], 1)
        self.assertIsNone(result["session"]["pending_question"])

    def test_ai_unavailable_after_point_selection_persists_session(self):
        self.ai.complete_json.side_effect = AiUnavailableError(
            "AI 服务暂时不可用"
        )

        with self.app.app_context():
            session = create_diagnosis(
                self.student_id,
                "litchi",
                "fruit",
                ["虫蛀"],
            )
            persisted = get_diagnosis(self.student_id, session["id"])

        self.assertEqual(session["id"], persisted["id"])
        self.assertEqual(persisted["status"], "in_progress")
        self.assertIsNone(session["pending_question"])
        self.assertEqual(session["ai_error"], "AI 服务暂时不可用")
        self.assertEqual(session["symptoms"], ["虫蛀"])

    def test_first_question_recovers_after_initial_ai_failure(self):
        self.ai.complete_json.side_effect = [
            AiUnavailableError("AI 服务暂时不可用"),
            {
                "status": "follow_up_required",
                "question": "请补充果实病斑颜色",
                "conclusion": None,
                "limited": False,
            },
            {
                "status": "conclusion_ready",
                "question": None,
                "conclusion": {
                    "cause": "疑似霜疫霉病",
                    "treatment": "清除病果并改善通风",
                },
                "limited": False,
            },
        ]

        with self.app.app_context():
            session = create_diagnosis(
                self.student_id,
                "litchi",
                "fruit",
                ["斑点"],
            )
            result = answer_diagnosis(
                self.student_id,
                session["id"],
                "病斑呈褐色",
                "text",
            )

        self.assertEqual(result["session"]["status"], "completed")
        self.assertEqual(result["session"]["round_count"], 1)
        self.assertEqual(
            result["session"]["answer_records"][0]["answer"],
            "病斑呈褐色",
        )
        self.assertEqual(
            result["session"]["answer_records"][0]["question"],
            "请补充果实病斑颜色",
        )

    def test_invalid_ai_status_preserves_in_progress_session(self):
        session = self._create_session()
        self.ai.complete_json.return_value = {
            "status": "unknown",
            "question": "不应展示",
            "conclusion": None,
            "limited": False,
        }

        with self.app.app_context():
            with self.assertRaisesRegex(
                AiUnavailableError,
                "AI 服务暂时不可用",
            ):
                answer_diagnosis(
                    self.student_id,
                    session["id"],
                    "补充",
                    "text",
                )
            persisted = get_diagnosis(self.student_id, session["id"])

        self.assertEqual(persisted["status"], "in_progress")
        self.assertEqual(persisted["round_count"], 0)
        self.assertEqual(
            persisted["pending_question"],
            "请补充症状出现时间",
        )
        self.assertEqual(persisted["answers"], [])

    def test_fifth_round_forces_limited_conclusion(self):
        session = self._answer_until_round(4)
        self.ai.complete_json.return_value = {
            "status": "follow_up_required",
            "question": "不应成为第六轮问题",
            "conclusion": None,
            "limited": False,
        }

        with self.app.app_context():
            result = answer_diagnosis(
                self.student_id,
                session["id"],
                "第五轮",
                "text",
            )

        self.assertEqual(result["session"]["status"], "completed")
        self.assertTrue(result["session"]["limited"])
        self.assertEqual(result["session"]["round_count"], 5)
        self.assertIsNone(result["session"]["pending_question"])
        self.assertTrue(result["session"]["conclusion"]["cause"])
        self.assertTrue(result["session"]["conclusion"]["treatment"])

    def test_fifth_round_invalid_status_still_returns_limited_conclusion(self):
        session = self._answer_until_round(4)
        self.ai.complete_json.return_value = {
            "status": "unknown",
            "question": "无效追问",
            "conclusion": None,
        }

        with self.app.app_context():
            result = answer_diagnosis(
                self.student_id,
                session["id"],
                "第五轮",
                "voice",
            )

        self.assertEqual(result["session"]["status"], "completed")
        self.assertTrue(result["session"]["limited"])
        self.assertIsNone(result["session"]["pending_question"])

    def test_abandoned_diagnosis_cannot_continue(self):
        session = self._create_session()
        calls_before_abandon = self.ai.complete_json.call_count

        with self.app.app_context():
            abandoned = abandon_diagnosis(self.student_id, session["id"])
            with self.assertRaisesRegex(
                AgriValidationError,
                "诊断会话不可继续",
            ):
                answer_diagnosis(
                    self.student_id,
                    session["id"],
                    "不应继续",
                    "text",
                )

        self.assertEqual(abandoned["status"], "abandoned")
        self.assertIsNotNone(abandoned["abandoned_at"])
        self.assertEqual(self.ai.complete_json.call_count, calls_before_abandon)

    def test_other_student_cannot_read_or_modify_diagnosis(self):
        session = self._create_session()

        with self.app.app_context():
            with self.assertRaises(AgriNotFoundError):
                get_diagnosis(self.other_student_id, session["id"])
            with self.assertRaises(AgriNotFoundError):
                start_diagnosis(self.other_student_id, session["id"])
            with self.assertRaises(AgriNotFoundError):
                abandon_diagnosis(self.other_student_id, session["id"])

    def test_inactive_diagnosis_expires_after_365_days(self):
        session = self._create_session()

        with self.app.app_context():
            expired_count = expire_inactive_diagnoses(
                "2027-09-16T00:00:00+00:00"
            )
            persisted = get_diagnosis(self.student_id, session["id"])

        self.assertEqual(expired_count, 1)
        self.assertEqual(persisted["status"], "abandoned")

    def _answer_until_round(self, round_no: int) -> dict:
        session = self._create_session()
        self.ai.complete_json.return_value = {
            "status": "follow_up_required",
            "question": "下一轮问题",
            "conclusion": None,
            "limited": False,
        }
        with self.app.app_context():
            for current_round in range(1, round_no + 1):
                result = answer_diagnosis(
                    self.student_id,
                    session["id"],
                    f"第{current_round}轮回答",
                    "text",
                )
                session = result["session"]
        return session


if __name__ == "__main__":
    unittest.main()
