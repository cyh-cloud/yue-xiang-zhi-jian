import tempfile
import unittest
from pathlib import Path

from app import create_app
from app.content_review import (
    get_content_review_provider,
    set_content_review_provider,
)
from app.db import get_db
from app.teacher_console.course_service import (
    create_teacher_course,
    submit_course_for_review,
)


class FakeReviewProvider:
    def __init__(self):
        self.calls = []

    def submit_for_review(
        self,
        *,
        content_type,
        content_id,
        submitter_id,
        expected_version,
        payload,
    ):
        self.calls.append(
            {
                "method": "submit_for_review",
                "content_type": content_type,
                "content_id": content_id,
                "submitter_id": submitter_id,
                "expected_version": expected_version,
                "payload": payload,
            }
        )
        return {
            "content_type": content_type,
            "content_id": content_id,
            "review_status": "pending",
            "version": expected_version,
            "opinion": None,
            "updated_at": "2026-09-19T10:00:00+08:00",
        }

    def get_review_status(self, *, content_type, content_id):
        self.calls.append(
            {
                "method": "get_review_status",
                "content_type": content_type,
                "content_id": content_id,
            }
        )
        return None

    def approve(self, **kwargs):
        raise AssertionError("approve is not part of this acceptance path")

    def reject(self, **kwargs):
        raise AssertionError("reject is not part of this acceptance path")

    def edit(self, **kwargs):
        raise AssertionError("edit is not part of this acceptance path")


class TestTeacherConsoleProviderReplacement(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.media_root = Path(self.temp_dir.name) / "media"
        self.media_root.mkdir()
        (self.media_root / "course.mp4").write_bytes(b"video")
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(Path(self.temp_dir.name) / "test.db"),
                "COURSE_MEDIA_ROOT": str(self.media_root),
                "SECRET_KEY": "test-only-secret",
            }
        )
        with self.app.app_context():
            db = get_db()
            now = "2026-09-19T09:00:00+08:00"
            db.execute(
                """
                INSERT INTO users (
                    id, username, password_hash, name, role, is_enabled,
                    created_at, updated_at
                )
                VALUES (7, 'teacher07', 'test-hash', '教师七', 'teacher', 1, ?, ?)
                """,
                (now, now),
            )
            db.commit()
            self.course_id = int(
                create_teacher_course(
                    7,
                    {
                        "title": "Provider replacement course",
                        "direction": "agriculture",
                        "summary": "Provider replacement acceptance course",
                        "content_tags": [],
                        "duration_seconds": 300,
                        "media_source_type": "local_upload",
                        "media_url": "/media/teacher-courses/course.mp4",
                    },
                )["id"]
            )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_replacement_review_provider_requires_no_consumer_change(self):
        replacement = FakeReviewProvider()
        set_content_review_provider(self.app, replacement)

        with self.app.app_context():
            self.assertIs(get_content_review_provider(), replacement)
            submitted = submit_course_for_review(
                7,
                self.course_id,
                expected_version=1,
            )

        self.assertEqual(submitted["status"], "pending")
        self.assertEqual(
            replacement.calls[-1]["method"],
            "submit_for_review",
        )
        self.assertEqual(
            replacement.calls[-1]["content_type"],
            "course_video",
        )
        self.assertEqual(
            replacement.calls[-1]["content_id"],
            str(self.course_id),
        )
        self.assertEqual(replacement.calls[-1]["submitter_id"], 7)
        self.assertEqual(replacement.calls[-1]["expected_version"], 1)
        self.assertEqual(
            replacement.calls[-1]["payload"]["title"],
            "Provider replacement course",
        )


if __name__ == "__main__":
    unittest.main()
