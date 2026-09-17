import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from app import create_app
from app.agri_skills.ai_client import set_ai_client
from app.agri_skills.errors import (
    AgriNotFoundError,
    AgriValidationError,
    AiUnavailableError,
)
from app.db import get_db
from app.ecommerce_training.customer_service import (
    end_customer_session,
    generate_next_customer_message,
    get_customer_session,
    list_customer_scenarios,
    list_customer_sessions,
    start_customer_session,
    submit_customer_reply,
)


class TestEcommerceCustomerService(unittest.TestCase):
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
            self.student_id = self._insert_student(db, "student01")
            self.other_student_id = self._insert_student(db, "student02")
            db.commit()

        self.ai = Mock()
        set_ai_client(self.app, self.ai)

    def tearDown(self):
        self.temp_dir.cleanup()

    @staticmethod
    def _insert_student(db, username: str) -> int:
        cursor = db.execute(
            """
            INSERT INTO users (
                username, password_hash, name, role, is_enabled,
                created_at, updated_at
            )
            VALUES (?, ?, ?, 'student', 1, ?, ?)
            """,
            (
                username,
                "test-password-hash",
                username,
                "2026-09-16T00:00:00+00:00",
                "2026-09-16T00:00:00+00:00",
            ),
        )
        return int(cursor.lastrowid)

    @staticmethod
    def _analysis(
        *,
        reached: bool,
        problem: str = "未先确认订单情况",
    ) -> dict:
        return {
            "problem": problem,
            "evidence": "学员直接说明退换政策",
            "suggestion": "先询问订单号和商品状态",
            "criteria": {
                "issue_identified": reached,
                "policy_and_process_explained": True,
            },
            "goal_status": "reached" if reached else "not_reached",
        }

    @staticmethod
    def _summary() -> dict:
        return {
            "overall_performance": "能承接问题",
            "main_problems": ["首次未确认订单"],
            "prioritized_improvements": ["先确认事实", "补充时效"],
            "goal_completion": "两项目标均完成",
        }

    def _start(self, scenario_key: str = "after_sales") -> dict:
        self.ai.complete_json.return_value = {
            "customer_message": "我想咨询退换货，应该怎么处理？"
        }
        with self.app.app_context():
            return start_customer_session(self.student_id, scenario_key)

    def test_lists_exact_five_scenarios_with_observable_criteria(self):
        scenarios = list_customer_scenarios()

        self.assertEqual(
            [item["key"] for item in scenarios],
            [
                "product_info",
                "price_promo",
                "shipping",
                "after_sales",
                "complaint",
            ],
        )
        self.assertEqual(
            [item["label"] for item in scenarios],
            [
                "商品信息咨询",
                "价格优惠咨询",
                "物流时效咨询",
                "售后退换咨询",
                "投诉与情绪安抚",
            ],
        )
        self.assertTrue(
            all(len(item["criteria"]) >= 2 for item in scenarios)
        )
        self.assertEqual(
            scenarios[3]["criteria"],
            ["issue_identified", "policy_and_process_explained"],
        )

    def test_start_generates_opening_and_creates_ordered_first_turn(self):
        session = self._start()

        self.assertEqual(session["status"], "active")
        self.assertFalse(session["end_suggested"])
        self.assertEqual(session["scenario_key"], "after_sales")
        self.assertEqual(
            session["goal_criteria"],
            ["issue_identified", "policy_and_process_explained"],
        )
        self.assertEqual(
            [
                (
                    turn["turn_no"],
                    turn["customer_message"],
                    turn["student_reply"],
                    turn["analysis"],
                )
                for turn in session["turns"]
            ],
            [
                (
                    1,
                    "我想咨询退换货，应该怎么处理？",
                    None,
                    None,
                )
            ],
        )

        call = self.ai.complete_json.call_args
        self.assertEqual(call.kwargs["call_point"], "customer_message_generate")

    def test_start_rejects_invalid_scenario_without_ai(self):
        with self.app.app_context():
            with self.assertRaisesRegex(
                AgriValidationError,
                "客服场景不存在",
            ):
                start_customer_session(self.student_id, "unknown")
            history = list_customer_sessions(self.student_id)

        self.ai.complete_json.assert_not_called()
        self.assertEqual(history, [])

    def test_start_ai_failure_is_exact_and_creates_no_session(self):
        self.ai.complete_json.side_effect = AiUnavailableError("raw error")

        with self.app.app_context():
            with self.assertRaisesRegex(
                AiUnavailableError,
                "^AI 服务暂时不可用$",
            ):
                start_customer_session(self.student_id, "after_sales")
            history = list_customer_sessions(self.student_id)

        self.assertEqual(history, [])

    def test_multiturn_analysis_precedes_next_message_and_goal_suggestion(self):
        self.ai.complete_json.side_effect = [
            {"customer_message": "我想咨询退换货，应该怎么处理？"},
            self._analysis(reached=False),
            {"customer_message": "商品已经拆封，还能退吗？"},
            self._analysis(reached=True),
            self._summary(),
        ]

        with self.app.app_context():
            session = start_customer_session(
                self.student_id,
                "after_sales",
            )
            after_reply = submit_customer_reply(
                self.student_id,
                session["id"],
                "请提供订单号",
            )
            next_turn = generate_next_customer_message(
                self.student_id,
                session["id"],
            )
            reached = submit_customer_reply(
                self.student_id,
                session["id"],
                "拆封后可按规定申请",
            )
            completed = end_customer_session(
                self.student_id,
                session["id"],
            )

        self.assertEqual(after_reply["status"], "active")
        self.assertEqual(
            after_reply["turns"][0]["analysis"]["problem"],
            "未先确认订单情况",
        )
        self.assertEqual(
            [turn["turn_no"] for turn in next_turn["turns"]],
            [1, 2],
        )
        self.assertEqual(
            next_turn["turns"][-1]["customer_message"],
            "商品已经拆封，还能退吗？",
        )
        self.assertIsNone(next_turn["turns"][-1]["student_reply"])
        self.assertEqual(reached["status"], "goal_reached")
        self.assertTrue(reached["end_suggested"])
        self.assertEqual(
            reached["turns"][0]["analysis"]["criteria"],
            {
                "issue_identified": False,
                "policy_and_process_explained": True,
            },
        )
        self.assertEqual(completed["status"], "completed")
        self.assertEqual(completed["summary"], self._summary())
        self.assertTrue(completed["confirmed_at"])
        self.assertTrue(completed["completed_at"])
        self.assertEqual(
            [
                call.kwargs["call_point"]
                for call in self.ai.complete_json.call_args_list
            ],
            [
                "customer_message_generate",
                "customer_reply_analyze",
                "customer_message_generate",
                "customer_reply_analyze",
                "customer_summary",
            ],
        )

    def test_invalid_analysis_is_exact_failure_and_keeps_pending_reply(self):
        invalid_payloads = (
            {},
            {
                **self._analysis(reached=False),
                "problem": " ",
            },
            {
                **self._analysis(reached=False),
                "criteria": {
                    "issue_identified": False,
                },
            },
            {
                **self._analysis(reached=False),
                "criteria": {
                    "issue_identified": False,
                    "policy_and_process_explained": 1,
                },
            },
            {
                **self._analysis(reached=False),
                "goal_status": "maybe",
            },
        )

        with self.app.app_context():
            for payload in invalid_payloads:
                with self.subTest(payload=payload):
                    self.ai.reset_mock()
                    self.ai.complete_json.side_effect = [
                        {"customer_message": "请问需要什么帮助？"},
                        payload,
                    ]
                    session = start_customer_session(
                        self.student_id,
                        "after_sales",
                    )

                    with self.assertRaisesRegex(
                        AiUnavailableError,
                        "^AI 服务暂时不可用$",
                    ):
                        submit_customer_reply(
                            self.student_id,
                            session["id"],
                            "请提供订单号",
                        )

                    loaded = get_customer_session(
                        self.student_id,
                        session["id"],
                    )
                    self.assertEqual(loaded["status"], "active")
                    self.assertFalse(loaded["end_suggested"])
                    self.assertEqual(
                        loaded["turns"][0]["student_reply"],
                        "请提供订单号",
                    )
                    self.assertIsNone(loaded["turns"][0]["analysis"])

    def test_goal_reached_requires_every_criterion_and_reached_status(self):
        payloads = (
            {
                **self._analysis(reached=False),
                "criteria": {
                    "issue_identified": True,
                    "policy_and_process_explained": True,
                },
            },
            {
                **self._analysis(reached=True),
                "criteria": {
                    "issue_identified": True,
                    "policy_and_process_explained": False,
                },
            },
        )

        with self.app.app_context():
            for payload in payloads:
                with self.subTest(payload=payload):
                    self.ai.reset_mock()
                    self.ai.complete_json.side_effect = [
                        {"customer_message": "请问需要什么帮助？"},
                        payload,
                    ]
                    session = start_customer_session(
                        self.student_id,
                        "after_sales",
                    )
                    result = submit_customer_reply(
                        self.student_id,
                        session["id"],
                        "请提供订单号",
                    )

                    self.assertEqual(result["status"], "active")
                    self.assertFalse(result["end_suggested"])

    def test_next_message_requires_analysis_and_is_blocked_after_suggestion(self):
        self.ai.complete_json.return_value = {
            "customer_message": "请问需要什么帮助？"
        }

        with self.app.app_context():
            session = start_customer_session(
                self.student_id,
                "after_sales",
            )
            with self.assertRaises(AgriValidationError):
                generate_next_customer_message(
                    self.student_id,
                    session["id"],
                )

            self.ai.complete_json.side_effect = [
                self._analysis(reached=True),
            ]
            reached = submit_customer_reply(
                self.student_id,
                session["id"],
                "拆封后可按规定申请",
            )
            self.assertTrue(reached["end_suggested"])
            self.ai.complete_json.reset_mock()

            with self.assertRaises(AgriValidationError):
                generate_next_customer_message(
                    self.student_id,
                    session["id"],
                )

        self.ai.complete_json.assert_not_called()

    def test_turn_number_is_not_capped_and_history_stays_ordered(self):
        with self.app.app_context():
            self.ai.complete_json.side_effect = [
                {"customer_message": "客户消息 1"},
                self._analysis(reached=False, problem="问题 1"),
                {"customer_message": "客户消息 2"},
                self._analysis(reached=False, problem="问题 2"),
                {"customer_message": "客户消息 3"},
                self._analysis(reached=False, problem="问题 3"),
                {"customer_message": "客户消息 4"},
                self._analysis(reached=False, problem="问题 4"),
                {"customer_message": "客户消息 5"},
                self._analysis(reached=False, problem="问题 5"),
                {"customer_message": "客户消息 6"},
                self._analysis(reached=False, problem="问题 6"),
            ]
            session = start_customer_session(
                self.student_id,
                "after_sales",
            )
            for turn_no in range(1, 7):
                submit_customer_reply(
                    self.student_id,
                    session["id"],
                    f"学员回复 {turn_no}",
                )
                if turn_no < 6:
                    generate_next_customer_message(
                        self.student_id,
                        session["id"],
                    )

            loaded = get_customer_session(
                self.student_id,
                session["id"],
            )

        self.assertEqual(
            [turn["turn_no"] for turn in loaded["turns"]],
            list(range(1, 7)),
        )
        self.assertEqual(
            [turn["customer_message"] for turn in loaded["turns"]],
            [f"客户消息 {turn_no}" for turn_no in range(1, 7)],
        )
        self.assertEqual(
            [turn["analysis"]["problem"] for turn in loaded["turns"]],
            [f"问题 {turn_no}" for turn_no in range(1, 7)],
        )

    def test_next_message_failure_preserves_transcript(self):
        self.ai.complete_json.side_effect = [
            {"customer_message": "请问需要什么帮助？"},
            self._analysis(reached=False),
            AiUnavailableError("raw error"),
        ]

        with self.app.app_context():
            session = start_customer_session(
                self.student_id,
                "after_sales",
            )
            analyzed = submit_customer_reply(
                self.student_id,
                session["id"],
                "请提供订单号",
            )

            with self.assertRaisesRegex(
                AiUnavailableError,
                "^AI 服务暂时不可用$",
            ):
                generate_next_customer_message(
                    self.student_id,
                    session["id"],
                )

            loaded = get_customer_session(
                self.student_id,
                session["id"],
            )

        self.assertEqual(loaded, analyzed)
        self.assertEqual(len(loaded["turns"]), 1)

    def test_end_requires_suggestion_and_summary_failure_preserves_state(self):
        self.ai.complete_json.side_effect = [
            {"customer_message": "请问需要什么帮助？"},
            self._analysis(reached=False),
        ]

        with self.app.app_context():
            session = start_customer_session(
                self.student_id,
                "after_sales",
            )
            active = submit_customer_reply(
                self.student_id,
                session["id"],
                "请提供订单号",
            )

            with self.assertRaises(AgriValidationError):
                end_customer_session(self.student_id, session["id"])

            self.ai.complete_json.side_effect = [
                {"customer_message": "商品已经拆封，还能退吗？"},
                self._analysis(reached=True),
                AiUnavailableError("raw error"),
            ]
            generate_next_customer_message(
                self.student_id,
                session["id"],
            )
            reached = submit_customer_reply(
                self.student_id,
                session["id"],
                "拆封后可按规定申请",
            )
            with self.assertRaisesRegex(
                AiUnavailableError,
                "^AI 服务暂时不可用$",
            ):
                end_customer_session(self.student_id, session["id"])
            failed = get_customer_session(
                self.student_id,
                session["id"],
            )

        self.assertEqual(active["status"], "active")
        self.assertTrue(reached["end_suggested"])
        self.assertEqual(failed["status"], "goal_reached")
        self.assertTrue(failed["end_suggested"])
        self.assertIsNone(failed["summary"])
        self.assertIsNone(failed["completed_at"])
        self.assertEqual(failed["turns"], reached["turns"])

    def test_summary_requires_exactly_four_nonempty_parts(self):
        invalid_payloads = (
            {
                "overall_performance": "表现",
                "main_problems": ["问题"],
                "prioritized_improvements": ["建议"],
            },
            {
                **self._summary(),
                "goal_completion": "",
            },
            {
                **self._summary(),
                "main_problems": [],
            },
            {
                **self._summary(),
                "extra": "不允许",
            },
        )

        with self.app.app_context():
            for payload in invalid_payloads:
                with self.subTest(payload=payload):
                    self.ai.reset_mock()
                    self.ai.complete_json.side_effect = [
                        {"customer_message": "请问需要什么帮助？"},
                        self._analysis(reached=True),
                        payload,
                    ]
                    session = start_customer_session(
                        self.student_id,
                        "after_sales",
                    )
                    submit_customer_reply(
                        self.student_id,
                        session["id"],
                        "拆封后可按规定申请",
                    )

                    with self.assertRaisesRegex(
                        AiUnavailableError,
                        "^AI 服务暂时不可用$",
                    ):
                        end_customer_session(
                            self.student_id,
                            session["id"],
                        )

                    loaded = get_customer_session(
                        self.student_id,
                        session["id"],
                    )
                    self.assertEqual(loaded["status"], "goal_reached")
                    self.assertIsNone(loaded["summary"])
                    self.assertIsNone(loaded["completed_at"])

    def test_completed_session_is_idempotent(self):
        self.ai.complete_json.side_effect = [
            {"customer_message": "请问需要什么帮助？"},
            self._analysis(reached=True),
            self._summary(),
        ]

        with self.app.app_context():
            session = start_customer_session(
                self.student_id,
                "after_sales",
            )
            submit_customer_reply(
                self.student_id,
                session["id"],
                "拆封后可按规定申请",
            )
            first = end_customer_session(
                self.student_id,
                session["id"],
            )
            self.ai.complete_json.reset_mock()
            second = end_customer_session(
                self.student_id,
                session["id"],
            )

        self.ai.complete_json.assert_not_called()
        self.assertEqual(second, first)

    def test_owner_scope_applies_to_reads_writes_and_history(self):
        self.ai.complete_json.side_effect = [
            {"customer_message": "请问需要什么帮助？"},
            self._analysis(reached=True),
            self._summary(),
        ]

        with self.app.app_context():
            other = start_customer_session(
                self.other_student_id,
                "after_sales",
            )
            submit_customer_reply(
                self.other_student_id,
                other["id"],
                "拆封后可按规定申请",
            )
            end_customer_session(
                self.other_student_id,
                other["id"],
            )
            self.ai.complete_json.reset_mock()

            with self.assertRaises(AgriNotFoundError):
                get_customer_session(self.student_id, other["id"])
            with self.assertRaises(AgriNotFoundError):
                submit_customer_reply(
                    self.student_id,
                    other["id"],
                    "越权回复",
                )
            with self.assertRaises(AgriNotFoundError):
                generate_next_customer_message(
                    self.student_id,
                    other["id"],
                )
            with self.assertRaises(AgriNotFoundError):
                end_customer_session(self.student_id, other["id"])

            self.assertEqual(list_customer_sessions(self.student_id), [])
            self.assertEqual(
                [item["id"] for item in list_customer_sessions(
                    self.other_student_id
                )],
                [other["id"]],
            )

        self.ai.complete_json.assert_not_called()


if __name__ == "__main__":
    unittest.main()
