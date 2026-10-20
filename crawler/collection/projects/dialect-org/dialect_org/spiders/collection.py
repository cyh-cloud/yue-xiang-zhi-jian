import scrapy

from ..parsers import parse_dialect_detail, parse_dialect_list


class DialectOrgSpider(scrapy.Spider):
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
            )

    def parse_detail(self, response, list_item):
        parsed = parse_dialect_detail(response)
        parsed["point"]["extra"].update(list_item.get("extra", {}))
        yield parsed
