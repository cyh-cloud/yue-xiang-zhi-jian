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
    source_id = (
        item.get("source_id")
        if isinstance(item, dict)
        else item.source_id
    )
    detail_url_status = (
        item.get("detail_url_status")
        if isinstance(item, dict)
        else item.detail_url_status
    )
    source = load_registry(registry_path).get(source_id)
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
    item_rights = str(
        item.get("rights_status")
        if isinstance(item, dict)
        else item.rights_status
    ).strip()
    if item_rights in NON_RUNNABLE_RIGHTS:
        return AdmissionDecision(
            False, "blocked", f"item_rights:{item_rights or 'missing'}"
        )
    item_access = str(
        item.get("access_level", "")
        if isinstance(item, dict)
        else getattr(item, "access_level", "")
    ).strip()
    if item_access in NON_RUNNABLE_ACCESS:
        return AdmissionDecision(
            False, "blocked", f"item_access:{item_access}"
        )
    if robots is None:
        return AdmissionDecision(False, "blocked", "robots:unknown")
    if robots.decision != "allowed":
        return AdmissionDecision(
            False, "blocked", f"robots:{robots.decision}"
        )
    if detail_url_status != "direct":
        return AdmissionDecision(
            False, "blocked", "detail_url:missing"
        )
    return AdmissionDecision(True, "candidate")
