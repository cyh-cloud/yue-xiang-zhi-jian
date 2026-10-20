"""Structured, auditable run reports for fixture and live collection."""

from __future__ import annotations

import json
import logging
import sqlite3
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
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
        if self.discovered == 0 or self.written == 0 and self.blocked == 0:
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
        candidate_count = 0
        candidate_states = {}
        for table in CANDIDATE_TABLES:
            exists = conn.execute(
                "SELECT 1 FROM sqlite_master "
                "WHERE type = 'table' AND name = ?",
                (table,),
            ).fetchone()
            if not exists:
                continue
            candidate_count += _count_rows(conn, table, run_id)
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
        "candidate_count": candidate_count,
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
    report = RunReport(
        run_id=run_id,
        source_id=source_id,
        mode=mode,
        discovered=item_counts.get(
            "discovered",
            counts["candidate_count"]
            + item_counts.get("blocked", 0)
            + item_counts.get("deferred", 0)
            + item_counts.get("skipped", 0)
            + item_counts.get("failed", 0),
        ),
        written=item_counts.get("written", counts["candidate_count"]),
        skipped=item_counts.get("skipped", 0),
        failed=item_counts.get("failed", 0),
        blocked=item_counts.get("blocked", 0),
        deferred=item_counts.get("deferred", 0),
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
        item_counts = dict(getattr(spider, "_collection_counts", {}))
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
            mode="live",
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
