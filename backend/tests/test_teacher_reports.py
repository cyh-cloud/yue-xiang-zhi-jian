import json
import re
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock
from zoneinfo import ZoneInfo

from app import create_app
from app.agri_skills.ai_client import set_ai_client
from app.agri_skills.errors import AiUnavailableError
from app.content_review import set_content_review_provider
from app.db import get_db
from app.teacher_console.dashboard import build_teacher_dashboard
from app.teacher_console.errors import (
    ProviderNotFoundError,
    ProviderUnavailableError,
)
from app.teacher_console.reports import (
    generate_teacher_report,
    get_teacher_report,
    list_teacher_reports,
)


SHANGHAI = ZoneInfo("Asia/Shanghai")


class TestTeacherReports(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(Path(self.temp_dir.name) / "test.db"),
                "SECRET_KEY": "test-only-secret",
            }
        )
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.ai = Mock()
        set_ai_client(self.app, self.ai)
        self.teacher_id = 1
        self._seed_users()
        self.ai.complete_json.return_value = {
            "progress_analysis": "整体进度稳定",
            "direction_comparison": "农业方向领先",
            "risk_warning": "1 名学员连续 30 天零进度",
        }

    def tearDown(self):
        self.app_context.pop()
        self.temp_dir.cleanup()

    def _seed_users(self):
        now = self._now()
        db = get_db()
        db.executemany(
            """
            INSERT INTO users (
                id, username, password_hash, name, role, is_enabled,
                created_at, updated_at
            )
            VALUES (?, ?, 'test-hash', ?, ?, ?, ?, ?)
            """,
            (
                (1, "teacher01", "教师甲", "teacher", 1, now, now),
                (2, "student02", "姓名学员乙", "student", 1, now, now),
                (3, "student03", "姓名学员丙", "student", 1, now, now),
                (4, "student04", "姓名学员丁", "student", 1, now, now),
                (5, "student05", "停用学员", "student", 0, now, now),
                (6, "teacher06", "教师己", "teacher", 1, now, now),
            ),
        )
        db.executemany(
            """
            INSERT INTO student_profiles (
                user_id, contact, learning_direction, updated_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                (2, "13800000002", "agriculture", now),
                (3, "13800000003", "ecommerce", now),
                (4, "13800000004", "comprehensive", now),
                (5, "13800000005", "agriculture", now),
            ),
        )
        db.commit()

    def _insert_student(self, user_id, direction):
        now = self._now()
        db = get_db()
        db.execute(
            """
            INSERT INTO users (
                id, username, password_hash, name, role, is_enabled,
                created_at, updated_at
            )
            VALUES (?, ?, 'test-hash', ?, 'student', 1, ?, ?)
            """,
            (user_id, f"student{user_id:02d}", f"姓名学员{user_id}", now, now),
        )
        db.execute(
            """
            INSERT INTO student_profiles (
                user_id, contact, learning_direction, updated_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (user_id, f"1380000{user_id:04d}", direction, now),
        )

    def _insert_published_course(self):
        now = self._now()
        db = get_db()
        db.execute(
            """
            INSERT INTO courses (
                id, title, direction, status, duration_seconds, media_url,
                published_at, summary, teacher_name, teacher_id, version,
                media_source_type, content_tags_json, rejection_opinion,
                submitted_at, created_at, updated_at
            )
            VALUES (
                1, '教师农业课程', 'agriculture', 'pending', 300, ?, NULL,
                '聚合课程', '教师甲', ?, 1, 'external_url', '[]',
                NULL, NULL, ?, ?
            )
            """,
            (
                "https://media.example.test/1.mp4",
                self.teacher_id,
                now,
                now,
            ),
        )

    def _enable_teacher_course_review(self):
        class ReviewProvider:
            def get_review_status(self, *, content_type, content_id):
                if content_type != "course_video" or content_id != "1":
                    return None
                return {
                    "content_type": content_type,
                    "content_id": content_id,
                    "review_status": "approved",
                    "version": 1,
                    "rejection_opinion": None,
                    "published_at": "2026-09-19T10:00:00+08:00",
                    "created_at": "2026-09-19T09:00:00+08:00",
                    "updated_at": "2026-09-19T10:00:00+08:00",
                }

        set_content_review_provider(self.app, ReviewProvider())

    def _insert_course_progress(self, user_id, updated_at, progress_percent):
        get_db().execute(
            """
            INSERT INTO agri_course_progress (
                user_id, course_id, duration_seconds,
                furthest_position_seconds, resume_position_seconds,
                progress_percent, watched_seconds, completed_at,
                last_viewed_at, updated_at
            )
            VALUES (?, 1, 300, 0, 0, ?, 0, NULL, ?, ?)
            """,
            (
                user_id,
                progress_percent,
                updated_at,
                updated_at,
            ),
        )

    def _insert_quiz_attempt(self, user_id, created_at):
        get_db().execute(
            """
            INSERT INTO agri_course_quiz_attempts (
                user_id, course_id, answers_json, result_json, score,
                is_formal, created_at
            )
            VALUES (?, 1, '{}', '{}', 80, 1, ?)
            """,
            (user_id, created_at),
        )

    def _insert_agri_self_test_outcome(self, user_id, created_at):
        db = get_db()
        cursor = db.execute(
            """
            INSERT INTO agri_diagnosis_sessions (
                user_id, product_key, affected_part, symptoms_json, status,
                round_count, created_at, updated_at
            )
            VALUES (?, 'litchi', 'leaf', '[]', 'completed', 1, ?, ?)
            """,
            (user_id, created_at, created_at),
        )
        self_test_id = db.execute(
            """
            INSERT INTO agri_self_tests (
                diagnosis_session_id, questions_json, created_at
            )
            VALUES (?, '[]', ?)
            """,
            (cursor.lastrowid, created_at),
        ).lastrowid
        db.execute(
            """
            INSERT INTO agri_self_test_attempts (
                self_test_id, user_id, answers_json, result_json, score,
                created_at
            )
            VALUES (?, ?, '{}', '{}', 80, ?)
            """,
            (self_test_id, user_id, created_at),
        )

    def _insert_handcraft_outcome(self, user_id, created_at):
        get_db().execute(
            """
            INSERT INTO handcraft_learning_outcomes (
                user_id, outcome_type, source_key, source_id, created_at,
                source_available, summary, score, is_formal, archive_written
            )
            VALUES (?, 'craft', 'guangxiu', 1, ?, 1, '完成广绣练习', 80, 1, 0)
            """,
            (user_id, created_at),
        )

    def _insert_live_script(self, user_id, created_at):
        get_db().execute(
            """
            INSERT INTO ecommerce_live_script_versions (
                user_id, product_name, selling_points_json, price_text,
                style, script_json, is_current, created_at
            )
            VALUES (?, '荔枝', '[]', '10 元', 'enthusiastic', '{}', 1, ?)
            """,
            (user_id, created_at),
        )

    def _insert_simulation(self, user_id, completed_at):
        get_db().execute(
            """
            INSERT INTO ecommerce_simulation_trainings (
                user_id, scene_key, segments_json, status, scores_json,
                total_score, created_at, updated_at, completed_at
            )
            VALUES (
                ?, 'live_room', '[]', 'completed', '[]', 80, ?, ?, ?
            )
            """,
            (user_id, completed_at, completed_at, completed_at),
        )

    def _insert_copy_session(self, user_id, completed_at):
        get_db().execute(
            """
            INSERT INTO ecommerce_copy_training_sessions (
                user_id, product_type, scene_key, status, case_json,
                created_at, updated_at, completed_at
            )
            VALUES (
                ?, 'agriculture', 'product_detail', 'completed', '{}', ?, ?, ?
            )
            """,
            (user_id, completed_at, completed_at, completed_at),
        )

    def _insert_customer_session(self, user_id, completed_at):
        get_db().execute(
            """
            INSERT INTO ecommerce_customer_sessions (
                user_id, scenario_key, goal_criteria_json, status,
                created_at, updated_at, completed_at
            )
            VALUES (
                ?, 'after_sale', '[]', 'completed', ?, ?, ?
            )
            """,
            (user_id, completed_at, completed_at, completed_at),
        )

    def _insert_store_plan(self, user_id, created_at):
        get_db().execute(
            """
            INSERT INTO ecommerce_store_plans (
                user_id, store_type, platform, style_preference,
                plan_json, created_at
            )
            VALUES (?, 'individual', 'douyin', 'professional', '{}', ?)
            """,
            (user_id, created_at),
        )

    @staticmethod
    def _now():
        return datetime.now(SHANGHAI).isoformat(timespec="seconds")

    @staticmethod
    def _at(days):
        return (
            datetime.now(SHANGHAI) + timedelta(days=days)
        ).isoformat(timespec="seconds")

    def test_report_contains_three_sections_and_persists(self):
        report = generate_teacher_report(self.teacher_id)

        self.assertRegex(report["report_id"], r"^report-[0-9a-f]{32}$")
        self.assertEqual(report["teacher_id"], self.teacher_id)
        self.assertTrue(report["created_at"].endswith("+08:00"))
        self.assertEqual(
            set(report["sections"]),
            {
                "progress_analysis",
                "direction_comparison",
                "risk_warning",
            },
        )
        self.assertEqual(
            report["sections"],
            self.ai.complete_json.return_value,
        )
        self.assertEqual(
            get_teacher_report(
                self.teacher_id,
                report["report_id"],
            ),
            report,
        )
        self.assertEqual(
            list_teacher_reports(self.teacher_id),
            [report],
        )

        row = get_db().execute(
            """
            SELECT teacher_id, sections_json, stats_snapshot_json, created_at
            FROM teacher_learning_reports
            WHERE report_id = ?
            """,
            (report["report_id"],),
        ).fetchone()
        self.assertEqual(row["teacher_id"], self.teacher_id)
        self.assertEqual(
            json.loads(row["sections_json"]),
            self.ai.complete_json.return_value,
        )
        self.assertEqual(
            json.loads(row["stats_snapshot_json"]),
            report["stats_snapshot"],
        )
        self.assertEqual(row["created_at"], report["created_at"])

        call = self.ai.complete_json.call_args
        self.assertEqual(
            call.kwargs["call_point"],
            "teacher_learning_report_generate",
        )
        context = json.loads(call.args[0][1]["content"])
        self.assertEqual(
            set(context),
            {
                "aggregate_stats",
                "direction_comparison",
                "risk_summary",
            },
        )
        self.assertEqual(
            context["aggregate_stats"],
            {
                "student_total": 3,
                "average_progress": 0.0,
                "completion_rate": 0.0,
                "quiz_attempt_count": 0,
                "quiz_average_score": 0.0,
            },
        )
        self.assertEqual(
            context["risk_summary"],
            {
                "student_count": 3,
                "at_risk_count": 3,
                "at_risk_ratio": 100.0,
                "directions": {
                    "agriculture": {
                        "student_count": 1,
                        "at_risk_count": 1,
                        "at_risk_ratio": 100.0,
                    },
                    "ecommerce": {
                        "student_count": 1,
                        "at_risk_count": 1,
                        "at_risk_ratio": 100.0,
                    },
                    "handcraft": {
                        "student_count": 0,
                        "at_risk_count": 0,
                        "at_risk_ratio": 0.0,
                    },
                    "comprehensive": {
                        "student_count": 1,
                        "at_risk_count": 1,
                        "at_risk_ratio": 100.0,
                    },
                },
            },
        )

    def test_ai_failure_does_not_break_dashboard_or_saved_reports(self):
        saved = generate_teacher_report(self.teacher_id)
        self.ai.complete_json.side_effect = AiUnavailableError("down")

        with self.assertRaisesRegex(
            ProviderUnavailableError,
            "AI 服务暂时不可用",
        ) as raised:
            generate_teacher_report(self.teacher_id)

        self.assertEqual(raised.exception.code, "ai_unavailable")
        self.assertEqual(raised.exception.details, {})
        self.assertEqual(
            build_teacher_dashboard(self.teacher_id)["student_total"],
            3,
        )
        self.assertEqual(
            list_teacher_reports(self.teacher_id),
            [saved],
        )
        self.assertEqual(
            get_db().execute(
                "SELECT COUNT(*) AS count FROM teacher_learning_reports"
            ).fetchone()["count"],
            1,
        )

    def test_invalid_report_sections_are_provider_errors(self):
        invalid_payloads = (
            None,
            {},
            {"progress_analysis": "only one"},
            {
                "progress_analysis": "有效",
                "direction_comparison": "  ",
                "risk_warning": "有效",
            },
            {
                "progress_analysis": "有效",
                "direction_comparison": ["not", "text"],
                "risk_warning": "有效",
            },
        )

        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                self.ai.complete_json.return_value = payload
                with self.assertRaisesRegex(
                    ProviderUnavailableError,
                    "AI 服务暂时不可用",
                ) as raised:
                    generate_teacher_report(self.teacher_id)
                self.assertEqual(raised.exception.code, "ai_unavailable")
                self.assertEqual(raised.exception.details, {})

        self.assertEqual(
            get_db().execute(
                "SELECT COUNT(*) AS count FROM teacher_learning_reports"
            ).fetchone()["count"],
            0,
        )

    def test_risk_summary_uses_latest_activity_and_completion_override(self):
        now = datetime.now(SHANGHAI)
        recent = (now - timedelta(days=10)).isoformat(timespec="seconds")
        old = (now - timedelta(days=31)).isoformat(timespec="seconds")
        recent_z = (
            now - timedelta(days=5)
        ).astimezone(ZoneInfo("UTC")).isoformat(timespec="seconds").replace(
            "+00:00",
            "Z",
        )

        for user_id, direction in (
            (10, "agriculture"),
            (11, "agriculture"),
            (12, "agriculture"),
            (13, "agriculture"),
            (14, "ecommerce"),
            (15, "ecommerce"),
            (16, "handcraft"),
            (17, "handcraft"),
            (18, "comprehensive"),
            (19, "comprehensive"),
        ):
            self._insert_student(user_id, direction)
        self._insert_published_course()
        self._enable_teacher_course_review()

        for user_id in range(10, 17):
            self._insert_course_progress(user_id, recent, 10)

        self._insert_course_progress(2, recent, 10)
        self._insert_quiz_attempt(2, old)
        self._insert_quiz_attempt(3, recent_z)
        self._insert_agri_self_test_outcome(10, recent)
        self._insert_handcraft_outcome(11, recent)
        self._insert_live_script(12, recent)
        self._insert_simulation(13, recent)
        self._insert_copy_session(14, recent)
        self._insert_customer_session(15, recent)
        self._insert_store_plan(16, recent)
        self._insert_course_progress(17, old, 85)
        self._insert_quiz_attempt(18, old)
        self._insert_quiz_attempt(19, old)
        self._insert_course_progress(19, recent, 10)
        get_db().commit()

        report = generate_teacher_report(self.teacher_id)
        risk = report["stats_snapshot"]["risk_summary"]

        self.assertEqual(risk["student_count"], 13)
        self.assertEqual(risk["at_risk_count"], 2)
        self.assertEqual(risk["at_risk_ratio"], 15.38)
        self.assertEqual(
            risk["directions"]["agriculture"]["at_risk_count"],
            0,
        )
        self.assertEqual(
            risk["directions"]["ecommerce"]["at_risk_count"],
            0,
        )
        self.assertEqual(
            risk["directions"]["handcraft"]["at_risk_count"],
            0,
        )
        self.assertEqual(
            risk["directions"]["comprehensive"]["at_risk_count"],
            2,
        )

    def test_ai_input_and_snapshot_exclude_identity_and_profile_fields(self):
        report = generate_teacher_report(self.teacher_id)
        context_text = self.ai.complete_json.call_args.args[0][1]["content"]
        snapshot_text = json.dumps(
            report["stats_snapshot"],
            ensure_ascii=False,
        )

        for serialized in (context_text, snapshot_text):
            self.assertNotIn("姓名", serialized)
            self.assertNotIn("student02", serialized)
            self.assertNotIn("138000000", serialized)
            self.assertNotIn('"user_id"', serialized)
            self.assertNotIn('"student_id"', serialized)
            self.assertNotIn('"teacher_id"', serialized)
            self.assertNotIn('"contact"', serialized)
            self.assertNotIn('"profile"', serialized)
            self.assertNotIn('"username"', serialized)

    def test_reports_are_teacher_scoped_and_newest_first(self):
        first = generate_teacher_report(self.teacher_id)
        self.ai.complete_json.return_value = {
            "progress_analysis": "第二次进度分析",
            "direction_comparison": "第二次方向对比",
            "risk_warning": "第二次风险预警",
        }
        second = generate_teacher_report(self.teacher_id)
        other = generate_teacher_report(6)

        self.assertEqual(
            list_teacher_reports(self.teacher_id),
            [second, first],
        )
        self.assertEqual(list_teacher_reports(6), [other])
        with self.assertRaises(ProviderNotFoundError) as raised:
            get_teacher_report(self.teacher_id, other["report_id"])
        self.assertEqual(raised.exception.code, "report_not_found")
        self.assertEqual(
            raised.exception.details,
            {"report_id": other["report_id"]},
        )


if __name__ == "__main__":
    unittest.main()
