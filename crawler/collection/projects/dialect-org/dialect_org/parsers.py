"""Site-specific dialect.org.cn list and detail parsing."""

from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from crawler.pipeline.sources.dialect_org import parse_detail


BASE_URL = "https://dialect.org.cn"


def _source_item_id(url):
    match = re.search(r"/dialect/([^/?#]+)", urlparse(url).path)
    return match.group(1) if match else None


def parse_dialect_list(response):
    soup = BeautifulSoup(response.text, "html.parser")
    items = []
    seen = set()
    for link in soup.select('a[href*="/dialect/"]'):
        url = urljoin(BASE_URL, link.get("href"))
        source_item_id = _source_item_id(url)
        if not source_item_id or source_item_id in seen:
            continue
        seen.add(source_item_id)
        items.append(
            {
                "source_item_id": source_item_id,
                "title": link.get_text(" ", strip=True),
                "detail_url": url,
            }
        )
    return items


def parse_dialect_detail(response):
    parsed = parse_detail(
        _source_item_id(response.url),
        response.text,
        {
            "rights_status": "attribution-required",
            "attribution_required": True,
            "attribution_text": "中国方言库",
            "rights_evidence_url": "https://dialect.org.cn/",
        },
    )
    parsed["point"]["source_url"] = response.url
    parsed["point"]["long_term_url"] = response.url
    parsed["point"]["detail_url"] = response.url
    parsed["lexeme"]["source_url"] = response.url
    parsed["lexeme"]["long_term_url"] = response.url
    parsed["lexeme"]["detail_url"] = response.url
    return parsed
