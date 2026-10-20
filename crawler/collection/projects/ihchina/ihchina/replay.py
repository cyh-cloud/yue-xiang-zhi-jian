"""Site-specific fixture adapter for ihchina."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from crawler.collection.shared.crawler_collection.replay import (
    replay_fixture,
)


def replay_ihchina_fixture(*, fixture_dir, database_path, download_root,
                           registry_path):
    fixture_dir = Path(fixture_dir)
    payload = json.loads(
        (fixture_dir / "discover.json").read_text(encoding="utf-8")
    )
    raw_items = payload.get("list") or []
    with tempfile.TemporaryDirectory() as tmp:
        adapted = Path(tmp) / "ihchina"
        adapted.mkdir()
        (adapted / "discover.json").write_text(
            json.dumps(
                {
                    "items": [
                        {
                            "source_item_id": str(raw["id"]),
                            "title": raw.get("title"),
                            "source_url": (
                                "https://www.ihchina.cn/project_details/"
                                f"{raw['id']}.html"
                            ),
                            "long_term_url": (
                                "https://www.ihchina.cn/project_details/"
                                f"{raw['id']}.html"
                            ),
                            "detail_url": (
                                "https://www.ihchina.cn/project_details/"
                                f"{raw['id']}.html"
                            ),
                            "detail_url_status": "direct",
                            "locator": f"list item {raw['id']}",
                        }
                        for raw in raw_items
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return replay_fixture(
            source_id="ihchina",
            fixture_dir=adapted,
            database_path=database_path,
            download_root=download_root,
            registry_path=registry_path,
        )
