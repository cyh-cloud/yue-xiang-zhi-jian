from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from app import create_app
from app.db import get_db
from app.job_matching import skill_profile
from app.job_matching.constants import SKILL_CATEGORIES
from app.job_matching.errors import JobMatchingValidationError
from app.job_matching.skill_profile import (
    build_skill_profile_snapshot,
    get_skill_profile,
    list_skill_outcomes,
    set_skill_visibility,
)


AGRI_ROWS = [
    {
        "kind": "diagnostic_self_test",
        "source_id": 7,
        "diagnosis_session_id": 3,
        "course_id": None,
        "score": 80,
        "is_formal": False,
        "created_at": "2026-09-19T08:00:00+08:00",
    },
    {
        "kind": "course_quiz",
        "source_id": 8,
        "diagnosis_session_id": None,
        "course_id": 11,
        "score": 90,
        "is_formal": True,
        "created_at": "2026-09-19T09:00:00+08:00",
    },
]

ECOMMERCE_ROWS = [
    {
        "kind": "live_script",
        "source_id": 21,
        "created_at": "2026-09-19T10:00:00+08:00",
        "summary": "直播话术",
        "score": None,
        "is_formal": False,
        "archive_written": False,
    },
    {
        "kind": "simulation_training",
        "source_id": 22,
        "created_at": "2026-09-19T11:00:00+08:00",
        "summary": "售后模拟",
        "score": 75,
        "is_formal": False,
        "archive_written": False,
    },
    {
        "kind": "course_quiz",
        "source_id": 8,
        "created_at": "2026-09-19T09:05:00+08:00",
        "summary": "电子商务课程",
        "score": 95,
        "is_formal": True,
        "archive_written": False,
    },
    {
        "kind": "course_completion",
        "source_id": 31,
        "created_at": "2026-09-19T12:00:00+08:00",
        "summary": "电子商务课程",
        "score": None,
        "is_formal": False,
        "archive_written": False,
    },
]

HANDCRAFT_ROWS = [
    {
        "outcome_type": "course_view",
        "source_id": 41,
        "created_at": "2026-09-19T13:00:00+08:00",
        "source_available": False,
        "summary": "广绣课程",
        "score": None,
        "is_formal": False,
        "archive_written": False,
    },
]


class SkillOutcomeAggregationTests(unittest.TestCase):
    def test_normalizes_and_maps_four_categories(self):
        with (
            patch.object(
                skill_profile,
                "list_learning_outcomes",
                return_value=AGRI_ROWS,
            ),
            patch.object(
                skill_profile,
                "list_ecommerce_learning_outcomes",
                return_value=ECOMMERCE_ROWS,
            ),
            patch.object(
                skill_profile,
                "list_handcraft_learning_outcomes",
                return_value=HANDCRAFT_ROWS,
            ),
        ):
            outcomes = list_skill_outcomes(101)

        self.assertEqual(
            {item["category"] for item in outcomes},
            {
                "live_script",
                "simulation_training",
                "quiz_score",
                "learning_record",
            },
        )
        self.assertEqual(
            len({item["item_id"] for item in outcomes}),
            len(outcomes),
        )
        self.assertTrue(
            all(
                item["source_module"]
                in {"agriculture", "ecommerce", "handcraft"}
                for item in outcomes
            )
        )
        self.assertEqual(
            {item["item_id"] for item in outcomes},
            {
                "agriculture:diagnostic_self_test:7",
                "ecommerce:course_quiz:8",
                "ecommerce:live_script:21",
                "ecommerce:simulation_training:22",
                "ecommerce:course_completion:31",
                "handcraft:course_view:41",
            },
        )
        handcraft_item = next(
            item
            for item in outcomes
            if item["item_id"] == "handcraft:course_view:41"
        )
        self.assertFalse(handcraft_item["source_available"])

    def test_deduplicates_course_quiz_preferring_ecommerce(self):
        agri_quiz = {
            **AGRI_ROWS[1],
            "source_id": 808,
            "created_at": "2026-09-19T09:00:00+08:00",
        }
        ecommerce_quiz = {
            **ECOMMERCE_ROWS[2],
            "source_id": 808,
            "created_at": "2026-09-19T09:05:00+08:00",
        }

        with (
            patch.object(
                skill_profile,
                "list_learning_outcomes",
                return_value=[agri_quiz],
            ),
            patch.object(
                skill_profile,
                "list_ecommerce_learning_outcomes",
                return_value=[ecommerce_quiz],
            ),
            patch.object(
                skill_profile,
                "list_handcraft_learning_outcomes",
                return_value=[],
            ),
        ):
            outcomes = list_skill_outcomes(101)

        self.assertEqual(len(outcomes), 1)
        self.assertEqual(outcomes[0]["source_module"], "ecommerce")
        self.assertEqual(outcomes[0]["item_id"], "ecommerce:course_quiz:808")
        self.assertEqual(outcomes[0]["score"], 95)

    def test_deduplicates_course_quiz_preferring_handcraft(self):
        agri_quiz = {
            **AGRI_ROWS[1],
            "source_id": 909,
            "created_at": "2026-09-19T09:00:00+08:00",
        }
        handcraft_quiz = {
            **HANDCRAFT_ROWS[0],
            "outcome_type": "course_quiz",
            "source_id": 909,
            "source_available": True,
            "summary": "手工课程",
            "score": 88,
            "is_formal": True,
            "created_at": "2026-09-19T09:05:00+08:00",
        }

        with (
            patch.object(
                skill_profile,
                "list_learning_outcomes",
                return_value=[agri_quiz],
            ),
            patch.object(
                skill_profile,
                "list_ecommerce_learning_outcomes",
                return_value=[],
            ),
            patch.object(
                skill_profile,
                "list_handcraft_learning_outcomes",
                return_value=[handcraft_quiz],
            ),
        ):
            outcomes = list_skill_outcomes(101)

        self.assertEqual(len(outcomes), 1)
        self.assertEqual(outcomes[0]["source_module"], "handcraft")
        self.assertEqual(outcomes[0]["item_id"], "handcraft:course_quiz:909")
        self.assertEqual(outcomes[0]["score"], 88)

    def test_isolates_a_failing_reader(self):
        with (
            patch.object(
                skill_profile,
                "list_learning_outcomes",
                return_value=AGRI_ROWS,
            ),
            patch.object(
                skill_profile,
                "list_ecommerce_learning_outcomes",
                side_effect=RuntimeError("ecommerce unavailable"),
            ),
            patch.object(
                skill_profile,
                "list_handcraft_learning_outcomes",
                return_value=HANDCRAFT_ROWS,
            ),
            self.assertLogs(
                "app.job_matching.skill_profile",
                level="ERROR",
            ),
        ):
            outcomes = list_skill_outcomes(101)

        self.assertEqual(
            {item["item_id"] for item in outcomes},
            {
                "agriculture:diagnostic_self_test:7",
                "agriculture:course_quiz:8",
                "handcraft:course_view:41",
            },
        )

    def test_skips_unknown_source_types_and_logs_warnings(self):
        unknown_agri = {
            **AGRI_ROWS[0],
            "kind": "unknown_agriculture",
            "source_id": 70,
        }
        unknown_ecommerce = {
            **ECOMMERCE_ROWS[0],
            "kind": "unknown_ecommerce",
            "source_id": 71,
        }
        unknown_handcraft = {
            **HANDCRAFT_ROWS[0],
            "outcome_type": "unknown_handcraft",
            "source_id": 72,
        }

        with (
            patch.object(
                skill_profile,
                "list_learning_outcomes",
                return_value=[AGRI_ROWS[0], unknown_agri],
            ),
            patch.object(
                skill_profile,
                "list_ecommerce_learning_outcomes",
                return_value=[ECOMMERCE_ROWS[0], unknown_ecommerce],
            ),
            patch.object(
                skill_profile,
                "list_handcraft_learning_outcomes",
                return_value=[HANDCRAFT_ROWS[0], unknown_handcraft],
            ),
            self.assertLogs(
                "app.job_matching.skill_profile",
                level="WARNING",
            ) as logs,
        ):
            outcomes = list_skill_outcomes(101)

        self.assertEqual(
            {item["item_id"] for item in outcomes},
            {
                "agriculture:diagnostic_self_test:7",
                "ecommerce:live_script:21",
                "handcraft:course_view:41",
            },
        )
        self.assertEqual(len(logs.records), 3)
        self.assertTrue(
            all(
                record.getMessage().startswith("Unknown skill outcome")
                for record in logs.records
            )
        )

    def test_sorts_by_parsed_time_instead_of_raw_iso_strings(self):
        agri_row = {
            **AGRI_ROWS[0],
            "created_at": "2026-09-19T08:00:00+08:00",
        }
        ecommerce_row = {
            **ECOMMERCE_ROWS[0],
            "created_at": "2026-09-19T01:00:00+00:00",
        }

        with (
            patch.object(
                skill_profile,
                "list_learning_outcomes",
                return_value=[agri_row],
            ),
            patch.object(
                skill_profile,
                "list_ecommerce_learning_outcomes",
                return_value=[ecommerce_row],
            ),
            patch.object(
                skill_profile,
                "list_handcraft_learning_outcomes",
                return_value=[],
            ),
        ):
            outcomes = list_skill_outcomes(101)

        self.assertEqual(
            [item["source_module"] for item in outcomes],
            ["agriculture", "ecommerce"],
        )

    def test_skips_naive_timestamp_and_keeps_valid_records(self):
        naive_agri = {
            **AGRI_ROWS[1],
            "source_id": 73,
            "created_at": "2026-09-19T09:00:00",
        }

        with (
            patch.object(
                skill_profile,
                "list_learning_outcomes",
                return_value=[AGRI_ROWS[0], naive_agri],
            ),
            patch.object(
                skill_profile,
                "list_ecommerce_learning_outcomes",
                return_value=[ECOMMERCE_ROWS[0]],
            ),
            patch.object(
                skill_profile,
                "list_handcraft_learning_outcomes",
                return_value=[HANDCRAFT_ROWS[0]],
            ),
            self.assertLogs(
                "app.job_matching.skill_profile",
                level="WARNING",
            ) as logs,
        ):
            outcomes = list_skill_outcomes(101)

        self.assertEqual(
            {item["item_id"] for item in outcomes},
            {
                "agriculture:diagnostic_self_test:7",
                "ecommerce:live_script:21",
                "handcraft:course_view:41",
            },
        )
        self.assertEqual(len(logs.records), 1)
        self.assertIn(
            "Invalid skill outcome timestamp",
            logs.records[0].getMessage(),
        )

    def test_skips_malformed_timestamp_and_keeps_valid_records(self):
        malformed_ecommerce = {
            **ECOMMERCE_ROWS[1],
            "source_id": 74,
            "created_at": "not-an-iso-timestamp",
        }

        with (
            patch.object(
                skill_profile,
                "list_learning_outcomes",
                return_value=[AGRI_ROWS[0]],
            ),
            patch.object(
                skill_profile,
                "list_ecommerce_learning_outcomes",
                return_value=[
                    ECOMMERCE_ROWS[0],
                    malformed_ecommerce,
                ],
            ),
            patch.object(
                skill_profile,
                "list_handcraft_learning_outcomes",
                return_value=[HANDCRAFT_ROWS[0]],
            ),
            self.assertLogs(
                "app.job_matching.skill_profile",
                level="WARNING",
            ) as logs,
        ):
            outcomes = list_skill_outcomes(101)

        self.assertEqual(
            {item["item_id"] for item in outcomes},
            {
                "agriculture:diagnostic_self_test:7",
                "ecommerce:live_script:21",
                "handcraft:course_view:41",
            },
        )
        self.assertEqual(len(logs.records), 1)
        self.assertIn(
            "Invalid skill outcome timestamp",
            logs.records[0].getMessage(),
        )


class SkillVisibilityProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        database_path = Path(self.temp_dir.name) / "test.db"
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(database_path),
                "SECRET_KEY": "test-only-secret",
            }
        )

        source_patches = (
            patch.object(
                skill_profile,
                "list_learning_outcomes",
                return_value=AGRI_ROWS,
            ),
            patch.object(
                skill_profile,
                "list_ecommerce_learning_outcomes",
                return_value=ECOMMERCE_ROWS,
            ),
            patch.object(
                skill_profile,
                "list_handcraft_learning_outcomes",
                return_value=HANDCRAFT_ROWS,
            ),
        )
        for source_patch in source_patches:
            source_patch.start()
            self.addCleanup(source_patch.stop)

        with self.app.app_context():
            db = get_db()
            self.student_id = self._insert_student(db, "student-1")
            self.other_student_id = self._insert_student(db, "student-2")
            db.commit()

    @staticmethod
    def _insert_student(db, username: str) -> int:
        timestamp = "2026-09-19T10:00:00+08:00"
        cursor = db.execute(
            """
            INSERT INTO users (
                username,
                password_hash,
                name,
                role,
                is_enabled,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, 'student', 1, ?, ?)
            """,
            (
                username,
                "test-password-hash",
                username,
                timestamp,
                timestamp,
            ),
        )
        return int(cursor.lastrowid)

    def test_profile_defaults_to_hidden_and_snapshot_uses_visible_items(self):
        with self.app.app_context():
            profile = get_skill_profile(self.student_id)

            self.assertTrue(profile["items"])
            self.assertTrue(
                all(not item["visible"] for item in profile["items"])
            )
            self.assertEqual(profile["visible_item_ids"], [])
            self.assertEqual(
                set(profile["summary"]),
                set(SKILL_CATEGORIES),
            )
            self.assertIsNone(
                build_skill_profile_snapshot(self.student_id)
            )

            visible_id = profile["items"][0]["item_id"]
            updated = set_skill_visibility(
                self.student_id,
                [visible_id],
            )
            self.assertEqual(updated["visible_item_ids"], [visible_id])

            snapshot = build_skill_profile_snapshot(self.student_id)
            self.assertEqual(
                set(snapshot),
                {"schema_version", "generated_at", "items", "summary"},
            )
            self.assertEqual(snapshot["schema_version"], 1)
            self.assertEqual(
                [item["item_id"] for item in snapshot["items"]],
                [visible_id],
            )
            self.assertNotIn("visible", snapshot["items"][0])
            self.assertEqual(
                snapshot["summary"],
                {
                    "live_script": 0,
                    "simulation_training": 0,
                    "quiz_score": 1,
                    "learning_record": 0,
                },
            )
            generated_at = datetime.fromisoformat(
                snapshot["generated_at"]
            )
            self.assertEqual(
                generated_at.utcoffset(),
                timedelta(hours=8),
            )

    def test_snapshot_excludes_hidden_and_unavailable_items(self):
        with self.app.app_context():
            profile = get_skill_profile(self.student_id)
            visible_id = profile["items"][0]["item_id"]
            hidden_id = next(
                item["item_id"]
                for item in profile["items"][1:]
                if item["source_available"]
            )
            unavailable_id = next(
                item["item_id"]
                for item in profile["items"]
                if not item["source_available"]
            )

            set_skill_visibility(
                self.student_id,
                [visible_id, unavailable_id],
            )
            snapshot = build_skill_profile_snapshot(self.student_id)

            self.assertEqual(
                [item["item_id"] for item in snapshot["items"]],
                [visible_id],
            )
            self.assertNotIn(
                hidden_id,
                [item["item_id"] for item in snapshot["items"]],
            )

    def test_invalid_item_id_is_rejected_without_changing_visibility(self):
        with self.app.app_context():
            profile = get_skill_profile(self.student_id)
            visible_id = profile["items"][0]["item_id"]
            set_skill_visibility(self.student_id, [visible_id])

            with self.assertRaises(
                JobMatchingValidationError
            ) as raised:
                set_skill_visibility(
                    self.student_id,
                    [visible_id, "unknown:item:99"],
                )

            self.assertEqual(raised.exception.message, "可见成果不存在")
            self.assertEqual(
                raised.exception.details,
                {"item_ids": ["unknown:item:99"]},
            )
            self.assertEqual(
                get_skill_profile(self.student_id)["visible_item_ids"],
                [visible_id],
            )

    def test_visibility_is_independent_for_each_student(self):
        with self.app.app_context():
            profile = get_skill_profile(self.student_id)
            first_student_id = profile["items"][0]["item_id"]
            second_student_id = profile["items"][1]["item_id"]

            set_skill_visibility(
                self.student_id,
                [first_student_id],
            )
            other_profile = get_skill_profile(self.other_student_id)
            self.assertTrue(
                all(not item["visible"] for item in other_profile["items"])
            )
            self.assertIsNone(
                build_skill_profile_snapshot(self.other_student_id)
            )

            set_skill_visibility(
                self.other_student_id,
                [second_student_id],
            )
            self.assertEqual(
                get_skill_profile(self.student_id)["visible_item_ids"],
                [first_student_id],
            )
            self.assertEqual(
                get_skill_profile(
                    self.other_student_id
                )["visible_item_ids"],
                [second_student_id],
            )

    def test_set_visibility_replaces_complete_set_and_empty_clears_it(self):
        with self.app.app_context():
            profile = get_skill_profile(self.student_id)
            first_id, second_id = (
                item["item_id"] for item in profile["items"][:2]
            )

            set_skill_visibility(
                self.student_id,
                [first_id, second_id],
            )
            self.assertEqual(
                get_skill_profile(self.student_id)["visible_item_ids"],
                [first_id, second_id],
            )

            set_skill_visibility(self.student_id, [second_id])
            self.assertEqual(
                get_skill_profile(self.student_id)["visible_item_ids"],
                [second_id],
            )

            cleared = set_skill_visibility(self.student_id, [])
            self.assertEqual(cleared["visible_item_ids"], [])
            self.assertIsNone(
                build_skill_profile_snapshot(self.student_id)
            )

    def test_snapshot_is_not_mutated_by_later_visibility_changes(self):
        with self.app.app_context():
            profile = get_skill_profile(self.student_id)
            first_id, second_id = (
                item["item_id"] for item in profile["items"][:2]
            )
            set_skill_visibility(self.student_id, [first_id])
            snapshot = build_skill_profile_snapshot(self.student_id)

            set_skill_visibility(self.student_id, [second_id])

            self.assertEqual(
                [item["item_id"] for item in snapshot["items"]],
                [first_id],
            )
            self.assertNotIn("visible", snapshot["items"][0])


if __name__ == "__main__":
    unittest.main()
