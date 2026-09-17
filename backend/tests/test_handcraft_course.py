import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from app import create_app
from app.agri_skills.ai_client import set_ai_client
from app.agri_skills.errors import (
    AgriNotFoundError,
    AgriValidationError,
    AiUnavailableError,
)
from app.agri_skills.providers import set_course_provider
from app.db import get_db
from app.handcraft_inheritance.course_learning import (
    list_handcraft_course_quiz_attempts,
    list_handcraft_courses,
    list_handcraft_learning_outcomes,
    list_handcraft_recommendations,
    submit_handcraft_course_quiz,
    update_handcraft_course_progress,
)


class DirectionAwareCourseProvider:
    def __init__(self) -> None:
        self.courses = [
            {
                "id": 201,
                "title": "广绣基础",
                "direction": "handcraft",
                "status": "published",
                "summary": "广绣针法与配色基础",
                "teacher_name": "梁老师",
                "published_at": "2026-09-01T00:00:00+00:00",
                "duration_seconds": 100,
                "tag_ids": [101, 102],
            },
            {
                "id": 202,
                "title": "潮汕木雕进阶",
                "direction": "handcraft",
                "status": "published",
                "summary": "潮汕木雕层次训练",
                "teacher_name": "陈老师",
                "published_at": "2026-09-01T00:00:00+00:00",
                "duration_seconds": 150,
                "tag_ids": [101, 102],
            },
            {
                "id": 203,
                "title": "石湾陶艺入门",
                "direction": "handcraft",
                "status": "published",
                "summary": "石湾陶艺塑形基础",
                "teacher_name": "何老师",
                "published_at": "2026-09-01T00:00:00+00:00",
                "duration_seconds": 100,
                "tag_ids": [101, 102],
            },
            {
                "id": 204,
                "title": "阳江漆器装饰",
                "direction": "handcraft",
                "status": "published",
                "summary": "阳江漆器描金彩绘",
                "teacher_name": "周老师",
                "published_at": "2026-09-05T00:00:00+00:00",
                "duration_seconds": 100,
                "tag_ids": [101, 102],
            },
            {
                "id": 205,
                "title": "传统竹编",
                "direction": "handcraft",
                "status": "published",
                "summary": "竹编基础",
                "teacher_name": "黄老师",
                "published_at": "2026-09-03T00:00:00+00:00",
                "duration_seconds": 100,
                "tag_ids": [101],
            },
            {
                "id": 206,
                "title": "传统竹编（同日）",
                "direction": "handcraft",
                "status": "published",
                "summary": "竹编基础",
                "teacher_name": "黄老师",
                "published_at": "2026-09-03T00:00:00+00:00",
                "duration_seconds": 100,
                "tag_ids": [101],
            },
            {
                "id": 207,
                "title": "待审核手工课程",
                "direction": "handcraft",
                "status": "pending",
                "summary": "待审核课程",
                "teacher_name": "黄老师",
                "published_at": None,
                "duration_seconds": 100,
                "tag_ids": [101],
            },
            {
                "id": 208,
                "title": "无标签手工课程",
                "direction": "handcraft",
                "status": "published",
                "summary": "无标签课程",
                "teacher_name": "黄老师",
                "published_at": "2026-09-03T00:00:00+00:00",
                "duration_seconds": 100,
                "tag_ids": [],
            },
            {
                "id": 209,
                "title": "无效时长手工课程",
                "direction": "handcraft",
                "status": "published",
                "summary": "无效时长课程",
                "teacher_name": "黄老师",
                "published_at": "2026-09-03T00:00:00+00:00",
                "duration_seconds": None,
                "tag_ids": [101],
            },
            {
                "id": 210,
                "title": "农业对照课程",
                "direction": "agriculture",
                "status": "published",
                "summary": "农业对照课程",
                "teacher_name": "林老师",
                "published_at": "2026-09-03T00:00:00+00:00",
                "duration_seconds": 100,
                "tag_ids": [101],
            },
        ]
        self.questions = [
            {
                "id": "q1",
                "type": "single_choice",
                "prompt": "手工课程测验题",
                "options": ["A", "B"],
                "answer": "A",
            }
        ]
        self.quiz_by_course = {
            201: {
                "enabled": True,
                "scoring_rule": "每题按 AI 判分",
                "questions": [dict(self.questions[0])],
            }
        }

    def list_published_courses(
        self,
        student_id: int,
        direction: str,
    ) -> list[dict]:
        return [
            dict(course)
            for course in self.courses
            if course["direction"] == direction
        ]

    def get_course(self, course_id: int) -> dict | None:
        return next(
            (
                dict(course)
                for course in self.courses
                if course["id"] == course_id
            ),
            None,
        )

    def get_quiz(self, course_id: int) -> dict | None:
        quiz = self.quiz_by_course.get(course_id)
        if quiz is None:
            return None
        return {
            **quiz,
            "questions": [
                dict(question)
                for question in quiz.get("questions", [])
            ],
        }


class TestHandcraftCourseLearning(unittest.TestCase):
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
            self.student_id = self._insert_student(db, "student01")
            self.other_student_id = self._insert_student(db, "student02")
            db.executemany(
                """
                INSERT INTO interest_tags (
                    id, group_key, name, sort_order, is_active
                )
                VALUES (?, 'skill', ?, ?, 1)
                """,
                (
                    (101, "手工技艺", 101),
                    (102, "造型设计", 102),
                ),
            )
            db.executemany(
                """
                INSERT INTO student_interest_tags (user_id, tag_id)
                VALUES (?, ?)
                """,
                (
                    (self.student_id, 101),
                    (self.student_id, 102),
                ),
            )
            now = "2026-09-17T00:00:00+00:00"
            db.executemany(
                """
                INSERT INTO courses (
                    id, title, direction, status, duration_seconds,
                    published_at, summary, teacher_name, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    (
                        course_id,
                        f"课程 {course_id}",
                        "handcraft",
                        "published",
                        100,
                        now,
                        f"课程简介 {course_id}",
                        "占位教师",
                        now,
                        now,
                    )
                    for course_id in range(201, 210)
                ),
            )
            db.commit()

        self.provider = DirectionAwareCourseProvider()
        set_course_provider(self.app, self.provider)
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
                "2026-09-17T00:00:00+00:00",
                "2026-09-17T00:00:00+00:00",
            ),
        )
        return int(cursor.lastrowid)

    @staticmethod
    def _valid_grade(score: int = 90, correct: bool = True) -> dict:
        return {
            "score": score,
            "questions": [
                {
                    "id": "q1",
                    "correct": correct,
                    "explanation": "正确" if correct else "应选择 A",
                }
            ],
        }

    def _set_progress_time(
        self,
        user_id: int,
        course_id: int,
        viewed_at: str,
    ) -> None:
        with self.app.app_context():
            db = get_db()
            db.execute(
                """
                UPDATE agri_course_progress
                SET last_viewed_at = ?, updated_at = ?
                WHERE user_id = ? AND course_id = ?
                """,
                (viewed_at, viewed_at, user_id, course_id),
            )
            db.commit()

    def test_catalog_only_contains_eligible_published_handcraft_courses(self):
        with self.app.app_context():
            courses = list_handcraft_courses(self.student_id)

        self.assertEqual(
            [course["id"] for course in courses],
            [201, 202, 203, 204, 205, 206, 208],
        )
        self.assertTrue(
            all(
                (
                    course["direction"],
                    course["status"],
                    isinstance(course["id"], int),
                    isinstance(course["duration_seconds"], int),
                    isinstance(course["tag_ids"], list),
                )
                == ("handcraft", "published", True, True, True)
                for course in courses
            )
        )
        self.assertEqual(courses[0]["tag_ids"], [101, 102])
        self.assertEqual(courses[0]["duration_seconds"], 100)

    def test_recommendation_order_matches_shared_direction_rule(self):
        with self.app.app_context():
            for course_id, position, watched in (
                (201, 20, 20),
                (202, 60, 60),
                (203, 70, 70),
            ):
                update_handcraft_course_progress(
                    self.student_id,
                    course_id,
                    position,
                    watched,
                )

        self._set_progress_time(
            self.student_id,
            201,
            "2026-09-17T10:00:00+00:00",
        )
        self._set_progress_time(
            self.student_id,
            202,
            "2026-09-17T10:00:00+00:00",
        )
        self._set_progress_time(
            self.student_id,
            203,
            "2026-09-17T09:00:00+00:00",
        )

        with self.app.app_context():
            recommendations = list_handcraft_recommendations(
                self.student_id
            )

        self.assertEqual(
            [course["id"] for course in recommendations],
            [202, 201, 203, 204, 205, 206, 208],
        )

    def test_progress_uses_floor_formula_and_80_percent_completion(self):
        with self.app.app_context():
            below = update_handcraft_course_progress(
                self.student_id,
                202,
                119,
                119,
            )
            complete = update_handcraft_course_progress(
                self.student_id,
                202,
                120,
                1,
            )

        self.assertEqual(below["progress_percent"], 79)
        self.assertIsNone(below["completed_at"])
        self.assertEqual(complete["progress_percent"], 80)
        self.assertIsNotNone(complete["completed_at"])

    def test_lower_duplicate_and_out_of_order_do_not_regress(self):
        with self.app.app_context():
            first = update_handcraft_course_progress(
                self.student_id,
                201,
                80,
                80,
            )
            lower = update_handcraft_course_progress(
                self.student_id,
                201,
                40,
                0,
            )
            duplicate = update_handcraft_course_progress(
                self.student_id,
                201,
                80,
                30,
            )
            out_of_order = update_handcraft_course_progress(
                self.student_id,
                201,
                50,
                20,
            )

        self.assertEqual(lower["furthest_position_seconds"], 80)
        self.assertEqual(lower["resume_position_seconds"], 40)
        self.assertEqual(lower["progress_percent"], 80)
        self.assertEqual(lower["watched_seconds"], 80)
        self.assertEqual(lower["completed_at"], first["completed_at"])

        self.assertEqual(duplicate["furthest_position_seconds"], 80)
        self.assertEqual(duplicate["watched_seconds"], 80)
        self.assertEqual(duplicate["completed_at"], first["completed_at"])

        self.assertEqual(out_of_order["furthest_position_seconds"], 80)
        self.assertEqual(out_of_order["resume_position_seconds"], 50)
        self.assertEqual(out_of_order["progress_percent"], 80)
        self.assertEqual(out_of_order["watched_seconds"], 80)
        self.assertEqual(out_of_order["completed_at"], first["completed_at"])

    def test_invalid_progress_is_rejected_without_mutation(self):
        with self.app.app_context():
            update_handcraft_course_progress(
                self.student_id,
                201,
                60,
                30,
            )
            before = get_db().execute(
                """
                SELECT *
                FROM agri_course_progress
                WHERE user_id = ? AND course_id = ?
                """,
                (self.student_id, 201),
            ).fetchone()

            invalid_cases = (
                (-1, 0),
                (101, 0),
                (50, -1),
                (True, 0),
                (50, True),
            )
            for position, watched_delta in invalid_cases:
                with self.subTest(
                    position=position,
                    watched_delta=watched_delta,
                ):
                    with self.assertRaises(AgriValidationError):
                        update_handcraft_course_progress(
                            self.student_id,
                            201,
                            position,
                            watched_delta,
                        )

            after = get_db().execute(
                """
                SELECT *
                FROM agri_course_progress
                WHERE user_id = ? AND course_id = ?
                """,
                (self.student_id, 201),
            ).fetchone()

        self.assertEqual(dict(after), dict(before))

    def test_quiz_requires_completion_and_valid_enabled_provider_config(self):
        invalid_quizzes = (
            None,
            {
                "questions": [dict(self.provider.questions[0])],
                "scoring_rule": "规则",
            },
            {
                "enabled": False,
                "questions": [dict(self.provider.questions[0])],
                "scoring_rule": "规则",
            },
            {
                "enabled": True,
                "questions": [dict(self.provider.questions[0])],
                "scoring_rule": "",
            },
            {
                "enabled": True,
                "questions": [],
                "scoring_rule": "规则",
            },
        )

        with self.app.app_context():
            with self.assertRaises(AgriNotFoundError):
                submit_handcraft_course_quiz(
                    self.student_id,
                    201,
                    {"q1": "A"},
                )

            self.ai.complete_json.assert_not_called()
            update_handcraft_course_progress(
                self.student_id,
                201,
                80,
                80,
            )

            for quiz in invalid_quizzes:
                with self.subTest(quiz=quiz):
                    self.provider.quiz_by_course[201] = quiz
                    progress = update_handcraft_course_progress(
                        self.student_id,
                        201,
                        80,
                        0,
                    )
                    self.assertFalse(progress["quiz_available"])

            self.provider.quiz_by_course[201] = {
                "enabled": True,
                "scoring_rule": "每题按 AI 判分",
                "questions": [dict(self.provider.questions[0])],
            }
            progress = update_handcraft_course_progress(
                self.student_id,
                201,
                80,
                0,
            )

        self.assertTrue(progress["quiz_available"])

    def test_ai_failure_preserves_progress_formal_score_and_answers(self):
        with self.app.app_context():
            update_handcraft_course_progress(
                self.student_id,
                201,
                80,
                80,
            )
            self.ai.complete_json.return_value = self._valid_grade()
            first = submit_handcraft_course_quiz(
                self.student_id,
                201,
                {"q1": "A"},
            )

            self.ai.complete_json.side_effect = AiUnavailableError(
                "raw provider error"
            )
            with self.assertRaisesRegex(
                AiUnavailableError,
                "^AI 服务暂时不可用$",
            ):
                submit_handcraft_course_quiz(
                    self.student_id,
                    201,
                    {"q1": "B"},
                )

            rows = get_db().execute(
                """
                SELECT *
                FROM agri_course_quiz_attempts
                WHERE user_id = ? AND course_id = ?
                ORDER BY id
                """,
                (self.student_id, 201),
            ).fetchall()
            progress = update_handcraft_course_progress(
                self.student_id,
                201,
                80,
                0,
            )

        self.assertEqual(len(rows), 1)
        self.assertEqual(int(rows[0]["id"]), first["id"])
        self.assertEqual(int(rows[0]["score"]), 90)
        self.assertEqual(int(rows[0]["is_formal"]), 1)
        self.assertEqual(
            json.loads(rows[0]["answers_json"]),
            {"q1": "A"},
        )
        self.assertEqual(progress["progress_percent"], 80)
        self.assertIsNotNone(progress["completed_at"])

    def test_quiz_history_keeps_all_attempts_and_latest_formal(self):
        with self.app.app_context():
            update_handcraft_course_progress(
                self.student_id,
                201,
                80,
                80,
            )
            self.ai.complete_json.side_effect = [
                self._valid_grade(90, True),
                self._valid_grade(20, False),
            ]
            first = submit_handcraft_course_quiz(
                self.student_id,
                201,
                {"q1": "A"},
            )
            second = submit_handcraft_course_quiz(
                self.student_id,
                201,
                {"q1": "B"},
            )
            attempts = list_handcraft_course_quiz_attempts(
                self.student_id,
                201,
            )
            other_attempts = list_handcraft_course_quiz_attempts(
                self.other_student_id,
                201,
            )

        self.assertEqual(
            [attempt["id"] for attempt in attempts],
            [second["id"], first["id"]],
        )
        self.assertEqual(
            [
                (
                    attempt["is_formal"],
                    attempt["is_current"],
                    attempt["is_latest"],
                )
                for attempt in attempts
            ],
            [
                (True, True, True),
                (False, False, False),
            ],
        )
        self.assertEqual(other_attempts, [])

    def test_outcomes_use_fr_093_handoff_shape_without_archive_write(self):
        with self.app.app_context():
            update_handcraft_course_progress(
                self.student_id,
                202,
                40,
                40,
            )
            update_handcraft_course_progress(
                self.student_id,
                201,
                80,
                80,
            )
            self.ai.complete_json.side_effect = [
                self._valid_grade(90, True),
                self._valid_grade(20, False),
            ]
            first = submit_handcraft_course_quiz(
                self.student_id,
                201,
                {"q1": "A"},
            )
            second = submit_handcraft_course_quiz(
                self.student_id,
                201,
                {"q1": "B"},
            )
            outcomes = list_handcraft_learning_outcomes(self.student_id)
            other_outcomes = list_handcraft_learning_outcomes(
                self.other_student_id
            )

        self.assertEqual(
            {outcome["outcome_type"] for outcome in outcomes},
            {"course_view", "course_completion", "course_quiz"},
        )
        self.assertEqual(
            [
                outcome["source_id"]
                for outcome in outcomes
                if outcome["outcome_type"] == "course_quiz"
            ],
            [first["id"], second["id"]],
        )
        self.assertEqual(other_outcomes, [])
        required_fields = {
            "outcome_type",
            "source_id",
            "created_at",
            "source_available",
            "summary",
            "score",
            "is_formal",
            "archive_written",
        }
        for outcome in outcomes:
            with self.subTest(outcome=outcome):
                self.assertEqual(set(outcome), required_fields)
                self.assertIsInstance(outcome["source_id"], int)
                self.assertTrue(outcome["source_available"])
                self.assertFalse(outcome["archive_written"])


if __name__ == "__main__":
    unittest.main()
