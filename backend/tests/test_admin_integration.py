"""011 跨模块端到端集成验收。

`test_admin_provider_acceptance.py` 证明八个 provider 槽可以整体替换、
真实 `create_app()` 也会注册数据库默认实现。本文件在同一台真实应用上再往前
一步：真实 SQLite 库 + 真实 HTTP 请求，证明经 011 后台写出的数据能原样抵达
03/05/06/08/09 的消费路由，审核动作的状态与 02 通知 outbox 同步落地，并且
01 的会话与角色守卫在 provider 装配之后没有被破坏。

覆盖范围与 Task 27 刻意错开：这里不重复槽级替换与协议完整性，全部用例都从
登录后的 `test_client()` 发起，跨模块走完整链路。
"""

from __future__ import annotations

from pathlib import Path
import tempfile
from unittest import TestCase

from flask import Flask
from werkzeug.security import generate_password_hash

from app import create_app
from app.admin_console.presets import DatabaseAgriPresetContentProvider
from app.admin_console.providers import (
    AdminDatabaseLocalResourceCaseProvider,
    CompositeContentReviewProvider,
    DatabaseAssistantFeatureKnowledgeProvider,
    DatabaseCraftPresetProvider,
    DatabaseFeedbackIntakeProvider,
    DatabasePointsPolicyProvider,
    DatabaseRewardCatalogProvider,
    get_assistant_feature_knowledge_provider,
    get_feedback_intake_provider,
    get_points_policy_provider as get_admin_points_policy_provider,
)
from app.agri_skills.presets import get_preset_provider
from app.content_review import get_content_review_provider
from app.db import get_db
from app.handcraft_inheritance.providers import (
    get_craft_preset_provider,
    get_points_policy_provider,
    get_reward_catalog_provider,
)
from app.local_resources.cases import get_local_resource_case_provider


PASSWORD = "password8"
TIMESTAMP = "2026-09-22T09:00:00+08:00"
COURSE_MEDIA_URL = "/media/teacher-courses/integration.mp4"
ROLES = (
    "super_admin",
    "admin",
    "teacher",
    "enterprise",
    "student",
    "government",
)
POINTS_WEIGHTS = {
    "default": 10,
    "live_script": 10,
    "simulation": 10,
    "copy_training": 10,
    "customer_service": 10,
}


class AdminIntegrationTestCase(TestCase):
    """One real app per test class, built exactly like production does."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.database_path = Path(self.temp_dir.name) / "integration.db"
        # `submit_course_for_review` re-checks a local upload against disk, so
        # the media root has to point at a directory this test owns.
        self.media_root = Path(self.temp_dir.name) / "course-media"
        self.media_root.mkdir(parents=True, exist_ok=True)
        (self.media_root / "integration.mp4").write_bytes(b"integration media")
        self.app = create_app(
            {
                "TESTING": True,
                "PROPAGATE_EXCEPTIONS": False,
                "DATABASE_PATH": str(self.database_path),
                "SECRET_KEY": "integration-only-secret",
                "SESSION_COOKIE_SECURE": False,
                "COURSE_MEDIA_ROOT": str(self.media_root),
            }
        )
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.addCleanup(self.app_context.pop)
        with self.app.app_context():
            db = get_db()
            self.user_ids: dict[str, int] = {}
            for role in ROLES:
                cursor = db.execute(
                    """
                    INSERT INTO users (
                        username, password_hash, name, role, is_enabled,
                        created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, 1, ?, ?)
                    """,
                    (
                        f"integration-{role}",
                        generate_password_hash(PASSWORD),
                        f"集成{role}",
                        role,
                        TIMESTAMP,
                        TIMESTAMP,
                    ),
                )
                self.user_ids[role] = int(cursor.lastrowid)
            category = db.execute(
                """
                INSERT INTO interest_tags (group_key, name, sort_order, is_active)
                VALUES ('job', '集成分类', 0, 1)
                """
            )
            self.category_id = int(category.lastrowid)
            # The job-matching recommendation read needs a profile to exist.
            db.execute(
                """
                INSERT INTO student_profiles (
                    user_id, contact, learning_direction, updated_at
                )
                VALUES (?, '', 'comprehensive', ?)
                """,
                (self.user_ids["student"], TIMESTAMP),
            )
            db.commit()
        self.clients = {role: self._login(role) for role in ROLES}
        self.anonymous = self.app.test_client()

    def _login(self, role: str):
        # A fresh client per call: `abort_session_required` clears the
        # cookie, so a client that was once rejected would report 401 for the
        # wrong reason afterwards.
        client = self.app.test_client()
        response = client.post(
            "/api/auth/login",
            json={
                "username": f"integration-{role}",
                "password": PASSWORD,
            },
        )
        self.assertEqual(response.status_code, 200, role)
        return client

    def scalar(self, sql: str, parameters: tuple = ()):
        with self.app.app_context():
            row = get_db().execute(sql, parameters).fetchone()
        return None if row is None else row[0]

    def rows(self, sql: str, parameters: tuple = ()) -> list[tuple]:
        with self.app.app_context():
            return [
                tuple(row)
                for row in get_db().execute(sql, parameters).fetchall()
            ]


class AdminProviderAssemblyTests(AdminIntegrationTestCase):
    """Real `create_app()` wiring, read through the consumers' own getters."""

    def test_real_app_installs_admin_providers_into_consumer_slots(self):
        with self.app.app_context():
            self.assertIsInstance(
                get_content_review_provider(),
                CompositeContentReviewProvider,
            )
            self.assertIsInstance(
                get_preset_provider(),
                DatabaseAgriPresetContentProvider,
            )
            self.assertIsInstance(
                get_reward_catalog_provider(),
                DatabaseRewardCatalogProvider,
            )
            self.assertIsInstance(
                get_craft_preset_provider(),
                DatabaseCraftPresetProvider,
            )
            self.assertIsInstance(
                get_local_resource_case_provider(),
                AdminDatabaseLocalResourceCaseProvider,
            )
            self.assertIsInstance(
                get_feedback_intake_provider(),
                DatabaseFeedbackIntakeProvider,
            )
            self.assertIsInstance(
                get_assistant_feature_knowledge_provider(),
                DatabaseAssistantFeatureKnowledgeProvider,
            )

    def test_points_policy_provider_reaches_both_read_slots(self):
        # 05 reads `handcraft_points_policy_provider` while 011 reads
        # `admin_points_policy_provider`. `install_default_admin_services`
        # installs one instance into both, so a consumer on either side sees
        # the same authoritative `platform_points_policy` row.
        with self.app.app_context():
            points_policy = get_points_policy_provider()
            self.assertIsInstance(points_policy, DatabasePointsPolicyProvider)
            self.assertIs(points_policy, get_admin_points_policy_provider())

    def test_provider_reads_are_served_from_the_admin_tables(self):
        with self.app.app_context():
            products = get_preset_provider().list_products()
            pest_entries = get_preset_provider().list_pest_entries()
            rewards = get_reward_catalog_provider().list_rewards()
            points_policy = get_points_policy_provider().get_policy()

        product_keys = {product["key"] for product in products}
        self.assertIn("litchi", product_keys)
        self.assertTrue(
            any("荔枝蒂蛀虫" in entry["pest_name"] for entry in pest_entries)
        )
        self.assertIn(
            "reward-guangxiu-bookmark",
            {reward["reward_id"] for reward in rewards},
        )
        self.assertEqual(points_policy["daily_limit"], 60)
        self.assertEqual(
            self.scalar("SELECT COUNT(*) FROM admin_agri_products"),
            len(products),
        )
        self.assertEqual(
            self.scalar("SELECT COUNT(*) FROM admin_rewards"),
            len(rewards),
        )
        self.assertEqual(
            self.scalar("SELECT COUNT(*) FROM platform_points_policy"),
            1,
        )


class AgriPresetConsumerChainTests(AdminIntegrationTestCase):
    """03 的农时月历、诊断与离线问答消费 011 的农产品预置内容。"""

    def test_admin_agri_presets_reach_student_calendar_diagnosis_and_qa(self):
        admin = self.clients["admin"]
        student = self.clients["student"]

        product = admin.post(
            "/api/admin/presets/agri_products",
            json={
                "product_key": "integration-mango",
                "name": "芒果",
                "sort_order": 9,
            },
        )
        calendar = admin.post(
            "/api/admin/presets/agri_calendar",
            json={
                "product_key": "integration-mango",
                "month": 9,
                "tasks": ["集成采收"],
                "management": ["控梢促花"],
                "solar_terms": ["秋分"],
                "reminder": "九月采收提醒",
            },
        )
        pest = admin.post(
            "/api/admin/presets/pest_knowledge",
            json={
                "item_id": "integration-mango-fruit-fly",
                "sort_order": 30,
                "pest_name": "芒果果实蝇",
                "product_names": ["芒果"],
                "symptoms": ["虫蛀果"],
                "aliases": ["果实蝇"],
                "answer": "清园并及时套袋。",
            },
        )
        self.assertEqual(
            [product.status_code, calendar.status_code, pest.status_code],
            [201, 201, 201],
        )

        self.assertEqual(
            self.scalar(
                "SELECT name FROM admin_agri_products WHERE product_key = ?",
                ("integration-mango",),
            ),
            "芒果",
        )
        self.assertEqual(
            self.scalar(
                "SELECT reminder FROM admin_agri_calendar"
                " WHERE product_key = ? AND month = ?",
                ("integration-mango", 9),
            ),
            "九月采收提醒",
        )
        self.assertEqual(
            self.scalar(
                "SELECT answer FROM admin_pest_knowledge WHERE item_id = ?",
                ("integration-mango-fruit-fly",),
            ),
            "清园并及时套袋。",
        )

        calendar_response = student.get(
            "/api/agri-skills/calendar?product_key=integration-mango&month=9"
        )
        self.assertEqual(calendar_response.status_code, 200)
        calendar_body = calendar_response.get_json()["calendar"]
        self.assertEqual(calendar_body["product"]["name"], "芒果")
        self.assertEqual(calendar_body["tasks"], ["集成采收"])
        self.assertEqual(calendar_body["reminder"], "九月采收提醒")
        self.assertIsNone(calendar_body["empty_state"])

        diagnosis = student.post(
            "/api/agri-skills/diagnoses",
            json={
                "product_key": "integration-mango",
                "affected_part": "果实",
                "symptoms": ["果实出现虫蛀"],
            },
        )
        self.assertEqual(diagnosis.status_code, 201)
        session_id = diagnosis.get_json()["session"]["id"]
        diagnosis_response = student.get(
            f"/api/agri-skills/diagnoses/{session_id}"
        )
        self.assertEqual(diagnosis_response.status_code, 200)
        self.assertEqual(
            diagnosis_response.get_json()["session"]["product"]["name"],
            "芒果",
        )

        conversation = student.post(
            "/api/agri-skills/qa/conversations",
            json={"question": "芒果果实蝇怎么防", "input_mode": "text"},
        )
        self.assertEqual(conversation.status_code, 201)
        conversation_id = conversation.get_json()["conversation"]["id"]
        answer = student.post(
            f"/api/agri-skills/qa/conversations/{conversation_id}/messages",
            json={"question": "芒果果实蝇导致虫蛀果怎么办"},
        )
        self.assertEqual(answer.status_code, 201)
        turn = answer.get_json()["turn"]
        # No AI client is configured for this app, so the answer has to come
        # from the 011 pest knowledge row through 03's offline path.
        self.assertEqual(turn["answer_mode"], "local_kb")
        self.assertEqual(
            turn["answer"],
            "离线知识库回答\n芒果果实蝇：清园并及时套袋。",
        )

    def test_disabled_agri_preset_disappears_from_the_student_calendar(self):
        admin = self.clients["admin"]
        student = self.clients["student"]
        created = admin.post(
            "/api/admin/presets/agri_products",
            json={
                "product_key": "integration-persimmon",
                "name": "柿子",
                "sort_order": 11,
            },
        )
        self.assertEqual(created.status_code, 201)

        disabled = admin.delete(
            "/api/admin/presets/agri_products/integration-persimmon"
        )
        self.assertEqual(disabled.status_code, 200)
        self.assertFalse(disabled.get_json()["item"]["is_enabled"])

        response = student.get(
            "/api/agri-skills/calendar"
            "?product_key=integration-persimmon&month=9"
        )
        self.assertEqual(response.status_code, 200)
        calendar = response.get_json()["calendar"]
        self.assertIsNone(calendar.get("product"))
        self.assertTrue(calendar["empty_state"])


class HandcraftConsumerChainTests(AdminIntegrationTestCase):
    """05 的积分商城与积分账户读 011 的奖品目录和平台积分规则。"""

    def test_admin_reward_reaches_the_student_mall(self):
        created = self.clients["admin"].post(
            "/api/admin/rewards",
            json={
                "reward_id": "integration-reward",
                "name": "集成奖品",
                "points_cost": 12,
                "stock": 3,
            },
        )
        self.assertEqual(created.status_code, 201)
        self.assertFalse(created.get_json()["reward"]["is_demo"])

        mall = self.clients["student"].get(
            "/api/handcraft-inheritance/rewards"
        )
        self.assertEqual(mall.status_code, 200)
        rewards = {
            reward["reward_id"]: reward
            for reward in mall.get_json()["rewards"]
        }
        self.assertIn("integration-reward", rewards)
        self.assertEqual(rewards["integration-reward"]["name"], "集成奖品")
        self.assertEqual(rewards["integration-reward"]["points_cost"], 12)
        self.assertEqual(
            self.scalar(
                "SELECT COUNT(*) FROM admin_rewards WHERE reward_id = ?",
                ("integration-reward",),
            ),
            1,
        )

    def test_admin_points_policy_edit_reaches_the_student_points_account(self):
        super_admin = self.clients["super_admin"]
        student = self.clients["student"]
        current = super_admin.get("/api/admin/points-policy")
        self.assertEqual(current.status_code, 200)
        self.assertEqual(current.get_json()["policy"]["version"], 1)

        updated = super_admin.put(
            "/api/admin/points-policy",
            json={
                "expected_version": 1,
                "seconds_per_point": 300,
                "daily_limit": 77,
                "expiry_mode": "permanent",
                "training_weights": POINTS_WEIGHTS,
            },
        )
        self.assertEqual(updated.status_code, 200)
        policy = updated.get_json()["policy"]
        self.assertEqual(policy["version"], 2)
        self.assertEqual(policy["daily_limit"], 77)
        self.assertFalse(policy["is_demo"])
        self.assertEqual(
            self.scalar(
                "SELECT version FROM platform_points_policy"
                " WHERE singleton = 1"
            ),
            2,
        )

        account = student.get("/api/handcraft-inheritance/points")
        self.assertEqual(account.status_code, 200)
        self.assertEqual(
            account.get_json()["account"]["daily_limit"], 77
        )


class LocalResourceConsumerChainTests(AdminIntegrationTestCase):
    """06 的成功案例与 AI 学伴知识消费 011 的预置内容。"""

    def test_admin_success_case_reaches_the_student_case_routes(self):
        admin = self.clients["admin"]
        student = self.clients["student"]
        created = admin.post(
            "/api/admin/presets/success_cases",
            json={
                "case_id": "integration-case",
                "title": "集成案例",
                "summary": "概要",
                "background": "背景",
                "journey": "历程",
                "lessons": "启示",
                "sort_order": 60,
                "published_at": "2026-09-05T08:00:00+08:00",
            },
        )
        self.assertEqual(created.status_code, 201)

        listed = student.get("/api/local-resources/cases")
        self.assertEqual(listed.status_code, 200)
        self.assertIn(
            "integration-case",
            {case["id"] for case in listed.get_json()["cases"]},
        )
        detail = student.get("/api/local-resources/cases/integration-case")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.get_json()["case"]["title"], "集成案例")

        disabled = admin.delete(
            "/api/admin/presets/success_cases/integration-case"
        )
        self.assertEqual(disabled.status_code, 200)
        self.assertFalse(disabled.get_json()["item"]["is_enabled"])

        after = student.get("/api/local-resources/cases")
        self.assertEqual(after.status_code, 200)
        self.assertNotIn(
            "integration-case",
            {case["id"] for case in after.get_json()["cases"]},
        )
        self.assertEqual(
            student.get(
                "/api/local-resources/cases/integration-case"
            ).status_code,
            404,
        )

    def test_admin_assistant_knowledge_reaches_the_knowledge_provider(self):
        created = self.clients["admin"].post(
            "/api/admin/presets/assistant_knowledge",
            json={
                "knowledge_id": "integration-knowledge",
                "title": "如何查看农事月历",
                "body": "在农技助手选择作物后查看当月农事。",
                "feature_key": "agri_skills",
                "jump_target": "/agri-skills/calendar",
                "sort_order": 80,
            },
        )
        self.assertEqual(created.status_code, 201)

        with self.app.app_context():
            from app.admin_console import (
                get_assistant_feature_knowledge_provider,
            )

            entries = get_assistant_feature_knowledge_provider().list_entries()

        self.assertIn(
            "integration-knowledge",
            {entry["knowledge_id"] for entry in entries},
        )
        self.assertEqual(
            self.scalar(
                "SELECT COUNT(*) FROM admin_assistant_feature_knowledge"
                " WHERE knowledge_id = ?",
                ("integration-knowledge",),
            ),
            1,
        )


class ContentReviewConsumerChainTests(AdminIntegrationTestCase):
    """08/09 提交审核，011 队列处理，状态与通知 outbox 同步落地。"""

    def _create_and_submit_course(self, title: str) -> tuple[int, int]:
        created = self.clients["teacher"].post(
            "/api/teacher/courses",
            json={
                "title": title,
                "direction": "agriculture",
                "summary": "跨模块集成课程",
                "content_tags": [],
                "duration_seconds": 300,
                "media_source_type": "local_upload",
                "media_url": COURSE_MEDIA_URL,
            },
        )
        self.assertEqual(created.status_code, 201, title)
        course = created.get_json()["course"]
        submitted = self.clients["teacher"].post(
            f"/api/teacher/courses/{course['id']}/submit",
            json={"expected_version": course["version"]},
        )
        self.assertEqual(submitted.status_code, 200, title)
        self.assertEqual(submitted.get_json()["course"]["status"], "pending")
        return int(course["id"]), int(course["version"])

    def test_teacher_course_submission_runs_through_the_admin_review_queue(self):
        admin = self.clients["admin"]
        student = self.clients["student"]
        course_id, version = self._create_and_submit_course("集成课程")

        queue = admin.get("/api/admin/review?content_type=course_video")
        self.assertEqual(queue.status_code, 200)
        body = queue.get_json()
        self.assertEqual(body["counts"]["course_video"], 1)
        item = body["items"][0]
        self.assertEqual(item["content_type"], "course_video")
        self.assertEqual(item["content_id"], str(course_id))
        self.assertEqual(item["review_status"], "pending")
        self.assertEqual(item["submitter_id"], self.user_ids["teacher"])
        self.assertEqual(item["title"], "集成课程")

        approved = admin.post(
            f"/api/admin/review/course_video/{course_id}/approve",
            json={"expected_version": version},
        )
        self.assertEqual(approved.status_code, 200)
        approved_item = approved.get_json()["item"]
        self.assertEqual(approved_item["review_status"], "approved")
        self.assertEqual(approved_item["version"], version + 1)
        self.assertTrue(approved_item["published_at"].endswith("+08:00"))
        self.assertEqual(
            self.rows(
                "SELECT status FROM admin_notification_outbox WHERE id = ?",
                (approved_item["outbox_id"],),
            ),
            [("sent",)],
        )
        self.assertEqual(
            self.rows(
                "SELECT recipient_id, event_type, source_type, source_id"
                " FROM system_notifications WHERE source_type = 'course_video'"
            ),
            [
                (
                    self.user_ids["teacher"],
                    "review_approved",
                    "course_video",
                    str(course_id),
                )
            ],
        )
        self.assertEqual(
            self.rows(
                "SELECT version FROM content_review_records"
                " WHERE content_type = 'course_video' AND content_id = ?",
                (str(course_id),),
            ),
            [(version + 1,)],
        )

        catalog = student.get("/api/student/courses?direction=agriculture")
        self.assertEqual(catalog.status_code, 200)
        self.assertIn(
            course_id,
            {course["id"] for course in catalog.get_json()["courses"]},
        )

    def test_rejected_course_stays_out_of_the_student_catalog(self):
        admin = self.clients["admin"]
        student = self.clients["student"]
        course_id, version = self._create_and_submit_course("被驳回的课程")

        rejected = admin.post(
            f"/api/admin/review/course_video/{course_id}/reject",
            json={"expected_version": version, "opinion": "画面模糊，请重录"},
        )
        self.assertEqual(rejected.status_code, 200)
        rejected_item = rejected.get_json()["item"]
        self.assertEqual(rejected_item["review_status"], "rejected")
        self.assertEqual(
            rejected_item["rejection_opinion"], "画面模糊，请重录"
        )
        self.assertIsNone(rejected_item["published_at"])
        self.assertEqual(
            self.rows(
                "SELECT status FROM admin_notification_outbox WHERE id = ?",
                (rejected_item["outbox_id"],),
            ),
            [("sent",)],
        )

        catalog = student.get("/api/student/courses?direction=agriculture")
        self.assertEqual(catalog.status_code, 200)
        self.assertNotIn(
            course_id,
            {course["id"] for course in catalog.get_json()["courses"]},
        )

        teacher_courses = self.clients["teacher"].get("/api/teacher/courses")
        self.assertEqual(teacher_courses.status_code, 200)
        course = next(
            item
            for item in teacher_courses.get_json()["courses"]
            if item["id"] == course_id
        )
        self.assertEqual(course["status"], "rejected")
        self.assertEqual(course["rejection_opinion"], "画面模糊，请重录")

    def test_enterprise_job_submission_runs_through_the_admin_review_queue(self):
        admin = self.clients["admin"]
        enterprise = self.clients["enterprise"]
        student = self.clients["student"]
        created = enterprise.post(
            "/api/enterprise/jobs",
            json={
                "title": "集成岗位",
                "salary": "6000-8000",
                "location": "Guangzhou",
                "category_id": self.category_id,
                "description": "集成岗位描述",
            },
        )
        self.assertEqual(created.status_code, 201)
        job = created.get_json()["job"]
        self.assertEqual(job["review_status"], "pending")

        queue = admin.get("/api/admin/review?content_type=job_position")
        self.assertEqual(queue.status_code, 200)
        self.assertEqual(queue.get_json()["counts"]["job_position"], 1)
        self.assertEqual(
            queue.get_json()["items"][0]["content_id"], job["job_id"]
        )

        approved = admin.post(
            f"/api/admin/review/job_position/{job['job_id']}/approve",
            json={"expected_version": job["version"]},
        )
        self.assertEqual(approved.status_code, 200)
        approved_item = approved.get_json()["item"]
        self.assertEqual(approved_item["review_status"], "approved")
        self.assertEqual(
            self.rows(
                "SELECT status FROM admin_notification_outbox WHERE id = ?",
                (approved_item["outbox_id"],),
            ),
            [("sent",)],
        )

        jobs = student.get("/api/job-matching/jobs")
        self.assertEqual(jobs.status_code, 200)
        self.assertIn(
            job["job_id"],
            {item["job_id"] for item in jobs.get_json()["jobs"]},
        )

    def test_feedback_intake_provider_writes_feedback_records(self):
        with self.app.app_context():
            self.assertIsInstance(
                get_feedback_intake_provider(),
                DatabaseFeedbackIntakeProvider,
            )
            record = get_feedback_intake_provider().submit_feedback(
                submitter_id=self.user_ids["student"],
                body="集成反馈正文",
                idempotency_key="integration-feedback-key",
            )

        self.assertEqual(record["status"], "pending")
        self.assertEqual(record["idempotency_key"], "integration-feedback-key")
        self.assertEqual(record["submitter_id"], self.user_ids["student"])
        self.assertEqual(
            self.rows(
                "SELECT feedback_id, status, idempotency_key"
                " FROM feedback_records WHERE idempotency_key = ?",
                ("integration-feedback-key",),
            ),
            [
                (
                    record["feedback_id"],
                    "pending",
                    "integration-feedback-key",
                )
            ],
        )

        listed = self.clients["admin"].get("/api/admin/feedback")
        self.assertEqual(listed.status_code, 200)
        self.assertIn(
            record["feedback_id"],
            {item["feedback_id"] for item in listed.get_json()["items"]},
        )


class SessionAndRoleGuardTests(AdminIntegrationTestCase):
    """01 的会话与角色守卫在 provider 装配后仍然按矩阵生效。"""

    PROVIDER_ROUTE_MATRIX = (
        # path, allowed roles, status an authenticated but wrong role gets.
        # 03/05/08/09 answer 401 via `abort_session_required`, 06 raises its
        # own access error and 011 raises a provider access error, both 403.
        ("/api/agri-skills/calendar", frozenset({"student"}), 401),
        ("/api/local-resources/cases", frozenset({"student"}), 403),
        ("/api/handcraft-inheritance/rewards", frozenset({"student"}), 401),
        ("/api/teacher/courses", frozenset({"teacher"}), 401),
        ("/api/enterprise/jobs", frozenset({"enterprise"}), 401),
        (
            "/api/admin/review",
            frozenset({"admin", "super_admin"}),
            403,
        ),
    )

    def test_anonymous_requests_still_require_an_active_session(self):
        for path, _, _ in self.PROVIDER_ROUTE_MATRIX:
            with self.subTest(path=path):
                response = self.anonymous.get(path)
                self.assertEqual(response.status_code, 401)

    def test_provider_related_routes_keep_their_role_boundaries(self):
        for path, allowed_roles, rejected_status in self.PROVIDER_ROUTE_MATRIX:
            with self.subTest(path=path):
                for role in sorted(allowed_roles):
                    allowed = self._login(role).get(path)
                    self.assertEqual(allowed.status_code, 200)
                for role in ROLES:
                    if role in allowed_roles:
                        continue
                    rejected = self._login(role).get(path)
                    self.assertEqual(
                        rejected.status_code, rejected_status, (path, role)
                    )

    def test_admin_only_surfaces_stay_out_of_the_ordinary_admin_console(self):
        admin = self.clients["admin"]
        for path in (
            "/api/admin/accounts",
            "/api/admin/points-policy",
            "/api/admin/announcements",
        ):
            with self.subTest(path=path):
                self.assertEqual(admin.get(path).status_code, 403)
        self.assertEqual(
            self.clients["super_admin"]
            .get("/api/admin/accounts")
            .status_code,
            200,
        )

    def test_messaging_center_stays_reachable_for_every_session(self):
        for role in ROLES:
            with self.subTest(role=role):
                response = self.clients[role].get("/api/messages/notifications")
                self.assertEqual(response.status_code, 200)
