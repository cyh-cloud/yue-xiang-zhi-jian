from __future__ import annotations

from app.teacher_console.errors import (
    ProviderAccessDeniedError as LegacyProviderAccessDeniedError,
    ProviderConflictError as LegacyProviderConflictError,
    ProviderError as LegacyProviderError,
    ProviderNotFoundError as LegacyProviderNotFoundError,
    ProviderUnavailableError as LegacyProviderUnavailableError,
    ProviderValidationError as LegacyProviderValidationError,
)


class ProviderError(LegacyProviderError):
    def __init__(self, message: str, *, code: str, details: dict):
        RuntimeError.__init__(self, message)
        self.message = message
        self.code = code
        self.details = dict(details)


class ProviderValidationError(
    ProviderError,
    LegacyProviderValidationError,
):
    pass


class ProviderNotFoundError(ProviderError, LegacyProviderNotFoundError):
    pass


class ProviderConflictError(ProviderError, LegacyProviderConflictError):
    pass


class ProviderUnavailableError(
    ProviderError,
    LegacyProviderUnavailableError,
):
    pass


class ProviderAccessDeniedError(
    ProviderError,
    LegacyProviderAccessDeniedError,
):
    pass
