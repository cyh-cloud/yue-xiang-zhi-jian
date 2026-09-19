import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import httpx
from werkzeug.security import generate_password_hash

from app import create_app
from app.agri_skills.ai_client import (
    OpenAiCompatibleAiClient,
    set_ai_client,
)
from app.agri_skills.errors import (
    AgriAccessError,
    AiUnavailableError,
)
from app.db import get_db


ROUTES = [
    ("POST", "/api/ecommerce-training/live-scripts", {}),
    ("GET", "/api/ecommerce-training/live-scripts", None),
    ("GET", "/api/ecommerce-training/live-scripts/1", None),
    ("GET", "/api/ecommerce-training/simulations/scenes", None),
    ("POST", "/api/ecommerce-training/simulations", {"scene_key": "opening"}),
    ("GET", "/api/ecommerce-training/simulations", None),
    ("GET", "/api/ecommerce-training/simulations/1", None),
    (
        "PUT",
        "/api/ecommerce-training/simulations/1/segments/greeting",
        {"text": "欢迎来到直播间"},
    ),
    ("POST", "/api/ecommerce-training/simulations/1/score", None),
    ("GET", "/api/ecommerce-training/copy-training/catalog", None),
    (
        "POST",
        "/api/ecommerce-training/copy-training",
        {"product_type": "food", "scene": "social_commerce"},
    ),
    ("GET", "/api/ecommerce-training/copy-training", None),
    ("GET", "/api/ecommerce-training/copy-training/1", None),
    (
        "POST",
        "/api/ecommerce-training/copy-training/1/critique",
        {"critique": "缺少行动指令"},
    ),
    (
        "POST",
        "/api/ecommerce-training/copy-training/1/copy",
        {"optimized_prompt": "补充规格和行动指令"},
    ),
    (
        "POST",
        "/api/ecommerce-training/copy-training/1/optimization",
        None,
    ),
    (
        "POST",
        "/api/ecommerce-training/store-plans",
        {
            "store_type": "农产品旗舰店",
            "platform": "taobao",
            "style_preference": "温暖可靠",
        },
    ),
    ("GET", "/api/ecommerce-training/store-plans", None),
    ("GET", "/api/ecommerce-training/store-plans/1", None),
    ("GET", "/api/ecommerce-training/customer-service/scenarios", None),
    (
        "POST",
        "/api/ecommerce-training/customer-service/sessions",
        {"scenario_key": "after_sales"},
    ),
    (
        "GET",
        "/api/ecommerce-training/customer-service/sessions",
        None,
    ),
    (
        "GET",
        "/api/ecommerce-training/customer-service/sessions/1",
        None,
    ),
    (
        "POST",
        "/api/ecommerce-training/customer-service/sessions/1/replies",
        {"reply": "请提供订单号"},
    ),
    (
        "POST",
        "/api/ecommerce-training/customer-service/sessions/1/next-message",
        None,
    ),
    (
        "POST",
        "/api/ecommerce-training/customer-service/sessions/1/end",
        None,
    ),
    ("GET", "/api/ecommerce-training/courses", None),
    ("GET", "/api/ecommerce-training/recommendations", None),
    (
        "GET",
        "/api/ecommerce-training/courses/1001/progress",
        None,
    ),
    (
        "PUT",
        "/api/ecommerce-training/courses/1001/progress",
        {"position_seconds": 240, "watched_delta_seconds": 240},
    ),
    ("GET", "/api/ecommerce-training/courses/1001/quiz", None),
    ("GET", "/api/ecommerce-training/courses/1001/comments", None),
    (
        "POST",
        "/api/ecommerce-training/courses/1001/comments",
        {"body": "课程评论"},
    ),
    ("GET", "/api/ecommerce-training/courses/1001/quiz/attempts", None),
    (
        "POST",
        "/api/ecommerce-training/courses/1001/quiz",
        {"answers": {"q1": "A"}},
    ),
]

LIVE_SCRIPT_FIXTURE = {
    "opening": "欢迎来到直播间",
    "product_intro": "这款荔枝干香甜耐储存",
    "interaction": "扣一告诉我你的口味偏好",
    "closing": "现在下单享优惠",
}
SIMULATION_SCORE_FIXTURE = {
    "scores": {
        "pacing": 80,
        "emotion": 72,
        "interaction": 90,
        "selling_point": 66,
    },
    "suggestions": {
        "pacing": "缩短长句。",
        "emotion": "增加情绪词。",
        "interaction": "增加提问。",
        "selling_point": "先讲核心利益。",
    },
}
COPY_CASE_FIXTURE = {
    "copy_text": "这款产品很好，赶紧买。",
    "defect_categories": [
        "missing_key_information",
        "missing_action",
    ],
}
COPY_REFERENCE_FIXTURE = {
    "reference_critique": "缺少价格、规格和行动引导。",
    "consistency_score": 67,
    "reason": "命中两个问题，遗漏信任证据。",
}
COPY_REVISED_FIXTURE = {
    "revised_copy": "精选荔枝干，净含量 250g，限时 39.9 元，点击下单。",
}
COPY_OPTIMIZATION_FIXTURE = {
    "differences": ["补充规格", "补充价格", "增加行动指令"],
    "optimization_score": 88,
    "evidence": "新版包含可验证信息并明确下一步。",
}
STORE_PLAN_FIXTURE = {
    "home_layout": ["顶部活动区", "商品分组"],
    "color_scheme": {
        "primary": "#E43D30",
        "accent": "#F7C948",
    },
    "detail_structure": ["卖点", "参数", "售后"],
    "navigation": ["首页", "新品", "优惠", "客服"],
}
CUSTOMER_OPENING_FIXTURE = {
    "customer_message": "我想咨询退换货，应该怎么处理？"
}
CUSTOMER_SECOND_FIXTURE = {
    "customer_message": "商品已经拆封，还能退吗？"
}
CUSTOMER_ANALYSIS_FALSE_FIXTURE = {
    "problem": "未先确认订单情况",
    "evidence": "学员直接说明退换政策",
    "suggestion": "先询问订单号和商品状态",
    "criteria": {
        "issue_identified": False,
        "policy_and_process_explained": True,
    },
    "goal_status": "not_reached",
}
CUSTOMER_ANALYSIS_TRUE_FIXTURE = {
    "problem": "回应完整",
    "evidence": "先确认拆封状态并说明流程",
    "suggestion": "补充时效",
    "criteria": {
        "issue_identified": True,
        "policy_and_process_explained": True,
    },
    "goal_status": "reached",
}
CUSTOMER_SUMMARY_FIXTURE = {
    "overall_performance": "能承接问题",
    "main_problems": ["首次未确认订单"],
    "prioritized_improvements": ["先确认事实", "补充时效"],
    "goal_completion": "两项目标均完成",
}


class TestEcommerceApi(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(Path(self.temp_dir.name) / "test.db"),
                "SECRET_KEY": "test-only-secret",
                "SESSION_HOURS": 24,
                "SESSION_COOKIE_SECURE": False,
                "AI_API_URL": "",
                "AI_API_KEY": "",
                "AI_MODEL": "test-model",
            }
        )
        self.student_id = self._create_user("student01", "student")
        self._create_user("student02", "student")
        self._create_user("teacher01", "teacher")
        self.client = self._login("student01")
        self.other_client = self._login("student02")
        self.teacher_client = self._login("teacher01")
        self.ai = Mock()
        set_ai_client(self.app, self.ai)

    def tearDown(self):
        self.temp_dir.cleanup()

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
                    username,
                    role,
                    "2026-09-17T00:00:00+00:00",
                    "2026-09-17T00:00:00+00:00",
                ),
            )
            get_db().commit()
        return int(cursor.lastrowid)

    def _login(self, username: str):
        client = self.app.test_client()
        response = client.post(
            "/api/auth/login",
            json={"username": username, "password": "password8"},
        )
        self.assertEqual(response.status_code, 200)
        return client

    def test_blueprint_registers_only_the_exact_route_table(self):
        rules = {
            (
                rule.rule,
                tuple(sorted(rule.methods - {"HEAD", "OPTIONS"})),
            )
            for rule in self.app.url_map.iter_rules()
            if rule.rule.startswith("/api/ecommerce-training")
        }
        replacements = (
            (
                r"/live-scripts/\d+$",
                "/live-scripts/<int:version_id>",
            ),
            (
                r"/simulations/\d+$",
                "/simulations/<int:training_id>",
            ),
            (
                r"/simulations/\d+/segments/[^/]+$",
                (
                    "/simulations/<int:training_id>/"
                    "segments/<segment_key>"
                ),
            ),
            (
                r"/simulations/\d+/score$",
                "/simulations/<int:training_id>/score",
            ),
            (
                r"/copy-training/\d+$",
                "/copy-training/<int:session_id>",
            ),
            (
                r"/copy-training/\d+/(critique|copy|optimization)$",
                r"/copy-training/<int:session_id>/\1",
            ),
            (
                r"/store-plans/\d+$",
                "/store-plans/<int:plan_id>",
            ),
            (
                r"/customer-service/sessions/\d+$",
                (
                    "/customer-service/sessions/"
                    "<int:session_id>"
                ),
            ),
            (
                (
                    r"/customer-service/sessions/\d+/"
                    r"(replies|next-message|end)$"
                ),
                (
                    "/customer-service/sessions/"
                    r"<int:session_id>/\1"
                ),
            ),
            (
                r"/courses/\d+/progress$",
                "/courses/<int:course_id>/progress",
            ),
            (
                r"/courses/\d+/quiz$",
                "/courses/<int:course_id>/quiz",
            ),
            (
                r"/courses/\d+/comments$",
                "/courses/<int:course_id>/comments",
            ),
            (
                r"/courses/\d+/quiz/attempts$",
                "/courses/<int:course_id>/quiz/attempts",
            ),
        )
        expected = set()
        for method, path, _ in ROUTES:
            for pattern, replacement in replacements:
                path = re.sub(pattern, replacement, path)
            expected.add((path, (method,)))

        self.assertEqual(rules, expected)

    def test_every_route_rejects_anonymous_and_teacher_users(self):
        for method, path, payload in ROUTES:
            for client_name, client in (
                ("anonymous", self.app.test_client()),
                ("teacher", self.teacher_client),
            ):
                with self.subTest(
                    method=method,
                    path=path,
                    client=client_name,
                ):
                    response = client.open(
                        path,
                        method=method,
                        json=payload,
                    )

                    self.assertEqual(response.status_code, 401)
                    self.assertEqual(
                        response.get_json()["message"],
                        "未登录或会话已过期",
                    )

    def test_creation_detail_and_action_routes_return_json_envelopes(self):
        self.ai.complete_json.side_effect = [
            LIVE_SCRIPT_FIXTURE,
            SIMULATION_SCORE_FIXTURE,
            COPY_CASE_FIXTURE,
            COPY_REFERENCE_FIXTURE,
            COPY_REVISED_FIXTURE,
            COPY_OPTIMIZATION_FIXTURE,
            STORE_PLAN_FIXTURE,
            CUSTOMER_OPENING_FIXTURE,
            CUSTOMER_ANALYSIS_FALSE_FIXTURE,
            CUSTOMER_SECOND_FIXTURE,
            CUSTOMER_ANALYSIS_TRUE_FIXTURE,
            CUSTOMER_SUMMARY_FIXTURE,
        ]

        live_script = self.client.post(
            "/api/ecommerce-training/live-scripts",
            json={
                "product_name": "荔枝干",
                "selling_points": ["香甜、耐储存"],
                "price_text": "39.9 元",
                "style": "enthusiastic",
            },
        )
        self.assertEqual(live_script.status_code, 201)
        version = live_script.get_json()["version"]
        self.assertEqual(version["script"], LIVE_SCRIPT_FIXTURE)

        history = self.client.get(
            "/api/ecommerce-training/live-scripts"
        )
        self.assertEqual(history.status_code, 200)
        self.assertEqual(
            [item["id"] for item in history.get_json()["versions"]],
            [version["id"]],
        )
        detail = self.client.get(
            f"/api/ecommerce-training/live-scripts/{version['id']}"
        )
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.get_json()["version"], version)

        scenes = self.client.get(
            "/api/ecommerce-training/simulations/scenes"
        )
        self.assertEqual(scenes.status_code, 200)
        self.assertEqual(
            [scene["key"] for scene in scenes.get_json()["scenes"]],
            [
                "opening",
                "product_intro",
                "interaction",
                "closing",
                "objection",
            ],
        )

        started = self.client.post(
            "/api/ecommerce-training/simulations",
            json={"scene_key": "opening"},
        )
        self.assertEqual(started.status_code, 201)
        training_id = started.get_json()["training"]["id"]
        for segment_key, text in (
            ("greeting", "欢迎来到直播间。"),
            ("hook", "今天介绍广东荔枝干。"),
            ("audience_call", "想了解的扣一。"),
        ):
            saved = self.client.put(
                (
                    "/api/ecommerce-training/simulations/"
                    f"{training_id}/segments/{segment_key}"
                ),
                json={"text": text},
            )
            self.assertEqual(saved.status_code, 200)
            self.assertEqual(
                saved.get_json()["training"]["id"],
                training_id,
            )

        scored = self.client.post(
            f"/api/ecommerce-training/simulations/{training_id}/score",
            json=None,
        )
        self.assertEqual(scored.status_code, 200)
        self.assertEqual(scored.get_json()["training"]["total_score"], 77)

        simulations = self.client.get(
            "/api/ecommerce-training/simulations"
        )
        simulation_detail = self.client.get(
            f"/api/ecommerce-training/simulations/{training_id}"
        )
        self.assertEqual(simulations.status_code, 200)
        self.assertEqual(simulation_detail.status_code, 200)
        self.assertEqual(
            simulations.get_json()["trainings"][0]["id"],
            training_id,
        )
        self.assertEqual(
            simulation_detail.get_json()["training"]["id"],
            training_id,
        )

        catalog = self.client.get(
            "/api/ecommerce-training/copy-training/catalog"
        )
        self.assertEqual(catalog.status_code, 200)
        self.assertIn(
            "missing_action",
            catalog.get_json()["catalog"]["defect_categories"],
        )

        copy_created = self.client.post(
            "/api/ecommerce-training/copy-training",
            json={"product_type": "food", "scene": "social_commerce"},
        )
        self.assertEqual(copy_created.status_code, 201)
        copy_id = copy_created.get_json()["session"]["id"]
        copy_critique = self.client.post(
            f"/api/ecommerce-training/copy-training/{copy_id}/critique",
            json={"critique": "缺少规格和行动指令。"},
        )
        copy_revised = self.client.post(
            f"/api/ecommerce-training/copy-training/{copy_id}/copy",
            json={"optimized_prompt": "补充规格、价格和行动指令"},
        )
        copy_completed = self.client.post(
            (
                "/api/ecommerce-training/copy-training/"
                f"{copy_id}/optimization"
            ),
            json=None,
        )
        self.assertEqual(copy_critique.status_code, 200)
        self.assertEqual(copy_revised.status_code, 200)
        self.assertEqual(copy_completed.status_code, 200)
        self.assertEqual(
            copy_completed.get_json()["session"]["status"],
            "completed",
        )

        copy_history = self.client.get(
            "/api/ecommerce-training/copy-training"
        )
        copy_detail = self.client.get(
            f"/api/ecommerce-training/copy-training/{copy_id}"
        )
        self.assertEqual(copy_history.status_code, 200)
        self.assertEqual(copy_detail.status_code, 200)
        self.assertEqual(
            copy_history.get_json()["sessions"][0]["id"],
            copy_id,
        )
        self.assertEqual(copy_detail.get_json()["session"]["id"], copy_id)

        store_created = self.client.post(
            "/api/ecommerce-training/store-plans",
            json={
                "store_type": "农产品旗舰店",
                "platform": "taobao",
                "style_preference": "温暖可靠",
            },
        )
        self.assertEqual(store_created.status_code, 201)
        plan_id = store_created.get_json()["plan"]["id"]
        store_history = self.client.get(
            "/api/ecommerce-training/store-plans"
        )
        store_detail = self.client.get(
            f"/api/ecommerce-training/store-plans/{plan_id}"
        )
        self.assertEqual(store_history.status_code, 200)
        self.assertEqual(store_detail.status_code, 200)
        self.assertEqual(
            store_history.get_json()["plans"][0]["id"],
            plan_id,
        )
        self.assertEqual(store_detail.get_json()["plan"]["id"], plan_id)

        scenarios = self.client.get(
            "/api/ecommerce-training/customer-service/scenarios"
        )
        self.assertEqual(scenarios.status_code, 200)
        self.assertEqual(
            [item["key"] for item in scenarios.get_json()["scenarios"]],
            [
                "product_info",
                "price_promo",
                "shipping",
                "after_sales",
                "complaint",
            ],
        )

        customer_started = self.client.post(
            "/api/ecommerce-training/customer-service/sessions",
            json={"scenario_key": "after_sales"},
        )
        self.assertEqual(customer_started.status_code, 201)
        customer_id = customer_started.get_json()["session"]["id"]
        customer_reply = self.client.post(
            (
                "/api/ecommerce-training/customer-service/sessions/"
                f"{customer_id}/replies"
            ),
            json={"reply": "请提供订单号"},
        )
        next_message = self.client.post(
            (
                "/api/ecommerce-training/customer-service/sessions/"
                f"{customer_id}/next-message"
            ),
            json=None,
        )
        customer_reached = self.client.post(
            (
                "/api/ecommerce-training/customer-service/sessions/"
                f"{customer_id}/replies"
            ),
            json={"reply": "拆封后可按规定申请"},
        )
        customer_ended = self.client.post(
            (
                "/api/ecommerce-training/customer-service/sessions/"
                f"{customer_id}/end"
            ),
            json=None,
        )
        self.assertEqual(customer_reply.status_code, 200)
        self.assertEqual(next_message.status_code, 200)
        self.assertEqual(customer_reached.status_code, 200)
        self.assertEqual(customer_ended.status_code, 200)
        self.assertTrue(
            customer_reached.get_json()["session"]["end_suggested"]
        )
        self.assertEqual(
            customer_ended.get_json()["session"]["status"],
            "completed",
        )

        customer_history = self.client.get(
            "/api/ecommerce-training/customer-service/sessions"
        )
        customer_detail = self.client.get(
            (
                "/api/ecommerce-training/customer-service/sessions/"
                f"{customer_id}"
            )
        )
        self.assertEqual(customer_history.status_code, 200)
        self.assertEqual(customer_detail.status_code, 200)
        self.assertEqual(
            customer_history.get_json()["sessions"][0]["id"],
            customer_id,
        )
        self.assertEqual(
            customer_detail.get_json()["session"]["id"],
            customer_id,
        )

        courses = self.client.get("/api/ecommerce-training/courses")
        recommendations = self.client.get(
            "/api/ecommerce-training/recommendations"
        )
        initial_progress = self.client.get(
            "/api/ecommerce-training/courses/1001/progress"
        )
        completed_progress = self.client.put(
            "/api/ecommerce-training/courses/1001/progress",
            json={"position_seconds": 240, "watched_delta_seconds": 240},
        )
        quiz = self.client.get(
            "/api/ecommerce-training/courses/1001/quiz"
        )
        attempts = self.client.get(
            "/api/ecommerce-training/courses/1001/quiz/attempts"
        )
        self.assertEqual(courses.status_code, 200)
        self.assertEqual(recommendations.status_code, 200)
        self.assertEqual(initial_progress.status_code, 200)
        self.assertEqual(completed_progress.status_code, 200)
        self.assertEqual(
            [course["id"] for course in courses.get_json()["courses"]],
            [1002, 1001],
        )
        self.assertEqual(
            completed_progress.get_json()["progress"]["progress_percent"],
            80,
        )
        self.assertEqual(quiz.status_code, 200)
        self.assertEqual(
            quiz.get_json()["quiz"]["questions"][0]["id"],
            "ecommerce-1001-q1",
        )
        self.assertEqual(attempts.status_code, 200)
        self.assertEqual(attempts.get_json()["attempts"], [])

    def test_quiz_attempt_history_refreshes_and_stays_owner_scoped(self):
        progress = self.client.put(
            "/api/ecommerce-training/courses/1001/progress",
            json={"position_seconds": 240, "watched_delta_seconds": 240},
        )
        self.assertEqual(progress.status_code, 200)

        self.ai.complete_json.return_value = {
            "score": 100,
            "questions": [
                {
                    "id": "ecommerce-1001-q1",
                    "correct": True,
                    "explanation": "达到 80% 即完成。",
                }
            ],
        }
        submitted = self.client.post(
            "/api/ecommerce-training/courses/1001/quiz",
            json={"answers": {"ecommerce-1001-q1": "80%"}},
        )
        self.assertEqual(submitted.status_code, 201)

        history = self.client.get(
            "/api/ecommerce-training/courses/1001/quiz/attempts"
        )
        other_history = self.other_client.get(
            "/api/ecommerce-training/courses/1001/quiz/attempts"
        )
        self.assertEqual(history.status_code, 200)
        self.assertEqual(other_history.status_code, 200)
        self.assertEqual(
            [
                (
                    attempt["id"],
                    attempt["score"],
                    attempt["is_formal"],
                    attempt["is_current"],
                    attempt["is_latest"],
                )
                for attempt in history.get_json()["attempts"]
            ],
            [
                (
                    submitted.get_json()["attempt"]["id"],
                    100,
                    True,
                    True,
                    True,
                )
            ],
        )
        self.assertEqual(other_history.get_json()["attempts"], [])

        self.ai.complete_json.side_effect = AiUnavailableError(
            "raw provider failure"
        )
        failed = self.client.post(
            "/api/ecommerce-training/courses/1001/quiz",
            json={"answers": {"ecommerce-1001-q1": "60%"}},
        )
        refreshed = self.client.get(
            "/api/ecommerce-training/courses/1001/quiz/attempts"
        )

        self.assertEqual(failed.status_code, 503)
        self.assertEqual(
            [
                (
                    attempt["id"],
                    attempt["score"],
                    attempt["is_formal"],
                )
                for attempt in refreshed.get_json()["attempts"]
            ],
            [
                (
                    submitted.get_json()["attempt"]["id"],
                    100,
                    True,
                )
            ],
        )

    def test_errors_map_to_400_404_and_exact_503_without_leaks(self):
        invalid = self.client.post(
            "/api/ecommerce-training/live-scripts",
            json={},
        )
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(invalid.get_json()["message"], "商品名称不能为空")
        self.ai.complete_json.assert_not_called()

        missing = self.client.get(
            "/api/ecommerce-training/live-scripts/999999"
        )
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(
            missing.get_json()["message"],
            "直播话术版本不存在",
        )

        with patch(
            "app.ecommerce_training.routes._get_live_script",
            side_effect=AgriAccessError("无权访问该记录"),
        ):
            access_denied = self.client.get(
                "/api/ecommerce-training/live-scripts/1"
            )
        self.assertEqual(access_denied.status_code, 404)
        self.assertEqual(
            access_denied.get_json()["message"],
            "无权访问该记录",
        )

        self.ai.complete_json.side_effect = AiUnavailableError(
            "raw provider traceback and secret"
        )
        unavailable = self.client.post(
            "/api/ecommerce-training/live-scripts",
            json={
                "product_name": "荔枝干",
                "selling_points": ["香甜"],
                "style": "enthusiastic",
            },
        )
        self.assertEqual(unavailable.status_code, 503)
        self.assertEqual(
            unavailable.get_json(),
            {
                "success": False,
                "message": "AI 服务暂时不可用",
            },
        )
        self.assertNotIn(
            "raw provider traceback and secret",
            unavailable.get_data(as_text=True),
        )

    def test_real_httpx_timeout_maps_to_fixed_ai_unavailable_prompt(self):
        def timeout(request):
            raise httpx.TimeoutException("upstream timed out")

        set_ai_client(
            self.app,
            OpenAiCompatibleAiClient(
                api_url="https://example.test/chat/completions",
                api_key="test-key",
                model="test-model",
                timeout=0.01,
                transport=httpx.MockTransport(timeout),
            ),
        )

        response = self.client.post(
            "/api/ecommerce-training/live-scripts",
            json={
                "product_name": "荔枝干",
                "selling_points": ["香甜"],
                "style": "enthusiastic",
            },
        )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.get_json(),
            {
                "success": False,
                "message": "AI 服务暂时不可用",
            },
        )
        self.assertNotIn("upstream timed out", response.get_data(as_text=True))

    def test_json_endpoints_reject_non_object_bodies(self):
        response = self.client.post(
            "/api/ecommerce-training/live-scripts",
            json=["not", "an", "object"],
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.get_json(),
            {
                "success": False,
                "message": "请求体格式不正确",
                "errors": {"body": "请求体必须是 JSON 对象"},
            },
        )
        self.ai.complete_json.assert_not_called()

    def test_copy_training_rejects_unknown_presets_before_ai_or_insert(self):
        with self.app.app_context():
            before = get_db().execute(
                """
                SELECT COUNT(*) AS count
                FROM ecommerce_copy_training_sessions
                """
            ).fetchone()["count"]

        invalid_product = self.client.post(
            "/api/ecommerce-training/copy-training",
            json={"product_type": "unknown", "scene": "social_commerce"},
        )
        invalid_scene = self.client.post(
            "/api/ecommerce-training/copy-training",
            json={"product_type": "food", "scene": "unknown"},
        )

        self.assertEqual(invalid_product.status_code, 400)
        self.assertEqual(invalid_scene.status_code, 400)
        self.ai.complete_json.assert_not_called()
        with self.app.app_context():
            after = get_db().execute(
                """
                SELECT COUNT(*) AS count
                FROM ecommerce_copy_training_sessions
                """
            ).fetchone()["count"]
        self.assertEqual(after, before)

    def test_history_routes_do_not_leak_other_students_records(self):
        self.ai.complete_json.return_value = LIVE_SCRIPT_FIXTURE
        created = self.client.post(
            "/api/ecommerce-training/live-scripts",
            json={
                "product_name": "荔枝干",
                "selling_points": ["香甜"],
                "style": "enthusiastic",
            },
        )
        self.assertEqual(created.status_code, 201)
        version_id = created.get_json()["version"]["id"]

        foreign_detail = self.other_client.get(
            f"/api/ecommerce-training/live-scripts/{version_id}"
        )
        foreign_history = self.other_client.get(
            "/api/ecommerce-training/live-scripts"
        )

        self.assertEqual(foreign_detail.status_code, 404)
        self.assertEqual(foreign_history.status_code, 200)
        self.assertEqual(foreign_history.get_json()["versions"], [])


if __name__ == "__main__":
    unittest.main()
