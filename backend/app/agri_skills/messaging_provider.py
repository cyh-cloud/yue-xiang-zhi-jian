from __future__ import annotations

from app.agri_skills.calendar import (
    list_product_subscriber_ids as _list_product_subscriber_ids,
)
from app.messaging.source_provider import NullMessagingSourceProvider


def list_product_subscriber_ids(product_key: str) -> list[int]:
    return _list_product_subscriber_ids(product_key)


class AgriMessagingProvider:
    def __init__(self, delegate=None) -> None:
        self.delegate = delegate or NullMessagingSourceProvider()

    def has_application_relationship(self, student_id: int, enterprise_id: int) -> bool:
        return self.delegate.has_application_relationship(student_id, enterprise_id)

    def list_applied_enterprise_ids(self, student_id: int) -> list[int]:
        return self.delegate.list_applied_enterprise_ids(student_id)

    def list_applicant_student_ids(self, enterprise_id: int) -> list[int]:
        return self.delegate.list_applicant_student_ids(enterprise_id)

    def list_policy_subscriber_ids(self, category: str) -> list[int]:
        return self.delegate.list_policy_subscriber_ids(category)

    def list_product_subscriber_ids(self, product_key: str) -> list[int]:
        return list_product_subscriber_ids(product_key)
