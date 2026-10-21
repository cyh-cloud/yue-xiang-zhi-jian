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
    extra = raw.get("extra") or {}
    return (
        '<div id="joblist_table"><table class="joblist_b_border"><tr><td>'
        '<div class="joblist_showlist"><table><tr>'
        '<td class="joblist_jobname">'
        f'<a href="/EmployView.aspx?Id={source_item_id}">'
        f'{raw.get("title") or ""}</a></td>'
        '<td class="joblist_a"><div class="fontover_hide width_240">'
        '<a id="rptList_hlCompany_0" href="'
        f'{extra.get("company_url") or "CompanyView.aspx?Id=1"}">'
        f'{extra.get("company_name") or "示例农牧公司"}</a></div></td>'
        '<td colspan="2"><div class="fontover_hide width_105">'
        f'{extra.get("location_raw") or "广东"}</div></td>'
        '<td width="105">1天前</td>'
        '</tr></table></div>'
        '<div class="joblist_info"><table><tr><td>'
        '<div class="job_list_zf">'
        f'招聘人数： <b>{extra.get("headcount") or 1}</b> | '
        f'月薪：{extra.get("salary_raw") or "面议"} | '
        f'学历要求：{extra.get("education_raw") or "大专"} '
        f'公司规模：{extra.get("company_size") or "100－499人"} | '
        f'公司性质：{extra.get("company_nature") or "民营企业"}'
        '</div></td></tr><tr><td height="48">'
        f'{extra.get("list_description") or "公开岗位摘要"}'
        '</td></tr></table></div>'
        '</td></tr></table></div>'
    )


def _detail_html(raw):
    extra = raw.get("extra") or {}
    return (
        '<div id="joblist"><div class="joblistonelf">'
        f'{raw.get("title") or ""}</div>'
        '<a id="hlCompanyName" href="'
        f'{extra.get("company_url") or "CompanyView.aspx?Id=1"}">'
        f'{extra.get("company_name") or "示例农牧公司"}</a></div>'
        '<div class="saverg"><table>'
        f'<tr><td>工作性质：</td><td>{extra.get("employment_type") or "全职"}</td>'
        f'<td>部 门：</td><td>{extra.get("department") or "生产部"}</td></tr>'
        f'<tr><td>招聘人数：</td><td>{extra.get("headcount") or 1}</td>'
        f'<td>截止日期：</td><td>{extra.get("deadline_at") or "2026-12-31"}</td></tr>'
        f'<tr><td>工作经验：</td><td>{extra.get("experience_raw") or "不限"}</td>'
        f'<td>学 历：</td><td>{extra.get("education_raw") or "大专"}</td></tr>'
        f'<tr><td>工作地点：</td><td>{extra.get("location_raw") or "广东"}</td>'
        f'<td>性 别：</td><td>{extra.get("gender_requirement") or "不限"}</td></tr>'
        f'<tr><td>年 龄：</td><td>{extra.get("age_requirement") or "不限"}</td>'
        '<td>邮 件：</td><td>{{EMAIL_demo}}</td></tr>'
        '<tr><td>职位描述及具体要求：</td></tr>'
        f'<tr><td style="word-break: break-all">{raw.get("body_text") or "公开岗位职责"}</td></tr>'
        f'<tr><td>发布时间：</td><td>{extra.get("published_at") or "2026-10-17"}</td></tr>'
        '</table></div>'
        '<div id="joblist1"><td class="y12x">'
        f'所属行业：{extra.get("company_industry") or "农业种植养殖"} '
        f'公司规模：{extra.get("company_size") or "100－499人"} '
        f'公司性质：{extra.get("company_nature") or "民营企业"} '
        '所在地区:广东</td></div>'
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
