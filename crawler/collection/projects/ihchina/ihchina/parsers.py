"""Site-specific ihchina list and detail parsing."""

from __future__ import annotations

import json
import re
from urllib.parse import urljoin, urlparse

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


def _detail_id(url, marker):
    match = re.search(rf"/{re.escape(marker)}/(\d+)(?:\.html)?", url or "")
    return match.group(1) if match else None


def _table_rows(container):
    table = container.select_one("table")
    if table is None:
        return []
    return table.select("tr")[1:]


def _inheritors(soup, source_url):
    containers = soup.select(".inherit_xx2 .x-tables")
    if not containers:
        return []
    inheritors = []
    for row in _table_rows(containers[0]):
        cells = row.select("td")
        if len(cells) < 2:
            continue
        link = row.select_one("a[href*='/ccr_detail/']")
        href = urljoin(source_url, link["href"]) if link else None
        name = _text(link) or _text(cells[1])
        if not name:
            continue
        inheritors.append(
            {
                "source_item_id": _detail_id(href, "ccr_detail"),
                "name": name,
                "gender": _text(cells[2]) if len(cells) > 2 else None,
                "birth_date": _text(cells[3]) if len(cells) > 3 else None,
                "ethnicity": _text(cells[4]) if len(cells) > 4 else None,
                "category": _text(cells[5]) if len(cells) > 5 else None,
                "ich_code": _text(cells[6]) if len(cells) > 6 else None,
                "project_name": _text(cells[7]) if len(cells) > 7 else None,
                "declaration_region": (
                    _text(cells[8]) if len(cells) > 8 else None
                ),
                "source_url": href,
            }
        )
    return inheritors


def _related_projects(soup, source_url):
    containers = soup.select(".inherit_xx2 .x-tables")
    if len(containers) < 2:
        return []
    related = []
    for row in _table_rows(containers[1]):
        cells = row.select("td")
        if len(cells) < 2:
            continue
        link = row.select_one("a[href*='/project_details/']")
        href = urljoin(source_url, link["href"]) if link else None
        name = _text(link) or _text(cells[1])
        if not name:
            continue
        related.append(
            {
                "source_item_id": _detail_id(href, "project_details"),
                "ich_code": _text(cells[0]),
                "name": name,
                "category": _text(cells[2]) if len(cells) > 2 else None,
                "declaration_region": (
                    _text(cells[3]) if len(cells) > 3 else None
                ),
                "source_url": href,
            }
        )
    return related


def _media_links(description_node, source_url):
    if description_node is None:
        return []
    links = []
    seen = set()
    media_types = {
        "img": "image",
        "video": "video",
        "audio": "audio",
        "iframe": "iframe",
    }
    for node in description_node.select(
        "img[src], video[src], audio[src], source[src], iframe[src], "
        "[data-src]"
    ):
        raw = node.get("src") or node.get("data-src")
        if not raw or raw in {"N;", "N"}:
            continue
        media_url = urljoin(source_url, raw)
        if media_url in seen:
            continue
        seen.add(media_url)
        media_type = media_types.get(node.name, node.name)
        if node.name == "source" and node.parent is not None:
            media_type = media_types.get(node.parent.name, node.parent.name)
        links.append(
            {
                "media_url": media_url,
                "media_type": media_type,
            }
        )
    return links


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
            "inheritors": _inheritors(soup, response.url),
            "related_projects": _related_projects(soup, response.url),
            "media_links": _media_links(body_node, response.url),
        },
    }
