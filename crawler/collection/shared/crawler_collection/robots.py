"""A serializable record of the robots decision used for a request."""

from __future__ import annotations

from dataclasses import dataclass


ROBOTS_DECISIONS = frozenset({"allowed", "disallowed", "unknown"})


@dataclass(frozen=True)
class RobotsFact:
    decision: str
    evidence_url: str | None = None
    checked_at: str | None = None

    def __post_init__(self):
        if self.decision not in ROBOTS_DECISIONS:
            raise ValueError(
                "robots decision must be allowed, disallowed, or unknown"
            )
