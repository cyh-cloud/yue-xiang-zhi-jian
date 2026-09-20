from __future__ import annotations


class ProviderError(RuntimeError):
    def __init__(self, message: str, *, code: str, details: dict):
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = dict(details)


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
