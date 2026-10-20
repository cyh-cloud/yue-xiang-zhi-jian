import scrapy

from crawler.collection.shared.crawler_collection.items import (
    item_from_mapping,
)
from ..parsers import parse_job_detail, parse_job_list


class NongmuhrSpider(scrapy.Spider):
    name = "nongmuhr"
    source_id = "nongmuhr"
    run_id = "live"
    allowed_domains = ["nongmuhr.com"]
    start_urls = ["http://nongmuhr.com/Employ.aspx"]

    def parse(self, response):
        for item in parse_job_list(response):
            yield scrapy.Request(
                item["detail_url"],
                callback=self.parse_detail,
                cb_kwargs={"list_item": item},
            )

    def parse_detail(self, response, list_item):
        item = parse_job_detail(response)
        item["extra"] = {
            **list_item.get("extra", {}),
            **item.get("extra", {}),
        }
        yield item_from_mapping(
            item, source_id=self.source_id, response=response,
            list_item=list_item,
        )
