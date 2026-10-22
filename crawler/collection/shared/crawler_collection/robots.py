"""Auditable robots decisions backed by Scrapy's robots middleware."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlparse

from scrapy.downloadermiddlewares.robotstxt import RobotsTxtMiddleware
from scrapy.exceptions import IgnoreRequest


ROBOTS_DECISIONS = frozenset(
    {"allowed", "disallowed", "not-found", "unknown"}
)


@dataclass(frozen=True)
class RobotsFact:
    decision: str
    evidence_url: str | None = None
    checked_at: str | None = None
    status_code: int | None = None

    def __post_init__(self):
        if self.decision not in ROBOTS_DECISIONS:
            raise ValueError(
                "robots decision must be allowed, disallowed, not-found, "
                "or unknown"
            )


def robots_fact_from_status(
    status_code,
    *,
    parser_allows,
    evidence_url=None,
    checked_at=None,
):
    """Map the actual robots.txt response to a conservative audit fact."""
    if status_code is not None and 200 <= int(status_code) < 300:
        decision = "allowed" if parser_allows else "disallowed"
    elif status_code in {404, 410}:
        decision = "not-found"
    else:
        decision = "unknown"
    return RobotsFact(
        decision,
        evidence_url=evidence_url,
        checked_at=checked_at or datetime.now(timezone.utc).isoformat(),
        status_code=status_code,
    )


class RobotsEvidenceMiddleware(RobotsTxtMiddleware):
    """Run Scrapy robots checks and attach the real result to each request."""

    def __init__(self, crawler):
        super().__init__(crawler)
        self._facts = {}
        self._schemes = {}

    async def process_request(self, request, spider=None):
        parsed = urlparse(request.url)
        netloc = parsed.netloc
        self._schemes[netloc] = parsed.scheme or "https"
        try:
            await super().process_request(request, spider)
        except IgnoreRequest:
            fact = self._facts.get(netloc) or RobotsFact(
                "disallowed",
                evidence_url=self._robots_url(netloc),
            )
            self._attach(request, RobotsFact(
                "disallowed",
                evidence_url=fact.evidence_url,
                checked_at=fact.checked_at,
                status_code=fact.status_code,
            ))
            raise
        if not request.meta.get("dont_obey_robotstxt"):
            fact = self._facts.get(netloc) or RobotsFact(
                "unknown",
                evidence_url=self._robots_url(netloc),
            )
            self._attach(request, fact)
            if fact.decision == "unknown":
                raise IgnoreRequest("robots:unknown")

    def _parse_robots(self, response, netloc):
        super()._parse_robots(response, netloc)
        self._facts[netloc] = robots_fact_from_status(
            response.status,
            parser_allows=response.status < 300,
            evidence_url=response.url,
        )

    def _robots_error(self, exc, netloc):
        super()._robots_error(exc, netloc)
        self._facts[netloc] = RobotsFact(
            "unknown",
            evidence_url=self._robots_url(netloc),
        )

    def _robots_url(self, netloc):
        scheme = self._schemes.get(netloc, "https")
        return f"{scheme}://{netloc}/robots.txt"

    @staticmethod
    def _attach(request, fact):
        request.meta["robots_decision"] = fact.decision
        request.meta["robots_status_code"] = fact.status_code
        request.meta["robots_evidence_url"] = fact.evidence_url
        request.meta["robots_checked_at"] = fact.checked_at
