"""Structured, auditable run reports for fixture and live collection."""

from __future__ import annotations

import json
import logging
import sqlite3
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from importlib import import_module
from pathlib import Path

from scrapy import signals


logger = logging.getLogger(__name__)
CANDIDATE_TABLES = (
    "std_agri_products",
    "std_ich_projects",
    "std_jobs",
    "std_dialect_points",
    "std_ich_articles",
    "std_research_articles",
)


@dataclass(frozen=True)
class RunReport:
    run_id: str
    source_id: str
    mode: str
    discovered: int
    written: int = 0
    skipped: int = 0
    failed: int = 0
    blocked: int = 0
    deferred: int = 0
    errors: tuple[str, ...] = ()
    started_at: str | None = None
    finished_at: str | None = None
    request_count: int = 0
    raw_count: int = 0
    stage_count: int = 0
    evidence_path: str | None = None
    report_path: str | None = None
    failure_reason: str | None = None

    @property
    def candidate_count(self):
        return self.written

    @property
    def failure_count(self):
        return self.failed

    @property
    def status(self):
        if self.discovered == 0 and not (
            self.blocked or self.deferred or self.skipped or self.failed
        ):
            return "failed"
        if (
            self.written == 0
            and self.blocked == 0
            and self.deferred == 0
            and self.skipped == 0
        ):
            return "failed"
        if self.failed or self.skipped or self.blocked or self.deferred:
            return "partial"
        return "succeeded"

    def to_dict(self):
        return {
            **asdict(self),
            "candidate_count": self.candidate_count,
            "failure_count": self.failure_count,
            "status": self.status,
        }


def _count_rows(conn, table, run_id):
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    ).fetchone()
    if not exists:
        return 0
    return conn.execute(
        f"SELECT COUNT(*) FROM {table} WHERE run_id = ?",
        (run_id,),
    ).fetchone()[0]


def collection_counts(database_path, run_id):
    conn = sqlite3.connect(Path(database_path))
    try:
        raw_count = _count_rows(conn, "raw_fetches", run_id)
        stage_count = _count_rows(conn, "stage_source_items", run_id)
        candidate_rows = 0
        candidate_states = {}
        for table in CANDIDATE_TABLES:
            exists = conn.execute(
                "SELECT 1 FROM sqlite_master "
                "WHERE type = 'table' AND name = ?",
                (table,),
            ).fetchone()
            if not exists:
                continue
            candidate_rows += _count_rows(conn, table, run_id)
            for status, count in conn.execute(
                f"SELECT candidate_status, COUNT(*) FROM {table} "
                "WHERE run_id = ? GROUP BY candidate_status",
                (run_id,),
            ):
                candidate_states[status] = (
                    candidate_states.get(status, 0) + count
                )
    finally:
        conn.close()
    return {
        "raw_count": raw_count,
        "stage_count": stage_count,
        "candidate_count": candidate_states.get("candidate", 0),
        "candidate_rows": candidate_rows,
        "candidate_states": candidate_states,
    }


def _report_path(report_root, run_id):
    safe_name = "".join(
        character if character.isalnum() or character in "-_." else "-"
        for character in run_id
    )
    return Path(report_root) / f"{safe_name}.json"


def _failure_reason(reasons):
    if not reasons:
        return None
    counts = Counter(reasons)
    parts = [
        f"{reason} (x{count})" if count > 1 else reason
        for reason, count in counts.items()
    ]
    return "; ".join(parts)


def write_run_report(report, report_root):
    path = _report_path(report_root, report.run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def build_run_report(
    *,
    run_id,
    source_id,
    mode,
    database_path,
    started_at=None,
    finished_at=None,
    request_count=0,
    item_counts=None,
    errors=(),
    failure_reason=None,
    evidence_path=None,
    report_root=None,
):
    counts = collection_counts(database_path, run_id)
    item_counts = item_counts or {}
    report_root = report_root or Path(database_path).parent / "reports"
    path = _report_path(report_root, run_id)
    written = item_counts.get(
        "written", counts["candidate_states"].get("candidate", 0)
    )
    blocked = item_counts.get(
        "blocked", counts["candidate_states"].get("blocked", 0)
    )
    deferred = item_counts.get(
        "deferred", counts["candidate_states"].get("deferred", 0)
    )
    skipped = item_counts.get("skipped", 0)
    failed = item_counts.get("failed", 0)
    if "discovered" in item_counts:
        discovered = item_counts["discovered"]
    elif item_counts:
        discovered = written + blocked + deferred + skipped + failed
    else:
        discovered = counts["candidate_rows"] + skipped + failed

    report = RunReport(
        run_id=run_id,
        source_id=source_id,
        mode=mode,
        discovered=discovered,
        written=written,
        skipped=skipped,
        failed=failed,
        blocked=blocked,
        deferred=deferred,
        errors=tuple(errors),
        started_at=started_at,
        finished_at=finished_at or datetime.now(timezone.utc).isoformat(),
        request_count=request_count,
        raw_count=counts["raw_count"],
        stage_count=counts["stage_count"],
        evidence_path=str(evidence_path) if evidence_path else None,
        report_path=str(path),
        failure_reason=failure_reason or _failure_reason(errors),
    )
    write_run_report(report, report_root)
    return report


def record_pipeline_result(spider, result):
    counts = getattr(spider, "_collection_counts", None)
    if counts is None:
        counts = {}
        spider._collection_counts = counts
    status = result.get("candidate_status") or "failed"
    key = {
        "candidate": "written",
        "blocked": "blocked",
        "deferred": "deferred",
        "skipped": "skipped",
    }.get(status, "failed")
    counts[key] = counts.get(key, 0) + 1


def _load_candidate_writer(dotted_path):
    if not dotted_path:
        return None
    module_name, attribute = dotted_path.rsplit(".", 1)
    return getattr(import_module(module_name), attribute)


class RunReportExtension:
    """Create one report for each Scrapy crawl and persist it as JSON."""

    def __init__(self, crawler):
        self.crawler = crawler
        self.settings = crawler.settings
        self.started_at = None
        self.request_count = 0
        self.errors = []
        self._failed_requests = set()
        self._failure_reasons = []
        self._item_failures = 0
        self._unattributed_spider_failures = 0
        crawler.signals.connect(self.spider_opened, signal=signals.spider_opened)
        crawler.signals.connect(self.spider_closed, signal=signals.spider_closed)
        crawler.signals.connect(
            self.request_scheduled, signal=signals.request_scheduled
        )
        crawler.signals.connect(
            self.response_received, signal=signals.response_received
        )
        crawler.signals.connect(self.spider_error, signal=signals.spider_error)
        crawler.signals.connect(self.item_error, signal=signals.item_error)

    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler)

    def spider_opened(self, spider):
        self.started_at = datetime.now(timezone.utc).isoformat()

    def request_scheduled(self, request, spider):
        if not request.meta.get("dont_obey_robotstxt"):
            self.request_count += 1

    def response_received(self, response, request, spider):
        if request.meta.get("dont_obey_robotstxt"):
            return
        if response.status >= 400:
            self._failed_requests.add(request)
            self._failure_reasons.append(
                f"HTTP {response.status}: {response.url}"
            )

    def spider_error(self, failure, response, spider):
        message = f"{type(failure.value).__name__}: {failure.value}"
        self.errors.append(message)
        self._failure_reasons.append(message)
        request = getattr(response, "request", None)
        if request is not None:
            self._failed_requests.add(request)
        else:
            self._unattributed_spider_failures += 1
        self._persist_parse_failure(response, failure, spider)

    def _persist_parse_failure(self, response, failure, spider):
        if response is None:
            return
        request = getattr(response, "request", None)
        meta = getattr(response, "meta", {}) or {}
        raw_evidence_id = meta.get("raw_evidence_id")
        if request is None or not raw_evidence_id:
            return
        try:
            from .runtime import CollectionRuntime

            runtime = CollectionRuntime(
                database_path=self.settings[
                    "COLLECTION_DATABASE_PATH"
                ],
                download_root=(
                    self.settings.get("COLLECTION_DOWNLOAD_ROOT")
                    or Path(
                        self.settings["COLLECTION_DATABASE_PATH"]
                    ).parent / "download"
                ),
                registry_path=self.settings.get(
                    "SOURCE_REGISTRY_PATH"
                ),
                candidate_writer=_load_candidate_writer(
                    self.settings.get("COLLECTION_CANDIDATE_WRITER")
                ),
            )
            reason = (
                f"parse_error:{type(failure.value).__name__}: "
                f"{failure.value}"
            )[:500]
            detail_url = meta.get("detail_url")
            source_url = meta.get("source_url") or request.url
            result = runtime.write_item(
                {
                    "source_id": spider.source_id,
                    "source_item_id": (
                        meta.get("source_item_id")
                        or f"parse-error:{request.url}"
                    ),
                    "source_url": source_url,
                    "long_term_url": (
                        meta.get("long_term_url") or source_url
                    ),
                    "detail_url": detail_url,
                    "detail_url_status": (
                        "direct" if detail_url else "missing"
                    ),
                    "fetch_url": request.url,
                    "locator": meta.get("locator"),
                    "run_id": meta.get("run_id") or spider.run_id,
                    "mode": self.settings.get(
                        "COLLECTION_RUN_MODE", "live"
                    ),
                    "title": (
                        meta.get("title")
                        or f"parse-error:{type(failure.value).__name__}"
                    ),
                    "candidate_status": "blocked",
                    "candidate_reason": reason,
                    "raw_evidence_id": raw_evidence_id,
                    "extra": {
                        "parse_error_type": type(
                            failure.value
                        ).__name__,
                        "parse_error_message": str(failure.value),
                    },
                },
                raw_evidence_id=raw_evidence_id,
            )
            if result.get("candidate_reason") == (
                "candidate_writer:missing"
            ):
                raise RuntimeError("candidate_writer:missing")
            record_pipeline_result(spider, result)
        except Exception as exc:
            persistence_error = (
                "parse_failure_persist:"
                f"{type(exc).__name__}: {exc}"
            )
            self.errors.append(persistence_error)
            self._failure_reasons.append(persistence_error)

    def item_error(self, item, response, spider, failure):
        self._item_failures += 1
        self._failure_reasons.append(
            f"pipeline: {type(failure.value).__name__}: {failure.value}"
        )

    def spider_closed(self, spider, reason):
        if not getattr(spider, "run_id", None):
            return
        stats = self.crawler.stats
        downloader_failures = 0
        robots_blocked = 0
        for key, value in (stats.get_stats() if stats else {}).items():
            if (
                key.startswith("downloader/exception_count/")
                or key.startswith("spider_exceptions/")
                or key == "robotstxt/forbidden"
            ) and value:
                self.errors.append(f"{key}={value}")
            if key.startswith("downloader/exception_count/") and value:
                downloader_failures += int(value)
                self._failure_reasons.append(
                    f"{key}={value}"
                )
            if key == "robotstxt/forbidden" and value:
                robots_blocked += int(value)
                self._failure_reasons.append(f"{key}={value}")
        item_counts = dict(getattr(spider, "_collection_counts", {}))
        item_counts["blocked"] = (
            int(item_counts.get("blocked", 0)) + robots_blocked
        )
        pipeline_failures = int(item_counts.get("failed", 0))
        request_failures = len(self._failed_requests)
        failed = (
            pipeline_failures
            + request_failures
            + self._item_failures
            + self._unattributed_spider_failures
            + downloader_failures
        )
        item_counts["failed"] = failed
        if failed and not self._failure_reasons:
            self._failure_reasons.append("pipeline_failure")
        database_path = self.settings["COLLECTION_DATABASE_PATH"]
        report = build_run_report(
            run_id=spider.run_id,
            source_id=spider.source_id,
            mode=self.settings.get("COLLECTION_RUN_MODE", "live"),
            database_path=database_path,
            started_at=self.started_at,
            finished_at=datetime.now(timezone.utc).isoformat(),
            request_count=self.request_count,
            item_counts=item_counts,
            errors=self.errors,
            failure_reason=_failure_reason(self._failure_reasons),
            evidence_path=self.settings.get("COLLECTION_DOWNLOAD_ROOT"),
            report_root=self.settings.get("COLLECTION_REPORT_ROOT"),
        )
        spider.run_report = report
        logger.info(
            "collection run report: %s",
            report.report_path,
            extra={"spider": spider},
        )
