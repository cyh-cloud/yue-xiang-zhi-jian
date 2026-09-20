from __future__ import annotations

from app.government_console.errors import ProviderError
from app.government_console.providers import get_policy_news_provider
from app.local_resources.errors import (
    LocalResourceValidationError,
    map_provider_error,
)


def _required_id(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise LocalResourceValidationError(
            "内容标识不能为空",
            details={field: "必须是文本"},
        )
    return value.strip()


def _required_event_id(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise LocalResourceValidationError(
            "浏览事件标识不能为空",
            details={"view_event_id": "必须是文本"},
        )
    return value.strip()


def record_policy_view(policy_id: str, view_event_id: str) -> int:
    policy = _required_id(policy_id, "policy_id")
    event = _required_event_id(view_event_id)
    try:
        return get_policy_news_provider().record_policy_view(policy, event)
    except ProviderError as error:
        map_provider_error(
            error,
            missing_message="政策不存在或不可见",
            unknown_message="浏览计数暂不可用",
        )


def record_news_view(news_id: str, view_event_id: str) -> int:
    news = _required_id(news_id, "news_id")
    event = _required_event_id(view_event_id)
    try:
        return get_policy_news_provider().record_news_view(news, event)
    except ProviderError as error:
        map_provider_error(
            error,
            missing_message="新闻不存在或不可见",
            unknown_message="浏览计数暂不可用",
        )
