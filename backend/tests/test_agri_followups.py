import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from app import create_app
from app.agri_skills.ai_client import set_ai_client
from app.agri_skills.diagnosis import (
    add_followup,
    answer_diagnosis,
    create_diagnosis,
    create_diagnosis_from_followup,
    get_diagnosis,
    list_followups,
)
from app.agri_skills.errors import (
    AgriNotFoundError,
    AgriValidationError,
)
from app.db import get_db


class TestAgriFollowups(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(Path(self.temp_dir.name) / "test.db"),
                "SECRET_KEY": "test-only-secret",
                "AI_API_URL": "",
                "AI_API_KEY": "",
                "AI_MODEL": "test-model",
            }
        )
        with self.app.app_context():
            db = get_db()
            self.student_id = self._insert_student(db, "student01")
            self.other_student_id = self._insert_student(db, "student02")
            db.commit()

        self.ai = Mock()
        set_ai_client(self.app, self.ai)
        self.ai.complete_json.side_effect = [
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
        ]
        with self.app.app_context():
            self.session = create_diagnosis(
                self.student_id,
                "litchi",
                "fruit",
                ["虫蛀", "落果"],
            )
            result = answer_diagnosis(
                self.student_id,
                self.session["id"],
                "果实有虫孔并有落果",
                "text",
            )
            self.session = result["session"]
        self.ai.complete_json.side_effect = None
        self.ai.complete_json.return_value = {
            "status": "follow_up_required",
            "question": "复诊首问",
            "conclusion": None,
            "limited": False,
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
                "2026-09-15T00:00:00+00:00",
                "2026-09-15T00:00:00+00:00",
            ),
        )
        return int(cursor.lastrowid)

    def _add_followup(
        self,
        outcome: str = "worsened",
        note: object = "雨后仍有落果",
    ) -> dict:
        with self.app.app_context():
            return add_followup(
                self.student_id,
                self.session["id"],
                outcome,
                note,
            )

    def test_completed_diagnosis_accepts_multiple_followups(self):
        first = self._add_followup("improved", "叶片恢复")
        second = self._add_followup("unchanged", "仍需观察")

        with self.app.app_context():
            followups = list_followups(
                self.student_id,
                self.session["id"],
            )

        self.assertNotEqual(first["id"], second["id"])
        self.assertEqual(
            [item["outcome"] for item in followups],
            ["improved", "unchanged"],
        )
        self.assertEqual(
            [item["note"] for item in followups],
            ["叶片恢复", "仍需观察"],
        )

    def test_followup_validates_outcome_and_normalizes_note(self):
        followup = self._add_followup("improved", "  叶片恢复  ")

        with self.app.app_context():
            with self.assertRaisesRegex(
                AgriValidationError,
                "复诊状态不正确",
            ):
                add_followup(
                    self.student_id,
                    self.session["id"],
                    "recovered",
                    "",
                )

        self.assertEqual(followup["note"], "叶片恢复")

    def test_in_progress_diagnosis_rejects_followup(self):
        self.ai.complete_json.return_value = {
            "status": "follow_up_required",
            "question": "请补充病斑颜色",
            "conclusion": None,
            "limited": False,
        }
        with self.app.app_context():
            in_progress = create_diagnosis(
                self.student_id,
                "litchi",
                "leaf",
                ["斑点"],
            )
            with self.assertRaisesRegex(
                AgriValidationError,
                "仅已完成诊断可记录复诊",
            ):
                add_followup(
                    self.student_id,
                    in_progress["id"],
                    "improved",
                    "",
                )

    def test_followup_operations_enforce_ownership(self):
        followup = self._add_followup()

        with self.app.app_context():
            with self.assertRaises(AgriNotFoundError):
                add_followup(
                    self.other_student_id,
                    self.session["id"],
                    "improved",
                    "",
                )
            with self.assertRaises(AgriNotFoundError):
                list_followups(
                    self.other_student_id,
                    self.session["id"],
                )
            with self.assertRaises(AgriNotFoundError):
                create_diagnosis_from_followup(
                    self.other_student_id,
                    self.session["id"],
                    followup["id"],
                )

    def test_foreign_followup_cannot_start_diagnosis(self):
        with self.app.app_context():
            followup = add_followup(
                self.student_id,
                self.session["id"],
                "worsened",
                "雨后仍有落果",
            )
            with self.assertRaises(AgriNotFoundError):
                create_diagnosis_from_followup(
                    self.other_student_id,
                    self.session["id"],
                    followup["id"],
                )

    def test_repeat_diagnosis_prefills_fields_and_readonly_context(self):
        followup = self._add_followup()
        self.ai.complete_json.return_value = {
            "status": "follow_up_required",
            "question": "复诊后症状范围是否扩大",
            "conclusion": None,
            "limited": False,
        }

        with self.app.app_context():
            session = create_diagnosis_from_followup(
                self.student_id,
                self.session["id"],
                followup["id"],
            )

        self.assertEqual(session["source_session_id"], self.session["id"])
        self.assertEqual(session["source_followup_id"], followup["id"])
        self.assertTrue(session["source_available"])
        self.assertEqual(session["product_key"], "litchi")
        self.assertEqual(session["affected_part"], "fruit")
        self.assertEqual(session["symptoms"], ["虫蛀", "落果"])
        self.assertEqual(session["answers"], [])
        self.assertEqual(
            session["source_context"],
            {
                "source_conclusion": {
                    "cause": "果实受蒂蛀虫危害",
                    "treatment": "清理落果并按登记药剂防治",
                },
                "followup_status": "worsened",
                "followup_note": "雨后仍有落果",
            },
        )

    def test_repeat_diagnosis_uses_source_context_without_q_and_a_copy(self):
        followup = self._add_followup()
        self.ai.complete_json.return_value = {
            "status": "follow_up_required",
            "question": "复诊后症状范围是否扩大",
            "conclusion": None,
            "limited": False,
        }
        calls_before_repeat = self.ai.complete_json.call_count

        with self.app.app_context():
            session = create_diagnosis_from_followup(
                self.student_id,
                self.session["id"],
                followup["id"],
            )

        call = self.ai.complete_json.call_args_list[calls_before_repeat]
        context = json.loads(call.args[0][1]["content"])
        self.assertEqual(context["source_conclusion"]["cause"], "果实受蒂蛀虫危害")
        self.assertEqual(context["followup_status"], "worsened")
        self.assertEqual(context["followup_note"], "雨后仍有落果")
        self.assertEqual(context["prior_questions"], [])
        self.assertEqual(context["prior_answers"], [])
        self.assertNotIn("果实有虫孔并有落果", call.args[0][1]["content"])
        self.assertEqual(session["answers"], [])
        self.assertEqual(session["round_count"], 0)

    def test_repeat_diagnosis_does_not_change_source_records(self):
        followup = self._add_followup()
        self.ai.complete_json.return_value = {
            "status": "follow_up_required",
            "question": "复诊后症状范围是否扩大",
            "conclusion": None,
            "limited": False,
        }

        with self.app.app_context():
            before = get_diagnosis(self.student_id, self.session["id"])
            create_diagnosis_from_followup(
                self.student_id,
                self.session["id"],
                followup["id"],
            )
            after = get_diagnosis(self.student_id, self.session["id"])
            followups_after = list_followups(
                self.student_id,
                self.session["id"],
            )

        self.assertEqual(after["answers"], before["answers"])
        self.assertEqual(after["conclusion"], before["conclusion"])
        self.assertEqual(after["updated_at"], before["updated_at"])
        self.assertEqual(followups_after, [followup])

    def test_selected_followup_must_belong_to_source_diagnosis(self):
        first_followup = self._add_followup("improved", "第一诊断")
        self.ai.complete_json.return_value = {
            "status": "follow_up_required",
            "question": "第一次复诊首问",
            "conclusion": None,
            "limited": False,
        }
        with self.app.app_context():
            repeated = create_diagnosis_from_followup(
                self.student_id,
                self.session["id"],
                first_followup["id"],
            )
            self.ai.complete_json.return_value = {
                "status": "conclusion_ready",
                "question": None,
                "conclusion": {
                    "cause": "复诊结论",
                    "treatment": "继续观察",
                },
                "limited": False,
            }
            repeated = answer_diagnosis(
                self.student_id,
                repeated["id"],
                "症状稳定",
                "text",
            )["session"]
            second_followup = add_followup(
                self.student_id,
                repeated["id"],
                "unchanged",
                "另一来源",
            )
            with self.assertRaises(AgriNotFoundError):
                create_diagnosis_from_followup(
                    self.student_id,
                    self.session["id"],
                    second_followup["id"],
                )

    def test_missing_source_followup_marks_source_unavailable(self):
        followup = self._add_followup()
        self.ai.complete_json.return_value = {
            "status": "follow_up_required",
            "question": "复诊首问",
            "conclusion": None,
            "limited": False,
        }
        with self.app.app_context():
            repeated = create_diagnosis_from_followup(
                self.student_id,
                self.session["id"],
                followup["id"],
            )
            db = get_db()
            db.execute(
                "DELETE FROM agri_diagnosis_followups WHERE id = ?",
                (followup["id"],),
            )
            db.commit()
            persisted = get_diagnosis(self.student_id, repeated["id"])

        self.assertEqual(persisted["id"], repeated["id"])
        self.assertEqual(
            persisted["source_session_id"],
            self.session["id"],
        )
        self.assertEqual(
            persisted["source_followup_id"],
            followup["id"],
        )
        self.assertFalse(persisted["source_available"])
        self.assertIsNone(persisted["source_context"])

    def test_missing_source_session_marks_source_unavailable(self):
        followup = self._add_followup()
        self.ai.complete_json.return_value = {
            "status": "follow_up_required",
            "question": "复诊首问",
            "conclusion": None,
            "limited": False,
        }
        with self.app.app_context():
            repeated = create_diagnosis_from_followup(
                self.student_id,
                self.session["id"],
                followup["id"],
            )
            db = get_db()
            db.commit()
            db.execute("PRAGMA foreign_keys = OFF")
            db.execute(
                """
                UPDATE agri_diagnosis_sessions
                SET source_session_id = 999999
                WHERE id = ?
                """,
                (repeated["id"],),
            )
            db.commit()
            db.execute("PRAGMA foreign_keys = ON")
            persisted = get_diagnosis(self.student_id, repeated["id"])

        self.assertEqual(persisted["id"], repeated["id"])
        self.assertEqual(persisted["source_session_id"], 999999)
        self.assertFalse(persisted["source_available"])
        self.assertIsNone(persisted["source_context"])


if __name__ == "__main__":
    unittest.main()
