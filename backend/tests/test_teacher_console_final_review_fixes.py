import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import httpx
from werkzeug.security import generate_password_hash

from app import create_app
from app.agri_skills.providers import set_course_provider
from app.config import build_config
from app.content_review import set_content_review_provider
from app.db import get_db
from app.handcraft_inheritance.providers import (
    set_teaching_video_provider,
)
from app.teacher_console.comments import reply_to_comment
from app.teacher_console.course_service import (
    create_teacher_course,
    list_teacher_courses,
)
from app.teacher_console.dashboard import build_teacher_dashboard
from app.teacher_console.errors import (
    ProviderValidationError,
)
from app.teacher_console.quiz import generate_course_quiz


class FakeReviewProvider:
    def __init__(self):
        self.records = {}

    def set_status(
        self,
        course_id,
        review_status,
        *,
        updated_at="2026-09-19T10:00:00+08:00",
        rejection_opinion=None,
    ):
        self.records[str(course_id)] = {
            "content_type": "course_video",
            "content_id": str(course_id),
            "review_status": review_status,
            "version": 1,
            "rejection_opinion": rejection_opinion,
            "published_at": (
                "2026-09-19T10:00:00+08:00"
                if review_status == "approved"
                else None
            ),
            "created_at": updated_at,
            "updated_at": updated_at,
        }

    def get_review_status(self, *, content_type, content_id):
        record = self.records.get(str(content_id))
        return dict(record) if record is not None else None


class StaticCourseProvider:
    def __init__(self, visible_ids):
        self.visible_ids = set(visible_ids)

    def list_published_courses(self, student_id, direction):
        return [self.get_course(course_id) for course_id in self.visible_ids]

    def get_course(self, course_id):
        if int(course_id) not in self.visible_ids:
            return None
        return {
            "id": int(course_id),
            "title": f"课程 {course_id}",
            "direction": "agriculture",
            "status": "published",
            "summary": "课程简介",
            "teacher_name": "教师",
            "published_at": "2026-09-19T10:00:00+08:00",
            "duration_seconds": 300,
            "media_url": "https://media.example.test/a.mp4",
            "tag_ids": [],
            "content_tags": [],
        }

    def get_quiz(self, course_id):
        return None


class StaticTeachingVideoProvider:
    def get_video(self, video_id):
        if video_id != "video-visible":
            return None
        return {
            "video_id": video_id,
            "craft_key": "guangxiu",
            "review_status": "approved",
            "source_available": True,
        }


class TeacherReviewFixTestCase(unittest.TestCase):
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

    def create_user(self, username, role):
        now = "2026-09-19T09:00:00+08:00"
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
                    now,
                    now,
                ),
            )
            get_db().commit()
        return int(cursor.lastrowid)

    def login(self, username):
        client = self.app.test_client()
        response = client.post(
            "/api/auth/login",
            json={"username": username, "password": "password8"},
        )
        self.assertEqual(response.status_code, 200)
        return client


class TestTeacherCourseListProviderHydration(TeacherReviewFixTestCase):
    def setUp(self):
        super().setUp()
        self.create_user("teacher01", "teacher")
        self.review = FakeReviewProvider()
        set_content_review_provider(self.app, self.review)

    def create_pending_course(self, title, updated_at):
        with self.app.app_context():
            course = create_teacher_course(
                1,
                {
                    "title": title,
                    "direction": "agriculture",
                    "summary": "课程简介",
                    "content_tags": [],
                    "duration_seconds": 300,
                    "media_source_type": "external_url",
                    "media_url": "https://media.example.test/a.mp4",
                },
            )
            db = get_db()
            db.execute(
                """
                UPDATE courses
                SET status = 'pending', updated_at = ?
                WHERE id = ?
                """,
                (updated_at, course["id"]),
            )
            db.commit()
            return course

    def test_list_projects_provider_status_opinion_and_time(self):
        rejected = self.create_pending_course(
            "驳回课程",
            "2026-09-19T09:00:00+08:00",
        )
        approved = self.create_pending_course(
            "已上架课程",
            "2026-09-19T08:00:00+08:00",
        )
        pending = self.create_pending_course(
            "待审核课程",
            "2026-09-19T07:00:00+08:00",
        )
        self.review.set_status(
            rejected["id"],
            "rejected",
            updated_at="2026-09-19T04:00:00+08:00",
            rejection_opinion="请补充知识点",
        )
        self.review.set_status(
            approved["id"],
            "approved",
            updated_at="2026-09-18T22:00:00+00:00",
        )
        self.review.set_status(
            pending["id"],
            "pending",
            updated_at="2026-09-18T18:00:00+00:00",
        )

        with self.app.app_context():
            courses = list_teacher_courses(1)
            rejected_only = list_teacher_courses(1, status="rejected")

        self.assertEqual(
            [course["id"] for course in courses],
            [approved["id"], rejected["id"], pending["id"]],
        )
        self.assertEqual(
            [course["status"] for course in courses],
            ["published", "rejected", "pending"],
        )
        self.assertEqual(
            [course["id"] for course in rejected_only],
            [rejected["id"]],
        )
        self.assertEqual(
            courses[1]["rejection_opinion"],
            "请补充知识点",
        )
        self.assertEqual(
            courses[1]["review_updated_at"],
            "2026-09-19T04:00:00+08:00",
        )

    def test_provider_unknown_status_is_rejected(self):
        course = self.create_pending_course(
            "非法状态课程",
            "2026-09-19T09:00:00+08:00",
        )
        self.review.set_status(course["id"], "offline")

        with self.app.app_context():
            with self.assertRaisesRegex(
                ProviderValidationError,
                "审核服务返回无效数据",
            ):
                list_teacher_courses(1)


class TestQuizInputValidation(TeacherReviewFixTestCase):
    def setUp(self):
        super().setUp()
        self.create_user("teacher01", "teacher")
        self.ai = Mock()
        from app.agri_skills.ai_client import set_ai_client

        set_ai_client(self.app, self.ai)
        with self.app.app_context():
            self.course = create_teacher_course(
                1,
                {
                    "title": "课程",
                    "direction": "agriculture",
                    "summary": "课程简介",
                    "content_tags": [],
                    "duration_seconds": 300,
                    "media_source_type": "external_url",
                    "media_url": "https://media.example.test/a.mp4",
                },
            )

    def test_blank_summary_and_invalid_direction_do_not_call_ai(self):
        invalid_inputs = (
            {"summary": "   ", "direction": "agriculture"},
            {"summary": "课程简介", "direction": "finance"},
            {"summary": None, "direction": "agriculture"},
            {"summary": "课程简介", "direction": None},
        )
        for changes in invalid_inputs:
            with self.subTest(changes=changes):
                with self.app.app_context():
                    with self.assertRaises(ProviderValidationError):
                        generate_course_quiz(
                            1,
                            self.course["id"],
                            **changes,
                        )
        self.ai.complete_json.assert_not_called()


class TestDashboardUsesCourseProviderSlot(TeacherReviewFixTestCase):
    def test_quiz_stats_use_registered_provider_visibility(self):
        self.create_user("teacher01", "teacher")
        student_id = self.create_user("student01", "student")
        set_course_provider(self.app, StaticCourseProvider({3}))
        now = "2026-09-19T10:00:00+08:00"
        with self.app.app_context():
            db = get_db()
            db.executemany(
                """
                INSERT INTO courses (
                    id, title, direction, status, duration_seconds,
                    media_url, published_at, summary, teacher_name,
                    teacher_id, version, media_source_type,
                    content_tags_json, created_at, updated_at
                )
                VALUES (
                    ?, ?, 'agriculture', 'pending', 300,
                    'https://media.example.test/a.mp4', NULL, '简介',
                    '教师', 1, 1, 'external_url', '[]', ?, ?
                )
                """,
                (
                    (2, "不可见课程", now, now),
                    (3, "可见课程", now, now),
                ),
            )
            db.execute(
                """
                INSERT INTO agri_course_quiz_attempts (
                    user_id, course_id, answers_json, result_json, score,
                    is_formal, created_at
                )
                VALUES (?, 2, '{}', '{}', 20, 1, ?)
                """,
                (student_id, now),
            )
            db.execute(
                """
                INSERT INTO agri_course_quiz_attempts (
                    user_id, course_id, answers_json, result_json, score,
                    is_formal, created_at
                )
                VALUES (?, 3, '{}', '{}', 90, 1, ?)
                """,
                (student_id, now),
            )
            db.commit()

            dashboard = build_teacher_dashboard(1)

        self.assertEqual(dashboard["quiz_attempt_count"], 1)
        self.assertEqual(dashboard["quiz_average_score"], 90.0)


class TestTeacherReportScope(TeacherReviewFixTestCase):
    def test_risk_activity_uses_teacher_visible_course_set(self):
        self.create_user("teacher01", "teacher")
        self.create_user("student01", "student")
        self.create_user("student02", "student")
        self.create_user("other_teacher", "teacher")
        from app.agri_skills.ai_client import set_ai_client

        ai = Mock()
        ai.complete_json.return_value = {
            "progress_analysis": "整体进度稳定",
            "direction_comparison": "农业方向领先",
            "risk_warning": "1 名学员长期零进度",
        }
        set_ai_client(self.app, ai)
        self.review = FakeReviewProvider()
        self.review.set_status(10, "approved")
        set_content_review_provider(self.app, self.review)
        now = "2026-09-19T10:00:00+08:00"
        with self.app.app_context():
            db = get_db()
            db.execute(
                """
                INSERT INTO student_profiles (
                    user_id, contact, learning_direction, updated_at
                )
                VALUES
                    (2, '13800000002', 'agriculture', ?),
                    (3, '13800000003', 'ecommerce', ?)
                """,
                (now, now),
            )
            db.execute(
                """
                INSERT INTO courses (
                    id, title, direction, status, duration_seconds,
                    media_url, published_at, summary, teacher_name,
                    teacher_id, version, media_source_type,
                    content_tags_json, created_at, updated_at
                )
                VALUES (
                    10, '教师可见课程', 'agriculture', 'pending', 300,
                    'https://media.example.test/a.mp4', NULL, '简介',
                    '教师', 1, 1, 'external_url', '[]', ?, ?
                )
                """,
                (now, now),
            )
            db.execute(
                """
                INSERT INTO agri_course_progress (
                    user_id, course_id, duration_seconds,
                    furthest_position_seconds, resume_position_seconds,
                    progress_percent, watched_seconds, completed_at,
                    last_viewed_at, updated_at
                )
                VALUES (2, 10, 300, 0, 0, 20, 0, NULL, ?, ?)
                """,
                (now, now),
            )
            db.execute(
                """
                INSERT INTO ecommerce_live_script_versions (
                    user_id, product_name, selling_points_json, price_text,
                    style, script_json, is_current, created_at
                )
                VALUES (
                    3, '荔枝', '[]', '10 元', 'enthusiastic', '{}', 1, ?
                )
                """,
                (now,),
            )
            db.commit()

            from app.teacher_console.reports import generate_teacher_report

            report = generate_teacher_report(1)

        risk = report["stats_snapshot"]["risk_summary"]
        self.assertEqual(risk["student_count"], 2)
        self.assertEqual(risk["at_risk_count"], 1)
        self.assertEqual(
            risk["directions"]["ecommerce"]["at_risk_count"],
            1,
        )


class TestVideoUploadConfig(unittest.TestCase):
    def test_uses_environment_limit_with_default(self):
        with patch.dict("os.environ", {}, clear=True):
            config = build_config()
        self.assertEqual(
            config["MAX_VIDEO_UPLOAD_BYTES"],
            500 * 1024 * 1024,
        )

        with patch.dict(
            "os.environ",
            {"MAX_VIDEO_UPLOAD_BYTES": "12"},
        ):
            config = build_config()
        self.assertEqual(config["MAX_VIDEO_UPLOAD_BYTES"], 12)

        with patch.dict(
            "os.environ",
            {"MAX_VIDEO_UPLOAD_BYTES": "0"},
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "MAX_VIDEO_UPLOAD_BYTES must be a positive integer",
            ):
                build_config()


class TestExternalMediaEgress(unittest.TestCase):
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

    def test_public_ip_url_is_allowed_after_validation(self):
        requests = []

        def handler(request):
            requests.append(request)
            return httpx.Response(204, request=request)

        with self.app.app_context():
            from app.teacher_console.media import validate_media_reference

            self.assertEqual(
                validate_media_reference(
                    "external_url",
                    "https://93.184.216.34/video.mp4",
                    transport=httpx.MockTransport(handler),
                    check_remote=True,
                ),
                "https://93.184.216.34/video.mp4",
            )
        self.assertEqual(len(requests), 1)

    def test_private_loopback_reserved_and_unresolved_targets_block_head(self):
        requests = []

        def handler(request):
            requests.append(request)
            return httpx.Response(204, request=request)

        blocked_urls = (
            "https://127.0.0.1/video.mp4",
            "https://10.0.0.1/video.mp4",
            "https://169.254.0.1/video.mp4",
            "https://192.0.2.10/video.mp4",
            "https://100.64.0.1/video.mp4",
        )
        with self.app.app_context():
            from app.teacher_console.media import validate_media_reference

            for media_url in blocked_urls:
                with self.subTest(media_url=media_url):
                    with self.assertRaises(ProviderValidationError):
                        validate_media_reference(
                            "external_url",
                            media_url,
                            transport=httpx.MockTransport(handler),
                            check_remote=True,
                        )
            with patch(
                "socket.getaddrinfo",
                side_effect=OSError("unresolved"),
            ):
                with self.assertRaises(ProviderValidationError):
                    validate_media_reference(
                        "external_url",
                        "https://media.example.test/video.mp4",
                        transport=httpx.MockTransport(handler),
                        check_remote=True,
                    )
        self.assertEqual(requests, [])

    def test_resolved_non_public_address_blocks_head(self):
        requests = []

        def handler(request):
            requests.append(request)
            return httpx.Response(204, request=request)

        with self.app.app_context():
            from app.teacher_console.media import validate_media_reference

            with patch(
                "socket.getaddrinfo",
                return_value=[(2, 1, 6, "", ("172.16.0.2", 443))],
            ):
                with self.assertRaises(ProviderValidationError):
                    validate_media_reference(
                        "external_url",
                        "https://media.example.test/video.mp4",
                        transport=httpx.MockTransport(handler),
                        check_remote=True,
                    )
        self.assertEqual(requests, [])


class TestLearnerContentComments(TeacherReviewFixTestCase):
    def setUp(self):
        super().setUp()
        self.teacher_id = self.create_user("teacher01", "teacher")
        self.student_id = self.create_user("student01", "student")
        self.teacher_client = self.login("teacher01")
        self.student_client = self.login("student01")
        set_course_provider(self.app, StaticCourseProvider({101}))
        with self.app.app_context():
            get_db().execute(
                """
                INSERT INTO courses (
                    id, title, direction, status, duration_seconds,
                    media_url, published_at, summary, teacher_name,
                    teacher_id, version, media_source_type,
                    content_tags_json, created_at, updated_at
                )
                VALUES (
                    101, '课程', 'agriculture', 'published', 300,
                    'https://media.example.test/a.mp4',
                    '2026-09-19T10:00:00+08:00', '课程简介', '教师',
                    ?, 1, 'external_url', '[]',
                    '2026-09-19T09:00:00+08:00',
                    '2026-09-19T09:00:00+08:00'
                )
                """,
                (self.teacher_id,),
            )
            get_db().commit()
        set_teaching_video_provider(
            self.app,
            StaticTeachingVideoProvider(),
        )

    def test_course_comment_creation_visibility_and_teacher_replies(self):
        response = self.student_client.post(
            "/api/agri-skills/courses/101/comments",
            json={"body": "  如何保果？  "},
        )
        self.assertEqual(response.status_code, 201)
        comment = response.get_json()["comment"]
        self.assertEqual(comment["body"], "如何保果？")
        self.assertFalse(comment["is_teacher_reply"])
        self.assertEqual(comment["content_id"], "101")

        with self.app.app_context():
            first_reply = reply_to_comment(
                self.teacher_id,
                comment["comment_id"],
                "先控梢再补钾",
            )
            second_reply = reply_to_comment(
                self.teacher_id,
                first_reply["comment_id"],
                "两周后再复核一次",
            )

        listed = self.student_client.get(
            "/api/agri-skills/courses/101/comments"
        )
        self.assertEqual(listed.status_code, 200)
        comments = listed.get_json()["comments"]
        self.assertEqual(
            [item["comment_id"] for item in comments],
            [
                comment["comment_id"],
                first_reply["comment_id"],
                second_reply["comment_id"],
            ],
        )
        self.assertTrue(comments[1]["is_teacher_reply"])
        self.assertTrue(comments[2]["is_teacher_reply"])

        denied = self.teacher_client.get(
            "/api/agri-skills/courses/101/comments"
        )
        self.assertEqual(denied.status_code, 401)

    def test_course_comment_rejects_invisible_target(self):
        response = self.student_client.post(
            "/api/agri-skills/courses/999/comments",
            json={"body": "不可见课程"},
        )
        self.assertEqual(response.status_code, 409)

    def test_heritage_video_comment_creation_and_teacher_reply(self):
        response = self.student_client.post(
            "/api/handcraft-inheritance/videos/video-visible/comments",
            json={"body": "如何起针？"},
        )
        self.assertEqual(response.status_code, 201)
        comment = response.get_json()["comment"]

        with self.app.app_context():
            reply = reply_to_comment(
                self.teacher_id,
                comment["comment_id"],
                "先固定绣线再起针",
            )

        listed = self.student_client.get(
            "/api/handcraft-inheritance/videos/video-visible/comments"
        )
        self.assertEqual(listed.status_code, 200)
        comments = listed.get_json()["comments"]
        self.assertEqual(
            [item["comment_id"] for item in comments],
            [comment["comment_id"], reply["comment_id"]],
        )
        self.assertTrue(comments[1]["is_teacher_reply"])


if __name__ == "__main__":
    unittest.main()
