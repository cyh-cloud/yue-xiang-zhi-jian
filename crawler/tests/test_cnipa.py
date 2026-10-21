import sqlite3
import shutil
import tempfile
import unittest
from pathlib import Path

from crawler.pipeline.offline_fixture import (
    OfflineFixtureConfig,
    run_offline_fixture,
)
from crawler.pipeline.converter import run_batch


ROOT = Path(__file__).resolve().parents[1]
PDF = (
    ROOT
    / "tests"
    / "fixtures"
    / "evidence"
    / "cnipa"
    / "synthetic-announcement-687.pdf"
)


class CnipaSourceTest(unittest.TestCase):
    def test_all_documented_pdf_fixtures_are_parsed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pdf_root = root / "pdfs"
            pdf_root.mkdir()
            shutil.copyfile(PDF, pdf_root / "公告-第687号.pdf")
            shutil.copyfile(PDF, pdf_root / "公告-第89号.pdf")
            config = OfflineFixtureConfig(
                database_path=root / "crawler.db",
                download_root=root / "download",
                fixture_root=root / "fixture",
                pdf_root=pdf_root,
            )

            result = run_offline_fixture("cnipa", "pdf", config)

            self.assertEqual(result.status, "succeeded")
            conn = sqlite3.connect(config.database_path)
            try:
                file_count = conn.execute(
                    "SELECT COUNT(*) FROM raw_files"
                ).fetchone()[0]
                ids = [
                    row[0]
                    for row in conn.execute(
                        "SELECT DISTINCT source_item_id "
                        "FROM stage_source_items"
                    )
                ]
            finally:
                conn.close()
            self.assertEqual(file_count, 2)
            self.assertEqual(result.discovered_count, 2)
            self.assertTrue(any(value.startswith("cnipa:687:") for value in ids))
            self.assertTrue(any(value.startswith("cnipa:89:") for value in ids))

    def test_pdf_products_keep_long_term_url_and_page_locator(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = OfflineFixtureConfig(
                database_path=root / "crawler.db",
                download_root=root / "download",
                fixture_root=root / "fixture",
                pdf_root=PDF.parent,
            )

            result = run_offline_fixture("cnipa", "pdf", config)

            self.assertEqual(result.status, "succeeded")
            self.assertEqual(result.written_count, 0)
            self.assertEqual(result.skipped_count, 1)
            conn = sqlite3.connect(config.database_path)
            try:
                first = conn.execute(
                    "SELECT title, source_url, long_term_url, detail_url, "
                    "detail_url_status, locator "
                    "FROM stage_source_items LIMIT 1"
                ).fetchone()
                raw_file_count = conn.execute(
                    "SELECT COUNT(*) FROM raw_files"
                ).fetchone()[0]
                std_count = conn.execute(
                    "SELECT COUNT(*) FROM std_agri_products"
                ).fetchone()[0]
            finally:
                conn.close()
            self.assertTrue(first[0])
            self.assertTrue(
                first[1].startswith(
                    "https://ggfw.cnipa.gov.cn/dlbzsq/detail?id="
                )
            )
            self.assertNotIn("X-Amz-Signature", first[1])
            self.assertEqual(first[2], first[1])
            self.assertIsNone(first[3])
            self.assertEqual(first[4], "missing")
            self.assertIn("page", first[5])
            self.assertEqual(raw_file_count, 1)
            self.assertEqual(std_count, 0)

    def test_pdf_product_rows_are_not_agri_publish_candidates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = OfflineFixtureConfig(
                database_path=root / "crawler.db",
                download_root=root / "download",
                fixture_root=root / "fixture",
                pdf_root=PDF.parent,
            )

            run_offline_fixture("cnipa", "pdf", config)
            result = run_batch(
                "agri",
                {
                    "batch_key": "cnipa-pdf-gate",
                    "converter_version": "test-v1",
                    "target_database": "yuexiang",
                    "dry_run": True,
                },
                crawler_database_path=config.database_path,
            )

            self.assertEqual(result.input_count, 0)
            self.assertEqual(result.inserted_count, 0)
            self.assertEqual(result.skipped_count, 0)
            self.assertEqual(result.by_entity["std_agri_products"]["rows"], [])

    def test_signature_url_is_not_persisted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = OfflineFixtureConfig(
                database_path=root / "crawler.db",
                download_root=root / "download",
                fixture_root=root / "fixture",
                pdf_root=PDF.parent,
            )
            run_offline_fixture("cnipa", "pdf", config)
            conn = sqlite3.connect(config.database_path)
            try:
                values = []
                for table, columns in (
                    (
                        "raw_fetches",
                        (
                            "request_url",
                            "final_url",
                            "source_url",
                            "long_term_url",
                            "fetch_url",
                        ),
                    ),
                    (
                        "raw_files",
                        (
                            "source_url",
                            "long_term_url",
                            "fetch_url",
                        ),
                    ),
                    (
                        "stage_source_items",
                        (
                            "source_url",
                            "long_term_url",
                            "fetch_url",
                        ),
                    ),
                ):
                    for column in columns:
                        values.extend(
                            row[0]
                            for row in conn.execute(
                                f"SELECT {column} FROM {table} "
                                f"WHERE {column} IS NOT NULL"
                            )
                        )
            finally:
                conn.close()
            self.assertTrue(values)
            self.assertTrue(all("X-Amz" not in value for value in values))

    def test_announcement_fixture_uses_long_term_detail_url(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = root / "cnipa"
            fixture.mkdir()
            (fixture / "announcements.json").write_text(
                '{"data":{"count":1,"data":[{"id":541,"name":"第687号","coding":"2026-08-03","type":2}]}}',
                encoding="utf-8",
            )
            config = OfflineFixtureConfig(
                database_path=root / "crawler.db",
                download_root=root / "download",
                fixture_root=fixture,
                pdf_root=PDF.parent,
            )
            result = run_offline_fixture("cnipa", "announcement-fixture", config)
            self.assertEqual(result.status, "succeeded")
            self.assertEqual(result.discovered_count, 1)
            conn = sqlite3.connect(config.database_path)
            try:
                stage = conn.execute(
                    "SELECT long_term_url, detail_url FROM stage_source_items"
                ).fetchone()
                raw_files = conn.execute(
                    "SELECT COUNT(*) FROM raw_files"
                ).fetchone()[0]
            finally:
                conn.close()
            self.assertEqual(
                stage,
                (
                    "https://ggfw.cnipa.gov.cn/dlbzsq/detail?id=541",
                    "https://ggfw.cnipa.gov.cn/dlbzsq/detail?id=541",
                ),
            )
            self.assertEqual(raw_files, 1)
