import scrapy

from crawler.collection.shared.crawler_collection.items import (
    item_from_mapping,
)
from ..parsers import parse_article_detail, parse_article_list


class CassLinguisticsSpider(scrapy.Spider):
    name = "cass-linguistics"
    source_id = "cass-linguistics"
    run_id = "live"
    allowed_domains = ["ling.cass.cn"]
    start_urls = ["http://ling.cass.cn/news/bensuo/"]

    def parse(self, response):
        parsed = parse_article_list(response)
        for item in parsed["items"]:
            yield scrapy.Request(
                item["detail_url"],
                callback=self.parse_detail,
                cb_kwargs={"list_item": item},
            )
        if parsed["next_page"]:
            yield scrapy.Request(parsed["next_page"], callback=self.parse)

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
