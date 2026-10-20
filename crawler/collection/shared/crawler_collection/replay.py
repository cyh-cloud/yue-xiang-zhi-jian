"""Drive a source-specific fixture through the shared runtime."""

from __future__ import annotations

import json
from pathlib import Path

from .items import CollectionItem
from .reporting import RunReport
from .runtime import CollectionRuntime


def replay_fixture(
    *,
    source_id,
    fixture_dir,
    database_path,
    download_root,
    registry_path=None,
    run_id="fixture-replay",
):
    fixture_dir = Path(fixture_dir)
    fixture_path = fixture_dir / "discover.json"
    if not fixture_path.is_file():
        return RunReport(
            run_id=run_id,
            source_id=source_id,
            mode="fixture",
            discovered=0,
            failed=1,
            errors=(f"fixture not found: {fixture_path}",),
        )
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    raw_items = payload.get("items") or []
    if not raw_items:
        return RunReport(
            run_id=run_id,
            source_id=source_id,
            mode="fixture",
            discovered=0,
            failed=1,
            errors=(f"fixture has no items: {fixture_path}",),
        )

    runtime = CollectionRuntime(
        database_path=database_path,
        download_root=download_root,
        registry_path=registry_path,
    )
    raw_id = runtime.persist_raw(
        runtime.evidence_from_fixture(
            source_id=source_id,
            body=fixture_path.read_bytes(),
            request_url="https://fixture.local/discover.json",
            content_type="application/json",
            run_id=run_id,
        )
    )
    written = 0
    blocked = 0
    failed = 0
    for index, raw in enumerate(raw_items):
        try:
            item = CollectionItem(
                source_id=source_id,
                source_item_id=str(raw["source_item_id"]),
                source_url=raw["source_url"],
                long_term_url=raw["long_term_url"],
                detail_url=raw.get("detail_url"),
                detail_url_status=raw["detail_url_status"],
                locator=raw.get("locator"),
                title=raw.get("title"),
                run_id=run_id,
                mode="fixture",
                rights_status="attribution-required",
                source_index=index,
            )
            result = runtime.write_item(item, raw_evidence_id=raw_id)
            if result["candidate_status"] == "candidate":
                written += 1
            else:
                blocked += 1
        except Exception as exc:
            failed += 1

    return RunReport(
        run_id=run_id,
        source_id=source_id,
        mode="fixture",
        discovered=len(raw_items),
        written=written,
        blocked=blocked,
        failed=failed,
    )
