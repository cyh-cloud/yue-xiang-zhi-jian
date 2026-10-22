import scrapy

from crawler.collection.shared.crawler_collection.items import (
    item_from_mapping,
)
from crawler.collection.shared.crawler_collection.spiders import (
    CollectionSpiderMixin,
)
from ..parsers import (
    default_max_pages,
    page_count,
    pagination_form,
    parse_job_detail,
    parse_job_list,
    unique_items,
)


class NzrcSpider(CollectionSpiderMixin, scrapy.Spider):
    name = "nzrc"
    source_id = "nzrc"
    allowed_domains = ["www.nzrc.com.cn"]
    start_urls = ["http://www.nzrc.com.cn/career_seek.html"]

    def __init__(self, max_pages=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_pages = page_count(
            int(max_pages) if max_pages is not None else default_max_pages()
        )
        self._seen_items = set()

    def parse(self, response):
        items = parse_job_list(response)
        for item in unique_items(items, self._seen_items):
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
        page = int(response.meta.get("page", 1))
        if page < self.max_pages:
            action, payload = pagination_form(response, page + 1)
            yield scrapy.FormRequest(
                action,
                formdata=payload,
                callback=self.parse,
                dont_filter=True,
                meta={"page": page + 1},
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
