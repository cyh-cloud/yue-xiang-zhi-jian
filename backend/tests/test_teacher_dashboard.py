import json
import tempfile
import unittest
from pathlib import Path

from werkzeug.security import generate_password_hash

from app import create_app
from app.content_review import set_content_review_provider
from app.db import get_db
from app.teacher_console.dashboard import build_teacher_dashboard


class FakeReviewProvider:
    def __init__(self):
        self.records = {}

    def set_status(
        self,
        course_id,
        review_status,
        *,
        published_at=None,
    ):
        self.records[str(course_id)] = {
            "review_status": review_status,
            "published_at": published_at,
        }

    def get_review_status(self, *, content_type, content_id):
        if content_type != "course_video":
            return None
        record = self.records.get(str(content_id))
        return dict(record) if record is not None else None


class TestTeacherDashboard(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(Path(self.temp_dir.name) / "test.db"),
                "SECRET_KEY": "test-only-secret",
            }
        )
        self.review = FakeReviewProvider()
        set_content_review_provider(self.app, self.review)
        self.teacher_id = 1

        with self.app.app_context():
            self._seed_fixture()

    def tearDown(self):
        self.temp_dir.cleanup()

    def _seed_fixture(self):
        db = get_db()
        now = "2026-09-19T09:00:00+08:00"
        db.execute("DELETE FROM courses")
        db.executemany(
            """
            INSERT INTO users (
                id, username, password_hash, name, role, is_enabled,
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                (
                    1,
                    "teacher01",
                    generate_password_hash("password8"),
                    "教师甲",
                    "teacher",
                    1,
                    now,
                    now,
                ),
                (
                    2,
                    "student02",
                    generate_password_hash("password8"),
                    "姓名学员乙",
                    "student",
                    1,
                    now,
                    now,
                ),
                (
                    3,
                    "student03",
                    generate_password_hash("password8"),
                    "姓名学员丙",
                    "student",
                    1,
                    now,
                    now,
                ),
                (
                    4,
                    "student04",
                    generate_password_hash("password8"),
                    "姓名学员丁",
                    "student",
                    1,
                    now,
                    now,
                ),
                (
                    5,
                    "student05",
                    generate_password_hash("password8"),
                    "停用学员",
                    "student",
                    0,
                    now,
                    now,
                ),
                (
                    6,
                    "student06",
                    generate_password_hash("password8"),
                    "未建档学员",
                    "student",
                    1,
                    now,
                    now,
                ),
                (
                    7,
                    "teacher07",
                    generate_password_hash("password8"),
                    "教师庚",
                    "teacher",
                    1,
                    now,
                    now,
                ),
            ),
        )
        db.executemany(
            """
            INSERT INTO student_profiles (
                user_id, contact, learning_direction, updated_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                (2, "13800000002", "agriculture", now),
                (3, "13800000003", "ecommerce", now),
                (4, "13800000004", "comprehensive", now),
                (5, "13800000005", "agriculture", now),
            ),
        )
        db.executemany(
            """
            INSERT INTO courses (
                id, title, direction, status, duration_seconds, media_url,
                published_at, summary, teacher_name, teacher_id, version,
                media_source_type, content_tags_json, rejection_opinion,
                submitted_at, created_at, updated_at
            )
            VALUES (
                ?, ?, ?, ?, 300, ?, ?, ?, ?, ?, 1, 'external_url', '[]',
                NULL, NULL, ?, ?
            )
            """,
            (
                (
                    1,
                    "农业基础一",
                    "agriculture",
                    "published",
                    "https://media.example.test/1.mp4",
                    now,
                    "农业课程",
                    "平台课程",
                    None,
                    now,
                    now,
                ),
                (
                    2,
                    "农业基础二",
                    "agriculture",
                    "published",
                    "https://media.example.test/2.mp4",
                    now,
                    "农业课程",
                    "平台课程",
                    None,
                    now,
                    now,
                ),
                (
                    3,
                    "教师农业课程一",
                    "agriculture",
                    "pending",
                    "https://media.example.test/3.mp4",
                    None,
                    "农业课程",
                    "教师甲",
                    1,
                    now,
                    now,
                ),
                (
                    4,
                    "教师农业课程二",
                    "agriculture",
                    "pending",
                    "https://media.example.test/4.mp4",
                    None,
                    "农业课程",
                    "教师甲",
                    1,
                    now,
                    now,
                ),
                (
                    5,
                    "电商基础",
                    "ecommerce",
                    "published",
                    "https://media.example.test/5.mp4",
                    now,
                    "电商课程",
                    "平台课程",
                    None,
                    now,
                    now,
                ),
                (
                    6,
                    "其他教师课程",
                    "handcraft",
                    "pending",
                    "https://media.example.test/6.mp4",
                    None,
                    "手工课程",
                    "教师庚",
                    7,
                    now,
                    now,
                ),
                (
                    7,
                    "教师未过审课程",
                    "agriculture",
                    "published",
                    "https://media.example.test/7.mp4",
                    now,
                    "农业课程",
                    "教师甲",
                    1,
                    now,
                    now,
                ),
            ),
        )
        self.review.set_status(
            3,
            "approved",
            published_at="2026-09-19T10:00:00+08:00",
        )
        self.review.set_status(
            4,
            "approved",
            published_at="2026-09-19T10:01:00+08:00",
        )
        self.review.set_status(
            6,
            "approved",
            published_at="2026-09-19T10:02:00+08:00",
        )
        self.review.set_status(7, "pending")
        db.executemany(
            """
            INSERT INTO agri_course_progress (
                user_id, course_id, duration_seconds,
                furthest_position_seconds, resume_position_seconds,
                progress_percent, watched_seconds, completed_at,
                last_viewed_at, updated_at
            )
            VALUES (?, ?, 300, 240, 240, ?, 240, ?, ?, ?)
            """,
            (
                (2, 1, 80, None, now, now),
                (2, 2, 100, now, now, now),
                (2, 3, 80, now, now, now),
                (2, 4, 100, now, now, now),
                (3, 5, 79, None, now, now),
                (4, 1, 80, None, now, now),
                (4, 2, 100, now, now, now),
                (4, 5, 80, None, now, now),
            ),
        )
        db.executemany(
            """
            INSERT INTO agri_course_quiz_attempts (
                user_id, course_id, answers_json, result_json, score,
                is_formal, created_at
            )
            VALUES (?, ?, '{}', '{}', ?, ?, ?)
            """,
            (
                (2, 3, 100, 1, now),
                (2, 4, 70, 0, now),
                (3, 7, 50, 1, now),
                (4, 6, 10, 1, now),
            ),
        )
        db.commit()

    def test_dashboard_uses_self_selected_direction_and_80_percent_completion(
        self,
    ):
        with self.app.app_context():
            dashboard = build_teacher_dashboard(self.teacher_id)

        self.assertEqual(dashboard["student_total"], 3)
        self.assertEqual(dashboard["average_progress"], 50.0)
        self.assertEqual(dashboard["completion_rate"], 33.33)
        self.assertEqual(dashboard["quiz_attempt_count"], 2)
        self.assertEqual(dashboard["quiz_average_score"], 85.0)
        self.assertEqual(
            dashboard["directions"]["comprehensive"]["student_count"],
            1,
        )
        self.assertEqual(
            dashboard["directions"],
            {
                "agriculture": {
                    "student_count": 1,
                    "average_progress": 100.0,
                },
                "ecommerce": {
                    "student_count": 1,
                    "average_progress": 0.0,
                },
                "handcraft": {
                    "student_count": 0,
                    "average_progress": 0.0,
                },
                "comprehensive": {
                    "student_count": 1,
                    "average_progress": 50.0,
                },
            },
        )

    def test_dashboard_does_not_expose_student_details(self):
        with self.app.app_context():
            payload = build_teacher_dashboard(self.teacher_id)

        serialized = json.dumps(payload, ensure_ascii=False)
        self.assertEqual(
            set(payload),
            {
                "student_total",
                "average_progress",
                "completion_rate",
                "quiz_attempt_count",
                "quiz_average_score",
                "directions",
            },
        )
        self.assertNotIn("姓名", serialized)
        self.assertNotIn("contact", serialized)
        self.assertNotIn("student_id", serialized)
        self.assertNotIn("138000000", serialized)

    def test_zero_published_courses_uses_zero_progress_and_no_division_error(
        self,
    ):
        with self.app.app_context():
            get_db().execute("DELETE FROM courses")
            get_db().commit()
            dashboard = build_teacher_dashboard(self.teacher_id)

        self.assertEqual(dashboard["average_progress"], 0.0)
        self.assertEqual(dashboard["completion_rate"], 0.0)
        self.assertEqual(dashboard["quiz_attempt_count"], 0)
        self.assertEqual(dashboard["quiz_average_score"], 0.0)
        self.assertTrue(
            all(
                group["average_progress"] == 0.0
                for group in dashboard["directions"].values()
            )
        )


if __name__ == "__main__":
    unittest.main()
