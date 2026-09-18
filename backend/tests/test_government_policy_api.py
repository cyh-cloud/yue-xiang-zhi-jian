import tempfile
from pathlib import Path
from unittest import TestCase

from werkzeug.security import generate_password_hash

from app import create_app
from app.db import get_db


class GovernmentPolicyApiTests(TestCase):
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

    def publish_policy(self, **overrides):
        payload = {
            "request_id": "api-policy-1",
            "title": "创业补贴",
            "content": "政策正文",
            "category_code": "entrepreneurship",
        }
        payload.update(overrides)
        return self.client.post("/api/government/policies", json=payload)

    def test_government_can_publish_list_unpublish_relist_and_delete(self):
        self.login_government()
        created = self.publish_policy()
        self.assertEqual(created.status_code, 201)
        policy = created.get_json()["policy"]
        self.assertEqual(policy["category_label"], "创业支持")
        self.assertEqual(policy["status"], "active")

        listed = self.client.get(
            "/api/government/policies?status=active&category=entrepreneurship"
        )
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(len(listed.get_json()["policies"]), 1)

        unpublished = self.client.post(
            f"/api/government/policies/{policy['id']}/unpublish",
            json={"expected_version": policy["version"]},
        )
        self.assertEqual(unpublished.status_code, 200)
        unpublished_policy = unpublished.get_json()["policy"]
        self.assertEqual(unpublished_policy["status"], "unpublished")

        relisted = self.client.post(
            f"/api/government/policies/{policy['id']}/relist",
            json={"expected_version": unpublished_policy["version"]},
        )
        self.assertEqual(relisted.status_code, 200)
        relisted_policy = relisted.get_json()["policy"]
        self.assertEqual(relisted_policy["status"], "active")

        deleted = self.client.delete(
            f"/api/government/policies/{policy['id']}",
            json={"expected_version": relisted_policy["version"]},
        )
        self.assertEqual(deleted.status_code, 200)
        self.assertTrue(deleted.get_json()["success"])
        self.assertEqual(
            self.client.get("/api/government/policies").get_json()["policies"],
            [],
        )

    def test_non_government_role_is_rejected(self):
        self.login_student()
        response = self.client.get("/api/government/policies")
        self.assertEqual(response.status_code, 403)
        self.assertFalse(response.get_json()["success"])

    def test_stale_publish_request_after_delete_is_a_provider_error(self):
        self.login_government()
        created = self.publish_policy()
        policy = created.get_json()["policy"]
        deleted = self.client.delete(
            f"/api/government/policies/{policy['id']}",
            json={"expected_version": policy["version"]},
        )
        self.assertEqual(deleted.status_code, 200)

        retried = self.publish_policy()

        self.assertEqual(retried.status_code, 409)
        self.assertFalse(retried.get_json()["success"])
        self.assertNotIn("policy", retried.get_json())

    def test_policy_errors_are_mapped_to_json_responses(self):
        self.login_government()

        invalid_filter = self.client.get(
            "/api/government/policies?status=deleted"
        )
        self.assertEqual(invalid_filter.status_code, 400)
        self.assertFalse(invalid_filter.get_json()["success"])

        missing = self.client.delete(
            "/api/government/policies/policy-missing",
            json={"expected_version": 1},
        )
        self.assertEqual(missing.status_code, 404)
        self.assertFalse(missing.get_json()["success"])
