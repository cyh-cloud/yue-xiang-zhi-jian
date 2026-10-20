"""Common Spider lifecycle helpers."""

from __future__ import annotations

from .run_id import new_run_id


class CollectionSpiderMixin:
    run_id = None

    def open_spider(self, spider=None):
        self.run_id = new_run_id(self.source_id)
