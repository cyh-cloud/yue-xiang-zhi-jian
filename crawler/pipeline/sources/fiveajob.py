"""5A agricultural job source discovery and filtering."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from .. import source_registry


SOURCE_ID = "5ajob"
RULE_VERSION = "5ajob-agriculture-v1"

_DETAIL_PATTERNS = (
    re.compile(r"^/c-d-[^/]+-h/(?P<job_id>\d+)\.html$"),
    re.compile(
        r"^/companyinfo/detail/(?:[^/]+/)?htmljob/(?P<job_id>\d+)\.html$"
    ),
)
_PRIVATE_PATH_PARTS = ("/personal/", "/resume/")
_AGRICULTURE_TERMS = (
    "农业",
    "农学",
    "农艺",
    "农技",
    "农资",
    "农机",
    "农田",
    "农户",
    "农作物",
    "作物",
    "种植",
    "植保",
    "植物保护",
    "育种",
    "种子",
    "种业",
    "肥料",
    "施肥",
    "土壤",
    "园艺",
    "果树",
    "蔬菜",
    "茶叶",
    "茶园",
    "畜牧",
    "养殖",
    "兽医",
    "兽药",
    "饲料",
    "水产",
    "渔业",
    "林业",
    "林木",
    "苗木",
    "花卉",
    "食用菌",
    "稻田",
    "田间",
    "农产品",
    "乡村振兴",
)


def discover(config):
    """Discover list fixtures, deduplicate jobs, and retain filter evidence."""
    source = source_registry.load_registry(
        getattr(config, "registry_path", None)
    )[SOURCE_ID]
    rights = source_registry.rights_fields(source)
    path = Path(config.fixture_root) / "discover.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    pages = payload.get("pages")
    if pages is None:
        pages = [{"page": 1, "items": payload.get("items") or []}]

    seen_ids = set()
    seen_urls = set()
    included = []
    excluded = []
    processed_pages = []
    duplicate_count = 0
    stop_reason = "fixture_exhausted"
    page_limit = max(1, int(getattr(config, "page_limit", 100)))

    for fallback_page_no, page in enumerate(pages, start=1):
        page_no = int(page.get("page") or fallback_page_no)
        if page_no > 251:
            stop_reason = "past_wraparound_page"
            break
        rows = page.get("items") or []
        if not rows:
            stop_reason = "empty_page"
            break

        processed_pages.append(page_no)
        new_ids = []
        for row_no, row in enumerate(rows, start=1):
            detail_html = row.get("detail_html")
            detail = (
                parse_detail(detail_html)
                if isinstance(detail_html, str) and detail_html.strip()
                else {}
            )
            if detail:
                row = {
                    **row,
                    **{
                        key: value
                        for key, value in detail.items()
                        if value not in (None, "")
                    },
                }
            raw_url = _first_text(row, "detail_url", "url", "source_url")
            job_id = _first_text(row, "job_id", "source_item_id")
            canonical_url, canonical_id, reason = _canonical_detail(raw_url, job_id)
            if reason:
                excluded.append(
                    {
                        "source_item_id": job_id,
                        "source_url": raw_url,
                        "reason": reason,
                        "page": page_no,
                        "row": row_no,
                    }
                )
                continue

            if canonical_id in seen_ids or canonical_url in seen_urls:
                duplicate_count += 1
                continue

            seen_ids.add(canonical_id)
            seen_urls.add(canonical_url)
            new_ids.append(canonical_id)

            relevance = _assess_agriculture(row)
            if not relevance["is_related"]:
                excluded.append(
                    {
                        "source_item_id": canonical_id,
                        "source_url": canonical_url,
                        "reason": "not_agriculture_related",
                        "page": page_no,
                        "row": row_no,
                    }
                )
                continue

            title = _first_text(row, "title", "job_name")
            if not title:
                excluded.append(
                    {
                        "source_item_id": canonical_id,
                        "source_url": canonical_url,
                        "reason": "missing_title",
                        "page": page_no,
                        "row": row_no,
                    }
                )
                continue

            extra = {
                "agriculture_relevance": relevance,
                "list_fields": {
                    "company_name": _first_text(row, "company_name"),
                    "industry": _first_text(row, "industry", "company_industry"),
                    "location": _first_text(row, "location", "location_raw"),
                    "salary": _first_text(row, "salary", "salary_raw"),
                    "status": _first_text(row, "status", "status_text"),
                    "description": _first_text(row, "description"),
                },
                "list_page": page_no,
                "list_row": row_no,
                "risk_acceptance": {
                    "reason": "noncommercial competition use accepted by project owner",
                    "source_notice": "reproduction requires 5ajob.com permission",
                },
            }
            if detail:
                extra["detail_html_sha256"] = hashlib.sha256(
                    detail_html.encode("utf-8")
                ).hexdigest()
            included.append(
                {
                    "source_item_id": canonical_id,
                    "title": title,
                    "company_name": _first_text(row, "company_name"),
                    "company_industry": _first_text(
                        row, "industry", "company_industry"
                    ),
                    "location_raw": _first_text(row, "location", "location_raw"),
                    "salary_raw": _first_text(row, "salary", "salary_raw"),
                    "education_raw": _first_text(row, "education_raw"),
                    "experience_raw": _first_text(row, "experience_raw"),
                    "employment_type": _first_text(row, "employment_type"),
                    "major_requirement": _first_text(row, "major_requirement"),
                    "requirements": _first_text(row, "requirements"),
                    "deadline_at": _first_text(row, "deadline_at"),
                    "status_text": _first_text(row, "status", "status_text"),
                    "description": _first_text(row, "description"),
                    "source_url": canonical_url,
                    "long_term_url": canonical_url,
                    "detail_url": canonical_url,
                    "detail_url_status": "direct",
                    "fetch_url": raw_url,
                    "locator": f"list-page:{page_no}:row:{row_no}",
                    **rights,
                    "publish_status": "blocked",
                    "confidence": "medium",
                    "extra": extra,
                }
            )

        if not new_ids:
            stop_reason = "no_new_ids"
            break
        if page.get("is_last"):
            stop_reason = "last_page"
            break
        if len(processed_pages) >= page_limit:
            stop_reason = "page_limit"
            break

    discovery = {
        "source_id": SOURCE_ID,
        "processed_pages": processed_pages,
        "stopped_reason": stop_reason,
        "unique_job_ids": len(seen_ids),
        "duplicate_count": duplicate_count,
        "excluded": excluded,
    }
    for item in included:
        item["extra"]["discovery"] = discovery
    return {"items": included, "discovery": discovery}


def parse_detail(html):
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    title_node = soup.select_one("#jobdetail h1")
    values = {}
    for row in soup.select("#jobdetail tr"):
        cells = row.select("th, td")
        if len(cells) < 2:
            continue
        label = cells[0].get_text(" ", strip=True)
        value = cells[1].get_text(" ", strip=True)
        if label and value:
            values[label] = value
    return {
        "title": _node_text(title_node),
        "company_name": _node_text(soup.select_one("#zhtitle")),
        "source_item_id": _node_text(soup.select_one("#rjobid")),
        "location_raw": values.get("工作地点"),
        "salary_raw": values.get("月薪"),
        "education_raw": values.get("学历要求"),
        "experience_raw": values.get("工作经验"),
        "employment_type": values.get("招聘方式"),
        "major_requirement": values.get("专业要求"),
        "description": values.get("岗位描述"),
        "requirements": values.get("应聘要求"),
        "deadline_at": _node_text(soup.select_one("#jobexpire")),
        "status_text": values.get("状态") or values.get("招聘状态"),
    }


def _node_text(node):
    return node.get_text(" ", strip=True) if node else None


def _first_text(row, *keys):
    for key in keys:
        value = row.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _canonical_detail(value, declared_job_id):
    if not value:
        return None, declared_job_id, "missing_detail_url"
    try:
        parsed = urlsplit(value)
    except ValueError:
        return None, declared_job_id, "invalid_detail_url"

    scheme = parsed.scheme.lower()
    hostname = (parsed.hostname or "").lower()
    if scheme not in {"http", "https"} or hostname not in {
        "5ajob.com",
        "www.5ajob.com",
    }:
        return None, declared_job_id, "unsupported_detail_url"

    path = re.sub(r"/+", "/", parsed.path or "/")
    lowered_path = path.lower()
    if any(part in lowered_path for part in _PRIVATE_PATH_PARTS):
        return None, declared_job_id, "private_path"

    matched_id = None
    for pattern in _DETAIL_PATTERNS:
        match = pattern.fullmatch(path)
        if match:
            matched_id = match.group("job_id")
            break
    if matched_id is None:
        return None, declared_job_id, "not_a_job_detail_url"
    if declared_job_id and declared_job_id != matched_id:
        return None, declared_job_id, "job_id_mismatch"

    canonical = urlunsplit((scheme, hostname, path, "", ""))
    return canonical, matched_id, None


def _assess_agriculture(row):
    evidence = {}
    matched_fields = []
    matched_terms = set()
    for field, keys in (
        ("title", ("title", "job_name")),
        ("industry", ("industry", "company_industry")),
        ("description", ("description",)),
    ):
        text = _normalize_text(_first_text(row, *keys))
        terms = sorted(term for term in _AGRICULTURE_TERMS if term in text)
        evidence[field] = {"text": text, "terms": terms}
        if terms:
            matched_fields.append(field)
            matched_terms.update(terms)
    return {
        "is_related": bool(matched_terms),
        "rule_version": RULE_VERSION,
        "matched_fields": matched_fields,
        "matched_terms": sorted(matched_terms),
        "evidence": evidence,
    }


def _normalize_text(value):
    if not value:
        return ""
    return unicodedata.normalize("NFKC", value).casefold()
