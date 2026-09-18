from __future__ import annotations


class ProviderError(RuntimeError):
    def __init__(self, message: str, *, code: str, details: dict):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details


class ProviderValidationError(ProviderError):
    pass


class ProviderNotFoundError(ProviderError):
    pass


class ProviderConflictError(ProviderError):
    pass


class ProviderUnavailableError(ProviderError):
    pass


class ProviderAccessDeniedError(ProviderError):
    pass
