from __future__ import annotations

from app.government_console.errors import ProviderError
from app.government_console.providers import get_policy_news_provider
from app.local_resources.constants import (
    NEWS_LABELS,
    POLICY_LABELS,
)
from app.local_resources.errors import (
    LocalResourceNotFoundError,
    LocalResourceValidationError,
    map_provider_error,
)


def _category(
    value: str | None,
    allowed: dict[str, str],
    field: str,
) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or value not in allowed:
        raise LocalResourceValidationError(
            "类别不正确",
            details={field: "类别不属于允许值"},
        )
    return value


def list_policies(category_code: str | None = None) -> list[dict]:
    category = _category(category_code, POLICY_LABELS, "category")
    try:
        return [
            dict(item)
            for item in get_policy_news_provider().list_published_policies(
                category
            )
        ]
    except ProviderError as error:
        map_provider_error(
            error,
            missing_message="政策不存在",
            unknown_message="政策数据暂不可用",
        )


def get_policy(policy_id: str) -> dict:
    if not isinstance(policy_id, str) or not policy_id.strip():
        raise LocalResourceNotFoundError("政策不存在")
    try:
        item = get_policy_news_provider().get_published_policy(
            policy_id.strip()
        )
    except ProviderError as error:
        map_provider_error(
            error,
            missing_message="政策不存在",
            unknown_message="政策数据暂不可用",
        )
    if item is None:
        raise LocalResourceNotFoundError("政策不存在")
    return dict(item)


def list_news(category_code: str | None = None) -> list[dict]:
    category = _category(category_code, NEWS_LABELS, "category")
    try:
        return [
            dict(item)
            for item in get_policy_news_provider().list_published_news(
                category
            )
        ]
    except ProviderError as error:
        map_provider_error(
            error,
            missing_message="新闻不存在",
            unknown_message="新闻数据暂不可用",
        )


def get_news(news_id: str) -> dict:
    if not isinstance(news_id, str) or not news_id.strip():
        raise LocalResourceNotFoundError("新闻不存在")
    try:
        item = get_policy_news_provider().get_published_news(news_id.strip())
    except ProviderError as error:
        map_provider_error(
            error,
            missing_message="新闻不存在",
            unknown_message="新闻数据暂不可用",
        )
    if item is None:
        raise LocalResourceNotFoundError("新闻不存在")
    return dict(item)
