"""Build and validate a public-safe index for archived live evidence."""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit, urlunsplit

try:
    from crawler.tools.public_hygiene import scan_fixture_bytes
except ModuleNotFoundError:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from crawler.tools.public_hygiene import scan_fixture_bytes


ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "crawler" / "docs" / "sources.json"
DEFAULT_OUTPUT = (
    ROOT / "crawler" / "docs" / "operations" / "live-evidence-index.json"
)
SCHEMA_VERSION = 1
COUNT_KEYS = (
    "raw",
    "stage",
    "candidate",
    "deferred",
    "blocked",
    "failed",
    "skipped",
)
TOP_LEVEL_KEYS = {
    "schema_version",
    "generated_at",
    "archive_root",
    "public_repository_policy",
    "source_count",
    "runs",
}
RUN_KEYS = {
    "source_id",
    "run_id",
    "mode",
    "status",
    "started_at",
    "finished_at",
    "retrieval_time",
    "archive_path",
    "report_path",
    "database_path",
    "download_root",
    "acceptance_record",
    "source_urls",
    "list_urls",
    "detail_urls",
    "carrier_urls",
    "attachment_urls",
    "counts",
    "failure_summary",
    "blocking_reason",
    "candidate_reasons",
    "responses",
}
RESPONSE_KEYS = (
    "role",
    "url",
    "final_url",
    "source_url",
    "carrier_url",
    "detail_url",
    "attachment_url",
    "retrieved_at",
    "http_status",
    "content_type",
    "byte_size",
    "sha256",
    "robots_decision",
    "fetch_status",
    "error",
)
CANDIDATE_REASON_KEYS = {"status", "reason", "count"}
ARCHIVE_PATH_KEYS = (
    "archive_path",
    "report_path",
    "database_path",
    "download_root",
)
URL_KEYS = (
    "source_urls",
    "list_urls",
    "detail_urls",
    "carrier_urls",
    "attachment_urls",
)
SENSITIVE_QUERY_MARKERS = (
    "signature",
    "credential",
    "access_token",
    "api_key",
    "apikey",
    "session",
    "cookie",
    "authorization",
    "x-amz-",
    "x-goog-",
    "expires",
    "policy",
)
MEDIA_SUFFIXES = {
    ".pdf",
    ".xls",
    ".xlsx",
    ".csv",
    ".zip",
    ".doc",
    ".docx",
}
TEMP_MARKERS = ("%temp%", "appdata\\local\\temp", "appdata/local/temp")
URL_PATTERN = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)


def _safe_url(value):
    if not value:
        return None
    parsed = urlsplit(str(value))
    query = parse_qsl(parsed.query, keep_blank_values=True)
    sensitive = any(
        any(marker in key.lower() for marker in SENSITIVE_QUERY_MARKERS)
        for key, _ in query
    )
    netloc = parsed.netloc
    if "@" in netloc:
        netloc = netloc.rsplit("@", 1)[-1]
    if sensitive:
        return urlunsplit((parsed.scheme, netloc, parsed.path, "", ""))
    return urlunsplit(
        (parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment)
    )


def _safe_text(value):
    if value is None:
        return None
    text = str(value)
    text = re.sub(
        r"https?://[^\s<>\"]+",
        lambda match: _safe_url(match.group(0)) or "",
        text,
    )
    text = re.sub(
        r"(?i)(?:[A-Z]:\\|/)[^ \t\r\n]*Temp[^ \t\r\n]*",
        "<temporary-path>",
        text,
    )
    return text


def _source_reviews():
    payload = json.loads(REGISTRY.read_text(encoding="utf-8"))
    reviews = {}
    for source in payload.get("sources", []):
        source_id = source.get("id")
        sample = (
            ROOT
            / "crawler"
            / "docs"
            / "reviews"
            / f"{source_id}-scrapy-sample.md"
        )
        if sample.is_file():
            reviews[source_id] = sample.relative_to(ROOT).as_posix()
        elif source.get("review"):
            reviews[source_id] = (
                Path("crawler") / "docs" / source["review"]
            ).as_posix()
    return reviews


def _table_columns(conn, table):
    return {
        row[1]
        for row in conn.execute(f"PRAGMA table_info({table})")
    }


def _candidate_reasons(conn, run_id):
    reasons = {}
    tables = conn.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type = 'table' AND name LIKE 'std_%'"
    )
    for (table,) in tables:
        columns = _table_columns(conn, table)
        if not {"run_id", "candidate_status", "candidate_reason"} <= columns:
            continue
        for status, reason, count in conn.execute(
            f"SELECT candidate_status, candidate_reason, COUNT(*) "
            f"FROM {table} WHERE run_id = ? "
            "GROUP BY candidate_status, candidate_reason",
            (run_id,),
        ):
            key = (status, reason)
            reasons[key] = reasons.get(key, 0) + count
    return [
        {"status": status, "reason": reason, "count": count}
        for (status, reason), count in sorted(
            reasons.items(), key=lambda item: (item[0][0], item[0][1] or "")
        )
    ]


def _raw_responses(conn, run_id):
    columns = _table_columns(conn, "raw_fetches")
    required = {
        "request_url",
        "final_url",
        "source_url",
        "long_term_url",
        "detail_url",
        "fetch_url",
        "status_code",
        "content_type",
        "body_bytes",
        "body_sha256",
        "robots_decision",
        "fetch_status",
        "error_message",
        "retrieved_at",
        "metadata_json",
    }
    if not required <= columns:
        missing = sorted(required - columns)
        raise ValueError(f"raw_fetches missing columns: {missing}")
    rows = conn.execute(
        "SELECT request_url, final_url, source_url, long_term_url, "
        "detail_url, fetch_url, status_code, content_type, body_bytes, "
        "body_sha256, robots_decision, fetch_status, error_message, "
        "retrieved_at, metadata_json "
        "FROM raw_fetches WHERE run_id = ? ORDER BY id",
        (run_id,),
    )
    responses = []
    for row in rows:
        (
            request_url,
            final_url,
            source_url,
            long_term_url,
            detail_url,
            fetch_url,
            status_code,
            content_type,
            body_bytes,
            body_sha256,
            robots_decision,
            fetch_status,
            error_message,
            retrieved_at,
            metadata_json,
        ) = row
        try:
            metadata = json.loads(metadata_json or "{}")
        except json.JSONDecodeError:
            metadata = {}
        file_name = str(metadata.get("file_name") or "")
        media_kind = str(metadata.get("media_kind") or "")
        content_type = str(content_type or "")
        attachment = (
            media_kind == "attachment"
            or Path(file_name).suffix.lower() in MEDIA_SUFFIXES
            or "pdf" in content_type.lower()
            or "spreadsheet" in content_type.lower()
            or "excel" in content_type.lower()
        )
        detail = bool(detail_url)
        carrier = bool(
            long_term_url
            and long_term_url != detail_url
            and not attachment
        )
        if attachment:
            role = "attachment"
        elif detail:
            role = "detail"
        elif carrier:
            role = "carrier"
        else:
            role = "list"
        responses.append(
            {
                "role": role,
                "url": _safe_url(request_url),
                "final_url": _safe_url(final_url),
                "source_url": _safe_url(source_url),
                "carrier_url": _safe_url(long_term_url)
                if carrier
                else None,
                "detail_url": _safe_url(detail_url),
                "attachment_url": _safe_url(fetch_url)
                if attachment
                else None,
                "retrieved_at": retrieved_at,
                "http_status": status_code,
                "content_type": content_type or None,
                "byte_size": body_bytes,
                "sha256": body_sha256,
                "robots_decision": robots_decision,
                "fetch_status": fetch_status,
                "error": _safe_text(error_message),
            }
        )
    return responses


def _unique_urls(responses, key):
    values = []
    seen = set()
    for response in responses:
        value = response.get(key)
        if not value or value in seen:
            continue
        seen.add(value)
        values.append(value)
    return values


def _report_for_source(report_paths):
    selected = {}
    for path in report_paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        source_id = payload.get("source_id")
        if not source_id:
            continue
        current = selected.get(source_id)
        current_key = (
            current.get("finished_at") or current.get("started_at") or "",
            current.get("status") == "succeeded",
        ) if current else ("", False)
        candidate_key = (
            payload.get("finished_at") or payload.get("started_at") or "",
            payload.get("status") == "succeeded",
        )
        if candidate_key >= current_key:
            selected[source_id] = payload
            selected[source_id]["_report_path"] = path
    return selected


def build_live_evidence_index(archive_root, output_path=DEFAULT_OUTPUT):
    archive_root = Path(archive_root).resolve()
    output_path = Path(output_path).resolve()
    report_paths = sorted(
        path
        for path in archive_root.rglob("*.json")
        if path.parent.name == "reports"
    )
    if not report_paths:
        raise ValueError(f"no run reports found under {archive_root}")
    reviews = _source_reviews()
    runs = []
    for source_id, report in sorted(_report_for_source(report_paths).items()):
        report_path = report["_report_path"]
        source_dir = report_path.parent.parent
        database_path = source_dir / "crawler.db"
        if not database_path.is_file():
            raise ValueError(f"missing collection database: {database_path}")
        conn = sqlite3.connect(database_path)
        try:
            responses = _raw_responses(conn, report["run_id"])
            candidate_reasons = _candidate_reasons(conn, report["run_id"])
        finally:
            conn.close()
        blocked_reasons = [
            item["reason"]
            for item in candidate_reasons
            if item["status"] == "blocked" and item["reason"]
        ]
        for response in responses:
            status = response.get("http_status")
            if status is not None and int(status) >= 400:
                blocked_reasons.append(
                    f"HTTP {status}: {response.get('url') or '<url>'}"
                )
            if response.get("robots_decision") in {
                "disallowed",
                "unknown",
            }:
                blocked_reasons.append(
                    f"robots:{response['robots_decision']}"
                )
        blocked_reasons = list(dict.fromkeys(blocked_reasons))
        counts = {
            "raw": int(report.get("raw_count", len(responses))),
            "stage": int(report.get("stage_count", 0)),
            "candidate": int(
                report.get("candidate_count", report.get("written", 0))
            ),
            "deferred": int(report.get("deferred", 0)),
            "blocked": int(report.get("blocked", 0)),
            "failed": int(
                report.get("failure_count", report.get("failed", 0))
            ),
            "skipped": int(report.get("skipped", 0)),
        }
        run = {
            "source_id": source_id,
            "run_id": report["run_id"],
            "mode": report.get("mode", "live"),
            "status": report.get("status"),
            "started_at": report.get("started_at"),
            "finished_at": report.get("finished_at"),
            "retrieval_time": report.get("finished_at")
            or report.get("started_at"),
            "archive_path": source_dir.relative_to(archive_root).as_posix(),
            "report_path": report_path.relative_to(archive_root).as_posix(),
            "database_path": database_path.relative_to(archive_root).as_posix(),
            "download_root": (
                source_dir / "download"
            ).relative_to(archive_root).as_posix(),
            "acceptance_record": reviews.get(source_id),
            "source_urls": _unique_urls(responses, "source_url"),
            "list_urls": [
                item["url"]
                for item in responses
                if item["role"] == "list" and item.get("url")
            ],
            "detail_urls": _unique_urls(responses, "detail_url"),
            "carrier_urls": _unique_urls(responses, "carrier_url"),
            "attachment_urls": _unique_urls(
                responses, "attachment_url"
            ),
            "counts": counts,
            "failure_summary": _safe_text(
                report.get("failure_reason")
                or "; ".join(report.get("errors") or [])
                or None
            ),
            "blocking_reason": "; ".join(blocked_reasons) or None,
            "candidate_reasons": [
                {
                    **item,
                    "reason": _safe_text(item.get("reason")),
                }
                for item in candidate_reasons
            ],
            "responses": responses,
        }
        if not run["acceptance_record"]:
            raise ValueError(
                f"no acceptance record found for {source_id}"
            )
        runs.append(run)
    try:
        archive_display = os.path.relpath(archive_root, ROOT)
    except ValueError:
        archive_display = archive_root.as_posix()
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "archive_root": archive_display.replace("\\", "/"),
        "public_repository_policy": (
            "Metadata only. Raw response bodies, personal data, credentials, "
            "cookies, and signed URLs remain outside the public repository."
        ),
        "source_count": len(runs),
        "runs": runs,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return payload


def _walk_keys(value, path=()):
    if isinstance(value, dict):
        for key, child in value.items():
            yield path + (key,), child
            yield from _walk_keys(child, path + (key,))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk_keys(child, path + (index,))


def _walk_strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from _walk_strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_strings(child)


def _unsafe_url_reason(value):
    try:
        parsed = urlsplit(value)
    except ValueError:
        return "malformed URL"
    if "@" in parsed.netloc:
        return "URL contains user information"
    for key, _ in parse_qsl(parsed.query, keep_blank_values=True):
        if any(
            marker in key.lower() for marker in SENSITIVE_QUERY_MARKERS
        ):
            return "URL contains a sensitive query parameter"
    return None


def _unknown_keys(value, allowed):
    return sorted(set(value) - set(allowed))


def validate_live_evidence_index(path=DEFAULT_OUTPUT):
    path = Path(path)
    errors = []
    try:
        raw = path.read_bytes()
        payload = json.loads(raw.decode("utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        return [f"live evidence index: cannot read {path}: {exc}"]
    if not isinstance(payload, dict):
        return ["live evidence index: top-level value must be an object"]
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append("live evidence index: schema_version must be 1")
    missing_top_level = sorted(TOP_LEVEL_KEYS - set(payload))
    if missing_top_level:
        errors.append(
            "live evidence index: missing top-level fields "
            + ", ".join(missing_top_level)
        )
    unknown_top_level = _unknown_keys(payload, TOP_LEVEL_KEYS)
    if unknown_top_level:
        errors.append(
            "live evidence index: unexpected top-level fields "
            + ", ".join(unknown_top_level)
        )
    archive_root = str(payload.get("archive_root") or "")
    if not archive_root:
        errors.append("live evidence index: archive_root must not be empty")
    if any(marker in archive_root.lower() for marker in TEMP_MARKERS):
        errors.append("live evidence index: archive_root is temporary")
    runs = payload.get("runs")
    if not isinstance(runs, list) or not runs:
        errors.append("live evidence index: runs must be a non-empty list")
        return errors
    if payload.get("source_count") != len(runs):
        errors.append("live evidence index: source_count does not match runs")
    seen_sources = set()
    forbidden_keys = {
        "body",
        "body_text",
        "body_html",
        "content",
        "html",
        "raw_html",
    }
    for run in runs:
        if not isinstance(run, dict):
            errors.append("live evidence index: run must be an object")
            continue
        source_id = run.get("source_id")
        if not source_id:
            errors.append("live evidence index: run missing source_id")
            continue
        if source_id in seen_sources:
            errors.append(
                f"live evidence index: duplicate source {source_id}"
            )
        seen_sources.add(source_id)
        unknown_run_keys = _unknown_keys(run, RUN_KEYS)
        if unknown_run_keys:
            errors.append(
                f"live evidence index: {source_id} unexpected fields "
                + ", ".join(unknown_run_keys)
            )
        for key in (
            "run_id",
            "mode",
            "status",
            "started_at",
            "finished_at",
            "retrieval_time",
            "archive_path",
            "report_path",
            "database_path",
            "download_root",
            "acceptance_record",
            "source_urls",
            "list_urls",
            "detail_urls",
            "carrier_urls",
            "attachment_urls",
            "counts",
            "failure_summary",
            "blocking_reason",
            "candidate_reasons",
            "responses",
        ):
            if key not in run:
                errors.append(
                    f"live evidence index: {source_id} missing {key}"
                )
        if run.get("mode") != "live":
            errors.append(
                f"live evidence index: {source_id} mode must be live"
            )
        if not str(run.get("retrieval_time") or "").strip():
            errors.append(
                f"live evidence index: {source_id} missing retrieval_time"
            )
        for key in ARCHIVE_PATH_KEYS:
            value = str(run.get(key) or "")
            path_value = Path(value)
            if (
                not value
                or path_value.is_absolute()
                or ".." in path_value.parts
            ):
                errors.append(
                    f"live evidence index: {source_id} invalid {key}"
                )
        for key in URL_KEYS:
            values = run.get(key)
            if not isinstance(values, list) or any(
                not isinstance(value, str) or not value
                for value in values
            ):
                errors.append(
                    f"live evidence index: {source_id} invalid {key}"
                )
        counts = run.get("counts")
        if not isinstance(counts, dict):
            errors.append(
                f"live evidence index: {source_id} counts must be an object"
            )
            counts = {}
        for key in COUNT_KEYS:
            if key not in counts:
                errors.append(
                    f"live evidence index: {source_id} count missing {key}"
                )
            value = counts.get(key)
            if (
                not isinstance(value, int)
                or isinstance(value, bool)
                or value < 0
            ):
                errors.append(
                    f"live evidence index: {source_id} invalid count {key}"
                )
        unknown_counts = _unknown_keys(counts, COUNT_KEYS)
        if unknown_counts:
            errors.append(
                f"live evidence index: {source_id} unexpected counts "
                + ", ".join(unknown_counts)
            )
        responses = run.get("responses") or []
        if not isinstance(responses, list):
            errors.append(
                f"live evidence index: {source_id} responses must be a list"
            )
            responses = []
        if counts.get("raw") != len(responses):
            errors.append(
                f"live evidence index: {source_id} raw count mismatch"
            )
        acceptance_value = str(run.get("acceptance_record") or "")
        acceptance = (ROOT / acceptance_value).resolve()
        try:
            acceptance.relative_to(ROOT.resolve())
        except ValueError:
            errors.append(
                f"live evidence index: {source_id} acceptance record escapes repo"
            )
        if not acceptance_value or not acceptance.is_file():
            errors.append(
                f"live evidence index: {source_id} acceptance record missing"
            )
        candidate_reasons = run.get("candidate_reasons") or []
        if not isinstance(candidate_reasons, list):
            errors.append(
                f"live evidence index: {source_id} candidate_reasons invalid"
            )
            candidate_reasons = []
        for item in candidate_reasons:
            if not isinstance(item, dict):
                errors.append(
                    f"live evidence index: {source_id} candidate reason invalid"
                )
                continue
            unknown_reason_keys = _unknown_keys(
                item, CANDIDATE_REASON_KEYS
            )
            if unknown_reason_keys:
                errors.append(
                    f"live evidence index: {source_id} candidate reason "
                    "unexpected fields "
                    + ", ".join(unknown_reason_keys)
                )
            count = item.get("count")
            if (
                not isinstance(count, int)
                or isinstance(count, bool)
                or count < 0
            ):
                errors.append(
                    f"live evidence index: {source_id} candidate reason count"
                )
            status = item.get("status")
            if not status or (
                status in {"deferred", "blocked"} and not item.get("reason")
            ):
                errors.append(
                    f"live evidence index: {source_id} candidate reason incomplete"
                )
        for response in responses:
            if not isinstance(response, dict):
                errors.append(
                    f"live evidence index: {source_id} response invalid"
                )
                continue
            unknown_response_keys = _unknown_keys(
                response, RESPONSE_KEYS
            )
            if unknown_response_keys:
                errors.append(
                    f"live evidence index: {source_id} response "
                    "unexpected fields "
                    + ", ".join(unknown_response_keys)
                )
            for key in RESPONSE_KEYS:
                if key not in response:
                    errors.append(
                        f"live evidence index: {source_id} response missing {key}"
                    )
            role = response.get("role")
            if role not in {"carrier", "detail", "attachment", "list"}:
                errors.append(
                    f"live evidence index: {source_id} invalid response role"
                )
            if not str(response.get("retrieved_at") or "").strip():
                errors.append(
                    f"live evidence index: {source_id} response missing time"
                )
            http_status = response.get("http_status")
            if http_status is not None and (
                not isinstance(http_status, int)
                or isinstance(http_status, bool)
            ):
                errors.append(
                    f"live evidence index: {source_id} invalid http_status"
                )
            byte_size = response.get("byte_size")
            if (
                not isinstance(byte_size, int)
                or isinstance(byte_size, bool)
                or byte_size < 0
            ):
                errors.append(
                    f"live evidence index: {source_id} invalid byte_size"
                )
            digest = str(response.get("sha256") or "")
            if not re.fullmatch(r"[0-9a-f]{64}", digest):
                errors.append(
                    f"live evidence index: {source_id} invalid sha256"
                )
            for key in (
                "url",
                "final_url",
                "source_url",
                "carrier_url",
                "detail_url",
                "attachment_url",
            ):
                value = response.get(key)
                if value is None:
                    continue
                reason = _unsafe_url_reason(str(value))
                if reason:
                    errors.append(
                        f"live evidence index: {source_id} {key}: {reason}"
                    )
    for value in _walk_strings(payload):
        for url in URL_PATTERN.findall(value):
            reason = _unsafe_url_reason(url)
            if reason:
                errors.append(
                    f"live evidence index: {reason}: {url}"
                )
    for key_path, value in _walk_keys(payload):
        if key_path and key_path[-1] in forbidden_keys:
            errors.append(
                "live evidence index: raw body field "
                + ".".join(str(part) for part in key_path)
            )
    text = raw.decode("utf-8", errors="ignore")
    for marker in (
        "%TEMP%",
        "AppData\\Local\\Temp",
        "AppData/Local/Temp",
        "X-Amz-",
        "Set-Cookie",
        "Cookie:",
        "Authorization:",
        "access_token=",
        "api_key=",
        "<html",
        "<!doctype",
    ):
        if marker.lower() in text.lower():
            errors.append(
                f"live evidence index: forbidden public marker {marker}"
            )
    scan_text = re.sub(
        r"\b[0-9a-f]{64}\b",
        "<sha256>",
        text,
        flags=re.IGNORECASE,
    )
    findings = scan_fixture_bytes(path.name, scan_text.encode("utf-8"))
    if findings:
        errors.append(
            "live evidence index: hygiene findings "
            + ", ".join(findings)
        )
    return errors


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive-root")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args(argv)
    if args.validate_only:
        errors = validate_live_evidence_index(args.output)
        if errors:
            for error in errors:
                print(error)
            return 1
        print("live evidence index passed")
        return 0
    if not args.archive_root:
        parser.error("--archive-root is required unless --validate-only is used")
    payload = build_live_evidence_index(args.archive_root, args.output)
    errors = validate_live_evidence_index(args.output)
    if errors:
        for error in errors:
            print(error)
        return 1
    print(
        f"live evidence index written: {args.output} "
        f"({payload['source_count']} sources)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
