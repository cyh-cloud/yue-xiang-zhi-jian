import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from app import create_app
from app.db import get_db
from app.government_console.errors import (
    ProviderConflictError,
    ProviderNotFoundError,
    ProviderUnavailableError,
    ProviderValidationError,
)
from app.government_console.policy import (
    delete_policy,
    list_policies,
    publish_policy,
    relist_policy,
    unpublish_policy,
)


class GovernmentPolicyTests(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(Path(self.temp_dir.name) / "test.db"),
                "SECRET_KEY": "test-only-secret",
            }
        )
        with self.app.app_context():
            cursor = get_db().execute(
                """
                INSERT INTO users (
                    username, password_hash, name, role, is_enabled,
                    created_at, updated_at
                )
                VALUES (
                    'government', 'hash', '政府用户', 'government', 1,
                    '2026-09-18T09:00:00+08:00',
                    '2026-09-18T09:00:00+08:00'
                )
                """
            )
            get_db().commit()
            self.government_id = int(cursor.lastrowid)

    def tearDown(self):
        self.temp_dir.cleanup()

    def publication_kwargs(self, **overrides):
        values = {
            "actor_id": self.government_id,
            "request_id": "publish-1",
            "title": "创业补贴",
            "content": "补贴内容",
            "category_code": "entrepreneurship",
        }
        values.update(overrides)
        return values

    def create_policy(self, **overrides):
        with patch(
            "app.government_console.policy.emit_policy_published",
            return_value={"created_count": 1},
        ):
            return publish_policy(**self.publication_kwargs(**overrides))

    def test_publish_is_idempotent_and_pushes_once(self):
        with self.app.app_context():
            with patch(
                "app.government_console.policy.emit_policy_published",
                return_value={"created_count": 1},
            ) as emit:
                first = publish_policy(**self.publication_kwargs())
                second = publish_policy(**self.publication_kwargs())

            self.assertEqual(first["id"], second["id"])
            self.assertEqual(first["status"], "active")
            self.assertEqual(first["category_label"], "创业支持")
            emit.assert_called_once_with(
                event_id="policy:publish-1",
                policy_id=first["id"],
                title="创业补贴",
                category="创业支持",
            )

    def test_publish_failure_rolls_back_and_same_request_can_retry(self):
        with self.app.app_context():
            with patch(
                "app.government_console.policy.emit_policy_published",
                side_effect=ProviderUnavailableError("订阅推送暂不可用"),
            ):
                with self.assertRaises(ProviderUnavailableError):
                    publish_policy(**self.publication_kwargs())

            self.assertIsNone(self.get_policy_row("policy:missing"))
            self.assertEqual(self.count_policies(), 0)
            self.assertEqual(self.count_publication_requests(), 0)

            with patch(
                "app.government_console.policy.emit_policy_published",
                return_value={"created_count": 1},
            ) as retry_emit:
                retried = publish_policy(**self.publication_kwargs())

            self.assertEqual(retried["status"], "active")
            retry_emit.assert_called_once()

    def test_unpublish_relist_delete_preserve_and_remove_correctly(self):
        with self.app.app_context():
            policy = self.create_policy()
            unpublished = unpublish_policy(
                policy["id"],
                expected_version=policy["version"],
            )
            self.assertEqual(unpublished["status"], "unpublished")
            self.assertEqual(unpublished["version"], policy["version"] + 1)

            with patch(
                "app.government_console.policy.emit_policy_published"
            ) as emit:
                relisted = relist_policy(
                    policy["id"],
                    expected_version=unpublished["version"],
                )
            emit.assert_not_called()
            self.assertEqual(relisted["status"], "active")
            self.assertEqual(
                relisted["version"],
                unpublished["version"] + 1,
            )

            get_db().execute(
                """
                INSERT INTO government_view_events (
                    content_type, content_id, view_event_id, created_at
                )
                VALUES ('policy', ?, 'view-1', ?)
                """,
                (policy["id"], relisted["updated_at"]),
            )
            get_db().commit()

            with patch(
                "app.government_console.policy."
                "mark_notification_sources_unavailable"
            ) as mark:
                delete_policy(
                    policy["id"],
                    expected_version=relisted["version"],
                )
                mark.assert_called_once_with(
                    source_type="policy",
                    source_id=policy["id"],
                )

            self.assertIsNone(self.get_policy_row(policy["id"]))
            self.assertEqual(self.count_policy_view_events(policy["id"]), 0)

    def test_delete_rolls_back_when_source_availability_update_fails(self):
        with self.app.app_context():
            policy = self.create_policy()
            get_db().execute(
                """
                INSERT INTO government_view_events (
                    content_type, content_id, view_event_id, created_at
                )
                VALUES ('policy', ?, 'view-1', ?)
                """,
                (policy["id"], policy["updated_at"]),
            )
            get_db().commit()

            with patch(
                "app.government_console.policy."
                "mark_notification_sources_unavailable",
                side_effect=ProviderUnavailableError("02 暂不可用"),
            ):
                with self.assertRaises(ProviderUnavailableError):
                    delete_policy(
                        policy["id"],
                        expected_version=policy["version"],
                    )

            self.assertIsNotNone(self.get_policy_row(policy["id"]))
            self.assertEqual(self.count_policy_view_events(policy["id"]), 1)

    def test_list_filters_and_orders_management_records(self):
        with self.app.app_context():
            first = self.create_policy(request_id="publish-1", title="第一条")
            second = self.create_policy(request_id="publish-2", title="第二条")
            hidden = self.create_policy(request_id="publish-3", title="第三条")
            unpublished = unpublish_policy(
                hidden["id"],
                expected_version=hidden["version"],
            )
            get_db().execute(
                """
                UPDATE government_policies
                SET published_at = ?
                WHERE id = ?
                """,
                ("2026-09-18T10:00:00+08:00", first["id"]),
            )
            get_db().execute(
                """
                UPDATE government_policies
                SET published_at = ?
                WHERE id = ?
                """,
                ("2026-09-18T09:00:00+08:00", second["id"]),
            )
            get_db().execute(
                """
                UPDATE government_policies
                SET published_at = ?
                WHERE id = ?
                """,
                ("2026-09-18T11:00:00+08:00", hidden["id"]),
            )
            get_db().commit()

            all_policies = list_policies(category_code="entrepreneurship")
            active_policies = list_policies(
                status="active",
                category_code="entrepreneurship",
            )
            unpublished_policies = list_policies(status="unpublished")

            self.assertEqual(
                [item["id"] for item in all_policies],
                [hidden["id"], first["id"], second["id"]],
            )
            self.assertEqual(
                [item["id"] for item in active_policies],
                [first["id"], second["id"]],
            )
            self.assertEqual(
                [item["id"] for item in unpublished_policies],
                [unpublished["id"]],
            )

            delete_policy(
                first["id"],
                expected_version=first["version"],
            )
            self.assertNotIn(
                first["id"],
                {item["id"] for item in list_policies()},
            )

    def test_validation_rejects_blank_or_unknown_values_without_writing(self):
        with self.app.app_context():
            invalid_values = (
                ("request_id", " "),
                ("title", ""),
                ("content", "\t"),
                ("category_code", "unknown"),
                ("actor_id", True),
            )
            for field, value in invalid_values:
                with self.subTest(field=field):
                    with patch(
                        "app.government_console.policy."
                        "emit_policy_published"
                    ) as emit:
                        with self.assertRaises(ProviderValidationError):
                            publish_policy(
                                **self.publication_kwargs(
                                    **{field: value}
                                )
                            )
                    emit.assert_not_called()

            self.assertEqual(self.count_policies(), 0)
            self.assertEqual(self.count_publication_requests(), 0)

    def test_list_validation_rejects_invalid_filter_types(self):
        with self.app.app_context():
            with self.assertRaises(ProviderValidationError):
                list_policies(status=[])
            with self.assertRaises(ProviderValidationError):
                list_policies(category_code=[])

    def test_transitions_reject_stale_versions_and_invalid_states(self):
        with self.app.app_context():
            policy = self.create_policy()
            unpublished = unpublish_policy(
                policy["id"],
                expected_version=policy["version"],
            )

            with self.assertRaises(ProviderConflictError):
                unpublish_policy(
                    policy["id"],
                    expected_version=unpublished["version"],
                )
            with self.assertRaises(ProviderConflictError):
                relist_policy(
                    policy["id"],
                    expected_version=policy["version"],
                )
            with self.assertRaises(ProviderNotFoundError):
                unpublish_policy("policy-missing", expected_version=1)

            row = self.get_policy_row(policy["id"])
            self.assertEqual(row["status"], "unpublished")
            self.assertEqual(row["version"], unpublished["version"])

    def get_policy_row(self, policy_id):
        return get_db().execute(
            """
            SELECT id, status, version
            FROM government_policies
            WHERE id = ?
            """,
            (policy_id,),
        ).fetchone()

    def count_policies(self):
        return int(
            get_db().execute(
                "SELECT COUNT(*) FROM government_policies"
            ).fetchone()[0]
        )

    def count_publication_requests(self):
        return int(
            get_db().execute(
                """
                SELECT COUNT(*)
                FROM government_publication_requests
                WHERE content_type = 'policy'
                """
            ).fetchone()[0]
        )

    def count_policy_view_events(self, policy_id):
        return int(
            get_db().execute(
                """
                SELECT COUNT(*)
                FROM government_view_events
                WHERE content_type = 'policy' AND content_id = ?
                """,
                (policy_id,),
            ).fetchone()[0]
        )


if __name__ == "__main__":
    import unittest

    unittest.main()
