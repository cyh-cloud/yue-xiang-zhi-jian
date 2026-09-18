import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import create_app
from app.db import get_db
from app.handcraft_inheritance import (
    get_effective_policy,
    list_redemptions,
    list_rewards,
    record_training_points,
    redeem_reward,
    set_craft_preset_provider,
    set_points_policy_provider,
    set_reward_catalog_provider,
    set_teaching_video_provider,
)
from app.handcraft_inheritance.admin_actions import (
    apply_fulfillment_admin_action,
    apply_video_review,
)
from app.handcraft_inheritance.crafts import (
    complete_craft_step,
    get_craft,
    get_craft_progress,
)
from app.handcraft_inheritance.presets import (
    PLACEHOLDER_POINTS_POLICY,
    PLACEHOLDER_REWARDS,
    PlaceholderCraftPresetProvider,
    PlaceholderTeachingVideoProvider,
)
from app.handcraft_inheritance.providers import (
    set_fulfillment_action_provider,
    set_video_review_action_provider,
)
from app.handcraft_inheritance.videos import (
    get_video_playback,
    list_video_reviews,
)


class ReplacementCraftPresetProvider(PlaceholderCraftPresetProvider):
    def _replace(self, craft):
        replacement = copy.deepcopy(craft)
        replacement["name"] = "广绣（11 替换源）"
        replacement["introduction"] = "由 11 替换来源提供的广绣内容。"
        return replacement

    def list_crafts(self):
        return [self._replace(craft) for craft in super().list_crafts()]

    def get_craft(self, craft_key):
        craft = super().get_craft(craft_key)
        return self._replace(craft) if craft is not None else None


class ReplacementTeachingVideoProvider(PlaceholderTeachingVideoProvider):
    def get_video(self, video_id):
        video = super().get_video(video_id)
        if video is not None:
            video["replacement_revision"] = 2
        return video


class ReplacementRewardCatalogProvider:
    def __init__(self):
        self.released = []

    def list_rewards(self):
        return [
            {
                "reward_id": PLACEHOLDER_REWARDS[0]["reward_id"],
                "name": "广绣书签（11 替换源）",
                "points_cost": 30,
                "stock": 4,
                "is_online": True,
                "is_demo": False,
                "source_available": True,
            }
        ]

    def reserve_stock(self, reward_id, quantity, reservation_id):
        return reservation_id

    def release_stock(self, reservation_id):
        self.released.append(reservation_id)
        return True


class ReplacementPointsPolicyProvider:
    def get_policy(self):
        policy = copy.deepcopy(PLACEHOLDER_POINTS_POLICY)
        policy.update(
            {
                "version": "replacement-v2",
                "seconds_per_point": 300,
                "daily_limit": 120,
                "source_available": True,
            }
        )
        return policy


class StaticPolicyProvider:
    def __init__(self, policy):
        self.policy = copy.deepcopy(policy)

    def get_policy(self):
        return copy.deepcopy(self.policy)


class RecordingVideoReviewProvider:
    def __init__(self):
        self.actions = []

    def apply(self, action):
        self.actions.append(copy.deepcopy(action))
        return {"status": "replacement-approved", "notification": None}


class RecordingFulfillmentActionProvider:
    def __init__(self):
        self.actions = []

    def apply(self, action):
        self.actions.append(copy.deepcopy(action))
        return {"status": "replacement-issued", "notification": None}


class TestHandcraftPlaceholderAcceptance(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(Path(self.temp_dir.name) / "test.db"),
                "SECRET_KEY": "task-20-placeholder-secret",
            }
        )
        with self.app.app_context():
            get_db().execute(
                """
                INSERT INTO users (
                    id, username, password_hash, name, role, is_enabled,
                    created_at, updated_at
                )
                VALUES (
                    1, 'student01', 'hash', '学员', 'student', 1,
                    '2026-09-18T00:00:00+08:00',
                    '2026-09-18T00:00:00+08:00'
                )
                """
            )
            get_db().commit()
        policy = copy.deepcopy(PLACEHOLDER_POINTS_POLICY)
        policy.update(
            {
                "seconds_per_point": 600,
                "training_weights": {"default": 1000},
                "daily_limit": 10000,
            }
        )
        set_points_policy_provider(
            self.app,
            StaticPolicyProvider(policy),
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def _fund(self):
        with self.app.app_context():
            result = record_training_points(
                1,
                "ecommerce",
                "placeholder_funding",
                "placeholder-funding",
                "2026-09-18T09:00:00+08:00",
            )
            self.assertEqual(result["status"], "processed")

    def test_provider_replacements_keep_stable_records_and_history(self):
        with self.app.app_context():
            complete_craft_step(
                1,
                "guangxiu",
                1,
                600,
                "placeholder-step-1",
            )
            self._fund()
            with patch(
                "app.handcraft_inheritance.rewards."
                "emit_redemption_succeeded"
            ):
                redemption = redeem_reward(
                    1,
                    PLACEHOLDER_REWARDS[0]["reward_id"],
                    "placeholder-redemption",
                )
            original_progress = get_craft_progress(1, "guangxiu")
            original_redemption = list_redemptions(1)[0]

        craft_provider = ReplacementCraftPresetProvider()
        video_provider = ReplacementTeachingVideoProvider()
        reward_provider = ReplacementRewardCatalogProvider()
        policy_provider = ReplacementPointsPolicyProvider()
        set_craft_preset_provider(self.app, craft_provider)
        set_teaching_video_provider(self.app, video_provider)
        set_reward_catalog_provider(self.app, reward_provider)
        set_points_policy_provider(self.app, policy_provider)

        with self.app.app_context():
            detail = get_craft("guangxiu")
            progress_after_replacement = get_craft_progress(1, "guangxiu")
            next_step = complete_craft_step(
                1,
                "guangxiu",
                2,
                300,
                "placeholder-step-2",
            )
            playback = get_video_playback("demo-guangxiu-approved")
            reviews = list_video_reviews()
            rewards = list_rewards(1)
            history = list_redemptions(1)
            policy = get_effective_policy()

        self.assertEqual(detail["name"], "广绣（11 替换源）")
        self.assertEqual(
            progress_after_replacement["completed_steps"],
            original_progress["completed_steps"],
        )
        self.assertTrue(next_step["accepted"])
        self.assertEqual(next_step["completed_steps"], [1, 2])
        self.assertTrue(playback["available"])
        self.assertEqual(playback["video_id"], "demo-guangxiu-approved")
        review = next(
            item
            for item in reviews
            if item["video_id"] == "demo-guangxiu-approved"
        )
        self.assertTrue(review["provider_available"])
        self.assertTrue(review["contract_valid"])
        self.assertEqual(rewards[0]["name"], "广绣书签（11 替换源）")
        self.assertEqual(
            history[0]["id"],
            original_redemption["id"],
        )
        self.assertEqual(
            history[0]["reward"]["reward_id"],
            redemption["reward_id"],
        )
        self.assertEqual(
            history[0]["reward_name"],
            original_redemption["reward_name"],
        )
        self.assertEqual(policy["version"], "replacement-v2")
        self.assertEqual(policy["seconds_per_point"], 300)

    def test_review_and_fulfillment_action_adapters_are_replaceable(self):
        video_provider = RecordingVideoReviewProvider()
        fulfillment_provider = RecordingFulfillmentActionProvider()
        set_video_review_action_provider(self.app, video_provider)
        set_fulfillment_action_provider(
            self.app,
            fulfillment_provider,
        )

        video_action = {
            "video_id": "stable-video-id",
            "action": "approve",
            "reviewer_role": "admin",
            "version": 3,
        }
        fulfillment_action = {
            "fulfillment_id": 42,
            "action": "issue",
            "admin_role": "super_admin",
        }
        with self.app.app_context():
            video_result = apply_video_review(video_action)
            fulfillment_result = apply_fulfillment_admin_action(
                fulfillment_action
            )

        self.assertEqual(
            video_result,
            {"status": "replacement-approved"},
        )
        self.assertEqual(
            fulfillment_result,
            {"status": "replacement-issued"},
        )
        self.assertEqual(video_provider.actions, [video_action])
        self.assertEqual(
            fulfillment_provider.actions,
            [fulfillment_action],
        )


if __name__ == "__main__":
    unittest.main()
