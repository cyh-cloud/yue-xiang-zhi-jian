"""Run the aqsc-moa live file-source canary."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from scrapy.crawler import CrawlerProcess
from scrapy.settings import Settings

from crawler.collection.shared.crawler_collection.run_id import new_run_id

from . import settings as project_settings
from .spiders.collection import AqscMoaSpider


SOURCE_ID = "aqsc-moa"


def run_live_sample(
    *,
    database_path,
    download_root,
    registry_path,
    report_root,
    start_urls=None,
    run_id=None,
):
    if isinstance(start_urls, str):
        start_urls = [start_urls]
    else:
        start_urls = list(start_urls or ())
    if not start_urls or any(
        not isinstance(url, str) or not url.strip() for url in start_urls
    ):
        raise ValueError(
            "run_live_sample requires at least one explicit start URL"
        )

    database_path = Path(database_path).resolve()
    download_root = Path(download_root).resolve()
    registry_path = Path(registry_path).resolve()
    report_root = Path(report_root).resolve()
    run_id = run_id or new_run_id(SOURCE_ID)
    settings = Settings()
    settings.setmodule(project_settings)
    settings.set("COLLECTION_DATABASE_PATH", str(database_path))
    settings.set("COLLECTION_DOWNLOAD_ROOT", str(download_root))
    settings.set("SOURCE_REGISTRY_PATH", str(registry_path))
    settings.set("COLLECTION_REPORT_ROOT", str(report_root))
    settings.set("COLLECTION_RUN_MODE", "live")
    settings.set("LOG_LEVEL", "ERROR")
    process = CrawlerProcess(settings, install_root_handler=False)
    process.crawl(
        AqscMoaSpider,
        start_urls=start_urls,
        run_id=run_id,
    )
    process.start(stop_after_crawl=True)
    report_path = report_root / f"{run_id}.json"
    return run_id, report_path


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-path", required=True)
    parser.add_argument("--download-root", required=True)
    parser.add_argument("--registry-path", required=True)
    parser.add_argument("--report-root", required=True)
    parser.add_argument("--run-id")
    parser.add_argument("--start-url", action="append", required=True)
    args = parser.parse_args(argv)
    run_id, report_path = run_live_sample(
        database_path=args.database_path,
        download_root=args.download_root,
        registry_path=args.registry_path,
        report_root=args.report_root,
        start_urls=args.start_url,
        run_id=args.run_id,
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    print(
        json.dumps(
            {
                "run_id": run_id,
                "report_path": str(report_path),
                "report": report,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
