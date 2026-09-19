import sqlite3
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from app import create_app
from app.db import get_db
from app.government_console.errors import (
    ProviderUnavailableError,
    ProviderValidationError,
)
from app.government_console.news import delete_news, publish_news
from app.government_console.policy import (
    delete_policy,
    publish_policy,
    unpublish_policy,
)
from app.government_console.providers import DatabasePolicyNewsProvider


POLICY_CONTRACT_FIELDS = {
    "id",
    "title",
    "content",
    "category_code",
    "category_label",
    "published_at",
    "updated_at",
    "version",
}
NEWS_CONTRACT_FIELDS = set(POLICY_CONTRACT_FIELDS)


class GovernmentProviderContractTests(TestCase):
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
                    '2026-09-18T09:00:00+08:00',
                    '2026-09-18T09:00:00+08:00'
                )
                """
            )
            get_db().commit()
            self.government_id = int(cursor.lastrowid)
        self.provider = DatabasePolicyNewsProvider()

    def tearDown(self):
        self.temp_dir.cleanup()

    def publish_policy(
        self,
        *,
        request_id,
        title="政策",
        category_code="entrepreneurship",
        published_at=None,
        updated_at=None,
    ):
        with self.app.app_context():
            with patch(
                "app.government_console.policy.emit_policy_published",
                return_value={"created_count": 1},
            ):
                policy = publish_policy(
                    actor_id=self.government_id,
                    request_id=request_id,
                    title=title,
                    content=f"{title}正文",
                    category_code=category_code,
                )
            if published_at is not None or updated_at is not None:
                get_db().execute(
                    """
                    UPDATE government_policies
                    SET published_at = COALESCE(?, published_at),
                        updated_at = COALESCE(?, updated_at)
                    WHERE id = ?
                    """,
                    (published_at, updated_at, policy["id"]),
                )
                get_db().commit()
            return policy

    def publish_news(
        self,
        *,
        request_id,
        title="新闻",
        category_code="news",
        published_at=None,
        updated_at=None,
    ):
        with self.app.app_context():
            news = publish_news(
                actor_id=self.government_id,
                request_id=request_id,
                title=title,
                content=f"{title}正文",
                category_code=category_code,
            )
            if published_at is not None or updated_at is not None:
                get_db().execute(
                    """
                    UPDATE government_news
                    SET published_at = COALESCE(?, published_at),
                        updated_at = COALESCE(?, updated_at)
                    WHERE id = ?
                    """,
                    (published_at, updated_at, news["id"]),
                )
                get_db().commit()
            return news

    def test_policy_provider_returns_exact_normalized_contract(self):
        with self.app.app_context():
            policy = self.publish_policy(
                request_id="policy-contract",
                title="创业补贴",
                published_at="2026-09-17T18:00:00Z",
                updated_at="2026-09-17T18:30:00Z",
            )

            item = self.provider.get_published_policy(policy["id"])

        self.assertEqual(set(item), POLICY_CONTRACT_FIELDS)
        self.assertEqual(
            item,
            {
                "id": policy["id"],
                "title": "创业补贴",
                "content": "创业补贴正文",
                "category_code": "entrepreneurship",
                "category_label": "创业支持",
                "published_at": "2026-09-18T02:00:00+08:00",
                "updated_at": "2026-09-18T02:30:00+08:00",
                "version": 1,
            },
        )

    def test_policy_list_hides_unpublished_and_orders_by_time_then_id(self):
        with self.app.app_context():
            active = self.publish_policy(
                request_id="policy-active",
                title="B",
                published_at="2026-09-18T10:00:00+08:00",
            )
            older = self.publish_policy(
                request_id="policy-older",
                title="A",
                published_at="2026-09-17T10:00:00+08:00",
            )
            tied = self.publish_policy(
                request_id="policy-tied",
                title="D",
                published_at="2026-09-18T10:00:00+08:00",
            )
            hidden = self.publish_policy(
                request_id="policy-hidden",
                title="C",
                published_at="2026-09-18T11:00:00+08:00",
            )
            unpublish_policy(hidden["id"], expected_version=hidden["version"])

            items = self.provider.list_published_policies(
                category="entrepreneurship"
            )
            hidden_item = self.provider.get_published_policy(hidden["id"])

            delete_policy(older["id"], expected_version=older["version"])
            deleted_item = self.provider.get_published_policy(older["id"])
            remaining_ids = {
                item["id"]
                for item in self.provider.list_published_policies(
                    category="entrepreneurship"
                )
            }

        self.assertEqual(
            [item["id"] for item in items],
            [*sorted((active["id"], tied["id"])), older["id"]],
        )
        self.assertIsNone(hidden_item)
        self.assertIsNone(deleted_item)
        self.assertNotIn(older["id"], remaining_ids)

    def test_news_provider_returns_exact_contract_and_filters_deleted_content(
        self,
    ):
        with self.app.app_context():
            news = self.publish_news(
                request_id="news-contract",
                title="暴雨预警",
                category_code="disaster_warning",
                published_at="2026-09-17T18:00:00Z",
                updated_at="2026-09-17T18:30:00Z",
            )
            other = self.publish_news(
                request_id="news-other",
                title="本地新闻",
                category_code="news",
            )

            item = self.provider.get_published_news(news["id"])
            filtered = self.provider.list_published_news(
                category="disaster_warning"
            )
            delete_news(news["id"], expected_version=news["version"])
            deleted_item = self.provider.get_published_news(news["id"])
            remaining = self.provider.list_published_news()

        self.assertEqual(set(item), NEWS_CONTRACT_FIELDS)
        self.assertEqual(
            item,
            {
                "id": news["id"],
                "title": "暴雨预警",
                "content": "暴雨预警正文",
                "category_code": "disaster_warning",
                "category_label": "灾害预警",
                "published_at": "2026-09-18T02:00:00+08:00",
                "updated_at": "2026-09-18T02:30:00+08:00",
                "version": 1,
            },
        )
        self.assertEqual([entry["id"] for entry in filtered], [news["id"]])
        self.assertIsNone(deleted_item)
        self.assertEqual([entry["id"] for entry in remaining], [other["id"]])

    def test_provider_rejects_unknown_category_filters(self):
        with self.app.app_context():
            with self.assertRaises(ProviderValidationError):
                self.provider.list_published_policies(category="unknown")
            with self.assertRaises(ProviderValidationError):
                self.provider.list_published_news(category="unknown")

    def test_provider_records_views_without_exposing_database(self):
        with self.app.app_context():
            policy = self.publish_policy(request_id="policy-view")
            news = self.publish_news(request_id="news-view")

            self.assertEqual(
                self.provider.record_policy_view(policy["id"], "view-1"),
                1,
            )
            self.assertEqual(
                self.provider.record_policy_view(policy["id"], "view-1"),
                1,
            )
            self.assertEqual(
                self.provider.record_policy_view(policy["id"], "view-2"),
                2,
            )
            self.assertEqual(
                self.provider.record_news_view(news["id"], "view-1"),
                1,
            )
            self.assertEqual(
                self.provider.record_news_view(news["id"], "view-1"),
                1,
            )
            self.assertEqual(
                self.provider.record_news_view(news["id"], "view-2"),
                2,
            )

    def test_provider_reads_map_sqlite_failures_to_unavailable(self):
        failure = sqlite3.OperationalError("database is locked")
        operations = {
            "list policies": self.provider.list_published_policies,
            "get policy": lambda: self.provider.get_published_policy("policy-1"),
            "list news": self.provider.list_published_news,
            "get news": lambda: self.provider.get_published_news("news-1"),
        }

        with self.app.app_context():
            with (
                patch(
                    "app.government_console.policy.get_db",
                    side_effect=failure,
                ),
                patch(
                    "app.government_console.news.get_db",
                    side_effect=failure,
                ),
            ):
                for label, operation in operations.items():
                    with self.subTest(operation=label):
                        with self.assertRaises(
                            ProviderUnavailableError
                        ) as raised:
                            operation()
                        self.assertIs(raised.exception.__cause__, failure)

    def test_provider_views_map_sqlite_failures_to_unavailable(self):
        failure = sqlite3.OperationalError("database is locked")
        operations = {
            "record policy view": lambda: self.provider.record_policy_view(
                "policy-1",
                "view-1",
            ),
            "record news view": lambda: self.provider.record_news_view(
                "news-1",
                "view-1",
            ),
        }

        with self.app.app_context():
            with patch(
                "app.government_console.views.get_db",
                side_effect=failure,
            ):
                for label, operation in operations.items():
                    with self.subTest(operation=label):
                        with self.assertRaises(
                            ProviderUnavailableError
                        ) as raised:
                            operation()
                        self.assertIs(raised.exception.__cause__, failure)


if __name__ == "__main__":
    import unittest

    unittest.main()
