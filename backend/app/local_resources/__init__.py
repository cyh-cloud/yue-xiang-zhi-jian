from app.local_resources.constants import (
    DIALECT_LABELS,
    DIALECTS,
    NEWS_CATEGORIES,
    NEWS_LABELS,
    POLICY_CATEGORIES,
    POLICY_LABELS,
    RECOMMENDATION_TAGS,
)
from app.local_resources.cases import (
    DatabaseLocalResourceCaseProvider,
    LocalResourceCaseProvider,
    UnavailableLocalResourceCaseProvider,
    get_local_resource_case_provider,
    set_local_resource_case_provider,
)
from app.local_resources.catalog import (
    get_news,
    get_policy,
    list_news,
    list_policies,
)
from app.local_resources.dialect_assistant import (
    complete_dialect_turn,
    generate_dialect_answer,
)
from app.local_resources.errors import (
    LocalResourceAccessDeniedError,
    LocalResourceAiUnavailableError,
    LocalResourceConflictError,
    LocalResourceError,
    LocalResourceNotFoundError,
    LocalResourceUnavailableError,
    LocalResourceValidationError,
)
from app.local_resources.messaging_provider import (
    LocalResourcesMessagingProvider,
)
from app.local_resources.subscriptions import (
    list_policy_subscriptions,
    recommend_policy_categories,
    set_policy_subscription,
)
from app.local_resources.tts import (
    OpenAiCompatibleTtsClient,
    TtsAudio,
    TtsClient,
    get_local_tts_client,
    set_local_tts_client,
    synthesize_dialect,
)
from app.local_resources.views import (
    record_news_view,
    record_policy_view,
)

__all__ = [
    "DIALECTS",
    "DIALECT_LABELS",
    "POLICY_CATEGORIES",
    "POLICY_LABELS",
    "NEWS_CATEGORIES",
    "NEWS_LABELS",
    "RECOMMENDATION_TAGS",
    "LocalResourceCaseProvider",
    "DatabaseLocalResourceCaseProvider",
    "UnavailableLocalResourceCaseProvider",
    "get_local_resource_case_provider",
    "set_local_resource_case_provider",
    "list_policies",
    "get_policy",
    "list_news",
    "get_news",
    "generate_dialect_answer",
    "complete_dialect_turn",
    "list_policy_subscriptions",
    "set_policy_subscription",
    "recommend_policy_categories",
    "LocalResourcesMessagingProvider",
    "record_policy_view",
    "record_news_view",
    "TtsAudio",
    "TtsClient",
    "OpenAiCompatibleTtsClient",
    "get_local_tts_client",
    "set_local_tts_client",
    "synthesize_dialect",
    "LocalResourceError",
    "LocalResourceValidationError",
    "LocalResourceNotFoundError",
    "LocalResourceConflictError",
    "LocalResourceUnavailableError",
    "LocalResourceAccessDeniedError",
    "LocalResourceAiUnavailableError",
]
