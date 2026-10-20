"""dialect-org project fixture replay entry."""

from __future__ import annotations

from scrapy.http import HtmlResponse

from crawler.collection.shared.crawler_collection.replay import replay_fixture
from .candidate import write_candidate
from .parsers import parse_dialect_detail


def _build_item(raw, *, index):
    source_item_id = str(raw["source_item_id"])
    response = HtmlResponse(
        f"https://dialect.org.cn/dialect/{source_item_id}",
        body=raw["detail_html"].encode("utf-8"),
        encoding="utf-8",
    )
    parsed = parse_dialect_detail(response)
    point = dict(parsed["point"])
    point["extra"] = {
        **point.get("extra", {}),
        "lexeme": parsed["lexeme"],
    }
    return point


def replay_dialect_fixture(**kwargs):
    return replay_fixture(
        source_id="dialect-org",
        item_builder=_build_item,
        candidate_writer=write_candidate,
        **kwargs,
    )
