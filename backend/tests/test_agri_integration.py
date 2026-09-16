import json
import tempfile
import unittest
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from werkzeug.security import generate_password_hash

from app import create_app
from app.agri_skills import configure_agri_providers
from app.agri_skills.ai_context import AI_FIELD_ALLOWLISTS, build_ai_messages
from app.agri_skills.calendar import list_product_subscriber_ids
from app.agri_skills.course_learning import list_recommendations
from app.agri_skills.errors import AiUnavailableError
from app.agri_skills.presets import PlaceholderPresetProvider
from app.db import get_db
from app.messaging.broadcasts import emit_monthly_agriculture_reminder
from app.messaging.notification_service import list_notifications


AI_UNAVAILABLE_MESSAGE = "AI 服务暂时不可用"
NO_LOCAL_MATCH_MESSAGE = "暂无法回答，建议稍后再试"


class FakeCourseProvider:
    def __init__(self, courses=None, quiz=None):
        self.courses = list(courses or [])
        self.quiz = quiz

    def list_published_agriculture_courses(self, student_id):
        del student_id
        return [
            {
                **course,
                "tag_ids": list(course.get("tag_ids", [])),
            }
            for course in self.courses
        ]

    def get_course(self, course_id):
        course = next(
            (course for course in self.courses if course["id"] == course_id),
            None,
        )
        if course is None:
            return None
        return {
            **course,
            "tag_ids": list(course.get("tag_ids", [])),
        }

    def get_quiz(self, course_id):
        if self.get_course(course_id) is None:
            return None
        return self.quiz


class FakeAiClient:
    def __init__(self):
        self.stream_chunks = ["荔枝", "保果要点"]
        self.stream_error = None
        self.responses = defaultdict(list)
        self.calls = []

    def queue(self, call_point, *responses):
        self.responses[call_point].extend(responses)

    @staticmethod
    def _context(messages):
        if len(messages) < 2:
            return {}
        try:
            return json.loads(messages[1]["content"])
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}

    def _record(self, call_point, messages):
        context = self._context(messages)
        self.calls.append(
            {
                "call_point": call_point,
                "context": context,
                "messages": messages,
            }
        )
        return context

    def stream_chat(self, messages, *, call_point):
        self._record(call_point, messages)
        if self.stream_error is not None:
            raise self.stream_error
        yield from self.stream_chunks

    def complete_json(self, messages, *, call_point):
        self._record(call_point, messages)
        queued = self.responses[call_point]
        if queued:
            response = queued.pop(0)
            if isinstance(response, Exception):
                raise response
            return response

        if call_point == "qa_followups":
            return {"suggestions": ["何时施肥", "如何排水", "怎样防虫"]}
        if call_point == "diagnosis_turn":
            return {
                "status": "follow_up_required",
                "question": "请补充症状出现时间",
                "conclusion": None,
                "limited": False,
            }
        if call_point == "selftest_generate":
            return {"questions": self.valid_questions()}
        if call_point == "selftest_grade":
            return {
                "score": 100,
                "questions": [
                    {"correct": True, "explanation": "回答正确。"},
                    {"correct": True, "explanation": "回答正确。"},
                    {"correct": True, "explanation": "回答正确。"},
                ],
            }
        if call_point == "course_quiz_grade":
            return {
                "score": 100,
                "questions": [
                    {
                        "id": "q1",
                        "correct": True,
                        "explanation": "达到 80% 即完成。",
                    }
                ],
            }
        raise AssertionError(f"unexpected call point: {call_point}")

    def transcribe(self, audio, filename, *, call_point):
        del audio, filename
        if call_point != "speech_to_text":
            raise AssertionError(f"unexpected call point: {call_point}")
        return "荔枝蒂蛀虫怎么防"

    @staticmethod
    def valid_questions():
        return [
            {
                "type": "true_false",
                "prompt": "要及时清理落果",
                "options": ["正确", "错误"],
                "answer": "正确",
            },
            {
                "type": "true_false",
                "prompt": "无需检查果实",
                "options": ["正确", "错误"],
                "answer": "错误",
            },
            {
                "type": "true_false",
                "prompt": "应规范用药",
                "options": ["正确", "错误"],
                "answer": "正确",
            },
        ]


class TestAgriIntegration(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(Path(self.temp_dir.name) / "test.db"),
                "SECRET_KEY": "test-only-secret",
                "SESSION_HOURS": 24,
                "SESSION_COOKIE_SECURE": False,
                "APP_TIMEZONE": "Asia/Shanghai",
            }
        )
        self.student_id = self._create_user("student01", "student")
        self.other_student_id = self._create_user("student02", "student")
        self.student_client = self._login("student01")
        self.other_client = self._login("student02")
        with self.app.app_context():
            now = "2026-09-15T00:00:00+00:00"
            get_db().execute(
                """
                INSERT INTO courses (
                    id, title, direction, status, published_at, summary,
                    teacher_name, created_at, updated_at
                )
                VALUES (
                    1, '荔枝保果', 'agriculture', 'published', ?, ?, ?, ?, ?
                )
                """,
                (
                    "2026-09-01T00:00:00+00:00",
                    "保果与病虫害管理",
                    "林老师",
                    now,
                    now,
                ),
            )
            get_db().commit()

        self.ai = FakeAiClient()
        self.course = {
            "id": 1,
            "title": "荔枝保果",
            "summary": "保果与病虫害管理",
            "teacher_name": "林老师",
            "published_at": "2026-09-01T00:00:00+00:00",
            "tag_ids": [1],
            "duration_seconds": 100,
        }
        self.course_provider = FakeCourseProvider(
            [self.course],
            {
                "questions": [
                    {
                        "id": "q1",
                        "type": "true_false",
                        "prompt": "80% 视为完成",
                        "options": ["正确", "错误"],
                        "answer": "正确",
                    }
                ]
            },
        )
        configure_agri_providers(
            self.app,
            preset_provider=PlaceholderPresetProvider(),
            course_provider=self.course_provider,
            ai_client=self.ai,
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def _create_user(self, username, role):
        with self.app.app_context():
            cursor = get_db().execute(
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
                    "2026-09-15T00:00:00+00:00",
                    "2026-09-15T00:00:00+00:00",
                ),
            )
            get_db().commit()
            return int(cursor.lastrowid)

    def _login(self, username):
        client = self.app.test_client()
        response = client.post(
            "/api/auth/login",
            json={"username": username, "password": "password8"},
        )
        self.assertEqual(response.status_code, 200)
        return client

    def _complete_diagnosis(self):
        self.ai.queue(
            "diagnosis_turn",
            {
                "status": "follow_up_required",
                "question": "请补充症状出现时间",
                "conclusion": None,
                "limited": False,
            },
            {
                "status": "conclusion_ready",
                "question": None,
                "conclusion": {
                    "cause": "疑似蒂蛀虫危害果实",
                    "treatment": "清理落果并按登记药剂防治",
                },
                "limited": False,
            },
        )
        created = self.student_client.post(
            "/api/agri-skills/diagnoses",
            json={
                "product_key": "litchi",
                "affected_part": "fruit",
                "symptoms": ["虫蛀", "落果"],
            },
        )
        self.assertEqual(created.status_code, 201)
        session_id = created.get_json()["session"]["id"]
        answered = self.student_client.post(
            f"/api/agri-skills/diagnoses/{session_id}/answers",
            json={"answer": "果实有虫孔并有落果", "input_mode": "text"},
        )
        self.assertEqual(answered.status_code, 200)
        self.assertEqual(
            answered.get_json()["session"]["status"],
            "completed",
        )
        return session_id

    def _complete_course(self, course_id=1):
        response = self.student_client.put(
            f"/api/agri-skills/courses/{course_id}/progress",
            json={"position_seconds": 80, "watched_delta_seconds": 80},
        )
        self.assertEqual(response.status_code, 200)
        return response.get_json()["progress"]

    def _attempt_rows(self):
        with self.app.app_context():
            rows = get_db().execute(
                """
                SELECT id, score, is_formal
                FROM agri_course_quiz_attempts
                WHERE user_id = ?
                ORDER BY id
                """,
                (self.student_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def test_calendar_defaults_empty_states_subscription_and_reminder(self):
        fixed_utc = datetime(2026, 3, 31, 16, 30, tzinfo=timezone.utc)
        with patch("app.agri_skills.routes.datetime") as route_datetime:
            route_datetime.now.side_effect = (
                lambda tz: fixed_utc.astimezone(tz)
            )
            calendar = self.student_client.get("/api/agri-skills/calendar")

        self.assertEqual(calendar.status_code, 200)
        calendar_body = calendar.get_json()["calendar"]
        self.assertEqual(calendar_body["product"]["key"], "litchi")
        self.assertEqual(calendar_body["month"], 4)
        self.assertIsNone(calendar_body["empty_state"])

        selected = self.student_client.put(
            "/api/agri-skills/calendar/selection",
            json={"product_key": "longan"},
        )
        self.assertEqual(selected.status_code, 200)
        product_empty = self.student_client.get(
            "/api/agri-skills/calendar?month=4"
        )
        self.assertEqual(
            product_empty.get_json()["calendar"]["empty_state"],
            "暂无该产品农时数据",
        )

        month_empty = self.student_client.get(
            "/api/agri-skills/calendar?product_key=litchi&month=2"
        )
        self.assertEqual(
            month_empty.get_json()["calendar"]["empty_state"],
            "当月无该产品农时",
        )

        first = self.student_client.post(
            "/api/agri-skills/subscriptions/litchi"
        )
        second = self.student_client.post(
            "/api/agri-skills/subscriptions/litchi"
        )
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)

        with self.app.app_context():
            self.assertEqual(
                list_product_subscriber_ids("litchi"),
                [self.student_id],
            )
            delivered = emit_monthly_agriculture_reminder(
                event_id="2026-10-litchi",
                product_key="litchi",
                month="2026-10",
                body="保果与病虫害巡查",
            )
            repeated = emit_monthly_agriculture_reminder(
                event_id="2026-10-litchi",
                product_key="litchi",
                month="2026-10",
                body="保果与病虫害巡查",
            )
            notifications = list_notifications(self.student_id)

        self.assertEqual(delivered["created_count"], 1)
        self.assertEqual(repeated["unique_recipient_count"], 1)
        self.assertEqual(len(notifications), 1)
        self.assertEqual(
            notifications[0]["event_type"],
            "agriculture_reminder",
        )

    def test_qa_ai_success_three_suggestions_and_history_order(self):
        first = self.student_client.post(
            "/api/agri-skills/qa/conversations",
            json={"question": "荔枝如何保果", "input_mode": "text"},
        )
        first_id = first.get_json()["conversation"]["id"]
        answered = self.student_client.post(
            f"/api/agri-skills/qa/conversations/{first_id}/messages",
            json={"question": "荔枝如何保果", "input_mode": "text"},
        )

        self.assertEqual(answered.status_code, 201)
        turn = answered.get_json()["turn"]
        self.assertEqual(turn["answer"], "荔枝保果要点")
        self.assertEqual(turn["answer_mode"], "ai")
        self.assertEqual(
            turn["suggestions"],
            ["何时施肥", "如何排水", "怎样防虫"],
        )

        second = self.student_client.post(
            "/api/agri-skills/qa/conversations",
            json={"question": "蒂蛀虫怎么防", "input_mode": "text"},
        )
        second_id = second.get_json()["conversation"]["id"]
        listed = self.student_client.get(
            "/api/agri-skills/qa/conversations"
        )

        self.assertEqual(
            [
                item["id"]
                for item in listed.get_json()["conversations"]
            ],
            [second_id, first_id],
        )

    def test_qa_failure_uses_local_kb_or_exact_no_match_message(self):
        created = self.student_client.post(
            "/api/agri-skills/qa/conversations",
            json={"question": "荔枝落果", "input_mode": "text"},
        )
        conversation_id = created.get_json()["conversation"]["id"]
        self.ai.stream_error = AiUnavailableError("upstream unavailable")

        fallback = self.student_client.post(
            f"/api/agri-skills/qa/conversations/{conversation_id}/messages",
            json={
                "question": "荔枝蒂蛀虫导致落果",
                "input_mode": "text",
            },
        )
        self.assertEqual(fallback.status_code, 201)
        fallback_turn = fallback.get_json()["turn"]
        self.assertEqual(fallback_turn["answer_mode"], "local_kb")
        self.assertIn("离线知识库回答", fallback_turn["answer"])
        self.assertEqual(fallback_turn["suggestions"], [])

        no_match = self.student_client.post(
            f"/api/agri-skills/qa/conversations/{conversation_id}/messages",
            json={"question": "完全无关的问题", "input_mode": "text"},
        )
        self.assertEqual(no_match.status_code, 503)
        self.assertEqual(
            no_match.get_json()["message"],
            NO_LOCAL_MATCH_MESSAGE,
        )

    def test_diagnosis_transitions_from_follow_up_to_conclusion(self):
        self.ai.queue(
            "diagnosis_turn",
            {
                "status": "follow_up_required",
                "question": "请补充症状出现时间",
                "conclusion": None,
                "limited": False,
            },
            {
                "status": "conclusion_ready",
                "question": None,
                "conclusion": {
                    "cause": "果实受蒂蛀虫危害",
                    "treatment": "清理落果并按登记药剂防治",
                },
                "limited": False,
            },
        )
        created = self.student_client.post(
            "/api/agri-skills/diagnoses",
            json={
                "product_key": "litchi",
                "affected_part": "fruit",
                "symptoms": ["虫蛀", "落果"],
            },
        )
        session = created.get_json()["session"]
        self.assertEqual(session["status"], "in_progress")
        self.assertEqual(session["pending_question"], "请补充症状出现时间")

        answered = self.student_client.post(
            f"/api/agri-skills/diagnoses/{session['id']}/answers",
            json={"answer": "已经持续三天", "input_mode": "text"},
        )
        result = answered.get_json()
        self.assertEqual(result["status"], "conclusion_ready")
        self.assertEqual(result["session"]["status"], "completed")
        self.assertEqual(
            result["session"]["conclusion"]["cause"],
            "果实受蒂蛀虫危害",
        )
        self.assertTrue(result["session"]["conclusion"]["treatment"])

    def test_five_rounds_force_a_limited_conclusion(self):
        self.ai.queue(
            "diagnosis_turn",
            *[
                {
                    "status": "follow_up_required",
                    "question": f"第 {round_no} 轮追问",
                    "conclusion": None,
                    "limited": False,
                }
                for round_no in range(1, 6)
            ],
            {"status": "follow_up_required"},
        )
        created = self.student_client.post(
            "/api/agri-skills/diagnoses",
            json={
                "product_key": "litchi",
                "affected_part": "fruit",
                "symptoms": ["虫蛀", "落果"],
            },
        )
        session_id = created.get_json()["session"]["id"]

        session = None
        for round_no in range(1, 6):
            answered = self.student_client.post(
                f"/api/agri-skills/diagnoses/{session_id}/answers",
                json={
                    "answer": f"第 {round_no} 轮补充",
                    "input_mode": "text",
                },
            )
            self.assertEqual(answered.status_code, 200)
            session = answered.get_json()["session"]
            if round_no < 5:
                self.assertEqual(session["status"], "in_progress")

        self.assertEqual(session["status"], "completed")
        self.assertEqual(session["round_count"], 5)
        self.assertTrue(session["limited"])
        self.assertIsNone(session["pending_question"])
        self.assertEqual(len(session["answer_records"]), 5)
        self.assertTrue(session["conclusion"]["cause"])
        self.assertTrue(session["conclusion"]["treatment"])

    def test_multiple_followups_and_repeat_source_context(self):
        session_id = self._complete_diagnosis()
        first = self.student_client.post(
            f"/api/agri-skills/diagnoses/{session_id}/followups",
            json={"outcome": "improved", "note": "叶片恢复"},
        )
        second = self.student_client.post(
            f"/api/agri-skills/diagnoses/{session_id}/followups",
            json={"outcome": "worsened", "note": "雨后仍有落果"},
        )
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)

        detail = self.student_client.get(
            f"/api/agri-skills/diagnoses/{session_id}"
        ).get_json()["session"]
        self.assertEqual(
            [item["outcome"] for item in detail["followups"]],
            ["improved", "worsened"],
        )

        self.ai.queue(
            "diagnosis_turn",
            {
                "status": "follow_up_required",
                "question": "复诊后症状范围是否扩大",
                "conclusion": None,
                "limited": False,
            },
        )
        repeated = self.student_client.post(
            f"/api/agri-skills/diagnoses/{session_id}/repeat",
            json={"followup_id": second.get_json()["followup"]["id"]},
        )
        repeated_session = repeated.get_json()["session"]

        self.assertEqual(repeated.status_code, 201)
        self.assertEqual(repeated_session["source_session_id"], session_id)
        self.assertEqual(
            repeated_session["source_followup_id"],
            second.get_json()["followup"]["id"],
        )
        self.assertEqual(repeated_session["product_key"], "litchi")
        self.assertEqual(repeated_session["affected_part"], "fruit")
        self.assertEqual(repeated_session["symptoms"], ["虫蛀", "落果"])
        self.assertEqual(repeated_session["answers"], [])
        self.assertEqual(
            repeated_session["source_context"]["followup_status"],
            "worsened",
        )
        self.assertEqual(
            repeated_session["source_context"]["followup_note"],
            "雨后仍有落果",
        )

        context = next(
            call["context"]
            for call in reversed(self.ai.calls)
            if call["call_point"] == "diagnosis_turn"
        )
        self.assertEqual(context["prior_questions"], [])
        self.assertEqual(context["prior_answers"], [])

    def test_self_test_retries_once_and_discards_two_invalid_results(self):
        valid = self.ai.valid_questions()
        session_id = self._complete_diagnosis()
        self.ai.queue(
            "selftest_generate",
            {"questions": valid[:2]},
            {"questions": valid},
        )
        generated = self.student_client.post(
            f"/api/agri-skills/diagnoses/{session_id}/self-test"
        )

        self.assertEqual(generated.status_code, 201)
        self.assertEqual(
            generated.get_json()["self_test"]["generation_attempts"],
            2,
        )

        second_session_id = self._complete_diagnosis()
        self.ai.queue(
            "selftest_generate",
            {"questions": valid[:2]},
            {"questions": []},
        )
        failed = self.student_client.post(
            f"/api/agri-skills/diagnoses/{second_session_id}/self-test"
        )

        self.assertEqual(failed.status_code, 503)
        self.assertEqual(
            failed.get_json()["message"],
            AI_UNAVAILABLE_MESSAGE,
        )
        with self.app.app_context():
            row = get_db().execute(
                "SELECT COUNT(*) AS count FROM agri_self_tests"
            ).fetchone()
        self.assertEqual(row["count"], 1)

    def test_course_progress_79_80_90_and_invalid_updates(self):
        first = self.student_client.put(
            "/api/agri-skills/courses/1/progress",
            json={"position_seconds": 79, "watched_delta_seconds": 19},
        )
        self.assertEqual(first.status_code, 200)
        self.assertEqual(
            first.get_json()["progress"]["progress_percent"],
            79,
        )
        self.assertIsNone(first.get_json()["progress"]["completed_at"])

        invalid = self.student_client.put(
            "/api/agri-skills/courses/1/progress",
            json={"position_seconds": 101, "watched_delta_seconds": 1},
        )
        self.assertEqual(invalid.status_code, 400)

        second = self.student_client.put(
            "/api/agri-skills/courses/1/progress",
            json={"position_seconds": 80, "watched_delta_seconds": 1},
        )
        self.assertEqual(
            second.get_json()["progress"]["progress_percent"],
            80,
        )
        self.assertIsNotNone(
            second.get_json()["progress"]["completed_at"]
        )

        third = self.student_client.put(
            "/api/agri-skills/courses/1/progress",
            json={"position_seconds": 90, "watched_delta_seconds": 10},
        )
        self.assertEqual(
            third.get_json()["progress"]["progress_percent"],
            90,
        )
        self.assertEqual(
            third.get_json()["progress"]["furthest_position_seconds"],
            90,
        )
        self.assertEqual(
            third.get_json()["progress"]["completed_at"],
            second.get_json()["progress"]["completed_at"],
        )

    def test_recommendations_exclude_completed_and_use_full_sort_chain(self):
        now = "2026-09-15T00:00:00+00:00"
        course_tags = {
            1: [1, 2],
            2: [1],
            3: [1],
            4: [1],
            5: [1],
            6: [1],
            7: [1],
            8: [1],
            9: [1],
            10: [1],
            11: [1, 2],
        }
        with self.app.app_context():
            db = get_db()
            db.executemany(
                """
                INSERT INTO courses (
                    id, title, direction, status, published_at, summary,
                    teacher_name, created_at, updated_at
                )
                VALUES (?, ?, 'agriculture', 'published', ?, '', '林老师', ?, ?)
                """,
                (
                    (
                        course_id,
                        f"课程 {course_id}",
                        "2026-09-01T00:00:00+00:00",
                        now,
                        now,
                    )
                    for course_id in range(2, 12)
                ),
            )
            db.execute(
                """
                UPDATE courses
                SET published_at = '2026-09-02T00:00:00+00:00'
                WHERE id = 7
                """
            )
            db.executemany(
                """
                INSERT INTO student_interest_tags (user_id, tag_id)
                VALUES (?, ?)
                """,
                (
                    (self.student_id, 1),
                    (self.student_id, 2),
                    (self.student_id, 3),
                ),
            )
            db.executemany(
                """
                INSERT INTO course_interest_tags (course_id, tag_id)
                VALUES (?, ?)
                """,
                (
                    (course_id, tag_id)
                    for course_id, tag_ids in course_tags.items()
                    for tag_id in tag_ids
                ),
            )
            progress_rows = [
                (8, 50, "2026-09-07T00:00:00+00:00"),
                (9, 50, "2026-09-07T00:00:00+00:00"),
                (7, 60, "2026-09-06T00:00:00+00:00"),
                (6, 60, "2026-09-06T00:00:00+00:00"),
                (4, 70, "2026-09-05T00:00:00+00:00"),
                (5, 40, "2026-09-05T00:00:00+00:00"),
                (3, 10, "2026-09-04T00:00:00+00:00"),
                (2, 90, "2026-09-03T00:00:00+00:00"),
            ]
            db.executemany(
                """
                INSERT INTO agri_course_progress (
                    user_id, course_id, duration_seconds,
                    furthest_position_seconds, resume_position_seconds,
                    progress_percent, watched_seconds, completed_at,
                    last_viewed_at, updated_at
                )
                VALUES (?, ?, 100, ?, ?, ?, ?, NULL, ?, ?)
                """,
                (
                    (
                        self.student_id,
                        course_id,
                        progress,
                        progress,
                        progress,
                        progress,
                        viewed_at,
                        viewed_at,
                    )
                    for course_id, progress, viewed_at in progress_rows
                ),
            )
            db.execute(
                """
                INSERT INTO agri_course_progress (
                    user_id, course_id, duration_seconds,
                    furthest_position_seconds, resume_position_seconds,
                    progress_percent, watched_seconds, completed_at,
                    last_viewed_at, updated_at
                )
                VALUES (?, 11, 100, 90, 90, 90, 90, ?, ?, ?)
                """,
                (
                    self.student_id,
                    "2026-09-08T00:00:00+00:00",
                    "2026-09-08T00:00:00+00:00",
                    "2026-09-08T00:00:00+00:00",
                ),
            )
            db.commit()
            recommendation_ids = [
                item["id"]
                for item in list_recommendations(self.student_id)
            ]

        self.assertNotIn(11, recommendation_ids)
        self.assertEqual(
            recommendation_ids,
            [1, 8, 9, 7, 6, 4, 5, 3, 2, 10],
        )

    def test_latest_valid_course_quiz_attempt_is_formal(self):
        self._complete_course()
        self.ai.queue(
            "course_quiz_grade",
            {
                "score": 100,
                "questions": [
                    {
                        "id": "q1",
                        "correct": True,
                        "explanation": "回答正确。",
                    }
                ],
            },
            {
                "score": 0,
                "questions": [
                    {
                        "id": "q1",
                        "correct": False,
                        "explanation": "应为正确。",
                    }
                ],
            },
        )
        first = self.student_client.post(
            "/api/agri-skills/courses/1/quiz",
            json={"answers": {"q1": "正确"}},
        )
        second = self.student_client.post(
            "/api/agri-skills/courses/1/quiz",
            json={"answers": {"q1": "错误"}},
        )

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)
        rows = self._attempt_rows()
        self.assertEqual([row["is_formal"] for row in rows], [0, 1])
        self.assertEqual(rows[-1]["score"], 0)

        self.ai.queue(
            "course_quiz_grade",
            AiUnavailableError("upstream unavailable"),
        )
        unavailable = self.student_client.post(
            "/api/agri-skills/courses/1/quiz",
            json={"answers": {"q1": "正确"}},
        )
        self.assertEqual(unavailable.status_code, 503)
        self.assertEqual(
            unavailable.get_json()["message"],
            AI_UNAVAILABLE_MESSAGE,
        )
        self.assertEqual(self._attempt_rows(), rows)

    def test_foreign_resources_return_404_and_ai_payloads_are_allowlisted(self):
        conversation = self.student_client.post(
            "/api/agri-skills/qa/conversations",
            json={"question": "荔枝如何保果", "input_mode": "text"},
        ).get_json()["conversation"]
        answered = self.student_client.post(
            f"/api/agri-skills/qa/conversations/{conversation['id']}/messages",
            json={"question": "荔枝如何保果", "input_mode": "text"},
        )
        self.assertEqual(answered.status_code, 201)

        diagnosis_id = self._complete_diagnosis()
        self.ai.queue(
            "selftest_generate",
            {"questions": self.ai.valid_questions()},
        )
        generated = self.student_client.post(
            f"/api/agri-skills/diagnoses/{diagnosis_id}/self-test"
        ).get_json()["self_test"]
        followup = self.student_client.post(
            f"/api/agri-skills/diagnoses/{diagnosis_id}/followups",
            json={"outcome": "improved", "note": "症状缓解"},
        ).get_json()["followup"]
        self._complete_course()
        course_quiz = self.student_client.post(
            "/api/agri-skills/courses/1/quiz",
            json={"answers": {"q1": "正确"}},
        )
        self.assertEqual(course_quiz.status_code, 201)

        self.assertEqual(
            self.other_client.get(
                f"/api/agri-skills/qa/conversations/{conversation['id']}"
            ).status_code,
            404,
        )
        self.assertEqual(
            self.other_client.get(
                f"/api/agri-skills/diagnoses/{diagnosis_id}"
            ).status_code,
            404,
        )
        self.assertEqual(
            self.other_client.post(
                f"/api/agri-skills/diagnoses/{diagnosis_id}/followups",
                json={"outcome": "worsened"},
            ).status_code,
            404,
        )
        self.assertEqual(
            self.other_client.post(
                f"/api/agri-skills/diagnoses/{diagnosis_id}/repeat",
                json={"followup_id": followup["id"]},
            ).status_code,
            404,
        )
        self.assertEqual(
            self.other_client.post(
                f"/api/agri-skills/self-tests/{generated['id']}/submit",
                json={"answers": {"q1": "正确"}},
            ).status_code,
            404,
        )

        other_progress = self.other_client.get(
            "/api/agri-skills/courses/1/progress"
        ).get_json()["progress"]
        self.assertEqual(other_progress["furthest_position_seconds"], 0)
        self.assertIsNone(other_progress["completed_at"])

        for call in self.ai.calls:
            call_point = call["call_point"]
            self.assertIn(call_point, AI_FIELD_ALLOWLISTS)
            self.assertLessEqual(
                set(call["context"]),
                AI_FIELD_ALLOWLISTS[call_point],
            )
            serialized = json.dumps(call["messages"], ensure_ascii=False)
            self.assertNotIn("student01", serialized)
            self.assertNotIn("password", serialized.lower())
            self.assertNotIn("token", serialized.lower())

        messages = build_ai_messages(
            "qa_answer",
            {
                "question": "荔枝落果怎么办",
                "username": "student01",
                "phone": "13800000000",
                "token": "secret-token",
            },
        )
        serialized = json.dumps(messages, ensure_ascii=False)
        self.assertIn("荔枝落果怎么办", serialized)
        self.assertNotIn("student01", serialized)
        self.assertNotIn("13800000000", serialized)
        self.assertNotIn("secret-token", serialized)


if __name__ == "__main__":
    unittest.main()
