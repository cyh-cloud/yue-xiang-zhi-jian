"""Site-specific fixture replay for ihchina through a real Scrapy crawl."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import fields
from pathlib import Path

from crawler.collection.shared.crawler_collection.reporting import (
    RunReport,
    build_run_report,
)
from crawler.collection.shared.crawler_collection.run_id import new_run_id
from crawler.collection.shared.crawler_collection.testing import (
    source_fixture_dir,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[5]
REPORT_MARKER = "REPORT_JSON:"


def _require_fixture_dir(fixture_dir):
    actual = Path(fixture_dir).resolve()
    expected = source_fixture_dir("ihchina").resolve()
    if actual != expected:
        raise ValueError(f"fixture directory must be {expected.as_posix()}")
    return expected


def _project_env():
    existing = os.environ.get("PYTHONPATH", "")
    entries = [str(REPO_ROOT), str(PROJECT_ROOT)]
    if existing:
        entries.append(existing)
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(entries)
    return env


def replay_ihchina_fixture(
    *,
    fixture_dir,
    database_path,
    download_root,
    registry_path,
    run_id=None,
    report_root=None,
):
    fixture_dir = _require_fixture_dir(fixture_dir)
    database_path = Path(database_path).resolve()
    download_root = Path(download_root).resolve()
    registry_path = Path(registry_path).resolve()
    run_id = run_id or new_run_id("ihchina")
    report_root = (
        Path(report_root).resolve()
        if report_root
        else (database_path.parent / "reports")
    )
    command = [
        sys.executable,
        "-m",
        "ihchina.replay",
        "--worker",
        "--fixture-dir",
        str(fixture_dir),
        "--database-path",
        str(database_path),
        "--download-root",
        str(download_root),
        "--registry-path",
        str(registry_path),
        "--run-id",
        run_id,
        "--report-root",
        str(report_root),
    ]
    try:
        completed = subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            env=_project_env(),
            text=True,
            capture_output=True,
            timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return RunReport(
            run_id=run_id,
            source_id="ihchina",
            mode="fixture",
            discovered=0,
            failed=1,
            errors=(f"{type(exc).__name__}: {exc}",),
        )
    payload = None
    for line in completed.stdout.splitlines():
        if line.startswith(REPORT_MARKER):
            payload = json.loads(line[len(REPORT_MARKER):])
    if completed.returncode != 0 or payload is None:
        detail = (completed.stderr or completed.stdout).strip()
        return RunReport(
            run_id=run_id,
            source_id="ihchina",
            mode="fixture",
            discovered=0,
            failed=1,
            errors=(detail[-2000:] or "Scrapy replay failed",),
        )
    names = {field.name for field in fields(RunReport)}
    return RunReport(**{key: value for key, value in payload.items() if key in names})


def _run_worker(args):
    from scrapy.crawler import CrawlerProcess
    from scrapy.settings import Settings
    from scrapy import signals

    from . import settings as project_settings
    from .spiders.collection import IhchinaSpider

    settings = Settings()
    settings.setmodule(project_settings)
    settings.set("COLLECTION_DATABASE_PATH", args.database_path)
    settings.set("COLLECTION_DOWNLOAD_ROOT", args.download_root)
    settings.set("SOURCE_REGISTRY_PATH", args.registry_path)
    settings.set("COLLECTION_REPORT_ROOT", args.report_root)
    settings.set("IHCHINA_FIXTURE_DIR", args.fixture_dir)
    settings.set("ROBOTSTXT_OBEY", False)
    settings.set("RETRY_TIMES", 0)
    settings.set("LOG_ENABLED", False)
    settings.set("TELNETCONSOLE_ENABLED", False)
    settings.set("EXTENSIONS", {})
    middlewares = dict(settings.getdict("DOWNLOADER_MIDDLEWARES"))
    middlewares[
        "ihchina.fixture_downloader.IhchinaFixtureDownloaderMiddleware"
    ] = 900
    settings.set("DOWNLOADER_MIDDLEWARES", middlewares)

    errors = []
    process = CrawlerProcess(settings)
    crawler = process.create_crawler(IhchinaSpider)

    def spider_error(failure, response, spider):
        errors.append(f"{type(failure.value).__name__}: {failure.value}")

    def item_error(item, response, spider, failure):
        errors.append(f"pipeline: {type(failure.value).__name__}: {failure.value}")

    crawler.signals.connect(spider_error, signal=signals.spider_error)
    crawler.signals.connect(item_error, signal=signals.item_error)
    process.crawl(crawler, run_id=args.run_id)
    process.start(stop_after_crawl=True)

    spider = crawler.spider
    item_counts = dict(getattr(spider, "_collection_counts", {}) or {})
    item_counts["failed"] = len(errors)
    item_counts["discovered"] = len(
        json.loads(
            (Path(args.fixture_dir) / "discover.json").read_text(
                encoding="utf-8"
            )
        ).get("list", [])
    )
    request_count = 0
    if crawler.stats is not None:
        request_count = crawler.stats.get_value(
            "downloader/request_count", 0
        )
    report = build_run_report(
        run_id=args.run_id,
        source_id="ihchina",
        mode="fixture",
        database_path=args.database_path,
        request_count=request_count,
        item_counts=item_counts,
        errors=errors,
        evidence_path=args.download_root,
        report_root=args.report_root,
    )
    print(REPORT_MARKER + json.dumps(report.to_dict(), ensure_ascii=False))
    return 0


def _main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--fixture-dir", required=True)
    parser.add_argument("--database-path", required=True)
    parser.add_argument("--download-root", required=True)
    parser.add_argument("--registry-path", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--report-root", required=True)
    args = parser.parse_args(argv)
    if args.worker:
        return _run_worker(args)
    parser.error("this module is invoked as the ihchina replay worker")


if __name__ == "__main__":
    raise SystemExit(_main())
