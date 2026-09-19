from __future__ import annotations


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
