"""Collection-side admission. This does not decide business publication."""

from __future__ import annotations

from dataclasses import dataclass

from .registry import load_registry


RUNNABLE_STATUSES = frozenset({"approved", "approved-with-gaps"})
NON_RUNNABLE_ACCESS = frozenset({"login-required", "manual-only"})
NON_RUNNABLE_RIGHTS = frozenset({"prohibited", "unknown"})


@dataclass(frozen=True)
class AdmissionDecision:
    allowed: bool
    status: str
    reason: str | None = None


def evaluate_admission(item, *, registry_path=None, robots=None):
    source = load_registry(registry_path).get(item.source_id)
    if source is None:
        return AdmissionDecision(False, "blocked", "source_not_registered")
    if not source.get("enabled"):
        return AdmissionDecision(False, "blocked", "source_disabled")
    status = str(source.get("status") or "").strip()
    if status not in RUNNABLE_STATUSES:
        return AdmissionDecision(
            False, "blocked", f"source_status:{status or 'missing'}"
        )
    access = str(source.get("access") or "").strip()
    if access in NON_RUNNABLE_ACCESS:
        return AdmissionDecision(False, "blocked", f"source_access:{access}")
    rights = str(source.get("rights_status") or "").strip()
    if rights in NON_RUNNABLE_RIGHTS:
        return AdmissionDecision(
            False, "blocked", f"source_rights:{rights or 'missing'}"
        )
    if robots is not None and robots.decision != "allowed":
        return AdmissionDecision(
            False, "blocked", f"robots:{robots.decision}"
        )
    if item.detail_url_status != "direct":
        return AdmissionDecision(
            False, "blocked", "detail_url:missing"
        )
    return AdmissionDecision(True, "candidate")
