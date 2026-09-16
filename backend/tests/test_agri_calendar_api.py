import tempfile
import unittest
from pathlib import Path

from werkzeug.security import generate_password_hash

from app import create_app
from app.db import get_db


class TestAgriCalendarApi(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(Path(self.temp_dir.name) / "test.db"),
                "SECRET_KEY": "test-only-secret",
                "SESSION_HOURS": 24,
                "SESSION_COOKIE_SECURE": False,
            }
        )

        self._create_user("student01", "student")
        self._create_user("student02", "student")
        self._create_user("teacher01", "teacher")
        self.student_client = self._login("student01")
        self.other_student_client = self._login("student02")
        self.teacher_client = self._login("teacher01")

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

    def test_products_and_missing_selection_fall_back_to_first_product(self):
        products = self.student_client.get("/api/agri-skills/products")

        self.assertEqual(products.status_code, 200)
        self.assertEqual(
            products.get_json()["products"],
            [
                {"key": "litchi", "name": "荔枝", "sort_order": 1},
                {"key": "longan", "name": "龙眼", "sort_order": 2},
                {"key": "aquaculture", "name": "水产", "sort_order": 3},
            ],
        )

        calendar = self.student_client.get("/api/agri-skills/calendar?month=4")

        self.assertEqual(calendar.status_code, 200)
        self.assertEqual(
            calendar.get_json()["calendar"]["product"]["key"],
            "litchi",
        )

    def test_selection_is_persisted_and_calendar_uses_last_selection(self):
        selected = self.student_client.put(
            "/api/agri-skills/calendar/selection",
            json={"product_key": "longan"},
        )

        self.assertEqual(selected.status_code, 200)
        self.assertEqual(selected.get_json()["product_key"], "longan")

        calendar = self.student_client.get("/api/agri-skills/calendar?month=4")
        calendar_body = calendar.get_json()["calendar"]

        self.assertEqual(calendar.status_code, 200)
        self.assertEqual(calendar_body["product_key"], "longan")
        self.assertEqual(
            calendar_body["empty_state"],
            "暂无该产品农时数据",
        )

    def test_calendar_returns_content_and_distinct_empty_states(self):
        content = self.student_client.get(
            "/api/agri-skills/calendar?product_key=litchi&month=4"
        )
        content_calendar = content.get_json()["calendar"]

        self.assertEqual(content.status_code, 200)
        self.assertIsNone(content_calendar["empty_state"])
        self.assertIn("清明", content_calendar["solar_terms"])

        missing_month = self.student_client.get(
            "/api/agri-skills/calendar?product_key=litchi&month=2"
        )
        missing_month_calendar = missing_month.get_json()["calendar"]

        self.assertEqual(missing_month.status_code, 200)
        self.assertEqual(
            missing_month_calendar["empty_state"],
            "当月无该产品农时",
        )
        self.assertEqual(missing_month_calendar["product"]["key"], "litchi")
        self.assertEqual(missing_month_calendar["month"], 2)

        missing_product_data = self.student_client.get(
            "/api/agri-skills/calendar?product_key=aquaculture&month=4"
        )
        missing_product_calendar = missing_product_data.get_json()["calendar"]

        self.assertEqual(missing_product_data.status_code, 200)
        self.assertEqual(
            missing_product_calendar["empty_state"],
            "暂无该产品农时数据",
        )
        self.assertEqual(
            missing_product_calendar["product_key"],
            "aquaculture",
        )
        self.assertEqual(missing_product_calendar["month"], 4)

    def test_calendar_rejects_missing_or_out_of_range_month(self):
        cases = [
            "/api/agri-skills/calendar?product_key=litchi",
            "/api/agri-skills/calendar?product_key=litchi&month=spring",
            "/api/agri-skills/calendar?product_key=litchi&month=0",
            "/api/agri-skills/calendar?product_key=litchi&month=13",
        ]

        for path in cases:
            with self.subTest(path=path):
                response = self.student_client.get(path)

                self.assertEqual(response.status_code, 400)
                self.assertEqual(
                    response.get_json()["errors"],
                    {"month": "月份必须是 1 至 12 的整数"},
                )

    def test_invalid_product_is_rejected_for_selection_and_subscription(self):
        selection = self.student_client.put(
            "/api/agri-skills/calendar/selection",
            json={"product_key": "missing-product"},
        )
        subscription = self.student_client.post(
            "/api/agri-skills/subscriptions/missing-product"
        )

        self.assertEqual(selection.status_code, 400)
        self.assertEqual(
            selection.get_json()["errors"],
            {"product_key": "产品不存在"},
        )
        self.assertEqual(subscription.status_code, 400)
        self.assertEqual(
            subscription.get_json()["errors"],
            {"product_key": "产品不存在"},
        )

    def test_subscribe_and_unsubscribe_are_idempotent_and_student_scoped(self):
        first = self.student_client.post(
            "/api/agri-skills/subscriptions/litchi"
        )
        second = self.student_client.post(
            "/api/agri-skills/subscriptions/litchi"
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(
            first.get_json()["subscription"],
            {"product_key": "litchi", "subscribed": True},
        )
        self.assertEqual(
            self.student_client.get(
                "/api/agri-skills/subscriptions"
            ).get_json()["subscriptions"],
            ["litchi"],
        )
        self.assertEqual(
            self.other_student_client.get(
                "/api/agri-skills/subscriptions"
            ).get_json()["subscriptions"],
            [],
        )

        first_delete = self.student_client.delete(
            "/api/agri-skills/subscriptions/litchi"
        )
        second_delete = self.student_client.delete(
            "/api/agri-skills/subscriptions/litchi"
        )

        self.assertEqual(first_delete.status_code, 200)
        self.assertEqual(second_delete.status_code, 200)
        self.assertEqual(
            self.student_client.get(
                "/api/agri-skills/subscriptions"
            ).get_json()["subscriptions"],
            [],
        )

    def test_calendar_and_subscription_routes_require_active_student(self):
        requests = [
            ("GET", "/api/agri-skills/products", None),
            ("GET", "/api/agri-skills/calendar?month=4", None),
            (
                "PUT",
                "/api/agri-skills/calendar/selection",
                {"product_key": "litchi"},
            ),
            ("GET", "/api/agri-skills/subscriptions", None),
            ("POST", "/api/agri-skills/subscriptions/litchi", None),
            ("DELETE", "/api/agri-skills/subscriptions/litchi", None),
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
                    self.assertTrue(
                        response.get_json()["redirect"].startswith("/login?")
                    )


if __name__ == "__main__":
    unittest.main()
