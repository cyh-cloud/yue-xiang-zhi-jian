import copy
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from werkzeug.security import generate_password_hash

from app import create_app
from app.agri_skills.ai_client import set_ai_client
from app.agri_skills.errors import AgriValidationError, AiUnavailableError
from app.agri_skills.providers import set_course_provider
from app.db import get_db
from app.handcraft_inheritance import (
    record_training_points,
    redeem_reward,
    retry_pending_fulfillment_notifications,
    set_craft_preset_provider,
    set_points_policy_provider,
    set_reward_catalog_provider,
)
from app.handcraft_inheritance.active_learning import heartbeat
from app.handcraft_inheritance.ar_guidance import generate_ar_guidance
from app.handcraft_inheritance.course_learning import (
    list_handcraft_learning_outcomes,
    submit_handcraft_course_quiz,
    update_handcraft_course_progress,
)
from app.handcraft_inheritance.crafts import complete_craft_step
from app.handcraft_inheritance.fulfillment import (
    cancel_pending_fulfillment,
)
from app.handcraft_inheritance.points import _platform_now
from app.handcraft_inheritance.presets import (
    PLACEHOLDER_POINTS_POLICY,
    PLACEHOLDER_REWARDS,
    PlaceholderRewardCatalogProvider,
)
from app.handcraft_inheritance.providers import EmptyCraftPresetProvider
from app.handcraft_inheritance.rewards import REDEMPTION_CONFLICT_MESSAGE


AR_GUIDANCE = {
    "craft_key": "guangxiu",
    "tool_preparation": ["绣线", "绣针"],
    "operating_points": ["先定位图案"],
    "common_errors": ["针脚不匀"],
    "steps": [
        {
            "step_no": 1,
            "title": "起针",
            "instruction": "从背面起针并固定绣线。",
        }
    ],
}

QUIZ_GRADE = {
    "score": 88,
    "questions": [
        {
            "id": "q1",
            "correct": True,
            "explanation": "选项 A 正确。",
        }
    ],
}


class StaticPolicyProvider:
    def __init__(self, policy):
        self.policy = copy.deepcopy(policy)

    def get_policy(self):
        return copy.deepcopy(self.policy)


class StaticCourseProvider:
    def __init__(self, courses=None, quiz=None):
        self.courses = copy.deepcopy(courses or [])
        self.quiz = copy.deepcopy(quiz)

    def list_published_courses(self, student_id, direction):
        return [
            copy.deepcopy(course)
            for course in self.courses
            if course["direction"] == direction
            and course["status"] == "published"
        ]

    def get_course(self, course_id):
        return next(
            (
                copy.deepcopy(course)
                for course in self.courses
                if course["id"] == course_id
            ),
            None,
        )

    def get_quiz(self, course_id):
        if course_id != 501:
            return None
        return copy.deepcopy(self.quiz)


class EmptyCourseProvider:
    def list_published_courses(self, student_id, direction):
        return []

    def get_course(self, course_id):
        return None

    def get_quiz(self, course_id):
        return None


class FakeAiClient:
    def __init__(self, responses=None):
        self.responses = list(responses or [])
        self.calls = []

    def complete_json(self, messages, *, call_point):
        self.calls.append(
            {
                "call_point": call_point,
                "messages": copy.deepcopy(messages),
            }
        )
        if not self.responses:
            raise AssertionError("Unexpected AI call")
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return copy.deepcopy(response)

    def stream_chat(self, messages, *, call_point):
        raise AssertionError("stream_chat is not used by this suite")

    def transcribe(self, audio, filename, *, call_point):
        raise AssertionError("transcribe is not used by this suite")


class HandcraftIntegrationAcceptance(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(Path(self.temp_dir.name) / "test.db"),
                "SECRET_KEY": "task-20-integration-secret",
                "SESSION_HOURS": 24,
                "SESSION_COOKIE_SECURE": False,
                "POINTS_EXPIRY_TOKEN": "task-20-expiry-token",
                "POINTS_EXPIRY_BATCH_SIZE": 100,
            }
        )
        with self.app.app_context():
            db = get_db()
            self.student_id = self._insert_user(db, "student01", "student")
            self.other_student_id = self._insert_user(
                db,
                "student02",
                "student",
            )
            self.teacher_id = self._insert_user(db, "teacher01", "teacher")
            db.execute(
                """
                INSERT INTO student_profiles (user_id, contact, updated_at)
                VALUES (?, '13800000001', '2026-09-18T00:00:00+08:00')
                """,
                (self.student_id,),
            )
            db.execute(
                """
                INSERT INTO interest_tags (
                    id, group_key, name, sort_order, is_active
                )
                VALUES (101, 'skill', '手工技艺', 101, 1)
                """
            )
            db.execute(
                """
                INSERT INTO courses (
                    id, title, direction, status, duration_seconds,
                    published_at, summary, teacher_name, created_at, updated_at
                )
                VALUES (
                    501, '广绣基础', 'handcraft', 'published', 100,
                    '2026-09-01T00:00:00+00:00', '广绣针法与配色基础',
                    '梁老师', '2026-09-01T00:00:00+00:00',
                    '2026-09-01T00:00:00+00:00'
                )
                """
            )
            db.commit()

        self.policy = copy.deepcopy(PLACEHOLDER_POINTS_POLICY)
        self.policy.update(
            {
                "seconds_per_point": 600,
                "training_weights": {"default": 1000},
                "daily_limit": 10000,
            }
        )
        set_points_policy_provider(
            self.app,
            StaticPolicyProvider(self.policy),
        )
        set_course_provider(
            self.app,
            StaticCourseProvider(
                courses=[
                    {
                        "id": 501,
                        "title": "广绣基础",
                        "direction": "handcraft",
                        "status": "published",
                        "summary": "广绣针法与配色基础",
                        "teacher_name": "梁老师",
                        "published_at": "2026-09-01T00:00:00+00:00",
                        "duration_seconds": 100,
                        "tag_ids": [101],
                    }
                ],
                quiz={
                    "enabled": True,
                    "scoring_rule": "按题判分",
                    "questions": [
                        {
                            "id": "q1",
                            "type": "single_choice",
                            "prompt": "广绣基础题",
                            "options": ["A", "B"],
                            "answer": "A",
                        }
                    ],
                },
            ),
        )
        self.ai = FakeAiClient()
        set_ai_client(self.app, self.ai)
        self.student_client = self._login("student01")
        self.other_student_client = self._login("student02")
        self.teacher_client = self._login("teacher01")

    def tearDown(self):
        self.temp_dir.cleanup()

    @staticmethod
    def _insert_user(db, username, role):
        cursor = db.execute(
            """
            INSERT INTO users (
                username, password_hash, name, role, is_enabled,
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?, 1, ?, ?)
            """,
            (
                username,
                generate_password_hash("password8"),
                username,
                role,
                "2026-09-18T00:00:00+08:00",
                "2026-09-18T00:00:00+08:00",
            ),
        )
        return int(cursor.lastrowid)

    def _login(self, username):
        client = self.app.test_client()
        response = client.post(
            "/api/auth/login",
            json={"username": username, "password": "password8"},
        )
        self.assertEqual(response.status_code, 200)
        return client

    def _fund_student(
        self,
        user_id=None,
        source_id="integration-funding",
        occurred_at=None,
    ):
        user_id = user_id or self.student_id
        occurred_at = occurred_at or _platform_now().isoformat(
            timespec="seconds"
        )
        with self.app.app_context():
            result = record_training_points(
                user_id,
                "ecommerce",
                "live_script",
                source_id,
                occurred_at,
            )
            self.assertEqual(result["status"], "processed")

    def _redeem(self, user_id=1, request_id="integration-redemption"):
        with self.app.app_context(), patch(
            "app.handcraft_inheritance.outbox.emit_redemption_succeeded"
        ):
            return redeem_reward(
                user_id,
                PLACEHOLDER_REWARDS[0]["reward_id"],
                request_id,
            )

    def _fulfillment_id(self, redemption_id):
        with self.app.app_context():
            return int(
                get_db().execute(
                    """
                    SELECT id
                    FROM fulfillments
                    WHERE redemption_id = ?
                    """,
                    (redemption_id,),
                ).fetchone()["id"]
            )

    def _fulfillment_snapshot(self, fulfillment_id, user_id=1):
        with self.app.app_context():
            db = get_db()
            fulfillment = dict(
                db.execute(
                    """
                    SELECT status, issued_at, verified_at, canceled_at
                    FROM fulfillments
                    WHERE id = ?
                    """,
                    (fulfillment_id,),
                ).fetchone()
            )
            redemption = dict(
                db.execute(
                    """
                    SELECT r.status, r.canceled_at
                    FROM redemptions r
                    JOIN fulfillments f ON f.redemption_id = r.id
                    WHERE f.id = ?
                    """,
                    (fulfillment_id,),
                ).fetchone()
            )
            reservation = dict(
                db.execute(
                    """
                    SELECT rs.status, rs.released_at
                    FROM reward_stock_reservations rs
                    JOIN fulfillments f
                      ON f.redemption_id = rs.redemption_id
                    WHERE f.id = ?
                    """,
                    (fulfillment_id,),
                ).fetchone()
            )
            counts = dict(
                db.execute(
                    """
                    SELECT
                        SUM(transaction_type = 'spend') AS spend_count,
                        SUM(transaction_type = 'refund') AS refund_count
                    FROM points_transactions
                    WHERE user_id = ?
                    """,
                    (user_id,),
                ).fetchone()
            )
            notification_count = int(
                db.execute(
                    """
                    SELECT COUNT(*) AS count
                    FROM system_notifications
                    WHERE source_type = 'fulfillment'
                      AND source_id = ?
                    """,
                    (str(fulfillment_id),),
                ).fetchone()["count"]
            )
            balance = int(
                db.execute(
                    """
                    SELECT balance
                    FROM points_accounts
                    WHERE user_id = ?
                    """,
                    (user_id,),
                ).fetchone()["balance"]
            )
            return {
                "fulfillment": fulfillment,
                "redemption": redemption,
                "reservation": reservation,
                "balance": balance,
                "spend_count": int(counts["spend_count"] or 0),
                "refund_count": int(counts["refund_count"] or 0),
                "notification_count": notification_count,
            }

    def test_session_expiry_disabled_account_and_active_student_use_01_rules(
        self,
    ):
        active = self.student_client.get(
            "/api/handcraft-inheritance/points"
        )
        self.assertEqual(active.status_code, 200)

        with self.app.app_context():
            get_db().execute(
                """
                UPDATE sessions
                SET expires_at = '2000-01-01T00:00:00+00:00'
                WHERE user_id = ?
                """,
                (self.student_id,),
            )
            get_db().commit()

        expired = self.student_client.get(
            (
                "/api/handcraft-inheritance/crafts/guangxiu/progress"
                "?next=/student/handcraft-inheritance/crafts/guangxiu"
            )
        )

        self.assertEqual(expired.status_code, 401)
        self.assertEqual(
            expired.get_json(),
            {
                "success": False,
                "message": "未登录或会话已过期",
                "redirect": (
                    "/login?redirect=%2Fstudent%2Fhandcraft-inheritance"
                    "%2Fcrafts%2Fguangxiu"
                ),
            },
        )

        self.student_client = self._login("student01")
        with self.app.app_context():
            get_db().execute(
                "UPDATE users SET is_enabled = 0 WHERE id = ?",
                (self.student_id,),
            )
            get_db().commit()

        disabled = self.student_client.get(
            "/api/handcraft-inheritance/points"
        )
        self.assertEqual(disabled.status_code, 403)
        self.assertEqual(
            disabled.get_json(),
            {
                "success": False,
                "message": "账户已被禁用，请联系管理员",
            },
        )
        with self.app.app_context():
            session_count = get_db().execute(
                "SELECT COUNT(*) AS count FROM sessions WHERE user_id = ?",
                (self.student_id,),
            ).fetchone()["count"]
        self.assertEqual(session_count, 0)

    def test_cross_student_progress_and_course_state_are_owner_scoped(self):
        completed = self.student_client.post(
            (
                "/api/handcraft-inheritance/crafts/guangxiu/"
                "steps/1/complete"
            ),
            json={
                "user_id": self.other_student_id,
                "active_seconds": 600,
                "event_id": "cross-student-step",
            },
        )
        own_progress = self.student_client.get(
            "/api/handcraft-inheritance/crafts/guangxiu/progress"
        )
        other_progress = self.other_student_client.get(
            "/api/handcraft-inheritance/crafts/guangxiu/progress"
        )
        own_course = self.student_client.put(
            "/api/handcraft-inheritance/courses/501/progress",
            json={
                "user_id": self.other_student_id,
                "position_seconds": 80,
                "watched_delta_seconds": 80,
            },
        )
        other_course = self.other_student_client.get(
            "/api/handcraft-inheritance/courses/501/progress"
        )

        self.assertEqual(completed.status_code, 200)
        self.assertEqual(
            completed.get_json()["progress"]["user_id"],
            self.student_id,
        )
        self.assertEqual(
            own_progress.get_json()["progress"]["completed_steps"],
            [1],
        )
        self.assertEqual(
            other_progress.get_json()["progress"]["completed_steps"],
            [],
        )
        self.assertEqual(own_course.status_code, 200)
        self.assertEqual(
            own_course.get_json()["progress"]["user_id"],
            self.student_id,
        )
        self.assertEqual(
            own_course.get_json()["progress"]["progress_percent"],
            80,
        )
        self.assertEqual(
            other_course.get_json()["progress"]["watched_seconds"],
            0,
        )

    def test_points_redemptions_and_fulfillments_do_not_cross_students(self):
        self._fund_student()
        redeemed = self.student_client.post(
            "/api/handcraft-inheritance/redemptions",
            json={
                "user_id": self.other_student_id,
                "reward_id": PLACEHOLDER_REWARDS[0]["reward_id"],
                "request_id": "owner-scope-redemption",
            },
        )
        redemption_id = redeemed.get_json()["redemption"]["id"]

        own_points = self.student_client.get(
            "/api/handcraft-inheritance/points"
        )
        other_points = self.other_student_client.get(
            "/api/handcraft-inheritance/points"
        )
        own_ledger = self.student_client.get(
            "/api/handcraft-inheritance/points/ledger"
        )
        other_ledger = self.other_student_client.get(
            "/api/handcraft-inheritance/points/ledger"
        )
        own_history = self.student_client.get(
            "/api/handcraft-inheritance/redemptions"
        )
        other_history = self.other_student_client.get(
            "/api/handcraft-inheritance/redemptions"
        )
        foreign_cancel = self.other_student_client.post(
            (
                "/api/handcraft-inheritance/redemptions/"
                f"{redemption_id}/cancel"
            )
        )
        foreign_verify = self.other_student_client.post(
            (
                "/api/handcraft-inheritance/redemptions/"
                f"{redemption_id}/verify"
            )
        )

        self.assertEqual(redeemed.status_code, 201)
        self.assertEqual(
            redeemed.get_json()["redemption"]["user_id"],
            self.student_id,
        )
        self.assertEqual(own_points.get_json()["account"]["balance"], 970)
        self.assertEqual(other_points.get_json()["account"]["balance"], 0)
        self.assertTrue(own_ledger.get_json()["ledger"])
        self.assertEqual(other_ledger.get_json()["ledger"], [])
        self.assertEqual(
            own_history.get_json()["redemptions"][0]["id"],
            redemption_id,
        )
        self.assertEqual(
            own_history.get_json()["fulfillments"][0]["redemption"]["id"],
            redemption_id,
        )
        self.assertEqual(other_history.get_json()["redemptions"], [])
        self.assertEqual(other_history.get_json()["fulfillments"], [])
        self.assertEqual(foreign_cancel.status_code, 404)
        self.assertEqual(foreign_verify.status_code, 404)

    def test_delivery_failure_does_not_rollback_cancel_and_retry_is_once(
        self,
    ):
        self._fund_student()
        redemption = self._redeem(request_id="notification-retry")
        fulfillment_id = self._fulfillment_id(redemption["id"])

        with self.app.app_context(), patch(
            "app.handcraft_inheritance.fulfillment."
            "emit_fulfillment_cancelled",
            side_effect=RuntimeError("notification delivery offline"),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "notification delivery offline",
            ):
                cancel_pending_fulfillment(
                    fulfillment_id,
                    role="student",
                    actor_user_id=self.student_id,
                )

        failed_delivery = self._fulfillment_snapshot(fulfillment_id)
        self.assertEqual(failed_delivery["fulfillment"]["status"], "canceled")
        self.assertEqual(failed_delivery["redemption"]["status"], "canceled")
        self.assertEqual(failed_delivery["reservation"]["status"], "released")
        self.assertEqual(failed_delivery["balance"], 1000)
        self.assertEqual(failed_delivery["spend_count"], 1)
        self.assertEqual(failed_delivery["refund_count"], 1)
        self.assertEqual(failed_delivery["notification_count"], 0)

        with self.app.app_context():
            first_retry = retry_pending_fulfillment_notifications(limit=100)
            second_retry = retry_pending_fulfillment_notifications(limit=100)

        recovered = self._fulfillment_snapshot(fulfillment_id)
        self.assertEqual(first_retry, {"attempted": 1, "sent": 1, "failed": 0})
        self.assertEqual(second_retry, {"attempted": 0, "sent": 0, "failed": 0})
        self.assertEqual(recovered["balance"], 1000)
        self.assertEqual(recovered["spend_count"], 1)
        self.assertEqual(recovered["refund_count"], 1)
        self.assertEqual(recovered["notification_count"], 1)

    def test_cancellation_refund_or_stock_failure_rolls_back_atomically(
        self,
    ):
        self._fund_student()

        refund_redemption = self._redeem(request_id="refund-failure")
        refund_fulfillment = self._fulfillment_id(refund_redemption["id"])
        with self.app.app_context(), patch(
            "app.handcraft_inheritance.fulfillment."
            "refund_points_in_transaction",
            side_effect=AgriValidationError("refund unavailable"),
        ):
            with self.assertRaisesRegex(
                AgriValidationError,
                "refund unavailable",
            ):
                cancel_pending_fulfillment(
                    refund_fulfillment,
                    role="admin",
                )

        refund_failed = self._fulfillment_snapshot(refund_fulfillment)
        self.assertEqual(refund_failed["fulfillment"]["status"], "pending")
        self.assertEqual(refund_failed["redemption"]["status"], "pending")
        self.assertEqual(refund_failed["reservation"]["status"], "reserved")
        self.assertEqual(refund_failed["balance"], 970)
        self.assertEqual(refund_failed["refund_count"], 0)

        stock_redemption = self._redeem(request_id="stock-failure")
        stock_fulfillment = self._fulfillment_id(stock_redemption["id"])
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
                    stock_fulfillment,
                    role="admin",
                )

        stock_failed = self._fulfillment_snapshot(stock_fulfillment)
        self.assertEqual(stock_failed["fulfillment"]["status"], "pending")
        self.assertEqual(stock_failed["redemption"]["status"], "pending")
        self.assertEqual(stock_failed["reservation"]["status"], "reserved")
        self.assertEqual(stock_failed["balance"], 940)
        self.assertEqual(stock_failed["refund_count"], 0)

    def test_fr_093_outcomes_cover_steps_ar_and_courses_after_replacement(
        self,
    ):
        self.ai.responses = [
            AR_GUIDANCE,
            AR_GUIDANCE,
            QUIZ_GRADE,
        ]
        with self.app.app_context():
            ar_segment = heartbeat(
                self.student_id,
                "ar",
                "guangxiu",
                heartbeat_seq=0,
                now_epoch=1000,
            )
            complete_craft_step(
                self.student_id,
                "guangxiu",
                1,
                600,
                "outcome-step",
            )
            generate_ar_guidance(
                self.student_id,
                "guangxiu",
                "绣制花瓣",
                str(ar_segment["segment_id"]),
            )
            generate_ar_guidance(
                self.student_id,
                "guangxiu",
                "绣制花瓣",
                str(ar_segment["segment_id"]),
            )
            update_handcraft_course_progress(
                self.student_id,
                501,
                80,
                80,
            )
            submit_handcraft_course_quiz(
                self.student_id,
                501,
                {"q1": "A"},
            )
            outcomes = list_handcraft_learning_outcomes(self.student_id)

        required_fields = {
            "outcome_type",
            "source_id",
            "created_at",
            "source_available",
            "summary",
            "score",
            "is_formal",
            "archive_written",
        }
        self.assertEqual(
            {outcome["outcome_type"] for outcome in outcomes},
            {
                "craft_step",
                "ar_usage",
                "course_view",
                "course_completion",
                "course_quiz",
            },
        )
        self.assertEqual(len(outcomes), 5)
        self.assertEqual(
            len(
                [
                    outcome
                    for outcome in outcomes
                    if outcome["outcome_type"] == "ar_usage"
                ]
            ),
            1,
        )
        for outcome in outcomes:
            with self.subTest(outcome=outcome):
                self.assertEqual(set(outcome), required_fields)
                self.assertIsInstance(outcome["source_id"], int)
                self.assertTrue(outcome["source_available"])
                self.assertIsInstance(outcome["created_at"], str)
                self.assertTrue(outcome["summary"].strip())
                self.assertFalse(outcome["archive_written"])

        stable_source_ids = {
            (outcome["outcome_type"], outcome["source_id"])
            for outcome in outcomes
        }
        set_craft_preset_provider(self.app, EmptyCraftPresetProvider())
        set_course_provider(self.app, EmptyCourseProvider())
        with self.app.app_context():
            historical = list_handcraft_learning_outcomes(self.student_id)

        self.assertEqual(len(historical), 5)
        self.assertEqual(
            {
                (outcome["outcome_type"], outcome["source_id"])
                for outcome in historical
            },
            stable_source_ids,
        )
        self.assertTrue(
            all(not outcome["source_available"] for outcome in historical)
        )
        self.assertTrue(
            all(not outcome["archive_written"] for outcome in historical)
        )

    def test_course_outcome_backfill_is_durable_across_contexts(self):
        with self.app.app_context():
            db = get_db()
            db.execute(
                """
                INSERT INTO agri_course_progress (
                    user_id, course_id, duration_seconds,
                    furthest_position_seconds, resume_position_seconds,
                    progress_percent, watched_seconds, completed_at,
                    last_viewed_at, updated_at
                )
                VALUES (
                    ?, 501, 100, 80, 80, 80, 80,
                    '2026-09-18T10:00:00+08:00',
                    '2026-09-18T10:00:00+08:00',
                    '2026-09-18T10:00:00+08:00'
                )
                """,
                (self.student_id,),
            )
            db.execute(
                """
                INSERT INTO agri_course_quiz_attempts (
                    user_id, course_id, answers_json, result_json,
                    score, is_formal, created_at
                )
                VALUES (
                    ?, 501, '{"q1":"A"}',
                    '{"score":88,"questions":[]}', 88, 1,
                    '2026-09-18T10:05:00+08:00'
                )
                """,
                (self.student_id,),
            )
            db.commit()

        with self.app.app_context():
            outcomes = list_handcraft_learning_outcomes(self.student_id)
            self.assertEqual(
                {outcome["outcome_type"] for outcome in outcomes},
                {"course_view", "course_completion", "course_quiz"},
            )
            self.assertTrue(
                all(not outcome["archive_written"] for outcome in outcomes)
            )

        with self.app.app_context():
            rows = get_db().execute(
                """
                SELECT outcome_type, source_id, source_key, archive_written
                FROM handcraft_learning_outcomes
                WHERE user_id = ?
                ORDER BY outcome_type, id
                """,
                (self.student_id,),
            ).fetchall()

        self.assertEqual(len(rows), 3)
        self.assertEqual(
            {row["outcome_type"] for row in rows},
            {"course_view", "course_completion", "course_quiz"},
        )
        self.assertTrue(all(row["source_id"] is not None for row in rows))
        self.assertTrue(all(row["archive_written"] == 0 for row in rows))

    def test_ar_failure_matrix_is_exact_and_never_degraded(self):
        with self.app.app_context():
            complete_craft_step(
                self.student_id,
                "guangxiu",
                1,
                600,
                "manual-progress-before-ar",
            )

        invalid_responses = (
            AiUnavailableError("provider timeout"),
            {},
            {
                "craft_key": "guangxiu",
                "tool_preparation": ["绣线"],
                "operating_points": ["定位"],
                "steps": [{"step_no": 1, "title": "起针"}],
            },
            {
                "craft_key": "guangxiu",
                "tool_preparation": [],
                "operating_points": [""],
                "common_errors": ["针脚不匀"],
                "steps": [],
            },
            [
                "not",
                "an",
                "object",
            ],
        )

        for index, response in enumerate(invalid_responses):
            with self.subTest(index=index, response=response):
                set_ai_client(self.app, FakeAiClient([response]))
                failed = self.student_client.post(
                    "/api/handcraft-inheritance/ar-guidance",
                    json={
                        "craft_key": "guangxiu",
                        "project_label": "绣制花瓣",
                        "active_seconds": 600,
                        "event_id": f"invalid-ar-{index}",
                    },
                )
                progress = self.student_client.get(
                    "/api/handcraft-inheritance/crafts/guangxiu/progress"
                )
                self.assertEqual(failed.status_code, 503)
                self.assertEqual(
                    failed.get_json(),
                    {
                        "success": False,
                        "message": "AI 服务暂时不可用",
                    },
                )
                self.assertEqual(
                    progress.get_json()["progress"]["completed_steps"],
                    [1],
                )

        with self.app.app_context():
            outcome_count = get_db().execute(
                """
                SELECT COUNT(*) AS count
                FROM handcraft_learning_outcomes
                WHERE user_id = ? AND outcome_type = 'ar_usage'
                """,
                (self.student_id,),
            ).fetchone()["count"]
        self.assertEqual(outcome_count, 0)

    def test_quiz_ai_failure_preserves_progress_and_previous_formal_score(
        self,
    ):
        with self.app.app_context():
            update_handcraft_course_progress(
                self.student_id,
                501,
                80,
                80,
            )

        set_ai_client(self.app, FakeAiClient([QUIZ_GRADE]))
        first = self.student_client.post(
            "/api/handcraft-inheritance/courses/501/quiz",
            json={"answers": {"q1": "A"}},
        )
        set_ai_client(
            self.app,
            FakeAiClient([AiUnavailableError("provider timeout")]),
        )
        failed = self.student_client.post(
            "/api/handcraft-inheritance/courses/501/quiz",
            json={"answers": {"q1": "B"}},
        )
        progress = self.student_client.get(
            "/api/handcraft-inheritance/courses/501/progress"
        )
        history = self.student_client.get(
            "/api/handcraft-inheritance/courses/501/quiz/attempts"
        )

        self.assertEqual(first.status_code, 201)
        self.assertEqual(failed.status_code, 503)
        self.assertEqual(
            failed.get_json(),
            {
                "success": False,
                "message": "AI 服务暂时不可用",
            },
        )
        self.assertEqual(
            progress.get_json()["progress"]["progress_percent"],
            80,
        )
        attempts = history.get_json()["attempts"]
        self.assertEqual(len(attempts), 1)
        self.assertEqual(attempts[0]["score"], 88)
        self.assertTrue(attempts[0]["is_formal"])

    def test_concurrent_last_stock_redemption_has_no_partial_or_negative_state(
        self,
    ):
        self._fund_student(
            user_id=self.student_id,
            source_id="concurrency-funding-1",
        )
        self._fund_student(
            user_id=self.other_student_id,
            source_id="concurrency-funding-2",
        )
        one_stock_rewards = (
            {
                **copy.deepcopy(PLACEHOLDER_REWARDS[0]),
                "stock": 1,
            },
            *copy.deepcopy(PLACEHOLDER_REWARDS[1:]),
        )
        barrier = threading.Barrier(2)

        def redeem(user_id, request_id):
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
            provider = PlaceholderRewardCatalogProvider()
            set_reward_catalog_provider(self.app, provider)
            with ThreadPoolExecutor(max_workers=2) as executor:
                results = list(
                    executor.map(
                        lambda item: redeem(*item),
                        (
                            (self.student_id, "last-stock-1"),
                            (self.other_student_id, "last-stock-2"),
                        ),
                    )
                )
            with self.app.app_context():
                stock = provider.list_rewards()[0]["stock"]

        with self.app.app_context():
            db = get_db()
            redemption_count = db.execute(
                "SELECT COUNT(*) AS count FROM redemptions"
            ).fetchone()["count"]
            fulfillment_count = db.execute(
                "SELECT COUNT(*) AS count FROM fulfillments"
            ).fetchone()["count"]
            reservation_count = db.execute(
                """
                SELECT COUNT(*) AS count
                FROM reward_stock_reservations
                WHERE status = 'reserved'
                """
            ).fetchone()["count"]
            spend_count = db.execute(
                """
                SELECT COUNT(*) AS count
                FROM points_transactions
                WHERE transaction_type = 'spend'
                """
            ).fetchone()["count"]
            balances = [
                int(row["balance"])
                for row in db.execute(
                    "SELECT balance FROM points_accounts ORDER BY user_id"
                ).fetchall()
            ]
        self.assertEqual(sum(result[0] == "ok" for result in results), 1)
        self.assertEqual(sum(result[0] == "error" for result in results), 1)
        failure = next(result for result in results if result[0] == "error")
        self.assertEqual(failure[1], REDEMPTION_CONFLICT_MESSAGE)
        self.assertEqual(redemption_count, 1)
        self.assertEqual(fulfillment_count, 1)
        self.assertEqual(reservation_count, 1)
        self.assertEqual(spend_count, 1)
        self.assertEqual(sorted(balances), [970, 1000])
        self.assertEqual(stock, 0)

    def test_natural_year_expiry_is_idempotent_and_notifies_once(self):
        natural_year_policy = copy.deepcopy(self.policy)
        natural_year_policy.update(
            {
                "version": "integration-natural-year",
                "expiry_mode": "natural_year",
            }
        )
        set_points_policy_provider(
            self.app,
            StaticPolicyProvider(natural_year_policy),
        )
        self._fund_student(
            source_id="expiring-award",
            occurred_at="2025-06-01T09:00:00+08:00",
        )

        first = self.student_client.get(
            "/api/handcraft-inheritance/points"
        )
        second = self.student_client.get(
            "/api/handcraft-inheritance/points"
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.get_json()["account"]["balance"], 0)
        self.assertEqual(second.get_json()["account"]["balance"], 0)
        with self.app.app_context():
            db = get_db()
            expire_count = db.execute(
                """
                SELECT COUNT(*) AS count
                FROM points_transactions
                WHERE transaction_type = 'expire'
                """
            ).fetchone()["count"]
            notification_count = db.execute(
                """
                SELECT COUNT(*) AS count
                FROM system_notifications
                WHERE event_type = 'points_expired'
                """
            ).fetchone()["count"]
            balance = db.execute(
                """
                SELECT balance
                FROM points_accounts
                WHERE user_id = ?
                """,
                (self.student_id,),
            ).fetchone()["balance"]
        self.assertEqual(expire_count, 1)
        self.assertEqual(notification_count, 1)
        self.assertEqual(balance, 0)


if __name__ == "__main__":
    unittest.main()
