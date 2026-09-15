import tempfile
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path

from werkzeug.security import generate_password_hash

from app import create_app
from app.db import get_db
from app.messaging.broadcasts import (
    emit_monthly_agriculture_reminder,
    emit_policy_published,
    emit_teaching_announcement,
)
from app.messaging.events import (
    emit_application_status_changed,
    emit_application_submitted,
    emit_fulfillment_issued,
    emit_review_result,
)
from app.messaging.notification_service import (
    emit_notification,
    list_notifications,
)
from app.messaging.service import (
    MessagingAccessDeniedError,
    clear_read_items,
    get_conversation_messages,
    get_message_summary,
    list_conversations,
    mark_notification_read,
    mark_private_message_read,
    reply_to_conversation,
    send_private_message,
)
from app.messaging.source_provider import (
    NullMessagingSourceProvider,
    set_messaging_source_provider,
)


class IntegrationSourceProvider(NullMessagingSourceProvider):
    def __init__(self, applications, product_subscribers, policy_subscribers):
        self.applications = set(applications)
        self.product_subscribers = product_subscribers
        self.policy_subscribers = policy_subscribers

    def has_application_relationship(
        self, student_id: int, enterprise_id: int
    ) -> bool:
        return (student_id, enterprise_id) in self.applications

    def list_applied_enterprise_ids(self, student_id: int) -> list[int]:
        return sorted(
            enterprise_id
            for current_student, enterprise_id in self.applications
            if current_student == student_id
        )

    def list_applicant_student_ids(self, enterprise_id: int) -> list[int]:
        return sorted(
            student_id
            for student_id, current_enterprise in self.applications
            if current_enterprise == enterprise_id
        )

    def list_policy_subscriber_ids(self, category: str) -> list[int]:
        return list(self.policy_subscribers.get(category, set()))

    def list_product_subscriber_ids(self, product_key: str) -> list[int]:
        return list(self.product_subscribers.get(product_key, set()))


class TestMessagingIntegration(unittest.TestCase):
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
        self.enterprise_id = self.create_user(
            "enterprise",
            "企业甲",
            "enterprise",
        )
        self.other_enterprise_id = self.create_user(
            "enterprise-other",
            "企业乙",
            "enterprise",
        )
        self.admin_id = self.create_user("admin", "管理员", "admin")

        set_messaging_source_provider(
            self.app,
            IntegrationSourceProvider(
                applications={(self.student_id, self.enterprise_id)},
                product_subscribers={"荔枝": {self.student_id}},
                policy_subscribers={"创业支持": {self.student_id}},
            ),
        )

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

    def notification_ids(self, user_id: int) -> set[int]:
        with self.app.app_context():
            return {
                notification["id"]
                for notification in list_notifications(user_id)
            }

    def test_cross_service_message_and_notification_flow(self):
        teacher_client = self.login("teacher")
        teacher_other_client = self.login("teacher")
        student_client = self.login("student")
        enterprise_client = self.login("enterprise")
        other_enterprise_client = self.login("enterprise-other")

        sent_response = teacher_client.post(
            "/api/messages/conversations",
            json={"recipient_id": self.student_id, "body": "请提交材料"},
        )
        self.assertEqual(sent_response.status_code, 201)
        sent = sent_response.get_json()
        conversation_id = sent["conversation"]["id"]
        self.assertEqual(sent["message"]["body"], "请提交材料")
        self.assertEqual(
            student_client.get("/api/messages/summary").get_json(),
            {
                "success": True,
                "unread_private": 1,
                "unread_notifications": 0,
                "unread_total": 1,
            },
        )

        reply_response = student_client.post(
            f"/api/messages/conversations/{conversation_id}/messages",
            json={"body": "已提交"},
        )
        self.assertEqual(reply_response.status_code, 201)
        reply_id = reply_response.get_json()["message"]["id"]

        read_response = teacher_client.post(
            f"/api/messages/private/{reply_id}/read"
        )
        self.assertEqual(read_response.status_code, 200)
        self.assertEqual(read_response.get_json()["unread_private"], 0)
        second_client_thread = teacher_other_client.get(
            f"/api/messages/conversations/{conversation_id}"
        )
        self.assertEqual(second_client_thread.status_code, 200)
        self.assertTrue(
            next(
                message
                for message in second_client_thread.get_json()["messages"]
                if message["id"] == reply_id
            )["read"]
        )

        enterprise_sent = enterprise_client.post(
            "/api/messages/conversations",
            json={"recipient_id": self.student_id, "body": "安排沟通"},
        )
        self.assertEqual(enterprise_sent.status_code, 201)
        enterprise_conversation_id = enterprise_sent.get_json()["conversation"][
            "id"
        ]
        student_reply = student_client.post(
            f"/api/messages/conversations/{enterprise_conversation_id}/messages",
            json={"body": "可以"},
        )
        self.assertEqual(student_reply.status_code, 201)

        prohibited = other_enterprise_client.post(
            "/api/messages/conversations",
            json={"recipient_id": self.other_student_id, "body": "不应送达"},
        )
        self.assertEqual(prohibited.status_code, 403)
        self.assertEqual(
            prohibited.get_json()["message"],
            "当前角色或关系不允许此私信",
        )
        self.assertEqual(
            other_enterprise_client.get("/api/messages/contacts").get_json()[
                "contacts"
            ],
            [],
        )

        with self.app.app_context():
            review = emit_review_result(
                event_id="review-1",
                submitter_id=self.teacher_id,
                content_type="course_video",
                content_id="video-1",
                approved=True,
            )
            application = emit_application_submitted(
                event_id="application-1",
                enterprise_id=self.enterprise_id,
                student_id=self.student_id,
                application_id="application-1",
                student_name="学员甲",
                job_title="农业技术员",
            )
            status = emit_application_status_changed(
                event_id="status-1",
                student_id=self.student_id,
                application_id="application-1",
                status="意向沟通",
            )
            fulfillment = emit_fulfillment_issued(
                event_id="fulfillment-1",
                student_id=self.student_id,
                fulfillment_id="fulfillment-1",
                prize_name="保温杯",
            )
            teaching = emit_teaching_announcement(
                event_id="teaching-1",
                teacher_id=self.teacher_id,
                announcement_id="announcement-1",
                title="课程安排",
                body="本周课程调整",
            )
            policy = emit_policy_published(
                event_id="policy-1",
                policy_id="policy-1",
                title="创业补贴",
                category="创业支持",
            )
            agriculture = emit_monthly_agriculture_reminder(
                event_id="agriculture-1",
                product_key="荔枝",
                month="2026-09",
                body="及时开展秋梢管理",
            )

        self.assertEqual(
            self.notification_ids(self.teacher_id),
            {review["id"]},
        )
        self.assertEqual(
            self.notification_ids(self.enterprise_id),
            {application["id"]},
        )
        self.assertEqual(
            self.notification_ids(self.student_id),
            {
                status["id"],
                fulfillment["id"],
                teaching["notifications"][0]["id"],
                policy["notifications"][0]["id"],
                agriculture["notifications"][0]["id"],
            },
        )
        self.assertEqual(
            self.notification_ids(self.other_student_id),
            {teaching["notifications"][1]["id"]},
        )
        self.assertEqual(
            self.notification_ids(self.other_enterprise_id),
            set(),
        )
        self.assertEqual(self.notification_ids(self.admin_id), set())

        with self.app.app_context():
            first_delivery = emit_notification(
                recipient_id=self.student_id,
                event_key="latency:event-1",
                event_type="latency",
                title="测试通知",
                body="立即可见",
            )
            repeated_delivery = emit_notification(
                recipient_id=self.student_id,
                event_key="latency:event-1",
                event_type="latency",
                title="测试通知",
                body="立即可见",
            )
            summary = get_message_summary(self.student_id)
            conversations = list_conversations(self.student_id)
            visible_notifications = list_notifications(self.student_id)

        self.assertEqual(first_delivery["id"], repeated_delivery["id"])
        self.assertEqual(
            len(
                [
                    notification
                    for notification in visible_notifications
                    if notification["event_type"] == "latency"
                ]
            ),
            1,
        )
        self.assertEqual(
            summary["unread_total"],
            summary["unread_private"] + summary["unread_notifications"],
        )
        self.assertEqual(len(conversations), 2)

        with self.app.app_context():
            read_message_id = send_private_message(
                self.teacher_id,
                self.student_id,
                "已读后清除",
            )["message"]["id"]
            unread_message_id = send_private_message(
                self.teacher_id,
                self.student_id,
                "保留未读",
            )["message"]["id"]
            mark_private_message_read(self.student_id, read_message_id)
            read_notification_id = emit_notification(
                recipient_id=self.student_id,
                event_key="clear:read",
                event_type="clear",
                title="已读通知",
                body="可清除",
            )["id"]
            unread_notification_id = emit_notification(
                recipient_id=self.student_id,
                event_key="clear:unread",
                event_type="clear",
                title="未读通知",
                body="应保留",
            )["id"]
            mark_private_message_read(self.student_id, read_message_id)
            mark_notification_read(self.student_id, read_notification_id)
            cleared = clear_read_items(self.student_id)
            thread = get_conversation_messages(
                self.student_id,
                sent["conversation"]["id"],
            )
            remaining_notifications = list_notifications(self.student_id)
            final_summary = get_message_summary(self.student_id)

        visible_message_ids = {
            message["id"] for message in thread["messages"]
        }
        self.assertNotIn(read_message_id, visible_message_ids)
        self.assertIn(unread_message_id, visible_message_ids)
        self.assertEqual(
            {notification["id"] for notification in remaining_notifications},
            {
                unread_notification_id,
                status["id"],
                fulfillment["id"],
                teaching["notifications"][0]["id"],
                policy["notifications"][0]["id"],
                agriculture["notifications"][0]["id"],
                first_delivery["id"],
            },
        )
        self.assertGreaterEqual(cleared["cleared_private"], 1)
        self.assertEqual(cleared["cleared_notifications"], 1)
        self.assertEqual(
            final_summary["unread_total"],
            final_summary["unread_private"]
            + final_summary["unread_notifications"],
        )

    def test_prohibited_service_call_creates_no_conversation(self):
        with self.app.app_context():
            with self.assertRaises(MessagingAccessDeniedError):
                send_private_message(
                    self.other_enterprise_id,
                    self.other_student_id,
                    "不应建立会话",
                )
            count = get_db().execute(
                "SELECT COUNT(*) AS count FROM message_conversations"
            ).fetchone()["count"]

        self.assertEqual(count, 0)

    def test_notification_is_visible_within_30_seconds(self):
        started = time.monotonic()
        with self.app.app_context():
            emit_notification(
                recipient_id=self.student_id,
                event_key="latency:event-1",
                event_type="latency",
                title="测试通知",
                body="立即可见",
            )
            notifications = list_notifications(self.student_id)
        self.assertEqual(len(notifications), 1)
        self.assertLess(time.monotonic() - started, 30)

    def test_100_mixed_actions_keep_unread_count_exact(self):
        with self.app.app_context():
            for index in range(100):
                sent = send_private_message(
                    self.teacher_id,
                    self.student_id,
                    f"消息{index}",
                )
                if index % 2 == 0:
                    mark_private_message_read(
                        self.student_id,
                        sent["message"]["id"],
                    )
            expected = 50
            self.assertEqual(
                get_message_summary(self.student_id)["unread_private"],
                expected,
            )


if __name__ == "__main__":
    unittest.main()
