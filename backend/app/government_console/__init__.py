from __future__ import annotations

from flask import Flask

from app.government_console.providers import (
    NullPolicyNewsProvider,
    UnavailableEmploymentStatisticsProvider,
    set_employment_statistics_provider,
    set_policy_news_provider,
)


def install_default_government_services(app: Flask) -> None:
    if "government_policy_news_provider" not in app.extensions:
        set_policy_news_provider(app, NullPolicyNewsProvider())
    if "government_employment_statistics_provider" not in app.extensions:
        set_employment_statistics_provider(
            app, UnavailableEmploymentStatisticsProvider()
        )
