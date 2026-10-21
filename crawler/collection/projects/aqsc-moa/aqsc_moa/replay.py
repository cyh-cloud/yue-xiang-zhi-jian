"""aqsc-moa fixture replay through a real Scrapy process."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import fields
from pathlib import Path

from scrapy.crawler import CrawlerProcess
from scrapy.settings import Settings

from crawler.collection.shared.crawler_collection.reporting import RunReport
from crawler.collection.shared.crawler_collection.run_id import new_run_id
from crawler.collection.shared.crawler_collection.testing import (
    FixtureHTTPServer,
    source_fixture_dir,
)

from . import settings as project_settings
from .parsers import XLSX_MIME_TYPE
from .spiders.collection import AqscMoaSpider


SOURCE_ID = "aqsc-moa"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[5]


def _require_fixture_dir(fixture_dir):
    actual = Path(fixture_dir).resolve()
    expected = source_fixture_dir(SOURCE_ID).resolve()
    if actual != expected:
        raise ValueError(f"fixture directory must be {expected.as_posix()}")
    return expected


def _manifest_url(fixture_dir, server, manifest_name="discover.json"):
    payload = json.loads(
        (fixture_dir / manifest_name).read_text(encoding="utf-8")
    )
    items = []
    for item in payload.get("items") or []:
        file_name = item.get("file_name")
        carrier_route = f"/carriers/{item['source_item_id']}.html"
        if file_name:
            file_path = fixture_dir / file_name
            file_route = f"/files/{file_name}"
            server.add_route(
                file_route,
                file_path.read_bytes(),
                content_type=XLSX_MIME_TYPE,
            )
        else:
            file_route = None

        carrier_file = item.get("carrier_file")
        if carrier_file:
            carrier_html = (fixture_dir / carrier_file).read_text(
                encoding="utf-8"
            )
        else:
            if not file_name:
                raise ValueError(
                    "fixture item needs file_name or carrier_file"
                )
            carrier_html = (
                "<!doctype html><html><head><meta charset=\"utf-8\">"
                "<meta name=\"fixture-origin\" content=\"synthetic-fixture\">"
                f"<title>{item.get('title') or item['source_item_id']}</title>"
                "</head><body>"
                f"<h1>{item.get('title') or item['source_item_id']}</h1>"
                f"<a class=\"attachment\" href=\"{file_route}\">"
                f"{file_name}</a>"
                "</body></html>"
            )
        server.add_route(
            carrier_route,
            carrier_html.encode("utf-8"),
            content_type="text/html; charset=utf-8",
        )
        replay_item = {
            **item,
            "carrier_url": server.url(carrier_route),
            "file_source_url": item.get("source_url"),
        }
        if file_route:
            replay_item["file_url"] = server.url(file_route)
        items.append(replay_item)
    manifest = {**payload, "items": items}
    server.add_route(
        "/discover.json",
        json.dumps(manifest, ensure_ascii=False).encode("utf-8"),
        content_type="application/json",
    )
    return server.url("/discover.json")


def _run_fixture_process(args):
    fixture_dir = Path(args.fixture_dir).resolve()
    database_path = Path(args.database_path).resolve()
    download_root = Path(args.download_root).resolve()
    registry_path = Path(args.registry_path).resolve()
    report_root = Path(args.report_root).resolve()
    with FixtureHTTPServer() as server:
        start_url = _manifest_url(
            fixture_dir, server, args.manifest_name
        )
        settings = Settings()
        settings.setmodule(project_settings)
        settings.set("COLLECTION_DATABASE_PATH", str(database_path))
        settings.set("COLLECTION_DOWNLOAD_ROOT", str(download_root))
        settings.set("SOURCE_REGISTRY_PATH", str(registry_path))
        settings.set("COLLECTION_REPORT_ROOT", str(report_root))
        settings.set("COLLECTION_RUN_MODE", "fixture")
        settings.set("DOWNLOAD_DELAY", 0)
        settings.set("RETRY_TIMES", 0)
        settings.set("LOG_LEVEL", "ERROR")
        process = CrawlerProcess(
            settings, install_root_handler=False
        )
        process.crawl(
            AqscMoaSpider,
            start_urls=[start_url],
            run_id=args.run_id,
        )
        process.start(stop_after_crawl=True)


def _report_from_file(path):
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    allowed = {field.name for field in fields(RunReport)}
    return RunReport(
        **{key: value for key, value in payload.items() if key in allowed}
    )


def replay_aqsc_fixture(
    *,
    fixture_dir,
    database_path,
    download_root,
    registry_path,
    run_id=None,
    report_root=None,
    manifest_name="discover.json",
):
    """Replay aqsc-moa fixtures through Spider, middleware, and Pipeline."""

    fixture_dir = _require_fixture_dir(fixture_dir)
    run_id = run_id or new_run_id(SOURCE_ID)
    database_path = Path(database_path).resolve()
    download_root = Path(download_root).resolve()
    registry_path = Path(registry_path).resolve()
    report_root = Path(
        report_root or database_path.parent / "reports"
    ).resolve()
    report_root.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        [
            str(REPO_ROOT),
            str(PROJECT_ROOT),
            env.get("PYTHONPATH", ""),
        ]
    )
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "aqsc_moa.replay",
            "--run-fixture",
            "--fixture-dir",
            str(fixture_dir),
            "--database-path",
            str(database_path),
            "--download-root",
            str(download_root),
            "--registry-path",
            str(registry_path),
            "--report-root",
            str(report_root),
            "--run-id",
            run_id,
            "--manifest-name",
            manifest_name,
        ],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=90,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "aqsc-moa fixture replay failed\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )
    report_path = report_root / f"{run_id}.json"
    if not report_path.is_file():
        raise RuntimeError(
            f"fixture replay did not write report: {report_path}"
        )
    return _report_from_file(report_path)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-fixture", action="store_true")
    parser.add_argument("--fixture-dir", required=True)
    parser.add_argument("--database-path", required=True)
    parser.add_argument("--download-root", required=True)
    parser.add_argument("--registry-path", required=True)
    parser.add_argument("--report-root", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument(
        "--manifest-name", default="discover.json"
    )
    args = parser.parse_args(argv)
    if not args.run_fixture:
        parser.error("--run-fixture is required")
    _run_fixture_process(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
