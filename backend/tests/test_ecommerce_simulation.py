import tempfile
import threading
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
from app.ecommerce_training.simulation import (
    get_simulation,
    list_simulation_scenes,
    list_simulations,
    save_simulation_segment,
    score_simulation,
    start_simulation,
)


class TestEcommerceSimulation(unittest.TestCase):
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
        self.segments = {
            "greeting": "欢迎来到直播间。",
            "hook": "今天介绍广东荔枝干。",
            "audience_call": "想了解的扣一。",
        }

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

    def _complete_training(self) -> dict:
        training = start_simulation(self.student_id, "opening")
        for key, text in self.segments.items():
            save_simulation_segment(
                self.student_id,
                training["id"],
                key,
                text,
            )
        return get_simulation(self.student_id, training["id"])

    @staticmethod
    def _score_fixture() -> dict:
        return {
            "scores": {
                "pacing": 80,
                "emotion": 72,
                "interaction": 90,
                "selling_point": 66,
            },
            "suggestions": {
                "pacing": "缩短长句。",
                "emotion": "增加情绪词。",
                "interaction": "增加提问。",
                "selling_point": "先讲核心利益。",
            },
        }

    def test_lists_exact_ordered_scenes_and_segments(self):
        scenes = list_simulation_scenes()

        self.assertEqual(
            [scene["key"] for scene in scenes],
            [
                "opening",
                "product_intro",
                "interaction",
                "closing",
                "objection",
            ],
        )
        self.assertEqual(
            [
                (
                    scene["key"],
                    scene["label"],
                    [
                        (segment["key"], segment["label"])
                        for segment in scene["segments"]
                    ],
                )
                for scene in scenes
            ],
            [
                (
                    "opening",
                    "开场白",
                    [
                        ("greeting", "问候"),
                        ("hook", "引题"),
                        ("audience_call", "聚人"),
                    ],
                ),
                (
                    "product_intro",
                    "产品介绍",
                    [
                        ("core_value", "核心卖点"),
                        ("use_case", "使用场景"),
                        ("proof", "信任证明"),
                    ],
                ),
                (
                    "interaction",
                    "互动引导",
                    [
                        ("question", "提问"),
                        ("poll", "投票"),
                        ("response_prompt", "回应引导"),
                    ],
                ),
                (
                    "closing",
                    "促单话术",
                    [
                        ("offer", "利益点"),
                        ("urgency", "紧迫感"),
                        ("call_to_action", "行动指令"),
                    ],
                ),
                (
                    "objection",
                    "异议处理",
                    [
                        ("acknowledge", "承接异议"),
                        ("clarify", "澄清问题"),
                        ("evidence", "证据回应"),
                        ("close", "再次促单"),
                    ],
                ),
            ],
        )

    def test_start_and_save_keep_ordered_segments(self):
        with self.app.app_context():
            training = start_simulation(self.student_id, "opening")
            for key, text in self.segments.items():
                saved = save_simulation_segment(
                    self.student_id,
                    training["id"],
                    key,
                    f"  {text}  ",
                )
            loaded = get_simulation(self.student_id, training["id"])

        self.assertEqual(training["status"], "draft")
        self.assertEqual(
            [segment["key"] for segment in training["segments"]],
            ["greeting", "hook", "audience_call"],
        )
        self.assertEqual(saved, loaded)
        self.assertEqual(
            [segment["text"] for segment in loaded["segments"]],
            list(self.segments.values()),
        )
        self.assertIsNone(loaded["scores"])
        self.assertIsNone(loaded["total_score"])

    def test_save_rejects_missing_training_segment_and_blank_text(self):
        with self.app.app_context():
            training = start_simulation(self.student_id, "opening")

            with self.assertRaisesRegex(
                AgriValidationError,
                "模拟环节不存在",
            ):
                save_simulation_segment(
                    self.student_id,
                    training["id"],
                    "unknown",
                    "内容",
                )
            with self.assertRaisesRegex(
                AgriValidationError,
                "环节内容不能为空",
            ):
                save_simulation_segment(
                    self.student_id,
                    training["id"],
                    "greeting",
                    "   ",
                )
            with self.assertRaises(AgriNotFoundError):
                save_simulation_segment(
                    self.student_id,
                    999999,
                    "greeting",
                    "内容",
                )

    def test_submitted_segment_cannot_be_changed(self):
        with self.app.app_context():
            training = start_simulation(self.student_id, "opening")
            save_simulation_segment(
                self.student_id,
                training["id"],
                "greeting",
                "第一次提交",
            )

            with self.assertRaisesRegex(
                AgriValidationError,
                "该环节已提交",
            ):
                save_simulation_segment(
                    self.student_id,
                    training["id"],
                    "greeting",
                    "尝试修改",
                )

            loaded = get_simulation(self.student_id, training["id"])

        self.assertEqual(loaded["segments"][0]["text"], "第一次提交")

    def test_concurrent_saves_for_different_segments_keep_both(self):
        with self.app.app_context():
            training = start_simulation(self.student_id, "opening")

        barrier = threading.Barrier(2)
        errors = []

        def save_segment(segment_key: str, text: str):
            try:
                with self.app.app_context():
                    barrier.wait()
                    save_simulation_segment(
                        self.student_id,
                        training["id"],
                        segment_key,
                        text,
                    )
            except BaseException as error:
                errors.append(error)

        threads = [
            threading.Thread(
                target=save_segment,
                args=("greeting", "并发提交的问候"),
            ),
            threading.Thread(
                target=save_segment,
                args=("hook", "并发提交的引题"),
            ),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(errors, [])
        with self.app.app_context():
            loaded = get_simulation(self.student_id, training["id"])

        self.assertEqual(
            [segment["text"] for segment in loaded["segments"]],
            ["并发提交的问候", "并发提交的引题", ""],
        )

    def test_scores_every_segment_and_calculates_equal_weight_total(self):
        self.ai.complete_json.return_value = self._score_fixture()

        with self.app.app_context():
            draft = self._complete_training()
            result = score_simulation(self.student_id, draft["id"])
            loaded = get_simulation(self.student_id, draft["id"])

        self.assertEqual(result["total_score"], 77)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(
            result["scores"],
            {
                "pacing": 80,
                "emotion": 72,
                "interaction": 90,
                "selling_point": 66,
            },
        )
        self.assertEqual(
            result["suggestions"],
            self._score_fixture()["suggestions"],
        )
        self.assertTrue(result["completed_at"])
        self.assertEqual(loaded, result)

        call = self.ai.complete_json.call_args
        self.assertEqual(call.kwargs["call_point"], "simulation_score")
        self.assertEqual(
            [segment["key"] for segment in loaded["segments"]],
            ["greeting", "hook", "audience_call"],
        )

    def test_incomplete_training_cannot_be_scored_and_keeps_draft(self):
        with self.app.app_context():
            training = start_simulation(self.student_id, "opening")
            save_simulation_segment(
                self.student_id,
                training["id"],
                "greeting",
                "欢迎来到直播间。",
            )

            with self.assertRaisesRegex(
                AgriValidationError,
                "请完成全部训练环节",
            ):
                score_simulation(self.student_id, training["id"])

            loaded = get_simulation(self.student_id, training["id"])

        self.ai.complete_json.assert_not_called()
        self.assertEqual(loaded["status"], "draft")
        self.assertIsNone(loaded["scores"])
        self.assertIsNone(loaded["total_score"])
        self.assertEqual(loaded["segments"][0]["text"], "欢迎来到直播间。")

    def test_invalid_dimension_or_suggestion_is_ai_failure_without_completion(self):
        invalid_payloads = (
            {},
            {
                "scores": {
                    "pacing": 80,
                    "emotion": 72,
                    "interaction": 90,
                },
                "suggestions": self._score_fixture()["suggestions"],
            },
            {
                "scores": {
                    **self._score_fixture()["scores"],
                    "interaction": 90.5,
                },
                "suggestions": self._score_fixture()["suggestions"],
            },
            {
                "scores": {
                    **self._score_fixture()["scores"],
                    "selling_point": 101,
                },
                "suggestions": self._score_fixture()["suggestions"],
            },
            {
                "scores": {
                    **self._score_fixture()["scores"],
                    "pacing": True,
                },
                "suggestions": self._score_fixture()["suggestions"],
            },
            {
                "scores": self._score_fixture()["scores"],
                "suggestions": {
                    **self._score_fixture()["suggestions"],
                    "emotion": " ",
                },
            },
        )

        with self.app.app_context():
            for payload in invalid_payloads:
                with self.subTest(payload=payload):
                    self.ai.reset_mock()
                    self.ai.complete_json.return_value = payload
                    training = self._complete_training()

                    with self.assertRaisesRegex(
                        AiUnavailableError,
                        "^AI 服务暂时不可用$",
                    ):
                        score_simulation(self.student_id, training["id"])

                    loaded = get_simulation(
                        self.student_id,
                        training["id"],
                    )
                    self.assertEqual(loaded["status"], "draft")
                    self.assertIsNone(loaded["scores"])
                    self.assertIsNone(loaded["total_score"])
                    self.assertEqual(
                        [segment["text"] for segment in loaded["segments"]],
                        list(self.segments.values()),
                    )

    def test_ai_failure_is_exact_and_preserves_every_segment(self):
        self.ai.complete_json.side_effect = AiUnavailableError(
            "raw provider error"
        )

        with self.app.app_context():
            training = self._complete_training()
            original = get_simulation(self.student_id, training["id"])

            with self.assertRaisesRegex(
                AiUnavailableError,
                "^AI 服务暂时不可用$",
            ):
                score_simulation(self.student_id, training["id"])

            loaded = get_simulation(self.student_id, training["id"])

        self.assertEqual(loaded, original)
        self.assertEqual(loaded["status"], "draft")
        self.assertIsNone(loaded["scores"])

    def test_another_student_cannot_read_or_write_training(self):
        with self.app.app_context():
            training = start_simulation(self.other_student_id, "opening")
            save_simulation_segment(
                self.other_student_id,
                training["id"],
                "greeting",
                "其他学员内容",
            )

            with self.assertRaises(AgriNotFoundError):
                get_simulation(self.student_id, training["id"])
            with self.assertRaises(AgriNotFoundError):
                save_simulation_segment(
                    self.student_id,
                    training["id"],
                    "hook",
                    "越权写入",
                )
            with self.assertRaises(AgriNotFoundError):
                score_simulation(self.student_id, training["id"])

            self.assertEqual(list_simulations(self.student_id), [])
            other = get_simulation(self.other_student_id, training["id"])

        self.ai.complete_json.assert_not_called()
        self.assertEqual(other["segments"][0]["text"], "其他学员内容")
        self.assertEqual(other["segments"][1]["text"], "")

    def test_list_is_owner_scoped_and_newest_first(self):
        with self.app.app_context():
            first = start_simulation(self.student_id, "opening")
            second = start_simulation(self.student_id, "product_intro")
            other = start_simulation(self.other_student_id, "closing")
            history = list_simulations(self.student_id)

        self.assertEqual(
            [training["id"] for training in history],
            [second["id"], first["id"]],
        )
        self.assertNotIn(other["id"], [training["id"] for training in history])

    def test_repeated_scoring_returns_existing_result_without_ai_call(self):
        self.ai.complete_json.return_value = self._score_fixture()

        with self.app.app_context():
            training = self._complete_training()
            first = score_simulation(self.student_id, training["id"])
            self.ai.complete_json.reset_mock()
            second = score_simulation(self.student_id, training["id"])

        self.ai.complete_json.assert_not_called()
        self.assertEqual(second, first)

    def test_invalid_scene_is_rejected(self):
        with self.app.app_context():
            with self.assertRaisesRegex(
                AgriValidationError,
                "模拟场景不存在",
            ):
                start_simulation(self.student_id, "unknown")


if __name__ == "__main__":
    unittest.main()
