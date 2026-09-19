import tempfile
import unittest
from pathlib import Path

from app import create_app
from app.db import get_db
from app.government_console.dashboard import get_government_dashboard
from app.government_console.news import delete_news, publish_news
from app.government_console.policy import (
    delete_policy,
    publish_policy,
    relist_policy,
    unpublish_policy,
)
from app.government_console.providers import get_policy_news_provider
from app.local_resources import (
    get_news,
    get_policy,
    record_news_view,
    record_policy_view,
    set_policy_subscription,
)
from app.local_resources.errors import LocalResourceNotFoundError


class LocalResourcesIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(
                    Path(self.temp_dir.name) / "test.db"
                ),
                "SECRET_KEY": "test-only-secret",
            }
        )
        with self.app.app_context():
            self.government_id = self._insert_user(
                "government01",
                "government",
            )
            self.student_id = self._insert_user("student01", "student")

    def tearDown(self):
        self.temp_dir.cleanup()

    def _insert_user(self, username, role):
        cursor = get_db().execute(
            """
            INSERT INTO users (
                username, password_hash, name, role, is_enabled,
                created_at, updated_at
            )
            VALUES (?, 'hash', ?, ?, 1, ?, ?)
            """,
            (
                username,
                username,
                role,
                "2026-09-20T00:00:00+08:00",
                "2026-09-20T00:00:00+08:00",
            ),
        )
        get_db().commit()
        return int(cursor.lastrowid)

    def test_policy_subscribe_publish_view_unpublish_relist_delete_flow(
        self,
    ):
        with self.app.app_context():
            set_policy_subscription(
                self.student_id,
                "ecommerce",
                True,
            )
            policy = publish_policy(
                actor_id=self.government_id,
                request_id="policy-1",
                title="直播培训补贴",
                content="正文",
                category_code="ecommerce",
            )
            visible = get_policy_news_provider().get_published_policy(
                policy["id"]
            )
            first = record_policy_view(policy["id"], "view-1")
            retry = record_policy_view(policy["id"], "view-1")
            second = record_policy_view(policy["id"], "view-2")
            notifications = get_db().execute(
                """
                SELECT recipient_id, title, body
                FROM system_notifications
                WHERE event_type = 'policy_published'
                """
            ).fetchall()

            unpublished = unpublish_policy(
                policy["id"],
                expected_version=policy["version"],
            )
            self.assertIsNone(
                get_policy_news_provider().get_published_policy(
                    policy["id"]
                )
            )
            with self.assertRaises(LocalResourceNotFoundError):
                get_policy(policy["id"])
            with self.assertRaises(LocalResourceNotFoundError):
                record_policy_view(policy["id"], "view-unpublished")

            relisted = relist_policy(
                policy["id"],
                expected_version=unpublished["version"],
            )
            self.assertEqual(
                get_policy_news_provider().get_published_policy(
                    policy["id"]
                )["title"],
                "直播培训补贴",
            )
            notification_count_after_relist = get_db().execute(
                """
                SELECT COUNT(*) AS count
                FROM system_notifications
                WHERE event_type = 'policy_published'
                """
            ).fetchone()["count"]
            self.assertEqual(notification_count_after_relist, 1)

            view_count_before_delete = get_government_dashboard()["policy"][
                "view_count"
            ]
            delete_policy(
                policy["id"],
                expected_version=relisted["version"],
            )
            view_count_after_delete = get_government_dashboard()["policy"][
                "view_count"
            ]
            with self.assertRaises(LocalResourceNotFoundError):
                get_policy(policy["id"])
            with self.assertRaises(LocalResourceNotFoundError):
                record_policy_view(policy["id"], "view-deleted")
            retained = get_db().execute(
                """
                SELECT recipient_id, title, body, source_available
                FROM system_notifications
                WHERE event_type = 'policy_published'
                """
            ).fetchall()

        self.assertEqual(visible["category_label"], "电商")
        self.assertEqual((first, retry, second), (1, 1, 2))
        self.assertEqual(
            [row["recipient_id"] for row in notifications],
            [self.student_id],
        )
        self.assertEqual(notifications[0]["body"], "政策类别：电商")
        self.assertEqual(view_count_before_delete, 2)
        self.assertEqual(view_count_after_delete, 0)
        self.assertEqual(len(retained), 1)
        self.assertEqual(retained[0]["title"], "直播培训补贴")
        self.assertEqual(retained[0]["body"], "政策类别：电商")
        self.assertEqual(retained[0]["source_available"], 0)

    def test_news_publish_view_delete_has_no_subscription_or_down_state(
        self,
    ):
        with self.app.app_context():
            news = publish_news(
                actor_id=self.government_id,
                request_id="news-1",
                title="暴雨预警",
                content="注意防范",
                category_code="disaster_warning",
            )
            self.assertEqual(
                get_policy_news_provider()
                .get_published_news(news["id"])["title"],
                "暴雨预警",
            )
            self.assertEqual(
                record_news_view(news["id"], "news-view-1"),
                1,
            )
            notifications_after_publish = get_db().execute(
                """
                SELECT recipient_id
                FROM system_notifications
                WHERE event_type = 'policy_published'
                """
            ).fetchall()
            self.assertEqual(notifications_after_publish, [])

            delete_news(
                news["id"],
                expected_version=news["version"],
            )
            with self.assertRaises(LocalResourceNotFoundError):
                get_news(news["id"])
            with self.assertRaises(LocalResourceNotFoundError):
                record_news_view(news["id"], "news-view-2")

    def test_local_resource_backend_has_no_ai_fallback_or_policy_table_access(
        self,
    ):
        root = Path(__file__).parents[1] / "app" / "local_resources"
        source = "\n".join(
            path.read_text(encoding="utf-8")
            for path in root.glob("*.py")
        )
        self.assertNotIn("local_kb", source)
        self.assertNotIn("agri_diagnosis", source)
        self.assertNotIn("FROM government_policies", source)
        self.assertNotIn("FROM government_news", source)


if __name__ == "__main__":
    unittest.main()
