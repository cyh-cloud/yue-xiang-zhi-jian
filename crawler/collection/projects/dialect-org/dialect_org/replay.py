"""dialect-org project fixture replay entry."""

from __future__ import annotations

from pathlib import Path

from scrapy.http import HtmlResponse

from crawler.collection.shared.crawler_collection.replay import replay_fixture
from crawler.collection.shared.crawler_collection.testing import (
    source_fixture_dir,
)

from .candidate import write_candidate
from .parsers import parse_dialect_detail, parse_dialect_list


BASE_URL = "https://dialect.org.cn"


def _require_fixture_dir(fixture_dir):
    actual = Path(fixture_dir).resolve()
    expected = source_fixture_dir("dialect-org").resolve()
    if actual != expected:
        raise ValueError(f"fixture directory must be {expected.as_posix()}")
    return expected


def _build_item(raw, *, index):
    source_item_id = str(raw["source_item_id"])
    list_response = HtmlResponse(
        f"{BASE_URL}/",
        body=(
            f'<a href="/dialect/{source_item_id}">'
            f'{raw.get("title") or "食饭"}</a>'
        ).encode("utf-8"),
        encoding="utf-8",
    )
    list_item = parse_dialect_list(list_response)[0]
    response = HtmlResponse(
        list_item["detail_url"],
        body=raw["detail_html"].encode("utf-8"),
        encoding="utf-8",
    )
    parsed = parse_dialect_detail(response)
    point = dict(parsed["point"])
    point["extra"] = {
        **point.get("extra", {}),
        **list_item.get("extra", {}),
        "lexeme": parsed["lexeme"],
    }
    return point


def replay_dialect_fixture(
    *,
    fixture_dir,
    database_path,
    download_root,
    registry_path,
    run_id=None,
    report_root=None,
):
    fixture_dir = _require_fixture_dir(fixture_dir)
    return replay_fixture(
        source_id="dialect-org",
        fixture_dir=fixture_dir,
        database_path=database_path,
        download_root=download_root,
        registry_path=registry_path,
        run_id=run_id,
        report_root=report_root,
        item_builder=_build_item,
        candidate_writer=write_candidate,
    )
