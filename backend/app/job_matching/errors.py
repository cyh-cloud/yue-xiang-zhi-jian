class JobMatchingError(RuntimeError):
    code = "job_matching_error"

    def __init__(self, message: str, *, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ResumeRequiredError(JobMatchingError):
    code = "resume_required"


class AlreadyAppliedError(JobMatchingError):
    code = "already_applied"


class JobUnavailableError(JobMatchingError):
    code = "job_unavailable"


class ResumeConflictError(JobMatchingError):
    code = "resume_conflict"


class JobMatchingValidationError(JobMatchingError):
    code = "validation_error"
