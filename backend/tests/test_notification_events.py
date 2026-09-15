import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from app import create_app
from app.db import get_db
from app.messaging.events import (
    APPLICATION_STATUS,
    APPLICATION_SUBMITTED,
    FULFILLMENT_CANCELLED,
    FULFILLMENT_ISSUED,
    PASSWORD_RESET,
    POINTS_EXPIRED,
    POSITION_CLOSED,
    REDEMPTION_SUCCEEDED,
    REVIEW_APPROVED,
    REVIEW_REJECTED,
    emit_application_status_changed,
    emit_application_submitted,
    emit_fulfillment_cancelled,
    emit_fulfillment_issued,
    emit_password_reset,
    emit_points_expired,
    emit_position_closed,
    emit_redemption_succeeded,
    emit_review_result,
)
from app.messaging.notification_service import (
    NotificationValidationError,
    list_notifications,
)


class TestNotificationEvents(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(Path(self.temp_dir.name) / "test.db"),
                "SECRET_KEY": "test-only-secret",
            }
        )
        self.submitter_id = self.create_user("submitter", "提交者", "teacher")
        self.enterprise_id = self.create_user(
            "enterprise",
            "企业用户",
            "enterprise",
        )
        self.student_id = self.create_user("student", "学员甲", "student")
        self.other_student_id = self.create_user(
            "student-other",
            "学员乙",
            "student",
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
                VALUES (?, 'hash', ?, ?, 1, ?, ?)
                """,
                (username, name, role, now, now),
            )
            get_db().commit()
        return int(cursor.lastrowid)

    def test_review_approval_notifies_submitter_once(self):
        with self.app.app_context():
            approval = emit_review_result(
                event_id="submission-42",
                submitter_id=self.submitter_id,
                content_type="course_video",
                content_id="video-8",
                approved=True,
            )
            retry = emit_review_result(
                event_id="submission-42",
                submitter_id=self.submitter_id,
                content_type="course_video",
                content_id="video-8",
                approved=True,
            )
            submitter_notifications = list_notifications(self.submitter_id)
            other_notifications = list_notifications(self.enterprise_id)

        self.assertEqual(approval["id"], retry["id"])
        self.assertEqual(approval["event_type"], REVIEW_APPROVED)
        self.assertEqual(approval["source_type"], "course_video")
        self.assertEqual(approval["source_id"], "video-8")
        self.assertIn(
            "已通过并上架",
            approval["title"] + approval["body"],
        )
        self.assertEqual(len(submitter_notifications), 1)
        self.assertEqual(other_notifications, [])

    def test_review_rejection_includes_opinion_and_requires_it(self):
        with self.app.app_context():
            rejection = emit_review_result(
                event_id="submission-43",
                submitter_id=self.submitter_id,
                content_type="intangible_heritage_video",
                content_id="heritage-3",
                approved=False,
                opinion="画面清晰",
            )
            retry = emit_review_result(
                event_id="submission-43",
                submitter_id=self.submitter_id,
                content_type="intangible_heritage_video",
                content_id="heritage-3",
                approved=False,
                opinion="画面清晰",
            )
            with self.assertRaises(NotificationValidationError):
                emit_review_result(
                    event_id="submission-44",
                    submitter_id=self.submitter_id,
                    content_type="intangible_heritage_video",
                    content_id="heritage-4",
                    approved=False,
                    opinion="  ",
                )
            notifications = list_notifications(self.submitter_id)

        self.assertEqual(rejection["id"], retry["id"])
        self.assertEqual(rejection["event_type"], REVIEW_REJECTED)
        self.assertEqual(
            rejection["source_type"],
            "intangible_heritage_video",
        )
        self.assertEqual(rejection["source_id"], "heritage-3")
        self.assertIn(
            "审核意见：画面清晰",
            rejection["title"] + rejection["body"],
        )
        self.assertEqual(len(notifications), 1)

    def test_application_submission_notifies_enterprise_once(self):
        with self.app.app_context():
            enterprise_notice = emit_application_submitted(
                event_id="application-7",
                enterprise_id=self.enterprise_id,
                student_id=self.student_id,
                application_id="application-7",
                student_name="张同学",
                job_title="农业技术员",
            )
            retry = emit_application_submitted(
                event_id="application-7",
                enterprise_id=self.enterprise_id,
                student_id=self.student_id,
                application_id="application-7",
                student_name="张同学",
                job_title="农业技术员",
            )
            enterprise_notifications = list_notifications(
                self.enterprise_id
            )
            student_notifications = list_notifications(self.student_id)

        self.assertEqual(enterprise_notice["id"], retry["id"])
        self.assertEqual(
            enterprise_notice["event_type"],
            APPLICATION_SUBMITTED,
        )
        self.assertEqual(enterprise_notice["source_type"], "application")
        self.assertEqual(enterprise_notice["source_id"], "application-7")
        self.assertIn(
            "张同学",
            enterprise_notice["title"] + enterprise_notice["body"],
        )
        self.assertIn(
            "农业技术员",
            enterprise_notice["title"] + enterprise_notice["body"],
        )
        self.assertEqual(len(enterprise_notifications), 1)
        self.assertEqual(student_notifications, [])

    def test_application_status_change_notifies_student_once(self):
        with self.app.app_context():
            status_notice = emit_application_status_changed(
                event_id="status-7",
                student_id=self.student_id,
                application_id="application-7",
                status="意向沟通",
            )
            retry = emit_application_status_changed(
                event_id="status-7",
                student_id=self.student_id,
                application_id="application-7",
                status="意向沟通",
            )
            student_notifications = list_notifications(self.student_id)
            enterprise_notifications = list_notifications(
                self.enterprise_id
            )

        self.assertEqual(status_notice["id"], retry["id"])
        self.assertEqual(
            status_notice["event_type"],
            APPLICATION_STATUS,
        )
        self.assertEqual(status_notice["source_type"], "application")
        self.assertEqual(status_notice["source_id"], "application-7")
        self.assertIn(
            "意向沟通",
            status_notice["title"] + status_notice["body"],
        )
        self.assertEqual(len(student_notifications), 1)
        self.assertEqual(enterprise_notifications, [])

    def test_position_closure_notifies_every_affected_student_once(self):
        with self.app.app_context():
            result = emit_position_closed(
                event_id="position-9",
                student_ids=[self.student_id, self.other_student_id],
                position_id="position-9",
                job_title="农业技术员",
            )
            retry = emit_position_closed(
                event_id="position-9",
                student_ids=[self.student_id, self.other_student_id],
                position_id="position-9",
                job_title="农业技术员",
            )
            first_notifications = list_notifications(self.student_id)
            second_notifications = list_notifications(
                self.other_student_id
            )
            enterprise_notifications = list_notifications(
                self.enterprise_id
            )

        self.assertEqual(result["unique_recipient_count"], 2)
        self.assertEqual(
            [item["id"] for item in result["notifications"]],
            [item["id"] for item in retry["notifications"]],
        )
        self.assertEqual(len(first_notifications), 1)
        self.assertEqual(len(second_notifications), 1)
        self.assertEqual(enterprise_notifications, [])
        for notice in first_notifications + second_notifications:
            self.assertEqual(notice["event_type"], POSITION_CLOSED)
            self.assertEqual(notice["source_type"], "job_position")
            self.assertEqual(notice["source_id"], "position-9")
            self.assertIn(
                "岗位已关闭",
                notice["title"] + notice["body"],
            )

    def test_redemption_success_notifies_student_once(self):
        with self.app.app_context():
            redemption = emit_redemption_succeeded(
                event_id="redemption-11",
                student_id=self.student_id,
                redemption_id="redemption-11",
                points_spent=120,
                prize_name="保温杯",
            )
            retry = emit_redemption_succeeded(
                event_id="redemption-11",
                student_id=self.student_id,
                redemption_id="redemption-11",
                points_spent=120,
                prize_name="保温杯",
            )
            notifications = list_notifications(self.student_id)

        self.assertEqual(redemption["id"], retry["id"])
        self.assertEqual(
            redemption["event_type"],
            REDEMPTION_SUCCEEDED,
        )
        self.assertEqual(redemption["source_type"], "redemption")
        self.assertEqual(redemption["source_id"], "redemption-11")
        self.assertIn(
            "120积分",
            redemption["title"] + redemption["body"],
        )
        self.assertIn(
            "保温杯",
            redemption["title"] + redemption["body"],
        )
        self.assertEqual(len(notifications), 1)

    def test_fulfillment_issued_notifies_student_once(self):
        with self.app.app_context():
            issued = emit_fulfillment_issued(
                event_id="fulfillment-12",
                student_id=self.student_id,
                fulfillment_id="fulfillment-12",
                prize_name="保温杯",
            )
            retry = emit_fulfillment_issued(
                event_id="fulfillment-12",
                student_id=self.student_id,
                fulfillment_id="fulfillment-12",
                prize_name="保温杯",
            )
            notifications = list_notifications(self.student_id)

        self.assertEqual(issued["id"], retry["id"])
        self.assertEqual(issued["event_type"], FULFILLMENT_ISSUED)
        self.assertEqual(issued["source_type"], "fulfillment")
        self.assertEqual(issued["source_id"], "fulfillment-12")
        self.assertIn("保温杯", issued["title"] + issued["body"])
        self.assertIn("已发放", issued["title"] + issued["body"])
        self.assertEqual(len(notifications), 1)

    def test_fulfillment_cancellation_includes_restored_points_once(self):
        with self.app.app_context():
            cancellation = emit_fulfillment_cancelled(
                event_id="fulfillment-13",
                student_id=self.student_id,
                fulfillment_id="fulfillment-13",
                prize_name="保温杯",
                restored_points=30,
            )
            retry = emit_fulfillment_cancelled(
                event_id="fulfillment-13",
                student_id=self.student_id,
                fulfillment_id="fulfillment-13",
                prize_name="保温杯",
                restored_points=30,
            )
            notifications = list_notifications(self.student_id)

        self.assertEqual(cancellation["id"], retry["id"])
        self.assertEqual(
            cancellation["event_type"],
            FULFILLMENT_CANCELLED,
        )
        self.assertEqual(cancellation["source_type"], "fulfillment")
        self.assertEqual(cancellation["source_id"], "fulfillment-13")
        self.assertIn(
            "积分已回退",
            cancellation["title"] + cancellation["body"],
        )
        self.assertIn(
            "30积分",
            cancellation["title"] + cancellation["body"],
        )
        self.assertIn(
            "保温杯",
            cancellation["title"] + cancellation["body"],
        )
        self.assertEqual(len(notifications), 1)

    def test_points_expiration_includes_cleared_amount_once(self):
        with self.app.app_context():
            expiration = emit_points_expired(
                event_id="expiration-14",
                student_id=self.student_id,
                points_cleared=30,
            )
            retry = emit_points_expired(
                event_id="expiration-14",
                student_id=self.student_id,
                points_cleared=30,
            )
            notifications = list_notifications(self.student_id)

        self.assertEqual(expiration["id"], retry["id"])
        self.assertEqual(expiration["event_type"], POINTS_EXPIRED)
        self.assertIsNone(expiration["source_type"])
        self.assertIsNone(expiration["source_id"])
        self.assertIn(
            "30积分清零",
            expiration["title"] + expiration["body"],
        )
        self.assertEqual(len(notifications), 1)

    def test_password_reset_notifies_user_without_changing_credentials(self):
        with self.app.app_context():
            before = get_db().execute(
                "SELECT password_hash FROM users WHERE id = ?",
                (self.student_id,),
            ).fetchone()["password_hash"]
            reset = emit_password_reset(
                event_id="reset-15",
                user_id=self.student_id,
            )
            retry = emit_password_reset(
                event_id="reset-15",
                user_id=self.student_id,
            )
            after = get_db().execute(
                "SELECT password_hash FROM users WHERE id = ?",
                (self.student_id,),
            ).fetchone()["password_hash"]
            notifications = list_notifications(self.student_id)

        self.assertEqual(reset["id"], retry["id"])
        self.assertEqual(reset["event_type"], PASSWORD_RESET)
        self.assertIsNone(reset["source_type"])
        self.assertIsNone(reset["source_id"])
        self.assertEqual(reset["title"], "密码已重置")
        self.assertEqual(reset["body"], "请联系管理员获取初始密码")
        self.assertEqual(before, after)
        self.assertEqual(len(notifications), 1)


if __name__ == "__main__":
    unittest.main()
