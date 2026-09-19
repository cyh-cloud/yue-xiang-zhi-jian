import json
import sqlite3
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from app import create_app
from app.agri_skills.ai_client import set_ai_client
from app.agri_skills.ai_context import (
    AI_CALL_DOMAINS,
    AI_FIELD_ALLOWLISTS,
    build_ai_messages,
)
from app.agri_skills.errors import AiUnavailableError
from app.db import get_db
from app.job_matching.errors import (
    JobMatchingValidationError,
    ResumeConflictError,
    ResumeRequiredError,
)
from app.job_matching.resume_ai import (
    _owned_offer,
    adopt_resume_optimization,
    discard_resume_optimization,
    optimize_resume,
)
from app.job_matching.resumes import get_resume, save_resume


_UNSET = object()


def _valid_ai_response() -> dict:
    return {
        "suggestions": ["补充量化成果"],
        "rewritten_resume": {
            "education_experiences": [],
            "work_experiences": [
                {
                    "company": "示范农场",
                    "role": "运营助理",
                    "start_date": "2025-07",
                    "end_date": "2026-06",
                    "description": "直播转化率提升 20%。",
                }
            ],
            "skills": ["直播运营"],
        },
    }


class FakeAi:
    def __init__(self, response=_UNSET, error=None):
        self.calls = []
        self.response = (
            _valid_ai_response() if response is _UNSET else response
        )
        self.error = error

    def complete_json(self, messages, *, call_point):
        self.calls.append((messages, call_point))
        if self.error is not None:
            raise self.error
        return self.response


class JobMatchingResumeAiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "test.db"
        self.app = self._create_app(self.database_path)

        with self.app.app_context():
            db = get_db()
            self.student_id = self._insert_student(db, "student-1")
            self.other_student_id = self._insert_student(db, "student-2")
            db.commit()

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
        student_id = int(cursor.lastrowid)
        db.execute(
            """
            INSERT INTO resumes (user_id, created_at)
            VALUES (?, ?)
            """,
            (student_id, timestamp),
        )
        return student_id

    @staticmethod
    def _valid_payload() -> dict:
        return {
            "education_experiences": [
                {
                    "school": "广东职业学院",
                    "major": "电子商务",
                    "degree": "专科",
                    "start_date": "2022-09",
                    "end_date": "2025-06",
                }
            ],
            "work_experiences": [
                {
                    "company": "示范农场",
                    "role": "运营助理",
                    "start_date": "2025-07",
                    "end_date": "2026-06",
                    "description": "负责直播数据记录。",
                }
            ],
            "skills": ["直播运营", "客户沟通"],
        }

    def _seed_saved_resume(self) -> dict:
        return save_resume(
            self.student_id,
            self._valid_payload(),
            expected_version=0,
        )

    def test_resume_optimize_registers_minimal_job_matching_allowlist(self):
        self.assertEqual(
            AI_FIELD_ALLOWLISTS["resume_optimize"],
            {
                "education_experiences",
                "work_experiences",
                "skills",
            },
        )
        self.assertEqual(
            AI_CALL_DOMAINS["resume_optimize"],
            "就业对接任务",
        )
        self.assertEqual(
            AI_CALL_DOMAINS["qa_answer"],
            "农业技能任务",
        )
        self.assertEqual(
            AI_CALL_DOMAINS["live_script_generate"],
            "电商运营实训任务",
        )
        self.assertEqual(
            AI_CALL_DOMAINS["handcraft_ar_guidance_generate"],
            "手工传承任务",
        )

        messages = build_ai_messages(
            "resume_optimize",
            {
                "education_experiences": [{"school": "广东职业学院"}],
                "work_experiences": [{"company": "示范农场"}],
                "skills": ["直播运营"],
                "contact": "13800000000",
                "student_id": 99,
                "interest_tags": ["job:ecommerce"],
            },
        )

        self.assertEqual(
            messages[0]["content"],
            "就业对接任务：resume_optimize",
        )
        self.assertEqual(
            json.loads(messages[1]["content"]),
            {
                "education_experiences": [{"school": "广东职业学院"}],
                "work_experiences": [{"company": "示范农场"}],
                "skills": ["直播运营"],
            },
        )

    def test_optimize_previews_then_adoption_saves_one_new_revision(self):
        with self.app.app_context():
            initial = self._seed_saved_resume()
            fake = FakeAi()
            set_ai_client(self.app, fake)

            offer = optimize_resume(
                self.student_id,
                expected_version=initial["version"],
            )

            self.assertEqual(offer["status"], "offered")
            self.assertEqual(offer["suggestions"], ["补充量化成果"])
            self.assertEqual(offer["base_version"], 1)
            self.assertTrue(offer["offer_id"].startswith("resume-offer-"))
            self.assertTrue(offer["created_at"].endswith("+08:00"))
            self.assertNotIn("contact", json.dumps(offer, ensure_ascii=False))
            self.assertNotIn("student_id", json.dumps(offer, ensure_ascii=False))
            self.assertIn(
                "20%",
                offer["rewritten_resume"]["work_experiences"][0]["description"],
            )
            self.assertEqual(len(fake.calls), 1)
            self.assertEqual(fake.calls[0][1], "resume_optimize")
            self.assertEqual(
                set(json.loads(fake.calls[0][0][1]["content"])),
                {
                    "education_experiences",
                    "work_experiences",
                    "skills",
                },
            )
            self.assertEqual(
                get_resume(self.student_id)["version"],
                1,
            )

            adopted = adopt_resume_optimization(
                self.student_id,
                offer["offer_id"],
                expected_version=1,
            )

            self.assertEqual(adopted["version"], 2)
            self.assertIn("20%", adopted["work_experiences"][0]["description"])
            self.assertTrue(adopted["saved_at"].endswith("+08:00"))

            stored_offer = get_db().execute(
                """
                SELECT status, resolved_at
                FROM resume_optimization_offers
                WHERE offer_id = ?
                """,
                (offer["offer_id"],),
            ).fetchone()
            revisions = get_db().execute(
                """
                SELECT version
                FROM resume_revisions
                WHERE resume_id = (
                    SELECT id FROM resumes WHERE user_id = ?
                )
                ORDER BY version
                """,
                (self.student_id,),
            ).fetchall()

        self.assertEqual(stored_offer["status"], "adopted")
        self.assertTrue(stored_offer["resolved_at"].endswith("+08:00"))
        self.assertEqual([int(row["version"]) for row in revisions], [1, 2])
        self.assertEqual(
            datetime.fromisoformat(offer["created_at"]).utcoffset().total_seconds(),
            8 * 60 * 60,
        )

    def test_optimize_rejects_empty_resume_without_calling_ai(self):
        with self.app.app_context():
            fake = FakeAi()
            set_ai_client(self.app, fake)

            with self.assertRaises(ResumeRequiredError) as raised:
                optimize_resume(self.student_id, expected_version=0)

            offer_count = get_db().execute(
                "SELECT COUNT(*) AS count FROM resume_optimization_offers"
            ).fetchone()["count"]
            current = get_resume(self.student_id)

        self.assertEqual(raised.exception.code, "resume_required")
        self.assertEqual(raised.exception.message, "请先创建并保存简历")
        self.assertEqual(fake.calls, [])
        self.assertEqual(offer_count, 0)
        self.assertEqual(current["version"], 0)
        self.assertFalse(current["has_saved_resume"])

    def test_discard_marks_offer_without_mutating_resume(self):
        with self.app.app_context():
            self._seed_saved_resume()
            set_ai_client(self.app, FakeAi())
            offer = optimize_resume(self.student_id, expected_version=1)
            before = get_resume(self.student_id)

            discarded = discard_resume_optimization(
                self.student_id,
                offer["offer_id"],
            )

            after = get_resume(self.student_id)
            stored_offer = get_db().execute(
                """
                SELECT status, resolved_at
                FROM resume_optimization_offers
                WHERE offer_id = ?
                """,
                (offer["offer_id"],),
            ).fetchone()

        self.assertEqual(discarded["status"], "discarded")
        self.assertTrue(discarded["resolved_at"].endswith("+08:00"))
        self.assertEqual(stored_offer["status"], "discarded")
        self.assertEqual(before, after)
        self.assertEqual(after["version"], 1)

    def test_malformed_or_unavailable_ai_response_preserves_manual_resume_path(self):
        malformed_responses = (
            None,
            {},
            {"suggestions": []},
            {"suggestions": [" ", ""]},
            {"suggestions": [1]},
            {
                "suggestions": ["补充量化成果"],
                "rewritten_resume": {
                    "education_experiences": [],
                    "work_experiences": [],
                },
            },
            {
                "suggestions": ["补充量化成果"],
                "rewritten_resume": {
                    "education_experiences": [{"school": "X"}],
                    "work_experiences": [],
                    "skills": [],
                    "contact": "13800000000",
                },
            },
            {
                "suggestions": ["补充量化成果"],
                "rewritten_resume": {
                    "education_experiences": [
                        {
                            "school": {},
                            "major": "电子商务",
                            "start_date": "2022-09",
                        }
                    ],
                    "work_experiences": [],
                    "skills": [],
                },
            },
            {
                "suggestions": ["补充量化成果"],
                "rewritten_resume": {
                    "education_experiences": [
                        {
                            "school": "广东职业学院",
                            "major": "电子商务",
                            "start_date": "2022-09",
                            "end_date": None,
                        }
                    ],
                    "work_experiences": [],
                    "skills": [],
                },
            },
            {
                "suggestions": ["补充量化成果"],
                "rewritten_resume": {
                    "education_experiences": [],
                    "work_experiences": [],
                    "skills": [1],
                },
            },
            {
                "suggestions": ["补充量化成果"],
                "rewritten_resume": {
                    "education_experiences": [
                        {
                            "school": "广东职业学院",
                            "major": "电子商务",
                            "start_date": "2022-09",
                            "degree": False,
                        }
                    ],
                    "work_experiences": [],
                    "skills": [],
                },
            },
            {
                "suggestions": ["补充量化成果"],
                "rewritten_resume": {
                    "education_experiences": [],
                    "work_experiences": [
                        {
                            "company": "示范农场",
                            "role": "运营助理",
                            "start_date": "2025-07",
                            "description": "超" * 2001,
                        }
                    ],
                    "skills": [],
                },
            },
            {
                "suggestions": ["补充量化成果"],
                "rewritten_resume": {
                    "education_experiences": [],
                    "work_experiences": [
                        {
                            "company": "示范农场",
                            "role": "运营助理",
                            "start_date": "2025-07",
                        }
                        for _ in range(21)
                    ],
                    "skills": [],
                },
            },
        )

        with self.app.app_context():
            self._seed_saved_resume()

            for response in malformed_responses:
                with self.subTest(response=response):
                    set_ai_client(self.app, FakeAi(response=response))
                    with self.assertRaises(AiUnavailableError) as raised:
                        optimize_resume(self.student_id, expected_version=1)
                    self.assertEqual(str(raised.exception), "AI 服务暂时不可用")
                    self.assertEqual(
                        raised.exception.message,
                        "AI 服务暂时不可用",
                    )

            set_ai_client(
                self.app,
                FakeAi(error=AiUnavailableError("upstream detail")),
            )
            with self.assertRaises(AiUnavailableError) as raised:
                optimize_resume(self.student_id, expected_version=1)
            self.assertEqual(str(raised.exception), "AI 服务暂时不可用")

            self.assertEqual(
                get_db().execute(
                    "SELECT COUNT(*) AS count FROM resume_optimization_offers"
                ).fetchone()["count"],
                0,
            )
            self.assertEqual(get_resume(self.student_id)["version"], 1)

            saved = save_resume(
                self.student_id,
                {"skills": ["客户沟通"]},
                expected_version=1,
            )

        self.assertEqual(saved["version"], 2)

    def test_suggestions_only_offer_remains_previewable_but_cannot_be_adopted(self):
        with self.app.app_context():
            self._seed_saved_resume()
            set_ai_client(
                self.app,
                FakeAi(response={"suggestions": [" 补充量化成果 "]}),
            )

            offer = optimize_resume(self.student_id, expected_version=1)

            self.assertEqual(offer["suggestions"], ["补充量化成果"])
            self.assertIsNone(offer["rewritten_resume"])
            with self.assertRaises(JobMatchingValidationError) as raised:
                adopt_resume_optimization(
                    self.student_id,
                    offer["offer_id"],
                    expected_version=1,
                )
            current = get_resume(self.student_id)

        self.assertEqual(
            raised.exception.message,
            "该结果仅包含建议，不能自动替换",
        )
        self.assertEqual(current["version"], 1)
        self.assertEqual(current["skills"], ["直播运营", "客户沟通"])

    def test_wrong_student_cannot_read_adopt_or_discard_another_offer(self):
        with self.app.app_context():
            self._seed_saved_resume()
            set_ai_client(self.app, FakeAi())
            offer = optimize_resume(self.student_id, expected_version=1)

            for reader_id in (self.other_student_id, self.student_id + 1000):
                with self.subTest(reader_id=reader_id):
                    with self.assertRaises(
                        JobMatchingValidationError
                    ) as raised:
                        _owned_offer(reader_id, offer["offer_id"])
                    self.assertEqual(raised.exception.message, "优化稿不存在")

            with self.assertRaises(JobMatchingValidationError):
                adopt_resume_optimization(
                    self.other_student_id,
                    offer["offer_id"],
                    expected_version=0,
                )
            with self.assertRaises(JobMatchingValidationError):
                discard_resume_optimization(
                    self.other_student_id,
                    offer["offer_id"],
                )

            stored_offer = get_db().execute(
                """
                SELECT status
                FROM resume_optimization_offers
                WHERE offer_id = ?
                """,
                (offer["offer_id"],),
            ).fetchone()

        self.assertEqual(stored_offer["status"], "offered")
        with self.app.app_context():
            self.assertEqual(get_resume(self.other_student_id)["version"], 0)

    def test_stale_expected_and_base_versions_raise_conflicts_without_mutation(self):
        with self.app.app_context():
            self._seed_saved_resume()
            set_ai_client(self.app, FakeAi())
            offer = optimize_resume(self.student_id, expected_version=1)
            current = save_resume(
                self.student_id,
                {"skills": ["客户沟通"]},
                expected_version=1,
            )

            with self.assertRaises(ResumeConflictError) as expired:
                adopt_resume_optimization(
                    self.student_id,
                    offer["offer_id"],
                    expected_version=current["version"],
                )
            with self.assertRaises(ResumeConflictError) as stale:
                adopt_resume_optimization(
                    self.student_id,
                    offer["offer_id"],
                    expected_version=1,
                )

            revision_count = get_db().execute(
                """
                SELECT COUNT(*) AS count
                FROM resume_revisions
                WHERE resume_id = (
                    SELECT id FROM resumes WHERE user_id = ?
                )
                """,
                (self.student_id,),
            ).fetchone()["count"]

        self.assertEqual(expired.exception.message, "优化稿已过期")
        self.assertEqual(stale.exception.message, "简历版本已变化")
        self.assertEqual(current["version"], 2)
        self.assertEqual(revision_count, 2)

    def test_offer_status_failure_rolls_back_resume_and_revision_then_retries(self):
        with self.app.app_context():
            initial = self._seed_saved_resume()
            set_ai_client(self.app, FakeAi())
            offer = optimize_resume(self.student_id, expected_version=1)
            db = get_db()
            db.execute(
                """
                CREATE TRIGGER force_offer_status_failure
                BEFORE UPDATE OF status ON resume_optimization_offers
                BEGIN
                    SELECT RAISE(ABORT, 'forced offer status failure');
                END
                """
            )
            db.commit()

            with self.assertRaises(sqlite3.IntegrityError):
                adopt_resume_optimization(
                    self.student_id,
                    offer["offer_id"],
                    expected_version=1,
                )

            rolled_back = get_resume(self.student_id)
            rolled_back_offer = db.execute(
                """
                SELECT status, resolved_at
                FROM resume_optimization_offers
                WHERE offer_id = ?
                """,
                (offer["offer_id"],),
            ).fetchone()
            revisions_after_failure = db.execute(
                """
                SELECT version
                FROM resume_revisions
                WHERE resume_id = (
                    SELECT id FROM resumes WHERE user_id = ?
                )
                ORDER BY version
                """,
                (self.student_id,),
            ).fetchall()

            db.execute("DROP TRIGGER force_offer_status_failure")
            db.commit()
            adopted = adopt_resume_optimization(
                self.student_id,
                offer["offer_id"],
                expected_version=1,
            )

        self.assertEqual(rolled_back, initial)
        self.assertEqual(rolled_back_offer["status"], "offered")
        self.assertIsNone(rolled_back_offer["resolved_at"])
        self.assertEqual(
            [int(row["version"]) for row in revisions_after_failure],
            [1],
        )
        self.assertEqual(adopted["version"], 2)

    def test_adopting_same_offer_twice_creates_exactly_one_revision(self):
        with self.app.app_context():
            self._seed_saved_resume()
            set_ai_client(self.app, FakeAi())
            offer = optimize_resume(self.student_id, expected_version=1)
            first = adopt_resume_optimization(
                self.student_id,
                offer["offer_id"],
                expected_version=1,
            )

            with self.assertRaises(JobMatchingValidationError) as raised:
                adopt_resume_optimization(
                    self.student_id,
                    offer["offer_id"],
                    expected_version=first["version"],
                )

            revisions = get_db().execute(
                """
                SELECT version
                FROM resume_revisions
                WHERE resume_id = (
                    SELECT id FROM resumes WHERE user_id = ?
                )
                ORDER BY version
                """,
                (self.student_id,),
            ).fetchall()

        self.assertEqual(raised.exception.message, "优化稿已处理")
        self.assertEqual(first["version"], 2)
        self.assertEqual([int(row["version"]) for row in revisions], [1, 2])


if __name__ == "__main__":
    unittest.main()
