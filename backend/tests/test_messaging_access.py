import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from app import create_app
from app.db import get_db
from app.messaging.relationships import (
    application_relationship_exists,
    list_allowed_contacts,
    messaging_relationship,
)
from app.messaging.source_provider import set_messaging_source_provider


class FakeMessagingSourceProvider:
    def __init__(self):
        self.applications: set[tuple[int, int]] = set()

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
        return []

    def list_product_subscriber_ids(self, product_key: str) -> list[int]:
        return []


class TestMessagingRelationships(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(Path(self.temp_dir.name) / "test.db"),
                "SECRET_KEY": "test-only-secret",
            }
        )

        self.teacher_a = self.create_user("teacher-a", "教师甲", "teacher")
        self.teacher_b = self.create_user("teacher-b", "教师乙", "teacher")
        self.student_a = self.create_user("student-a", "学员甲", "student")
        self.student_b = self.create_user("student-b", "学员乙", "student")
        self.enterprise_with_application = self.create_user(
            "enterprise-applied",
            "已申请企业",
            "enterprise",
        )
        self.enterprise_without_application = self.create_user(
            "enterprise-unapplied",
            "未申请企业",
            "enterprise",
        )
        self.admin_user = self.create_user("admin", "管理员", "admin")
        self.government_user = self.create_user(
            "government",
            "政府用户",
            "government",
        )

        self.source_provider = FakeMessagingSourceProvider()
        self.source_provider.applications.add(
            (self.student_a, self.enterprise_with_application)
        )
        set_messaging_source_provider(self.app, self.source_provider)

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

    def test_application_relationship_is_exposed_through_source_provider(self):
        with self.app.app_context():
            self.assertTrue(
                application_relationship_exists(
                    self.student_a,
                    self.enterprise_with_application,
                )
            )
            self.assertFalse(
                application_relationship_exists(
                    self.student_a,
                    self.enterprise_without_application,
                )
            )

    def test_student_enterprise_requires_an_application(self):
        with self.app.app_context():
            self.assertEqual(
                messaging_relationship(
                    self.student_a,
                    self.enterprise_with_application,
                ),
                "application",
            )
            self.assertEqual(
                messaging_relationship(
                    self.enterprise_with_application,
                    self.student_a,
                ),
                "application",
            )
            self.assertIsNone(
                messaging_relationship(
                    self.student_a,
                    self.enterprise_without_application,
                )
            )
            self.assertIsNone(
                messaging_relationship(
                    self.enterprise_without_application,
                    self.student_a,
                )
            )

    def test_teacher_and_student_are_always_allowed(self):
        with self.app.app_context():
            self.assertEqual(
                messaging_relationship(self.teacher_a, self.student_b),
                "teacher_student",
            )
            self.assertEqual(
                messaging_relationship(self.student_b, self.teacher_a),
                "teacher_student",
            )

    def test_contacts_are_exactly_allowed_and_unique(self):
        with self.app.app_context():
            contacts = list_allowed_contacts(self.student_a)
            self.assertEqual(
                contacts,
                [
                    {
                        "id": self.teacher_a,
                        "name": "教师甲",
                        "role": "teacher",
                        "relationship": "teacher_student",
                    },
                    {
                        "id": self.teacher_b,
                        "name": "教师乙",
                        "role": "teacher",
                        "relationship": "teacher_student",
                    },
                    {
                        "id": self.enterprise_with_application,
                        "name": "已申请企业",
                        "role": "enterprise",
                        "relationship": "application",
                    },
                ],
            )
            contact_ids = [contact["id"] for contact in contacts]
            self.assertEqual(len(contact_ids), len(set(contact_ids)))
            self.assertEqual(list_allowed_contacts(self.admin_user), [])

    def test_same_role_and_privileged_role_pairs_are_denied(self):
        denied_pairs = [
            (self.teacher_a, self.teacher_b),
            (self.student_a, self.student_b),
            (
                self.enterprise_with_application,
                self.enterprise_without_application,
            ),
            (self.admin_user, self.government_user),
            (self.government_user, self.admin_user),
            (self.admin_user, self.teacher_a),
            (self.government_user, self.student_a),
        ]
        with self.app.app_context():
            for viewer_id, other_id in denied_pairs:
                with self.subTest(viewer_id=viewer_id, other_id=other_id):
                    self.assertIsNone(
                        messaging_relationship(viewer_id, other_id)
                    )


if __name__ == "__main__":
    unittest.main()
