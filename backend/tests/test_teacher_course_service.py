import json
import tempfile
import unittest
from pathlib import Path

import httpx

from app import create_app
from app.db import get_db
from app.teacher_console.course_service import (
    create_teacher_course,
    get_teacher_course,
    list_teacher_courses,
    update_teacher_course_draft,
)
from app.teacher_console.errors import (
    ProviderAccessDeniedError,
    ProviderConflictError,
    ProviderNotFoundError,
    ProviderValidationError,
)
from app.teacher_console.media import validate_media_reference


class TestTeacherCourseService(unittest.TestCase):
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
            now = "2026-09-19T10:00:00+08:00"
            db.executemany(
                """
                INSERT INTO users (
                    id, username, password_hash, name, role, is_enabled,
                    created_at, updated_at
                )
                VALUES (?, ?, 'test-hash', ?, ?, ?, ?, ?)
                """,
                (
                    (7, "teacher07", "教师七", "teacher", 1, now, now),
                    (8, "teacher08", "教师八", "teacher", 1, now, now),
                    (9, "student09", "学员九", "student", 1, now, now),
                ),
            )
            self.interest_tag_id = int(
                db.execute(
                    """
                    SELECT id
                    FROM interest_tags
                    WHERE group_key = 'crop' AND name = '荔枝'
                    """
                ).fetchone()["id"]
            )
            self.other_interest_tag_id = int(
                db.execute(
                    """
                    SELECT id
                    FROM interest_tags
                    WHERE group_key = 'crop' AND name = '龙眼'
                    """
                ).fetchone()["id"]
            )
            db.commit()

        self.base_payload = {
            "title": "荔枝保果",
            "direction": "agriculture",
            "summary": "花期与果期管理要点",
            "content_tags": [" 荔枝 ", "保果", "荔枝"],
            "duration_seconds": 300,
            "media_source_type": "external_url",
            "media_url": "https://media.example.test/lychee.mp4",
        }

    def tearDown(self):
        self.temp_dir.cleanup()

    def _create_course(self, payload=None):
        return create_teacher_course(7, payload or self.base_payload)

    def test_create_and_list_owned_course(self):
        with self.app.app_context():
            course = self._create_course()

            self.assertEqual(course["teacher_id"], 7)
            self.assertEqual(course["teacher_name"], "教师七")
            self.assertEqual(course["status"], "draft")
            self.assertEqual(course["version"], 1)
            self.assertEqual(course["content_tags"], ["荔枝", "保果"])
            self.assertEqual(course["tag_ids"], [self.interest_tag_id])
            self.assertTrue(course["created_at"].endswith("+08:00"))
            self.assertTrue(course["updated_at"].endswith("+08:00"))

            stored = get_db().execute(
                """
                SELECT content_tags_json
                FROM courses
                WHERE id = ?
                """,
                (course["id"],),
            ).fetchone()
            self.assertEqual(
                json.loads(stored["content_tags_json"]),
                ["荔枝", "保果"],
            )
            self.assertEqual(
                [item["id"] for item in list_teacher_courses(7)],
                [course["id"]],
            )

    def test_other_teacher_cannot_read_course(self):
        with self.app.app_context():
            course = self._create_course()

            with self.assertRaises(ProviderAccessDeniedError):
                get_teacher_course(8, course["id"])

    def test_missing_course_is_not_found(self):
        with self.app.app_context():
            with self.assertRaises(ProviderNotFoundError):
                get_teacher_course(7, 999999)

    def test_non_teacher_cannot_create_course(self):
        with self.app.app_context():
            with self.assertRaises(ProviderAccessDeniedError):
                create_teacher_course(9, self.base_payload)

    def test_update_draft_increments_version_and_resyncs_tags(self):
        with self.app.app_context():
            course = self._create_course()

            updated = update_teacher_course_draft(
                7,
                course["id"],
                expected_version=1,
                payload={
                    "title": "  荔枝保果修订  ",
                    "content_tags": ["龙眼", "自定义标签"],
                    "status": "published",
                },
            )

            self.assertEqual(updated["title"], "荔枝保果修订")
            self.assertEqual(updated["summary"], self.base_payload["summary"])
            self.assertEqual(updated["version"], 2)
            self.assertEqual(updated["status"], "draft")
            self.assertEqual(updated["content_tags"], ["龙眼", "自定义标签"])
            self.assertEqual(updated["tag_ids"], [self.other_interest_tag_id])

    def test_stale_version_is_rejected_without_overwriting(self):
        with self.app.app_context():
            course = self._create_course()

            with self.assertRaises(ProviderConflictError):
                update_teacher_course_draft(
                    7,
                    course["id"],
                    expected_version=99,
                    payload={"title": "过期写入"},
                )

            unchanged = get_teacher_course(7, course["id"])
            self.assertEqual(unchanged["title"], self.base_payload["title"])
            self.assertEqual(unchanged["version"], 1)

    def test_non_draft_course_cannot_be_updated_as_draft(self):
        with self.app.app_context():
            course = self._create_course()
            get_db().execute(
                "UPDATE courses SET status = 'pending' WHERE id = ?",
                (course["id"],),
            )
            get_db().commit()

            with self.assertRaises(ProviderConflictError):
                update_teacher_course_draft(
                    7,
                    course["id"],
                    expected_version=1,
                    payload={"title": "不应写入"},
                )

    def test_other_teacher_cannot_update_course(self):
        with self.app.app_context():
            course = self._create_course()

            with self.assertRaises(ProviderAccessDeniedError):
                update_teacher_course_draft(
                    8,
                    course["id"],
                    expected_version=1,
                    payload={"title": "越权修改"},
                )

    def test_course_payload_validation_rejects_invalid_values(self):
        invalid_payloads = (
            {"direction": "finance"},
            {"title": "   "},
            {"summary": "\t "},
            {"content_tags": "荔枝"},
            {"content_tags": ["荔枝", " "]},
            {"duration_seconds": 0},
            {"duration_seconds": True},
            {"media_source_type": "embed"},
            {"media_url": "javascript:alert(1)"},
        )

        with self.app.app_context():
            for changes in invalid_payloads:
                with self.subTest(changes=changes):
                    with self.assertRaises(ProviderValidationError):
                        self._create_course({**self.base_payload, **changes})

    def test_list_filters_by_owner_direction_and_status(self):
        with self.app.app_context():
            agriculture = self._create_course()
            ecommerce = self._create_course(
                {
                    **self.base_payload,
                    "title": "直播运营",
                    "direction": "ecommerce",
                    "content_tags": [],
                }
            )
            get_db().execute(
                "UPDATE courses SET status = 'pending' WHERE id = ?",
                (ecommerce["id"],),
            )
            get_db().commit()

            self.assertEqual(
                [
                    item["id"]
                    for item in list_teacher_courses(
                        7,
                        direction="agriculture",
                    )
                ],
                [agriculture["id"]],
            )
            self.assertEqual(
                [
                    item["id"]
                    for item in list_teacher_courses(7, status="pending")
                ],
                [ecommerce["id"]],
            )
            self.assertEqual(list_teacher_courses(8), [])

    def test_list_orders_parsed_timestamps_across_timezone_forms(self):
        with self.app.app_context():
            earliest = self._create_course(
                {**self.base_payload, "title": "最早更新"}
            )
            tied_second = self._create_course(
                {**self.base_payload, "title": "并列更新"}
            )
            tied_first = self._create_course(
                {**self.base_payload, "title": "并列更新二"}
            )
            db = get_db()
            db.execute(
                "UPDATE courses SET updated_at = ? WHERE id = ?",
                ("2026-09-19T01:00:00+08:00", earliest["id"]),
            )
            db.execute(
                "UPDATE courses SET updated_at = ? WHERE id = ?",
                ("2026-09-18T20:00:00+00:00", tied_second["id"]),
            )
            db.execute(
                "UPDATE courses SET updated_at = ? WHERE id = ?",
                ("2026-09-19T04:00:00+08:00", tied_first["id"]),
            )
            db.commit()

            self.assertEqual(
                [item["id"] for item in list_teacher_courses(7)],
                [tied_first["id"], tied_second["id"], earliest["id"]],
            )


class TestTeacherCourseMediaValidation(unittest.TestCase):
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

    def test_external_url_format_is_validated_without_network(self):
        with self.app.app_context():
            self.assertEqual(
                validate_media_reference(
                    "external_url",
                    "https://media.example.test/lychee.mp4",
                ),
                "https://media.example.test/lychee.mp4",
            )
            with self.assertRaises(ProviderValidationError):
                validate_media_reference(
                    "external_url",
                    "javascript:alert(1)",
                )

    def test_reachable_external_url_passes_when_checked(self):
        def handler(request):
            return httpx.Response(204, request=request)

        with self.app.app_context():
            self.assertEqual(
                validate_media_reference(
                    "external_url",
                    "https://media.example.test/lychee.mp4",
                    transport=httpx.MockTransport(handler),
                    check_remote=True,
                ),
                "https://media.example.test/lychee.mp4",
            )

    def test_redirect_response_is_accepted_when_checked(self):
        def handler(request):
            return httpx.Response(
                302,
                headers={"Location": "https://cdn.example.test/lychee.mp4"},
                request=request,
            )

        with self.app.app_context():
            self.assertEqual(
                validate_media_reference(
                    "external_url",
                    "https://media.example.test/lychee.mp4",
                    transport=httpx.MockTransport(handler),
                    check_remote=True,
                ),
                "https://media.example.test/lychee.mp4",
            )

    def test_unreachable_external_url_is_rejected(self):
        def handler(request):
            return httpx.Response(404, request=request)

        with self.app.app_context():
            with self.assertRaisesRegex(
                ProviderValidationError,
                "媒体地址不可访问",
            ):
                validate_media_reference(
                    "external_url",
                    "https://media.example.test/missing.mp4",
                    transport=httpx.MockTransport(handler),
                    check_remote=True,
                )

    def test_local_upload_reference_must_use_platform_media_path(self):
        with self.app.app_context():
            self.assertEqual(
                validate_media_reference(
                    "local_upload",
                    "/media/teacher-courses/example.mp4",
                ),
                "/media/teacher-courses/example.mp4",
            )
            with self.assertRaises(ProviderValidationError):
                validate_media_reference(
                    "local_upload",
                    "/tmp/example.mp4",
                )

    def test_local_upload_format_does_not_require_app_context(self):
        self.assertEqual(
            validate_media_reference(
                "local_upload",
                "/media/teacher-courses/example.mp4",
            ),
            "/media/teacher-courses/example.mp4",
        )

    def test_local_upload_rejects_windows_traversal_before_resolution(self):
        invalid_urls = (
            r"/media/teacher-courses/C:\foo.mp4",
            r"/media/teacher-courses/\foo.mp4",
            r"/media/teacher-courses/..\foo.mp4",
            "/media/teacher-courses/../foo.mp4",
            "/media/teacher-courses/./foo.mp4",
            "/media/teacher-courses/sub/foo.mp4",
            r"/media/teacher-courses/C:foo.mp4",
            r"/media/teacher-courses/\\server\share\foo.mp4",
        )

        with self.app.app_context():
            self.app.config["COURSE_MEDIA_ROOT"] = str(
                Path(self.temp_dir.name) / "media-root"
            )
            for media_url in invalid_urls:
                with self.subTest(media_url=media_url):
                    with self.assertRaises(ProviderValidationError):
                        validate_media_reference(
                            "local_upload",
                            media_url,
                        )

    def test_local_upload_cannot_read_outside_course_media_root(self):
        media_root = Path(self.temp_dir.name) / "media-root"
        media_root.mkdir()
        outside_file = Path(self.temp_dir.name) / "outside.mp4"
        outside_file.write_bytes(b"video")

        with self.app.app_context():
            self.app.config["COURSE_MEDIA_ROOT"] = str(media_root)
            with self.assertRaises(ProviderValidationError):
                validate_media_reference(
                    "local_upload",
                    r"/media/teacher-courses/..\outside.mp4",
                    check_remote=True,
                )


if __name__ == "__main__":
    unittest.main()
