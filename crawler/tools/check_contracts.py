"""Mechanical checks for crawler design and implementation contracts."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


DOCS = Path(__file__).resolve().parents[1] / "docs"
PIPELINE = Path(__file__).resolve().parents[1] / "pipeline"
SCHEMA_SOURCE = (
    Path(__file__).resolve().parents[1]
    / "collection"
    / "shared"
    / "crawler_collection"
    / "schema.py"
)
TOOLS = Path(__file__).resolve().parent
SOURCES = DOCS / "sources.json"

SOURCE_STATUSES = {
    "draft",
    "approved",
    "approved-with-gaps",
    "blocked",
    "deferred",
    "excluded",
}
ACCESS_LEVELS = {
    "public",
    "login-required",
    "robots-restricted",
    "manual-only",
}
RIGHTS_STATUSES = {
    "noncommercial-permitted",
    "attribution-required",
    "assumed-noncommercial-user-risk",
    "prohibited",
    "unknown",
}
ISSUE_STATUSES = {"resolved", "deferred", "excluded"}
EXPECTED_SOURCE_COUNT = 14

REQUIRED_SERVICE_TABLES = {
    "std_sources",
    "import_batches",
    "import_conflicts",
    "import_batch_items",
}
REQUIRED_RELATION_TABLES = {
    "std_agri_product_sources",
    "std_agri_product_aliases",
    "std_job_sources",
    "std_job_locations",
    "std_ich_inheritors",
    "std_ich_related_items",
    "std_ich_media_links",
}

FORBIDDEN_SOURCE_FIELDS = {
    "source_record_id",
    "std_jobs.headcount_raw",
    "std_jobs.description_html",
    "std_jobs.requirements_text",
    "std_jobs.company_address",
    "std_jobs.contact_name",
    "std_jobs.contact_phone",
    "std_jobs.contact_fax",
    "std_jobs.company_website",
    "std_jobs.postal_code",
    "std_jobs.contact_email",
    "std_jobs.listed_at",
    "std_jobs.department",
    "std_jobs.company_description",
    "std_jobs.listed_relative_time",
}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _rel(path: Path) -> str:
    return str(path.relative_to(DOCS.parent.parent)).replace("\\", "/")


def check_docs() -> list[str]:
    errors: list[str] = []
    for path in sorted(DOCS.rglob("*.md")):
        text = _read(path)
        rel = _rel(path)
        if "\u2014" in text:
            errors.append(f"{rel}: contains em-dash")
        if any(
            ord(char) < 32 and char not in {"\n", "\r", "\t"}
            for char in text
        ):
            errors.append(f"{rel}: contains control character")
        for match in re.finditer(
            r"\b(std_[a-z0-9_]+ss|stage_[a-z0-9_]+ss)\b",
            text,
        ):
            errors.append(f"{rel}: repeated-letter table name {match.group(0)}")
    return errors


def _declared_line(path: Path, label: str) -> str | None:
    match = re.search(
        rf"^\s*(?:-\s*)?{re.escape(label)}:\s*`([^`]+)`",
        _read(path),
        re.MULTILINE,
    )
    return match.group(1) if match else None


def check_sources() -> list[str]:
    errors: list[str] = []
    data = json.loads(_read(SOURCES))
    sources = data.get("sources")
    if not isinstance(sources, list):
        return ["sources.json: sources must be a list"]
    if len(sources) != EXPECTED_SOURCE_COUNT:
        errors.append(
            "sources.json: expected "
            f"{EXPECTED_SOURCE_COUNT} sources, found {len(sources)}"
        )
    seen: set[str] = set()
    seen_documents: dict[str, str] = {}
    seen_reviews: dict[str, str] = {}
    required = {
        "id",
        "name",
        "domains",
        "content_domains",
        "priority",
        "enabled",
        "status",
        "access",
        "rights_status",
        "attribution_required",
        "attribution_text",
        "rights_evidence_url",
        "run_modes",
        "verification",
        "document",
        "review",
    }
    for source in sources:
        source_id = source.get("id", "<missing>")
        if source_id in seen:
            errors.append(f"sources.json: duplicate source id {source_id}")
        seen.add(source_id)
        missing = required - source.keys()
        if missing:
            errors.append(f"sources.json: {source_id} missing {sorted(missing)}")
        if source.get("status") not in SOURCE_STATUSES:
            errors.append(
                f"sources.json: {source_id} invalid status {source.get('status')}"
            )
        if source.get("access") not in ACCESS_LEVELS:
            errors.append(
                f"sources.json: {source_id} invalid access {source.get('access')}"
            )
        if source.get("rights_status") not in RIGHTS_STATUSES:
            errors.append(
                "sources.json: "
                f"{source_id} invalid rights_status {source.get('rights_status')}"
            )
        if not isinstance(source.get("enabled"), bool):
            errors.append(f"sources.json: {source_id} enabled must be boolean")
        if not isinstance(source.get("attribution_required"), bool):
            errors.append(
                f"sources.json: {source_id} attribution_required must be boolean"
            )
        if not (source.get("attribution_text") or "").strip():
            errors.append(f"sources.json: {source_id} missing attribution_text")
        if not (source.get("rights_evidence_url") or "").strip():
            errors.append(
                f"sources.json: {source_id} missing rights_evidence_url"
            )
        run_modes = source.get("run_modes")
        if not isinstance(run_modes, list) or any(
            not isinstance(mode, str) or not mode.strip()
            for mode in (run_modes or [])
        ):
            errors.append(f"sources.json: {source_id} invalid run_modes")
        for key in ("document", "review"):
            rel = source.get(key)
            if rel and not (DOCS / rel).exists():
                errors.append(f"sources.json: {source_id} missing {rel}")
        document = source.get("document")
        if document:
            owner = seen_documents.get(document)
            if owner and owner != source_id:
                errors.append(
                    f"sources.json: {source_id} reuses {document} from {owner}"
                )
            seen_documents[document] = source_id
            path = DOCS / document
            status = _declared_line(path, "状态")
            rights = _declared_line(path, "权利状态")
            access = _declared_line(path, "访问等级")
            if status != source.get("status"):
                errors.append(
                    f"sources.json: {source_id} status {source.get('status')} "
                    f"does not match {document} status {status}"
                )
            if rights != source.get("rights_status"):
                errors.append(
                    f"sources.json: {source_id} rights {source.get('rights_status')} "
                    f"does not match {document} rights {rights}"
                )
            if access != source.get("access"):
                errors.append(
                    f"sources.json: {source_id} access {source.get('access')} "
                    f"does not match {document} access {access}"
                )
        review = source.get("review")
        if review:
            owner = seen_reviews.get(review)
            if owner and owner != source_id:
                errors.append(
                    f"sources.json: {source_id} reuses {review} from {owner}"
                )
            seen_reviews[review] = source_id
            path = DOCS / review
            status = _declared_line(path, "审核结论")
            rights = _declared_line(path, "权利状态")
            if status != source.get("status"):
                errors.append(
                    f"sources.json: {source_id} status {source.get('status')} "
                    f"does not match {review} conclusion {status}"
                )
            if rights != source.get("rights_status"):
                errors.append(
                    f"sources.json: {source_id} rights {source.get('rights_status')} "
                    f"does not match {review} rights {rights}"
                )

    weather_ids = {
        source.get("id")
        for source in sources
        if "weather" in (source.get("content_domains") or [])
    }
    expected_weather_ids = {"weather", "open-meteo", "qweather"}
    if weather_ids != expected_weather_ids:
        errors.append(
            "sources.json: weather source ids must be "
            f"{sorted(expected_weather_ids)}, found {sorted(weather_ids)}"
        )
    by_id = {source.get("id"): source for source in sources}
    expected_status = {
        "zhongguoyuyan": "excluded",
        "cnopendata": "deferred",
        "open-meteo": "draft",
        "qweather": "draft",
    }
    for source_id, expected in expected_status.items():
        if source_id not in by_id:
            errors.append(f"sources.json: missing {source_id}")
        elif by_id[source_id].get("status") != expected:
            errors.append(
                f"sources.json: {source_id} must be {expected}, "
                f"found {by_id[source_id].get('status')}"
            )
    five = by_id.get("5ajob")
    if five and five.get("rights_status") not in {"prohibited", "excluded"}:
        errors.append("sources.json: 5ajob must be prohibited or excluded")
    return errors


def check_source_fields() -> list[str]:
    errors: list[str] = []
    for folder in ("sources", "reviews"):
        for path in sorted((DOCS / folder).glob("*.md")):
            if path.name.startswith("_"):
                continue
            text = _read(path)
            for token in FORBIDDEN_SOURCE_FIELDS:
                if token in text:
                    errors.append(f"{_rel(path)}: unresolved field {token}")
    feiyiw = _read(DOCS / "sources" / "feiyiw.md")
    if "字段定义见 `schema/std-entities.md#std_ich_articles`" not in feiyiw:
        errors.append("sources/feiyiw.md: std_ich_articles must use a schema pointer")
    return errors


def check_schema_names() -> list[str]:
    errors: list[str] = []
    std_text = _read(DOCS / "schema" / "std-entities.md")
    schema_text = _read(DOCS / "schema" / "crawler-db.md")
    converter_text = _read(DOCS / "schema" / "converter.md")
    database_text = _read(SCHEMA_SOURCE)
    entities = set(re.findall(r"^### `(std_[a-z0-9_]+)`", std_text, re.MULTILINE))
    tables = set(re.findall(r"^#### (std_[a-z0-9_]+)", schema_text, re.MULTILINE))
    services = REQUIRED_SERVICE_TABLES
    for name in sorted(tables - entities - services):
        errors.append(f"crawler-db.md: table {name} is not in std-entities.md")
    for name in sorted(entities - tables):
        errors.append(f"crawler-db.md: missing physical table {name}")
    for name in sorted(set(re.findall(r"`(std_[a-z0-9_]+)`", converter_text))):
        if name not in entities and name not in services:
            errors.append(f"converter.md: unknown entity {name}")
    for name in sorted(REQUIRED_RELATION_TABLES | services):
        if f"CREATE TABLE IF NOT EXISTS {name}" not in database_text:
            errors.append(f"database.py: missing required table {name}")
    article_section = re.search(
        r"^### `std_ich_articles`.*?(?=^## |\Z)",
        std_text,
        re.MULTILINE | re.DOTALL,
    )
    if not article_section:
        errors.append("std-entities.md: missing frozen std_ich_articles entity")
    elif "尚未冻结" in article_section.group(0):
        errors.append("std-entities.md: std_ich_articles must be frozen")
    return errors


def check_mapping_contracts() -> list[str]:
    errors: list[str] = []
    forbidden = (
        "source_record_id",
        "mandarin_definition",
        "body_text",
        "body_html",
        "project_code",
        "declared_by",
        "batch_label",
    )
    for name in ("agri-products.md", "ich-crafts.md", "jobs.md", "dialects.md"):
        path = DOCS / "mapping" / name
        text = _read(path)
        for token in forbidden:
            if token in text:
                errors.append(f"{_rel(path)}: unresolved contract field {token}")
    return errors


def check_url_and_rights_contract() -> list[str]:
    errors: list[str] = []
    contract = _read(DOCS / "sources" / "CONTRACT.md")
    schema = _read(DOCS / "schema" / "crawler-db.md")
    for token in (
        "source_url",
        "long_term_url",
        "detail_url_status",
        "fetch_url",
        "locator",
        "rights_status",
        "attribution_required",
        "attribution_text",
        "rights_evidence_url",
    ):
        if token not in contract:
            errors.append(f"sources/CONTRACT.md: missing {token}")
        if token not in schema:
            errors.append(f"crawler-db.md: missing {token}")
    return errors


def _table_block(text: str, table: str) -> str:
    match = re.search(
        rf"CREATE TABLE IF NOT EXISTS\s+{re.escape(table)}\s*\((.*?)\);",
        text,
        re.DOTALL,
    )
    return match.group(1) if match else ""


def _function_block(text: str, name: str) -> str:
    match = re.search(
        rf"^def\s+{re.escape(name)}\s*\(.*?(?=^def\s+|\Z)",
        text,
        re.DOTALL | re.MULTILINE,
    )
    return match.group(0) if match else ""


def check_implementation_contract() -> list[str]:
    errors: list[str] = []
    database_text = _read(SCHEMA_SOURCE)
    evidence_text = _read(PIPELINE / "evidence.py")
    run_source_text = _read(PIPELINE / "run_source.py")
    converter_text = _read(PIPELINE / "converter.py")
    run_py_text = _read(PIPELINE.parent / "run.py")
    init_text = _read(PIPELINE / "__init__.py")
    feiyiw_text = _read(PIPELINE / "sources" / "feiyiw.py")

    raw_block = _table_block(database_text, "raw_fetches")
    for declaration in (
        "source_url TEXT NOT NULL",
        "long_term_url TEXT NOT NULL",
        "detail_url_status TEXT NOT NULL",
        "locator TEXT",
    ):
        if declaration not in raw_block:
            errors.append(f"database.py: raw_fetches missing {declaration}")
    for field in (
        "source_url",
        "long_term_url",
        "detail_url",
        "detail_url_status",
        "locator",
        "status_code",
        "content_type",
        "response_headers",
        "body_path",
        "body_sha256",
        "body_saved",
    ):
        if field not in evidence_text:
            errors.append(f"evidence.py: raw evidence missing {field}")

    if "RUN_MODES = tuple(" not in run_source_text:
        errors.append("run_source.py: RUN_MODES must be the single mode tuple")
    if "_SOURCE_MODES" not in run_source_text:
        errors.append("run_source.py: missing source-mode truth table")
    if "source_registry.load_registry" not in run_source_text:
        errors.append("run_source.py: must load the central source registry")
    if "source_registry.rights_fields" not in run_source_text:
        errors.append("run_source.py: rights must come from the source registry")
    if "RUN_MODES = (" in run_py_text:
        errors.append("run.py: duplicate RUN_MODES definition")
    if "from .pipeline import RUN_MODES" not in run_py_text:
        errors.append("run.py: must import RUN_MODES")
    for token in (
        "persist_raw_evidence",
        "stage_source_items",
        "evaluate_publication",
        "source:{source_id}:{mode}:",
        "P020251225613822033339.xlsx",
        "t20251128_468194.htm",
        "_ihchina_list_url",
    ):
        if token not in run_source_text:
            errors.append(f"run_source.py: missing {token}")
    if 'run_id="fixture:announcements"' in run_source_text:
        errors.append("run_source.py: hardcoded announcement success path")
    if "_is_public_article_url" not in feiyiw_text:
        errors.append("feiyiw.py: missing public URL boundary")

    for token in (
        "_sort_by_source_priority",
        "_publishable_rows",
        "evaluate_publication",
        "std_sources",
        "import_batches",
        "import_conflicts",
        "import_batch_items",
        "def rollback_batch",
        "source_registry.load_registry",
        "source_registry.evaluate_source",
    ):
        if token not in converter_text:
            errors.append(f"converter.py: missing {token}")
    if "rollback_batch" not in init_text:
        errors.append("pipeline/__init__.py: missing rollback_batch export")

    agri_block = _function_block(converter_text, "_agri_plan")
    if "_publishable_rows" not in agri_block:
        errors.append("converter.py: _agri_plan bypasses publication gate")
    for planner in ("_ich_plan", "_job_plan", "_dialect_plan"):
        block = _function_block(converter_text, planner)
        if "evaluate_publication" not in block and "_publishable_rows" not in block:
            errors.append(f"converter.py: {planner} bypasses publication gate")
    return errors


def check_issue_counts() -> list[str]:
    errors: list[str] = []
    text = _read(DOCS / "ISSUES.md")
    rows = []
    for line in text.splitlines():
        if not re.match(r"^\| P[0-2]-\d+ \|", line):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 7:
            errors.append(f"ISSUES.md: malformed row {cells[0] if cells else '?'}")
            continue
        issue_id, status, blocking, evidence = cells[0], cells[5], cells[6], cells[3]
        action = cells[4]
        if status not in ISSUE_STATUSES:
            errors.append(f"ISSUES.md: {issue_id} invalid terminal status {status}")
        if not evidence:
            errors.append(f"ISSUES.md: {issue_id} missing evidence")
        if status == "resolved" and not any(
            token in evidence
            for token in ("docs/", "crawler/tests/", "sources.json")
        ):
            errors.append(f"ISSUES.md: {issue_id} resolved without evidence link")
        if status == "deferred" and "解除条件" not in action:
            errors.append(f"ISSUES.md: {issue_id} deferred without release condition")
        rows.append((issue_id.split("-", 1)[0], status, blocking))

    expected_total = len(rows)
    expected_blocking = sum(1 for _, _, blocking in rows if blocking == "是")
    total_match = re.search(r"- 合计: (\d+)", text)
    blocking_match = re.search(r"- 阻塞首批: (\d+)", text)
    if not total_match or int(total_match.group(1)) != expected_total:
        errors.append(
            f"ISSUES.md: total mismatch, rows={expected_total}, "
            f"header={total_match.group(1) if total_match else 'missing'}"
        )
    for priority in ("P0", "P1", "P2"):
        expected = sum(1 for row_priority, _, _ in rows if row_priority == priority)
        match = re.search(rf"- {priority}: (\d+)", text)
        if not match or int(match.group(1)) != expected:
            errors.append(
                f"ISSUES.md: {priority} mismatch, rows={expected}, "
                f"header={match.group(1) if match else 'missing'}"
            )
    if not blocking_match or int(blocking_match.group(1)) != expected_blocking:
        errors.append(
            f"ISSUES.md: blocking mismatch, rows={expected_blocking}, "
            f"header={blocking_match.group(1) if blocking_match else 'missing'}"
        )
    return errors


def check_history_hygiene() -> list[str]:
    sys.path.insert(0, str(TOOLS))
    try:
        from check_history_hygiene import _load_baseline, scan_history
    except ImportError as exc:
        return [f"history hygiene: cannot import scanner: {exc}"]
    findings = set(scan_history())
    new_findings = findings - _load_baseline()
    return [
        f"history hygiene: new {category} in {path or '<no-path>'} "
        f"({object_id[:12]})"
        for object_id, path, category in sorted(new_findings)
    ]


def check_history_baseline() -> list[str]:
    path = DOCS / "operations" / "history-hygiene-baseline.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"history baseline: cannot read {path}: {exc}"]
    findings = payload.get("findings")
    if findings:
        return [
            "history baseline: clean public branch must use an empty findings list"
        ]
    return []


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scan-history",
        action="store_true",
        help="also scan reachable history; final clean-clone release gate",
    )
    args = parser.parse_args(argv)
    errors: list[str] = []
    errors.extend(check_docs())
    errors.extend(check_sources())
    errors.extend(check_source_fields())
    errors.extend(check_schema_names())
    errors.extend(check_mapping_contracts())
    errors.extend(check_url_and_rights_contract())
    errors.extend(check_implementation_contract())
    errors.extend(check_issue_counts())
    errors.extend(check_history_baseline())
    if args.scan_history:
        errors.extend(check_history_hygiene())
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        print(f"contract check failed: {len(errors)} error(s)", file=sys.stderr)
        return 1
    print("contract check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
