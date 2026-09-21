from __future__ import annotations

import ast
import json
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from app import create_app
from app.admin_console import moderation
from app.admin_console.errors import (
    ProviderNotFoundError,
    ProviderValidationError,
)
from app.admin_console.moderation import (
    delete_comment,
    list_moderation_comments,
    processed_comment_count,
    list_feedback,
    list_reports,
    processed_report_count,
    resolve_report,
    submit_feedback,
    update_feedback,
)
from app.admin_console.providers import get_feedback_intake_provider
from app.agri_skills.providers import set_course_provider
from app.db import get_db
from app.teacher_console.comments import list_content_comments


# Every table 02 can write a delivery row into. A silent moderation action
# must leave all of them untouched.
NOTIFICATION_TABLES = (
    "admin_notification_outbox",
    "enterprise_notification_outbox",
    "fulfillment_notification_outbox",
    "handcraft_notification_outbox",
    "points_notification_outbox",
    "system_notifications",
    "teacher_announcement_delivery_events",
)


class StaticCourseProvider:
    """Serves the two fixture courses to 08's `_require_target_visible`.

    `create_app` installs 08's teacher-scoped course provider, which only
    answers for a teacher's own courses, so the student-side comment read
    would refuse the fixture course without this replacement. The provider
    slot is a test seam and is never written to from `moderation.py`.
    """

    def __init__(self, courses):
        self.courses = {
            int(course_id): dict(course)
            for course_id, course in courses.items()
        }

    def get_course(self, course_id):
        course = self.courses.get(int(course_id))
        return dict(course) if course is not None else None


class AdminModerationTests(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "PROPAGATE_EXCEPTIONS": False,
                "DATABASE_PATH": str(
                    Path(self.temp_dir.name) / "test.db"
                ),
                "SECRET_KEY": "test-only-secret",
                "SESSION_HOURS": 24,
                "SESSION_COOKIE_SECURE": False,
            }
        )
        self.user_ids: dict[str, int] = {}
        self.super_admin = self._login(
            "moderation-super-admin",
            "super_admin",
            "超级管理员",
        )
        self.admin = self._login("moderation-admin", "admin", "普通管理员")
        self.student = self._login("moderation-student", "student", "学员甲")
        self.teacher = self._login("moderation-teacher", "teacher", "教师甲")

        self.course_id = 7001
        self.other_course_id = 7002
        self._create_course(self.course_id, "农业技术基础")
        self._create_course(self.other_course_id, "病虫害防治")

        self.comment_id = "comment-course-b"
        self._create_comment(
            "comment-old",
            "course_video",
            str(self.course_id),
            self.student_id,
            "较早发布的正常评论",
            "2026-09-19T09:00:00+08:00",
        )
        self._create_comment(
            "comment-course-a",
            "course_video",
            str(self.course_id),
            self.student_id,
            "课程讲解很清楚，收获很多",
            "2026-09-20T10:00:00+08:00",
        )
        self._create_comment(
            self.comment_id,
            "course_video",
            str(self.course_id),
            self.student_id,
            "这条包含违规内容需要巡查处理",
            "2026-09-20T10:05:00+08:00",
        )
        self._create_comment(
            "comment-video-c",
            "handcraft_teaching_video",
            "video-approved",
            self.teacher_id,
            "非遗教学视频的补充说明",
            "2026-09-20T10:10:00+08:00",
        )
        self._create_comment(
            "comment-hidden",
            "course_video",
            str(self.course_id),
            self.student_id,
            "已经被隐藏的历史评论",
            "2026-09-20T09:00:00+08:00",
            is_visible=0,
        )
        self._create_comment(
            "comment-other-course",
            "course_video",
            str(self.other_course_id),
            self.student_id,
            "其他课程下的评论",
            "2026-09-20T10:15:00+08:00",
        )

        # One pending report on the comment the confirmed-resolution tests
        # hide. The two already-resolved reports live in
        # `_seed_resolved_reports` instead of here, so a test that counts
        # resolved reports starts from zero.
        self.report_id = "report-pending-course-b"
        self._create_report(
            self.report_id,
            self.comment_id,
            self.student_id,
            "含有违规内容",
            "2026-09-20T11:00:00+08:00",
        )

        self.feedback_id = "feedback-pending-1"
        self._create_feedback(
            self.feedback_id,
            self.student_id,
            "建议增加夜校课程",
            "2026-09-20T13:00:00+08:00",
        )
        self._create_feedback(
            "feedback-processed-2",
            self.student_id,
            "希望能按产地筛选农产品",
            "2026-09-20T13:05:00+08:00",
            status="processed",
        )
        self._create_feedback(
            "feedback-closed-3",
            self.teacher_id,
            "重复提交的反馈",
            "2026-09-20T13:10:00+08:00",
            status="closed",
        )

        set_course_provider(
            self.app,
            StaticCourseProvider(
                {
                    self.course_id: self._course_payload(
                        self.course_id, "农业技术基础"
                    ),
                    self.other_course_id: self._course_payload(
                        self.other_course_id, "病虫害防治"
                    ),
                }
            ),
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def _create_user(self, username: str, role: str, name: str) -> int:
        from werkzeug.security import generate_password_hash

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
                    name,
                    role,
                    "2026-09-21T09:00:00+08:00",
                    "2026-09-21T09:00:00+08:00",
                ),
            )
            user_id = int(cursor.lastrowid)
            get_db().commit()
        return user_id

    def _login(self, username: str, role: str, name: str):
        self.user_ids[username] = self._create_user(username, role, name)
        client = self.app.test_client()
        response = client.post(
            "/api/auth/login",
            json={"username": username, "password": "password8"},
        )
        self.assertEqual(response.status_code, 200)
        return client

    @property
    def student_id(self) -> int:
        return self.user_ids["moderation-student"]

    @property
    def admin_id(self) -> int:
        return self.user_ids["moderation-admin"]

    @property
    def super_admin_id(self) -> int:
        return self.user_ids["moderation-super-admin"]

    @property
    def teacher_id(self) -> int:
        return self.user_ids["moderation-teacher"]

    def _create_course(self, course_id: int, title: str) -> None:
        now = "2026-09-19T09:00:00+08:00"
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
                    ?, ?, 'agriculture', 'published', 300,
                    'https://media.example.test/course.mp4', ?, ?,
                    '教师', ?, 1, 'external_url', '[]', ?, ?
                )
                """,
                (
                    course_id,
                    title,
                    now,
                    f"{title}简介",
                    self.teacher_id,
                    now,
                    now,
                ),
            )
            get_db().commit()

    def _create_comment(
        self,
        comment_id: str,
        content_type: str,
        content_id: str,
        author_id: int,
        body: str,
        created_at: str,
        *,
        is_visible: int = 1,
    ) -> None:
        with self.app.app_context():
            get_db().execute(
                """
                INSERT INTO content_comments (
                    comment_id, content_type, content_id, author_id,
                    body, is_teacher_reply, is_visible, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?)
                """,
                (
                    comment_id,
                    content_type,
                    content_id,
                    author_id,
                    body,
            is_visible,
                    created_at,
                    created_at,
                ),
        )
            get_db().commit()

    def _create_report(
        self,
        report_id: str,
        comment_id: str,
        reporter_id: int,
        reason: str,
        created_at: str,
        *,
        status: str = "pending",
        resolver_id: int | None = None,
        result: str | None = None,
        resolved_at: str | None = None,
    ) -> None:
        with self.app.app_context():
            get_db().execute(
                """
                INSERT INTO comment_reports (
                    report_id, comment_id, reporter_id, reason, status,
                    resolver_id, result, created_at, updated_at, resolved_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    report_id,
                    comment_id,
                    reporter_id,
                    reason,
                    status,
                    resolver_id,
                    result,
                    created_at,
                    created_at,
                    resolved_at,
                ),
            )
            get_db().commit()

    def _create_feedback(
        self,
        feedback_id: str,
        submitter_id: int,
        body: str,
        created_at: str,
        *,
        status: str = "pending",
    ) -> None:
        with self.app.app_context():
            get_db().execute(
                """
                INSERT INTO feedback_records (
                    feedback_id, submitter_id, body, status, idempotency_key,
                    handler_id, result, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, NULL, NULL, ?, ?)
                """,
                (
                    feedback_id,
                    submitter_id,
                    body,
                    status,
                    f"{feedback_id}-key",
                    created_at,
                    created_at,
                ),
            )
            get_db().commit()

    def _course_payload(self, course_id: int, title: str) -> dict:
        return {
            "id": course_id,
            "title": title,
            "direction": "agriculture",
            "status": "published",
            "summary": f"{title}简介",
            "teacher_name": "教师甲",
            "published_at": "2026-09-19T09:00:00+08:00",
            "duration_seconds": 300,
            "media_url": "https://media.example.test/course.mp4",
            "tag_ids": [],
            "content_tags": [],
        }

    def _seed_resolved_reports(self) -> None:
        """Add one rejected and one confirmed report to the pending one.

        The queue tests need all three states to narrow by, and the count
        tests need to start from a single pending report, so the two
        already-resolved rows are created on demand.
        """
        self._create_report(
            "report-rejected-course-a",
            "comment-course-a",
            self.student_id,
            "与课程无关的刷屏",
            "2026-09-20T11:05:00+08:00",
            status="rejected",
            resolver_id=self.admin_id,
            result="不属于违规内容",
            resolved_at="2026-09-20T12:00:00+08:00",
        )
        self._create_report(
            "report-confirmed-old",
            "comment-old",
            self.teacher_id,
            "抄袭他人课程笔记",
            "2026-09-20T11:10:00+08:00",
            status="confirmed",
            resolver_id=self.super_admin_id,
            result="已核实并删除",
            resolved_at="2026-09-20T12:05:00+08:00",
        )

    def _items(self, **query) -> list[dict]:
        response = self.admin.get("/api/admin/comments", query_string=query)
        self.assertEqual(response.status_code, 200, response.get_json())
        return response.get_json()["items"]

    def reports(self, **query) -> list[dict]:
        response = self.admin.get("/api/admin/reports", query_string=query)
        self.assertEqual(response.status_code, 200, response.get_json())
        return response.get_json()["items"]

    def feedback_items(self, **query) -> list[dict]:
        response = self.admin.get("/api/admin/feedback", query_string=query)
        self.assertEqual(response.status_code, 200, response.get_json())
        return response.get_json()["items"]

    def resolve(self, report_id: str, **payload):
        return self.admin.post(
            f"/api/admin/reports/{report_id}/resolve",
            json=payload,
        )

    def patch_feedback(self, feedback_id: str, **payload):
        return self.admin.patch(
            f"/api/admin/feedback/{feedback_id}",
            json=payload,
        )

    def report_processed_count(self) -> int:
        with self.app.app_context():
            return processed_report_count()

    def feedback_row_count(self) -> int:
        with self.app.app_context():
            return int(
                get_db()
                .execute("SELECT COUNT(*) AS count FROM feedback_records")
                .fetchone()["count"]
            )

    def student_visible_comment_ids(self) -> list[str]:
        response = self.student.get(
            f"/api/agri-skills/courses/{self.course_id}/comments"
        )
        self.assertEqual(response.status_code, 200)
        return [
            item["comment_id"] for item in response.get_json()["comments"]
        ]

    def notification_count(self, user_id: int) -> int:
        with self.app.app_context():
            return int(
                get_db()
                .execute(
                    """
                    SELECT COUNT(*) AS count
                    FROM system_notifications
                    WHERE recipient_id = ?
                    """,
                    (user_id,),
                )
                .fetchone()["count"]
            )

    def notification_row_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        with self.app.app_context():
            for table in NOTIFICATION_TABLES:
                counts[table] = int(
                    get_db()
                    .execute(f"SELECT COUNT(*) AS count FROM {table}")
                    .fetchone()["count"]
                )
        return counts

    def audit_rows(self) -> list[dict]:
        with self.app.app_context():
            return [
                dict(row)
                for row in get_db().execute(
                    """
                    SELECT actor_id, action, target_type, target_id,
                           before_json, after_json, result, created_at
                    FROM admin_audit_log
                    ORDER BY id
                    """
                )
            ]

    def processed_count(self) -> int:
        with self.app.app_context():
            return processed_comment_count()

    def stored_updated_at(self, comment_id: str) -> str:
        with self.app.app_context():
            row = (
                get_db()
                .execute(
                    """
                    SELECT updated_at
                    FROM content_comments
                    WHERE comment_id = ?
                    """,
                    (comment_id,),
                )
                .fetchone()
            )
        return str(row["updated_at"])

    def test_delete_comment_hides_it_without_notification(self):
        response = self.admin.delete(f"/api/admin/comments/{self.comment_id}")
        self.assertEqual(response.status_code, 200)
        visible = self.student.get(
            f"/api/agri-skills/courses/{self.course_id}/comments"
        )
        self.assertEqual(visible.status_code, 200)
        self.assertNotIn(
            self.comment_id,
            [item["comment_id"] for item in visible.get_json()["comments"]],
        )
        self.assertEqual(self.notification_count(self.student_id), 0)

    def test_hidden_comment_also_leaves_the_shared_comment_service(self):
        self.admin.delete(f"/api/admin/comments/{self.comment_id}")
        with self.app.app_context():
            remaining = [
                str(item["comment_id"])
                for item in list_content_comments(
                    "course_video",
                    str(self.course_id),
                )
            ]
        self.assertNotIn(self.comment_id, remaining)
        self.assertIn("comment-course-a", remaining)

    def test_silent_delete_emits_no_notification_event_at_all(self):
        # `_persist_notification` is the only writer of
        # `system_notifications` and is resolved at call time, so patching it
        # catches every possible delivery path. The two `events` entry points
        # are the wrapper layer the domain modules actually import, and the
        # two `notification_service` entry points are patched too, so a
        # future refactor that bypasses the wrapper is still caught.
        before = self.notification_row_counts()
        with (
            patch("app.messaging.events.emit_notification") as events_emit,
            patch("app.messaging.events.emit_notifications") as events_many,
            patch(
                "app.messaging.notification_service.emit_notification"
            ) as service_emit,
            patch(
                "app.messaging.notification_service.emit_notifications"
            ) as service_many,
            patch(
                "app.messaging.notification_service._persist_notification"
            ) as persist,
        ):
            response = self.admin.delete(
                f"/api/admin/comments/{self.comment_id}"
            )

        self.assertEqual(response.status_code, 200)
        events_emit.assert_not_called()
        events_many.assert_not_called()
        service_emit.assert_not_called()
        service_many.assert_not_called()
        persist.assert_not_called()
        self.assertEqual(self.notification_row_counts(), before)
        self.assertEqual(self.notification_count(self.student_id), 0)

    def test_moderation_module_never_reaches_the_notification_layer(self):
        # Parsed rather than grepped, so a docstring that merely names the
        # forbidden layer cannot trip the guard and a future refactor that
        # imports it cannot slip past.
        tree = ast.parse(
            Path(moderation.__file__).read_text(encoding="utf-8")
        )
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module or "")

        self.assertEqual(
            sorted(name for name in imported if "messaging" in name),
            [],
        )
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                self.assertNotIn("messaging", ast.unparse(node))

    def test_delete_comment_response_shape_is_explicit(self):
        stored_before = self.stored_updated_at(self.comment_id)
        payload = self.admin.delete(
            f"/api/admin/comments/{self.comment_id}"
        ).get_json()

        self.assertTrue(payload["success"])
        self.assertEqual(payload["comment_id"], self.comment_id)
        self.assertIs(payload["is_visible"], False)
        self.assertIs(payload["changed"], True)
        self.assertTrue(payload["updated_at"].endswith("+08:00"))
        self.assertEqual(
            payload["updated_at"],
            self.stored_updated_at(self.comment_id),
        )
        self.assertNotEqual(stored_before, payload["updated_at"])

    def test_delete_unknown_comment_is_reported_as_404(self):
        response = self.admin.delete("/api/admin/comments/comment-missing")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json()["code"], "comment_not_found")
        self.assertFalse(response.get_json()["success"])
        self.assertEqual(self.audit_rows(), [])
        self.assertEqual(self.processed_count(), 1)

    def test_delete_comment_service_raises_not_found_for_unknown_id(self):
        with self.app.app_context():
            with self.assertRaises(ProviderNotFoundError) as caught:
                delete_comment(
                    self.user_ids["moderation-admin"],
                    "comment-missing",
                )

        self.assertEqual(caught.exception.code, "comment_not_found")

    def test_repeated_delete_is_idempotent_and_counts_once(self):
        first = self.admin.delete(f"/api/admin/comments/{self.comment_id}")
        second = self.admin.delete(f"/api/admin/comments/{self.comment_id}")
        third = self.admin.delete(f"/api/admin/comments/{self.comment_id}")

        self.assertEqual(first.status_code, 200)
        self.assertTrue(first.get_json()["changed"])
        for repeat in (second, third):
            self.assertEqual(repeat.status_code, 200)
            self.assertIs(repeat.get_json()["changed"], False)
            self.assertIs(repeat.get_json()["is_visible"], False)
            self.assertEqual(
                repeat.get_json()["comment_id"], self.comment_id
            )

        self.assertEqual(len(self.audit_rows()), 1)
        self.assertEqual(self.processed_count(), 2)

    def test_delete_comment_writes_exactly_one_meaningful_audit_row(self):
        self.admin.delete(f"/api/admin/comments/{self.comment_id}")

        rows = self.audit_rows()
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["action"], "delete_comment")
        self.assertEqual(row["target_type"], "content_comment")
        self.assertEqual(row["target_id"], self.comment_id)
        self.assertEqual(row["actor_id"], self.user_ids["moderation-admin"])
        self.assertEqual(row["result"], "success")

        before = json.loads(row["before_json"])
        after = json.loads(row["after_json"])
        self.assertIs(before["is_visible"], True)
        self.assertIs(after["is_visible"], False)
        self.assertEqual(before["content_type"], "course_video")
        self.assertEqual(before["content_id"], str(self.course_id))
        self.assertEqual(before["author_id"], self.student_id)
        self.assertEqual(after["content_type"], before["content_type"])
        self.assertEqual(after["content_id"], before["content_id"])
        self.assertEqual(after["author_id"], before["author_id"])
        self.assertNotEqual(before["updated_at"], after["updated_at"])
        self.assertTrue(after["updated_at"].endswith("+08:00"))

    def test_repeat_delete_writes_no_second_audit_row(self):
        self.admin.delete(f"/api/admin/comments/{self.comment_id}")
        self.admin.delete(f"/api/admin/comments/{self.comment_id}")

        self.assertEqual(
            [row["action"] for row in self.audit_rows()],
            ["delete_comment"],
        )

    def test_processed_comment_count_tracks_real_hidden_rows(self):
        self.assertEqual(self.processed_count(), 1)

        self.admin.delete(f"/api/admin/comments/{self.comment_id}")
        self.assertEqual(self.processed_count(), 2)

        self.admin.delete(f"/api/admin/comments/{self.comment_id}")
        self.assertEqual(self.processed_count(), 2)

        self.admin.delete("/api/admin/comments/comment-course-a")
        self.assertEqual(self.processed_count(), 3)

        with self.app.app_context():
            hidden = {
                str(row["comment_id"])
                for row in get_db().execute(
                    """
                    SELECT comment_id
                    FROM content_comments
                    WHERE is_visible = 0
                    """
                )
            }
        self.assertEqual(
            hidden,
            {
                "comment-hidden",
                "comment-course-a",
                self.comment_id,
            },
        )

    def test_list_moderation_comments_orders_newest_first_and_keeps_hidden(self):
        payload = self.admin.get("/api/admin/comments").get_json()

        self.assertTrue(payload["success"])
        self.assertEqual(payload["count"], 6)
        self.assertEqual(
            [item["comment_id"] for item in payload["items"]],
            [
                "comment-other-course",
                "comment-video-c",
                "comment-course-b",
                "comment-course-a",
                "comment-hidden",
                "comment-old",
            ],
        )

    def test_moderation_item_carries_the_patrol_fields(self):
        items = self._items(content_type="handcraft_teaching_video")

        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(
            set(item),
            {
                "comment_id",
                "content_type",
                "content_id",
                "author_id",
                "author",
                "parent_comment_id",
                "body",
                "is_teacher_reply",
                "is_visible",
                "created_at",
                "updated_at",
            },
        )
        self.assertEqual(
            item,
            {
                "comment_id": "comment-video-c",
                "content_type": "handcraft_teaching_video",
                "content_id": "video-approved",
                "author_id": self.teacher_id,
                "author": {
                    "username": "moderation-teacher",
                    "name": "教师甲",
                },
                "parent_comment_id": None,
                "body": "非遗教学视频的补充说明",
                "is_teacher_reply": False,
                "is_visible": True,
                "created_at": "2026-09-20T10:10:00+08:00",
                "updated_at": "2026-09-20T10:10:00+08:00",
            },
        )

    def test_filters_narrow_the_patrol_list(self):
        self.assertEqual(
            [
                item["comment_id"]
                for item in self._items(
                    content_type="handcraft_teaching_video"
                )
            ],
            ["comment-video-c"],
        )
        self.assertEqual(len(self._items(content_type="course_video")), 5)

        self.assertEqual(
            [
                item["comment_id"]
                for item in self._items(content_id=str(self.other_course_id))
            ],
            ["comment-other-course"],
        )

        self.assertEqual(
            [
                item["comment_id"]
                for item in self._items(author_id=str(self.teacher_id))
            ],
            ["comment-video-c"],
        )
        self.assertEqual(len(self._items(author_id=str(self.student_id))), 5)

        self.assertEqual(
            [
                item["comment_id"]
                for item in self._items(is_visible="0")
            ],
            ["comment-hidden"],
        )
        self.assertEqual(len(self._items(is_visible="1")), 5)
        self.assertEqual(len(self._items(is_visible="false")), 1)
        self.assertEqual(len(self._items(is_visible="true")), 5)

        self.assertEqual(
            [
                item["comment_id"]
                for item in self._items(keyword="违规")
            ],
            ["comment-course-b"],
        )
        self.assertEqual(
            len(self._items(keyword="moderation-student")),
            5,
        )

        self.assertEqual(
            [
                item["comment_id"]
                for item in self._items(
                    content_type="course_video",
                    content_id=str(self.course_id),
                    is_visible="1",
                )
            ],
            ["comment-course-b", "comment-course-a", "comment-old"],
        )

    def test_time_filters_compare_parsed_timestamps(self):
        self.assertEqual(
            [
                item["comment_id"]
                for item in self._items(
                    created_from="2026-09-20T10:00:00+08:00",
                    created_to="2026-09-20T10:10:00+08:00",
                )
            ],
            ["comment-video-c", "comment-course-b", "comment-course-a"],
        )

        # A UTC `Z` stamp and a `+08:00` stamp name the same instant.
        self.assertEqual(
            [
                item["comment_id"]
                for item in self._items(created_from="2026-09-20T02:05:00Z")
            ],
            [
                "comment-other-course",
                "comment-video-c",
                "comment-course-b",
            ],
        )

        self.assertEqual(
            self._items(created_from="2027-01-01T00:00:00+08:00"),
            [],
        )

    def test_pagination_slices_the_ordered_list(self):
        self.assertEqual(
            [
                item["comment_id"]
                for item in self._items(limit="2", offset="0")
            ],
            ["comment-other-course", "comment-video-c"],
        )
        self.assertEqual(
            [
                item["comment_id"]
                for item in self._items(limit="2", offset="2")
            ],
            ["comment-course-b", "comment-course-a"],
        )
        self.assertEqual(
            [
                item["comment_id"]
                for item in self._items(limit="2", offset="4")
            ],
            ["comment-hidden", "comment-old"],
        )
        self.assertEqual(self._items(limit="2", offset="10"), [])

    def test_invalid_filters_are_rejected_with_400(self):
        cases = (
            ("content_type", "course_audio"),
            ("content_type", "handcraft_video"),
            ("is_visible", "maybe"),
            ("is_visible", "2"),
            ("author_id", "0"),
            ("author_id", "-3"),
            ("author_id", "abc"),
            ("limit", "0"),
            ("limit", "-1"),
            ("limit", "1000"),
            ("offset", "-1"),
            ("offset", "abc"),
            ("created_from", "2026-09-20"),
            ("created_from", "not-a-time"),
            ("created_to", "2026-09-20T10:00:00"),
        )
        for field, value in cases:
            with self.subTest(**{field: value}):
                response = self.admin.get(
                    f"/api/admin/comments?{field}={value}"
                )
                self.assertEqual(response.status_code, 400)
                self.assertEqual(
                    response.get_json()["code"],
                    "moderation_filter_invalid",
                )
                self.assertFalse(response.get_json()["success"])

        self.assertEqual(self.audit_rows(), [])

    def test_blank_filter_values_are_treated_as_absent(self):
        # An explicitly empty query value is a client sending the whole
        # filter set, not a malformed one, so it must not 400 the patrol.
        baseline = self._items()

        for query in (
            {"content_type": ""},
            {"content_id": ""},
            {"author_id": ""},
            {"keyword": ""},
            {"is_visible": ""},
            {"created_from": ""},
            {"created_to": ""},
            {"limit": ""},
            {"offset": ""},
        ):
            with self.subTest(**query):
                self.assertEqual(self._items(**query), baseline)
        self.assertEqual(self.audit_rows(), [])

    def test_reversed_time_range_is_rejected(self):
        response = self.admin.get(
            "/api/admin/comments"
            "?created_from=2026-09-20T12:00:00%2B08:00"
            "&created_to=2026-09-20T10:00:00%2B08:00"
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.get_json()["code"], "moderation_filter_invalid"
        )

    def test_list_moderation_comments_service_rejects_invalid_filters(self):
        for filters in (
            {"content_type": "course_audio"},
            {"is_visible": "maybe"},
            {"author_id": 0},
            {"limit": 0},
            {"offset": -1},
            {"created_from": "2026-09-20"},
            "not-a-dict",
        ):
            with self.subTest(filters=filters):
                with self.app.app_context():
                    with self.assertRaises(ProviderValidationError) as caught:
                        list_moderation_comments(filters)
                self.assertEqual(
                    caught.exception.code,
                    "moderation_filter_invalid",
                )

    def test_comment_moderation_is_available_to_both_admin_roles(self):
        for client, username, target in (
            (self.admin, "moderation-admin", "comment-course-a"),
            (
                self.super_admin,
                "moderation-super-admin",
                "comment-course-b",
            ),
        ):
            with self.subTest(role=username):
                listing = client.get("/api/admin/comments")
                self.assertEqual(listing.status_code, 200)

                deletion = client.delete(
                    f"/api/admin/comments/{target}"
                )
                self.assertEqual(deletion.status_code, 200)
                self.assertTrue(deletion.get_json()["changed"])

        self.assertEqual(len(self.audit_rows()), 2)
        self.assertEqual(
            sorted(row["actor_id"] for row in self.audit_rows()),
            sorted(
                [
                    self.user_ids["moderation-admin"],
                    self.user_ids["moderation-super-admin"],
                ]
            ),
        )

    def test_comment_moderation_is_denied_for_non_admin_roles(self):
        for client, username in (
            (self.student, "moderation-student"),
            (self.teacher, "moderation-teacher"),
        ):
            with self.subTest(role=username):
                listing = client.get("/api/admin/comments")
                self.assertEqual(listing.status_code, 403)
                self.assertEqual(
                    listing.get_json()["code"], "admin_access_denied"
                )

                deletion = client.delete(
                    f"/api/admin/comments/{self.comment_id}"
                )
                self.assertEqual(deletion.status_code, 403)

        anonymous = self.app.test_client()
        self.assertEqual(
            anonymous.get("/api/admin/comments").status_code, 401
        )
        self.assertEqual(
            anonymous.delete(
                f"/api/admin/comments/{self.comment_id}"
            ).status_code,
            401,
        )

        self.assertEqual(self.audit_rows(), [])
        self.assertEqual(self.processed_count(), 1)


    def test_confirmed_report_deletes_comment_and_counts_once(self):
        first = self.resolve(self.report_id, confirmed=True, result="违规")
        second = self.resolve(self.report_id, confirmed=True, result="违规")

        self.assertEqual(first.status_code, 200)
        self.assertTrue(first.get_json()["changed"])
        self.assertFalse(second.get_json()["changed"])
        self.assertEqual(self.report_processed_count(), 1)

    def test_rejected_report_keeps_the_comment_visible_and_emits_nothing(self):
        before = self.notification_row_counts()
        response = self.resolve(
            self.report_id,
            confirmed=False,
            result="经核实不属于违规内容",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIs(response.get_json()["changed"], True)
        # The comment is untouched: still readable by the student, still
        # counted as visible, and the report itself says `rejected`.
        self.assertIn(self.comment_id, self.student_visible_comment_ids())
        self.assertEqual(self.processed_count(), 1)
        report = response.get_json()["report"]
        self.assertEqual(report["status"], "rejected")
        self.assertEqual(report["result"], "经核实不属于违规内容")
        self.assertEqual(report["resolver_id"], self.admin_id)
        self.assertEqual(report["resolver"]["username"], "moderation-admin")
        self.assertTrue(report["resolved_at"].endswith("+08:00"))
        # A rejected report is still processed work, so the count moves.
        self.assertEqual(self.report_processed_count(), 1)
        self.assertEqual(self.notification_row_counts(), before)
        self.assertEqual(self.notification_count(self.student_id), 0)
        self.assertEqual(
            [row["action"] for row in self.audit_rows()],
            ["resolve_comment_report"],
        )

    def test_confirmed_resolution_hides_the_comment_silently(self):
        # The same four-layer proof Task 18 uses for a bare DELETE: every
        # notification entry point is patched, every outbox and delivery
        # table is compared row by row, and the student read path is the
        # one that has to stop returning the comment.
        before = self.notification_row_counts()
        with (
            patch("app.messaging.events.emit_notification") as events_emit,
            patch("app.messaging.events.emit_notifications") as events_many,
            patch(
                "app.messaging.notification_service.emit_notification"
            ) as service_emit,
            patch(
                "app.messaging.notification_service.emit_notifications"
            ) as service_many,
            patch(
                "app.messaging.notification_service._persist_notification"
            ) as persist,
        ):
            response = self.resolve(
                self.report_id,
                confirmed=True,
                result="含有违规内容",
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["changed"])
        events_emit.assert_not_called()
        events_many.assert_not_called()
        service_emit.assert_not_called()
        service_many.assert_not_called()
        persist.assert_not_called()
        self.assertEqual(self.notification_row_counts(), before)
        self.assertEqual(self.notification_count(self.student_id), 0)

        self.assertNotIn(
            self.comment_id,
            self.student_visible_comment_ids(),
        )
        self.assertEqual(self.processed_count(), 2)
        self.assertEqual(self.report_processed_count(), 1)

    def test_report_resolution_is_idempotent_and_counts_once(self):
        first = self.resolve(self.report_id, confirmed=True, result="违规")
        second = self.resolve(
            self.report_id,
            confirmed=False,
            result="改主意了，不属于违规",
        )
        third = self.resolve(self.report_id, confirmed=True, result="违规")

        self.assertTrue(first.get_json()["changed"])
        for repeat in (second, third):
            self.assertEqual(repeat.status_code, 200)
            self.assertIs(repeat.get_json()["changed"], False)
            # The repeat echoes the stored decision, not the request that
            # was refused, so a console cannot mistake it for a reversal.
            self.assertEqual(repeat.get_json()["report"]["status"], "confirmed")

        # The reversal was refused, so the comment stays hidden and only the
        # one real decision is on file.
        self.assertNotIn(self.comment_id, self.student_visible_comment_ids())
        self.assertEqual(self.processed_count(), 2)
        self.assertEqual(self.report_processed_count(), 1)
        self.assertEqual(
            [row["action"] for row in self.audit_rows()],
            ["delete_comment", "resolve_comment_report"],
        )

    def test_resolution_writes_an_audit_row_per_decision(self):
        self.resolve(self.report_id, confirmed=True, result="含有违规内容")

        rows = self.audit_rows()
        self.assertEqual(
            [row["action"] for row in rows],
            ["delete_comment", "resolve_comment_report"],
        )
        report_row = rows[1]
        self.assertEqual(report_row["target_type"], "comment_report")
        self.assertEqual(report_row["target_id"], self.report_id)
        self.assertEqual(report_row["actor_id"], self.admin_id)
        self.assertEqual(report_row["result"], "success")

        before = json.loads(report_row["before_json"])
        after = json.loads(report_row["after_json"])
        self.assertEqual(before["status"], "pending")
        self.assertEqual(before["comment_id"], self.comment_id)
        self.assertEqual(before["reporter_id"], self.student_id)
        self.assertEqual(before["reason"], "含有违规内容")
        self.assertIsNone(before["resolver_id"])
        self.assertIsNone(before["result"])
        self.assertEqual(after["status"], "confirmed")
        self.assertEqual(after["resolver_id"], self.admin_id)
        self.assertEqual(after["result"], "含有违规内容")
        # The deletion that the confirmation caused is recorded with the
        # report, so the audit trail explains why the comment disappeared.
        self.assertIs(after["comment_deleted"], True)
        self.assertIs(after["comment_already_hidden"], False)

    def test_second_confirmation_of_an_already_hidden_comment_counts_once(self):
        # The comment was hidden outside the report queue, so the report is
        # still pending and its confirmation has to resolve it while
        # reporting that the deletion changed nothing.
        self.admin.delete(f"/api/admin/comments/{self.comment_id}")
        response = self.resolve(self.report_id, confirmed=True, result="违规")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["changed"])
        self.assertEqual(
            response.get_json()["report"]["comment_is_visible"], False
        )
        self.assertEqual(self.processed_count(), 2)
        self.assertEqual(self.report_processed_count(), 1)
        after = json.loads(self.audit_rows()[-1]["after_json"])
        self.assertIs(after["comment_deleted"], False)
        self.assertIs(after["comment_already_hidden"], True)

    def test_confirmed_report_still_resolves_when_its_comment_is_gone(self):
        # `comment_reports` has no foreign key to `content_comments`, so a
        # report can outlive the comment it names. The confirmation is
        # already satisfied and the report must not stay pending forever.
        self._create_report(
            "report-vanished-comment",
            "comment-never-existed",
            self.student_id,
            "举报一条已不存在的评论",
            "2026-09-20T11:20:00+08:00",
        )
        response = self.resolve(
            "report-vanished-comment",
            confirmed=True,
            result="评论已不存在",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["changed"])
        self.assertEqual(
            response.get_json()["report"]["comment_is_visible"], None
        )
        self.assertEqual(self.report_processed_count(), 1)
        self.assertEqual(self.processed_count(), 1)

    def test_resolving_unknown_report_is_reported_as_404(self):
        response = self.resolve("report-missing", confirmed=True, result="违规")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.get_json()["code"],
            "comment_report_not_found",
        )
        self.assertFalse(response.get_json()["success"])
        self.assertEqual(self.audit_rows(), [])
        self.assertEqual(self.report_processed_count(), 0)

        with self.app.app_context():
            with self.assertRaises(ProviderNotFoundError) as caught:
                resolve_report(self.admin_id, "report-missing", True, "违规")
        self.assertEqual(
            caught.exception.code,
            "comment_report_not_found",
        )

    def test_resolution_requires_a_bounded_result_and_a_boolean_confirmation(self):
        cases = (
            {"confirmed": True},
            {"confirmed": True, "result": "   "},
            {"confirmed": True, "result": "x" * 501},
            {"confirmed": True, "result": 7},
            {"confirmed": "yes", "result": "违规"},
            {"confirmed": 1, "result": "违规"},
            {"confirmed": None, "result": "违规"},
            {},
        )
        for payload in cases:
            with self.subTest(**payload):
                response = self.resolve(self.report_id, **payload)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(
                    response.get_json()["code"],
                    "moderation_validation_failed",
                )
                self.assertFalse(response.get_json()["success"])

        # Nothing was decided and nothing was hidden by a refused request.
        self.assertEqual(self.audit_rows(), [])
        self.assertEqual(self.report_processed_count(), 0)
        self.assertIn(self.comment_id, self.student_visible_comment_ids())

    def test_report_queue_lists_every_report_newest_first(self):
        self._seed_resolved_reports()

        payload = self.admin.get("/api/admin/reports").get_json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["count"], 3)
        self.assertEqual(
            [item["report_id"] for item in payload["items"]],
            [
                "report-confirmed-old",
                "report-rejected-course-a",
                self.report_id,
            ],
        )

        pending = self.reports(status="pending")
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0], {
            "report_id": self.report_id,
            "comment_id": self.comment_id,
            "reporter_id": self.student_id,
            "reporter": {"username": "moderation-student", "name": "学员甲"},
            "reason": "含有违规内容",
            "status": "pending",
            "resolver_id": None,
            "resolver": {"username": "", "name": ""},
            "result": None,
            "comment_is_visible": True,
            "created_at": "2026-09-20T11:00:00+08:00",
            "updated_at": "2026-09-20T11:00:00+08:00",
            "resolved_at": None,
        })

    def test_report_filters_and_pagination_narrow_the_queue(self):
        self._seed_resolved_reports()

        self.assertEqual(
            [item["report_id"] for item in self.reports(status="pending")],
            [self.report_id],
        )
        self.assertEqual(
            [
                item["report_id"]
                for item in self.reports(status="confirmed")
            ],
            ["report-confirmed-old"],
        )
        self.assertEqual(
            [item["report_id"] for item in self.reports(status="rejected")],
            ["report-rejected-course-a"],
        )
        self.assertEqual(
            [
                item["report_id"]
                for item in self.reports(comment_id=self.comment_id)
            ],
            [self.report_id],
        )
        self.assertEqual(
            [
                item["report_id"]
                for item in self.reports(reporter_id=str(self.teacher_id))
            ],
            ["report-confirmed-old"],
        )
        self.assertEqual(
            len(self.reports(reporter_id=str(self.student_id))),
            2,
        )
        self.assertEqual(
            [
                item["report_id"]
                for item in self.reports(
                    created_from="2026-09-20T11:06:00+08:00"
                )
            ],
            ["report-confirmed-old"],
        )
        self.assertEqual(
            [
                item["report_id"]
                for item in self.reports(
                    created_to="2026-09-20T11:04:00+08:00"
                )
            ],
            [self.report_id],
        )
        # A UTC `Z` stamp and a `+08:00` stamp name the same instant.
        self.assertEqual(
            [
                item["report_id"]
                for item in self.reports(created_from="2026-09-20T03:06:00Z")
            ],
            ["report-confirmed-old"],
        )

        self.assertEqual(
            [item["report_id"] for item in self.reports(limit="1")],
            ["report-confirmed-old"],
        )
        self.assertEqual(
            [
                item["report_id"]
                for item in self.reports(limit="1", offset="1")
            ],
            ["report-rejected-course-a"],
        )
        self.assertEqual(
            [item["report_id"] for item in self.reports(limit="2", offset="2")],
            [self.report_id],
        )
        self.assertEqual(self.reports(limit="2", offset="5"), [])

    def test_invalid_report_filters_are_rejected_with_400(self):
        cases = (
            ("status", "archived"),
            ("reporter_id", "0"),
            ("reporter_id", "-1"),
            ("reporter_id", "abc"),
            ("limit", "0"),
            ("limit", "201"),
            ("offset", "-1"),
            ("offset", "abc"),
            ("created_from", "2026-09-20"),
            ("created_from", "2026-09-20T11:00:00"),
            ("comment_id", "x" * 129),
        )
        for field, value in cases:
            with self.subTest(**{field: value}):
                response = self.admin.get(
                    f"/api/admin/reports?{field}={value}"
                )
                self.assertEqual(response.status_code, 400)
                self.assertEqual(
                    response.get_json()["code"],
                    "moderation_filter_invalid",
                )
                self.assertEqual(
                    response.get_json()["details"]["field"],
                    field,
                )

        reversed_range = self.admin.get(
            "/api/admin/reports"
            "?created_from=2026-09-20T12:00:00%2B08:00"
            "&created_to=2026-09-20T10:00:00%2B08:00"
        )
        self.assertEqual(reversed_range.status_code, 400)
        self.assertEqual(
            reversed_range.get_json()["code"],
            "moderation_filter_invalid",
        )

        self.assertEqual(self.audit_rows(), [])

    def test_blank_report_filters_are_treated_as_absent(self):
        baseline = self.reports()

        for query in (
            {"status": ""},
            {"comment_id": ""},
            {"reporter_id": ""},
            {"created_from": ""},
            {"created_to": ""},
            {"limit": ""},
            {"offset": ""},
        ):
            with self.subTest(**query):
                self.assertEqual(self.reports(**query), baseline)

    def test_list_reports_service_rejects_invalid_filters(self):
        for filters in (
            {"status": "archived"},
            {"reporter_id": 0},
            {"limit": 0},
            {"offset": -1},
            {"created_from": "2026-09-20"},
            "not-a-dict",
        ):
            with self.subTest(filters=filters):
                with self.app.app_context():
                    with self.assertRaises(ProviderValidationError) as caught:
                        list_reports(filters)
                self.assertEqual(
                    caught.exception.code,
                    "moderation_filter_invalid",
                )

    def test_report_moderation_is_available_to_both_admin_roles(self):
        self._seed_resolved_reports()
        self._create_report(
            "report-pending-old",
            "comment-video-c",
            self.student_id,
            "教学视频下的刷屏",
            "2026-09-20T11:15:00+08:00",
        )

        for client, username, report_id in (
            (self.admin, "moderation-admin", self.report_id),
            (
                self.super_admin,
                "moderation-super-admin",
                "report-pending-old",
            ),
        ):
            with self.subTest(role=username):
                listing = client.get("/api/admin/reports")
                self.assertEqual(listing.status_code, 200)
                self.assertEqual(listing.get_json()["count"], 4)

                resolution = client.post(
                    f"/api/admin/reports/{report_id}/resolve",
                    json={"confirmed": False, "result": "已核实"},
                )
                self.assertEqual(resolution.status_code, 200)
                self.assertTrue(resolution.get_json()["changed"])

        # Two of the four reports were already resolved before either admin
        # acted, and both admins answered one pending report each.
        self.assertEqual(self.report_processed_count(), 4)
        self.assertEqual(
            sorted(row["actor_id"] for row in self.audit_rows()),
            sorted([self.admin_id, self.super_admin_id]),
        )

    def test_report_moderation_is_denied_for_non_admin_roles(self):
        for client, username in (
            (self.student, "moderation-student"),
            (self.teacher, "moderation-teacher"),
        ):
            with self.subTest(role=username):
                listing = client.get("/api/admin/reports")
                self.assertEqual(listing.status_code, 403)
                self.assertEqual(
                    listing.get_json()["code"], "admin_access_denied"
                )

                resolution = client.post(
                    f"/api/admin/reports/{self.report_id}/resolve",
                    json={"confirmed": True, "result": "违规"},
                )
                self.assertEqual(resolution.status_code, 403)

        anonymous = self.app.test_client()
        self.assertEqual(
            anonymous.get("/api/admin/reports").status_code, 401
        )
        self.assertEqual(
            anonymous.post(
                f"/api/admin/reports/{self.report_id}/resolve",
                json={"confirmed": True, "result": "违规"},
            ).status_code,
            401,
        )

        self.assertEqual(self.audit_rows(), [])
        self.assertEqual(self.report_processed_count(), 0)
        self.assertIn(self.comment_id, self.student_visible_comment_ids())


    def test_feedback_intake_is_idempotent(self):
        with self.app.app_context():
            provider = get_feedback_intake_provider()
            first = provider.submit_feedback(
                submitter_id=self.student_id,
                body="建议增加夜校课程",
                idempotency_key="feedback-1",
            )
            second = provider.submit_feedback(
                submitter_id=self.student_id,
                body="建议增加夜校课程",
                idempotency_key="feedback-1",
            )
            # The unique constraint is on the pair, so the same key from
            # another submitter is a different record rather than a retry.
            other = provider.submit_feedback(
                submitter_id=self.teacher_id,
                body="希望增加线下实训",
                idempotency_key="feedback-1",
            )

        self.assertEqual(first["feedback_id"], second["feedback_id"])
        self.assertEqual(first, second)
        self.assertNotEqual(other["feedback_id"], first["feedback_id"])
        self.assertEqual(self.feedback_row_count(), 5)

    def test_feedback_intake_stores_one_pending_record(self):
        with self.app.app_context():
            provider = get_feedback_intake_provider()
            record = provider.submit_feedback(
                submitter_id=self.student_id,
                body="  建议增加夜校课程  ",
                idempotency_key="intake-1",
            )

        self.assertTrue(record["feedback_id"].startswith("feedback-"))
        self.assertEqual(record["status"], "pending")
        self.assertEqual(record["submitter_id"], self.student_id)
        # Stored trimmed, so a retry with stray whitespace still matches.
        self.assertEqual(record["body"], "建议增加夜校课程")
        self.assertEqual(record["idempotency_key"], "intake-1")
        self.assertEqual(
            record["submitter"],
            {"username": "moderation-student", "name": "学员甲"},
        )
        self.assertIsNone(record["handler_id"])
        self.assertIsNone(record["result"])
        self.assertTrue(record["created_at"].endswith("+08:00"))
        self.assertEqual(record["created_at"], record["updated_at"])
        self.assertEqual(self.feedback_row_count(), 4)

        # The stored record is the same shape the console lists back.
        listed = self.feedback_items(submitter_id=str(self.student_id))
        self.assertEqual(
            [item["feedback_id"] for item in listed],
            [record["feedback_id"], "feedback-processed-2", self.feedback_id],
        )

    def test_feedback_intake_validates_its_required_fields(self):
        cases = (
            {"body": "", "idempotency_key": "key-1"},
            {"body": "   ", "idempotency_key": "key-1"},
            {"body": None, "idempotency_key": "key-1"},
            {"body": 42, "idempotency_key": "key-1"},
            {"body": "x" * 2001, "idempotency_key": "key-1"},
            {"body": "内容", "idempotency_key": ""},
            {"body": "内容", "idempotency_key": None},
            {"body": "内容", "idempotency_key": "k" * 129},
        )
        for payload in cases:
            with self.subTest(**payload):
                with self.app.app_context():
                    provider = get_feedback_intake_provider()
                    with self.assertRaises(ProviderValidationError) as caught:
                        provider.submit_feedback(
                            submitter_id=self.student_id,
                            **payload,
                        )
                self.assertEqual(
                    caught.exception.code,
                    "moderation_validation_failed",
                )
        self.assertEqual(self.feedback_row_count(), 3)

    def test_feedback_intake_rejects_an_invalid_submitter_id(self):
        for submitter_id in (0, -1, "7", 2**63, 2**63 - 1 + 1, True, None):
            with self.subTest(submitter_id=submitter_id):
                with self.app.app_context():
                    provider = get_feedback_intake_provider()
                    with self.assertRaises(ProviderValidationError):
                        provider.submit_feedback(
                            submitter_id=submitter_id,
                            body="内容",
                            idempotency_key="key-1",
                        )
        self.assertEqual(self.feedback_row_count(), 3)

    def test_feedback_intake_is_silent(self):
        before = self.notification_row_counts()
        with (
            patch("app.messaging.events.emit_notification") as events_emit,
            patch("app.messaging.events.emit_notifications") as events_many,
            patch(
                "app.messaging.notification_service.emit_notification"
            ) as service_emit,
            patch(
                "app.messaging.notification_service.emit_notifications"
            ) as service_many,
            patch(
                "app.messaging.notification_service._persist_notification"
            ) as persist,
        ):
            with self.app.app_context():
                provider = get_feedback_intake_provider()
                provider.submit_feedback(
                    submitter_id=self.student_id,
                    body="建议增加夜校课程",
                    idempotency_key="silent-1",
                )

        events_emit.assert_not_called()
        events_many.assert_not_called()
        service_emit.assert_not_called()
        service_many.assert_not_called()
        persist.assert_not_called()
        self.assertEqual(self.notification_row_counts(), before)
        self.assertEqual(self.notification_count(self.student_id), 0)

    def test_feedback_queue_lists_every_feedback_newest_first(self):
        payload = self.admin.get("/api/admin/feedback").get_json()

        self.assertTrue(payload["success"])
        self.assertEqual(payload["count"], 3)
        self.assertEqual(
            [item["feedback_id"] for item in payload["items"]],
            [
                "feedback-closed-3",
                "feedback-processed-2",
                self.feedback_id,
            ],
        )

        pending = self.feedback_items(status="pending")
        self.assertEqual(len(pending), 1)
        self.assertEqual(
            set(pending[0]),
            {
                "feedback_id",
                "submitter_id",
                "submitter",
                "body",
                "status",
                "idempotency_key",
                "handler_id",
                "handler",
                "result",
                "created_at",
                "updated_at",
            },
        )
        self.assertEqual(pending[0], {
            "feedback_id": self.feedback_id,
            "submitter_id": self.student_id,
            "submitter": {"username": "moderation-student", "name": "学员甲"},
            "body": "建议增加夜校课程",
            "status": "pending",
            "idempotency_key": "feedback-pending-1-key",
            "handler_id": None,
            "handler": {"username": "", "name": ""},
            "result": None,
            "created_at": "2026-09-20T13:00:00+08:00",
            "updated_at": "2026-09-20T13:00:00+08:00",
        })

    def test_feedback_filters_and_pagination_narrow_the_queue(self):
        self.assertEqual(
            [item["feedback_id"] for item in self.feedback_items(status="pending")],
            [self.feedback_id],
        )
        self.assertEqual(
            [
                item["feedback_id"]
                for item in self.feedback_items(status="closed")
            ],
            ["feedback-closed-3"],
        )
        self.assertEqual(
            [
                item["feedback_id"]
                for item in self.feedback_items(submitter_id=str(self.teacher_id))
            ],
            ["feedback-closed-3"],
        )
        self.assertEqual(
            len(self.feedback_items(submitter_id=str(self.student_id))),
            2,
        )
        self.assertEqual(
            [
                item["feedback_id"]
                for item in self.feedback_items(
                    created_from="2026-09-20T13:06:00+08:00"
                )
            ],
            ["feedback-closed-3"],
        )
        self.assertEqual(
            [
                item["feedback_id"]
                for item in self.feedback_items(
                    created_to="2026-09-20T13:04:00+08:00"
                )
            ],
            [self.feedback_id],
        )
        self.assertEqual(
            [
                item["feedback_id"]
                for item in self.feedback_items(
                    created_from="2026-09-20T05:06:00Z"
                )
            ],
            ["feedback-closed-3"],
        )

        self.assertEqual(
            [item["feedback_id"] for item in self.feedback_items(limit="1")],
            ["feedback-closed-3"],
        )
        self.assertEqual(
            [
                item["feedback_id"]
                for item in self.feedback_items(limit="1", offset="1")
            ],
            ["feedback-processed-2"],
        )
        self.assertEqual(
            [
                item["feedback_id"]
                for item in self.feedback_items(limit="2", offset="2")
            ],
            [self.feedback_id],
        )
        self.assertEqual(self.feedback_items(limit="2", offset="5"), [])

    def test_invalid_feedback_filters_are_rejected_with_400(self):
        cases = (
            ("status", "archived"),
            ("submitter_id", "0"),
            ("submitter_id", "-2"),
            ("submitter_id", "abc"),
            ("limit", "0"),
            ("limit", "201"),
            ("offset", "-1"),
            ("offset", "abc"),
            ("created_from", "2026-09-20"),
            ("created_from", "2026-09-20T13:00:00"),
        )
        for field, value in cases:
            with self.subTest(**{field: value}):
                response = self.admin.get(
                    f"/api/admin/feedback?{field}={value}"
                )
                self.assertEqual(response.status_code, 400)
                self.assertEqual(
                    response.get_json()["code"],
                    "moderation_filter_invalid",
                )
                self.assertEqual(
                    response.get_json()["details"]["field"],
                    field,
                )

        self.assertEqual(self.audit_rows(), [])

    def test_list_feedback_service_rejects_invalid_filters(self):
        for filters in (
            {"status": "archived"},
            {"submitter_id": 0},
            {"limit": 0},
            {"offset": -1},
            {"created_from": "2026-09-20"},
            "not-a-dict",
        ):
            with self.subTest(filters=filters):
                with self.app.app_context():
                    with self.assertRaises(ProviderValidationError) as caught:
                        list_feedback(filters)
                self.assertEqual(
                    caught.exception.code,
                    "moderation_filter_invalid",
                )

    def test_feedback_patch_moves_the_status_machine_and_audits(self):
        response = self.patch_feedback(
            self.feedback_id,
            status="processed",
            result="已转课程组评估",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["success"])
        self.assertIs(payload["changed"], True)
        self.assertEqual(payload["feedback"]["status"], "processed")
        self.assertEqual(payload["feedback"]["result"], "已转课程组评估")
        self.assertEqual(payload["feedback"]["handler_id"], self.admin_id)
        self.assertEqual(
            payload["handler"],
            {"username": "moderation-admin", "name": "普通管理员"},
        )
        self.assertTrue(payload["feedback"]["updated_at"].endswith("+08:00"))
        # Intake fields are never rewritten by an answer.
        self.assertEqual(
            payload["feedback"]["created_at"],
            "2026-09-20T13:00:00+08:00",
        )
        self.assertEqual(payload["feedback"]["submitter_id"], self.student_id)
        self.assertEqual(payload["feedback"]["body"], "建议增加夜校课程")

        closed = self.patch_feedback(
            self.feedback_id,
            status="closed",
            result="已安排秋季班",
        )
        self.assertIs(closed.get_json()["changed"], True)
        self.assertEqual(closed.get_json()["feedback"]["status"], "closed")

        rows = self.audit_rows()
        self.assertEqual(
            [row["action"] for row in rows],
            ["update_feedback", "update_feedback"],
        )
        self.assertEqual(rows[0]["target_type"], "feedback_record")
        self.assertEqual(rows[0]["target_id"], self.feedback_id)
        self.assertEqual(rows[0]["actor_id"], self.admin_id)
        self.assertEqual(rows[0]["result"], "success")
        self.assertEqual(
            json.loads(rows[0]["before_json"])["status"], "pending"
        )
        self.assertEqual(
            json.loads(rows[0]["after_json"])["status"], "processed"
        )
        self.assertEqual(
            json.loads(rows[1]["before_json"])["status"], "processed"
        )
        self.assertEqual(
            json.loads(rows[1]["after_json"])["status"], "closed"
        )

    def test_feedback_patch_is_idempotent_without_a_second_audit_row(self):
        first = self.patch_feedback(
            self.feedback_id,
            status="processed",
            result="已转课程组评估",
        )
        second = self.patch_feedback(
            self.feedback_id,
            status="processed",
            result="已转课程组评估",
        )

        self.assertIs(first.get_json()["changed"], True)
        self.assertEqual(second.status_code, 200)
        self.assertIs(second.get_json()["changed"], False)
        self.assertEqual(
            second.get_json()["feedback"]["handler_id"], self.admin_id
        )
        self.assertEqual(
            [row["action"] for row in self.audit_rows()],
            ["update_feedback"],
        )

    def test_feedback_patch_unknown_id_is_reported_as_404(self):
        response = self.patch_feedback(
            "feedback-missing",
            status="processed",
            result="已转课程组评估",
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json()["code"], "feedback_not_found")
        self.assertFalse(response.get_json()["success"])

        with self.app.app_context():
            with self.assertRaises(ProviderNotFoundError) as caught:
                update_feedback(
                    self.admin_id,
                    "feedback-missing",
                    "processed",
                    "已转课程组评估",
                )
        self.assertEqual(caught.exception.code, "feedback_not_found")

    def test_feedback_patch_validates_status_and_result(self):
        cases = (
            {"status": "archived", "result": "已归档"},
            {"status": "processed"},
            {"status": "processed", "result": "  "},
            {"status": "processed", "result": "x" * 501},
            {"status": "processed", "result": 3},
            {"status": None, "result": "已处理"},
            {"status": "", "result": "已处理"},
            {},
        )
        for payload in cases:
            with self.subTest(**payload):
                response = self.patch_feedback(self.feedback_id, **payload)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(
                    response.get_json()["code"],
                    "moderation_validation_failed",
                )

        # A refused request leaves the record and the audit trail alone.
        self.assertEqual(self.audit_rows(), [])
        self.assertEqual(
            self.feedback_items(status="pending")[0]["result"], None
        )

    def test_feedback_moderation_is_available_to_both_admin_roles(self):
        self._create_feedback(
            "feedback-pending-4",
            self.teacher_id,
            "希望增加案例库",
            "2026-09-20T13:15:00+08:00",
        )

        for client, username, feedback_id in (
            (self.admin, "moderation-admin", self.feedback_id),
            (
                self.super_admin,
                "moderation-super-admin",
                "feedback-pending-4",
            ),
        ):
            with self.subTest(role=username):
                listing = client.get("/api/admin/feedback")
                self.assertEqual(listing.status_code, 200)
                self.assertEqual(listing.get_json()["count"], 4)

                update = client.patch(
                    f"/api/admin/feedback/{feedback_id}",
                    json={"status": "processed", "result": "已评估"},
                )
                self.assertEqual(update.status_code, 200)
                self.assertTrue(update.get_json()["changed"])

        self.assertEqual(
            sorted(row["actor_id"] for row in self.audit_rows()),
            sorted([self.admin_id, self.super_admin_id]),
        )

    def test_feedback_moderation_is_denied_for_non_admin_roles(self):
        for client, username in (
            (self.student, "moderation-student"),
            (self.teacher, "moderation-teacher"),
        ):
            with self.subTest(role=username):
                listing = client.get("/api/admin/feedback")
                self.assertEqual(listing.status_code, 403)
                self.assertEqual(
                    listing.get_json()["code"], "admin_access_denied"
                )

                update = client.patch(
                    f"/api/admin/feedback/{self.feedback_id}",
                    json={"status": "processed", "result": "已评估"},
                )
                self.assertEqual(update.status_code, 403)

        anonymous = self.app.test_client()
        self.assertEqual(
            anonymous.get("/api/admin/feedback").status_code, 401
        )
        self.assertEqual(
            anonymous.patch(
                f"/api/admin/feedback/{self.feedback_id}",
                json={"status": "processed", "result": "已评估"},
            ).status_code,
            401,
        )

        self.assertEqual(self.audit_rows(), [])
        self.assertEqual(
            self.feedback_items(status="pending")[0]["status"], "pending"
        )


    def test_integer_filters_reject_values_outside_the_int64_range(self):
        # Every INTEGER filter is bound straight into SQLite, which raises
        # OverflowError instead of a validation error outside the signed
        # 64-bit range, so the ceiling has to be enforced before the bind.
        for path, field in (
            ("/api/admin/comments", "author_id"),
            ("/api/admin/reports", "reporter_id"),
            ("/api/admin/feedback", "submitter_id"),
        ):
            with self.subTest(path=path):
                response = self.admin.get(
                    f"{path}?{field}=99999999999999999999"
                )
                self.assertEqual(response.status_code, 400)
                self.assertEqual(
                    response.get_json()["code"],
                    "moderation_filter_invalid",
                )
                self.assertEqual(
                    response.get_json()["details"]["field"],
                    field,
                )

        # The inclusive ceiling is the SQLite range itself, not something
        # tighter, so the largest legal id still resolves.
        self.assertEqual(self._items(author_id=str(2**63 - 1)), [])

        for filters, service in (
            ({"author_id": 2**63}, list_moderation_comments),
            ({"reporter_id": 2**63}, list_reports),
            ({"submitter_id": 2**63}, list_feedback),
        ):
            with self.subTest(filters=filters):
                with self.app.app_context():
                    with self.assertRaises(ProviderValidationError) as caught:
                        service(filters)
                self.assertEqual(
                    caught.exception.code,
                    "moderation_filter_invalid",
                )
                self.assertEqual(
                    caught.exception.details["maximum"],
                    2**63 - 1,
                )


if __name__ == "__main__":
    import unittest

    unittest.main()
