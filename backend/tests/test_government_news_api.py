import tempfile
from pathlib import Path
from unittest import TestCase

from werkzeug.security import generate_password_hash

from app import create_app
from app.db import get_db


class GovernmentNewsApiTests(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(Path(self.temp_dir.name) / "test.db"),
                "SECRET_KEY": "test-only-secret",
                "SESSION_HOURS": 24,
                "SESSION_COOKIE_SECURE": False,
            }
        )
        self.client = self.app.test_client()
        self._create_user("government01", "government")
        self._create_user("student01", "student")

    def tearDown(self):
        self.temp_dir.cleanup()

    def _create_user(self, username: str, role: str) -> int:
        with self.app.app_context():
            cursor = get_db().execute(
                """
                INSERT INTO users (
                    username, password_hash, name, role, is_enabled,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, 1, ?, ?)
                """,
                (
                    username,
                    generate_password_hash("password8"),
                    username,
                    role,
                    "2026-09-18T09:00:00+08:00",
                    "2026-09-18T09:00:00+08:00",
                ),
            )
            get_db().commit()
        return int(cursor.lastrowid)

    def login_government(self):
        response = self.client.post(
            "/api/auth/login",
            json={"username": "government01", "password": "password8"},
        )
        self.assertEqual(response.status_code, 200)

    def login_student(self):
        response = self.client.post(
            "/api/auth/login",
            json={"username": "student01", "password": "password8"},
        )
        self.assertEqual(response.status_code, 200)

    def publish_news(self, **overrides):
        payload = {
            "request_id": "api-news-1",
            "title": "暴雨预警",
            "content": "注意防范",
            "category_code": "disaster_warning",
        }
        payload.update(overrides)
        return self.client.post("/api/government/news", json=payload)

    def test_government_can_publish_list_and_delete_news(self):
        self.login_government()

        created = self.publish_news()
        self.assertEqual(created.status_code, 201)
        news = created.get_json()["news"]
        self.assertEqual(news["category_label"], "灾害预警")
        self.assertNotIn("status", news)

        listed = self.client.get(
            "/api/government/news?category=disaster_warning"
        )
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(
            [item["id"] for item in listed.get_json()["news"]],
            [news["id"]],
        )

        deleted = self.client.delete(
            f"/api/government/news/{news['id']}",
            json={"expected_version": news["version"]},
        )
        self.assertEqual(deleted.status_code, 200)
        self.assertTrue(deleted.get_json()["success"])
        self.assertEqual(
            self.client.get("/api/government/news").get_json()["news"],
            [],
        )

    def test_publish_api_is_idempotent(self):
        self.login_government()

        first = self.publish_news()
        second = self.publish_news()

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)
        self.assertEqual(
            first.get_json()["news"]["id"],
            second.get_json()["news"]["id"],
        )
        self.assertEqual(
            len(
                self.client.get(
                    "/api/government/news"
                ).get_json()["news"]
            ),
            1,
        )

    def test_non_government_role_is_rejected_for_all_news_actions(self):
        self.login_student()

        listed = self.client.get("/api/government/news")
        created = self.publish_news()
        deleted = self.client.delete(
            "/api/government/news/news-missing",
            json={"expected_version": 1},
        )

        for response in (listed, created, deleted):
            self.assertEqual(response.status_code, 403)
            self.assertFalse(response.get_json()["success"])

    def test_unpublish_and_relist_routes_are_not_registered(self):
        self.login_government()
        created = self.publish_news()
        news = created.get_json()["news"]
        paths = (
            f"/api/government/news/{news['id']}/unpublish",
            f"/api/government/news/{news['id']}/relist",
        )

        for path in paths:
            with self.subTest(path=path):
                self.assertEqual(self.client.post(path).status_code, 404)

        registered_rules = {
            str(rule)
            for rule in self.app.url_map.iter_rules()
            if str(rule).startswith("/api/government/news")
        }
        self.assertNotIn(
            "/api/government/news/<news_id>/unpublish",
            registered_rules,
        )
        self.assertNotIn(
            "/api/government/news/<news_id>/relist",
            registered_rules,
        )

    def test_news_errors_are_mapped_to_json_responses(self):
        self.login_government()

        invalid = self.publish_news(category_code="unknown")
        self.assertEqual(invalid.status_code, 400)
        self.assertFalse(invalid.get_json()["success"])

        invalid_filter = self.client.get(
            "/api/government/news?category=unknown"
        )
        self.assertEqual(invalid_filter.status_code, 400)
        self.assertFalse(invalid_filter.get_json()["success"])

        missing = self.client.delete(
            "/api/government/news/news-missing",
            json={"expected_version": 1},
        )
        self.assertEqual(missing.status_code, 404)
        self.assertFalse(missing.get_json()["success"])
