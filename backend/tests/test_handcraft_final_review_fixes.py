import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from werkzeug.security import generate_password_hash

from app import create_app
from app.agri_skills.ai_client import set_ai_client
from app.agri_skills.providers import set_course_provider
from app.db import get_db
from app.handcraft_inheritance import (
    set_points_policy_provider,
)
from app.handcraft_inheritance.admin_actions import apply_video_review
from app.handcraft_inheritance.presets import PLACEHOLDER_POINTS_POLICY
from app.handcraft_inheritance.providers import set_teaching_video_provider
from app.handcraft_inheritance.rewards import redeem_reward


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


class StaticPolicyProvider:
    def __init__(self, policy):
        self.policy = copy.deepcopy(policy)

    def get_policy(self):
        return copy.deepcopy(self.policy)


class StaticCourseProvider:
    def __init__(self):
        self.course = {
            "id": 501,
            "title": "广绣基础",
            "direction": "handcraft",
            "status": "published",
            "summary": "广绣针法与配色基础",
            "teacher_name": "梁老师",
            "published_at": "2026-09-01T00:00:00+00:00",
            "duration_seconds": 100,
            "media_url": "https://media.example.test/guangxiu.mp4",
            "tag_ids": [],
        }
        self.quiz = {
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
        }

    def list_published_courses(self, student_id, direction):
        del student_id
        return [copy.deepcopy(self.course)] if direction == "handcraft" else []

    def get_course(self, course_id):
        if course_id != 501:
            return None
        return copy.deepcopy(self.course)

    def get_quiz(self, course_id):
        if course_id != 501:
            return None
        return copy.deepcopy(self.quiz)


class PublishedVideoProvider:
    def get_video(self, video_id):
        if video_id != "published-provider":
            return None
        return {
            "video_id": video_id,
            "craft_key": "guangxiu",
            "title": "Provider published video",
            "review_status": "published",
            "source_available": True,
            "media_url": "https://media.example.test/published.mp4",
            "version": 1,
            "rejection_opinion": None,
            "published_at": "2026-09-17T00:00:00+08:00",
            "created_at": "2026-09-17T00:00:00+08:00",
            "updated_at": "2026-09-17T00:00:00+08:00",
        }


class TestHandcraftFinalReviewFixes(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(Path(self.temp_dir.name) / "test.db"),
                "SECRET_KEY": "test-only-secret",
                "SESSION_HOURS": 24,
                "SESSION_COOKIE_SECURE": False,
                "POINTS_EXPIRY_TOKEN": "internal-test-token",
                "POINTS_EXPIRY_BATCH_SIZE": 10,
            }
        )
        with self.app.app_context():
            db = get_db()
            self.student_id = self._insert_user(db, "student01", "student")
            self.admin_id = self._insert_user(db, "admin01", "admin")
            self.teacher_id = self._insert_user(db, "teacher01", "teacher")
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

        policy = copy.deepcopy(PLACEHOLDER_POINTS_POLICY)
        policy.update(
            {
                "seconds_per_point": 1,
                "training_weights": {"default": 1000},
                "daily_limit": 10000,
            }
        )
        set_points_policy_provider(
            self.app,
            StaticPolicyProvider(policy),
        )
        set_course_provider(self.app, StaticCourseProvider())
        self.ai = Mock()
        set_ai_client(self.app, self.ai)
        self.student_client = self._login("student01")

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
                "2026-09-17T00:00:00+00:00",
                "2026-09-17T00:00:00+00:00",
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

    def _fund_student(self):
        from app.handcraft_inheritance import record_training_points

        with self.app.app_context():
            result = record_training_points(
                self.student_id,
                "ecommerce",
                "live_script",
                "review-fix-funding",
                "2026-09-18T09:00:00+08:00",
            )
            self.assertEqual(result["status"], "processed")

    def test_heartbeat_gap_restarts_segment_without_crediting_gap(self):
        from app.handcraft_inheritance.active_learning import heartbeat

        with self.app.app_context():
            first = heartbeat(
                self.student_id,
                "craft",
                "guangxiu",
                heartbeat_seq=0,
                now_epoch=1000,
            )
            credited = heartbeat(
                self.student_id,
                "craft",
                "guangxiu",
                segment_id=first["segment_id"],
                heartbeat_seq=1,
                now_epoch=1030,
            )
            restarted = heartbeat(
                self.student_id,
                "craft",
                "guangxiu",
                segment_id=first["segment_id"],
                heartbeat_seq=2,
                now_epoch=1211,
            )
            resumed = heartbeat(
                self.student_id,
                "craft",
                "guangxiu",
                segment_id=restarted["segment_id"],
                heartbeat_seq=3,
                now_epoch=1241,
            )

        self.assertEqual(credited["active_seconds"], 30)
        self.assertTrue(restarted["restarted"])
        self.assertNotEqual(restarted["segment_id"], first["segment_id"])
        self.assertEqual(restarted["active_seconds"], 0)
        self.assertEqual(resumed["active_seconds"], 30)

    def test_heartbeat_replays_and_out_of_order_calls_are_idempotent(self):
        from app.handcraft_inheritance.active_learning import heartbeat

        with self.app.app_context():
            first = heartbeat(
                self.student_id,
                "craft",
                "guangxiu",
                heartbeat_seq=0,
                now_epoch=2000,
            )
            second = heartbeat(
                self.student_id,
                "craft",
                "guangxiu",
                segment_id=first["segment_id"],
                heartbeat_seq=1,
                now_epoch=2030,
            )
            replay = heartbeat(
                self.student_id,
                "craft",
                "guangxiu",
                segment_id=first["segment_id"],
                heartbeat_seq=1,
                now_epoch=2060,
            )
            third = heartbeat(
                self.student_id,
                "craft",
                "guangxiu",
                segment_id=first["segment_id"],
                heartbeat_seq=2,
                now_epoch=2090,
            )
            old = heartbeat(
                self.student_id,
                "craft",
                "guangxiu",
                segment_id=first["segment_id"],
                heartbeat_seq=1,
                now_epoch=2120,
            )
            fourth = heartbeat(
                self.student_id,
                "craft",
                "guangxiu",
                segment_id=first["segment_id"],
                heartbeat_seq=3,
                now_epoch=2120,
            )

        self.assertEqual(second["active_seconds"], 30)
        self.assertEqual(replay["active_seconds"], 30)
        self.assertEqual(third["active_seconds"], 60)
        self.assertEqual(old["active_seconds"], 60)
        self.assertEqual(fourth["active_seconds"], 90)

    def test_heartbeat_caps_one_segment_at_7200_seconds(self):
        from app.handcraft_inheritance.active_learning import heartbeat

        with self.app.app_context():
            current = heartbeat(
                self.student_id,
                "craft",
                "guangxiu",
                heartbeat_seq=0,
                now_epoch=3000,
            )
            for sequence in range(1, 242):
                current = heartbeat(
                    self.student_id,
                    "craft",
                    "guangxiu",
                    segment_id=current["segment_id"],
                    heartbeat_seq=sequence,
                    now_epoch=3000 + sequence * 30,
                )
            capped = heartbeat(
                self.student_id,
                "craft",
                "guangxiu",
                segment_id=current["segment_id"],
                heartbeat_seq=242,
                now_epoch=3000 + 242 * 30,
            )

        self.assertEqual(current["active_seconds"], 7200)
        self.assertEqual(capped["active_seconds"], 7200)

    def test_client_supplied_duration_cannot_mint_points(self):
        self.ai.complete_json.return_value = AR_GUIDANCE
        craft = self.student_client.post(
            "/api/handcraft-inheritance/crafts/guangxiu/steps/1/complete",
            json={"active_seconds": 7200, "event_id": "spoof-step"},
        )
        ar = self.student_client.post(
            "/api/handcraft-inheritance/ar-guidance",
            json={
                "craft_key": "guangxiu",
                "project_label": "绣制花瓣",
                "active_seconds": 7200,
                "event_id": "spoof-ar",
            },
        )
        course = self.student_client.put(
            "/api/handcraft-inheritance/courses/501/progress",
            json={
                "position_seconds": 80,
                "watched_delta_seconds": 7200,
            },
        )

        self.assertEqual(craft.status_code, 200)
        self.assertEqual(craft.get_json()["progress"]["completed_steps"], [1])
        self.assertEqual(ar.status_code, 200)
        self.assertEqual(course.status_code, 200)
        self.assertEqual(
            course.get_json()["progress"]["watched_seconds"],
            0,
        )
        with self.app.app_context():
            count = get_db().execute(
                """
                SELECT COUNT(*) AS count
                FROM points_event_inbox
                WHERE source_module = 'handcraft'
                """
            ).fetchone()["count"]
        self.assertEqual(count, 0)

    def test_heartbeat_endpoint_feeds_step_points_and_handles_bad_token(self):
        with patch(
            "app.handcraft_inheritance.active_learning._now_epoch",
            side_effect=[4000, 4030],
        ):
            started = self.student_client.post(
                "/api/handcraft-inheritance/crafts/guangxiu/heartbeat",
                json={"heartbeat_seq": 0},
            )
            beat = self.student_client.post(
                "/api/handcraft-inheritance/crafts/guangxiu/heartbeat",
                json={
                    "segment_id": started.get_json()["session"]["segment_id"],
                    "heartbeat_seq": 1,
                },
            )
        completed = self.student_client.post(
            "/api/handcraft-inheritance/crafts/guangxiu/steps/1/complete",
            json={
                "segment_id": beat.get_json()["session"]["segment_id"],
            },
        )
        invalid_token = self.student_client.post(
            "/api/handcraft-inheritance/internal/points-expiry/run",
            headers={"X-Points-Expiry-Token": "无效令牌"},
        )

        self.assertEqual(started.status_code, 200)
        self.assertEqual(beat.status_code, 200)
        self.assertEqual(beat.get_json()["session"]["active_seconds"], 30)
        self.assertEqual(completed.status_code, 200)
        self.assertEqual(invalid_token.status_code, 401)
        with self.app.app_context():
            inbox = get_db().execute(
                """
                SELECT duration_seconds
                FROM points_event_inbox
                WHERE user_id = ?
                  AND source_module = 'handcraft'
                """,
                (self.student_id,),
            ).fetchone()
        self.assertEqual(inbox["duration_seconds"], 30)

    def test_published_provider_video_is_visible_and_playable(self):
        set_teaching_video_provider(self.app, PublishedVideoProvider())
        with self.app.app_context():
            db = get_db()
            db.execute(
                """
                INSERT INTO heritage_videos (
                    video_id, craft_key, title, review_status,
                    source_available, media_url, version, rejection_opinion,
                    published_at, created_at, updated_at
                )
                VALUES (
                    'published-provider', 'guangxiu',
                    'Provider published video', 'approved', 1,
                    'https://media.example.test/published.mp4', 1, NULL,
                    '2026-09-17T00:00:00+08:00',
                    '2026-09-17T00:00:00+08:00',
                    '2026-09-17T00:00:00+08:00'
                )
                """
            )
            db.commit()

        response = self.student_client.get(
            "/api/handcraft-inheritance/videos?craft_key=guangxiu"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [video["video_id"] for video in response.get_json()["videos"]],
            ["published-provider"],
        )
        self.assertEqual(
            response.get_json()["videos"][0]["playback_url"],
            "https://media.example.test/published.mp4",
        )

    def test_redemption_notification_retry_is_durable_and_deduplicated(self):
        self._fund_student()
        with patch(
            "app.handcraft_inheritance.outbox.emit_redemption_succeeded",
            side_effect=RuntimeError("temporary 02 outage"),
        ):
            with self.app.app_context():
                redemption = redeem_reward(
                    self.student_id,
                    "reward-guangxiu-bookmark",
                    "durable-redemption",
                )

        with self.app.app_context():
            db = get_db()
            pending = db.execute(
                """
                SELECT status, attempts, event_id
                FROM handcraft_notification_outbox
                """
            ).fetchone()
            counts = db.execute(
                """
                SELECT
                    (SELECT COUNT(*) FROM redemptions) AS redemptions,
                    (SELECT COUNT(*) FROM points_transactions
                     WHERE transaction_type = 'spend') AS spends
                """
            ).fetchone()

        self.assertEqual(redemption["request_id"], "durable-redemption")
        self.assertEqual(pending["status"], "pending")
        self.assertEqual(pending["attempts"], 1)
        self.assertEqual((counts["redemptions"], counts["spends"]), (1, 1))

        from app.handcraft_inheritance.outbox import (
            retry_pending_handcraft_notifications,
        )
        from app.messaging.events import emit_redemption_succeeded

        with patch(
            "app.handcraft_inheritance.outbox.emit_redemption_succeeded",
            side_effect=emit_redemption_succeeded,
        ) as emit:
            recovered = self.student_client.post(
                "/api/handcraft-inheritance/internal/points-expiry/run",
                headers={"X-Points-Expiry-Token": "internal-test-token"},
            )
            with self.app.app_context():
                second = retry_pending_handcraft_notifications()
                notification_count = get_db().execute(
                    "SELECT COUNT(*) AS count FROM system_notifications"
                ).fetchone()["count"]

        self.assertEqual(
            recovered.get_json()["handcraft_notifications"]["sent"],
            1,
        )
        self.assertEqual(second["sent"], 0)
        self.assertEqual(emit.call_count, 1)
        self.assertEqual(notification_count, 1)

    def test_video_review_notification_retry_preserves_committed_state(self):
        with self.app.app_context():
            db = get_db()
            db.execute(
                """
                INSERT INTO heritage_videos (
                    video_id, craft_key, title, review_status,
                    source_available, media_url, version, rejection_opinion,
                    published_at, created_at, updated_at
                )
                VALUES (
                    'retry-review', 'guangxiu', '待审核', 'pending', 1,
                    'https://media.example.test/retry.mp4', 1, NULL, NULL,
                    '2026-09-17T00:00:00+08:00',
                    '2026-09-17T00:00:00+08:00'
                )
                """
            )
            db.commit()

        action = {
            "video_id": "retry-review",
            "action": "approve",
            "reviewer_role": "admin",
            "submitter_id": self.teacher_id,
            "version": 1,
        }
        with patch(
            "app.handcraft_inheritance.outbox.emit_review_result",
            side_effect=RuntimeError("temporary 02 outage"),
        ):
            with self.app.app_context():
                result = apply_video_review(action)

        self.assertEqual(result["status"], "approved")
        with self.app.app_context():
            db = get_db()
            row = db.execute(
                """
                SELECT review_status
                FROM heritage_videos
                WHERE video_id = 'retry-review'
                """
            ).fetchone()
            pending = db.execute(
                """
                SELECT status, attempts
                FROM handcraft_notification_outbox
                """
            ).fetchone()
        self.assertEqual(row["review_status"], "approved")
        self.assertEqual(pending["status"], "pending")
        self.assertEqual(pending["attempts"], 1)

        from app.handcraft_inheritance.outbox import (
            retry_pending_handcraft_notifications,
        )
        from app.messaging.events import emit_review_result

        with patch(
            "app.handcraft_inheritance.outbox.emit_review_result",
            side_effect=emit_review_result,
        ) as emit:
            with self.app.app_context():
                first = retry_pending_handcraft_notifications()
                second = retry_pending_handcraft_notifications()
                notification_count = get_db().execute(
                    "SELECT COUNT(*) AS count FROM system_notifications"
                ).fetchone()["count"]

        self.assertEqual(first["sent"], 1)
        self.assertEqual(second["sent"], 0)
        self.assertEqual(emit.call_count, 1)
        self.assertEqual(notification_count, 1)


if __name__ == "__main__":
    unittest.main()
