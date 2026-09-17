import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from werkzeug.security import generate_password_hash

from app import create_app
from app.agri_skills.ai_client import set_ai_client
from app.agri_skills.errors import AgriValidationError, AiUnavailableError
from app.agri_skills.providers import set_course_provider
from app.db import get_db
from app.handcraft_inheritance import (
    record_training_points,
    set_points_policy_provider,
)
from app.handcraft_inheritance.fulfillment import (
    cancel_pending_fulfillment,
)
from app.handcraft_inheritance.presets import PLACEHOLDER_POINTS_POLICY
from app.handcraft_inheritance.rewards import REDEMPTION_CONFLICT_MESSAGE


LEARNER_ROUTES = (
    ("GET", "/api/handcraft-inheritance/crafts", None),
    ("GET", "/api/handcraft-inheritance/crafts/guangxiu", None),
    ("GET", "/api/handcraft-inheritance/crafts/guangxiu/progress", None),
    (
        "POST",
        "/api/handcraft-inheritance/crafts/guangxiu/steps/1/complete",
        {"active_seconds": 600, "event_id": "step-1"},
    ),
    (
        "GET",
        "/api/handcraft-inheritance/videos?craft_key=guangxiu",
        None,
    ),
    (
        "POST",
        "/api/handcraft-inheritance/ar-guidance",
        {
            "craft_key": "guangxiu",
            "project_label": "绣制花瓣",
            "active_seconds": 600,
            "event_id": "ar-1",
        },
    ),
    ("GET", "/api/handcraft-inheritance/points", None),
    ("GET", "/api/handcraft-inheritance/points/ledger", None),
    ("GET", "/api/handcraft-inheritance/rewards", None),
    ("GET", "/api/handcraft-inheritance/redemptions", None),
    (
        "POST",
        "/api/handcraft-inheritance/redemptions",
        {"reward_id": "reward-guangxiu-bookmark", "request_id": "api-1"},
    ),
    (
        "POST",
        "/api/handcraft-inheritance/redemptions/1/cancel",
        None,
    ),
    ("GET", "/api/handcraft-inheritance/courses", None),
    ("GET", "/api/handcraft-inheritance/recommendations", None),
    (
        "GET",
        "/api/handcraft-inheritance/courses/501/progress",
        None,
    ),
    (
        "PUT",
        "/api/handcraft-inheritance/courses/501/progress",
        {"position_seconds": 80, "watched_delta_seconds": 80},
    ),
    (
        "GET",
        "/api/handcraft-inheritance/courses/501/quiz",
        None,
    ),
    (
        "POST",
        "/api/handcraft-inheritance/courses/501/quiz",
        {"answers": {"q1": "A"}},
    ),
)

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
    "score": 100,
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


class StaticHandcraftCourseProvider:
    def __init__(self):
        self.courses = [
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
            },
            {
                "id": 502,
                "title": "待审核课程",
                "direction": "handcraft",
                "status": "pending",
                "summary": "不可泄漏",
                "teacher_name": "梁老师",
                "published_at": None,
                "duration_seconds": 100,
                "tag_ids": [101],
            },
        ]
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
        return [
            copy.deepcopy(course)
            for course in self.courses
            if course["direction"] == direction
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


class TestHandcraftApi(unittest.TestCase):
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
                "POINTS_EXPIRY_BATCH_SIZE": 1,
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
        set_course_provider(
            self.app,
            StaticHandcraftCourseProvider(),
        )
        self.ai = Mock()
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

    def _fund_student(
        self,
        user_id=None,
        source_id="funding",
        occurred_at="2026-09-17T09:00:00+08:00",
    ):
        user_id = user_id or self.student_id
        with self.app.app_context():
            result = record_training_points(
                user_id,
                "ecommerce",
                "api_funding",
                source_id,
                occurred_at,
            )
            self.assertEqual(result["status"], "processed")

    def _use_natural_year_policy(self):
        policy = copy.deepcopy(PLACEHOLDER_POINTS_POLICY)
        policy.update(
            {
                "seconds_per_point": 1,
                "training_weights": {"default": 1000},
                "daily_limit": 10000,
                "expiry_mode": "natural_year",
            }
        )
        set_points_policy_provider(
            self.app,
            StaticPolicyProvider(policy),
        )

    def test_blueprint_registers_the_exact_handcraft_route_table(self):
        routes = {}
        for rule in self.app.url_map.iter_rules():
            if not rule.rule.startswith("/api/handcraft-inheritance"):
                continue
            routes.setdefault(rule.rule, set()).update(
                rule.methods - {"HEAD", "OPTIONS"}
            )

        expected = {
            "/api/handcraft-inheritance/crafts": {"GET"},
            "/api/handcraft-inheritance/crafts/<craft_key>": {"GET"},
            (
                "/api/handcraft-inheritance/crafts/<craft_key>/progress"
            ): {"GET"},
            (
                "/api/handcraft-inheritance/crafts/<craft_key>/"
                "steps/<int:step_no>/complete"
            ): {"POST"},
            "/api/handcraft-inheritance/videos": {"GET"},
            "/api/handcraft-inheritance/ar-guidance": {"POST"},
            "/api/handcraft-inheritance/points": {"GET"},
            "/api/handcraft-inheritance/points/ledger": {"GET"},
            "/api/handcraft-inheritance/rewards": {"GET"},
            "/api/handcraft-inheritance/redemptions": {"GET", "POST"},
            (
                "/api/handcraft-inheritance/redemptions/"
                "<int:redemption_id>/cancel"
            ): {"POST"},
            "/api/handcraft-inheritance/courses": {"GET"},
            "/api/handcraft-inheritance/recommendations": {"GET"},
            (
                "/api/handcraft-inheritance/courses/<int:course_id>/progress"
            ): {"GET", "PUT"},
            (
                "/api/handcraft-inheritance/courses/<int:course_id>/quiz"
            ): {"GET", "POST"},
            (
                "/api/handcraft-inheritance/internal/points-expiry/run"
            ): {"POST"},
        }
        self.assertEqual(routes, expected)

    def test_learner_routes_require_active_student_sessions(self):
        anonymous = self.app.test_client()
        for method, path, payload in LEARNER_ROUTES:
            for name, client in (
                ("anonymous", anonymous),
                ("teacher", self.teacher_client),
            ):
                with self.subTest(method=method, path=path, client=name):
                    response = client.open(
                        path,
                        method=method,
                        json=payload,
                    )
                    self.assertEqual(response.status_code, 401)
                    self.assertEqual(
                        response.get_json()["message"],
                        "未登录或会话已过期",
                    )

    def test_crafts_progress_steps_and_video_payloads_are_student_scoped(self):
        crafts = self.student_client.get(
            "/api/handcraft-inheritance/crafts"
        )
        detail = self.student_client.get(
            "/api/handcraft-inheritance/crafts/guangxiu"
        )
        initial = self.student_client.get(
            "/api/handcraft-inheritance/crafts/guangxiu/progress"
        )
        completed = self.student_client.post(
            (
                "/api/handcraft-inheritance/crafts/guangxiu/"
                "steps/1/complete"
            ),
            json={
                "user_id": self.other_student_id,
                "active_seconds": 600,
                "event_id": "api-step-1",
            },
        )

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
                    'hidden-pending', 'guangxiu', '待审核视频', 'pending',
                    1, 'https://example.test/pending.mp4', 1, '不公开',
                    NULL, '2026-09-17T00:00:00+08:00',
                    '2026-09-17T00:00:00+08:00'
                )
                """
            )
            db.commit()

        videos = self.student_client.get(
            "/api/handcraft-inheritance/videos?craft_key=guangxiu"
        )

        self.assertEqual(crafts.status_code, 200)
        self.assertEqual(len(crafts.get_json()["crafts"]), 4)
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(len(detail.get_json()["craft"]["steps"]), 6)
        self.assertTrue(
            detail.get_json()["craft"]["material_guide"][0][
                "taobao_keyword"
            ]
        )
        self.assertEqual(initial.status_code, 200)
        self.assertEqual(
            initial.get_json()["progress"]["completed_step_count"],
            0,
        )
        self.assertEqual(completed.status_code, 200)
        self.assertEqual(
            completed.get_json()["progress"]["user_id"],
            self.student_id,
        )
        self.assertEqual(
            completed.get_json()["progress"]["completed_steps"],
            [1],
        )
        self.assertEqual(videos.status_code, 200)
        self.assertEqual(
            [video["video_id"] for video in videos.get_json()["videos"]],
            ["demo-guangxiu-approved"],
        )
        self.assertNotIn(
            "rejection_opinion",
            videos.get_json()["videos"][0],
        )

        with self.app.app_context():
            inbox = get_db().execute(
                """
                SELECT user_id, source_event_id, duration_seconds
                FROM points_event_inbox
                WHERE source_module = 'handcraft'
                """
            ).fetchone()
            progress = get_db().execute(
                """
                SELECT user_id
                FROM heritage_craft_progress
                WHERE craft_key = 'guangxiu'
                """
            ).fetchone()

        self.assertEqual(
            dict(inbox),
            {
                "user_id": self.student_id,
                "source_event_id": "guangxiu|1:api-step-1",
                "duration_seconds": 600,
            },
        )
        self.assertEqual(progress["user_id"], self.student_id)

    def test_ar_route_records_server_duration_and_exact_ai_failure(self):
        self.ai.complete_json.return_value = AR_GUIDANCE
        success = self.student_client.post(
            "/api/handcraft-inheritance/ar-guidance",
            json={
                "user_id": self.other_student_id,
                "craft_key": "guangxiu",
                "project_label": "绣制花瓣",
                "active_seconds": 600,
                "event_id": "api-ar-1",
            },
        )

        self.ai.complete_json.side_effect = AiUnavailableError(
            "raw provider traceback and secret"
        )
        unavailable = self.student_client.post(
            "/api/handcraft-inheritance/ar-guidance",
            json={
                "craft_key": "guangxiu",
                "project_label": "绣制花瓣",
            },
        )

        self.assertEqual(success.status_code, 200)
        self.assertEqual(success.get_json()["guidance"], AR_GUIDANCE)
        self.assertEqual(unavailable.status_code, 503)
        self.assertEqual(
            unavailable.get_json(),
            {
                "success": False,
                "message": "AI 服务暂时不可用",
            },
        )
        self.assertNotIn(
            "raw provider traceback",
            unavailable.get_data(as_text=True),
        )

        with self.app.app_context():
            inbox = get_db().execute(
                """
                SELECT user_id, source_event_id, duration_seconds
                FROM points_event_inbox
                WHERE source_module = 'handcraft'
                """
            ).fetchone()

        self.assertEqual(
            dict(inbox),
            {
                "user_id": self.student_id,
                "source_event_id": "guangxiu|api-ar-1",
                "duration_seconds": 600,
            },
        )

    def test_points_rewards_redemption_and_cancellation_are_owner_scoped(self):
        self._fund_student()

        account = self.student_client.get(
            "/api/handcraft-inheritance/points"
        )
        ledger = self.student_client.get(
            "/api/handcraft-inheritance/points/ledger"
        )
        rewards = self.student_client.get(
            "/api/handcraft-inheritance/rewards"
        )
        redeemed = self.student_client.post(
            "/api/handcraft-inheritance/redemptions",
            json={
                "user_id": self.other_student_id,
                "reward_id": "reward-guangxiu-bookmark",
                "request_id": "api-redemption-1",
            },
        )

        self.assertEqual(account.status_code, 200)
        self.assertEqual(account.get_json()["account"]["balance"], 1000)
        self.assertEqual(ledger.status_code, 200)
        self.assertTrue(ledger.get_json()["ledger"])
        self.assertEqual(rewards.status_code, 200)
        self.assertTrue(rewards.get_json()["rewards"][0]["can_redeem"])
        self.assertEqual(redeemed.status_code, 201)
        redemption = redeemed.get_json()["redemption"]
        self.assertEqual(redemption["user_id"], self.student_id)

        own_history = self.student_client.get(
            "/api/handcraft-inheritance/redemptions"
        )
        other_history = self.other_student_client.get(
            "/api/handcraft-inheritance/redemptions"
        )
        foreign_cancel = self.other_student_client.post(
            (
                "/api/handcraft-inheritance/redemptions/"
                f"{redemption['id']}/cancel"
            ),
            json={"user_id": self.student_id},
        )
        canceled = self.student_client.post(
            (
                "/api/handcraft-inheritance/redemptions/"
                f"{redemption['id']}/cancel"
            ),
            json={"user_id": self.other_student_id},
        )

        self.assertEqual(own_history.status_code, 200)
        self.assertEqual(
            own_history.get_json()["redemptions"][0]["id"],
            redemption["id"],
        )
        self.assertEqual(
            own_history.get_json()["fulfillments"][0]["redemption"]["id"],
            redemption["id"],
        )
        self.assertEqual(other_history.status_code, 200)
        self.assertEqual(other_history.get_json()["redemptions"], [])
        self.assertEqual(other_history.get_json()["fulfillments"], [])
        self.assertEqual(foreign_cancel.status_code, 404)
        self.assertEqual(canceled.status_code, 200)
        self.assertEqual(
            canceled.get_json()["cancellation"]["status"],
            "canceled",
        )

    def test_course_routes_filter_hidden_courses_and_preserve_stable_event_id(self):
        courses = self.student_client.get(
            "/api/handcraft-inheritance/courses"
        )
        recommendations = self.student_client.get(
            "/api/handcraft-inheritance/recommendations"
        )
        progress = self.student_client.put(
            "/api/handcraft-inheritance/courses/501/progress",
            json={
                "user_id": self.other_student_id,
                "position_seconds": 80,
                "watched_delta_seconds": 80,
            },
        )
        quiz = self.student_client.get(
            "/api/handcraft-inheritance/courses/501/quiz"
        )
        self.ai.complete_json.return_value = QUIZ_GRADE
        submitted = self.student_client.post(
            "/api/handcraft-inheritance/courses/501/quiz",
            json={
                "user_id": self.other_student_id,
                "answers": {"q1": "A"},
            },
        )

        self.assertEqual(courses.status_code, 200)
        self.assertEqual(
            [course["id"] for course in courses.get_json()["courses"]],
            [501],
        )
        self.assertEqual(recommendations.status_code, 200)
        self.assertEqual(
            [
                course["id"]
                for course in recommendations.get_json()["courses"]
            ],
            [501],
        )
        self.assertEqual(progress.status_code, 200)
        self.assertEqual(
            progress.get_json()["progress"]["progress_percent"],
            80,
        )
        self.assertEqual(quiz.status_code, 200)
        self.assertEqual(submitted.status_code, 201)
        self.assertEqual(submitted.get_json()["attempt"]["score"], 100)

        with self.app.app_context():
            inbox = get_db().execute(
                """
                SELECT user_id, source_event_id
                FROM points_event_inbox
                WHERE source_module = 'handcraft'
                """
            ).fetchone()
            course_progress = get_db().execute(
                """
                SELECT user_id
                FROM agri_course_progress
                WHERE course_id = 501
                """
            ).fetchone()

        self.assertEqual(
            dict(inbox),
            {
                "user_id": self.student_id,
                "source_event_id": "handcraft-course:501|80",
            },
        )
        self.assertEqual(course_progress["user_id"], self.student_id)

    def test_quiz_ai_failure_returns_exact_503_without_overwriting_attempt(self):
        self.student_client.put(
            "/api/handcraft-inheritance/courses/501/progress",
            json={"position_seconds": 80, "watched_delta_seconds": 80},
        )
        self.ai.complete_json.return_value = QUIZ_GRADE
        first = self.student_client.post(
            "/api/handcraft-inheritance/courses/501/quiz",
            json={"answers": {"q1": "A"}},
        )
        self.ai.complete_json.side_effect = AiUnavailableError(
            "raw provider failure"
        )
        failed = self.student_client.post(
            "/api/handcraft-inheritance/courses/501/quiz",
            json={"answers": {"q1": "B"}},
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
        with self.app.app_context():
            attempts = get_db().execute(
                """
                SELECT id, score, is_formal
                FROM agri_course_quiz_attempts
                WHERE course_id = 501
                """
            ).fetchall()
        self.assertEqual(len(attempts), 1)
        self.assertEqual(int(attempts[0]["score"]), 100)
        self.assertEqual(int(attempts[0]["is_formal"]), 1)

    def test_validation_and_conflict_errors_use_stable_json_statuses(self):
        invalid = self.student_client.post(
            (
                "/api/handcraft-inheritance/crafts/guangxiu/"
                "steps/1/complete"
            ),
            json={"active_seconds": -1, "event_id": "invalid"},
        )
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(invalid.get_json()["success"], False)

        with patch(
            "app.handcraft_inheritance.routes._redeem_reward",
            side_effect=AgriValidationError(REDEMPTION_CONFLICT_MESSAGE),
        ):
            conflict = self.student_client.post(
                "/api/handcraft-inheritance/redemptions",
                json={
                    "reward_id": "reward-guangxiu-bookmark",
                    "request_id": "conflict",
                },
            )

        self.assertEqual(conflict.status_code, 409)
        self.assertEqual(
            conflict.get_json(),
            {
                "success": False,
                "message": REDEMPTION_CONFLICT_MESSAGE,
                "errors": {},
            },
        )

    def test_internal_expiry_route_uses_token_batch_and_is_idempotent(self):
        self._use_natural_year_policy()
        self._fund_student(
            source_id="expired-award",
            occurred_at="2025-06-01T09:00:00+08:00",
        )
        self._fund_student(
            user_id=self.other_student_id,
            source_id="expired-award-2",
            occurred_at="2025-06-01T09:00:00+08:00",
        )

        missing = self.student_client.post(
            "/api/handcraft-inheritance/internal/points-expiry/run"
        )
        first = self.app.test_client().post(
            "/api/handcraft-inheritance/internal/points-expiry/run",
            headers={"X-Points-Expiry-Token": "internal-test-token"},
            json={"batch_size": 100},
        )
        second = self.student_client.post(
            "/api/handcraft-inheritance/internal/points-expiry/run",
            headers={"Authorization": "Bearer internal-test-token"},
            json={"batch_size": 100},
        )

        self.assertEqual(missing.status_code, 401)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.get_json()["processed_users"], 1)
        self.assertEqual(first.get_json()["points_cleared"], 1000)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.get_json()["processed_users"], 1)
        self.assertEqual(second.get_json()["points_cleared"], 1000)
        third = self.student_client.post(
            "/api/handcraft-inheritance/internal/points-expiry/run",
            headers={"X-Points-Expiry-Token": "internal-test-token"},
        )
        self.assertEqual(third.get_json()["processed_users"], 0)
        self.assertEqual(third.get_json()["points_cleared"], 0)

    def test_internal_recovery_retries_pending_fulfillment_notifications(self):
        self._fund_student(source_id="fulfillment-retry-funding")
        redeemed = self.student_client.post(
            "/api/handcraft-inheritance/redemptions",
            json={
                "reward_id": "reward-guangxiu-bookmark",
                "request_id": "fulfillment-retry",
            },
        )
        redemption = redeemed.get_json()["redemption"]

        with self.app.app_context():
            history = self.student_client.get(
                "/api/handcraft-inheritance/redemptions"
            )
            fulfillment_id = history.get_json()["fulfillments"][0][
                "fulfillment"
            ]["id"]
            with patch(
                "app.handcraft_inheritance.fulfillment."
                "emit_fulfillment_cancelled",
                side_effect=RuntimeError("notification offline"),
            ):
                with self.assertRaises(RuntimeError):
                    cancel_pending_fulfillment(
                        fulfillment_id,
                        role="student",
                        actor_user_id=self.student_id,
                    )

        recovered = self.student_client.post(
            "/api/handcraft-inheritance/internal/points-expiry/run",
            headers={"X-Points-Expiry-Token": "internal-test-token"},
        )

        self.assertEqual(recovered.status_code, 200)
        self.assertEqual(
            recovered.get_json()["fulfillment_notifications"]["sent"],
            1,
        )
        with self.app.app_context():
            notification = get_db().execute(
                """
                SELECT event_key
                FROM system_notifications
                WHERE source_type = 'fulfillment'
                  AND source_id = ?
                """,
                (str(fulfillment_id),),
            ).fetchone()
        self.assertEqual(
            notification["event_key"],
            (
                "fulfillment_cancelled:"
                f"handcraft-fulfillment:{fulfillment_id}:cancel_pending"
            ),
        )
        self.assertEqual(redemption["status"], "pending")


if __name__ == "__main__":
    unittest.main()
