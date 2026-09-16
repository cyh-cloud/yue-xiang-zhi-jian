import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from werkzeug.security import generate_password_hash

from app import create_app
from app.agri_skills.ai_client import set_ai_client
from app.agri_skills.errors import AiUnavailableError
from app.agri_skills.providers import set_course_provider
from app.db import get_db


class FakeCourseProvider:
    def __init__(self, courses: list[dict], quiz: dict | None) -> None:
        self.courses = [dict(course) for course in courses]
        self.quiz = quiz

    def list_published_agriculture_courses(
        self,
        student_id: int,
    ) -> list[dict]:
        return [dict(course) for course in self.courses]

    def get_course(self, course_id: int) -> dict | None:
        course = next(
            (course for course in self.courses if course["id"] == course_id),
            None,
        )
        return dict(course) if course is not None else None

    def get_quiz(self, course_id: int) -> dict | None:
        return self.quiz


class TestAgriCourseApi(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(Path(self.temp_dir.name) / "test.db"),
                "SECRET_KEY": "test-only-secret",
                "SESSION_HOURS": 24,
                "SESSION_COOKIE_SECURE": False,
                "AI_API_URL": "",
                "AI_API_KEY": "",
                "AI_MODEL": "test-model",
            }
        )
        with self.app.app_context():
            db = get_db()
            db.execute("DELETE FROM courses WHERE id BETWEEN 1001 AND 1005")
            db.commit()
        self.student_id = self._create_user("student01", "student")
        self.other_student_id = self._create_user("student02", "student")
        self._create_user("teacher01", "teacher")
        self.client = self._login("student01")
        self.other_client = self._login("student02")
        self.teacher_client = self._login("teacher01")

        now = "2026-09-15T00:00:00+00:00"
        with self.app.app_context():
            db = get_db()
            db.executemany(
                """
                INSERT INTO courses (
                    id, title, direction, status, duration_seconds,
                    published_at, summary,
                    teacher_name, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, 300, ?, ?, ?, ?, ?)
                """,
                (
                    (
                        1,
                        "荔枝保果",
                        "agriculture",
                        "published",
                        "2026-09-01T00:00:00+00:00",
                        "荔枝保果课程",
                        "林老师",
                        now,
                        now,
                    ),
                    (
                        2,
                        "水稻种植",
                        "agriculture",
                        "published",
                        "2026-09-03T00:00:00+00:00",
                        "水稻种植课程",
                        "陈老师",
                        now,
                        now,
                    ),
                    (
                        3,
                        "电商课程",
                        "ecommerce",
                        "published",
                        "2026-09-04T00:00:00+00:00",
                        "",
                        "",
                        now,
                        now,
                    ),
                    (
                        4,
                        "下架农业课程",
                        "agriculture",
                        "offline",
                        "2026-09-05T00:00:00+00:00",
                        "",
                        "",
                        now,
                        now,
                    ),
                ),
            )
            db.execute(
                """
                INSERT INTO student_interest_tags (user_id, tag_id)
                VALUES (?, 1)
                """,
                (self.student_id,),
            )
            db.executemany(
                """
                INSERT INTO course_interest_tags (course_id, tag_id)
                VALUES (?, 1)
                """,
                ((1,), (2,)),
            )
            db.commit()

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
            [
                {
                    "id": 1,
                    "title": "荔枝保果",
                    "direction": "agriculture",
                    "summary": "荔枝保果课程",
                    "teacher_name": "林老师",
                    "published_at": "2026-09-01T00:00:00+00:00",
                    "tag_ids": [1],
                    "duration_seconds": 100,
                },
                {
                    "id": 2,
                    "title": "水稻种植",
                    "direction": "agriculture",
                    "summary": "水稻种植课程",
                    "teacher_name": "陈老师",
                    "published_at": "2026-09-03T00:00:00+00:00",
                    "tag_ids": [1],
                    "duration_seconds": 100,
                },
            ],
            {"questions": self.questions},
        )
        set_course_provider(self.app, self.provider)
        self.ai = Mock()
        set_ai_client(self.app, self.ai)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _create_user(self, username: str, role: str) -> int:
        with self.app.app_context():
            cursor = get_db().execute(
                """
                INSERT INTO users (
                    username, password_hash, name, role, is_enabled,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, 1, ?, ?)
                """,
                (
                    username,
                    generate_password_hash("password8"),
                    username,
                    role,
                    "2026-09-15T00:00:00+00:00",
                    "2026-09-15T00:00:00+00:00",
                ),
            )
            get_db().commit()
        return int(cursor.lastrowid)

    def _login(self, username: str):
        client = self.app.test_client()
        response = client.post(
            "/api/auth/login",
            json={"username": username, "password": "password8"},
        )
        self.assertEqual(response.status_code, 200)
        return client

    def _attempt_rows(self) -> list[dict]:
        with self.app.app_context():
            rows = get_db().execute(
                """
                SELECT *
                FROM agri_course_quiz_attempts
                WHERE user_id = ?
                ORDER BY id
                """,
                (self.student_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def _complete_course(self, course_id: int) -> None:
        response = self.client.put(
            f"/api/agri-skills/courses/{course_id}/progress",
            json={"position_seconds": 80, "watched_delta_seconds": 80},
        )
        self.assertEqual(response.status_code, 200)

    def test_course_list_only_contains_published_agriculture(self):
        response = self.client.get("/api/agri-skills/courses")

        self.assertEqual(response.status_code, 200)
        courses = response.get_json()["courses"]
        self.assertEqual([course["id"] for course in courses], [1, 2])
        self.assertTrue(
            all(item["direction"] == "agriculture" for item in courses)
        )

    def test_progress_returns_80_percent_completion(self):
        response = self.client.put(
            "/api/agri-skills/courses/1/progress",
            json={"position_seconds": 80, "watched_delta_seconds": 20},
        )

        self.assertEqual(response.status_code, 200)
        progress = response.get_json()["progress"]
        self.assertEqual(progress["progress_percent"], 80)
        self.assertIsNotNone(progress["completed_at"])

    def test_latest_quiz_attempt_is_formal(self):
        completed = self.client.put(
            "/api/agri-skills/courses/1/progress",
            json={"position_seconds": 80, "watched_delta_seconds": 80},
        )
        self.assertEqual(completed.status_code, 200)
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

        first = self.client.post(
            "/api/agri-skills/courses/1/quiz",
            json={"answers": {"q1": "A"}},
        )
        second = self.client.post(
            "/api/agri-skills/courses/1/quiz",
            json={"answers": {"q1": "B"}},
        )

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)
        self.assertTrue(first.get_json()["attempt"]["is_formal"])
        self.assertTrue(second.get_json()["attempt"]["is_formal"])
        attempts = self._attempt_rows()
        self.assertEqual(
            [attempt["is_formal"] for attempt in attempts],
            [0, 1],
        )

    def test_recommendations_exclude_completed_and_unavailable_courses(self):
        recommendations = self.client.get("/api/agri-skills/recommendations")

        self.assertEqual(recommendations.status_code, 200)
        self.assertEqual(
            [
                course["id"]
                for course in recommendations.get_json()["courses"]
            ],
            [2, 1],
        )

        self._complete_course(2)
        recommendations = self.client.get("/api/agri-skills/recommendations")

        self.assertEqual(recommendations.status_code, 200)
        self.assertEqual(
            [
                course["id"]
                for course in recommendations.get_json()["courses"]
            ],
            [1],
        )

    def test_progress_get_put_and_lower_resume_position(self):
        initial = self.client.get("/api/agri-skills/courses/1/progress")

        self.assertEqual(initial.status_code, 200)
        self.assertEqual(initial.get_json()["progress"]["progress_percent"], 0)
        self.assertIsNone(initial.get_json()["progress"]["completed_at"])

        updated = self.client.put(
            "/api/agri-skills/courses/1/progress",
            json={"position_seconds": 79, "watched_delta_seconds": 10},
        )

        self.assertEqual(updated.status_code, 200)
        self.assertEqual(
            updated.get_json()["progress"]["progress_percent"],
            79,
        )
        self.assertIsNone(updated.get_json()["progress"]["completed_at"])

        resumed = self.client.put(
            "/api/agri-skills/courses/1/progress",
            json={"position_seconds": 40, "watched_delta_seconds": 0},
        )

        self.assertEqual(resumed.status_code, 200)
        progress = resumed.get_json()["progress"]
        self.assertEqual(progress["furthest_position_seconds"], 79)
        self.assertEqual(progress["resume_position_seconds"], 40)
        self.assertEqual(progress["progress_percent"], 79)

    def test_invalid_progress_returns_400_without_mutation(self):
        self._complete_course(1)

        invalid = self.client.put(
            "/api/agri-skills/courses/1/progress",
            json={"position_seconds": 101, "watched_delta_seconds": 1},
        )

        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(
            invalid.get_json()["message"],
            "观看位置超出有效范围",
        )
        progress = self.client.get(
            "/api/agri-skills/courses/1/progress"
        ).get_json()["progress"]
        self.assertEqual(progress["furthest_position_seconds"], 80)
        self.assertEqual(progress["watched_seconds"], 80)
        self.assertIsNotNone(progress["completed_at"])

    def test_non_object_progress_body_is_rejected_without_mutation(self):
        created = self.client.put(
            "/api/agri-skills/courses/1/progress",
            json={"position_seconds": 50, "watched_delta_seconds": 5},
        )
        self.assertEqual(created.status_code, 200)
        before = self.client.get(
            "/api/agri-skills/courses/1/progress"
        ).get_json()["progress"]

        invalid = self.client.put(
            "/api/agri-skills/courses/1/progress",
            json=[{"position_seconds": 80, "watched_delta_seconds": 10}],
        )

        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(
            invalid.get_json(),
            {
                "success": False,
                "message": "请求体格式不正确",
                "errors": {"body": "请求体必须是 JSON 对象"},
            },
        )
        after = self.client.get(
            "/api/agri-skills/courses/1/progress"
        ).get_json()["progress"]
        self.assertEqual(after, before)

    def test_quiz_requires_owned_completed_course_and_hides_answers(self):
        unavailable = self.client.get(
            "/api/agri-skills/courses/1/quiz"
        )

        self.assertEqual(unavailable.status_code, 404)
        self.assertEqual(unavailable.get_json()["message"], "暂无可用测验")

        self._complete_course(1)
        quiz = self.client.get("/api/agri-skills/courses/1/quiz")

        self.assertEqual(quiz.status_code, 200)
        questions = quiz.get_json()["quiz"]["questions"]
        self.assertEqual([question["id"] for question in questions], ["q1"])
        self.assertTrue(all("answer" not in item for item in questions))

        foreign = self.other_client.get(
            "/api/agri-skills/courses/1/quiz"
        )

        self.assertEqual(foreign.status_code, 404)
        self.assertEqual(foreign.get_json()["message"], "暂无可用测验")

    def test_quiz_validation_and_ai_failure_use_api_error_mapping(self):
        self._complete_course(1)

        invalid = self.client.post(
            "/api/agri-skills/courses/1/quiz",
            json={"answers": {}},
        )

        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(invalid.get_json()["message"], "测验答案不完整")
        self.ai.complete_json.assert_not_called()

        self.ai.complete_json.side_effect = AiUnavailableError(
            "raw upstream failure"
        )
        unavailable = self.client.post(
            "/api/agri-skills/courses/1/quiz",
            json={"answers": {"q1": "A"}},
        )

        self.assertEqual(unavailable.status_code, 503)
        self.assertEqual(
            unavailable.get_json()["message"],
            "AI 服务暂时不可用",
        )
        progress = self.client.get(
            "/api/agri-skills/courses/1/progress"
        ).get_json()["progress"]
        self.assertIsNotNone(progress["completed_at"])

    def test_non_object_quiz_body_does_not_grade_or_create_attempt(self):
        self._complete_course(1)

        invalid = self.client.post(
            "/api/agri-skills/courses/1/quiz",
            json=[{"answers": {"q1": "A"}}],
        )

        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(
            invalid.get_json(),
            {
                "success": False,
                "message": "请求体格式不正确",
                "errors": {"body": "请求体必须是 JSON 对象"},
            },
        )
        self.ai.complete_json.assert_not_called()
        self.assertEqual(self._attempt_rows(), [])

    def test_all_routes_require_active_student(self):
        requests = [
            ("GET", "/api/agri-skills/courses", None),
            ("GET", "/api/agri-skills/recommendations", None),
            ("GET", "/api/agri-skills/courses/1/progress", None),
            (
                "PUT",
                "/api/agri-skills/courses/1/progress",
                {"position_seconds": 10, "watched_delta_seconds": 10},
            ),
            ("GET", "/api/agri-skills/courses/1/quiz", None),
            (
                "POST",
                "/api/agri-skills/courses/1/quiz",
                {"answers": {"q1": "A"}},
            ),
        ]

        for method, path, payload in requests:
            for client_name, client in (
                ("anonymous", self.app.test_client()),
                ("teacher", self.teacher_client),
            ):
                with self.subTest(
                    method=method,
                    path=path,
                    client=client_name,
                ):
                    response = client.open(path, method=method, json=payload)

                    self.assertEqual(response.status_code, 401)
                    self.assertEqual(
                        response.get_json()["message"],
                        "未登录或会话已过期",
                    )


if __name__ == "__main__":
    unittest.main()
