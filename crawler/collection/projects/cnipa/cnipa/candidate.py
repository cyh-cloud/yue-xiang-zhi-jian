"""cnipa candidate field mapping."""

from crawler.collection.shared.crawler_collection.candidate import (
    upsert_candidate,
)


FIELDS = (
    "cert_type",
    "product_name",
    "product_name_raw",
    "normalized_name",
    "category",
    "is_aquatic",
    "province",
    "city",
    "county",
    "region",
    "origin_scope",
    "applicant",
    "protection_unit",
    "certificate_no",
    "certified_at",
)


def write_candidate(conn, item, *, now):
    extra = item["extra"]
    product_name = extra.get("product_name") or item["title"]
    upsert_candidate(
        conn,
        item,
        table="std_agri_products",
        fields=FIELDS,
        values=(
            extra.get("cert_type") or "公告",
            product_name,
            extra.get("product_name_raw") or product_name,
            extra.get("normalized_name") or product_name,
            extra.get("category"),
            extra.get("is_aquatic"),
            extra.get("province"),
            extra.get("city"),
            extra.get("county"),
            extra.get("region"),
            extra.get("origin_scope"),
            extra.get("applicant"),
            extra.get("protection_unit"),
            extra.get("certificate_no"),
            extra.get("certified_at"),
        ),
        now=now,
    )
