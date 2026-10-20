"""ihchina candidate field mapping."""

from crawler.collection.shared.crawler_collection.candidate import (
    upsert_candidate,
)


FIELDS = (
    "ich_code",
    "name",
    "project_serial",
    "source_project_num",
    "category",
    "project_type",
    "announcement_batch",
    "announcement_year",
    "declaration_region",
    "protection_unit",
    "province",
    "city",
    "county",
    "description_html",
    "description_text",
    "source_modified_at",
)


def write_candidate(conn, item, *, now):
    extra = item["extra"]
    upsert_candidate(
        conn,
        item,
        table="std_ich_projects",
        fields=FIELDS,
        values=(
            extra.get("ich_code"),
            item["title"],
            extra.get("project_serial"),
            extra.get("source_project_num"),
            extra.get("category"),
            extra.get("project_type"),
            extra.get("announcement_batch"),
            extra.get("announcement_year"),
            extra.get("declaration_region"),
            extra.get("protection_unit"),
            extra.get("province"),
            extra.get("city"),
            extra.get("county"),
            extra.get("description_html"),
            item.get("body_text"),
            extra.get("source_modified_at"),
        ),
        now=now,
    )
