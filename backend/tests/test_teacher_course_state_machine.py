import json
import tempfile
import unittest
from pathlib import Path

from app import create_app
from app.content_review import set_content_review_provider
from app.db import get_db
from app.teacher_console.course_service import (
    create_teacher_course,
    edit_course,
    get_teacher_course,
    list_teacher_courses,
    request_course_relist,
    resolve_teacher_visible_status,
    review_payload,
    set_course_offline,
    submit_course_for_review,
)
from app.teacher_console.errors import (
    ProviderConflictError,
    ProviderUnavailableError,
    ProviderValidationError,
)
from app.teacher_console.review_adapter import CourseReviewAdapter
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


def valid_quiz():
    return {
        "enabled": True,
        "scoring_rule": "all_correct",
        "questions": valid_questions(),
    }


class FakeReviewProvider:
    def __init__(self):
        self.records = {}
        self.calls = []
        self.fail_next = None
        self.return_pending = True
        self.write_db_marker = False

    def set_status(
        self,
        content_type,
        content_id,
        review_status,
        *,
        version=1,
        opinion=None,
        updated_at=None,
    ):
        self.records[(content_type, content_id)] = {
            "content_type": content_type,
            "content_id": content_id,
            "review_status": review_status,
            "version": version,
            "rejection_opinion": opinion,
            "updated_at": updated_at or now_shanghai_iso(),
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
        return self._write(
            "submit_for_review",
            content_type=content_type,
            content_id=content_id,
            submitter_id=submitter_id,
            expected_version=expected_version,
            payload=payload,
        )

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
        raise AssertionError("Task 4 must not call approve")

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
        raise AssertionError("Task 4 must not call reject")

    def edit(
        self,
        *,
        content_type,
        content_id,
        submitter_id,
        expected_version,
        payload,
    ):
        return self._write(
            "edit",
            content_type=content_type,
            content_id=content_id,
            submitter_id=submitter_id,
            expected_version=expected_version,
            payload=payload,
        )

    def _write(
        self,
        method,
        *,
        content_type,
        content_id,
        submitter_id,
        expected_version,
        payload,
    ):
        self.calls.append(
            {
                "method": method,
                "content_type": content_type,
                "content_id": content_id,
                "submitter_id": submitter_id,
                "expected_version": expected_version,
                "payload": payload,
            }
        )
        if self.write_db_marker:
            db = get_db()
            db.execute(
                """
                INSERT INTO teacher_course_status_history (
                    course_id, from_status, to_status, actor_id,
                    opinion, version, created_at
                )
                VALUES (?, 'provider', 'marker', ?, NULL, ?, ?)
                """,
                (
                    int(content_id),
                    submitter_id,
                    expected_version,
                    now_shanghai_iso(),
                ),
            )
        if self.fail_next is not None:
            error = self.fail_next
            self.fail_next = None
            raise error

        key = (content_type, content_id)
        current = self.records.get(key)
        version = (
            expected_version
            if current is None
            else expected_version + 1
        )
        review_status = "pending" if self.return_pending else "approved"
        record = {
            "content_type": content_type,
            "content_id": content_id,
            "review_status": review_status,
            "version": version,
            "rejection_opinion": None,
            "updated_at": now_shanghai_iso(),
        }
        self.records[key] = record
        return dict(record)


class TestTeacherCourseStateMachine(unittest.TestCase):
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

        with self.app.app_context():
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
            self.course = create_teacher_course(
                7,
                {
                    "title": "荔枝保果",
                    "direction": "agriculture",
                    "summary": "花期与果期管理要点",
                    "content_tags": ["荔枝", "保果"],
                    "duration_seconds": 300,
                    "media_source_type": "local_upload",
                    "media_url": "/media/teacher-courses/course.mp4",
                },
            )
            self.course_id = self.course["id"]

    def tearDown(self):
        self.app_context.pop()
        self.temp_dir.cleanup()

    def visible_status(self):
        course = get_teacher_course(7, self.course_id)
        review = CourseReviewAdapter().read(self.course_id)
        review_status = (
            review.get("review_status") if review is not None else None
        )
        return resolve_teacher_visible_status(course, review_status)

    def visible_course_ids(self, direction):
        return [
            course["id"]
            for course in list_teacher_courses(7, direction=direction)
            if self.visible_status() == "published"
        ]

    def history_rows(self):
        return get_db().execute(
            """
            SELECT from_status, to_status, actor_id, opinion, version, created_at
            FROM teacher_course_status_history
            WHERE course_id = ?
            ORDER BY id
            """,
            (self.course_id,),
        ).fetchall()

    def submit_initial_course(self):
        return submit_course_for_review(
            7,
            self.course_id,
            expected_version=1,
        )

    def test_edit_published_course_hides_it_until_reapproval(self):
        self.submit_initial_course()
        self.review.set_status(
            "course_video",
            str(self.course_id),
            "approved",
        )
        self.assertEqual(self.visible_status(), "published")

        edited = edit_course(
            7,
            self.course_id,
            expected_version=1,
            payload={"title": "修订标题"},
        )

        self.assertEqual(edited["title"], "修订标题")
        self.assertEqual(edited["status"], "pending")
        self.assertEqual(edited["version"], 2)
        self.assertEqual(self.visible_status(), "pending")
        self.assertEqual(self.visible_course_ids("agriculture"), [])
        self.review.set_status(
            "course_video",
            str(self.course_id),
            "approved",
            version=2,
        )
        self.assertEqual(self.visible_status(), "published")

    def test_rejected_course_returns_to_pending_on_edit(self):
        self.submit_initial_course()
        self.review.set_status(
            "course_video",
            str(self.course_id),
            "rejected",
            opinion="补充课程简介",
        )
        get_db().execute(
            """
            UPDATE courses
            SET rejection_opinion = '补充课程简介'
            WHERE id = ?
            """,
            (self.course_id,),
        )
        get_db().commit()

        edited = edit_course(
            7,
            self.course_id,
            expected_version=1,
            payload={"summary": "补充后的知识点"},
        )

        self.assertEqual(self.review.calls[-1]["method"], "edit")
        self.assertEqual(edited["status"], "pending")
        self.assertEqual(edited["summary"], "补充后的知识点")
        self.assertIsNone(edited["rejection_opinion"])
        self.assertTrue(edited["submitted_at"].endswith("+08:00"))

    def test_offline_relist_starts_new_review_round(self):
        self.submit_initial_course()
        self.review.set_status(
            "course_video",
            str(self.course_id),
            "approved",
        )
        offline = set_course_offline(
            7,
            self.course_id,
            expected_version=1,
        )
        self.assertEqual(offline["status"], "offline")

        self.review.return_pending = True
        relisted = request_course_relist(
            7,
            self.course_id,
            expected_version=1,
        )

        self.assertEqual(relisted["status"], "pending")
        self.assertEqual(self.review.calls[-1]["method"], "submit_for_review")
        self.assertEqual(
            self.review.calls[-1]["expected_version"],
            1,
        )
        history = self.history_rows()[-1]
        self.assertEqual(
            (
                history["from_status"],
                history["to_status"],
                history["actor_id"],
            ),
            ("offline", "pending", 7),
        )

    def test_submit_only_accepts_draft_or_rejected(self):
        submitted = submit_course_for_review(
            7,
            self.course_id,
            expected_version=1,
        )

        self.assertEqual(submitted["status"], "pending")
        self.assertEqual(self.review.calls[-1]["method"], "submit_for_review")
        self.assertEqual(self.review.calls[-1]["content_type"], "course_video")
        self.assertEqual(
            self.review.calls[-1]["content_id"],
            str(self.course_id),
        )
        history = self.history_rows()[-1]
        self.assertEqual(
            (history["from_status"], history["to_status"]),
            ("draft", "pending"),
        )

        with self.assertRaises(ProviderConflictError):
            submit_course_for_review(
                7,
                self.course_id,
                expected_version=1,
            )

    def test_stale_edit_is_rejected_without_provider_write(self):
        self.submit_initial_course()
        self.review.set_status(
            "course_video",
            str(self.course_id),
            "approved",
        )
        calls_before = list(self.review.calls)

        with self.assertRaises(ProviderConflictError):
            edit_course(
                7,
                self.course_id,
                expected_version=99,
                payload={"title": "过期写入"},
            )

        write_calls_after = [
            call
            for call in self.review.calls
            if call["method"] != "get_review_status"
        ]
        write_calls_before = [
            call
            for call in calls_before
            if call["method"] != "get_review_status"
        ]
        self.assertEqual(write_calls_after, write_calls_before)
        unchanged = get_teacher_course(7, self.course_id)
        self.assertEqual(unchanged["title"], "荔枝保果")
        self.assertEqual(unchanged["version"], 1)

    def test_provider_failure_rolls_back_provider_and_local_writes(self):
        self.submit_initial_course()
        self.review.set_status(
            "course_video",
            str(self.course_id),
            "approved",
        )
        self.review.write_db_marker = True
        self.review.fail_next = ProviderUnavailableError(
            "审核不可用",
            code="review_unavailable",
            details={},
        )

        with self.assertRaises(ProviderUnavailableError):
            edit_course(
                7,
                self.course_id,
                expected_version=1,
                payload={"title": "不应提交"},
            )

        unchanged = get_teacher_course(7, self.course_id)
        self.assertEqual(unchanged["title"], "荔枝保果")
        self.assertEqual(unchanged["status"], "published")
        self.assertEqual(unchanged["version"], 1)
        local_status = get_db().execute(
            "SELECT status FROM courses WHERE id = ?",
            (self.course_id,),
        ).fetchone()["status"]
        self.assertEqual(local_status, "pending")
        self.assertEqual(len(self.history_rows()), 1)

    def test_relist_rejects_non_pending_provider_result(self):
        self.submit_initial_course()
        self.review.set_status(
            "course_video",
            str(self.course_id),
            "approved",
        )
        set_course_offline(7, self.course_id, expected_version=1)
        self.review.return_pending = False

        with self.assertRaises(ProviderConflictError):
            request_course_relist(
                7,
                self.course_id,
                expected_version=1,
            )

        unchanged = get_teacher_course(7, self.course_id)
        self.assertEqual(unchanged["status"], "offline")
        self.assertEqual(unchanged["version"], 1)

    def test_review_payload_uses_contract_fields_and_quiz_config(self):
        now = now_shanghai_iso()
        questions = valid_questions()
        get_db().execute(
            """
            INSERT INTO course_quizzes (
                course_id, enabled, scoring_rule, questions_json, updated_at
            )
            VALUES (?, 1, 'all_correct', ?, ?)
            """,
            (
                self.course_id,
                json.dumps(questions, ensure_ascii=False),
                now,
            ),
        )
        get_db().commit()

        payload = review_payload(
            get_teacher_course(7, self.course_id)
        )

        self.assertEqual(
            set(payload),
            {
                "title",
                "direction",
                "summary",
                "tag_ids",
                "duration_seconds",
                "media_url",
                "quiz_config",
            },
        )
        self.assertEqual(payload["title"], "荔枝保果")
        self.assertEqual(payload["quiz_config"]["enabled"], True)
        self.assertEqual(
            payload["quiz_config"]["questions"],
            questions,
        )

    def test_edit_course_persists_quiz_override_with_course_transition(self):
        self.submit_initial_course()
        self.review.set_status(
            "course_video",
            str(self.course_id),
            "approved",
        )
        quiz = valid_quiz()

        edit_course(
            7,
            self.course_id,
            expected_version=1,
            payload={"title": "带测验修订"},
            quiz_override=quiz,
        )

        self.assertEqual(
            self.review.calls[-1]["payload"]["quiz_config"],
            quiz,
        )
        row = get_db().execute(
            """
            SELECT enabled, scoring_rule, questions_json
            FROM course_quizzes
            WHERE course_id = ?
            """,
            (self.course_id,),
        ).fetchone()
        self.assertEqual(row["enabled"], 1)
        self.assertEqual(row["scoring_rule"], "all_correct")
        self.assertEqual(
            row["questions_json"],
            json.dumps(quiz["questions"], ensure_ascii=False),
        )

    def test_invalid_enabled_quiz_override_is_rejected_before_provider(self):
        self.submit_initial_course()
        self.review.set_status(
            "course_video",
            str(self.course_id),
            "approved",
        )
        questions = valid_questions()
        invalid_quizzes = (
            {**valid_quiz(), "scoring_rule": " "},
            {**valid_quiz(), "questions": questions[:2]},
            {
                **valid_quiz(),
                "questions": [
                    questions[0],
                    questions[1],
                    {**questions[2], "id": ""},
                ],
            },
            {
                **valid_quiz(),
                "questions": [
                    questions[0],
                    questions[1],
                    {**questions[2], "id": "q1"},
                ],
            },
            {
                **valid_quiz(),
                "questions": [
                    questions[0],
                    questions[1],
                    {**questions[2], "type": "multiple_choice"},
                ],
            },
            {
                **valid_quiz(),
                "questions": [
                    questions[0],
                    questions[1],
                    {**questions[2], "type": None},
                ],
            },
            {
                **valid_quiz(),
                "questions": [
                    questions[0],
                    questions[1],
                    {**questions[2], "prompt": " "},
                ],
            },
            {
                **valid_quiz(),
                "questions": [
                    questions[0],
                    questions[1],
                    {**questions[2], "options": ["疏果", ""]},
                ],
            },
            {
                **valid_quiz(),
                "questions": [
                    questions[0],
                    questions[1],
                    {**questions[2], "answer": "不存在"},
                ],
            },
        )

        for quiz in invalid_quizzes:
            with self.subTest(quiz=quiz):
                calls_before = list(self.review.calls)
                with self.assertRaises(ProviderValidationError):
                    edit_course(
                        7,
                        self.course_id,
                        expected_version=1,
                        payload={"title": "无效测验不应保存"},
                        quiz_override=quiz,
                    )

                self.assertEqual(self.review.calls, calls_before)
                self.assertIsNone(
                    get_db().execute(
                        """
                        SELECT course_id
                        FROM course_quizzes
                        WHERE course_id = ?
                        """,
                        (self.course_id,),
                    ).fetchone()
                )
                unchanged = get_teacher_course(7, self.course_id)
                self.assertEqual(unchanged["title"], "荔枝保果")
                self.assertEqual(unchanged["version"], 1)

    def test_invalid_persisted_quiz_blocks_submit_before_provider(self):
        now = now_shanghai_iso()
        get_db().execute(
            """
            INSERT INTO course_quizzes (
                course_id, enabled, scoring_rule, questions_json, updated_at
            )
            VALUES (?, 1, 'all_correct', ?, ?)
            """,
            (
                self.course_id,
                json.dumps(valid_questions()[:2], ensure_ascii=False),
                now,
            ),
        )
        get_db().commit()

        with self.assertRaises(ProviderValidationError):
            submit_course_for_review(
                7,
                self.course_id,
                expected_version=1,
            )

        self.assertEqual(self.review.calls, [])
        unchanged = get_teacher_course(7, self.course_id)
        self.assertEqual(unchanged["status"], "draft")
        self.assertEqual(unchanged["version"], 1)
        self.assertEqual(self.history_rows(), [])

    def test_invalid_persisted_quiz_blocks_relist_before_provider(self):
        now = now_shanghai_iso()
        get_db().execute(
            """
            INSERT INTO course_quizzes (
                course_id, enabled, scoring_rule, questions_json, updated_at
            )
            VALUES (?, 1, 'all_correct', ?, ?)
            """,
            (
                self.course_id,
                json.dumps(valid_questions(), ensure_ascii=False),
                now,
            ),
        )
        get_db().commit()
        self.submit_initial_course()
        self.review.set_status(
            "course_video",
            str(self.course_id),
            "approved",
        )
        set_course_offline(7, self.course_id, expected_version=1)
        get_db().execute(
            """
            UPDATE course_quizzes
            SET scoring_rule = ''
            WHERE course_id = ?
            """,
            (self.course_id,),
        )
        get_db().commit()
        calls_before = list(self.review.calls)

        with self.assertRaises(ProviderValidationError):
            request_course_relist(
                7,
                self.course_id,
                expected_version=1,
            )

        self.assertEqual(self.review.calls, calls_before)
        unchanged = get_teacher_course(7, self.course_id)
        self.assertEqual(unchanged["status"], "offline")
        self.assertEqual(unchanged["version"], 1)

    def test_visible_status_matrix_preserves_legacy_published_courses(self):
        self.assertEqual(
            resolve_teacher_visible_status(
                {"teacher_id": None, "status": "published"},
                None,
            ),
            "published",
        )
        self.assertEqual(
            resolve_teacher_visible_status(
                {"teacher_id": 7, "status": "draft"},
                None,
            ),
            "draft",
        )
        self.assertEqual(
            resolve_teacher_visible_status(
                {"teacher_id": 7, "status": "offline"},
                "approved",
            ),
            "offline",
        )
        self.assertEqual(
            resolve_teacher_visible_status(
                {"teacher_id": 7, "status": "pending"},
                "approved",
            ),
            "published",
        )
        self.assertEqual(
            resolve_teacher_visible_status(
                {"teacher_id": 7, "status": "pending"},
                "rejected",
            ),
            "rejected",
        )
        self.assertEqual(
            resolve_teacher_visible_status(
                {"teacher_id": 7, "status": "pending"},
                None,
            ),
            "pending",
        )


if __name__ == "__main__":
    unittest.main()
