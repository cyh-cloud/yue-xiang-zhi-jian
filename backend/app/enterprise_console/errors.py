from __future__ import annotations


class EnterpriseConsoleError(RuntimeError):
    code = "enterprise_console_error"

    def __init__(self, message: str, *, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class EnterpriseValidationError(EnterpriseConsoleError):
    code = "validation_error"


class EnterpriseNotFoundError(EnterpriseConsoleError):
    code = "not_found"


class EnterpriseConflictError(EnterpriseConsoleError):
    code = "conflict"


class ProviderError(EnterpriseConsoleError):
    code = "provider_error"


class ProviderValidationError(ProviderError):
    code = "provider_validation_error"


class ProviderNotFoundError(ProviderError):
    code = "provider_not_found"


class ProviderConflictError(ProviderError):
    code = "provider_conflict"


class ProviderUnavailableError(ProviderError):
    code = "provider_unavailable"


class ProviderAccessDeniedError(ProviderError):
    code = "provider_access_denied"
