import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from app import create_app
from app.db import get_db
from app.government_console.errors import (
    ProviderNotFoundError,
    ProviderValidationError,
)
from app.government_console.news import delete_news, publish_news
from app.government_console.policy import (
    delete_policy,
    publish_policy,
    unpublish_policy,
)
from app.government_console.providers import (
    DatabasePolicyNewsProvider,
    get_policy_news_provider,
)
from app.government_console.views import (
    record_news_view,
    record_policy_view,
)


class GovernmentViewTests(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(Path(self.temp_dir.name) / "test.db"),
            }
        )
        with self.app.app_context():
            cursor = get_db().execute(
                """
                INSERT INTO users (
                    username, password_hash, name, role, is_enabled,
                    created_at, updated_at
                )
                VALUES (
                    'government', 'hash', '政府用户', 'government', 1,
                    '2026-09-19T09:00:00+08:00',
                    '2026-09-19T09:00:00+08:00'
                )
                """
            )
            get_db().commit()
            self.government_id = int(cursor.lastrowid)

    def tearDown(self):
        self.temp_dir.cleanup()

    def create_policy(self, **overrides):
        values = {
            "actor_id": self.government_id,
            "request_id": "policy-view-1",
            "title": "创业补贴",
            "content": "补贴内容",
            "category_code": "entrepreneurship",
        }
        values.update(overrides)
        with patch(
            "app.government_console.policy.emit_policy_published",
            return_value={"created_count": 1},
        ):
            return publish_policy(**values)

    def create_news(self, **overrides):
        values = {
            "actor_id": self.government_id,
            "request_id": "news-view-1",
            "title": "暴雨预警",
            "content": "注意防范",
            "category_code": "disaster_warning",
        }
        values.update(overrides)
        return publish_news(**values)

    def test_policy_retry_counts_once_and_new_event_counts_again(self):
        with self.app.app_context():
            policy = self.create_policy()

            first = record_policy_view(policy["id"], "view-1")
            retry = record_policy_view(policy["id"], "view-1")
            second = record_policy_view(policy["id"], "view-2")

            self.assertEqual((first, retry, second), (1, 1, 2))
            self.assertEqual(self.policy_view_count(policy["id"]), 2)
            self.assertEqual(self.policy_event_count(policy["id"]), 2)

    def test_policy_view_rejects_unpublished_and_deleted_content(self):
        with self.app.app_context():
            policy = self.create_policy()
            unpublished = unpublish_policy(
                policy["id"],
                expected_version=policy["version"],
            )

            with self.assertRaises(ProviderNotFoundError):
                record_policy_view(policy["id"], "view-unpublished")
            self.assertEqual(self.policy_event_count(policy["id"]), 0)

            delete_policy(
                policy["id"],
                expected_version=unpublished["version"],
            )
            with self.assertRaises(ProviderNotFoundError):
                record_policy_view(policy["id"], "view-deleted")
            self.assertEqual(self.policy_event_count(policy["id"]), 0)

    def test_news_retry_counts_once_and_new_event_counts_again(self):
        with self.app.app_context():
            news = self.create_news()

            first = record_news_view(news["id"], "view-1")
            retry = record_news_view(news["id"], "view-1")
            second = record_news_view(news["id"], "view-2")

            self.assertEqual((first, retry, second), (1, 1, 2))
            self.assertEqual(self.news_view_count(news["id"]), 2)
            self.assertEqual(self.news_event_count(news["id"]), 2)

    def test_news_view_rejects_deleted_content(self):
        with self.app.app_context():
            news = self.create_news()
            delete_news(news["id"], expected_version=news["version"])

            with self.assertRaises(ProviderNotFoundError):
                record_news_view(news["id"], "view-deleted")
            self.assertEqual(self.news_event_count(news["id"]), 0)

    def test_database_provider_is_default_and_delegates_view_recording(self):
        with self.app.app_context():
            policy = self.create_policy()
            news = self.create_news()
            provider = get_policy_news_provider()

            self.assertIsInstance(provider, DatabasePolicyNewsProvider)
            self.assertEqual(
                provider.record_policy_view(policy["id"], "provider-policy"),
                1,
            )
            self.assertEqual(
                provider.record_news_view(news["id"], "provider-news"),
                1,
            )

    def test_view_event_id_must_be_non_empty_text(self):
        with self.app.app_context():
            policy = self.create_policy()
            news = self.create_news()

            for value in (None, "", " ", 123):
                with self.subTest(value=value):
                    with self.assertRaises(ProviderValidationError):
                        record_policy_view(policy["id"], value)
                    with self.assertRaises(ProviderValidationError):
                        record_news_view(news["id"], value)

    def policy_view_count(self, policy_id):
        return int(
            get_db().execute(
                """
                SELECT view_count
                FROM government_policies
                WHERE id = ?
                """,
                (policy_id,),
            ).fetchone()["view_count"]
        )

    def news_view_count(self, news_id):
        return int(
            get_db().execute(
                """
                SELECT view_count
                FROM government_news
                WHERE id = ?
                """,
                (news_id,),
            ).fetchone()["view_count"]
        )

    def policy_event_count(self, policy_id):
        return int(
            get_db().execute(
                """
                SELECT COUNT(*)
                FROM government_view_events
                WHERE content_type = 'policy' AND content_id = ?
                """,
                (policy_id,),
            ).fetchone()[0]
        )

    def news_event_count(self, news_id):
        return int(
            get_db().execute(
                """
                SELECT COUNT(*)
                FROM government_view_events
                WHERE content_type = 'news' AND content_id = ?
                """,
                (news_id,),
            ).fetchone()[0]
        )


if __name__ == "__main__":
    import unittest

    unittest.main()
