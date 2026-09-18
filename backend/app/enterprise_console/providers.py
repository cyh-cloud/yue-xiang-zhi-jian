from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING, Protocol

from flask import Flask, current_app

if TYPE_CHECKING:
    from app.enterprise_console.review import ContentReviewProvider


class JobPositionProvider(Protocol):
    def list_published_positions(self) -> list[dict]: ...

    def get_published_position(self, *, job_id: str) -> dict | None: ...


class EmptyJobPositionProvider:
    def list_published_positions(self) -> list[dict]:
        return []

    def get_published_position(self, *, job_id: str) -> dict | None:
        return None


class DatabaseJobPositionProvider(EmptyJobPositionProvider):
    """Database-backed provider that preserves the placeholder contract."""

    @staticmethod
    def _database_call(operation):
        try:
            return operation()
        except sqlite3.Error as error:
            from app.enterprise_console.errors import ProviderUnavailableError

            raise ProviderUnavailableError(
                "Job position data is unavailable"
            ) from error

    def list_published_positions(self) -> list[dict]:
        def load_records():
            from app.enterprise_console.jobs import (
                list_published_position_records,
            )

            return list_published_position_records()

        return self._database_call(load_records)

    def get_published_position(self, *, job_id: str) -> dict | None:
        def load_record():
            from app.enterprise_console.jobs import (
                get_published_position_record,
            )

            return get_published_position_record(job_id)

        return self._database_call(load_record)


class JobApplicationIntakeProvider(Protocol):
    def submit_application(
        self,
        *,
        job_id: str,
        student_id: int,
        resume_snapshot: dict,
        skill_profile_snapshot: dict | None,
        idempotency_key: str,
    ) -> dict: ...


class EmptyJobApplicationIntakeProvider:
    def submit_application(
        self,
        *,
        job_id: str,
        student_id: int,
        resume_snapshot: dict,
        skill_profile_snapshot: dict | None,
        idempotency_key: str,
    ) -> dict:
        from app.enterprise_console.errors import ProviderUnavailableError

        raise ProviderUnavailableError("申请接收服务暂不可用")


def set_job_position_provider(
    app: Flask,
    provider: JobPositionProvider,
) -> None:
    app.extensions["job_position_provider"] = provider


def get_job_position_provider() -> JobPositionProvider:
    return current_app.extensions.get(
        "job_position_provider",
        EmptyJobPositionProvider(),
    )


def set_job_application_intake_provider(
    app: Flask,
    provider: JobApplicationIntakeProvider,
) -> None:
    app.extensions["job_application_intake_provider"] = provider


def get_job_application_intake_provider() -> JobApplicationIntakeProvider:
    return current_app.extensions.get(
        "job_application_intake_provider",
        EmptyJobApplicationIntakeProvider(),
    )


def configure_enterprise_providers(
    app: Flask,
    *,
    job_position_provider: JobPositionProvider | None = None,
    job_application_intake_provider: JobApplicationIntakeProvider | None = None,
    content_review_provider: ContentReviewProvider | None = None,
) -> None:
    if job_position_provider is not None:
        set_job_position_provider(app, job_position_provider)
    if job_application_intake_provider is not None:
        set_job_application_intake_provider(
            app,
            job_application_intake_provider,
        )
    if content_review_provider is not None:
        from app.enterprise_console.review import set_content_review_provider

        set_content_review_provider(app, content_review_provider)
