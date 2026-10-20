"""Shared Pipeline boundary: raw, stage, and crawler-DB candidates only."""

from __future__ import annotations

from .database import CollectionDatabase
from .items import validate_item


class CollectionPipeline:
    def __init__(self, database_path):
        self.database = CollectionDatabase(database_path)

    def process_item(self, item, spider):
        validate_item(item)
        return item
