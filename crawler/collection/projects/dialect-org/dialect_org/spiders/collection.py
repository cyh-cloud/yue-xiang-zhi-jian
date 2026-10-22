import scrapy

from crawler.collection.shared.crawler_collection.items import (
    item_from_mapping,
)
from crawler.collection.shared.crawler_collection.spiders import (
    CollectionSpiderMixin,
)
from ..parsers import parse_dialect_detail, parse_dialect_list


class DialectOrgSpider(CollectionSpiderMixin, scrapy.Spider):
    name = "dialect-org"
    source_id = "dialect-org"
    allowed_domains = ["dialect.org.cn"]
    start_urls = ["https://dialect.org.cn/"]

    def parse(self, response):
        for item in parse_dialect_list(response):
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
        parsed = parse_dialect_detail(response)
        parsed["point"]["extra"].update(list_item.get("extra", {}))
        parsed["point"]["extra"]["lexeme"] = parsed["lexeme"]
        yield item_from_mapping(
            parsed["point"], source_id=self.source_id, response=response,
            list_item=list_item,
        )
