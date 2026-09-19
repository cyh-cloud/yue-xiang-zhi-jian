import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager


class ProviderError(RuntimeError):
    code = "provider_error"

    def __init__(self, message: str, *, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ProviderValidationError(ProviderError):
    code = "validation_error"


class ProviderNotFoundError(ProviderError):
    code = "not_found"


class ProviderConflictError(ProviderError):
    code = "conflict"


class ProviderUnavailableError(ProviderError):
    code = "unavailable"


class ProviderAccessDeniedError(ProviderError):
    code = "access_denied"


@contextmanager
def database_error_boundary(message: str) -> Iterator[None]:
    try:
        yield
    except sqlite3.Error as error:
        raise ProviderUnavailableError(message) from error
