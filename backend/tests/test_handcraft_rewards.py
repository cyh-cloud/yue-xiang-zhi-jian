import copy
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from app import create_app
from app.agri_skills.errors import AgriValidationError
from app.db import get_db
from app.handcraft_inheritance import (
    get_reward_catalog_provider,
    list_redemptions,
    list_rewards,
    record_training_points,
    redeem_reward,
    set_points_policy_provider,
    set_reward_catalog_provider,
)
from app.handcraft_inheritance.presets import (
    PLACEHOLDER_POINTS_POLICY,
    PLACEHOLDER_REWARDS,
)


class StaticPolicyProvider:
    def __init__(self, policy):
        self.policy = copy.deepcopy(policy)

    def get_policy(self):
        return copy.deepcopy(self.policy)


class StaticRewardProvider:
    def __init__(self, rewards):
        self.rewards = copy.deepcopy(rewards)
        self.releases = []

    def list_rewards(self):
        return copy.deepcopy(self.rewards)

    def reserve_stock(self, reward_id, quantity, reservation_id):
        reward = next(
            (
                item
                for item in self.rewards
                if item["reward_id"] == reward_id
            ),
            None,
        )
        if reward is None or reward["stock"] < quantity:
            return None
        reward["stock"] -= quantity
        return f"external-{reservation_id}"

    def release_stock(self, reservation_id):
        self.releases.append(reservation_id)
        return True


class TestHandcraftRewards(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(Path(self.temp_dir.name) / "test.db"),
                "SECRET_KEY": "test-only-secret",
            }
        )
        with self.app.app_context():
            db = get_db()
            for user_id, username in ((1, "student01"), (2, "student02")):
                db.execute(
                    """
                    INSERT INTO users (
                        id, username, password_hash, name, role, is_enabled,
                        created_at, updated_at
                    )
                    VALUES (?, ?, 'hash', ?, 'student', 1, ?, ?)
                    """,
                    (
                        user_id,
                        username,
                        username,
                        "2026-09-17T00:00:00+08:00",
                        "2026-09-17T00:00:00+08:00",
                    ),
                )
            db.commit()

    def tearDown(self):
        self.temp_dir.cleanup()

    def use_points_policy(self, **overrides):
        policy = copy.deepcopy(PLACEHOLDER_POINTS_POLICY)
        policy.update(
            {
                "seconds_per_point": 1,
                "daily_limit": 1000,
                "training_weights": {"default": 1000},
                **overrides,
            }
        )
        set_points_policy_provider(self.app, StaticPolicyProvider(policy))

    def fund_user(self, user_id: int, amount: int) -> None:
        with self.app.app_context():
            result = record_training_points(
                user_id,
                "ecommerce",
                "live_script",
                f"funding-{user_id}-{amount}",
                "2026-09-17T09:00:00+08:00",
            )
            self.assertEqual(result["status"], "processed")

    def test_list_rewards_and_three_validation_failures(self):
        self.use_points_policy()
        with self.app.app_context():
            rewards = list_rewards(1)
            self.assertTrue(rewards)
            self.assertIn("can_redeem", rewards[0])

            with self.assertRaisesRegex(
                AgriValidationError,
                "积分不足，还差 30 分",
            ):
                redeem_reward(1, rewards[0]["reward_id"], "insufficient")
            self.assertEqual(list_redemptions(1), [])

        offline_reward = {
            "reward_id": "offline-reward",
            "name": "下架奖品",
            "points_cost": 10,
            "stock": 10,
            "is_online": False,
            "source_available": True,
        }
        set_reward_catalog_provider(
            self.app,
            StaticRewardProvider([offline_reward]),
        )
        self.fund_user(1, 50)
        with self.app.app_context():
            with self.assertRaisesRegex(
                AgriValidationError,
                "奖品已下架",
            ):
                redeem_reward(1, "offline-reward", "offline")

        no_stock = {
            **offline_reward,
            "reward_id": "empty-reward",
            "name": "库存为0奖品",
            "stock": 0,
            "is_online": True,
        }
        set_reward_catalog_provider(
            self.app,
            StaticRewardProvider([no_stock]),
        )
        with self.app.app_context():
            with self.assertRaisesRegex(AgriValidationError, "已抢完"):
                redeem_reward(1, "empty-reward", "empty")
            redemption_count = get_db().execute(
                "SELECT COUNT(*) AS count FROM redemptions"
            ).fetchone()["count"]

        self.assertEqual(redemption_count, 0)

    def test_redeem_is_atomic_and_notification_is_idempotent(self):
        self.use_points_policy()
        self.fund_user(1, 50)
        with self.app.app_context():
            reward = list_rewards(1)[0]
            with patch(
                "app.handcraft_inheritance.outbox."
                "emit_redemption_succeeded"
            ) as emit:
                first = redeem_reward(
                    1,
                    reward["reward_id"],
                    "request-1",
                )
                second = redeem_reward(
                    1,
                    reward["reward_id"],
                    "request-1",
                )
            redemption_rows = get_db().execute(
                "SELECT * FROM redemptions"
            ).fetchall()
            reservations = get_db().execute(
                "SELECT * FROM reward_stock_reservations"
            ).fetchall()
            spend_rows = get_db().execute(
                """
                SELECT *
                FROM points_transactions
                WHERE transaction_type = 'spend'
                """
            ).fetchall()
            balance = get_db().execute(
                """
                SELECT balance
                FROM points_accounts
                WHERE user_id = 1
                """
            ).fetchone()["balance"]
            redemptions = list_redemptions(1)
            fulfillment = get_db().execute(
                """
                SELECT *
                FROM fulfillments
                WHERE redemption_id = ?
                """,
                (first["id"],),
            ).fetchone()
            self.assertTrue(
                get_reward_catalog_provider().release_stock(str(first["id"]))
            )
            released = get_db().execute(
                """
                SELECT status
                FROM reward_stock_reservations
                WHERE redemption_id = ?
                """,
                (first["id"],),
            ).fetchone()

        self.assertEqual(first["id"], second["id"])
        self.assertEqual(first["status"], "pending")
        self.assertEqual(len(redemption_rows), 1)
        self.assertEqual(len(reservations), 1)
        self.assertEqual(reservations[0]["status"], "reserved")
        self.assertEqual(fulfillment["status"], "pending")
        self.assertEqual(released["status"], "released")
        self.assertEqual(len(spend_rows), 1)
        self.assertEqual(balance, 970)
        self.assertEqual(redemptions[0]["id"], first["id"])
        self.assertEqual(emit.call_count, 1)
        self.assertEqual(
            {
                call.kwargs["event_id"]
                for call in emit.call_args_list
            },
            {f"handcraft-redemption:{first['id']}:succeeded"},
        )

    def test_existing_request_returns_before_reward_or_balance_validation(self):
        self.use_points_policy()
        self.fund_user(1, 50)
        with self.app.app_context():
            reward = list_rewards(1)[0]
            first = redeem_reward(1, reward["reward_id"], "existing-request")
            set_reward_catalog_provider(
                self.app,
                StaticRewardProvider(
                    [
                        {
                            **reward,
                            "is_online": False,
                            "stock": 0,
                        }
                    ]
                ),
            )
            set_points_policy_provider(
                self.app,
                StaticPolicyProvider({"invalid": True}),
            )
            with patch(
                "app.handcraft_inheritance.outbox."
                "emit_redemption_succeeded"
            ) as emit:
                repeated = redeem_reward(
                    1,
                    reward["reward_id"],
                    "existing-request",
                )

        self.assertEqual(repeated["id"], first["id"])
        emit.assert_not_called()

    def test_notification_failure_does_not_rollback_and_can_retry(self):
        self.use_points_policy()
        self.fund_user(1, 50)
        with self.app.app_context():
            reward = list_rewards(1)[0]
            with patch(
                "app.handcraft_inheritance.outbox."
                "emit_redemption_succeeded",
                side_effect=RuntimeError("notification offline"),
            ):
                redemption = redeem_reward(
                    1,
                    reward["reward_id"],
                    "retry-request",
                )

            redemption_count = get_db().execute(
                "SELECT COUNT(*) AS count FROM redemptions"
            ).fetchone()["count"]
            spend_count = get_db().execute(
                """
                SELECT COUNT(*) AS count
                FROM points_transactions
                WHERE transaction_type = 'spend'
                """
            ).fetchone()["count"]
            from app.handcraft_inheritance.outbox import (
                retry_pending_handcraft_notifications,
            )

            with patch(
                "app.handcraft_inheritance.outbox."
                "emit_redemption_succeeded"
            ) as emit:
                retry = retry_pending_handcraft_notifications()
            retry_spend_count = get_db().execute(
                """
                SELECT COUNT(*) AS count
                FROM points_transactions
                WHERE transaction_type = 'spend'
                """
            ).fetchone()["count"]

        self.assertEqual(redemption_count, 1)
        self.assertEqual(spend_count, 1)
        self.assertEqual(retry_spend_count, 1)
        self.assertEqual(redemption["status"], "pending")
        self.assertEqual(retry["sent"], 1)
        emit.assert_called_once()

    def test_concurrent_redeem_of_last_stock_conflict_is_atomic(self):
        self.use_points_policy()
        self.fund_user(1, 100)
        self.fund_user(2, 100)
        one_stock_rewards = (
            {
                **copy.deepcopy(PLACEHOLDER_REWARDS[0]),
                "stock": 1,
            },
            *copy.deepcopy(PLACEHOLDER_REWARDS[1:]),
        )
        barrier = threading.Barrier(2)

        def redeem(user_id: int, request_id: str):
            with self.app.app_context():
                barrier.wait(timeout=5)
                try:
                    result = redeem_reward(
                        user_id,
                        PLACEHOLDER_REWARDS[0]["reward_id"],
                        request_id,
                    )
                    return "ok", result
                except AgriValidationError as error:
                    return "error", str(error)

        with patch(
            "app.handcraft_inheritance.presets.PLACEHOLDER_REWARDS",
            one_stock_rewards,
        ), patch(
            "app.handcraft_inheritance.outbox."
            "emit_redemption_succeeded"
        ):
            with ThreadPoolExecutor(max_workers=2) as executor:
                results = list(
                    executor.map(
                        lambda item: redeem(*item),
                        ((1, "concurrent-1"), (2, "concurrent-2")),
                    )
                )

        with self.app.app_context():
            redemption_count = get_db().execute(
                "SELECT COUNT(*) AS count FROM redemptions"
            ).fetchone()["count"]
            reservation_count = get_db().execute(
                "SELECT COUNT(*) AS count FROM reward_stock_reservations"
            ).fetchone()["count"]
            spend_count = get_db().execute(
                """
                SELECT COUNT(*) AS count
                FROM points_transactions
                WHERE transaction_type = 'spend'
                """
            ).fetchone()["count"]
            fulfillment_count = get_db().execute(
                "SELECT COUNT(*) AS count FROM fulfillments"
            ).fetchone()["count"]

        self.assertEqual(sum(result[0] == "ok" for result in results), 1)
        self.assertEqual(sum(result[0] == "error" for result in results), 1)
        failure = next(result for result in results if result[0] == "error")
        self.assertEqual(
            failure[1],
            "库存或积分已变化，请刷新后重试",
        )
        self.assertEqual(redemption_count, 1)
        self.assertEqual(reservation_count, 1)
        self.assertEqual(spend_count, 1)
        self.assertEqual(fulfillment_count, 1)

    def test_external_reservation_is_compensated_when_spend_fails(self):
        self.use_points_policy()
        self.fund_user(1, 50)
        reward = copy.deepcopy(PLACEHOLDER_REWARDS[0])
        provider = StaticRewardProvider([reward])
        set_reward_catalog_provider(self.app, provider)

        with self.app.app_context(), patch(
            "app.handcraft_inheritance.rewards."
            "spend_points_in_transaction",
            side_effect=AgriValidationError("积分不足"),
        ):
            with self.assertRaisesRegex(
                AgriValidationError,
                "库存或积分已变化，请刷新后重试",
            ):
                redeem_reward(1, reward["reward_id"], "compensate")

            redemption_count = get_db().execute(
                "SELECT COUNT(*) AS count FROM redemptions"
            ).fetchone()["count"]
            fulfillment_count = get_db().execute(
                "SELECT COUNT(*) AS count FROM fulfillments"
            ).fetchone()["count"]

        self.assertEqual(len(provider.releases), 1)
        self.assertTrue(provider.releases[0].startswith("external-"))
        self.assertEqual(redemption_count, 0)
        self.assertEqual(fulfillment_count, 0)

    def test_invalid_reward_config_uses_stable_error(self):
        self.use_points_policy()
        self.fund_user(1, 50)
        invalid_values = (
            {"points_cost": 0, "stock": -1},
            {"points_cost": 10, "stock": None},
            {"points_cost": 10, "stock": "abc"},
            {"points_cost": "abc", "stock": 10},
        )

        for index, invalid in enumerate(invalid_values):
            with self.subTest(invalid=invalid):
                invalid_reward = {
                    "reward_id": f"invalid-reward-{index}",
                    "name": "非法奖品",
                    "is_online": True,
                    "source_available": True,
                    **invalid,
                }
                set_reward_catalog_provider(
                    self.app,
                    StaticRewardProvider([invalid_reward]),
                )

                with self.app.app_context():
                    listed = list_rewards(1)
                    with self.assertRaisesRegex(
                        AgriValidationError,
                        "奖品配置不可用",
                    ):
                        redeem_reward(
                            1,
                            invalid_reward["reward_id"],
                            f"invalid-config-{index}",
                        )

                self.assertEqual(
                    listed[0]["unavailable_reason"],
                    "奖品配置不可用",
                )


if __name__ == "__main__":
    unittest.main()
