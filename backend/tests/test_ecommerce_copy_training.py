import json
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
from app.ecommerce_training.copy_training import (
    create_copy_training,
    generate_optimization_critique,
    generate_revised_copy,
    get_copy_training,
    list_copy_trainings,
    submit_copy_critique,
)


CASE_FIXTURE = {
    "copy_text": "这款产品很好，赶紧买。",
    "defect_categories": [
        "missing_key_information",
        "missing_action",
    ],
}
REFERENCE_FIXTURE = {
    "reference_critique": "缺少价格、规格和行动引导。",
    "consistency_score": 67,
    "reason": "命中两个问题，遗漏信任证据。",
}
REVISED_FIXTURE = {
    "revised_copy": "精选荔枝干，净含量 250g，限时 39.9 元，点击下单。",
}
OPTIMIZATION_FIXTURE = {
    "differences": ["补充规格", "补充价格", "增加行动指令"],
    "optimization_score": 88,
    "evidence": "新版包含可验证信息并明确下一步。",
}


class TestEcommerceCopyTraining(unittest.TestCase):
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

    def _create_session(self, user_id: int | None = None) -> dict:
        self.ai.complete_json.return_value = CASE_FIXTURE
        return create_copy_training(
            self.student_id if user_id is None else user_id,
            "food",
            "social_commerce",
        )

    def _advance_to_critique(self) -> dict:
        self.ai.complete_json.side_effect = [
            CASE_FIXTURE,
            REFERENCE_FIXTURE,
        ]
        session = create_copy_training(
            self.student_id,
            "food",
            "social_commerce",
        )
        session = submit_copy_critique(
            self.student_id,
            session["id"],
            "没有规格和下单引导。",
        )
        self.ai.complete_json.side_effect = None
        return session

    def _advance_to_copy(self) -> dict:
        self.ai.complete_json.side_effect = [
            CASE_FIXTURE,
            REFERENCE_FIXTURE,
            REVISED_FIXTURE,
        ]
        session = create_copy_training(
            self.student_id,
            "food",
            "social_commerce",
        )
        submit_copy_critique(
            self.student_id,
            session["id"],
            "没有规格和下单引导。",
        )
        session = generate_revised_copy(
            self.student_id,
            session["id"],
            "写一段荔枝干短文案，包含规格、价格和行动指令",
        )
        self.ai.complete_json.side_effect = None
        return session

    @staticmethod
    def _message_context(call) -> dict:
        return json.loads(call.args[0][1]["content"])

    def test_five_stage_flow_persists_exact_values_and_hides_defects(self):
        self.ai.complete_json.side_effect = [
            CASE_FIXTURE,
            REFERENCE_FIXTURE,
            REVISED_FIXTURE,
            OPTIMIZATION_FIXTURE,
        ]

        with self.app.app_context():
            session = create_copy_training(
                self.student_id,
                " food ",
                " social_commerce ",
            )
            critiqued = submit_copy_critique(
                self.student_id,
                session["id"],
                " 没有规格和下单引导。 ",
            )
            copied = generate_revised_copy(
                self.student_id,
                session["id"],
                " 写一段荔枝干短文案，包含规格、价格和行动指令 ",
            )
            completed = generate_optimization_critique(
                self.student_id,
                session["id"],
            )
            loaded = get_copy_training(self.student_id, session["id"])

        self.assertEqual(session["status"], "case_ready")
        self.assertEqual(session["product_type"], "food")
        self.assertEqual(session["scene"], "social_commerce")
        self.assertEqual(session["case"]["copy_text"], CASE_FIXTURE["copy_text"])
        self.assertTrue(session["case"]["is_teaching_case"])
        self.assertNotIn("defect_categories", session["case"])
        self.assertIsNone(session["learner_critique"])

        self.assertEqual(critiqued["status"], "critique_ready")
        self.assertEqual(
            critiqued["learner_critique"],
            "没有规格和下单引导。",
        )
        self.assertEqual(
            critiqued["case"]["defect_categories"],
            ["missing_action", "missing_key_information"],
        )
        self.assertEqual(critiqued["reference"], REFERENCE_FIXTURE)

        self.assertEqual(copied["status"], "copy_ready")
        self.assertEqual(
            copied["optimized_prompt"],
            "写一段荔枝干短文案，包含规格、价格和行动指令",
        )
        self.assertEqual(copied["revised_copy"], REVISED_FIXTURE["revised_copy"])
        self.assertIsNone(copied["optimization"])

        self.assertEqual(completed["status"], "completed")
        self.assertEqual(completed["optimization"], OPTIMIZATION_FIXTURE)
        self.assertTrue(completed["completed_at"])
        self.assertEqual(loaded, completed)

        calls = self.ai.complete_json.call_args_list
        self.assertEqual(
            [call.kwargs["call_point"] for call in calls],
            [
                "copy_case_generate",
                "copy_reference_critique",
                "copy_revised_generate",
                "copy_optimization_critique",
            ],
        )
        self.assertEqual(
            self._message_context(calls[0]),
            {"product_type": "food", "scene": "social_commerce"},
        )
        self.assertEqual(
            self._message_context(calls[1]),
            {
                "case_text": CASE_FIXTURE["copy_text"],
                "defect_categories": [
                    "missing_action",
                    "missing_key_information",
                ],
                "learner_critique": "没有规格和下单引导。",
            },
        )
        self.assertEqual(
            self._message_context(calls[2]),
            {
                "optimized_prompt": (
                    "写一段荔枝干短文案，包含规格、价格和行动指令"
                ),
                "case_text": CASE_FIXTURE["copy_text"],
            },
        )
        self.assertEqual(
            self._message_context(calls[3]),
            {
                "original_copy": CASE_FIXTURE["copy_text"],
                "revised_copy": REVISED_FIXTURE["revised_copy"],
                "optimized_prompt": (
                    "写一段荔枝干短文案，包含规格、价格和行动指令"
                ),
            },
        )

    def test_state_transitions_reject_skips_and_repeated_steps_before_ai(self):
        self.ai.complete_json.side_effect = [
            CASE_FIXTURE,
            REFERENCE_FIXTURE,
            REVISED_FIXTURE,
            OPTIMIZATION_FIXTURE,
        ]

        with self.app.app_context():
            session = create_copy_training(
                self.student_id,
                "food",
                "social_commerce",
            )

            with self.assertRaisesRegex(
                AgriValidationError,
                "训练步骤不正确",
            ):
                generate_revised_copy(
                    self.student_id,
                    session["id"],
                    "优化提示词",
                )
            with self.assertRaisesRegex(
                AgriValidationError,
                "训练步骤不正确",
            ):
                generate_optimization_critique(
                    self.student_id,
                    session["id"],
                )
            self.assertEqual(self.ai.complete_json.call_count, 1)

            submit_copy_critique(
                self.student_id,
                session["id"],
                "没有规格和下单引导。",
            )
            with self.assertRaisesRegex(
                AgriValidationError,
                "训练步骤不正确",
            ):
                submit_copy_critique(
                    self.student_id,
                    session["id"],
                    "再次提交",
                )
            self.assertEqual(self.ai.complete_json.call_count, 2)

            generate_revised_copy(
                self.student_id,
                session["id"],
                "优化提示词",
            )
            with self.assertRaisesRegex(
                AgriValidationError,
                "训练步骤不正确",
            ):
                generate_revised_copy(
                    self.student_id,
                    session["id"],
                    "再次生成",
                )
            self.assertEqual(self.ai.complete_json.call_count, 3)

            generate_optimization_critique(
                self.student_id,
                session["id"],
            )
            self.ai.complete_json.reset_mock()
            repeated = generate_optimization_critique(
                self.student_id,
                session["id"],
            )

        self.ai.complete_json.assert_not_called()
        self.assertEqual(repeated["status"], "completed")
        self.assertEqual(repeated["optimization"], OPTIMIZATION_FIXTURE)

    def test_blank_inputs_are_rejected_before_ai(self):
        with self.app.app_context():
            for product_type, scene, message in (
                (" ", "social_commerce", "商品类型不能为空"),
                ("food", " ", "训练场景不能为空"),
            ):
                with self.subTest(message=message):
                    with self.assertRaisesRegex(
                        AgriValidationError,
                        message,
                    ):
                        create_copy_training(
                            self.student_id,
                            product_type,
                            scene,
                        )

            session = self._create_session()
            with self.assertRaisesRegex(
                AgriValidationError,
                "学员评判不能为空",
            ):
                submit_copy_critique(
                    self.student_id,
                    session["id"],
                    " ",
                )

        self.assertEqual(self.ai.complete_json.call_count, 1)

    def test_invalid_case_payloads_are_ai_failure_and_create_no_record(self):
        invalid_payloads = (
            None,
            [],
            {},
            {"copy_text": " ", "defect_categories": []},
            {
                "copy_text": "案例",
                "defect_categories": "missing_action",
            },
            {
                "copy_text": "案例",
                "defect_categories": ["missing_action"],
            },
            {
                "copy_text": "案例",
                "defect_categories": ["missing_action", "missing_action"],
            },
            {
                "copy_text": "案例",
                "defect_categories": ["missing_action", "unknown"],
            },
            {
                "copy_text": "案例",
                "defect_categories": ["missing_action", 1],
            },
        )

        with self.app.app_context():
            for payload in invalid_payloads:
                with self.subTest(payload=payload):
                    self.ai.complete_json.return_value = payload
                    with self.assertRaisesRegex(
                        AiUnavailableError,
                        "^AI 服务暂时不可用$",
                    ):
                        create_copy_training(
                            self.student_id,
                            "food",
                            "social_commerce",
                        )
            history = list_copy_trainings(self.student_id)

        self.assertEqual(history, [])

    def test_case_ai_exception_is_exact_and_creates_no_record(self):
        self.ai.complete_json.side_effect = AiUnavailableError(
            "raw provider error"
        )

        with self.app.app_context():
            with self.assertRaisesRegex(
                AiUnavailableError,
                "^AI 服务暂时不可用$",
            ):
                create_copy_training(
                    self.student_id,
                    "food",
                    "social_commerce",
                )
            history = list_copy_trainings(self.student_id)

        self.assertEqual(history, [])

    def test_reference_failure_preserves_case_and_current_critique(self):
        invalid_payloads = (
            {},
            {
                "reference_critique": "参考",
                "consistency_score": True,
                "reason": "理由",
            },
            {
                "reference_critique": "参考",
                "consistency_score": 67.5,
                "reason": "理由",
            },
            {
                "reference_critique": "参考",
                "consistency_score": -1,
                "reason": "理由",
            },
            {
                "reference_critique": "参考",
                "consistency_score": 101,
                "reason": "理由",
            },
            {
                "reference_critique": "参考",
                "consistency_score": 67,
                "reason": " ",
            },
        )

        with self.app.app_context():
            for payload in invalid_payloads:
                with self.subTest(payload=payload):
                    self.ai.complete_json.side_effect = None
                    session = self._create_session()
                    self.ai.complete_json.return_value = payload

                    with self.assertRaisesRegex(
                        AiUnavailableError,
                        "^AI 服务暂时不可用$",
                    ):
                        submit_copy_critique(
                            self.student_id,
                            session["id"],
                            " 没有规格和下单引导。 ",
                        )

                    loaded = get_copy_training(
                        self.student_id,
                        session["id"],
                    )
                    self.assertEqual(loaded["status"], "case_ready")
                    self.assertEqual(
                        loaded["learner_critique"],
                        "没有规格和下单引导。",
                    )
                    self.assertEqual(
                        loaded["case"]["copy_text"],
                        CASE_FIXTURE["copy_text"],
                    )
                    self.assertNotIn(
                        "defect_categories",
                        loaded["case"],
                    )
                    self.assertIsNone(loaded["reference"])

    def test_reference_ai_exception_is_exact_and_keeps_current_critique(self):
        with self.app.app_context():
            session = self._create_session()
            self.ai.complete_json.side_effect = AiUnavailableError(
                "raw provider error"
            )

            with self.assertRaisesRegex(
                AiUnavailableError,
                "^AI 服务暂时不可用$",
            ):
                submit_copy_critique(
                    self.student_id,
                    session["id"],
                    "没有规格和下单引导。",
                )
            loaded = get_copy_training(self.student_id, session["id"])

        self.assertEqual(loaded["status"], "case_ready")
        self.assertEqual(
            loaded["learner_critique"],
            "没有规格和下单引导。",
        )
        self.assertIsNone(loaded["reference"])

    def test_revised_copy_failure_preserves_prior_steps_and_current_prompt(self):
        invalid_payloads = (
            None,
            {},
            {"revised_copy": " "},
            {"revised_copy": 123},
        )

        with self.app.app_context():
            for payload in invalid_payloads:
                with self.subTest(payload=payload):
                    self.ai.complete_json.side_effect = None
                    session = self._advance_to_critique()
                    self.ai.complete_json.return_value = payload

                    with self.assertRaisesRegex(
                        AiUnavailableError,
                        "^AI 服务暂时不可用$",
                    ):
                        generate_revised_copy(
                            self.student_id,
                            session["id"],
                            " 写一段包含规格和价格的文案。 ",
                        )

                    loaded = get_copy_training(
                        self.student_id,
                        session["id"],
                    )
                    self.assertEqual(loaded["status"], "critique_ready")
                    self.assertEqual(
                        loaded["learner_critique"],
                        "没有规格和下单引导。",
                    )
                    self.assertEqual(
                        loaded["reference"],
                        REFERENCE_FIXTURE,
                    )
                    self.assertEqual(
                        loaded["optimized_prompt"],
                        "写一段包含规格和价格的文案。",
                    )
                    self.assertIsNone(loaded["revised_copy"])

    def test_revised_copy_ai_exception_is_exact_and_keeps_prompt(self):
        with self.app.app_context():
            session = self._advance_to_critique()
            self.ai.complete_json.side_effect = AiUnavailableError(
                "raw provider error"
            )

            with self.assertRaisesRegex(
                AiUnavailableError,
                "^AI 服务暂时不可用$",
            ):
                generate_revised_copy(
                    self.student_id,
                    session["id"],
                    "写一段包含规格和价格的文案。",
                )
            loaded = get_copy_training(self.student_id, session["id"])

        self.assertEqual(loaded["status"], "critique_ready")
        self.assertEqual(loaded["reference"], REFERENCE_FIXTURE)
        self.assertEqual(
            loaded["optimized_prompt"],
            "写一段包含规格和价格的文案。",
        )
        self.assertIsNone(loaded["revised_copy"])

    def test_optimization_failure_preserves_completed_chain(self):
        invalid_payloads = (
            None,
            {},
            {
                "differences": [],
                "optimization_score": 88,
                "evidence": "证据",
            },
            {
                "differences": ["补充规格", " "],
                "optimization_score": 88,
                "evidence": "证据",
            },
            {
                "differences": ["补充规格"],
                "optimization_score": True,
                "evidence": "证据",
            },
            {
                "differences": ["补充规格"],
                "optimization_score": 88.5,
                "evidence": "证据",
            },
            {
                "differences": ["补充规格"],
                "optimization_score": 101,
                "evidence": "证据",
            },
            {
                "differences": ["补充规格"],
                "optimization_score": 88,
                "evidence": " ",
            },
        )

        with self.app.app_context():
            for payload in invalid_payloads:
                with self.subTest(payload=payload):
                    self.ai.complete_json.side_effect = None
                    session = self._advance_to_copy()
                    self.ai.complete_json.return_value = payload

                    with self.assertRaisesRegex(
                        AiUnavailableError,
                        "^AI 服务暂时不可用$",
                    ):
                        generate_optimization_critique(
                            self.student_id,
                            session["id"],
                        )

                    loaded = get_copy_training(
                        self.student_id,
                        session["id"],
                    )
                    self.assertEqual(loaded["status"], "copy_ready")
                    self.assertEqual(
                        loaded["learner_critique"],
                        "没有规格和下单引导。",
                    )
                    self.assertEqual(
                        loaded["reference"],
                        REFERENCE_FIXTURE,
                    )
                    self.assertEqual(
                        loaded["optimized_prompt"],
                        "写一段荔枝干短文案，包含规格、价格和行动指令",
                    )
                    self.assertEqual(
                        loaded["revised_copy"],
                        REVISED_FIXTURE["revised_copy"],
                    )
                    self.assertIsNone(loaded["optimization"])
                    self.assertIsNone(loaded["completed_at"])

    def test_optimization_ai_exception_is_exact_and_keeps_revised_copy(self):
        with self.app.app_context():
            session = self._advance_to_copy()
            self.ai.complete_json.side_effect = AiUnavailableError(
                "raw provider error"
            )

            with self.assertRaisesRegex(
                AiUnavailableError,
                "^AI 服务暂时不可用$",
            ):
                generate_optimization_critique(
                    self.student_id,
                    session["id"],
                )
            loaded = get_copy_training(self.student_id, session["id"])

        self.assertEqual(loaded["status"], "copy_ready")
        self.assertEqual(
            loaded["revised_copy"],
            REVISED_FIXTURE["revised_copy"],
        )
        self.assertIsNone(loaded["optimization"])
        self.assertIsNone(loaded["completed_at"])

    def test_ownership_is_enforced_on_reads_and_every_write_step(self):
        self.ai.complete_json.return_value = CASE_FIXTURE

        with self.app.app_context():
            session = create_copy_training(
                self.other_student_id,
                "food",
                "social_commerce",
            )

            with self.assertRaises(AgriNotFoundError):
                get_copy_training(self.student_id, session["id"])
            with self.assertRaises(AgriNotFoundError):
                submit_copy_critique(
                    self.student_id,
                    session["id"],
                    "越权评判",
                )
            with self.assertRaises(AgriNotFoundError):
                generate_revised_copy(
                    self.student_id,
                    session["id"],
                    "越权提示词",
                )
            with self.assertRaises(AgriNotFoundError):
                generate_optimization_critique(
                    self.student_id,
                    session["id"],
                )

            self.assertEqual(list_copy_trainings(self.student_id), [])
            owner_view = get_copy_training(
                self.other_student_id,
                session["id"],
            )

        self.assertEqual(self.ai.complete_json.call_count, 1)
        self.assertEqual(owner_view["status"], "case_ready")
        self.assertIsNone(owner_view["learner_critique"])

    def test_history_is_owner_scoped_and_newest_first(self):
        with self.app.app_context():
            self.ai.complete_json.return_value = CASE_FIXTURE
            first = create_copy_training(
                self.student_id,
                "food",
                "social_commerce",
            )
            second = create_copy_training(
                self.student_id,
                "craft",
                "product_page",
            )
            other = create_copy_training(
                self.other_student_id,
                "food",
                "live_room",
            )
            history = list_copy_trainings(self.student_id)

        self.assertEqual(
            [session["id"] for session in history],
            [second["id"], first["id"]],
        )
        self.assertNotIn(
            other["id"],
            [session["id"] for session in history],
        )

    def test_missing_session_raises_not_found(self):
        with self.app.app_context():
            with self.assertRaises(AgriNotFoundError):
                get_copy_training(self.student_id, 999999)
            with self.assertRaises(AgriNotFoundError):
                submit_copy_critique(
                    self.student_id,
                    999999,
                    "评判",
                )

        self.ai.complete_json.assert_not_called()


if __name__ == "__main__":
    unittest.main()
