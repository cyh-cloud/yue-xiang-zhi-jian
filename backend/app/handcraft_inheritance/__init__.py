from __future__ import annotations

from flask import Flask

from app.handcraft_inheritance.admin_actions import (
    DatabaseFulfillmentAdminActionProvider,
    DatabaseTeachingVideoReviewActionProvider,
    apply_fulfillment_admin_action,
    apply_video_review,
)
from app.handcraft_inheritance.providers import (
    CraftPresetProvider,
    FulfillmentAdminActionProvider,
    PointsPolicyProvider,
    RewardCatalogProvider,
    TeachingVideoReviewActionProvider,
    TeachingVideoProvider,
    get_craft_preset_provider,
    get_fulfillment_action_provider,
    get_points_policy_provider,
    get_reward_catalog_provider,
    get_teaching_video_provider,
    get_video_review_action_provider,
    set_craft_preset_provider,
    set_fulfillment_action_provider,
    set_points_policy_provider,
    set_reward_catalog_provider,
    set_teaching_video_provider,
    set_video_review_action_provider,
)
from app.handcraft_inheritance.presets import (
    PlaceholderCraftPresetProvider,
    PlaceholderPointsPolicyProvider,
    PlaceholderRewardCatalogProvider,
    PlaceholderTeachingVideoProvider,
)
from app.handcraft_inheritance.points import (
    PointsPolicyUnavailable,
    enqueue_learning_event,
    get_effective_policy,
    get_points_account,
    get_points_ledger,
    process_pending_events,
    record_duration_points,
    record_training_points,
    refund_points,
    settle_user_expiry,
    spend_points,
)


def install_default_handcraft_services(app: Flask) -> None:
    if "handcraft_craft_preset_provider" not in app.extensions:
        set_craft_preset_provider(app, PlaceholderCraftPresetProvider())
    if "handcraft_teaching_video_provider" not in app.extensions:
        set_teaching_video_provider(app, PlaceholderTeachingVideoProvider())
    if "handcraft_reward_catalog_provider" not in app.extensions:
        set_reward_catalog_provider(app, PlaceholderRewardCatalogProvider())
    if "handcraft_points_policy_provider" not in app.extensions:
        set_points_policy_provider(app, PlaceholderPointsPolicyProvider())
    if "handcraft_video_review_action" not in app.extensions:
        set_video_review_action_provider(
            app,
            DatabaseTeachingVideoReviewActionProvider(),
        )
    if "handcraft_fulfillment_action" not in app.extensions:
        set_fulfillment_action_provider(
            app,
            DatabaseFulfillmentAdminActionProvider(),
        )


__all__ = [
    "CraftPresetProvider",
    "DatabaseFulfillmentAdminActionProvider",
    "DatabaseTeachingVideoReviewActionProvider",
    "FulfillmentAdminActionProvider",
    "PlaceholderCraftPresetProvider",
    "PlaceholderPointsPolicyProvider",
    "PlaceholderRewardCatalogProvider",
    "PlaceholderTeachingVideoProvider",
    "PointsPolicyProvider",
    "PointsPolicyUnavailable",
    "RewardCatalogProvider",
    "TeachingVideoProvider",
    "TeachingVideoReviewActionProvider",
    "apply_fulfillment_admin_action",
    "apply_video_review",
    "enqueue_learning_event",
    "get_craft_preset_provider",
    "get_effective_policy",
    "get_fulfillment_action_provider",
    "get_points_policy_provider",
    "get_points_account",
    "get_points_ledger",
    "get_reward_catalog_provider",
    "get_teaching_video_provider",
    "get_video_review_action_provider",
    "install_default_handcraft_services",
    "process_pending_events",
    "record_duration_points",
    "record_training_points",
    "refund_points",
    "set_craft_preset_provider",
    "set_fulfillment_action_provider",
    "set_points_policy_provider",
    "set_reward_catalog_provider",
    "set_teaching_video_provider",
    "set_video_review_action_provider",
    "settle_user_expiry",
    "spend_points",
]
