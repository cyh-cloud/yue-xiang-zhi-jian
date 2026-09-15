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


def set_messaging_source_provider(
    app: Flask, provider: MessagingSourceProvider
) -> None:
    app.extensions["messaging_source_provider"] = provider


def get_messaging_source_provider() -> MessagingSourceProvider:
    return current_app.extensions.get(
        "messaging_source_provider",
        NullMessagingSourceProvider(),
    )
