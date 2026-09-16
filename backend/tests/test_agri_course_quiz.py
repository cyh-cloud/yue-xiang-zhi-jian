import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from app import create_app
from app.agri_skills.ai_client import set_ai_client
from app.agri_skills.course_learning import (
    get_course_quiz,
    submit_course_quiz,
    update_course_progress,
)
from app.agri_skills.errors import (
    AgriNotFoundError,
    AgriValidationError,
    AiUnavailableError,
)
from app.agri_skills.outcomes import list_learning_outcomes
from app.agri_skills.providers import set_course_provider
from app.db import get_db


class FakeCourseProvider:
    def __init__(self, course: dict, quiz: dict | None) -> None:
        self.course = dict(course)
        self.quiz = quiz

    def list_published_agriculture_courses(self, student_id: int) -> list[dict]:
        return [dict(self.course)]

    def get_course(self, course_id: int) -> dict | None:
        if course_id != self.course["id"]:
            return None
        return dict(self.course)

    def get_quiz(self, course_id: int) -> dict | None:
        if course_id != self.course["id"]:
            return None
        return self.quiz


class TestAgriCourseQuiz(unittest.TestCase):
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
            cursor = db.execute(
                """
                INSERT INTO users (
                    username, password_hash, name, role, is_enabled,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, 'student', 1, ?, ?)
                """,
                (
                    "student01",
                    "test-password-hash",
                    "林晓",
                    "2026-09-15T00:00:00+00:00",
                    "2026-09-15T00:00:00+00:00",
                ),
            )
            self.student_id = int(cursor.lastrowid)
            cursor = db.execute(
                """
                INSERT INTO users (
                    username, password_hash, name, role, is_enabled,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, 'student', 1, ?, ?)
                """,
                (
                    "student02",
                    "test-password-hash",
                    "陈禾",
                    "2026-09-15T00:00:00+00:00",
                    "2026-09-15T00:00:00+00:00",
                ),
            )
            self.other_student_id = int(cursor.lastrowid)
            now = "2026-09-15T00:00:00+00:00"
            db.execute(
                """
                INSERT INTO courses (
                    id, title, direction, status, duration_seconds,
                    published_at, summary,
                    teacher_name, created_at, updated_at
                )
                VALUES (
                    1, '荔枝保果', 'agriculture', 'published', 300,
                    ?, ?, '林老师', ?, ?
                )
                """,
                (
                    "2026-09-01T00:00:00+00:00",
                    "荔枝保果课程",
                    now,
                    now,
                ),
            )
            db.commit()

        self.course_fixture = {
            "id": 1,
            "title": "荔枝保果",
            "direction": "agriculture",
            "summary": "荔枝保果课程",
            "teacher_name": "林老师",
            "published_at": "2026-09-01T00:00:00+00:00",
            "tag_ids": [],
            "duration_seconds": 100,
        }
        self.questions = [
            {
                "id": "q1",
                "type": "single_choice",
                "prompt": "达到多少进度视为完成？",
                "options": ["A", "B"],
                "answer": "A",
            }
        ]
        self.provider = FakeCourseProvider(
            self.course_fixture,
            {"questions": self.questions},
        )
        set_course_provider(self.app, self.provider)
        self.ai = Mock()
        set_ai_client(self.app, self.ai)

    def tearDown(self):
        self.temp_dir.cleanup()

    def complete_course(self, course_id: int) -> None:
        with self.app.app_context():
            update_course_progress(self.student_id, course_id, 80, 80)

    def formal_attempt(self, attempt_id: int) -> bool:
        with self.app.app_context():
            row = get_db().execute(
                """
                SELECT is_formal
                FROM agri_course_quiz_attempts
                WHERE id = ?
                """,
                (attempt_id,),
            ).fetchone()
        return bool(row["is_formal"])

    def get_formal_attempt(self, user_id: int, course_id: int) -> dict:
        with self.app.app_context():
            row = get_db().execute(
                """
                SELECT *
                FROM agri_course_quiz_attempts
                WHERE user_id = ? AND course_id = ? AND is_formal = 1
                """,
                (user_id, course_id),
            ).fetchone()
        return dict(row)

    def count_attempts(self) -> int:
        with self.app.app_context():
            row = get_db().execute(
                "SELECT COUNT(*) AS count FROM agri_course_quiz_attempts"
            ).fetchone()
        return int(row["count"])

    def test_quiz_hidden_until_course_completed(self):
        with self.app.app_context():
            self.assertIsNone(get_course_quiz(self.student_id, 1))

        self.complete_course(1)

        with self.app.app_context():
            quiz = get_course_quiz(self.student_id, 1)
        self.assertEqual(
            quiz,
            {
                "course_id": 1,
                "questions": [
                    {
                        "id": "q1",
                        "type": "single_choice",
                        "prompt": "达到多少进度视为完成？",
                        "options": ["A", "B"],
                    }
                ],
            },
        )

    def test_empty_quiz_is_unavailable_after_completion(self):
        self.complete_course(1)
        self.provider.quiz = {"questions": []}

        with self.app.app_context():
            self.assertIsNone(get_course_quiz(self.student_id, 1))

    def test_latest_valid_attempt_replaces_formal_result(self):
        self.complete_course(1)
        self.ai.complete_json.side_effect = [
            {
                "score": 100,
                "questions": [
                    {
                        "id": "q1",
                        "correct": True,
                        "explanation": "正确。",
                    }
                ],
            },
            {
                "score": 0,
                "questions": [
                    {
                        "id": "q1",
                        "correct": False,
                        "explanation": "应为 A。",
                    }
                ],
            },
        ]

        with self.app.app_context():
            first = submit_course_quiz(self.student_id, 1, {"q1": "A"})
            second = submit_course_quiz(self.student_id, 1, {"q1": "B"})
            outcomes = list_learning_outcomes(
                self.student_id,
                kind="course_quiz",
            )

        self.assertEqual(first["score"], 100)
        self.assertEqual(second["score"], 0)
        self.assertFalse(self.formal_attempt(first["id"]))
        self.assertTrue(self.formal_attempt(second["id"]))
        self.assertEqual(self.count_attempts(), 2)
        self.assertEqual(
            [outcome["source_id"] for outcome in outcomes],
            [first["id"], second["id"]],
        )
        formal_outcomes = [
            outcome for outcome in outcomes if outcome["is_formal"]
        ]
        self.assertEqual(len(formal_outcomes), 1)
        self.assertEqual(formal_outcomes[0]["score"], 0)
        self.assertEqual(formal_outcomes[0]["course_id"], 1)
        self.assertIsNone(formal_outcomes[0]["diagnosis_session_id"])

        call = self.ai.complete_json.call_args_list[0]
        self.assertEqual(call.kwargs["call_point"], "course_quiz_grade")
        context = json.loads(call.args[0][1]["content"])
        self.assertEqual(
            context,
            {
                "course_summary": "荔枝保果课程",
                "questions": self.questions,
                "answers": {"q1": "A"},
            },
        )

    def test_ai_failure_preserves_previous_formal_attempt(self):
        self.complete_course(1)
        self.ai.complete_json.return_value = {
            "score": 100,
            "questions": [
                {
                    "id": "q1",
                    "correct": True,
                    "explanation": "正确。",
                }
            ],
        }
        with self.app.app_context():
            first = submit_course_quiz(self.student_id, 1, {"q1": "A"})

        self.ai.complete_json.side_effect = AiUnavailableError(
            "raw upstream failure"
        )
        with self.app.app_context():
            with self.assertRaisesRegex(
                AiUnavailableError,
                "AI 服务暂时不可用",
            ):
                submit_course_quiz(self.student_id, 1, {"q1": "B"})

        self.assertEqual(self.count_attempts(), 1)
        formal = self.get_formal_attempt(self.student_id, 1)
        self.assertEqual(formal["id"], first["id"])
        self.assertEqual(formal["score"], 100)

    def test_invalid_ai_result_preserves_previous_formal_attempt(self):
        self.complete_course(1)
        self.ai.complete_json.return_value = {
            "score": 100,
            "questions": [
                {
                    "id": "q1",
                    "correct": True,
                    "explanation": "正确。",
                }
            ],
        }
        with self.app.app_context():
            first = submit_course_quiz(self.student_id, 1, {"q1": "A"})

        self.ai.complete_json.return_value = {
            "score": 101,
            "questions": [
                {
                    "id": "q1",
                    "correct": False,
                    "explanation": "无效。",
                }
            ],
        }
        with self.app.app_context():
            with self.assertRaisesRegex(
                AiUnavailableError,
                "AI 服务暂时不可用",
            ):
                submit_course_quiz(self.student_id, 1, {"q1": "B"})

        self.assertEqual(self.count_attempts(), 1)
        formal = self.get_formal_attempt(self.student_id, 1)
        self.assertEqual(formal["id"], first["id"])
        self.assertEqual(formal["score"], 100)

    def test_invalid_answers_preserve_previous_formal_attempt(self):
        self.complete_course(1)
        self.ai.complete_json.return_value = {
            "score": 100,
            "questions": [
                {
                    "id": "q1",
                    "correct": True,
                    "explanation": "正确。",
                }
            ],
        }
        with self.app.app_context():
            first = submit_course_quiz(self.student_id, 1, {"q1": "A"})
            self.ai.complete_json.reset_mock()

            with self.assertRaises(AgriValidationError):
                submit_course_quiz(self.student_id, 1, {})

        self.ai.complete_json.assert_not_called()
        self.assertEqual(self.count_attempts(), 1)
        formal = self.get_formal_attempt(self.student_id, 1)
        self.assertEqual(formal["id"], first["id"])
        self.assertEqual(formal["score"], 100)

    def test_submission_requires_owned_completed_progress(self):
        with self.app.app_context():
            with self.assertRaises(AgriNotFoundError):
                submit_course_quiz(self.other_student_id, 1, {"q1": "A"})

        self.ai.complete_json.assert_not_called()
        self.assertEqual(self.count_attempts(), 0)


if __name__ == "__main__":
    unittest.main()
