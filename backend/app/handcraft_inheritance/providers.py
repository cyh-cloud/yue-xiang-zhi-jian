from __future__ import annotations

from typing import Protocol

from flask import Flask, current_app


class CraftPresetProvider(Protocol):
    def list_crafts(self) -> list[dict]: ...

    def get_craft(self, craft_key: str) -> dict | None: ...


class TeachingVideoProvider(Protocol):
    def list_videos(self, craft_key: str | None = None) -> list[dict]: ...

    def get_video(self, video_id: str) -> dict | None: ...

    def get_review_status(self, video_id: str) -> str | None: ...


class RewardCatalogProvider(Protocol):
    def list_rewards(self) -> list[dict]: ...

    def reserve_stock(
        self,
        reward_id: str,
        quantity: int,
        reservation_id: str,
    ) -> str | None: ...

    def release_stock(self, reservation_id: str) -> bool: ...


class PointsPolicyProvider(Protocol):
    def get_policy(self) -> dict | None: ...


class TeachingVideoReviewActionProvider(Protocol):
    def apply(self, action: dict) -> dict: ...


class FulfillmentAdminActionProvider(Protocol):
    def apply(self, action: dict) -> dict: ...


class EmptyCraftPresetProvider:
    def list_crafts(self) -> list[dict]:
        return []

    def get_craft(self, craft_key: str) -> dict | None:
        return None


class EmptyTeachingVideoProvider:
    def list_videos(self, craft_key: str | None = None) -> list[dict]:
        return []

    def get_video(self, video_id: str) -> dict | None:
        return None

    def get_review_status(self, video_id: str) -> str | None:
        return None


class EmptyRewardCatalogProvider:
    def list_rewards(self) -> list[dict]:
        return []

    def reserve_stock(
        self,
        reward_id: str,
        quantity: int,
        reservation_id: str,
    ) -> str | None:
        return None

    def release_stock(self, reservation_id: str) -> bool:
        return False


class UnavailablePointsPolicyProvider:
    def get_policy(self) -> dict | None:
        return None


def set_craft_preset_provider(
    app: Flask,
    provider: CraftPresetProvider,
) -> None:
    app.extensions["handcraft_craft_preset_provider"] = provider


def get_craft_preset_provider() -> CraftPresetProvider:
    return current_app.extensions.get(
        "handcraft_craft_preset_provider",
        EmptyCraftPresetProvider(),
    )


def set_teaching_video_provider(
    app: Flask,
    provider: TeachingVideoProvider,
) -> None:
    app.extensions["handcraft_teaching_video_provider"] = provider


def get_teaching_video_provider() -> TeachingVideoProvider:
    return current_app.extensions.get(
        "handcraft_teaching_video_provider",
        EmptyTeachingVideoProvider(),
    )


def set_reward_catalog_provider(
    app: Flask,
    provider: RewardCatalogProvider,
) -> None:
    app.extensions["handcraft_reward_catalog_provider"] = provider


def get_reward_catalog_provider() -> RewardCatalogProvider:
    return current_app.extensions.get(
        "handcraft_reward_catalog_provider",
        EmptyRewardCatalogProvider(),
    )


def set_points_policy_provider(
    app: Flask,
    provider: PointsPolicyProvider,
) -> None:
    app.extensions["handcraft_points_policy_provider"] = provider


def get_points_policy_provider() -> PointsPolicyProvider:
    return current_app.extensions.get(
        "handcraft_points_policy_provider",
        UnavailablePointsPolicyProvider(),
    )


def set_video_review_action_provider(
    app: Flask,
    provider: TeachingVideoReviewActionProvider,
) -> None:
    app.extensions["handcraft_video_review_action"] = provider


def get_video_review_action_provider() -> TeachingVideoReviewActionProvider:
    return current_app.extensions["handcraft_video_review_action"]


def set_video_review_provider(
    app: Flask,
    provider: TeachingVideoProvider | TeachingVideoReviewActionProvider,
) -> None:
    supports_read = any(
        hasattr(provider, method)
        for method in ("list_videos", "get_video", "get_review_status")
    )
    supports_actions = hasattr(provider, "apply")
    if not supports_read and not supports_actions:
        raise TypeError("video review provider must support read or action calls")
    if supports_read:
        set_teaching_video_provider(app, provider)
    if supports_actions:
        set_video_review_action_provider(app, provider)


def set_fulfillment_action_provider(
    app: Flask,
    provider: FulfillmentAdminActionProvider,
) -> None:
    app.extensions["handcraft_fulfillment_action"] = provider


def get_fulfillment_action_provider() -> FulfillmentAdminActionProvider:
    return current_app.extensions["handcraft_fulfillment_action"]
