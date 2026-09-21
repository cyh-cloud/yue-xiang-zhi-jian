from __future__ import annotations

import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import TestCase

from app import create_app
from app.admin_console import (
    get_assistant_feature_knowledge_provider,
    get_craft_preset_provider,
    get_local_resource_case_provider,
)
from app.admin_console.errors import ProviderConflictError
from app.admin_console.presets import (
    disable_craft_preset,
    list_craft_presets,
    update_craft_preset,
)
from app.db import get_db, init_db
from app.handcraft_inheritance.crafts import get_craft, list_crafts


CRAFT_READ_FIELDS = {
    "craft_key",
    "name",
    "introduction",
    "steps",
    "material_guide",
    "is_demo",
    "source_available",
    "available",
    "sort_order",
    "is_enabled",
    "version",
    "created_at",
    "updated_at",
}

CASE_READ_FIELDS = {
    "id",
    "title",
    "summary",
    "background",
    "journey",
    "lessons",
    "published_at",
    "updated_at",
    "is_demo",
}

KNOWLEDGE_ENTRY_FIELDS = {
    "knowledge_id",
    "title",
    "body",
    "feature_key",
    "jump_target",
    "is_enabled",
    "version",
    "updated_at",
}


class AdminPresetTests(TestCase):
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
        self._seed_crafts()
        self.super_admin = self._login("preset-super-admin", "super_admin")
        self.admin = self._login("preset-admin", "admin")
        self.student = self._login("preset-student", "student")

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
                    "2026-09-20T10:00:00+08:00",
                    "2026-09-20T10:00:00+08:00",
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

    def _seed_crafts(self) -> None:
        import json
        # `init_db()` now seeds the four 05 demo crafts as real manageable
        # rows, so the fixture clears the table first to keep this class
        # independent of seed state.

        rows = [
            ("guangxiu", "广绣", 1, 1, 1),
            ("craft-alpha", "技艺甲", 5, 1, 1),
            ("craft-bravo", "技艺乙", 5, 1, 1),
            ("craft-charlie", "技艺丙", 5, 1, 1),
        ]
        now = "2026-09-20T10:00:00+08:00"
        with self.app.app_context():
            db = get_db()
            db.execute("DELETE FROM admin_handcraft_crafts")
            for craft_key, name, sort_order, source, enabled in rows:
                db.execute(
                    """
                    INSERT INTO admin_handcraft_crafts (
                        craft_key, name, introduction, steps_json,
                        material_guide_json, source_available, sort_order,
                        is_demo, is_enabled, version, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, 1, ?, ?)
                    """,
                    (
                        craft_key,
                        name,
                        f"{name}的介绍文本。",
                        json.dumps(
                            [self.step(index) for index in range(1, 7)],
                            ensure_ascii=False,
                        ),
                        json.dumps(self.material_guide(), ensure_ascii=False),
                        source,
                        sort_order,
                        enabled,
                        now,
                        now,
                    ),
                )
            db.commit()

    def step(self, index: int) -> dict:
        return {
            "step_key": f"guangxiu-{index:02d}",
            "step_no": index,
            "title": f"步骤 {index}",
            "description": f"第 {index} 步的操作说明。",
            "tips": [f"提示 {index}"],
        }

    def material_guide(self) -> list[dict]:
        return [
            {
                "name": "真丝绣线",
                "reference_price": "20-40 元/束",
                "purchase_channel": "广州绣品市场或正规电商店铺",
                "precautions": "按色系分批采购，避免明显色差。",
                "taobao_keyword": "广绣真丝绣线",
            }
        ]

    def case_payload(self) -> dict:
        return {
            "case_id": "case-admin-owned",
            "title": "果园合作社的统防统治",
            "summary": "统一防控降低成本。",
            "background": "散户防治时机不一致。",
            "journey": "组建合作社统一采购与施药。",
            "lessons": "统一时间节点是关键。",
            "sort_order": 40,
            "published_at": "2026-09-05T08:00:00+08:00",
        }

    def _update_craft(self, path_key: str, **overrides) -> dict:
        """PUT a craft, always sending the version currently stored."""
        with self.app.app_context():
            row = get_db().execute(
                """
                SELECT version FROM admin_handcraft_crafts
                WHERE craft_key = ?
                """,
                (path_key,),
            ).fetchone()
        payload = {
            "expected_version": int(row["version"]),
            "name": "广绣",
            "introduction": "更新介绍",
            "steps": [self.step(index) for index in range(1, 7)],
            "material_guide": self.material_guide(),
            "sort_order": 1,
            "source_available": True,
            "is_enabled": True,
        }
        payload.update(overrides)
        return self.admin.put(
            f"/api/admin/presets/handcraft_crafts/{path_key}", json=payload
        )

    def test_craft_provider_keeps_stable_key_and_steps(self):
        self.admin.put(
            "/api/admin/presets/handcraft_crafts/guangxiu",
            json={
                "expected_version": 1,
                "name": "广绣",
                "introduction": "更新介绍",
                "steps": [self.step(index) for index in range(1, 7)],
                "material_guide": self.material_guide(),
                "sort_order": 1,
                "source_available": True,
                "is_enabled": True,
            },
        )
        with self.app.app_context():
            craft = get_craft_preset_provider().get_craft("guangxiu")
        self.assertEqual(craft["craft_key"], "guangxiu")
        self.assertEqual(len(craft["steps"]), 6)
        self.assertTrue(craft["source_available"])

    def test_disabled_craft_and_success_case_are_not_visible_to_consumers(
        self,
    ):
        self.admin.delete("/api/admin/presets/handcraft_crafts/guangxiu")
        with self.app.app_context():
            self.assertIsNone(
                get_craft_preset_provider().get_craft("guangxiu")
            )

        # Seeded demo cases refuse writes, so the visibility boundary is
        # proven on an admin-created case while the demo cases stay visible.
        created = self.admin.post(
            "/api/admin/presets/success_cases",
            json=self.case_payload(),
        )
        self.assertEqual(created.status_code, 201)
        self.admin.delete("/api/admin/presets/success_cases/case-admin-owned")
        with self.app.app_context():
            provider = get_local_resource_case_provider()
            self.assertIsNone(
                provider.get_success_case("case-admin-owned")
            )
            listed_ids = {
                item["id"] for item in provider.list_success_cases()
            }
        self.assertNotIn("case-admin-owned", listed_ids)
        self.assertIn("case-rice-ecommerce", listed_ids)

    def test_incomplete_steps_with_available_source_make_craft_not_learnable(
        self,
    ):
        self.admin.put(
            "/api/admin/presets/handcraft_crafts/guangxiu",
            json={
                "expected_version": 1,
                "name": "广绣",
                "introduction": "更新介绍",
                "steps": [self.step(index) for index in range(1, 6)],
                "material_guide": self.material_guide(),
                "sort_order": 1,
                "source_available": True,
                "is_enabled": True,
            },
        )
        with self.app.app_context():
            craft = get_craft_preset_provider().get_craft("guangxiu")
        self.assertFalse(craft["available"])
        self.assertTrue(craft["source_available"])

    def test_unavailable_source_with_six_steps_makes_craft_not_learnable(
        self,
    ):
        self.admin.put(
            "/api/admin/presets/handcraft_crafts/guangxiu",
            json={
                "expected_version": 1,
                "name": "广绣",
                "introduction": "更新介绍",
                "steps": [self.step(index) for index in range(1, 7)],
                "material_guide": self.material_guide(),
                "sort_order": 1,
                "source_available": False,
                "is_enabled": True,
            },
        )
        with self.app.app_context():
            craft = get_craft_preset_provider().get_craft("guangxiu")
        self.assertFalse(craft["available"])
        self.assertFalse(craft["source_available"])

    def test_six_step_craft_with_source_available_is_learnable(self):
        self.admin.put(
            "/api/admin/presets/handcraft_crafts/guangxiu",
            json={
                "expected_version": 1,
                "name": "广绣",
                "introduction": "更新介绍",
                "steps": [self.step(index) for index in range(1, 7)],
                "material_guide": self.material_guide(),
                "sort_order": 1,
                "source_available": True,
                "is_enabled": True,
            },
        )
        with self.app.app_context():
            craft = get_craft_preset_provider().get_craft("guangxiu")
        self.assertTrue(craft["available"])
        self.assertEqual(len(craft["steps"]), 6)

    def test_assistant_knowledge_provider_returns_enabled_entries(self):
        with self.app.app_context():
            entries = get_assistant_feature_knowledge_provider().list_entries()
        self.assertEqual(entries[0]["title"], "如何投递简历")
        self.assertTrue(entries[0]["jump_target"])

    def test_knowledge_entries_expose_contract_fields_and_enabled_filter(self):
        self.admin.delete(
            "/api/admin/presets/assistant_knowledge/knowledge-job-application"
        )
        with self.app.app_context():
            provider = get_assistant_feature_knowledge_provider()
            enabled = provider.list_entries()
            everything = provider.list_entries(enabled_only=False)

        self.assertEqual(set(enabled[0]), KNOWLEDGE_ENTRY_FIELDS)
        self.assertTrue(all(entry["is_enabled"] for entry in enabled))
        enabled_ids = {entry["knowledge_id"] for entry in enabled}
        all_ids = {entry["knowledge_id"] for entry in everything}
        self.assertEqual(len(everything), len(enabled) + 1)
        self.assertNotIn("knowledge-job-application", enabled_ids)
        self.assertIn("knowledge-job-application", all_ids)

    def test_knowledge_provider_no_longer_reports_unavailable(self):
        with self.app.app_context():
            entries = get_assistant_feature_knowledge_provider().list_entries()
        self.assertIsInstance(entries, list)
        self.assertTrue(entries)

    def test_craft_list_orders_by_sort_order_then_craft_key(self):
        with self.app.app_context():
            crafts = get_craft_preset_provider().list_crafts()
        self.assertEqual(
            [craft["craft_key"] for craft in crafts],
            ["guangxiu", "craft-alpha", "craft-bravo", "craft-charlie"],
        )
        self.assertEqual(set(crafts[0]), CRAFT_READ_FIELDS)

    def test_success_case_reads_keep_frozen_06_field_shape(self):
        with self.app.app_context():
            provider = get_local_resource_case_provider()
            cases = provider.list_success_cases()
            detail = provider.get_success_case(cases[0]["id"])

        self.assertEqual(
            [item["id"] for item in cases],
            [
                "case-litchi-coop",
                "case-rice-ecommerce",
                "case-bamboo-studio",
            ],
        )
        self.assertEqual(set(detail), CASE_READ_FIELDS)

    def test_disabled_case_stays_readable_for_managers(self):
        created = self.admin.post(
            "/api/admin/presets/success_cases",
            json=self.case_payload(),
        )
        self.assertEqual(created.status_code, 201)
        self.admin.delete("/api/admin/presets/success_cases/case-admin-owned")
        response = self.admin.get("/api/admin/presets/success_cases")
        self.assertEqual(response.status_code, 200)
        items = {
            item["id"]: item
            for item in response.get_json()["items"]
        }
        self.assertIn("case-admin-owned", items)
        self.assertFalse(items["case-admin-owned"]["is_enabled"])
        self.assertFalse(items["case-admin-owned"]["source_available"])
        self.assertEqual(items["case-admin-owned"]["id"], "case-admin-owned")

    def test_created_preset_is_visible_to_consumers_on_next_read(self):
        response = self.admin.post(
            "/api/admin/presets/handcraft_crafts",
            json={
                "craft_key": "yangjiang-lacquerware",
                "name": "阳江漆器",
                "introduction": "阳江漆器的介绍文本。",
                "steps": [self.step(index) for index in range(1, 7)],
                "material_guide": self.material_guide(),
                "sort_order": 9,
                "source_available": True,
            },
        )
        self.assertEqual(response.status_code, 201)
        created = response.get_json()["item"]
        self.assertEqual(created["craft_key"], "yangjiang-lacquerware")
        self.assertEqual(created["version"], 1)
        with self.app.app_context():
            craft = get_craft_preset_provider().get_craft(
                "yangjiang-lacquerware"
            )
        self.assertTrue(craft["available"])

    def test_preset_validation_errors_return_code_message_details(self):
        invalid_payloads = (
            (
                "put",
                "/api/admin/presets/handcraft_crafts/guangxiu",
                {
                    "expected_version": 1,
                    "name": "广绣",
                    "introduction": "更新介绍",
                    "steps": "六步",
                    "material_guide": self.material_guide(),
                    "sort_order": 1,
                    "source_available": True,
                },
            ),
            (
                "put",
                "/api/admin/presets/handcraft_crafts/guangxiu",
                {
                    "expected_version": 1,
                    "name": "广绣",
                    "introduction": "更新介绍",
                    "steps": [
                        {**self.step(1), "title": "  "},
                        *[self.step(index) for index in range(2, 7)],
                    ],
                    "material_guide": self.material_guide(),
                    "sort_order": 1,
                    "source_available": True,
                },
            ),
            (
                "put",
                "/api/admin/presets/handcraft_crafts/guangxiu",
                {
                    "expected_version": 1,
                    "name": "广绣",
                    "introduction": "更新介绍",
                    "steps": [
                        self.step(1),
                        self.step(1),
                        *[self.step(index) for index in range(2, 6)],
                    ],
                    "material_guide": self.material_guide(),
                    "sort_order": 1,
                    "source_available": True,
                },
            ),
            (
                "put",
                "/api/admin/presets/assistant_knowledge/knowledge-job-application",
                {
                    "expected_version": 1,
                    "title": "如何投递简历",
                    "body": "在职位详情中投递。",
                    "feature_key": "unknown_feature",
                    "jump_target": "/student/employment/jobs",
                    "sort_order": 10,
                },
            ),
            (
                "put",
                "/api/admin/presets/success_cases/case-litchi-coop",
                {
                    "expected_version": 1,
                    "title": "荔枝合作社的品牌化起步",
                    "summary": "从分散销售到统一品控。",
                    "background": "种植户规模小。",
                    "journey": "统一采摘标准。",
                    "lessons": "先解决品质一致性。",
                    "sort_order": 10,
                    "published_at": "2026-09-01 08:00:00",
                },
            ),
        )
        for method, path, payload in invalid_payloads:
            with self.subTest(path=path):
                response = getattr(self.admin, method)(path, json=payload)
                self.assertEqual(response.status_code, 400)
                body = response.get_json()
                self.assertEqual(
                    set(body), {"success", "code", "message", "details"}
                )
                self.assertFalse(body["success"])
                self.assertTrue(body["code"])
                self.assertTrue(body["message"])

    def test_stale_expected_version_and_unknown_ids_are_rejected(self):
        stale = self.admin.put(
            "/api/admin/presets/handcraft_crafts/guangxiu",
            json={
                "expected_version": 99,
                "name": "广绣",
                "introduction": "更新介绍",
                "steps": [self.step(index) for index in range(1, 7)],
                "material_guide": self.material_guide(),
                "sort_order": 1,
                "source_available": True,
            },
        )
        self.assertEqual(stale.status_code, 409)
        self.assertEqual(
            stale.get_json()["code"], "craft_preset_version_conflict"
        )

        missing = self.admin.put(
            "/api/admin/presets/handcraft_crafts/missing-craft",
            json={
                "expected_version": 1,
                "name": "不存在的技艺",
                "introduction": "介绍",
                "steps": [self.step(index) for index in range(1, 7)],
                "material_guide": self.material_guide(),
                "sort_order": 1,
                "source_available": True,
            },
        )
        self.assertEqual(missing.status_code, 404)

    def test_only_admin_roles_manage_presets(self):
        for path in (
            "/api/admin/presets/handcraft_crafts",
            "/api/admin/presets/success_cases",
            "/api/admin/presets/assistant_knowledge",
        ):
            with self.subTest(path=path):
                self.assertEqual(
                    self.student.get(path).status_code, 403
                )

        for client in (self.admin, self.super_admin):
            response = client.get("/api/admin/presets/handcraft_crafts")
            self.assertEqual(response.status_code, 200)
            self.assertGreaterEqual(response.get_json()["count"], 1)

    def test_default_admin_services_register_preset_providers(self):
        # FR-104/FR-109: consumers read the slots and never branch on the
        # concrete provider type, so only slot population is asserted here.
        craft_provider = self.app.extensions[
            "handcraft_craft_preset_provider"
        ]
        case_provider = self.app.extensions["local_resource_case_provider"]
        knowledge_provider = self.app.extensions[
            "assistant_feature_knowledge_provider"
        ]
        for provider in (craft_provider, case_provider, knowledge_provider):
            self.assertIsNotNone(provider)

        with self.app.app_context():
            crafts = {
                craft["craft_key"]: craft
                for craft in craft_provider.list_crafts()
            }
            self.assertIsNotNone(craft_provider.get_craft("guangxiu"))
            self.assertIsNone(craft_provider.get_craft("craft-missing"))
            self.assertEqual(
                sorted(crafts),
                [
                    "craft-alpha",
                    "craft-bravo",
                    "craft-charlie",
                    "guangxiu",
                ],
            )
            # Only keys 05 recognises can ever be learnable.
            self.assertTrue(crafts["guangxiu"]["available"])
            self.assertFalse(crafts["craft-alpha"]["available"])
            case_ids = {
                item["id"] for item in case_provider.list_success_cases()
            }
            self.assertIn("case-litchi-coop", case_ids)
            self.assertIsNotNone(
                case_provider.get_success_case("case-litchi-coop")
            )
            self.assertTrue(knowledge_provider.list_entries())

    def test_case_and_knowledge_crud_round_trip(self):
        created_case = self.admin.post(
            "/api/admin/presets/success_cases",
            json={
                "case_id": "case-orchard-coop",
                "title": "果园合作社的统防统治",
                "summary": "统一防控降低成本。",
                "background": "散户防治时机不一致。",
                "journey": "组建合作社统一采购与施药。",
                "lessons": "统一时间节点是关键。",
                "sort_order": 40,
                "published_at": "2026-09-05T08:00:00+08:00",
            },
        )
        self.assertEqual(created_case.status_code, 201)
        case_item = created_case.get_json()["item"]
        self.assertEqual(case_item["id"], "case-orchard-coop")
        self.assertEqual(case_item["published_at"], "2026-09-05T08:00:00+08:00")
        self.assertTrue(case_item["is_enabled"])
        with self.app.app_context():
            self.assertIsNotNone(
                get_local_resource_case_provider().get_success_case(
                    "case-orchard-coop"
                )
            )

        updated_case = self.admin.put(
            "/api/admin/presets/success_cases/case-orchard-coop",
            json={
                "expected_version": 1,
                "title": "果园合作社的统防统治",
                "summary": "统一防控降低成本。",
                "background": "散户防治时机不一致。",
                "journey": "组建合作社统一采购与施药。",
                "lessons": "统一时间节点是关键。",
                "sort_order": 40,
                "published_at": "2026-09-05T08:00:00+08:00",
                "is_enabled": False,
            },
        )
        self.assertEqual(updated_case.status_code, 200)
        self.assertEqual(updated_case.get_json()["item"]["version"], 2)
        with self.app.app_context():
            self.assertIsNone(
                get_local_resource_case_provider().get_success_case(
                    "case-orchard-coop"
                )
            )

        created_knowledge = self.admin.post(
            "/api/admin/presets/assistant_knowledge",
            json={
                "knowledge_id": "knowledge-course-catalog",
                "title": "如何浏览课程目录",
                "body": "在课程目录中按学习方向筛选课程并查看详情后学习。",
                "feature_key": "course_catalog",
                "jump_target": "/student/courses",
                "sort_order": 120,
            },
        )
        self.assertEqual(created_knowledge.status_code, 201)
        self.assertEqual(
            created_knowledge.get_json()["item"]["knowledge_id"],
            "knowledge-course-catalog",
        )
        with self.app.app_context():
            entries = get_assistant_feature_knowledge_provider().list_entries()
        self.assertIn(
            "knowledge-course-catalog",
            {entry["knowledge_id"] for entry in entries},
        )

        disabled = self.admin.delete(
            "/api/admin/presets/assistant_knowledge/knowledge-course-catalog"
        )
        self.assertEqual(disabled.status_code, 200)
        self.assertFalse(disabled.get_json()["item"]["is_enabled"])
        with self.app.app_context():
            provider = get_assistant_feature_knowledge_provider()
            enabled_ids = {
                entry["knowledge_id"] for entry in provider.list_entries()
            }
            all_ids = {
                entry["knowledge_id"]
                for entry in provider.list_entries(enabled_only=False)
            }
        self.assertNotIn("knowledge-course-catalog", enabled_ids)
        self.assertIn("knowledge-course-catalog", all_ids)

    def test_available_matches_frozen_05_rule_over_the_whole_row(self):
        scenarios = (
            ("complete", {}, True),
            ("sort_order_zero", {"sort_order": 0}, False),
            ("empty_material_guide", {"material_guide": []}, False),
            (
                "five_steps",
                {"steps": [self.step(index) for index in range(1, 6)]},
                False,
            ),
            ("source_unavailable", {"source_available": False}, False),
        )
        for label, overrides, expected in scenarios:
            with self.subTest(scenario=label):
                response = self._update_craft("guangxiu", **overrides)
                self.assertEqual(response.status_code, 200, label)
                with self.app.app_context():
                    admin_craft = get_craft_preset_provider().get_craft(
                        "guangxiu"
                    )
                    frozen_craft = get_craft("guangxiu")
                self.assertEqual(admin_craft["available"], expected, label)
                self.assertEqual(frozen_craft["available"], expected, label)
                self.assertEqual(
                    frozen_craft["status"],
                    "available" if expected else "unavailable",
                    label,
                )
                # 05 collapses `source_available` to False for any unusable
                # content, while the admin surface keeps reporting the raw
                # source flag, so the parity invariant is the conjunction.
                self.assertEqual(
                    frozen_craft["source_available"],
                    admin_craft["source_available"] and expected,
                    label,
                )

    def test_craft_key_outside_frozen_05_keys_is_not_learnable(self):
        response = self.admin.post(
            "/api/admin/presets/handcraft_crafts",
            json={
                "craft_key": "craft-unlisted",
                "name": "未列入技艺",
                "introduction": "未列入技艺的介绍文本。",
                "steps": [self.step(index) for index in range(1, 7)],
                "material_guide": self.material_guide(),
                "sort_order": 7,
                "source_available": True,
            },
        )
        self.assertEqual(response.status_code, 201)
        with self.app.app_context():
            admin_craft = get_craft_preset_provider().get_craft(
                "craft-unlisted"
            )
            frozen_craft = get_craft("craft-unlisted")
        self.assertFalse(admin_craft["available"])
        self.assertFalse(frozen_craft["available"])
        self.assertEqual(frozen_craft["status"], "unavailable")
        self.assertFalse(frozen_craft["source_available"])

    def test_body_stable_id_that_differs_from_path_is_rejected(self):
        craft = self._update_craft("guangxiu", craft_key="craft-alpha")
        self.assertEqual(craft.status_code, 400)
        self.assertEqual(craft.get_json()["code"], "craft_key_mismatch")
        with self.app.app_context():
            self.assertIsNotNone(
                get_craft_preset_provider().get_craft("guangxiu")
            )

        knowledge_items = self.admin.get(
            "/api/admin/presets/assistant_knowledge"
        ).get_json()["items"]
        knowledge = next(
            item
            for item in knowledge_items
            if item["knowledge_id"] == "knowledge-job-application"
        )
        knowledge_response = self.admin.put(
            "/api/admin/presets/assistant_knowledge/knowledge-job-application",
            json={
                "expected_version": knowledge["version"],
                "knowledge_id": "knowledge-other",
                "title": knowledge["title"],
                "body": knowledge["body"],
                "feature_key": knowledge["feature_key"],
                "jump_target": knowledge["jump_target"],
                "sort_order": knowledge["sort_order"],
            },
        )
        self.assertEqual(knowledge_response.status_code, 400)
        self.assertEqual(
            knowledge_response.get_json()["code"], "knowledge_id_mismatch"
        )

        created_case = self.admin.post(
            "/api/admin/presets/success_cases",
            json=self.case_payload(),
        )
        self.assertEqual(created_case.status_code, 201)
        case_response = self.admin.put(
            "/api/admin/presets/success_cases/case-admin-owned",
            json={
                **self.case_payload(),
                "case_id": "case-other",
                "expected_version": 1,
            },
        )
        self.assertEqual(case_response.status_code, 400)
        self.assertEqual(case_response.get_json()["code"], "case_id_mismatch")

    def test_delete_accepts_optional_expected_version(self):
        created_case = self.admin.post(
            "/api/admin/presets/success_cases",
            json=self.case_payload(),
        )
        self.assertEqual(created_case.status_code, 201)

        stale_paths = (
            "/api/admin/presets/handcraft_crafts/guangxiu?expected_version=99",
            "/api/admin/presets/success_cases/case-admin-owned"
            "?expected_version=99",
            "/api/admin/presets/assistant_knowledge/"
            "knowledge-job-application?expected_version=99",
        )
        for path in stale_paths:
            with self.subTest(path=path):
                response = self.admin.delete(path)
                self.assertEqual(response.status_code, 409)
                self.assertEqual(
                    set(response.get_json()),
                    {"success", "code", "message", "details"},
                )

        accepted_paths = (
            "/api/admin/presets/handcraft_crafts/guangxiu?expected_version=1",
            "/api/admin/presets/success_cases/case-admin-owned"
            "?expected_version=1",
            "/api/admin/presets/assistant_knowledge/"
            "knowledge-job-application?expected_version=1",
        )
        for path in accepted_paths:
            with self.subTest(path=path):
                response = self.admin.delete(path)
                self.assertEqual(response.status_code, 200)
                self.assertFalse(response.get_json()["item"]["is_enabled"])

    def test_platform_timestamp_normalizes_utc_offsets_to_shanghai(self):
        from app.admin_console.presets import _platform_timestamp

        for raw in ("2026-09-05T00:00:00Z", "2026-09-05T00:00:00+00:00"):
            with self.subTest(raw=raw):
                self.assertEqual(
                    _platform_timestamp(raw, field="published_at"),
                    "2026-09-05T08:00:00+08:00",
                )

    def test_seeded_demo_case_update_and_delete_are_refused(self):
        created_case = self.admin.post(
            "/api/admin/presets/success_cases",
            json=self.case_payload(),
        )
        self.assertEqual(created_case.status_code, 201)

        with self.app.app_context():
            before = dict(
                get_db()
                .execute(
                    """
                    SELECT title, version, is_enabled, is_demo
                    FROM local_resource_success_cases
                    WHERE case_id = 'case-litchi-coop'
                    """
                )
                .fetchone()
            )

        for method, path in (
            ("put", "/api/admin/presets/success_cases/case-litchi-coop"),
            ("delete", "/api/admin/presets/success_cases/case-litchi-coop"),
        ):
            with self.subTest(method=method):
                response = getattr(self.admin, method)(
                    path,
                    json={
                        **self.case_payload(),
                        "case_id": "case-litchi-coop",
                        "title": "试图改写演示案例",
                        "expected_version": int(before["version"]),
                    },
                )
                self.assertEqual(response.status_code, 400)
                body = response.get_json()
                self.assertEqual(body["code"], "demo_case_not_editable")
                self.assertIn("新建案例", body["message"])

        with self.app.app_context():
            after = dict(
                get_db()
                .execute(
                    """
                    SELECT title, version, is_enabled, is_demo
                    FROM local_resource_success_cases
                    WHERE case_id = 'case-litchi-coop'
                    """
                )
                .fetchone()
            )
            # Reads of demo rows are still allowed.
            self.assertIsNotNone(
                get_local_resource_case_provider().get_success_case(
                    "case-litchi-coop"
                )
            )
        self.assertEqual(after, before)

    def test_delete_without_expected_version_still_works(self):
        response = self.admin.delete(
            "/api/admin/presets/handcraft_crafts/guangxiu"
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.get_json()["item"]["is_enabled"])


class SeededCraftPresetTests(TestCase):
    """011 owns the craft slot, so `init_db()` seeds manageable demo rows."""

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

    def test_seed_turns_the_four_demo_crafts_into_manageable_rows(self):
        with self.app.app_context():
            items = list_craft_presets()
            listed = get_craft_preset_provider().list_crafts()

        self.assertEqual(
            [item["craft_key"] for item in items],
            [
                "guangxiu",
                "chaoshan-woodcarving",
                "shiwan-ceramics",
                "yangjiang-lacquerware",
            ],
        )
        self.assertEqual(
            [craft["craft_key"] for craft in listed],
            [item["craft_key"] for item in items],
        )
        for item in items:
            with self.subTest(craft_key=item["craft_key"]):
                self.assertTrue(item["is_demo"])
                self.assertTrue(item["is_enabled"])
                self.assertTrue(item["available"])
                self.assertEqual(len(item["steps"]), 6)
                self.assertTrue(item["material_guide"])
                self.assertGreater(item["sort_order"], 0)

    def test_admin_edit_to_a_seeded_demo_craft_survives_restart(self):
        with self.app.app_context():
            update_craft_preset(
                1,
                "guangxiu",
                {
                    "expected_version": 1,
                    "name": "广绣（管理员修订）",
                    "introduction": "管理员修订后的介绍文本。",
                    "steps": [
                        {
                            "step_key": f"guangxiu-{index:02d}",
                            "step_no": index,
                            "title": f"步骤 {index}",
                            "description": f"第 {index} 步的操作说明。",
                            "tips": [f"提示 {index}"],
                        }
                        for index in range(1, 7)
                    ],
                    "material_guide": [
                        {
                            "name": "真丝绣线",
                            "reference_price": "20-40 元/束",
                            "purchase_channel": "广州绣品市场",
                            "precautions": "按色系分批采购。",
                            "taobao_keyword": "广绣真丝绣线",
                        }
                    ],
                    "sort_order": 1,
                    "source_available": True,
                    "is_enabled": True,
                },
            )
            init_db()
            row = (
                get_db()
                .execute(
                    """
                    SELECT name, version, is_demo
                    FROM admin_handcraft_crafts
                    WHERE craft_key = 'guangxiu'
                    """
                )
                .fetchone()
            )
        self.assertEqual(row["name"], "广绣（管理员修订）")
        self.assertEqual(int(row["version"]), 2)
        self.assertEqual(int(row["is_demo"]), 1)

    def test_disabling_a_seeded_demo_craft_survives_restart(self):
        with self.app.app_context():
            disable_craft_preset(1, "guangxiu")
            init_db()
            provider = get_craft_preset_provider()
            self.assertIsNone(provider.get_craft("guangxiu"))
            self.assertEqual(
                [craft["craft_key"] for craft in provider.list_crafts()],
                [
                    "chaoshan-woodcarving",
                    "shiwan-ceramics",
                    "yangjiang-lacquerware",
                ],
            )
            guangxiu = next(
                item
                for item in list_craft_presets()
                if item["craft_key"] == "guangxiu"
            )
        self.assertFalse(guangxiu["is_enabled"])

    def test_empty_craft_table_yields_no_placeholder_content(self):
        with self.app.app_context():
            get_db().execute("DELETE FROM admin_handcraft_crafts")
            get_db().commit()
            provider = get_craft_preset_provider()
            self.assertEqual(provider.list_crafts(), [])
            self.assertIsNone(provider.get_craft("guangxiu"))

            learner_crafts = list_crafts()
        self.assertEqual(
            [craft["craft_key"] for craft in learner_crafts],
            [
                "guangxiu",
                "chaoshan-woodcarving",
                "shiwan-ceramics",
                "yangjiang-lacquerware",
            ],
        )
        self.assertTrue(
            all(not craft["available"] for craft in learner_crafts)
        )


class CraftPresetConcurrencyTests(TestCase):
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

    @staticmethod
    def _payload(name: str, expected_version: int) -> dict:
        return {
            "expected_version": expected_version,
            "name": name,
            "introduction": f"{name}的介绍文本。",
            "steps": [
                {
                    "step_key": f"guangxiu-{index:02d}",
                    "step_no": index,
                    "title": f"步骤 {index}",
                    "description": f"第 {index} 步的操作说明。",
                    "tips": [f"提示 {index}"],
                }
                for index in range(1, 7)
            ],
            "material_guide": [
                {
                    "name": "真丝绣线",
                    "reference_price": "20-40 元/束",
                    "purchase_channel": "广州绣品市场",
                    "precautions": "按色系分批采购。",
                    "taobao_keyword": "广绣真丝绣线",
                }
            ],
            "sort_order": 1,
            "source_available": True,
            "is_enabled": True,
        }

    def test_concurrent_updates_raise_409_instead_of_losing_the_first_edit(
        self,
    ):
        with self.app.app_context():
            starting_version = int(
                get_db()
                .execute(
                    """
                    SELECT version FROM admin_handcraft_crafts
                    WHERE craft_key = 'guangxiu'
                    """
                )
                .fetchone()["version"]
            )
        self.assertEqual(starting_version, 1)

        # Both admins read version 1 before either one writes, which is the
        # precondition for the lost update the old read-then-write allowed.
        barrier = threading.Barrier(2)
        outcomes: list[tuple[str, str]] = []
        outcomes_lock = threading.Lock()

        def submit(name: str) -> None:
            with self.app.app_context():
                barrier.wait(timeout=10)
                try:
                    update_craft_preset(
                        1,
                        "guangxiu",
                        self._payload(name, starting_version),
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
                    SELECT name, version FROM admin_handcraft_crafts
                    WHERE craft_key = 'guangxiu'
                    """
                )
                .fetchone()
            )
        self.assertEqual(int(row["version"]), starting_version + 1)
        self.assertEqual(row["name"], winner)


class DemoCaseBoundaryTests(TestCase):
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
        self.admin = self._login("demo-boundary-admin", "admin")

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
                    "2026-09-20T10:00:00+08:00",
                    "2026-09-20T10:00:00+08:00",
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

    def test_admin_created_case_survives_restart_with_edits(self):
        created = self.admin.post(
            "/api/admin/presets/success_cases",
            json={
                "case_id": "case-admin-owned",
                "title": "果园合作社的统防统治",
                "summary": "统一防控降低成本。",
                "background": "散户防治时机不一致。",
                "journey": "组建合作社统一采购与施药。",
                "lessons": "统一时间节点是关键。",
                "sort_order": 40,
                "published_at": "2026-09-05T08:00:00+08:00",
            },
        )
        self.assertEqual(created.status_code, 201)

        updated = self.admin.put(
            "/api/admin/presets/success_cases/case-admin-owned",
            json={
                "expected_version": 1,
                "title": "果园合作社的统防统治（修订）",
                "summary": "统一防控降低成本。",
                "background": "散户防治时机不一致。",
                "journey": "组建合作社统一采购与施药。",
                "lessons": "统一时间节点是关键。",
                "sort_order": 40,
                "published_at": "2026-09-05T08:00:00+08:00",
            },
        )
        self.assertEqual(updated.status_code, 200)

        with self.app.app_context():
            init_db()
            row = (
                get_db()
                .execute(
                    """
                    SELECT title, version, is_demo
                    FROM local_resource_success_cases
                    WHERE case_id = 'case-admin-owned'
                    """
                )
                .fetchone()
            )
            detail = get_local_resource_case_provider().get_success_case(
                "case-admin-owned"
            )

        self.assertEqual(int(row["is_demo"]), 0)
        self.assertEqual(int(row["version"]), 2)
        self.assertEqual(row["title"], "果园合作社的统防统治（修订）")
        self.assertEqual(detail["title"], "果园合作社的统防统治（修订）")

    def test_frozen_seeder_reverts_demo_case_edits_on_restart(self):
        with self.app.app_context():
            get_db().execute(
                """
                UPDATE local_resource_success_cases
                SET title = '绕过 provider 直接改库'
                WHERE case_id = 'case-litchi-coop'
                """
            )
            get_db().commit()
            init_db()
            row = (
                get_db()
                .execute(
                    """
                    SELECT title FROM local_resource_success_cases
                    WHERE case_id = 'case-litchi-coop'
                    """
                )
                .fetchone()
            )
        self.assertEqual(row["title"], "荔枝合作社的品牌化起步")


class AgriPresetTests(TestCase):
    """011 owns the 03 `agri_preset_provider` slot and its preset tables."""

    AGRI_PRESET_PATHS = (
        "/api/admin/presets/agri_products",
        "/api/admin/presets/agri_calendar",
        "/api/admin/presets/pest_knowledge",
    )

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
        self.super_admin = self._login("agri-super-admin", "super_admin")
        self.admin = self._login("agri-admin", "admin")
        self.student = self._login("agri-student", "student")

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
                    "2026-09-20T10:00:00+08:00",
                    "2026-09-20T10:00:00+08:00",
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

    def test_seeded_agri_content_matches_03_placeholder_field_for_field(self):
        from app.agri_skills.presets import (
            PlaceholderPresetProvider,
            get_preset_provider,
        )

        placeholder = PlaceholderPresetProvider()
        with self.app.app_context():
            provider = get_preset_provider()

            self.assertEqual(
                provider.list_products(),
                placeholder.list_products(),
            )
            self.assertEqual(
                [product["key"] for product in provider.list_products()],
                ["litchi", "longan", "aquaculture"],
            )
            self.assertEqual(
                set(provider.list_products()[0]),
                {"key", "name", "sort_order"},
            )
            self.assertEqual(
                provider.get_product("litchi"),
                placeholder.get_product("litchi"),
            )
            self.assertIsNone(provider.get_product("missing-product"))
            for month in (4, 5):
                with self.subTest(month=month):
                    self.assertEqual(
                        provider.get_calendar_entry("litchi", month),
                        placeholder.get_calendar_entry("litchi", month),
                    )
            self.assertEqual(
                provider.list_calendar_entries("litchi"),
                placeholder.list_calendar_entries("litchi"),
            )
            self.assertEqual(
                [
                    entry["month"]
                    for entry in provider.list_calendar_entries("litchi")
                ],
                [4, 5],
            )
            self.assertEqual(
                set(provider.list_calendar_entries("litchi")[0]),
                {
                    "month",
                    "tasks",
                    "management",
                    "solar_terms",
                    "reminder",
                },
            )
            self.assertEqual(
                provider.list_pest_entries(),
                placeholder.list_pest_entries(),
            )
            self.assertEqual(
                [entry["id"] for entry in provider.list_pest_entries()],
                ["litchi-stem-borer", "litchi-downy-blight"],
            )
            self.assertEqual(
                set(provider.list_pest_entries()[0]),
                {
                    "id",
                    "sort_order",
                    "pest_name",
                    "product_names",
                    "symptoms",
                    "aliases",
                    "answer",
                },
            )

    def test_create_app_installs_database_agri_preset_provider(self):
        from app.admin_console.presets import (
            DatabaseAgriPresetContentProvider,
        )
        from app.agri_skills.presets import get_preset_provider

        with self.app.app_context():
            # `create_app` runs 03's install before 011's, so the slot only
            # reaches the database provider if the 011 install replaces it
            # unconditionally.
            self.assertIsInstance(
                get_preset_provider(),
                DatabaseAgriPresetContentProvider,
            )

    def test_admin_install_replaces_03_placeholder_preset_provider(self):
        from app.admin_console.presets import (
            DatabaseAgriPresetContentProvider,
        )
        from app.admin_console.providers import (
            install_default_admin_services,
        )
        from app.agri_skills.presets import (
            PlaceholderPresetProvider,
            get_preset_provider,
            set_preset_provider,
        )

        set_preset_provider(self.app, PlaceholderPresetProvider())
        install_default_admin_services(self.app)
        with self.app.app_context():
            provider = get_preset_provider()
            self.assertIsInstance(
                provider,
                DatabaseAgriPresetContentProvider,
            )
            self.assertNotIsInstance(provider, PlaceholderPresetProvider)
            self.assertEqual(
                [product["key"] for product in provider.list_products()],
                ["litchi", "longan", "aquaculture"],
            )

    def test_agri_calendar_edit_is_visible_to_03_on_next_read(self):
        from app.agri_skills.calendar import get_calendar
        from app.agri_skills.presets import get_preset_provider

        response = self.admin.put(
            "/api/admin/presets/agri_calendar/calendar-litchi-4",
            json={
                "expected_version": 1,
                "product_key": "litchi",
                "month": 4,
                "tasks": ["保果施肥"],
                "management": ["及时排水"],
                "solar_terms": ["清明", "谷雨"],
                "reminder": "更新后的提示",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["item"]["version"], 2)
        with self.app.app_context():
            entry = get_preset_provider().get_calendar_entry("litchi", 4)
            calendar = get_calendar("litchi", 4)
        self.assertEqual(entry["reminder"], "更新后的提示")
        self.assertEqual(entry["tasks"], ["保果施肥"])
        self.assertEqual(entry["management"], ["及时排水"])
        self.assertEqual(calendar["reminder"], "更新后的提示")
        self.assertIsNone(calendar["empty_state"])

    def test_agri_product_crud_roundtrip_and_provider_visibility(self):
        created = self.admin.post(
            "/api/admin/presets/agri_products",
            json={"product_key": "mango", "name": "芒果", "sort_order": 4},
        )
        self.assertEqual(created.status_code, 201)
        item = created.get_json()["item"]
        self.assertEqual(item["product_key"], "mango")
        self.assertEqual(item["version"], 1)
        self.assertTrue(item["is_enabled"])
        self.assertTrue(item["created_at"].endswith("+08:00"))

        updated = self.admin.put(
            "/api/admin/presets/agri_products/mango",
            json={
                "expected_version": 1,
                "name": "芒果（修订）",
                "sort_order": 6,
            },
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.get_json()["item"]["version"], 2)

        with self.app.app_context():
            from app.agri_skills.presets import get_preset_provider

            provider = get_preset_provider()
            self.assertEqual(
                provider.get_product("mango"),
                {"key": "mango", "name": "芒果（修订）", "sort_order": 6},
            )
            self.assertIn(
                "mango",
                [product["key"] for product in provider.list_products()],
            )

        deleted = self.admin.delete("/api/admin/presets/agri_products/mango")
        self.assertEqual(deleted.status_code, 200)
        self.assertFalse(deleted.get_json()["item"]["is_enabled"])
        self.assertEqual(deleted.get_json()["item"]["version"], 3)

        with self.app.app_context():
            from app.agri_skills.presets import get_preset_provider

            provider = get_preset_provider()
            self.assertIsNone(provider.get_product("mango"))
            self.assertNotIn(
                "mango",
                [product["key"] for product in provider.list_products()],
            )

        # The logical delete keeps the stable key, so a recreate is refused
        # as a conflict instead of silently shadowing the old row.
        again = self.admin.post(
            "/api/admin/presets/agri_products",
            json={"product_key": "mango", "name": "芒果", "sort_order": 4},
        )
        self.assertEqual(again.status_code, 409)
        self.assertEqual(
            again.get_json()["code"], "agri_product_preset_conflict"
        )

    def test_agri_calendar_duplicate_month_returns_conflict(self):
        duplicate = self.admin.post(
            "/api/admin/presets/agri_calendar",
            json={
                "product_key": "litchi",
                "month": 4,
                "tasks": ["保果施肥"],
                "management": ["保持果园通风"],
                "solar_terms": ["清明"],
                "reminder": "重复的四月",
            },
        )
        self.assertEqual(duplicate.status_code, 409)
        body = duplicate.get_json()
        self.assertEqual(body["code"], "agri_calendar_preset_conflict")
        self.assertEqual(
            set(body),
            {"success", "code", "message", "details"},
        )
        self.assertEqual(body["details"]["item_id"], "calendar-litchi-4")
        self.assertEqual(body["details"]["month"], 4)

        fresh = self.admin.post(
            "/api/admin/presets/agri_calendar",
            json={
                "product_key": "litchi",
                "month": 6,
                "tasks": ["采后修剪"],
                "management": ["控梢促花"],
                "solar_terms": ["夏至"],
                "reminder": "采后恢复",
            },
        )
        self.assertEqual(fresh.status_code, 201)
        self.assertEqual(fresh.get_json()["item"]["item_id"], "calendar-litchi-6")
        with self.app.app_context():
            from app.agri_skills.presets import get_preset_provider

            entry = get_preset_provider().get_calendar_entry("litchi", 6)
        self.assertEqual(entry["reminder"], "采后恢复")

    def test_pest_knowledge_crud_roundtrip_and_provider_visibility(self):
        created = self.admin.post(
            "/api/admin/presets/pest_knowledge",
            json={
                "item_id": "litchi-fruit-moth",
                "sort_order": 5,
                "pest_name": "荔枝果实蛾",
                "product_names": ["荔枝"],
                "symptoms": ["虫蛀", "落果"],
                "aliases": ["果实蛾"],
                "answer": "及时清理落果并轮换用药。",
            },
        )
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.get_json()["item"]["version"], 1)

        updated = self.admin.put(
            "/api/admin/presets/pest_knowledge/litchi-fruit-moth",
            json={
                "expected_version": 1,
                "sort_order": 5,
                "pest_name": "荔枝果实蛾",
                "product_names": ["荔枝"],
                "symptoms": ["虫蛀"],
                "aliases": ["果实蛾"],
                "answer": "修订后的防治建议。",
            },
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.get_json()["item"]["version"], 2)
        self.assertEqual(
            updated.get_json()["item"]["symptoms"], ["虫蛀"]
        )

        with self.app.app_context():
            from app.agri_skills.presets import get_preset_provider
            from app.agri_skills.qa import select_local_knowledge_entry

            listed = get_preset_provider().list_pest_entries()
            self.assertEqual(
                [entry["id"] for entry in listed],
                [
                    "litchi-stem-borer",
                    "litchi-downy-blight",
                    "litchi-fruit-moth",
                ],
            )
            # 03's offline Q&A still ranks the seeded rows by itself.
            entry = select_local_knowledge_entry("荔枝蒂蛀虫导致落果")
        self.assertEqual(entry["id"], "litchi-stem-borer")

        deleted = self.admin.delete(
            "/api/admin/presets/pest_knowledge/litchi-fruit-moth"
        )
        self.assertEqual(deleted.status_code, 200)
        with self.app.app_context():
            from app.agri_skills.presets import get_preset_provider

            self.assertEqual(
                [
                    entry["id"]
                    for entry in get_preset_provider().list_pest_entries()
                ],
                ["litchi-stem-borer", "litchi-downy-blight"],
            )

    def test_disabled_agri_rows_are_invisible_to_consumers_and_stay_readable(
        self,
    ):
        from app.agri_skills.calendar import get_calendar
        from app.agri_skills.presets import get_preset_provider

        for path in (
            "/api/admin/presets/agri_calendar/calendar-litchi-4",
            "/api/admin/presets/pest_knowledge/litchi-stem-borer",
            "/api/admin/presets/agri_products/aquaculture",
        ):
            with self.subTest(path=path):
                response = self.admin.delete(path)
                self.assertEqual(response.status_code, 200)
                self.assertFalse(response.get_json()["item"]["is_enabled"])

        with self.app.app_context():
            provider = get_preset_provider()
            self.assertIsNone(provider.get_calendar_entry("litchi", 4))
            self.assertIsNone(provider.get_product("aquaculture"))
            self.assertEqual(
                [entry["id"] for entry in provider.list_pest_entries()],
                ["litchi-downy-blight"],
            )
            self.assertEqual(
                [
                    entry["month"]
                    for entry in provider.list_calendar_entries("litchi")
                ],
                [5],
            )
            self.assertEqual(
                [product["key"] for product in provider.list_products()],
                ["litchi", "longan"],
            )
            # 03's consumer reports the empty month instead of the content
            # the console just disabled.
            self.assertEqual(
                get_calendar("litchi", 4)["empty_state"], "当月无该产品农时"
            )

        # Disabled rows stay readable for managers, stable IDs included.
        calendar_items = {
            item["item_id"]: item
            for item in self.admin.get(
                "/api/admin/presets/agri_calendar"
            ).get_json()["items"]
        }
        pest_items = {
            item["item_id"]: item
            for item in self.admin.get(
                "/api/admin/presets/pest_knowledge"
            ).get_json()["items"]
        }
        product_items = {
            item["product_key"]: item
            for item in self.admin.get(
                "/api/admin/presets/agri_products"
            ).get_json()["items"]
        }
        self.assertIn("calendar-litchi-4", calendar_items)
        self.assertFalse(calendar_items["calendar-litchi-4"]["is_enabled"])
        self.assertIn("litchi-stem-borer", pest_items)
        self.assertFalse(pest_items["litchi-stem-borer"]["is_enabled"])
        self.assertIn("aquaculture", product_items)
        self.assertFalse(product_items["aquaculture"]["is_enabled"])

    def test_agri_preset_stale_expected_version_returns_409(self):
        stale_update = self.admin.put(
            "/api/admin/presets/agri_products/litchi",
            json={
                "expected_version": 99,
                "name": "荔枝",
                "sort_order": 1,
            },
        )
        self.assertEqual(stale_update.status_code, 409)
        self.assertEqual(
            stale_update.get_json()["code"],
            "agri_product_preset_version_conflict",
        )

        stale_delete = self.admin.delete(
            "/api/admin/presets/agri_calendar/calendar-litchi-4"
            "?expected_version=99"
        )
        self.assertEqual(stale_delete.status_code, 409)
        self.assertEqual(
            stale_delete.get_json()["code"],
            "agri_calendar_preset_version_conflict",
        )

        with self.app.app_context():
            from app.agri_skills.presets import get_preset_provider

            # Neither stale write landed, so 03 still reads the seed.
            entry = get_preset_provider().get_calendar_entry("litchi", 4)
            product = get_preset_provider().get_product("litchi")
        self.assertEqual(entry["reminder"], "荔枝正值保果关键期")
        self.assertEqual(product["name"], "荔枝")

    def test_agri_preset_routes_allow_both_admin_roles(self):
        for client in (self.admin, self.super_admin):
            for path in self.AGRI_PRESET_PATHS:
                with self.subTest(path=path):
                    response = client.get(path)
                    self.assertEqual(response.status_code, 200)
                    body = response.get_json()
                    self.assertTrue(body["success"])
                    self.assertEqual(body["count"], len(body["items"]))

        listed = self.super_admin.get(
            "/api/admin/presets/agri_products"
        ).get_json()["items"]
        self.assertEqual(len(listed), 3)
        listed = self.super_admin.get(
            "/api/admin/presets/agri_calendar"
        ).get_json()["items"]
        self.assertEqual(len(listed), 2)
        listed = self.super_admin.get(
            "/api/admin/presets/pest_knowledge"
        ).get_json()["items"]
        self.assertEqual(len(listed), 2)

    def test_agri_preset_routes_reject_student_and_anonymous(self):
        for path in self.AGRI_PRESET_PATHS:
            with self.subTest(path=path):
                self.assertEqual(self.student.get(path).status_code, 403)
                anonymous = self.app.test_client()
                response = anonymous.get(path)
                self.assertEqual(response.status_code, 401)
                self.assertFalse(response.get_json()["success"])

    def test_agri_preset_validation_errors(self):
        cases = (
            (
                "post",
                "/api/admin/presets/agri_products",
                {"product_key": "Bad Key", "name": "农产品"},
                "preset_validation_failed",
            ),
            (
                "post",
                "/api/admin/presets/agri_calendar",
                {
                    "product_key": "litchi",
                    "month": 13,
                    "tasks": [],
                    "management": [],
                    "solar_terms": [],
                    "reminder": "越界的月份",
                },
                "preset_validation_failed",
            ),
            (
                "post",
                "/api/admin/presets/pest_knowledge",
                {
                    "item_id": "bad id!",
                    "pest_name": "病虫害",
                    "product_names": ["荔枝"],
                    "symptoms": ["虫蛀"],
                    "aliases": [],
                    "answer": "防治建议。",
                },
                "preset_validation_failed",
            ),
            (
                "put",
                "/api/admin/presets/agri_calendar/calendar-litchi-4",
                {
                    "expected_version": 1,
                    "product_key": "litchi",
                    "month": 9,
                    "tasks": [],
                    "management": [],
                    "solar_terms": [],
                    "reminder": "试图改成九月",
                },
                "month_mismatch",
            ),
            (
                "put",
                "/api/admin/presets/agri_calendar/calendar-litchi-4",
                {
                    "expected_version": 1,
                    "product_key": "longan",
                    "month": 4,
                    "tasks": [],
                    "management": [],
                    "solar_terms": [],
                    "reminder": "试图挂到龙眼名下",
                },
                "product_key_mismatch",
            ),
            (
                "put",
                "/api/admin/presets/pest_knowledge/litchi-stem-borer",
                {
                    "expected_version": 1,
                    "item_id": "litchi-other-borer",
                    "sort_order": 1,
                    "pest_name": "荔枝蒂蛀虫",
                    "product_names": ["荔枝"],
                    "symptoms": ["虫蛀", "落果"],
                    "aliases": ["蒂蛀虫", "蛀果"],
                    "answer": "及时清理落果，重点保护果实和结果母枝，"
                    "并按当地规范轮换用药。",
                },
                "item_id_mismatch",
            ),
        )
        for method, path, payload, expected_code in cases:
            with self.subTest(path=path):
                response = getattr(self.admin, method)(path, json=payload)
                self.assertEqual(response.status_code, 400)
                body = response.get_json()
                self.assertEqual(
                    set(body),
                    {"success", "code", "message", "details"},
                )
                self.assertFalse(body["success"])
                self.assertEqual(body["code"], expected_code)


if __name__ == "__main__":
    unittest.main()
