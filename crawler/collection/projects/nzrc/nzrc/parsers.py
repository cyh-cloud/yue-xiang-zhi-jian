"""Site-specific nzrc list and detail parsing."""

from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup


BASE_URL = "http://www.nzrc.com.cn/"


def _text(node):
    return node.get_text(" ", strip=True) if node else None


def _field(label, container):
    for node in container.select("li"):
        text = _text(node) or ""
        if text.startswith(f"{label}："):
            return text.split("：", 1)[1].strip()
    return None


def _int_field(label, container):
    value = _field(label, container)
    if not value:
        return None
    match = re.search(r"\d+", value)
    return int(match.group(0)) if match else None


def parse_job_list(response):
    soup = BeautifulSoup(response.text, "html.parser")
    items = []
    for node in soup.select("div.detail_headline"):
        checkbox = node.select_one('input[name="checkbox2"]')
        link = node.select_one("div.career_name a.green")
        if checkbox is None or link is None:
            continue
        source_item_id = str(checkbox.get("value") or "").strip()
        href = link.get("href") or ""
        if not source_item_id or not href:
            continue
        company_link = node.select_one("div.corp_name a.green")
        items.append(
            {
                "source_item_id": source_item_id,
                "title": _text(link),
                "detail_url": urljoin(BASE_URL, href),
                "extra": {
                    "company_name": _text(company_link),
                    "company_url": (
                        urljoin(BASE_URL, company_link.get("href"))
                        if company_link and company_link.get("href")
                        else None
                    ),
                    "location_raw": _text(node.select_one("div.suozaidi")),
                    "listed_at": _text(node.select_one("div.shijian")),
                },
            }
        )
    return items


def parse_job_detail(response):
    soup = BeautifulSoup(response.text, "html.parser")
    container = soup.select_one("#project_L")
    source_item_id = None
    match = re.search(r"/jobs/(\d+)\.html", response.url)
    if match:
        source_item_id = match.group(1)
    title = _text(container.select_one("h2")) if container else None
    if title:
        title = title.removeprefix("招聘职位：").strip()
    company_link = (
        container.select_one("h1 a") if container is not None else None
    )
    body = (
        " ".join(_text(node) or "" for node in container.select("#brief_info p"))
        if container is not None
        else None
    )
    extra = {
        "company_name": _text(company_link),
        "company_url": (
            urljoin(BASE_URL, company_link.get("href"))
            if company_link and company_link.get("href")
            else None
        ),
        "location_raw": _field("工作地点", container),
        "validity_days": _int_field("有效时间", container),
        "employment_type": _field("招聘方式", container),
        "headcount": _int_field("招聘人数", container),
        "gender_requirement": _field("性别要求", container),
        "salary_raw": _field("承诺月薪", container),
        "published_at": _field("发布日期", container),
        "education_raw": _field("学历要求", container),
        "rights_risk": {
            "status": "attribution-required",
            "notice": "只采集公开岗位字段，不采集登录后联系方式。",
        },
    }
    return {
        "source_item_id": source_item_id,
        "title": title,
        "source_url": response.url,
        "long_term_url": response.url,
        "detail_url": response.url,
        "detail_url_status": "direct",
        "body_text": body,
        "extra": extra,
    }
