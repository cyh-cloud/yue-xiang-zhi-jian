"""feiyiw candidate field mapping."""

from crawler.collection.shared.crawler_collection.candidate import (
    upsert_candidate,
)


FIELDS = ("title", "published_at", "body_text")


def write_candidate(conn, item, *, now):
    extra = item["extra"]
    upsert_candidate(
        conn,
        item,
        table="std_ich_articles",
        fields=FIELDS,
        values=(
            item["title"],
            item.get("published_at") or extra.get("published_at"),
            item.get("body_text"),
        ),
        now=now,
    )
