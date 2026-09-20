"""Administrator console foundation package."""

from __future__ import annotations

from app.admin_console.providers import (
    AssistantFeatureKnowledgeProvider,
    DatabaseAssistantFeatureKnowledgeProvider,
    DatabaseFeedbackIntakeProvider,
    FeedbackIntakeProvider,
    UnavailableAssistantFeatureKnowledgeProvider,
    UnavailableFeedbackIntakeProvider,
    configure_admin_providers,
    get_assistant_feature_knowledge_provider,
    get_feedback_intake_provider,
    install_default_admin_services,
    set_assistant_feature_knowledge_provider,
    set_feedback_intake_provider,
)
from app.admin_console.routes import (
    admin_console_bp,
    register_admin_console_error_handlers,
    require_admin_session,
)


__all__ = [
    "AssistantFeatureKnowledgeProvider",
    "DatabaseAssistantFeatureKnowledgeProvider",
    "DatabaseFeedbackIntakeProvider",
    "FeedbackIntakeProvider",
    "UnavailableAssistantFeatureKnowledgeProvider",
    "UnavailableFeedbackIntakeProvider",
    "admin_console_bp",
    "configure_admin_providers",
    "get_assistant_feature_knowledge_provider",
    "get_feedback_intake_provider",
    "install_default_admin_services",
    "register_admin_console_error_handlers",
    "require_admin_session",
    "set_assistant_feature_knowledge_provider",
    "set_feedback_intake_provider",
]
