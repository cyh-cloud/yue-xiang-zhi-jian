import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from app import create_app
from app.agri_skills.ai_client import set_ai_client
from app.agri_skills.errors import AiUnavailableError
from app.content_review import set_content_review_provider
from app.db import get_db
from app.teacher_console.course_service import (
    create_teacher_course,
    get_teacher_course,
    submit_course_for_review,
)
from app.teacher_console.errors import (
    ProviderAccessDeniedError,
    ProviderUnavailableError,
    ProviderValidationError,
)
from app.teacher_console.quiz import (
    generate_course_quiz,
    get_teacher_course_quiz,
    save_course_quiz,
)
from app.teacher_console.time_utils import now_shanghai_iso


def valid_questions():
    return [
        {
            "id": "q1",
            "type": "single_choice",
            "prompt": "荔枝保果的关键时期是？",
            "options": ["花期", "果期"],
            "answer": "果期",
        },
        {
            "id": "q2",
            "type": "true_false",
            "prompt": "保果期间需要关注水分管理。",
            "options": ["正确", "错误"],
            "answer": "正确",
        },
        {
            "id": "q3",
            "type": "single_choice",
            "prompt": "以下哪项属于保果措施？",
            "options": ["疏果", "停止施肥"],
            "answer": "疏果",
        },
    ]


class FakeReviewProvider:
    def __init__(self):
        self.records = {}
        self.calls = []
        self.fail_next = None

    def set_status(
        self,
        content_type,
        content_id,
        review_status,
        *,
        version=1,
    ):
        self.records[(content_type, content_id)] = {
            "content_type": content_type,
            "content_id": content_id,
            "review_status": review_status,
            "version": version,
            "rejection_opinion": None,
            "published_at": (
                now_shanghai_iso()
                if review_status == "approved"
                else None
            ),
            "updated_at": now_shanghai_iso(),
        }

    def get_review_status(self, *, content_type, content_id):
        self.calls.append(
            {
                "method": "get_review_status",
                "content_type": content_type,
                "content_id": content_id,
            }
        )
        record = self.records.get((content_type, content_id))
        return dict(record) if record is not None else None

    def submit_for_review(
        self,
        *,
        content_type,
        content_id,
        submitter_id,
        expected_version,
        payload,
    ):
        self.calls.append(
            {
                "method": "submit_for_review",
                "content_type": content_type,
                "content_id": content_id,
                "submitter_id": submitter_id,
                "expected_version": expected_version,
                "payload": payload,
            }
        )
        key = (content_type, content_id)
        record = {
            "content_type": content_type,
            "content_id": content_id,
            "review_status": "pending",
            "version": expected_version,
            "rejection_opinion": None,
            "published_at": None,
            "updated_at": now_shanghai_iso(),
        }
        self.records[key] = record
        return dict(record)

    def approve(
        self,
        *,
        content_type,
        content_id,
        submitter_id,
        reviewer_id,
        reviewer_role,
        expected_version,
    ):
        raise AssertionError("Task 7 must not call approve")

    def reject(
        self,
        *,
        content_type,
        content_id,
        submitter_id,
        reviewer_id,
        reviewer_role,
        expected_version,
        opinion,
    ):
        raise AssertionError("Task 7 must not call reject")

    def edit(
        self,
        *,
        content_type,
        content_id,
        submitter_id,
        expected_version,
        payload,
    ):
        self.calls.append(
            {
                "method": "edit",
                "content_type": content_type,
                "content_id": content_id,
                "submitter_id": submitter_id,
                "expected_version": expected_version,
                "payload": payload,
            }
        )
        if self.fail_next is not None:
            error = self.fail_next
            self.fail_next = None
            raise error

        key = (content_type, content_id)
        record = {
            "content_type": content_type,
            "content_id": content_id,
            "review_status": "pending",
            "version": expected_version + 1,
            "rejection_opinion": None,
            "published_at": None,
            "updated_at": now_shanghai_iso(),
        }
        self.records[key] = record
        return dict(record)


class TestTeacherQuiz(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.media_root = Path(self.temp_dir.name) / "media"
        self.media_root.mkdir()
        (self.media_root / "course.mp4").write_bytes(b"video")

        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(Path(self.temp_dir.name) / "test.db"),
                "COURSE_MEDIA_ROOT": str(self.media_root),
                "SECRET_KEY": "test-only-secret",
            }
        )
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.review = FakeReviewProvider()
        set_content_review_provider(self.app, self.review)
        self.ai = Mock()
        set_ai_client(self.app, self.ai)

        db = get_db()
        now = "2026-09-19T10:00:00+08:00"
        db.executemany(
            """
            INSERT INTO users (
                id, username, password_hash, name, role, is_enabled,
                created_at, updated_at
            )
            VALUES (?, ?, 'test-hash', ?, 'teacher', 1, ?, ?)
            """,
            (
                (7, "teacher07", "教师七", now, now),
                (8, "teacher08", "教师八", now, now),
            ),
        )
        db.commit()

        self.teacher_id = 7
        self.course_id = create_teacher_course(
            7,
            {
                "title": "荔枝保果",
                "direction": "agriculture",
                "summary": "花期与果期管理要点",
                "content_tags": ["荔枝"],
                "duration_seconds": 300,
                "media_source_type": "local_upload",
                "media_url": "/media/teacher-courses/course.mp4",
            },
        )["id"]
        self.valid_questions = valid_questions()

    def tearDown(self):
        self.app_context.pop()
        self.temp_dir.cleanup()

    def mark_published(self, version=1):
        if get_teacher_course(7, self.course_id)["status"] == "draft":
            submit_course_for_review(
                7,
                self.course_id,
                expected_version=1,
            )
        self.review.set_status(
            "course_video",
            str(self.course_id),
            "approved",
            version=version,
        )

    def test_generate_quiz_uses_only_summary_and_direction(self):
        self.ai.complete_json.return_value = {
            "questions": [
                {
                    "id": "q1",
                    "type": "single_choice",
                    "prompt": "?",
                    "options": ["A", "B"],
                    "answer": "A",
                },
                {
                    "id": "q2",
                    "type": "true_false",
                    "prompt": "?",
                    "options": ["正确", "错误"],
                    "answer": "正确",
                },
                {
                    "id": "q3",
                    "type": "true_false",
                    "prompt": "?",
                    "options": ["正确", "错误"],
                    "answer": "错误",
                },
            ]
        }

        quiz = generate_course_quiz(
            self.teacher_id,
            self.course_id,
            summary="课程简介",
            direction="agriculture",
        )

        self.assertEqual(len(quiz["questions"]), 3)
        call = self.ai.complete_json.call_args
        self.assertEqual(
            call.kwargs["call_point"],
            "teacher_quiz_generate",
        )
        context = json.loads(call.args[0][1]["content"])
        self.assertEqual(
            context,
            {
                "course_summary": "课程简介",
                "course_direction": "agriculture",
            },
        )
        self.assertIn("课程简介", call.args[0][1]["content"])
        self.assertNotIn("video", call.args[0][1]["content"].lower())

    def test_quiz_ai_failure_is_provider_error(self):
        self.ai.complete_json.side_effect = AiUnavailableError("down")

        with self.assertRaisesRegex(
            ProviderUnavailableError,
            "AI 服务暂时不可用",
        ) as raised:
            generate_course_quiz(
                self.teacher_id,
                self.course_id,
                summary="课程简介",
                direction="agriculture",
            )

        self.assertEqual(raised.exception.code, "ai_unavailable")
        self.assertEqual(raised.exception.details, {})

    def test_invalid_ai_questions_are_provider_errors(self):
        invalid_payloads = (
            [],
            {},
            {"questions": [{"id": "q1"}]},
            {"questions": self.valid_questions[:2]},
            {"questions": self.valid_questions + self.valid_questions[:3]},
            {
                "questions": [
                    self.valid_questions[0],
                    self.valid_questions[1],
                    {**self.valid_questions[2], "id": "q1"},
                ]
            },
            {
                "questions": [
                    self.valid_questions[0],
                    self.valid_questions[1],
                    {**self.valid_questions[2], "type": "multiple_choice"},
                ]
            },
            {
                "questions": [
                    self.valid_questions[0],
                    self.valid_questions[1],
                    {**self.valid_questions[2], "prompt": " "},
                ]
            },
            {
                "questions": [
                    self.valid_questions[0],
                    self.valid_questions[1],
                    {**self.valid_questions[2], "options": []},
                ]
            },
            {
                "questions": [
                    self.valid_questions[0],
                    self.valid_questions[1],
                    {**self.valid_questions[2], "options": ["疏果", ""]},
                ]
            },
            {
                "questions": [
                    self.valid_questions[0],
                    self.valid_questions[1],
                    {**self.valid_questions[2], "answer": "不存在"},
                ]
            },
        )

        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                self.ai.complete_json.return_value = payload
                with self.assertRaisesRegex(
                    ProviderUnavailableError,
                    "AI 服务暂时不可用",
                ) as raised:
                    generate_course_quiz(
                        self.teacher_id,
                        self.course_id,
                        summary="课程简介",
                        direction="agriculture",
                    )
                self.assertEqual(raised.exception.code, "ai_unavailable")
                self.assertEqual(raised.exception.details, {})

    def test_generate_quiz_rejects_unowned_course_before_ai(self):
        with self.assertRaises(ProviderAccessDeniedError):
            generate_course_quiz(
                8,
                self.course_id,
                summary="课程简介",
                direction="agriculture",
            )

        self.ai.complete_json.assert_not_called()

    def test_published_quiz_change_reenters_review(self):
        self.mark_published()

        quiz = save_course_quiz(
            self.teacher_id,
            self.course_id,
            expected_version=1,
            enabled=True,
            questions=self.valid_questions,
            scoring_rule="all_correct",
        )

        self.assertEqual(self.review.calls[-1]["method"], "edit")
        self.assertEqual(
            self.review.calls[-1]["payload"]["quiz_config"],
            {
                "enabled": True,
                "scoring_rule": "all_correct",
                "questions": self.valid_questions,
            },
        )
        self.assertEqual(quiz["enabled"], True)
        self.assertEqual(get_teacher_course(7, self.course_id)["status"], "pending")

    def test_provider_failure_does_not_write_quiz(self):
        self.mark_published()
        self.review.fail_next = ProviderUnavailableError(
            "审核不可用",
            code="review_unavailable",
            details={},
        )

        with self.assertRaises(ProviderUnavailableError):
            save_course_quiz(
                self.teacher_id,
                self.course_id,
                expected_version=1,
                enabled=True,
                questions=self.valid_questions,
                scoring_rule="all_correct",
            )

        self.assertIsNone(
            get_teacher_course_quiz(self.teacher_id, self.course_id)
        )

    def test_draft_quiz_save_stays_local_and_uses_shanghai_time(self):
        quiz = save_course_quiz(
            self.teacher_id,
            self.course_id,
            expected_version=1,
            enabled=True,
            questions=self.valid_questions,
            scoring_rule="all_correct",
        )

        self.assertEqual(
            [
                call
                for call in self.review.calls
                if call["method"] == "edit"
            ],
            [],
        )
        self.assertEqual(quiz["questions"], self.valid_questions)
        self.assertEqual(get_teacher_course(7, self.course_id)["version"], 2)
        row = get_db().execute(
            """
            SELECT updated_at
            FROM course_quizzes
            WHERE course_id = ?
            """,
            (self.course_id,),
        ).fetchone()
        self.assertTrue(row["updated_at"].endswith("+08:00"))

    def test_unchanged_non_draft_quiz_does_not_reenter_review(self):
        self.mark_published()
        save_course_quiz(
            self.teacher_id,
            self.course_id,
            expected_version=1,
            enabled=True,
            questions=self.valid_questions,
            scoring_rule="all_correct",
        )
        edit_count = len(
            [
                call
                for call in self.review.calls
                if call["method"] == "edit"
            ]
        )
        self.mark_published(version=2)

        saved = save_course_quiz(
            self.teacher_id,
            self.course_id,
            expected_version=2,
            enabled=True,
            questions=self.valid_questions,
            scoring_rule="all_correct",
        )

        self.assertEqual(saved["questions"], self.valid_questions)
        self.assertEqual(
            len(
                [
                    call
                    for call in self.review.calls
                    if call["method"] == "edit"
                ]
            ),
            edit_count,
        )

    def test_save_quiz_rejects_invalid_config_before_provider(self):
        self.mark_published()
        invalid_configs = (
            {"scoring_rule": " "},
            {"enabled": "yes"},
            {"questions": self.valid_questions[:2]},
            {
                "questions": [
                    self.valid_questions[0],
                    self.valid_questions[1],
                    {**self.valid_questions[2], "answer": "不存在"},
                ]
            },
        )
        valid_config = {
            "enabled": True,
            "questions": self.valid_questions,
            "scoring_rule": "all_correct",
        }

        for changes in invalid_configs:
            with self.subTest(changes=changes):
                calls_before = [
                    call
                    for call in self.review.calls
                    if call["method"] == "edit"
                ]
                with self.assertRaises(ProviderValidationError):
                    save_course_quiz(
                        self.teacher_id,
                        self.course_id,
                        expected_version=1,
                        **{**valid_config, **changes},
                    )
                self.assertEqual(
                    [
                        call
                        for call in self.review.calls
                        if call["method"] == "edit"
                    ],
                    calls_before,
                )
                self.assertIsNone(
                    get_teacher_course_quiz(
                        self.teacher_id,
                        self.course_id,
                    )
                )

    def test_disabled_quiz_clears_questions(self):
        saved = save_course_quiz(
            self.teacher_id,
            self.course_id,
            expected_version=1,
            enabled=False,
            questions=self.valid_questions,
            scoring_rule="all_correct",
        )

        self.assertEqual(
            saved,
            {
                "enabled": False,
                "scoring_rule": "all_correct",
                "questions": [],
            },
        )


if __name__ == "__main__":
    unittest.main()
