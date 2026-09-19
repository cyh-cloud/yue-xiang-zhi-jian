import tempfile
from pathlib import Path
from unittest import TestCase

from werkzeug.security import generate_password_hash

from app import create_app
from app.db import get_db
from app.government_console.providers import (
    get_policy_news_provider,
    set_employment_statistics_provider,
)
from app.messaging.source_provider import register_messaging_source_provider


FORBIDDEN_DASHBOARD_KEYS = {
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


class StaticMessagingSourceProvider:
    def __init__(self, policy_subscribers):
        self.policy_subscribers = policy_subscribers

    def has_application_relationship(self, student_id, enterprise_id):
        return False

    def list_applied_enterprise_ids(self, student_id):
        return []

    def list_applicant_student_ids(self, enterprise_id):
        return []

    def list_policy_subscriber_ids(self, category):
        return self.policy_subscribers.get(category, [])

    def list_product_subscriber_ids(self, product_key):
        return []


class FakeEmploymentStatisticsProvider:
    def get_active_job_count(self):
        return 8

    def get_cumulative_application_count(self):
        return 21


class GovernmentIntegrationTests(TestCase):
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
        self.government_id = self._create_user("government01", "government")
        self.student_id = self._create_user("student01", "student")
        register_messaging_source_provider(
            self.app,
            StaticMessagingSourceProvider(
                {"创业支持": [self.student_id]},
            ),
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def _create_user(self, username, role):
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
            return int(cursor.lastrowid)

    def login_government(self):
        response = self.client.post(
            "/api/auth/login",
            json={"username": "government01", "password": "password8"},
        )
        self.assertEqual(response.status_code, 200)

    def subscriber_notification_titles(self):
        with self.app.app_context():
            return [
                str(row["title"])
                for row in get_db()
                .execute(
                    """
                    SELECT title
                    FROM system_notifications
                    WHERE recipient_id = ?
                    ORDER BY id
                    """,
                    (self.student_id,),
                )
                .fetchall()
            ]

    def test_government_console_end_to_end(self):
        self.login_government()
        policy = self.client.post(
            "/api/government/policies",
            json={
                "request_id": "policy-e2e",
                "title": "创业支持政策",
                "content": "正文",
                "category_code": "entrepreneurship",
            },
        ).get_json()["policy"]
        self.assertEqual(
            self.subscriber_notification_titles(),
            ["创业支持政策"],
        )

        with self.app.app_context():
            provider = get_policy_news_provider()
            self.assertEqual(
                provider.record_policy_view(policy["id"], "view-1"),
                1,
            )
            self.assertEqual(
                provider.record_policy_view(policy["id"], "view-1"),
                1,
            )

        dashboard = self.client.get(
            "/api/government/dashboard"
        ).get_json()["dashboard"]
        self.assertEqual(dashboard["policy"]["active_count"], 1)
        self.assertEqual(dashboard["policy"]["view_count"], 1)
        self.assertFalse(
            FORBIDDEN_DASHBOARD_KEYS.intersection(_walk_keys(dashboard))
        )

    def test_relist_does_not_push_and_news_has_no_unpublish_path(self):
        self.login_government()
        policy = self.client.post(
            "/api/government/policies",
            json={
                "request_id": "policy-lifecycle",
                "title": "创业支持政策",
                "content": "正文",
                "category_code": "entrepreneurship",
            },
        ).get_json()["policy"]
        unpublished = self.client.post(
            f"/api/government/policies/{policy['id']}/unpublish",
            json={"expected_version": policy["version"]},
        ).get_json()["policy"]
        self.client.post(
            f"/api/government/policies/{policy['id']}/relist",
            json={"expected_version": unpublished["version"]},
        )
        self.assertEqual(
            self.subscriber_notification_titles(),
            ["创业支持政策"],
        )

        news = self.client.post(
            "/api/government/news",
            json={
                "request_id": "news-lifecycle",
                "title": "本地新闻",
                "content": "新闻正文",
                "category_code": "news",
            },
        ).get_json()["news"]
        self.assertEqual(
            self.subscriber_notification_titles(),
            ["创业支持政策"],
        )
        with self.app.app_context():
            provider = get_policy_news_provider()
            published_news = provider.get_published_news(news["id"])
        self.assertEqual(
            set(published_news),
            {
                "id",
                "title",
                "content",
                "category_code",
                "category_label",
                "published_at",
                "updated_at",
                "version",
            },
        )
        self.assertEqual(published_news["category_label"], "新闻")

        for action in ("unpublish", "relist"):
            response = self.client.post(
                f"/api/government/news/{news['id']}/{action}",
                json={"expected_version": news["version"]},
            )
            self.assertEqual(response.status_code, 404)

        deleted = self.client.delete(
            f"/api/government/news/{news['id']}",
            json={"expected_version": news["version"]},
        )
        self.assertEqual(deleted.status_code, 200)
        with self.app.app_context():
            provider = get_policy_news_provider()
            self.assertIsNone(provider.get_published_news(news["id"]))
            self.assertEqual(provider.list_published_news(), [])

    def test_employment_placeholder_and_provider_replacement(self):
        self.login_government()
        initial = self.client.get(
            "/api/government/dashboard"
        ).get_json()["dashboard"]["employment"]
        self.assertEqual(
            initial,
            {
                "active_job_count": None,
                "cumulative_application_count": None,
                "available": False,
            },
        )

        set_employment_statistics_provider(
            self.app,
            FakeEmploymentStatisticsProvider(),
        )
        replaced = self.client.get(
            "/api/government/dashboard"
        ).get_json()["dashboard"]["employment"]
        self.assertEqual(
            replaced,
            {
                "active_job_count": 8,
                "cumulative_application_count": 21,
                "available": True,
            },
        )

    def test_government_module_has_no_ai_review_or_09_dependency(self):
        source = "\n".join(
            path.read_text(encoding="utf-8")
            for path in Path("app/government_console").glob("*.py")
        )
        self.assertNotIn("ContentReviewProvider", source)
        self.assertNotIn("get_ai_client", source)
        self.assertNotIn("complete_json", source)
        self.assertNotIn("ai_unavailable", source)
        self.assertNotIn("FROM jobs", source)
        self.assertNotIn("FROM applications", source)
        self.assertNotIn("job_positions", source)
        self.assertNotIn("employment_applications", source)


if __name__ == "__main__":
    import unittest

    unittest.main()
