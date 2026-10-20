"""Explicit run outcomes so empty or partial runs are never success."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class RunReport:
    run_id: str
    source_id: str
    mode: str
    discovered: int
    written: int = 0
    skipped: int = 0
    failed: int = 0
    blocked: int = 0
    deferred: int = 0
    errors: tuple[str, ...] = ()

    @property
    def status(self):
        if self.discovered == 0 or self.written == 0 and self.blocked == 0:
            return "failed"
        if self.failed or self.skipped or self.blocked or self.deferred:
            return "partial"
        return "succeeded"

    def to_dict(self):
        return {**asdict(self), "status": self.status}
