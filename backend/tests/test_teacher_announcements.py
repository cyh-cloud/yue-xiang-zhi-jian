import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from app import create_app
from app.db import get_db
from app.teacher_console.announcements import (
    list_teaching_announcements,
    publish_teaching_announcement,
    update_teaching_announcement,
)
from app.teacher_console.errors import (
    ProviderAccessDeniedError,
    ProviderConflictError,
)


class TestTeacherAnnouncements(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(Path(self.temp_dir.name) / "test.db"),
                "SECRET_KEY": "test-only-secret",
            }
        )
        self.context = self.app.app_context()
        self.context.push()
        self.teacher_id = self.create_user("teacher", "教师甲", "teacher")
        self.student_ids = {
            self.create_user("student-a", "学员甲", "student"),
            self.create_user("student-b", "学员乙", "student"),
        }
        self.create_user("enterprise", "企业用户", "enterprise")

    def tearDown(self):
        self.context.pop()
        self.temp_dir.cleanup()

    def create_user(self, username: str, name: str, role: str) -> int:
        now = datetime.now(timezone.utc).isoformat()
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

    def notifications(self) -> list:
        return get_db().execute(
            """
            SELECT recipient_id
            FROM system_notifications
            ORDER BY id
            """
        ).fetchall()

    def test_publish_sends_exactly_one_notification_per_student(self):
        announcement = publish_teaching_announcement(
            self.teacher_id, "课程安排", "本周课程调整"
        )
        self.assertEqual(
            {row["recipient_id"] for row in self.notifications()},
            self.student_ids,
        )
        self.assertEqual(announcement["delivery_status"], "sent")

    def test_publish_commits_pending_then_records_result_once(self):
        statuses_during_broadcast = []
        broadcast_result = {"created_count": 2, "unique_recipient_count": 2}

        def broadcast(**_kwargs):
            statuses_during_broadcast.append(
                get_db()
                .execute(
                    """
                    SELECT delivery_status
                    FROM teacher_announcements
                    """
                )
                .fetchone()["delivery_status"]
            )
            return broadcast_result

        with patch(
            "app.teacher_console.announcements.emit_teaching_announcement",
            side_effect=broadcast,
        ) as emit:
            announcement = publish_teaching_announcement(
                self.teacher_id, "课程安排", "本周课程调整"
            )

        emit.assert_called_once()
        self.assertEqual(statuses_during_broadcast, ["pending"])
        self.assertEqual(announcement["delivery_result"], broadcast_result)
        self.assertEqual(
            list_teaching_announcements(self.teacher_id),
            [announcement],
        )

    def test_published_announcement_is_immutable(self):
        announcement = publish_teaching_announcement(
            self.teacher_id, "标题", "正文"
        )
        with self.assertRaises(ProviderConflictError) as raised:
            update_teaching_announcement(
                self.teacher_id, announcement["announcement_id"], "新标题", "新正文"
            )
        self.assertEqual(str(raised.exception), "已群发公告不可修改")

    def test_broadcast_failure_is_recorded_and_not_reported_as_success(self):
        with patch(
            "app.teacher_console.announcements.emit_teaching_announcement",
            side_effect=RuntimeError("delivery failed"),
        ):
            with self.assertRaises(RuntimeError):
                publish_teaching_announcement(
                    self.teacher_id, "标题", "正文"
                )
        row = get_db().execute(
            "SELECT delivery_status FROM teacher_announcements"
        ).fetchone()
        events = get_db().execute(
            """
            SELECT status FROM teacher_announcement_delivery_events
            ORDER BY id
            """
        ).fetchall()
        self.assertEqual(row["delivery_status"], "failed")
        self.assertEqual([event["status"] for event in events], ["failed"])

    def test_publish_rejects_nonexistent_teacher_before_write_or_broadcast(self):
        with patch(
            "app.teacher_console.announcements.emit_teaching_announcement"
        ) as emit:
            with self.assertRaises(ProviderAccessDeniedError):
                publish_teaching_announcement(
                    999999, "课程安排", "本周课程调整"
                )

        emit.assert_not_called()
        self.assertEqual(
            get_db()
            .execute("SELECT COUNT(*) AS count FROM teacher_announcements")
            .fetchone()["count"],
            0,
        )
        self.assertEqual(
            get_db()
            .execute(
                """
                SELECT COUNT(*) AS count
                FROM teacher_announcement_delivery_events
                """
            )
            .fetchone()["count"],
            0,
        )

    def test_publish_rejects_non_teacher_before_write_or_broadcast(self):
        student_id = next(iter(self.student_ids))
        with patch(
            "app.teacher_console.announcements.emit_teaching_announcement"
        ) as emit:
            with self.assertRaises(ProviderAccessDeniedError):
                publish_teaching_announcement(
                    student_id, "课程安排", "本周课程调整"
                )

        emit.assert_not_called()
        self.assertEqual(
            get_db()
            .execute("SELECT COUNT(*) AS count FROM teacher_announcements")
            .fetchone()["count"],
            0,
        )
        self.assertEqual(
            get_db()
            .execute(
                """
                SELECT COUNT(*) AS count
                FROM teacher_announcement_delivery_events
                """
            )
            .fetchone()["count"],
            0,
        )


if __name__ == "__main__":
    unittest.main()
