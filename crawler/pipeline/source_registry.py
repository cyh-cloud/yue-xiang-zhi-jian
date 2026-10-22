"""Shared access decisions for the machine-readable source registry."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


DEFAULT_REGISTRY_PATH = (
    Path(__file__).resolve().parents[1] / "docs" / "sources.json"
)
RUNNABLE_STATUSES = frozenset({"approved", "approved-with-gaps"})
NON_RUNNABLE_ACCESS = frozenset({"login-required", "manual-only"})
NON_RUNNABLE_RIGHTS = frozenset({"prohibited", "unknown"})
ATTRIBUTION_RIGHTS = frozenset(
    {
        "noncommercial-permitted",
        "attribution-required",
        "assumed-noncommercial-user-risk",
    }
)


@dataclass(frozen=True)
class SourceDecision:
    allowed: bool
    reason: str | None = None


def load_registry(path=None):
    registry_path = Path(path) if path else DEFAULT_REGISTRY_PATH
    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    sources = payload.get("sources")
    if not isinstance(sources, list):
        raise ValueError("source registry must contain a sources list")
    registry = {}
    for source in sources:
        source_id = (source.get("id") or "").strip()
        if not source_id:
            raise ValueError("source registry entry is missing id")
        if source_id in registry:
            raise ValueError(f"duplicate source registry id: {source_id}")
        registry[source_id] = source
    return registry


def evaluate_source(source):
    if not source.get("enabled"):
        return SourceDecision(False, "source_disabled")
    status = (source.get("status") or "").strip()
    if status not in RUNNABLE_STATUSES:
        return SourceDecision(False, f"source_status:{status or 'missing'}")
    access = (source.get("access") or "").strip()
    if access in NON_RUNNABLE_ACCESS:
        return SourceDecision(False, f"source_access:{access}")
    rights = (source.get("rights_status") or "").strip()
    if rights in NON_RUNNABLE_RIGHTS:
        return SourceDecision(False, f"source_rights:{rights or 'missing'}")
    return SourceDecision(True)


def run_modes(source):
    modes = source.get("run_modes")
    if not isinstance(modes, list):
        return frozenset()
    return frozenset(str(mode) for mode in modes if str(mode).strip())


def rights_fields(source):
    rights = (source.get("rights_status") or "unknown").strip()
    domains = source.get("domains") or []
    evidence_url = source.get("rights_evidence_url")
    if not evidence_url and domains:
        evidence_url = f"https://{domains[0]}/"
    return {
        "rights_status": rights,
        "attribution_required": bool(
            source.get("attribution_required", rights in ATTRIBUTION_RIGHTS)
        ),
        "attribution_text": (
            source.get("attribution_text")
            or source.get("name")
            or source.get("id")
        ),
        "rights_evidence_url": evidence_url,
    }
