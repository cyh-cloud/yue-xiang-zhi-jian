"""feiyiw project fixture replay entry."""

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


BASE_URL = "https://www.feiyiw.cn"


def _require_fixture_dir(fixture_dir):
    actual = Path(fixture_dir).resolve()
    expected = source_fixture_dir("feiyiw").resolve()
    if actual != expected:
        raise ValueError(f"fixture directory must be {expected.as_posix()}")
    return expected


def _list_html(raw):
    source_item_id = raw["source_item_id"]
    return (
        '<div id="page-article"><div class="col-main">'
        '<ul class="content"><li>'
        '<a class="lebioa" href="/index.php?app=article&amp;'
        f'act=view&amp;article_id={source_item_id}">'
        f'{raw.get("title") or ""}</a>'
        f'<span>{raw.get("published_at") or ""}</span>'
        "</li></ul>"
        "</div></div>"
    )


def _detail_html(raw):
    return (
        '<div id="page-article"><div class="col-main">'
        '<div class="article-info">'
        f'<h1>{raw.get("title") or ""}</h1>'
        f'<h2>{raw.get("published_at") or ""}</h2>'
        "</div>"
        f'<div class="article-detail"><p>{raw.get("body_text") or ""}</p>'
        "</div>"
        "</div></div>"
    )


def replay_feiyiw_fixture(
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
            f"{BASE_URL}/index.php?app=article&cate_id=4",
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
            **list_item.get("extra", {}),
            **parsed.get("extra", {}),
        }
        return parsed

    return replay_fixture(
        source_id="feiyiw",
        fixture_dir=fixture_dir,
        database_path=database_path,
        download_root=download_root,
        registry_path=registry_path,
        run_id=run_id,
        report_root=report_root,
        item_builder=build_item,
        candidate_writer=write_candidate,
    )
