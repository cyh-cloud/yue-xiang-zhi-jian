import scrapy


class AqscMoaSpider(scrapy.Spider):
    name = "aqsc-moa"
    source_id = "aqsc-moa"
    allowed_domains = []
    start_urls = []
    live_enabled = False

    def parse(self, response):
        return iter(())
