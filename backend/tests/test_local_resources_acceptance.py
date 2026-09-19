import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from werkzeug.security import generate_password_hash

from app import create_app
from app.agri_skills.ai_client import set_ai_client
from app.agri_skills.errors import AgriValidationError, AiUnavailableError
from app.db import get_db
from app.government_console.dashboard import get_government_dashboard
from app.government_console.news import delete_news, publish_news
from app.government_console.policy import (
    delete_policy,
    publish_policy,
    relist_policy,
    unpublish_policy,
)
from app.government_console.providers import (
    get_policy_news_provider,
)
from app.local_resources.catalog import get_news, get_policy
from app.local_resources.dialect_assistant import complete_dialect_turn
from app.local_resources.errors import LocalResourceNotFoundError
from app.local_resources.subscriptions import (
    recommend_policy_categories,
    set_policy_subscription,
)
from app.local_resources.tts import TtsAudio, set_local_tts_client
from app.local_resources.views import (
    record_news_view,
    record_policy_view,
)
from app.messaging.source_provider import get_messaging_source_provider


class LocalResourceAcceptanceTests(unittest.TestCase):
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
            self.government_id = self._insert_user(
                "government01",
                "government",
            )
        self.ai = Mock()
        self.ai.complete_json.return_value = {
            "dialect_text": "方言回答",
            "mandarin_text": "普通话回答",
        }
        set_ai_client(self.app, self.ai)
        self.tts = Mock()
        self.tts.synthesize.return_value = TtsAudio(b"ID3", "audio/mpeg")
        set_local_tts_client(self.app, self.tts)

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
        get_db().commit()
        if role == "student":
            get_db().execute(
                """
                INSERT INTO student_profiles (
                    user_id, contact, learning_direction, updated_at
                ) VALUES (?, '', 'comprehensive', ?)
                """,
                (
                    int(cursor.lastrowid),
                    "2026-09-19T00:00:00+08:00",
                ),
            )
            get_db().commit()
        return int(cursor.lastrowid)

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

    def test_dialect_three_mappings_and_no_audio_persistence(self):
        captured = []

        class RecordingTts:
            def synthesize(self, text, language_code, voice_code, *, call_point):
                del text, voice_code, call_point
                captured.append(language_code)
                return TtsAudio(b"ID3", "audio/mpeg")

        set_local_tts_client(self.app, RecordingTts())
        with self.app.app_context():
            for dialect_code in ("yue", "hak", "nan"):
                complete_dialect_turn(
                    self.student_id,
                    dialect_code,
                    "问题",
                )
            stored_columns = {
                row["name"]
                for row in get_db().execute(
                    "PRAGMA table_info(local_resource_dialect_turns)"
                )
            }
        self.assertEqual(captured, ["yue", "hak", "nan"])
        self.assertNotIn("audio", stored_columns)

    def test_policy_subscription_audience_and_view_idempotency(self):
        with self.app.app_context():
            set_policy_subscription(
                self.student_id,
                "ecommerce",
                True,
            )
            policy = publish_policy(
                actor_id=self.government_id,
                request_id="policy-acceptance",
                title="电商培训补贴",
                content="正文",
                category_code="ecommerce",
            )
            totals = [
                record_policy_view(policy["id"], "same-event")
                for _ in range(10)
            ]
            totals.extend(
                record_policy_view(policy["id"], event_id)
                for event_id in ("new-event-1", "new-event-2", "new-event-3")
            )
            dashboard = get_government_dashboard()
            notifications = get_db().execute(
                """
                SELECT recipient_id, body
                FROM system_notifications
                WHERE event_type = 'policy_published'
                """
            ).fetchall()
        self.assertEqual(totals[:10], [1] * 10)
        self.assertEqual(totals[10:], [2, 3, 4])
        self.assertEqual(dashboard["policy"]["view_count"], 4)
        self.assertEqual(
            [(row["recipient_id"], row["body"]) for row in notifications],
            [(self.student_id, "政策类别：电商")],
        )

    def test_policy_unpublish_relist_delete_semantics(self):
        with self.app.app_context():
            set_policy_subscription(
                self.student_id,
                "entrepreneurship",
                True,
            )
            self.assertEqual(
                get_messaging_source_provider().list_policy_subscriber_ids(
                    "创业支持"
                ),
                [self.student_id],
            )
            policy = publish_policy(
                actor_id=self.government_id,
                request_id="policy-lifecycle",
                title="创业支持",
                content="正文",
                category_code="entrepreneurship",
            )
            self.assertEqual(record_policy_view(policy["id"], "view-1"), 1)
            hidden = unpublish_policy(
                policy["id"],
                expected_version=policy["version"],
            )
            with self.assertRaises(LocalResourceNotFoundError):
                get_policy(policy["id"])
            visible = relist_policy(
                policy["id"],
                expected_version=hidden["version"],
            )
            self.assertEqual(
                get_policy(policy["id"])["id"],
                policy["id"],
            )
            self.assertEqual(
                record_policy_view(policy["id"], "view-2"),
                2,
            )
            self.assertEqual(
                get_government_dashboard()["policy"]["view_count"],
                2,
            )
            notification_count = get_db().execute(
                """
                SELECT COUNT(*) AS count
                FROM system_notifications
                WHERE event_type = 'policy_published'
                """
            ).fetchone()["count"]
            delete_policy(
                policy["id"],
                expected_version=visible["version"],
            )
            with self.assertRaises(LocalResourceNotFoundError):
                get_policy(policy["id"])
            dashboard = get_government_dashboard()
        self.assertEqual(notification_count, 1)
        self.assertEqual(dashboard["policy"]["total_count"], 0)
        self.assertEqual(dashboard["policy"]["view_count"], 0)

    def test_news_publish_delete_and_no_push(self):
        with self.app.app_context():
            before = get_db().execute(
                """
                SELECT COUNT(*) AS count
                FROM system_notifications
                WHERE event_type = 'policy_published'
                """
            ).fetchone()["count"]
            news = publish_news(
                actor_id=self.government_id,
                request_id="news-acceptance",
                title="暴雨预警",
                content="注意防范",
                category_code="disaster_warning",
            )
            self.assertEqual(get_news(news["id"])["title"], "暴雨预警")
            self.assertEqual(record_news_view(news["id"], "view-1"), 1)
            visible_dashboard = get_government_dashboard()
            self.assertEqual(visible_dashboard["news"]["total_count"], 1)
            self.assertEqual(visible_dashboard["news"]["view_count"], 1)
            delete_news(news["id"], expected_version=news["version"])
            with self.assertRaises(LocalResourceNotFoundError):
                get_news(news["id"])
            deleted_dashboard = get_government_dashboard()
            self.assertEqual(deleted_dashboard["news"]["total_count"], 0)
            self.assertEqual(deleted_dashboard["news"]["view_count"], 0)
            after = get_db().execute(
                """
                SELECT COUNT(*) AS count
                FROM system_notifications
                WHERE event_type = 'policy_published'
                """
            ).fetchone()["count"]
        self.assertEqual(after, before)

    def test_asr_route_is_reused_and_ai_path_has_no_local_fallback(self):
        root = Path(__file__).parents[1] / "app"
        local_source = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (root / "local_resources").glob("*.py")
        )
        agri_source = (root / "agri_skills" / "routes.py").read_text(
            encoding="utf-8"
        )
        self.assertEqual(
            agri_source.count('@agri_skills_bp.post("/speech/transcriptions")'),
            1,
        )
        self.assertNotIn("local_kb", local_source)
        self.assertNotIn("government_policies", local_source)
        self.assertNotIn("government_news", local_source)
        self.assertNotIn("set_policy_news_provider", local_source)
        self.assertNotIn("def transcribe(", local_source)

    def test_asr_ai_tts_failures_and_case_write_boundary(self):
        student = self._login("student01")
        empty = student.post(
            "/api/agri-skills/speech/transcriptions",
            data={},
            content_type="multipart/form-data",
        )
        self.assertEqual(empty.status_code, 422)
        self.assertEqual(
            empty.get_json()["message"],
            "未能识别，请重试或改用文字输入",
        )
        self.ai.transcribe.side_effect = AgriValidationError(
            "未能识别，请重试或改用文字输入"
        )
        noise = student.post(
            "/api/agri-skills/speech/transcriptions",
            data={
                "audio": (io.BytesIO(b"noise"), "noise.webm")
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(noise.status_code, 422)
        self.assertEqual(
            noise.get_json()["message"],
            "未能识别，请重试或改用文字输入",
        )

        self.ai.complete_json.side_effect = AiUnavailableError("down")
        answer_failure = student.post(
            "/api/local-resources/dialect-assistant/turns",
            json={"dialect_code": "yue", "question": "问题"},
        )
        self.assertEqual(answer_failure.status_code, 503)
        self.assertEqual(
            answer_failure.get_json()["message"],
            "AI 服务暂时不可用",
        )

        self.ai.complete_json.side_effect = None
        self.tts.synthesize.side_effect = RuntimeError("down")
        tts_failure = student.post(
            "/api/local-resources/dialect-assistant/turns",
            json={"dialect_code": "hak", "question": "问题"},
        )
        self.assertEqual(tts_failure.status_code, 503)
        self.assertEqual(
            tts_failure.get_json()["message"],
            "AI 服务暂时不可用",
        )
        write_boundaries = (
            ("post", "/api/local-resources/cases"),
            ("put", "/api/local-resources/cases/missing"),
            ("patch", "/api/local-resources/cases/missing"),
            ("delete", "/api/local-resources/cases/missing"),
        )
        for method, path in write_boundaries:
            with self.subTest(method=method, path=path):
                self.assertEqual(
                    getattr(student, method)(path).status_code,
                    405,
                )
        self.assertEqual(
            student.get(
                "/api/local-resources/cases/missing"
            ).status_code,
            404,
        )

    def test_interest_recommendation_matrix(self):
        with self.app.app_context():
            crop = self._insert_user("crop01", "student")
            ecommerce = self._insert_user("ecommerce01", "student")
            handcraft = self._insert_user("handcraft01", "student")
            job = self._insert_user("job01", "student")
            none = self._insert_user("none01", "student")
            self._assign_tag(crop, "荔枝")
            self._assign_tag(ecommerce, "电商直播")
            self._assign_tag(handcraft, "手工艺")
            self._assign_tag(job, "农业技术员")
            actual = {
                "crop": recommend_policy_categories(crop),
                "ecommerce": recommend_policy_categories(ecommerce),
                "handcraft": recommend_policy_categories(handcraft),
                "job": recommend_policy_categories(job),
                "none": recommend_policy_categories(none),
            }
            subscription_count = get_db().execute(
                """
                SELECT COUNT(*) AS count
                FROM local_resource_policy_subscriptions
                WHERE user_id IN (?, ?, ?, ?, ?)
                """,
                (crop, ecommerce, handcraft, job, none),
            ).fetchone()["count"]
        self.assertEqual(
            actual,
            {
                "crop": ["subsidy", "training", "general"],
                "ecommerce": ["ecommerce", "entrepreneurship"],
                "handcraft": ["heritage"],
                "job": ["certification", "entrepreneurship"],
                "none": [],
            },
        )
        self.assertEqual(subscription_count, 0)

    def test_all_student_routes_and_cross_student_subscription_isolation(self):
        with self.app.app_context():
            second_student_id = self._insert_user(
                "student02",
                "student",
            )
        student = self._login("student01")
        second = self._login("student02")
        teacher = self._login("teacher01")
        anonymous = self.app.test_client()
        with self.app.app_context():
            set_policy_subscription(
                self.student_id,
                "ecommerce",
                True,
            )
            set_policy_subscription(
                second_student_id,
                "ecommerce",
                False,
            )
        paths = [
            "/api/local-resources/cases",
            "/api/local-resources/cases/missing",
            "/api/local-resources/policies",
            "/api/local-resources/policies/policy-1",
            "/api/local-resources/policy-subscriptions",
            "/api/local-resources/news",
            "/api/local-resources/news/news-1",
        ]
        for path in paths:
            with self.subTest(path=path):
                self.assertEqual(anonymous.get(path).status_code, 401)
                self.assertEqual(teacher.get(path).status_code, 403)
        protected_posts = (
            "/api/local-resources/policy-subscriptions/ecommerce",
            "/api/local-resources/policies/policy-1/views",
            "/api/local-resources/news/news-1/views",
            "/api/local-resources/dialect-assistant/turns",
        )
        for path in protected_posts:
            with self.subTest(method="POST", path=path):
                self.assertEqual(
                    anonymous.post(path, json={}).status_code,
                    401,
                )
                self.assertEqual(
                    teacher.post(path, json={}).status_code,
                    403,
                )
        anonymous_slots = self.app.test_client()
        teacher_slots = self._login("teacher01")
        self.assertEqual(
            anonymous_slots.delete(
                "/api/local-resources/policy-subscriptions/ecommerce"
            ).status_code,
            401,
        )
        self.assertEqual(
            teacher_slots.delete(
                "/api/local-resources/policy-subscriptions/ecommerce"
            ).status_code,
            403,
        )
        first_state = student.get(
            "/api/local-resources/policy-subscriptions"
        ).get_json()["subscriptions"]
        second_state = second.get(
            "/api/local-resources/policy-subscriptions"
        ).get_json()["subscriptions"]
        self.assertTrue(
            next(
                item for item in first_state["categories"]
                if item["code"] == "ecommerce"
            )["subscribed"]
        )
        self.assertFalse(
            next(
                item for item in second_state["categories"]
                if item["code"] == "ecommerce"
            )["subscribed"]
        )

    def test_non_student_and_direct_table_boundary(self):
        teacher = self._login("teacher01")
        anonymous = self.app.test_client()
        self.assertEqual(
            anonymous.get("/api/local-resources/cases").status_code,
            401,
        )
        self.assertEqual(
            teacher.get("/api/local-resources/cases").status_code,
            403,
        )
        with self.app.app_context():
            provider = get_policy_news_provider()
            self.assertTrue(
                hasattr(provider, "list_published_policies")
            )


if __name__ == "__main__":
    unittest.main()
