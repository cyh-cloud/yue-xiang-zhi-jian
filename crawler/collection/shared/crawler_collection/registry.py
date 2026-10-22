"""Read the frozen source registry without copying site policy."""

from __future__ import annotations

import json
from pathlib import Path


DEFAULT_REGISTRY_PATH = (
    Path(__file__).resolve().parents[3] / "docs" / "sources.json"
)


def load_registry(path=None):
    registry_path = Path(path) if path else DEFAULT_REGISTRY_PATH
    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    sources = payload.get("sources")
    if not isinstance(sources, list):
        raise ValueError("source registry must contain a sources list")
    registry = {}
    for source in sources:
        source_id = str(source.get("id") or "").strip()
        if not source_id:
            raise ValueError("source registry entry is missing id")
        if source_id in registry:
            raise ValueError(f"duplicate source registry id: {source_id}")
        registry[source_id] = source
    return registry
