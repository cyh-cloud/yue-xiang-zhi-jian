from __future__ import annotations

from typing import Protocol

from flask import Flask, current_app


class MessagingSourceProvider(Protocol):
    def has_application_relationship(
        self, student_id: int, enterprise_id: int
    ) -> bool: ...

    def list_applied_enterprise_ids(self, student_id: int) -> list[int]: ...

    def list_applicant_student_ids(self, enterprise_id: int) -> list[int]: ...

    def list_policy_subscriber_ids(self, category: str) -> list[int]: ...

    def list_product_subscriber_ids(self, product_key: str) -> list[int]: ...


class NullMessagingSourceProvider:
    def has_application_relationship(
        self, student_id: int, enterprise_id: int
    ) -> bool:
        return False

    def list_applied_enterprise_ids(self, student_id: int) -> list[int]:
        return []

    def list_applicant_student_ids(self, enterprise_id: int) -> list[int]:
        return []

    def list_policy_subscriber_ids(self, category: str) -> list[int]:
        return []

    def list_product_subscriber_ids(self, product_key: str) -> list[int]:
        return []


class CompositeMessagingSourceProvider:
    def __init__(self, providers: list[MessagingSourceProvider]) -> None:
        self.providers = list(providers)

    def has_application_relationship(
        self, student_id: int, enterprise_id: int
    ) -> bool:
        return any(
            provider.has_application_relationship(student_id, enterprise_id)
            for provider in self.providers
        )

    def list_applied_enterprise_ids(self, student_id: int) -> list[int]:
        return sorted(
            {
                item
                for provider in self.providers
                for item in provider.list_applied_enterprise_ids(student_id)
            }
        )

    def list_applicant_student_ids(self, enterprise_id: int) -> list[int]:
        return sorted(
            {
                item
                for provider in self.providers
                for item in provider.list_applicant_student_ids(enterprise_id)
            }
        )

    def list_policy_subscriber_ids(self, category: str) -> list[int]:
        return sorted(
            {
                item
                for provider in self.providers
                for item in provider.list_policy_subscriber_ids(category)
            }
        )

    def list_product_subscriber_ids(self, product_key: str) -> list[int]:
        return sorted(
            {
                item
                for provider in self.providers
                for item in provider.list_product_subscriber_ids(product_key)
            }
        )


def set_messaging_source_provider(
    app: Flask, provider: MessagingSourceProvider
) -> None:
    app.extensions["messaging_source_provider"] = provider


def get_messaging_source_provider() -> MessagingSourceProvider:
    return current_app.extensions.get(
        "messaging_source_provider",
        NullMessagingSourceProvider(),
    )


def register_messaging_source_provider(app: Flask, provider) -> None:
    current = app.extensions.get("messaging_source_provider")
    if isinstance(current, CompositeMessagingSourceProvider):
        current.providers.append(provider)
        return
    providers = [current, provider] if current is not None else [provider]
    set_messaging_source_provider(app, CompositeMessagingSourceProvider(providers))
