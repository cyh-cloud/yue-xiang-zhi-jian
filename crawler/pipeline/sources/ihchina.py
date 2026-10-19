"""IHChina project and inheritor detail parsing."""

from __future__ import annotations

import re
from urllib.parse import urljoin


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


def _related_articles(soup, source_url):
    articles = []
    for section in soup.select(".inherit_xx2 .list"):
        section_text = _text(section.select_one(".title")) or _text(section) or ""
        relation_type = (
            "相关学术" if "学术" in section_text else "相关资讯"
        )
        for link in section.select("a.list-link[href]"):
            href = urljoin(source_url, link["href"])
            articles.append(
                {
                    "relation_type": relation_type,
                    "published_date": _text(link.select_one(".date")),
                    "title": _text(link.select_one(".p")),
                    "source_url": href,
                }
            )
    return articles


def _media_links(description_node, source_url):
    if description_node is None:
        return []
    links = []
    seen = set()
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
        links.append(
            {
                "media_url": media_url,
                "media_type": node.name,
            }
        )
    return links


def parse_project_detail(html, source_url):
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    values = _key_values(soup)
    title = _text(soup.select_one(".article-mod2 .t_head .h30"))
    description_node = soup.select_one(".article-mod2 .text .p")
    description_html = (
        description_node.decode_contents().strip()
        if description_node is not None
        else None
    )
    return {
        "title": title,
        "project_serial": values.get("项目序号"),
        "ich_code": values.get("项目编号"),
        "announcement_batch": values.get("公布时间"),
        "category": values.get("类别"),
        "province": values.get("所属地区"),
        "project_type": values.get("类型"),
        "declaration_region": values.get("申报地区或单位"),
        "protection_unit": values.get("保护单位"),
        "description_html": description_html,
        "description_text": _text(description_node),
        "inheritors": _inheritors(soup, source_url),
        "related_projects": _related_projects(soup, source_url),
        "related_articles": _related_articles(soup, source_url),
        "media_links": _media_links(description_node, source_url),
    }


def parse_inheritor_detail(html, source_url):
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    values = _key_values(soup)
    biography_node = soup.select_one(".article-mod2 .text .p")
    return {
        "name": _text(soup.select_one(".article-mod2 .t_head .h30")),
        "gender": values.get("性别"),
        "birth_date": values.get("出生日期"),
        "ethnicity": values.get("民族"),
        "category": values.get("类别"),
        "ich_code": values.get("项目编号"),
        "project_name": values.get("项目名称"),
        "declaration_region": values.get("申报地区或单位"),
        "biography_text": _text(biography_node),
        "source_url": source_url,
    }
