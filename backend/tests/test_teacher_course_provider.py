import json
import tempfile
import unittest
from pathlib import Path

from werkzeug.security import generate_password_hash

from app import create_app
from app.agri_skills.course_learning import list_courses, list_recommendations
from app.agri_skills.providers import get_course_provider
from app.content_review import set_content_review_provider
from app.db import get_db
from app.teacher_console.course_service import create_teacher_course
from app.teacher_console.providers import DatabaseTeacherCourseProvider


class FakeReviewProvider:
    def __init__(self):
        self.records = {}

    def set_status(
        self,
        content_type,
        content_id,
        review_status,
        *,
        published_at=None,
    ):
        self.records[(content_type, content_id)] = {
            "content_type": content_type,
            "content_id": content_id,
            "review_status": review_status,
            "published_at": published_at,
        }

    def clear_status(self, content_type, content_id):
        self.records.pop((content_type, content_id), None)

    def get_review_status(self, *, content_type, content_id):
        record = self.records.get((content_type, content_id))
        return dict(record) if record is not None else None


class TestTeacherCourseProvider(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(Path(self.temp_dir.name) / "test.db"),
                "SECRET_KEY": "test-only-secret",
                "SESSION_HOURS": 24,
                "SESSION_COOKIE_SECURE": False,
            }
        )
        self.review = FakeReviewProvider()
        set_content_review_provider(self.app, self.review)
        self.client = self.app.test_client()

        with self.app.app_context():
            db = get_db()
            now = "2026-09-19T09:00:00+08:00"
            db.executemany(
                """
                INSERT INTO users (
                    id, username, password_hash, name, role, is_enabled,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, 1, ?, ?)
                """,
                (
                    (
                        7,
                        "teacher07",
                        generate_password_hash("password8"),
                        "教师七",
                        "teacher",
                        now,
                        now,
                    ),
                    (
                        8,
                        "student08",
                        generate_password_hash("password8"),
                        "学员八",
                        "student",
                        now,
                        now,
                    ),
                ),
            )
            self.lychee_tag_id = int(
                db.execute(
                    """
                    SELECT id
                    FROM interest_tags
                    WHERE group_key = 'crop' AND name = '荔枝'
                    """
                ).fetchone()["id"]
            )
            self.longan_tag_id = int(
                db.execute(
                    """
                    SELECT id
                    FROM interest_tags
                    WHERE group_key = 'crop' AND name = '龙眼'
                    """
                ).fetchone()["id"]
            )
            db.commit()

        self.course_id = self._create_course("荔枝保果")
        self._login("student08")

    def tearDown(self):
        self.temp_dir.cleanup()

    def _create_course(self, title):
        with self.app.app_context():
            course = create_teacher_course(
                7,
                {
                    "title": title,
                    "direction": "agriculture",
                    "summary": "荔枝保果与采后管理",
                    "content_tags": ["荔枝", "保果", "自定义标签"],
                    "duration_seconds": 300,
                    "media_source_type": "external_url",
                    "media_url": "https://media.example.test/course.mp4",
                },
            )
        return int(course["id"])

    def _login(self, username):
        response = self.client.post(
            "/api/auth/login",
            json={"username": username, "password": "password8"},
        )
        self.assertEqual(response.status_code, 200)

    def _set_local_status(self, course_id, status):
        with self.app.app_context():
            db = get_db()
            db.execute(
                "UPDATE courses SET status = ? WHERE id = ?",
                (status, course_id),
            )
            db.commit()

    def _set_review(
        self,
        course_id,
        review_status,
        *,
        published_at=None,
    ):
        self.review.set_status(
            "course_video",
            str(course_id),
            review_status,
            published_at=published_at,
        )

    def _surface_course_ids(self, direction="agriculture"):
        with self.app.app_context():
            catalog_ids = {
                item["id"] for item in list_courses(8, direction)
            }
            recommendation_ids = {
                item["id"]
                for item in list_recommendations(8, direction)
            }
        response = self.client.get(
            f"/api/student/courses?direction={direction}"
        )
        self.assertEqual(response.status_code, 200)
        aggregation_ids = {
            item["id"] for item in response.get_json()["courses"]
        }
        return catalog_ids, recommendation_ids, aggregation_ids

    def test_default_app_registers_teacher_provider_in_existing_slot(self):
        with self.app.app_context():
            provider = get_course_provider()
            provider_keys = {
                key
                for key in self.app.extensions
                if "course_provider" in key
            }

        self.assertIsInstance(provider, DatabaseTeacherCourseProvider)
        self.assertEqual(provider_keys, {"agri_course_provider"})

    def test_approved_course_is_visible_in_all_three_surfaces(self):
        published_at = "2026-09-19T10:00:00+08:00"
        self._set_local_status(self.course_id, "pending")
        self._set_review(
            self.course_id,
            "approved",
            published_at=published_at,
        )

        catalog_ids, recommendation_ids, aggregation_ids = (
            self._surface_course_ids()
        )

        self.assertIn(self.course_id, catalog_ids)
        self.assertIn(self.course_id, recommendation_ids)
        self.assertIn(self.course_id, aggregation_ids)

        response = self.client.get(
            "/api/student/courses?direction=agriculture"
        )
        course = next(
            item
            for item in response.get_json()["courses"]
            if item["id"] == self.course_id
        )
        self.assertEqual(course["status"], "published")
        self.assertEqual(course["published_at"], published_at)
        self.assertEqual(
            course["content_tags"],
            ["荔枝", "保果", "自定义标签"],
        )
        self.assertEqual(course["tag_ids"], [self.lychee_tag_id])

    def test_unresolved_courses_are_hidden_from_all_three_surfaces(self):
        published_at = "2026-09-19T10:00:00+08:00"
        cases = (
            ("draft", "approved", published_at),
            ("pending", "pending", None),
            ("pending", "rejected", None),
            ("offline", "approved", published_at),
            ("published", None, None),
        )

        for local_status, review_status, review_published_at in cases:
            with self.subTest(
                local_status=local_status,
                review_status=review_status,
            ):
                self._set_local_status(self.course_id, local_status)
                if review_status is None:
                    self.review.clear_status(
                        "course_video",
                        str(self.course_id),
                    )
                else:
                    self._set_review(
                        self.course_id,
                        review_status,
                        published_at=review_published_at,
                    )

                catalog_ids, recommendation_ids, aggregation_ids = (
                    self._surface_course_ids()
                )

                self.assertNotIn(self.course_id, catalog_ids)
                self.assertNotIn(self.course_id, recommendation_ids)
                self.assertNotIn(self.course_id, aggregation_ids)

    def test_get_course_and_quiz_require_resolved_publication(self):
        with self.app.app_context():
            db = get_db()
            db.execute(
                """
                INSERT INTO course_quizzes (
                    course_id, enabled, scoring_rule, questions_json,
                    updated_at
                )
                VALUES (?, 1, 'all_correct', ?, ?)
                """,
                (
                    self.course_id,
                    json.dumps(
                        [
                            {
                                "id": "q1",
                                "type": "true_false",
                                "prompt": "是否完成？",
                                "options": ["正确", "错误"],
                                "answer": "正确",
                            }
                        ],
                        ensure_ascii=False,
                    ),
                    "2026-09-19T09:00:00+08:00",
                ),
            )
            db.commit()

        self._set_local_status(self.course_id, "pending")
        self._set_review(self.course_id, "pending")
        with self.app.app_context():
            provider = DatabaseTeacherCourseProvider()
            self.assertIsNone(provider.get_course(self.course_id))
            self.assertIsNone(provider.get_quiz(self.course_id))

        self._set_review(
            self.course_id,
            "approved",
            published_at="2026-09-19T10:00:00+08:00",
        )
        with self.app.app_context():
            provider = DatabaseTeacherCourseProvider()
            self.assertEqual(
                provider.get_course(self.course_id)["status"],
                "published",
            )
            self.assertEqual(
                provider.get_quiz(self.course_id)["questions"][0]["id"],
                "q1",
            )

    def test_tag_ids_are_exact_active_matches_not_stale_catalog_links(self):
        with self.app.app_context():
            db = get_db()
            db.execute(
                "DELETE FROM course_interest_tags WHERE course_id = ?",
                (self.course_id,),
            )
            db.execute(
                """
                INSERT INTO course_interest_tags (course_id, tag_id)
                VALUES (?, ?)
                """,
                (self.course_id, self.longan_tag_id),
            )
            db.commit()

        self._set_local_status(self.course_id, "pending")
        self._set_review(
            self.course_id,
            "approved",
            published_at="2026-09-19T10:00:00+08:00",
        )
        with self.app.app_context():
            course = next(
                item
                for item in list_courses(8, "agriculture")
                if item["id"] == self.course_id
            )

        self.assertEqual(
            course["content_tags"],
            ["荔枝", "保果", "自定义标签"],
        )
        self.assertEqual(course["tag_ids"], [self.lychee_tag_id])

    def test_courses_are_sorted_by_parsed_publication_time(self):
        later_course_id = self._create_course("后发布课程")
        self._set_local_status(self.course_id, "pending")
        self._set_local_status(later_course_id, "pending")
        self._set_review(
            self.course_id,
            "approved",
            published_at="2026-09-19T01:00:00+08:00",
        )
        self._set_review(
            later_course_id,
            "approved",
            published_at="2026-09-18T20:00:00+00:00",
        )

        with self.app.app_context():
            courses = list_courses(8, "agriculture")
            provider = get_course_provider()
            provider_ids = {
                item["id"]
                for item in courses
                if item["id"] in {self.course_id, later_course_id}
            }
            provider_course = provider.get_course(self.course_id)

        self.assertEqual(
            [
                item["id"]
                for item in courses
                if item["id"] in {self.course_id, later_course_id}
            ],
            [later_course_id, self.course_id],
        )
        self.assertEqual(
            provider_ids,
            {self.course_id, later_course_id},
        )
        self.assertIsInstance(provider_course["id"], int)
        self.assertGreater(provider_course["id"], 0)


if __name__ == "__main__":
    unittest.main()
