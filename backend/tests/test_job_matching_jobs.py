from __future__ import annotations

import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

from app import create_app
from app.db import get_db
from app.enterprise_console.providers import set_job_position_provider
from app.job_matching import jobs
from app.job_matching.errors import JobUnavailableError
from app.tags.service import replace_student_tags


JOB_FIELDS = {
    "job_id",
    "enterprise_id",
    "enterprise_name",
    "title",
    "salary",
    "location",
    "category_id",
    "category_name",
    "description",
    "review_status",
    "version",
    "published_at",
    "updated_at",
}

RECENT_OUTCOME = {
    "item_id": "ecommerce:course_completion:31",
    "category": "learning_record",
    "source_module": "ecommerce",
    "source_type": "course_completion",
    "title": "电子商务课程",
    "summary": "电子商务课程",
    "score": None,
    "is_formal": False,
    "occurred_at": "2026-09-19T10:00:00+08:00",
    "source_available": True,
}


def make_job(
    job_id: str,
    *,
    category_id: int,
    published_at: str,
) -> dict:
    return {
        "job_id": job_id,
        "enterprise_id": 2,
        "enterprise_name": "荔乡电商",
        "title": f"岗位 {job_id}",
        "salary": "7k-9k",
        "location": "佛山",
        "category_id": category_id,
        "category_name": f"类别 {category_id}",
        "description": "负责直播运营。",
        "review_status": "approved",
        "version": 1,
        "published_at": published_at,
        "updated_at": "2026-09-18T09:00:00+08:00",
    }


class ReplacementJobPositionProvider:
    def __init__(self, positions: list[dict]):
        self._positions = {
            position["job_id"]: position
            for position in positions
        }
        self.list_calls = 0
        self.get_calls = []

    def list_published_positions(self) -> list[dict]:
        self.list_calls += 1
        return list(self._positions.values())

    def get_published_position(self, *, job_id: str) -> dict | None:
        self.get_calls.append(job_id)
        return self._positions.get(job_id)

    def remove(self, job_id: str) -> None:
        self._positions.pop(job_id, None)


class JobMatchingJobsTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(
                    Path(self.temp_dir.name) / "test.db"
                ),
                "SECRET_KEY": "test-only-secret",
            }
        )

        with self.app.app_context():
            db = get_db()
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
                    "job-student",
                    "test-password-hash",
                    "岗位测试学员",
                    "2026-09-19T10:00:00+08:00",
                    "2026-09-19T10:00:00+08:00",
                ),
            )
            self.student_id = int(cursor.lastrowid)
            db.execute(
                """
                INSERT INTO student_profiles (
                    user_id,
                    contact,
                    learning_direction,
                    updated_at
                )
                VALUES (?, '', 'ecommerce', ?)
                """,
                (
                    self.student_id,
                    "2026-09-19T10:00:00+08:00",
                ),
            )
            db.execute(
                """
                INSERT INTO student_interest_tags (user_id, tag_id)
                VALUES (?, 10)
                """,
                (self.student_id,),
            )
            db.commit()

    def _set_provider(
        self,
        *positions: dict,
    ) -> ReplacementJobPositionProvider:
        provider = ReplacementJobPositionProvider(list(positions))
        set_job_position_provider(self.app, provider)
        return provider

    def test_list_projects_sorts_and_recommends_by_category_match(self):
        intent_job = {
            "job_id": "job-intent",
            "enterprise_id": 2,
            "enterprise_name": "荔乡电商",
            "title": "电商运营",
            "salary": "7k-9k",
            "location": "佛山",
            "category_id": 10,
            "category_name": "电商运营",
            "description": "负责直播运营。",
            "review_status": "approved",
            "version": 1,
            "published_at": "2026-09-18T09:00:00+08:00",
            "updated_at": "2026-09-18T09:00:00+08:00",
        }
        newest_job = make_job(
            "job-newest",
            category_id=11,
            published_at="2026-09-19T09:00:00+08:00",
        )
        tie_a = make_job(
            "job-tie-a",
            category_id=11,
            published_at="2026-09-18T10:00:00+08:00",
        )
        tie_b = make_job(
            "job-tie-b",
            category_id=11,
            published_at="2026-09-18T10:00:00+08:00",
        )
        self._set_provider(tie_b, intent_job, newest_job, tie_a)

        with (
            self.app.app_context(),
            patch.object(
                jobs,
                "list_skill_outcomes",
                return_value=[RECENT_OUTCOME],
            ),
        ):
            result = jobs.list_published_jobs(self.student_id)

        self.assertEqual(
            set(result),
            {"jobs", "recommended_jobs"},
        )
        self.assertEqual(
            [job["job_id"] for job in result["jobs"]],
            [
                "job-newest",
                "job-tie-a",
                "job-tie-b",
                "job-intent",
            ],
        )
        self.assertEqual(
            [job["job_id"] for job in result["recommended_jobs"]],
            [
                "job-intent",
                "job-newest",
                "job-tie-a",
                "job-tie-b",
            ],
        )
        self.assertEqual(
            set(result["jobs"][0]),
            JOB_FIELDS,
        )
        self.assertEqual(
            result["recommended_jobs"][0]["category_match_count"],
            1,
        )
        self.assertEqual(
            result["recommended_jobs"][0]["recent_learning"],
            True,
        )
        self.assertEqual(
            result["recommended_jobs"][0]["latest_learning_at"],
            RECENT_OUTCOME["occurred_at"],
        )
        self.assertEqual(result["jobs"][-1], intent_job)

    def test_interest_tag_change_reads_latest_profile_value(self):
        intent_job = make_job(
            "job-intent",
            category_id=10,
            published_at="2026-09-18T09:00:00+08:00",
        )
        newest_job = make_job(
            "job-newest",
            category_id=11,
            published_at="2026-09-19T09:00:00+08:00",
        )
        self._set_provider(intent_job, newest_job)

        with (
            self.app.app_context(),
            patch.object(
                jobs,
                "list_skill_outcomes",
                return_value=[RECENT_OUTCOME],
            ),
        ):
            before = jobs.list_published_jobs(self.student_id)
            replace_student_tags(self.student_id, [11])
            after = jobs.list_published_jobs(self.student_id)

        self.assertEqual(
            before["recommended_jobs"][0]["job_id"],
            "job-intent",
        )
        self.assertEqual(
            before["recommended_jobs"][0]["category_match_count"],
            1,
        )
        self.assertEqual(
            after["recommended_jobs"][0]["job_id"],
            "job-newest",
        )
        self.assertEqual(
            after["recommended_jobs"][0]["category_match_count"],
            1,
        )
        self.assertEqual(
            after["recommended_jobs"][1]["job_id"],
            "job-intent",
        )
        self.assertEqual(
            after["recommended_jobs"][1]["category_match_count"],
            0,
        )

    def test_parsed_times_drive_published_and_learning_order(self):
        raw_string_first = make_job(
            "job-raw-string-first",
            category_id=11,
            published_at="2026-09-18T09:00:00+08:00",
        )
        parsed_time_later = make_job(
            "job-parsed-time-later",
            category_id=12,
            published_at="2026-09-18T02:30:00+00:00",
        )
        older_learning = {
            **RECENT_OUTCOME,
            "item_id": "ecommerce:course_completion:31",
            "occurred_at": "2026-09-18T09:00:00+08:00",
        }
        newer_learning = {
            **RECENT_OUTCOME,
            "item_id": "handcraft:course_view:41",
            "source_module": "handcraft",
            "source_type": "course_view",
            "occurred_at": "2026-09-18T02:00:00+00:00",
        }
        self._set_provider(raw_string_first, parsed_time_later)

        with (
            self.app.app_context(),
            patch.object(jobs, "datetime") as mocked_datetime,
            patch.object(
                jobs,
                "list_skill_outcomes",
                return_value=[older_learning, newer_learning],
            ),
        ):
            mocked_datetime.fromisoformat.side_effect = (
                datetime.fromisoformat
            )
            mocked_datetime.now.return_value = datetime(
                2026,
                9,
                20,
                12,
                0,
                tzinfo=ZoneInfo("Asia/Shanghai"),
            )
            result = jobs.list_published_jobs(self.student_id)

        self.assertEqual(
            [job["job_id"] for job in result["jobs"]],
            ["job-parsed-time-later", "job-raw-string-first"],
        )
        for job in result["recommended_jobs"]:
            self.assertEqual(
                job["latest_learning_at"],
                newer_learning["occurred_at"],
            )
            self.assertTrue(job["recent_learning"])

    def test_old_learning_is_not_recent(self):
        job = make_job(
            "job-old-learning",
            category_id=10,
            published_at="2026-09-18T09:00:00+08:00",
        )
        old_outcome = {
            **RECENT_OUTCOME,
            "occurred_at": "2026-01-01T09:00:00+08:00",
        }
        self._set_provider(job)

        with (
            self.app.app_context(),
            patch.object(jobs, "datetime") as mocked_datetime,
            patch.object(
                jobs,
                "list_skill_outcomes",
                return_value=[old_outcome],
            ),
        ):
            mocked_datetime.fromisoformat.side_effect = (
                datetime.fromisoformat
            )
            mocked_datetime.now.return_value = datetime(
                2026,
                9,
                20,
                12,
                0,
                tzinfo=ZoneInfo("Asia/Shanghai"),
            )
            result = jobs.list_published_jobs(self.student_id)

        recommendation = result["recommended_jobs"][0]
        self.assertFalse(recommendation["recent_learning"])
        self.assertIsNone(recommendation["latest_learning_at"])

    def test_detail_uses_current_provider_and_returns_none_after_removal(self):
        job = make_job(
            "job-removable",
            category_id=10,
            published_at="2026-09-18T09:00:00+08:00",
        )
        provider = self._set_provider(job)

        with (
            self.app.app_context(),
            patch.object(
                jobs,
                "list_skill_outcomes",
                return_value=[],
            ),
        ):
            listed = jobs.list_published_jobs(self.student_id)
            detail = jobs.get_published_job(
                self.student_id,
                "job-removable",
            )
            provider.remove("job-removable")
            removed = jobs.get_published_job(
                self.student_id,
                "job-removable",
            )

        self.assertEqual(
            listed["jobs"][0]["job_id"],
            "job-removable",
        )
        self.assertEqual(detail, job)
        self.assertIsNone(removed)
        self.assertEqual(
            provider.get_calls,
            ["job-removable", "job-removable"],
        )

    def test_projection_omits_extra_fields_and_rejects_missing_fields(self):
        job = {
            **make_job(
                "job-projected",
                category_id=10,
                published_at="2026-09-18T09:00:00+08:00",
            ),
            "internal_secret": "must-not-leak",
        }
        self._set_provider(job)

        with (
            self.app.app_context(),
            patch.object(
                jobs,
                "list_skill_outcomes",
                return_value=[],
            ),
        ):
            result = jobs.list_published_jobs(self.student_id)
            self.assertEqual(set(result["jobs"][0]), JOB_FIELDS)
            self.assertNotIn(
                "internal_secret",
                result["jobs"][0],
            )

            missing_description = {
                key: value
                for key, value in job.items()
                if key != "description"
            }
            self._set_provider(missing_description)
            with self.assertRaises(JobUnavailableError) as raised:
                jobs.list_published_jobs(self.student_id)

        self.assertEqual(raised.exception.message, "岗位数据字段不完整")
        self.assertEqual(
            raised.exception.details,
            {"missing": ["description"]},
        )


if __name__ == "__main__":
    unittest.main()
