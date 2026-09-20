import json
import sqlite3
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest import TestCase

from app import create_app
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
