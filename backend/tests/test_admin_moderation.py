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
)
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

    def _items(self, **query) -> list[dict]:
        response = self.admin.get("/api/admin/comments", query_string=query)
        self.assertEqual(response.status_code, 200, response.get_json())
        return response.get_json()["items"]

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


if __name__ == "__main__":
    import unittest

    unittest.main()
