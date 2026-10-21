"""Discover executable Scrapy project packages from the source registry."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .registry import load_registry


RUNNABLE_STATUSES = frozenset({"approved", "approved-with-gaps"})
EXECUTABLE_RUN_MODES = frozenset({"fixture", "live"})


@dataclass(frozen=True)
class ProjectInfo:
    source_id: str
    root: Path
    config_path: Path
    package_path: Path


def executable_source_ids(registry):
    """Return sources that should have a runnable Scrapy project."""
    return {
        source_id
        for source_id, source in registry.items()
        if source.get("enabled")
        and source.get("status") in RUNNABLE_STATUSES
        and EXECUTABLE_RUN_MODES.intersection(source.get("run_modes") or ())
    }


def discover_projects(root, registry_path=None):
    base = Path(root)
    projects = {}
    expected_ids = executable_source_ids(load_registry(registry_path))
    actual_ids = {
        path.name
        for path in base.iterdir()
        if path.is_dir() and path.name != "__pycache__"
    }
    unexpected = actual_ids - expected_ids
    missing = expected_ids - actual_ids
    if unexpected:
        raise ValueError(
            "unexpected Scrapy project directories: "
            + ", ".join(sorted(unexpected))
        )
    if missing:
        raise ValueError(
            "missing Scrapy project directories: "
            + ", ".join(sorted(missing))
        )
    for source_id in sorted(expected_ids):
        project_root = base / source_id
        package_name = source_id.replace("-", "_")
        package_path = project_root / package_name
        config_path = project_root / "scrapy.cfg"
        if not config_path.is_file() or not package_path.is_dir():
            raise ValueError(f"incomplete Scrapy project: {source_id}")
        projects[source_id] = ProjectInfo(
            source_id=source_id,
            root=project_root,
            config_path=config_path,
            package_path=package_path,
        )
    return projects
