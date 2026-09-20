from __future__ import annotations

import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest import TestCase

from app import create_app
from app.admin_console import (
    DatabaseRewardCatalogProvider,
    create_reward,
    list_reward_reservations,
    list_rewards_admin,
    set_reward_online,
    update_reward,
)
from app.admin_console.errors import (
    ProviderConflictError,
    ProviderValidationError,
)
from app.db import get_db, init_db
from app.handcraft_inheritance import get_reward_catalog_provider
from app.handcraft_inheritance.presets import (
    PLACEHOLDER_REWARDS,
    PlaceholderRewardCatalogProvider,
)
from app.handcraft_inheritance.rewards import (
    list_rewards as list_rewards_for_student,
)


CATALOG_REWARD_KEYS = {
    "reward_id",
    "name",
    "points_cost",
    "stock",
    "is_online",
    "is_demo",
    "source_available",
    "version",
    "created_at",
    "updated_at",
}
NOW = "2026-09-20T10:00:00+08:00"


class AdminRewardCatalogTests(TestCase):
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
            }
        )
        with self.app.app_context():
            db = get_db()
            db.execute(
                """
                INSERT INTO users (
                    id, username, password_hash, name, role, is_enabled,
                    created_at, updated_at
                )
                VALUES (1, 'reward-admin', 'hash', '管理员', 'admin', 1, ?, ?)
                """,
                (NOW, NOW),
            )
            db.commit()

    def tearDown(self):
        self.temp_dir.cleanup()

    def _create(self, **overrides) -> dict:
        payload = {"name": "测试奖品", "points_cost": 20, "stock": 5}
        payload.update(overrides)
        with self.app.app_context():
            return create_reward(1, payload)

    def _reward(self, reward_id: str) -> dict:
        with self.app.app_context():
            return next(
                reward
                for reward in list_rewards_admin()
                if reward["reward_id"] == reward_id
            )

    def test_seeded_demo_rewards_expose_real_bools_and_required_keys(self):
        with self.app.app_context():
            provider = get_reward_catalog_provider()
            self.assertIsInstance(provider, DatabaseRewardCatalogProvider)
            self.assertIsInstance(provider, PlaceholderRewardCatalogProvider)
            rewards = provider.list_rewards()

        self.assertEqual(
            [reward["reward_id"] for reward in rewards],
            [
                "reward-guangxiu-bookmark",
                "reward-yangjiang-lacquerware-keychain",
                "reward-chaoshan-woodcarving-coaster",
                "reward-shiwan-ceramics-teacup",
            ],
        )
        for reward in rewards:
            self.assertTrue(CATALOG_REWARD_KEYS.issubset(reward))
            self.assertIsInstance(reward["reward_id"], str)
            self.assertIs(reward["is_online"], True)
            self.assertIs(reward["is_demo"], True)
            self.assertIs(reward["source_available"], True)
            self.assertIsInstance(reward["stock"], int)
            self.assertIsInstance(reward["points_cost"], int)
            self.assertIsInstance(reward["version"], int)

    def test_admin_created_reward_is_immediately_visible_to_05(self):
        created = self._create(
            reward_id="reward-admin-owned",
            name="新奖品",
            points_cost=20,
            stock=3,
        )
        with self.app.app_context():
            visible = get_reward_catalog_provider().list_rewards()

        self.assertIn(
            created["reward_id"],
            {reward["reward_id"] for reward in visible},
        )
        listed = next(
            reward
            for reward in visible
            if reward["reward_id"] == created["reward_id"]
        )
        self.assertEqual(listed["stock"], 3)
        self.assertIs(listed["is_online"], True)
        self.assertIs(listed["is_demo"], False)

    def test_offline_reward_cannot_reserve_stock(self):
        self._create(
            reward_id="reward-offline",
            name="下架奖品",
            points_cost=10,
            stock=9,
            is_online=False,
        )
        with self.app.app_context():
            provider = get_reward_catalog_provider()
            self.assertIsNone(
                provider.reserve_stock("reward-offline", 1, "r1")
            )
            reservations = list_reward_reservations()

        self.assertEqual(reservations, [])

    def test_offline_reward_is_reported_offline_to_05(self):
        self._create(
            reward_id="reward-hidden",
            name="下架奖品",
            points_cost=10,
            stock=9,
            is_online=False,
        )
        with self.app.app_context():
            rewards = list_rewards_for_student(1)
            hidden = next(
                reward
                for reward in rewards
                if reward["reward_id"] == "reward-hidden"
            )

        self.assertIs(hidden["is_online"], False)
        self.assertIs(hidden["source_available"], True)
        self.assertEqual(hidden["unavailable_reason"], "奖品已下架")
        self.assertIs(hidden["can_redeem"], False)

    def test_source_unavailable_reward_is_reported_unavailable_to_05(self):
        self._create(
            reward_id="reward-no-source",
            name="来源不可用奖品",
            points_cost=10,
            stock=9,
            source_available=False,
        )
        with self.app.app_context():
            rewards = list_rewards_for_student(1)
            unavailable = next(
                reward
                for reward in rewards
                if reward["reward_id"] == "reward-no-source"
            )

        self.assertIs(unavailable["source_available"], False)
        self.assertEqual(unavailable["unavailable_reason"], "奖品已下架")

    def test_reserve_and_release_are_idempotent_and_account_for_stock(self):
        self._create(
            reward_id="reward-stock",
            name="库存奖品",
            points_cost=10,
            stock=4,
        )
        with self.app.app_context():
            provider = get_reward_catalog_provider()
            self.assertEqual(
                provider.reserve_stock("reward-stock", 2, "reservation-1"),
                "reservation-1",
            )
            self.assertEqual(
                next(
                    reward
                    for reward in provider.list_rewards()
                    if reward["reward_id"] == "reward-stock"
                )["stock"],
                2,
            )
            self.assertEqual(
                provider.reserve_stock("reward-stock", 2, "reservation-1"),
                "reservation-1",
            )
            self.assertIsNone(
                provider.reserve_stock("reward-stock", 3, "reservation-1")
            )
            self.assertIsNone(
                provider.reserve_stock("reward-stock", 3, "reservation-2")
            )
            self.assertEqual(
                next(
                    reward
                    for reward in provider.list_rewards()
                    if reward["reward_id"] == "reward-stock"
                )["stock"],
                2,
            )
            self.assertTrue(provider.release_stock("reservation-1"))
            self.assertTrue(provider.release_stock("reservation-1"))
            self.assertFalse(provider.release_stock("unknown-reservation"))
            self.assertEqual(
                next(
                    reward
                    for reward in provider.list_rewards()
                    if reward["reward_id"] == "reward-stock"
                )["stock"],
                4,
            )
            reservations = list_reward_reservations("reward-stock")

        self.assertEqual(len(reservations), 1)
        self.assertEqual(reservations[0]["status"], "released")
        self.assertIsNotNone(reservations[0]["released_at"])

    def test_reserve_rejects_invalid_arguments_without_writing(self):
        self._create(
            reward_id="reward-guard",
            name="校验奖品",
            points_cost=10,
            stock=4,
        )
        with self.app.app_context():
            provider = get_reward_catalog_provider()
            for reward_id, quantity, reservation_id in (
                ("", 1, "reservation-a"),
                ("reward-guard", 0, "reservation-b"),
                ("reward-guard", -1, "reservation-c"),
                ("reward-guard", True, "reservation-d"),
                ("reward-guard", 1.0, "reservation-e"),
                ("reward-guard", 1, ""),
                ("reward-missing", 1, "reservation-f"),
            ):
                with self.subTest(reservation_id=reservation_id):
                    self.assertIsNone(
                        provider.reserve_stock(
                            reward_id,
                            quantity,
                            reservation_id,
                        )
                    )
            self.assertEqual(list_reward_reservations(), [])

    def test_non_redemption_reservation_is_stored_in_admin_table(self):
        self._create(
            reward_id="reward-external",
            name="外部预留奖品",
            points_cost=10,
            stock=4,
        )
        with self.app.app_context():
            self.assertEqual(
                get_reward_catalog_provider().reserve_stock(
                    "reward-external",
                    2,
                    "reservation-1",
                ),
                "reservation-1",
            )
            admin_rows = get_db().execute(
                """
                SELECT reservation_id, reward_id, quantity, status, released_at
                FROM admin_reward_reservations
                """
            ).fetchall()
            redemption_rows = get_db().execute(
                "SELECT * FROM reward_stock_reservations"
            ).fetchall()

        self.assertEqual(len(admin_rows), 1)
        self.assertEqual(admin_rows[0]["reservation_id"], "reservation-1")
        self.assertEqual(admin_rows[0]["reward_id"], "reward-external")
        self.assertEqual(admin_rows[0]["quantity"], 2)
        self.assertEqual(admin_rows[0]["status"], "reserved")
        self.assertIsNone(admin_rows[0]["released_at"])
        self.assertEqual(redemption_rows, [])

    def test_redemption_backed_reservation_is_stored_in_05_table(self):
        self._create(
            reward_id="reward-redeemable",
            name="可兑换奖品",
            points_cost=10,
            stock=4,
        )
        with self.app.app_context():
            db = get_db()
            db.execute(
                """
                INSERT INTO users (
                    id, username, password_hash, name, role, is_enabled,
                    created_at, updated_at
                )
                VALUES (7, 'redeemer', 'hash', '学员', 'student', 1, ?, ?)
                """,
                (NOW, NOW),
            )
            db.execute(
                """
                INSERT INTO redemptions (
                    id, user_id, reward_id, reward_name, reward_snapshot_json,
                    points_cost, request_id, status, created_at, updated_at
                )
                VALUES (7, 7, 'reward-redeemable', '可兑换奖品', '{}', 10,
                        'request-7', 'pending', ?, ?)
                """,
                (NOW, NOW),
            )
            db.execute(
                """
                INSERT INTO redemptions (
                    id, user_id, reward_id, reward_name, reward_snapshot_json,
                    points_cost, request_id, status, created_at, updated_at
                )
                VALUES (8, 7, 'reward-redeemable', '可兑换奖品', '{}', 10,
                        'request-8', 'pending', ?, ?)
                """,
                (NOW, NOW),
            )
            db.commit()
            provider = get_reward_catalog_provider()
            self.assertEqual(
                provider.reserve_stock("reward-redeemable", 1, "7"),
                "7",
            )
            self.assertEqual(
                provider.reserve_stock("reward-redeemable", 1, "redemption:8"),
                "redemption:8",
            )
            # 05 declares `redemption_id` UNIQUE, so a second token naming
            # redemption 7 is refused instead of double booking it.
            self.assertIsNone(
                provider.reserve_stock("reward-redeemable", 1, "redemption:7")
            )
            rows = get_db().execute(
                """
                SELECT reservation_id, redemption_id, reward_id, quantity, status
                FROM reward_stock_reservations
                ORDER BY reservation_id
                """
            ).fetchall()
            admin_rows = get_db().execute(
                "SELECT * FROM admin_reward_reservations"
            ).fetchall()
            stock = next(
                reward
                for reward in provider.list_rewards()
                if reward["reward_id"] == "reward-redeemable"
            )["stock"]

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["reservation_id"], "7")
        self.assertEqual(rows[0]["redemption_id"], 7)
        self.assertEqual(rows[1]["reservation_id"], "redemption:8")
        self.assertEqual(rows[1]["redemption_id"], 8)
        self.assertEqual(admin_rows, [])
        self.assertEqual(stock, 2)

    def test_release_of_redemption_backed_reservation_keeps_the_row(self):
        self._create(
            reward_id="reward-release",
            name="释放奖品",
            points_cost=10,
            stock=4,
        )
        with self.app.app_context():
            db = get_db()
            db.execute(
                """
                INSERT INTO users (
                    id, username, password_hash, name, role, is_enabled,
                    created_at, updated_at
                )
                VALUES (7, 'redeemer', 'hash', '学员', 'student', 1, ?, ?)
                """,
                (NOW, NOW),
            )
            db.execute(
                """
                INSERT INTO redemptions (
                    id, user_id, reward_id, reward_name, reward_snapshot_json,
                    points_cost, request_id, status, created_at, updated_at
                )
                VALUES (7, 7, 'reward-release', '释放奖品', '{}', 10,
                        'request-7', 'pending', ?, ?)
                """,
                (NOW, NOW),
            )
            db.commit()
            provider = get_reward_catalog_provider()
            self.assertEqual(
                provider.reserve_stock("reward-release", 1, "7"), "7"
            )
            self.assertTrue(provider.release_stock("7"))
            released_rows = get_db().execute(
                """
                SELECT status, released_at, redemption_id
                FROM reward_stock_reservations
                WHERE reservation_id = '7'
                """
            ).fetchall()
            stock = next(
                reward
                for reward in provider.list_rewards()
                if reward["reward_id"] == "reward-release"
            )["stock"]

        self.assertEqual(len(released_rows), 1)
        self.assertEqual(released_rows[0]["status"], "released")
        self.assertEqual(released_rows[0]["redemption_id"], 7)
        self.assertIsNotNone(released_rows[0]["released_at"])
        self.assertEqual(stock, 4)

    def test_reserve_refuses_when_reward_or_stock_is_unknown(self):
        with self.app.app_context():
            provider = get_reward_catalog_provider()
            self.assertIsNone(provider.reserve_stock("nope", 1, "reservation-x"))
            self.assertIsNone(
                provider.reserve_stock(
                    PLACEHOLDER_REWARDS[0]["reward_id"],
                    11,
                    "reservation-y",
                )
            )


class RewardStockConcurrencyTests(TestCase):
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
            }
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_concurrent_reserve_of_last_unit_does_not_oversell(self):
        with self.app.app_context():
            create_reward(
                1,
                {
                    "reward_id": "reward-last-unit",
                    "name": "限购奖品",
                    "points_cost": 10,
                    "stock": 1,
                },
            )

        barrier = threading.Barrier(2)

        def reserve(reservation_id: str):
            with self.app.app_context():
                barrier.wait(timeout=10)
                return get_reward_catalog_provider().reserve_stock(
                    "reward-last-unit",
                    1,
                    reservation_id,
                )

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(
                executor.map(reserve, ("concurrent-1", "concurrent-2"))
            )

        with self.app.app_context():
            stock = next(
                reward
                for reward in get_reward_catalog_provider().list_rewards()
                if reward["reward_id"] == "reward-last-unit"
            )["stock"]
            reserved = get_db().execute(
                "SELECT COUNT(*) AS count FROM admin_reward_reservations"
            ).fetchone()["count"]

        self.assertEqual(sum(result is not None for result in results), 1)
        self.assertEqual(stock, 0)
        self.assertEqual(reserved, 1)

    def test_concurrent_updates_raise_409_instead_of_losing_the_first_edit(self):
        with self.app.app_context():
            create_reward(
                1,
                {
                    "reward_id": "reward-race",
                    "name": "并发奖品",
                    "points_cost": 10,
                    "stock": 5,
                },
            )

        barrier = threading.Barrier(2)
        outcomes: list[tuple[str, str]] = []
        outcomes_lock = threading.Lock()

        def submit(name: str) -> None:
            with self.app.app_context():
                barrier.wait(timeout=10)
                try:
                    update_reward(
                        1,
                        "reward-race",
                        1,
                        {"name": name, "points_cost": 10},
                    )
                    outcome = ("ok", name)
                except ProviderConflictError:
                    outcome = ("conflict", name)
            with outcomes_lock:
                outcomes.append(outcome)

        threads = [
            threading.Thread(target=submit, args=("管理员甲",)),
            threading.Thread(target=submit, args=("管理员乙",)),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)

        self.assertEqual(len(outcomes), 2)
        self.assertEqual(
            sorted(outcome[0] for outcome in outcomes),
            ["conflict", "ok"],
        )
        winner = next(name for status, name in outcomes if status == "ok")
        with self.app.app_context():
            row = (
                get_db()
                .execute(
                    """
                    SELECT name, version FROM admin_rewards
                    WHERE reward_id = 'reward-race'
                    """
                )
                .fetchone()
            )
        self.assertEqual(int(row["version"]), 2)
        self.assertEqual(row["name"], winner)


class AdminRewardServiceTests(TestCase):
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
            }
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def _create(self, **overrides) -> dict:
        payload = {"name": "测试奖品", "points_cost": 20, "stock": 5}
        payload.update(overrides)
        with self.app.app_context():
            return create_reward(1, payload)

    def test_create_reward_validates_payload(self):
        cases = (
            ({}, "name"),
            ({"name": "奖品"}, "points_cost"),
            ({"name": "奖品", "points_cost": 0}, "points_cost"),
            ({"name": "奖品", "points_cost": True}, "points_cost"),
            ({"name": "奖品", "points_cost": 10, "stock": -1}, "stock"),
            ({"name": "奖品", "points_cost": 10, "stock": "5"}, "stock"),
            (
                {"name": "奖品", "points_cost": 10, "stock": 1, "is_online": 1},
                "is_online",
            ),
            (
                {
                    "reward_id": "Bad_Id",
                    "name": "奖品",
                    "points_cost": 10,
                    "stock": 1,
                },
                "reward_id",
            ),
        )
        for payload, field in cases:
            with self.subTest(payload=payload):
                with self.app.app_context():
                    with self.assertRaises(ProviderValidationError) as caught:
                        create_reward(1, payload)
                self.assertEqual(caught.exception.details.get("field"), field)
                self.assertEqual(caught.exception.code, "reward_validation_failed")

    def test_create_reward_conflicts_on_duplicate_id(self):
        self._create(reward_id="reward-duplicate")
        with self.app.app_context():
            with self.assertRaises(ProviderConflictError) as caught:
                create_reward(
                    1,
                    {
                        "reward_id": "reward-duplicate",
                        "name": "重复奖品",
                        "points_cost": 10,
                        "stock": 1,
                    },
                )
        self.assertEqual(caught.exception.code, "reward_conflict")

    def test_update_reward_round_trip_writes_audit_rows(self):
        created = self._create(reward_id="reward-editable")
        with self.app.app_context():
            updated = update_reward(
                1,
                "reward-editable",
                1,
                {
                    "name": "改名后的奖品",
                    "points_cost": 25,
                    "stock": 4,
                    "is_online": False,
                },
            )
            audit = get_db().execute(
                """
                SELECT action, target_type, target_id
                FROM admin_audit_log
                WHERE target_type = 'reward' AND target_id = 'reward-editable'
                ORDER BY id
                """
            ).fetchall()

        self.assertEqual(created["version"], 1)
        self.assertEqual(updated["name"], "改名后的奖品")
        self.assertEqual(updated["points_cost"], 25)
        self.assertEqual(updated["stock"], 4)
        self.assertIs(updated["is_online"], False)
        self.assertEqual(updated["version"], 2)
        self.assertEqual(
            [row["action"] for row in audit],
            ["create_reward", "update_reward"],
        )
        self.assertEqual(audit[0]["target_type"], "reward")

    def test_update_reward_rejects_version_mismatch(self):
        self._create(reward_id="reward-locked")
        with self.app.app_context():
            with self.assertRaises(ProviderConflictError) as caught:
                update_reward(
                    1,
                    "reward-locked",
                    99,
                    {"name": "改名", "points_cost": 10},
                )
        self.assertEqual(caught.exception.code, "reward_version_conflict")
        self.assertEqual(
            caught.exception.details,
            {
                "reward_id": "reward-locked",
                "expected_version": 99,
                "current_version": 1,
            },
        )

    def test_update_reward_rejects_path_id_mismatch(self):
        self._create(reward_id="reward-immutable")
        with self.app.app_context():
            with self.assertRaises(ProviderValidationError) as caught:
                update_reward(
                    1,
                    "reward-immutable",
                    1,
                    {
                        "reward_id": "reward-other",
                        "name": "改名",
                        "points_cost": 10,
                    },
                )
        self.assertEqual(caught.exception.code, "reward_id_mismatch")

    def test_update_reward_rejects_unknown_reward(self):
        from app.admin_console.errors import ProviderNotFoundError

        with self.app.app_context():
            with self.assertRaises(ProviderNotFoundError) as caught:
                update_reward(
                    1,
                    "reward-missing",
                    1,
                    {"name": "改名", "points_cost": 10},
                )
        self.assertEqual(caught.exception.code, "reward_not_found")

    def test_stock_cannot_drop_below_reserved_quantity(self):
        self._create(reward_id="reward-reserved", stock=5)
        with self.app.app_context():
            self.assertEqual(
                get_reward_catalog_provider().reserve_stock(
                    "reward-reserved",
                    2,
                    "reservation-1",
                ),
                "reservation-1",
            )
            with self.assertRaises(ProviderValidationError) as caught:
                update_reward(
                    1,
                    "reward-reserved",
                    1,
                    {"name": "库存奖品", "points_cost": 20, "stock": 1},
                )
            self.assertEqual(
                caught.exception.code, "reward_stock_below_reserved"
            )
            updated = update_reward(
                1,
                "reward-reserved",
                1,
                {"name": "库存奖品", "points_cost": 20, "stock": 2},
            )
            self.assertEqual(updated["stock"], 2)
            self.assertEqual(updated["available"], 0)

    def test_set_reward_online_toggles_state_and_audits(self):
        self._create(reward_id="reward-toggle")
        with self.app.app_context():
            offline = set_reward_online(1, "reward-toggle", 1, False)
            audit = get_db().execute(
                """
                SELECT action, result FROM admin_audit_log
                WHERE target_id = 'reward-toggle' AND action LIKE 'set_reward%'
                """
            ).fetchall()
            online_again = set_reward_online(1, "reward-toggle", 2, True)
            visible = get_reward_catalog_provider().list_rewards()

        self.assertIs(offline["is_online"], False)
        self.assertEqual(offline["version"], 2)
        self.assertEqual([row["action"] for row in audit], ["set_reward_offline"])
        self.assertIs(online_again["is_online"], True)
        self.assertEqual(online_again["version"], 3)
        self.assertIn(
            "reward-toggle",
            {reward["reward_id"] for reward in visible},
        )

    def test_set_reward_online_rejects_version_mismatch(self):
        self._create(reward_id="reward-toggle-locked")
        with self.app.app_context():
            with self.assertRaises(ProviderConflictError) as caught:
                set_reward_online(1, "reward-toggle-locked", 99, False)
        self.assertEqual(caught.exception.code, "reward_version_conflict")

    def test_set_reward_online_rejects_unknown_reward(self):
        from app.admin_console.errors import ProviderNotFoundError

        with self.app.app_context():
            with self.assertRaises(ProviderNotFoundError):
                set_reward_online(1, "reward-missing", 1, False)

    def test_list_rewards_admin_reports_stock_reserved_and_available(self):
        self._create(reward_id="reward-reporting", stock=6)
        with self.app.app_context():
            get_reward_catalog_provider().reserve_stock(
                "reward-reporting",
                2,
                "reservation-1",
            )
            items = list_rewards_admin()
            reservations = list_reward_reservations("reward-reporting")

        reported = next(
            item for item in items if item["reward_id"] == "reward-reporting"
        )
        self.assertEqual(reported["stock"], 6)
        self.assertEqual(reported["reserved"], 2)
        self.assertEqual(reported["available"], 4)
        self.assertEqual(len(reservations), 1)
        self.assertEqual(reservations[0]["source"], "admin_reward_reservations")


class DemoRewardSeedTests(TestCase):
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
            }
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_init_db_twice_keeps_admin_edits_and_offline_state(self):
        with self.app.app_context():
            created = create_reward(
                1,
                {
                    "reward_id": "reward-survivor",
                    "name": "重启后仍在",
                    "points_cost": 20,
                    "stock": 5,
                },
            )
            update_reward(
                1,
                "reward-survivor",
                1,
                {"name": "改名后的奖品", "points_cost": 25, "stock": 4},
            )
            set_reward_online(1, "reward-survivor", 2, False)
            init_db()
            items = {item["reward_id"]: item for item in list_rewards_admin()}
            demo_rows = get_db().execute(
                "SELECT COUNT(*) AS count FROM admin_rewards WHERE is_demo = 1"
            ).fetchone()["count"]

        survivor = items["reward-survivor"]
        self.assertEqual(survivor["name"], "改名后的奖品")
        self.assertEqual(survivor["points_cost"], 25)
        self.assertEqual(survivor["stock"], 4)
        self.assertIs(survivor["is_online"], False)
        self.assertEqual(survivor["version"], 3)
        self.assertIs(survivor["is_demo"], False)
        self.assertEqual(demo_rows, len(PLACEHOLDER_REWARDS))
        for reward in PLACEHOLDER_REWARDS:
            seeded = items[reward["reward_id"]]
            self.assertIs(seeded["is_demo"], True)
            self.assertIs(seeded["is_online"], True)
            self.assertEqual(seeded["stock"], reward["stock"])
            self.assertEqual(seeded["version"], 1)
        self.assertEqual(created["version"], 1)


class AdminRewardRouteTests(TestCase):
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
        self.super_admin = self._login("reward-super-admin", "super_admin")
        self.admin = self._login("reward-admin", "admin")
        self.student = self._login("reward-student", "student")

    def tearDown(self):
        self.temp_dir.cleanup()

    def _create_user(self, username: str, role: str) -> None:
        from werkzeug.security import generate_password_hash

        with self.app.app_context():
            get_db().execute(
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
            get_db().commit()

    def _login(self, username: str, role: str):
        self._create_user(username, role)
        client = self.app.test_client()
        response = client.post(
            "/api/auth/login",
            json={"username": username, "password": "password8"},
        )
        self.assertEqual(response.status_code, 200)
        return client

    def test_admin_created_reward_is_immediately_visible_to_05(self):
        response = self.admin.post(
            "/api/admin/rewards",
            json={"name": "新奖品", "points_cost": 20, "stock": 3},
        )
        self.assertEqual(response.status_code, 201)
        reward_id = response.get_json()["reward"]["reward_id"]
        with self.app.app_context():
            visible = get_reward_catalog_provider().list_rewards()

        self.assertIn(reward_id, {reward["reward_id"] for reward in visible})

    def test_reward_crud_round_trip(self):
        created = self.admin.post(
            "/api/admin/rewards",
            json={
                "reward_id": "reward-console",
                "name": "后台奖品",
                "points_cost": 30,
                "stock": 6,
            },
        )
        self.assertEqual(created.status_code, 201)
        reward_id = created.get_json()["reward"]["reward_id"]

        updated = self.admin.put(
            f"/api/admin/rewards/{reward_id}",
            json={
                "expected_version": 1,
                "name": "后台奖品（修订）",
                "points_cost": 35,
                "stock": 5,
            },
        )
        self.assertEqual(updated.status_code, 200)
        body = updated.get_json()["reward"]
        self.assertEqual(body["name"], "后台奖品（修订）")
        self.assertEqual(body["points_cost"], 35)
        self.assertEqual(body["version"], 2)

        offline = self.admin.post(
            f"/api/admin/rewards/{reward_id}/online",
            json={"expected_version": 2, "online": False},
        )
        self.assertEqual(offline.status_code, 200)
        self.assertIs(offline.get_json()["reward"]["is_online"], False)
        self.assertEqual(offline.get_json()["reward"]["version"], 3)

        with self.app.app_context():
            rewards = list_rewards_for_student(1)
        listed = next(
            reward for reward in rewards if reward["reward_id"] == reward_id
        )
        self.assertEqual(listed["unavailable_reason"], "奖品已下架")

    def test_reward_update_rejects_stale_expected_version(self):
        created = self.admin.post(
            "/api/admin/rewards",
            json={"name": "版本奖品", "points_cost": 20, "stock": 3},
        )
        reward_id = created.get_json()["reward"]["reward_id"]
        response = self.admin.put(
            f"/api/admin/rewards/{reward_id}",
            json={
                "expected_version": 99,
                "name": "改名",
                "points_cost": 20,
            },
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.get_json()["code"],
            "reward_version_conflict",
        )

    def test_reward_online_toggle_rejects_stale_expected_version(self):
        created = self.admin.post(
            "/api/admin/rewards",
            json={"name": "切换奖品", "points_cost": 20, "stock": 3},
        )
        reward_id = created.get_json()["reward"]["reward_id"]
        response = self.admin.post(
            f"/api/admin/rewards/{reward_id}/online",
            json={"expected_version": 99, "online": False},
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.get_json()["code"],
            "reward_version_conflict",
        )

    def test_reward_routes_reject_invalid_payload_with_400(self):
        response = self.admin.post(
            "/api/admin/rewards",
            json={"name": "坏奖品", "points_cost": 0, "stock": 1},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.get_json()["code"], "reward_validation_failed"
        )

    def test_reward_routes_return_404_for_unknown_reward(self):
        response = self.admin.put(
            "/api/admin/rewards/reward-missing",
            json={"expected_version": 1, "name": "改名", "points_cost": 10},
        )
        self.assertEqual(response.status_code, 404)

    def test_super_admin_and_admin_both_manage_rewards(self):
        for client in (self.super_admin, self.admin):
            response = client.get("/api/admin/rewards")
            self.assertEqual(response.status_code, 200)
            body = response.get_json()
            self.assertIn("items", body)
            self.assertEqual(body["count"], len(body["items"]))
            self.assertTrue(
                all("available" in item for item in body["items"])
            )

    def test_student_session_cannot_manage_rewards(self):
        for method, path, payload in (
            ("get", "/api/admin/rewards", None),
            ("post", "/api/admin/rewards", {"name": "x", "points_cost": 1, "stock": 1}),
            (
                "put",
                "/api/admin/rewards/reward-guangxiu-bookmark",
                {"expected_version": 1, "name": "x", "points_cost": 1},
            ),
            (
                "post",
                "/api/admin/rewards/reward-guangxiu-bookmark/online",
                {"expected_version": 1, "online": False},
            ),
        ):
            with self.subTest(method=method, path=path):
                response = getattr(self.student, method)(path, json=payload)
                self.assertEqual(response.status_code, 403)

    def test_anonymous_session_cannot_manage_rewards(self):
        response = self.app.test_client().get("/api/admin/rewards")
        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
