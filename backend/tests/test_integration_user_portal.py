import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from werkzeug.security import generate_password_hash

from app import create_app
from app.db import get_db
from app.seed_dev import seed_local_data


ROLE_PATHS = {
    "student": "/student",
    "teacher": "/teacher",
    "enterprise": "/enterprise",
    "government": "/government",
    "super_admin": "/admin",
    "admin": "/admin",
}


class TestUserPortalIntegration(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = str(Path(self.temp_dir.name) / "test.db")
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": self.database_path,
                "SECRET_KEY": "test-only-secret",
                "SESSION_HOURS": 24,
                "SESSION_COOKIE_SECURE": False,
            }
        )
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def create_tag(self, group_key: str, name: str) -> int:
        with self.app.app_context():
            db = get_db()
            db.execute(
                """
                INSERT INTO interest_tags (group_key, name, sort_order)
                VALUES (?, ?, 0)
                ON CONFLICT (group_key, name) DO UPDATE SET
                    is_active = 1
                """,
                (group_key, name),
            )
            row = db.execute(
                """
                SELECT id
                FROM interest_tags
                WHERE group_key = ? AND name = ?
                """,
                (group_key, name),
            ).fetchone()
            db.commit()
        self.assertIsNotNone(row)
        return int(row["id"])

    def seed_course(
        self,
        title: str,
        direction: str,
        status: str,
        published_at: str,
        tag_ids: list[int],
    ) -> int:
        with self.app.app_context():
            db = get_db()
            cursor = db.execute(
                """
                INSERT INTO courses (
                    title, direction, status, published_at, summary,
                    teacher_name, created_at, updated_at
                ) VALUES (?, ?, ?, ?, '', '测试教师', ?, ?)
                """,
                (
                    title,
                    direction,
                    status,
                    published_at,
                    "2026-09-01T00:00:00+00:00",
                    "2026-09-01T00:00:00+00:00",
                ),
            )
            course_id = cursor.lastrowid
            db.executemany(
                "INSERT INTO course_interest_tags (course_id, tag_id) VALUES (?, ?)",
                [(course_id, tag_id) for tag_id in tag_ids],
            )
            db.commit()
            return course_id

    def login_role(self, role: str) -> None:
        username = f"{role}_acceptance"
        password = "password8"
        now = "2026-09-01T00:00:00+00:00"
        with self.app.app_context():
            db = get_db()
            cursor = db.execute(
                """
                INSERT INTO users (
                    username, password_hash, name, role, is_enabled,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, 1, ?, ?)
                """,
                (
                    username,
                    generate_password_hash(password),
                    f"{role}测试账号",
                    role,
                    now,
                    now,
                ),
            )
            if role == "student":
                user_id = int(cursor.lastrowid)
                db.execute(
                    """
                    INSERT INTO student_profiles (
                        user_id, learning_direction, updated_at
                    )
                    VALUES (?, 'comprehensive', ?)
                    """,
                    (user_id, now),
                )
                db.execute(
                    "INSERT INTO resumes (user_id, created_at) VALUES (?, ?)",
                    (user_id, now),
                )
            db.commit()

        response = self.client.post(
            "/api/auth/login",
            json={"username": username, "password": password},
        )
        self.assertEqual(response.status_code, 200)

    def test_complete_user_portal_journey(self):
        student_payload = {
            "role": "student",
            "username": "journey_student",
            "password": "password8",
            "confirm_password": "password8",
            "name": "整合学员",
        }
        profile_payload = {
            "name": "整合学员",
            "contact": "13800000000",
            "learning_direction": "agriculture",
            "tag_ids": [],
        }

        register = self.client.post("/api/auth/register", json=student_payload)

        self.assertEqual(register.status_code, 201)
        self.assertEqual(register.get_json()["next_step"], "interest-tags")
        self.client.post("/api/auth/interest-tags", json={"tag_ids": []})
        self.assertEqual(self.client.get("/api/auth/session").status_code, 200)

        tag_id = self.create_tag("crop", "荔枝")
        self.seed_course(
            title="荔枝保果",
            direction="agriculture",
            status="published",
            published_at="2026-09-01T00:00:00+00:00",
            tag_ids=[tag_id],
        )
        profile_payload["tag_ids"] = [tag_id]
        profile = self.client.put(
            "/api/student/profile",
            json=profile_payload,
        )
        self.assertEqual(profile.status_code, 200)

        courses = self.client.get(
            "/api/student/courses?direction=agriculture"
        ).get_json()["courses"]
        self.assertTrue(courses[0]["interest_match"])

        for role, expected in ROLE_PATHS.items():
            with self.subTest(role=role):
                self.login_role(role)
                session = self.client.get("/api/auth/session")
                self.assertEqual(session.status_code, 200)
                self.assertEqual(
                    session.get_json()["default_path"],
                    expected,
                )

    def test_seed_dev_requires_configuration_and_refuses_production(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "DEV_SEED_PASSWORD"):
                seed_local_data(self.database_path)

        with patch.dict(
            os.environ,
            {
                "DEV_SEED_PASSWORD": "local-password",
                "SECRET_KEY": "local-secret",
                "FLASK_ENV": "production",
            },
            clear=True,
        ):
            with self.assertRaisesRegex(ValueError, "production"):
                seed_local_data(self.database_path)

    def test_seed_dev_is_repeatable_and_seeds_all_roles(self):
        environment = {
            "DEV_SEED_PASSWORD": "local-password",
            "SECRET_KEY": "local-secret",
        }
        with patch.dict(os.environ, environment, clear=True):
            seed_local_data(self.database_path)
            seed_local_data(self.database_path)

        with self.app.app_context():
            db = get_db()
            seeded_roles = {
                row["role"]
                for row in db.execute(
                    """
                    SELECT role
                    FROM users
                    WHERE is_enabled = 1
                    """
                )
            }
            published_count = db.execute(
                """
                SELECT COUNT(*) AS count
                FROM courses
                WHERE status = 'published'
                """
            ).fetchone()["count"]
            tag_count = db.execute(
                "SELECT COUNT(*) AS count FROM interest_tags"
            ).fetchone()["count"]

        self.assertEqual(seeded_roles, set(ROLE_PATHS))
        self.assertGreaterEqual(published_count, 3)
        self.assertGreaterEqual(tag_count, 12)


if __name__ == "__main__":
    unittest.main()
