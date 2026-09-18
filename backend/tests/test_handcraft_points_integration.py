import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import app.handcraft_inheritance.points as points_module
from app import create_app
from app.agri_skills.ai_client import set_ai_client
from app.agri_skills.errors import AiUnavailableError
from app.agri_skills.providers import set_course_provider
from app.db import get_db
from app.ecommerce_training.copy_training import (
    create_copy_training,
    generate_optimization_critique,
    generate_revised_copy,
    submit_copy_critique,
)
from app.ecommerce_training.customer_service import (
    end_customer_session,
    start_customer_session,
    submit_customer_reply,
)
from app.ecommerce_training.live_script import generate_live_script
from app.ecommerce_training.simulation import (
    save_simulation_segment,
    score_simulation,
    start_simulation,
)
from app.handcraft_inheritance.active_learning import heartbeat
from app.handcraft_inheritance.ar_guidance import generate_ar_guidance
from app.handcraft_inheritance.course_learning import (
    update_handcraft_course_progress,
)
from app.handcraft_inheritance.crafts import complete_craft_step
from app.handcraft_inheritance.points import (
    get_points_account,
    process_pending_events,
)
from app.handcraft_inheritance.presets import PlaceholderPointsPolicyProvider
from app.handcraft_inheritance.providers import set_points_policy_provider
from app.session_manager import utc_now_iso


def active_segment(
    user_id: int,
    source_type: str,
    source_key: str,
    seconds: int,
    *,
    start_epoch: float = 1000,
) -> str:
    current = heartbeat(
        user_id,
        source_type,
        source_key,
        heartbeat_seq=0,
        now_epoch=start_epoch,
    )
    elapsed = 0
    sequence = 1
    while elapsed < seconds:
        elapsed += min(30, seconds - elapsed)
        current = heartbeat(
            user_id,
            source_type,
            source_key,
            segment_id=current["segment_id"],
            heartbeat_seq=sequence,
            now_epoch=start_epoch + elapsed,
        )
        sequence += 1
    return str(current["segment_id"])


AR_GUIDANCE = {
    "craft_key": "guangxiu",
    "tool_preparation": ["needle"],
    "operating_points": ["steady stitch"],
    "common_errors": ["uneven spacing"],
    "steps": [
        {
            "step_no": 1,
            "title": "start",
            "instruction": "start from the back",
        }
    ],
}
LIVE_SCRIPT = {
    "opening": "opening",
    "product_intro": "product intro",
    "interaction": "interaction",
    "closing": "closing",
}
SIMULATION_SCORES = {
    "scores": {
        "pacing": 80,
        "emotion": 70,
        "interaction": 90,
        "selling_point": 60,
    },
    "suggestions": {
        "pacing": "shorten",
        "emotion": "add feeling",
        "interaction": "ask more",
        "selling_point": "lead with value",
    },
}
COPY_CASE = {
    "copy_text": "generic copy",
    "defect_categories": [
        "missing_key_information",
        "missing_action",
    ],
}
COPY_REFERENCE = {
    "reference_critique": "missing facts",
    "consistency_score": 60,
    "reason": "two defects found",
}
COPY_REVISION = {"revised_copy": "specific copy with action"}
COPY_OPTIMIZATION = {
    "differences": ["added facts", "added action"],
    "optimization_score": 90,
    "evidence": "both issues resolved",
}
CUSTOMER_ANALYSIS = {
    "problem": "did not confirm the order",
    "evidence": "policy explained first",
    "suggestion": "confirm the facts first",
    "criteria": {
        "issue_identified": True,
        "policy_and_process_explained": True,
    },
    "goal_status": "reached",
}
CUSTOMER_SUMMARY = {
    "overall_performance": "adequate",
    "main_problems": ["initial order check"],
    "prioritized_improvements": ["confirm facts"],
    "goal_completion": "complete",
}


class StaticHandcraftCourseProvider:
    def __init__(self):
        self.course = {
            "id": 201,
            "title": "Guangxiu basics",
            "direction": "handcraft",
            "status": "published",
            "summary": "Guangxiu stitch practice",
            "teacher_name": "teacher",
            "published_at": "2026-09-01T00:00:00+00:00",
            "duration_seconds": 1000,
            "tag_ids": [101],
        }

    def list_published_courses(
        self,
        student_id: int,
        direction: str,
    ) -> list[dict]:
        return (
            [copy.deepcopy(self.course)]
            if direction == "handcraft"
            else []
        )

    def get_course(self, course_id: int) -> dict | None:
        return (
            copy.deepcopy(self.course)
            if course_id == self.course["id"]
            else None
        )

    def get_quiz(self, course_id: int) -> dict | None:
        return None


class FailingPointsPolicyProvider:
    def get_policy(self):
        raise RuntimeError("temporary policy outage")


class TestHandcraftPointsIntegration(unittest.TestCase):
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
            cursor = db.execute(
                """
                INSERT INTO users (
                    username, password_hash, name, role, is_enabled,
                    created_at, updated_at
                )
                VALUES (
                    'student01', 'hash', 'student', 'student', 1,
                    '2026-09-18T00:00:00+08:00',
                    '2026-09-18T00:00:00+08:00'
                )
                """
            )
            self.student_id = int(cursor.lastrowid)
            db.execute(
                """
                INSERT INTO courses (
                    id, title, direction, status, duration_seconds,
                    published_at, summary, teacher_name, created_at,
                    updated_at
                )
                VALUES (
                    201, 'Guangxiu basics', 'handcraft', 'published', 1000,
                    '2026-09-01T00:00:00+00:00', 'Guangxiu stitch practice',
                    'teacher', '2026-09-01T00:00:00+00:00',
                    '2026-09-01T00:00:00+00:00'
                )
                """
            )
            db.commit()

        set_course_provider(self.app, StaticHandcraftCourseProvider())
        self.ai = Mock()
        set_ai_client(self.app, self.ai)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _complete_simulation(self) -> dict:
        training = start_simulation(self.student_id, "opening")
        for key, text in (
            ("greeting", "hello"),
            ("hook", "today's product"),
            ("audience_call", "reply one"),
        ):
            save_simulation_segment(
                self.student_id,
                training["id"],
                key,
                text,
            )
        return training

    def _complete_copy_training(self) -> dict:
        self.ai.complete_json.side_effect = [
            COPY_CASE,
            COPY_REFERENCE,
            COPY_REVISION,
            COPY_OPTIMIZATION,
        ]
        session = create_copy_training(
            self.student_id,
            "food",
            "social_commerce",
        )
        submit_copy_critique(
            self.student_id,
            session["id"],
            "missing facts",
        )
        generate_revised_copy(
            self.student_id,
            session["id"],
            "add facts and action",
        )
        generate_optimization_critique(
            self.student_id,
            session["id"],
        )
        self.ai.complete_json.side_effect = None
        return session

    def _complete_customer_sessions(self) -> dict:
        self.ai.complete_json.side_effect = [
            {"customer_message": "I want to return an item"},
            CUSTOMER_ANALYSIS,
            CUSTOMER_SUMMARY,
        ]
        session = start_customer_session(
            self.student_id,
            "after_sales",
        )
        submit_customer_reply(
            self.student_id,
            session["id"],
            "Please provide the order number",
        )
        end_customer_session(
            self.student_id,
            session["id"],
        )
        self.ai.complete_json.side_effect = None
        return session

    def _insert_historical_records(self) -> dict:
        db = get_db()
        now = "2026-09-17T09:00:00+08:00"
        live_cursor = db.execute(
            """
            INSERT INTO ecommerce_live_script_versions (
                user_id, product_name, selling_points_json, price_text,
                style, script_json, is_current, created_at
            )
            VALUES (?, 'historical product', '[]', '', 'enthusiastic',
                    ?, 1, ?)
            """,
            (
                self.student_id,
                json.dumps(LIVE_SCRIPT),
                now,
            ),
        )
        simulation_cursor = db.execute(
            """
            INSERT INTO ecommerce_simulation_trainings (
                user_id, scene_key, segments_json, status, scores_json,
                total_score, created_at, updated_at, completed_at
            )
            VALUES (?, 'opening', '[]', 'completed', ?, 75, ?, ?, ?)
            """,
            (
                self.student_id,
                json.dumps(SIMULATION_SCORES),
                now,
                now,
                now,
            ),
        )
        copy_cursor = db.execute(
            """
            INSERT INTO ecommerce_copy_training_sessions (
                user_id, product_type, scene_key, status, case_json,
                learner_critique, reference_json, optimized_prompt,
                revised_copy, optimization_json, created_at, updated_at,
                completed_at
            )
            VALUES (?, 'food', 'social_commerce', 'completed', ?,
                    'critique', ?, 'prompt', ?, ?, ?, ?, ?)
            """,
            (
                self.student_id,
                json.dumps(COPY_CASE),
                json.dumps(COPY_REFERENCE),
                COPY_REVISION["revised_copy"],
                json.dumps(COPY_OPTIMIZATION),
                now,
                now,
                now,
            ),
        )
        customer_cursor = db.execute(
            """
            INSERT INTO ecommerce_customer_sessions (
                user_id, scenario_key, goal_criteria_json, status,
                end_suggested, confirmed_at, summary_json, created_at,
                updated_at, completed_at
            )
            VALUES (?, 'after_sales', ?, 'completed', 1, ?, ?, ?, ?, ?)
            """,
            (
                self.student_id,
                json.dumps(
                    [
                        "issue_identified",
                        "policy_and_process_explained",
                    ]
                ),
                now,
                json.dumps(CUSTOMER_SUMMARY),
                now,
                now,
                now,
            ),
        )
        db.commit()
        return {
            "live_script": int(live_cursor.lastrowid),
            "simulation": int(simulation_cursor.lastrowid),
            "copy_training": int(copy_cursor.lastrowid),
            "customer_service": int(customer_cursor.lastrowid),
        }

    def _points_state(self) -> tuple[list[dict], list[dict], dict]:
        inbox = [
            dict(row)
            for row in get_db().execute(
                """
                SELECT source_module, event_type, source_event_id,
                       duration_seconds, status
                FROM points_event_inbox
                ORDER BY id
                """
            ).fetchall()
        ]
        ledger = [
            dict(row)
            for row in get_db().execute(
                """
                SELECT transaction_type, source_module, source_event_id,
                       delta, balance_after
                FROM points_transactions
                ORDER BY id
                """
            ).fetchall()
        ]
        return inbox, ledger, get_points_account(self.student_id)

    def test_successful_005_and_004_records_are_written_then_credited(self):
        with self.app.app_context():
            craft_segment = active_segment(
                self.student_id,
                "craft",
                "guangxiu",
                600,
            )
            complete_craft_step(
                self.student_id,
                "guangxiu",
                1,
                craft_segment,
            )

            self.ai.complete_json.return_value = AR_GUIDANCE
            ar_segment = active_segment(
                self.student_id,
                "ar",
                "guangxiu",
                600,
                start_epoch=3000,
            )
            generate_ar_guidance(
                self.student_id,
                "guangxiu",
                "practice",
                ar_segment,
            )

            course_segment = active_segment(
                self.student_id,
                "course",
                "handcraft-course:201",
                600,
                start_epoch=6000,
            )
            update_handcraft_course_progress(
                self.student_id,
                201,
                600,
                course_segment,
            )

            self.ai.complete_json.return_value = LIVE_SCRIPT
            live = generate_live_script(
                self.student_id,
                {
                    "product_name": "product",
                    "selling_points": ["value"],
                    "price_text": "10",
                    "style": "enthusiastic",
                },
            )

            self.ai.complete_json.return_value = SIMULATION_SCORES
            simulation = self._complete_simulation()
            score_simulation(self.student_id, simulation["id"])

            copy_session = self._complete_copy_training()
            customer_session = self._complete_customer_sessions()
            inbox, ledger, account = self._points_state()

        self.assertEqual(account["balance"], 43)
        self.assertEqual(len(inbox), 7)
        self.assertTrue(all(row["status"] == "processed" for row in inbox))
        self.assertEqual(len(ledger), 7)
        self.assertEqual(
            {
                (
                    row["source_module"],
                    row["event_type"],
                    row["source_event_id"],
                )
                for row in inbox
            },
            {
                (
                    "handcraft",
                    "duration",
                    f"guangxiu|1:segment-{craft_segment}",
                ),
                (
                    "handcraft",
                    "duration",
                    f"guangxiu|ar:segment-{ar_segment}",
                ),
                (
                    "handcraft",
                    "duration",
                    (
                        f"handcraft-course:201|segment-{course_segment}:"
                        "settled-600"
                    ),
                ),
                (
                    "ecommerce",
                    "live_script",
                    f"live-script:{live['id']}",
                ),
                (
                    "ecommerce",
                    "simulation",
                    f"simulation:{simulation['id']}",
                ),
                (
                    "ecommerce",
                    "copy_training",
                    f"copy-training:{copy_session['id']}",
                ),
                (
                    "ecommerce",
                    "customer_service",
                    f"customer-service:{customer_session['id']}",
                ),
            },
        )

    def test_failed_or_incomplete_flows_write_no_points(self):
        with self.app.app_context():
            self.ai.complete_json.side_effect = AiUnavailableError(
                "live failed"
            )
            with self.assertRaises(AiUnavailableError):
                generate_live_script(
                    self.student_id,
                    {
                        "product_name": "product",
                        "selling_points": ["value"],
                        "style": "enthusiastic",
                    },
                )

            simulation = self._complete_simulation()
            with self.assertRaises(AiUnavailableError):
                score_simulation(self.student_id, simulation["id"])

            self.ai.complete_json.side_effect = [
                COPY_CASE,
                COPY_REFERENCE,
                COPY_REVISION,
                AiUnavailableError("optimization failed"),
            ]
            copy_session = create_copy_training(
                self.student_id,
                "food",
                "social_commerce",
            )
            submit_copy_critique(
                self.student_id,
                copy_session["id"],
                "missing facts",
            )
            generate_revised_copy(
                self.student_id,
                copy_session["id"],
                "add facts and action",
            )
            with self.assertRaises(AiUnavailableError):
                generate_optimization_critique(
                    self.student_id,
                    copy_session["id"],
                )

            self.ai.complete_json.side_effect = [
                {"customer_message": "I want to return an item"},
                CUSTOMER_ANALYSIS,
                AiUnavailableError("summary failed"),
            ]
            customer_session = start_customer_session(
                self.student_id,
                "after_sales",
            )
            submit_customer_reply(
                self.student_id,
                customer_session["id"],
                "Please provide the order number",
            )
            with self.assertRaises(AiUnavailableError):
                end_customer_session(
                    self.student_id,
                    customer_session["id"],
                )

            inbox, ledger, account = self._points_state()

        self.assertEqual(inbox, [])
        self.assertEqual(ledger, [])
        self.assertEqual(account["balance"], 0)

    def test_historical_004_records_are_not_backfilled(self):
        with self.app.app_context():
            historical = self._insert_historical_records()
            from app.ecommerce_training.copy_training import (
                generate_optimization_critique as repeat_copy,
            )
            from app.ecommerce_training.customer_service import (
                end_customer_session as repeat_customer,
            )
            from app.ecommerce_training.live_script import list_live_scripts
            from app.ecommerce_training.simulation import (
                score_simulation as repeat_simulation,
            )

            list_live_scripts(self.student_id)
            repeat_simulation(
                self.student_id,
                historical["simulation"],
            )
            repeat_copy(
                self.student_id,
                historical["copy_training"],
            )
            repeat_customer(
                self.student_id,
                historical["customer_service"],
            )
            inbox, ledger, account = self._points_state()

        self.ai.complete_json.assert_not_called()
        self.assertEqual(inbox, [])
        self.assertEqual(ledger, [])
        self.assertEqual(account["balance"], 0)

    def test_repeated_successful_records_credit_once(self):
        with self.app.app_context():
            self.ai.complete_json.return_value = LIVE_SCRIPT
            live = generate_live_script(
                self.student_id,
                {
                    "product_name": "product",
                    "selling_points": ["value"],
                    "style": "enthusiastic",
                },
            )

            self.ai.complete_json.return_value = SIMULATION_SCORES
            simulation = self._complete_simulation()
            score_simulation(self.student_id, simulation["id"])

            copy_session = self._complete_copy_training()
            customer_session = self._complete_customer_sessions()

            self.ai.complete_json.reset_mock()
            score_simulation(self.student_id, simulation["id"])
            generate_optimization_critique(
                self.student_id,
                copy_session["id"],
            )
            end_customer_session(
                self.student_id,
                customer_session["id"],
            )
            from app.ecommerce_training.live_script import list_live_scripts

            live_scripts = list_live_scripts(self.student_id)
            inbox, ledger, account = self._points_state()

        self.ai.complete_json.assert_not_called()
        self.assertEqual(
            [script["id"] for script in live_scripts],
            [live["id"]],
        )
        self.assertEqual(account["balance"], 40)
        self.assertEqual(
            [row["event_type"] for row in inbox],
            [
                "live_script",
                "simulation",
                "copy_training",
                "customer_service",
            ],
        )
        self.assertEqual(len(ledger), 4)

    def test_transient_points_rule_failure_keeps_source_and_pending_event(self):
        with self.app.app_context():
            db = get_db()
            db.execute("DELETE FROM points_policy_snapshots")
            db.commit()
            set_points_policy_provider(
                self.app,
                FailingPointsPolicyProvider(),
            )

            simulation = self._complete_simulation()
            self.ai.complete_json.return_value = SIMULATION_SCORES
            result = score_simulation(self.student_id, simulation["id"])
            inbox, ledger, account = self._points_state()

        self.assertEqual(result["status"], "completed")
        self.assertEqual(len(inbox), 1)
        self.assertEqual(inbox[0]["status"], "pending")
        self.assertEqual(ledger, [])
        self.assertEqual(account["balance"], 0)

        set_points_policy_provider(
            self.app,
            PlaceholderPointsPolicyProvider(),
        )
        with self.app.app_context():
            process_pending_events(self.student_id)
            process_pending_events(self.student_id)
            inbox, ledger, account = self._points_state()

        self.assertEqual(inbox[0]["status"], "processed")
        self.assertEqual(account["balance"], 10)
        self.assertEqual(len(ledger), 1)

    def test_processing_exception_keeps_event_retryable_without_duplicates(self):
        with self.app.app_context():
            enqueued = points_module.enqueue_learning_event(
                self.student_id,
                "ecommerce",
                "simulation",
                "retry-simulation",
                utc_now_iso(),
            )
            original_process_event = points_module._process_event

            def process_then_fail(db, event, policy):
                original_process_event(db, event, policy)
                raise RuntimeError("temporary processing failure")

            with patch.object(
                points_module,
                "_process_event",
                side_effect=process_then_fail,
            ):
                first = process_pending_events(self.student_id)
            first_inbox, first_ledger, first_account = self._points_state()
            stored_error = get_db().execute(
                """
                SELECT error
                FROM points_event_inbox
                WHERE id = ?
                """,
                (enqueued["event_id"],),
            ).fetchone()["error"]

            second = process_pending_events(self.student_id)
            inbox, ledger, account = self._points_state()

        self.assertEqual(
            [result["status"] for result in first],
            ["pending"],
        )
        self.assertEqual(stored_error, "temporary processing failure")
        self.assertEqual(first_inbox[0]["status"], "pending")
        self.assertEqual(first_inbox[0]["duration_seconds"], None)
        self.assertEqual(first_ledger, [])
        self.assertEqual(first_account["balance"], 0)
        self.assertEqual(
            [result["status"] for result in second],
            ["processed"],
        )
        self.assertEqual(inbox[0]["status"], "processed")
        self.assertEqual(account["balance"], 10)
        self.assertEqual(
            [
                (
                    row["source_module"],
                    row["source_event_id"],
                    row["delta"],
                )
                for row in ledger
            ],
            [("ecommerce", "retry-simulation", 10)],
        )

    def test_large_course_progress_delta_is_capped_to_one_event(self):
        provider = StaticHandcraftCourseProvider()
        provider.course["duration_seconds"] = 9000
        set_course_provider(self.app, provider)

        with self.app.app_context():
            segment_id = active_segment(
                self.student_id,
                "course",
                "handcraft-course:201",
                7200,
            )
            progress = update_handcraft_course_progress(
                self.student_id,
                201,
                9000,
                segment_id,
            )
            inbox, ledger, account = self._points_state()

        self.assertEqual(progress["watched_seconds"], 7200)
        self.assertEqual(len(inbox), 1)
        self.assertEqual(inbox[0]["status"], "processed")
        self.assertEqual(inbox[0]["duration_seconds"], 7200)
        self.assertEqual(len(ledger), 1)
        self.assertEqual(ledger[0]["delta"], 12)
        self.assertEqual(account["balance"], 12)

    def test_ar_without_active_seconds_creates_no_points_event(self):
        self.ai.complete_json.return_value = AR_GUIDANCE

        with self.app.app_context():
            generate_ar_guidance(
                self.student_id,
                "guangxiu",
                "practice",
            )
            inbox, ledger, account = self._points_state()

        self.assertEqual(inbox, [])
        self.assertEqual(ledger, [])
        self.assertEqual(account["balance"], 0)


if __name__ == "__main__":
    unittest.main()
