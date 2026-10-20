"""Discover the eight independent Scrapy project packages."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


PROJECT_IDS = (
    "ihchina",
    "nzrc",
    "nongmuhr",
    "dialect-org",
    "cass-linguistics",
    "feiyiw",
    "aqsc-moa",
    "cnipa",
)


@dataclass(frozen=True)
class ProjectInfo:
    source_id: str
    root: Path
    config_path: Path
    package_path: Path


def discover_projects(root):
    base = Path(root)
    projects = {}
    actual_ids = {
        path.name
        for path in base.iterdir()
        if path.is_dir()
        and path.name != "__pycache__"
        and (path / "scrapy.cfg").is_file()
    }
    if actual_ids != set(PROJECT_IDS):
        raise ValueError(
            "Scrapy project list does not match the frozen eight-project scope: "
            + ", ".join(sorted(actual_ids))
        )
    for source_id in PROJECT_IDS:
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
