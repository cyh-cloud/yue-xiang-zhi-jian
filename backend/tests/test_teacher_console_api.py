import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from flask import request
from werkzeug.security import generate_password_hash

from app import create_app
from app.db import get_db
from app.teacher_console.errors import (
    ProviderAccessDeniedError,
    ProviderConflictError,
    ProviderNotFoundError,
    ProviderUnavailableError,
    ProviderValidationError,
)


PROTECTED_TEACHER_ROUTES = (
    ("GET", "/api/teacher/courses"),
    ("POST", "/api/teacher/courses"),
    ("GET", "/api/teacher/courses/1"),
    ("PUT", "/api/teacher/courses/1"),
    ("POST", "/api/teacher/courses/1/submit"),
    ("POST", "/api/teacher/courses/1/offline"),
    ("POST", "/api/teacher/courses/1/relist"),
    ("POST", "/api/teacher/uploads/video"),
    ("GET", "/api/teacher/courses/1/quiz"),
    ("POST", "/api/teacher/courses/1/quiz"),
    ("POST", "/api/teacher/courses/1/quiz/generate"),
    ("GET", "/api/teacher/announcements"),
    ("POST", "/api/teacher/announcements"),
    ("GET", "/api/teacher/comments"),
    ("POST", "/api/teacher/comments/comment-1/replies"),
    ("GET", "/api/teacher/dashboard"),
    ("GET", "/api/teacher/reports"),
    ("POST", "/api/teacher/reports"),
    ("GET", "/api/teacher/reports/report-1"),
)


class TestTeacherConsoleApi(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.media_root = Path(self.temp_dir.name) / "teacher-courses"
        self.media_root.mkdir()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(Path(self.temp_dir.name) / "test.db"),
                "COURSE_MEDIA_ROOT": str(self.media_root),
                "SECRET_KEY": "test-only-secret",
                "SESSION_HOURS": 24,
                "SESSION_COOKIE_SECURE": False,
            }
        )
        self.teacher_id = self._create_user("teacher01", "teacher")
        self._create_user("student01", "student")
        self.teacher_client = self._login("teacher01")
        self.student_client = self._login("student01")

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
                    "2026-09-19T00:00:00+08:00",
                    "2026-09-19T00:00:00+08:00",
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

    def test_blueprint_registers_exact_teacher_and_media_routes(self):
        rules = {
            (
                rule.rule,
                tuple(sorted(rule.methods - {"HEAD", "OPTIONS"})),
            )
            for rule in self.app.url_map.iter_rules()
            if rule.rule.startswith("/api/teacher")
            or rule.rule.startswith("/media/teacher-courses")
        }
        expected = {
            ("/api/teacher/courses", ("GET",)),
            ("/api/teacher/courses", ("POST",)),
            ("/api/teacher/courses/<int:course_id>", ("GET",)),
            ("/api/teacher/courses/<int:course_id>", ("PUT",)),
            (
                "/api/teacher/courses/<int:course_id>/submit",
                ("POST",),
            ),
            (
                "/api/teacher/courses/<int:course_id>/offline",
                ("POST",),
            ),
            (
                "/api/teacher/courses/<int:course_id>/relist",
                ("POST",),
            ),
            ("/api/teacher/uploads/video", ("POST",)),
            ("/api/teacher/courses/<int:course_id>/quiz", ("GET",)),
            ("/api/teacher/courses/<int:course_id>/quiz", ("POST",)),
            (
                "/api/teacher/courses/<int:course_id>/quiz/generate",
                ("POST",),
            ),
            ("/api/teacher/announcements", ("GET",)),
            ("/api/teacher/announcements", ("POST",)),
            ("/api/teacher/comments", ("GET",)),
            (
                "/api/teacher/comments/<comment_id>/replies",
                ("POST",),
            ),
            ("/api/teacher/dashboard", ("GET",)),
            ("/api/teacher/reports", ("GET",)),
            ("/api/teacher/reports", ("POST",)),
            ("/api/teacher/reports/<report_id>", ("GET",)),
            (
                "/media/teacher-courses/<path:filename>",
                ("GET",),
            ),
        }

        self.assertEqual(rules, expected)
        self.assertNotIn(
            "/api/teacher/media/<path:filename>",
            {rule.rule for rule in self.app.url_map.iter_rules()},
        )

    def test_every_api_route_rejects_anonymous_and_student_users(self):
        for method, path in PROTECTED_TEACHER_ROUTES:
            for client_name, client in (
                ("anonymous", self.app.test_client()),
                ("student", self.student_client),
            ):
                with self.subTest(
                    method=method,
                    path=path,
                    client=client_name,
                ):
                    response = client.open(path, method=method, json={})

                    self.assertEqual(response.status_code, 401)
                    self.assertEqual(
                        response.get_json()["message"],
                        "未登录或会话已过期",
                    )

    def test_course_create_uses_session_identity(self):
        response = self.teacher_client.post(
            "/api/teacher/courses",
            json={
                "title": "课程",
                "direction": "agriculture",
                "summary": "简介",
                "content_tags": ["荔枝"],
                "duration_seconds": 300,
                "media_source_type": "external_url",
                "media_url": "https://media.example.test/course.mp4",
                "teacher_id": 999,
            },
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            response.get_json()["course"]["teacher_id"],
            self.teacher_id,
        )

    def test_course_payloads_use_session_identity_and_forward_fields(self):
        course = {"id": 1, "status": "draft", "teacher_id": self.teacher_id}

        with patch(
            "app.teacher_console.routes.list_teacher_courses",
            return_value=[course],
        ) as list_courses:
            response = self.teacher_client.get(
                "/api/teacher/courses"
                "?direction=agriculture&status=draft&teacher_id=999"
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_json()["courses"], [course])
            list_courses.assert_called_once_with(
                self.teacher_id,
                direction="agriculture",
                status="draft",
            )

        with patch(
            "app.teacher_console.routes.get_teacher_course",
            return_value=course,
        ) as get_course:
            response = self.teacher_client.get("/api/teacher/courses/1")
            self.assertEqual(response.status_code, 200)
            get_course.assert_called_once_with(self.teacher_id, 1)

        with patch(
            "app.teacher_console.routes.edit_course",
            return_value=course,
        ) as edit:
            response = self.teacher_client.put(
                "/api/teacher/courses/1",
                json={
                    "title": "修订课程",
                    "expected_version": 2,
                    "teacher_id": 999,
                },
            )
            self.assertEqual(response.status_code, 200)
            edit.assert_called_once_with(
                self.teacher_id,
                1,
                2,
                {"title": "修订课程"},
            )

        action_cases = (
            (
                "submit_course_for_review",
                "/api/teacher/courses/1/submit",
            ),
            (
                "set_course_offline",
                "/api/teacher/courses/1/offline",
            ),
            (
                "request_course_relist",
                "/api/teacher/courses/1/relist",
            ),
        )
        for service_name, path in action_cases:
            with self.subTest(service=service_name):
                with patch(
                    f"app.teacher_console.routes.{service_name}",
                    return_value=course,
                ) as action:
                    response = self.teacher_client.post(
                        path,
                        json={"expected_version": 3, "teacher_id": 999},
                    )
                    self.assertEqual(response.status_code, 200)
                    action.assert_called_once_with(self.teacher_id, 1, 3)

    def test_quiz_announcement_comment_dashboard_and_report_routes(self):
        quiz = {
            "enabled": True,
            "scoring_rule": "all_correct",
            "questions": [],
        }
        with patch(
            "app.teacher_console.routes.get_teacher_course_quiz",
            return_value=quiz,
        ) as get_quiz:
            response = self.teacher_client.get(
                "/api/teacher/courses/1/quiz"
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_json()["quiz"], quiz)
            get_quiz.assert_called_once_with(self.teacher_id, 1)

        with patch(
            "app.teacher_console.routes.save_course_quiz",
            return_value=quiz,
        ) as save_quiz:
            response = self.teacher_client.post(
                "/api/teacher/courses/1/quiz",
                json={
                    "expected_version": 4,
                    "enabled": True,
                    "questions": [],
                    "scoring_rule": "all_correct",
                    "teacher_id": 999,
                },
            )
            self.assertEqual(response.status_code, 200)
            save_quiz.assert_called_once_with(
                self.teacher_id,
                1,
                4,
                True,
                [],
                "all_correct",
            )

        generated = {"questions": [{"id": "q1"}]}
        with patch(
            "app.teacher_console.routes.generate_course_quiz",
            return_value=generated,
        ) as generate_quiz:
            response = self.teacher_client.post(
                "/api/teacher/courses/1/quiz/generate",
                json={
                    "summary": "课程简介",
                    "direction": "agriculture",
                    "teacher_id": 999,
                },
            )
            self.assertEqual(response.status_code, 200)
            generate_quiz.assert_called_once_with(
                self.teacher_id,
                1,
                summary="课程简介",
                direction="agriculture",
            )

        announcement = {"announcement_id": "teaching-1"}
        with patch(
            "app.teacher_console.routes.list_teaching_announcements",
            return_value=[announcement],
        ) as list_announcements:
            response = self.teacher_client.get(
                "/api/teacher/announcements?teacher_id=999"
            )
            self.assertEqual(response.status_code, 200)
            list_announcements.assert_called_once_with(self.teacher_id)

        with patch(
            "app.teacher_console.routes.publish_teaching_announcement",
            return_value=announcement,
        ) as publish_announcement:
            response = self.teacher_client.post(
                "/api/teacher/announcements",
                json={
                    "title": "课程安排",
                    "body": "本周调整",
                    "teacher_id": 999,
                },
            )
            self.assertEqual(response.status_code, 201)
            publish_announcement.assert_called_once_with(
                self.teacher_id,
                "课程安排",
                "本周调整",
            )

        comment = {"comment_id": "comment-1"}
        with patch(
            "app.teacher_console.routes.list_teacher_comments",
            return_value=[comment],
        ) as list_comments:
            response = self.teacher_client.get(
                "/api/teacher/comments"
                "?content_type=course_video&content_id=1&teacher_id=999"
            )
            self.assertEqual(response.status_code, 200)
            list_comments.assert_called_once_with(
                self.teacher_id,
                content_type="course_video",
                content_id="1",
            )

        with patch(
            "app.teacher_console.routes.reply_to_comment",
            return_value=comment,
        ) as reply:
            response = self.teacher_client.post(
                "/api/teacher/comments/comment-1/replies",
                json={"body": "收到", "teacher_id": 999},
            )
            self.assertEqual(response.status_code, 201)
            reply.assert_called_once_with(
                self.teacher_id,
                "comment-1",
                "收到",
            )

        dashboard = {"student_total": 2}
        with patch(
            "app.teacher_console.routes.build_teacher_dashboard",
            return_value=dashboard,
        ) as build_dashboard:
            response = self.teacher_client.get(
                "/api/teacher/dashboard?teacher_id=999"
            )
            self.assertEqual(response.status_code, 200)
            build_dashboard.assert_called_once_with(self.teacher_id)

        report = {"report_id": "report-1"}
        with patch(
            "app.teacher_console.routes.list_teacher_reports",
            return_value=[report],
        ) as list_reports:
            response = self.teacher_client.get(
                "/api/teacher/reports?teacher_id=999"
            )
            self.assertEqual(response.status_code, 200)
            list_reports.assert_called_once_with(self.teacher_id)

        with patch(
            "app.teacher_console.routes.generate_teacher_report",
            return_value=report,
        ) as generate_report:
            response = self.teacher_client.post(
                "/api/teacher/reports",
                json={"teacher_id": 999},
            )
            self.assertEqual(response.status_code, 201)
            generate_report.assert_called_once_with(self.teacher_id)

        with patch(
            "app.teacher_console.routes.get_teacher_report",
            return_value=report,
        ) as get_report:
            response = self.teacher_client.get(
                "/api/teacher/reports/report-1"
            )
            self.assertEqual(response.status_code, 200)
            get_report.assert_called_once_with(
                self.teacher_id,
                "report-1",
            )

    def test_upload_accepts_multipart_and_sets_route_limit(self):
        captured = {}

        def fake_save(file_storage, teacher_id):
            captured["filename"] = file_storage.filename
            captured["content"] = file_storage.read()
            captured["teacher_id"] = teacher_id
            captured["max_content_length"] = request.max_content_length
            return {
                "media_source_type": "local_upload",
                "media_url": "/media/teacher-courses/course.mp4",
                "size_bytes": 5,
            }

        with patch(
            "app.teacher_console.routes.save_course_video",
            side_effect=fake_save,
        ):
            response = self.teacher_client.post(
                "/api/teacher/uploads/video",
                data={
                    "file": (io.BytesIO(b"video"), "course.mp4"),
                    "teacher_id": "999",
                },
                content_type="multipart/form-data",
            )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            response.get_json()["media"]["media_source_type"],
            "local_upload",
        )
        self.assertEqual(
            captured,
            {
                "filename": "course.mp4",
                "content": b"video",
                "teacher_id": self.teacher_id,
                "max_content_length": self.app.config[
                    "MAX_VIDEO_UPLOAD_BYTES"
                ],
            },
        )

    def test_public_media_route_serves_approved_course_files(self):
        media_path = self.media_root / "course.mp4"
        media_path.write_bytes(b"video")

        response = self.app.test_client().get(
            "/media/teacher-courses/course.mp4"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, b"video")
        self.assertEqual(response.content_type, "video/mp4")
        response.close()

    def test_provider_errors_map_to_required_http_statuses(self):
        cases = (
            (
                ProviderValidationError(
                    "校验失败",
                    code="validation",
                    details={"field": "title"},
                ),
                400,
            ),
            (
                ProviderNotFoundError(
                    "不存在",
                    code="not_found",
                    details={"course_id": 1},
                ),
                404,
            ),
            (
                ProviderConflictError(
                    "状态冲突",
                    code="conflict",
                    details={"course_id": 1},
                ),
                409,
            ),
            (
                ProviderAccessDeniedError(
                    "无权访问",
                    code="access_denied",
                    details={"course_id": 1},
                ),
                403,
            ),
            (
                ProviderUnavailableError(
                    "AI 服务暂时不可用",
                    code="ai_unavailable",
                    details={},
                ),
                503,
            ),
        )

        for error, expected_status in cases:
            with self.subTest(status=expected_status):
                with patch(
                    "app.teacher_console.routes.list_teacher_courses",
                    side_effect=error,
                ):
                    response = self.teacher_client.get(
                        "/api/teacher/courses"
                    )

                self.assertEqual(response.status_code, expected_status)
                self.assertEqual(
                    response.get_json()["message"],
                    error.message,
                )
                self.assertEqual(
                    response.get_json()["errors"],
                    error.details,
                )

    def test_json_routes_reject_non_object_bodies(self):
        response = self.teacher_client.post(
            "/api/teacher/courses",
            json=["not", "an", "object"],
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.get_json(),
            {
                "success": False,
                "message": "请求体格式不正确",
                "errors": {"body": "请求体必须是 JSON 对象"},
            },
        )


if __name__ == "__main__":
    unittest.main()
