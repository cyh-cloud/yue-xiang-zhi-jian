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
    ) -> bool: ...

    def release_stock(self, reservation_id: str) -> bool: ...


class PointsPolicyProvider(Protocol):
    def get_policy(self) -> dict | None: ...


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
    ) -> bool:
        return False

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
