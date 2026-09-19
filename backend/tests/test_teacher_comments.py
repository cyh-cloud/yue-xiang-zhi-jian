import copy
import tempfile
import unittest
from pathlib import Path

from app import create_app
from app.agri_skills.providers import set_course_provider
from app.db import get_db
from app.handcraft_inheritance.providers import (
    EmptyTeachingVideoProvider,
    set_teaching_video_provider,
)
from app.teacher_console.comments import (
    list_teacher_comments,
    reply_to_comment,
)
from app.teacher_console.errors import (
    ProviderAccessDeniedError,
    ProviderConflictError,
    ProviderNotFoundError,
    ProviderValidationError,
)


class CompleteTeachingVideoProvider:
    def __init__(self, videos):
        self.videos = copy.deepcopy(videos)
        self.requested_video_ids = []

    def list_videos(self, craft_key=None):
        return [
            copy.deepcopy(video)
            for video in self.videos
            if craft_key is None or video["craft_key"] == craft_key
        ]

    def get_video(self, video_id):
        self.requested_video_ids.append(video_id)
        return next(
            (
                copy.deepcopy(video)
                for video in self.videos
                if video["video_id"] == video_id
            ),
            None,
        )

    def get_review_status(self, video_id):
        video = next(
            (
                video
                for video in self.videos
                if video["video_id"] == video_id
            ),
            None,
        )
        return video["review_status"] if video is not None else None


class StaticCourseProvider:
    def __init__(self, courses):
        self.courses = copy.deepcopy(courses)

    def list_published_courses(self, student_id, direction):
        return [
            copy.deepcopy(course)
            for course in self.courses.values()
            if course["direction"] == direction
        ]

    def get_course(self, course_id):
        course = self.courses.get(int(course_id))
        return copy.deepcopy(course) if course is not None else None

    def get_quiz(self, course_id):
        return None


class TestTeacherComments(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(Path(self.temp_dir.name) / "test.db"),
                "SECRET_KEY": "test-only-secret",
            }
        )
        self.context = self.app.app_context()
        self.context.push()

        self.teacher_id = self.create_user(
            "teacher-a", "教师甲", "teacher"
        )
        self.other_teacher_id = self.create_user(
            "teacher-b", "教师乙", "teacher"
        )
        self.student_id = self.create_user(
            "student-a", "学员甲", "student"
        )

        self.course_id = 101
        self.other_course_id = 202
        self.create_course(self.course_id, self.teacher_id, "本人课程")
        self.create_course(
            self.other_course_id,
            self.other_teacher_id,
            "他人课程",
        )

        self.course_comment_id = self.create_comment(
            "course-own",
            "course_video",
            str(self.course_id),
            "2026-09-19T10:00:00+08:00",
        )
        self.create_comment(
            "course-other",
            "course_video",
            str(self.other_course_id),
            "2026-09-19T10:01:00+08:00",
        )
        self.heritage_comment_id = self.create_comment(
            "heritage-visible",
            "handcraft_teaching_video",
            "video-visible",
            "2026-09-19T10:02:00+08:00",
        )
        self.create_comment(
            "heritage-pending",
            "handcraft_teaching_video",
            "video-pending",
            "2026-09-19T10:03:00+08:00",
        )
        self.create_comment(
            "heritage-offline",
            "handcraft_teaching_video",
            "video-offline",
            "2026-09-19T10:04:00+08:00",
        )
        self.create_comment(
            "heritage-missing",
            "handcraft_teaching_video",
            "video-missing",
            "2026-09-19T10:05:00+08:00",
        )
        self.create_comment(
            "comment-hidden",
            "course_video",
            str(self.course_id),
            "2026-09-19T10:06:00+08:00",
            is_visible=0,
        )
        get_db().commit()

        set_course_provider(
            self.app,
            StaticCourseProvider(
                {
                    self.course_id: self.course_payload(
                        self.course_id,
                        "本人课程",
                    ),
                    self.other_course_id: self.course_payload(
                        self.other_course_id,
                        "他人课程",
                    ),
                }
            ),
        )
        self.video_provider = CompleteTeachingVideoProvider(
            [
                {
                    "video_id": "video-visible",
                    "craft_key": "guangxiu",
                    "review_status": "approved",
                    "source_available": True,
                },
                {
                    "video_id": "video-pending",
                    "craft_key": "guangxiu",
                    "review_status": "pending",
                    "source_available": True,
                },
                {
                    "video_id": "video-offline",
                    "craft_key": "guangxiu",
                    "review_status": "approved",
                    "source_available": False,
                },
            ]
        )
        set_teaching_video_provider(self.app, self.video_provider)

    def tearDown(self):
        self.context.pop()
        self.temp_dir.cleanup()

    def create_user(self, username, name, role):
        now = "2026-09-19T09:00:00+08:00"
        cursor = get_db().execute(
            """
            INSERT INTO users (
                username, password_hash, name, role, is_enabled,
                created_at, updated_at
            )
            VALUES (?, 'hash', ?, ?, 1, ?, ?)
            """,
            (username, name, role, now, now),
        )
        return int(cursor.lastrowid)

    def create_course(self, course_id, teacher_id, title):
        now = "2026-09-19T09:00:00+08:00"
        get_db().execute(
            """
            INSERT INTO courses (
                id, title, direction, status, duration_seconds,
                media_url, published_at, summary, teacher_name,
                teacher_id, version, media_source_type,
                content_tags_json, created_at, updated_at
            )
            VALUES (
                ?, ?, 'agriculture', 'published', 300,
                'https://media.example.test/course.mp4', ?, ?,
                '教师', ?, 1, 'external_url', '[]', ?, ?
            )
            """,
            (
                course_id,
                title,
                now,
                f"{title}简介",
                teacher_id,
                now,
                now,
            ),
        )

    def course_payload(self, course_id, title):
        return {
            "id": course_id,
            "title": title,
            "direction": "agriculture",
            "status": "published",
            "summary": f"{title}简介",
            "teacher_name": "教师",
            "published_at": "2026-09-19T09:00:00+08:00",
            "duration_seconds": 300,
            "media_url": "https://media.example.test/course.mp4",
            "tag_ids": [],
            "content_tags": [],
        }

    def create_comment(
        self,
        comment_id,
        content_type,
        content_id,
        created_at,
        *,
        is_visible=1,
    ):
        get_db().execute(
            """
            INSERT INTO content_comments (
                comment_id, content_type, content_id, author_id,
                body, is_teacher_reply, is_visible, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?)
            """,
            (
                comment_id,
                content_type,
                content_id,
                self.student_id,
                f"{comment_id} 留言",
                is_visible,
                created_at,
                created_at,
            ),
        )
        return comment_id

    def create_heritage_video(self, video_id):
        now = "2026-09-19T09:00:00+08:00"
        get_db().execute(
            """
            INSERT INTO heritage_videos (
                video_id, craft_key, title, review_status,
                source_available, media_url, version,
                published_at, created_at, updated_at
            )
            VALUES (
                ?, 'guangxiu', ?, 'approved', 1,
                'https://media.example.test/heritage.mp4', 1, ?, ?, ?
            )
            """,
            (video_id, video_id, now, now, now),
        )

    def test_list_teacher_comments_scopes_courses_and_visible_videos(self):
        comments = list_teacher_comments(self.teacher_id)

        self.assertEqual(
            [comment["comment_id"] for comment in comments],
            ["course-own", "heritage-visible"],
        )
        self.assertEqual(comments[0]["content_id"], str(self.course_id))
        self.assertIsInstance(comments[0]["content_id"], str)
        self.assertFalse(comments[0]["is_teacher_reply"])

    def test_list_teacher_comments_applies_content_filters(self):
        self.assertEqual(
            [
                comment["comment_id"]
                for comment in list_teacher_comments(
                    self.teacher_id,
                    content_type="course_video",
                )
            ],
            ["course-own"],
        )
        self.assertEqual(
            [
                comment["comment_id"]
                for comment in list_teacher_comments(
                    self.teacher_id,
                    content_type="handcraft_teaching_video",
                    content_id="video-visible",
                )
            ],
            ["heritage-visible"],
        )
        self.assertEqual(
            list_teacher_comments(
                self.teacher_id,
                content_type="handcraft_teaching_video",
                content_id="video-pending",
            ),
            [],
        )

    def test_reply_to_own_course_persists_teacher_reply(self):
        reply = reply_to_comment(
            self.teacher_id,
            self.course_comment_id,
            "  按以下步骤复习  ",
        )

        self.assertTrue(reply["is_teacher_reply"])
        self.assertEqual(reply["parent_comment_id"], self.course_comment_id)
        self.assertEqual(reply["body"], "按以下步骤复习")
        self.assertEqual(reply["content_id"], str(self.course_id))
        self.assertTrue(reply["created_at"].endswith("+08:00"))
        self.assertTrue(reply["updated_at"].endswith("+08:00"))

        row = get_db().execute(
            """
            SELECT author_id, parent_comment_id, body,
                   is_teacher_reply, is_visible
            FROM content_comments
            WHERE comment_id = ?
            """,
            (reply["comment_id"],),
        ).fetchone()
        self.assertEqual(row["author_id"], self.teacher_id)
        self.assertEqual(row["parent_comment_id"], self.course_comment_id)
        self.assertEqual(row["body"], "按以下步骤复习")
        self.assertEqual(row["is_teacher_reply"], 1)
        self.assertEqual(row["is_visible"], 1)

    def test_reply_to_another_teachers_course_is_denied(self):
        with self.assertRaises(ProviderAccessDeniedError):
            reply_to_comment(
                self.other_teacher_id,
                self.course_comment_id,
                "越权",
            )

        count = get_db().execute(
            """
            SELECT COUNT(*) AS count
            FROM content_comments
            WHERE parent_comment_id = ?
            """,
            (self.course_comment_id,),
        ).fetchone()["count"]
        self.assertEqual(count, 0)

    def test_reply_to_visible_heritage_video_uses_provider(self):
        reply = reply_to_comment(
            self.teacher_id,
            self.heritage_comment_id,
            "先固定绣线再起针",
        )

        self.assertTrue(reply["is_teacher_reply"])
        self.assertEqual(reply["content_id"], "video-visible")
        self.assertEqual(
            self.video_provider.requested_video_ids,
            ["video-visible"],
        )

    def test_reply_to_hidden_or_missing_heritage_video_is_conflict(self):
        for comment_id in (
            "heritage-pending",
            "heritage-offline",
            "heritage-missing",
        ):
            with self.subTest(comment_id=comment_id):
                with self.assertRaises(ProviderConflictError):
                    reply_to_comment(
                        self.teacher_id,
                        comment_id,
                        "不应写入",
                    )

        count = get_db().execute(
            """
            SELECT COUNT(*) AS count
            FROM content_comments
            WHERE is_teacher_reply = 1
            """
        ).fetchone()["count"]
        self.assertEqual(count, 0)

    def test_default_video_provider_does_not_fallback_to_database(self):
        self.create_heritage_video("video-db-approved")
        self.create_comment(
            "heritage-db-approved",
            "handcraft_teaching_video",
            "video-db-approved",
            "2026-09-19T10:07:00+08:00",
        )
        get_db().commit()
        set_teaching_video_provider(
            self.app,
            EmptyTeachingVideoProvider(),
        )

        with self.assertRaises(ProviderConflictError):
            reply_to_comment(
                self.teacher_id,
                "heritage-db-approved",
                "不能绕过 provider",
            )

    def test_hidden_parent_comment_is_not_found(self):
        with self.assertRaises(ProviderNotFoundError):
            reply_to_comment(
                self.teacher_id,
                "comment-hidden",
                "不应回复",
            )

    def test_comment_inputs_are_validated(self):
        with self.assertRaises(ProviderValidationError):
            list_teacher_comments(
                self.teacher_id,
                content_type="unknown",
            )
        with self.assertRaises(ProviderValidationError):
            list_teacher_comments(
                self.teacher_id,
                content_type="course_video",
                content_id=" ",
            )
        with self.assertRaises(ProviderValidationError):
            reply_to_comment(
                self.teacher_id,
                self.course_comment_id,
                "   ",
            )


if __name__ == "__main__":
    unittest.main()
