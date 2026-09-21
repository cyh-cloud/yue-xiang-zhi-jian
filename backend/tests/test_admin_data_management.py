from __future__ import annotations

import tempfile
from pathlib import Path
from unittest import TestCase

from werkzeug.security import generate_password_hash

from app import create_app
from app.admin_console.data_management import (
    get_managed_content,
    list_managed_content,
)
from app.db import get_db


NOW = "2026-09-21T10:00:00+08:00"


class AdminDataManagementTests(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "PROPAGATE_EXCEPTIONS": False,
                "DATABASE_PATH": str(Path(self.temp_dir.name) / "test.db"),
                "SECRET_KEY": "test-only-secret",
                "SESSION_HOURS": 24,
                "SESSION_COOKIE_SECURE": False,
            }
        )
        with self.app.app_context():
            self.super_admin_id = self._create_user("super-admin", "super_admin")
            self.admin_id = self._create_user("ordinary-admin", "admin")
            self.teacher_id = self._create_user("teacher-1", "teacher")
            self.enterprise_id = self._create_user("enterprise-1", "enterprise")
            self.government_id = self._create_user("government-1", "government")
            self.student_id = self._create_user("student-1", "student")
            self.job_category_id = self._ensure_job_category()
        self.super_admin = self._login("super-admin")
        self.admin = self._login("ordinary-admin")
        self.anonymous = self.app.test_client()
        self._case_ids: dict[str, object] = {}
        self._case_actions: dict[str, str] = {}

    def tearDown(self):
        self.temp_dir.cleanup()

    # --- harness -------------------------------------------------------------

    def _create_user(self, username: str, role: str) -> int:
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
                NOW,
                NOW,
            ),
        )
        get_db().commit()
        return int(cursor.lastrowid)

    def _ensure_job_category(self) -> int:
        row = get_db().execute(
            "SELECT id FROM interest_tags WHERE group_key = 'job' LIMIT 1"
        ).fetchone()
        if row is not None:
            return int(row["id"])
        cursor = get_db().execute(
            """
            INSERT INTO interest_tags (group_key, name, sort_order, is_active)
            VALUES ('job', '数据管理测试', 99, 1)
            """
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

    # --- content factories ---------------------------------------------------

    def _make_policy(self, *, status: str = "active") -> str:
        policy_id = f"policy-{status}-{self._next_id()}"
        get_db().execute(
            """
            INSERT INTO government_policies (
                id, title, content, category_code, status, version,
                created_by, published_at, created_at, updated_at
            )
            VALUES (?, ?, ?, 'general', ?, 1, ?, ?, ?, ?)
            """,
            (policy_id, "政策标题", "政策正文", status, self.government_id, NOW, NOW, NOW),
        )
        get_db().commit()
        return policy_id

    def _make_news(self) -> str:
        news_id = f"news-{self._next_id()}"
        get_db().execute(
            """
            INSERT INTO government_news (
                id, title, content, category_code, version,
                created_by, published_at, created_at, updated_at
            )
            VALUES (?, ?, ?, 'news', 1, ?, ?, ?, ?)
            """,
            (news_id, "新闻标题", "新闻正文", self.government_id, NOW, NOW, NOW),
        )
        get_db().commit()
        return news_id

    def _make_course(self, *, status: str = "published") -> int:
        cursor = get_db().execute(
            """
            INSERT INTO courses (
                title, direction, status, summary, teacher_name, teacher_id,
                version, content_tags_json, created_at, updated_at
            )
            VALUES (?, 'agriculture', ?, '', 'teacher', ?, 1, '[]', ?, ?)
            """,
            ("课程标题", status, self.teacher_id, NOW, NOW),
        )
        get_db().commit()
        return int(cursor.lastrowid)

    def _make_job(self, *, review_status: str = "approved") -> str:
        job_id = f"job-{self._next_id()}"
        published_at = NOW if review_status == "approved" else None
        get_db().execute(
            """
            INSERT INTO job_positions (
                job_id, enterprise_id, title, salary, location, category_id,
                category_name, description, review_status, version,
                published_at, created_at, updated_at
            )
            VALUES (?, ?, ?, '5000', '广州', ?, '数据管理测试', '岗位描述', ?, 1, ?, ?, ?)
            """,
            (
                job_id,
                self.enterprise_id,
                "职位标题",
                self.job_category_id,
                review_status,
                published_at,
                NOW,
                NOW,
            ),
        )
        get_db().commit()
        return job_id

    def _make_video(self, *, review_status: str = "approved") -> str:
        video_id = f"video-{self._next_id()}"
        published_at = NOW if review_status == "approved" else None
        get_db().execute(
            """
            INSERT INTO heritage_videos (
                video_id, craft_key, title, review_status, media_url, version,
                published_at, created_at, updated_at
            )
            VALUES (?, 'test_craft', ?, ?, 'https://example/v.mp4', 1, ?, ?, ?)
            """,
            (video_id, "视频标题", review_status, published_at, NOW, NOW),
        )
        get_db().commit()
        return video_id

    def _make_comment(self, *, visible: bool = True) -> str:
        comment_id = f"comment-{self._next_id()}"
        get_db().execute(
            """
            INSERT INTO content_comments (
                comment_id, content_type, content_id, author_id, body,
                is_visible, created_at, updated_at
            )
            VALUES (?, 'course_video', '1', ?, '评论内容', ?, ?, ?)
            """,
            (comment_id, self.student_id, 1 if visible else 0, NOW, NOW),
        )
        get_db().commit()
        return comment_id

    def _make_craft(self, *, enabled: bool = True) -> str:
        craft_key = f"test_craft_{self._next_id()}"
        get_db().execute(
            """
            INSERT INTO admin_handcraft_crafts (
                craft_key, name, introduction, is_enabled, version,
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?, 1, ?, ?)
            """,
            (craft_key, "技艺名称", "技艺介绍", 1 if enabled else 0, NOW, NOW),
        )
        get_db().commit()
        return craft_key

    def _make_review_record(
        self,
        content_type: str,
        content_id: str,
        review_status: str = "pending",
    ) -> None:
        get_db().execute(
            """
            INSERT INTO content_review_records (
                content_type, content_id, submitter_id, review_status, version,
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?, 1, ?, ?)
            """,
            (content_type, content_id, self.teacher_id, review_status, NOW, NOW),
        )
        get_db().commit()

    def _make_progress(self, course_id: int) -> None:
        get_db().execute(
            """
            INSERT INTO agri_course_progress (
                user_id, course_id, duration_seconds, progress_percent,
                watched_seconds, updated_at
            )
            VALUES (?, ?, 100, 50, 50, ?)
            """,
            (self.student_id, course_id, NOW),
        )
        get_db().commit()

    _counter = 0

    def _next_id(self) -> int:
        AdminDataManagementTests._counter += 1
        return AdminDataManagementTests._counter

    # --- state readers -------------------------------------------------------

    def _read_state(self, content_type: str, content_id: object):
        with self.app.app_context():
            if content_type == "policy":
                item = get_managed_content("policy", str(content_id))
                return item["status"] if item else None
            if content_type == "news":
                item = get_managed_content("news", str(content_id))
                return "published" if item else None
            if content_type == "course":
                item = get_managed_content("course", str(content_id))
                return item["status"] if item else None
            if content_type == "job":
                item = get_managed_content("job", str(content_id))
                return item["review_status"] if item else None
            if content_type == "handcraft_video":
                item = get_managed_content("handcraft_video", str(content_id))
                return item["review_status"] if item else None
            if content_type == "comment":
                row = get_db().execute(
                    "SELECT is_visible FROM content_comments WHERE comment_id = ?",
                    (str(content_id),),
                ).fetchone()
                if row is None:
                    return None
                return "visible" if row["is_visible"] else "hidden"
            row = get_db().execute(
                "SELECT is_enabled FROM admin_handcraft_crafts WHERE craft_key = ?",
                (str(content_id),),
            ).fetchone()
            if row is None:
                return None
            return "enabled" if row["is_enabled"] else "disabled"

    def _policy_push_count(self, policy_id: str) -> int:
        with self.app.app_context():
            return int(
                get_db()
                .execute(
                    """
                    SELECT COUNT(*) FROM system_notifications
                    WHERE source_type = 'policy' AND source_id = ?
                    """,
                    (policy_id,),
                )
                .fetchone()[0]
            )

    # --- case runner ---------------------------------------------------------

    _INITIAL_STATE = {
        "policy": "active",
        "news": "published",
        "course": "published",
        "job": "approved",
        "handcraft_video": "approved",
        "comment": "visible",
        "preset": "enabled",
    }

    def _create_content(self, content_type: str, state: str):
        with self.app.app_context():
            if content_type == "policy":
                return self._make_policy(status=state)
            if content_type == "news":
                return self._make_news()
            if content_type == "course":
                return self._make_course(status=state)
            if content_type == "job":
                return self._make_job(review_status=state)
            if content_type == "handcraft_video":
                return self._make_video(review_status=state)
            if content_type == "comment":
                return self._make_comment(visible=(state == "visible"))
            return self._make_craft(enabled=(state == "enabled"))

    def _run_managed_case(self, content_type, action, before, after):
        content_id = self._create_content(content_type, before)
        self._case_ids[content_type] = content_id
        self._case_actions[content_type] = action
        if action == "unpublish":
            response = self.super_admin.post(
                f"/api/admin/content/{content_type}/{content_id}/unpublish",
                json={"expected_version": 1},
            )
        else:
            response = self.super_admin.delete(
                f"/api/admin/content/{content_type}/{content_id}",
                json={"expected_version": 1},
            )
        self.assertEqual(
            response.status_code,
            200,
            msg=f"{content_type}/{action} -> {response.get_json()}",
        )
        self.assertEqual(
            self._read_state(content_type, content_id),
            after,
            msg=f"{content_type}/{action} final state",
        )

    def _assert_version_conflict_rejected(self, content_type):
        if content_type == "comment":
            # Comments carry no version column; a repeat delete of an
            # already-hidden comment is the conflict path for this type.
            comment_id = self._case_ids["comment"]
            response = self.super_admin.delete(
                f"/api/admin/content/comment/{comment_id}",
                json={"expected_version": 1},
            )
            self.assertEqual(response.status_code, 409)
            return
        content_id = self._create_content(
            content_type, self._INITIAL_STATE[content_type]
        )
        response = self.super_admin.delete(
            f"/api/admin/content/{content_type}/{content_id}",
            json={"expected_version": 999},
        )
        self.assertEqual(
            response.status_code,
            409,
            msg=f"{content_type} version conflict -> {response.get_json()}",
        )

    def _assert_history_preserved(self, content_type):
        content_id = self._case_ids[content_type]
        audit_target_type = {
            "comment": "content_comment",
            "preset": "handcraft_craft",
        }.get(content_type, content_type)
        with self.app.app_context():
            audit = int(
                get_db()
                .execute(
                    """
                    SELECT COUNT(*) FROM admin_audit_log
                    WHERE target_type = ? AND target_id = ?
                    """,
                    (audit_target_type, str(content_id)),
                )
                .fetchone()[0]
            )
            self.assertGreaterEqual(
                audit, 1, msg=f"missing audit for {content_type} {content_id}"
            )
            action = self._case_actions.get(content_type)
            if action == "delete" and content_type == "course":
                row = get_db().execute(
                    "SELECT deleted_at FROM courses WHERE id = ?", (content_id,)
                ).fetchone()
                self.assertIsNotNone(row["deleted_at"])
            elif action == "delete" and content_type == "job":
                row = get_db().execute(
                    "SELECT deleted_at FROM job_positions WHERE job_id = ?",
                    (content_id,),
                ).fetchone()
                self.assertIsNotNone(row["deleted_at"])
            elif action == "delete" and content_type == "handcraft_video":
                row = get_db().execute(
                    "SELECT deleted_at FROM heritage_videos WHERE video_id = ?",
                    (content_id,),
                ).fetchone()
                self.assertIsNotNone(row["deleted_at"])

    # --- tests ---------------------------------------------------------------

    def test_policy_correction_does_not_repush_or_change_status(self):
        policy_id = self._create_content("policy", "active")
        response = self.super_admin.put(
            f"/api/admin/content/policy/{policy_id}",
            json={"expected_version": 1, "title": "纠错标题", "content": "纠错正文"},
        )
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            self.assertEqual(
                self._read_state("policy", policy_id), "active"
            )
            self.assertEqual(self._policy_push_count(policy_id), 0)
            row = get_db().execute(
                """
                SELECT title, content, version FROM government_policies
                WHERE id = ?
                """,
                (policy_id,),
            ).fetchone()
        self.assertEqual(row["title"], "纠错标题")
        self.assertEqual(row["content"], "纠错正文")
        self.assertEqual(row["version"], 2)

    def test_course_delete_preserves_progress(self):
        course_id = self._create_content("course", "published")
        with self.app.app_context():
            self._make_progress(course_id)
        self.super_admin.delete(
            f"/api/admin/content/course/{course_id}",
            json={"expected_version": 1},
        )
        with self.app.app_context():
            progress = int(
                get_db()
                .execute(
                    "SELECT COUNT(*) FROM agri_course_progress WHERE course_id = ?",
                    (course_id,),
                )
                .fetchone()[0]
            )
            from app.teacher_console.providers import (
                DatabaseTeacherCourseProvider,
            )

            provider_course = DatabaseTeacherCourseProvider().get_course(course_id)
        self.assertEqual(progress, 1)
        self.assertIsNone(provider_course)

    def test_every_managed_content_type_has_unpublish_delete_and_version_assertions(
        self,
    ):
        cases = (
            ("policy", "unpublish", "active", "unpublished"),
            ("policy", "delete", "active", None),
            ("news", "delete", "published", None),
            ("course", "unpublish", "published", "offline"),
            ("course", "delete", "published", None),
            ("job", "unpublish", "approved", "pending"),
            ("job", "delete", "approved", None),
            ("handcraft_video", "unpublish", "approved", "pending"),
            ("handcraft_video", "delete", "approved", None),
            ("comment", "delete", "visible", "hidden"),
            ("preset", "delete", "enabled", "disabled"),
        )
        for content_type, action, before, after in cases:
            with self.subTest(content_type=content_type, action=action):
                self._run_managed_case(content_type, action, before, after)
                self._assert_version_conflict_rejected(content_type)
                self._assert_history_preserved(content_type)

    def test_news_and_comment_do_not_support_unpublish(self):
        news_id = self._create_content("news", "published")
        response = self.super_admin.post(
            f"/api/admin/content/news/{news_id}/unpublish",
            json={"expected_version": 1},
        )
        self.assertEqual(response.status_code, 400)
        comment_id = self._create_content("comment", "visible")
        response = self.super_admin.post(
            f"/api/admin/content/comment/{comment_id}/unpublish",
            json={"expected_version": 1},
        )
        self.assertEqual(response.status_code, 400)

    def test_deleted_course_and_job_are_absent_from_review_queue(self):
        course_id = self._create_content("course", "published")
        job_id = self._create_content("job", "approved")
        with self.app.app_context():
            self._make_review_record("course_video", str(course_id), "pending")
            self._make_review_record("job_position", job_id, "pending")

        before = self.admin.get("/api/admin/review").get_json()["items"]
        before_ids = {item["content_id"] for item in before}
        self.assertIn(str(course_id), before_ids)
        self.assertIn(job_id, before_ids)

        self.super_admin.delete(
            f"/api/admin/content/course/{course_id}",
            json={"expected_version": 1},
        )
        self.super_admin.delete(
            f"/api/admin/content/job/{job_id}",
            json={"expected_version": 1},
        )

        after = self.admin.get("/api/admin/review").get_json()["items"]
        after_ids = {item["content_id"] for item in after}
        self.assertNotIn(str(course_id), after_ids)
        self.assertNotIn(job_id, after_ids)

    def test_review_queue_hides_tombstoned_course_with_lingering_record(self):
        course_id = self._create_content("course", "published")
        with self.app.app_context():
            self._make_review_record("course_video", str(course_id), "pending")
            # A tombstone that left its review projection behind must still be
            # filtered from the queue by the owner join (Task 24 migration).
            get_db().execute(
                "UPDATE courses SET deleted_at = ? WHERE id = ?",
                ("2026-09-21T12:00:00+08:00", course_id),
            )
            get_db().commit()
        items = self.admin.get("/api/admin/review").get_json()["items"]
        self.assertNotIn(
            str(course_id), {item["content_id"] for item in items}
        )

    def test_tombstoned_content_absent_from_dashboard_and_queue_counts(self):
        course_id = self._create_content("course", "published")
        job_id = self._create_content("job", "approved")
        video_id = self._create_content("handcraft_video", "approved")
        with self.app.app_context():
            self._make_review_record("course_video", str(course_id), "pending")
            self._make_review_record("job_position", job_id, "pending")
            self._make_review_record(
                "handcraft_teaching_video", video_id, "pending"
            )

        before = self.admin.get("/api/admin/content-dashboard").get_json()[
            "dashboard"
        ]

        self.super_admin.delete(
            f"/api/admin/content/course/{course_id}",
            json={"expected_version": 1},
        )
        self.super_admin.delete(
            f"/api/admin/content/job/{job_id}",
            json={"expected_version": 1},
        )
        self.super_admin.delete(
            f"/api/admin/content/handcraft_video/{video_id}",
            json={"expected_version": 1},
        )

        after = self.admin.get("/api/admin/content-dashboard").get_json()[
            "dashboard"
        ]
        self.assertEqual(
            after["published_course_count"], before["published_course_count"] - 1
        )
        self.assertEqual(
            after["active_job_count"], before["active_job_count"] - 1
        )
        self.assertEqual(
            after["pending_review"]["course_video"],
            before["pending_review"]["course_video"] - 1,
        )
        self.assertEqual(
            after["pending_review"]["job_position"],
            before["pending_review"]["job_position"] - 1,
        )
        self.assertEqual(
            after["pending_review"]["handcraft_teaching_video"],
            before["pending_review"]["handcraft_teaching_video"] - 1,
        )

        queue = self.admin.get("/api/admin/review").get_json()
        queue_ids = {item["content_id"] for item in queue["items"]}
        self.assertNotIn(str(course_id), queue_ids)
        self.assertNotIn(job_id, queue_ids)

        with self.app.app_context():
            video_ids = {
                item["video_id"]
                for item in list_managed_content("handcraft_video", {})
            }
        self.assertNotIn(video_id, video_ids)

    def test_content_routes_enforce_super_admin_role(self):
        policy_id = self._create_content("policy", "active")

        self.assertEqual(
            self.super_admin.get("/api/admin/content/policy").status_code, 200
        )
        self.assertEqual(
            self.super_admin.get(
                f"/api/admin/content/policy/{policy_id}"
            ).status_code,
            200,
        )

        for client in (self.admin, self.anonymous):
            expected = 403 if client is self.admin else 401
            self.assertEqual(
                client.get("/api/admin/content/policy").status_code, expected
            )
            self.assertEqual(
                client.get(f"/api/admin/content/policy/{policy_id}").status_code,
                expected,
            )
            self.assertEqual(
                client.put(
                    f"/api/admin/content/policy/{policy_id}",
                    json={"expected_version": 1, "title": "x", "content": "y"},
                ).status_code,
                expected,
            )
            self.assertEqual(
                client.post(
                    f"/api/admin/content/policy/{policy_id}/unpublish",
                    json={"expected_version": 1},
                ).status_code,
                expected,
            )
            self.assertEqual(
                client.delete(
                    f"/api/admin/content/policy/{policy_id}",
                    json={"expected_version": 1},
                ).status_code,
                expected,
            )

    def test_list_managed_content_filters_tombstones(self):
        kept_course = self._create_content("course", "published")
        dropped_course = self._create_content("course", "published")
        self.super_admin.delete(
            f"/api/admin/content/course/{dropped_course}",
            json={"expected_version": 1},
        )
        with self.app.app_context():
            course_ids = {
                item["id"] for item in list_managed_content("course", {})
            }
        self.assertIn(kept_course, course_ids)
        self.assertNotIn(dropped_course, course_ids)
