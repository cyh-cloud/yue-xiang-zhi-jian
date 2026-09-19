import tempfile
import unittest
from pathlib import Path

from app import create_app
from app.db import get_db
from app.local_resources.cases import (
    DatabaseLocalResourceCaseProvider,
    get_local_resource_case_provider,
    set_local_resource_case_provider,
)
from app.local_resources.errors import LocalResourceUnavailableError


class LocalResourceCaseTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(Path(self.temp_dir.name) / "test.db"),
            }
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_seed_has_stable_order_and_complete_detail(self):
        with self.app.app_context():
            provider = DatabaseLocalResourceCaseProvider()
            cases = provider.list_success_cases()
            detail = provider.get_success_case(cases[0]["id"])
        self.assertGreaterEqual(len(cases), 3)
        self.assertEqual(
            [item["id"] for item in cases],
            [
                "case-litchi-coop",
                "case-rice-ecommerce",
                "case-bamboo-studio",
            ],
        )
        self.assertEqual(
            set(detail),
            {
                "id",
                "title",
                "summary",
                "background",
                "journey",
                "lessons",
                "published_at",
                "updated_at",
                "is_demo",
            },
        )

    def test_unknown_case_returns_none(self):
        with self.app.app_context():
            self.assertIsNone(
                DatabaseLocalResourceCaseProvider()
                .get_success_case("missing")
            )

    def test_provider_is_replaceable(self):
        class Replacement:
            def list_success_cases(self):
                return [{"id": "real-1"}]

            def get_success_case(self, case_id):
                return {"id": case_id} if case_id == "real-1" else None

        replacement = Replacement()
        set_local_resource_case_provider(self.app, replacement)
        with self.app.app_context():
            self.assertIs(
                get_local_resource_case_provider(),
                replacement,
            )

    def test_unavailable_provider_has_exact_message(self):
        class Unavailable:
            def list_success_cases(self):
                raise LocalResourceUnavailableError("案例数据暂不可用")

            def get_success_case(self, case_id):
                raise LocalResourceUnavailableError("案例数据暂不可用")

        set_local_resource_case_provider(self.app, Unavailable())
        with self.app.app_context():
            with self.assertRaisesRegex(
                LocalResourceUnavailableError,
                "案例数据暂不可用",
            ):
                get_local_resource_case_provider().list_success_cases()


if __name__ == "__main__":
    unittest.main()
