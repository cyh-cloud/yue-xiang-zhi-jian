import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from app import create_app
from app.agri_skills.course_learning import (
    DatabaseAgriCourseProvider,
    get_course_progress,
    list_courses,
    list_recommendations,
    update_course_progress,
)
from app.agri_skills.errors import AgriNotFoundError, AgriValidationError
from app.agri_skills.providers import get_course_provider, set_course_provider
from app.db import get_db


class FakeCourseProvider:
    def __init__(self, courses: list[dict]) -> None:
        self.courses = [dict(course) for course in courses]

    def list_published_agriculture_courses(self, student_id: int) -> list[dict]:
        return [dict(course) for course in self.courses]

    def get_course(self, course_id: int) -> dict | None:
        course = next(
            (course for course in self.courses if course["id"] == course_id),
            None,
        )
        return dict(course) if course is not None else None

    def get_quiz(self, course_id: int) -> dict | None:
        return None


class BlockingProgressSnapshotConnection:
    def __init__(self, connection, barrier: threading.Barrier) -> None:
        self.connection = connection
        self.barrier = barrier
        if not hasattr(threading.current_thread(), "agri_snapshot_blocked"):
            threading.current_thread().agri_snapshot_blocked = False
        if not hasattr(threading.current_thread(), "agri_progress_written"):
            threading.current_thread().agri_progress_written = False

    def execute(self, statement: str, parameters=()):
        cursor = self.connection.execute(statement, parameters)
        normalized = " ".join(statement.upper().split())
        if normalized.startswith("INSERT INTO AGRI_COURSE_PROGRESS"):
            threading.current_thread().agri_progress_written = True
        if (
            normalized.startswith("SELECT * FROM AGRI_COURSE_PROGRESS")
            and not threading.current_thread().agri_snapshot_blocked
            and not threading.current_thread().agri_progress_written
        ):
            threading.current_thread().agri_snapshot_blocked = True
            self.barrier.wait(timeout=5)
        return cursor

    def __enter__(self):
        self.connection.__enter__()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return self.connection.__exit__(exc_type, exc_value, traceback)


class TestAgriCourseProgress(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(Path(self.temp_dir.name) / "test.db"),
                "SECRET_KEY": "test-only-secret",
            }
        )
        with self.app.app_context():
            db = get_db()
            cursor = db.execute(
                """
                INSERT INTO users (
                    username, password_hash, name, role, is_enabled,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, 'student', 1, ?, ?)
                """,
                (
                    "student01",
                    "test-password-hash",
                    "林晓",
                    "2026-09-15T00:00:00+00:00",
                    "2026-09-15T00:00:00+00:00",
                ),
            )
            self.student_id = int(cursor.lastrowid)
            now = "2026-09-15T00:00:00+00:00"
            db.executemany(
                """
                INSERT INTO courses (
                    id, title, direction, status, published_at, summary,
                    teacher_name, created_at, updated_at
                )
                VALUES (?, ?, 'agriculture', 'published', ?, ?, '林老师', ?, ?)
                """,
                (
                    (
                        1,
                        "荔枝保果",
                        "2026-09-01T00:00:00+00:00",
                        "荔枝保果课程简介",
                        now,
                        now,
                    ),
                    (
                        2,
                        "水稻种植",
                        "2026-09-03T00:00:00+00:00",
                        "水稻种植课程简介",
                        now,
                        now,
                    ),
                    (
                        3,
                        "荔枝病虫害防治",
                        "2026-09-02T00:00:00+00:00",
                        "荔枝病虫害防治课程简介",
                        now,
                        now,
                    ),
                ),
            )
            db.execute(
                """
                INSERT INTO courses (
                    id, title, direction, status, published_at, summary,
                    teacher_name, created_at, updated_at
                )
                VALUES (
                    4, '电商课程', 'ecommerce', 'published', ?,
                    '电商课程简介', '陈老师', ?, ?
                )
                """,
                (now, now, now),
            )
            db.execute(
                """
                INSERT INTO courses (
                    id, title, direction, status, published_at, summary,
                    teacher_name, created_at, updated_at
                )
                VALUES (5, '未上架农业课程', 'agriculture', 'offline', ?, '', '', ?, ?)
                """,
                (now, now, now),
            )
            db.executemany(
                """
                INSERT INTO student_interest_tags (user_id, tag_id)
                VALUES (?, ?)
                """,
                ((self.student_id, 1), (self.student_id, 2)),
            )
            db.executemany(
                """
                INSERT INTO course_interest_tags (course_id, tag_id)
                VALUES (?, ?)
                """,
                ((1, 1), (2, 1), (3, 1), (3, 2)),
            )
            db.commit()

        self.course_fixture = {
            "id": 1,
            "title": "荔枝保果",
            "direction": "agriculture",
            "summary": "保果与病虫害管理",
            "teacher_name": "林老师",
            "published_at": "2026-09-01T00:00:00+00:00",
            "tag_ids": [1],
            "duration_seconds": 100,
        }
        self.course_provider = FakeCourseProvider(
            [
                self.course_fixture,
                {
                    **self.course_fixture,
                    "id": 2,
                    "title": "水稻种植",
                    "published_at": "2026-09-03T00:00:00+00:00",
                },
                {
                    **self.course_fixture,
                    "id": 3,
                    "title": "荔枝病虫害防治",
                    "published_at": "2026-09-02T00:00:00+00:00",
                    "tag_ids": [1, 2],
                },
            ]
        )
        set_course_provider(self.app, self.course_provider)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_progress_is_floor_position_over_duration(self):
        with self.app.app_context():
            result = update_course_progress(self.student_id, 1, 79, 10)
            self.assertEqual(result["progress_percent"], 79)
            self.assertIsNone(result["completed_at"])

            result = update_course_progress(self.student_id, 1, 80, 1)
            self.assertEqual(result["progress_percent"], 80)
            self.assertIsNotNone(result["completed_at"])

    def test_lower_resume_position_does_not_lower_furthest_progress(self):
        with self.app.app_context():
            update_course_progress(self.student_id, 1, 90, 90)
            result = update_course_progress(self.student_id, 1, 40, 0)

            self.assertEqual(result["furthest_position_seconds"], 90)
            self.assertEqual(result["resume_position_seconds"], 40)
            self.assertEqual(result["progress_percent"], 90)

    def test_duplicate_progress_event_does_not_double_count_watch_time(self):
        with self.app.app_context():
            first = update_course_progress(self.student_id, 1, 60, 30)
            duplicate = update_course_progress(self.student_id, 1, 60, 30)

            self.assertEqual(first["watched_seconds"], 30)
            self.assertEqual(duplicate["watched_seconds"], 30)
            self.assertEqual(duplicate["furthest_position_seconds"], 60)
            self.assertEqual(duplicate["progress_percent"], 60)

    def test_out_of_order_progress_does_not_double_count_watch_time(self):
        with self.app.app_context():
            update_course_progress(self.student_id, 1, 90, 30)
            result = update_course_progress(self.student_id, 1, 40, 20)

            self.assertEqual(result["watched_seconds"], 30)
            self.assertEqual(result["furthest_position_seconds"], 90)
            self.assertEqual(result["resume_position_seconds"], 40)
            self.assertEqual(result["progress_percent"], 90)

    def test_same_position_replay_does_not_double_count_watch_time(self):
        with self.app.app_context():
            update_course_progress(self.student_id, 1, 60, 30)
            replay = update_course_progress(self.student_id, 1, 60, 5)

            self.assertEqual(replay["watched_seconds"], 30)
            self.assertEqual(replay["furthest_position_seconds"], 60)
            self.assertEqual(replay["resume_position_seconds"], 60)
            self.assertEqual(replay["progress_percent"], 60)

    def test_concurrent_duplicate_updates_are_counted_once(self):
        barrier = threading.Barrier(2)

        def update(position, watched_delta):
            with self.app.app_context():
                return update_course_progress(
                    self.student_id,
                    1,
                    position,
                    watched_delta,
                )

        def blocking_get_db():
            return BlockingProgressSnapshotConnection(get_db(), barrier)

        with patch(
            "app.agri_skills.course_learning.get_db",
            side_effect=blocking_get_db,
        ):
            with ThreadPoolExecutor(max_workers=2) as executor:
                results = [
                    future.result()
                    for future in (
                        executor.submit(update, 40, 10),
                        executor.submit(update, 40, 10),
                    )
                ]

        self.assertEqual(len(results), 2)
        with self.app.app_context():
            progress = get_course_progress(self.student_id, 1)
        self.assertEqual(progress["furthest_position_seconds"], 40)
        self.assertEqual(progress["watched_seconds"], 10)
        self.assertEqual(progress["progress_percent"], 40)
        self.assertIsNone(progress["completed_at"])

    def test_invalid_progress_is_rejected_without_mutation(self):
        with self.app.app_context():
            for position in (-1, 101):
                with self.subTest(position=position):
                    with self.assertRaises(AgriValidationError):
                        update_course_progress(self.student_id, 1, position, 0)

            self.assertEqual(
                get_course_progress(self.student_id, 1)["progress_percent"],
                0,
            )

    def test_missing_duration_rejects_progress_without_mutation(self):
        with self.app.app_context():
            self.course_provider.courses[0]["duration_seconds"] = None

            with self.assertRaisesRegex(AgriValidationError, "课程时长不可用"):
                update_course_progress(self.student_id, 1, 10, 10)

            self.assertEqual(
                get_course_progress(self.student_id, 1)["progress_percent"],
                0,
            )

    def test_recommendations_sort_by_intersection_viewing_and_time(self):
        with self.app.app_context():
            db = get_db()
            for course_id, progress, viewed_at in (
                (1, 20, "2026-09-10T00:00:00+00:00"),
                (2, 30, "2026-09-12T00:00:00+00:00"),
            ):
                db.execute(
                    """
                    INSERT INTO agri_course_progress (
                        user_id, course_id, duration_seconds,
                        furthest_position_seconds, resume_position_seconds,
                        progress_percent, watched_seconds, completed_at,
                        last_viewed_at, updated_at
                    )
                    VALUES (?, ?, 100, ?, ?, ?, ?, NULL, ?, ?)
                    """,
                    (
                        self.student_id,
                        course_id,
                        progress,
                        progress,
                        progress,
                        progress,
                        viewed_at,
                        viewed_at,
                    ),
                )
            db.commit()

            ids = [
                item["id"] for item in list_recommendations(self.student_id)
            ]

            self.assertEqual(ids, [3, 2, 1])

    def test_database_provider_filters_and_hydrates_agriculture_courses(self):
        with self.app.app_context():
            provider = DatabaseAgriCourseProvider()

            courses = provider.list_published_courses(
                self.student_id,
                "agriculture",
            )

            self.assertEqual([course["id"] for course in courses], [2, 3, 1])
            self.assertEqual(courses[0]["tag_ids"], [1])
            duration = courses[0]["duration_seconds"]
            self.assertIsInstance(duration, int)
            self.assertGreater(duration, 0)
            self.assertEqual(
                provider.get_course(2)["duration_seconds"],
                duration,
            )
            ecommerce = provider.list_published_courses(
                self.student_id,
                "ecommerce",
            )
            self.assertEqual([course["id"] for course in ecommerce], [4])
            self.assertEqual(provider.get_course(4)["direction"], "ecommerce")
            self.assertIsNone(provider.get_course(5))

    def test_list_courses_and_recommendations_are_direction_aware(self):
        with self.app.app_context():
            self.app.extensions.pop("agri_course_provider", None)

            agriculture = list_courses(self.student_id, "agriculture")
            ecommerce = list_courses(self.student_id, "ecommerce")
            recommendations = list_recommendations(
                self.student_id,
                "ecommerce",
            )

            self.assertEqual(
                [course["id"] for course in agriculture],
                [2, 3, 1],
            )
            self.assertEqual([course["id"] for course in ecommerce], [4])
            self.assertEqual([course["id"] for course in recommendations], [4])

    def test_course_actions_reject_courses_from_another_direction(self):
        with self.app.app_context():
            with self.assertRaises(AgriNotFoundError):
                get_course_progress(self.student_id, 1, "ecommerce")

    def test_default_course_provider_supports_stable_progress_loop(self):
        with self.app.app_context():
            self.app.extensions.pop("agri_course_provider", None)

            provider = get_course_provider()
            self.assertIsInstance(provider, DatabaseAgriCourseProvider)
            first = provider.get_course(1)
            second = provider.get_course(1)
            duration = first["duration_seconds"]
            self.assertIsInstance(duration, int)
            self.assertGreater(duration, 0)
            self.assertEqual(second["duration_seconds"], duration)

            completion_position = (duration * 80) // 100
            progress = update_course_progress(
                self.student_id,
                1,
                completion_position,
                completion_position,
            )

            self.assertEqual(progress["duration_seconds"], duration)
            self.assertEqual(progress["progress_percent"], 80)
            self.assertIsNotNone(progress["completed_at"])


if __name__ == "__main__":
    unittest.main()
