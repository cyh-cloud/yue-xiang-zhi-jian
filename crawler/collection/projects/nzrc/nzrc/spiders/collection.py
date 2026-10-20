import scrapy

from crawler.collection.shared.crawler_collection.items import (
    item_from_mapping,
)
from ..parsers import parse_job_detail, parse_job_list


class NzrcSpider(scrapy.Spider):
    name = "nzrc"
    source_id = "nzrc"
    run_id = "live"
    allowed_domains = ["www.nzrc.com.cn"]
    start_urls = ["http://www.nzrc.com.cn/career_seek.html"]

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
