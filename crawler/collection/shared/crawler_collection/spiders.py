"""Common Spider lifecycle helpers."""

from __future__ import annotations

from scrapy import signals

from .run_id import new_run_id


class CollectionSpiderMixin:
    run_id = None

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super().from_crawler(crawler, *args, **kwargs)
        if not spider.run_id:
            spider.run_id = new_run_id(spider.source_id)
        crawler.signals.connect(
            spider._collection_spider_opened,
            signal=signals.spider_opened,
        )
        return spider

    def _collection_spider_opened(self, spider):
        if not self.run_id:
            self.run_id = new_run_id(self.source_id)
