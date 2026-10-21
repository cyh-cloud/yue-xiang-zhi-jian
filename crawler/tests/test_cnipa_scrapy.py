import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT / "collection" / "projects" / "cnipa"
FIXTURE = ROOT / "tests" / "fixtures" / "evidence" / "cnipa"
REGISTRY = ROOT / "docs" / "sources.json"
sys.path.insert(0, str(PROJECT_ROOT))

from cnipa import live as live_module
from cnipa.parsers import parse_pdf_rows  # noqa: E402
from cnipa.replay import replay_cnipa_fixture  # noqa: E402
from cnipa.spiders.collection import CnipaSpider  # noqa: E402


class CnipaScrapyTest(unittest.TestCase):
    def test_live_canary_requires_explicit_start_urls_before_crawl(self):
        for start_urls in (None, [], ("",)):
            with self.subTest(start_urls=start_urls):
                with mock.patch.object(
                    live_module, "CrawlerProcess"
                ) as process:
                    with self.assertRaisesRegex(
                        ValueError, "explicit start URL"
                    ):
                        live_module.run_live_sample(
                            database_path=Path("unused.db"),
                            download_root=Path("unused-download"),
                            registry_path=REGISTRY,
                            report_root=Path("unused-reports"),
                            start_urls=start_urls,
                        )
                    process.assert_not_called()

    def test_spider_is_live_enabled_with_explicit_start_urls(self):
        spider = CnipaSpider()
        self.assertEqual(spider.name, "cnipa")
        self.assertEqual(spider.source_id, "cnipa")
        self.assertTrue(spider.live_enabled)
        self.assertEqual(spider.start_urls, [])
        self.assertEqual(spider.max_download_bytes, 100 * 1024 * 1024)

    def test_pdf_parser_keeps_page_and_sequence_locators(self):
        payload = json.loads(
            (FIXTURE / "discover.json").read_text(encoding="utf-8")
        )
        item = payload["items"][0]
        path = FIXTURE / item["file_name"]
        rows = parse_pdf_rows(
            path.read_bytes(),
            file_name=path.name,
            metadata=item,
        )

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["title"], "Sample Pomegranate")
        self.assertEqual(
            rows[0]["locator"],
            "pdf=synthetic-announcement-687.pdf; page=1; row=1; seq=1",
        )
        self.assertEqual(
            rows[1]["locator"],
            "pdf=synthetic-announcement-687.pdf; page=2; row=1; seq=2",
        )
        self.assertTrue(all(row["detail_url"] is None for row in rows))
        self.assertTrue(
            all(row["detail_url_status"] == "missing" for row in rows)
        )

    def test_fixture_replay_uses_spider_middleware_and_pipeline(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = replay_cnipa_fixture(
                fixture_dir=FIXTURE,
                database_path=root / "crawler.db",
                download_root=root / "download",
                registry_path=REGISTRY,
                run_id="cnipa-fixture-test",
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
                    "source_url, long_term_url, "
                    "candidate_status, candidate_reason "
                    "FROM std_agri_products ORDER BY source_item_id"
                ).fetchall()
                fetch_urls = [
                    row[0]
                    for row in conn.execute(
                        "SELECT fetch_url FROM stage_source_items "
                        "ORDER BY source_item_id"
                    )
                ]
            finally:
                conn.close()

        self.assertEqual(result.mode, "fixture")
        self.assertEqual(result.raw_count, 3)
        self.assertEqual(result.stage_count, 2)
        self.assertEqual(result.written, 0)
        self.assertEqual(result.deferred, 2)
        self.assertEqual(raw_count, 3)
        self.assertEqual(raw_file_count, 1)
        self.assertEqual(stage_count, 2)
        self.assertEqual(len(rows), 2)
        for row, fetch_url in zip(rows, fetch_urls):
            self.assertIn("page=", row[0])
            self.assertIn("seq=", row[0])
            self.assertIsNone(row[1])
            self.assertEqual(row[2], "missing")
            self.assertEqual(
                row[3],
                "https://www.cnipa.gov.cn/art/2026/8/12/"
                "art_1400_207705.html",
            )
            self.assertEqual(row[4], row[3])
            self.assertTrue(fetch_url.startswith("http://127.0.0.1:"))
            self.assertEqual(row[5], "deferred")
            self.assertEqual(row[6], "file-source:fixture")
            self.assertNotIn("X-Amz", row[3])
            self.assertNotIn("X-Amz", row[4])
            self.assertNotIn("X-Amz", fetch_url)


if __name__ == "__main__":
    unittest.main()
