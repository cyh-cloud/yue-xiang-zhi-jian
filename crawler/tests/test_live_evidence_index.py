import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from crawler.tools.build_live_evidence_index import (
    build_live_evidence_index,
    validate_live_evidence_index,
)


ROOT = Path(__file__).resolve().parents[2]
INDEX = ROOT / "crawler" / "docs" / "operations" / "live-evidence-index.json"


def _valid_index_payload():
    return {
        "schema_version": 1,
        "generated_at": "2026-10-21T00:02:00+00:00",
        "archive_root": "../crawler-live-evidence/test",
        "public_repository_policy": "Metadata only.",
        "source_count": 1,
        "runs": [
            {
                "source_id": "ihchina",
                "run_id": "run-1",
                "mode": "live",
                "status": "partial",
                "started_at": "2026-10-21T00:00:00+00:00",
                "finished_at": "2026-10-21T00:01:00+00:00",
                "retrieval_time": "2026-10-21T00:01:00+00:00",
                "archive_path": "ihchina",
                "report_path": "ihchina/reports/run-1.json",
                "database_path": "ihchina/crawler.db",
                "download_root": "ihchina/download",
                "acceptance_record": (
                    "crawler/docs/reviews/ihchina-scrapy-sample.md"
                ),
                "source_urls": ["https://example.test/list"],
                "list_urls": [],
                "detail_urls": [],
                "carrier_urls": ["https://example.test/list"],
                "attachment_urls": [],
                "counts": {
                    "raw": 1,
                    "stage": 1,
                    "candidate": 0,
                    "deferred": 1,
                    "blocked": 0,
                    "failed": 0,
                    "skipped": 0,
                },
                "failure_summary": None,
                "blocking_reason": None,
                "candidate_reasons": [
                    {
                        "status": "deferred",
                        "reason": "robots:not-found",
                        "count": 1,
                    }
                ],
                "responses": [
                    {
                        "role": "carrier",
                        "url": "https://example.test/list",
                        "final_url": "https://example.test/list",
                        "source_url": "https://example.test/list",
                        "carrier_url": "https://example.test/list",
                        "detail_url": None,
                        "attachment_url": None,
                        "retrieved_at": "2026-10-21T00:00:30+00:00",
                        "http_status": 200,
                        "content_type": "text/html",
                        "byte_size": 10,
                        "sha256": "a" * 64,
                        "robots_decision": "not-found",
                        "fetch_status": "ok",
                        "error": None,
                    }
                ],
            }
        ],
    }


class LiveEvidenceIndexTest(unittest.TestCase):
    def test_builder_redacts_signed_urls_and_keeps_required_metadata(self):
        with tempfile.TemporaryDirectory(dir=ROOT.parent) as tmp:
            archive = Path(tmp) / "archive"
            source = archive / "ihchina"
            reports = source / "reports"
            reports.mkdir(parents=True)
            database = source / "crawler.db"
            conn = sqlite3.connect(database)
            try:
                conn.executescript(
                    """
                    CREATE TABLE raw_fetches (
                        id INTEGER PRIMARY KEY,
                        request_url TEXT,
                        final_url TEXT,
                        source_url TEXT,
                        long_term_url TEXT,
                        detail_url TEXT,
                        fetch_url TEXT,
                        status_code INTEGER,
                        content_type TEXT,
                        body_bytes INTEGER,
                        body_sha256 TEXT,
                        robots_decision TEXT,
                        fetch_status TEXT,
                        error_message TEXT,
                        retrieved_at TEXT,
                        metadata_json TEXT,
                        run_id TEXT
                    );
                    CREATE TABLE std_ich_projects (
                        id INTEGER PRIMARY KEY,
                        run_id TEXT,
                        candidate_status TEXT,
                        candidate_reason TEXT
                    );
                    """
                )
                conn.execute(
                    "INSERT INTO raw_fetches "
                    "(request_url, final_url, source_url, long_term_url, "
                    "detail_url, fetch_url, status_code, content_type, "
                    "body_bytes, body_sha256, robots_decision, fetch_status, "
                    "error_message, retrieved_at, metadata_json, run_id) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        "https://example.test/file.pdf?X-Amz-Signature=secret",
                        "https://example.test/file.pdf",
                        "https://example.test/carrier",
                        "https://example.test/carrier",
                        None,
                        "https://example.test/file.pdf?X-Amz-Signature=secret",
                        200,
                        "application/pdf",
                        10,
                        "a" * 64,
                        "not-found",
                        "ok",
                        None,
                        "2026-10-21T00:00:00+00:00",
                        '{"file_name":"file.pdf","media_kind":"attachment"}',
                        "run-1",
                    ),
                )
                conn.execute(
                    "INSERT INTO std_ich_projects "
                    "(run_id, candidate_status, candidate_reason) "
                    "VALUES ('run-1', 'deferred', 'robots:not-found')"
                )
                conn.commit()
            finally:
                conn.close()
            (reports / "run-1.json").write_text(
                json.dumps(
                    {
                        "run_id": "run-1",
                        "source_id": "ihchina",
                        "mode": "live",
                        "status": "partial",
                        "started_at": "2026-10-21T00:00:00+00:00",
                        "finished_at": "2026-10-21T00:01:00+00:00",
                        "raw_count": 1,
                        "stage_count": 1,
                        "candidate_count": 0,
                        "deferred": 1,
                        "blocked": 0,
                        "failure_count": 0,
                        "skipped": 0,
                        "failure_reason": None,
                    }
                ),
                encoding="utf-8",
            )
            output = Path(tmp) / "index.json"

            payload = build_live_evidence_index(archive, output)

            self.assertEqual(payload["source_count"], 1)
            run = payload["runs"][0]
            self.assertEqual(run["counts"]["deferred"], 1)
            self.assertEqual(
                run["attachment_urls"], ["https://example.test/file.pdf"]
            )
            self.assertNotIn(
                "X-Amz-Signature",
                output.read_text(encoding="utf-8"),
            )
            self.assertEqual(validate_live_evidence_index(output), [])

    def test_committed_index_has_required_public_metadata(self):
        self.assertTrue(INDEX.is_file(), INDEX)
        payload = json.loads(INDEX.read_text(encoding="utf-8"))

        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["source_count"], 8)
        self.assertEqual(len(payload["runs"]), 8)
        self.assertEqual(validate_live_evidence_index(INDEX), [])
        for run in payload["runs"]:
            self.assertIn("retrieval_time", run)
            self.assertIn("responses", run)
            self.assertTrue(run["acceptance_record"].endswith(".md"))

    def test_validator_rejects_non_metadata_response_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "index.json"
            payload = _valid_index_payload()
            payload["runs"][0]["responses"][0]["body"] = "full source text"
            output.write_text(
                json.dumps(payload, ensure_ascii=False),
                encoding="utf-8",
            )

            errors = validate_live_evidence_index(output)

            self.assertTrue(
                any("unexpected fields body" in error for error in errors)
            )

    def test_validator_rejects_signed_urls_in_any_url_field(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "index.json"
            payload = _valid_index_payload()
            payload["runs"][0]["responses"][0]["detail_url"] = (
                "https://example.test/detail?X-Amz-Signature=secret"
            )
            output.write_text(
                json.dumps(payload, ensure_ascii=False),
                encoding="utf-8",
            )

            errors = validate_live_evidence_index(output)

            self.assertTrue(
                any("sensitive query parameter" in error for error in errors)
            )

    def test_validate_only_cli_does_not_require_archive_root(self):
        from crawler.tools import build_live_evidence_index

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "index.json"
            output.write_text(
                json.dumps(_valid_index_payload(), ensure_ascii=False),
                encoding="utf-8",
            )

            result = build_live_evidence_index.main(
                ["--validate-only", "--output", str(output)]
            )

            self.assertEqual(result, 0)


if __name__ == "__main__":
    unittest.main()
