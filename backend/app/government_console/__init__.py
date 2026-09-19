from __future__ import annotations

from flask import Flask

from app.government_console.policy import (
    delete_policy,
    list_policies,
    publish_policy,
    relist_policy,
    unpublish_policy,
)
from app.government_console.providers import (
    DatabasePolicyNewsProvider,
    UnavailableEmploymentStatisticsProvider,
    set_employment_statistics_provider,
    set_policy_news_provider,
)


def install_default_government_services(app: Flask) -> None:
    if "government_policy_news_provider" not in app.extensions:
        set_policy_news_provider(app, DatabasePolicyNewsProvider())
    if "government_employment_statistics_provider" not in app.extensions:
        set_employment_statistics_provider(
            app, UnavailableEmploymentStatisticsProvider()
        )
