import scrapy

from crawler.collection.shared.crawler_collection.items import (
    item_from_mapping,
)
from ..parsers import parse_dialect_detail, parse_dialect_list


class DialectOrgSpider(scrapy.Spider):
    name = "dialect-org"
    source_id = "dialect-org"
    run_id = "live"
    allowed_domains = ["dialect.org.cn"]
    start_urls = ["https://dialect.org.cn/"]

    def parse(self, response):
        for item in parse_dialect_list(response):
            yield scrapy.Request(
                item["detail_url"],
                callback=self.parse_detail,
                cb_kwargs={"list_item": item},
            )

    def parse_detail(self, response, list_item):
        parsed = parse_dialect_detail(response)
        parsed["point"]["extra"].update(list_item.get("extra", {}))
        yield item_from_mapping(
            parsed["point"], source_id=self.source_id, response=response,
            list_item=list_item,
        )
