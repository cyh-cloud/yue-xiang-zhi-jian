"""nongmuhr project fixture replay entry."""

from __future__ import annotations

import json
from pathlib import Path

from scrapy.http import HtmlResponse

from crawler.collection.shared.crawler_collection.replay import replay_fixture
from crawler.collection.shared.crawler_collection.testing import (
    source_fixture_dir,
)

from .candidate import write_candidate
from .parsers import parse_job_detail, parse_job_list


BASE_URL = "http://nongmuhr.com"


def _require_fixture_dir(fixture_dir):
    actual = Path(fixture_dir).resolve()
    expected = source_fixture_dir("nongmuhr").resolve()
    if actual != expected:
        raise ValueError(f"fixture directory must be {expected.as_posix()}")
    return expected


def _list_html(raw):
    source_item_id = raw["source_item_id"]
    return (
        f'<a href="/EmployView.aspx?id={source_item_id}">'
        f'{raw.get("title") or ""}</a>'
    )


def _detail_html(raw):
    return (
        '<div id="project_L">'
        '<h1><a href="/CompanyView.aspx?id=1">'
        "示例农牧公司</a></h1>"
        f'<h2>招聘职位：{raw.get("title") or ""}</h2>'
        "<ul>"
        "<li>工作地点：广东</li>"
        "<li>有效时间：90 天</li>"
        "<li>招聘方式：全职</li>"
        "<li>招聘人数：2人</li>"
        "<li>性别要求：不限</li>"
        "<li>承诺月薪：面议</li>"
        "<li>发布日期：2026-10-17</li>"
        "<li>学历要求：大专</li>"
        "</ul>"
        '<div id="brief_info"><p>公开岗位职责</p></div>'
        "</div>"
    )


def replay_nongmuhr_fixture(
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
            f"{BASE_URL}/Employ.aspx",
            body=_list_html(raw).encode("utf-8"),
            encoding="utf-8",
        )
        list_item = parse_job_list(list_response)[0]
        response = HtmlResponse(
            list_item["detail_url"],
            body=_detail_html(raw).encode("utf-8"),
            encoding="utf-8",
        )
        parsed = parse_job_detail(response)
        parsed["extra"] = {
            **list_item.get("extra", {}),
            **parsed.get("extra", {}),
        }
        return parsed

    return replay_fixture(
        source_id="nongmuhr",
        fixture_dir=fixture_dir,
        database_path=database_path,
        download_root=download_root,
        registry_path=registry_path,
        run_id=run_id,
        report_root=report_root,
        item_builder=build_item,
        candidate_writer=write_candidate,
    )
