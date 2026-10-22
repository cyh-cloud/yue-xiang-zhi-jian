import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

from crawler.collection.shared.crawler_collection.admission import evaluate_admission
from crawler.collection.shared.crawler_collection.evidence import RawEvidence
from crawler.collection.shared.crawler_collection.items import CollectionItem
from crawler.collection.shared.crawler_collection.reporting import RunReport
from crawler.collection.shared.crawler_collection.robots import RobotsFact
from crawler.collection.shared.crawler_collection.runtime import CollectionRuntime


PROJECTS = Path(__file__).resolve().parents[1] / "collection" / "projects"
sys.path.insert(0, str(PROJECTS / "ihchina"))
from ihchina.candidate import write_candidate  # noqa: E402


class CollectionRuntimeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.db_path = self.root / "crawler.db"
        self.runtime = CollectionRuntime(
            database_path=self.db_path,
            download_root=self.root / "downloads",
            registry_path=Path("crawler/docs/sources.json"),
            candidate_writer=write_candidate,
        )

    def tearDown(self):
        self.tmp.cleanup()

    def _finish(self, conn):
        conn.commit()
        conn.close()

    def _item(self, **overrides):
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

    def _evidence(self, **overrides):
        payload = {
            "source_id": "ihchina",
            "request_url": "https://example.test/1",
            "final_url": "https://example.test/1",
            "body": b"<html>fixture</html>",
            "content_type": "text/html",
            "run_id": "run-1",
            "robots_decision": "allowed",
            "request_headers": {
                "User-Agent": "test",
                "Authorization": "secret",
            },
        }
        payload.update(overrides)
        return RawEvidence(**payload)

    def test_raw_is_appended_and_sensitive_headers_are_redacted(self):
        first_raw = self.runtime.persist_raw(self._evidence())
        second_raw = self.runtime.persist_raw(self._evidence())

        self.assertNotEqual(first_raw, second_raw)
        conn = sqlite3.connect(self.db_path)
        try:
            rows = conn.execute(
                "SELECT request_headers, body_sha256 FROM raw_fetches "
                "ORDER BY id"
            ).fetchall()
        finally:
            self._finish(conn)

        self.assertEqual(len(rows), 2)
        self.assertNotIn("secret", rows[0][0])
        self.assertIn("[redacted]", rows[0][0])
        self.assertEqual(rows[0][1], rows[1][1])

    def test_stage_and_candidate_are_idempotent(self):
        raw_id = self.runtime.persist_raw(self._evidence())
        item = self._item()

        first = self.runtime.write_item(item, raw_evidence_id=raw_id)
        second = self.runtime.write_item(item, raw_evidence_id=raw_id)

        self.assertEqual(first["candidate_status"], "candidate")
        self.assertEqual(second["candidate_status"], "candidate")
        conn = sqlite3.connect(self.db_path)
        try:
            stage_count = conn.execute(
                "SELECT COUNT(*) FROM stage_source_items"
            ).fetchone()[0]
            candidate_count = conn.execute(
                "SELECT COUNT(*) FROM std_ich_projects"
            ).fetchone()[0]
            candidate = conn.execute(
                "SELECT candidate_status, candidate_reason "
                "FROM std_ich_projects"
            ).fetchone()
        finally:
            self._finish(conn)

        self.assertEqual(stage_count, 1)
        self.assertEqual(candidate_count, 1)
        self.assertEqual(candidate, ("candidate", None))

    def test_runtime_returns_the_written_candidate_state_and_reason(self):
        raw_id = self.runtime.persist_raw(self._evidence())
        expected = (
            ("deferred", "missing_required_field"),
            ("blocked", "rights_review_required"),
        )

        for index, (status, reason) in enumerate(expected):
            with self.subTest(status=status):
                result = self.runtime.write_item(
                    self._item(
                        source_item_id=f"state-{index}",
                        candidate_status=status,
                        candidate_reason=reason,
                    ),
                    raw_evidence_id=raw_id,
                )
                self.assertEqual(result["candidate_status"], status)
                self.assertEqual(result["candidate_reason"], reason)

        conn = sqlite3.connect(self.db_path)
        try:
            rows = conn.execute(
                "SELECT candidate_status, candidate_reason "
                "FROM std_ich_projects ORDER BY source_item_id"
            ).fetchall()
        finally:
            self._finish(conn)
        self.assertEqual(rows, list(expected))

    def test_missing_detail_uses_carrier_and_locator_as_candidate(self):
        raw_id = self.runtime.persist_raw(self._evidence())
        item = self._item(
            detail_url=None,
            detail_url_status="missing",
            locator="attachment row 1",
        )

        result = self.runtime.write_item(item, raw_evidence_id=raw_id)

        self.assertEqual(result["candidate_status"], "candidate")
        conn = sqlite3.connect(self.db_path)
        try:
            stage_count = conn.execute(
                "SELECT COUNT(*) FROM stage_source_items"
            ).fetchone()[0]
            candidate_count = conn.execute(
                "SELECT COUNT(*) FROM std_ich_projects"
            ).fetchone()[0]
        finally:
            self._finish(conn)
        self.assertEqual(stage_count, 1)
        self.assertEqual(candidate_count, 1)

    def test_disabled_and_robots_rejected_sources_write_blocked_candidates(self):
        for evidence, item, robot in (
            (
                self._evidence(source_id="5ajob"),
                self._item(
                    source_id="5ajob",
                    source_item_id="disabled-source",
                ),
                RobotsFact("allowed"),
            ),
            (
                self._evidence(),
                self._item(source_item_id="robots-disallowed"),
                RobotsFact("disallowed"),
            ),
        ):
            raw_id = self.runtime.persist_raw(evidence)
            decision = evaluate_admission(
                item,
                registry_path=Path("crawler/docs/sources.json"),
                robots=robot,
            )
            result = self.runtime.write_item(
                item,
                raw_evidence_id=raw_id,
                admission=decision,
            )
            self.assertEqual(result["candidate_status"], "blocked")

        conn = sqlite3.connect(self.db_path)
        try:
            rows = conn.execute(
                "SELECT source_item_id, candidate_status, candidate_reason "
                "FROM std_ich_projects ORDER BY source_item_id"
            ).fetchall()
        finally:
            self._finish(conn)
        self.assertEqual(
            rows,
            [
                ("disabled-source", "blocked", "source_disabled"),
                ("robots-disallowed", "blocked", "robots:disallowed"),
            ],
        )

    def test_missing_candidate_writer_blocks_without_guessing_a_table(self):
        runtime = CollectionRuntime(
            database_path=self.db_path,
            download_root=self.root / "downloads",
            registry_path=Path("crawler/docs/sources.json"),
        )
        raw_id = runtime.persist_raw(self._evidence())

        result = runtime.write_item(self._item(), raw_evidence_id=raw_id)

        self.assertEqual(result["candidate_status"], "blocked")
        self.assertEqual(
            result["candidate_reason"], "candidate_writer:missing"
        )
        conn = sqlite3.connect(self.db_path)
        try:
            stage_count = conn.execute(
                "SELECT COUNT(*) FROM stage_source_items"
            ).fetchone()[0]
            candidate_count = conn.execute(
                "SELECT COUNT(*) FROM std_ich_projects"
            ).fetchone()[0]
        finally:
            self._finish(conn)
        self.assertEqual(stage_count, 1)
        self.assertEqual(candidate_count, 0)

    def test_run_report_counts_partial_and_failed(self):
        report = RunReport(
            run_id="run-1",
            source_id="ihchina",
            mode="fixture",
            discovered=2,
            written=1,
            blocked=1,
        )
        self.assertEqual(report.status, "partial")

        report = RunReport(
            run_id="run-1",
            source_id="ihchina",
            mode="fixture",
            discovered=0,
        )
        self.assertEqual(report.status, "failed")

    def test_oversize_file_writes_note_instead_of_body(self):
        raw_id = self.runtime.persist_raw(
            self._evidence(
                body=b"x",
                declared_size=100 * 1024 * 1024 + 1,
                metadata={"media_kind": "attachment"},
            )
        )
        conn = sqlite3.connect(self.db_path)
        try:
            row = conn.execute(
                "SELECT download_status, oversize_note, sha256 "
                "FROM raw_files "
                "WHERE raw_fetch_id = ?",
                (raw_id,),
            ).fetchone()
            fetch = conn.execute(
                "SELECT body_saved, body_sha256, body_path "
                "FROM raw_fetches WHERE id = ?",
                (raw_id,),
            ).fetchone()
        finally:
            self._finish(conn)
        self.assertEqual(row[0], "oversize")
        self.assertIn("exceeds", row[1])
        self.assertEqual(row[2], "")
        self.assertEqual(fetch, (0, None, None))

    def test_runtime_does_not_import_business_or_converter(self):
        source = (
            Path(__file__).resolve().parents[1]
            / "collection"
            / "shared"
            / "crawler_collection"
        )
        forbidden = ("backend", "crawler.pipeline.converter")
        for path in source.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            for token in forbidden:
                self.assertNotIn(f"import {token}", text, path)


if __name__ == "__main__":
    unittest.main()
