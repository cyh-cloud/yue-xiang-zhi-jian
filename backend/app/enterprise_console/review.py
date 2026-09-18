from __future__ import annotations

from typing import Protocol

from flask import Flask, current_app

from app.enterprise_console.errors import ProviderUnavailableError


class ContentReviewProvider(Protocol):
    def submit_for_review(
        self,
        *,
        content_type: str,
        content_id: str,
        submitter_id: int,
        expected_version: int,
        payload: dict,
    ) -> dict: ...

    def get_review_status(
        self,
        *,
        content_type: str,
        content_id: str,
    ) -> dict | None: ...

    def approve(
        self,
        *,
        content_type: str,
        content_id: str,
        submitter_id: int,
        reviewer_id: int,
        reviewer_role: str,
        expected_version: int,
    ) -> dict: ...

    def reject(
        self,
        *,
        content_type: str,
        content_id: str,
        submitter_id: int,
        reviewer_id: int,
        reviewer_role: str,
        expected_version: int,
        opinion: str,
    ) -> dict: ...

    def edit(
        self,
        *,
        content_type: str,
        content_id: str,
        submitter_id: int,
        expected_version: int,
        payload: dict,
    ) -> dict: ...


class UnavailableContentReviewProvider:
    def _unavailable(self):
        raise ProviderUnavailableError("内容审核服务暂不可用")

    submit_for_review = _unavailable
    get_review_status = _unavailable
    approve = _unavailable
    reject = _unavailable
    edit = _unavailable


def set_content_review_provider(app: Flask, provider: ContentReviewProvider) -> None:
    app.extensions["content_review_provider"] = provider


def get_content_review_provider() -> ContentReviewProvider:
    return current_app.extensions.get(
        "content_review_provider",
        UnavailableContentReviewProvider(),
    )
