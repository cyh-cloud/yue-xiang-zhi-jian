import json
import subprocess
import sys
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class RobotsEvidenceIntegrationTest(unittest.TestCase):
    def test_robots_only_block_is_reported_once_with_reason(self):
        script = textwrap.dedent(
            """
            import json
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
                def do_GET(self):
                    if self.path == "/robots.txt":
                        status = 200
                        body = b"User-agent: *\\nDisallow: /item\\n"
                    else:
                        status = 200
                        body = b"<html>item</html>"
                    self.send_response(status)
                    self.send_header("Content-Type", "text/html")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)

                def log_message(self, *args):
                    pass

            server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            url = f"http://127.0.0.1:{server.server_port}/item"
            root = Path(tempfile.mkdtemp())
            database_path = root / "crawler.db"
            settings = Settings(
                collection_settings(
                    bot_name="robots-only",
                    package_name="robots_only",
                    database_path=str(database_path),
                    download_root=str(root / "download"),
                    registry_path=str(
                        Path.cwd() / "crawler" / "docs" / "sources.json"
                    ),
                )
            )
            settings.set("LOG_LEVEL", "ERROR")
            settings.set("ROBOTSTXT_OBEY", True)
            settings.set("RETRY_TIMES", 0)
            settings.set("SPIDER_MODULES", [])
            settings.set("NEWSPIDER_MODULE", "")

            class Spider(CollectionSpiderMixin, scrapy.Spider):
                name = "robots-only"
                source_id = "ihchina"
                start_urls = [url]

                def parse(self, response):
                    raise AssertionError("robots-disallowed URL was parsed")

            process = CrawlerProcess(settings)
            process.crawl(Spider)
            process.start(stop_after_crawl=True)
            server.shutdown()

            reports = list((root / "reports").glob("*.json"))
            report_data = json.loads(reports[0].read_text()) if reports else {}
            print(json.dumps({
                "reports": [path.name for path in reports],
                "report": report_data,
            }))
            """
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
        self.assertEqual(
            len(payload["reports"]),
            1,
            f"{payload}\n{completed.stderr}",
        )
        report = payload["report"]
        self.assertEqual(report["blocked"], 1, report)
        self.assertEqual(report["failed"], 0, report)
        self.assertEqual(report["failure_count"], 0, report)
        self.assertEqual(report["status"], "partial", report)
        self.assertIn("robotstxt/forbidden=1", report["errors"])
        self.assertIn("robotstxt/forbidden=1", report["failure_reason"])

    def test_allowed_denied_404_and_unknown_are_persisted(self):
        script = textwrap.dedent(
            """
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
                robots_status = 200
                robots_body = b""

                def do_GET(self):
                    if self.path == "/robots.txt":
                        status = self.robots_status
                        body = self.robots_body
                    elif self.path == "/item":
                        status = 200
                        body = b"<html>item</html>"
                    else:
                        status = 404
                        body = b"missing"
                    self.send_response(status)
                    self.send_header("Content-Type", "text/html")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)

                def log_message(self, *args):
                    pass

            def serve(status, body):
                handler = type(
                    f"Handler{status}",
                    (Handler,),
                    {"robots_status": status, "robots_body": body},
                )
                server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
                threading.Thread(target=server.serve_forever, daemon=True).start()
                return server, f"http://127.0.0.1:{server.server_port}/item"

            servers = [
                serve(200, b"User-agent: *\\nAllow: /\\n"),
                serve(200, b"User-agent: *\\nDisallow: /item\\n"),
                serve(404, b"not found"),
                serve(500, b"server error"),
            ]
            urls = [url for _, url in servers]
            root = Path(tempfile.mkdtemp())
            database_path = root / "crawler.db"
            settings = Settings(
                collection_settings(
                    bot_name="robots-contract",
                    package_name="robots_contract",
                    database_path=str(database_path),
                    download_root=str(root / "download"),
                    registry_path=str(
                        Path.cwd() / "crawler" / "docs" / "sources.json"
                    ),
                )
            )
            settings.set("LOG_LEVEL", "ERROR")
            settings.set("ROBOTSTXT_OBEY", True)
            settings.set("RETRY_TIMES", 0)
            settings.set("SPIDER_MODULES", [])
            settings.set("NEWSPIDER_MODULE", "")

            class Spider(CollectionSpiderMixin, scrapy.Spider):
                name = "robots-contract"
                source_id = "ihchina"
                start_urls = urls

                def parse(self, response):
                    yield {
                        "source_id": self.source_id,
                        "source_item_id": response.url,
                        "source_url": response.url,
                        "long_term_url": response.url,
                        "detail_url": response.url,
                        "detail_url_status": "direct",
                        "run_id": response.meta["run_id"],
                        "mode": "live",
                        "rights_status": "attribution-required",
                        "title": "robots integration item",
                        "raw_evidence_id": response.meta["raw_evidence_id"],
                    }

            process = CrawlerProcess(settings)
            process.crawl(Spider)
            process.start(stop_after_crawl=True)
            for server, _ in servers:
                server.shutdown()

            conn = sqlite3.connect(database_path)
            try:
                decisions = [
                    row[0]
                    for row in conn.execute(
                        "SELECT robots_decision FROM raw_fetches ORDER BY id"
                    )
                ]
                stage_count = conn.execute(
                    "SELECT COUNT(*) FROM stage_source_items"
                ).fetchone()[0]
                candidate_count = conn.execute(
                    "SELECT COUNT(*) FROM std_ich_projects"
                ).fetchone()[0]
            finally:
                conn.close()
            reports = list((root / "reports").glob("*.json"))
            report_data = json.loads(reports[0].read_text()) if reports else {}
            print(json.dumps({
                "decisions": decisions,
                "stage_count": stage_count,
                "candidate_count": candidate_count,
                "reports": [path.name for path in reports],
                "report": report_data,
            }))
            """
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
        self.assertEqual(
            set(payload["decisions"]),
            {"allowed", "disallowed", "not-found", "unknown"},
            f"{payload}\n{completed.stderr}",
        )
        self.assertEqual(
            payload["stage_count"], 3, f"{payload}\n{completed.stderr}"
        )
        self.assertEqual(
            payload["candidate_count"], 1, f"{payload}\n{completed.stderr}"
        )
        self.assertEqual(
            len(payload["reports"]), 1, f"{payload}\n{completed.stderr}"
        )
        report = payload["report"]
        self.assertEqual(report["mode"], "live")
        self.assertEqual(report["request_count"], 4)
        self.assertEqual(report["raw_count"], 4)
        self.assertEqual(report["stage_count"], 3)
        self.assertEqual(report["candidate_count"], 1)
        self.assertEqual(report["blocked"], 3)
        self.assertTrue(report["started_at"])
        self.assertTrue(report["finished_at"])
        self.assertTrue(report["evidence_path"])


if __name__ == "__main__":
    unittest.main()
