"""cass-linguistics project fixture replay entry."""

from __future__ import annotations

import json
from pathlib import Path

from scrapy.http import HtmlResponse

from crawler.collection.shared.crawler_collection.replay import replay_fixture
from crawler.collection.shared.crawler_collection.testing import (
    source_fixture_dir,
)

from .candidate import write_candidate
from .parsers import parse_article_detail, parse_article_list


BASE_URL = "http://ling.cass.cn"


def _require_fixture_dir(fixture_dir):
    actual = Path(fixture_dir).resolve()
    expected = source_fixture_dir("cass-linguistics").resolve()
    if actual != expected:
        raise ValueError(f"fixture directory must be {expected.as_posix()}")
    return expected


def _list_html(raw):
    source_item_id = raw["source_item_id"]
    return (
        '<div class="li_pgUl"><div class="li_bqListRight">'
        f'<h2><a href="/news/bensuo/202609/'
        f't20260904_{source_item_id}.html">'
        f'{raw.get("title") or ""}</a></h2>'
        f'<p>{raw.get("summary") or ""}</p>'
        "</div></div>"
    )


def _detail_html(raw):
    return (
        "<html><head>"
        f'<title>{raw.get("title") or ""}</title>'
        "</head><body>"
        f'<div class="TRS_Editor"><p>{raw.get("body_text") or ""}</p></div>'
        "<span>来源：中国社会科学网</span>"
        f'<span>时间：{raw.get("published_at") or ""}</span>'
        "</body></html>"
    )


def replay_cass_fixture(
    *,
    fixture_dir,
    database_path,
    download_root,
    registry_path,
    run_id=None,
    report_root=None,
):
    fixture_dir = _require_fixture_dir(fixture_dir)
    payload = json.loads(
        (fixture_dir / "discover.json").read_text(encoding="utf-8")
    )

    def build_item(raw, *, index):
        list_response = HtmlResponse(
            f"{BASE_URL}/news/bensuo/",
            body=_list_html(raw).encode("utf-8"),
            encoding="utf-8",
        )
        list_item = parse_article_list(list_response)["items"][0]
        response = HtmlResponse(
            list_item["detail_url"],
            body=_detail_html(raw).encode("utf-8"),
            encoding="utf-8",
        )
        parsed = parse_article_detail(response)
        parsed["extra"] = {
            **list_item,
            **parsed.get("extra", {}),
        }
        return parsed

    return replay_fixture(
        source_id="cass-linguistics",
        fixture_dir=fixture_dir,
        database_path=database_path,
        download_root=download_root,
        registry_path=registry_path,
        run_id=run_id,
        report_root=report_root,
        item_builder=build_item,
        candidate_writer=write_candidate,
    )
