import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from crawler.pipeline.offline_fixture import (
    OfflineFixtureConfig,
    run_offline_fixture,
)
from crawler.pipeline.offline_fixture import OFFLINE_MODES


FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "fixture-source"


class OfflineFixtureContractTest(unittest.TestCase):
    def test_offline_modes_do_not_include_live(self):
        self.assertEqual(
            set(OFFLINE_MODES),
            {
                "fixture",
                "xlsx",
                "pdf",
                "saved",
                "announcement-fixture",
            },
        )
        self.assertNotIn("live", OFFLINE_MODES)

    def test_legacy_online_entrypoints_are_retired(self):
        crawler_root = Path(__file__).resolve().parents[1]
        self.assertFalse((crawler_root / "run.py").exists())
        self.assertFalse(
            (crawler_root / "pipeline" / "run_source.py").exists()
        )

        import crawler.pipeline as pipeline

        self.assertFalse(hasattr(pipeline, "run_source"))
        self.assertFalse(hasattr(pipeline, "RUN_MODES"))

    def test_live_mode_is_rejected_before_any_writer_is_opened(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = OfflineFixtureConfig(
                database_path=root / "crawler.db",
                download_root=root / "download",
                fixture_root=root / "fixture",
            )

            with self.assertRaisesRegex(ValueError, "Scrapy"):
                run_offline_fixture("ihchina", "live", config)

            self.assertFalse(config.database_path.exists())

    def test_unsupported_source_mode_combinations_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = OfflineFixtureConfig(
                database_path=Path(tmp) / "crawler.db",
                download_root=Path(tmp) / "download",
                fixture_root=Path(tmp) / "fixture",
            )
            with self.assertRaises(ValueError):
                run_offline_fixture("aqsc-moa", "pdf", config)
            with self.assertRaises(ValueError):
                run_offline_fixture("cnipa", "xlsx", config)

    def test_fixture_source_runs_through_all_layers_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = OfflineFixtureConfig(
                database_path=root / "crawler.db",
                download_root=root / "download",
                fixture_root=FIXTURE_ROOT,
            )

            first = run_offline_fixture("fixture-source", "fixture", config)
            second = run_offline_fixture("fixture-source", "fixture", config)

            self.assertEqual(first.status, "succeeded")
            self.assertGreaterEqual(first.discovered_count, 1)
            self.assertGreaterEqual(first.fetched_count, 1)
            self.assertGreaterEqual(first.written_count, 1)
            self.assertEqual(second.status, "succeeded")
            self.assertEqual(second.written_count, first.written_count)

            conn = sqlite3.connect(config.database_path)
            try:
                raw = conn.execute(
                    "SELECT source_id, request_url, final_url, source_url, "
                    "long_term_url, detail_url, detail_url_status, fetch_url, "
                    "rights_status, attribution_required, attribution_text, "
                    "rights_evidence_url, body_sha256 FROM raw_fetches"
                ).fetchall()
                stage = conn.execute(
                    "SELECT source_id, source_url, long_term_url, detail_url, detail_url_status, rights_status FROM stage_fixture_items ORDER BY id"
                ).fetchall()
                std = conn.execute(
                    "SELECT source_id, source_item_id, source_url, long_term_url, detail_url_status FROM std_jobs"
                ).fetchall()
            finally:
                conn.close()

            self.assertEqual(len(raw), 2)
            self.assertEqual(len(stage), 1)
            self.assertEqual(len(std), 1)
            self.assertTrue(
                all(
                    row[1]
                    and row[2]
                    and row[3]
                    and row[4] == "direct"
                    and row[5]
                    for row in stage
                )
            )
            self.assertTrue(
                all(
                    row[3]
                    and row[4]
                    and row[5] is None
                    and row[6] == "missing"
                    and row[7]
                    and row[8] == "noncommercial-permitted"
                    and row[9] == 1
                    and row[10]
                    and row[11]
                    for row in raw
                )
            )
            self.assertTrue(std[0][2] and std[0][3] and std[0][4] == "direct")

    def test_record_without_direct_detail_url_stays_out_of_publishable_std(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = root / "fixture-source"
            fixture.mkdir()
            (fixture / "discover.json").write_text(
                json.dumps(
                    {
                        "source_id": "fixture-source",
                        "items": [
                            {
                                "source_item_id": "no-detail",
                                "title": "No detail fixture",
                                "source_url": "https://example.test/announcement",
                                "long_term_url": "https://example.test/announcement",
                                "detail_url": None,
                                "detail_url_status": "missing",
                                "locator": "attachment row 1",
                                "rights_status": "noncommercial-permitted",
                                "attribution_required": True,
                                "attribution_text": "Example",
                                "rights_evidence_url": "https://example.test/copyright",
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            config = OfflineFixtureConfig(
                database_path=root / "crawler.db",
                download_root=root / "download",
                fixture_root=fixture,
            )

            result = run_offline_fixture("fixture-source", "fixture", config)

            self.assertEqual(result.status, "succeeded")
            self.assertEqual(result.written_count, 0)
            self.assertEqual(result.skipped_count, 1)
            conn = sqlite3.connect(config.database_path)
            try:
                stage_count = conn.execute("SELECT COUNT(*) FROM stage_fixture_items").fetchone()[0]
                std_count = conn.execute("SELECT COUNT(*) FROM std_jobs").fetchone()[0]
            finally:
                conn.close()
            self.assertEqual(stage_count, 1)
            self.assertEqual(std_count, 0)

    def test_source_runner_applies_one_publication_disposition_per_item(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = root / "fixture-source"
            fixture.mkdir()
            common = {
                "rights_status": "noncommercial-permitted",
                "attribution_required": True,
                "attribution_text": "Example",
                "rights_evidence_url": "https://example.test/copyright",
            }
            items = [
                {
                    **common,
                    "source_item_id": "missing",
                    "title": "Missing detail",
                    "source_url": "https://example.test/jobs/list",
                    "long_term_url": "https://example.test/jobs/announcement",
                    "detail_url": "https://example.test/jobs/announcement",
                    "detail_url_status": "missing",
                    "locator": "announcement attachment row 1",
                    "publish_status": "draft",
                },
                {
                    **common,
                    "source_item_id": "null",
                    "title": "Null detail",
                    "source_url": "https://example.test/jobs/list",
                    "long_term_url": "https://example.test/jobs/null",
                    "detail_url": None,
                    "detail_url_status": "direct",
                    "publish_status": "draft",
                },
                {
                    **common,
                    "source_item_id": "blocked",
                    "title": "Blocked detail",
                    "source_url": "https://example.test/jobs/list",
                    "long_term_url": "https://example.test/jobs/blocked",
                    "detail_url": "https://example.test/jobs/blocked",
                    "detail_url_status": "direct",
                    "publish_status": "blocked",
                },
                {
                    **common,
                    "source_item_id": "valid",
                    "title": "Valid detail",
                    "source_url": "https://example.test/jobs/list",
                    "long_term_url": "https://example.test/jobs/valid",
                    "detail_url": "https://example.test/jobs/valid",
                    "detail_url_status": "direct",
                    "publish_status": "draft",
                },
            ]
            (fixture / "discover.json").write_text(
                json.dumps({"source_id": "fixture-source", "items": items}),
                encoding="utf-8",
            )
            config = OfflineFixtureConfig(
                database_path=root / "crawler.db",
                download_root=root / "download",
                fixture_root=fixture,
            )

            result = run_offline_fixture("fixture-source", "fixture", config)

            self.assertEqual(result.discovered_count, 4)
            self.assertEqual(result.written_count, 1)
            self.assertEqual(result.skipped_count, 3)
            self.assertEqual(result.failed_count, 0)
            self.assertEqual(
                result.written_count + result.skipped_count + result.failed_count,
                result.discovered_count,
            )
            conn = sqlite3.connect(config.database_path)
            try:
                self.assertEqual(
                    conn.execute("SELECT COUNT(*) FROM stage_fixture_items").fetchone()[0],
                    3,
                )
                rows = conn.execute(
                    "SELECT source_item_id FROM std_jobs"
                ).fetchall()
            finally:
                conn.close()
            self.assertEqual(rows, [("valid",)])


    def test_download_files_are_hashed_and_private_session_directory_is_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = root / "fixture-source"
            fixture.mkdir()
            (fixture / "discover.json").write_text(
                json.dumps(
                    {
                        "source_id": "fixture-source",
                        "items": [
                            {
                                "source_item_id": "1",
                                "title": "Fixture source item",
                                "source_url": "https://example.test/item/1",
                                "long_term_url": "https://example.test/item/1",
                                "detail_url": "https://example.test/item/1",
                                "detail_url_status": "direct",
                                "locator": "attachment row 1",
                                "rights_status": "noncommercial-permitted",
                                "attribution_required": True,
                                "attribution_text": "Example source",
                                "rights_evidence_url": "https://example.test/copyright",
                                "download": {
                                    "url": "https://example.test/files/sample.txt",
                                    "file_name": "sample.txt",
                                    "body": "fixture body",
                                },
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            config = OfflineFixtureConfig(
                database_path=root / "crawler.db",
                download_root=root / "download",
                fixture_root=fixture,
            )

            result = run_offline_fixture("fixture-source", "fixture", config)

            self.assertEqual(result.status, "succeeded")
            saved = config.download_root / "example.test" / "sample.txt"
            self.assertTrue(saved.exists())
            conn = sqlite3.connect(config.database_path)
            try:
                row = conn.execute(
                    "SELECT file_path, byte_size, sha256, source_url, "
                    "raw_fetch_id, long_term_url, detail_url, detail_url_status, "
                    "fetch_url, locator, rights_status FROM raw_files "
                    "WHERE file_name = 'sample.txt'"
                ).fetchone()
            finally:
                conn.close()
            self.assertIsNotNone(row)
            self.assertEqual(row[0], "example.test/sample.txt")
            self.assertEqual(row[1], len("fixture body"))
            self.assertEqual(row[2], hashlib.sha256(b"fixture body").hexdigest())
            self.assertEqual(row[3], "https://example.test/files/sample.txt")
            self.assertIsNotNone(row[4])
            self.assertEqual(row[5], "https://example.test/item/1")
            self.assertEqual(row[6], "https://example.test/item/1")
            self.assertEqual(row[7], "direct")
            self.assertEqual(row[8], "https://example.test/files/sample.txt")
            self.assertEqual(row[9], "attachment row 1")
            self.assertEqual(row[10], "noncommercial-permitted")

    def test_oversize_download_writes_note_instead_of_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = root / "fixture-source"
            fixture.mkdir()
            (fixture / "discover.json").write_text(
                json.dumps(
                    {
                        "source_id": "fixture-source",
                        "items": [
                            {
                                "source_item_id": "1",
                                "title": "Fixture source item",
                                "source_url": "https://example.test/item/1",
                                "long_term_url": "https://example.test/item/1",
                                "detail_url": "https://example.test/item/1",
                                "detail_url_status": "direct",
                                "locator": "attachment row 1",
                                "rights_status": "noncommercial-permitted",
                                "attribution_required": True,
                                "attribution_text": "Example source",
                                "rights_evidence_url": "https://example.test/copyright",
                                "download": {
                                    "url": "https://example.test/files/huge.bin",
                                    "file_name": "huge.bin",
                                    "declared_size": 100 * 1024 * 1024 + 1,
                                },
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            config = OfflineFixtureConfig(
                database_path=root / "crawler.db",
                download_root=root / "download",
                fixture_root=fixture,
            )

            result = run_offline_fixture("fixture-source", "fixture", config)

            self.assertEqual(result.status, "succeeded")
            domain_dir = config.download_root / "example.test"
            self.assertFalse((domain_dir / "huge.bin").exists())
            self.assertTrue((domain_dir / "OVERSIZE.md").exists())
            conn = sqlite3.connect(config.database_path)
            try:
                row = conn.execute(
                    "SELECT raw_fetch_id, source_url, long_term_url, detail_url, "
                    "detail_url_status, fetch_url, locator, rights_status "
                    "FROM raw_files WHERE file_name = 'huge.bin'"
                ).fetchone()
            finally:
                conn.close()
            self.assertIsNotNone(row[0])
            self.assertEqual(row[1], "https://example.test/files/huge.bin")
            self.assertEqual(row[2], "https://example.test/item/1")
            self.assertEqual(row[3], "https://example.test/item/1")
            self.assertEqual(row[4], "direct")
            self.assertEqual(row[5], "https://example.test/files/huge.bin")
            self.assertEqual(row[6], "attachment row 1")
            self.assertEqual(row[7], "noncommercial-permitted")
