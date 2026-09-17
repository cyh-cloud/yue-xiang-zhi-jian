import sqlite3
import tempfile
import unittest
from pathlib import Path

from app import create_app
from app.db import get_db
from app.handcraft_inheritance.providers import (
    EmptyCraftPresetProvider,
    EmptyRewardCatalogProvider,
    EmptyTeachingVideoProvider,
    UnavailablePointsPolicyProvider,
    get_craft_preset_provider,
    get_points_policy_provider,
    get_reward_catalog_provider,
    get_teaching_video_provider,
    set_craft_preset_provider,
    set_points_policy_provider,
    set_reward_catalog_provider,
    set_teaching_video_provider,
)


class ReplacementCraftPresetProvider:
    def list_crafts(self):
        return [{"key": "replacement-craft"}]

    def get_craft(self, craft_key):
        return {"key": craft_key}


class ReplacementTeachingVideoProvider:
    def list_videos(self, craft_key=None):
        return []

    def get_video(self, video_id):
        return None

    def get_review_status(self, video_id):
        return None


class ReplacementRewardCatalogProvider:
    def list_rewards(self):
        return []

    def reserve_stock(self, reward_id, quantity, reservation_id):
        return True

    def release_stock(self, reservation_id):
        return True


class ReplacementPointsPolicyProvider:
    def get_policy(self):
        return {"version": "replacement"}


class TestHandcraftFoundation(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(Path(self.temp_dir.name) / "test.db"),
                "SECRET_KEY": "test-only-secret",
            }
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_handcraft_tables_exist(self):
        expected = {
            "heritage_craft_progress",
            "heritage_videos",
            "points_accounts",
            "points_lots",
            "points_transactions",
            "points_allocations",
            "points_event_inbox",
            "points_learning_accruals",
            "points_policy_snapshots",
            "reward_stock_reservations",
            "redemptions",
            "fulfillments",
        }
        with self.app.app_context():
            names = {
                row["name"]
                for row in get_db().execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
        self.assertTrue(expected.issubset(names))

    def test_points_schema_enforces_balance_and_event_idempotency(self):
        with self.app.app_context():
            db = get_db()
            db.execute(
                """
                INSERT INTO users (
                    id, username, password_hash, name, role, is_enabled,
                    created_at, updated_at
                )
                VALUES (
                    1, 'student-1', 'hash', 'Student', 'student', 1,
                    '2026-09-17T00:00:00+08:00',
                    '2026-09-17T00:00:00+08:00'
                )
                """
            )
            db.execute(
                """
                INSERT INTO points_accounts (user_id, balance, updated_at)
                VALUES (1, 0, '2026-09-17T00:00:00+08:00')
                """
            )
            db.commit()
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute(
                    """
                    UPDATE points_accounts
                    SET balance = -1
                    WHERE user_id = 1
                    """
                )
            db.rollback()

            db.execute(
                """
                INSERT INTO points_event_inbox (
                    user_id, source_module, event_type, source_event_id,
                    occurred_at, duration_seconds, status, error, created_at
                )
                VALUES (
                    1, 'handcraft', 'craft_step', 'source-1',
                    '2026-09-17T00:00:00+08:00', 600, 'pending', NULL,
                    '2026-09-17T00:00:00+08:00'
                )
                """
            )
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute(
                    """
                    INSERT INTO points_event_inbox (
                        user_id, source_module, event_type, source_event_id,
                        occurred_at, duration_seconds, status, error, created_at
                    )
                    VALUES (
                        1, 'handcraft', 'craft_step', 'source-1',
                        '2026-09-17T00:00:00+08:00', 600, 'pending', NULL,
                        '2026-09-17T00:00:00+08:00'
                    )
                    """
                )

    def test_default_providers_are_installed_without_a_blueprint(self):
        with self.app.app_context():
            self.assertIsInstance(
                get_craft_preset_provider(), EmptyCraftPresetProvider
            )
            self.assertIsInstance(
                get_teaching_video_provider(), EmptyTeachingVideoProvider
            )
            self.assertIsInstance(
                get_reward_catalog_provider(), EmptyRewardCatalogProvider
            )
            self.assertIsInstance(
                get_points_policy_provider(), UnavailablePointsPolicyProvider
            )

        rules = {rule.rule for rule in self.app.url_map.iter_rules()}
        self.assertNotIn("/api/handcraft-inheritance", rules)

    def test_providers_are_replaceable(self):
        craft_provider = ReplacementCraftPresetProvider()
        video_provider = ReplacementTeachingVideoProvider()
        reward_provider = ReplacementRewardCatalogProvider()
        points_provider = ReplacementPointsPolicyProvider()

        set_craft_preset_provider(self.app, craft_provider)
        set_teaching_video_provider(self.app, video_provider)
        set_reward_catalog_provider(self.app, reward_provider)
        set_points_policy_provider(self.app, points_provider)

        with self.app.app_context():
            self.assertIs(get_craft_preset_provider(), craft_provider)
            self.assertIs(get_teaching_video_provider(), video_provider)
            self.assertIs(get_reward_catalog_provider(), reward_provider)
            self.assertIs(get_points_policy_provider(), points_provider)


if __name__ == "__main__":
    unittest.main()
