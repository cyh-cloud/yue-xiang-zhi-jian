from __future__ import annotations

from typing import Protocol

from flask import Flask, current_app

from app.admin_console.errors import ProviderUnavailableError
from app.admin_console.handcraft_review_adapter import (
    CompositeContentReviewProvider,
    HandcraftTeachingVideoReviewAdapter,
)
from app.admin_console.presets import (
    AdminDatabaseLocalResourceCaseProvider,
    DatabaseAgriPresetContentProvider,
    DatabaseAssistantFeatureKnowledgeProvider,
    DatabaseCraftPresetProvider,
)
from app.admin_console.points_policy import DatabasePointsPolicyProvider
from app.admin_console.rewards import DatabaseRewardCatalogProvider
from app.agri_skills.presets import set_preset_provider
from app.agri_skills.providers import PresetContentProvider
from app.content_review.providers import (
    ContentReviewProvider,
    UnavailableContentReviewProvider,
    set_content_review_provider,
)
from app.handcraft_inheritance.providers import (
    PointsPolicyProvider,
    UnavailablePointsPolicyProvider,
    CraftPresetProvider,
    RewardCatalogProvider,
    set_reward_catalog_provider,
    set_craft_preset_provider,
    # Aliased because this module exports its own `set_points_policy_provider`
    # for the 011 `admin_points_policy_provider` slot; the 05 setter writes
    # the `handcraft_points_policy_provider` slot that 05 itself reads.
    set_points_policy_provider as set_handcraft_points_policy_provider,
)
from app.local_resources.cases import (
    LocalResourceCaseProvider,
    set_local_resource_case_provider,
)


class AssistantFeatureKnowledgeProvider(Protocol):
    def list_entries(
        self,
        enabled_only: bool = True,
    ) -> list[dict]: ...


class FeedbackIntakeProvider(Protocol):
    def submit_feedback(
        self,
        *,
        submitter_id: int,
        body: str,
        idempotency_key: str,
    ) -> dict: ...


class UnavailableAssistantFeatureKnowledgeProvider:
    def list_entries(
        self,
        enabled_only: bool = True,
    ) -> list[dict]:
        raise ProviderUnavailableError(
            "AI 学伴功能说明知识库暂不可用",
            code="assistant_feature_knowledge_unavailable",
            details={},
        )


class UnavailableFeedbackIntakeProvider:
    def submit_feedback(
        self,
        *,
        submitter_id: int,
        body: str,
        idempotency_key: str,
    ) -> dict:
        raise ProviderUnavailableError(
            "意见反馈接收服务暂不可用",
            code="feedback_intake_unavailable",
            details={},
        )


class DatabaseFeedbackIntakeProvider(UnavailableFeedbackIntakeProvider):
    """Feedback intake backed by the `feedback_records` table.

    The table is owned by `moderation`, which also owns the canonical
    record shape the admin console reads back through `list_feedback`, so
    the intake lives there and this class is the slot-facing wrapper 07 and
    12 install. That keeps one implementation and one shape: a field added
    to a feedback record is visible to the submitter's provider and to the
    console at the same time, and neither side can drift from the other.

    Every failure is a `ProviderValidationError` from the 011 error
    hierarchy, so a caller sees the same code whether it reached this
    provider or the console route.
    """

    def submit_feedback(
        self,
        *,
        submitter_id: int,
        body: str,
        idempotency_key: str,
    ) -> dict:
        from app.admin_console.moderation import submit_feedback

        return submit_feedback(
            submitter_id=submitter_id,
            body=body,
            idempotency_key=idempotency_key,
        )


def set_assistant_feature_knowledge_provider(
    app: Flask,
    provider: AssistantFeatureKnowledgeProvider,
) -> None:
    app.extensions["assistant_feature_knowledge_provider"] = provider


def get_assistant_feature_knowledge_provider(
) -> AssistantFeatureKnowledgeProvider:
    return current_app.extensions.get(
        "assistant_feature_knowledge_provider",
        UnavailableAssistantFeatureKnowledgeProvider(),
    )


def set_feedback_intake_provider(
    app: Flask,
    provider: FeedbackIntakeProvider,
) -> None:
    app.extensions["feedback_intake_provider"] = provider


def get_feedback_intake_provider() -> FeedbackIntakeProvider:
    return current_app.extensions.get(
        "feedback_intake_provider",
        UnavailableFeedbackIntakeProvider(),
    )


def set_points_policy_provider(
    app: Flask,
    provider: PointsPolicyProvider,
) -> None:
    app.extensions["admin_points_policy_provider"] = provider


def get_points_policy_provider() -> PointsPolicyProvider:
    return current_app.extensions.get(
        "admin_points_policy_provider",
        UnavailablePointsPolicyProvider(),
    )


def configure_admin_providers(
    app: Flask,
    *,
    content_review: ContentReviewProvider | None = None,
    points_policy: PointsPolicyProvider | None = None,
    reward_catalog: RewardCatalogProvider | None = None,
    agri_preset: PresetContentProvider | None = None,
    craft_preset: CraftPresetProvider | None = None,
    local_case: LocalResourceCaseProvider | None = None,
    knowledge: AssistantFeatureKnowledgeProvider | None = None,
    feedback_intake: FeedbackIntakeProvider | None = None,
) -> None:
    """Install explicit providers into the eight slots 011 owns.

    One setter per slot, so a caller can swap a single slot without touching
    the others. Every parameter defaults to `None` and a `None` value leaves
    whatever is already installed in place, which keeps `create_app`'s
    database defaults and lets a later feature (012 and beyond) override one
    slot after the fact. `points_policy` writes the 011 management read slot;
    05's own read slot has its own setter, exactly as in
    `install_default_admin_services`.
    """
    for setter, provider in (
        (set_content_review_provider, content_review),
        (set_points_policy_provider, points_policy),
        (set_reward_catalog_provider, reward_catalog),
        (set_preset_provider, agri_preset),
        (set_craft_preset_provider, craft_preset),
        (set_local_resource_case_provider, local_case),
        (set_assistant_feature_knowledge_provider, knowledge),
        (set_feedback_intake_provider, feedback_intake),
    ):
        if provider is not None:
            setter(app, provider)


def install_default_admin_services(app: Flask) -> None:
    content_review = app.extensions.get("content_review_provider")
    if content_review is None or isinstance(
        content_review,
        UnavailableContentReviewProvider,
    ):
        set_content_review_provider(
            app,
            CompositeContentReviewProvider(),
        )
    # These two slots must be replaced unconditionally. 05 and 06 install
    # their own defaults earlier in `create_app`, so a `not in
    # app.extensions` guard here would leave 05's placeholder craft provider
    # and 06's unfiltered case provider installed, and 011 would never take
    # effect.
    set_craft_preset_provider(app, DatabaseCraftPresetProvider())
    set_local_resource_case_provider(
        app,
        AdminDatabaseLocalResourceCaseProvider(),
    )
    # This slot must be replaced unconditionally for the same reason. 03's
    # `install_default_agri_services` runs before this function in
    # `create_app` and already installed `PlaceholderPresetProvider`, so a
    # `not in app.extensions` guard would leave 03's placeholder content in
    # place and 011's authoritative `admin_agri_products`,
    # `admin_agri_calendar` and `admin_pest_knowledge` rows would never
    # reach 03's calendar, diagnosis or offline Q&A paths. 03's own setter
    # is reused so the `agri_preset_provider` slot stays the single
    # registry.
    set_preset_provider(app, DatabaseAgriPresetContentProvider())
    # This slot must be replaced unconditionally for the same reason. 05's
    # `install_default_handcraft_services` runs before this function in
    # `create_app` and already installed `PlaceholderRewardCatalogProvider`,
    # so a `not in app.extensions` guard would leave 05's placeholder reward
    # catalog in place and 011's authoritative `admin_rewards` would never
    # reach the mall.
    set_reward_catalog_provider(app, DatabaseRewardCatalogProvider())
    # The points-policy slots follow the same unconditional pattern. 05's
    # `install_default_handcraft_services` runs before this function in
    # `create_app` and already installed `PlaceholderPointsPolicyProvider`,
    # so a `not in app.extensions` guard would leave 05's demo rule in place
    # and 011's authoritative `platform_points_policy` would never reach 05's
    # points, expiry or fulfillment paths. One instance is installed into
    # both the 05 read slot and the 011 management read entry, so replacing
    # the provider through either setter is visible to both consumers.
    points_policy = DatabasePointsPolicyProvider()
    set_handcraft_points_policy_provider(app, points_policy)
    set_points_policy_provider(app, points_policy)
    # These last two slots follow the same unconditional pattern and must
    # never grow a `not in app.extensions` guard. On this branch nothing
    # installs either slot before `create_app` reaches this function, so a
    # guard is a no-op today and therefore invisible in review. The risk is
    # cross-branch: once 011 merges, any feature (012 and later) whose
    # `create_app` or test assembly installs its own provider - or an
    # `Unavailable` default - earlier in the sequence would keep that value
    # here, and 011's authoritative
    # `DatabaseAssistantFeatureKnowledgeProvider` and
    # `DatabaseFeedbackIntakeProvider` rows would silently never reach the AI
    # companion's feature knowledge or the feedback intake path. Providers
    # stay overridable because a caller writes `app.extensions` (or calls
    # `configure_admin_providers`) after `create_app`, which unconditional
    # replacement preserves.
    set_assistant_feature_knowledge_provider(
        app,
        DatabaseAssistantFeatureKnowledgeProvider(),
    )
    set_feedback_intake_provider(app, DatabaseFeedbackIntakeProvider())


__all__ = [
    "AdminDatabaseLocalResourceCaseProvider",
    "AssistantFeatureKnowledgeProvider",
    "DatabaseAgriPresetContentProvider",
    "CompositeContentReviewProvider",
    "CraftPresetProvider",
    "DatabaseAssistantFeatureKnowledgeProvider",
    "DatabaseCraftPresetProvider",
    "DatabasePointsPolicyProvider",
    "DatabaseRewardCatalogProvider",
    "DatabaseFeedbackIntakeProvider",
    "FeedbackIntakeProvider",
    "HandcraftTeachingVideoReviewAdapter",
    "LocalResourceCaseProvider",
    "PointsPolicyProvider",
    "PresetContentProvider",
    "RewardCatalogProvider",
    "UnavailablePointsPolicyProvider",
    "UnavailableAssistantFeatureKnowledgeProvider",
    "UnavailableFeedbackIntakeProvider",
    "configure_admin_providers",
    "get_assistant_feature_knowledge_provider",
    "get_feedback_intake_provider",
    "get_points_policy_provider",
    "install_default_admin_services",
    "set_assistant_feature_knowledge_provider",
    "set_feedback_intake_provider",
    "set_points_policy_provider",
]
