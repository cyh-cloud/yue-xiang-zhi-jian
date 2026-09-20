from __future__ import annotations

from typing import NoReturn

from app.government_console.errors import (
    ProviderAccessDeniedError,
    ProviderConflictError,
    ProviderError,
    ProviderNotFoundError,
    ProviderUnavailableError,
    ProviderValidationError,
)


class LocalResourceError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        code: str,
        details: dict | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}


class LocalResourceValidationError(LocalResourceError):
    def __init__(self, message: str, *, details: dict | None = None) -> None:
        super().__init__(message, code="validation_error", details=details)


class LocalResourceNotFoundError(LocalResourceError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="not_found")


class LocalResourceConflictError(LocalResourceError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="conflict")


class LocalResourceUnavailableError(LocalResourceError):
    def __init__(self, message: str, *, details: dict | None = None) -> None:
        super().__init__(message, code="unavailable", details=details)


class LocalResourceAccessDeniedError(LocalResourceError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="access_denied")


class LocalResourceAiUnavailableError(LocalResourceUnavailableError):
    def __init__(self) -> None:
        super().__init__("AI 服务暂时不可用")


def map_provider_error(
    error: ProviderError,
    *,
    missing_message: str,
    unknown_message: str,
) -> NoReturn:
    if isinstance(error, ProviderValidationError):
        raise LocalResourceValidationError(
            error.message,
            details=error.details,
        ) from error
    if isinstance(error, ProviderNotFoundError):
        raise LocalResourceNotFoundError(missing_message) from error
    if isinstance(error, ProviderConflictError):
        raise LocalResourceConflictError(error.message) from error
    if isinstance(error, ProviderUnavailableError):
        raise LocalResourceUnavailableError(
            error.message,
            details=error.details,
        ) from error
    if isinstance(error, ProviderAccessDeniedError):
        raise LocalResourceAccessDeniedError(error.message) from error
    raise LocalResourceUnavailableError(unknown_message) from error
