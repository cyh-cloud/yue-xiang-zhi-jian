from __future__ import annotations

from flask import Flask

from app.agri_skills.ai_client import (
    NullAiClient,
    OpenAiCompatibleAiClient,
    get_ai_client,
    set_ai_client,
)
from app.agri_skills.ai_context import (
    AI_FIELD_ALLOWLISTS,
    allowed_context,
    build_ai_messages,
    redact_ai_log,
)
from app.agri_skills.calendar import (
    list_product_subscriber_ids,
    list_product_subscriptions,
    subscribe_product,
    unsubscribe_product,
)
from app.agri_skills.course_learning import DatabaseAgriCourseProvider
from app.agri_skills.messaging_provider import AgriMessagingProvider
from app.agri_skills.presets import (
    PlaceholderPresetProvider,
    set_preset_provider,
)
from app.agri_skills.providers import set_course_provider


def configure_agri_providers(
    app: Flask,
    *,
    preset_provider=None,
    course_provider=None,
    ai_client=None,
) -> None:
    if preset_provider is not None:
        set_preset_provider(app, preset_provider)
    if course_provider is not None:
        set_course_provider(app, course_provider)
    if ai_client is not None:
        set_ai_client(app, ai_client)


def install_default_agri_services(app: Flask) -> None:
    if "agri_ai_client" not in app.extensions:
        if app.config.get("AI_API_URL") and app.config.get("AI_API_KEY"):
            set_ai_client(
                app,
                OpenAiCompatibleAiClient(
                    api_url=str(app.config["AI_API_URL"]),
                    api_key=str(app.config["AI_API_KEY"]),
                    model=str(app.config["AI_MODEL"]),
                    timeout=float(app.config["AI_TIMEOUT_SECONDS"]),
                ),
            )
        else:
            set_ai_client(app, NullAiClient())
    if "agri_preset_provider" not in app.extensions:
        set_preset_provider(app, PlaceholderPresetProvider())
    if "agri_course_provider" not in app.extensions:
        set_course_provider(app, DatabaseAgriCourseProvider())
