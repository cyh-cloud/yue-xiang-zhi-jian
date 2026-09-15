from __future__ import annotations


class AgriSkillError(RuntimeError):
    code = "agri_skill_error"

    def __init__(self, message: str, *, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class AgriValidationError(AgriSkillError):
    code = "validation_error"


class AgriNotFoundError(AgriSkillError):
    code = "not_found"


class AgriAccessError(AgriSkillError):
    code = "access_denied"


class AiUnavailableError(AgriSkillError):
    code = "ai_unavailable"


class PresetContentUnavailableError(AgriSkillError):
    code = "preset_content_unavailable"
