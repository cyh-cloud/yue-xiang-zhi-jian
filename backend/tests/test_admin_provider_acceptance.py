"""011 cross-module provider contract acceptance.

011 installs database-backed providers into the extension slots that 03, 05,
06, 08 and 09 already read through their own getters. Two properties have to
hold at the same time: replacing a slot is the only step a consumer feature
ever needs, so every consumer call site and signature stays frozen; and 011's
defaults beat the placeholders the other modules install earlier in
`create_app`, because a slot guard would silently leave 011 disabled.
"""

from __future__ import annotations

import ast
import inspect
import tempfile
import unittest
from collections import defaultdict
from pathlib import Path

from flask import Flask
from werkzeug.security import generate_password_hash

from app import create_app
from app.admin_console.content_review_service import (
    approve_review,
    list_review_queue,
)
from app.admin_console.providers import (
    AdminDatabaseLocalResourceCaseProvider,
    AssistantFeatureKnowledgeProvider,
    CompositeContentReviewProvider,
    ContentReviewProvider,
    DatabaseAgriPresetContentProvider,
    DatabaseAssistantFeatureKnowledgeProvider,
    DatabaseCraftPresetProvider,
    DatabaseFeedbackIntakeProvider,
    DatabasePointsPolicyProvider,
    DatabaseRewardCatalogProvider,
    FeedbackIntakeProvider,
    configure_admin_providers,
    get_assistant_feature_knowledge_provider,
    get_feedback_intake_provider,
    install_default_admin_services,
)
from app.agri_skills.calendar import get_calendar, list_products
from app.agri_skills.diagnosis import get_diagnosis
from app.agri_skills.providers import PresetContentProvider
from app.agri_skills.qa import select_local_knowledge_entry
from app.content_review import (
    ContentReviewProvider,
    UnavailableContentReviewProvider,
)
from app.db import get_db
from app.enterprise_console.jobs import create_job
from app.handcraft_inheritance import (
    CraftPresetProvider,
    PointsPolicyProvider,
    RewardCatalogProvider,
)
from app.handcraft_inheritance.crafts import list_crafts
from app.handcraft_inheritance.points import get_effective_policy
from app.handcraft_inheritance.rewards import list_rewards
from app.local_resources.cases import (
    LocalResourceCaseProvider,
)


CRAFT_STEP_COUNT = 6
REVIEW_TIMESTAMP = "2026-09-22T09:00:00+08:00"


class ReplacementReviewProvider:
    """Complete `ContentReviewProvider` plus the queue read the console uses.

    `list_review_items` is called by `content_review_service.list_review_queue`
    even though the `ContentReviewProvider` protocol does not declare it, so a
    replacement has to carry it for the 09 consumer path to stay real.
    """

    def __init__(self):
        self.records = {}
        self.calls = []

    def submit_for_review(
        self,
        *,
        content_type,
        content_id,
        submitter_id,
        expected_version,
        payload,
    ):
        return self._write(
            "submit_for_review",
            {
                "content_type": content_type,
                "content_id": content_id,
                "submitter_id": submitter_id,
                "expected_version": expected_version,
                "payload": dict(payload),
            },
        )

    def get_review_status(self, *, content_type, content_id):
        self.calls.append(
            {
                "method": "get_review_status",
                "content_type": content_type,
                "content_id": content_id,
            }
        )
        record = self.records.get(content_id)
        return dict(record) if record is not None else None

    def approve(
        self,
        *,
        content_type,
        content_id,
        submitter_id,
        reviewer_id,
        reviewer_role,
        expected_version,
    ):
        return self._write(
            "approve",
            {
                "content_type": content_type,
                "content_id": content_id,
                "submitter_id": submitter_id,
                "reviewer_id": reviewer_id,
                "reviewer_role": reviewer_role,
                "expected_version": expected_version,
            },
        )

    def reject(
        self,
        *,
        content_type,
        content_id,
        submitter_id,
        reviewer_id,
        reviewer_role,
        expected_version,
        opinion,
    ):
        return self._write(
            "reject",
            {
                "content_type": content_type,
                "content_id": content_id,
                "submitter_id": submitter_id,
                "reviewer_id": reviewer_id,
                "reviewer_role": reviewer_role,
                "expected_version": expected_version,
                "opinion": opinion,
            },
        )

    def edit(
        self,
        *,
        content_type,
        content_id,
        submitter_id,
        expected_version,
        payload,
    ):
        return self._write(
            "edit",
            {
                "content_type": content_type,
                "content_id": content_id,
                "submitter_id": submitter_id,
                "expected_version": expected_version,
                "payload": dict(payload),
            },
        )

    def list_review_items(self, content_type=None):
        self.calls.append(
            {"method": "list_review_items", "content_type": content_type}
        )
        return [dict(record) for record in self.records.values()]

    def _write(self, method, fields):
        self.calls.append({"method": method, **fields})
        record = {
            "content_type": fields["content_type"],
            "content_id": fields["content_id"],
            "submitter_id": fields["submitter_id"],
            "review_status": {
                "approve": "approved",
                "reject": "rejected",
            }.get(method, "pending"),
            "version": fields["expected_version"],
            "rejection_opinion": fields.get("opinion"),
            "published_at": None,
            "created_at": REVIEW_TIMESTAMP,
            "updated_at": REVIEW_TIMESTAMP,
        }
        self.records[str(fields["content_id"])] = record
        return dict(record)


class ReplacementPointsPolicyProvider:
    def __init__(self):
        self.calls = []

    def get_policy(self):
        self.calls.append("get_policy")
        return {
            "version": "replacement-policy",
            "seconds_per_point": 600,
            "daily_limit": 60,
            "expiry_mode": "permanent",
            "training_weights": {"default": 10},
            "is_demo": False,
        }


class ReplacementRewardCatalogProvider:
    def __init__(self):
        self.calls = []

    def list_rewards(self):
        self.calls.append("list_rewards")
        return [
            {
                "reward_id": "replacement-reward",
                "name": "替换奖品",
                "points_cost": 100,
                "stock": 5,
                "is_online": True,
                "is_demo": False,
                "source_available": True,
            }
        ]

    def reserve_stock(self, reward_id, quantity, reservation_id):
        self.calls.append(
            {
                "method": "reserve_stock",
                "reward_id": reward_id,
                "quantity": quantity,
                "reservation_id": reservation_id,
            }
        )
        return f"reservation-{reservation_id}"

    def release_stock(self, reservation_id):
        self.calls.append(
            {"method": "release_stock", "reservation_id": reservation_id}
        )
        return True


class ReplacementAgriPresetProvider:
    def __init__(self):
        self.calls = []

    def list_products(self):
        self.calls.append("list_products")
        return [
            {"key": "replacement-litchi", "name": "替换荔枝", "sort_order": 1},
            {"key": "replacement-longan", "name": "替换龙眼", "sort_order": 2},
        ]

    def get_product(self, product_key):
        self.calls.append({"method": "get_product", "key": product_key})
        product = next(
            (
                item
                for item in self.list_products()
                if item["key"] == product_key
            ),
            None,
        )
        return dict(product) if product is not None else None

    def get_calendar_entry(self, product_key, month):
        self.calls.append(
            {
                "method": "get_calendar_entry",
                "key": product_key,
                "month": month,
            }
        )
        if product_key != "replacement-litchi" or month != 4:
            return None
        return {
            "tasks": ["替换农事"],
            "management": ["替换管理措施"],
            "solar_terms": ["清明"],
            "reminder": "替换提醒",
        }

    def list_calendar_entries(self, product_key):
        self.calls.append({"method": "list_calendar_entries", "key": product_key})
        entry = self.get_calendar_entry(product_key, 4)
        return [{"month": 4, **entry}] if entry is not None else []

    def list_pest_entries(self):
        self.calls.append("list_pest_entries")
        return [
            {
                "id": "replacement-pest",
                "sort_order": 1,
                "pest_name": "替换荔枝蒂蛀虫",
                "product_names": ["替换荔枝"],
                "symptoms": ["替换虫蛀"],
                "aliases": ["替换蒂蛀虫"],
                "answer": "替换答案：及时清理落果并轮换用药。",
            }
        ]


class ReplacementCraftPresetProvider:
    def __init__(self):
        self.calls = []

    def list_crafts(self):
        self.calls.append("list_crafts")
        return [self._craft("guangxiu")]

    def get_craft(self, craft_key):
        self.calls.append({"method": "get_craft", "key": craft_key})
        craft = self._craft(str(craft_key))
        return craft if craft["craft_key"] == "guangxiu" else None

    @staticmethod
    def _craft(craft_key):
        return {
            "craft_key": craft_key,
            "name": "替换广绣",
            "introduction": "替换技艺介绍",
            "sort_order": 1,
            "is_demo": False,
            "steps": [
                {
                    "step_no": step_no,
                    "step_key": f"replacement-step-{step_no}",
                    "title": f"替换步骤{step_no}",
                    "description": f"替换步骤说明{step_no}",
                    "tips": ["替换要领"],
                }
                for step_no in range(1, CRAFT_STEP_COUNT + 1)
            ],
            "material_guide": [
                {
                    "name": "替换绣线",
                    "reference_price": "20 元",
                    "purchase_channel": "替换渠道",
                    "precautions": "替换注意事项",
                    "taobao_keyword": "替换关键词",
                }
            ],
        }


class ReplacementCaseProvider:
    def __init__(self):
        self.calls = []

    def list_success_cases(self):
        self.calls.append("list_success_cases")
        return [self._case()]

    def get_success_case(self, case_id):
        self.calls.append({"method": "get_success_case", "id": case_id})
        case = self._case()
        return case if case_id == case["id"] else None

    @staticmethod
    def _case():
        return {
            "id": "replacement-case",
            "title": "替换案例",
            "summary": "替换案例摘要",
            "background": "替换案例背景",
            "journey": "替换案例路径",
            "lessons": "替换案例经验",
            "published_at": REVIEW_TIMESTAMP,
            "updated_at": REVIEW_TIMESTAMP,
            "is_demo": False,
        }


class ReplacementKnowledgeProvider:
    def __init__(self):
        self.calls = []

    def list_entries(self, enabled_only=True):
        self.calls.append({"enabled_only": enabled_only})
        return [
            {
                "feature_key": "replacement-feature",
                "title": "替换功能说明",
                "content": "替换功能说明正文",
                "is_enabled": True,
            }
        ]


class ReplacementFeedbackProvider:
    def __init__(self):
        self.calls = []

    def submit_feedback(self, *, submitter_id, body, idempotency_key):
        self.calls.append(
            {
                "submitter_id": submitter_id,
                "body": body,
                "idempotency_key": idempotency_key,
            }
        )
        return {
            "id": "replacement-feedback",
            "submitter_id": submitter_id,
            "body": body,
            "idempotency_key": idempotency_key,
            "status": "pending",
            "created_at": REVIEW_TIMESTAMP,
        }


# Every slot this task owns, mapped to the protocol its consumer reads.
PROVIDER_PROTOCOLS = {
    "content_review_provider": ContentReviewProvider,
    "handcraft_points_policy_provider": PointsPolicyProvider,
    "admin_points_policy_provider": PointsPolicyProvider,
    "handcraft_reward_catalog_provider": RewardCatalogProvider,
    "agri_preset_provider": PresetContentProvider,
    "handcraft_craft_preset_provider": CraftPresetProvider,
    "local_resource_case_provider": LocalResourceCaseProvider,
    "assistant_feature_knowledge_provider": AssistantFeatureKnowledgeProvider,
    "feedback_intake_provider": FeedbackIntakeProvider,
}

# Methods consumer call sites require but the protocol does not declare.
CONSUMER_REQUIRED_METHODS = {
    "content_review_provider": ("list_review_items",),
}


def _protocol_surface(protocol) -> dict[str, tuple[str, ...]]:
    return {
        name: tuple(
            parameter
            for parameter in inspect.signature(method).parameters
            if parameter != "self"
        )
        for name, method in vars(protocol).items()
        if callable(method) and not name.startswith("_")
    }


def assert_protocol_complete(testcase, slot: str, provider) -> None:
    """A placeholder that covers only part of a protocol is a contract break."""
    for name, parameters in _protocol_surface(
        PROVIDER_PROTOCOLS[slot]
    ).items():
        method = getattr(provider, name, None)
        testcase.assertIsNotNone(
            method,
            f"{slot} replacement does not implement {name}",
        )
        testcase.assertEqual(
            tuple(inspect.signature(method).parameters),
            parameters,
            f"{slot} replacement changed the {name} signature",
        )
    for name in CONSUMER_REQUIRED_METHODS.get(slot, ()):
        testcase.assertTrue(
            hasattr(provider, name),
            f"{slot} replacement misses the consumer-required {name}",
        )


def replacement_providers() -> dict[str, object]:
    return {
        "content_review_provider": ReplacementReviewProvider(),
        "handcraft_points_policy_provider": (
            ReplacementPointsPolicyProvider()
        ),
        "handcraft_reward_catalog_provider": (
            ReplacementRewardCatalogProvider()
        ),
        "agri_preset_provider": ReplacementAgriPresetProvider(),
        "handcraft_craft_preset_provider": ReplacementCraftPresetProvider(),
        "local_resource_case_provider": ReplacementCaseProvider(),
        "assistant_feature_knowledge_provider": (
            ReplacementKnowledgeProvider()
        ),
        "feedback_intake_provider": ReplacementFeedbackProvider(),
    }


class AdminProviderReplacementTests(unittest.TestCase):
    """Replacing a slot is the whole migration story for 03/05/06/08/09."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(
                    Path(self.temp_dir.name) / "test.db"
                ),
                "SECRET_KEY": "test-only-secret",
                "SESSION_COOKIE_SECURE": False,
            }
        )
        with self.app.app_context():
            db = get_db()
            self.student_id = self._insert_user(
                db, "student01", "student", with_profile=True
            )
            self.enterprise_id = self._insert_user(
                db, "enterprise01", "enterprise"
            )
            self.category_id = self._insert_category(db, "替换分类")
            self.diagnosis_id = self._insert_diagnosis(
                db, self.student_id, "replacement-litchi"
            )

    def tearDown(self):
        self.temp_dir.cleanup()

    @staticmethod
    def _insert_user(db, username, role, *, with_profile=False):
        timestamp = "2026-09-22T09:00:00+08:00"
        cursor = db.execute(
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
                username,
                role,
                timestamp,
                timestamp,
            ),
        )
        user_id = int(cursor.lastrowid)
        if with_profile:
            db.execute(
                """
                INSERT INTO student_profiles (
                    user_id, contact, learning_direction, updated_at
                )
                VALUES (?, '', 'comprehensive', ?)
                """,
                (user_id, timestamp),
            )
        db.commit()
        return user_id

    @staticmethod
    def _insert_category(db, name):
        cursor = db.execute(
            """
            INSERT INTO interest_tags (group_key, name, sort_order, is_active)
            VALUES ('job', ?, 0, 1)
            """,
            (name,),
        )
        db.commit()
        return int(cursor.lastrowid)

    @staticmethod
    def _insert_diagnosis(db, user_id, product_key):
        timestamp = "2026-09-22T09:00:00+08:00"
        cursor = db.execute(
            """
            INSERT INTO agri_diagnosis_sessions (
                user_id, product_key, affected_part, symptoms_json,
                status, round_count, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, 'in_progress', 1, ?, ?)
            """,
            (
                user_id,
                product_key,
                "果实",
                '["替换虫蛀"]',
                timestamp,
                timestamp,
            ),
        )
        db.commit()
        return int(cursor.lastrowid)

    def _install_replacements(self) -> dict[str, object]:
        replacements = replacement_providers()
        for key, provider in replacements.items():
            self.app.extensions[key] = provider
        return replacements

    def _login(self, username):
        client = self.app.test_client()
        response = client.post(
            "/api/auth/login",
            json={"username": username, "password": "password8"},
        )
        self.assertEqual(response.status_code, 200)
        return client

    def test_all_admin_provider_slots_replace_without_consumer_changes(self):
        replacements = {
            "content_review_provider": ReplacementReviewProvider(),
            "handcraft_points_policy_provider": ReplacementPointsPolicyProvider(),
            "handcraft_reward_catalog_provider": ReplacementRewardCatalogProvider(),
            "agri_preset_provider": ReplacementAgriPresetProvider(),
            "handcraft_craft_preset_provider": ReplacementCraftPresetProvider(),
            "local_resource_case_provider": ReplacementCaseProvider(),
            "assistant_feature_knowledge_provider": ReplacementKnowledgeProvider(),
            "feedback_intake_provider": ReplacementFeedbackProvider(),
        }
        for key, provider in replacements.items():
            self.app.extensions[key] = provider
            self.assertIs(self.app.extensions[key], provider)

    def test_every_replacement_implements_its_full_protocol(self):
        for key, provider in replacement_providers().items():
            with self.subTest(slot=key):
                assert_protocol_complete(self, key, provider)

    def test_agri_calendar_diagnosis_and_qa_read_the_replaced_preset(self):
        replacements = self._install_replacements()
        preset = replacements["agri_preset_provider"]

        with self.app.app_context():
            self.assertEqual(
                [product["key"] for product in list_products()],
                ["replacement-litchi", "replacement-longan"],
            )

            calendar = get_calendar("replacement-litchi", 4)

            diagnosis = get_diagnosis(self.student_id, self.diagnosis_id)

            knowledge_entry = select_local_knowledge_entry("替换荔枝蒂蛀虫")

        self.assertEqual(calendar["product"]["name"], "替换荔枝")
        self.assertEqual(calendar["tasks"], ["替换农事"])
        self.assertEqual(calendar["reminder"], "替换提醒")
        self.assertEqual(diagnosis["product"]["name"], "替换荔枝")
        self.assertEqual(diagnosis["product_key"], "replacement-litchi")
        self.assertEqual(knowledge_entry["id"], "replacement-pest")
        self.assertEqual(
            {
                entry["method"]
                for entry in preset.calls
                if isinstance(entry, dict)
            },
            {"get_product", "list_calendar_entries", "get_calendar_entry"},
        )
        self.assertIn("list_pest_entries", preset.calls)

    def test_handcraft_points_rewards_and_crafts_read_the_replacements(self):
        replacements = self._install_replacements()
        points_policy = replacements["handcraft_points_policy_provider"]
        reward_catalog = replacements["handcraft_reward_catalog_provider"]
        craft_preset = replacements["handcraft_craft_preset_provider"]

        with self.app.app_context():
            policy = get_effective_policy()
            rewards = list_rewards(self.student_id)
            crafts = list_crafts()

        self.assertEqual(policy["version"], "replacement-policy")
        self.assertEqual(policy["daily_limit"], 60)
        # The mall listing settles the account first, which reads the policy
        # again; every recorded read still has to be the replacement's.
        self.assertEqual(set(points_policy.calls), {"get_policy"})
        self.assertEqual(
            [reward["reward_id"] for reward in rewards],
            ["replacement-reward"],
        )
        self.assertFalse(rewards[0]["can_redeem"])
        self.assertEqual(
            rewards[0]["unavailable_reason"], "积分不足，还差 100 分"
        )
        self.assertEqual(reward_catalog.calls, ["list_rewards"])
        self.assertEqual(crafts[0]["craft_key"], "guangxiu")
        self.assertEqual(crafts[0]["name"], "替换广绣")
        self.assertEqual(
            [step["step_no"] for step in crafts[0]["steps"]],
            list(range(1, CRAFT_STEP_COUNT + 1)),
        )
        self.assertFalse(crafts[1]["available"])
        self.assertEqual(
            craft_preset.calls,
            ["list_crafts"],
        )

    def test_local_resource_case_routes_read_the_replaced_case(self):
        replacements = self._install_replacements()
        case_provider = replacements["local_resource_case_provider"]

        client = self._login("student01")
        response = client.get("/api/local-resources/cases")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json()["cases"],
            [ReplacementCaseProvider._case()],
        )

        detail = client.get("/api/local-resources/cases/replacement-case")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(
            detail.get_json()["case"]["title"], "替换案例"
        )
        list_calls = [
            call for call in case_provider.calls if call == "list_success_cases"
        ]
        detail_calls = [
            call for call in case_provider.calls if isinstance(call, dict)
        ]
        self.assertEqual(
            [call["id"] for call in detail_calls],
            ["replacement-case"],
        )
        self.assertEqual(list_calls, ["list_success_cases"])

    def test_enterprise_console_job_creation_reads_the_replaced_reviewer(self):
        replacements = self._install_replacements()
        reviewer = replacements["content_review_provider"]

        with self.app.app_context():
            job = create_job(
                self.enterprise_id,
                {
                    "title": "替换岗位",
                    "salary": "6000-8000",
                    "location": "Guangzhou",
                    "category_id": self.category_id,
                    "description": "替换岗位描述",
                },
            )

        self.assertEqual(job["review_status"], "pending")
        submit_calls = [
            call for call in reviewer.calls if call["method"] == "submit_for_review"
        ]
        self.assertEqual(len(submit_calls), 1)
        self.assertEqual(submit_calls[0]["content_type"], "job_position")
        self.assertEqual(submit_calls[0]["content_id"], job["job_id"])
        self.assertEqual(submit_calls[0]["submitter_id"], self.enterprise_id)
        self.assertEqual(submit_calls[0]["expected_version"], 1)
        self.assertEqual(submit_calls[0]["payload"]["title"], "替换岗位")

    def test_content_review_queue_and_approval_read_the_replacement(self):
        replacements = self._install_replacements()
        reviewer = replacements["content_review_provider"]

        with self.app.app_context():
            reviewer.submit_for_review(
                content_type="course_video",
                content_id="replacement-course",
                submitter_id=self.student_id,
                expected_version=1,
                payload={"title": "替换课程"},
            )
            queue = list_review_queue("course_video")
            approved = approve_review(
                {"id": 9001, "role": "admin"},
                content_type="course_video",
                content_id="replacement-course",
                expected_version=1,
            )

        self.assertEqual(
            [item["content_id"] for item in queue["items"]],
            ["replacement-course"],
        )
        self.assertEqual(queue["counts"]["course_video"], 1)
        self.assertEqual(approved["review_status"], "approved")
        approve_calls = [
            call for call in reviewer.calls if call["method"] == "approve"
        ]
        self.assertEqual(len(approve_calls), 1)
        self.assertEqual(approve_calls[0]["reviewer_id"], 9001)
        self.assertEqual(approve_calls[0]["reviewer_role"], "admin")
        self.assertEqual(approve_calls[0]["submitter_id"], self.student_id)

    def test_assistant_knowledge_and_feedback_read_the_replacements(self):
        replacements = self._install_replacements()
        knowledge = replacements["assistant_feature_knowledge_provider"]
        feedback = replacements["feedback_intake_provider"]

        with self.app.app_context():
            entries = get_assistant_feature_knowledge_provider().list_entries()
            record = get_feedback_intake_provider().submit_feedback(
                submitter_id=self.student_id,
                body="替换反馈正文",
                idempotency_key="replacement-feedback-key",
            )

        self.assertEqual(entries[0]["feature_key"], "replacement-feature")
        self.assertEqual(record["id"], "replacement-feedback")
        self.assertEqual(record["idempotency_key"], "replacement-feedback-key")
        self.assertEqual(knowledge.calls, [{"enabled_only": True}])
        self.assertEqual(
            feedback.calls,
            [
                {
                    "submitter_id": self.student_id,
                    "body": "替换反馈正文",
                    "idempotency_key": "replacement-feedback-key",
                }
            ],
        )


class AdminProviderDefaultInstallationTests(unittest.TestCase):
    """011's database defaults win over every earlier placeholder install."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(
                    Path(self.temp_dir.name) / "test.db"
                ),
                "SECRET_KEY": "test-only-secret",
            }
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_create_app_registers_database_defaults_for_all_eight_slots(self):
        extensions = self.app.extensions

        self.assertIsInstance(
            extensions["content_review_provider"],
            CompositeContentReviewProvider,
        )
        self.assertIsInstance(
            extensions["handcraft_craft_preset_provider"],
            DatabaseCraftPresetProvider,
        )
        self.assertIsInstance(
            extensions["handcraft_reward_catalog_provider"],
            DatabaseRewardCatalogProvider,
        )
        self.assertIsInstance(
            extensions["agri_preset_provider"],
            DatabaseAgriPresetContentProvider,
        )
        self.assertIsInstance(
            extensions["local_resource_case_provider"],
            AdminDatabaseLocalResourceCaseProvider,
        )
        self.assertIsInstance(
            extensions["assistant_feature_knowledge_provider"],
            DatabaseAssistantFeatureKnowledgeProvider,
        )
        self.assertIsInstance(
            extensions["feedback_intake_provider"],
            DatabaseFeedbackIntakeProvider,
        )
        for slot in (
            "handcraft_points_policy_provider",
            "admin_points_policy_provider",
        ):
            self.assertIsInstance(
                extensions[slot], DatabasePointsPolicyProvider
            )
        self.assertIs(
            extensions["handcraft_points_policy_provider"],
            extensions["admin_points_policy_provider"],
        )

    def test_test_override_after_create_app_still_reaches_consumers(self):
        points_policy = ReplacementPointsPolicyProvider()
        reward_catalog = ReplacementRewardCatalogProvider()
        self.app.extensions["handcraft_points_policy_provider"] = points_policy
        self.app.extensions["handcraft_reward_catalog_provider"] = (
            reward_catalog
        )

        with self.app.app_context():
            policy = get_effective_policy()
            rewards = list_rewards(7)

        self.assertIs(
            self.app.extensions["handcraft_points_policy_provider"],
            points_policy,
        )
        self.assertEqual(policy["version"], "replacement-policy")
        self.assertEqual(
            [reward["reward_id"] for reward in rewards],
            ["replacement-reward"],
        )
        self.assertEqual(reward_catalog.calls, ["list_rewards"])


class UnconditionalSlotReplacementTests(unittest.TestCase):
    """A slot that is only filled when empty silently disables 011."""

    def _cross_branch_app(self) -> Flask:
        """Simulate a later feature pre-installing its own providers."""
        app = Flask("cross-branch-simulation")
        app.extensions["assistant_feature_knowledge_provider"] = object()
        app.extensions["feedback_intake_provider"] = object()
        return app

    def test_pre_installed_knowledge_and_feedback_slots_are_replaced(self):
        app = self._cross_branch_app()

        install_default_admin_services(app)

        self.assertIsInstance(
            app.extensions["assistant_feature_knowledge_provider"],
            DatabaseAssistantFeatureKnowledgeProvider,
        )
        self.assertIsInstance(
            app.extensions["feedback_intake_provider"],
            DatabaseFeedbackIntakeProvider,
        )

    def test_every_unconditional_slot_replaces_a_pre_installed_slot(self):
        app = self._cross_branch_app()
        sentinels = {
            "content_review_provider": UnavailableContentReviewProvider(),
            "handcraft_craft_preset_provider": object(),
            "handcraft_reward_catalog_provider": object(),
            "agri_preset_provider": object(),
            "local_resource_case_provider": object(),
            "handcraft_points_policy_provider": object(),
            "admin_points_policy_provider": object(),
        }
        for key, sentinel in sentinels.items():
            app.extensions[key] = sentinel

        install_default_admin_services(app)

        for key, sentinel in sentinels.items():
            with self.subTest(slot=key):
                self.assertIsNot(app.extensions[key], sentinel)
        for key, expected in (
            ("content_review_provider", CompositeContentReviewProvider),
            ("handcraft_craft_preset_provider", DatabaseCraftPresetProvider),
            ("handcraft_reward_catalog_provider", DatabaseRewardCatalogProvider),
            ("agri_preset_provider", DatabaseAgriPresetContentProvider),
            (
                "local_resource_case_provider",
                AdminDatabaseLocalResourceCaseProvider,
            ),
            ("handcraft_points_policy_provider", DatabasePointsPolicyProvider),
            ("admin_points_policy_provider", DatabasePointsPolicyProvider),
        ):
            with self.subTest(slot=key):
                self.assertIsInstance(app.extensions[key], expected)

    def test_non_placeholder_content_review_provider_is_left_alone(self):
        """09 installs a protocol-complete placeholder; replacing it is intent."""
        app = self._cross_branch_app()
        installed = ReplacementReviewProvider()
        app.extensions["content_review_provider"] = installed

        install_default_admin_services(app)

        self.assertIs(app.extensions["content_review_provider"], installed)


class ConfigureAdminProvidersTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(
                    Path(self.temp_dir.name) / "test.db"
                ),
                "SECRET_KEY": "test-only-secret",
            }
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_every_parameter_installs_into_its_own_slot(self):
        replacements = replacement_providers()
        replacements["admin_points_policy_provider"] = (
            replacements.pop("handcraft_points_policy_provider")
        )

        configure_admin_providers(
            self.app,
            content_review=replacements["content_review_provider"],
            points_policy=replacements["admin_points_policy_provider"],
            reward_catalog=replacements["handcraft_reward_catalog_provider"],
            agri_preset=replacements["agri_preset_provider"],
            craft_preset=replacements["handcraft_craft_preset_provider"],
            local_case=replacements["local_resource_case_provider"],
            knowledge=replacements["assistant_feature_knowledge_provider"],
            feedback_intake=replacements["feedback_intake_provider"],
        )

        for key, provider in replacements.items():
            with self.subTest(slot=key):
                self.assertIs(self.app.extensions[key], provider)

    def test_none_parameters_leave_the_installed_defaults_in_place(self):
        before = dict(self.app.extensions)

        configure_admin_providers(
            self.app,
            knowledge=ReplacementKnowledgeProvider(),
        )

        for key, provider in before.items():
            if key == "assistant_feature_knowledge_provider":
                continue
            with self.subTest(slot=key):
                self.assertIs(self.app.extensions[key], provider)


class ProviderSlotRegistryTests(unittest.TestCase):
    """One setter and one getter per slot key across the whole backend."""

    APP_ROOT = Path(__file__).resolve().parents[1] / "app"

    SLOT_KEYS = tuple(PROVIDER_PROTOCOLS)

    # Legacy setter without a same-name getter: it fans out to two slots that
    # each have their own getter, and existing code is not rewritten here.
    LEGACY_UNPAIRED_SETTERS = frozenset({"set_video_review_provider"})

    # One slot key is written by two setters in the repo: 06's
    # `set_employment_statistics_provider` and 010's both write
    # `government_employment_statistics_provider`, so the two consoles share
    # one key instead of owning separate keys. Splitting them would mean
    # editing 06/010 code, which is outside this task's write set.
    SHARED_SLOT_KEYS = frozenset({"government_employment_statistics_provider"})

    @staticmethod
    def _extension_keys(node) -> set[str]:
        """Slot keys a function reads or writes through `app.extensions`."""
        keys = set()
        for child in ast.walk(node):
            subscript_write = isinstance(
                child, ast.Subscript
            ) and isinstance(child.slice, ast.Constant)
            getter_read = (
                isinstance(child, ast.Call)
                and isinstance(child.func, ast.Attribute)
                and child.func.attr == "get"
            )
            if subscript_write and isinstance(child.slice.value, str):
                keys.add(child.slice.value)
            elif getter_read:
                for argument in child.args:
                    if isinstance(argument, ast.Constant) and isinstance(
                        argument.value, str
                    ):
                        keys.add(argument.value)
        return keys

    def _collect_slot_accessors(self, keys=None):
        setters = defaultdict(list)
        getters = defaultdict(list)
        for path in sorted(self.APP_ROOT.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            tree = ast.parse(
                path.read_text(encoding="utf-8"),
                filename=str(path),
            )
            for node in ast.walk(tree):
                if not isinstance(node, ast.FunctionDef):
                    continue
                accessors = {
                    key
                    for key in self._extension_keys(node)
                    if key.endswith("_provider")
                    and (keys is None or key in keys)
                }
                for key in accessors:
                    if node.name.startswith("set_"):
                        setters[key].append(
                            (path.relative_to(self.APP_ROOT.parent), node.name, node.lineno)
                        )
                    elif node.name.startswith("get_"):
                        getters[key].append(
                            (path.relative_to(self.APP_ROOT.parent), node.name, node.lineno)
                        )
        return setters, getters

    def test_each_slot_has_exactly_one_setter_and_getter_in_the_repo(self):
        setters, getters = self._collect_slot_accessors(self.SLOT_KEYS)

        for key in self.SLOT_KEYS:
            with self.subTest(slot=key):
                self.assertEqual(len(setters[key]), 1, f"{key} setters")
                self.assertEqual(len(getters[key]), 1, f"{key} getters")
                setter_module = setters[key][0][0]
                getter_module = getters[key][0][0]
                self.assertEqual(
                    setter_module,
                    getter_module,
                    f"{key} setter and getter live in different modules",
                )

    def test_repo_wide_slot_keys_have_one_owner_unless_documented_shared(self):
        setters, _getters = self._collect_slot_accessors()

        multi_writer = {
            key for key, owners in setters.items() if len(owners) > 1
        }
        self.assertEqual(
            multi_writer,
            self.SHARED_SLOT_KEYS,
            "a slot key written by more than one setter must be documented",
        )

    def test_repo_wide_setters_are_paired_with_getters(self):
        setter_names = set()
        getter_names = set()
        for path in sorted(self.APP_ROOT.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            tree = ast.parse(
                path.read_text(encoding="utf-8"),
                filename=str(path),
            )
            for node in ast.walk(tree):
                if not isinstance(node, ast.FunctionDef):
                    continue
                if node.name.startswith("set_") and node.name.endswith(
                    "_provider"
                ):
                    setter_names.add(node.name)
                elif node.name.startswith("get_") and node.name.endswith(
                    "_provider"
                ):
                    getter_names.add(node.name)

        # Compare the accessor stem, not the function name: `set_points_policy_
        # provider` and `get_points_policy_provider` are one pair, and the
        # same setter name can legally serve two different slots.
        unpaired = {
            name
            for name in setter_names
            if f"get_{name[len('set_'):]}" not in getter_names
        }
        self.assertEqual(
            unpaired,
            self.LEGACY_UNPAIRED_SETTERS,
            "unpaired provider setters must stay limited to the known legacy set",
        )

    def test_admin_console_exports_the_configure_provider_types(self):
        import app.admin_console as admin_console

        for name in (
            "ContentReviewProvider",
            "PointsPolicyProvider",
            "RewardCatalogProvider",
            "PresetContentProvider",
            "CraftPresetProvider",
            "LocalResourceCaseProvider",
            "AssistantFeatureKnowledgeProvider",
            "FeedbackIntakeProvider",
        ):
            with self.subTest(name=name):
                self.assertIn(name, admin_console.__all__)


if __name__ == "__main__":
    unittest.main()
