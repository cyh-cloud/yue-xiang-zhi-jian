import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

from scrapy.http import HtmlResponse, Request

from crawler.collection.shared.crawler_collection.admission import (
    AdmissionDecision,
    evaluate_admission,
)
from crawler.collection.shared.crawler_collection.evidence import RawEvidence
from crawler.collection.shared.crawler_collection.items import (
    CollectionItem,
    item_from_mapping,
    validate_item,
)
from crawler.collection.shared.crawler_collection.reporting import (
    RunReport,
    build_run_report,
)
from crawler.collection.shared.crawler_collection.robots import RobotsFact
from crawler.collection.shared.crawler_collection.runtime import CollectionRuntime


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "docs" / "sources.json"
PROJECTS = ROOT / "collection" / "projects"
sys.path.insert(0, str(PROJECTS / "ihchina"))
from ihchina.candidate import write_candidate  # noqa: E402


def _item(**overrides):
    payload = {
        "source_id": "ihchina",
        "source_item_id": "state-1",
        "source_url": "https://example.test/1",
        "long_term_url": "https://example.test/1",
        "detail_url": "https://example.test/1",
        "detail_url_status": "direct",
        "run_id": "run-state",
        "mode": "fixture",
        "title": "状态契约",
    }
    payload.update(overrides)
    return CollectionItem(**payload)


class CollectionStateAdmissionTest(unittest.TestCase):
    def test_item_rights_may_start_unset(self):
        payload = validate_item(_item())

        self.assertIsNone(payload["rights_status"])
        self.assertIsNone(payload["attribution_required"])

    def test_spider_mapping_does_not_prefill_rights(self):
        request = Request(
            "https://example.test/1",
            meta={"run_id": "run-state"},
        )
        response = HtmlResponse(
            "https://example.test/1",
            body=b"<html></html>",
            encoding="utf-8",
            request=request,
        )

        item = item_from_mapping(
            {
                "source_item_id": "state-1",
                "source_url": "https://example.test/1",
                "long_term_url": "https://example.test/1",
                "detail_url": "https://example.test/1",
                "detail_url_status": "direct",
                "title": "状态契约",
            },
            source_id="ihchina",
            response=response,
        )

        self.assertIsNone(item.rights_status)
        self.assertIsNone(item.attribution_required)

    def test_robots_not_found_is_allowed_as_deferred(self):
        decision = evaluate_admission(
            _item(rights_status="attribution-required"),
            registry_path=REGISTRY,
            robots=RobotsFact("not-found"),
        )

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.status, "deferred")
        self.assertEqual(decision.reason, "robots:not-found")

    def test_actual_http_error_remains_blocked(self):
        decision = evaluate_admission(
            _item(rights_status="attribution-required"),
            registry_path=REGISTRY,
            robots=RobotsFact("allowed"),
            fetch_status="http_error",
            status_code=403,
        )

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.status, "blocked")
        self.assertIn("fetch", decision.reason)

    def test_carrier_url_and_locator_allow_missing_detail_url(self):
        decision = evaluate_admission(
            _item(
                rights_status="attribution-required",
                detail_url=None,
                detail_url_status="missing",
                locator="sheet=产品; row=2",
            ),
            registry_path=REGISTRY,
            robots=RobotsFact("allowed"),
        )

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.status, "candidate")

    def test_explicit_deferred_state_is_preserved(self):
        decision = evaluate_admission(
            _item(
                rights_status="attribution-required",
                candidate_status="deferred",
                candidate_reason="batch:later",
            ),
            registry_path=REGISTRY,
            robots=RobotsFact("allowed"),
        )

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.status, "deferred")
        self.assertEqual(decision.reason, "batch:later")

    def test_deferred_item_may_omit_carrier_and_locator(self):
        payload = validate_item(
            _item(
                long_term_url=None,
                detail_url=None,
                detail_url_status="missing",
                locator=None,
                candidate_status="deferred",
                candidate_reason="carrier:missing",
            )
        )

        self.assertEqual(payload["candidate_status"], "deferred")
        self.assertIsNone(payload["long_term_url"])
        self.assertIsNone(payload["locator"])

    def test_candidate_item_still_requires_carrier_and_locator(self):
        with self.assertRaises(ValueError):
            validate_item(
                _item(
                    long_term_url=None,
                    detail_url=None,
                    detail_url_status="missing",
                    locator=None,
                )
            )


class CollectionStateRuntimeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.database_path = self.root / "crawler.db"
        self.runtime = CollectionRuntime(
            database_path=self.database_path,
            download_root=self.root / "download",
            registry_path=REGISTRY,
            candidate_writer=write_candidate,
        )

    def tearDown(self):
        self.tmp.cleanup()

    def _raw(self, **overrides):
        payload = {
            "source_id": "ihchina",
            "request_url": "https://example.test/1",
            "final_url": "https://example.test/1",
            "body": b"<html>fixture</html>",
            "content_type": "text/html",
            "locator": "fixture:1",
            "run_id": "run-state",
            "robots_decision": "allowed",
        }
        payload.update(overrides)
        return RawEvidence(**payload)

    def test_robots_not_found_writes_raw_stage_and_deferred_candidate(self):
        raw_id = self.runtime.persist_raw(
            self._raw(robots_decision="not-found")
        )

        result = self.runtime.write_item(_item(), raw_evidence_id=raw_id)

        self.assertEqual(result["candidate_status"], "deferred")
        self.assertEqual(result["candidate_reason"], "robots:not-found")
        conn = sqlite3.connect(self.database_path)
        try:
            counts = tuple(
                conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in (
                    "raw_fetches",
                    "stage_source_items",
                    "std_ich_projects",
                )
            )
            candidate = conn.execute(
                "SELECT candidate_status, candidate_reason "
                "FROM std_ich_projects"
            ).fetchone()
        finally:
            conn.close()

        self.assertEqual(counts, (1, 1, 1))
        self.assertEqual(candidate, ("deferred", "robots:not-found"))

    def test_item_rights_are_injected_from_registry(self):
        raw_id = self.runtime.persist_raw(self._raw())

        result = self.runtime.write_item(_item(), raw_evidence_id=raw_id)

        self.assertEqual(result["candidate_status"], "candidate")
        conn = sqlite3.connect(self.database_path)
        try:
            stage_rights = conn.execute(
                "SELECT rights_status, attribution_required "
                "FROM stage_source_items"
            ).fetchone()
            candidate_rights = conn.execute(
                "SELECT rights_status, attribution_required "
                "FROM std_ich_projects"
            ).fetchone()
        finally:
            conn.close()

        self.assertEqual(stage_rights, ("attribution-required", 1))
        self.assertEqual(candidate_rights, ("attribution-required", 1))

    def test_explicit_false_rights_override_registry_default(self):
        raw_id = self.runtime.persist_raw(
            self._raw(attribution_required=False)
        )

        self.runtime.write_item(
            _item(attribution_required=False),
            raw_evidence_id=raw_id,
        )

        conn = sqlite3.connect(self.database_path)
        try:
            raw_flag = conn.execute(
                "SELECT attribution_required FROM raw_fetches"
            ).fetchone()[0]
            stage_flag = conn.execute(
                "SELECT attribution_required FROM stage_source_items"
            ).fetchone()[0]
            candidate_flag = conn.execute(
                "SELECT attribution_required FROM std_ich_projects"
            ).fetchone()[0]
        finally:
            conn.close()

        self.assertEqual((raw_flag, stage_flag, candidate_flag), (0, 0, 0))

    def test_deferred_item_without_carrier_fields_is_persisted(self):
        raw_id = self.runtime.persist_raw(self._raw())

        result = self.runtime.write_item(
            _item(
                source_item_id="deferred-missing",
                long_term_url=None,
                detail_url=None,
                detail_url_status="missing",
                locator=None,
                candidate_status="deferred",
                candidate_reason="carrier:missing",
            ),
            raw_evidence_id=raw_id,
        )

        self.assertEqual(result["candidate_status"], "deferred")
        conn = sqlite3.connect(self.database_path)
        try:
            row = conn.execute(
                "SELECT candidate_status, candidate_reason, "
                "long_term_url, locator FROM std_ich_projects "
                "WHERE source_item_id = 'deferred-missing'"
            ).fetchone()
        finally:
            conn.close()
        self.assertEqual(
            row,
            (
                "deferred",
                "carrier:missing",
                "https://example.test/1",
                "locator:missing",
            ),
        )

    def test_failed_admission_persists_blocked_candidate(self):
        raw_id = self.runtime.persist_raw(self._raw())

        result = self.runtime.write_item(
            _item(source_item_id="blocked-admission"),
            raw_evidence_id=raw_id,
            admission=AdmissionDecision(
                False,
                "blocked",
                "policy:blocked",
            ),
        )

        self.assertEqual(result["candidate_status"], "blocked")
        self.assertEqual(result["candidate_reason"], "policy:blocked")
        conn = sqlite3.connect(self.database_path)
        try:
            row = conn.execute(
                "SELECT candidate_status, candidate_reason "
                "FROM std_ich_projects "
                "WHERE source_item_id = 'blocked-admission'"
            ).fetchone()
        finally:
            conn.close()
        self.assertEqual(row, ("blocked", "policy:blocked"))

    def test_candidate_deferred_and_blocked_states_persist(self):
        raw_id = self.runtime.persist_raw(self._raw())
        expected = (
            ("candidate", None),
            ("deferred", "batch:later"),
            ("blocked", "rights:review"),
        )

        for index, (status, reason) in enumerate(expected):
            result = self.runtime.write_item(
                _item(
                    source_item_id=f"state-{index}",
                    candidate_status=status,
                    candidate_reason=reason,
                ),
                raw_evidence_id=raw_id,
            )
            self.assertEqual(result["candidate_status"], status)

        conn = sqlite3.connect(self.database_path)
        try:
            rows = conn.execute(
                "SELECT candidate_status, candidate_reason "
                "FROM std_ich_projects ORDER BY source_item_id"
            ).fetchall()
        finally:
            conn.close()
        self.assertEqual(rows, list(expected))

    def test_report_derives_deferred_and_blocked_from_database(self):
        report_database = self.root / "report.db"
        conn = sqlite3.connect(report_database)
        try:
            conn.executescript(
                """
                CREATE TABLE raw_fetches (
                    id INTEGER PRIMARY KEY,
                    run_id TEXT NOT NULL
                );
                CREATE TABLE stage_source_items (
                    id INTEGER PRIMARY KEY,
                    run_id TEXT NOT NULL
                );
                CREATE TABLE std_ich_projects (
                    id INTEGER PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    candidate_status TEXT NOT NULL
                );
                INSERT INTO raw_fetches (run_id) VALUES ('run-report');
                INSERT INTO stage_source_items (run_id) VALUES ('run-report');
                INSERT INTO std_ich_projects (run_id, candidate_status)
                    VALUES
                    ('run-report', 'candidate'),
                    ('run-report', 'deferred'),
                    ('run-report', 'blocked');
                """
            )
            conn.commit()
        finally:
            conn.close()

        report = build_run_report(
            run_id="run-report",
            source_id="ihchina",
            mode="fixture",
            database_path=report_database,
            report_root=self.root / "reports",
        )

        self.assertEqual(report.written, 1)
        self.assertEqual(report.deferred, 1)
        self.assertEqual(report.blocked, 1)
        self.assertEqual(report.status, "partial")

    def test_all_deferred_run_is_partial_not_failed(self):
        report = RunReport(
            run_id="run-deferred",
            source_id="ihchina",
            mode="fixture",
            discovered=1,
            deferred=1,
        )

        self.assertEqual(report.status, "partial")


if __name__ == "__main__":
    unittest.main()
