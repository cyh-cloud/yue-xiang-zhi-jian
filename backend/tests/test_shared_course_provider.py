import tempfile
import unittest
from pathlib import Path

from app import create_app
from app.agri_skills.course_learning import (
    DatabaseAgriCourseProvider,
    list_courses,
)
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
    def list_published_courses(self, student_id, direction):
        return [
            {
                "id": 2,
                "direction": direction,
                "title": "电商课程",
                "summary": "电商课程简介",
                "teacher_name": "陈老师",
                "duration_seconds": 300,
            }
        ]

    def get_course(self, course_id):
        return {"id": course_id, "direction": "ecommerce"}

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
                        "title": "",
                        "summary": "无标题",
                        "teacher_name": "陈老师",
                        "duration_seconds": 300,
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


if __name__ == "__main__":
    unittest.main()
