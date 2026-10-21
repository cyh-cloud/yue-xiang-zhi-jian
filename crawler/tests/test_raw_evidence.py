import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from crawler.pipeline import RunConfig, run_source
from crawler.pipeline import database
from crawler.pipeline.evidence import RawEvidence, persist_raw_evidence


ROOT = Path(__file__).resolve().parents[1]
AQSC = ROOT / "tests" / "fixtures" / "evidence" / "aqsc-moa"
CNIPA = ROOT / "tests" / "fixtures" / "evidence" / "cnipa"
NZRC = ROOT / "tests" / "fixtures" / "evidence" / "nzrc"


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class RawEvidenceTest(unittest.TestCase):
    def test_repeated_file_evidence_appends_and_uses_actual_size_and_final_url(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = root / "fixture-source"
            fixture.mkdir()
            body = "actual fixture bytes"
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
                                "locator": "fixture item 1",
                                "rights_status": "noncommercial-permitted",
                                "attribution_required": True,
                                "attribution_text": "Example source",
                                "rights_evidence_url": "https://example.test/copyright",
                                "fetched_url": "https://example.test/old/1",
                                "final_url": "https://example.test/final/1",
                                "detail_html": body,
                                "download": {
                                    "url": "https://example.test/files/sample.txt",
                                    "file_name": "sample.txt",
                                    "body": body,
                                    "declared_size": 1,
                                },
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            config = RunConfig(
                database_path=root / "crawler.db",
                download_root=root / "download",
                fixture_root=fixture,
            )

            first = run_source("fixture-source", "fixture", config)
            second = run_source("fixture-source", "fixture", config)

            self.assertEqual(first.status, "succeeded")
            self.assertEqual(second.status, "succeeded")
            conn = sqlite3.connect(config.database_path)
            try:
                file_rows = conn.execute(
                    """
                    SELECT raw_fetch_id, file_path, byte_size, sha256
                    FROM raw_files WHERE file_name = 'sample.txt'
                    ORDER BY id
                    """
                ).fetchall()
                fetch_rows = conn.execute(
                    """
                    SELECT id, final_url, body_bytes FROM raw_fetches
                    ORDER BY id
                    """
                ).fetchall()
            finally:
                conn.close()

            self.assertEqual(len(file_rows), 2)
            self.assertNotEqual(file_rows[0][0], file_rows[1][0])
            self.assertTrue(
                all(row[2] == len(body.encode("utf-8")) for row in file_rows)
            )
            self.assertTrue(
                all(row[3] == hashlib.sha256(body.encode("utf-8")).hexdigest() for row in file_rows)
            )
            detail_fetches = [
                row for row in fetch_rows
                if row[1] == "https://example.test/final/1"
            ]
            self.assertEqual(len(detail_fetches), 2)
            self.assertTrue(
                all(row[2] == len(body.encode("utf-8")) for row in detail_fetches)
            )

    def test_missing_detail_evidence_requires_a_locator(self):
        with tempfile.TemporaryDirectory() as tmp:
            conn = database.connect(Path(tmp) / "crawler.db")
            try:
                with self.assertRaises(ValueError):
                    persist_raw_evidence(
                        conn,
                        RawEvidence(
                            source_id="fixture-source",
                            key="invalid",
                            request_url="https://example.test/announcement",
                            final_url="https://example.test/announcement",
                            source_url="https://example.test/announcement",
                            long_term_url="https://example.test/announcement",
                            detail_url=None,
                            detail_url_status="missing",
                            fetch_url=None,
                            locator=None,
                            body=b"fixture",
                            content_type="text/plain",
                        ),
                        Path(tmp) / "download",
                        1024,
                        "2026-10-20T00:00:00+00:00",
                    )
            finally:
                conn.close()

    def test_aqsc_xlsx_evidence_uses_documented_urls_and_actual_file_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = RunConfig(
                database_path=root / "crawler.db",
                download_root=root / "download",
                fixture_root=root / "fixture",
                xlsx_root=AQSC,
            )

            result = run_source("aqsc-moa", "xlsx", config)

            self.assertEqual(result.written_count, 0)
            self.assertEqual(result.skipped_count, 8)
            conn = sqlite3.connect(config.database_path)
            try:
                fetches = conn.execute(
                    """
                    SELECT request_url, final_url, source_url, long_term_url,
                           detail_url, detail_url_status, content_type,
                           body_sha256, body_path, response_headers,
                           body_saved, locator, fetch_status
                    FROM raw_fetches ORDER BY id
                    """
                ).fetchall()
                files = conn.execute(
                    """
                    SELECT source_url, long_term_url, file_path, file_name,
                           mime_type, file_ext, byte_size, sha256, locator,
                           download_status
                    FROM raw_files ORDER BY id
                    """
                ).fetchall()
                std_count = conn.execute(
                    "SELECT COUNT(*) FROM std_agri_products"
                ).fetchone()[0]
            finally:
                conn.close()

            expected = {
                "synthetic-mtyx-sample.xlsx": {
                    "announcement": (
                        "http://www.aqsc.agri.cn/tzgg/202511/"
                        "t20251128_468194.htm"
                    ),
                    "attachment": (
                        "http://www.aqsc.agri.cn/tzgg/202511/"
                        "P020251225613822033339.xlsx"
                    ),
                },
                "synthetic-tepinongpin-sample.xlsx": {
                    "announcement": (
                        "http://www.aqsc.agri.cn/tzgg/202511/"
                        "t20251128_468195.htm"
                    ),
                    "attachment": (
                        "http://www.aqsc.agri.cn/tzgg/202511/"
                        "P020251128359343750170.xlsx"
                    ),
                },
            }
            self.assertEqual(len(fetches), 2)
            self.assertEqual(len(files), 2)
            self.assertEqual(std_count, 0)

            for fetch in fetches:
                file_name = next(
                    name
                    for name, urls in expected.items()
                    if fetch[0] == urls["attachment"]
                )
                source_path = AQSC / file_name
                self.assertEqual(fetch[1], fetch[0])
                self.assertEqual(fetch[2], expected[file_name]["attachment"])
                self.assertEqual(fetch[3], expected[file_name]["announcement"])
                self.assertIsNone(fetch[4])
                self.assertEqual(fetch[5], "missing")
                self.assertIn("spreadsheet", fetch[6])
                self.assertEqual(fetch[7], _sha256(source_path))
                self.assertTrue((config.download_root / fetch[8]).exists())
                self.assertTrue(json.loads(fetch[9]))
                self.assertEqual(fetch[10], 1)
                self.assertTrue(fetch[11])
                self.assertEqual(fetch[12], "ok")

            for file_row in files:
                file_name = file_row[3]
                self.assertEqual(file_row[0], expected[file_name]["attachment"])
                self.assertEqual(file_row[1], expected[file_name]["announcement"])
                self.assertTrue((config.download_root / file_row[2]).exists())
                self.assertIn("spreadsheet", file_row[4])
                self.assertEqual(file_row[5], ".xlsx")
                self.assertEqual(file_row[6], (AQSC / file_name).stat().st_size)
                self.assertEqual(file_row[7], _sha256(AQSC / file_name))
                self.assertTrue(file_row[8])
                self.assertEqual(file_row[9], "saved")

    def test_cnipa_pdf_evidence_keeps_stable_detail_url_and_file_hash(self):
        pdf = next(CNIPA.glob("*.pdf"))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = RunConfig(
                database_path=root / "crawler.db",
                download_root=root / "download",
                fixture_root=root / "fixture",
                pdf_root=CNIPA,
            )

            result = run_source("cnipa", "pdf", config)

            self.assertEqual(result.written_count, 0)
            self.assertEqual(result.skipped_count, 1)
            conn = sqlite3.connect(config.database_path)
            try:
                fetch = conn.execute(
                    """
                    SELECT request_url, final_url, source_url, long_term_url,
                           content_type, body_sha256, body_path, locator
                    FROM raw_fetches
                    """
                ).fetchone()
                file_row = conn.execute(
                    """
                    SELECT source_url, long_term_url, file_path, file_name,
                           mime_type, file_ext, byte_size, sha256
                    FROM raw_files
                    """
                ).fetchone()
                std_count = conn.execute(
                    "SELECT COUNT(*) FROM std_agri_products"
                ).fetchone()[0]
            finally:
                conn.close()

            self.assertEqual(
                fetch[0],
                "https://ggfw.cnipa.gov.cn/dlbzsq/detail?id=541",
            )
            self.assertEqual(fetch[1], fetch[0])
            self.assertEqual(fetch[2], fetch[0])
            self.assertEqual(fetch[3], fetch[0])
            self.assertEqual(fetch[4], "application/pdf")
            self.assertEqual(fetch[5], _sha256(pdf))
            self.assertTrue((config.download_root / fetch[6]).exists())
            self.assertTrue(fetch[7])
            self.assertEqual(file_row[0], fetch[0])
            self.assertEqual(file_row[1], fetch[0])
            self.assertTrue((config.download_root / file_row[2]).exists())
            self.assertEqual(file_row[3], pdf.name)
            self.assertEqual(file_row[4], "application/pdf")
            self.assertEqual(file_row[5], ".pdf")
            self.assertEqual(file_row[6], pdf.stat().st_size)
            self.assertEqual(file_row[7], _sha256(pdf))
            self.assertEqual(std_count, 0)

    def test_ihchina_fixture_records_each_list_page_url_and_raw_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = root / "ihchina"
            fixture.mkdir()
            pages = [
                {
                    "total": 2,
                    "count": 2,
                    "p": 1,
                    "links": {"total_pages": 2},
                    "list": [{"id": 1, "title": "A", "num": "Ⅰ-1"}],
                },
                {
                    "total": 2,
                    "count": 2,
                    "p": 2,
                    "links": {"total_pages": 2},
                    "list": [{"id": 2, "title": "B", "num": "Ⅰ-2"}],
                },
            ]
            (fixture / "discover.json").write_text(
                json.dumps({"pages": pages}, ensure_ascii=False),
                encoding="utf-8",
            )
            config = RunConfig(
                database_path=root / "crawler.db",
                download_root=root / "download",
                fixture_root=fixture,
                page_limit=1,
            )

            result = run_source("ihchina", "fixture", config)

            self.assertEqual(result.discovered_count, 2)
            self.assertEqual(result.written_count, 2)
            conn = sqlite3.connect(config.database_path)
            try:
                fetches = conn.execute(
                    """
                    SELECT request_url, final_url, body_path, body_sha256,
                           content_type, locator, metadata_json
                    FROM raw_fetches ORDER BY id
                    """
                ).fetchall()
                files = conn.execute(
                    "SELECT file_path, sha256, mime_type FROM raw_files ORDER BY id"
                ).fetchall()
            finally:
                conn.close()

            self.assertEqual(len(fetches), 2)
            self.assertEqual(len(files), 2)
            for page_no, fetch in enumerate(fetches, start=1):
                self.assertIn("category_id=16", fetch[0])
                self.assertIn("limit=1", fetch[0])
                self.assertIn(f"p={page_no}", fetch[0])
                self.assertEqual(fetch[1], fetch[0])
                self.assertTrue((config.download_root / fetch[2]).exists())
                self.assertTrue(fetch[3])
                self.assertEqual(fetch[4], "application/json")
                self.assertIn(f"page={page_no}", fetch[5])
                metadata = json.loads(fetch[6])
                self.assertEqual(metadata["page"], page_no)

    def test_saved_html_evidence_keeps_actual_bytes_and_content_type(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = RunConfig(
                database_path=root / "crawler.db",
                download_root=root / "download",
                fixture_root=root / "fixture",
                source_root=NZRC,
            )

            run_source("nzrc", "saved", config)

            conn = sqlite3.connect(config.database_path)
            try:
                rows = conn.execute(
                    """
                    SELECT f.body_sha256, f.content_type, f.body_path,
                           r.file_path, r.sha256, r.mime_type
                    FROM raw_fetches f
                    JOIN raw_files r ON r.raw_fetch_id = f.id
                    ORDER BY f.id
                    """
                ).fetchall()
            finally:
                conn.close()
            expected_hashes = {_sha256(path) for path in NZRC.glob("*.html")}
            self.assertEqual({row[0] for row in rows}, expected_hashes)
            self.assertTrue(all(row[1] == "text/html" for row in rows))
            self.assertTrue(
                all((config.download_root / row[2]).exists() for row in rows)
            )
            self.assertTrue(
                all((config.download_root / row[3]).exists() for row in rows)
            )
            self.assertEqual({row[4] for row in rows}, expected_hashes)
            self.assertTrue(all(row[5] == "text/html" for row in rows))


if __name__ == "__main__":
    unittest.main()
