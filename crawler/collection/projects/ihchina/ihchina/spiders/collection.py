import scrapy

from crawler.collection.shared.crawler_collection.items import (
    item_from_mapping,
)
from crawler.collection.shared.crawler_collection.spiders import (
    CollectionSpiderMixin,
)
from ..parsers import parse_list_page, parse_project_detail


class IhchinaSpider(CollectionSpiderMixin, scrapy.Spider):
    name = "ihchina"
    source_id = "ihchina"
    allowed_domains = ["www.ihchina.cn"]
    start_urls = [
        "https://www.ihchina.cn/getProject.html?"
        "category_id=16&limit=10&p=1"
    ]

    def parse(self, response):
        parsed = parse_list_page(response)
        for item in parsed["items"]:
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
        if parsed["next_page"] is not None:
            next_url = (
                "https://www.ihchina.cn/getProject.html?"
                f"category_id=16&limit=10&p={parsed['next_page']}"
            )
            yield scrapy.Request(next_url, callback=self.parse)

    def parse_detail(self, response, list_item):
        parsed = parse_project_detail(response)
        parsed["extra"] = {
            **list_item.get("extra", {}),
            **parsed.get("extra", {}),
        }
        yield item_from_mapping(
            parsed, source_id=self.source_id, response=response,
            list_item=list_item,
        )
