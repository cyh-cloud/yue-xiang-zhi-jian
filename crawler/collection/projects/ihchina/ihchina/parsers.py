"""Site-specific ihchina list and detail parsing."""

from __future__ import annotations

import json
import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup


BASE_URL = "https://www.ihchina.cn"


def _text(node):
    return node.get_text(" ", strip=True) if node else None


def _key_values(soup):
    values = {}
    for node in soup.select(".article-mod2 .table .p"):
        text = _text(node) or ""
        match = re.match(r"^([^:：]+)[:：]\s*(.*)$", text)
        if match:
            values[match.group(1).strip()] = match.group(2).strip()
    return values


def parse_list_page(response):
    payload = json.loads(response.text)
    page = int(payload.get("p") or 1)
    total_pages = int(
        (payload.get("links") or {}).get("total_pages")
        or payload.get("total_pages")
        or page
    )
    items = []
    for raw in payload.get("list") or []:
        source_item_id = str(raw.get("id") or "").strip()
        if not source_item_id:
            continue
        items.append(
            {
                "source_item_id": source_item_id,
                "title": raw.get("title"),
                "detail_url": (
                    f"{BASE_URL}/project_details/{source_item_id}.html"
                ),
                "extra": {
                    "ich_code": raw.get("num"),
                    "project_type": raw.get("cate"),
                    "declaration_region": raw.get("province"),
                },
            }
        )
    return {
        "items": items,
        "page": page,
        "total_pages": total_pages,
        "next_page": page + 1 if page < total_pages else None,
    }


def parse_project_detail(response):
    soup = BeautifulSoup(response.text, "html.parser")
    values = _key_values(soup)
    source_item_id = None
    path = urlparse(response.url).path
    if "/project_details/" in path:
        source_item_id = (
            path.split("/project_details/", 1)[1].split(".", 1)[0]
        )
    title = _text(soup.select_one(".article-mod2 .t_head .h30"))
    body_node = soup.select_one(".article-mod2 .text .p")
    detail_url = response.url
    return {
        "source_item_id": source_item_id,
        "title": title,
        "source_url": response.url,
        "long_term_url": detail_url,
        "detail_url": detail_url,
        "detail_url_status": "direct",
        "body_text": _text(body_node),
        "extra": {
            "project_serial": values.get("项目序号"),
            "ich_code": values.get("项目编号"),
            "announcement_batch": values.get("公布时间"),
            "category": values.get("类别"),
            "declaration_region": values.get("申报地区或单位"),
            "protection_unit": values.get("保护单位"),
            "project_type": values.get("类型"),
        },
    }
