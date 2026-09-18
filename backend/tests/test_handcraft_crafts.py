import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import create_app
from app.agri_skills.errors import AgriValidationError
from app.db import get_db
from app.handcraft_inheritance.crafts import (
    complete_craft_step,
    get_craft,
    get_craft_progress,
    get_material_guide,
    list_crafts,
)
from app.handcraft_inheritance.presets import PLACEHOLDER_CRAFTS
from app.handcraft_inheritance.providers import (
    EmptyCraftPresetProvider,
    set_craft_preset_provider,
)


class StaticCraftPresetProvider:
    def __init__(self, crafts):
        self.crafts = copy.deepcopy(crafts)

    def list_crafts(self):
        return copy.deepcopy(self.crafts)

    def get_craft(self, craft_key):
        return next(
            (
                copy.deepcopy(craft)
                for craft in self.crafts
                if craft.get("craft_key") == craft_key
            ),
            None,
        )


class TestHandcraftCrafts(unittest.TestCase):
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
            db.execute(
                """
                INSERT INTO users (
                    id, username, password_hash, name, role, is_enabled,
                    created_at, updated_at
                )
                VALUES (
                    1, 'student01', 'hash', '学员', 'student', 1,
                    '2026-09-18T00:00:00+08:00',
                    '2026-09-18T00:00:00+08:00'
                )
                """
            )
            db.commit()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_catalog_exposes_four_complete_ordered_crafts_and_guides(self):
        with self.app.app_context():
            crafts = list_crafts()

        self.assertEqual(
            [craft["craft_key"] for craft in crafts],
            [
                "guangxiu",
                "chaoshan-woodcarving",
                "shiwan-ceramics",
                "yangjiang-lacquerware",
            ],
        )
        self.assertEqual(
            [craft["name"] for craft in crafts],
            ["广绣", "潮汕木雕", "石湾陶艺", "阳江漆器"],
        )
        expected_guide_fields = {
            "name",
            "reference_price",
            "purchase_channel",
            "precautions",
            "taobao_keyword",
        }
        for craft in crafts:
            with self.subTest(craft=craft["craft_key"]):
                self.assertTrue(craft["available"])
                self.assertEqual(craft["status"], "available")
                self.assertIsNone(craft["unavailable_reason"])
                self.assertTrue(craft["introduction"].strip())
                self.assertEqual(len(craft["steps"]), 6)
                self.assertEqual(
                    [step["step_no"] for step in craft["steps"]],
                    [1, 2, 3, 4, 5, 6],
                )
                for step in craft["steps"]:
                    self.assertTrue(step["step_key"].strip())
                    self.assertTrue(step["title"].strip())
                    self.assertTrue(step["description"].strip())
                    self.assertTrue(step["tips"])
                    self.assertTrue(
                        all(tip.strip() for tip in step["tips"])
                    )

                with self.app.app_context():
                    guide = get_material_guide(craft["craft_key"])
                self.assertTrue(guide["available"])
                self.assertEqual(guide["status"], "available")
                self.assertEqual(guide["craft_key"], craft["craft_key"])
                self.assertTrue(guide["material_guide"])
                for material in guide["material_guide"]:
                    self.assertEqual(set(material), expected_guide_fields)
                    self.assertTrue(
                        all(
                            isinstance(value, str) and value.strip()
                            for value in material.values()
                        )
                    )

    def test_malformed_or_missing_craft_content_is_explicitly_unavailable(self):
        incomplete = copy.deepcopy(PLACEHOLDER_CRAFTS[0])
        incomplete["steps"] = list(incomplete["steps"][:5])
        non_contiguous = copy.deepcopy(PLACEHOLDER_CRAFTS[0])
        non_contiguous["steps"] = list(non_contiguous["steps"])
        non_contiguous["steps"][2] = {
            **non_contiguous["steps"][2],
            "step_no": 4,
        }

        with self.app.app_context():
            unavailable_content = []
            for broken in (incomplete, non_contiguous):
                set_craft_preset_provider(
                    self.app,
                    StaticCraftPresetProvider([broken]),
                )
                unavailable_content.extend(
                    (
                        get_craft("guangxiu"),
                        get_material_guide("guangxiu"),
                    )
                )
            missing = get_craft("missing")
            missing_guide = get_material_guide("missing")

        for unavailable in (*unavailable_content, missing, missing_guide):
            self.assertFalse(unavailable["available"])
            self.assertEqual(unavailable["status"], "unavailable")
            self.assertEqual(
                unavailable["unavailable_reason"],
                "技艺内容不可用",
            )
            self.assertEqual(unavailable["steps"], [])
            self.assertEqual(unavailable["material_guide"], [])

    def test_progress_is_monotonic_and_resumes_at_the_next_step(self):
        with self.app.app_context():
            initial = get_craft_progress(1, "guangxiu")
            first = complete_craft_step(
                1,
                "guangxiu",
                1,
                600,
                "guangxiu-step-1",
            )
            repeated = complete_craft_step(
                1,
                "guangxiu",
                1,
                600,
                "guangxiu-step-1",
            )
            skipped = complete_craft_step(
                1,
                "guangxiu",
                3,
                600,
                "guangxiu-step-3-too-early",
            )
            after_skipped = get_craft_progress(1, "guangxiu")
            second = complete_craft_step(
                1,
                "guangxiu",
                2,
                300,
                "guangxiu-step-2",
            )
            lower = complete_craft_step(
                1,
                "guangxiu",
                1,
                300,
                "guangxiu-step-1-lower",
            )
            for step_no in range(3, 7):
                complete_craft_step(
                    1,
                    "guangxiu",
                    step_no,
                    300,
                    f"guangxiu-step-{step_no}",
                )
            final = get_craft_progress(1, "guangxiu")

        self.assertEqual(initial["completed_steps"], [])
        self.assertEqual(initial["completed_step_count"], 0)
        self.assertEqual(initial["resume_step_no"], 1)
        self.assertFalse(initial["is_completed"])

        self.assertTrue(first["accepted"])
        self.assertEqual(first["status"], "completed")
        self.assertEqual(first["completed_steps"], [1])
        self.assertEqual(first["completed_step_count"], 1)
        self.assertEqual(first["resume_step_no"], 2)

        self.assertFalse(repeated["accepted"])
        self.assertEqual(repeated["status"], "already_completed")
        self.assertEqual(repeated["completed_steps"], [1])
        self.assertEqual(after_skipped["completed_steps"], [1])
        self.assertEqual(skipped["status"], "out_of_order")
        self.assertFalse(skipped["accepted"])
        self.assertEqual(second["completed_steps"], [1, 2])
        self.assertEqual(second["resume_step_no"], 3)
        self.assertEqual(lower["status"], "already_completed")
        self.assertEqual(final["completed_steps"], [1, 2, 3, 4, 5, 6])
        self.assertEqual(final["completed_step_count"], 6)
        self.assertIsNone(final["resume_step_no"])
        self.assertTrue(final["is_completed"])

    def test_invalid_step_and_active_duration_do_not_change_progress(self):
        with self.app.app_context():
            for active_seconds in (-1, True, 7201):
                with self.subTest(active_seconds=active_seconds):
                    with self.assertRaises(AgriValidationError):
                        complete_craft_step(
                            1,
                            "guangxiu",
                            1,
                            active_seconds,
                            f"invalid-duration-{active_seconds}",
                        )
            for step_no in (0, 7, True):
                with self.subTest(step_no=step_no):
                    with self.assertRaises(AgriValidationError):
                        complete_craft_step(
                            1,
                            "guangxiu",
                            step_no,
                            300,
                            f"invalid-step-{step_no}",
                        )
            progress = get_craft_progress(1, "guangxiu")
            event_count = get_db().execute(
                "SELECT COUNT(*) AS count FROM points_event_inbox"
            ).fetchone()["count"]

        self.assertEqual(progress["completed_steps"], [])
        self.assertEqual(event_count, 0)

    def test_each_legal_step_records_one_processed_duration_event(self):
        with self.app.app_context():
            first = complete_craft_step(
                1,
                "guangxiu",
                1,
                600,
                "craft-event-1",
            )
            second = complete_craft_step(
                1,
                "guangxiu",
                2,
                300,
                "craft-event-2",
            )
            repeated = complete_craft_step(
                1,
                "guangxiu",
                1,
                600,
                "craft-event-1-repeat",
            )
            rows = [
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

        self.assertEqual(first["points_status"], "processed")
        self.assertEqual(second["points_status"], "processed")
        self.assertEqual(
            [row["source_event_id"] for row in rows],
            [
                "guangxiu|1:craft-event-1",
                "guangxiu|2:craft-event-2",
            ],
        )
        self.assertEqual(
            [row["duration_seconds"] for row in rows],
            [600, 300],
        )
        self.assertTrue(
            all(row["source_module"] == "handcraft" for row in rows)
        )
        self.assertTrue(all(row["event_type"] == "duration" for row in rows))
        self.assertTrue(all(row["status"] == "processed" for row in rows))
        self.assertEqual(repeated["status"], "already_completed")
        self.assertEqual(repeated["points_status"], "not_enqueued")
        self.assertEqual(len(rows), 2)

    def test_event_id_is_scoped_by_craft_and_step(self):
        with self.app.app_context():
            guangxiu_first = complete_craft_step(
                1,
                "guangxiu",
                1,
                600,
                "shared-event",
            )
            woodcarving_first = complete_craft_step(
                1,
                "chaoshan-woodcarving",
                1,
                300,
                "shared-event",
            )
            guangxiu_second = complete_craft_step(
                1,
                "guangxiu",
                2,
                300,
                "shared-event",
            )
            repeated = complete_craft_step(
                1,
                "guangxiu",
                1,
                600,
                "shared-event",
            )
            source_event_ids = [
                row["source_event_id"]
                for row in get_db().execute(
                    """
                    SELECT source_event_id
                    FROM points_event_inbox
                    ORDER BY id
                    """
                ).fetchall()
            ]

        self.assertEqual(
            source_event_ids,
            [
                "guangxiu|1:shared-event",
                "chaoshan-woodcarving|1:shared-event",
                "guangxiu|2:shared-event",
            ],
        )
        self.assertEqual(
            guangxiu_first["points_source_event_id"],
            "guangxiu|1:shared-event",
        )
        self.assertEqual(
            woodcarving_first["points_source_event_id"],
            "chaoshan-woodcarving|1:shared-event",
        )
        self.assertEqual(
            guangxiu_second["points_source_event_id"],
            "guangxiu|2:shared-event",
        )
        self.assertEqual(repeated["status"], "already_completed")
        self.assertEqual(len(source_event_ids), 3)

    def test_unavailable_provider_preserves_existing_progress_history(self):
        with self.app.app_context():
            completed = complete_craft_step(
                1,
                "guangxiu",
                1,
                600,
                "history-event",
            )
            set_craft_preset_provider(
                self.app,
                EmptyCraftPresetProvider(),
            )
            history = get_craft_progress(1, "guangxiu")
            rejected = complete_craft_step(
                1,
                "guangxiu",
                2,
                600,
                "history-next-event",
            )

        self.assertEqual(history["status"], "unavailable")
        self.assertFalse(history["available"])
        self.assertEqual(history["completed_steps"], [1])
        self.assertEqual(history["completed_step_count"], 1)
        self.assertEqual(history["updated_at"], completed["updated_at"])
        self.assertIsNone(history["resume_step_no"])

        self.assertFalse(rejected["accepted"])
        self.assertEqual(rejected["status"], "unavailable")
        self.assertEqual(rejected["completed_steps"], [1])
        self.assertEqual(rejected["completed_step_count"], 1)
        self.assertEqual(rejected["updated_at"], completed["updated_at"])
        self.assertIsNone(rejected["resume_step_no"])
        self.assertEqual(rejected["points_status"], "not_enqueued")

    def test_duplicate_provider_craft_key_is_unavailable(self):
        duplicate = copy.deepcopy(PLACEHOLDER_CRAFTS[0])
        set_craft_preset_provider(
            self.app,
            StaticCraftPresetProvider([duplicate, duplicate]),
        )

        with self.app.app_context():
            crafts = {
                craft["craft_key"]: craft
                for craft in list_crafts()
            }
            detail = get_craft("guangxiu")

        guangxiu = crafts["guangxiu"]
        self.assertFalse(guangxiu["available"])
        self.assertEqual(guangxiu["status"], "unavailable")
        self.assertIn("重复", guangxiu["unavailable_reason"])
        self.assertEqual(guangxiu["steps"], [])
        self.assertEqual(guangxiu["material_guide"], [])
        self.assertEqual(detail["available"], guangxiu["available"])
        self.assertEqual(detail["status"], guangxiu["status"])
        self.assertEqual(
            detail["unavailable_reason"],
            guangxiu["unavailable_reason"],
        )
        self.assertEqual(detail["steps"], guangxiu["steps"])
        self.assertEqual(
            detail["material_guide"],
            guangxiu["material_guide"],
        )

    def test_points_recording_failure_does_not_rollback_progress(self):
        with self.app.app_context():
            with patch(
                "app.handcraft_inheritance.crafts.record_duration_points",
                side_effect=RuntimeError("points unavailable"),
            ):
                result = complete_craft_step(
                    1,
                    "guangxiu",
                    1,
                    600,
                    "craft-event-failure",
                )
            progress = get_craft_progress(1, "guangxiu")
            event_count = get_db().execute(
                "SELECT COUNT(*) AS count FROM points_event_inbox"
            ).fetchone()["count"]

        self.assertTrue(result["accepted"])
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["points_status"], "failed")
        self.assertEqual(result["points_error"], "points unavailable")
        self.assertEqual(progress["completed_steps"], [1])
        self.assertEqual(progress["completed_step_count"], 1)
        self.assertEqual(event_count, 0)


if __name__ == "__main__":
    unittest.main()
