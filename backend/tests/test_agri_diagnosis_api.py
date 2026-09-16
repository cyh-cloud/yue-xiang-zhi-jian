import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from werkzeug.security import generate_password_hash

from app import create_app
from app.agri_skills.ai_client import set_ai_client
from app.agri_skills.errors import AiUnavailableError
from app.db import get_db


class TestAgriDiagnosisApi(unittest.TestCase):
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

        self._create_user("student01", "student")
        self._create_user("student02", "student")
        self._create_user("teacher01", "teacher")
        self.client = self._login("student01")
        self.other_client = self._login("student02")
        self.teacher_client = self._login("teacher01")

        self.ai = Mock()
        set_ai_client(self.app, self.ai)
        self.ai.complete_json.return_value = {
            "status": "follow_up_required",
            "question": "请补充症状出现时间",
            "conclusion": None,
            "limited": False,
        }
        self.questions = [
            {
                "type": "single_choice",
                "prompt": "蒂蛀虫防治的第一步是什么？",
                "options": ["清理落果", "增加浇水"],
                "answer": "清理落果",
            },
            {
                "type": "true_false",
                "prompt": "药剂防治应按登记说明使用。",
                "options": ["正确", "错误"],
                "answer": "正确",
            },
            {
                "type": "single_choice",
                "prompt": "雨后应重点检查什么？",
                "options": ["落果和虫孔", "果实甜度"],
                "answer": "落果和虫孔",
            },
        ]

    def tearDown(self):
        self.temp_dir.cleanup()

    def _create_user(self, username: str, role: str) -> None:
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
                    username,
                    role,
                    "2026-09-15T00:00:00+00:00",
                    "2026-09-15T00:00:00+00:00",
                ),
            )
            get_db().commit()

    def _login(self, username: str):
        client = self.app.test_client()
        response = client.post(
            "/api/auth/login",
            json={"username": username, "password": "password8"},
        )
        self.assertEqual(response.status_code, 200)
        return client

    def _complete_diagnosis(self) -> int:
        self.ai.complete_json.side_effect = [
            {
                "status": "follow_up_required",
                "question": "请补充症状出现时间",
                "conclusion": None,
                "limited": False,
            },
            {
                "status": "conclusion_ready",
                "question": None,
                "conclusion": {
                    "cause": "果实受蒂蛀虫危害",
                    "treatment": "清理落果并按登记药剂防治",
                },
                "limited": False,
            },
        ]
        created = self.client.post(
            "/api/agri-skills/diagnoses",
            json={
                "product_key": "litchi",
                "affected_part": "fruit",
                "symptoms": ["虫蛀", "落果"],
            },
        )
        self.assertEqual(created.status_code, 201)
        session_id = created.get_json()["session"]["id"]

        answered = self.client.post(
            f"/api/agri-skills/diagnoses/{session_id}/answers",
            json={"answer": "果实有虫孔并有落果", "input_mode": "text"},
        )
        self.assertEqual(answered.status_code, 200)
        self.assertEqual(
            answered.get_json()["session"]["status"],
            "completed",
        )
        self.ai.complete_json.side_effect = None
        return session_id

    def test_create_list_detail_start_and_answer_routes(self):
        created = self.client.post(
            "/api/agri-skills/diagnoses",
            json={
                "product_key": "litchi",
                "affected_part": "fruit",
                "symptoms": ["虫蛀", "落果"],
            },
        )

        self.assertEqual(created.status_code, 201)
        session = created.get_json()["session"]
        session_id = session["id"]
        self.assertEqual(session["status"], "in_progress")
        self.assertEqual(session["pending_question"], "请补充症状出现时间")

        listed = self.client.get("/api/agri-skills/diagnoses")

        self.assertEqual(listed.status_code, 200)
        self.assertEqual(
            [item["id"] for item in listed.get_json()["diagnoses"]],
            [session_id],
        )

        detail = self.client.get(
            f"/api/agri-skills/diagnoses/{session_id}"
        )

        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.get_json()["session"]["id"], session_id)

        calls_before_start = self.ai.complete_json.call_count
        started = self.client.post(
            f"/api/agri-skills/diagnoses/{session_id}/start"
        )

        self.assertEqual(started.status_code, 200)
        self.assertEqual(
            started.get_json()["session"]["pending_question"],
            "请补充症状出现时间",
        )
        self.assertEqual(self.ai.complete_json.call_count, calls_before_start)

        self.ai.complete_json.return_value = {
            "status": "conclusion_ready",
            "question": None,
            "conclusion": {
                "cause": "果实受蒂蛀虫危害",
                "treatment": "清理落果并按登记药剂防治",
            },
            "limited": False,
        }
        answered = self.client.post(
            f"/api/agri-skills/diagnoses/{session_id}/answers",
            json={"answer": "果实有虫孔并有落果", "input_mode": "text"},
        )

        self.assertEqual(answered.status_code, 200)
        self.assertEqual(answered.get_json()["status"], "conclusion_ready")
        self.assertEqual(
            answered.get_json()["session"]["status"],
            "completed",
        )
        self.assertEqual(
            answered.get_json()["session"]["conclusion"]["cause"],
            "果实受蒂蛀虫危害",
        )

    def test_abandon_route_is_idempotent(self):
        created = self.client.post(
            "/api/agri-skills/diagnoses",
            json={
                "product_key": "litchi",
                "affected_part": "fruit",
                "symptoms": ["虫蛀"],
            },
        )
        session_id = created.get_json()["session"]["id"]

        abandoned = self.client.post(
            f"/api/agri-skills/diagnoses/{session_id}/abandon"
        )
        repeated = self.client.post(
            f"/api/agri-skills/diagnoses/{session_id}/abandon"
        )

        self.assertEqual(abandoned.status_code, 200)
        self.assertEqual(repeated.status_code, 200)
        self.assertEqual(
            abandoned.get_json()["session"]["status"],
            "abandoned",
        )
        self.assertIsNotNone(
            abandoned.get_json()["session"]["abandoned_at"]
        )
        self.assertEqual(
            repeated.get_json()["session"]["abandoned_at"],
            abandoned.get_json()["session"]["abandoned_at"],
        )

    def test_followup_and_repeat_routes(self):
        session_id = self._complete_diagnosis()

        followup = self.client.post(
            f"/api/agri-skills/diagnoses/{session_id}/followups",
            json={"outcome": "worsened", "note": "雨后仍有落果"},
        )

        self.assertEqual(followup.status_code, 201)
        followup_body = followup.get_json()["followup"]
        self.assertEqual(followup_body["outcome"], "worsened")
        self.assertEqual(followup_body["note"], "雨后仍有落果")

        self.ai.complete_json.return_value = {
            "status": "follow_up_required",
            "question": "复诊后症状范围是否扩大",
            "conclusion": None,
            "limited": False,
        }
        repeated = self.client.post(
            f"/api/agri-skills/diagnoses/{session_id}/repeat",
            json={"followup_id": followup_body["id"]},
        )

        self.assertEqual(repeated.status_code, 201)
        repeated_session = repeated.get_json()["session"]
        self.assertEqual(repeated_session["source_session_id"], session_id)
        self.assertEqual(
            repeated_session["source_followup_id"],
            followup_body["id"],
        )
        self.assertEqual(
            repeated_session["source_context"]["followup_status"],
            "worsened",
        )

    def test_self_test_generate_and_submit_routes(self):
        session_id = self._complete_diagnosis()
        self.ai.complete_json.return_value = {"questions": self.questions}

        generated = self.client.post(
            f"/api/agri-skills/diagnoses/{session_id}/self-test"
        )

        self.assertEqual(generated.status_code, 201)
        self_test = generated.get_json()["self_test"]
        self_test_id = self_test["id"]
        self.assertEqual(self_test["generation_attempts"], 1)
        self.assertTrue(
            all("answer" not in item for item in self_test["questions"])
        )

        answers = {
            "q1": "清理落果",
            "q2": "正确",
            "q3": "落果和虫孔",
        }
        self.ai.complete_json.return_value = {
            "score": 100,
            "questions": [
                {"correct": True, "explanation": "清理落果可减少虫源。"},
                {"correct": True, "explanation": "必须按登记说明用药。"},
                {"correct": True, "explanation": "雨后重点检查落果和虫孔。"},
            ],
        }
        submitted = self.client.post(
            f"/api/agri-skills/self-tests/{self_test_id}/submit",
            json={"answers": answers},
        )

        self.assertEqual(submitted.status_code, 200)
        result = submitted.get_json()["result"]
        self.assertEqual(result["score"], 100)
        self.assertTrue(all(item["correct"] for item in result["questions"]))

    def test_error_mapping_and_resource_ownership(self):
        invalid = self.client.post(
            "/api/agri-skills/diagnoses",
            json={
                "product_key": "missing-product",
                "affected_part": "fruit",
                "symptoms": ["虫蛀"],
            },
        )

        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(invalid.get_json()["message"], "产品不存在")
        self.assertEqual(
            invalid.get_json()["errors"],
            {"product_key": "产品不存在"},
        )

        created = self.client.post(
            "/api/agri-skills/diagnoses",
            json={
                "product_key": "litchi",
                "affected_part": "fruit",
                "symptoms": ["虫蛀"],
            },
        )
        session_id = created.get_json()["session"]["id"]
        foreign = self.other_client.get(
            f"/api/agri-skills/diagnoses/{session_id}"
        )

        self.assertEqual(foreign.status_code, 404)
        self.assertEqual(
            foreign.get_json()["message"],
            "诊断记录不存在",
        )

        self.ai.complete_json.side_effect = AiUnavailableError(
            "AI 服务暂时不可用"
        )
        unavailable = self.client.post(
            f"/api/agri-skills/diagnoses/{session_id}/answers",
            json={"answer": "果实有虫孔", "input_mode": "text"},
        )

        self.assertEqual(unavailable.status_code, 503)
        self.assertEqual(
            unavailable.get_json()["message"],
            "AI 服务暂时不可用",
        )

    def test_all_routes_require_active_student(self):
        requests = [
            ("POST", "/api/agri-skills/diagnoses", {}),
            ("GET", "/api/agri-skills/diagnoses", None),
            ("GET", "/api/agri-skills/diagnoses/1", None),
            ("POST", "/api/agri-skills/diagnoses/1/start", None),
            (
                "POST",
                "/api/agri-skills/diagnoses/1/answers",
                {"answer": "补充", "input_mode": "text"},
            ),
            ("POST", "/api/agri-skills/diagnoses/1/abandon", None),
            (
                "POST",
                "/api/agri-skills/diagnoses/1/followups",
                {"outcome": "improved"},
            ),
            (
                "POST",
                "/api/agri-skills/diagnoses/1/repeat",
                {"followup_id": 1},
            ),
            ("POST", "/api/agri-skills/diagnoses/1/self-test", None),
            (
                "POST",
                "/api/agri-skills/self-tests/1/submit",
                {"answers": {}},
            ),
        ]

        for method, path, payload in requests:
            for client_name, client in (
                ("anonymous", self.app.test_client()),
                ("teacher", self.teacher_client),
            ):
                with self.subTest(
                    method=method,
                    path=path,
                    client=client_name,
                ):
                    response = client.open(path, method=method, json=payload)

                    self.assertEqual(response.status_code, 401)
                    self.assertEqual(
                        response.get_json()["message"],
                        "未登录或会话已过期",
                    )


if __name__ == "__main__":
    unittest.main()
