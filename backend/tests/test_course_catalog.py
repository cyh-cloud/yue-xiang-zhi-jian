import tempfile
import unittest
from pathlib import Path

from app import create_app
from app.content_review import set_content_review_provider
from app.db import get_db


ECOMMERCE_FIXTURE_IDS = {1001, 1002, 1003, 1004, 1005}


class FakeReviewProvider:
    def __init__(self):
        self.records = {}

    def set_status(self, content_type, content_id, review_status, **values):
        self.records[(content_type, content_id)] = {
            "content_type": content_type,
            "content_id": content_id,
            "review_status": review_status,
            **values,
        }

    def get_review_status(self, *, content_type, content_id):
        record = self.records.get((content_type, content_id))
        return dict(record) if record is not None else None


class TestCourseCatalog(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(Path(self.temp_dir.name) / "test.db"),
                "SECRET_KEY": "test-only-secret",
                "SESSION_HOURS": 24,
            }
        )
        self.client = self.app.test_client()
        self.review = FakeReviewProvider()
        set_content_review_provider(self.app, self.review)

    def tearDown(self):
        self.temp_dir.cleanup()

    def seed_course(
        self,
        status: str,
        direction: str,
        published_at: str,
        tags: list[int] | None = None,
    ) -> int:
        now = "2026-09-14T00:00:00+00:00"
        with self.app.app_context():
            db = get_db()
            cursor = db.execute(
                """
                INSERT INTO courses (
                    title, direction, status, duration_seconds,
                    published_at, summary,
                    teacher_name, created_at, updated_at
                )
                VALUES (?, ?, ?, 300, ?, '课程简介', '测试教师', ?, ?)
                """,
                (
                    f"{direction}-{status}",
                    direction,
                    status,
                    published_at,
                    now,
                    now,
                ),
            )
            course_id = int(cursor.lastrowid)
            for tag_id in tags or []:
                db.execute(
                    """
                    INSERT INTO course_interest_tags (course_id, tag_id)
                    VALUES (?, ?)
                    """,
                    (course_id, tag_id),
                )
            db.commit()
        return course_id

    def seed_teacher_course(self, status: str, review_status: str) -> int:
        now = "2026-09-14T00:00:00+00:00"
        with self.app.app_context():
            db = get_db()
            db.execute(
                """
                INSERT OR IGNORE INTO users (
                    id, username, password_hash, name, role, is_enabled,
                    created_at, updated_at
                )
                VALUES (
                    7, 'review-teacher', 'test-hash', '审核教师', 'teacher',
                    1, ?, ?
                )
                """,
                (now, now),
            )
            cursor = db.execute(
                """
                INSERT INTO courses (
                    title, direction, status, duration_seconds,
                    published_at, summary, teacher_name, teacher_id,
                    content_tags_json, created_at, updated_at
                )
                VALUES (
                    '教师审核课程', 'agriculture', ?, 300, NULL,
                    '审核可见性测试', '审核教师', 7, '[]', ?, ?
                )
                """,
                (status, now, now),
            )
            course_id = int(cursor.lastrowid)
            db.commit()

        self.review.set_status(
            "course_video",
            str(course_id),
            review_status,
            published_at=(
                "2026-09-18T10:00:00+08:00"
                if review_status == "approved"
                else None
            ),
        )
        return course_id

    def login_student(
        self,
        username: str,
        tag_ids: list[int] | None = None,
    ) -> None:
        registered = self.client.post(
            "/api/auth/register",
            json={
                "role": "student",
                "username": username,
                "password": "password8",
                "confirm_password": "password8",
                "name": "林晓",
            },
        )
        self.assertEqual(registered.status_code, 201)
        completed = self.client.post(
            "/api/auth/interest-tags",
            json={"tag_ids": tag_ids or []},
        )
        self.assertEqual(completed.status_code, 200)

    def test_only_published_courses_for_selected_direction_are_returned(self):
        self.seed_course(
            "published", "agriculture", "2026-09-01T00:00:00+00:00"
        )
        self.seed_course(
            "pending", "agriculture", "2026-09-02T00:00:00+00:00"
        )
        self.seed_course(
            "offline", "agriculture", "2026-09-03T00:00:00+00:00"
        )
        self.seed_course(
            "published", "ecommerce", "2026-09-04T00:00:00+00:00"
        )
        self.login_student("student01")

        response = self.client.get(
            "/api/student/courses?direction=agriculture"
        )
        titles = [
            item["title"]
            for item in response.get_json()["courses"]
            if item["id"] not in ECOMMERCE_FIXTURE_IDS
        ]
        self.assertEqual(titles, ["agriculture-published"])

    def test_approved_pending_local_course_is_visible_in_catalog(self):
        course_id = self.seed_teacher_course("pending", "approved")
        self.login_student("student01")

        response = self.client.get(
            "/api/student/courses?direction=agriculture"
        )
        course = next(
            item
            for item in response.get_json()["courses"]
            if item["id"] == course_id
        )

        self.assertEqual(course["status"], "published")
        self.assertEqual(
            course["published_at"],
            "2026-09-18T10:00:00+08:00",
        )

    def test_pending_teacher_course_is_hidden_from_catalog(self):
        course_id = self.seed_teacher_course("pending", "pending")
        self.login_student("student01")

        response = self.client.get(
            "/api/student/courses?direction=agriculture"
        )

        self.assertNotIn(
            course_id,
            [item["id"] for item in response.get_json()["courses"]],
        )

    def test_interest_match_ranks_before_newer_nonmatch(self):
        self.seed_course(
            "published",
            "agriculture",
            "2026-09-01T00:00:00+00:00",
            tags=[1],
        )
        self.seed_course(
            "published",
            "agriculture",
            "2026-09-12T00:00:00+00:00",
            tags=[2],
        )
        self.login_student("student01", tag_ids=[1])

        response = self.client.get(
            "/api/student/courses?direction=agriculture"
        )
        self.assertEqual(
            response.get_json()["courses"][0]["interest_match"],
            True,
        )

    def test_equal_recommendation_level_uses_published_at_desc_then_id_desc(
        self,
    ):
        self.seed_course(
            "published", "agriculture", "2026-09-01T00:00:00+00:00"
        )
        self.seed_course(
            "published", "agriculture", "2026-09-12T00:00:00+00:00"
        )
        self.login_student("student01")

        response = self.client.get(
            "/api/student/courses?direction=agriculture"
        )
        self.assertEqual(
            [
                item["published_at"]
                for item in response.get_json()["courses"]
                if item["id"] not in ECOMMERCE_FIXTURE_IDS
            ],
            [
                "2026-09-12T00:00:00+00:00",
                "2026-09-01T00:00:00+00:00",
            ],
        )

    def test_empty_direction_returns_empty_list_for_frontend_empty_state(self):
        self.login_student("student01")
        response = self.client.get(
            "/api/student/courses?direction=handcraft"
        )
        self.assertEqual(response.get_json()["courses"], [])

    def test_invalid_or_missing_direction_returns_clear_400(self):
        self.login_student("student01")

        for direction in ("invalid", None):
            with self.subTest(direction=direction):
                path = (
                    "/api/student/courses?direction=invalid"
                    if direction is not None
                    else "/api/student/courses"
                )
                response = self.client.get(path)

                self.assertEqual(response.status_code, 400)
                self.assertEqual(
                    response.get_json()["errors"],
                    {"direction": "学习方向不正确"},
                )


if __name__ == "__main__":
    unittest.main()
