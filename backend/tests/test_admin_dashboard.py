from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from werkzeug.security import generate_password_hash

from app import create_app
from app.admin_console.moderation import FEEDBACK_STATUS_VALUES
from app.db import get_db
from app.enterprise_console.providers import (
    set_employment_statistics_provider,
)
from app.handcraft_inheritance.presets import PLACEHOLDER_REWARDS


FORBIDDEN_ADMIN_DASHBOARD_KEYS = {
    "total_users",
    "role_distribution",
    "region_distribution",
    "direction_distribution",
    "student_total",
    "student_count",
    "user_details",
    "course_count",
    "average_progress",
    "completion_rate",
    "progress",
    "certificate_count",
    "quiz_attempt_count",
    "quiz_average_score",
    "training_progress",
    "learning_behavior_count",
}


def walk_keys(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from walk_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_keys(child)


class FailingEmploymentStatisticsProvider:
    def get_active_job_count(self):
        raise sqlite3.OperationalError("job source unavailable")

    def get_cumulative_application_count(self):
        raise sqlite3.OperationalError("job source unavailable")


class AdminDashboardTests(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(
                    Path(self.temp_dir.name) / "test.db"
                ),
                "SECRET_KEY": "test-only-secret",
                "SESSION_HOURS": 24,
                "SESSION_COOKIE_SECURE": False,
            }
        )
        with self.app.app_context():
            self.super_admin_id = self._create_user(
                "super-admin",
                "super_admin",
            )
            self.admin_id = self._create_user("ordinary-admin", "admin")
            self.student_id = self._create_user("student-1", "student")
            self.disabled_student_id = self._create_user(
                "student-disabled",
                "student",
                enabled=False,
            )
            self.teacher_id = self._create_user("teacher-1", "teacher")
            self.enterprise_id = self._create_user(
                "enterprise-1",
                "enterprise",
            )
            self.government_id = self._create_user(
                "government-1",
                "government",
            )
            self._seed_dashboard_sources()

    def tearDown(self):
        self.temp_dir.cleanup()

    def _create_user(
        self,
        username: str,
        role: str,
        *,
        enabled: bool = True,
    ) -> int:
        cursor = get_db().execute(
            """
            INSERT INTO users (
                username, password_hash, name, role, is_enabled,
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                username,
                generate_password_hash("password8"),
                username,
                role,
                int(enabled),
                "2026-09-20T10:00:00+08:00",
                "2026-09-20T10:00:00+08:00",
            ),
        )
        get_db().commit()
        return int(cursor.lastrowid)

    def _seed_dashboard_sources(self):
        db = get_db()
        self.published_course_count = int(
            db.execute(
                "SELECT COUNT(*) FROM courses WHERE status = 'published'"
            ).fetchone()[0]
        )
        db.execute(
            """
            INSERT INTO interest_tags (group_key, name, sort_order, is_active)
            VALUES ('job', '农业运营', 1, 1)
            """
        )
        category_id = int(
            db.execute(
                "SELECT id FROM interest_tags WHERE name = '农业运营'"
            ).fetchone()["id"]
        )

        for course_id, status in enumerate(
            ("published", "published", "draft", "pending"),
            start=1,
        ):
            db.execute(
                """
                INSERT INTO courses (
                    id, title, direction, status, summary, teacher_name,
                    teacher_id, version, content_tags_json, created_at,
                    updated_at
                )
                VALUES (?, ?, 'agriculture', ?, '', 'teacher', ?, 1, '[]', ?, ?)
                """,
                (
                    course_id,
                    f"course-{course_id}",
                    status,
                    self.teacher_id,
                    "2026-09-20T10:00:00+08:00",
                    "2026-09-20T10:00:00+08:00",
                ),
            )
        self.published_course_count += 2

        for index, (status, deleted) in enumerate(
            (
                ("approved", False),
                ("approved", False),
                ("approved", False),
                ("pending", False),
                ("approved", True),
            ),
            start=1,
        ):
            db.execute(
                """
                INSERT INTO job_positions (
                    job_id, enterprise_id, title, salary, location,
                    category_id, category_name, description, review_status,
                    version, published_at, deleted_at, created_at, updated_at
                )
                VALUES (?, ?, ?, '5000', '广州', ?, '农业运营', '岗位',
                        ?, 1, ?, ?, ?, ?)
                """,
                (
                    f"job-{index}",
                    self.enterprise_id,
                    f"岗位 {index}",
                    category_id,
                    status,
                    "2026-09-20T10:00:00+08:00",
                    (
                        "2026-09-20T11:00:00+08:00"
                        if deleted
                        else None
                    ),
                    "2026-09-20T10:00:00+08:00",
                    "2026-09-20T10:00:00+08:00",
                ),
            )

        for index, (content_type, review_status) in enumerate(
            (
                ("course_video", "pending"),
                ("course_video", "pending"),
                ("job_position", "pending"),
                ("handcraft_teaching_video", "pending"),
                ("course_video", "approved"),
            ),
            start=1,
        ):
            db.execute(
                """
                INSERT INTO content_review_records (
                    content_type, content_id, submitter_id, review_status,
                    version, payload_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, 1, '{}', ?, ?)
                """,
                (
                    content_type,
                    f"review-{index}",
                    self.teacher_id,
                    review_status,
                    "2026-09-20T10:00:00+08:00",
                    "2026-09-20T10:00:00+08:00",
                ),
            )

        for index, visible in enumerate((0, 0, 1), start=1):
            db.execute(
                """
                INSERT INTO content_comments (
                    comment_id, content_type, content_id, author_id, body,
                    is_visible, created_at, updated_at
                )
                VALUES (?, 'course_video', ?, ?, '评论', ?, ?, ?)
                """,
                (
                    f"comment-{index}",
                    f"course-{index}",
                    self.student_id,
                    visible,
                    "2026-09-20T10:00:00+08:00",
                    "2026-09-20T10:00:00+08:00",
                ),
            )

        for index, status in enumerate(
            ("confirmed", "rejected", "pending"),
            start=1,
        ):
            db.execute(
                """
                INSERT INTO comment_reports (
                    report_id, comment_id, reporter_id, reason, status,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, '违规', ?, ?, ?)
                """,
                (
                    f"report-{index}",
                    f"comment-{index}",
                    self.student_id,
                    status,
                    "2026-09-20T10:00:00+08:00",
                    "2026-09-20T10:00:00+08:00",
                ),
            )

        for index, status in enumerate(
            ("processed", "closed", "pending"),
            start=1,
        ):
            db.execute(
                """
                INSERT INTO feedback_records (
                    feedback_id, submitter_id, body, status, idempotency_key,
                    created_at, updated_at
                )
                VALUES (?, ?, '反馈', ?, ?, ?, ?)
                """,
                (
                    f"feedback-{index}",
                    self.student_id,
                    status,
                    f"feedback-key-{index}",
                    "2026-09-20T10:00:00+08:00",
                    "2026-09-20T10:00:00+08:00",
                ),
            )

        # `reward_stock` is a real SUM over `admin_rewards`, so its
        # expected value is owned by the seeders, not by this test: Task
        # 10's `seed_demo_rewards` turned 05's PLACEHOLDER_REWARDS into
        # rows during database init (stock 10 + 8 + 6 + 8 = 32), and the
        # loop below adds this fixture's own rows.
        self.demo_reward_stock = sum(
            int(reward["stock"]) for reward in PLACEHOLDER_REWARDS
        )
        self.seeded_reward_stock = 0
        for index, stock in enumerate((5, 4), start=1):
            db.execute(
                """
                INSERT INTO admin_rewards (
                    reward_id, name, points_cost, stock, is_online,
                    source_available, version, created_at, updated_at
                )
                VALUES (?, ?, 10, ?, 1, 1, 1, ?, ?)
                """,
                (
                    f"reward-{index}",
                    f"奖品 {index}",
                    stock,
                    "2026-09-20T10:00:00+08:00",
                    "2026-09-20T10:00:00+08:00",
                ),
            )
            self.seeded_reward_stock += stock

        for index, status in enumerate(
            ("pending", "issued", "canceled"),
            start=1,
        ):
            cursor = db.execute(
                """
                INSERT INTO redemptions (
                    user_id, reward_id, reward_name, reward_snapshot_json,
                    points_cost, request_id, status, created_at, updated_at
                )
                VALUES (?, 'reward-1', '奖品 1', '{}', 10, ?, ?, ?, ?)
                """,
                (
                    self.student_id,
                    f"redemption-{index}",
                    status,
                    "2026-09-20T10:00:00+08:00",
                    "2026-09-20T10:00:00+08:00",
                ),
            )
            db.execute(
                """
                INSERT INTO fulfillments (
                    redemption_id, user_id, status, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    int(cursor.lastrowid),
                    self.student_id,
                    status,
                    "2026-09-20T10:00:00+08:00",
                    "2026-09-20T10:00:00+08:00",
                ),
            )

        for index, (transaction_type, delta) in enumerate(
            (("award", 10), ("award", 15), ("refund", 5)),
            start=1,
        ):
            db.execute(
                """
                INSERT INTO points_transactions (
                    user_id, transaction_type, source_module, source_event_id,
                    delta, balance_after, metadata_json, created_at
                )
                VALUES (?, ?, 'dashboard-test', ?, ?, 20, '{}', ?)
                """,
                (
                    self.student_id,
                    transaction_type,
                    f"points-{index}",
                    delta,
                    "2026-09-20T10:00:00+08:00",
                ),
            )

        for index, view_count in enumerate((7, 11), start=1):
            db.execute(
                """
                INSERT INTO government_policies (
                    id, title, content, category_code, status, view_count,
                    version, created_by, published_at, created_at, updated_at
                )
                VALUES (?, ?, '政策', 'general', 'active', ?, 1, ?, ?, ?, ?)
                """,
                (
                    f"policy-{index}",
                    f"政策 {index}",
                    view_count,
                    self.government_id,
                    "2026-09-20T10:00:00+08:00",
                    "2026-09-20T10:00:00+08:00",
                    "2026-09-20T10:00:00+08:00",
                ),
            )

        db.execute(
            """
            INSERT INTO government_news (
                id, title, content, category_code, view_count, version,
                created_by, published_at, created_at, updated_at
            )
            VALUES ('news-1', '新闻 1', '新闻', 'news', 13, 1, ?, ?, ?, ?)
            """,
            (
                self.government_id,
                "2026-09-20T10:00:00+08:00",
                "2026-09-20T10:00:00+08:00",
                "2026-09-20T10:00:00+08:00",
            ),
        )
        db.commit()

    def _login(self, username: str):
        client = self.app.test_client()
        response = client.post(
            "/api/auth/login",
            json={"username": username, "password": "password8"},
        )
        self.assertEqual(response.status_code, 200)
        return client

    def test_content_dashboard_recursively_excludes_user_and_training_keys(self):
        response = self._login("ordinary-admin").get(
            "/api/admin/content-dashboard"
        )

        self.assertEqual(response.status_code, 200)
        dashboard = response.get_json()["dashboard"]
        self.assertFalse(
            FORBIDDEN_ADMIN_DASHBOARD_KEYS.intersection(
                walk_keys(dashboard)
            )
        )
        self.assertEqual(dashboard["pending_review"]["course_video"], 2)

    def test_content_dashboard_has_exact_allowed_metrics_and_real_counts(self):
        response = self._login("ordinary-admin").get(
            "/api/admin/content-dashboard"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json()["dashboard"],
            {
                "pending_review": {
                    "course_video": 2,
                    "job_position": 1,
                    "handcraft_teaching_video": 1,
                },
                "published_course_count": self.published_course_count,
                "active_job_count": 3,
                "comment_processed_count": 2,
                "report_processed_count": 2,
                "feedback_processed_count": 2,
                # 05's PLACEHOLDER_REWARDS (32, seeded by Task 10's
                # `seed_demo_rewards`) plus this fixture's reward-1 (5)
                # and reward-2 (4).
                "reward_stock": (
                    self.demo_reward_stock + self.seeded_reward_stock
                ),
                "pending_fulfillment_count": 1,
            },
        )

    def test_super_admin_dashboard_contains_platform_user_and_training_metrics(self):
        response = self._login("super-admin").get("/api/admin/dashboard")

        self.assertEqual(response.status_code, 200)
        dashboard = response.get_json()["dashboard"]
        self.assertEqual(dashboard["total_users"], 7)
        self.assertEqual(
            dashboard["role_distribution"],
            {
                "student": 2,
                "teacher": 1,
                "enterprise": 1,
                "government": 1,
                "admin": 1,
                "super_admin": 1,
            },
        )
        self.assertEqual(dashboard["student_count"], 2)
        self.assertEqual(
            dashboard["published_course_count"],
            self.published_course_count,
        )
        self.assertEqual(dashboard["active_job_count"], 3)
        self.assertEqual(dashboard["policy_count"], 2)
        self.assertEqual(dashboard["policy_view_count"], 18)
        self.assertEqual(dashboard["news_count"], 1)
        self.assertEqual(dashboard["news_view_count"], 13)
        self.assertEqual(dashboard["points_issued"], 25)
        self.assertEqual(dashboard["redemption_count"], 3)
        self.assertEqual(dashboard["pending_fulfillment_count"], 1)

    def test_dashboard_routes_enforce_role_boundaries(self):
        ordinary = self._login("ordinary-admin")
        super_admin = self._login("super-admin")
        anonymous = self.app.test_client()

        self.assertEqual(
            ordinary.get("/api/admin/content-dashboard").status_code,
            200,
        )
        self.assertEqual(ordinary.get("/api/admin/dashboard").status_code, 403)
        self.assertEqual(
            super_admin.get("/api/admin/content-dashboard").status_code,
            200,
        )
        self.assertEqual(super_admin.get("/api/admin/dashboard").status_code, 200)
        self.assertEqual(
            anonymous.get("/api/admin/content-dashboard").status_code,
            401,
        )

    def test_assert_boundary_rejects_nested_forbidden_keys(self):
        from app.admin_console.dashboard import (
            assert_admin_dashboard_boundary,
        )

        dashboard = {
            "pending_review": {
                "items": [{"nested": {"student_count": 1}}],
            },
        }

        with self.assertRaises(AssertionError):
            assert_admin_dashboard_boundary(dashboard)

    def test_assert_boundary_rejects_forbidden_keys_at_any_depth(self):
        from app.admin_console.dashboard import (
            assert_admin_dashboard_boundary,
        )

        dashboard = {"pending_review": [{"nested": {"total_users": 1}}]}

        with self.assertRaises(AssertionError) as raised:
            assert_admin_dashboard_boundary(dashboard)

        self.assertIn("total_users", str(raised.exception))

        # Recursion is the contract, so every exclusion key must be
        # rejected from inside a nested list of dicts, not only from the
        # dashboard surface.
        for key in sorted(FORBIDDEN_ADMIN_DASHBOARD_KEYS):
            nested = {"pending_review": [{"nested": {key: 0}}]}
            with self.assertRaises(AssertionError, msg=key):
                assert_admin_dashboard_boundary(nested)

    def test_walk_keys_descends_into_nested_dicts_and_lists(self):
        nested = {"pending_review": [{"nested": {"total_users": 1}}]}

        self.assertEqual(
            set(walk_keys(nested)),
            {"pending_review", "nested", "total_users"},
        )

    def test_source_failures_are_unavailable_not_zero(self):
        set_employment_statistics_provider(
            self.app,
            FailingEmploymentStatisticsProvider(),
        )
        client = self._login("ordinary-admin")

        with patch(
            "app.admin_console.dashboard.get_db",
            side_effect=sqlite3.OperationalError("database unavailable"),
        ):
            response = client.get("/api/admin/content-dashboard")

        self.assertEqual(response.status_code, 200)
        dashboard = response.get_json()["dashboard"]
        unavailable = {"available": False, "value": None}
        self.assertEqual(
            dashboard["pending_review"]["course_video"],
            unavailable,
        )
        self.assertEqual(
            dashboard["published_course_count"],
            unavailable,
        )
        self.assertEqual(dashboard["active_job_count"], unavailable)
        self.assertEqual(dashboard["reward_stock"], unavailable)
        self.assertEqual(
            dashboard["pending_fulfillment_count"],
            unavailable,
        )

    def test_processed_feedback_predicates_cover_the_same_statuses(self):
        """Pin the feedback "handled" reading while the column is CHECK-less.

        `feedback_records.status` is a bare `TEXT NOT NULL DEFAULT
        'pending'` (db.py), so nothing in the schema polices the value
        space. The dashboard counts a handled row with `status IN
        ('processed', 'closed')`, and the console's other reading of
        "answered" is exactly "left pending". The fixture seeds one row
        per canonical status from `FEEDBACK_STATUS_VALUES`, so both
        predicates must classify every stored status alike: the counted
        set has to equal the canonical set minus `pending`. Adding a
        fourth status without teaching it to the dashboard predicate
        turns this red.
        """
        with self.app.app_context():
            stored_statuses = {
                str(row["status"])
                for row in get_db().execute(
                    "SELECT DISTINCT status FROM feedback_records"
                ).fetchall()
            }
            counted_by_dashboard = {
                str(row["status"])
                for row in get_db().execute(
                    """
                    SELECT DISTINCT status
                    FROM feedback_records
                    WHERE status IN ('processed', 'closed')
                    """
                ).fetchall()
            }
            counted_as_handled = {
                str(row["status"])
                for row in get_db().execute(
                    """
                    SELECT DISTINCT status
                    FROM feedback_records
                    WHERE status <> 'pending'
                    """
                ).fetchall()
            }

        self.assertEqual(stored_statuses, set(FEEDBACK_STATUS_VALUES))
        self.assertEqual(counted_by_dashboard, counted_as_handled)
        self.assertEqual(
            counted_by_dashboard,
            set(FEEDBACK_STATUS_VALUES) - {"pending"},
        )


if __name__ == "__main__":
    import unittest

    unittest.main()
