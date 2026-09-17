from __future__ import annotations

from flask import Flask

from app.handcraft_inheritance.providers import (
    CraftPresetProvider,
    PointsPolicyProvider,
    RewardCatalogProvider,
    TeachingVideoProvider,
    get_craft_preset_provider,
    get_points_policy_provider,
    get_reward_catalog_provider,
    get_teaching_video_provider,
    set_craft_preset_provider,
    set_points_policy_provider,
    set_reward_catalog_provider,
    set_teaching_video_provider,
)
from app.handcraft_inheritance.presets import (
    PlaceholderCraftPresetProvider,
    PlaceholderPointsPolicyProvider,
    PlaceholderRewardCatalogProvider,
    PlaceholderTeachingVideoProvider,
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


__all__ = [
    "CraftPresetProvider",
    "PlaceholderCraftPresetProvider",
    "PlaceholderPointsPolicyProvider",
    "PlaceholderRewardCatalogProvider",
    "PlaceholderTeachingVideoProvider",
    "PointsPolicyProvider",
    "RewardCatalogProvider",
    "TeachingVideoProvider",
    "get_craft_preset_provider",
    "get_points_policy_provider",
    "get_reward_catalog_provider",
    "get_teaching_video_provider",
    "install_default_handcraft_services",
    "set_craft_preset_provider",
    "set_points_policy_provider",
    "set_reward_catalog_provider",
    "set_teaching_video_provider",
]
