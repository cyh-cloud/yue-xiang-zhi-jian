from dataclasses import dataclass
from urllib.parse import urlparse


ALLOWED_PUBLISH_STATUSES = frozenset({"draft", "reviewed", "published"})
ALLOWED_RIGHTS_STATUSES = frozenset(
    {
        "noncommercial-permitted",
        "attribution-required",
        "assumed-noncommercial-user-risk",
    }
)


@dataclass(frozen=True)
class PublicationDecision:
    allowed: bool
    reason: str | None = None

    @property
    def disposition(self) -> str:
        return "candidate" if self.allowed else "skipped"


def evaluate_publication(row) -> PublicationDecision:
    """Return the single publication decision shared by runner and converter."""
    publish_status = (row.get("publish_status") or "").strip()
    if not publish_status:
        return PublicationDecision(False, "missing_publish_status")
    if publish_status not in ALLOWED_PUBLISH_STATUSES:
        return PublicationDecision(False, f"publish_status:{publish_status}")

    if row.get("detail_url_status") != "direct":
        return PublicationDecision(False, "detail_url_status_not_direct")

    detail_url = (row.get("detail_url") or "").strip()
    if not detail_url:
        return PublicationDecision(False, "missing_detail_url")
    parsed = urlparse(detail_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return PublicationDecision(False, "detail_url_not_absolute")

    rights_status = (row.get("rights_status") or "").strip()
    if rights_status not in ALLOWED_RIGHTS_STATUSES:
        return PublicationDecision(False, f"rights_status:{rights_status or 'missing'}")

    return PublicationDecision(True)
