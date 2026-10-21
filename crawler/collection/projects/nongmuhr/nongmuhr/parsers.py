"""Site-specific nongmuhr list and detail parsing."""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urljoin, urlparse

from bs4 import BeautifulSoup


BASE_URL = "http://nongmuhr.com/"
_SPACE = re.compile(r"\s+")


def _text(node):
    if node is None:
        return None
    value = _SPACE.sub(" ", node.get_text(" ", strip=True)).strip()
    return value or None


def _normalized_label(value):
    return re.sub(r"\s+", "", value or "").rstrip("：:")


def _field(container, label):
    for cell in container.select("td"):
        if _normalized_label(_text(cell)) != label:
            continue
        value = cell.find_next_sibling("td")
        return _text(value)
    return None


def _int_field(container, label):
    value = _field(container, label)
    if not value:
        return None
    match = re.search(r"\d+", value)
    return int(match.group(0)) if match else None


def _inline_field(text, label, following_labels):
    if not text:
        return None
    stops = "|".join(
        re.escape(item) for item in ("|", *following_labels)
    )
    match = re.search(
        rf"{re.escape(label)}\s*[：:]\s*(.*?)(?=\s*(?:{stops})\s*[：:|]|$)",
        text,
    )
    if not match:
        return None
    return _SPACE.sub(" ", match.group(1)).strip(" \t|") or None


def _int_text(value):
    if not value:
        return None
    match = re.search(r"\d+", value)
    return int(match.group(0)) if match else None


def _job_id(url):
    query = parse_qs(urlparse(url).query)
    return (query.get("id") or query.get("Id") or [None])[0]


def _description(soup):
    heading = next(
        (
            node
            for node in soup.find_all(string=True)
            if "职位描述及具体要求" in str(node)
        ),
        None,
    )
    if heading is None:
        return None
    heading_row = heading.find_parent("tr")
    body_row = heading_row.find_next_sibling("tr") if heading_row else None
    return _text(body_row.find("td")) if body_row else None


def _company_meta(soup):
    text = _text(soup.select_one("#joblist1 td.y12x"))
    return {
        "company_industry": _inline_field(
            text, "所属行业", ("公司规模", "公司性质", "所在地区")
        ),
        "company_size": _inline_field(
            text, "公司规模", ("公司性质", "所在地区")
        ),
        "company_nature": _inline_field(
            text, "公司性质", ("所在地区",)
        ),
        "company_region": _inline_field(text, "所在地区", ()),
    }


def parse_job_list(response):
    soup = BeautifulSoup(response.text, "html.parser")
    items = []
    seen = set()
    for block in soup.select("#joblist_table div.joblist_showlist"):
        row = block.find_parent("tr")
        if row is None:
            continue
        link = row.select_one(
            'td.joblist_jobname a[href*="EmployView.aspx"]'
        )
        if link is None:
            continue
        detail_url = urljoin(response.url or BASE_URL, link.get("href"))
        source_item_id = _job_id(detail_url)
        if not source_item_id or source_item_id in seen:
            continue
        seen.add(source_item_id)
        company = row.select_one(
            'td.joblist_a a[id^="rptList_hlCompany_"]'
        )
        location = row.select_one("div.fontover_hide.width_105")
        relative_time = row.select_one('td[width="105"]')
        info = _text(row.select_one("div.job_list_zf"))
        summary = row.select_one('td[height="48"]')
        items.append(
            {
                "source_item_id": source_item_id,
                "title": _text(link),
                "detail_url": detail_url,
                "extra": {
                    "company_name": _text(company),
                    "company_url": (
                        urljoin(response.url or BASE_URL, company.get("href"))
                        if company is not None and company.get("href")
                        else None
                    ),
                    "location_raw": _text(location),
                    "listed_relative_time": _text(relative_time),
                    "headcount": _int_text(
                        _inline_field(info, "招聘人数", ("月薪",))
                    ),
                    "salary_raw": _inline_field(
                        info, "月薪", ("学历要求", "公司规模", "公司性质")
                    ),
                    "education_raw": _inline_field(
                        info, "学历要求", ("公司规模", "公司性质")
                    ),
                    "company_size": _inline_field(
                        info, "公司规模", ("公司性质",)
                    ),
                    "company_nature": _inline_field(
                        info, "公司性质", ()
                    ),
                    "list_description": _text(summary),
                },
            }
        )
    return items


def parse_job_detail(response):
    soup = BeautifulSoup(response.text, "html.parser")
    title = _text(soup.select_one("#joblist .joblistonelf"))
    if not title:
        raise ValueError("nongmuhr job title container not found")
    company = soup.select_one("#joblist #hlCompanyName")
    company_url = (
        urljoin(response.url or BASE_URL, company.get("href"))
        if company is not None and company.get("href")
        else None
    )
    meta = _company_meta(soup)
    return {
        "source_item_id": _job_id(response.url),
        "title": title,
        "source_url": response.url,
        "long_term_url": response.url,
        "detail_url": response.url,
        "detail_url_status": "direct",
        "body_text": _description(soup),
        "extra": {
            "company_name": _text(company),
            "company_url": company_url,
            "location_raw": _field(soup, "工作地点"),
            "employment_type": _field(soup, "工作性质"),
            "department": _field(soup, "部门"),
            "headcount": _int_field(soup, "招聘人数"),
            "deadline_at": _field(soup, "截止日期"),
            "experience_raw": _field(soup, "工作经验"),
            "education_raw": _field(soup, "学历"),
            "gender_requirement": _field(soup, "性别"),
            "age_requirement": _field(soup, "年龄"),
            "published_at": _field(soup, "发布时间"),
            **meta,
            "rights_risk": {
                "status": "attribution-required",
                "notice": "只采集公开岗位字段，不采集登录后联系方式。",
            },
        },
    }
