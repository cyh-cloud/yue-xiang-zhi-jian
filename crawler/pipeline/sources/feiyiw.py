import re
from urllib.parse import parse_qs, urljoin, urlparse

from .. import source_registry


SOURCE_ID = "feiyiw"
DETAIL_URL_PREFIX = "https://www.feiyiw.cn/index.php?app=article&act=view&article_id="
LIST_URL = "https://www.feiyiw.cn/index.php?app=article&cate_id=4"


def article_id_from_url(url):
    values = parse_qs(urlparse(url).query).get("article_id")
    return values[0] if values and values[0].isdigit() else None


def _is_public_article_url(url):
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    app = (query.get("app") or [""])[0].lower()
    act = (query.get("act") or [""])[0].lower()
    path = (parsed.path or "").lower()
    blocked_values = {
        "member",
        "shop",
        "login",
        "logout",
        "order",
        "purchase",
        "buy",
    }
    if app in blocked_values or act in blocked_values:
        return False
    return not any(
        marker in path
        for marker in ("/login", "/member", "/order", "/purchase", "/shop")
    )


def _text(node):
    return node.get_text(" ", strip=True) if node else None


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


def parse_article_detail(html, fetched_url, rights=None):
    from bs4 import BeautifulSoup

    rights = rights or source_registry.rights_fields(
        source_registry.load_registry()[SOURCE_ID]
    )
    rights_risk = {
        "status": rights["rights_status"],
        "notice": "站方版权保留且供稿权属不保证；只作补充资讯，不默认拥有全文再发布权。",
    }
    if not _is_public_article_url(fetched_url):
        raise ValueError("feiyiw URL is not a public article detail")
    soup = BeautifulSoup(html, "html.parser")
    title = _text(soup.select_one(".article-info h1"))
    published_at = _text(soup.select_one(".article-info h2"))
    category_name = _text(
        soup.select_one("#page-article div.col-main > div.title .location")
    )
    body = soup.select_one(".article-detail")
    body_text = _text(body)
    labelled = _labelled_values(body_text)
    article_id = article_id_from_url(fetched_url)
    if not article_id:
        raise ValueError("feiyiw detail URL has no article_id")
    if not title or not body_text:
        raise ValueError("feiyiw page is not a public article detail")
    canonical = f"{DETAIL_URL_PREFIX}{article_id}"
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
        "source_id": SOURCE_ID,
        "source_item_id": article_id,
        "article_id": article_id,
        "title": title,
        "published_at": published_at,
        "category_name": category_name,
        "body_text": body_text,
        "source_url": fetched_url,
        "long_term_url": canonical,
        "detail_url": canonical,
        "detail_url_status": "direct",
        "publish_status": "draft",
        **rights,
        "extra": {
            "supplementary": {
                key: value for key, value in supplementary.items() if value is not None
            },
            "rights_risk": rights_risk,
        },
    }


def parse_article_list(html, fetched_url, rights=None):
    from bs4 import BeautifulSoup

    rights = rights or source_registry.rights_fields(
        source_registry.load_registry()[SOURCE_ID]
    )
    rights_risk = {
        "status": rights["rights_status"],
        "notice": "站方版权保留且供稿权属不保证。",
    }
    soup = BeautifulSoup(html, "html.parser")
    items = []
    seen = set()
    list_nodes = soup.select("#page-article div.col-main ul.content > li")
    for node in list_nodes:
        link = node.select_one("a.lebioa[href]")
        if not link:
            continue
        detail_url = urljoin(fetched_url, link["href"])
        if not _is_public_article_url(detail_url):
            continue
        article_id = article_id_from_url(detail_url)
        if not article_id or article_id in seen:
            continue
        seen.add(article_id)
        date_node = node.select_one("span")
        items.append(
            {
                "source_id": SOURCE_ID,
                "source_item_id": article_id,
                "article_id": article_id,
                "title": _text(link),
                "list_date": _text(date_node),
                "source_url": fetched_url,
                "long_term_url": f"{DETAIL_URL_PREFIX}{article_id}",
                "detail_url": f"{DETAIL_URL_PREFIX}{article_id}",
                "detail_url_status": "direct",
                "publish_status": "draft",
                **rights,
                "extra": {"rights_risk": rights_risk},
            }
        )
    total = _text(soup.select_one(".page .total"))
    match = re.search(r"(\d+)", total or "")
    next_link = soup.select_one(".page .items a.item.next[href]")
    return {
        "source_id": SOURCE_ID,
        "list_url": fetched_url,
        "page_count": int(match.group(1)) if match else None,
        "next_page": urljoin(fetched_url, next_link["href"]) if next_link else None,
        "items": items,
    }
