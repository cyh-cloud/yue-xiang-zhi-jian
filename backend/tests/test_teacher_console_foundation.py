import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from app import create_app
from app.db import get_db


class TestTeacherConsoleFoundation(unittest.TestCase):
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

    def test_teacher_console_schema_and_columns(self):
        with self.app.app_context():
            columns = {
                row["name"]
                for row in get_db().execute("PRAGMA table_info(courses)")
            }
            tables = {
                row["name"]
                for row in get_db().execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
        self.assertTrue(
            {
                "teacher_id",
                "version",
                "media_source_type",
                "content_tags_json",
                "rejection_opinion",
                "submitted_at",
            }.issubset(columns)
        )
        self.assertTrue(
            {
                "teacher_announcements",
                "teacher_announcement_delivery_events",
                "teacher_course_status_history",
                "content_comments",
                "teacher_learning_reports",
            }.issubset(tables)
        )

    def test_time_helpers_are_timezone_aware(self):
        from app.teacher_console.time_utils import (
            now_shanghai_iso,
            parse_provider_time,
        )

        value = now_shanghai_iso()
        self.assertTrue(value.endswith("+08:00"))
        self.assertEqual(
            parse_provider_time("2026-09-18T10:00:00Z").utcoffset(),
            timedelta(hours=8),
        )


if __name__ == "__main__":
    unittest.main()
