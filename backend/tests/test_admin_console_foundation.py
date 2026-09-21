import json
import sqlite3
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from app import create_app
from app.admin_console import system_announcements
from app.admin_console.audit import record_admin_audit
from app.admin_console.errors import (
    ProviderAccessDeniedError,
    ProviderConflictError,
    ProviderError,
    ProviderNotFoundError,
    ProviderUnavailableError,
    ProviderValidationError,
)
from app.admin_console.time_utils import platform_now_iso
from app.db import get_db


ADMIN_TABLES = {
    "admin_agri_calendar",
    "admin_agri_products",
    "admin_assistant_feature_knowledge",
    "admin_audit_log",
    "admin_handcraft_crafts",
    "admin_notification_outbox",
    "admin_pest_knowledge",
    "admin_rewards",
    "comment_reports",
    "content_review_records",
    "feedback_records",
    "platform_points_policy",
    "system_announcements",
}

ADMIN_TABLE_COLUMNS = {
    "admin_agri_calendar": {
        "item_id",
        "product_key",
        "month",
        "tasks_json",
        "management_json",
        "solar_terms_json",
        "reminder",
        "sort_order",
        "is_enabled",
        "version",
        "created_at",
        "updated_at",
    },
    "admin_agri_products": {
        "product_key",
        "name",
        "sort_order",
        "is_enabled",
        "version",
        "created_at",
        "updated_at",
    },
    "admin_assistant_feature_knowledge": {
        "knowledge_id",
        "title",
        "body",
        "feature_key",
        "jump_target",
        "is_enabled",
        "sort_order",
        "version",
        "created_at",
        "updated_at",
    },
    "admin_audit_log": {
        "id",
        "actor_id",
        "action",
        "target_type",
        "target_id",
        "before_json",
        "after_json",
        "result",
        "created_at",
    },
    "admin_handcraft_crafts": {
        "craft_key",
        "name",
        "introduction",
        "steps_json",
        "material_guide_json",
        "source_available",
        "sort_order",
        "is_enabled",
        "version",
        "created_at",
        "updated_at",
    },
    "admin_notification_outbox": {
        "id",
        "event_type",
        "event_id",
        "payload_json",
        "status",
        "attempts",
        "last_error",
        "created_at",
        "sent_at",
    },
    "admin_pest_knowledge": {
        "item_id",
        "sort_order",
        "pest_name",
        "product_names_json",
        "symptoms_json",
        "aliases_json",
        "answer",
        "is_enabled",
        "version",
        "created_at",
        "updated_at",
    },
    "admin_rewards": {
        "reward_id",
        "name",
        "points_cost",
        "stock",
        "is_online",
        "source_available",
        "version",
        "created_at",
        "updated_at",
    },
    "comment_reports": {
        "report_id",
        "comment_id",
        "reporter_id",
        "reason",
        "status",
        "resolver_id",
        "result",
        "created_at",
        "updated_at",
        "resolved_at",
    },
    "content_review_records": {
        "content_type",
        "content_id",
        "submitter_id",
        "review_status",
        "version",
        "rejection_opinion",
        "published_at",
        "payload_json",
        "created_at",
        "updated_at",
    },
    "feedback_records": {
        "feedback_id",
        "submitter_id",
        "body",
        "status",
        "idempotency_key",
        "handler_id",
        "result",
        "created_at",
        "updated_at",
    },
    "platform_points_policy": {
        "singleton",
        "version",
        "policy_json",
        "updated_by",
        "updated_at",
    },
    "system_announcements": {
        "announcement_id",
        "title",
        "body",
        "target_roles_json",
        "status",
        "event_id",
        "created_by",
        "created_at",
        "published_at",
    },
}


class AdminConsoleFoundationTests(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(Path(self.temp_dir.name) / "test.db"),
            }
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_admin_foundation_tables_and_columns_exist(self):
        with self.app.app_context():
            names = {
                row["name"]
                for row in get_db().execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
            self.assertTrue(ADMIN_TABLES.issubset(names))

            for table_name, expected_columns in ADMIN_TABLE_COLUMNS.items():
                with self.subTest(table=table_name):
                    columns = {
                        row["name"]
                        for row in get_db().execute(
                            f"PRAGMA table_info({table_name})"
                        )
                    }
                    self.assertTrue(expected_columns.issubset(columns))

    def test_provider_error_hierarchy_preserves_frozen_contract(self):
        details = {"field": "content_id"}
        base = ProviderError("failed", code="provider_error", details=details)
        details["field"] = "mutated"
        self.assertEqual(base.message, "failed")
        self.assertEqual(base.code, "provider_error")
        self.assertEqual(base.details, {"field": "content_id"})
        self.assertEqual(str(base), "failed")

        error_types = (
            ProviderValidationError,
            ProviderNotFoundError,
            ProviderConflictError,
            ProviderUnavailableError,
            ProviderAccessDeniedError,
        )
        for error_type in error_types:
            with self.subTest(error_type=error_type.__name__):
                error = error_type("x", code="c", details={"value": 1})
                self.assertIsInstance(error, ProviderError)
                self.assertEqual(error.message, "x")
                self.assertEqual(error.code, "c")
                self.assertEqual(error.details, {"value": 1})

    def test_platform_now_iso_uses_asia_shanghai_offset(self):
        value = platform_now_iso()
        parsed = datetime.fromisoformat(value)

        self.assertEqual(parsed.utcoffset(), timedelta(hours=8))
        self.assertTrue(value.endswith("+08:00"))

    def test_record_admin_audit_persists_before_and_after_json(self):
        with self.app.app_context():
            db = get_db()
            audit_id = record_admin_audit(
                db,
                actor_id=7,
                action="approve_content",
                target_type="content_review",
                target_id="course-1",
                before={"status": "pending"},
                after={"status": "approved"},
                result="success",
            )
            db.commit()
            row = db.execute(
                "SELECT * FROM admin_audit_log WHERE id = ?",
                (audit_id,),
            ).fetchone()

        self.assertIsInstance(audit_id, int)
        self.assertEqual(row["actor_id"], 7)
        self.assertEqual(row["action"], "approve_content")
        self.assertEqual(row["target_type"], "content_review")
        self.assertEqual(row["target_id"], "course-1")
        self.assertEqual(json.loads(row["before_json"]), {"status": "pending"})
        self.assertEqual(json.loads(row["after_json"]), {"status": "approved"})
        self.assertEqual(row["result"], "success")
        self.assertTrue(row["created_at"].endswith("+08:00"))

    def test_admin_notification_outbox_is_idempotent_by_event(self):
        with self.app.app_context():
            db = get_db()
            db.execute(
                """
                INSERT INTO admin_notification_outbox (
                    event_type, event_id, payload_json, created_at
                )
                VALUES ('review_approved', 'event-1', '{}', ?)
                """,
                (platform_now_iso(),),
            )
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute(
                    """
                    INSERT INTO admin_notification_outbox (
                        event_type, event_id, payload_json, created_at
                    )
                    VALUES ('review_approved', 'event-1', '{}', ?)
                    """,
                    (platform_now_iso(),),
                )

    def test_admin_provider_slots_use_single_registry(self):
        from app.admin_console.providers import (
            get_assistant_feature_knowledge_provider,
            get_feedback_intake_provider,
            set_assistant_feature_knowledge_provider,
            set_feedback_intake_provider,
        )

        knowledge = object()
        feedback = object()
        set_assistant_feature_knowledge_provider(self.app, knowledge)
        set_feedback_intake_provider(self.app, feedback)

        with self.app.app_context():
            self.assertIs(
                get_assistant_feature_knowledge_provider(),
                knowledge,
            )
            self.assertIs(get_feedback_intake_provider(), feedback)

        self.assertIs(
            self.app.extensions["assistant_feature_knowledge_provider"],
            knowledge,
        )
        self.assertIs(
            self.app.extensions["feedback_intake_provider"],
            feedback,
        )

    def test_admin_provider_getters_return_complete_unavailable_defaults(self):
        from app.admin_console.providers import (
            UnavailableAssistantFeatureKnowledgeProvider,
            UnavailableFeedbackIntakeProvider,
            get_assistant_feature_knowledge_provider,
            get_feedback_intake_provider,
        )

        self.app.extensions.pop(
            "assistant_feature_knowledge_provider",
            None,
        )
        self.app.extensions.pop("feedback_intake_provider", None)

        with self.app.app_context():
            knowledge = get_assistant_feature_knowledge_provider()
            feedback = get_feedback_intake_provider()

            self.assertIsInstance(
                knowledge,
                UnavailableAssistantFeatureKnowledgeProvider,
            )
            self.assertIsInstance(
                feedback,
                UnavailableFeedbackIntakeProvider,
            )
            with self.assertRaises(ProviderUnavailableError) as knowledge_error:
                knowledge.list_entries()
            with self.assertRaises(ProviderUnavailableError) as feedback_error:
                feedback.submit_feedback(
                    submitter_id=7,
                    body="建议增加夜校课程",
                    idempotency_key="feedback-1",
                )

        self.assertEqual(
            knowledge_error.exception.code,
            "assistant_feature_knowledge_unavailable",
        )
        self.assertEqual(
            feedback_error.exception.code,
            "feedback_intake_unavailable",
        )

    def test_configure_admin_providers_delegates_to_required_slots(self):
        from app.admin_console.providers import (
            configure_admin_providers,
        )

        knowledge = object()
        feedback = object()
        configure_admin_providers(
            self.app,
            knowledge=knowledge,
            feedback_intake=feedback,
        )

        self.assertIs(
            self.app.extensions["assistant_feature_knowledge_provider"],
            knowledge,
        )
        self.assertIs(
            self.app.extensions["feedback_intake_provider"],
            feedback,
        )

    def test_install_default_admin_services_registers_database_defaults(self):
        from app.admin_console.providers import (
            DatabaseAssistantFeatureKnowledgeProvider,
            DatabaseFeedbackIntakeProvider,
        )

        self.assertIsInstance(
            self.app.extensions["assistant_feature_knowledge_provider"],
            DatabaseAssistantFeatureKnowledgeProvider,
        )
        self.assertIsInstance(
            self.app.extensions["feedback_intake_provider"],
            DatabaseFeedbackIntakeProvider,
        )


class AdminAnnouncementTests(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "PROPAGATE_EXCEPTIONS": False,
                "DATABASE_PATH": str(
                    Path(self.temp_dir.name) / "test.db"
                ),
                "SECRET_KEY": "test-only-secret",
                "SESSION_HOURS": 24,
                "SESSION_COOKIE_SECURE": False,
            }
        )
        self.user_ids: dict[str, int] = {}
        self.super_admin = self._login(
            "announcement-super-admin",
            "super_admin",
        )
        self.admin = self._login("announcement-admin", "admin")
        self.student = self._login("announcement-student", "student")

    def tearDown(self):
        self.temp_dir.cleanup()

    def _create_user(self, username: str, role: str) -> int:
        from werkzeug.security import generate_password_hash

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
                    f"{role}-{username}",
                    role,
                    "2026-09-21T09:00:00+08:00",
                    "2026-09-21T09:00:00+08:00",
                ),
            )
            user_id = int(cursor.lastrowid)
            get_db().commit()
        return user_id

    def _login(self, username: str, role: str):
        self.user_ids[username] = self._create_user(username, role)
        client = self.app.test_client()
        response = client.post(
            "/api/auth/login",
            json={"username": username, "password": "password8"},
        )
        self.assertEqual(response.status_code, 200)
        return client

    @property
    def super_admin_id(self) -> int:
        return self.user_ids["announcement-super-admin"]

    def _create_announcement(self, **overrides) -> dict:
        payload = {
            "title": "维护通知",
            "body": "本周六凌晨进行系统维护",
            "target_roles": ["student"],
        }
        payload.update(overrides)
        response = self.super_admin.post(
            "/api/admin/announcements",
            json=payload,
        )
        self.assertEqual(response.status_code, 201)
        return response.get_json()["announcement"]

    def _publish(self, announcement_id: str):
        return self.super_admin.post(
            f"/api/admin/announcements/{announcement_id}/publish"
        )

    def _backdate(self, announcement_id: str, stamp: str) -> None:
        with self.app.app_context():
            get_db().execute(
                """
                UPDATE system_announcements
                SET created_at = ?
                WHERE announcement_id = ?
                """,
                (stamp, announcement_id),
            )
            get_db().commit()

    def _count(self, table: str) -> int:
        with self.app.app_context():
            return int(
                get_db()
                .execute(f"SELECT COUNT(*) AS count FROM {table}")
                .fetchone()["count"]
            )

    def notification_count(self, event_type: str) -> int:
        with self.app.app_context():
            return int(
                get_db()
                .execute(
                    """
                    SELECT COUNT(*) AS count
                    FROM system_notifications
                    WHERE event_type = ?
                    """,
                    (event_type,),
                )
                .fetchone()["count"]
            )

    def outbox_rows(self, event_id: str) -> list[dict]:
        with self.app.app_context():
            return [
                dict(row)
                for row in get_db().execute(
                    """
                    SELECT id, event_type, event_id, payload_json, status,
                           attempts, last_error, sent_at
                    FROM admin_notification_outbox
                    WHERE event_type = 'system_announcement'
                      AND event_id = ?
                    """,
                    (event_id,),
                )
            ]

    def audit_actions(self) -> list[str]:
        with self.app.app_context():
            return [
                str(row["action"])
                for row in get_db().execute(
                    "SELECT action FROM admin_audit_log ORDER BY id"
                )
            ]

    def test_publishing_announcement_twice_notifies_once(self):
        created = self._create_announcement()
        first = self._publish(created["announcement_id"])
        second = self._publish(created["announcement_id"])

        self.assertTrue(first.get_json()["changed"])
        self.assertFalse(second.get_json()["changed"])
        self.assertEqual(self.notification_count("system_announcement"), 1)
        self.assertEqual(len(self.outbox_rows(created["event_id"])), 1)

    def test_announcements_are_invisible_and_unoperable_for_other_roles(self):
        created = self._create_announcement()
        paths = (
            ("get", "/api/admin/announcements"),
            ("post", "/api/admin/announcements"),
            (
                "post",
                f"/api/admin/announcements/{created['announcement_id']}/publish",
            ),
        )
        for role, client in (("admin", self.admin), ("student", self.student)):
            for method, path in paths:
                with self.subTest(role=role, method=method, path=path):
                    response = getattr(client, method)(
                        path,
                        json={
                            "title": "越权创建",
                            "body": "越权正文",
                            "target_roles": ["student"],
                        },
                    )
                    self.assertEqual(response.status_code, 403)
                    body = response.get_json()
                    self.assertFalse(body["success"])
                    self.assertEqual(body["code"], "admin_access_denied")
                    self.assertNotIn("items", body)
                    self.assertNotIn("announcement", body)

        self.assertEqual(self._count("system_announcements"), 1)
        self.assertEqual(self.notification_count("system_announcement"), 0)
        self.assertEqual(self.outbox_rows(created["event_id"]), [])

    def test_unknown_announcement_publish_is_reported_as_404(self):
        response = self._publish("announcement-00000000000000000000000000000000")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.get_json()["code"],
            "announcement_not_found",
        )

    def test_delivery_failure_keeps_published_state_and_retryable_outbox_row(self):
        created = self._create_announcement()
        with patch.object(
            system_announcements,
            "emit_system_announcement",
            side_effect=OSError("gateway unreachable"),
        ):
            response = self._publish(created["announcement_id"])

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["changed"])
        self.assertEqual(response.get_json()["delivery"]["failed"], 1)

        with self.app.app_context():
            row = get_db().execute(
                """
                SELECT status, published_at
                FROM system_announcements
                WHERE announcement_id = ?
                """,
                (created["announcement_id"],),
            ).fetchone()
        self.assertEqual(row["status"], "published")
        self.assertTrue(row["published_at"].endswith("+08:00"))
        self.assertEqual(self.notification_count("system_announcement"), 0)

        outbox = self.outbox_rows(created["event_id"])
        self.assertEqual(len(outbox), 1)
        self.assertEqual(outbox[0]["status"], "pending")
        self.assertEqual(outbox[0]["attempts"], 1)
        self.assertIn("gateway unreachable", outbox[0]["last_error"])
        self.assertIsNone(outbox[0]["sent_at"])

        with self.app.app_context():
            retry = system_announcements.deliver_announcement_notification(
                int(outbox[0]["id"])
            )
        self.assertEqual(retry["delivered"], 1)
        self.assertEqual(self.notification_count("system_announcement"), 1)
        resent = self.outbox_rows(created["event_id"])
        self.assertEqual(resent[0]["status"], "sent")
        self.assertEqual(resent[0]["attempts"], 2)

        repeat = self._publish(created["announcement_id"])
        self.assertFalse(repeat.get_json()["changed"])
        self.assertEqual(self.notification_count("system_announcement"), 1)

    def test_outbox_row_and_published_status_share_one_transaction(self):
        created = self._create_announcement()
        with self.app.app_context(), patch.object(
            system_announcements,
            "record_admin_audit",
            side_effect=sqlite3.OperationalError("audit table locked"),
        ):
            with self.assertRaises(sqlite3.OperationalError):
                system_announcements.publish_announcement(
                    self.super_admin_id,
                    created["announcement_id"],
                )

        with self.app.app_context():
            row = get_db().execute(
                """
                SELECT status, published_at
                FROM system_announcements
                WHERE announcement_id = ?
                """,
                (created["announcement_id"],),
            ).fetchone()

        self.assertEqual(row["status"], "draft")
        self.assertIsNone(row["published_at"])
        self.assertEqual(self.outbox_rows(created["event_id"]), [])
        self.assertEqual(self.notification_count("system_announcement"), 0)
        self.assertEqual(self.audit_actions(), ["create_announcement"])

    def test_target_role_validation_rejects_unknown_role_and_empty_set(self):
        cases = (
            {"target_roles": ["wizard"]},
            {"target_roles": []},
            {"target_roles": "student"},
            {"target_roles": ["student", 7]},
        )
        for overrides in cases:
            with self.subTest(target_roles=overrides["target_roles"]):
                response = self.super_admin.post(
                    "/api/admin/announcements",
                    json={
                        "title": "维护通知",
                        "body": "本周六凌晨进行系统维护",
                        **overrides,
                    },
                )
                self.assertEqual(response.status_code, 400)
                body = response.get_json()
                self.assertFalse(body["success"])
                self.assertEqual(body["code"], "announcement_validation_failed")
                self.assertTrue(body["message"])
                self.assertEqual(body["details"]["field"], "target_roles")
                self.assertEqual(
                    body["details"]["allowed"],
                    [
                        "admin",
                        "enterprise",
                        "government",
                        "student",
                        "super_admin",
                        "teacher",
                    ],
                )

        blank_title = self.super_admin.post(
            "/api/admin/announcements",
            json={"title": "   ", "body": "正文", "target_roles": ["student"]},
        )
        self.assertEqual(blank_title.status_code, 400)
        self.assertEqual(blank_title.get_json()["details"]["field"], "title")

        long_body = self.super_admin.post(
            "/api/admin/announcements",
            json={
                "title": "标题",
                "body": "长" * 2001,
                "target_roles": ["student"],
            },
        )
        self.assertEqual(long_body.status_code, 400)
        self.assertEqual(long_body.get_json()["details"]["field"], "body")

        self.assertEqual(self._count("system_announcements"), 0)
        self.assertEqual(self.audit_actions(), [])

    def test_announcement_without_matching_recipients_still_publishes(self):
        created = self._create_announcement(target_roles=["government"])
        response = self._publish(created["announcement_id"])

        # The publish is committed regardless; only the frozen, empty recipient
        # list drives the outbox row to a terminal failure, so the retry sweep
        # never keeps re-attempting a row that can no longer succeed.
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["changed"])
        self.assertEqual(response.get_json()["delivery"]["recipient_count"], 0)
        self.assertEqual(response.get_json()["delivery"]["failed"], 1)
        self.assertEqual(self.notification_count("system_announcement"), 0)

        outbox = self.outbox_rows(created["event_id"])
        self.assertEqual(len(outbox), 1)
        self.assertEqual(outbox[0]["status"], "failed")
        self.assertEqual(outbox[0]["attempts"], 1)
        self.assertIsNone(outbox[0]["sent_at"])
        self.assertIn("收件人", outbox[0]["last_error"])
        self.assertEqual(
            json.loads(outbox[0]["payload_json"])["recipient_ids"],
            [],
        )

    def test_retry_sweep_delivers_pending_announcement_exactly_once(self):
        from app.admin_console.outbox import retry_admin_notifications

        created = self._create_announcement()
        with patch.object(
            system_announcements,
            "emit_system_announcement",
            side_effect=OSError("gateway unreachable"),
        ):
            response = self._publish(created["announcement_id"])
        self.assertEqual(response.status_code, 200)

        outbox = self.outbox_rows(created["event_id"])
        self.assertEqual(outbox[0]["status"], "pending")
        self.assertEqual(outbox[0]["attempts"], 1)
        self.assertEqual(self.notification_count("system_announcement"), 0)

        # The event id is frozen in the payload, so a scan retry delivers the
        # same event to the recipient side exactly once and marks the row sent.
        with self.app.app_context():
            summary = retry_admin_notifications()
        self.assertEqual(summary["delivered"], 1)
        self.assertEqual(self.notification_count("system_announcement"), 1)

        resent = self.outbox_rows(created["event_id"])
        self.assertEqual(resent[0]["status"], "sent")
        self.assertEqual(resent[0]["attempts"], 2)

        # A second sweep finds nothing pending and re-notifies nobody.
        with self.app.app_context():
            retry_admin_notifications()
        self.assertEqual(self.notification_count("system_announcement"), 1)

    def test_outbox_accounting_db_error_does_not_fail_publish(self):
        from app.admin_console import outbox

        created = self._create_announcement()

        class _AccountingFailureConnection:
            def __init__(self, real):
                self._real = real

            def execute(self, sql, *args, **kwargs):
                if "status = 'sent'" in sql:
                    raise sqlite3.OperationalError("simulated accounting failure")
                return self._real.execute(sql, *args, **kwargs)

            def __enter__(self):
                self._real.__enter__()
                return self

            def __exit__(self, *exc):
                return self._real.__exit__(*exc)

        with self.app.app_context():
            proxy = _AccountingFailureConnection(get_db())
            with patch.object(outbox, "get_db", return_value=proxy):
                result = system_announcements.publish_announcement(
                    self.super_admin_id,
                    created["announcement_id"],
                )

        # The emit reached 02 and the notification was persisted, but only the
        # sent-mark accounting write failed: the publish still reports success
        # and the row stays pending, instead of escaping as a spurious 500.
        self.assertTrue(result["changed"])
        self.assertEqual(result["delivery"]["delivered"], 1)
        self.assertEqual(self.notification_count("system_announcement"), 1)
        self.assertEqual(
            self.outbox_rows(created["event_id"])[0]["status"], "pending"
        )

    def test_announcements_list_flushes_pending_outbox_via_hook(self):
        created = self._create_announcement()
        with patch.object(
            system_announcements,
            "emit_system_announcement",
            side_effect=OSError("gateway unreachable"),
        ):
            self._publish(created["announcement_id"])

        self.assertEqual(self.notification_count("system_announcement"), 0)
        self.assertEqual(
            self.outbox_rows(created["event_id"])[0]["status"], "pending"
        )

        # No manual retry call: reading the announcements list as a super admin
        # lets the endpoint's automatic-retry hook deliver the pending row --
        # exactly the self-driven retry the publish-failure UI copy promises.
        listed = self.super_admin.get("/api/admin/announcements")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(
            self.outbox_rows(created["event_id"])[0]["status"], "sent"
        )
        self.assertEqual(self.notification_count("system_announcement"), 1)

    def test_create_and_publish_write_audit_rows(self):
        created = self._create_announcement()
        self.assertEqual(self.audit_actions(), ["create_announcement"])

        self._publish(created["announcement_id"])
        self.assertEqual(
            self.audit_actions(),
            ["create_announcement", "publish_announcement"],
        )

        self._publish(created["announcement_id"])
        self.assertEqual(
            self.audit_actions(),
            ["create_announcement", "publish_announcement"],
        )

    def test_list_announcements_keeps_history_in_deterministic_order(self):
        first = self._create_announcement(title="第一条")
        second = self._create_announcement(title="第二条")
        third = self._create_announcement(title="第三条")
        self._publish(second["announcement_id"])
        self._backdate(first["announcement_id"], "2026-09-21T10:00:00+08:00")
        self._backdate(second["announcement_id"], "2026-09-21T11:00:00+08:00")
        self._backdate(third["announcement_id"], "2026-09-21T09:00:00+08:00")

        response = self.super_admin.get("/api/admin/announcements")
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["count"], 3)
        items = body["items"]
        self.assertEqual(
            [item["announcement_id"] for item in items],
            [
                second["announcement_id"],
                first["announcement_id"],
                third["announcement_id"],
            ],
        )
        self.assertEqual(
            [item["status"] for item in items],
            ["published", "draft", "draft"],
        )
        self.assertEqual(
            [item["created_at"] for item in items],
            [
                "2026-09-21T11:00:00+08:00",
                "2026-09-21T10:00:00+08:00",
                "2026-09-21T09:00:00+08:00",
            ],
        )
        self.assertEqual(items[0]["target_roles"], ["student"])
        self.assertIsNotNone(items[0]["published_at"])
        self.assertTrue(items[0]["published_at"].endswith("+08:00"))
        self.assertIsNone(items[1]["published_at"])
        self.assertIsNone(items[2]["published_at"])

    def test_announcement_history_breaks_created_at_ties_on_announcement_id(self):
        first = self._create_announcement(title="并列一")
        second = self._create_announcement(title="并列二")
        stamp = "2026-09-21T12:00:00+08:00"
        self._backdate(first["announcement_id"], stamp)
        self._backdate(second["announcement_id"], stamp)

        items = self.super_admin.get("/api/admin/announcements").get_json()["items"]
        tied = [
            item["announcement_id"]
            for item in items
            if item["created_at"] == stamp
        ]

        self.assertEqual(len(tied), 2)
        self.assertEqual(tied, sorted(tied))
