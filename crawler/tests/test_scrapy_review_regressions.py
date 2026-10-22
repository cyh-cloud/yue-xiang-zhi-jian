import importlib
import hashlib
import json
import sqlite3
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from types import SimpleNamespace

import scrapy
from scrapy.crawler import CrawlerProcess
from scrapy.exceptions import IgnoreRequest
from scrapy.http import HtmlResponse, Request
from scrapy.settings import Settings

from crawler.collection.shared.crawler_collection.admission import (
    evaluate_admission,
)
from crawler.collection.shared.crawler_collection.evidence import RawEvidence
from crawler.collection.shared.crawler_collection.database import (
    CollectionDatabase,
)
from crawler.collection.shared.crawler_collection.items import CollectionItem
from crawler.collection.shared.crawler_collection.middlewares import (
    RawEvidenceMiddleware,
)
from crawler.collection.shared.crawler_collection.projects import (
    discover_projects,
    executable_source_ids,
)
from crawler.collection.shared.crawler_collection.registry import load_registry
from crawler.collection.shared.crawler_collection.robots import RobotsFact
from crawler.collection.shared.crawler_collection.robots import (
    robots_fact_from_status,
)
from crawler.collection.shared.crawler_collection.runtime import CollectionRuntime
from crawler.collection.shared.crawler_collection.reporting import (
    RunReportExtension,
)
from crawler.collection.shared.crawler_collection.spiders import (
    CollectionSpiderMixin,
)
from crawler.collection.shared.crawler_collection.testing import (
    source_fixture_dir,
)


ROOT = Path(__file__).resolve().parents[1]
PROJECTS = ROOT / "collection" / "projects"
REGISTRY = ROOT / "docs" / "sources.json"


SOURCE_EXPECTATIONS = {
    "ihchina": {
        "replay_function": "replay_ihchina_fixture",
        "status": "succeeded",
        "candidates": 2,
        "report_candidates": 2,
        "stage_count": 2,
        "blocked": 0,
        "table": "std_ich_projects",
        "column": "protection_unit",
        "value": "示例保护单位",
        "candidate_status": "candidate",
        "file_extensions": (),
        "job_relations": False,
        "stage_extra_media": None,
        "stage_extra_keys": (),
    },
    "nzrc": {
        "replay_function": "replay_nzrc_fixture",
        "status": "succeeded",
        "candidates": 2,
        "report_candidates": 2,
        "stage_count": 2,
        "blocked": 0,
        "table": "std_jobs",
        "column": "company_url",
        "value": "http://www.nzrc.com.cn/company/companys/90001.html",
        "candidate_status": "candidate",
        "file_extensions": (),
        "job_relations": True,
        "stage_extra_media": None,
        "stage_extra_keys": (),
    },
    "nongmuhr": {
        "replay_function": "replay_nongmuhr_fixture",
        "status": "succeeded",
        "candidates": 2,
        "report_candidates": 2,
        "stage_count": 2,
        "blocked": 0,
        "table": "std_jobs",
        "column": "deadline_at",
        "value": "2026-12-31",
        "candidate_status": "candidate",
        "file_extensions": (),
        "job_relations": True,
        "stage_extra_media": None,
        "stage_extra_keys": (),
    },
    "dialect-org": {
        "replay_function": "replay_dialect_fixture",
        "status": "succeeded",
        "candidates": 1,
        "report_candidates": 1,
        "stage_count": 1,
        "blocked": 0,
        "table": "std_dialect_points",
        "column": "city",
        "value": "广州",
        "candidate_status": "candidate",
        "file_extensions": (),
        "job_relations": False,
        "stage_extra_media": None,
        "stage_extra_keys": (),
    },
    "cass-linguistics": {
        "replay_function": "replay_cass_fixture",
        "status": "succeeded",
        "candidates": 1,
        "report_candidates": 1,
        "stage_count": 1,
        "blocked": 0,
        "table": "std_research_articles",
        "column": "summary",
        "value": "公开摘要",
        "candidate_status": "candidate",
        "file_extensions": (),
        "job_relations": False,
        "stage_extra_media": "中国社会科学网",
        "stage_extra_keys": (),
    },
    "feiyiw": {
        "replay_function": "replay_feiyiw_fixture",
        "status": "succeeded",
        "candidates": 1,
        "report_candidates": 1,
        "stage_count": 1,
        "blocked": 0,
        "table": "std_ich_articles",
        "column": "body_text",
        "value": "公开正文",
        "candidate_status": "candidate",
        "file_extensions": (),
        "job_relations": False,
        "stage_extra_media": None,
        "stage_extra_keys": ("supplementary",),
    },
    "aqsc-moa": {
        "replay_function": "replay_aqsc_fixture",
        "status": "partial",
        "candidates": 8,
        "report_candidates": 0,
        "stage_count": 8,
        "blocked": 0,
        "table": "std_agri_products",
        "column": "product_name",
        "value": "示例鲅鱼圈鸡蛋",
        "candidate_status": "deferred",
        "file_extensions": (".xlsx", ".pdf"),
        "job_relations": False,
        "stage_extra_media": None,
        "stage_extra_keys": (),
    },
    "cnipa": {
        "replay_function": "replay_cnipa_fixture",
        "status": "partial",
        "candidates": 2,
        "report_candidates": 0,
        "stage_count": 2,
        "blocked": 0,
        "table": "std_agri_products",
        "column": "product_name",
        "value": "Sample Pomegranate",
        "candidate_status": "deferred",
        "file_extensions": (".xlsx", ".pdf"),
        "job_relations": False,
        "stage_extra_media": None,
        "stage_extra_keys": (),
    },
}


def _item(**overrides):
    payload = {
        "source_id": "ihchina",
        "source_item_id": "1",
        "source_url": "https://example.test/1",
        "long_term_url": "https://example.test/1",
        "detail_url": "https://example.test/1",
        "detail_url_status": "direct",
        "run_id": "run-1",
        "mode": "fixture",
        "rights_status": "attribution-required",
        "title": "示例条目",
    }
    payload.update(overrides)
    return CollectionItem(**payload)


class ProjectSettingsPathTest(unittest.TestCase):
    def test_all_project_paths_resolve_below_crawler_root(self):
        for project_root in sorted(PROJECTS.iterdir()):
            if not (project_root / "scrapy.cfg").is_file():
                continue
            package = project_root.name.replace("-", "_")
            sys.path.insert(0, str(project_root))
            settings = importlib.import_module(f"{package}.settings")

            database_path = Path(settings.COLLECTION_DATABASE_PATH)
            registry_path = Path(settings.SOURCE_REGISTRY_PATH)

            self.assertEqual(Path(settings.CRAWLER_ROOT), ROOT)
            self.assertEqual(Path(settings.REPO_ROOT), ROOT.parent)
            self.assertEqual(
                database_path,
                ROOT / "data" / "crawler.db",
                project_root.name,
            )
            self.assertEqual(
                Path(settings.COLLECTION_DOWNLOAD_ROOT),
                ROOT / "download",
                project_root.name,
            )
            self.assertEqual(
                Path(settings.COLLECTION_REPORT_ROOT),
                ROOT / "data" / "reports",
                project_root.name,
            )
            self.assertEqual(registry_path, REGISTRY, project_root.name)
            self.assertTrue(registry_path.is_file(), project_root.name)


class ProjectFixtureReplayTest(unittest.TestCase):
    def _discover_projects_with_expectations(self):
        projects = discover_projects(PROJECTS, REGISTRY)
        registry_source_ids = executable_source_ids(load_registry(REGISTRY))
        self.assertEqual(set(projects), registry_source_ids)
        self.assertEqual(set(SOURCE_EXPECTATIONS), registry_source_ids)
        return projects

    def test_every_project_replays_from_its_entry_with_expected_counts(self):
        projects = self._discover_projects_with_expectations()
        for source_id, project in sorted(projects.items()):
            expected = SOURCE_EXPECTATIONS[source_id]
            with self.subTest(source_id=source_id):
                sys.path.insert(0, str(project.root))
                replay = getattr(
                    importlib.import_module(
                        f"{project.package_path.name}.replay"
                    ),
                    expected["replay_function"],
                )
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    kwargs = {
                        "fixture_dir": source_fixture_dir(source_id),
                        "database_path": root / "crawler.db",
                        "download_root": root / "downloads",
                        "registry_path": REGISTRY,
                    }
                    first = replay(**kwargs)
                    second = replay(**kwargs)
                    self.assertEqual(first.status, expected["status"])
                    self.assertEqual(second.status, expected["status"])
                    self.assertEqual(
                        first.candidate_count,
                        expected["report_candidates"],
                    )
                    self.assertEqual(
                        second.candidate_count,
                        expected["report_candidates"],
                    )
                    self.assertEqual(
                        first.stage_count,
                        expected["stage_count"],
                    )
                    self.assertEqual(
                        second.stage_count,
                        expected["stage_count"],
                    )
                    self.assertEqual(first.blocked, expected["blocked"])
                    self.assertEqual(second.blocked, expected["blocked"])
                    conn = sqlite3.connect(root / "crawler.db")
                    try:
                        raw_count = conn.execute(
                            "SELECT COUNT(*) FROM raw_fetches "
                            "WHERE source_id = ?",
                            (source_id,),
                        ).fetchone()[0]
                        stage_count = conn.execute(
                            "SELECT COUNT(*) FROM stage_source_items "
                            "WHERE source_id = ?",
                            (source_id,),
                        ).fetchone()[0]
                        stage_extra = json.loads(
                            conn.execute(
                                "SELECT extra FROM stage_source_items "
                                "WHERE source_id = ? ORDER BY id LIMIT 1",
                                (source_id,),
                            ).fetchone()[0]
                        )
                        file_extensions = expected["file_extensions"]
                        if file_extensions:
                            allowed_extensions = ", ".join(
                                f"'{extension}'"
                                for extension in file_extensions
                            )
                            file_filter = (
                                " AND file_ext IN "
                                f"({allowed_extensions})"
                            )
                        else:
                            file_filter = ""
                        raw_file_count = conn.execute(
                            "SELECT COUNT(*) FROM raw_files "
                            "WHERE source_id = ?" + file_filter,
                            (source_id,),
                        ).fetchone()[0]
                        raw_file_rows = conn.execute(
                            "SELECT file_name, sha256, byte_size "
                            "FROM raw_files WHERE source_id = ? "
                            + file_filter +
                            " ORDER BY file_name",
                            (source_id,),
                        ).fetchall()
                        if expected["job_relations"]:
                            job_source_count = conn.execute(
                                """
                                SELECT COUNT(*)
                                FROM std_job_sources
                                WHERE source_id = ?
                                """,
                                (source_id,),
                            ).fetchone()[0]
                            job_location_count = conn.execute(
                                """
                                SELECT COUNT(*)
                                FROM std_job_locations
                                WHERE source_id = ?
                                """,
                                (source_id,),
                            ).fetchone()[0]
                        else:
                            job_source_count = None
                            job_location_count = None
                        table = expected["table"]
                        column = expected["column"]
                        if table is None:
                            candidate_count = 0
                            candidate_states = []
                            selected_value = None
                        else:
                            candidate_count = conn.execute(
                                f"SELECT COUNT(*) FROM {table} "
                                "WHERE source_id = ?",
                                (source_id,),
                            ).fetchone()[0]
                            candidate_states = conn.execute(
                                f"SELECT candidate_status, COUNT(*) "
                                f"FROM {table} WHERE source_id = ? "
                                "GROUP BY candidate_status",
                                (source_id,),
                            ).fetchall()
                            selected_value = conn.execute(
                                f"SELECT {column} FROM {table} "
                                "WHERE source_id = ? "
                                "ORDER BY source_item_id LIMIT 1",
                                (source_id,),
                            ).fetchone()[0]
                    finally:
                        conn.close()
                    self.assertEqual(
                        stage_count,
                        expected["stage_count"],
                    )
                    self.assertEqual(
                        candidate_count,
                        expected["candidates"],
                    )
                    if expected["candidate_status"] == "deferred":
                        self.assertEqual(
                            candidate_states,
                            [("deferred", expected["stage_count"])],
                        )
                    elif expected["candidates"]:
                        self.assertEqual(
                            candidate_states,
                            [("candidate", expected["candidates"])],
                        )
                    else:
                        self.assertEqual(candidate_states, [])
                    self.assertEqual(selected_value, expected["value"])
                    if expected["stage_extra_media"] is not None:
                        self.assertEqual(
                            stage_extra["media"],
                            expected["stage_extra_media"],
                        )
                    for key in expected["stage_extra_keys"]:
                        self.assertIn(key, stage_extra)
                    if expected["job_relations"]:
                        self.assertEqual(
                            job_source_count,
                            expected["candidates"],
                        )
                        self.assertEqual(
                            job_location_count,
                            expected["candidates"],
                        )
                    self.assertEqual(
                        raw_count, 2 * first.raw_count
                    )
                    if file_extensions:
                        fixture_files = sorted(
                            path
                            for path in source_fixture_dir(source_id).iterdir()
                            if path.suffix.lower()
                            in set(file_extensions)
                        )
                        expected_files = {
                            (
                                path.name,
                                hashlib.sha256(path.read_bytes()).hexdigest(),
                                path.stat().st_size,
                            )
                            for path in fixture_files
                        }
                        self.assertEqual(
                            raw_file_count, 2 * len(fixture_files)
                        )
                        self.assertEqual(
                            {
                                tuple(row)
                                for row in raw_file_rows
                            },
                            expected_files,
                        )
                    else:
                        self.assertEqual(
                            raw_file_count, 2 * first.raw_count
                        )

    def test_every_project_rejects_a_fixture_directory_for_another_source(self):
        projects = self._discover_projects_with_expectations()
        for source_id, project in sorted(projects.items()):
            expected = SOURCE_EXPECTATIONS[source_id]
            with self.subTest(source_id=source_id):
                sys.path.insert(0, str(project.root))
                replay = getattr(
                    importlib.import_module(
                        f"{project.package_path.name}.replay"
                    ),
                    expected["replay_function"],
                )
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    with self.assertRaises(ValueError):
                        replay(
                            fixture_dir=source_fixture_dir("weather"),
                            database_path=root / "crawler.db",
                            download_root=root / "downloads",
                            registry_path=REGISTRY,
                        )


class AdmissionRegressionTest(unittest.TestCase):
    def test_missing_robots_fact_blocks_even_with_allowed_source(self):
        decision = evaluate_admission(
            _item(), registry_path=REGISTRY, robots=None
        )

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "robots:unknown")

    def test_item_level_prohibited_rights_blocks(self):
        decision = evaluate_admission(
            _item(rights_status="prohibited"),
            registry_path=REGISTRY,
            robots=RobotsFact("allowed"),
        )

        self.assertFalse(decision.allowed)
        self.assertIn("item_rights", decision.reason)


class RawEvidenceRegressionTest(unittest.TestCase):
    def test_robots_status_maps_to_auditable_facts(self):
        cases = (
            (200, True, "allowed"),
            (200, False, "disallowed"),
            (404, True, "not-found"),
            (503, True, "unknown"),
        )
        for status, parser_allows, expected in cases:
            with self.subTest(status=status, parser_allows=parser_allows):
                fact = robots_fact_from_status(
                    status,
                    parser_allows=parser_allows,
                    evidence_url="https://example.test/robots.txt",
                )
                self.assertEqual(fact.decision, expected)
                self.assertEqual(fact.status_code, status)

    def test_robots_rejection_leaves_raw_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = Settings(
                {
                    "COLLECTION_DATABASE_PATH": str(root / "crawler.db"),
                    "COLLECTION_DOWNLOAD_ROOT": str(root / "downloads"),
                    "SOURCE_REGISTRY_PATH": str(REGISTRY),
                }
            )
            crawler = type("Crawler", (), {"settings": settings})()
            middleware = RawEvidenceMiddleware.from_crawler(crawler)
            request = Request(
                "https://example.test/denied",
                meta={
                    "run_id": "run-robots-denied",
                    "robots_decision": "disallowed",
                    "robots_status_code": 200,
                    "robots_evidence_url": (
                        "https://example.test/robots.txt"
                    ),
                    "locator": "denied request",
                },
            )
            spider = type(
                "Spider",
                (),
                {"source_id": "ihchina", "run_id": "run-robots-denied"},
            )()

            middleware.process_exception(
                request,
                IgnoreRequest("Forbidden by robots.txt"),
                spider,
            )

            conn = sqlite3.connect(root / "crawler.db")
            try:
                row = conn.execute(
                    """
                    SELECT request_url, robots_decision, fetch_status,
                           error_message, run_id, metadata_json
                    FROM raw_fetches
                    """
                ).fetchone()
            finally:
                conn.close()

            self.assertEqual(row[0], "https://example.test/denied")
            self.assertEqual(row[1], "disallowed")
            self.assertEqual(row[2], "error")
            self.assertIn("robots", row[3].lower())
            self.assertEqual(row[4], "run-robots-denied")
            self.assertEqual(
                json.loads(row[5])["robots_status_code"], 200
            )

    def test_error_response_keeps_only_diagnostic_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = Settings(
                {
                    "COLLECTION_DATABASE_PATH": str(root / "crawler.db"),
                    "COLLECTION_DOWNLOAD_ROOT": str(root / "downloads"),
                    "SOURCE_REGISTRY_PATH": str(REGISTRY),
                    "ROBOTSTXT_OBEY": True,
                }
            )
            middleware = RawEvidenceMiddleware.from_crawler(
                type(
                    "Crawler",
                    (),
                    {"settings": settings},
                )()
            )
            request = Request(
                "https://example.test/item/1",
                meta={
                    "detail_url": "https://example.test/item/1",
                    "locator": "detail page",
                },
            )
            body = b"not found"
            response = HtmlResponse(
                "https://example.test/final/1",
                body=body,
                status=404,
                encoding="utf-8",
                request=request,
            )
            spider = type(
                "Spider",
                (),
                {"source_id": "ihchina", "run_id": "run-live-1"},
            )()

            middleware.process_response(request, response, spider)

            conn = sqlite3.connect(root / "crawler.db")
            try:
                row = conn.execute(
                    """
                    SELECT final_url, detail_url, detail_url_status,
                           status_code, fetch_status, body_sha256,
                           body_path, body_saved, error_message, run_id,
                           retrieved_at
                    FROM raw_fetches
                    """
                ).fetchone()
                file_count = conn.execute(
                    "SELECT COUNT(*) FROM raw_files"
                ).fetchone()[0]
            finally:
                conn.close()

            self.assertEqual(row[0], "https://example.test/final/1")
            self.assertEqual(row[1], "https://example.test/item/1")
            self.assertEqual(row[2], "direct")
            self.assertEqual(row[3], 404)
            self.assertNotEqual(row[4], "ok")
            self.assertIsNone(row[5])
            self.assertIsNone(row[6])
            self.assertEqual(row[7], 0)
            self.assertEqual(row[8], "HTTP 404")
            self.assertEqual(row[9], "run-live-1")
            self.assertTrue(row[10])
            self.assertEqual(file_count, 0)

    def test_server_error_response_is_not_saved_as_file_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = Settings(
                {
                    "COLLECTION_DATABASE_PATH": str(root / "crawler.db"),
                    "COLLECTION_DOWNLOAD_ROOT": str(root / "downloads"),
                    "SOURCE_REGISTRY_PATH": str(REGISTRY),
                }
            )
            middleware = RawEvidenceMiddleware.from_crawler(
                type(
                    "Crawler",
                    (),
                    {"settings": settings},
                )()
            )
            request = Request(
                "https://example.test/server-error",
                meta={"locator": "server error page"},
            )
            response = HtmlResponse(
                request.url,
                body=b"server error",
                status=500,
                encoding="utf-8",
                request=request,
            )
            spider = type(
                "Spider",
                (),
                {"source_id": "ihchina", "run_id": "run-server-error"},
            )()

            middleware.process_response(request, response, spider)

            conn = sqlite3.connect(root / "crawler.db")
            try:
                fetch = conn.execute(
                    "SELECT status_code, fetch_status, body_saved, "
                    "body_sha256, body_path, error_message "
                    "FROM raw_fetches"
                ).fetchone()
                file_count = conn.execute(
                    "SELECT COUNT(*) FROM raw_files"
                ).fetchone()[0]
            finally:
                conn.close()

        self.assertEqual(fetch[0], 500)
        self.assertEqual(fetch[1], "http_error")
        self.assertEqual(fetch[2], 0)
        self.assertIsNone(fetch[3])
        self.assertIsNone(fetch[4])
        self.assertEqual(fetch[5], "HTTP 500")
        self.assertEqual(file_count, 0)

    def test_downloader_maxsize_writes_oversize_note(self):
        script = textwrap.dedent(
            '''
            import json
            import sqlite3
            import tempfile
            import threading
            from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
            from pathlib import Path

            import scrapy
            from scrapy.crawler import CrawlerProcess
            from scrapy.settings import Settings

            from crawler.collection.shared.crawler_collection.pipelines import (
                collection_settings,
            )
            from crawler.collection.shared.crawler_collection.spiders import (
                CollectionSpiderMixin,
            )

            class Handler(BaseHTTPRequestHandler):
                target_hits = 0

                def do_GET(self):
                    if self.path == "/robots.txt":
                        body = b"not found"
                        self.send_response(404)
                        self.send_header("Content-Type", "text/plain")
                        self.send_header("Content-Length", str(len(body)))
                        self.end_headers()
                        self.wfile.write(body)
                        return
                    type(self).target_hits += 1
                    self.send_response(200)
                    self.send_header("Content-Type", "application/octet-stream")
                    self.send_header("Content-Length", "104857601")
                    self.end_headers()

                def log_message(self, *args):
                    pass

            server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            url = (
                f"http://127.0.0.1:{server.server_port}/huge.bin"
            )
            root = Path(tempfile.mkdtemp())
            database_path = root / "crawler.db"
            settings = Settings(
                collection_settings(
                    bot_name="oversize-contract",
                    package_name="oversize_contract",
                    database_path=str(database_path),
                    download_root=str(root / "download"),
                    registry_path=str(
                        Path.cwd() / "crawler" / "docs" / "sources.json"
                    ),
                    candidate_writer=(
                        "ihchina.candidate.write_candidate"
                    ),
                )
            )
            settings.set("LOG_LEVEL", "ERROR")
            settings.set("ROBOTSTXT_OBEY", True)
            settings.set("RETRY_TIMES", 0)
            settings.set("DOWNLOAD_MAXSIZE", 100 * 1024 * 1024)
            settings.set("DOWNLOAD_WARNSIZE", 100 * 1024 * 1024)
            settings.set("SPIDER_MODULES", [])
            settings.set("NEWSPIDER_MODULE", "")

            class Spider(CollectionSpiderMixin, scrapy.Spider):
                name = "oversize-contract"
                source_id = "ihchina"
                start_urls = [url]

                def parse(self, response):
                    raise AssertionError("oversize response reached parse")

            process = CrawlerProcess(settings)
            process.crawl(Spider)
            process.start(stop_after_crawl=True)
            server.shutdown()

            conn = sqlite3.connect(database_path)
            try:
                fetch = conn.execute(
                    """
                    SELECT fetch_status, status_code, body_saved,
                           body_sha256, body_path, robots_decision,
                           error_message
                    FROM raw_fetches
                    """
                ).fetchone()
                file_row = conn.execute(
                    """
                    SELECT download_status, sha256, byte_size,
                           file_path, file_name, oversize_note
                    FROM raw_files
                    """
                ).fetchone()
            finally:
                conn.close()
            note_path = root / "download" / file_row[3]
            print(json.dumps({
                "fetch": fetch,
                "file": file_row,
                "target_hits": Handler.target_hits,
                "note": note_path.read_text(encoding="utf-8")
                    if note_path.exists() else None,
            }))
            '''
        )
        script = script.replace(
            "import json\n",
            "import json\n"
            "import sys\n"
            "from pathlib import Path\n"
            f"project_root = Path({str(PROJECTS / 'ihchina')!r})\n"
            "sys.path.insert(0, str(project_root))\n",
            1,
        )

        completed = subprocess.run(
            [sys.executable, "-c", script],
            cwd=ROOT.parent,
            text=True,
            capture_output=True,
            timeout=45,
        )

        self.assertEqual(
            completed.returncode,
            0,
            f"{completed.stdout}\n{completed.stderr}",
        )
        payload = json.loads(completed.stdout.strip().splitlines()[-1])
        fetch = payload["fetch"]
        file_row = payload["file"]
        self.assertEqual(fetch[0], "oversize")
        self.assertIsNone(fetch[1])
        self.assertEqual(fetch[2], 0)
        self.assertIsNone(fetch[3])
        self.assertTrue(fetch[4].endswith("OVERSIZE.md"))
        self.assertEqual(fetch[5], "not-found")
        self.assertIn("104857601", fetch[6])
        self.assertEqual(file_row[0], "oversize")
        self.assertEqual(file_row[1], "")
        self.assertEqual(file_row[2], 104857601)
        self.assertTrue(file_row[3].endswith("OVERSIZE.md"))
        self.assertEqual(file_row[4], "huge.bin")
        self.assertIn("104857601", file_row[5])
        self.assertEqual(payload["target_hits"], 1)
        self.assertIn("104857601", payload["note"])

    def test_streamed_download_over_limit_writes_oversize_note(self):
        script = textwrap.dedent(
            '''
            import json
            import sqlite3
            import tempfile
            import threading
            from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
            from pathlib import Path

            import scrapy
            from scrapy.crawler import CrawlerProcess
            from scrapy.settings import Settings

            from crawler.collection.shared.crawler_collection.pipelines import (
                collection_settings,
            )
            from crawler.collection.shared.crawler_collection.spiders import (
                CollectionSpiderMixin,
            )

            class Handler(BaseHTTPRequestHandler):
                target_hits = 0

                def do_GET(self):
                    if self.path == "/robots.txt":
                        body = b"not found"
                        self.send_response(404)
                        self.send_header("Content-Length", str(len(body)))
                        self.end_headers()
                        self.wfile.write(body)
                        return
                    type(self).target_hits += 1
                    self.send_response(200)
                    self.send_header("Content-Type", "application/octet-stream")
                    self.end_headers()
                    self.wfile.write(b"x" * 4096)

                def log_message(self, *args):
                    pass

            server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            url = f"http://127.0.0.1:{server.server_port}/stream.bin"
            root = Path(tempfile.mkdtemp())
            database_path = root / "crawler.db"
            settings = Settings(
                collection_settings(
                    bot_name="stream-oversize",
                    package_name="stream_oversize",
                    database_path=str(database_path),
                    download_root=str(root / "download"),
                    registry_path=str(
                        Path.cwd() / "crawler" / "docs" / "sources.json"
                    ),
                    candidate_writer=(
                        "ihchina.candidate.write_candidate"
                    ),
                )
            )
            settings.set("LOG_LEVEL", "ERROR")
            settings.set("ROBOTSTXT_OBEY", True)
            settings.set("RETRY_TIMES", 0)
            settings.set("DOWNLOAD_MAXSIZE", 1024)
            settings.set("DOWNLOAD_WARNSIZE", 1024)
            settings.set("SPIDER_MODULES", [])
            settings.set("NEWSPIDER_MODULE", "")

            class Spider(CollectionSpiderMixin, scrapy.Spider):
                name = "stream-oversize"
                source_id = "ihchina"
                start_urls = [url]

                def parse(self, response):
                    raise AssertionError("oversize response reached parse")

            process = CrawlerProcess(settings)
            process.crawl(Spider)
            process.start(stop_after_crawl=True)
            server.shutdown()

            conn = sqlite3.connect(database_path)
            try:
                fetch = conn.execute(
                    "SELECT fetch_status, body_saved, body_sha256 "
                    "FROM raw_fetches"
                ).fetchone()
                file_row = conn.execute(
                    "SELECT download_status, sha256, file_path "
                    "FROM raw_files"
                ).fetchone()
            finally:
                conn.close()
            note_path = root / "download" / file_row[2]
            print(json.dumps({
                "fetch": fetch,
                "file": file_row,
                "target_hits": Handler.target_hits,
                "note": note_path.read_text(encoding="utf-8")
                    if note_path.exists() else None,
            }))
            '''
        )
        script = script.replace(
            "import json\n",
            "import json\n"
            "import sys\n"
            "from pathlib import Path\n"
            f"project_root = Path({str(PROJECTS / 'ihchina')!r})\n"
            "sys.path.insert(0, str(project_root))\n",
            1,
        )

        completed = subprocess.run(
            [sys.executable, "-c", script],
            cwd=ROOT.parent,
            text=True,
            capture_output=True,
            timeout=45,
        )

        self.assertEqual(
            completed.returncode,
            0,
            f"{completed.stdout}\n{completed.stderr}",
        )
        payload = json.loads(completed.stdout.strip().splitlines()[-1])
        self.assertEqual(payload["fetch"], ["oversize", 0, None])
        self.assertEqual(payload["file"][0], "oversize")
        self.assertEqual(payload["file"][1], "")
        self.assertEqual(payload["target_hits"], 1)
        self.assertIn("exceeds 1024 bytes", payload["note"])

    def test_parse_failure_writes_blocked_audit_candidate(self):
        class Signals:
            def connect(self, *args, **kwargs):
                return None

        class Stats:
            def get_stats(self):
                return {}

        class Crawler:
            def __init__(self, settings):
                self.settings = settings
                self.signals = Signals()
                self.stats = Stats()

        sys.path.insert(0, str(PROJECTS / "ihchina"))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = Settings(
                {
                    "COLLECTION_DATABASE_PATH": str(root / "crawler.db"),
                    "COLLECTION_DOWNLOAD_ROOT": str(root / "downloads"),
                    "COLLECTION_REPORT_ROOT": str(root / "reports"),
                    "COLLECTION_RUN_MODE": "live",
                    "SOURCE_REGISTRY_PATH": str(REGISTRY),
                    "COLLECTION_CANDIDATE_WRITER": (
                        "ihchina.candidate.write_candidate"
                    ),
                }
            )
            crawler = Crawler(settings)
            spider = type(
                "Spider",
                (),
                {"source_id": "ihchina", "run_id": "run-parse"},
            )()
            middleware = RawEvidenceMiddleware.from_crawler(crawler)
            request = Request(
                "https://example.test/parse-error",
                meta={
                    "run_id": "run-parse",
                    "robots_decision": "allowed",
                    "locator": "parse error page",
                },
            )
            middleware.process_request(request, spider)
            response = HtmlResponse(
                request.url,
                body=b"<html>broken</html>",
                encoding="utf-8",
                request=request,
            )
            response = middleware.process_response(
                request, response, spider
            )
            extension = RunReportExtension(crawler)
            extension.spider_opened(spider)
            extension.spider_error(
                SimpleNamespace(value=ValueError("bad selector")),
                response,
                spider,
            )
            extension.spider_closed(spider, "finished")

            conn = sqlite3.connect(root / "crawler.db")
            try:
                stage_count = conn.execute(
                    "SELECT COUNT(*) FROM stage_source_items"
                ).fetchone()[0]
                candidate = conn.execute(
                    "SELECT candidate_status, candidate_reason "
                    "FROM std_ich_projects"
                ).fetchone()
            finally:
                conn.close()

        self.assertEqual(stage_count, 1)
        self.assertEqual(candidate[0], "blocked")
        self.assertIn("parse_error:ValueError", candidate[1])
        self.assertEqual(spider.run_report.blocked, 1)
        self.assertEqual(spider.run_report.failed, 1)


class RuntimeRegressionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.db_path = self.root / "crawler.db"
        self.runtime = CollectionRuntime(
            database_path=self.db_path,
            download_root=self.root / "downloads",
            registry_path=REGISTRY,
            candidate_writer=self._candidate_writer(),
        )

    @staticmethod
    def _candidate_writer():
        project_root = PROJECTS / "ihchina"
        sys.path.insert(0, str(project_root))
        from ihchina.candidate import write_candidate

        return write_candidate

    def tearDown(self):
        self.tmp.cleanup()

    def _evidence(self, **overrides):
        payload = {
            "source_id": "ihchina",
            "request_url": "https://example.test/1",
            "final_url": "https://example.test/1",
            "body": b"<html>fixture</html>",
            "content_type": "text/html",
            "run_id": "run-1",
            "robots_decision": "allowed",
        }
        payload.update(overrides)
        return RawEvidence(**payload)

    def test_stage_is_idempotent_across_new_raw_fetches_and_keeps_run_id(self):
        first_raw = self.runtime.persist_raw(self._evidence(run_id="run-1"))
        second_raw = self.runtime.persist_raw(self._evidence(run_id="run-2"))
        item = _item(content_hash="content-hash-1")

        self.runtime.write_item(item, raw_evidence_id=first_raw)
        self.runtime.write_item(
            _item(content_hash="content-hash-1", run_id="run-2"),
            raw_evidence_id=second_raw,
        )

        conn = sqlite3.connect(self.db_path)
        try:
            stage = conn.execute(
                """
                SELECT raw_fetch_id, run_id, content_hash
                FROM stage_source_items
                """
            ).fetchall()
            candidate = conn.execute(
                """
                SELECT run_id, content_hash
                FROM std_ich_projects
                """
            ).fetchone()
        finally:
            conn.close()

        self.assertEqual(len(stage), 1)
        self.assertEqual(stage[0], (second_raw, "run-2", "content-hash-1"))
        self.assertEqual(candidate, ("run-2", "content-hash-1"))

    def test_missing_robots_fact_cannot_be_overridden_by_allowed_admission(self):
        raw_id = self.runtime.persist_raw(
            self._evidence(robots_decision="unknown")
        )
        result = self.runtime.write_item(
            _item(),
            raw_evidence_id=raw_id,
            admission=type(
                "Decision",
                (),
                {"allowed": True, "status": "candidate", "reason": None},
            )(),
        )

        self.assertEqual(result["candidate_status"], "blocked")
        self.assertEqual(result["candidate_reason"], "robots:unknown")

    def test_raw_from_another_source_is_rejected_before_stage(self):
        raw_id = self.runtime.persist_raw(self._evidence())
        item = _item(
            source_id="nzrc",
            source_url="https://example.test/job/1",
            long_term_url="https://example.test/job/1",
            detail_url="https://example.test/job/1",
        )

        result = self.runtime.write_item(item, raw_evidence_id=raw_id)

        self.assertEqual(result["candidate_status"], "blocked")
        self.assertIn("raw_source_mismatch", result["candidate_reason"])
        conn = sqlite3.connect(self.db_path)
        try:
            stage_count = conn.execute(
                "SELECT COUNT(*) FROM stage_source_items"
            ).fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(stage_count, 0)

    def test_item_run_id_must_match_raw_evidence_run_id(self):
        raw_id = self.runtime.persist_raw(self._evidence(run_id="run-1"))

        result = self.runtime.write_item(
            _item(run_id="run-2"), raw_evidence_id=raw_id
        )

        self.assertEqual(result["candidate_status"], "blocked")
        self.assertIn("raw_run_mismatch", result["candidate_reason"])
        conn = sqlite3.connect(self.db_path)
        try:
            stage_count = conn.execute(
                "SELECT COUNT(*) FROM stage_source_items"
            ).fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(stage_count, 0)


class LifecycleRegressionTest(unittest.TestCase):
    def test_two_requests_in_one_crawl_share_a_run_id(self):
        class Spider(CollectionSpiderMixin, scrapy.Spider):
            name = "run-id-contract"
            source_id = "ihchina"

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = Settings(
                {
                    "COLLECTION_DATABASE_PATH": str(root / "crawler.db"),
                    "COLLECTION_DOWNLOAD_ROOT": str(root / "download"),
                    "SOURCE_REGISTRY_PATH": str(REGISTRY),
                    "ROBOTSTXT_OBEY": False,
                }
            )
            crawler = CrawlerProcess(settings).create_crawler(Spider)
            spider = Spider.from_crawler(crawler)
            middleware = RawEvidenceMiddleware.from_crawler(crawler)
            first = Request("https://example.test/one")
            second = Request("https://example.test/two")

            middleware.process_request(first, spider)
            middleware.process_request(second, spider)

            self.assertTrue(spider.run_id.startswith("ihchina-"))
            self.assertEqual(first.meta["run_id"], spider.run_id)
            self.assertEqual(second.meta["run_id"], spider.run_id)

    def test_old_stage_key_is_migrated_to_source_item_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "crawler.db"
            conn = sqlite3.connect(path)
            try:
                conn.execute(
                    """
                    CREATE TABLE stage_source_items (
                        id INTEGER PRIMARY KEY,
                        raw_fetch_id INTEGER NOT NULL,
                        source_id TEXT NOT NULL,
                        source_item_id TEXT NOT NULL,
                        source_url TEXT NOT NULL,
                        long_term_url TEXT NOT NULL,
                        detail_url TEXT,
                        detail_url_status TEXT NOT NULL,
                        fetch_url TEXT,
                        locator TEXT,
                        rights_status TEXT NOT NULL,
                        attribution_required INTEGER NOT NULL DEFAULT 0,
                        attribution_text TEXT,
                        rights_evidence_url TEXT,
                        title TEXT NOT NULL,
                        retrieved_at TEXT NOT NULL,
                        content_hash TEXT NOT NULL,
                        parser_version TEXT NOT NULL,
                        extra TEXT NOT NULL DEFAULT '{}',
                        UNIQUE(raw_fetch_id, source_item_id)
                    )
                    """
                )
                conn.executemany(
                    """
                    INSERT INTO stage_source_items (
                        raw_fetch_id, source_id, source_item_id, source_url,
                        long_term_url, detail_url, detail_url_status, locator, rights_status,
                        title, retrieved_at, content_hash, parser_version, extra
                    ) VALUES (?, 'ihchina', '1', ?, ?, ?, 'direct', ?, ?, ?, ?, ?, '1', '{}')
                    """,
                    (
                        (
                            1,
                            "https://example.test/1",
                            "https://example.test/1",
                            "https://example.test/1",
                            "detail",
                            "attribution-required",
                            "old",
                            "2026-10-20T00:00:00+00:00",
                            "old-hash",
                        ),
                        (
                            2,
                            "https://example.test/1",
                            "https://example.test/1",
                            "https://example.test/1",
                            "detail",
                            "attribution-required",
                            "new",
                            "2026-10-20T00:00:01+00:00",
                            "new-hash",
                        ),
                    ),
                )
                conn.commit()
            finally:
                conn.close()

            database = CollectionDatabase(path)
            conn = database.connect()
            try:
                rows = conn.execute(
                    "SELECT raw_fetch_id, title, run_id FROM stage_source_items"
                ).fetchall()
                sql = conn.execute(
                    "SELECT sql FROM sqlite_master "
                    "WHERE type='table' AND name='stage_source_items'"
                ).fetchone()[0]
            finally:
                conn.close()

        self.assertEqual(rows, [(2, "new", "legacy")])
        self.assertIn("UNIQUE(source_id, source_item_id)", sql)


class SiteCandidateMappingTest(unittest.TestCase):
    def _write(self, source_id, project, package, extra, **overrides):
        project_root = PROJECTS / project
        sys.path.insert(0, str(project_root))
        writer = importlib.import_module(
            f"{package}.candidate"
        ).write_candidate
        tmp = tempfile.TemporaryDirectory()
        try:
            root = Path(tmp.name)
            runtime = CollectionRuntime(
                database_path=root / "crawler.db",
                download_root=root / "downloads",
                registry_path=REGISTRY,
                candidate_writer=writer,
            )
            raw_id = runtime.persist_raw(
                RawEvidence(
                    source_id=source_id,
                    request_url="https://example.test/item/1",
                    final_url="https://example.test/item/1",
                    body=b"fixture",
                    content_type="text/html",
                    run_id=f"{source_id}-run",
                    robots_decision="allowed",
                )
            )
            payload = {
                "source_id": source_id,
                "source_item_id": "1",
                "source_url": "https://example.test/item/1",
                "long_term_url": "https://example.test/item/1",
                "detail_url": "https://example.test/item/1",
                "detail_url_status": "direct",
                "run_id": f"{source_id}-run",
                "mode": "fixture",
                "rights_status": "attribution-required",
                "title": "示例",
                "content_hash": "hash-1",
                "extra": extra,
            }
            payload.update(overrides)
            result = runtime.write_item(
                CollectionItem(**payload), raw_evidence_id=raw_id
            )
            conn = sqlite3.connect(root / "crawler.db")
            return result, conn, tmp
        except Exception:
            tmp.cleanup()
            raise

    def test_all_site_writers_keep_standard_fields(self):
        cases = (
            (
                "ihchina",
                "ihchina",
                "ihchina",
                {"ich_code": "Ⅰ-1", "declaration_region": "贵州省"},
                "std_ich_projects",
                "ich_code",
                "Ⅰ-1",
            ),
            (
                "nzrc",
                "nzrc",
                "nzrc",
                {
                    "company_name": "示例公司",
                    "salary_raw": "5000",
                    "location_raw": "广东",
                    "province": "广东",
                    "city": "广州",
                },
                "std_jobs",
                "company_name",
                "示例公司",
            ),
            (
                "nongmuhr",
                "nongmuhr",
                "nongmuhr",
                {"company_name": "农牧公司", "location_raw": "广东"},
                "std_jobs",
                "company_name",
                "农牧公司",
            ),
            (
                "cass-linguistics",
                "cass-linguistics",
                "cass_linguistics",
                {"summary": "摘要", "published_at": "2026-10-01"},
                "std_research_articles",
                "summary",
                "摘要",
            ),
            (
                "feiyiw",
                "feiyiw",
                "feiyiw",
                {},
                "std_ich_articles",
                "body_text",
                "正文",
            ),
            (
                "aqsc-moa",
                "aqsc-moa",
                "aqsc_moa",
                {"product_name": "示例产品"},
                "std_agri_products",
                "product_name",
                "示例产品",
            ),
            (
                "cnipa",
                "cnipa",
                "cnipa",
                {"product_name": "地理标志产品"},
                "std_agri_products",
                "product_name",
                "地理标志产品",
            ),
        )
        for (
            source_id,
            project,
            package,
            extra,
            table,
            column,
            expected,
        ) in cases:
            with self.subTest(source_id=source_id):
                result, conn, tmp = self._write(
                    source_id,
                    project,
                    package,
                    extra,
                    body_text="正文",
                )
                try:
                    self.assertEqual(result["candidate_status"], "candidate")
                    row = conn.execute(
                        f"SELECT {column} FROM {table}"
                    ).fetchone()
                    self.assertEqual(row[0], expected)
                finally:
                    conn.close()
                    tmp.cleanup()

    def test_dialect_writer_keeps_point_and_lexeme(self):
        result, conn, tmp = self._write(
            "dialect-org",
            "dialect-org",
            "dialect_org",
            {
                "region_raw": "广东广州",
                "province": "广东",
                "city": "广州",
                "lexeme": {
                    "lemma": "食饭",
                    "definition": "粤语：吃饭",
                    "audio_status": "missing",
                    "rights_status": "attribution-required",
                },
            },
        )
        try:
            self.assertEqual(result["candidate_status"], "candidate")
            point = conn.execute(
                "SELECT region_raw, province, city FROM std_dialect_points"
            ).fetchone()
            lexeme = conn.execute(
                "SELECT lemma, definition, run_id FROM std_dialect_lexemes"
            ).fetchone()
        finally:
            conn.close()
            tmp.cleanup()
        self.assertEqual(point, ("广东广州", "广东", "广州"))
        self.assertEqual(lexeme, ("食饭", "粤语：吃饭", "dialect-org-run"))


class FixtureAndRegistryRegressionTest(unittest.TestCase):
    def test_aqsc_fixture_uses_source_id_directory_without_alias(self):
        self.assertTrue(source_fixture_dir("aqsc-moa").is_dir())
        with self.assertRaises(ValueError):
            source_fixture_dir("aqsc")

    def test_run_modes_match_executable_projects(self):
        sources = {
            source["id"]: source
            for source in json.loads(
                REGISTRY.read_text(encoding="utf-8")
            )["sources"]
        }
        for source_id in (
            "ihchina",
            "nzrc",
            "nongmuhr",
            "dialect-org",
            "cass-linguistics",
            "feiyiw",
        ):
            self.assertIn("live", sources[source_id]["run_modes"], source_id)
        self.assertEqual(
            sources["aqsc-moa"]["run_modes"], ["fixture", "live"]
        )
        self.assertEqual(sources["cnipa"]["run_modes"], ["fixture", "live"])


class ConverterIsolationRegressionTest(unittest.TestCase):
    def test_importing_runtime_does_not_load_converter(self):
        code = (
            "import sys; "
            "import crawler.collection.shared.crawler_collection.runtime; "
            "assert 'crawler.pipeline.converter' not in sys.modules, "
            "'converter imported eagerly'"
        )
        completed = subprocess.run(
            [sys.executable, "-c", code],
            cwd=ROOT.parent,
            text=True,
            capture_output=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)


if __name__ == "__main__":
    unittest.main()
