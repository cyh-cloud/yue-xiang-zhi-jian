from __future__ import annotations

from typing import Protocol

from flask import Flask, current_app

from app.admin_console.errors import ProviderUnavailableError


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


class DatabaseAssistantFeatureKnowledgeProvider(
    UnavailableAssistantFeatureKnowledgeProvider
):
    pass


class DatabaseFeedbackIntakeProvider(UnavailableFeedbackIntakeProvider):
    pass


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


def configure_admin_providers(
    app: Flask,
    *,
    knowledge: AssistantFeatureKnowledgeProvider | None = None,
    feedback_intake: FeedbackIntakeProvider | None = None,
) -> None:
    if knowledge is not None:
        set_assistant_feature_knowledge_provider(app, knowledge)
    if feedback_intake is not None:
        set_feedback_intake_provider(app, feedback_intake)


def install_default_admin_services(app: Flask) -> None:
    if "assistant_feature_knowledge_provider" not in app.extensions:
        set_assistant_feature_knowledge_provider(
            app,
            DatabaseAssistantFeatureKnowledgeProvider(),
        )
    if "feedback_intake_provider" not in app.extensions:
        set_feedback_intake_provider(
            app,
            DatabaseFeedbackIntakeProvider(),
        )
