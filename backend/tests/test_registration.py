import hashlib
import tempfile
import unittest
from pathlib import Path

from app import create_app
from app.db import get_db
from werkzeug.security import check_password_hash


class TestRegistration(unittest.TestCase):
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

    def test_student_registration_creates_default_profile(self):
        response = self.client.post(
            "/api/auth/register",
            json={
                "role": "student",
                "username": "student01",
                "password": "password8",
                "confirm_password": "password8",
                "name": "林晓",
            },
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json()["next_step"], "interest-tags")
        with self.app.app_context():
            profile = get_db().execute(
                "SELECT learning_direction FROM student_profiles WHERE user_id = 1"
            ).fetchone()
            resume = get_db().execute(
                "SELECT user_id FROM resumes WHERE user_id = 1"
            ).fetchone()
        self.assertEqual(profile["learning_direction"], "comprehensive")
        self.assertEqual(resume["user_id"], 1)

    def test_registration_validation_errors_are_field_specific(self):
        cases = (
            ({"username": ""}, "username", "用户名不能为空"),
            ({"username": "1bad"}, "username", "用户名格式不正确"),
            ({"password": ""}, "password", "密码不能为空"),
            ({"password": "short"}, "password", "密码长度不能少于8位"),
            (
                {"confirm_password": "different8"},
                "confirm_password",
                "两次输入的密码不一致",
            ),
            ({"name": ""}, "name", "姓名不能为空"),
        )
        base = {
            "role": "student",
            "username": "student01",
            "password": "password8",
            "confirm_password": "password8",
            "name": "林晓",
        }
        for patch, field, message in cases:
            with self.subTest(field=field):
                response = self.client.post(
                    "/api/auth/register", json={**base, **patch}
                )
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.get_json()["errors"][field], message)

    def test_duplicate_username_is_rejected_for_any_role(self):
        first = {
            "role": "teacher",
            "username": "shared01",
            "password": "password8",
            "confirm_password": "password8",
            "name": "教师甲",
        }
        self.client.post("/api/auth/register", json=first)
        response = self.client.post(
            "/api/auth/register", json={**first, "role": "student", "name": "学员乙"}
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["errors"]["username"], "用户名已被占用")

    def test_other_roles_cannot_self_register(self):
        response = self.client.post(
            "/api/auth/register",
            json={
                "role": "enterprise",
                "username": "company01",
                "password": "password8",
                "confirm_password": "password8",
                "name": "企业甲",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.get_json()["errors"]["role"], "该角色不支持自助注册"
        )

    def test_teacher_registration_creates_active_session_and_cookie(self):
        response = self.client.post(
            "/api/auth/register",
            json={
                "role": "teacher",
                "username": "teacher01",
                "password": "password8",
                "confirm_password": "password8",
                "name": "陈老师",
            },
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json()["next_step"], "portal")
        raw_token = response.headers["Set-Cookie"].split("yx_session=", 1)[1].split(
            ";", 1
        )[0]
        with self.app.app_context():
            session = get_db().execute(
                "SELECT state, token_hash FROM sessions WHERE user_id = 1"
            ).fetchone()
        self.assertEqual(session["state"], "active")
        self.assertEqual(
            session["token_hash"], hashlib.sha256(raw_token.encode()).hexdigest()
        )
        self.assertNotEqual(session["token_hash"], raw_token)

    def test_student_registration_creates_pending_session(self):
        response = self.client.post(
            "/api/auth/register",
            json={
                "role": "student",
                "username": "student02",
                "password": "password8",
                "confirm_password": "password8",
                "name": "林晓",
            },
        )

        self.assertEqual(response.status_code, 201)
        with self.app.app_context():
            session = get_db().execute(
                "SELECT state FROM sessions WHERE user_id = 1"
            ).fetchone()
            user = get_db().execute(
                "SELECT username, name, password_hash FROM users WHERE id = 1"
            ).fetchone()
        self.assertEqual(session["state"], "pending")
        self.assertEqual(user["username"], "student02")
        self.assertEqual(user["name"], "林晓")
        self.assertNotEqual(user["password_hash"], "password8")

    def test_payload_values_are_trimmed_before_storage(self):
        response = self.client.post(
            "/api/auth/register",
            json={
                "role": "student",
                "username": "  student03  ",
                "password": " password8 ",
                "confirm_password": " password8 ",
                "name": "  林晓  ",
            },
        )

        self.assertEqual(response.status_code, 201)
        with self.app.app_context():
            user = get_db().execute(
                "SELECT username, name, password_hash FROM users WHERE id = 1"
            ).fetchone()
        self.assertEqual(user["username"], "student03")
        self.assertEqual(user["name"], "林晓")
        self.assertTrue(check_password_hash(user["password_hash"], " password8 "))
        self.assertFalse(check_password_hash(user["password_hash"], "password8"))

    def test_invalid_registration_does_not_create_an_account(self):
        response = self.client.post(
            "/api/auth/register",
            json={
                "role": "student",
                "username": "bad",
                "password": "short",
                "confirm_password": "different",
                "name": "",
            },
        )

        self.assertEqual(response.status_code, 400)
        with self.app.app_context():
            count = get_db().execute("SELECT COUNT(*) AS count FROM users").fetchone()[
                "count"
            ]
        self.assertEqual(count, 0)


if __name__ == "__main__":
    unittest.main()
