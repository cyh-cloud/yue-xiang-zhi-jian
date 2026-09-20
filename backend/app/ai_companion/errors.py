from __future__ import annotations


class AiCompanionError(RuntimeError):
    code = "ai_companion_error"

    def __init__(self, message: str, *, details: dict | None = None):
        RuntimeError.__init__(self, message)
        self.message = message
        self.details = dict(details or {})


class AiCompanionValidationError(AiCompanionError):
    code = "validation_error"


class AiCompanionForbiddenError(AiCompanionError):
    code = "access_denied"


class AiCompanionNotFoundError(AiCompanionError):
    code = "not_found"


class AiCompanionKnowledgeUnavailableError(AiCompanionError):
    code = "knowledge_unavailable"


class AiCompanionAiUnavailableError(AiCompanionError):
    code = "ai_unavailable"


class AiCompanionRecognitionError(AiCompanionError):
    code = "recognition_failed"
