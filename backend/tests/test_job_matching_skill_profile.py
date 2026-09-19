from __future__ import annotations

import unittest
from unittest.mock import patch

from app.job_matching import skill_profile
from app.job_matching.skill_profile import list_skill_outcomes


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


if __name__ == "__main__":
    unittest.main()
