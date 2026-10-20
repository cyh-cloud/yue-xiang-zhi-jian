import scrapy


class CnipaSpider(scrapy.Spider):
    name = "cnipa"
    source_id = "cnipa"
    allowed_domains = []
    start_urls = []
    live_enabled = False

    def parse(self, response):
        return iter(())
