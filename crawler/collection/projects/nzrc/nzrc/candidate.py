"""nzrc candidate field mapping."""

from crawler.collection.shared.crawler_collection.candidate import (
    upsert_candidate,
)


FIELDS = (
    "title",
    "title_raw",
    "company_name",
    "company_url",
    "company_industry",
    "company_size",
    "company_nature",
    "location_raw",
    "province",
    "city",
    "employment_type",
    "headcount",
    "salary_raw",
    "education_raw",
    "experience_raw",
    "gender_requirement",
    "age_requirement",
    "major_requirement",
    "description",
    "requirements",
    "published_at",
    "deadline_at",
    "validity_days",
    "status_text",
)


def write_candidate(conn, item, *, now):
    extra = item["extra"]
    upsert_candidate(
        conn,
        item,
        table="std_jobs",
        fields=FIELDS,
        values=(
            item["title"],
            item["title"],
            extra.get("company_name"),
            extra.get("company_url"),
            extra.get("company_industry"),
            extra.get("company_size"),
            extra.get("company_nature"),
            extra.get("location_raw"),
            extra.get("province"),
            extra.get("city"),
            extra.get("employment_type"),
            extra.get("headcount"),
            extra.get("salary_raw"),
            extra.get("education_raw"),
            extra.get("experience_raw"),
            extra.get("gender_requirement"),
            extra.get("age_requirement"),
            extra.get("major_requirement"),
            item.get("body_text"),
            extra.get("requirements"),
            extra.get("published_at"),
            extra.get("deadline_at"),
            extra.get("validity_days"),
            extra.get("status_text"),
        ),
        now=now,
    )
