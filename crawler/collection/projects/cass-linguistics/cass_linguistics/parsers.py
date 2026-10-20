"""Site-specific CASS public article parsing."""

from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup


BASE_URL = "http://ling.cass.cn/"


def _text(node):
    return node.get_text(" ", strip=True) if node else None


def parse_article_list(response):
    soup = BeautifulSoup(response.text, "html.parser")
    items = []
    seen = set()
    for row in soup.select(".li_pgUl"):
        link = row.select_one(".li_bqListRight a[href]")
        if link is None:
            continue
        url = urljoin(BASE_URL, link.get("href"))
        match = re.search(r"t(\d{8})_(\d+)\.html", url)
        source_item_id = match.group(2) if match else None
        if not source_item_id or source_item_id in seen:
            continue
        seen.add(source_item_id)
        items.append(
            {
                "source_item_id": source_item_id,
                "title": _text(row.select_one(".li_bqListRight h2")),
                "summary": _text(row.select_one(".li_bqListRight p")),
                "published_at": (
                    match.group(1)
                    if match and len(match.group(1)) == 8
                    else None
                ),
                "detail_url": url,
            }
        )
    next_link = soup.select_one("a.next[href], .page a.next[href]")
    return {
        "items": items,
        "next_page": (
            urljoin(BASE_URL, next_link.get("href"))
            if next_link is not None
            else None
        ),
    }


def parse_article_detail(response):
    soup = BeautifulSoup(response.text, "html.parser")
    body = soup.select_one(".TRS_Editor")
    text = soup.get_text(" ", strip=True)
    title = None
    heading = (
        soup.select_one(".article-title")
        or soup.select_one("h1")
        or soup.select_one("title")
    )
    if heading is not None:
        title = _text(heading)
    if not title:
        for name in ("h2", "h3"):
            node = soup.select_one(name)
            if node is not None:
                title = _text(node)
                break
    source_match = re.search(r"来源[:：]\s*([^\s]+)", text)
    date_match = re.search(r"时间[:：]\s*(\d{4}-\d{2}-\d{2})", text)
    match = re.search(r"t(\d{8})_(\d+)\.html", response.url)
    return {
        "source_item_id": match.group(2) if match else None,
        "title": title,
        "source_url": response.url,
        "long_term_url": response.url,
        "detail_url": response.url,
        "detail_url_status": "direct",
        "body_text": _text(body),
        "body_access": "public",
        "extra": {
            "media": source_match.group(1) if source_match else None,
            "published_at": (
                date_match.group(1) if date_match else None
            ),
        },
    }
