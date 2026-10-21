"""Drive a source-specific fixture through the shared runtime."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .items import CollectionItem
from .run_id import new_run_id
from .reporting import RunReport, build_run_report
from .runtime import CollectionRuntime


def replay_fixture(
    *,
    source_id,
    fixture_dir,
    database_path,
    download_root,
    registry_path=None,
    run_id=None,
    item_builder=None,
    candidate_writer=None,
    report_root=None,
):
    started_at = datetime.now(timezone.utc).isoformat()
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
    raw_items = payload.get("items") or payload.get("list") or []
    if not raw_items:
        return RunReport(
            run_id=run_id,
            source_id=source_id,
            mode="fixture",
            discovered=0,
            failed=1,
            errors=(f"fixture has no items: {fixture_path}",),
        )

    run_id = run_id or new_run_id(source_id)
    runtime = CollectionRuntime(
        database_path=database_path,
        download_root=download_root,
        registry_path=registry_path,
        candidate_writer=candidate_writer,
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
    deferred = 0
    skipped = 0
    failed = 0
    errors = []
    for index, raw in enumerate(raw_items):
        try:
            payload = (
                item_builder(raw, index=index)
                if item_builder is not None
                else _default_item(raw, source_id=source_id, index=index)
            )
            if isinstance(payload, CollectionItem):
                item = payload
            else:
                item = _item_from_payload(
                    payload, source_id=source_id, run_id=run_id, index=index
                )
            result = runtime.write_item(item, raw_evidence_id=raw_id)
            if result["candidate_status"] == "candidate":
                written += 1
            elif result["candidate_status"] == "deferred":
                deferred += 1
            elif result["candidate_status"] == "skipped":
                skipped += 1
            else:
                blocked += 1
        except Exception as exc:
            failed += 1
            errors.append(f"{index}: {type(exc).__name__}: {exc}")

    return build_run_report(
        run_id=run_id,
        source_id=source_id,
        mode="fixture",
        database_path=database_path,
        started_at=started_at,
        finished_at=datetime.now(timezone.utc).isoformat(),
        request_count=1,
        item_counts={
            "discovered": len(raw_items),
            "written": written,
            "blocked": blocked,
            "deferred": deferred,
            "skipped": skipped,
            "failed": failed,
        },
        errors=errors,
        evidence_path=download_root,
        report_root=report_root,
    )


def _default_item(raw, *, source_id, index):
    detail_url = raw.get("detail_url")
    return {
        "source_id": source_id,
        "source_item_id": str(
            raw.get("source_item_id") or raw.get("id") or index + 1
        ),
        "source_url": raw.get("source_url")
        or detail_url
        or f"https://fixture.local/{source_id}/{index + 1}",
        "long_term_url": raw.get("long_term_url")
        or detail_url
        or f"https://fixture.local/{source_id}/{index + 1}",
        "detail_url": detail_url,
        "detail_url_status": raw.get("detail_url_status")
        or ("direct" if detail_url else "missing"),
        "locator": raw.get("locator")
        or f"fixture item {raw.get('source_item_id') or index + 1}",
        "title": raw.get("title"),
        "body_text": raw.get("body_text"),
        "extra": raw.get("extra") or {},
    }


def _item_from_payload(payload, *, source_id, run_id, index):
    merged = dict(payload)
    merged.setdefault("source_id", source_id)
    merged.setdefault("run_id", run_id)
    merged.setdefault("mode", "fixture")
    merged.setdefault("source_index", index)
    extra = dict(merged.get("extra") or {})
    known = set(CollectionItem.__dataclass_fields__)
    for key, value in list(merged.items()):
        if key not in known and key != "extra":
            extra[key] = value
            merged.pop(key)
    merged["extra"] = extra
    return CollectionItem(**merged)
