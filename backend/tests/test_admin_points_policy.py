from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from werkzeug.security import generate_password_hash

from app import create_app
from app.admin_console import (
    DatabasePointsPolicyProvider,
    get_points_policy,
    set_points_policy_provider,
    update_points_policy,
)
from app.admin_console.errors import (
    ProviderConflictError,
    ProviderNotFoundError,
    ProviderUnavailableError,
    ProviderValidationError,
)
from app.admin_console.points_policy import TRAINING_WEIGHT_KEYS
from app.admin_console.providers import (
    get_points_policy_provider as get_admin_points_policy_provider,
)
from app.db import get_db
from app.handcraft_inheritance import get_points_policy_provider
from app.handcraft_inheritance.points import (
    SUPPORTED_TRAINING_EVENT_TYPES,
    get_effective_policy,
)
from app.handcraft_inheritance.presets import (
    PLACEHOLDER_POINTS_POLICY,
    PlaceholderPointsPolicyProvider,
)


NOW = "2026-09-21T09:00:00+08:00"
POLICY_PAYLOAD = {
    "expected_version": 1,
    "seconds_per_point": 300,
    "training_weights": {
        "default": 1,
        "live_script": 4,
        "simulation": 3,
        "copy_training": 2,
        "customer_service": 5,
    },
    "daily_limit": 50,
    "expiry_mode": "natural_year",
}
POINTS_STATE_TABLES = (
    "points_policy_snapshots",
    "points_transactions",
    "points_lots",
    "points_allocations",
    "points_accounts",
)
POLICY_ROW_SQL = """
    SELECT singleton, version, policy_json, updated_by, updated_at
    FROM platform_points_policy
    WHERE singleton = 1
"""


def _policy_row() -> dict:
    row = get_db().execute(POLICY_ROW_SQL).fetchone()
    return dict(row) if row is not None else {}


class PointsPolicyTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = str(Path(self.temp_dir.name) / "test.db")
        self.app = create_app(
            {
                "TESTING": True,
                "PROPAGATE_EXCEPTIONS": False,
                "DATABASE_PATH": self.database_path,
                "SECRET_KEY": "test-only-secret",
                "SESSION_HOURS": 24,
                "SESSION_COOKIE_SECURE": False,
            }
        )
        self.user_ids: dict[str, int] = {}

    def tearDown(self):
        self.temp_dir.cleanup()

    def _stored_policy(self) -> dict:
        return json.loads(_policy_row()["policy_json"])

    def _points_state(self) -> dict:
        state: dict[str, list[dict]] = {}
        for table in POINTS_STATE_TABLES:
            state[table] = [
                dict(row)
                for row in get_db().execute(
                    f"SELECT * FROM {table} ORDER BY 1"
                ).fetchall()
            ]
        return state

    def _create_points_student(self) -> None:
        db = get_db()
        db.execute(
            """
            INSERT INTO users (
                id, username, password_hash, name, role, is_enabled,
                created_at, updated_at
            )
            VALUES (11, 'points-student', 'hash', '学员', 'student', 1, ?, ?)
            """,
            (NOW, NOW),
        )
        db.execute(
            """
            INSERT INTO points_accounts (user_id, balance, updated_at)
            VALUES (11, 30, ?)
            """,
            (NOW,),
        )
        award_cursor = db.execute(
            """
            INSERT INTO points_transactions (
                user_id, transaction_type, source_module, source_event_id,
                delta, balance_after, created_at
            )
            VALUES (11, 'award', 'handcraft', 'seed-award-1', 30, 30, ?)
            """,
            (NOW,),
        )
        award_id = int(award_cursor.lastrowid)
        lot_cursor = db.execute(
            """
            INSERT INTO points_lots (
                user_id, award_transaction_id, original_points,
                remaining_points, expires_at, created_at
            )
            VALUES (11, ?, 30, 30, NULL, ?)
            """,
            (award_id, NOW),
        )
        db.execute(
            """
            INSERT INTO points_allocations (transaction_id, lot_id, points)
            VALUES (?, ?, 10)
            """,
            (award_id, int(lot_cursor.lastrowid)),
        )
        db.commit()


class PointsPolicySeedTests(PointsPolicyTestCase):
    def test_seed_writes_the_05_demo_policy_as_the_platform_row(self):
        with self.app.app_context():
            row = _policy_row()

        self.assertEqual(row["singleton"], 1)
        self.assertEqual(row["version"], 1)
        self.assertEqual(row["updated_by"], 0)
        self.assertTrue(row["updated_at"].endswith("+08:00"))
        self.assertEqual(json.loads(row["policy_json"]), PLACEHOLDER_POINTS_POLICY)

    def test_installed_provider_reads_the_database_row(self):
        with self.app.app_context():
            provider = get_points_policy_provider()
            policy = provider.get_policy()
            admin_provider = get_admin_points_policy_provider()

        self.assertIsInstance(provider, DatabasePointsPolicyProvider)
        self.assertIsInstance(provider, PlaceholderPointsPolicyProvider)
        self.assertIs(admin_provider, provider)
        self.assertEqual(policy, PLACEHOLDER_POINTS_POLICY)

    def test_provider_slot_is_replaceable_through_the_console_owner(self):
        with self.app.app_context():
            replacement = DatabasePointsPolicyProvider()
            set_points_policy_provider(self.app, replacement)
            installed = get_admin_points_policy_provider()

        self.assertIs(installed, replacement)
        self.assertIs(
            self.app.extensions["admin_points_policy_provider"],
            replacement,
        )

    def test_seed_keeps_an_admin_edit_across_restart(self):
        with self.app.app_context():
            update_points_policy(7, dict(POLICY_PAYLOAD), 1)
            edited = _policy_row()

        restarted = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": self.database_path,
                "SECRET_KEY": "test-only-secret",
            }
        )
        with restarted.app_context():
            row = _policy_row()

        self.assertEqual(row["version"], 2)
        self.assertEqual(row["policy_json"], edited["policy_json"])
        self.assertEqual(row["updated_by"], 7)


class PointsPolicyValidationTests(PointsPolicyTestCase):
    def _update(self, **overrides):
        payload = dict(POLICY_PAYLOAD)
        payload.update(overrides)
        with self.app.app_context():
            return update_points_policy(
                7,
                payload,
                payload.get("expected_version"),
            )

    def _expect_validation(self, code: str, **overrides):
        with self.assertRaises(ProviderValidationError) as caught:
            self._update(**overrides)
        self.assertEqual(caught.exception.code, code)
        return caught.exception

    def test_unknown_field_is_rejected(self):
        error = self._expect_validation("points_policy_field_unknown", note="备注")
        self.assertEqual(error.details["fields"], ["note"])
        self.assertIn("daily_limit", error.details["allowed"])

    def test_missing_field_is_rejected(self):
        payload = dict(POLICY_PAYLOAD)
        del payload["daily_limit"]
        with self.app.app_context():
            with self.assertRaises(ProviderValidationError) as caught:
                update_points_policy(7, payload, payload.get("expected_version"))
        self.assertEqual(caught.exception.code, "points_policy_field_missing")
        self.assertEqual(caught.exception.details["fields"], ["daily_limit"])

    def test_non_dict_payload_is_rejected(self):
        with self.app.app_context():
            with self.assertRaises(ProviderValidationError):
                update_points_policy(7, [], 1)

    def test_missing_expected_version_is_rejected(self):
        payload = dict(POLICY_PAYLOAD, expected_version=None)
        with self.app.app_context():
            with self.assertRaises(ProviderValidationError) as caught:
                update_points_policy(7, payload, None)
        self.assertEqual(caught.exception.details["field"], "expected_version")

    def test_deleted_expected_version_key_is_rejected(self):
        payload = dict(POLICY_PAYLOAD)
        del payload["expected_version"]
        with self.app.app_context():
            with self.assertRaises(ProviderValidationError) as caught:
                update_points_policy(7, payload, payload.get("expected_version"))
        self.assertEqual(caught.exception.code, "points_policy_field_missing")
        self.assertEqual(
            caught.exception.details["fields"],
            ["expected_version"],
        )

    def test_training_weights_missing_a_key_is_rejected(self):
        weights = dict(POLICY_PAYLOAD["training_weights"])
        del weights["customer_service"]
        error = self._expect_validation(
            "points_policy_weight_missing",
            training_weights=weights,
        )
        self.assertEqual(error.details["fields"], ["customer_service"])

    def test_unknown_training_weight_key_is_rejected(self):
        weights = dict(POLICY_PAYLOAD["training_weights"], quiz=3)
        error = self._expect_validation(
            "points_policy_weight_unknown",
            training_weights=weights,
        )
        self.assertEqual(error.details["fields"], ["quiz"])

    def test_non_positive_training_weight_is_rejected(self):
        cases = (
            ("simulation", 0),
            ("copy_training", -2),
            ("customer_service", 1.5),
            ("live_script", True),
        )
        for key, weight in cases:
            with self.subTest(key=key, weight=weight):
                weights = dict(POLICY_PAYLOAD["training_weights"])
                weights[key] = weight
                with self.assertRaises(ProviderValidationError) as caught:
                    self._update(training_weights=weights)
                self.assertEqual(
                    caught.exception.details["field"],
                    f"training_weights.{key}",
                )

    def test_non_dict_training_weights_is_rejected(self):
        with self.assertRaises(ProviderValidationError) as caught:
            self._update(training_weights=[1, 2, 3])
        self.assertEqual(caught.exception.details["field"], "training_weights")

    def test_non_positive_ratio_and_daily_limit_are_rejected(self):
        cases = (
            ("seconds_per_point", 0),
            ("seconds_per_point", "600"),
            ("daily_limit", -1),
            ("daily_limit", True),
        )
        for field, value in cases:
            with self.subTest(field=field, value=value):
                error = self._expect_validation(
                    "points_policy_validation_failed",
                    **{field: value},
                )
                self.assertEqual(error.details["field"], field)

    def test_unknown_expiry_mode_is_rejected(self):
        error = self._expect_validation(
            "points_policy_expiry_mode_invalid",
            expiry_mode="rolling_year",
        )
        self.assertEqual(error.details["field"], "expiry_mode")
        self.assertEqual(
            sorted(error.details["allowed"]),
            ["natural_year", "permanent"],
        )

    def test_unhashable_expiry_mode_is_rejected(self):
        error = self._expect_validation(
            "points_policy_expiry_mode_invalid",
            expiry_mode=["permanent"],
        )
        self.assertEqual(error.details["field"], "expiry_mode")


class PointsPolicyServiceTests(PointsPolicyTestCase):
    def test_stale_expected_version_is_a_conflict(self):
        with self.app.app_context():
            with self.assertRaises(ProviderConflictError) as caught:
                update_points_policy(7, dict(POLICY_PAYLOAD), 99)

        self.assertEqual(caught.exception.code, "points_policy_version_conflict")
        self.assertEqual(caught.exception.details["expected_version"], 99)
        self.assertEqual(caught.exception.details["current_version"], 1)

    def test_conflict_leaves_the_stored_row_untouched(self):
        with self.app.app_context():
            before = _policy_row()
            with self.assertRaises(ProviderConflictError):
                update_points_policy(7, dict(POLICY_PAYLOAD), 99)
            after = _policy_row()

        self.assertEqual(before, after)

    def test_update_writes_new_version_policy_and_one_audit_row(self):
        with self.app.app_context():
            before = _policy_row()
            result = update_points_policy(7, dict(POLICY_PAYLOAD), 1)
            after = _policy_row()
            stored = self._stored_policy()
            audit_rows = get_db().execute(
                """
                SELECT actor_id, action, target_type, target_id,
                       before_json, after_json, result
                FROM admin_audit_log
                WHERE action = 'update_points_policy'
                """
            ).fetchall()

        self.assertEqual(result["version"], 2)
        self.assertEqual(result["rule_version"], "v2")
        self.assertEqual(result["seconds_per_point"], 300)
        self.assertEqual(result["daily_limit"], 50)
        self.assertEqual(result["expiry_mode"], "natural_year")
        self.assertEqual(
            result["training_weights"],
            POLICY_PAYLOAD["training_weights"],
        )
        self.assertFalse(result["is_demo"])
        self.assertTrue(result["source_available"])
        self.assertEqual(result["updated_by"], 7)
        self.assertTrue(result["updated_at"].endswith("+08:00"))

        self.assertEqual(after["version"], 2)
        self.assertEqual(after["updated_by"], 7)
        self.assertNotEqual(after["policy_json"], before["policy_json"])
        self.assertEqual(stored["version"], "v2")

        self.assertEqual(len(audit_rows), 1)
        audit = dict(audit_rows[0])
        self.assertEqual(audit["actor_id"], 7)
        self.assertEqual(audit["action"], "update_points_policy")
        self.assertEqual(audit["target_type"], "points_policy")
        self.assertEqual(audit["target_id"], "platform")
        self.assertEqual(audit["result"], "success")
        self.assertEqual(json.loads(audit["before_json"])["seconds_per_point"], 600)
        self.assertEqual(
            json.loads(audit["after_json"])["training_weights"]["live_script"],
            4,
        )

    def test_second_update_requires_the_new_version(self):
        with self.app.app_context():
            update_points_policy(7, dict(POLICY_PAYLOAD), 1)
            second = dict(POLICY_PAYLOAD)
            second["expected_version"] = 2
            second["seconds_per_point"] = 900
            result = update_points_policy(8, second, 2)

        self.assertEqual(result["version"], 3)
        self.assertEqual(result["rule_version"], "v3")
        self.assertEqual(result["seconds_per_point"], 900)
        self.assertEqual(result["updated_by"], 8)

    def test_get_points_policy_exposes_the_stored_row(self):
        with self.app.app_context():
            update_points_policy(7, dict(POLICY_PAYLOAD), 1)
            policy = get_points_policy()

        self.assertEqual(policy["version"], 2)
        self.assertEqual(policy["rule_version"], "v2")
        self.assertEqual(policy["training_weights"]["customer_service"], 5)
        self.assertEqual(policy["updated_by"], 7)
        self.assertTrue(policy["updated_at"].endswith("+08:00"))

    def test_missing_row_is_reported_as_not_found(self):
        with self.app.app_context():
            get_db().execute("DELETE FROM platform_points_policy")
            get_db().commit()
            with self.assertRaises(ProviderNotFoundError) as caught:
                get_points_policy()
            provider_policy = get_points_policy_provider().get_policy()

        self.assertEqual(caught.exception.code, "points_policy_not_found")
        self.assertIsNone(provider_policy)

    def test_updated_policy_is_used_by_05_on_the_next_event(self):
        with self.app.app_context():
            update_points_policy(7, dict(POLICY_PAYLOAD), 1)
            effective = get_effective_policy()

        self.assertEqual(effective["seconds_per_point"], 300)
        self.assertEqual(effective["daily_limit"], 50)
        self.assertEqual(effective["expiry_mode"], "natural_year")
        self.assertEqual(effective["version"], "v2")
        self.assertEqual(effective["training_weights"]["live_script"], 4)
        self.assertEqual(effective["training_weights"]["copy_training"], 2)
        self.assertTrue(effective["source_available"])

    def test_update_leaves_existing_points_state_untouched(self):
        with self.app.app_context():
            self._create_points_student()
            get_effective_policy()
            before = self._points_state()
            update_points_policy(7, dict(POLICY_PAYLOAD), 1)
            after = self._points_state()

        self.assertEqual(before, after)
        self.assertTrue(before["points_policy_snapshots"])
        self.assertTrue(before["points_lots"])
        self.assertTrue(before["points_transactions"])


class PointsPolicyRouteTests(PointsPolicyTestCase):
    def setUp(self):
        super().setUp()
        self.super_admin = self._login("policy-super-admin", "super_admin")
        self.admin = self._login("policy-admin", "admin")

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
                    f"{role}-{username}",
                    role,
                    NOW,
                    NOW,
                ),
            )
            user_id = int(cursor.lastrowid)
            get_db().commit()
        self.user_ids[username] = user_id
        return user_id

    def _login(self, username: str, role: str):
        self._create_user(username, role)
        client = self.app.test_client()
        response = client.post(
            "/api/auth/login",
            json={"username": username, "password": "password8"},
        )
        self.assertEqual(response.status_code, 200)
        return client

    def test_super_admin_reads_and_updates_the_policy(self):
        response = self.super_admin.get("/api/admin/points-policy")

        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertTrue(body["success"])
        self.assertEqual(body["policy"]["version"], 1)
        self.assertEqual(body["policy"]["rule_version"], "demo-v1")
        self.assertEqual(
            body["policy"]["seconds_per_point"],
            PLACEHOLDER_POINTS_POLICY["seconds_per_point"],
        )
        self.assertEqual(
            body["policy"]["training_weights"],
            PLACEHOLDER_POINTS_POLICY["training_weights"],
        )
        self.assertTrue(body["policy"]["is_demo"])
        self.assertTrue(body["policy"]["source_available"])
        self.assertTrue(body["policy"]["updated_at"].endswith("+08:00"))

        updated = self.super_admin.put(
            "/api/admin/points-policy",
            json=dict(POLICY_PAYLOAD),
        )

        self.assertEqual(updated.status_code, 200)
        updated_body = updated.get_json()
        self.assertTrue(updated_body["success"])
        self.assertEqual(updated_body["policy"]["version"], 2)
        self.assertEqual(updated_body["policy"]["rule_version"], "v2")
        self.assertEqual(
            updated_body["policy"]["training_weights"]["live_script"],
            4,
        )

    def test_update_records_the_session_actor_in_the_audit_row(self):
        self.super_admin.put(
            "/api/admin/points-policy",
            json=dict(POLICY_PAYLOAD),
        )

        with self.app.app_context():
            row = get_db().execute(
                """
                SELECT actor_id, action
                FROM admin_audit_log
                WHERE action = 'update_points_policy'
                """
            ).fetchone()

        self.assertIsNotNone(row)
        self.assertEqual(row["actor_id"], self.user_ids["policy-super-admin"])

    def test_forged_actor_in_the_body_is_ignored(self):
        response = self.super_admin.put(
            "/api/admin/points-policy",
            json=dict(POLICY_PAYLOAD, actor_id=999, updated_by=999),
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.get_json()["code"],
            "points_policy_field_unknown",
        )

    def test_ordinary_admin_cannot_read_or_write_the_policy(self):
        requests = (
            ("get", "/api/admin/points-policy", None),
            ("put", "/api/admin/points-policy", dict(POLICY_PAYLOAD)),
        )
        for method, path, payload in requests:
            with self.subTest(method=method):
                response = getattr(self.admin, method)(path, json=payload)
                self.assertEqual(response.status_code, 403)
                self.assertEqual(
                    response.get_json()["code"],
                    "admin_access_denied",
                )

        with self.app.app_context():
            row = _policy_row()
        self.assertEqual(row["version"], 1)

    def test_anonymous_request_is_rejected(self):
        response = self.app.test_client().get("/api/admin/points-policy")

        self.assertEqual(response.status_code, 401)
        self.assertFalse(response.get_json()["success"])

    def test_unknown_field_returns_400_with_field_details(self):
        response = self.super_admin.put(
            "/api/admin/points-policy",
            json=dict(POLICY_PAYLOAD, note="备注"),
        )

        self.assertEqual(response.status_code, 400)
        body = response.get_json()
        self.assertFalse(body["success"])
        self.assertEqual(body["code"], "points_policy_field_unknown")
        self.assertEqual(body["details"]["fields"], ["note"])

    def test_incomplete_training_weights_return_400(self):
        weights = dict(POLICY_PAYLOAD["training_weights"])
        del weights["default"]
        response = self.super_admin.put(
            "/api/admin/points-policy",
            json=dict(POLICY_PAYLOAD, training_weights=weights),
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.get_json()["code"],
            "points_policy_weight_missing",
        )

    def test_stale_version_returns_409_with_the_current_version(self):
        first = self.super_admin.put(
            "/api/admin/points-policy",
            json=dict(POLICY_PAYLOAD),
        )
        self.assertEqual(first.status_code, 200)

        stale = self.super_admin.put(
            "/api/admin/points-policy",
            json=dict(POLICY_PAYLOAD),
        )

        self.assertEqual(stale.status_code, 409)
        body = stale.get_json()
        self.assertFalse(body["success"])
        self.assertEqual(body["code"], "points_policy_version_conflict")
        self.assertEqual(body["details"]["current_version"], 2)


class PointsPolicyConcurrencyTests(PointsPolicyTestCase):
    def test_external_write_lock_blocks_the_update_instead_of_using_a_stale_version(
        self,
    ):
        with self.app.app_context():
            # Fail fast and deterministically when another connection holds
            # the write lock, instead of relying on the default 5s wait.
            get_db().execute("PRAGMA busy_timeout = 250")
            before = _policy_row()
            external = sqlite3.connect(self.database_path, timeout=30)
            try:
                external.execute("BEGIN IMMEDIATE")
                external.execute(
                    "UPDATE platform_points_policy SET version = 99 "
                    "WHERE singleton = 1"
                )
                # Another writer holds the write lock with an uncommitted
                # version bump. Taking the write lock has to fail, so the
                # update can never read a stale version and silently succeed.
                with self.assertRaises(sqlite3.OperationalError):
                    update_points_policy(7, dict(POLICY_PAYLOAD), 1)
                after = _policy_row()
            finally:
                external.rollback()
                external.close()

        self.assertEqual(after["version"], before["version"])
        self.assertEqual(after["policy_json"], before["policy_json"])

    def test_conflict_leaves_no_points_policy_audit_row(self):
        with self.app.app_context():
            with self.assertRaises(ProviderConflictError):
                update_points_policy(7, dict(POLICY_PAYLOAD), 99)
            audit_rows = get_db().execute(
                """
                SELECT id FROM admin_audit_log
                WHERE action = 'update_points_policy'
                """
            ).fetchall()

        self.assertEqual(audit_rows, [])

    def test_write_lock_is_taken_before_the_version_read(self):
        with self.app.app_context():
            connection = get_db()
            statements: list[str] = []
            connection.set_trace_callback(statements.append)
            try:
                update_points_policy(7, dict(POLICY_PAYLOAD), 1)
            finally:
                connection.set_trace_callback(None)
            normalized = [" ".join(sql.split()).upper() for sql in statements]

        begin_index = next(
            (i for i, sql in enumerate(normalized) if "BEGIN IMMEDIATE" in sql),
            None,
        )
        read_index = next(
            (
                i
                for i, sql in enumerate(normalized)
                if sql.startswith("SELECT") and "PLATFORM_POINTS_POLICY" in sql
            ),
            None,
        )

        # The write lock must be acquired before the version SELECT, otherwise
        # two super admins could both read the same version and both pass the
        # optimistic check. The external-lock test above pins the same
        # invariant behaviorally: with the lock taken first, the update cannot
        # read any version at all while another writer holds it.
        self.assertIsNotNone(begin_index)
        self.assertIsNotNone(read_index)
        self.assertLess(begin_index, read_index)


class PointsPolicyWeightContractTests(PointsPolicyTestCase):
    def test_training_weight_keys_match_the_05_supported_event_types(self):
        # 011 hard-codes the weight keys, so pin them to 05's contract: if 05
        # ever adds a sixth event type, this fails instead of the console
        # silently refusing to configure it.
        self.assertEqual(
            set(TRAINING_WEIGHT_KEYS),
            SUPPORTED_TRAINING_EVENT_TYPES | {"default"},
        )

    def test_stored_row_with_an_extra_weight_key_is_reported_unavailable(self):
        with self.app.app_context():
            # A valid read first, so 05 has a good snapshot to fall back to.
            self.assertTrue(get_effective_policy()["source_available"])
            corrupted = json.loads(json.dumps(PLACEHOLDER_POINTS_POLICY))
            corrupted["training_weights"] = dict(
                corrupted["training_weights"],
                quiz=3,
            )
            get_db().execute(
                """
                UPDATE platform_points_policy
                SET policy_json = ?
                WHERE singleton = 1
                """,
                (json.dumps(corrupted, ensure_ascii=False),),
            )
            get_db().commit()
            with self.assertRaises(ProviderUnavailableError) as console_caught:
                get_points_policy()
            with self.assertRaises(ProviderUnavailableError):
                get_admin_points_policy_provider().get_policy()
            effective = get_effective_policy()

        self.assertEqual(console_caught.exception.code, "points_policy_corrupted")
        self.assertNotIn("quiz", effective["training_weights"])
        self.assertFalse(effective["source_available"])


if __name__ == "__main__":
    unittest.main()
