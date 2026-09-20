import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from app import create_app
from app.db import get_db
from app.job_matching.errors import (
    JobMatchingValidationError,
    ResumeConflictError,
    ResumeRequiredError,
)
from app.job_matching.resumes import (
    _normalize_payload,
    _save_normalized_resume,
    build_resume_snapshot,
    get_resume,
    resume_exists,
    save_resume,
)


class JobMatchingResumeTests(unittest.TestCase):
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

    def test_save_persists_projection_snapshot_and_isolates_students(self):
        payload = self._valid_payload()

        with self.app.app_context():
            saved = save_resume(
                self.student_id,
                payload,
                expected_version=0,
            )

            self.assertEqual(saved["version"], 1)
            self.assertEqual(saved["education_experiences"], payload["education_experiences"])
            self.assertEqual(saved["work_experiences"], payload["work_experiences"])
            self.assertEqual(saved["skills"], payload["skills"])
            self.assertTrue(saved["has_saved_resume"])
            self.assertTrue(resume_exists(self.student_id))
            self.assertEqual(
                build_resume_snapshot(self.student_id),
                {
                    "resume_version": 1,
                    "saved_at": saved["saved_at"],
                    **payload,
                },
            )
            self.assertFalse(resume_exists(self.other_student_id))
            self.assertEqual(
                get_resume(self.other_student_id)["version"],
                0,
            )
            with self.assertRaisesRegex(
                ResumeRequiredError,
                "^请先创建并保存简历$",
            ):
                build_resume_snapshot(self.other_student_id)

    def test_normalizes_fields_and_deduplicates_skills(self):
        payload = {
            "education_experiences": [
                {
                    "school": " 广东职业学院 ",
                    "major": " 电子商务 ",
                    "degree": " 专科 ",
                    "start_date": " 2022-09 ",
                    "end_date": " 2025-06 ",
                    "ignored": "not persisted",
                }
            ],
            "work_experiences": [
                {
                    "company": " 示范农场 ",
                    "role": " 运营助理 ",
                    "start_date": " 2025-07 ",
                }
            ],
            "skills": [
                " 直播运营 ",
                "直播运营",
                "",
                " 客户沟通 ",
            ],
            "unsupported_section": {"value": "ignored"},
        }

        with self.app.app_context():
            saved = save_resume(
                self.student_id,
                payload,
                expected_version=0,
            )

        self.assertEqual(
            saved["education_experiences"],
            [
                {
                    "school": "广东职业学院",
                    "major": "电子商务",
                    "start_date": "2022-09",
                    "degree": "专科",
                    "end_date": "2025-06",
                }
            ],
        )
        self.assertEqual(
            saved["work_experiences"],
            [
                {
                    "company": "示范农场",
                    "role": "运营助理",
                    "start_date": "2025-07",
                    "end_date": "",
                    "description": "",
                }
            ],
        )
        self.assertEqual(saved["skills"], ["直播运营", "客户沟通"])
        self.assertNotIn("unsupported_section", saved)

    def test_rejects_all_empty_payloads(self):
        empty_payloads = (
            {},
            {
                "education_experiences": [],
                "work_experiences": [],
                "skills": [],
            },
            {
                "education_experiences": [],
                "work_experiences": [],
                "skills": [" ", ""],
            },
        )

        with self.app.app_context():
            for payload in empty_payloads:
                with self.subTest(payload=payload):
                    with self.assertRaises(
                        JobMatchingValidationError
                    ) as raised:
                        save_resume(
                            self.student_id,
                            payload,
                            expected_version=0,
                        )
                    self.assertEqual(
                        raised.exception.message,
                        "至少填写一个简历区块",
                    )
                    self.assertEqual(
                        raised.exception.details,
                        {"resume": "至少填写一个简历区块"},
                    )

    def test_rejects_invalid_required_and_optional_field_shapes(self):
        invalid_payloads = (
            (
                {"education_experiences": "invalid"},
                "education_experiences 必须是列表",
                {},
            ),
            (
                {"education_experiences": ["invalid"]},
                "education_experiences 条目格式不正确",
                {},
            ),
            (
                {
                    "education_experiences": [{"major": "电子商务", "start_date": "2022-09"}]
                },
                "education_experiences.school 不能为空",
                {"education_experiences.school": "不能为空"},
            ),
            (
                {
                    "education_experiences": [
                        {"school": "广东职业学院", "major": " ", "start_date": "2022-09"}
                    ]
                },
                "education_experiences.major 不能为空",
                {"education_experiences.major": "不能为空"},
            ),
            (
                {
                    "education_experiences": [
                        {"school": "广东职业学院", "major": "电子商务", "start_date": " "}
                    ]
                },
                "education_experiences.start_date 不能为空",
                {"education_experiences.start_date": "不能为空"},
            ),
            (
                {"work_experiences": "invalid"},
                "work_experiences 必须是列表",
                {},
            ),
            (
                {"work_experiences": ["invalid"]},
                "work_experiences 条目格式不正确",
                {},
            ),
            (
                {"work_experiences": [{"role": "运营助理", "start_date": "2025-07"}]},
                "work_experiences.company 不能为空",
                {"work_experiences.company": "不能为空"},
            ),
            (
                {
                    "work_experiences": [
                        {"company": "示范农场", "role": " ", "start_date": "2025-07"}
                    ]
                },
                "work_experiences.role 不能为空",
                {"work_experiences.role": "不能为空"},
            ),
            (
                {
                    "work_experiences": [
                        {"company": "示范农场", "role": "运营助理", "start_date": ""}
                    ]
                },
                "work_experiences.start_date 不能为空",
                {"work_experiences.start_date": "不能为空"},
            ),
            (
                {"skills": "invalid"},
                "skills 必须是列表",
                {},
            ),
        )

        with self.app.app_context():
            for payload, message, details in invalid_payloads:
                with self.subTest(payload=payload):
                    with self.assertRaises(
                        JobMatchingValidationError
                    ) as raised:
                        save_resume(
                            self.student_id,
                            payload,
                            expected_version=0,
                        )
                    self.assertEqual(raised.exception.message, message)
                    self.assertEqual(raised.exception.details, details)

    def test_rejects_non_text_oversized_and_unbounded_values(self):
        valid_education = {
            "school": "广东职业学院",
            "major": "电子商务",
            "start_date": "2022-09",
        }
        invalid_payloads = (
            (
                {
                    "education_experiences": [
                        {**valid_education, "school": []}
                    ]
                },
                "education_experiences.school 必须是文本",
                {"education_experiences.school": "必须是文本"},
            ),
            (
                {
                    "education_experiences": [
                        {**valid_education, "degree": 1}
                    ]
                },
                "education_experiences.degree 必须是文本",
                {"education_experiences.degree": "必须是文本"},
            ),
            (
                {
                    "education_experiences": [
                        {**valid_education, "end_date": None}
                    ]
                },
                "education_experiences.end_date 必须是文本",
                {"education_experiences.end_date": "必须是文本"},
            ),
            (
                {
                    "work_experiences": [
                        {
                            "company": True,
                            "role": "运营助理",
                            "start_date": "2025-07",
                        }
                    ]
                },
                "work_experiences.company 必须是文本",
                {"work_experiences.company": "必须是文本"},
            ),
            (
                {
                    "work_experiences": [
                        {
                            "company": "示范农场",
                            "role": "运营助理",
                            "start_date": "2025-07",
                            "description": [],
                        }
                    ]
                },
                "work_experiences.description 必须是文本",
                {"work_experiences.description": "必须是文本"},
            ),
            (
                {"skills": [{}]},
                "skills 条目必须是文本",
                {"skills": "条目必须是文本"},
            ),
            (
                {"skills": [None]},
                "skills 条目必须是文本",
                {"skills": "条目必须是文本"},
            ),
            (
                {"skills": [1]},
                "skills 条目必须是文本",
                {"skills": "条目必须是文本"},
            ),
            (
                {
                    "education_experiences": [
                        {**valid_education, "school": "超" * 201}
                    ]
                },
                "education_experiences.school 长度不能超过 200",
                {"education_experiences.school": "最多 200 个字符"},
            ),
            (
                {
                    "work_experiences": [
                        {
                            "company": "示范农场",
                            "role": "运营助理",
                            "start_date": "2025-07",
                            "description": "超" * 2001,
                        }
                    ]
                },
                "work_experiences.description 长度不能超过 2000",
                {"work_experiences.description": "最多 2000 个字符"},
            ),
            (
                {"skills": ["超" * 101]},
                "skills 条目长度不能超过 100",
                {"skills": "每条最多 100 个字符"},
            ),
            (
                {
                    "education_experiences": [
                        dict(valid_education) for _ in range(21)
                    ]
                },
                "education_experiences 最多 20 条",
                {"education_experiences": "最多 20 条"},
            ),
            (
                {
                    "work_experiences": [
                        {
                            "company": "示范农场",
                            "role": "运营助理",
                            "start_date": "2025-07",
                        }
                        for _ in range(21)
                    ]
                },
                "work_experiences 最多 20 条",
                {"work_experiences": "最多 20 条"},
            ),
            (
                {"skills": [f"技能 {index}" for index in range(51)]},
                "skills 最多 50 条",
                {"skills": "最多 50 条"},
            ),
        )

        with self.app.app_context():
            for payload, message, details in invalid_payloads:
                with self.subTest(message=message):
                    with self.assertRaises(
                        JobMatchingValidationError
                    ) as raised:
                        save_resume(
                            self.student_id,
                            payload,
                            expected_version=0,
                        )
                    self.assertEqual(raised.exception.message, message)
                    self.assertEqual(raised.exception.details, details)

            current = get_resume(self.student_id)

        self.assertEqual(current["version"], 0)
        self.assertEqual(current["skills"], [])

    def test_three_consecutive_saves_create_revisions_one_through_three(self):
        with self.app.app_context():
            first = save_resume(
                self.student_id,
                {"skills": ["直播运营"]},
                expected_version=0,
            )
            second = save_resume(
                self.student_id,
                {"skills": ["直播运营", "客户沟通"]},
                expected_version=1,
            )
            third = save_resume(
                self.student_id,
                {"skills": ["客户沟通"]},
                expected_version=2,
            )
            revisions = get_db().execute(
                """
                SELECT version, skills_json
                FROM resume_revisions
                WHERE resume_id = (
                    SELECT id FROM resumes WHERE user_id = ?
                )
                ORDER BY version
                """,
                (self.student_id,),
            ).fetchall()

        self.assertEqual([first["version"], second["version"], third["version"]], [1, 2, 3])
        self.assertEqual([int(row["version"]) for row in revisions], [1, 2, 3])
        self.assertEqual(
            [json.loads(row["skills_json"]) for row in revisions],
            [["直播运营"], ["直播运营", "客户沟通"], ["客户沟通"]],
        )

    def test_stale_version_is_rejected_without_mutation(self):
        with self.app.app_context():
            save_resume(
                self.student_id,
                {"skills": ["直播运营"]},
                expected_version=0,
            )

            with self.assertRaisesRegex(
                ResumeConflictError,
                "^简历版本已变化$",
            ):
                save_resume(
                    self.student_id,
                    {"skills": ["客户沟通"]},
                    expected_version=0,
                )

            current = get_resume(self.student_id)
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

        self.assertEqual(current["version"], 1)
        self.assertEqual(current["skills"], ["直播运营"])
        self.assertEqual(revision_count, 1)

    def test_resume_exists_requires_positive_version_and_nonempty_content(self):
        with self.app.app_context():
            db = get_db()
            db.execute(
                """
                UPDATE resumes
                SET skills_json = ?
                WHERE user_id = ?
                """,
                (json.dumps(["直播运营"]), self.student_id),
            )
            db.commit()
            self.assertFalse(resume_exists(self.student_id))

            db.execute(
                """
                UPDATE resumes
                SET skills_json = '[]', version = 1
                WHERE user_id = ?
                """,
                (self.student_id,),
            )
            db.commit()
            self.assertFalse(resume_exists(self.student_id))

            save_resume(
                self.student_id,
                {"skills": ["直播运营"]},
                expected_version=1,
            )
            self.assertTrue(resume_exists(self.student_id))

    def test_snapshot_requires_saved_nonempty_content(self):
        with self.app.app_context():
            with self.assertRaisesRegex(
                ResumeRequiredError,
                "^请先创建并保存简历$",
            ):
                build_resume_snapshot(self.student_id)

            db = get_db()
            db.execute(
                """
                UPDATE resumes
                SET version = 1
                WHERE user_id = ?
                """,
                (self.student_id,),
            )
            with self.assertRaisesRegex(
                ResumeRequiredError,
                "^请先创建并保存简历$",
            ):
                build_resume_snapshot(self.student_id)

    def test_generated_timestamps_are_shanghai_iso(self):
        with self.app.app_context():
            saved = save_resume(
                self.student_id,
                {"skills": ["直播运营"]},
                expected_version=0,
            )
            revision = get_db().execute(
                """
                SELECT saved_at
                FROM resume_revisions
                WHERE resume_id = (
                    SELECT id FROM resumes WHERE user_id = ?
                )
                """,
                (self.student_id,),
            ).fetchone()

        parsed = datetime.fromisoformat(saved["saved_at"])
        self.assertEqual(parsed.utcoffset().total_seconds(), 8 * 60 * 60)
        self.assertTrue(saved["saved_at"].endswith("+08:00"))
        self.assertEqual(revision["saved_at"], saved["saved_at"])

    def test_offer_resolution_is_part_of_same_transaction(self):
        with self.app.app_context():
            first = save_resume(
                self.student_id,
                {"skills": ["直播运营"]},
                expected_version=0,
            )
            db = get_db()
            offer_id = "resume-offer-test"
            db.execute(
                """
                INSERT INTO resume_optimization_offers (
                    offer_id,
                    student_id,
                    base_version,
                    suggestions_json,
                    rewritten_json,
                    status,
                    created_at
                )
                VALUES (?, ?, ?, ?, NULL, 'offered', ?)
                """,
                (
                    offer_id,
                    self.student_id,
                    first["version"],
                    json.dumps(["补充量化成果"], ensure_ascii=False),
                    "2026-09-19T10:00:00+08:00",
                ),
            )
            db.commit()

            adopted = _save_normalized_resume(
                self.student_id,
                _normalize_payload({"skills": ["直播运营", "客户沟通"]}),
                first["version"],
                offer_id=offer_id,
            )
            offer = db.execute(
                """
                SELECT status, resolved_at
                FROM resume_optimization_offers
                WHERE offer_id = ?
                """,
                (offer_id,),
            ).fetchone()

        self.assertEqual(adopted["version"], 2)
        self.assertEqual(offer["status"], "adopted")
        self.assertTrue(offer["resolved_at"].endswith("+08:00"))

    def test_invalid_offer_resolution_rolls_back_resume_and_revision(self):
        with self.app.app_context():
            first = save_resume(
                self.student_id,
                {"skills": ["直播运营"]},
                expected_version=0,
            )

            with self.assertRaisesRegex(
                JobMatchingValidationError,
                "^优化稿已处理$",
            ):
                _save_normalized_resume(
                    self.student_id,
                    _normalize_payload({"skills": ["客户沟通"]}),
                    first["version"],
                    offer_id="missing-offer",
                )

            current = get_resume(self.student_id)
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

        self.assertEqual(current["version"], 1)
        self.assertEqual(current["skills"], ["直播运营"])
        self.assertEqual(revision_count, 1)


if __name__ == "__main__":
    unittest.main()
