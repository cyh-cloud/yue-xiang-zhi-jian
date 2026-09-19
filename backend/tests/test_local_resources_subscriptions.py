import tempfile
import unittest
from pathlib import Path

from app import create_app
from app.db import get_db
from app.local_resources.messaging_provider import (
    LocalResourcesMessagingProvider,
)
from app.local_resources.subscriptions import (
    list_policy_subscriptions,
    recommend_policy_categories,
    set_policy_subscription,
)


class LocalResourceSubscriptionTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(Path(self.temp_dir.name) / "test.db"),
            }
        )
        with self.app.app_context():
            self.student_id = self._insert_user("student01", "student", 1)
            self.disabled_id = self._insert_user("student02", "student", 0)
            self.tag_id = int(
                get_db().execute(
                    "SELECT id FROM interest_tags WHERE name = '荔枝'"
                ).fetchone()["id"]
            )
            get_db().execute(
                """
                INSERT INTO student_profiles (
                    user_id, contact, learning_direction, updated_at
                ) VALUES (?, '', 'comprehensive', ?)
                """,
                (
                    self.student_id,
                    "2026-09-19T00:00:00+08:00",
                ),
            )
            get_db().execute(
                "INSERT INTO student_interest_tags (user_id, tag_id) VALUES (?, ?)",
                (self.student_id, self.tag_id),
            )
            get_db().commit()

    def tearDown(self):
        self.temp_dir.cleanup()

    def _insert_user(self, username, role, enabled):
        cursor = get_db().execute(
            """
            INSERT INTO users (
                username, password_hash, name, role, is_enabled,
                created_at, updated_at
            ) VALUES (?, 'hash', ?, ?, ?, ?, ?)
            """,
            (
                username,
                username,
                role,
                enabled,
                "2026-09-19T00:00:00+08:00",
                "2026-09-19T00:00:00+08:00",
            ),
        )
        return int(cursor.lastrowid)

    def test_subscribe_and_unsubscribe_are_idempotent_soft_state(self):
        with self.app.app_context():
            first = set_policy_subscription(
                self.student_id,
                "ecommerce",
                True,
            )
            second = set_policy_subscription(
                self.student_id,
                "ecommerce",
                True,
            )
            self.assertEqual(first["subscribed"], True)
            self.assertEqual(second["subscribed"], True)
            state = list_policy_subscriptions(self.student_id)
            self.assertEqual(
                next(
                    item for item in state["categories"]
                    if item["code"] == "ecommerce"
                )["subscribed"],
                True,
            )
            set_policy_subscription(
                self.student_id,
                "ecommerce",
                False,
            )
            row = get_db().execute(
                """
                SELECT is_active
                FROM local_resource_policy_subscriptions
                WHERE user_id = ? AND category_code = 'ecommerce'
                """,
                (self.student_id,),
            ).fetchone()
            self.assertEqual(row["is_active"], 0)

    def test_messaging_bridge_filters_label_role_and_enabled(self):
        with self.app.app_context():
            set_policy_subscription(
                self.student_id,
                "ecommerce",
                True,
            )
            set_policy_subscription(
                self.disabled_id,
                "ecommerce",
                True,
            )
            provider = LocalResourcesMessagingProvider()
            self.assertEqual(
                provider.list_policy_subscriber_ids("电商"),
                [self.student_id],
            )
            self.assertEqual(
                provider.list_policy_subscriber_ids("未知"),
                [],
            )

    def test_recommendations_come_from_existing_tags_and_do_not_subscribe(self):
        with self.app.app_context():
            recommended = recommend_policy_categories(self.student_id)
            self.assertEqual(
                recommended,
                ["subsidy", "training", "general"],
            )
            count = get_db().execute(
                """
                SELECT COUNT(*) AS count
                FROM local_resource_policy_subscriptions
                WHERE user_id = ?
                """,
                (self.student_id,),
            ).fetchone()["count"]
            self.assertEqual(count, 0)


if __name__ == "__main__":
    unittest.main()
