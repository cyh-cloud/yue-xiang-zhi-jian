import io
import re
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlsplit
from unittest.mock import patch

import httpx
from werkzeug.datastructures import FileStorage

from app import create_app
from app.teacher_console.errors import ProviderValidationError
from app.teacher_console.media import (
    course_media_path,
    save_course_video,
    validate_media_reference,
)


class TestTeacherMedia(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.media_root = Path(self.temp_dir.name) / "teacher-courses"
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(Path(self.temp_dir.name) / "test.db"),
                "SECRET_KEY": "test-only-secret",
                "COURSE_MEDIA_ROOT": str(self.media_root),
            }
        )
        self.teacher_id = 7

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_local_upload_rejects_oversize_and_non_video(self):
        with self.app.app_context():
            with self.assertRaises(ProviderValidationError):
                save_course_video(
                    FileStorage(
                        stream=io.BytesIO(b"x" * 10),
                        filename="bad.txt",
                    ),
                    self.teacher_id,
                )

            self.app.config["MAX_VIDEO_UPLOAD_BYTES"] = 4
            with self.assertRaisesRegex(
                ProviderValidationError,
                "大小超出限制",
            ):
                save_course_video(
                    FileStorage(
                        stream=io.BytesIO(b"12345"),
                        filename="large.mp4",
                    ),
                    self.teacher_id,
                )

    def test_local_upload_rejects_empty_video(self):
        with self.app.app_context():
            with self.assertRaisesRegex(
                ProviderValidationError,
                "大小超出限制",
            ):
                save_course_video(
                    FileStorage(
                        stream=io.BytesIO(b""),
                        filename="empty.mp4",
                    ),
                    self.teacher_id,
                )

    def test_local_upload_saves_uuid_media_and_is_referenceable(self):
        content = b"video-bytes"

        with self.app.app_context():
            result = save_course_video(
                FileStorage(
                    stream=io.BytesIO(content),
                    filename="Lesson.MP4",
                ),
                self.teacher_id,
            )

            self.assertEqual(result["media_source_type"], "local_upload")
            self.assertEqual(result["size_bytes"], len(content))
            filename = Path(urlsplit(result["media_url"]).path).name
            self.assertRegex(
                filename,
                re.compile(rf"^{self.teacher_id}-[0-9a-f]{{32}}\.mp4$"),
            )
            self.assertEqual(
                course_media_path(filename),
                self.media_root / filename,
            )
            self.assertEqual(course_media_path(filename).read_bytes(), content)
            self.assertEqual(
                validate_media_reference(
                    result["media_source_type"],
                    result["media_url"],
                    check_remote=True,
                ),
                result["media_url"],
            )

    def test_course_media_path_rejects_traversal(self):
        invalid_filenames = (
            "../outside.mp4",
            r"..\outside.mp4",
            r"C:\outside.mp4",
            "sub/outside.mp4",
        )

        with self.app.app_context():
            for filename in invalid_filenames:
                with self.subTest(filename=filename):
                    with self.assertRaises(ProviderValidationError):
                        course_media_path(filename)

    def test_external_url_requires_http_scheme_and_reachable_head(self):
        def reachable_transport(request):
            if request.method != "HEAD":
                return httpx.Response(405, request=request)
            return httpx.Response(204, request=request)

        media_url = "https://media.example.test/a.mp4"
        with self.app.app_context():
            with patch(
                "socket.getaddrinfo",
                return_value=[
                    (2, 1, 6, "", ("93.184.216.34", 443))
                ],
            ):
                self.assertEqual(
                    validate_media_reference(
                        "external_url",
                        media_url,
                        transport=httpx.MockTransport(
                            reachable_transport
                        ),
                        check_remote=True,
                    ),
                    media_url,
                )
            with self.assertRaises(ProviderValidationError):
                validate_media_reference(
                    "external_url",
                    "javascript:alert(1)",
                )

    def test_unreachable_external_url_is_rejected_without_network(self):
        def unreachable_transport(request):
            return httpx.Response(404, request=request)

        with self.app.app_context():
            with self.assertRaisesRegex(
                ProviderValidationError,
                "媒体地址不可访问",
            ):
                validate_media_reference(
                    "external_url",
                    "https://media.example.test/missing.mp4",
                    transport=httpx.MockTransport(unreachable_transport),
                    check_remote=True,
                )


if __name__ == "__main__":
    unittest.main()
