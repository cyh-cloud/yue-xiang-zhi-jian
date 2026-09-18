from __future__ import annotations

from typing import Protocol

from flask import Flask, current_app

from app.government_console.errors import ProviderUnavailableError
from app.government_console.news import (
    get_published_news as _get_published_news,
    list_published_news as _list_published_news,
)
from app.government_console.policy import (
    get_published_policy as _get_published_policy,
    list_published_policies as _list_published_policies,
)
from app.government_console.views import (
    record_news_view as _record_news_view,
    record_policy_view as _record_policy_view,
)


class PolicyNewsProvider(Protocol):
    def list_published_policies(self, category: str | None = None) -> list[dict]: ...

    def get_published_policy(self, policy_id: str) -> dict | None: ...

    def list_published_news(self, category: str | None = None) -> list[dict]: ...

    def get_published_news(self, news_id: str) -> dict | None: ...

    def record_policy_view(self, policy_id: str, view_event_id: str) -> int: ...

    def record_news_view(self, news_id: str, view_event_id: str) -> int: ...


class EmploymentStatisticsProvider(Protocol):
    def get_active_job_count(self) -> int | None: ...

    def get_cumulative_application_count(self) -> int | None: ...


class NullPolicyNewsProvider:
    def list_published_policies(self, category: str | None = None) -> list[dict]:
        return []

    def get_published_policy(self, policy_id: str) -> dict | None:
        return None

    def list_published_news(self, category: str | None = None) -> list[dict]:
        return []

    def get_published_news(self, news_id: str) -> dict | None:
        return None

    def record_policy_view(self, policy_id: str, view_event_id: str) -> int:
        raise ProviderUnavailableError("政策浏览计数暂不可用")

    def record_news_view(self, news_id: str, view_event_id: str) -> int:
        raise ProviderUnavailableError("新闻浏览计数暂不可用")


class DatabasePolicyNewsProvider(NullPolicyNewsProvider):
    def list_published_policies(
        self, category: str | None = None
    ) -> list[dict]:
        return _list_published_policies(category)

    def get_published_policy(self, policy_id: str) -> dict | None:
        return _get_published_policy(policy_id)

    def list_published_news(self, category: str | None = None) -> list[dict]:
        return _list_published_news(category)

    def get_published_news(self, news_id: str) -> dict | None:
        return _get_published_news(news_id)

    def record_policy_view(self, policy_id: str, view_event_id: str) -> int:
        return _record_policy_view(policy_id, view_event_id)

    def record_news_view(self, news_id: str, view_event_id: str) -> int:
        return _record_news_view(news_id, view_event_id)


class UnavailableEmploymentStatisticsProvider:
    def get_active_job_count(self) -> int | None:
        return None

    def get_cumulative_application_count(self) -> int | None:
        return None


def set_policy_news_provider(
    app: Flask, provider: PolicyNewsProvider
) -> None:
    app.extensions["government_policy_news_provider"] = provider


def get_policy_news_provider() -> PolicyNewsProvider:
    return current_app.extensions.get(
        "government_policy_news_provider",
        NullPolicyNewsProvider(),
    )


def set_employment_statistics_provider(
    app: Flask, provider: EmploymentStatisticsProvider
) -> None:
    app.extensions["government_employment_statistics_provider"] = provider


def get_employment_statistics_provider() -> EmploymentStatisticsProvider:
    return current_app.extensions.get(
        "government_employment_statistics_provider",
        UnavailableEmploymentStatisticsProvider(),
    )


def configure_government_providers(
    app: Flask,
    *,
    policy_news: PolicyNewsProvider | None = None,
    employment_statistics: EmploymentStatisticsProvider | None = None,
) -> None:
    if policy_news is not None:
        set_policy_news_provider(app, policy_news)
    if employment_statistics is not None:
        set_employment_statistics_provider(app, employment_statistics)
