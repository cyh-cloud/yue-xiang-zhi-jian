"""Site-specific feiyiw article parsing."""

from __future__ import annotations

from urllib.parse import urljoin

from crawler.pipeline.sources.feiyiw import (
    parse_article_detail as _parse_detail,
    parse_article_list as _parse_list,
)


BASE_URL = "https://www.feiyiw.cn/"


def parse_article_list(response):
    parsed = _parse_list(response.text, response.url)
    for item in parsed["items"]:
        item["source_url"] = response.url
        item["long_term_url"] = urljoin(
            BASE_URL,
            f"index.php?app=article&act=view&article_id={item['source_item_id']}",
        )
        item["detail_url"] = item["long_term_url"]
        item["detail_url_status"] = "direct"
        item["published_at"] = item.pop("list_date", None)
    parsed["source_url"] = response.url
    parsed["long_term_url"] = response.url
    return parsed


def parse_article_detail(response):
    item = _parse_detail(response.text, response.url)
    item.pop("publish_status", None)
    item.pop("source_id", None)
    item.pop("article_id", None)
    item.pop("category_name", None)
    return item
