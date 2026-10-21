"""Site-specific fixture replay for ihchina."""

from __future__ import annotations

import json
from pathlib import Path

from scrapy.http import HtmlResponse, TextResponse

from crawler.collection.shared.crawler_collection.replay import replay_fixture
from crawler.collection.shared.crawler_collection.testing import (
    source_fixture_dir,
)

from .candidate import write_candidate
from .parsers import parse_list_page, parse_project_detail


BASE_URL = "https://www.ihchina.cn"


def _require_fixture_dir(fixture_dir):
    actual = Path(fixture_dir).resolve()
    expected = source_fixture_dir("ihchina").resolve()
    if actual != expected:
        raise ValueError(f"fixture directory must be {expected.as_posix()}")
    return expected


def _detail_html(raw):
    source_item_id = str(raw["id"])
    relations = ""
    if source_item_id == "12178":
        relations = """
        <div class="inherit_xx2">
          <div class="x-tables"><table>
            <tr><th>序号</th><th>姓名</th><th>性别</th><th>出生日期</th>
              <th>民族</th><th>类别</th><th>项目编号</th>
              <th>项目名称</th><th>申报地区或单位</th></tr>
            <tr><td>01</td><td><a href="/ccr_detail/716.html">王安江</a></td>
              <td>男</td><td>1935.11</td><td>苗族</td><td>民间文学</td>
              <td>Ⅰ-1</td><td>苗族古歌</td><td>贵州省台江县</td></tr>
          </table></div>
          <div class="x-tables"><table>
            <tr><th>编号</th><th>项目名称</th><th>类型</th><th>地区</th></tr>
            <tr><td>Ⅰ-2</td>
              <td><a href="/project_details/12179.html">相关项目</a></td>
              <td>民间文学</td><td>贵州省</td></tr>
          </table></div>
        </div>
        """
    image = (
        '<img src="/uploads/project.jpg">'
        if source_item_id == "12178"
        else ""
    )
    return (
        '<div class="article-mod2">'
        f'<div class="t_head"><div class="h30">{raw.get("title")}</div></div>'
        '<div class="table">'
        f'<div class="p">项目编号：{raw.get("num") or ""}</div>'
        f'<div class="p">类别：{raw.get("cate") or ""}</div>'
        f'<div class="p">申报地区或单位：{raw.get("province") or ""}</div>'
        '<div class="p">保护单位：示例保护单位</div>'
        "</div>"
        f'<div class="text"><div class="p">公开项目正文{image}</div></div>'
        "</div>"
        f"{relations}"
    )


def replay_ihchina_fixture(
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
    list_response = TextResponse(
        url=(
            f"{BASE_URL}/getProject.html?"
            "category_id=16&limit=10&p=1"
        ),
        body=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        encoding="utf-8",
    )
    list_items = {
        item["source_item_id"]: item
        for item in parse_list_page(list_response)["items"]
    }

    def build_item(raw, *, index):
        source_item_id = str(raw["id"])
        list_item = list_items[source_item_id]
        detail_url = (
            f"{BASE_URL}/project_details/{source_item_id}.html"
        )
        response = HtmlResponse(
            detail_url,
            body=_detail_html(raw).encode("utf-8"),
            encoding="utf-8",
        )
        parsed = parse_project_detail(response)
        parsed["extra"] = {
            **list_item.get("extra", {}),
            **parsed.get("extra", {}),
        }
        return parsed

    return replay_fixture(
        source_id="ihchina",
        fixture_dir=fixture_dir,
        database_path=database_path,
        download_root=download_root,
        registry_path=registry_path,
        run_id=run_id,
        report_root=report_root,
        item_builder=build_item,
        candidate_writer=write_candidate,
    )
