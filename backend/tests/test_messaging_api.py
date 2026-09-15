import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from werkzeug.security import generate_password_hash

from app import create_app
from app.db import get_db
from app.messaging.notification_service import emit_notification


class TestMessagingApi(unittest.TestCase):
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

        self.teacher_id = self.create_user("teacher", "教师甲", "teacher")
        self.student_id = self.create_user("student", "学员甲", "student")
        self.other_student_id = self.create_user(
            "student-other",
            "学员乙",
            "student",
        )
        self.admin_id = self.create_user("admin", "管理员", "admin")

        self.teacher_client = self.login("teacher")
        self.student_client = self.login("student")
        self.other_student_client = self.login("student-other")
        self.admin_client = self.login("admin")

    def tearDown(self):
        self.temp_dir.cleanup()

    def create_user(self, username: str, name: str, role: str) -> int:
        now = datetime.now(timezone.utc).isoformat()
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
                    name,
                    role,
                    now,
                    now,
                ),
            )
            get_db().commit()
        return int(cursor.lastrowid)

    def login(self, username: str):
        client = self.app.test_client()
        response = client.post(
            "/api/auth/login",
            json={"username": username, "password": "password8"},
        )
        self.assertEqual(response.status_code, 200)
        return client

    def emit_notification(self) -> int:
        with self.app.app_context():
            notification = emit_notification(
                recipient_id=self.student_id,
                event_key="api:test-event",
                event_type="test",
                title="测试通知",
                body="通知正文",
            )
        return notification["id"]

    def send_message(self, client=None) -> dict:
        response = (client or self.teacher_client).post(
            "/api/messages/conversations",
            json={"recipient_id": self.student_id, "body": "老师您好"},
        )
        self.assertEqual(response.status_code, 201)
        return response.get_json()

    def test_contact_and_conversation_flow(self):
        summary = self.student_client.get("/api/messages/summary")
        contacts = self.student_client.get("/api/messages/contacts")
        conversations = self.student_client.get("/api/messages/conversations")
        notifications = self.student_client.get("/api/messages/notifications")

        self.assertEqual(summary.status_code, 200)
        self.assertEqual(
            summary.get_json(),
            {
                "success": True,
                "unread_private": 0,
                "unread_notifications": 0,
                "unread_total": 0,
            },
        )
        self.assertEqual(contacts.status_code, 200)
        self.assertEqual(contacts.get_json()["contacts"][0]["role"], "teacher")
        self.assertEqual(
            conversations.get_json(),
            {"success": True, "conversations": []},
        )
        self.assertEqual(
            notifications.get_json(),
            {"success": True, "notifications": []},
        )

        sent = self.teacher_client.post(
            "/api/messages/conversations",
            json={"recipient_id": self.student_id, "body": "老师您好"},
        )
        self.assertEqual(sent.status_code, 201)
        sent_record = sent.get_json()
        conversation_id = sent_record["conversation"]["id"]
        self.assertEqual(
            sent_record["conversation"]["participant"]["id"],
            self.student_id,
        )
        self.assertEqual(sent_record["message"]["body"], "老师您好")

        thread = self.student_client.get(
            f"/api/messages/conversations/{conversation_id}"
        )
        self.assertEqual(thread.status_code, 200)
        self.assertEqual(
            thread.get_json()["messages"][0]["body"],
            "老师您好",
        )

        reply = self.student_client.post(
            f"/api/messages/conversations/{conversation_id}/messages",
            json={"body": "你好"},
        )
        self.assertEqual(reply.status_code, 201)
        self.assertEqual(reply.get_json()["message"]["body"], "你好")

    def test_admin_can_read_notifications_but_cannot_send_private_messages(self):
        self.assertEqual(
            self.admin_client.get("/api/messages/notifications").status_code,
            200,
        )
        denied = self.admin_client.post(
            "/api/messages/conversations",
            json={"recipient_id": self.student_id, "body": "不允许"},
        )
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(
            denied.get_json(),
            {
                "success": False,
                "message": "当前角色或关系不允许此私信",
            },
        )

    def test_invalid_message_body_returns_validation_errors(self):
        responses = [
            self.teacher_client.post(
                "/api/messages/conversations",
                json={"recipient_id": self.student_id, "body": " \n\t "},
            ),
            self.teacher_client.post(
                "/api/messages/conversations",
                data="not-json",
                content_type="application/json",
            ),
        ]

        for response in responses:
            with self.subTest(response=response):
                self.assertEqual(response.status_code, 400)
                self.assertEqual(
                    response.get_json(),
                {
                    "success": False,
                    "errors": {"body": "消息内容不能为空"},
                },
            )

    def test_invalid_recipient_id_returns_validation_errors(self):
        cases = [[], True, False, 1.5, 0, -1]

        for recipient_id in cases:
            with self.subTest(recipient_id=recipient_id):
                response = self.teacher_client.post(
                    "/api/messages/conversations",
                    json={"recipient_id": recipient_id, "body": "消息"},
                )
                self.assertEqual(response.status_code, 400)
                self.assertEqual(
                    response.get_json(),
                    {
                        "success": False,
                        "errors": {"recipient_id": "接收人必须是正整数"},
                    },
                )

    def test_all_routes_require_an_active_session(self):
        cases = [
            ("get", "/api/messages/summary", None),
            ("get", "/api/messages/contacts", None),
            ("get", "/api/messages/conversations", None),
            (
                "post",
                "/api/messages/conversations",
                {"recipient_id": self.student_id, "body": "消息"},
            ),
            ("get", "/api/messages/conversations/1", None),
            (
                "post",
                "/api/messages/conversations/1/messages",
                {"body": "回复"},
            ),
            ("get", "/api/messages/notifications", None),
            ("post", "/api/messages/private/1/read", None),
            ("post", "/api/messages/notifications/1/read", None),
            ("post", "/api/messages/read-all", None),
            ("post", "/api/messages/clear-read", None),
        ]
        client = self.app.test_client()

        for method, path, payload in cases:
            with self.subTest(method=method, path=path):
                response = getattr(client, method)(path, json=payload)
                self.assertEqual(response.status_code, 401)
                self.assertEqual(
                    response.get_json()["message"],
                    "未登录或会话已过期",
                )

    def test_foreign_or_missing_conversations_return_404(self):
        sent = self.send_message()
        conversation_id = sent["conversation"]["id"]

        responses = [
            self.other_student_client.get(
                f"/api/messages/conversations/{conversation_id}"
            ),
            self.other_student_client.get(
                "/api/messages/conversations/9999"
            ),
            self.other_student_client.post(
                f"/api/messages/conversations/{conversation_id}/messages",
                json={"body": "越权回复"},
            ),
            self.other_student_client.post(
                "/api/messages/conversations/9999/messages",
                json={"body": "不存在"},
            ),
        ]

        for response in responses:
            with self.subTest(response=response):
                self.assertEqual(response.status_code, 404)
                self.assertEqual(
                    response.get_json(),
                    {"success": False, "message": "会话不存在"},
                )

    def test_foreign_or_missing_read_records_return_404(self):
        sent = self.send_message()
        message_id = sent["message"]["id"]
        notification_id = self.emit_notification()

        responses = [
            self.other_student_client.post(
                f"/api/messages/private/{message_id}/read"
            ),
            self.other_student_client.post("/api/messages/private/9999/read"),
            self.other_student_client.post(
                f"/api/messages/notifications/{notification_id}/read"
            ),
            self.other_student_client.post(
                "/api/messages/notifications/9999/read"
            ),
        ]

        for response in responses:
            with self.subTest(response=response):
                self.assertEqual(response.status_code, 404)
                self.assertEqual(
                    response.get_json(),
                    {"success": False, "message": "消息不存在"},
                )

    def test_read_actions_return_updated_summaries(self):
        sent = self.send_message()
        message_id = sent["message"]["id"]
        notification_id = self.emit_notification()

        private_read = self.student_client.post(
            f"/api/messages/private/{message_id}/read"
        )
        self.assertEqual(private_read.status_code, 200)
        self.assertEqual(
            private_read.get_json(),
            {
                "success": True,
                "unread_private": 0,
                "unread_notifications": 1,
                "unread_total": 1,
            },
        )

        notification_read = self.student_client.post(
            f"/api/messages/notifications/{notification_id}/read"
        )
        self.assertEqual(notification_read.status_code, 200)
        self.assertEqual(notification_read.get_json()["unread_total"], 0)

        second = self.send_message()
        self.assertEqual(second["conversation"]["id"], sent["conversation"]["id"])
        mark_all_read = self.student_client.post("/api/messages/read-all")
        self.assertEqual(mark_all_read.status_code, 200)
        self.assertEqual(mark_all_read.get_json()["unread_total"], 0)

        clear_read = self.student_client.post("/api/messages/clear-read")
        self.assertEqual(clear_read.status_code, 200)
        self.assertEqual(
            clear_read.get_json(),
            {
                "success": True,
                "cleared_private": 2,
                "cleared_notifications": 1,
                "unread_total": 0,
            },
        )


if __name__ == "__main__":
    unittest.main()
