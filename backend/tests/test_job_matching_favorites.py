from __future__ import annotations

import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from app import create_app
from app.db import get_db
from app.enterprise_console.providers import set_job_position_provider
from app.job_matching.errors import JobUnavailableError
from app.job_matching.favorites import (
    add_favorite,
    list_favorites,
    remove_favorite,
)


JOB = {
    "job_id": "job-1",
    "enterprise_id": 20,
    "enterprise_name": "荔乡电商",
    "title": "电商运营",
    "salary": "7k-9k",
    "location": "佛山",
    "category_id": 10,
    "category_name": "电商运营",
    "description": "负责直播运营。",
    "review_status": "approved",
    "version": 1,
    "published_at": "2026-09-19T09:00:00+08:00",
    "updated_at": "2026-09-19T09:00:00+08:00",
}

JOB_TITLE_CHANGED = {
    **JOB,
    "enterprise_name": "新企业名称",
    "title": "新职位标题",
    "salary": "9k-12k",
    "location": "广州",
    "description": "负责新的岗位工作。",
    "version": 2,
    "updated_at": "2026-09-19T10:00:00+08:00",
}

SECOND_JOB = {
    **JOB,
    "job_id": "job-2",
    "title": "农产品运营",
    "salary": "6k-8k",
    "location": "茂名",
    "description": "负责农产品线上运营。",
}


class RecordingJobPositionProvider:
    def __init__(self, jobs: list[dict]):
        self.set_jobs(jobs)
        self.list_calls = 0
        self.get_calls = []

    def set_jobs(self, jobs: list[dict]) -> None:
        self.jobs = {job["job_id"]: job for job in jobs}

    def list_published_positions(self) -> list[dict]:
        self.list_calls += 1
        return list(self.jobs.values())

    def get_published_position(self, *, job_id: str) -> dict | None:
        self.get_calls.append(job_id)
        return self.jobs.get(job_id)


class JobMatchingFavoriteTests(unittest.TestCase):
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
        self.student_id = self._create_student("favorite-student-a")
        self.other_student_id = self._create_student(
            "favorite-student-b"
        )
        self.job_provider = RecordingJobPositionProvider([JOB])
        set_job_position_provider(self.app, self.job_provider)

    def _create_student(self, username: str) -> int:
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
                    username,
                    "test-password-hash",
                    f"收藏测试-{username}",
                    "2026-09-19T10:00:00+08:00",
                    "2026-09-19T10:00:00+08:00",
                ),
            )
            student_id = int(cursor.lastrowid)
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
                    student_id,
                    "2026-09-19T10:00:00+08:00",
                ),
            )
            db.commit()
        return student_id

    def test_add_is_idempotent_and_closed_favorite_recovers(self):
        with self.app.app_context():
            first = add_favorite(self.student_id, "job-1")
            second = add_favorite(self.student_id, "job-1")
            self.assertEqual(first["job_id"], second["job_id"])
            self.assertEqual(len(list_favorites(self.student_id)), 1)

            job_provider = self.job_provider
            job_provider.set_jobs([])
            closed = list_favorites(self.student_id)[0]
            self.assertTrue(closed["closed"])
            self.assertEqual(closed["title"], "电商运营")
            self.assertEqual(closed["title_snapshot"], "电商运营")

            job_fixture_title_changed = JOB_TITLE_CHANGED
            job_provider.set_jobs([job_fixture_title_changed])
            reopened = list_favorites(self.student_id)[0]
            self.assertFalse(reopened["closed"])
            self.assertEqual(reopened["title"], "新职位标题")

            job_provider.set_jobs([])
            closed_again = list_favorites(self.student_id)[0]
            self.assertTrue(closed_again["closed"])
            self.assertEqual(closed_again["title"], "新职位标题")
            self.assertEqual(
                closed_again["salary"],
                job_fixture_title_changed["salary"],
            )
            self.assertEqual(
                closed_again["enterprise_name"],
                job_fixture_title_changed["enterprise_name"],
            )
            self.assertEqual(
                closed_again["location"],
                job_fixture_title_changed["location"],
            )
            self.assertEqual(
                closed_again["description"],
                job_fixture_title_changed["description"],
            )

            remove_favorite(self.student_id, "job-1")
            self.assertEqual(list_favorites(self.student_id), [])

    def test_duplicate_add_refreshes_snapshot_and_keeps_favorite_time(self):
        with self.app.app_context():
            first = add_favorite(self.student_id, "job-1")
            self.job_provider.set_jobs([JOB_TITLE_CHANGED])
            second = add_favorite(self.student_id, "job-1")

            self.assertEqual(
                second["favorited_at"],
                first["favorited_at"],
            )
            self.assertEqual(second["title"], "新职位标题")
            self.assertEqual(second["title_snapshot"], "新职位标题")
            self.assertEqual(len(list_favorites(self.student_id)), 1)

            self.job_provider.set_jobs([])
            closed = list_favorites(self.student_id)[0]
            self.assertEqual(closed["title"], "新职位标题")
            self.assertEqual(closed["salary"], "9k-12k")

    def test_unavailable_job_cannot_be_favorited(self):
        self.job_provider.set_jobs([])

        with (
            self.app.app_context(),
            self.assertRaises(JobUnavailableError) as raised,
        ):
            add_favorite(self.student_id, "job-1")

        self.assertEqual(
            raised.exception.message,
            "岗位已关闭或暂不可收藏",
        )
        with self.app.app_context():
            self.assertEqual(list_favorites(self.student_id), [])

    def test_favorites_and_removal_are_student_scoped(self):
        self.job_provider.set_jobs([JOB, SECOND_JOB])

        with self.app.app_context():
            add_favorite(self.student_id, "job-1")
            add_favorite(self.other_student_id, "job-1")
            add_favorite(self.student_id, "job-2")

            self.assertEqual(
                {item["job_id"] for item in list_favorites(self.student_id)},
                {"job-1", "job-2"},
            )
            self.assertEqual(
                [item["job_id"] for item in list_favorites(
                    self.other_student_id
                )],
                ["job-1"],
            )

            remove_favorite(self.student_id, "job-1")

            self.assertEqual(
                [item["job_id"] for item in list_favorites(
                    self.student_id
                )],
                ["job-2"],
            )
            self.assertEqual(
                [item["job_id"] for item in list_favorites(
                    self.other_student_id
                )],
                ["job-1"],
            )

    def test_remove_is_idempotent_and_returns_stable_shape(self):
        with self.app.app_context():
            add_favorite(self.student_id, "job-1")
            first = remove_favorite(self.student_id, "job-1")
            second = remove_favorite(self.student_id, "job-1")

            self.assertEqual(
                first,
                {"job_id": "job-1", "favorited": False},
            )
            self.assertEqual(second, first)
            self.assertEqual(list_favorites(self.student_id), [])

    def test_favorite_timestamp_is_timezone_aware(self):
        with self.app.app_context():
            favorite = add_favorite(self.student_id, "job-1")

        favorited_at = datetime.fromisoformat(favorite["favorited_at"])
        self.assertIsNotNone(favorited_at.utcoffset())
        self.assertTrue(favorite["favorited_at"].endswith("+08:00"))


if __name__ == "__main__":
    unittest.main()
