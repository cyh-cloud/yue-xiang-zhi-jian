import hashlib

import scrapy

from crawler.collection.shared.crawler_collection.items import (
    item_from_mapping,
)
from crawler.collection.shared.crawler_collection.spiders import (
    CollectionSpiderMixin,
)
from ..parsers import (
    default_max_pages,
    list_page_url,
    page_count,
    parse_job_detail,
    parse_job_list,
    unique_items,
)


class NongmuhrSpider(CollectionSpiderMixin, scrapy.Spider):
    name = "nongmuhr"
    source_id = "nongmuhr"
    allowed_domains = ["nongmuhr.com"]
    start_urls = ["http://nongmuhr.com/Employ.aspx"]

    def __init__(self, max_pages=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_pages = page_count(
            int(max_pages) if max_pages is not None else default_max_pages()
        )
        self._seen_items = set()

    def start_requests(self):
        for page in range(self.max_pages):
            yield scrapy.Request(
                list_page_url(page),
                callback=self.parse,
                dont_filter=page > 0,
                meta={"page": page},
            )

    def parse(self, response):
        try:
            items = parse_job_list(response)
        except Exception as exc:
            self.logger.exception("nongmuhr list parsing failed")
            yield self._blocked_item(
                response,
                "parse:job_list",
                exc,
                source_item_id=self._blocked_id(response.url),
                locator=f"list={response.url}",
            )
            return
        for item in unique_items(items, self._seen_items):
            yield scrapy.Request(
                item["detail_url"],
                callback=self.parse_detail,
                cb_kwargs={"list_item": item},
                meta={
                    "detail_url": item["detail_url"],
                    "source_url": item.get("source_url") or response.url,
                    "long_term_url": (
                        item.get("long_term_url") or item["detail_url"]
                    ),
                    "locator": item.get("locator") or item["detail_url"],
                },
            )

    def parse_detail(self, response, list_item):
        try:
            item = parse_job_detail(
                response,
                list_extra=list_item.get("extra"),
            )
        except Exception as exc:
            self.logger.exception(
                "nongmuhr detail parsing failed: %s", response.url
            )
            yield self._blocked_item(
                response,
                "parse:job_detail",
                exc,
                source_item_id=(
                    list_item.get("source_item_id")
                    or self._blocked_id(response.url)
                ),
                title=list_item.get("title"),
                locator=(
                    list_item.get("locator")
                    or f"detail={response.url}"
                ),
            )
            return
        item["extra"] = {
            **list_item.get("extra", {}),
            **item.get("extra", {}),
        }
        yield item_from_mapping(
            item, source_id=self.source_id, response=response,
            list_item=list_item,
        )

    @staticmethod
    def _blocked_id(url):
        digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:12]
        return f"blocked:{digest}"

    def _blocked_item(
        self,
        response,
        reason,
        error,
        *,
        source_item_id,
        title=None,
        locator=None,
    ):
        detail_url = response.meta.get("detail_url") or response.url
        long_term_url = response.meta.get("long_term_url") or detail_url
        payload = {
            "source_item_id": source_item_id,
            "title": (
                title
                or response.css("title::text").get()
                or response.url
            ),
            "source_url": response.url,
            "long_term_url": long_term_url,
            "detail_url": detail_url,
            "detail_url_status": "direct",
            "fetch_url": response.url,
            "locator": locator or f"detail={response.url}",
            "candidate_status": "blocked",
            "candidate_reason": (
                f"{reason}:{type(error).__name__}:{error}"
            ),
            "mode": response.meta.get("mode", "live"),
            "extra": {
                "failure_url": response.url,
                "error_type": type(error).__name__,
                "error_message": str(error),
                "release_condition": (
                    "the job detail page must match the current table "
                    "structure"
                ),
            },
        }
        return item_from_mapping(
            payload,
            source_id=self.source_id,
            response=response,
        )
