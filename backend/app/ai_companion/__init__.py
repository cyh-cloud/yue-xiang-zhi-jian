from flask import Flask

from app.ai_companion.constants import (
    ADMIN_ROLES,
    AI_COMPANION_ROLES,
    CONVERSATION_RETENTION_DAYS,
    DIALECTS,
    INTENTS,
    KNOWLEDGE_UNAVAILABLE_MESSAGE,
    MAX_CONVERSATIONS,
    MAX_MESSAGES_PER_CONVERSATION,
    MAX_QUESTION_LENGTH,
    REFUSAL_MESSAGE,
)
from app.ai_companion.errors import (
    AiCompanionAiUnavailableError,
    AiCompanionError,
    AiCompanionForbiddenError,
    AiCompanionKnowledgeUnavailableError,
    AiCompanionNotFoundError,
    AiCompanionRecognitionError,
    AiCompanionValidationError,
)
from app.ai_companion.knowledge_provider import (
    AssistantFeatureKnowledgeProvider,
    UnavailableAssistantFeatureKnowledgeProvider,
    get_assistant_feature_knowledge_provider,
    set_assistant_feature_knowledge_provider,
)
from app.ai_companion.routes import (
    ai_companion_bp,
    register_ai_companion_error_handlers,
)


def install_default_ai_companion_services(app: Flask) -> None:
    if "assistant_feature_knowledge_provider" not in app.extensions:
        set_assistant_feature_knowledge_provider(
            app,
            UnavailableAssistantFeatureKnowledgeProvider(),
        )


__all__ = [
    "ADMIN_ROLES",
    "AI_COMPANION_ROLES",
    "CONVERSATION_RETENTION_DAYS",
    "DIALECTS",
    "INTENTS",
    "KNOWLEDGE_UNAVAILABLE_MESSAGE",
    "MAX_CONVERSATIONS",
    "MAX_MESSAGES_PER_CONVERSATION",
    "MAX_QUESTION_LENGTH",
    "REFUSAL_MESSAGE",
    "AiCompanionAiUnavailableError",
    "AiCompanionError",
    "AiCompanionForbiddenError",
    "AiCompanionKnowledgeUnavailableError",
    "AiCompanionNotFoundError",
    "AiCompanionRecognitionError",
    "AiCompanionValidationError",
    "AssistantFeatureKnowledgeProvider",
    "UnavailableAssistantFeatureKnowledgeProvider",
    "get_assistant_feature_knowledge_provider",
    "set_assistant_feature_knowledge_provider",
    "ai_companion_bp",
    "install_default_ai_companion_services",
    "register_ai_companion_error_handlers",
]
