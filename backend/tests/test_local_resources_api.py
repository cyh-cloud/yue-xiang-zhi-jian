import base64
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from werkzeug.security import generate_password_hash

from app import create_app
from app.agri_skills.ai_client import set_ai_client
from app.db import get_db
from app.government_console.errors import (
    ProviderAccessDeniedError,
    ProviderConflictError,
    ProviderUnavailableError,
)
from app.government_console.providers import set_policy_news_provider
from app.local_resources.tts import TtsAudio, set_local_tts_client


class LocalResourceApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(Path(self.temp_dir.name) / "test.db"),
                "SECRET_KEY": "test",
                "AI_TTS_VOICE_YUE": "voice-yue",
                "AI_TTS_VOICE_HAKKA": "voice-hak",
                "AI_TTS_VOICE_TEOCHEW": "voice-nan",
            }
        )
        with self.app.app_context():
            self.student_id = self._insert_user("student01", "student")
            self.teacher_id = self._insert_user("teacher01", "teacher")

        self.policy = {
            "id": "policy-1",
            "title": "创业补贴",
            "content": "补贴正文",
            "category_code": "entrepreneurship",
            "category_label": "创业支持",
            "published_at": "2026-09-19T10:00:00+08:00",
            "updated_at": "2026-09-19T10:00:00+08:00",
            "version": 1,
        }
        self.news = {
            "id": "news-1",
            "title": "暴雨预警",
            "content": "预警正文",
            "category_code": "disaster_warning",
            "category_label": "灾害预警",
            "published_at": "2026-09-19T11:00:00+08:00",
            "updated_at": "2026-09-19T11:00:00+08:00",
            "version": 1,
        }
        self.provider = Mock()
        self.provider.list_published_policies.return_value = [self.policy]
        self.provider.get_published_policy.return_value = self.policy
        self.provider.list_published_news.return_value = [self.news]
        self.provider.get_published_news.return_value = self.news
        self.provider.record_policy_view.return_value = 1
        self.provider.record_news_view.return_value = 1
        set_policy_news_provider(self.app, self.provider)

        self.ai = Mock()
        self.ai.complete_json.return_value = {
            "dialect_text": "方言回答",
            "mandarin_text": "普通话回答",
        }
        set_ai_client(self.app, self.ai)
        self.tts = Mock(
            synthesize=Mock(return_value=TtsAudio(b"ID3", "audio/mpeg"))
        )
        set_local_tts_client(self.app, self.tts)
        self.student = self._login("student01")
        self.teacher = self._login("teacher01")

    def tearDown(self):
        self.temp_dir.cleanup()

    def _insert_user(self, username, role):
        cursor = get_db().execute(
            """
            INSERT INTO users (
                username, password_hash, name, role, is_enabled,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, 1, ?, ?)
            """,
            (
                username,
                generate_password_hash("password8"),
                username,
                role,
                "2026-09-19T00:00:00+08:00",
                "2026-09-19T00:00:00+08:00",
            ),
        )
        user_id = int(cursor.lastrowid)
        if role == "student":
            get_db().execute(
                """
                INSERT INTO student_profiles (
                    user_id, contact, learning_direction, updated_at
                ) VALUES (?, '', 'comprehensive', ?)
                """,
                (user_id, "2026-09-19T00:00:00+08:00"),
            )
        get_db().commit()
        return user_id

    def _login(self, username):
        client = self.app.test_client()
        response = client.post(
            "/api/auth/login",
            json={"username": username, "password": "password8"},
        )
        self.assertEqual(response.status_code, 200)
        return client

    def _assign_tag(self, user_id, tag_name):
        get_db().execute(
            """
            INSERT INTO student_interest_tags (user_id, tag_id)
            SELECT ?, id FROM interest_tags WHERE name = ?
            """,
            (user_id, tag_name),
        )
        get_db().commit()

    def test_exact_local_resource_routes_are_registered(self):
        expected = {
            ("GET", "/api/local-resources/cases"),
            ("GET", "/api/local-resources/cases/<case_id>"),
            ("GET", "/api/local-resources/policies"),
            ("GET", "/api/local-resources/policies/<policy_id>"),
            ("GET", "/api/local-resources/policy-subscriptions"),
            (
                "POST",
                "/api/local-resources/policy-subscriptions/<category_code>",
            ),
            (
                "DELETE",
                "/api/local-resources/policy-subscriptions/<category_code>",
            ),
            ("GET", "/api/local-resources/news"),
            ("GET", "/api/local-resources/news/<news_id>"),
            (
                "POST",
                "/api/local-resources/policies/<policy_id>/views",
            ),
            ("POST", "/api/local-resources/news/<news_id>/views"),
            (
                "POST",
                "/api/local-resources/dialect-assistant/turns",
            ),
        }
        actual = {
            (method, str(rule))
            for rule in self.app.url_map.iter_rules()
            if str(rule).startswith("/api/local-resources")
            for method in rule.methods
            if method in {"GET", "POST", "DELETE"}
        }
        self.assertEqual(actual, expected)

    def test_student_can_list_cases_and_subscribe(self):
        cases = self.student.get("/api/local-resources/cases")
        self.assertEqual(cases.status_code, 200)
        self.assertEqual(set(cases.get_json()), {"success", "cases"})
        self.assertGreaterEqual(len(cases.get_json()["cases"]), 3)

        case_id = cases.get_json()["cases"][0]["id"]
        detail = self.student.get(
            f"/api/local-resources/cases/{case_id}"
        )
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(set(detail.get_json()), {"success", "case"})
        self.assertEqual(detail.get_json()["case"]["id"], case_id)

        with self.app.app_context():
            self._assign_tag(self.student_id, "电商直播")
        subscriptions = self.student.get(
            "/api/local-resources/policy-subscriptions"
        )
        self.assertEqual(subscriptions.status_code, 200)
        self.assertEqual(
            set(subscriptions.get_json()),
            {"success", "subscriptions"},
        )
        self.assertIn(
            "ecommerce",
            subscriptions.get_json()["subscriptions"][
                "recommended_category_codes"
            ],
        )

        subscribed = self.student.post(
            "/api/local-resources/policy-subscriptions/ecommerce"
        )
        self.assertEqual(subscribed.status_code, 200)
        self.assertEqual(
            set(subscribed.get_json()),
            {"success", "subscription"},
        )
        self.assertEqual(
            subscribed.get_json()["subscription"]["subscribed"],
            True,
        )

        unsubscribed = self.student.delete(
            "/api/local-resources/policy-subscriptions/ecommerce"
        )
        self.assertEqual(unsubscribed.status_code, 200)
        self.assertEqual(
            unsubscribed.get_json()["subscription"]["subscribed"],
            False,
        )

    def test_policy_and_news_routes_have_exact_payloads(self):
        policies = self.student.get(
            "/api/local-resources/policies?category=entrepreneurship"
        )
        self.assertEqual(policies.status_code, 200)
        self.assertEqual(
            policies.get_json(),
            {"success": True, "policies": [self.policy]},
        )
        self.provider.list_published_policies.assert_called_with(
            "entrepreneurship"
        )

        policy = self.student.get(
            "/api/local-resources/policies/policy-1"
        )
        self.assertEqual(policy.status_code, 200)
        self.assertEqual(
            policy.get_json(),
            {"success": True, "policy": self.policy},
        )

        news = self.student.get(
            "/api/local-resources/news?category=disaster_warning"
        )
        self.assertEqual(news.status_code, 200)
        self.assertEqual(
            news.get_json(),
            {"success": True, "news": [self.news]},
        )
        self.provider.list_published_news.assert_called_with(
            "disaster_warning"
        )

        detail = self.student.get(
            "/api/local-resources/news/news-1"
        )
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(
            detail.get_json(),
            {"success": True, "news": self.news},
        )

    def test_teacher_and_anonymous_are_rejected(self):
        self.assertEqual(
            self.app.test_client().get(
                "/api/local-resources/cases"
            ).status_code,
            401,
        )
        rejected = self.teacher.get("/api/local-resources/cases")
        self.assertEqual(rejected.status_code, 403)
        self.assertEqual(
            set(rejected.get_json()),
            {"success", "message", "details"},
        )

    def test_dialect_endpoint_returns_base64_audio_without_storing_it(self):
        response = self.student.post(
            "/api/local-resources/dialect-assistant/turns",
            json={"dialect_code": "yue", "question": "几时种荔枝？"},
        )
        payload = response.get_json()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            set(payload),
            {"success", "turn", "audio_base64", "audio_content_type"},
        )
        self.assertEqual(
            base64.b64decode(payload["audio_base64"]),
            b"ID3",
        )
        self.assertEqual(payload["audio_content_type"], "audio/mpeg")
        self.assertNotIn("audio_content", payload["turn"])
        self.assertNotIn("audio_content_type", payload["turn"])
        with self.app.app_context():
            row = get_db().execute(
                "SELECT * FROM local_resource_dialect_turns"
            ).fetchone()
            columns = {
                item["name"]
                for item in get_db().execute(
                    "PRAGMA table_info(local_resource_dialect_turns)"
                ).fetchall()
            }
        self.assertEqual(row["dialect_answer"], "方言回答")
        self.assertFalse(
            any("audio" in column for column in columns)
        )

    def test_view_endpoint_requires_event_id_and_delegates(self):
        bad = self.student.post(
            "/api/local-resources/policies/policy-1/views",
            json={},
        )
        self.assertEqual(bad.status_code, 400)
        self.provider.record_policy_view.assert_not_called()

        good = self.student.post(
            "/api/local-resources/policies/policy-1/views",
            json={"view_event_id": "view-1"},
        )
        self.assertEqual(good.status_code, 200)
        self.assertEqual(
            good.get_json(),
            {"success": True, "view_count": 1},
        )
        self.provider.record_policy_view.assert_called_once_with(
            "policy-1",
            "view-1",
        )

        news = self.student.post(
            "/api/local-resources/news/news-1/views",
            json={"view_event_id": "news-view-1"},
        )
        self.assertEqual(news.status_code, 200)
        self.assertEqual(
            news.get_json(),
            {"success": True, "view_count": 1},
        )
        self.provider.record_news_view.assert_called_once_with(
            "news-1",
            "news-view-1",
        )

    def test_malformed_bodies_are_rejected_before_route_logic(self):
        paths = (
            "/api/local-resources/dialect-assistant/turns",
            "/api/local-resources/policies/policy-1/views",
            "/api/local-resources/news/news-1/views",
        )
        for path in paths:
            with self.subTest(path=path):
                response = self.student.post(path, json=[])
                self.assertEqual(response.status_code, 400)
                self.assertEqual(
                    response.get_json(),
                    {
                        "success": False,
                        "message": "请求格式不正确",
                        "details": {
                            "body": "请求体必须是 JSON 对象",
                        },
                    },
                )

        self.ai.complete_json.assert_not_called()
        self.tts.synthesize.assert_not_called()
        self.provider.record_policy_view.assert_not_called()
        self.provider.record_news_view.assert_not_called()

    def test_local_resource_errors_map_to_exact_statuses(self):
        invalid = self.student.get(
            "/api/local-resources/policies?category=unknown"
        )
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(
            set(invalid.get_json()),
            {"success", "message", "details"},
        )

        missing = self.student.get(
            "/api/local-resources/cases/missing"
        )
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(
            set(missing.get_json()),
            {"success", "message", "details"},
        )

        self.provider.record_policy_view.side_effect = (
            ProviderConflictError("浏览事件冲突")
        )
        conflict = self.student.post(
            "/api/local-resources/policies/policy-1/views",
            json={"view_event_id": "view-1"},
        )
        self.assertEqual(conflict.status_code, 409)
        self.assertEqual(conflict.get_json()["message"], "浏览事件冲突")
        self.assertFalse(conflict.get_json()["success"])
        self.assertIn("details", conflict.get_json())

        self.provider.list_published_news.side_effect = (
            ProviderUnavailableError("新闻暂不可用")
        )
        unavailable = self.student.get(
            "/api/local-resources/news"
        )
        self.assertEqual(unavailable.status_code, 503)
        self.assertEqual(
            unavailable.get_json()["message"],
            "新闻暂不可用",
        )
        self.assertFalse(unavailable.get_json()["success"])
        self.assertIn("details", unavailable.get_json())

        self.provider.record_news_view.side_effect = (
            ProviderAccessDeniedError("无权记录浏览")
        )
        denied = self.student.post(
            "/api/local-resources/news/news-1/views",
            json={"view_event_id": "news-view-1"},
        )
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(denied.get_json()["message"], "无权记录浏览")
        self.assertFalse(denied.get_json()["success"])
        self.assertIn("details", denied.get_json())

    def test_create_app_installs_defaults_and_registers_bridge(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            app = create_app(
                {
                    "TESTING": True,
                    "DATABASE_PATH": str(Path(temp_dir) / "test.db"),
                }
            )

            from app.enterprise_console.messaging_provider import (
                EnterpriseMessagingProvider,
            )
            from app.local_resources import (
                DatabaseLocalResourceCaseProvider,
                OpenAiCompatibleTtsClient,
            )
            from app.local_resources.messaging_provider import (
                LocalResourcesMessagingProvider,
            )

            self.assertIsInstance(
                app.extensions["local_resource_case_provider"],
                DatabaseLocalResourceCaseProvider,
            )
            self.assertIsInstance(
                app.extensions["local_resource_tts_client"],
                OpenAiCompatibleTtsClient,
            )
            sources = app.extensions[
                "messaging_source_provider"
            ].providers
            self.assertIsInstance(
                sources[-2],
                EnterpriseMessagingProvider,
            )
            self.assertIsInstance(
                sources[-1],
                LocalResourcesMessagingProvider,
            )

    def test_default_install_does_not_replace_injected_services(self):
        from app.local_resources import (
            install_default_local_resource_services,
        )
        from app.local_resources.cases import (
            set_local_resource_case_provider,
        )

        case_provider = Mock()
        tts_client = Mock()
        set_local_resource_case_provider(self.app, case_provider)
        set_local_tts_client(self.app, tts_client)

        install_default_local_resource_services(self.app)

        self.assertIs(
            self.app.extensions["local_resource_case_provider"],
            case_provider,
        )
        self.assertIs(
            self.app.extensions["local_resource_tts_client"],
            tts_client,
        )

    def test_default_tts_api_key_prefers_specific_then_shared(self):
        from app.local_resources import OpenAiCompatibleTtsClient

        cases = (
            ("tts-specific", "shared", "tts-specific"),
            ("", "shared", "shared"),
        )
        for specific_key, shared_key, expected in cases:
            with self.subTest(expected=expected):
                with tempfile.TemporaryDirectory() as temp_dir:
                    app = create_app(
                        {
                            "TESTING": True,
                            "DATABASE_PATH": str(
                                Path(temp_dir) / "test.db"
                            ),
                            "AI_API_KEY": shared_key,
                            "AI_TTS_API_KEY": specific_key,
                        }
                    )
                client = app.extensions["local_resource_tts_client"]
                self.assertIsInstance(
                    client,
                    OpenAiCompatibleTtsClient,
                )
                self.assertEqual(client.api_key, expected)


if __name__ == "__main__":
    unittest.main()
