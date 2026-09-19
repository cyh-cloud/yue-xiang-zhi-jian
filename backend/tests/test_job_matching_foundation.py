import sqlite3
import tempfile
import unittest
from pathlib import Path

from app import create_app
from app.db import get_db
from app.job_matching import (
    install_default_job_matching_services,
    job_matching_bp,
)
from app.job_matching.constants import (
    AI_UNAVAILABLE_MESSAGE,
    APPLICATION_LABELS,
    SKILL_CATEGORIES,
)
from app.job_matching.errors import (
    AlreadyAppliedError,
    JobMatchingValidationError,
    JobUnavailableError,
    ResumeConflictError,
    ResumeRequiredError,
)


class JobMatchingFoundationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "test.db"
        self.app = self._create_app(self.database_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    @staticmethod
    def _create_app(database_path: Path):
        return create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(database_path),
                "SECRET_KEY": "test-only-secret",
            }
        )

    def test_tables_and_resume_columns_exist(self):
        with self.app.app_context():
            tables = {
                row["name"]
                for row in get_db().execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
            columns = {
                row["name"]
                for row in get_db().execute("PRAGMA table_info(resumes)")
            }
        self.assertTrue(
            {
                "resume_revisions",
                "resume_optimization_offers",
                "skill_visibility_settings",
                "job_favorites",
            }.issubset(tables)
        )
        self.assertTrue(
            {
                "education_json",
                "work_experiences_json",
                "skills_json",
                "version",
                "updated_at",
            }.issubset(columns)
        )

    def test_job_matching_prefix_requires_session(self):
        response = self.app.test_client().get("/api/job-matching/jobs")
        self.assertEqual(response.status_code, 401)

    def test_existing_resume_table_is_migrated(self):
        legacy_path = Path(self.temp_dir.name) / "legacy.db"
        connection = sqlite3.connect(legacy_path)
        connection.execute(
            """
            CREATE TABLE resumes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO resumes (user_id, created_at)
            VALUES (1, '2026-09-19T10:00:00+08:00')
            """
        )
        connection.commit()
        connection.close()

        legacy_app = self._create_app(legacy_path)
        with legacy_app.app_context():
            row = get_db().execute(
                """
                SELECT education_json, work_experiences_json,
                       skills_json, version, updated_at
                FROM resumes
                WHERE user_id = 1
                """
            ).fetchone()

        self.assertEqual(row["education_json"], "[]")
        self.assertEqual(row["work_experiences_json"], "[]")
        self.assertEqual(row["skills_json"], "[]")
        self.assertEqual(row["version"], 0)
        self.assertIsNone(row["updated_at"])

    def test_job_matching_constants_match_contract(self):
        self.assertEqual(
            SKILL_CATEGORIES,
            (
                "live_script",
                "simulation_training",
                "quiz_score",
                "learning_record",
            ),
        )
        self.assertEqual(
            APPLICATION_LABELS,
            {
                "pending": "待处理",
                "viewed": "已查看",
                "intent": "意向沟通",
                "unsuitable": "不合适",
                "closed": "岗位已关闭",
            },
        )
        self.assertEqual(AI_UNAVAILABLE_MESSAGE, "AI 服务暂时不可用")

    def test_job_matching_errors_expose_contract_fields(self):
        error_types = {
            ResumeRequiredError: "resume_required",
            AlreadyAppliedError: "already_applied",
            JobUnavailableError: "job_unavailable",
            ResumeConflictError: "resume_conflict",
            JobMatchingValidationError: "validation_error",
        }
        for error_type, expected_code in error_types.items():
            with self.subTest(error_type=error_type.__name__):
                error = error_type("测试错误")
                self.assertEqual(error.code, expected_code)
                self.assertEqual(error.message, "测试错误")
                self.assertEqual(error.details, {})

        error = ResumeRequiredError(
            "请先创建并保存简历",
            details={"resume": "required"},
        )
        self.assertEqual(error.details, {"resume": "required"})

    def test_job_matching_blueprint_is_registered(self):
        self.assertIn(job_matching_bp.name, self.app.blueprints)
        self.assertTrue(callable(install_default_job_matching_services))


if __name__ == "__main__":
    unittest.main()
