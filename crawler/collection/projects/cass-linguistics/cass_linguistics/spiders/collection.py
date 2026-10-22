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
    parse_article_detail,
    parse_article_list,
    unique_items,
)


class CassLinguisticsSpider(CollectionSpiderMixin, scrapy.Spider):
    name = "cass-linguistics"
    source_id = "cass-linguistics"
    allowed_domains = ["ling.cass.cn"]
    start_urls = ["http://ling.cass.cn/news/bensuo/"]

    def __init__(self, max_pages=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_pages = min(
            page_count(
                int(max_pages)
                if max_pages is not None
                else default_max_pages()
            ),
            default_max_pages(),
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
        parsed = parse_article_list(response)
        for item in unique_items(parsed["items"], self._seen_items):
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
        item = parse_article_detail(response)
        item["extra"] = {
            **list_item,
            **item.get("extra", {}),
        }
        yield item_from_mapping(
            item, source_id=self.source_id, response=response,
            list_item=list_item,
        )
