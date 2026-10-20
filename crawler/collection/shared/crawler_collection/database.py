"""Crawler database writer boundary. Business database modules are forbidden."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .schema import ensure_schema


FORBIDDEN_IMPORT_PREFIXES = (
    "backend",
    "crawler.pipeline.converter",
    "crawler.pipeline.database",
)


class CollectionDatabase:
    def __init__(self, path):
        self.path = Path(path)

    def connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path)
        conn.execute("PRAGMA foreign_keys = ON")
        ensure_schema(conn)
        return conn
