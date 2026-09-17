import threading
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from app import create_app
from app.db import get_db
from app.handcraft_inheritance import (
    get_craft_preset_provider,
    get_points_policy_provider,
    get_reward_catalog_provider,
    get_teaching_video_provider,
    set_craft_preset_provider,
    set_points_policy_provider,
    set_reward_catalog_provider,
    set_teaching_video_provider,
)
from app.handcraft_inheritance.presets import (
    PlaceholderCraftPresetProvider,
    PlaceholderPointsPolicyProvider,
    PlaceholderRewardCatalogProvider,
    PlaceholderTeachingVideoProvider,
)
from app.handcraft_inheritance.seed import seed_handcraft_fixtures


class ReplacementCraftPresetProvider:
    def list_crafts(self):
        return [{"craft_key": "replacement", "name": "替换技艺"}]

    def get_craft(self, craft_key):
        return {"craft_key": craft_key, "name": "替换技艺"}


class ReplacementTeachingVideoProvider:
    def list_videos(self, craft_key=None):
        return [
            {
                "video_id": "replacement-video",
                "review_status": "approved",
            }
        ]

    def get_video(self, video_id):
        return {"video_id": video_id, "review_status": "approved"}

    def get_review_status(self, video_id):
        return "approved"


class ReplacementRewardCatalogProvider:
    def list_rewards(self):
        return [{"reward_id": "replacement-reward", "name": "替换奖品"}]

    def reserve_stock(self, reward_id, quantity, reservation_id):
        return True

    def release_stock(self, reservation_id):
        return True


class ReplacementPointsPolicyProvider:
    def get_policy(self):
        return {"version": "replacement"}


class TestHandcraftPresets(unittest.TestCase):
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

    def test_four_crafts_have_exact_six_steps_and_material_guides(self):
        with self.app.app_context():
            provider = get_craft_preset_provider()
            crafts = provider.list_crafts()

        self.assertIsInstance(provider, PlaceholderCraftPresetProvider)
        self.assertEqual(
            [craft["name"] for craft in crafts],
            ["广绣", "潮汕木雕", "石湾陶艺", "阳江漆器"],
        )
        self.assertEqual(len({craft["craft_key"] for craft in crafts}), 4)

        material_fields = {
            "name",
            "reference_price",
            "purchase_channel",
            "precautions",
            "taobao_keyword",
        }
        introduction_keywords = {
            "guangxiu": ("广州", "明清", "针法细密"),
            "chaoshan-woodcarving": ("潮汕", "唐宋", "多层镂通"),
            "shiwan-ceramics": ("佛山石湾", "明清", "胎釉浑厚"),
            "yangjiang-lacquerware": ("阳江", "晚清民国", "逐层打磨"),
        }
        for craft in crafts:
            with self.subTest(craft=craft["craft_key"]):
                self.assertTrue(craft["is_demo"])
                self.assertTrue(craft["introduction"].strip())
                for keyword in introduction_keywords[craft["craft_key"]]:
                    self.assertIn(keyword, craft["introduction"])
                self.assertEqual(len(craft["steps"]), 6)
                self.assertEqual(
                    [step["step_no"] for step in craft["steps"]],
                    [1, 2, 3, 4, 5, 6],
                )
                self.assertEqual(
                    len({step["step_key"] for step in craft["steps"]}),
                    6,
                )
                self.assertTrue(craft["material_guide"])
                for material in craft["material_guide"]:
                    self.assertEqual(set(material), material_fields)
                    self.assertTrue(
                        all(
                            isinstance(value, str) and value.strip()
                            for value in material.values()
                        )
                    )

    def test_video_provider_exposes_only_approved_safe_demo_records(self):
        with self.app.app_context():
            provider = get_teaching_video_provider()
            videos = provider.list_videos()

        self.assertIsInstance(provider, PlaceholderTeachingVideoProvider)
        self.assertEqual(len(videos), 4)
        self.assertEqual(len({video["craft_key"] for video in videos}), 4)
        for video in videos:
            with self.subTest(video=video["video_id"]):
                self.assertTrue(video["video_id"].startswith("demo-"))
                self.assertTrue(video["is_demo"])
                self.assertEqual(video["review_status"], "approved")
                self.assertTrue(video["source_available"])
                self.assertTrue(
                    video["media_url"].startswith("https://example.test/")
                )
                self.assertIs(
                    provider.get_video(video["video_id"])["review_status"],
                    "approved",
                )
                self.assertEqual(
                    provider.get_review_status(video["video_id"]),
                    "approved",
                )

    def test_reward_provider_reserves_and_releases_stock_idempotently(self):
        with self.app.app_context():
            provider = get_reward_catalog_provider()
            rewards = provider.list_rewards()
            reward = rewards[0]
            initial_stock = reward["stock"]

            self.assertTrue(
                provider.reserve_stock(
                    reward["reward_id"],
                    2,
                    "reservation-1",
                )
            )
            self.assertEqual(
                provider.list_rewards()[0]["stock"],
                initial_stock - 2,
            )
            self.assertTrue(
                provider.reserve_stock(
                    reward["reward_id"],
                    2,
                    "reservation-1",
                )
            )
            self.assertEqual(
                provider.list_rewards()[0]["stock"],
                initial_stock - 2,
            )
            self.assertTrue(provider.release_stock("reservation-1"))
            self.assertTrue(provider.release_stock("reservation-1"))
            self.assertEqual(
                provider.list_rewards()[0]["stock"],
                initial_stock,
            )

        self.assertIsInstance(provider, PlaceholderRewardCatalogProvider)
        self.assertTrue(rewards)
        self.assertTrue(
            all(
                {
                    "reward_id",
                    "name",
                    "points_cost",
                    "stock",
                    "is_online",
                    "is_demo",
                    "source_available",
                }.issubset(reward)
                for reward in rewards
            )
        )

    def test_points_policy_matches_demo_values(self):
        with self.app.app_context():
            provider = get_points_policy_provider()
            policy = provider.get_policy()

        self.assertIsInstance(provider, PlaceholderPointsPolicyProvider)
        self.assertEqual(policy["seconds_per_point"], 600)
        self.assertEqual(policy["training_weights"]["default"], 10)
        self.assertEqual(policy["daily_limit"], 60)
        self.assertEqual(policy["expiry_mode"], "permanent")
        self.assertTrue(policy["is_demo"])
        self.assertTrue(policy["source_available"])

    def test_seed_is_idempotent_and_writes_only_demo_video_records(self):
        with self.app.app_context():
            db = get_db()
            seed_handcraft_fixtures(db)
            first_count = db.execute(
                "SELECT COUNT(*) AS count FROM heritage_videos"
            ).fetchone()["count"]
            seed_handcraft_fixtures(db)
            second_count = db.execute(
                "SELECT COUNT(*) AS count FROM heritage_videos"
            ).fetchone()["count"]
            rows = db.execute(
                """
                SELECT video_id, review_status, source_available
                FROM heritage_videos
                ORDER BY video_id
                """
            ).fetchall()
            points_count = db.execute(
                "SELECT COUNT(*) AS count FROM points_accounts"
            ).fetchone()["count"]
            redemption_count = db.execute(
                "SELECT COUNT(*) AS count FROM redemptions"
            ).fetchone()["count"]
            fulfillment_count = db.execute(
                "SELECT COUNT(*) AS count FROM fulfillments"
            ).fetchone()["count"]

        self.assertEqual(first_count, 4)
        self.assertEqual(second_count, first_count)
        self.assertTrue(
            all(
                row["video_id"].startswith("demo-")
                and row["review_status"] == "approved"
                and row["source_available"] == 1
                for row in rows
            )
        )
        self.assertEqual(points_count, 0)
        self.assertEqual(redemption_count, 0)
        self.assertEqual(fulfillment_count, 0)

    def test_seed_does_not_overwrite_hidden_video_state(self):
        with self.app.app_context():
            db = get_db()
            db.execute(
                """
                UPDATE heritage_videos
                SET title = '人工隐藏的演示视频',
                    review_status = 'offline',
                    source_available = 0
                WHERE video_id = 'demo-guangxiu-approved'
                """
            )
            db.commit()

            seed_handcraft_fixtures(db)
            row = db.execute(
                """
                SELECT title, review_status, source_available
                FROM heritage_videos
                WHERE video_id = 'demo-guangxiu-approved'
                """
            ).fetchone()

        self.assertEqual(row["title"], "人工隐藏的演示视频")
        self.assertEqual(row["review_status"], "offline")
        self.assertEqual(row["source_available"], 0)

    def test_reward_provider_concurrent_reserve_does_not_oversell(self):
        provider = PlaceholderRewardCatalogProvider()
        reward = provider.list_rewards()[0]
        reward_id = reward["reward_id"]
        self.assertTrue(
            provider.reserve_stock(
                reward_id,
                reward["stock"] - 1,
                "preload",
            )
        )
        barrier = threading.Barrier(2)

        def reserve(reservation_id: str) -> bool:
            barrier.wait(timeout=5)
            return provider.reserve_stock(
                reward_id,
                1,
                reservation_id,
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(
                executor.map(
                    reserve,
                    ("concurrent-1", "concurrent-2"),
                )
            )

        self.assertEqual(sum(results), 1)
        self.assertEqual(provider.list_rewards()[0]["stock"], 0)

    def test_providers_are_replaceable_through_existing_extensions(self):
        replacements = (
            (
                set_craft_preset_provider,
                get_craft_preset_provider,
                ReplacementCraftPresetProvider(),
            ),
            (
                set_teaching_video_provider,
                get_teaching_video_provider,
                ReplacementTeachingVideoProvider(),
            ),
            (
                set_reward_catalog_provider,
                get_reward_catalog_provider,
                ReplacementRewardCatalogProvider(),
            ),
            (
                set_points_policy_provider,
                get_points_policy_provider,
                ReplacementPointsPolicyProvider(),
            ),
        )

        for setter, getter, replacement in replacements:
            setter(self.app, replacement)
            with self.app.app_context():
                self.assertIs(getter(), replacement)

        with self.app.app_context():
            self.assertEqual(
                get_craft_preset_provider().list_crafts()[0]["name"],
                "替换技艺",
            )
            self.assertEqual(
                get_craft_preset_provider().get_craft("replacement")["name"],
                "替换技艺",
            )
            self.assertEqual(
                get_teaching_video_provider().list_videos()[0]["video_id"],
                "replacement-video",
            )
            self.assertEqual(
                get_teaching_video_provider().get_review_status(
                    "replacement-video"
                ),
                "approved",
            )
            self.assertEqual(
                get_reward_catalog_provider().list_rewards()[0]["reward_id"],
                "replacement-reward",
            )
            self.assertEqual(
                get_points_policy_provider().get_policy()["version"],
                "replacement",
            )

        provider_keys = {
            key
            for key in self.app.extensions
            if key.startswith("handcraft_")
            and key.endswith("_provider")
        }
        self.assertEqual(
            provider_keys,
            {
                "handcraft_craft_preset_provider",
                "handcraft_teaching_video_provider",
                "handcraft_reward_catalog_provider",
                "handcraft_points_policy_provider",
            },
        )


if __name__ == "__main__":
    unittest.main()
