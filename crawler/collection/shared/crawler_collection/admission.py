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


def _value(item, name, default=None):
    if isinstance(item, dict):
        return item.get(name, default)
    return getattr(item, name, default)


def evaluate_admission(
    item,
    *,
    registry_path=None,
    robots=None,
    fetch_status=None,
    status_code=None,
):
    source_id = _value(item, "source_id")
    detail_url_status = _value(item, "detail_url_status")
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
    item_rights = _value(item, "rights_status")
    if item_rights is None:
        item_rights = rights
    item_rights = str(item_rights or "").strip()
    if not item_rights or item_rights in NON_RUNNABLE_RIGHTS:
        return AdmissionDecision(
            False, "blocked", f"item_rights:{item_rights or 'missing'}"
        )
    item_access = _value(item, "access_level")
    if item_access is None:
        item_access = access
    item_access = str(item_access or "").strip()
    if item_access in NON_RUNNABLE_ACCESS:
        return AdmissionDecision(
            False, "blocked", f"item_access:{item_access}"
        )
    fetch_status = str(fetch_status or "").strip()
    if (
        fetch_status in {"http_error", "error", "unknown"}
        or (
            status_code is not None
            and int(status_code) >= 400
        )
    ):
        reason = f"fetch:{fetch_status or 'http_error'}"
        if status_code is not None:
            reason = f"{reason}:{status_code}"
        return AdmissionDecision(False, "blocked", reason)
    if robots is None:
        return AdmissionDecision(False, "blocked", "robots:unknown")
    if robots.decision not in {"allowed", "not-found"}:
        return AdmissionDecision(
            False, "blocked", f"robots:{robots.decision}"
        )
    item_status = str(_value(item, "candidate_status") or "").strip()
    item_reason = _value(item, "candidate_reason")
    if item_status == "blocked":
        return AdmissionDecision(
            True,
            "blocked",
            item_reason or "item:blocked",
        )
    if robots.decision == "not-found":
        return AdmissionDecision(True, "deferred", "robots:not-found")
    if item_status == "deferred":
        return AdmissionDecision(
            True, "deferred", item_reason or "item:deferred"
        )
    if detail_url_status != "direct":
        long_term_url = _value(item, "long_term_url")
        locator = _value(item, "locator")
        if (
            not str(long_term_url or "").strip()
            or not str(locator or "").strip()
        ):
            return AdmissionDecision(
                True, "deferred", "detail_url:missing"
            )
    if detail_url_status == "direct" and not str(
        _value(item, "detail_url") or ""
    ).strip():
        return AdmissionDecision(
            False, "blocked", "detail_url:missing"
        )
    return AdmissionDecision(True, "candidate")
