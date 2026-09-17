import copy
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import create_app
from app.agri_skills.errors import AgriValidationError
from app.config import build_config
from app.db import get_db
from app.handcraft_inheritance import (
    get_points_account,
    record_training_points,
    refund_points,
    run_expiry_settlement,
    set_points_policy_provider,
    spend_points,
)
from app.handcraft_inheritance.presets import PLACEHOLDER_POINTS_POLICY


class StaticPolicyProvider:
    def __init__(self, policy):
        self.policy = copy.deepcopy(policy)

    def get_policy(self):
        return copy.deepcopy(self.policy)


class FailingPolicyProvider:
    def get_policy(self):
        raise RuntimeError("policy source unavailable")


class TestHandcraftPointsExpiry(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(Path(self.temp_dir.name) / "test.db"),
                "SECRET_KEY": "test-only-secret",
                "POINTS_EXPIRY_BATCH_SIZE": 100,
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

    def use_policy(self, **overrides):
        policy = copy.deepcopy(PLACEHOLDER_POINTS_POLICY)
        policy.update(
            {
                "seconds_per_point": 1,
                "daily_limit": 1000,
                "training_weights": {
                    "default": 1,
                    "copy_training": 2,
                    "simulation": 3,
                },
                **overrides,
            }
        )
        set_points_policy_provider(self.app, StaticPolicyProvider(policy))

    def award(self, user_id: int, event_type: str, source_id: str) -> None:
        with self.app.app_context():
            result = record_training_points(
                user_id,
                "ecommerce",
                event_type,
                source_id,
                "2025-06-01T09:00:00+08:00",
            )
            self.assertEqual(result["status"], "processed")

    def test_config_defaults_and_overrides_are_safe(self):
        with patch.dict(os.environ, {}, clear=True):
            defaults = build_config()
        self.assertEqual(defaults["POINTS_EXPIRY_TOKEN"], "")
        self.assertEqual(defaults["POINTS_EXPIRY_BATCH_SIZE"], 100)

        with patch.dict(
            os.environ,
            {
                "POINTS_EXPIRY_TOKEN": "internal-secret",
                "POINTS_EXPIRY_BATCH_SIZE": "25",
            },
            clear=True,
        ):
            configured = build_config()
        self.assertEqual(
            configured["POINTS_EXPIRY_TOKEN"],
            "internal-secret",
        )
        self.assertEqual(configured["POINTS_EXPIRY_BATCH_SIZE"], 25)

        for invalid in ("0", "abc"):
            with self.subTest(invalid=invalid):
                with patch.dict(
                    os.environ,
                    {"POINTS_EXPIRY_BATCH_SIZE": invalid},
                    clear=True,
                ):
                    with self.assertRaisesRegex(
                        RuntimeError,
                        "POINTS_EXPIRY_BATCH_SIZE",
                    ):
                        build_config()

    def test_permanent_mode_never_settles(self):
        self.use_policy(expiry_mode="permanent")
        self.award(1, "copy_training", "permanent-award")

        with self.app.app_context(), patch(
            "app.handcraft_inheritance.points.emit_points_expired"
        ) as emit:
            result = run_expiry_settlement(
                "2026-01-01T00:00:00+08:00",
                batch_size=10,
            )
            account = get_points_account(1)

        self.assertEqual(result["points_cleared"], 0)
        self.assertEqual(account["balance"], 2)
        emit.assert_not_called()

    def test_batch_settlement_is_fifo_one_transaction_per_learner(self):
        self.use_policy(expiry_mode="natural_year")
        self.award(1, "copy_training", "user-1-lot-1")
        self.award(1, "simulation", "user-1-lot-2")
        self.award(2, "copy_training", "user-2-lot-1")

        with self.app.app_context(), patch(
            "app.handcraft_inheritance.points.emit_points_expired"
        ) as emit:
            first = run_expiry_settlement(
                "2026-01-01T00:00:00+08:00",
                batch_size=10,
            )
            first_notifications = emit.call_count
            second = run_expiry_settlement(
                "2026-01-01T00:00:00+08:00",
                batch_size=10,
            )
            transactions = get_db().execute(
                """
                SELECT user_id, transaction_type, delta, metadata_json
                FROM points_transactions
                WHERE transaction_type = 'expire'
                ORDER BY user_id
                """
            ).fetchall()
            outbox = get_db().execute(
                """
                SELECT event_id, status, sent_at
                FROM points_notification_outbox
                ORDER BY user_id
                """
            ).fetchall()
            remaining = get_db().execute(
                """
                SELECT COUNT(*) AS count
                FROM points_lots
                WHERE expires_at <= '2026-01-01T00:00:00+08:00'
                  AND remaining_points > 0
                """
            ).fetchone()["count"]

        self.assertEqual(first["processed_users"], 2)
        self.assertEqual(first["points_cleared"], 7)
        self.assertEqual(first["notifications"], 2)
        self.assertEqual(first_notifications, 2)
        self.assertEqual(second["points_cleared"], 0)
        self.assertEqual(emit.call_count, 2)
        self.assertEqual(len(transactions), 2)
        self.assertEqual(
            [row["status"] for row in outbox],
            ["sent", "sent"],
        )
        self.assertTrue(all(row["sent_at"] for row in outbox))
        self.assertEqual(
            [(row["user_id"], row["delta"]) for row in transactions],
            [(1, -5), (2, -2)],
        )
        self.assertEqual(remaining, 0)

    def test_lazy_settlement_runs_before_account_read(self):
        self.use_policy(expiry_mode="natural_year")
        self.award(1, "copy_training", "lazy-award")

        with self.app.app_context(), patch(
            "app.handcraft_inheritance.points.emit_points_expired"
        ) as emit:
            account = get_points_account(1)
            transactions = get_db().execute(
                """
                SELECT COUNT(*) AS count
                FROM points_transactions
                WHERE transaction_type = 'expire'
                """
            ).fetchone()["count"]

        self.assertEqual(account["balance"], 0)
        self.assertEqual(transactions, 1)
        emit.assert_called_once()

    def test_no_rule_pauses_batch_and_lazy_settlement(self):
        self.use_policy(expiry_mode="natural_year")
        self.award(1, "copy_training", "paused-award")
        with self.app.app_context():
            get_db().execute("DELETE FROM points_policy_snapshots")
            get_db().commit()
            set_points_policy_provider(self.app, FailingPolicyProvider())
            batch = run_expiry_settlement(
                "2026-01-01T00:00:00+08:00",
                batch_size=10,
            )
            account = get_points_account(1)
            remaining = get_db().execute(
                """
                SELECT remaining_points
                FROM points_lots
                WHERE user_id = 1
                """
            ).fetchone()["remaining_points"]

        self.assertTrue(batch["paused"])
        self.assertEqual(batch["points_cleared"], 0)
        self.assertEqual(account["balance"], 2)
        self.assertEqual(remaining, 2)

    def test_failed_settlement_leaves_lots_for_next_run(self):
        self.use_policy(expiry_mode="natural_year")
        self.award(1, "copy_training", "retry-award")

        with self.app.app_context(), patch(
            "app.handcraft_inheritance.points._ensure_account",
            side_effect=RuntimeError("database write failed"),
        ), patch(
            "app.handcraft_inheritance.points.emit_points_expired"
        ):
            failed = run_expiry_settlement(
                "2026-01-01T00:00:00+08:00",
                batch_size=10,
            )
            remaining_after_failure = get_db().execute(
                """
                SELECT remaining_points
                FROM points_lots
                WHERE user_id = 1
                """
            ).fetchone()["remaining_points"]

        with self.app.app_context(), patch(
            "app.handcraft_inheritance.points.emit_points_expired"
        ) as emit:
            retried = run_expiry_settlement(
                "2026-01-01T00:00:00+08:00",
                batch_size=10,
            )
            account = get_points_account(1)

        self.assertEqual(failed["failed_users"], 1)
        self.assertEqual(remaining_after_failure, 2)
        self.assertEqual(retried["points_cleared"], 2)
        self.assertEqual(account["balance"], 0)
        emit.assert_called_once()

    def test_expiry_notification_failure_retries_on_later_access(self):
        self.use_policy(expiry_mode="natural_year")
        self.award(1, "copy_training", "notification-retry-award")

        with self.app.app_context(), patch(
            "app.handcraft_inheritance.points.emit_points_expired",
            side_effect=RuntimeError("notification offline"),
        ):
            failed = run_expiry_settlement(
                "2026-01-01T00:00:00+08:00",
                batch_size=10,
            )
            expire_transaction = get_db().execute(
                """
                SELECT id, metadata_json
                FROM points_transactions
                WHERE user_id = 1 AND transaction_type = 'expire'
                """
            ).fetchone()
            pending_outbox = get_db().execute(
                """
                SELECT status
                FROM points_notification_outbox
                WHERE user_id = 1
                """
            ).fetchone()
            balance_after_settlement = get_db().execute(
                """
                SELECT balance
                FROM points_accounts
                WHERE user_id = 1
                """
            ).fetchone()["balance"]

        with self.app.app_context():
            account = get_points_account(1)
            first_count = get_db().execute(
                """
                SELECT COUNT(*) AS count
                FROM system_notifications
                WHERE recipient_id = 1
                  AND event_type = 'points_expired'
                """
            ).fetchone()["count"]
            sent_outbox = get_db().execute(
                """
                SELECT status, sent_at
                FROM points_notification_outbox
                WHERE user_id = 1
                """
            ).fetchone()
            metadata_after_retry = get_db().execute(
                """
                SELECT metadata_json
                FROM points_transactions
                WHERE user_id = 1 AND transaction_type = 'expire'
                """
            ).fetchone()["metadata_json"]
            get_points_account(1)
            second_count = get_db().execute(
                """
                SELECT COUNT(*) AS count
                FROM system_notifications
                WHERE recipient_id = 1
                  AND event_type = 'points_expired'
                """
            ).fetchone()["count"]

        self.assertEqual(failed["notifications"], 0)
        self.assertEqual(balance_after_settlement, 0)
        self.assertIsNotNone(expire_transaction)
        self.assertEqual(pending_outbox["status"], "pending")
        self.assertEqual(account["balance"], 0)
        self.assertEqual(first_count, 1)
        self.assertEqual(second_count, 1)
        self.assertEqual(sent_outbox["status"], "sent")
        self.assertTrue(sent_outbox["sent_at"])
        self.assertEqual(metadata_after_retry, expire_transaction["metadata_json"])
        self.assertEqual(metadata_after_retry, "{}")

    def test_public_spend_and_refund_run_lazy_expiry_guard(self):
        self.use_policy(expiry_mode="natural_year")
        self.award(1, "copy_training", "spend-expired-award")
        self.award(2, "copy_training", "refund-source-award")
        self.award(2, "simulation", "refund-source-award-2")

        with self.app.app_context():
            with self.assertRaisesRegex(
                AgriValidationError,
                "积分不足",
            ):
                spend_points(
                    1,
                    1,
                    "handcraft",
                    "spend-after-expiry",
                    "2026-01-02T09:00:00+08:00",
                )
            user_1_balance = get_db().execute(
                """
                SELECT balance
                FROM points_accounts
                WHERE user_id = 1
                """
            ).fetchone()["balance"]
            expire_count = get_db().execute(
                """
                SELECT COUNT(*) AS count
                FROM points_transactions
                WHERE user_id = 1 AND transaction_type = 'expire'
                """
            ).fetchone()["count"]

            original_spend = spend_points(
                2,
                5,
                "handcraft",
                "original-spend",
                "2025-06-02T09:00:00+08:00",
            )
            refund = refund_points(
                2,
                5,
                "handcraft",
                "refund-after-expiry",
                original_spend["id"],
                "2026-01-02T09:00:00+08:00",
            )
            refund_lot = get_db().execute(
                """
                SELECT remaining_points, expires_at
                FROM points_lots
                WHERE user_id = 2
                ORDER BY id DESC
                LIMIT 1
                """
            ).fetchone()

        self.assertEqual(user_1_balance, 0)
        self.assertEqual(expire_count, 1)
        self.assertEqual(refund["balance_after"], 5)
        self.assertEqual(refund_lot["remaining_points"], 5)
        self.assertGreaterEqual(
            refund_lot["expires_at"],
            "2026-01-02T09:00:00+08:00",
        )

    def test_batch_aggregates_per_user_paused_results(self):
        self.use_policy(expiry_mode="natural_year")
        self.award(1, "copy_training", "paused-user-1")
        self.award(2, "copy_training", "paused-user-2")

        def fake_settle(user_id, now):
            if user_id == 1:
                return {
                    "points_cleared": 2,
                    "lots": 1,
                    "transaction_id": 1,
                    "paused": False,
                    "notification_sent": True,
                }
            return {
                "points_cleared": 0,
                "lots": 0,
                "transaction_id": None,
                "paused": True,
                "notification_sent": False,
                "error": "积分规则暂不可用，请稍后重试",
            }

        with self.app.app_context(), patch(
            "app.handcraft_inheritance.points.settle_user_expiry",
            side_effect=fake_settle,
        ), patch(
            "app.handcraft_inheritance.points."
            "retry_pending_expiry_notifications"
        ):
            result = run_expiry_settlement(
                "2026-01-01T00:00:00+08:00",
                batch_size=10,
            )

        self.assertTrue(result["paused"])
        self.assertEqual(result["paused_users"], 1)
        self.assertEqual(result["processed_users"], 1)

    def test_sent_outbox_rows_do_not_starve_pending_users(self):
        self.use_policy(expiry_mode="natural_year")
        with self.app.app_context():
            db = get_db()
            for user_id, status in ((1, "sent"), (2, "pending")):
                cursor = db.execute(
                    """
                    INSERT INTO points_transactions (
                        user_id, transaction_type, source_module,
                        source_event_id, delta, balance_after,
                        metadata_json, created_at
                    )
                    VALUES (?, 'expire', 'points', ?, ?, 0, '{}', ?)
                    """,
                    (
                        user_id,
                        f"seed-expire-{user_id}",
                        user_id * -1,
                        "2026-01-01T00:00:00+08:00",
                    ),
                )
                transaction_id = int(cursor.lastrowid)
                db.execute(
                    """
                    INSERT INTO points_notification_outbox (
                        user_id, event_type, event_id, transaction_id,
                        payload_json, status, created_at, sent_at
                    )
                    VALUES (
                        ?, 'points_expired', ?, ?, ?, ?, ?,
                        CASE WHEN ? = 'sent' THEN ? ELSE NULL END
                    )
                    """,
                    (
                        user_id,
                        f"handcraft-points-expiry:{transaction_id}",
                        transaction_id,
                        f'{{"student_id": {user_id}, "points_cleared": {user_id}}}',
                        status,
                        "2026-01-01T00:00:00+08:00",
                        status,
                        "2026-01-01T00:00:01+08:00",
                    ),
                )
            db.commit()

        with self.app.app_context(), patch(
            "app.handcraft_inheritance.points.emit_points_expired"
        ) as emit:
            result = run_expiry_settlement(
                "2026-01-01T01:00:00+08:00",
                batch_size=1,
            )
            statuses = {
                row["user_id"]: row["status"]
                for row in get_db().execute(
                    """
                    SELECT user_id, status
                    FROM points_notification_outbox
                    """
                ).fetchall()
            }

        self.assertEqual(result["notifications"], 1)
        self.assertEqual(emit.call_count, 1)
        self.assertEqual(emit.call_args.kwargs["student_id"], 2)
        self.assertEqual(statuses, {1: "sent", 2: "sent"})


if __name__ == "__main__":
    unittest.main()
