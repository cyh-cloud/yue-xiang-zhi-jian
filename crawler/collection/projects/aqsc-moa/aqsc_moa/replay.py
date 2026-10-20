"""aqsc-moa project fixture replay entry."""

from __future__ import annotations

import json
import mimetypes
from datetime import datetime, timezone
from pathlib import Path

from crawler.collection.shared.crawler_collection.evidence import RawEvidence
from crawler.collection.shared.crawler_collection.reporting import (
    build_run_report,
)
from crawler.collection.shared.crawler_collection.run_id import new_run_id
from crawler.collection.shared.crawler_collection.runtime import (
    CollectionRuntime,
)
from crawler.collection.shared.crawler_collection.testing import (
    source_fixture_dir,
)

from .candidate import write_candidate
from .parsers import fixture_item


SOURCE_ID = "aqsc-moa"


def _require_fixture_dir(fixture_dir):
    actual = Path(fixture_dir).resolve()
    expected = source_fixture_dir(SOURCE_ID).resolve()
    if actual != expected:
        raise ValueError(f"fixture directory must be {expected.as_posix()}")
    return expected


def _discover_items(fixture_dir):
    payload = json.loads(
        (fixture_dir / "discover.json").read_text(encoding="utf-8")
    )
    return {
        item["source_item_id"]: item
        for item in payload.get("items") or []
    }


def replay_aqsc_fixture(
    *,
    fixture_dir,
    database_path,
    download_root,
    registry_path,
    run_id=None,
    report_root=None,
):
    fixture_dir = _require_fixture_dir(fixture_dir)
    run_id = run_id or new_run_id(SOURCE_ID)
    started_at = datetime.now(timezone.utc).isoformat()
    runtime = CollectionRuntime(
        database_path=database_path,
        download_root=download_root,
        registry_path=registry_path,
        candidate_writer=write_candidate,
    )
    discover = _discover_items(fixture_dir)
    files = sorted(fixture_dir.glob("*.xlsx"))
    blocked = 0
    failed = 0
    errors = []
    for path in files:
        item = fixture_item(path)
        metadata = discover.get(item["source_item_id"], {})
        item.update(
            {
                "source_url": metadata.get(
                    "source_url", item["source_url"]
                ),
                "long_term_url": metadata.get(
                    "long_term_url", item["long_term_url"]
                ),
                "locator": metadata.get("locator", item["locator"]),
                "run_id": run_id,
                "mode": "fixture",
                "extra": metadata.get("extra") or {},
            }
        )
        body = path.read_bytes()
        raw_id = runtime.persist_raw(
            RawEvidence(
                source_id=SOURCE_ID,
                request_url=item["source_url"],
                final_url=item["source_url"],
                source_url=item["source_url"],
                long_term_url=item["long_term_url"],
                detail_url=None,
                detail_url_status="missing",
                fetch_url=item["source_url"],
                locator=item["locator"],
                body=body,
                content_type=(
                    mimetypes.guess_type(path.name)[0]
                    or "application/octet-stream"
                ),
                run_id=run_id,
                robots_decision="allowed",
                metadata={"file_name": path.name},
            )
        )
        try:
            result = runtime.write_item(item, raw_evidence_id=raw_id)
            if result["candidate_status"] == "blocked":
                blocked += 1
            elif result["candidate_status"] != "candidate":
                failed += 1
                errors.append(
                    f"{path.name}: {result['candidate_status']}: "
                    f"{result.get('candidate_reason')}"
                )
        except Exception as exc:
            failed += 1
            errors.append(f"{path.name}: {type(exc).__name__}: {exc}")
    return build_run_report(
        run_id=run_id,
        source_id=SOURCE_ID,
        mode="fixture",
        database_path=database_path,
        started_at=started_at,
        finished_at=datetime.now(timezone.utc).isoformat(),
        request_count=len(files),
        item_counts={
            "discovered": len(files),
            "written": 0,
            "blocked": blocked,
            "failed": failed,
        },
        errors=errors,
        evidence_path=download_root,
        report_root=report_root,
    )
