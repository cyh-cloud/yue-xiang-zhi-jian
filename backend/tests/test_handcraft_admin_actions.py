import threading
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from app import create_app
from app.agri_skills.errors import AgriNotFoundError, AgriValidationError
from app.db import get_db
from app.handcraft_inheritance import (
    apply_fulfillment_admin_action,
    apply_video_review,
    get_fulfillment_action_provider,
    get_video_review_action_provider,
    set_fulfillment_action_provider,
    set_video_review_action_provider,
)


class ReplacementVideoReviewProvider:
    def __init__(self):
        self.actions = []

    def apply(self, action):
        self.actions.append(dict(action))
        return {"status": "replacement-approved", "notification": None}


class ReplacementFulfillmentAdminProvider:
    def __init__(self):
        self.actions = []

    def apply(self, action):
        self.actions.append(dict(action))
        return {"status": "replacement-issued", "notification": None}


class TestHandcraftAdminActions(unittest.TestCase):
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
            self._insert_user()

    def tearDown(self):
        self.temp_dir.cleanup()

    @staticmethod
    def _insert_user() -> None:
        get_db().execute(
            """
            INSERT INTO users (
                id, username, password_hash, name, role, is_enabled,
                created_at, updated_at
            )
            VALUES (
                1, 'submitter', 'hash', '提交者', 'teacher', 1,
                '2026-09-17T00:00:00+08:00',
                '2026-09-17T00:00:00+08:00'
            )
            """
        )
        get_db().commit()

    @staticmethod
    def _insert_video(
        *,
        video_id: str = "review-video",
        status: str = "pending",
        version: int = 1,
    ) -> None:
        get_db().execute(
            """
            INSERT INTO heritage_videos (
                video_id, craft_key, title, review_status,
                source_available, media_url, version, rejection_opinion,
                published_at, created_at, updated_at
            )
            VALUES (?, 'guangxiu', '广绣教学', ?, 1,
                    'https://example.test/video.mp4', ?, NULL,
                    ?, '2026-09-17T00:00:00+08:00',
                    '2026-09-17T00:00:00+08:00')
            """,
            (
                video_id,
                status,
                version,
                (
                    "2026-09-17T00:00:00+08:00"
                    if status == "approved"
                    else None
                ),
            ),
        )
        get_db().commit()

    @staticmethod
    def _insert_fulfillment(
        *,
        fulfillment_id: int = 20,
        status: str = "pending",
    ) -> None:
        db = get_db()
        db.execute(
            """
            INSERT INTO redemptions (
                id, user_id, reward_id, reward_name, points_cost,
                request_id, status, created_at, updated_at
            )
            VALUES (
                10, 1, 'reward-1', '广绣书签', 30, 'request-1', ?,
                '2026-09-17T00:00:00+08:00',
                '2026-09-17T00:00:00+08:00'
            )
            """,
            (status,),
        )
        db.execute(
            """
            INSERT INTO fulfillments (
                id, redemption_id, user_id, status,
                created_at, updated_at
            )
            VALUES (
                ?, 10, 1, ?, '2026-09-17T00:00:00+08:00',
                '2026-09-17T00:00:00+08:00'
            )
            """,
            (fulfillment_id, status),
        )
        db.commit()

    def test_approve_video_updates_state_and_emits_after_commit(self):
        with self.app.app_context():
            self._insert_video()
            before_tables = {
                row["name"]
                for row in get_db().execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
            with patch(
                "app.handcraft_inheritance.admin_actions.emit_review_result"
            ) as emit:
                result = apply_video_review(
                    {
                        "video_id": "review-video",
                        "action": "approve",
                        "reviewer_role": "admin",
                        "submitter_id": 1,
                        "version": 1,
                    }
                )
            row = get_db().execute(
                """
                SELECT review_status, version, rejection_opinion
                FROM heritage_videos
                WHERE video_id = 'review-video'
                """
            ).fetchone()
            after_tables = {
                row["name"]
                for row in get_db().execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }

        self.assertEqual(result["status"], "approved")
        self.assertEqual(row["review_status"], "approved")
        self.assertEqual(row["version"], 1)
        self.assertIsNone(row["rejection_opinion"])
        emit.assert_called_once_with(
            event_id="handcraft-video-review:review-video:v1:approve",
            submitter_id=1,
            content_type="handcraft_teaching_video",
            content_id="review-video",
            approved=True,
            opinion=None,
        )
        self.assertEqual(after_tables, before_tables)

    def test_reject_video_requires_opinion_and_records_result(self):
        with self.app.app_context():
            self._insert_video()
            with patch(
                "app.handcraft_inheritance.admin_actions.emit_review_result"
            ) as emit:
                with self.assertRaisesRegex(
                    AgriValidationError,
                    "驳回意见不能为空",
                ):
                    apply_video_review(
                        {
                            "video_id": "review-video",
                            "action": "reject",
                            "reviewer_role": "super_admin",
                            "submitter_id": 1,
                            "version": 1,
                        }
                    )
                row = get_db().execute(
                    """
                    SELECT review_status
                    FROM heritage_videos
                    WHERE video_id = 'review-video'
                    """
                ).fetchone()
                self.assertEqual(row["review_status"], "pending")
                emit.assert_not_called()

                result = apply_video_review(
                    {
                        "video_id": "review-video",
                        "action": "reject",
                        "reviewer_role": "super_admin",
                        "submitter_id": 1,
                        "version": 1,
                        "opinion": "画面不稳定，请重新录制。",
                    }
                )
                row = get_db().execute(
                    """
                    SELECT review_status, rejection_opinion
                    FROM heritage_videos
                    WHERE video_id = 'review-video'
                    """
                ).fetchone()

        self.assertEqual(result["status"], "rejected")
        self.assertEqual(row["review_status"], "rejected")
        self.assertEqual(
            row["rejection_opinion"],
            "画面不稳定，请重新录制。",
        )
        emit.assert_called_once_with(
            event_id="handcraft-video-review:review-video:v1:reject",
            submitter_id=1,
            content_type="handcraft_teaching_video",
            content_id="review-video",
            approved=False,
            opinion="画面不稳定，请重新录制。",
        )

    def test_editing_pending_keeps_pending_and_approved_edit_returns_pending(
        self,
    ):
        with self.app.app_context():
            self._insert_video()
            pending = apply_video_review(
                {
                    "video_id": "review-video",
                    "action": "edit",
                    "actor_role": "teacher",
                    "actor_id": 1,
                    "submitter_id": 1,
                    "version": 1,
                    "title": "广绣教学修订版",
                    "media_url": "https://example.test/revision.mp4",
                }
            )
            pending_row = get_db().execute(
                """
                SELECT review_status, version, title, media_url
                FROM heritage_videos
                WHERE video_id = 'review-video'
                """
            ).fetchone()

            self._insert_video(
                video_id="approved-video",
                status="approved",
            )
            approved = apply_video_review(
                {
                    "video_id": "approved-video",
                    "action": "edit",
                    "actor_role": "teacher",
                    "actor_id": 1,
                    "submitter_id": 1,
                    "version": 1,
                    "title": "已上架视频修订版",
                }
            )
            approved_row = get_db().execute(
                """
                SELECT review_status, version, title, published_at
                FROM heritage_videos
                WHERE video_id = 'approved-video'
                """
            ).fetchone()

        self.assertEqual(pending["status"], "pending")
        self.assertEqual(pending_row["review_status"], "pending")
        self.assertEqual(pending_row["version"], 2)
        self.assertEqual(pending_row["title"], "广绣教学修订版")
        self.assertEqual(
            pending_row["media_url"],
            "https://example.test/revision.mp4",
        )
        self.assertEqual(approved["status"], "pending")
        self.assertEqual(approved_row["review_status"], "pending")
        self.assertEqual(approved_row["version"], 2)
        self.assertIsNone(approved_row["published_at"])

    def test_noop_video_edit_preserves_status_and_version(self):
        with self.app.app_context():
            self._insert_video(status="approved")
            with patch(
                "app.handcraft_inheritance.admin_actions.emit_review_result"
            ) as emit:
                result = apply_video_review(
                    {
                        "video_id": "review-video",
                        "action": "edit",
                        "actor_role": "teacher",
                        "actor_id": 1,
                        "submitter_id": 1,
                        "version": 1,
                    }
                )
            row = get_db().execute(
                """
                SELECT review_status, version, published_at
                FROM heritage_videos
                WHERE video_id = 'review-video'
                """
            ).fetchone()

        self.assertEqual(result["status"], "approved")
        self.assertEqual(result["version"], 1)
        self.assertEqual(row["review_status"], "approved")
        self.assertEqual(row["version"], 1)
        self.assertIsNotNone(row["published_at"])
        emit.assert_not_called()

    def test_video_edit_rejects_admin_and_mismatched_teacher(self):
        with self.app.app_context():
            self._insert_video()
            invalid_actions = (
                {
                    "video_id": "review-video",
                    "action": "edit",
                    "actor_role": "admin",
                    "actor_id": 1,
                    "submitter_id": 1,
                    "version": 1,
                    "title": "管理员不应代编辑",
                },
                {
                    "video_id": "review-video",
                    "action": "edit",
                    "actor_role": "teacher",
                    "actor_id": 2,
                    "submitter_id": 1,
                    "version": 1,
                    "title": "非本人不应编辑",
                },
            )

            for action in invalid_actions:
                with self.subTest(actor=action["actor_role"]):
                    with self.assertRaises(AgriValidationError):
                        apply_video_review(action)
                    row = get_db().execute(
                        """
                        SELECT review_status, version, title
                        FROM heritage_videos
                        WHERE video_id = 'review-video'
                        """
                    ).fetchone()
                    self.assertEqual(row["review_status"], "pending")
                    self.assertEqual(row["version"], 1)
                    self.assertEqual(row["title"], "广绣教学")

    def test_video_invalid_role_version_and_transition_are_atomic(self):
        with self.app.app_context():
            self._insert_video(status="approved")
            for action in (
                {
                    "video_id": "review-video",
                    "action": "reject",
                    "reviewer_role": "student",
                    "submitter_id": 1,
                    "version": 1,
                    "opinion": "不应执行",
                },
                {
                    "video_id": "review-video",
                    "action": "approve",
                    "reviewer_role": "admin",
                    "submitter_id": 1,
                    "version": 1,
                },
                {
                    "video_id": "review-video",
                    "action": "edit",
                    "actor_role": "teacher",
                    "actor_id": 1,
                    "submitter_id": 1,
                    "version": 99,
                },
            ):
                with self.subTest(action=action["action"]):
                    with self.assertRaises(AgriValidationError):
                        apply_video_review(action)
                    row = get_db().execute(
                        """
                        SELECT review_status, version, title
                        FROM heritage_videos
                        WHERE video_id = 'review-video'
                        """
                    ).fetchone()
                    self.assertEqual(row["review_status"], "approved")
                    self.assertEqual(row["version"], 1)
                    self.assertEqual(row["title"], "广绣教学")

            with self.assertRaises(AgriNotFoundError):
                apply_video_review(
                    {
                        "video_id": "missing-video",
                        "action": "approve",
                        "reviewer_role": "admin",
                        "submitter_id": 1,
                        "version": 1,
                    }
                )

    def test_concurrent_approve_and_reject_allow_only_one_review(self):
        with self.app.app_context():
            self._insert_video()
        barrier = threading.Barrier(2)

        def perform(action: str):
            with self.app.app_context():
                barrier.wait(timeout=5)
                try:
                    result = apply_video_review(
                        {
                            "video_id": "review-video",
                            "action": action,
                            "reviewer_role": "admin",
                            "submitter_id": 1,
                            "version": 1,
                            "opinion": (
                                "画面需要重录。"
                                if action == "reject"
                                else None
                            ),
                        }
                    )
                    return "ok", result["status"]
                except AgriValidationError as error:
                    return "error", str(error)

        with patch(
            "app.handcraft_inheritance.admin_actions.emit_review_result"
        ) as emit:
            with ThreadPoolExecutor(max_workers=2) as executor:
                results = list(
                    executor.map(perform, ("approve", "reject"))
                )

        with self.app.app_context():
            row = get_db().execute(
                """
                SELECT review_status, rejection_opinion
                FROM heritage_videos
                WHERE video_id = 'review-video'
                """
            ).fetchone()

        successes = [result for result in results if result[0] == "ok"]
        failures = [result for result in results if result[0] == "error"]
        self.assertEqual(len(successes), 1)
        self.assertEqual(len(failures), 1)
        self.assertEqual(row["review_status"], successes[0][1])
        if row["review_status"] == "approved":
            self.assertIsNone(row["rejection_opinion"])
            expected_approved = True
        else:
            self.assertEqual(row["rejection_opinion"], "画面需要重录。")
            expected_approved = False
        emit.assert_called_once()
        self.assertEqual(
            emit.call_args.kwargs["approved"],
            expected_approved,
        )

    def test_issue_fulfillment_updates_state_and_emits_after_commit(self):
        with self.app.app_context():
            self._insert_fulfillment()
            with patch(
                "app.handcraft_inheritance.admin_actions."
                "emit_fulfillment_issued"
            ) as emit:
                result = apply_fulfillment_admin_action(
                    {
                        "fulfillment_id": 20,
                        "action": "issue",
                        "admin_role": "admin",
                    }
                )
            row = get_db().execute(
                """
                SELECT status, issued_at
                FROM fulfillments
                WHERE id = 20
                """
            ).fetchone()

        self.assertEqual(result["status"], "issued")
        self.assertEqual(row["status"], "issued")
        self.assertIsNotNone(row["issued_at"])
        emit.assert_called_once_with(
            event_id="handcraft-fulfillment:20:issue",
            student_id=1,
            fulfillment_id="20",
            prize_name="广绣书签",
        )

    def test_cancel_pending_fulfillment_emits_restored_points(self):
        with self.app.app_context():
            self._insert_fulfillment()
            db = get_db()
            db.execute(
                """
                INSERT INTO points_accounts (user_id, balance, updated_at)
                VALUES (1, 970, '2026-09-17T00:00:00+08:00')
                """
            )
            award = db.execute(
                """
                INSERT INTO points_transactions (
                    user_id, transaction_type, source_module,
                    source_event_id, delta, balance_after,
                    metadata_json, created_at
                )
                VALUES (
                    1, 'award', 'test', 'fixture-award', 1000, 1000,
                    '{}', '2026-09-17T00:00:00+08:00'
                )
                """
            )
            lot = db.execute(
                """
                INSERT INTO points_lots (
                    user_id, award_transaction_id, original_points,
                    remaining_points, expires_at, created_at
                )
                VALUES (
                    1, ?, 1000, 970, NULL,
                    '2026-09-17T00:00:00+08:00'
                )
                """,
                (award.lastrowid,),
            )
            spend = db.execute(
                """
                INSERT INTO points_transactions (
                    user_id, transaction_type, source_module,
                    source_event_id, delta, balance_after,
                    metadata_json, created_at
                )
                VALUES (
                    1, 'spend', 'handcraft', 'redemption:request-1',
                    -30, 970, '{}', '2026-09-17T00:00:00+08:00'
                )
                """
            )
            db.execute(
                """
                INSERT INTO points_allocations (
                    transaction_id, lot_id, points
                )
                VALUES (?, ?, 30)
                """,
                (spend.lastrowid, lot.lastrowid),
            )
            db.execute(
                """
                INSERT INTO reward_stock_reservations (
                    reservation_id, redemption_id, reward_id,
                    quantity, status, created_at
                )
                VALUES (
                    '10', 10, 'reward-1', 1, 'reserved',
                    '2026-09-17T00:00:00+08:00'
                )
                """
            )
            db.commit()
            with patch(
                "app.handcraft_inheritance.admin_actions."
                "emit_fulfillment_cancelled"
            ) as emit:
                result = apply_fulfillment_admin_action(
                    {
                        "fulfillment_id": 20,
                        "action": "cancel_pending",
                        "admin_role": "super_admin",
                    }
                )
            row = get_db().execute(
                """
                SELECT status, canceled_at
                FROM fulfillments
                WHERE id = 20
                """
            ).fetchone()

        self.assertEqual(result["status"], "canceled")
        self.assertEqual(row["status"], "canceled")
        self.assertIsNotNone(row["canceled_at"])
        emit.assert_called_once_with(
            event_id="handcraft-fulfillment:20:cancel_pending",
            student_id=1,
            fulfillment_id="20",
            prize_name="广绣书签",
            restored_points=30,
        )

    def test_concurrent_issue_and_cancel_allow_only_one_transition(self):
        with self.app.app_context():
            self._insert_fulfillment()
        barrier = threading.Barrier(2)

        def perform(action: str):
            with self.app.app_context():
                barrier.wait(timeout=5)
                try:
                    result = apply_fulfillment_admin_action(
                        {
                            "fulfillment_id": 20,
                            "action": action,
                            "admin_role": "admin",
                        }
                    )
                    return "ok", result["status"]
                except AgriValidationError as error:
                    return "error", str(error)

        with patch(
            "app.handcraft_inheritance.admin_actions."
            "emit_fulfillment_issued"
        ) as issued_emit, patch(
            "app.handcraft_inheritance.admin_actions."
            "emit_fulfillment_cancelled"
        ) as cancelled_emit:
            with ThreadPoolExecutor(max_workers=2) as executor:
                results = list(
                    executor.map(
                        perform,
                        ("issue", "cancel_pending"),
                    )
                )

        with self.app.app_context():
            fulfillment = get_db().execute(
                """
                SELECT status
                FROM fulfillments
                WHERE id = 20
                """
            ).fetchone()
            redemption = get_db().execute(
                """
                SELECT status
                FROM redemptions
                WHERE id = 10
                """
            ).fetchone()

        self.assertEqual(sum(result[0] == "ok" for result in results), 1)
        self.assertEqual(sum(result[0] == "error" for result in results), 1)
        self.assertEqual(fulfillment["status"], redemption["status"])
        self.assertIn(fulfillment["status"], {"issued", "canceled"})
        self.assertEqual(
            issued_emit.call_count + cancelled_emit.call_count,
            1,
        )

    def test_manual_verify_only_accepts_issued_without_notification(self):
        with self.app.app_context():
            self._insert_fulfillment()
            with self.assertRaises(AgriValidationError):
                apply_fulfillment_admin_action(
                    {
                        "fulfillment_id": 20,
                        "action": "manual_verify",
                        "admin_role": "admin",
                    }
                )
            get_db().execute(
                """
                UPDATE fulfillmentS
                SET status = 'issued',
                    issued_at = '2026-09-17T01:00:00+08:00'
                WHERE id = 20
                """
            )
            get_db().commit()
            with patch(
                "app.handcraft_inheritance.admin_actions."
                "emit_fulfillment_issued"
            ) as issued_emit, patch(
                "app.handcraft_inheritance.admin_actions."
                "emit_fulfillment_cancelled"
            ) as cancelled_emit:
                result = apply_fulfillment_admin_action(
                    {
                        "fulfillment_id": 20,
                        "action": "manual_verify",
                        "admin_role": "admin",
                    }
                )
            row = get_db().execute(
                """
                SELECT status, verified_at
                FROM fulfillments
                WHERE id = 20
                """
            ).fetchone()

        self.assertEqual(result["status"], "verified")
        self.assertEqual(row["status"], "verified")
        self.assertIsNotNone(row["verified_at"])
        issued_emit.assert_not_called()
        cancelled_emit.assert_not_called()

    def test_fulfillment_invalid_role_and_transition_are_atomic(self):
        with self.app.app_context():
            self._insert_fulfillment(status="issued")
            for action in (
                {
                    "fulfillment_id": 20,
                    "action": "manual_verify",
                    "admin_role": "student",
                },
                {
                    "fulfillment_id": 20,
                    "action": "cancel_pending",
                    "admin_role": "admin",
                },
                {
                    "fulfillment_id": 20,
                    "action": "issue",
                    "admin_role": "admin",
                },
            ):
                with self.subTest(action=action["action"]):
                    with self.assertRaises(AgriValidationError):
                        apply_fulfillment_admin_action(action)
                    row = get_db().execute(
                        """
                        SELECT status, verified_at, canceled_at
                        FROM fulfillments
                        WHERE id = 20
                        """
                    ).fetchone()
                    self.assertEqual(row["status"], "issued")
                    self.assertIsNone(row["verified_at"])
                    self.assertIsNone(row["canceled_at"])

            with self.assertRaises(AgriNotFoundError):
                apply_fulfillment_admin_action(
                    {
                        "fulfillment_id": 999,
                        "action": "issue",
                        "admin_role": "admin",
                    }
                )

    def test_action_providers_are_replaceable(self):
        video_provider = ReplacementVideoReviewProvider()
        fulfillment_provider = ReplacementFulfillmentAdminProvider()
        set_video_review_action_provider(self.app, video_provider)
        set_fulfillment_action_provider(self.app, fulfillment_provider)

        with self.app.app_context():
            self.assertIs(
                get_video_review_action_provider(),
                video_provider,
            )
            self.assertIs(
                get_fulfillment_action_provider(),
                fulfillment_provider,
            )
            video_result = apply_video_review({"video_id": "external"})
            fulfillment_result = apply_fulfillment_admin_action(
                {"fulfillment_id": 99}
            )

        self.assertEqual(video_result["status"], "replacement-approved")
        self.assertEqual(
            fulfillment_result["status"],
            "replacement-issued",
        )
        self.assertEqual(video_provider.actions, [{"video_id": "external"}])
        self.assertEqual(
            fulfillment_provider.actions,
            [{"fulfillment_id": 99}],
        )

    def test_notification_failure_does_not_rollback_business_state(self):
        with self.app.app_context():
            self._insert_video()
            with patch(
                "app.handcraft_inheritance.admin_actions.emit_review_result",
                side_effect=RuntimeError("notification offline"),
            ):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "notification offline",
                ):
                    apply_video_review(
                        {
                            "video_id": "review-video",
                            "action": "approve",
                            "reviewer_role": "admin",
                            "submitter_id": 1,
                            "version": 1,
                        }
                    )
            video = get_db().execute(
                """
                SELECT review_status
                FROM heritage_videos
                WHERE video_id = 'review-video'
                """
            ).fetchone()
            self.assertEqual(video["review_status"], "approved")

            self._insert_fulfillment(status="pending")
            with patch(
                "app.handcraft_inheritance.admin_actions."
                "emit_fulfillment_issued",
                side_effect=RuntimeError("notification offline"),
            ):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "notification offline",
                ):
                    apply_fulfillment_admin_action(
                        {
                            "fulfillment_id": 20,
                            "action": "issue",
                            "admin_role": "admin",
                        }
                    )
            fulfillment = get_db().execute(
                """
                SELECT status
                FROM fulfillments
                WHERE id = 20
                """
            ).fetchone()

        self.assertEqual(fulfillment["status"], "issued")


if __name__ == "__main__":
    unittest.main()
