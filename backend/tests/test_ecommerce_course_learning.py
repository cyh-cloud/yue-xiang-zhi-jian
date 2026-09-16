import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from app import create_app
from app.agri_skills.ai_client import set_ai_client
from app.agri_skills.errors import AgriNotFoundError, AiUnavailableError
from app.agri_skills.providers import set_course_provider
from app.db import get_db
from app.ecommerce_training.course_learning import (
    get_ecommerce_course_progress,
    get_ecommerce_course_quiz,
    list_ecommerce_courses,
    list_ecommerce_learning_outcomes,
    list_ecommerce_recommendations,
    submit_ecommerce_course_quiz,
    update_ecommerce_course_progress,
)


class DirectionAwareCourseProvider:
    def __init__(self) -> None:
        self.courses = [
            {
                "id": 1002,
                "title": "电商产品讲解与促单（占位）",
                "direction": "ecommerce",
                "status": "published",
                "summary": "电商产品讲解与促单课程",
                "teacher_name": "占位教师",
                "published_at": "2026-09-16T00:00:00+00:00",
                "duration_seconds": 100,
                "tag_ids": [],
            },
            {
                "id": 1001,
                "title": "电商直播开场实战（占位）",
                "direction": "ecommerce",
                "status": "published",
                "summary": "电商直播开场课程",
                "teacher_name": "占位教师",
                "published_at": "2026-09-16T00:00:00+00:00",
                "duration_seconds": 100,
                "tag_ids": [],
            },
            {
                "id": 1003,
                "title": "待审核电商课程（占位）",
                "direction": "ecommerce",
                "status": "pending",
                "summary": "待审核课程",
                "teacher_name": "占位教师",
                "published_at": None,
                "duration_seconds": 100,
                "tag_ids": [],
            },
            {
                "id": 1004,
                "title": "农业对照课程（占位）",
                "direction": "agriculture",
                "status": "published",
                "summary": "农业对照课程",
                "teacher_name": "占位教师",
                "published_at": "2026-09-16T00:00:00+00:00",
                "duration_seconds": 100,
                "tag_ids": [],
            },
            {
                "id": 1005,
                "title": "无效时长电商课程（占位）",
                "direction": "ecommerce",
                "status": "published",
                "summary": "无效时长课程",
                "teacher_name": "占位教师",
                "published_at": "2026-09-16T00:00:00+00:00",
                "duration_seconds": None,
                "tag_ids": [],
            },
        ]
        self.questions = [
            {
                "id": "q1",
                "type": "single_choice",
                "prompt": "电商课程测验题",
                "options": ["A", "B"],
                "answer": "A",
            }
        ]

    def list_published_courses(
        self,
        student_id: int,
        direction: str,
    ) -> list[dict]:
        return [
            dict(course)
            for course in self.courses
            if course["direction"] == direction
            and course["status"] == "published"
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
        if course_id != 1002:
            return None
        return {
            "enabled": True,
            "questions": [dict(question) for question in self.questions],
            "scoring_rule": "每题按 AI 判分",
        }


class TestEcommerceCourseLearning(unittest.TestCase):
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
    def _valid_grade() -> dict:
        return {
            "score": 90,
            "questions": [
                {
                    "id": "q1",
                    "correct": True,
                    "explanation": "正确",
                }
            ],
        }

    def _insert_outcome_sources(self, user_id: int) -> None:
        with self.app.app_context():
            db = get_db()
            db.execute(
                """
                INSERT INTO ecommerce_live_script_versions (
                    user_id, product_name, selling_points_json, price_text,
                    style, script_json, is_current, created_at
                )
                VALUES (?, ?, ?, '', 'enthusiastic', ?, 1, ?)
                """,
                (
                    user_id,
                    "荔枝干",
                    json.dumps(["香甜"], ensure_ascii=False),
                    json.dumps(
                        {
                            "opening": "开场",
                            "product_intro": "介绍",
                            "interaction": "互动",
                            "closing": "促单",
                        },
                        ensure_ascii=False,
                    ),
                    "2026-09-17T01:00:00+00:00",
                ),
            )
            db.execute(
                """
                INSERT INTO ecommerce_simulation_trainings (
                    user_id, scene_key, segments_json, status, scores_json,
                    total_score, created_at, updated_at, completed_at
                )
                VALUES (
                    ?, 'opening', '[]', 'completed', '{}', 80, ?, ?, ?
                )
                """,
                (
                    user_id,
                    "2026-09-17T02:00:00+00:00",
                    "2026-09-17T02:10:00+00:00",
                    "2026-09-17T02:10:00+00:00",
                ),
            )
            db.execute(
                """
                INSERT INTO ecommerce_simulation_trainings (
                    user_id, scene_key, segments_json, status, scores_json,
                    total_score, created_at, updated_at, completed_at
                )
                VALUES (?, 'opening', '[]', 'draft', NULL, NULL, ?, ?, NULL)
                """,
                (
                    user_id,
                    "2026-09-17T03:00:00+00:00",
                    "2026-09-17T03:00:00+00:00",
                ),
            )
            db.commit()

    def test_direction_wrappers_and_outcome_projection(self):
        self._insert_outcome_sources(self.student_id)

        with self.app.app_context():
            courses = list_ecommerce_courses(self.student_id)
            self.assertEqual(
                [course["id"] for course in courses],
                [1002, 1001],
            )
            self.assertTrue(
                all(
                    course["direction"] == "ecommerce"
                    for course in courses
                )
            )
            self.assertTrue(
                {1003, 1004, 1005}.isdisjoint(
                    {course["id"] for course in courses}
                )
            )

            progress = update_ecommerce_course_progress(
                self.student_id,
                1001,
                80,
                80,
            )
            self.assertEqual(progress["progress_percent"], 80)
            self.assertIsNotNone(progress["completed_at"])

            recommendations = list_ecommerce_recommendations(
                self.student_id
            )
            self.assertNotIn(
                1001,
                [course["id"] for course in recommendations],
            )

            update_ecommerce_course_progress(
                self.student_id,
                1002,
                80,
                80,
            )
            quiz = get_ecommerce_course_quiz(self.student_id, 1002)
            self.assertEqual(quiz["course_id"], 1002)
            self.assertEqual(
                quiz["questions"],
                [
                    {
                        "id": "q1",
                        "type": "single_choice",
                        "prompt": "电商课程测验题",
                        "options": ["A", "B"],
                    }
                ],
            )

            self.ai.complete_json.return_value = self._valid_grade()
            attempt = submit_ecommerce_course_quiz(
                self.student_id,
                1002,
                {"q1": "A"},
            )
            self.assertTrue(attempt["is_formal"])

            outcomes = list_ecommerce_learning_outcomes(self.student_id)

        self.assertEqual(
            {outcome["kind"] for outcome in outcomes},
            {
                "live_script",
                "simulation_training",
                "course_quiz",
                "course_completion",
            },
        )
        self.assertTrue(
            all(
                outcome["archive_written"] is False
                for outcome in outcomes
            )
        )
        self.assertTrue(
            all(
                set(outcome)
                == {
                    "kind",
                    "source_id",
                    "created_at",
                    "summary",
                    "score",
                    "is_formal",
                    "archive_written",
                }
                for outcome in outcomes
            )
        )
        self.assertEqual(
            [outcome["kind"] for outcome in outcomes].count(
                "simulation_training"
            ),
            1,
        )
        self.assertEqual(
            [
                outcome["is_formal"]
                for outcome in outcomes
                if outcome["kind"] == "course_quiz"
            ],
            [True],
        )

    def test_only_shared_course_provider_registry_is_used(self):
        provider_keys = {
            key
            for key in self.app.extensions
            if "course_provider" in key
        }
        self.assertEqual(provider_keys, {"agri_course_provider"})

    def test_quiz_requires_owned_completed_course(self):
        with self.app.app_context():
            self.assertIsNone(
                get_ecommerce_course_quiz(self.student_id, 1002)
            )
            with self.assertRaises(AgriNotFoundError):
                submit_ecommerce_course_quiz(
                    self.student_id,
                    1002,
                    {"q1": "A"},
                )

        self.ai.complete_json.assert_not_called()

    def test_ai_failure_is_exact_and_preserves_formal_score_and_answers(self):
        with self.app.app_context():
            update_ecommerce_course_progress(
                self.student_id,
                1002,
                80,
                80,
            )
            self.ai.complete_json.return_value = self._valid_grade()
            first = submit_ecommerce_course_quiz(
                self.student_id,
                1002,
                {"q1": "A"},
            )

            self.ai.complete_json.side_effect = AiUnavailableError(
                "raw provider error"
            )
            with self.assertRaisesRegex(
                AiUnavailableError,
                "^AI 服务暂时不可用$",
            ):
                submit_ecommerce_course_quiz(
                    self.student_id,
                    1002,
                    {"q1": "B"},
                )

            rows = get_db().execute(
                """
                SELECT *
                FROM agri_course_quiz_attempts
                WHERE user_id = ? AND course_id = ?
                """,
                (self.student_id, 1002),
            ).fetchall()

        self.assertEqual(len(rows), 1)
        self.assertEqual(int(rows[0]["id"]), first["id"])
        self.assertEqual(rows[0]["score"], 90)
        self.assertEqual(rows[0]["is_formal"], 1)
        self.assertEqual(
            json.loads(rows[0]["answers_json"]),
            {"q1": "A"},
        )

    def test_outcomes_are_owner_scoped(self):
        self._insert_outcome_sources(self.student_id)
        self._insert_outcome_sources(self.other_student_id)

        with self.app.app_context():
            outcomes = list_ecommerce_learning_outcomes(self.student_id)
            other_outcomes = list_ecommerce_learning_outcomes(
                self.other_student_id
            )

        self.assertEqual(len(outcomes), 2)
        self.assertEqual(
            {outcome["kind"] for outcome in outcomes},
            {"live_script", "simulation_training"},
        )
        self.assertTrue(
            set(outcome["source_id"] for outcome in outcomes).isdisjoint(
                outcome["source_id"] for outcome in other_outcomes
            )
        )

    def test_course_actions_reject_other_direction(self):
        with self.app.app_context():
            with self.assertRaises(AgriNotFoundError):
                get_ecommerce_course_progress(self.student_id, 1004)


if __name__ == "__main__":
    unittest.main()
