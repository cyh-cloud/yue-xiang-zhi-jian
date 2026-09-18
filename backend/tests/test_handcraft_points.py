import copy
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from app import create_app
from app.agri_skills.errors import AgriValidationError
from app.db import get_db
from app.handcraft_inheritance import (
    PointsPolicyUnavailable,
    enqueue_learning_event,
    get_effective_policy,
    get_points_daily_status,
    get_points_account,
    get_points_ledger,
    process_pending_events,
    record_duration_points,
    record_training_points,
    refund_points,
    set_points_policy_provider,
    settle_user_expiry,
    spend_points,
)
from app.handcraft_inheritance.presets import (
    PLACEHOLDER_POINTS_POLICY,
    PlaceholderPointsPolicyProvider,
)


class StaticPolicyProvider:
    def __init__(self, policy):
        self.policy = copy.deepcopy(policy)

    def get_policy(self):
        return copy.deepcopy(self.policy)


class FailingPolicyProvider:
    def get_policy(self):
        raise RuntimeError("policy source unavailable")


class TestHandcraftPoints(unittest.TestCase):
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
            get_db().execute(
                """
                INSERT INTO users (
                    id, username, password_hash, name, role, is_enabled,
                    created_at, updated_at
                )
                VALUES (
                    1, 'student01', 'hash', '学员', 'student', 1,
                    '2026-09-17T00:00:00+08:00',
                    '2026-09-17T00:00:00+08:00'
                )
                """
            )
            get_db().commit()

    def tearDown(self):
        self.temp_dir.cleanup()

    def use_policy(self, **overrides):
        policy = copy.deepcopy(PLACEHOLDER_POINTS_POLICY)
        policy.update(overrides)
        set_points_policy_provider(self.app, StaticPolicyProvider(policy))
        return policy

    def test_policy_snapshot_fallback_and_no_rule_pause(self):
        with self.app.app_context():
            policy = get_effective_policy()
            snapshot_count = get_db().execute(
                "SELECT COUNT(*) AS count FROM points_policy_snapshots"
            ).fetchone()["count"]

            self.assertEqual(policy["version"], "demo-v1")
            self.assertTrue(policy["source_available"])
            self.assertEqual(snapshot_count, 1)

            set_points_policy_provider(self.app, FailingPolicyProvider())
            fallback = get_effective_policy()
            fallback_count = get_db().execute(
                "SELECT COUNT(*) AS count FROM points_policy_snapshots"
            ).fetchone()["count"]

            self.assertEqual(fallback["version"], "demo-v1")
            self.assertFalse(fallback["source_available"])
            self.assertEqual(fallback_count, snapshot_count)

            get_db().execute("DELETE FROM points_policy_snapshots")
            get_db().commit()
            with self.assertRaisesRegex(
                PointsPolicyUnavailable,
                "积分规则暂不可用，请稍后重试",
            ):
                get_effective_policy()

    def test_duration_fragments_accumulate_and_events_are_idempotent(self):
        with self.app.app_context():
            first = record_duration_points(
                1,
                "handcraft",
                "guangxiu:step-1",
                300,
                "2026-09-17T10:00:00+08:00",
                "heartbeat-1",
            )
            self.assertEqual(first["status"], "processed")
            self.assertEqual(first["awarded"], 0)
            self.assertIsNone(first["transaction"])
            self.assertEqual(get_points_account(1)["balance"], 0)

            second = record_duration_points(
                1,
                "handcraft",
                "guangxiu:step-1",
                300,
                "2026-09-17T10:05:00+08:00",
                "heartbeat-2",
            )
            repeated = record_duration_points(
                1,
                "handcraft",
                "guangxiu:step-1",
                300,
                "2026-09-17T10:05:00+08:00",
                "heartbeat-2",
            )

            account = get_points_account(1)
            accrual = get_db().execute(
                """
                SELECT accumulated_seconds, awarded_units
                FROM points_learning_accruals
                WHERE user_id = 1
                """
            ).fetchone()
            transactions = get_points_ledger(1)

        self.assertEqual(second["status"], "processed")
        self.assertEqual(repeated["status"], "processed")
        self.assertEqual(second["awarded"], 1)
        self.assertEqual(repeated["awarded"], 1)
        self.assertEqual(account["balance"], 1)
        self.assertEqual(accrual["accumulated_seconds"], 600)
        self.assertEqual(accrual["awarded_units"], 1)
        self.assertEqual(len(transactions), 1)
        self.assertEqual(transactions[0]["delta"], 1)

    def test_natural_day_daily_limit_uses_platform_timezone(self):
        self.use_policy(
            seconds_per_point=1,
            daily_limit=2,
            training_weights={"default": 1},
        )
        with self.app.app_context():
            for index in range(3):
                record_duration_points(
                    1,
                    "handcraft",
                    "guangxiu:step-1",
                    1,
                    f"2026-09-16T0{6 + index}:00:00+08:00",
                    f"same-day-{index}",
                )
            same_day_balance = get_points_account(1)["balance"]

            record_duration_points(
                1,
                "handcraft",
                "guangxiu:step-1",
                1,
                "2026-09-17T00:00:01+08:00",
                "next-day",
            )
            next_day_balance = get_points_account(1)["balance"]
            daily_awards = [
                entry
                for entry in get_points_ledger(1)
                if entry["transaction_type"] == "award"
            ]

        self.assertEqual(same_day_balance, 2)
        self.assertEqual(next_day_balance, 3)
        self.assertEqual(len(daily_awards), 3)

    def test_daily_points_status_reports_below_reached_and_next_day(self):
        self.use_policy(
            seconds_per_point=1,
            daily_limit=2,
            training_weights={"default": 1},
        )
        with self.app.app_context():
            below = get_points_daily_status(
                1,
                at="2026-09-18T09:00:00+08:00",
            )
            record_duration_points(
                1,
                "handcraft",
                "guangxiu:step-1",
                1,
                "2026-09-18T09:01:00+08:00",
                "daily-status-1",
            )
            record_duration_points(
                1,
                "handcraft",
                "guangxiu:step-1",
                1,
                "2026-09-18T09:02:00+08:00",
                "daily-status-2",
            )
            reached = get_points_daily_status(
                1,
                at="2026-09-18T09:03:00+08:00",
            )
            next_day = get_points_daily_status(
                1,
                at="2026-09-19T09:00:00+08:00",
            )

        self.assertEqual(
            below,
            {
                "awarded_today": 0,
                "daily_limit": 2,
                "daily_limit_reached": False,
            },
        )
        self.assertEqual(
            reached,
            {
                "awarded_today": 2,
                "daily_limit": 2,
                "daily_limit_reached": True,
            },
        )
        self.assertEqual(
            next_day,
            {
                "awarded_today": 0,
                "daily_limit": 2,
                "daily_limit_reached": False,
            },
        )

    def test_daily_points_status_requires_an_effective_policy(self):
        with self.app.app_context():
            get_db().execute("DELETE FROM points_policy_snapshots")
            get_db().commit()
            set_points_policy_provider(self.app, FailingPolicyProvider())

            with self.assertRaisesRegex(
                PointsPolicyUnavailable,
                "积分规则暂不可用，请稍后重试",
            ):
                get_points_daily_status(
                    1,
                    at="2026-09-18T09:00:00+08:00",
                )

    def test_partial_daily_cap_consumes_units_without_reissue(self):
        self.use_policy(
            seconds_per_point=600,
            daily_limit=2,
            training_weights={"default": 1},
        )
        with self.app.app_context():
            first = record_duration_points(
                1,
                "handcraft",
                "guangxiu:step-1",
                3000,
                "2026-09-16T10:00:00+08:00",
                "partial-cap-1",
            )
            first_accrual = get_db().execute(
                """
                SELECT awarded_units, consumed_units
                FROM points_learning_accruals
                WHERE user_id = 1
                """
            ).fetchone()

            second = record_duration_points(
                1,
                "handcraft",
                "guangxiu:step-1",
                600,
                "2026-09-17T10:00:00+08:00",
                "partial-cap-2",
            )
            second_accrual = get_db().execute(
                """
                SELECT awarded_units, consumed_units
                FROM points_learning_accruals
                WHERE user_id = 1
                """
            ).fetchone()

        self.assertEqual(first["awarded"], 2)
        self.assertEqual(first_accrual["awarded_units"], 2)
        self.assertEqual(first_accrual["consumed_units"], 5)
        self.assertEqual(second["awarded"], 1)
        self.assertEqual(second_accrual["awarded_units"], 3)
        self.assertEqual(second_accrual["consumed_units"], 6)
        self.assertEqual(second["balance_after"], 3)

    def test_pending_events_are_processed_in_occurred_at_order(self):
        self.use_policy(
            seconds_per_point=600,
            daily_limit=100,
            training_weights={"default": 1},
        )
        with self.app.app_context():
            later = enqueue_learning_event(
                1,
                "handcraft",
                "training",
                "later-event",
                "2026-09-17T10:00:00+08:00",
            )
            older = enqueue_learning_event(
                1,
                "handcraft",
                "training",
                "older-event",
                "2026-09-16T10:00:00+08:00",
            )
            results = process_pending_events(1)

        self.assertEqual(
            [result["event_id"] for result in results],
            [older["event_id"], later["event_id"]],
        )

    def test_segment_longer_than_120_minutes_is_rejected(self):
        with self.app.app_context():
            with self.assertRaisesRegex(AgriValidationError, "120 分钟"):
                record_duration_points(
                    1,
                    "handcraft",
                    "guangxiu:step-1",
                    7201,
                    "2026-09-17T10:00:00+08:00",
                    "too-long",
                )
            event_count = get_db().execute(
                "SELECT COUNT(*) AS count FROM points_event_inbox"
            ).fetchone()["count"]

        self.assertEqual(event_count, 0)

    def test_spend_and_refund_follow_fifo_and_are_idempotent(self):
        self.use_policy(
            seconds_per_point=1,
            daily_limit=100,
            training_weights={
                "default": 1,
                "live_script": 5,
                "simulation": 7,
            },
        )
        with self.app.app_context():
            first = record_training_points(
                1,
                "ecommerce",
                "live_script",
                "training-1",
                "2026-09-17T09:00:00+08:00",
            )
            second = record_training_points(
                1,
                "ecommerce",
                "simulation",
                "training-2",
                "2026-09-17T09:05:00+08:00",
            )
            spend = spend_points(
                1,
                8,
                "handcraft",
                "redeem-1",
                "2026-09-17T10:00:00+08:00",
            )
            after_spend = get_points_account(1)["balance"]
            lots_after_spend = [
                dict(row)
                for row in get_db().execute(
                    """
                    SELECT original_points, remaining_points
                    FROM points_lots
                    ORDER BY id
                    """
                ).fetchall()
            ]
            refund = refund_points(
                1,
                8,
                "handcraft",
                "cancel-1",
                spend["id"],
                "2026-09-17T11:00:00+08:00",
            )
            repeated_refund = refund_points(
                1,
                8,
                "handcraft",
                "cancel-1",
                spend["id"],
                "2026-09-17T11:00:00+08:00",
            )
            different_source_refund = refund_points(
                1,
                8,
                "handcraft",
                "cancel-2",
                spend["id"],
                "2026-09-17T11:05:00+08:00",
            )
            account = get_points_account(1)
            lots_after_refund = [
                dict(row)
                for row in get_db().execute(
                    """
                    SELECT original_points, remaining_points
                    FROM points_lots
                    ORDER BY id
                    """
                ).fetchall()
            ]
            ledger = get_points_ledger(1)

            with self.assertRaisesRegex(AgriValidationError, "积分不足"):
                spend_points(
                    1,
                    99,
                    "handcraft",
                    "redeem-too-much",
                    "2026-09-17T12:00:00+08:00",
                )
            with self.assertRaisesRegex(
                AgriValidationError,
                "回退金额与原消费不一致",
            ):
                refund_points(
                    1,
                    7,
                    "handcraft",
                    "cancel-wrong-amount",
                    spend["id"],
                    "2026-09-17T12:05:00+08:00",
                )

        self.assertEqual(first["status"], "processed")
        self.assertEqual(second["status"], "processed")
        self.assertEqual(after_spend, 4)
        self.assertEqual(
            [lot["remaining_points"] for lot in lots_after_spend],
            [0, 4],
        )
        self.assertEqual(refund["id"], repeated_refund["id"])
        self.assertEqual(refund["id"], different_source_refund["id"])
        self.assertEqual(account["balance"], 12)
        self.assertEqual(
            [lot["remaining_points"] for lot in lots_after_refund],
            [5, 7],
        )
        self.assertEqual(
            [entry["transaction_type"] for entry in ledger[:3]],
            ["refund", "spend", "award"],
        )

    def test_training_weights_and_transaction_types_are_discrete(self):
        weights = {
            "live_script": 3,
            "simulation": 5,
            "copy_training": 7,
            "customer_service": 11,
        }
        self.use_policy(
            seconds_per_point=1,
            daily_limit=100,
            training_weights={"default": 1, **weights},
            expiry_mode="natural_year",
        )
        with self.app.app_context():
            for index, (event_type, expected_weight) in enumerate(
                weights.items()
            ):
                result = record_training_points(
                    1,
                    "ecommerce",
                    event_type,
                    f"weight-{event_type}",
                    f"2025-09-17T09:0{index}:00+08:00",
                )
                self.assertEqual(result["awarded"], expected_weight)

            spend = spend_points(
                1,
                4,
                "handcraft",
                "weight-spend",
                "2025-09-17T10:00:00+08:00",
            )
            refund_points(
                1,
                4,
                "handcraft",
                "weight-refund",
                spend["id"],
                "2025-09-17T11:00:00+08:00",
            )
            settle_user_expiry(
                1,
                "2026-01-01T00:00:00+08:00",
            )
            ledger = get_points_ledger(1)

        self.assertEqual(
            {entry["transaction_type"] for entry in ledger},
            {"award", "spend", "refund", "expire"},
        )

    def test_refund_of_expired_lot_creates_new_usable_lot(self):
        self.use_policy(
            seconds_per_point=1,
            daily_limit=100,
            training_weights={"default": 5, "copy_training": 5},
            expiry_mode="natural_year",
        )
        with self.app.app_context():
            record_training_points(
                1,
                "ecommerce",
                "copy_training",
                "expired-award",
                "2025-06-01T09:00:00+08:00",
            )
            spend = spend_points(
                1,
                5,
                "handcraft",
                "expired-spend",
                "2025-06-02T09:00:00+08:00",
            )
            refund = refund_points(
                1,
                5,
                "handcraft",
                "expired-refund",
                spend["id"],
                "2026-01-02T09:00:00+08:00",
            )
            lots = [
                dict(row)
                for row in get_db().execute(
                    """
                    SELECT original_points, remaining_points,
                           expires_at, created_at
                    FROM points_lots
                    ORDER BY id
                    """
                ).fetchall()
            ]
            usable_spend = spend_points(
                1,
                3,
                "handcraft",
                "new-lot-spend",
                "2026-01-03T09:00:00+08:00",
            )
            balance = get_points_account(1)["balance"]

        self.assertEqual(refund["balance_after"], 5)
        self.assertEqual(lots[0]["remaining_points"], 0)
        self.assertEqual(lots[1]["remaining_points"], 5)
        self.assertGreaterEqual(lots[1]["expires_at"], "2026-01-02T09:00:00+08:00")
        self.assertEqual(usable_spend["balance_after"], 2)
        self.assertEqual(balance, 2)

    def test_natural_year_expiry_is_idempotent(self):
        self.use_policy(
            seconds_per_point=1,
            daily_limit=100,
            training_weights={"default": 1, "copy_training": 2},
            expiry_mode="natural_year",
        )
        with self.app.app_context():
            record_training_points(
                1,
                "ecommerce",
                "copy_training",
                "training-expiry",
                "2025-06-01T09:00:00+08:00",
            )
            before = get_points_account(1, settle=False)["balance"]
            first = settle_user_expiry(
                1,
                "2026-01-01T00:00:00+08:00",
            )
            second = settle_user_expiry(
                1,
                "2026-01-01T00:00:00+08:00",
            )
            account = get_points_account(1)
            ledger = get_points_ledger(1)

        self.assertEqual(before, 2)
        self.assertEqual(first["points_cleared"], 2)
        self.assertEqual(second["points_cleared"], 0)
        self.assertEqual(account["balance"], 0)
        self.assertEqual(ledger[0]["transaction_type"], "expire")
        self.assertEqual(ledger[0]["delta"], -2)

    def test_no_rule_pauses_processing_without_losing_inbox_event(self):
        with self.app.app_context():
            get_db().execute("DELETE FROM points_policy_snapshots")
            get_db().commit()
            set_points_policy_provider(self.app, FailingPolicyProvider())
            event_id = enqueue_learning_event(
                1,
                "handcraft",
                "duration",
                "paused-event",
                "2026-09-17T10:00:00+08:00",
                600,
            )
            processed = process_pending_events(1)
            row = get_db().execute(
                """
                SELECT status, error
                FROM points_event_inbox
                WHERE id = ?
                """,
                (event_id["event_id"],),
            ).fetchone()

        self.assertEqual(len(processed), 1)
        self.assertEqual(processed[0]["status"], "pending")
        self.assertEqual(processed[0]["awarded"], 0)
        self.assertEqual(processed[0]["balance_after"], 0)
        self.assertIsNone(processed[0]["transaction"])
        self.assertEqual(event_id["status"], "pending")
        self.assertEqual(row["status"], "pending")
        self.assertIsNone(row["error"])

    def test_concurrent_same_learning_event_awards_once(self):
        self.use_policy(
            seconds_per_point=600,
            daily_limit=100,
            training_weights={"default": 1},
        )
        barrier = threading.Barrier(2)

        def record():
            with self.app.app_context():
                barrier.wait(timeout=5)
                return record_training_points(
                    1,
                    "handcraft",
                    "training",
                    "same-event",
                    "2026-09-17T10:00:00+08:00",
                )

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: record(), range(2)))

        with self.app.app_context():
            award_count = get_db().execute(
                """
                SELECT COUNT(*) AS count
                FROM points_transactions
                WHERE user_id = 1 AND transaction_type = 'award'
                """
            ).fetchone()["count"]
            account = get_points_account(1)

        self.assertTrue(all(result["status"] == "processed" for result in results))
        self.assertEqual(award_count, 1)
        self.assertEqual(account["balance"], 1)

    def test_concurrent_spend_does_not_allow_negative_balance(self):
        self.use_policy(
            seconds_per_point=1,
            daily_limit=100,
            training_weights={"default": 1},
        )
        with self.app.app_context():
            record_training_points(
                1,
                "ecommerce",
                "training",
                "funding-event",
                "2026-09-17T09:00:00+08:00",
            )
            for index in range(9):
                record_training_points(
                    1,
                    "ecommerce",
                    "training",
                    f"funding-event-{index}",
                    f"2026-09-17T09:0{index + 1}:00+08:00",
                )

        barrier = threading.Barrier(2)

        def spend(source_event_id: str):
            with self.app.app_context():
                barrier.wait(timeout=5)
                try:
                    result = spend_points(
                        1,
                        8,
                        "handcraft",
                        source_event_id,
                        "2026-09-17T11:00:00+08:00",
                    )
                    return "ok", result
                except AgriValidationError as error:
                    return "error", str(error)

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(
                executor.map(
                    spend,
                    ("concurrent-spend-1", "concurrent-spend-2"),
                )
            )

        with self.app.app_context():
            account = get_points_account(1)
            spend_count = get_db().execute(
                """
                SELECT COUNT(*) AS count
                FROM points_transactions
                WHERE user_id = 1 AND transaction_type = 'spend'
                """
            ).fetchone()["count"]

        self.assertEqual(sum(result[0] == "ok" for result in results), 1)
        self.assertEqual(sum(result[0] == "error" for result in results), 1)
        self.assertEqual(account["balance"], 2)
        self.assertGreaterEqual(account["balance"], 0)
        self.assertEqual(spend_count, 1)


if __name__ == "__main__":
    unittest.main()
