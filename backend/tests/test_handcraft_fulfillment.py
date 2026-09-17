import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import create_app
from app.agri_skills.errors import AgriNotFoundError, AgriValidationError
from app.db import get_db
from app.handcraft_inheritance import (
    apply_fulfillment_admin_action,
    redeem_reward,
    record_training_points,
    set_points_policy_provider,
)
from app.handcraft_inheritance.fulfillment import (
    cancel_pending_fulfillment,
    issue_fulfillment,
    list_admin_fulfillments,
    list_student_fulfillments,
    manual_verify_fulfillment,
    retry_fulfillment_notification,
    retry_pending_fulfillment_notifications,
    student_verify_fulfillment,
)
from app.handcraft_inheritance.presets import PLACEHOLDER_POINTS_POLICY


class StaticPolicyProvider:
    def __init__(self, policy):
        self.policy = copy.deepcopy(policy)

    def get_policy(self):
        return copy.deepcopy(self.policy)


class TestHandcraftFulfillment(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(Path(self.temp_dir.name) / "test.db"),
                "SECRET_KEY": "test-only-secret",
            }
        )
        self.policy = copy.deepcopy(PLACEHOLDER_POINTS_POLICY)
        self.policy.update(
            {
                "seconds_per_point": 1,
                "daily_limit": 1000,
                "training_weights": {"default": 1000},
            }
        )
        set_points_policy_provider(
            self.app,
            StaticPolicyProvider(self.policy),
        )
        with self.app.app_context():
            db = get_db()
            for user_id, username, role in (
                (1, "student01", "student"),
                (2, "student02", "student"),
                (3, "normal-admin", "admin"),
                (4, "super-admin", "super_admin"),
            ):
                db.execute(
                    """
                    INSERT INTO users (
                        id, username, password_hash, name, role, is_enabled,
                        created_at, updated_at
                    )
                    VALUES (?, ?, 'hash', ?, ?, 1, ?, ?)
                    """,
                    (
                        user_id,
                        username,
                        username,
                        role,
                        "2026-09-17T00:00:00+08:00",
                        "2026-09-17T00:00:00+08:00",
                    ),
                )
            db.execute(
                """
                INSERT INTO student_profiles (user_id, contact, updated_at)
                VALUES (1, '13800000001', '2026-09-17T00:00:00+08:00')
                """
            )
            db.commit()
            for user_id in (1, 2):
                result = record_training_points(
                    user_id,
                    "ecommerce",
                    "funding",
                    f"funding-{user_id}",
                    "2026-09-17T09:00:00+08:00",
                )
                self.assertEqual(result["status"], "processed")

    def tearDown(self):
        self.temp_dir.cleanup()

    def _redeem(self, user_id: int = 1, request_id: str = "request-1"):
        with self.app.app_context(), patch(
            "app.handcraft_inheritance.rewards.emit_redemption_succeeded"
        ):
            redemption = redeem_reward(
                user_id,
                "reward-guangxiu-bookmark",
                request_id,
            )
            fulfillment = get_db().execute(
                """
                SELECT *
                FROM fulfillments
                WHERE redemption_id = ?
                """,
                (redemption["id"],),
            ).fetchone()
            return dict(redemption), dict(fulfillment)

    def _fulfillment_state(self, fulfillment_id: int):
        with self.app.app_context():
            return dict(
                get_db().execute(
                    """
                    SELECT *
                    FROM fulfillments
                    WHERE id = ?
                    """,
                    (fulfillment_id,),
                ).fetchone()
            )

    def _mutation_snapshot(
        self,
        fulfillment_id: int,
        redemption_id: int,
    ) -> dict:
        with self.app.app_context():
            db = get_db()
            fulfillment = db.execute(
                """
                SELECT status, issued_at, verified_at, canceled_at
                FROM fulfillments
                WHERE id = ?
                """,
                (fulfillment_id,),
            ).fetchone()
            redemption = db.execute(
                """
                SELECT status, canceled_at
                FROM redemptions
                WHERE id = ?
                """,
                (redemption_id,),
            ).fetchone()
            reservation = db.execute(
                """
                SELECT status, released_at
                FROM reward_stock_reservations
                WHERE redemption_id = ?
                """,
                (redemption_id,),
            ).fetchone()
            account = db.execute(
                """
                SELECT balance
                FROM points_accounts
                WHERE user_id = 1
                """
            ).fetchone()
            transaction_counts = db.execute(
                """
                SELECT
                    SUM(transaction_type = 'spend') AS spend_count,
                    SUM(transaction_type = 'refund') AS refund_count
                FROM points_transactions
                WHERE user_id = 1
                """
            ).fetchone()
            lot_points = db.execute(
                """
                SELECT COALESCE(SUM(remaining_points), 0) AS total
                FROM points_lots
                WHERE user_id = 1
                """
            ).fetchone()["total"]
            notification_count = db.execute(
                """
                SELECT COUNT(*) AS count
                FROM system_notifications
                WHERE source_type = 'fulfillment'
                  AND source_id = ?
                """,
                (str(fulfillment_id),),
            ).fetchone()["count"]
            outbox = db.execute(
                """
                SELECT status, attempts, last_error
                FROM fulfillment_notification_outbox
                WHERE fulfillment_id = ?
                ORDER BY id
                """,
                (fulfillment_id,),
            ).fetchall()
            return {
                "fulfillment": dict(fulfillment),
                "redemption": dict(redemption),
                "reservation": dict(reservation),
                "balance": int(account["balance"]) if account else 0,
                "spend_count": int(transaction_counts["spend_count"] or 0),
                "refund_count": int(
                    transaction_counts["refund_count"] or 0
                ),
                "lot_points": int(lot_points),
                "notification_count": int(notification_count),
                "outbox": [dict(row) for row in outbox],
            }

    def test_legal_transitions_and_single_action_student_verification(self):
        redemption, fulfillment = self._redeem()

        with self.app.app_context(), patch(
            "app.handcraft_inheritance.fulfillment.emit_fulfillment_issued"
        ) as issue_emit:
            issued = issue_fulfillment(
                fulfillment["id"],
                role="admin",
            )
            issued_state = self._fulfillment_state(fulfillment["id"])
            redemption_state = dict(
                get_db().execute(
                    """
                    SELECT status
                    FROM redemptions
                    WHERE id = ?
                    """,
                    (redemption["id"],),
                ).fetchone()
            )

            self.assertEqual(issued["status"], "issued")
            self.assertEqual(issued["changed"], True)
            self.assertEqual(issued_state["status"], "issued")
            self.assertIsNone(issued_state["verified_at"])
            self.assertEqual(redemption_state["status"], "issued")
            issue_emit.assert_called_once()

            verified = student_verify_fulfillment(
                fulfillment["id"],
                1,
            )
            verified_state = self._fulfillment_state(fulfillment["id"])

        self.assertEqual(verified["status"], "verified")
        self.assertEqual(verified["changed"], True)
        self.assertEqual(verified_state["status"], "verified")
        self.assertIsNotNone(verified_state["verified_at"])

    def test_pending_can_be_canceled_and_invalid_cancellations_are_atomic(self):
        redemption, fulfillment = self._redeem()

        with self.app.app_context(), patch(
            "app.handcraft_inheritance.fulfillment.emit_fulfillment_cancelled"
        ) as cancel_emit:
            result = cancel_pending_fulfillment(
                fulfillment["id"],
                role="student",
                actor_user_id=1,
            )
            fulfillment_state = self._fulfillment_state(fulfillment["id"])
            redemption_state = dict(
                get_db().execute(
                    """
                    SELECT status
                    FROM redemptions
                    WHERE id = ?
                    """,
                    (redemption["id"],),
                ).fetchone()
            )
            reservation = dict(
                get_db().execute(
                    """
                    SELECT status
                    FROM reward_stock_reservations
                    WHERE redemption_id = ?
                    """,
                    (redemption["id"],),
                ).fetchone()
            )
            refund_count = get_db().execute(
                """
                SELECT COUNT(*) AS count
                FROM points_transactions
                WHERE transaction_type = 'refund'
                """
            ).fetchone()["count"]
            balance = get_db().execute(
                """
                SELECT balance
                FROM points_accounts
                WHERE user_id = 1
                """
            ).fetchone()["balance"]

        self.assertEqual(result["status"], "canceled")
        self.assertEqual(result["restored_points"], 30)
        self.assertEqual(fulfillment_state["status"], "canceled")
        self.assertEqual(redemption_state["status"], "canceled")
        self.assertEqual(reservation["status"], "released")
        self.assertEqual(refund_count, 1)
        self.assertEqual(balance, 1000)
        cancel_emit.assert_called_once()

        issued_redemption, issued_fulfillment = self._redeem(
            request_id="issued-request"
        )
        with self.app.app_context():
            issue_fulfillment(issued_fulfillment["id"], role="super_admin")
            with self.assertRaisesRegex(
                AgriValidationError,
                "当前履约状态不可取消",
            ):
                cancel_pending_fulfillment(
                    issued_fulfillment["id"],
                    role="student",
                    actor_user_id=1,
                )
            issued_state = self._fulfillment_state(issued_fulfillment["id"])
            issued_redemption_state = get_db().execute(
                """
                SELECT status
                FROM redemptions
                WHERE id = ?
                """,
                (issued_redemption["id"],),
            ).fetchone()

            self.assertEqual(issued_state["status"], "issued")
            self.assertEqual(issued_redemption_state["status"], "issued")

            student_verify_fulfillment(issued_fulfillment["id"], 1)
            with self.assertRaisesRegex(
                AgriValidationError,
                "当前履约状态不可取消",
            ):
                cancel_pending_fulfillment(
                    issued_fulfillment["id"],
                    role="admin",
                )
            self.assertEqual(
                self._fulfillment_state(issued_fulfillment["id"])["status"],
                "verified",
            )

    def test_issue_cancel_and_verify_are_idempotent(self):
        redemption, fulfillment = self._redeem()
        with self.app.app_context():
            first_issue = issue_fulfillment(
                fulfillment["id"],
                role="admin",
            )
            repeated_issue = issue_fulfillment(
                fulfillment["id"],
                role="admin",
            )
            first_verify = manual_verify_fulfillment(
                fulfillment["id"],
                role="super_admin",
            )
            repeated_verify = manual_verify_fulfillment(
                fulfillment["id"],
                role="super_admin",
            )
            notification_count = get_db().execute(
                """
                SELECT COUNT(*) AS count
                FROM system_notifications
                WHERE source_type = 'fulfillment'
                  AND source_id = ?
                """,
                (str(fulfillment["id"]),),
            ).fetchone()["count"]

            self.assertEqual(first_issue["changed"], True)
            self.assertEqual(repeated_issue["changed"], False)
            self.assertEqual(first_verify["changed"], True)
            self.assertEqual(repeated_verify["changed"], False)
            self.assertEqual(notification_count, 1)

        canceled_redemption, canceled_fulfillment = self._redeem(
            request_id="cancel-idempotent"
        )
        with self.app.app_context(), patch(
            "app.handcraft_inheritance.fulfillment.emit_fulfillment_cancelled"
        ):
            first_cancel = cancel_pending_fulfillment(
                canceled_fulfillment["id"],
                role="student",
                actor_user_id=1,
            )
            repeated_cancel = cancel_pending_fulfillment(
                canceled_fulfillment["id"],
                role="student",
                actor_user_id=1,
            )
            refund_count = get_db().execute(
                """
                SELECT COUNT(*) AS count
                FROM points_transactions
                WHERE transaction_type = 'refund'
                  AND source_event_id = ?
                """,
                (f"fulfillment-cancel:{canceled_fulfillment['id']}",),
            ).fetchone()["count"]

        self.assertEqual(first_cancel["changed"], True)
        self.assertEqual(repeated_cancel["changed"], False)
        self.assertEqual(refund_count, 1)
        self.assertEqual(
            repeated_cancel["redemption_id"],
            canceled_redemption["id"],
        )

    def test_admin_action_repeated_issue_reuses_committed_transition(self):
        redemption, fulfillment = self._redeem()

        with self.app.app_context():
            first = apply_fulfillment_admin_action(
                {
                    "fulfillment_id": fulfillment["id"],
                    "action": "issue",
                    "admin_role": "admin",
                }
            )
            repeated = apply_fulfillment_admin_action(
                {
                    "fulfillment_id": fulfillment["id"],
                    "action": "issue",
                    "admin_role": "admin",
                }
            )
            spend_count = get_db().execute(
                """
                SELECT COUNT(*) AS count
                FROM points_transactions
                WHERE transaction_type = 'spend'
                  AND source_event_id = ?
                """,
                (f"redemption:{redemption['request_id']}",),
            ).fetchone()["count"]
            notification_count = get_db().execute(
                """
                SELECT COUNT(*) AS count
                FROM system_notifications
                WHERE source_type = 'fulfillment'
                  AND source_id = ?
                """,
                (str(fulfillment["id"]),),
            ).fetchone()["count"]

        self.assertEqual(first["status"], "issued")
        self.assertEqual(first["changed"], True)
        self.assertEqual(repeated["status"], "issued")
        self.assertEqual(repeated["changed"], False)
        self.assertEqual(spend_count, 1)
        self.assertEqual(notification_count, 1)

    def test_student_ownership_is_enforced_for_read_and_verify(self):
        _, fulfillment = self._redeem()

        with self.app.app_context():
            self.assertEqual(list_student_fulfillments(2), [])
            with self.assertRaisesRegex(
                AgriValidationError,
                "无权操作该履约单",
            ):
                student_verify_fulfillment(fulfillment["id"], 2)
            with self.assertRaisesRegex(
                AgriValidationError,
                "无权操作该履约单",
            ):
                cancel_pending_fulfillment(
                    fulfillment["id"],
                    role="student",
                    actor_user_id=2,
                )
            self.assertEqual(
                self._fulfillment_state(fulfillment["id"])["status"],
                "pending",
            )

            issue_fulfillment(fulfillment["id"], role="admin")
            with self.assertRaisesRegex(
                AgriValidationError,
                "无权操作该履约单",
            ):
                student_verify_fulfillment(fulfillment["id"], 2)
            self.assertEqual(
                self._fulfillment_state(fulfillment["id"])["status"],
                "issued",
            )

    def test_cancel_rolls_back_refund_failure_atomically(self):
        redemption, fulfillment = self._redeem()
        with self.app.app_context(), patch(
            "app.handcraft_inheritance.fulfillment."
            "refund_points_in_transaction",
            side_effect=AgriValidationError("积分回退失败"),
        ):
            with self.assertRaisesRegex(AgriValidationError, "积分回退失败"):
                cancel_pending_fulfillment(
                    fulfillment["id"],
                    role="admin",
                )
            fulfillment_state = self._fulfillment_state(fulfillment["id"])
            redemption_state = get_db().execute(
                """
                SELECT status
                FROM redemptions
                WHERE id = ?
                """,
                (redemption["id"],),
            ).fetchone()
            reservation_state = get_db().execute(
                """
                SELECT status
                FROM reward_stock_reservations
                WHERE redemption_id = ?
                """,
                (redemption["id"],),
            ).fetchone()
            balance = get_db().execute(
                """
                SELECT balance
                FROM points_accounts
                WHERE user_id = 1
                """
            ).fetchone()["balance"]
            refund_count = get_db().execute(
                """
                SELECT COUNT(*) AS count
                FROM points_transactions
                WHERE transaction_type = 'refund'
                """
            ).fetchone()["count"]

        self.assertEqual(fulfillment_state["status"], "pending")
        self.assertEqual(redemption_state["status"], "pending")
        self.assertEqual(reservation_state["status"], "reserved")
        self.assertEqual(balance, 970)
        self.assertEqual(refund_count, 0)

    def test_cancel_rolls_back_stock_release_failure_atomically(self):
        redemption, fulfillment = self._redeem()
        provider = self.app.extensions["handcraft_reward_catalog_provider"]
        with self.app.app_context(), patch.object(
            provider,
            "release_stock",
            return_value=False,
        ):
            with self.assertRaisesRegex(
                AgriValidationError,
                "库存回滚失败",
            ):
                cancel_pending_fulfillment(
                    fulfillment["id"],
                    role="admin",
                )
            fulfillment_state = self._fulfillment_state(fulfillment["id"])
            redemption_state = get_db().execute(
                """
                SELECT status
                FROM redemptions
                WHERE id = ?
                """,
                (redemption["id"],),
            ).fetchone()
            reservation_state = get_db().execute(
                """
                SELECT status
                FROM reward_stock_reservations
                WHERE redemption_id = ?
                """,
                (redemption["id"],),
            ).fetchone()
            balance = get_db().execute(
                """
                SELECT balance
                FROM points_accounts
                WHERE user_id = 1
                """
            ).fetchone()["balance"]
            refund_count = get_db().execute(
                """
                SELECT COUNT(*) AS count
                FROM points_transactions
                WHERE transaction_type = 'refund'
                """
            ).fetchone()["count"]

        self.assertEqual(fulfillment_state["status"], "pending")
        self.assertEqual(redemption_state["status"], "pending")
        self.assertEqual(reservation_state["status"], "reserved")
        self.assertEqual(balance, 970)
        self.assertEqual(refund_count, 0)

    def test_notification_failure_does_not_rollback_and_retry_is_idempotent(self):
        redemption, fulfillment = self._redeem()
        with self.app.app_context():
            with patch(
                "app.handcraft_inheritance.fulfillment."
                "emit_fulfillment_cancelled",
                side_effect=RuntimeError("notification offline"),
            ):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "notification offline",
                ):
                    cancel_pending_fulfillment(
                        fulfillment["id"],
                        role="student",
                        actor_user_id=1,
                    )
                fulfillment_state = self._fulfillment_state(
                    fulfillment["id"]
                )
                redemption_state = get_db().execute(
                    """
                    SELECT status
                    FROM redemptions
                    WHERE id = ?
                    """,
                    (redemption["id"],),
                ).fetchone()
                refund_count = get_db().execute(
                    """
                    SELECT COUNT(*) AS count
                    FROM points_transactions
                    WHERE transaction_type = 'refund'
                    """
                ).fetchone()["count"]

            self.assertEqual(fulfillment_state["status"], "canceled")
            self.assertEqual(redemption_state["status"], "canceled")
            self.assertEqual(refund_count, 1)

            first_retry = retry_fulfillment_notification(
                fulfillment["id"],
                role="admin",
            )
            second_retry = retry_fulfillment_notification(
                fulfillment["id"],
                role="admin",
            )
            retry_refund_count = get_db().execute(
                """
                SELECT COUNT(*) AS count
                FROM points_transactions
                WHERE transaction_type = 'refund'
                """
            ).fetchone()["count"]
            notification_count = get_db().execute(
                """
                SELECT COUNT(*) AS count
                FROM system_notifications
                WHERE source_type = 'fulfillment'
                  AND source_id = ?
                """,
                (str(fulfillment["id"]),),
            ).fetchone()["count"]

        self.assertEqual(first_retry["status"], "canceled")
        self.assertEqual(second_retry["status"], "canceled")
        self.assertEqual(retry_refund_count, 1)
        self.assertEqual(notification_count, 1)

    def test_admin_roles_share_records_but_only_super_admin_has_config_scope(self):
        _, fulfillment = self._redeem()
        with self.app.app_context():
            issue_fulfillment(fulfillment["id"], role="admin")
            normal_records = list_admin_fulfillments("admin")
            super_records = list_admin_fulfillments("super_admin")

        self.assertEqual(len(normal_records), 1)
        self.assertEqual(len(super_records), 1)
        normal_record = normal_records[0]
        super_record = super_records[0]
        for record in (normal_record, super_record):
            self.assertEqual(record["user"]["username"], "student01")
            self.assertEqual(record["user"]["contact"], "13800000001")
            self.assertEqual(record["redemption"]["status"], "issued")
            self.assertEqual(record["fulfillment"]["status"], "issued")
            self.assertEqual(len(record["points_flow"]), 1)
            self.assertEqual(
                record["points_flow"][0]["transaction_type"],
                "spend",
            )
        self.assertFalse(
            normal_record["capabilities"]["configure_points_rules"]
        )
        self.assertFalse(normal_record["capabilities"]["manage_accounts"])
        self.assertTrue(
            normal_record["capabilities"]["view_user_details"]
        )
        self.assertTrue(normal_record["capabilities"]["issue_fulfillment"])
        self.assertTrue(
            normal_record["capabilities"]["manual_verify_fulfillment"]
        )
        self.assertTrue(
            super_record["capabilities"]["configure_points_rules"]
        )
        self.assertTrue(super_record["capabilities"]["manage_accounts"])

    def test_untrusted_roles_and_invalid_transitions_are_rejected(self):
        _, fulfillment = self._redeem()

        with self.app.app_context():
            operations = (
                lambda: issue_fulfillment(
                    fulfillment["id"],
                    role="student",
                ),
                lambda: manual_verify_fulfillment(
                    fulfillment["id"],
                    role="teacher",
                ),
                lambda: list_admin_fulfillments("student"),
            )
            for operation in operations:
                with self.subTest(operation=operation):
                    with self.assertRaisesRegex(
                        AgriValidationError,
                        "无管理权限",
                    ):
                        operation()
            with self.assertRaisesRegex(
                AgriValidationError,
                "当前履约状态不可手工核销",
            ):
                manual_verify_fulfillment(
                    fulfillment["id"],
                    role="admin",
                )
            with self.assertRaises(AgriNotFoundError):
                issue_fulfillment(999, role="super_admin")

    def test_illegal_transition_matrix_has_no_side_effects(self):
        def setup_state(state: str, request_id: str):
            redemption, fulfillment = self._redeem(request_id=request_id)
            with self.app.app_context():
                if state == "issued":
                    issue_fulfillment(fulfillment["id"], role="admin")
                elif state == "verified":
                    issue_fulfillment(fulfillment["id"], role="admin")
                    student_verify_fulfillment(fulfillment["id"], 1)
                elif state == "canceled":
                    cancel_pending_fulfillment(
                        fulfillment["id"],
                        role="admin",
                    )
            return redemption, fulfillment

        cases = (
            ("pending-admin-verify", "pending", "admin-verify"),
            ("pending-student-verify", "pending", "student-verify"),
            ("issued-cancel-admin", "issued", "cancel-admin"),
            ("issued-cancel-student", "issued", "cancel-student"),
            ("verified-issue", "verified", "issue"),
            ("verified-cancel-admin", "verified", "cancel-admin"),
            ("verified-cancel-student", "verified", "cancel-student"),
            ("canceled-issue", "canceled", "issue"),
            ("canceled-manual-verify", "canceled", "manual-verify"),
            ("canceled-student-verify", "canceled", "student-verify"),
        )

        for index, (name, state, operation) in enumerate(cases):
            with self.subTest(name=name):
                redemption, fulfillment = setup_state(
                    state,
                    f"matrix-{index}",
                )
                before = self._mutation_snapshot(
                    fulfillment["id"],
                    redemption["id"],
                )
                with self.app.app_context():
                    with self.assertRaises(AgriValidationError):
                        if operation == "admin-verify":
                            manual_verify_fulfillment(
                                fulfillment["id"],
                                role="admin",
                            )
                        elif operation == "student-verify":
                            student_verify_fulfillment(
                                fulfillment["id"],
                                1,
                            )
                        elif operation == "cancel-admin":
                            cancel_pending_fulfillment(
                                fulfillment["id"],
                                role="admin",
                            )
                        elif operation == "cancel-student":
                            cancel_pending_fulfillment(
                                fulfillment["id"],
                                role="student",
                                actor_user_id=1,
                            )
                        else:
                            issue_fulfillment(
                                fulfillment["id"],
                                role="admin",
                            )
                after = self._mutation_snapshot(
                    fulfillment["id"],
                    redemption["id"],
                )
                self.assertEqual(after, before)

    def test_outbox_survives_delivery_failure_and_retry_is_idempotent(self):
        redemption, fulfillment = self._redeem()
        with self.app.app_context():
            with patch(
                "app.handcraft_inheritance.fulfillment."
                "emit_fulfillment_cancelled",
                side_effect=RuntimeError("notification offline"),
            ):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "notification offline",
                ):
                    cancel_pending_fulfillment(
                        fulfillment["id"],
                        role="student",
                        actor_user_id=1,
                    )
                failed_outbox = dict(
                    get_db().execute(
                        """
                        SELECT *
                        FROM fulfillment_notification_outbox
                        WHERE fulfillment_id = ?
                        """,
                        (fulfillment["id"],),
                    ).fetchone()
                )
                failed_snapshot = self._mutation_snapshot(
                    fulfillment["id"],
                    redemption["id"],
                )

            self.assertEqual(failed_outbox["status"], "pending")
            self.assertEqual(failed_outbox["attempts"], 1)
            self.assertIn(
                "notification offline",
                failed_outbox["last_error"],
            )
            self.assertEqual(failed_snapshot["notification_count"], 0)
            self.assertEqual(failed_snapshot["refund_count"], 1)
            self.assertEqual(
                failed_snapshot["reservation"]["status"],
                "released",
            )

            first_retry = retry_fulfillment_notification(
                fulfillment["id"],
                role="admin",
            )
            second_retry = retry_fulfillment_notification(
                fulfillment["id"],
                role="admin",
            )
            final_snapshot = self._mutation_snapshot(
                fulfillment["id"],
                redemption["id"],
            )
            sent_outbox = dict(
                get_db().execute(
                    """
                    SELECT *
                    FROM fulfillment_notification_outbox
                    WHERE fulfillment_id = ?
                    """,
                    (fulfillment["id"],),
                ).fetchone()
            )

        self.assertEqual(first_retry["status"], "canceled")
        self.assertEqual(second_retry["status"], "canceled")
        self.assertEqual(first_retry["outbox"]["sent"], 1)
        self.assertEqual(second_retry["outbox"]["sent"], 0)
        self.assertEqual(
            final_snapshot["fulfillment"]["status"],
            "canceled",
        )
        self.assertEqual(final_snapshot["balance"], 1000)
        self.assertEqual(final_snapshot["spend_count"], 1)
        self.assertEqual(final_snapshot["refund_count"], 1)
        self.assertEqual(final_snapshot["lot_points"], 1000)
        self.assertEqual(
            final_snapshot["reservation"]["status"],
            "released",
        )
        self.assertEqual(final_snapshot["notification_count"], 1)
        self.assertEqual(sent_outbox["status"], "sent")
        self.assertEqual(sent_outbox["attempts"], 2)

    def test_batch_retry_reads_pending_outbox_once(self):
        redemption, fulfillment = self._redeem()
        with self.app.app_context():
            with patch(
                "app.handcraft_inheritance.fulfillment."
                "emit_fulfillment_cancelled",
                side_effect=RuntimeError("notification offline"),
            ):
                with self.assertRaises(RuntimeError):
                    cancel_pending_fulfillment(
                        fulfillment["id"],
                        role="admin",
                    )
            first = retry_pending_fulfillment_notifications(limit=100)
            second = retry_pending_fulfillment_notifications(limit=100)
            outbox = dict(
                get_db().execute(
                    """
                    SELECT *
                    FROM fulfillment_notification_outbox
                    WHERE fulfillment_id = ?
                    """,
                    (fulfillment["id"],),
                ).fetchone()
            )
            snapshot = self._mutation_snapshot(
                fulfillment["id"],
                redemption["id"],
            )

        self.assertEqual(first["attempted"], 1)
        self.assertEqual(first["sent"], 1)
        self.assertEqual(first["failed"], 0)
        self.assertEqual(second["attempted"], 0)
        self.assertEqual(outbox["status"], "sent")
        self.assertEqual(snapshot["refund_count"], 1)
        self.assertEqual(snapshot["notification_count"], 1)

    def test_duplicate_issue_and_cancel_do_not_duplicate_outbox(self):
        redemption, fulfillment = self._redeem()
        with self.app.app_context():
            issue_fulfillment(fulfillment["id"], role="admin")
            issue_fulfillment(fulfillment["id"], role="admin")
            issue_outbox_count = get_db().execute(
                """
                SELECT COUNT(*) AS count
                FROM fulfillment_notification_outbox
                WHERE fulfillment_id = ?
                """,
                (fulfillment["id"],),
            ).fetchone()["count"]
            self.assertEqual(issue_outbox_count, 1)

        canceled_redemption, canceled_fulfillment = self._redeem(
            request_id="duplicate-outbox-cancel"
        )
        with self.app.app_context():
            cancel_pending_fulfillment(
                canceled_fulfillment["id"],
                role="admin",
            )
            cancel_pending_fulfillment(
                canceled_fulfillment["id"],
                role="admin",
            )
            cancel_outbox_count = get_db().execute(
                """
                SELECT COUNT(*) AS count
                FROM fulfillment_notification_outbox
                WHERE fulfillment_id = ?
                """,
                (canceled_fulfillment["id"],),
            ).fetchone()["count"]
            self.assertEqual(cancel_outbox_count, 1)

        self.assertEqual(
            canceled_redemption["id"],
            canceled_fulfillment["redemption_id"],
        )

    def test_cancel_idempotency_does_not_require_points_policy(self):
        redemption, fulfillment = self._redeem()
        with self.app.app_context():
            first = cancel_pending_fulfillment(
                fulfillment["id"],
                role="admin",
            )
            set_points_policy_provider(
                self.app,
                StaticPolicyProvider({"invalid": True}),
            )
            repeated = cancel_pending_fulfillment(
                fulfillment["id"],
                role="admin",
            )
            snapshot = self._mutation_snapshot(
                fulfillment["id"],
                redemption["id"],
            )

        self.assertEqual(first["changed"], True)
        self.assertEqual(repeated["status"], "canceled")
        self.assertEqual(repeated["changed"], False)
        self.assertEqual(snapshot["refund_count"], 1)
        self.assertEqual(
            snapshot["reservation"]["status"],
            "released",
        )

    def test_cancel_without_refund_does_not_claim_restored_points(self):
        with self.app.app_context():
            db = get_db()
            db.execute(
                """
                INSERT INTO redemptions (
                    id, user_id, reward_id, reward_name, points_cost,
                    request_id, status, created_at, updated_at
                )
                VALUES (
                    50, 1, 'legacy-reward', '历史奖品', 30,
                    'legacy-request', 'pending',
                    '2026-09-17T00:00:00+08:00',
                    '2026-09-17T00:00:00+08:00'
                )
                """
            )
            db.execute(
                """
                INSERT INTO fulfillments (
                    id, redemption_id, user_id, status,
                    created_at, updated_at
                )
                VALUES (
                    60, 50, 1, 'pending',
                    '2026-09-17T00:00:00+08:00',
                    '2026-09-17T00:00:00+08:00'
                )
                """
            )
            db.commit()
            set_points_policy_provider(
                self.app,
                StaticPolicyProvider({"invalid": True}),
            )
            with patch(
                "app.handcraft_inheritance.fulfillment."
                "emit_fulfillment_cancelled"
            ) as emit:
                result = cancel_pending_fulfillment(
                    60,
                    role="admin",
                )

        self.assertEqual(result["status"], "canceled")
        self.assertEqual(result["restored_points"], 0)
        self.assertEqual(
            emit.call_args.kwargs["restored_points"],
            0,
        )


if __name__ == "__main__":
    unittest.main()
