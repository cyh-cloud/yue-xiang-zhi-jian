import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

from scrapy.http import Request, Response

from crawler.collection.shared.crawler_collection.middlewares import (
    RawEvidenceMiddleware,
)


ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT / "collection" / "projects" / "aqsc-moa"
FIXTURE = ROOT / "tests" / "fixtures" / "evidence" / "aqsc-moa"
REGISTRY = ROOT / "docs" / "sources.json"
sys.path.insert(0, str(PROJECT_ROOT))

from aqsc_moa.parsers import parse_xlsx_rows  # noqa: E402
from aqsc_moa.replay import replay_aqsc_fixture  # noqa: E402
from aqsc_moa.spiders.collection import AqscMoaSpider  # noqa: E402


class AqscMoaScrapyTest(unittest.TestCase):
    def test_spider_is_live_enabled_with_explicit_start_urls(self):
        spider = AqscMoaSpider()
        self.assertEqual(spider.name, "aqsc-moa")
        self.assertEqual(spider.source_id, "aqsc-moa")
        self.assertTrue(spider.live_enabled)
        self.assertEqual(spider.start_urls, [])
        self.assertEqual(spider.max_download_bytes, 100 * 1024 * 1024)

    def test_xlsx_parser_keeps_sheet_and_row_locators(self):
        payload = json.loads(
            (FIXTURE / "discover.json").read_text(encoding="utf-8")
        )
        rows = []
        for item in payload["items"]:
            path = FIXTURE / item["file_name"]
            rows.extend(
                parse_xlsx_rows(
                    path.read_bytes(),
                    file_name=path.name,
                    metadata=item,
                )
            )

        self.assertEqual(len(rows), 8)
        self.assertEqual(
            rows[0]["locator"], "sheet=Sheet1; row=3; seq=1"
        )
        self.assertEqual(rows[0]["extra"]["cert_type"], "mingteyouxin")
        self.assertEqual(rows[4]["extra"]["cert_type"], "tezhi_nongpin")
        self.assertTrue(all(row["detail_url"] is None for row in rows))
        self.assertTrue(
            all(row["detail_url_status"] == "missing" for row in rows)
        )

    def test_fixture_replay_uses_spider_middleware_and_pipeline(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = replay_aqsc_fixture(
                fixture_dir=FIXTURE,
                database_path=root / "crawler.db",
                download_root=root / "download",
                registry_path=REGISTRY,
                run_id="aqsc-fixture-test",
            )
            conn = sqlite3.connect(root / "crawler.db")
            try:
                raw_count = conn.execute(
                    "SELECT COUNT(*) FROM raw_fetches"
                ).fetchone()[0]
                raw_file_count = conn.execute(
                    "SELECT COUNT(*) FROM raw_files "
                    "WHERE file_ext IN ('.xlsx', '.pdf')"
                ).fetchone()[0]
                stage_count = conn.execute(
                    "SELECT COUNT(*) FROM stage_source_items"
                ).fetchone()[0]
                rows = conn.execute(
                    "SELECT locator, detail_url, detail_url_status, "
                    "source_url, long_term_url, candidate_status, "
                    "candidate_reason FROM std_agri_products "
                    "ORDER BY source_item_id"
                ).fetchall()
            finally:
                conn.close()

        self.assertEqual(result.mode, "fixture")
        self.assertEqual(result.raw_count, 5)
        self.assertEqual(result.stage_count, 8)
        self.assertEqual(result.written, 0)
        self.assertEqual(result.deferred, 8)
        self.assertEqual(raw_count, 5)
        self.assertEqual(raw_file_count, 2)
        self.assertEqual(stage_count, 8)
        self.assertEqual(len(rows), 8)
        for row in rows:
            self.assertIn("sheet=Sheet1; row=", row[0])
            self.assertIsNone(row[1])
            self.assertEqual(row[2], "missing")
            self.assertTrue(row[3].startswith("http://www.aqsc.agri.cn/"))
            self.assertTrue(row[4].endswith(".htm"))
            self.assertEqual(row[5], "deferred")
            self.assertEqual(row[6], "file-source:fixture")

    def test_oversize_response_writes_note_without_file_body(self):
        class Spider:
            source_id = "aqsc-moa"
            run_id = "oversize-test"

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            middleware = RawEvidenceMiddleware(
                root / "crawler.db",
                root / "download",
                REGISTRY,
            )
            request = Request("http://example.test/huge.xlsx")
            middleware.process_request(request, Spider())
            response = Response(
                request.url,
                body=b"not the full file",
                headers={"Content-Length": "104857601"},
                request=request,
            )
            middleware.process_response(request, response, Spider())
            conn = sqlite3.connect(root / "crawler.db")
            try:
                status, note = conn.execute(
                    "SELECT download_status, oversize_note FROM raw_files"
                ).fetchone()
            finally:
                conn.close()
            note_path = root / "download" / "example.test" / "OVERSIZE.md"
            self.assertTrue(note_path.is_file())

        self.assertEqual(status, "oversize")
        self.assertIn("104857601", note)


if __name__ == "__main__":
    unittest.main()
