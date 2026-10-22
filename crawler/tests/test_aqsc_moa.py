import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from crawler.pipeline.offline_fixture import (
    OfflineFixtureConfig,
    run_offline_fixture,
)
from crawler.pipeline.converter import run_batch


ROOT = Path(__file__).resolve().parents[1]
DOWNLOAD = ROOT / "tests" / "fixtures" / "evidence" / "aqsc-moa"


class AqscMoaSourceTest(unittest.TestCase):
    def test_xlsx_rows_become_stage_products_with_source_locator(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = OfflineFixtureConfig(
                database_path=root / "crawler.db",
                download_root=root / "download",
                fixture_root=root / "fixture",
                xlsx_root=DOWNLOAD,
            )

            result = run_offline_fixture("aqsc-moa", "xlsx", config)

            self.assertEqual(result.status, "succeeded")
            self.assertEqual(result.written_count, 0)
            self.assertEqual(result.skipped_count, 8)
            conn = sqlite3.connect(config.database_path)
            try:
                first = conn.execute(
                    "SELECT title, source_url, long_term_url, detail_url, "
                    "detail_url_status, locator, extra "
                    "FROM stage_source_items LIMIT 1"
                ).fetchone()
                std_count = conn.execute(
                    "SELECT COUNT(*) FROM std_agri_products"
                ).fetchone()[0]
            finally:
                conn.close()
            self.assertTrue(first[0])
            self.assertTrue(first[1].startswith("http://www.aqsc.agri.cn/"))
            self.assertTrue(first[2].startswith("http://www.aqsc.agri.cn/tzgg/"))
            self.assertIsNone(first[3])
            self.assertEqual(first[4], "missing")
            self.assertIn("Sheet1", first[5])
            self.assertIsNone(json.loads(first[6])["is_aquatic"])
            self.assertEqual(std_count, 0)

    def test_xlsx_rows_are_evidence_only_and_never_enter_agri_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = OfflineFixtureConfig(
                database_path=root / "crawler.db",
                download_root=root / "download",
                fixture_root=root / "fixture",
                xlsx_root=DOWNLOAD,
            )

            run_offline_fixture("aqsc-moa", "xlsx", config)
            result = run_batch(
                "agri",
                {
                    "batch_key": "aqsc-xlsx-gate",
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
            conn = sqlite3.connect(config.database_path)
            try:
                stage_count = conn.execute(
                    "SELECT COUNT(*) FROM stage_source_items"
                ).fetchone()[0]
                raw_file_count = conn.execute(
                    "SELECT COUNT(*) FROM raw_files"
                ).fetchone()[0]
            finally:
                conn.close()
            self.assertEqual(stage_count, 8)
            self.assertEqual(raw_file_count, 2)

    def test_unknown_cert_type_is_not_invented(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = root / "fixture"
            fixture.mkdir()
            config = OfflineFixtureConfig(
                database_path=root / "crawler.db",
                download_root=root / "download",
                fixture_root=fixture,
                xlsx_root=DOWNLOAD,
            )

            result = run_offline_fixture("aqsc-moa", "xlsx", config)

            self.assertEqual(result.failed_count, 0)

    def test_aquatic_keywords_do_not_create_false_positive(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = OfflineFixtureConfig(
                database_path=root / "crawler.db",
                download_root=root / "download",
                fixture_root=root / "fixture",
                xlsx_root=DOWNLOAD,
            )
            run_offline_fixture("aqsc-moa", "xlsx", config)
            conn = sqlite3.connect(config.database_path)
            try:
                rows = conn.execute(
                    "SELECT title, extra FROM stage_source_items "
                    "WHERE title IN ('示例鲅鱼圈鸡蛋', '示例安溪毛蟹', "
                    "'示例仪征紫菜薹', '示例贝母', '示例丹参', "
                    "'示例鱼腥草', '示例螺丝椒')"
                ).fetchall()
            finally:
                conn.close()
            self.assertTrue(rows)
            for _, extra in rows:
                self.assertIsNone(json.loads(extra)["is_aquatic"])
