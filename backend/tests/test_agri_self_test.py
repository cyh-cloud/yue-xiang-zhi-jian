import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from app import create_app
from app.agri_skills.ai_client import set_ai_client
from app.agri_skills.diagnosis import get_diagnosis
from app.agri_skills.self_test import generate_self_test, submit_self_test
from app.agri_skills.errors import (
    AgriNotFoundError,
    AgriValidationError,
    AiUnavailableError,
)
from app.agri_skills.outcomes import list_learning_outcomes
from app.db import get_db


class TestAgriSelfTest(unittest.TestCase):
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
            self.session_id = self._insert_completed_diagnosis(db)
            db.commit()

        self.ai = Mock()
        set_ai_client(self.app, self.ai)
        self.questions = [
            {
                "type": "single_choice",
                "prompt": "蒂蛀虫防治的第一步是什么？",
                "options": ["清理落果", "增加浇水"],
                "answer": "清理落果",
            },
            {
                "type": "true_false",
                "prompt": "药剂防治应按登记说明使用。",
                "options": ["正确", "错误"],
                "answer": "正确",
            },
            {
                "type": "single_choice",
                "prompt": "雨后应重点检查什么？",
                "options": ["落果和虫孔", "果实甜度"],
                "answer": "落果和虫孔",
            },
        ]

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

    def _insert_completed_diagnosis(self, db) -> int:
        cursor = db.execute(
            """
            INSERT INTO agri_diagnosis_sessions (
                user_id, product_key, affected_part, symptoms_json,
                status, round_count, conclusion_json, limited,
                created_at, updated_at
            )
            VALUES (?, 'litchi', 'fruit', ?, 'completed', 1, ?, 0, ?, ?)
            """,
            (
                self.student_id,
                json.dumps(["虫蛀", "落果"], ensure_ascii=False),
                json.dumps(
                    {
                        "cause": "果实受蒂蛀虫危害",
                        "treatment": "清理落果并按登记药剂防治",
                    },
                    ensure_ascii=False,
                ),
                "2026-09-15T00:00:00+00:00",
                "2026-09-15T00:00:00+00:00",
            ),
        )
        return int(cursor.lastrowid)

    def count_rows(self, table: str) -> int:
        with self.app.app_context():
            row = get_db().execute(
                f"SELECT COUNT(*) AS count FROM {table}"
            ).fetchone()
        return int(row["count"])

    def test_first_invalid_generation_retries_once_and_saves_second(self):
        self.ai.complete_json.side_effect = [
            {"questions": self.questions[:2]},
            {"questions": self.questions},
        ]

        with self.app.app_context():
            result = generate_self_test(self.student_id, self.session_id)

        self.assertEqual(result["generation_attempts"], 2)
        self.assertEqual(
            result["questions"],
            [
                {
                    "type": question["type"],
                    "prompt": question["prompt"],
                    "options": question["options"],
                }
                for question in self.questions
            ],
        )
        self.assertEqual(self.count_rows("agri_self_tests"), 1)

        call = self.ai.complete_json.call_args
        self.assertEqual(call.kwargs["call_point"], "selftest_generate")
        context = json.loads(call.args[0][1]["content"])
        self.assertEqual(
            context,
            {
                "diagnosis_text": (
                    "病因分析：果实受蒂蛀虫危害\n"
                    "防治方案：清理落果并按登记药剂防治"
                )
            },
        )

    def test_two_invalid_generations_publish_nothing(self):
        self.ai.complete_json.side_effect = [
            {"questions": self.questions[:2]},
            {"questions": []},
        ]

        with self.app.app_context():
            with self.assertRaisesRegex(
                AiUnavailableError,
                "AI 服务暂时不可用",
            ):
                generate_self_test(self.student_id, self.session_id)
            diagnosis = get_diagnosis(self.student_id, self.session_id)

        self.assertEqual(self.count_rows("agri_self_tests"), 0)
        self.assertEqual(diagnosis["status"], "completed")
        self.assertEqual(
            diagnosis["conclusion"]["cause"],
            "果实受蒂蛀虫危害",
        )

    def _generate_self_test(self) -> dict:
        self.ai.complete_json.return_value = {"questions": self.questions}
        with self.app.app_context():
            return generate_self_test(self.student_id, self.session_id)

    def test_submission_returns_score_and_explanations(self):
        self_test = self._generate_self_test()
        self.ai.complete_json.reset_mock()
        self.ai.complete_json.return_value = {
            "score": 67,
            "questions": [
                {"correct": True, "explanation": "清理落果可减少虫源。"},
                {"correct": False, "explanation": "必须按登记说明用药。"},
                {"correct": True, "explanation": "雨后重点检查落果和虫孔。"},
            ],
        }
        answers = {"q1": "清理落果", "q2": "错误", "q3": "落果和虫孔"}

        with self.app.app_context():
            result = submit_self_test(
                self.student_id,
                self_test["id"],
                answers,
            )

        self.assertEqual(result["score"], 67)
        self.assertEqual(result["attempt_id"], 1)
        self.assertEqual(
            result["questions"],
            [
                {
                    **{
                        "type": question["type"],
                        "prompt": question["prompt"],
                        "options": question["options"],
                    },
                    "correct": correctness,
                    "explanation": explanation,
                }
                for question, correctness, explanation in zip(
                    self.questions,
                    [True, False, True],
                    [
                        "清理落果可减少虫源。",
                        "必须按登记说明用药。",
                        "雨后重点检查落果和虫孔。",
                    ],
                )
            ],
        )
        self.assertEqual(self.count_rows("agri_self_test_attempts"), 1)

        call = self.ai.complete_json.call_args
        self.assertEqual(call.kwargs["call_point"], "selftest_grade")
        context = json.loads(call.args[0][1]["content"])
        self.assertEqual(
            context,
            {"questions": self.questions, "answers": answers},
        )

    def test_ai_grading_failure_preserves_data(self):
        self_test = self._generate_self_test()
        self.ai.complete_json.return_value = {
            "score": 67,
            "questions": [
                {"correct": True, "explanation": "清理落果可减少虫源。"},
                {"correct": False, "explanation": "必须按登记说明用药。"},
                {"correct": True, "explanation": "雨后重点检查落果和虫孔。"},
            ],
        }
        with self.app.app_context():
            submit_self_test(
                self.student_id,
                self_test["id"],
                {"q1": "清理落果", "q2": "错误", "q3": "落果和虫孔"},
            )

        self.ai.complete_json.side_effect = AiUnavailableError(
            "AI 服务暂时不可用"
        )
        with self.app.app_context():
            with self.assertRaisesRegex(
                AiUnavailableError,
                "AI 服务暂时不可用",
            ):
                submit_self_test(
                    self.student_id,
                    self_test["id"],
                    {"q1": "增加浇水", "q2": "正确", "q3": "果实甜度"},
                )
            diagnosis = get_diagnosis(self.student_id, self.session_id)

        self.assertEqual(self.count_rows("agri_self_tests"), 1)
        self.assertEqual(self.count_rows("agri_self_test_attempts"), 1)
        self.assertEqual(diagnosis["status"], "completed")

    def test_generation_requires_owned_completed_diagnosis(self):
        with self.app.app_context():
            db = get_db()
            in_progress_id = self._insert_in_progress_diagnosis(db)
            db.commit()
            with self.assertRaises(AgriNotFoundError):
                generate_self_test(self.other_student_id, self.session_id)
            with self.assertRaises(AgriValidationError):
                generate_self_test(self.student_id, in_progress_id)

        self.ai.complete_json.assert_not_called()
        self.assertEqual(self.count_rows("agri_self_tests"), 0)

    def _insert_in_progress_diagnosis(self, db) -> int:
        cursor = db.execute(
            """
            INSERT INTO agri_diagnosis_sessions (
                user_id, product_key, affected_part, symptoms_json,
                status, round_count, created_at, updated_at
            )
            VALUES (?, 'litchi', 'fruit', ?, 'in_progress', 0, ?, ?)
            """,
            (
                self.student_id,
                json.dumps(["虫蛀"], ensure_ascii=False),
                "2026-09-15T00:00:00+00:00",
                "2026-09-15T00:00:00+00:00",
            ),
        )
        return int(cursor.lastrowid)

    def test_grading_requires_owned_self_test(self):
        self_test = self._generate_self_test()
        self.ai.complete_json.reset_mock()

        with self.app.app_context():
            with self.assertRaises(AgriNotFoundError):
                submit_self_test(
                    self.other_student_id,
                    self_test["id"],
                    {"q1": "清理落果"},
                )

        self.ai.complete_json.assert_not_called()
        self.assertEqual(self.count_rows("agri_self_test_attempts"), 0)

    def test_invalid_grading_output_publishes_no_attempt(self):
        self_test = self._generate_self_test()
        self.ai.complete_json.return_value = {
            "score": 101,
            "questions": [
                {"correct": True, "explanation": "清理落果可减少虫源。"},
                {"correct": False, "explanation": "必须按登记说明用药。"},
                {"correct": True},
            ],
        }

        with self.app.app_context():
            with self.assertRaisesRegex(
                AiUnavailableError,
                "AI 服务暂时不可用",
            ):
                submit_self_test(
                    self.student_id,
                    self_test["id"],
                    {"q1": "清理落果", "q2": "错误", "q3": "落果和虫孔"},
                )

        self.assertEqual(self.count_rows("agri_self_test_attempts"), 0)

    def test_learning_outcomes_read_contract(self):
        self_test = self._generate_self_test()
        self.ai.complete_json.side_effect = [
            {
                "score": 67,
                "questions": [
                    {"correct": True, "explanation": "清理落果可减少虫源。"},
                    {"correct": False, "explanation": "必须按登记说明用药。"},
                    {"correct": True, "explanation": "雨后重点检查落果和虫孔。"},
                ],
            },
            {
                "score": 100,
                "questions": [
                    {"correct": True, "explanation": "清理落果可减少虫源。"},
                    {"correct": True, "explanation": "必须按登记说明用药。"},
                    {"correct": True, "explanation": "雨后重点检查落果和虫孔。"},
                ],
            },
        ]

        with self.app.app_context():
            first = submit_self_test(
                self.student_id,
                self_test["id"],
                {"q1": "清理落果", "q2": "错误", "q3": "落果和虫孔"},
            )
            second = submit_self_test(
                self.student_id,
                self_test["id"],
                {"q1": "清理落果", "q2": "正确", "q3": "落果和虫孔"},
            )
            outcomes = list_learning_outcomes(self.student_id)
            self_test_outcomes = list_learning_outcomes(
                self.student_id,
                kind="diagnostic_self_test",
            )
            other_outcomes = list_learning_outcomes(self.other_student_id)

        self.assertEqual(len(outcomes), 2)
        self.assertEqual(outcomes, self_test_outcomes)
        self.assertEqual(other_outcomes, [])
        self.assertEqual(
            [outcome["source_id"] for outcome in outcomes],
            [first["attempt_id"], second["attempt_id"]],
        )
        self.assertEqual(
            [outcome["score"] for outcome in outcomes],
            [67, 100],
        )
        for outcome in outcomes:
            self.assertEqual(outcome["kind"], "diagnostic_self_test")
            self.assertEqual(
                outcome["diagnosis_session_id"],
                self.session_id,
            )
            self.assertIsNone(outcome["course_id"])
            self.assertFalse(outcome["is_formal"])
            self.assertTrue(outcome["created_at"])

    def test_learning_outcomes_rejects_unknown_kind(self):
        with self.app.app_context():
            with self.assertRaisesRegex(ValueError, "Unsupported"):
                list_learning_outcomes(self.student_id, kind="unknown")
            self.assertEqual(
                list_learning_outcomes(self.student_id, kind="course_quiz"),
                [],
            )


if __name__ == "__main__":
    unittest.main()
