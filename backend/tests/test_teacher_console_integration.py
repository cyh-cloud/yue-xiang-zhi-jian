import tempfile
import unittest
from pathlib import Path

from werkzeug.security import generate_password_hash

from app import create_app
from app.agri_skills.course_learning import list_courses, list_recommendations
from app.agri_skills.providers import get_course_provider
from app.content_review import set_content_review_provider
from app.db import get_db
from app.teacher_console.course_service import (
    create_teacher_course,
    get_teacher_course,
)


DIRECTION_SURFACES = {
    "agriculture": (
        "/api/agri-skills/courses",
        "/api/agri-skills/recommendations",
    ),
    "ecommerce": (
        "/api/ecommerce-training/courses",
        "/api/ecommerce-training/recommendations",
    ),
    "handcraft": (
        "/api/handcraft-inheritance/courses",
        "/api/handcraft-inheritance/recommendations",
    ),
}


class FakeReviewProvider:
    def __init__(self):
        self.records = {}
        self.calls = []

    def set_status(
        self,
        content_type,
        content_id,
        review_status,
        *,
        opinion=None,
        updated_at=None,
        published_at=None,
        version=1,
    ):
        self.records[(content_type, content_id)] = {
            "content_type": content_type,
            "content_id": content_id,
            "review_status": review_status,
            "rejection_opinion": opinion,
            "updated_at": updated_at,
            "published_at": published_at,
            "version": version,
        }

    def clear_status(self, content_type, content_id):
        self.records.pop((content_type, content_id), None)

    def get_review_status(self, *, content_type, content_id):
        self.calls.append(
            {
                "method": "get_review_status",
                "content_type": content_type,
                "content_id": content_id,
            }
        )
        record = self.records.get((content_type, content_id))
        return dict(record) if record is not None else None


class TestTeacherConsoleCrossModuleIntegration(unittest.TestCase):
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

        with self.app.app_context():
            db = get_db()
            now = "2026-09-19T09:00:00+08:00"
            db.execute("DELETE FROM courses")
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
            db.commit()

        self.client = self.app.test_client()
        login = self.client.post(
            "/api/auth/login",
            json={"username": "student08", "password": "password8"},
        )
        self.assertEqual(login.status_code, 200)

    def tearDown(self):
        self.temp_dir.cleanup()

    def create_course(self, direction):
        with self.app.app_context():
            return create_teacher_course(
                7,
                {
                    "title": f"{direction} integration course",
                    "direction": direction,
                    "summary": "Cross-module acceptance course",
                    "content_tags": [],
                    "duration_seconds": 300,
                    "media_source_type": "external_url",
                    "media_url": (
                        f"https://media.example.test/{direction}.mp4"
                    ),
                },
            )

    def set_local_status(self, course_id, status):
        with self.app.app_context():
            db = get_db()
            db.execute(
                "UPDATE courses SET status = ? WHERE id = ?",
                (status, course_id),
            )
            db.commit()

    def set_review(
        self,
        course_id,
        review_status,
        *,
        opinion=None,
        updated_at=None,
        published_at=None,
    ):
        self.review.set_status(
            "course_video",
            str(course_id),
            review_status,
            opinion=opinion,
            updated_at=updated_at,
            published_at=published_at,
        )

    def provider_course_ids(self, direction):
        with self.app.app_context():
            return [
                int(course["id"])
                for course in get_course_provider().list_published_courses(
                    8,
                    direction,
                )
            ]

    def catalog_course_ids(self, direction):
        response = self.client.get(
            f"/api/student/courses?direction={direction}"
        )
        self.assertEqual(response.status_code, 200)
        return [
            int(course["id"])
            for course in response.get_json()["courses"]
        ]

    def recommendation_course_ids(self, direction):
        with self.app.app_context():
            return [
                int(course["id"])
                for course in list_recommendations(8, direction)
            ]

    def seed_legacy_published_course(self, direction):
        now = "2026-09-19T09:00:00+08:00"
        with self.app.app_context():
            db = get_db()
            cursor = db.execute(
                """
                INSERT INTO courses (
                    title, direction, status, duration_seconds, published_at,
                    summary, teacher_name, created_at, updated_at
                )
                VALUES (?, ?, 'published', 300, ?, ?, ?, ?, ?)
                """,
                (
                    "Legacy published course",
                    direction,
                    "2026-09-18T10:00:00+08:00",
                    "Legacy course summary",
                    "Legacy teacher",
                    now,
                    now,
                ),
            )
            db.commit()
            return int(cursor.lastrowid)

    def test_approved_course_serves_03_04_05_without_consumer_changes(self):
        for direction in ("agriculture", "ecommerce", "handcraft"):
            with self.subTest(direction=direction):
                course = self.create_course(direction)
                self.set_local_status(course["id"], "pending")
                self.set_review(
                    course["id"],
                    "approved",
                    published_at="2026-09-19T10:00:00+08:00",
                )

                with self.app.app_context():
                    self.assertEqual(
                        [
                            item["id"]
                            for item in list_courses(8, direction)
                        ],
                        [course["id"]],
                    )

                course_path, recommendation_path = DIRECTION_SURFACES[
                    direction
                ]
                course_response = self.client.get(course_path)
                recommendation_response = self.client.get(
                    recommendation_path
                )

                self.assertEqual(course_response.status_code, 200)
                self.assertEqual(recommendation_response.status_code, 200)
                self.assertEqual(
                    [
                        item["id"]
                        for item in course_response.get_json()["courses"]
                    ],
                    [course["id"]],
                )
                self.assertEqual(
                    [
                        item["id"]
                        for item in recommendation_response.get_json()[
                            "courses"
                        ]
                    ],
                    [course["id"]],
                )
                self.assertEqual(
                    self.catalog_course_ids(direction),
                    [course["id"]],
                )
                self.assertEqual(
                    self.recommendation_course_ids(direction),
                    [course["id"]],
                )

    def test_all_course_states_have_the_same_visibility_in_three_surfaces(
        self,
    ):
        course = self.create_course("agriculture")
        for review_status in ("pending", "approved", "rejected", None):
            for local_status in ("pending", "offline"):
                with self.subTest(
                    review_status=review_status,
                    local_status=local_status,
                ):
                    expected = (
                        review_status == "approved"
                        and local_status != "offline"
                    )
                    self.set_local_status(course["id"], local_status)
                    if review_status is None:
                        self.review.clear_status(
                            "course_video",
                            str(course["id"]),
                        )
                    else:
                        self.set_review(
                            course["id"],
                            review_status,
                            published_at=(
                                "2026-09-19T10:00:00+08:00"
                                if review_status == "approved"
                                else None
                            ),
                        )

                    self.assertEqual(
                        bool(self.provider_course_ids("agriculture")),
                        expected,
                    )
                    self.assertEqual(
                        bool(self.catalog_course_ids("agriculture")),
                        expected,
                    )
                    self.assertEqual(
                        bool(
                            self.recommendation_course_ids(
                                "agriculture"
                            )
                        ),
                        expected,
                    )

    def test_legacy_published_course_remains_visible_in_all_three_surfaces(
        self,
    ):
        course_id = self.seed_legacy_published_course("agriculture")

        self.assertIn(
            course_id,
            self.provider_course_ids("agriculture"),
        )
        self.assertIn(
            course_id,
            self.catalog_course_ids("agriculture"),
        )
        self.assertIn(
            course_id,
            self.recommendation_course_ids("agriculture"),
        )

    def test_review_history_is_read_from_provider_authority(self):
        course = self.create_course("agriculture")
        self.set_local_status(course["id"], "pending")
        self.set_review(
            course["id"],
            "rejected",
            opinion="补充课程简介",
            updated_at="2026-09-18T12:00:00+08:00",
        )

        with self.app.app_context():
            stored_course = get_teacher_course(7, course["id"])

        self.assertEqual(stored_course["status"], "rejected")
        self.assertEqual(
            stored_course["rejection_opinion"],
            "补充课程简介",
        )
        self.assertEqual(
            stored_course["review_updated_at"],
            "2026-09-18T12:00:00+08:00",
        )


if __name__ == "__main__":
    unittest.main()
