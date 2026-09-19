import sqlite3
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from werkzeug.security import generate_password_hash

from app import create_app
from app.db import get_db
from app.government_console.dashboard import get_government_dashboard
from app.government_console.errors import ProviderUnavailableError
from app.government_console.news import delete_news, publish_news
from app.government_console.policy import (
    delete_policy,
    publish_policy,
    unpublish_policy,
)
from app.government_console.providers import (
    set_employment_statistics_provider,
)
from app.government_console.views import (
    record_news_view,
    record_policy_view,
)


FORBIDDEN_KEYS = {
    "total_users",
    "role_distribution",
    "region_distribution",
    "direction_distribution",
    "user_details",
    "course_count",
    "learning_behavior_count",
    "progress",
    "completion_rate",
    "certificate_count",
}


def _walk_keys(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from _walk_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_keys(child)


class FakeEmploymentStatisticsProvider:
    def __init__(self, *, active: int, applications: int):
        self.active = active
        self.applications = applications

    def get_active_job_count(self):
        return self.active

    def get_cumulative_application_count(self):
        return self.applications


class GovernmentDashboardTests(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(Path(self.temp_dir.name) / "test.db"),
                "SECRET_KEY": "test-only-secret",
                "SESSION_HOURS": 24,
                "SESSION_COOKIE_SECURE": False,
            }
        )
        self.client = self.app.test_client()
        self._create_user("government01", "government")
        self._create_user("student01", "student")

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
                    "2026-09-19T09:00:00+08:00",
                    "2026-09-19T09:00:00+08:00",
                ),
            )
            get_db().commit()
            user_id = int(cursor.lastrowid)
        if role == "government":
            self.government_id = user_id
        return user_id

    def login(self, username: str):
        response = self.client.post(
            "/api/auth/login",
            json={"username": username, "password": "password8"},
        )
        self.assertEqual(response.status_code, 200)

    def publish_policy(self, **overrides):
        payload = {
            "actor_id": self.government_id,
            "request_id": "dashboard-policy-1",
            "title": "创业补贴",
            "content": "政策正文",
            "category_code": "entrepreneurship",
        }
        payload.update(overrides)
        with patch(
            "app.government_console.policy.emit_policy_published",
            return_value={"created_count": 1},
        ):
            return publish_policy(**payload)

    def publish_news(self, **overrides):
        payload = {
            "actor_id": self.government_id,
            "request_id": "dashboard-news-1",
            "title": "暴雨预警",
            "content": "注意防范",
            "category_code": "disaster_warning",
        }
        payload.update(overrides)
        return publish_news(**payload)

    def test_dashboard_has_exact_allowed_shape(self):
        with self.app.app_context():
            dashboard = get_government_dashboard()

        self.assertEqual(
            set(dashboard),
            {"employment", "policy", "news"},
        )
        self.assertEqual(
            set(dashboard["employment"]),
            {
                "active_job_count",
                "cumulative_application_count",
                "available",
            },
        )
        self.assertEqual(
            set(dashboard["policy"]),
            {
                "active_count",
                "unpublished_count",
                "total_count",
                "view_count",
            },
        )
        self.assertEqual(
            set(dashboard["news"]),
            {"total_count", "view_count"},
        )
        self.assertFalse(FORBIDDEN_KEYS.intersection(_walk_keys(dashboard)))

    def test_employment_placeholder_is_unavailable_not_zero(self):
        with self.app.app_context():
            dashboard = get_government_dashboard()

        self.assertEqual(
            dashboard["employment"],
            {
                "active_job_count": None,
                "cumulative_application_count": None,
                "available": False,
            },
        )

    def test_fake_09_provider_replaces_values_without_consumer_branch(self):
        set_employment_statistics_provider(
            self.app,
            FakeEmploymentStatisticsProvider(active=8, applications=21),
        )

        with self.app.app_context():
            dashboard = get_government_dashboard()

        self.assertEqual(dashboard["employment"]["active_job_count"], 8)
        self.assertEqual(
            dashboard["employment"]["cumulative_application_count"],
            21,
        )
        self.assertTrue(dashboard["employment"]["available"])

    def test_policy_and_news_metrics_count_current_rows_and_views(self):
        with self.app.app_context():
            first_policy = self.publish_policy()
            second_policy = self.publish_policy(request_id="dashboard-policy-2")
            deleted_policy = self.publish_policy(
                request_id="dashboard-policy-3"
            )
            first_news = self.publish_news()
            self.publish_news(request_id="dashboard-news-2")

            record_policy_view(first_policy["id"], "policy-view-1")
            record_policy_view(second_policy["id"], "policy-view-2")
            record_news_view(first_news["id"], "news-view-1")
            record_news_view(first_news["id"], "news-view-2")

            unpublish_policy(
                second_policy["id"],
                expected_version=second_policy["version"],
            )
            delete_policy(
                deleted_policy["id"],
                expected_version=deleted_policy["version"],
            )
            delete_news(
                first_news["id"],
                expected_version=first_news["version"],
            )

            dashboard = get_government_dashboard()

        self.assertEqual(
            dashboard["policy"],
            {
                "active_count": 1,
                "unpublished_count": 1,
                "total_count": 2,
                "view_count": 2,
            },
        )
        self.assertEqual(
            dashboard["news"],
            {"total_count": 1, "view_count": 0},
        )

    def test_dashboard_api_returns_exact_boundary_for_government(self):
        set_employment_statistics_provider(
            self.app,
            FakeEmploymentStatisticsProvider(active=8, applications=21),
        )
        self.login("government01")

        response = self.client.get("/api/government/dashboard")

        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertTrue(body["success"])
        dashboard = body["dashboard"]
        self.assertEqual(
            dashboard["employment"],
            {
                "active_job_count": 8,
                "cumulative_application_count": 21,
                "available": True,
            },
        )
        self.assertEqual(
            dashboard["policy"],
            {
                "active_count": 0,
                "unpublished_count": 0,
                "total_count": 0,
                "view_count": 0,
            },
        )
        self.assertEqual(
            dashboard["news"],
            {"total_count": 0, "view_count": 0},
        )
        self.assertFalse(FORBIDDEN_KEYS.intersection(_walk_keys(dashboard)))

    def test_dashboard_api_rejects_non_government_role(self):
        self.login("student01")

        response = self.client.get("/api/government/dashboard")

        self.assertEqual(response.status_code, 403)
        self.assertFalse(response.get_json()["success"])

    def test_dashboard_maps_sqlite_failure_to_unavailable(self):
        failure = sqlite3.OperationalError("database is locked")

        with self.app.app_context():
            with patch(
                "app.government_console.dashboard.get_db",
                side_effect=failure,
            ):
                with self.assertRaises(ProviderUnavailableError) as raised:
                    get_government_dashboard()

        self.assertIs(raised.exception.__cause__, failure)

    def test_dashboard_api_returns_503_on_sqlite_failure(self):
        self.login("government01")

        with patch(
            "app.government_console.dashboard.get_db",
            side_effect=sqlite3.OperationalError("database is locked"),
        ):
            response = self.client.get("/api/government/dashboard")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.get_json(),
            {
                "success": False,
                "message": "政务数据暂不可用",
                "details": {},
            },
        )
