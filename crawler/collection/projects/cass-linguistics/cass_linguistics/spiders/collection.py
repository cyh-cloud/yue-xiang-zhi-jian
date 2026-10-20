import scrapy

from ..parsers import parse_article_detail, parse_article_list


class CassLinguisticsSpider(scrapy.Spider):
    name = "cass-linguistics"
    source_id = "cass-linguistics"
    allowed_domains = ["ling.cass.cn"]
    start_urls = ["http://ling.cass.cn/news/bensuo/"]

    def parse(self, response):
        for item in parse_article_list(response):
            yield scrapy.Request(
                item["detail_url"],
                callback=self.parse_detail,
                cb_kwargs={"list_item": item},
            )

    def parse_detail(self, response, list_item):
        item = parse_article_detail(response)
        item["extra"] = {
            **list_item,
            **item.get("extra", {}),
        }
        yield item
