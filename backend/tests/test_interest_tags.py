import tempfile
import unittest
from pathlib import Path

from app import create_app
from app.db import get_db, init_db
from app.seed import DEFAULT_INTEREST_TAGS
from app.tags.service import replace_student_tags


class TestInterestTags(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(Path(self.temp_dir.name) / "test.db"),
                "SECRET_KEY": "test-only-secret",
                "SESSION_HOURS": 24,
            }
        )
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def register_student(self, username: str):
        return self.client.post(
            "/api/auth/register",
            json={
                "role": "student",
                "username": username,
                "password": "password8",
                "confirm_password": "password8",
                "name": "林晓",
            },
        )

    def test_tag_catalog_has_three_exact_groups(self):
        response = self.client.get("/api/interest-tags")

        self.assertEqual(response.status_code, 200)
        groups = {item["group_key"] for item in response.get_json()["tags"]}
        self.assertEqual(groups, {"crop", "skill", "job"})

    def test_catalog_seed_is_exact_and_idempotent(self):
        with self.app.app_context():
            init_db()
            rows = get_db().execute(
                """
                SELECT group_key, name
                FROM interest_tags
                WHERE is_active = 1
                ORDER BY
                    CASE group_key
                        WHEN 'crop' THEN 1
                        WHEN 'skill' THEN 2
                        WHEN 'job' THEN 3
                    END,
                    sort_order
                """
            ).fetchall()

        self.assertEqual(
            [(row["group_key"], row["name"]) for row in rows],
            list(DEFAULT_INTEREST_TAGS),
        )

    def test_student_can_save_tags_then_session_becomes_active(self):
        self.register_student("student01")
        tag_ids = [
            tag["id"]
            for tag in self.client.get("/api/interest-tags").get_json()["tags"][:2]
        ]

        saved = self.client.post(
            "/api/auth/interest-tags",
            json={"tag_ids": tag_ids},
        )

        self.assertEqual(saved.status_code, 200)
        self.assertEqual(saved.get_json()["default_path"], "/student")
        session = self.client.get("/api/auth/session")
        self.assertEqual(session.status_code, 200)
        self.assertEqual(session.get_json()["user"]["role"], "student")

    def test_student_can_skip_all_tags(self):
        self.register_student("student01")

        response = self.client.post(
            "/api/auth/interest-tags",
            json={"tag_ids": []},
        )

        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            count = get_db().execute(
                "SELECT COUNT(*) AS total FROM student_interest_tags"
            ).fetchone()["total"]
        self.assertEqual(count, 0)

    def test_student_tag_replacement_removes_previous_selection(self):
        self.register_student("student01")
        tags = self.client.get("/api/interest-tags").get_json()["tags"]
        tag_ids = [tag["id"] for tag in tags[:3]]

        with self.app.app_context():
            replace_student_tags(1, tag_ids[:2])
            replace_student_tags(1, [tag_ids[2], tag_ids[2]])
            selected = {
                row["tag_id"]
                for row in get_db().execute(
                    "SELECT tag_id FROM student_interest_tags"
                )
            }
        self.assertEqual(selected, {tag_ids[2]})

    def test_unknown_tag_id_is_rejected_without_replacing_selection(self):
        self.register_student("student01")
        tag_ids = [
            tag["id"]
            for tag in self.client.get("/api/interest-tags").get_json()["tags"][:1]
        ]
        with self.app.app_context():
            get_db().execute(
                "INSERT INTO student_interest_tags (user_id, tag_id) VALUES (1, ?)",
                (tag_ids[0],),
            )
            get_db().commit()

        response = self.client.post(
            "/api/auth/interest-tags",
            json={"tag_ids": [999999]},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("tag_ids", response.get_json()["errors"])
        with self.app.app_context():
            selected = {
                row["tag_id"]
                for row in get_db().execute(
                    "SELECT tag_id FROM student_interest_tags"
                )
            }
        self.assertEqual(selected, set(tag_ids))

    def test_inactive_tag_id_is_rejected(self):
        self.register_student("student01")
        tag_id = self.client.get("/api/interest-tags").get_json()["tags"][0]["id"]
        with self.app.app_context():
            get_db().execute(
                "UPDATE interest_tags SET is_active = 0 WHERE id = ?",
                (tag_id,),
            )
            get_db().commit()

        response = self.client.post(
            "/api/auth/interest-tags",
            json={"tag_ids": [tag_id]},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("tag_ids", response.get_json()["errors"])

    def test_teacher_session_cannot_use_student_completion_route(self):
        self.client.post(
            "/api/auth/register",
            json={
                "role": "teacher",
                "username": "teacher01",
                "password": "password8",
                "confirm_password": "password8",
                "name": "陈老师",
            },
        )

        response = self.client.post(
            "/api/auth/interest-tags",
            json={"tag_ids": []},
        )

        self.assertEqual(response.status_code, 401)

    def test_pending_session_cannot_open_student_profile(self):
        self.register_student("student01")

        response = self.client.get("/api/student/profile")

        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
