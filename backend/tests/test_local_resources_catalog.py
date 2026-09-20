import tempfile
import unittest
from pathlib import Path

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
from app.local_resources.catalog import (
    get_news,
    get_policy,
    list_news,
    list_policies,
)
from app.local_resources.errors import (
    LocalResourceAccessDeniedError,
    LocalResourceConflictError,
    LocalResourceNotFoundError,
    LocalResourceUnavailableError,
    LocalResourceValidationError,
)


POLICY = {
    "id": "policy-1",
    "title": "创业补贴",
    "content": "正文",
    "category_code": "entrepreneurship",
    "category_label": "创业支持",
    "published_at": "2026-09-19T10:00:00+08:00",
    "updated_at": "2026-09-19T10:00:00+08:00",
    "version": 1,
}
NEWS = {
    **POLICY,
    "id": "news-1",
    "title": "暴雨预警",
    "category_code": "disaster_warning",
    "category_label": "灾害预警",
}


class FakeProvider:
    def list_published_policies(self, category=None):
        return [POLICY] if category in (None, "entrepreneurship") else []

    def get_published_policy(self, policy_id):
        return POLICY if policy_id == "policy-1" else None

    def list_published_news(self, category=None):
        return [NEWS] if category in (None, "disaster_warning") else []

    def get_published_news(self, news_id):
        return NEWS if news_id == "news-1" else None

    def record_policy_view(self, policy_id, view_event_id):
        return 1

    def record_news_view(self, news_id, view_event_id):
        return 1


class FailingProvider(FakeProvider):
    def list_published_policies(self, category=None):
        raise ProviderUnavailableError("政策数据暂不可用")

    def get_published_policy(self, policy_id):
        raise ProviderUnavailableError("政策数据暂不可用")

    def list_published_news(self, category=None):
        raise ProviderUnavailableError("新闻数据暂不可用")

    def get_published_news(self, news_id):
        raise ProviderUnavailableError("新闻数据暂不可用")


class TargetedFailingProvider(FakeProvider):
    def __init__(self, error):
        self.error = error

    def _raise_error(self):
        raise self.error

    def list_published_policies(self, category=None):
        self._raise_error()

    def get_published_policy(self, policy_id):
        self._raise_error()

    def list_published_news(self, category=None):
        self._raise_error()

    def get_published_news(self, news_id):
        self._raise_error()


class LocalResourceCatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(Path(self.temp_dir.name) / "test.db"),
            }
        )
        set_policy_news_provider(self.app, FakeProvider())

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_lists_exact_visible_records(self):
        with self.app.app_context():
            self.assertEqual(list_policies("entrepreneurship"), [POLICY])
            self.assertEqual(
                list_news("disaster_warning"),
                [NEWS],
            )
            self.assertEqual(get_policy("policy-1"), POLICY)
            self.assertEqual(get_news("news-1"), NEWS)

    def test_records_are_detached_from_provider_owned_data(self):
        with self.app.app_context():
            policies = list_policies("entrepreneurship")
            news = list_news("disaster_warning")
            policy = get_policy("policy-1")
            detail = get_news("news-1")

        self.assertIsNot(policies[0], POLICY)
        self.assertIsNot(news[0], NEWS)
        self.assertIsNot(policy, POLICY)
        self.assertIsNot(detail, NEWS)
        policies[0]["title"] = "已修改"
        news[0]["title"] = "已修改"
        policy["title"] = "已修改"
        detail["title"] = "已修改"
        self.assertEqual(POLICY["title"], "创业补贴")
        self.assertEqual(NEWS["title"], "暴雨预警")

    def test_unknown_categories_are_rejected(self):
        with self.app.app_context():
            with self.assertRaises(LocalResourceValidationError):
                list_policies("unknown")
            with self.assertRaises(LocalResourceValidationError):
                list_news("unknown")

    def test_missing_or_removed_records_are_not_found(self):
        with self.app.app_context():
            with self.assertRaises(LocalResourceNotFoundError):
                get_policy("missing")
            with self.assertRaises(LocalResourceNotFoundError):
                get_news("missing")

    def test_provider_errors_map_to_unavailable_with_cause(self):
        operations = {
            "list policies": lambda: list_policies("entrepreneurship"),
            "get policy": lambda: get_policy("policy-1"),
            "list news": lambda: list_news("disaster_warning"),
            "get news": lambda: get_news("news-1"),
        }
        expected_messages = {
            "list policies": "政策数据暂不可用",
            "get policy": "政策数据暂不可用",
            "list news": "新闻数据暂不可用",
            "get news": "新闻数据暂不可用",
        }

        with self.app.app_context():
            set_policy_news_provider(self.app, FailingProvider())
            for label, operation in operations.items():
                with self.subTest(operation=label):
                    with self.assertRaises(
                        LocalResourceUnavailableError
                    ) as raised:
                        operation()
                    self.assertEqual(
                        raised.exception.message,
                        expected_messages[label],
                    )
                    self.assertIsInstance(
                        raised.exception.__cause__,
                        ProviderUnavailableError,
                    )

    def test_provider_error_hierarchy_is_preserved_and_unknown_errors_are_private(self):
        operations = (
            (
                "list policies",
                lambda: list_policies("entrepreneurship"),
                "政策不存在",
                "政策数据暂不可用",
            ),
            (
                "get policy",
                lambda: get_policy("policy-1"),
                "政策不存在",
                "政策数据暂不可用",
            ),
            (
                "list news",
                lambda: list_news("disaster_warning"),
                "新闻不存在",
                "新闻数据暂不可用",
            ),
            (
                "get news",
                lambda: get_news("news-1"),
                "新闻不存在",
                "新闻数据暂不可用",
            ),
        )
        error_cases = (
            (
                "validation",
                lambda: ProviderValidationError(
                    "参数非法",
                    details={"category": "不允许"},
                ),
                LocalResourceValidationError,
                "参数非法",
                {"category": "不允许"},
            ),
            (
                "not found",
                lambda: ProviderNotFoundError("provider missing"),
                LocalResourceNotFoundError,
                None,
                {},
            ),
            (
                "conflict",
                lambda: ProviderConflictError("状态冲突"),
                LocalResourceConflictError,
                "状态冲突",
                {},
            ),
            (
                "unavailable",
                lambda: ProviderUnavailableError(
                    "目录暂不可用",
                    details={"retryable": True},
                ),
                LocalResourceUnavailableError,
                "目录暂不可用",
                {"retryable": True},
            ),
            (
                "access denied",
                lambda: ProviderAccessDeniedError("无权读取"),
                LocalResourceAccessDeniedError,
                "无权读取",
                {},
            ),
            (
                "unknown",
                lambda: ProviderError(
                    "sqlite3.OperationalError: no such table: secrets"
                ),
                LocalResourceUnavailableError,
                None,
                {},
            ),
        )

        with self.app.app_context():
            for (
                operation_label,
                operation,
                missing_message,
                unknown_message,
            ) in operations:
                for (
                    error_label,
                    error_factory,
                    expected_error,
                    expected_message,
                    expected_details,
                ) in error_cases:
                    with self.subTest(
                        operation=operation_label,
                        error=error_label,
                    ):
                        provider_error = error_factory()
                        set_policy_news_provider(
                            self.app,
                            TargetedFailingProvider(provider_error),
                        )
                        with self.assertRaises(expected_error) as raised:
                            operation()
                        if isinstance(
                            provider_error,
                            ProviderNotFoundError,
                        ):
                            expected_message = missing_message
                        elif type(provider_error) is ProviderError:
                            expected_message = unknown_message
                        self.assertEqual(
                            raised.exception.message,
                            expected_message,
                        )
                        self.assertEqual(
                            raised.exception.details,
                            expected_details,
                        )
                        self.assertIs(
                            raised.exception.__cause__,
                            provider_error,
                        )

if __name__ == "__main__":
    unittest.main()
