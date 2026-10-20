"""cass-linguistics candidate field mapping."""

from crawler.collection.shared.crawler_collection.candidate import (
    upsert_candidate,
)


FIELDS = ("title", "summary", "published_at", "body_text", "body_access")


def write_candidate(conn, item, *, now):
    extra = item["extra"]
    upsert_candidate(
        conn,
        item,
        table="std_research_articles",
        fields=FIELDS,
        values=(
            item["title"],
            extra.get("summary"),
            extra.get("published_at"),
            item.get("body_text"),
            extra.get("body_access") or "public",
        ),
        now=now,
    )
