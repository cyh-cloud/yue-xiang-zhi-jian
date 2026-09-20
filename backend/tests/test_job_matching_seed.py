from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from werkzeug.security import generate_password_hash

from app import create_app
from app.db import get_db
from app.enterprise_console import seed_enterprise_console_fixtures
from app.enterprise_console.providers import set_job_position_provider
from app.job_matching.seed import (
    DEMO_RESUME,
    seed_job_matching_fixtures,
)
from app.seed import seed_courses, seed_interest_tags
from app.seed_dev import seed_local_data


DEMO_TIMESTAMP = "2026-09-19T10:00:00+08:00"
CLOSED_JOB_ID = "job-demo-deleted-for-007"
AVAILABLE_JOB_ID = "job-demo-approved"


class JobMatchingSeedTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = str(
            Path(self.temp_dir.name) / "job-matching-seed.db"
        )
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": self.database_path,
                "SECRET_KEY": "test-only-secret",
            }
        )

        with self.app.app_context():
            db = get_db()
            seed_interest_tags(db)
            seed_courses(db)
            self.student_id = self._insert_user(
                db,
                username="student_demo",
                name="本地学员",
                role="student",
            )
            self._insert_user(
                db,
                username="enterprise_demo",
                name="本地企业",
                role="enterprise",
            )
            db.execute(
                """
                INSERT INTO student_profiles (
                    user_id, learning_direction, updated_at
                )
                VALUES (?, 'comprehensive', ?)
                """,
                (self.student_id, DEMO_TIMESTAMP),
            )
            db.execute(
                """
                INSERT INTO resumes (user_id, created_at)
                VALUES (?, ?)
                """,
                (self.student_id, DEMO_TIMESTAMP),
            )
            self.expected_source_item_ids = self._insert_source_outcomes(
                db,
                self.student_id,
            )
            seed_enterprise_console_fixtures(db)
            db.commit()

    def tearDown(self):
        self.temp_dir.cleanup()

    @staticmethod
    def _insert_user(db, *, username, name, role):
        return int(
            db.execute(
                """
                INSERT INTO users (
                    username, password_hash, name, role, is_enabled,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, 1, ?, ?)
                """,
                (
                    username,
                    generate_password_hash("password8"),
                    name,
                    role,
                    DEMO_TIMESTAMP,
                    DEMO_TIMESTAMP,
                ),
            ).lastrowid
        )

    @staticmethod
    def _insert_source_outcomes(db, student_id):
        agriculture_course_id = int(
            db.execute(
                """
                SELECT id
                FROM courses
                WHERE title = '荔枝保果与采收管理'
                """
            ).fetchone()["id"]
        )
        agriculture_attempt_id = int(
            db.execute(
                """
                INSERT INTO agri_course_quiz_attempts (
                    user_id, course_id, answers_json, result_json,
                    score, is_formal, created_at
                )
                VALUES (?, ?, '{}', '{}', 90, 1, ?)
                """,
                (
                    student_id,
                    agriculture_course_id,
                    DEMO_TIMESTAMP,
                ),
            ).lastrowid
        )
        db.execute(
            """
            INSERT INTO agri_course_progress (
                user_id, course_id, duration_seconds,
                furthest_position_seconds, resume_position_seconds,
                progress_percent, watched_seconds, completed_at,
                last_viewed_at, updated_at
            )
            VALUES (?, 1001, 300, 80, 80, 100, 80, ?, ?, ?)
            """,
            (
                student_id,
                DEMO_TIMESTAMP,
                DEMO_TIMESTAMP,
                DEMO_TIMESTAMP,
            ),
        )
        handcraft_course_id = int(
            db.execute(
                """
                SELECT id
                FROM courses
                WHERE title = '竹编基础与产品设计'
                """
            ).fetchone()["id"]
        )
        db.execute(
            """
            INSERT INTO agri_course_progress (
                user_id, course_id, duration_seconds,
                furthest_position_seconds, resume_position_seconds,
                progress_percent, watched_seconds, completed_at,
                last_viewed_at, updated_at
            )
            VALUES (?, ?, 300, 40, 40, 13, 40, NULL, ?, ?)
            """,
            (
                student_id,
                handcraft_course_id,
                DEMO_TIMESTAMP,
                DEMO_TIMESTAMP,
            ),
        )
        return sorted(
            (
                f"agriculture:course_quiz:{agriculture_attempt_id}",
                "ecommerce:course_completion:1001",
                f"handcraft:course_view:{handcraft_course_id}",
            )
        )

    def test_seed_is_idempotent_and_uses_real_source_ids(self):
        with self.app.app_context():
            db = get_db()
            first = seed_job_matching_fixtures(db)
            db.commit()
            second = seed_job_matching_fixtures(db)
            db.commit()

            self.assertEqual(first["resumes"], second["resumes"])
            self.assertEqual(
                db.execute(
                    "SELECT COUNT(*) AS count FROM job_favorites"
                ).fetchone()["count"],
                first["favorites"],
            )
            self.assertEqual(
                db.execute(
                    "SELECT COUNT(*) AS count FROM resume_revisions"
                ).fetchone()["count"],
                first["resume_revisions"],
            )

            resume = db.execute(
                """
                SELECT id, version, education_json, work_experiences_json,
                       skills_json, updated_at
                FROM resumes
                WHERE user_id = ?
                """,
                (self.student_id,),
            ).fetchone()
            revisions = db.execute(
                """
                SELECT version, education_json, work_experiences_json,
                       skills_json, saved_at
                FROM resume_revisions
                WHERE resume_id = ?
                ORDER BY version
                """,
                (resume["id"],),
            ).fetchall()
            visibility_rows = db.execute(
                """
                SELECT item_id, visible
                FROM skill_visibility_settings
                WHERE user_id = ?
                ORDER BY item_id
                """,
                (self.student_id,),
            ).fetchall()
            favorites = {
                row["job_id"]: row
                for row in db.execute(
                    """
                    SELECT *
                    FROM job_favorites
                    WHERE user_id = ?
                    ORDER BY job_id
                    """,
                    (self.student_id,),
                ).fetchall()
            }

            self.assertEqual(first, second)
            self.assertEqual(resume["version"], 1)
            self.assertEqual(
                json.loads(resume["education_json"]),
                DEMO_RESUME["education_experiences"],
            )
            self.assertEqual(
                json.loads(resume["work_experiences_json"]),
                DEMO_RESUME["work_experiences"],
            )
            self.assertEqual(
                json.loads(resume["skills_json"]),
                DEMO_RESUME["skills"],
            )
            self.assertEqual(len(revisions), 1)
            self.assertEqual(revisions[0]["version"], 1)
            self.assertEqual(
                json.loads(revisions[0]["education_json"]),
                DEMO_RESUME["education_experiences"],
            )
            self.assertEqual(
                json.loads(revisions[0]["work_experiences_json"]),
                DEMO_RESUME["work_experiences"],
            )
            self.assertEqual(
                json.loads(revisions[0]["skills_json"]),
                DEMO_RESUME["skills"],
            )
            self.assertEqual(
                {
                    "item_id": visibility_rows[0]["item_id"],
                    "visible": visibility_rows[0]["visible"],
                },
                {
                    "item_id": self.expected_source_item_ids[0],
                    "visible": 1,
                },
            )
            self.assertEqual(
                {
                    "item_id": visibility_rows[1]["item_id"],
                    "visible": visibility_rows[1]["visible"],
                },
                {
                    "item_id": self.expected_source_item_ids[1],
                    "visible": 0,
                },
            )
            self.assertEqual(first["visibility"], 2)
            self.assertEqual(first["visible"], 1)
            self.assertEqual(first["hidden"], 1)
            self.assertEqual(set(favorites), {AVAILABLE_JOB_ID, CLOSED_JOB_ID})

            available = db.execute(
                """
                SELECT positions.title, positions.salary,
                       positions.location, positions.description,
                       users.name AS enterprise_name
                FROM job_positions AS positions
                JOIN users ON users.id = positions.enterprise_id
                WHERE positions.job_id = ?
                  AND positions.review_status = 'approved'
                  AND positions.deleted_at IS NULL
                """,
                (AVAILABLE_JOB_ID,),
            ).fetchone()
            self.assertIsNotNone(available)
            favorite = favorites[AVAILABLE_JOB_ID]
            self.assertEqual(favorite["title_snapshot"], available["title"])
            self.assertEqual(
                favorite["enterprise_name_snapshot"],
                available["enterprise_name"],
            )
            self.assertEqual(
                favorite["salary_snapshot"],
                available["salary"],
            )
            self.assertEqual(
                favorite["location_snapshot"],
                available["location"],
            )
            self.assertEqual(
                favorite["description_snapshot"],
                available["description"],
            )
            self.assertIsNone(
                db.execute(
                    """
                    SELECT 1
                    FROM job_positions
                    WHERE job_id = ?
                    """,
                    (CLOSED_JOB_ID,),
                ).fetchone()
            )
            self.assertEqual(
                db.execute(
                    "SELECT COUNT(*) AS count FROM job_positions"
                ).fetchone()["count"],
                3,
            )
            self.assertEqual(
                db.execute(
                    "SELECT COUNT(*) AS count FROM system_notifications"
                ).fetchone()["count"],
                0,
            )
            self.assertEqual(
                db.execute(
                    """
                    SELECT COUNT(*) AS count
                    FROM enterprise_notification_outbox
                    """
                ).fetchone()["count"],
                0,
            )

    def test_seed_skips_visibility_rows_for_absent_source_outcomes(self):
        with self.app.app_context():
            db = get_db()
            db.execute(
                "DELETE FROM agri_course_quiz_attempts WHERE user_id = ?",
                (self.student_id,),
            )
            db.execute(
                "DELETE FROM agri_course_progress WHERE user_id = ?",
                (self.student_id,),
            )
            db.execute(
                """
                DELETE FROM handcraft_learning_outcomes
                WHERE user_id = ?
                """,
                (self.student_id,),
            )
            db.commit()

            result = seed_job_matching_fixtures(db)
            db.commit()

            self.assertEqual(result["visibility"], 0)
            self.assertEqual(
                db.execute(
                    """
                    SELECT COUNT(*) AS count
                    FROM skill_visibility_settings
                    WHERE user_id = ?
                    """,
                    (self.student_id,),
                ).fetchone()["count"],
                0,
            )

    def test_available_favorite_uses_job_position_provider(self):
        class ReplacementJobPositionProvider:
            def __init__(self):
                self.get_calls = []

            def list_published_positions(self):
                return []

            def get_published_position(self, *, job_id):
                self.get_calls.append(job_id)
                return {
                    "job_id": job_id,
                    "enterprise_id": 2,
                    "enterprise_name": "Provider 企业",
                    "title": "Provider 岗位",
                    "salary": "9k-12k",
                    "location": "深圳",
                    "category_id": 1,
                    "category_name": "Provider 类别",
                    "description": "Provider 岗位描述",
                    "review_status": "approved",
                    "version": 3,
                    "published_at": DEMO_TIMESTAMP,
                    "updated_at": DEMO_TIMESTAMP,
                }

        provider = ReplacementJobPositionProvider()
        set_job_position_provider(self.app, provider)

        with self.app.app_context():
            result = seed_job_matching_fixtures(get_db())
            favorite = get_db().execute(
                """
                SELECT *
                FROM job_favorites
                WHERE user_id = ? AND job_id = ?
                """,
                (self.student_id, AVAILABLE_JOB_ID),
            ).fetchone()

        self.assertEqual(provider.get_calls, [AVAILABLE_JOB_ID])
        self.assertEqual(result["favorites"], 2)
        self.assertEqual(favorite["title_snapshot"], "Provider 岗位")
        self.assertEqual(
            favorite["enterprise_name_snapshot"],
            "Provider 企业",
        )
        self.assertEqual(favorite["salary_snapshot"], "9k-12k")
        self.assertEqual(favorite["location_snapshot"], "深圳")
        self.assertEqual(
            favorite["description_snapshot"],
            "Provider 岗位描述",
        )

    def test_seed_local_data_wires_demo_fixtures_idempotently(self):
        environment = {
            "DEV_SEED_PASSWORD": "local-password",
            "SECRET_KEY": "local-secret",
        }
        with patch.dict(os.environ, environment, clear=True):
            first = seed_local_data(self.database_path)
            second = seed_local_data(self.database_path)

        summary_keys = (
            "job_matching_resumes",
            "job_matching_resume_revisions",
            "job_matching_tags",
            "job_matching_visibility",
            "job_matching_visible",
            "job_matching_hidden",
            "job_matching_favorites",
        )
        for key in summary_keys:
            self.assertEqual(first[key], second[key])

        self.assertEqual(first["job_matching_resumes"], 1)
        self.assertEqual(first["job_matching_resume_revisions"], 1)
        self.assertEqual(first["job_matching_tags"], 4)
        self.assertEqual(first["job_matching_visibility"], 2)
        self.assertEqual(first["job_matching_visible"], 1)
        self.assertEqual(first["job_matching_hidden"], 1)
        self.assertEqual(first["job_matching_favorites"], 2)

        with self.app.app_context():
            db = get_db()
            self.assertEqual(
                db.execute(
                    "SELECT COUNT(*) AS count FROM resume_revisions"
                ).fetchone()["count"],
                1,
            )
            self.assertEqual(
                db.execute(
                    """
                    SELECT COUNT(*) AS count
                    FROM skill_visibility_settings
                    WHERE user_id = ?
                    """,
                    (self.student_id,),
                ).fetchone()["count"],
                2,
            )
            self.assertEqual(
                db.execute(
                    "SELECT COUNT(*) AS count FROM job_favorites"
                ).fetchone()["count"],
                2,
            )
            self.assertEqual(
                db.execute(
                    "SELECT COUNT(*) AS count FROM system_notifications"
                ).fetchone()["count"],
                0,
            )


if __name__ == "__main__":
    unittest.main()
