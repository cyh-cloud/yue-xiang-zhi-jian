import tempfile
import unittest
from pathlib import Path

from app import create_app
from app.agri_skills.course_learning import (
    DatabaseAgriCourseProvider,
    get_course_progress,
    list_courses,
    list_recommendations,
)
from app.agri_skills.errors import AgriNotFoundError
from app.agri_skills.providers import list_provider_courses, set_course_provider
from app.db import get_db


class LegacyProvider:
    def list_published_agriculture_courses(self, student_id):
        return [{"id": 1, "direction": "agriculture"}]

    def get_course(self, course_id):
        return {"id": course_id, "direction": "agriculture"}

    def get_quiz(self, course_id):
        return None


class DirectionProvider:
    def __init__(self) -> None:
        self.course = {
            "id": 2,
            "direction": "ecommerce",
            "status": "published",
            "title": "电商课程",
            "summary": "电商课程简介",
            "teacher_name": "陈老师",
            "published_at": "2026-09-01T00:00:00+00:00",
            "duration_seconds": 300,
            "tag_ids": [1],
        }

    def list_published_courses(self, student_id, direction):
        return [{**self.course, "direction": direction}]

    def get_course(self, course_id):
        if course_id != self.course["id"]:
            return None
        return dict(self.course)

    def get_quiz(self, course_id):
        return None


class TestSharedCourseProvider(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(Path(self.temp_dir.name) / "test.db"),
                "SECRET_KEY": "test-only-secret",
            }
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_legacy_agriculture_provider_still_works(self):
        with self.app.app_context():
            set_course_provider(self.app, LegacyProvider())
            self.assertEqual(
                list_provider_courses(1, "agriculture")[0]["id"],
                1,
            )

    def test_direction_provider_serves_ecommerce(self):
        with self.app.app_context():
            set_course_provider(self.app, DirectionProvider())
            self.assertEqual(
                list_courses(1, "ecommerce")[0]["direction"],
                "ecommerce",
            )

    def test_agriculture_recommendations_use_replacement_provider_catalog(self):
        with self.app.app_context():
            set_course_provider(self.app, DirectionProvider())

            recommendations = list_recommendations(1, "agriculture")

            self.assertEqual(
                [course["id"] for course in recommendations],
                [2],
            )

    def test_direction_provider_serves_handcraft_without_new_registry(self):
        class RecordingDirectionProvider(DirectionProvider):
            def __init__(self) -> None:
                super().__init__()
                self.requested_directions = []

            def list_published_courses(self, student_id, direction):
                self.requested_directions.append(direction)
                return super().list_published_courses(student_id, direction)

        with self.app.app_context():
            provider = RecordingDirectionProvider()
            set_course_provider(self.app, provider)

            courses = list_courses(1, "handcraft")
            recommendations = list_recommendations(1, "handcraft")
            provider_keys = {
                key
                for key in self.app.extensions
                if "course_provider" in key
            }

        self.assertEqual(
            [(course["id"], course["direction"]) for course in courses],
            [(2, "handcraft")],
        )
        self.assertEqual(
            [
                (course["id"], course["direction"])
                for course in recommendations
            ],
            [(2, "handcraft")],
        )
        self.assertEqual(
            provider.requested_directions,
            ["handcraft", "handcraft"],
        )
        self.assertEqual(provider_keys, {"agri_course_provider"})

    def test_database_provider_keeps_legacy_agriculture_method(self):
        with self.app.app_context():
            provider = DatabaseAgriCourseProvider()
            self.assertEqual(
                provider.list_published_agriculture_courses(1),
                provider.list_published_courses(1, "agriculture"),
            )

    def test_list_courses_filters_ineligible_rows(self):
        class MixedProvider(DirectionProvider):
            def list_published_courses(self, student_id, direction):
                return [
                    *super().list_published_courses(student_id, direction),
                    {
                        "id": 3,
                        "direction": direction,
                        "status": "published",
                        "title": "",
                        "summary": "无标题",
                        "teacher_name": "陈老师",
                        "published_at": "2026-09-01T00:00:00+00:00",
                        "duration_seconds": 300,
                        "tag_ids": [1],
                    },
                ]

        with self.app.app_context():
            set_course_provider(self.app, MixedProvider())
            self.assertEqual(
                [
                    course["id"]
                    for course in list_courses(1, "ecommerce")
                ],
                [2],
            )

    def test_ecommerce_provider_rejects_incomplete_or_unpublished_courses(self):
        invalid_courses = (
            {"status": "pending"},
            {"status": "offline"},
            {"published_at": None},
            {"published_at": ""},
            {"tag_ids": None},
            {"tag_ids": [True]},
            {"tag_ids": ["1"]},
        )

        with self.app.app_context():
            for changes in invalid_courses:
                with self.subTest(changes=changes):
                    provider = DirectionProvider()
                    provider.course.update(changes)
                    set_course_provider(self.app, provider)

                    self.assertEqual(
                        list_courses(1, "ecommerce"),
                        [],
                    )
                    self.assertEqual(
                        list_recommendations(1, "ecommerce"),
                        [],
                    )
                    with self.assertRaisesRegex(
                        AgriNotFoundError,
                        "课程不存在",
                    ):
                        get_course_progress(1, 2, "ecommerce")

    def test_replacement_provider_accepts_complete_published_ecommerce_course(
        self,
    ):
        with self.app.app_context():
            set_course_provider(self.app, DirectionProvider())
            courses = list_courses(1, "ecommerce")

            self.assertEqual(
                list(courses),
                [
                    {
                        "id": 2,
                        "direction": "ecommerce",
                        "status": "published",
                        "title": "电商课程",
                        "summary": "电商课程简介",
                        "teacher_name": "陈老师",
                        "published_at": "2026-09-01T00:00:00+00:00",
                        "duration_seconds": 300,
                        "tag_ids": [1],
                    }
                ],
            )

    def test_ecommerce_recommendations_use_replacement_provider_catalog(self):
        with self.app.app_context():
            set_course_provider(self.app, DirectionProvider())

            recommendations = list_recommendations(1, "ecommerce")

            self.assertEqual(
                [course["id"] for course in recommendations],
                [2],
            )


if __name__ == "__main__":
    unittest.main()
