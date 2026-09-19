import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from app import create_app
from app.government_console.errors import (
    ProviderAccessDeniedError,
    ProviderConflictError,
    ProviderError,
    ProviderNotFoundError,
    ProviderUnavailableError,
    ProviderValidationError,
)
from app.government_console.providers import set_policy_news_provider
from app.local_resources.errors import (
    LocalResourceAccessDeniedError,
    LocalResourceConflictError,
    LocalResourceNotFoundError,
    LocalResourceUnavailableError,
    LocalResourceValidationError,
)
from app.local_resources.views import (
    record_news_view,
    record_policy_view,
)


class LocalResourceViewTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(Path(self.temp_dir.name) / "test.db"),
            }
        )
        self.provider = Mock()
        set_policy_news_provider(self.app, self.provider)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_views_delegate_and_return_provider_total(self):
        self.provider.record_policy_view.return_value = 4
        self.provider.record_news_view.return_value = 7
        with self.app.app_context():
            self.assertEqual(
                record_policy_view("policy-1", "view-1"),
                4,
            )
            self.assertEqual(
                record_news_view("news-1", "view-1"),
                7,
            )
        self.provider.record_policy_view.assert_called_once_with(
            "policy-1",
            "view-1",
        )
        self.provider.record_news_view.assert_called_once_with(
            "news-1",
            "view-1",
        )

    def test_ids_are_stripped_before_delegation(self):
        self.provider.record_policy_view.return_value = 8
        self.provider.record_news_view.return_value = 9
        with self.app.app_context():
            record_policy_view(" policy-1 ", " view-1 ")
            record_news_view(" news-1 ", " view-2 ")
        self.provider.record_policy_view.assert_called_once_with(
            "policy-1",
            "view-1",
        )
        self.provider.record_news_view.assert_called_once_with(
            "news-1",
            "view-2",
        )

    def test_both_ids_are_required_text(self):
        with self.app.app_context():
            for value in (None, "", " ", 123):
                with self.subTest(content_id=value):
                    with self.assertRaises(LocalResourceValidationError):
                        record_policy_view(value, "view-1")
                    with self.assertRaises(LocalResourceValidationError):
                        record_news_view(value, "view-1")
                with self.subTest(event_id=value):
                    with self.assertRaises(LocalResourceValidationError):
                        record_policy_view("policy-1", value)
                    with self.assertRaises(LocalResourceValidationError):
                        record_news_view("news-1", value)
        self.provider.record_policy_view.assert_not_called()
        self.provider.record_news_view.assert_not_called()

    def test_all_provider_errors_map_to_local_errors(self):
        cases = (
            (
                ProviderValidationError(
                    "非法",
                    details={"policy_id": "格式错误"},
                ),
                LocalResourceValidationError,
                "非法",
                {"policy_id": "格式错误"},
            ),
            (
                ProviderNotFoundError("内容不存在"),
                LocalResourceNotFoundError,
                "政策不存在或不可见",
                {},
            ),
            (
                ProviderConflictError("冲突"),
                LocalResourceConflictError,
                "冲突",
                {},
            ),
            (
                ProviderUnavailableError(
                    "政策浏览计数暂不可用",
                    details={"retryable": True},
                ),
                LocalResourceUnavailableError,
                "政策浏览计数暂不可用",
                {"retryable": True},
            ),
            (
                ProviderAccessDeniedError("拒绝"),
                LocalResourceAccessDeniedError,
                "拒绝",
                {},
            ),
        )
        with self.app.app_context():
            for (
                provider_error,
                local_error,
                message,
                details,
            ) in cases:
                with self.subTest(error=provider_error):
                    self.provider.record_policy_view.side_effect = (
                        provider_error
                    )
                    with self.assertRaises(local_error) as raised:
                        record_policy_view("policy-1", "view-1")
                    self.assertEqual(raised.exception.message, message)
                    self.assertEqual(raised.exception.details, details)
                    self.assertIs(
                        raised.exception.__cause__,
                        provider_error,
                    )

    def test_unknown_provider_error_does_not_leak_database_text(self):
        database_text = "sqlite3.OperationalError: no such table: secrets"
        self.provider.record_news_view.side_effect = ProviderError(
            database_text
        )
        with self.app.app_context():
            with self.assertRaises(LocalResourceUnavailableError) as raised:
                record_news_view("news-1", "view-1")
        self.assertEqual(raised.exception.message, "浏览计数暂不可用")
        self.assertNotIn(database_text, raised.exception.message)
        self.assertEqual(raised.exception.details, {})


if __name__ == "__main__":
    unittest.main()
