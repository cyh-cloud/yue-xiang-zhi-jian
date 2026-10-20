"""Site-specific feiyiw list and detail parsing."""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urljoin, urlparse

from bs4 import BeautifulSoup


BASE_URL = "https://www.feiyiw.cn/"
DETAIL_URL_PREFIX = (
    "https://www.feiyiw.cn/index.php?app=article&act=view&article_id="
)


def _text(node):
    return node.get_text(" ", strip=True) if node else None


def _is_public_article_url(url):
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    app = (query.get("app") or [""])[0].lower()
    act = (query.get("act") or [""])[0].lower()
    path = (parsed.path or "").lower()
    blocked = {"member", "shop", "login", "logout", "order", "purchase", "buy"}
    if app in blocked or act in blocked:
        return False
    return not any(
        marker in path
        for marker in ("/login", "/member", "/order", "/purchase", "/shop")
    )


def _article_id(url):
    values = parse_qs(urlparse(url).query).get("article_id")
    return values[0] if values and values[0].isdigit() else None


def _labelled_values(text):
    values = {}
    for label in (
        "项目名称",
        "项目类别",
        "项目地区",
        "项目级别",
        "项目保护单位",
        "项目批准时间",
        "传承人简介",
    ):
        match = re.search(
            rf"【{label}】\s*(.*?)(?=\s*【[^】]+】|\Z)",
            text or "",
            flags=re.S,
        )
        if match:
            values[label] = match.group(1).strip()
    return values


def parse_article_list(response):
    soup = BeautifulSoup(response.text, "html.parser")
    items = []
    seen = set()
    for node in soup.select("#page-article div.col-main ul.content > li"):
        link = node.select_one("a.lebioa[href]")
        if link is None:
            continue
        detail_url = urljoin(response.url, link["href"])
        if not _is_public_article_url(detail_url):
            continue
        article_id = _article_id(detail_url)
        if not article_id or article_id in seen:
            continue
        seen.add(article_id)
        canonical = f"{DETAIL_URL_PREFIX}{article_id}"
        items.append(
            {
                "source_id": "feiyiw",
                "source_item_id": article_id,
                "title": _text(link),
                "published_at": _text(node.select_one("span")),
                "source_url": response.url,
                "long_term_url": canonical,
                "detail_url": canonical,
                "detail_url_status": "direct",
            }
        )
    total = _text(soup.select_one(".page .total"))
    match = re.search(r"(\d+)", total or "")
    next_link = soup.select_one(".page .items a.item.next[href]")
    return {
        "items": items,
        "page_count": int(match.group(1)) if match else None,
        "next_page": (
            urljoin(response.url, next_link["href"])
            if next_link is not None
            else None
        ),
    }


def parse_article_detail(response):
    soup = BeautifulSoup(response.text, "html.parser")
    title = _text(soup.select_one(".article-info h1"))
    published_at = _text(soup.select_one(".article-info h2"))
    body = soup.select_one(".article-detail")
    body_text = _text(body)
    article_id = _article_id(response.url)
    if not article_id:
        raise ValueError("feiyiw detail URL has no article_id")
    if not title or not body_text:
        raise ValueError("feiyiw page is not a public article detail")
    canonical = f"{DETAIL_URL_PREFIX}{article_id}"
    labelled = _labelled_values(body_text)
    supplementary = {
        "project_name": labelled.get("项目名称"),
        "ich_category": labelled.get("项目类别"),
        "region_text": labelled.get("项目地区"),
        "level_text": labelled.get("项目级别"),
        "protection_unit": labelled.get("项目保护单位"),
        "approval_text": labelled.get("项目批准时间"),
        "inheritor_text": labelled.get("传承人简介"),
    }
    return {
        "source_id": "feiyiw",
        "source_item_id": article_id,
        "title": title,
        "published_at": published_at,
        "body_text": body_text,
        "source_url": response.url,
        "long_term_url": canonical,
        "detail_url": canonical,
        "detail_url_status": "direct",
        "extra": {
            "supplementary": {
                key: value
                for key, value in supplementary.items()
                if value is not None
            },
            "rights_risk": {
                "status": "attribution-required",
                "notice": "站方版权保留且供稿权属不保证；只作补充资讯，不默认拥有全文再发布权。",
            },
        },
    }
