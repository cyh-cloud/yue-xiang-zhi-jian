import ast
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from crawler.collection.shared.crawler_collection.admission import (
    evaluate_admission,
)
from crawler.collection.shared.crawler_collection.dedupe import (
    candidate_natural_key,
    stage_natural_key,
)
from crawler.collection.shared.crawler_collection.items import (
    CollectionItem,
    validate_item,
)
from crawler.collection.shared.crawler_collection.projects import (
    discover_projects,
)
from crawler.collection.shared.crawler_collection.reporting import (
    RunReport,
    build_run_report,
)
from crawler.collection.shared.crawler_collection.robots import RobotsFact


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "docs" / "sources.json"
PROJECTS = ROOT / "collection" / "projects"


EXPECTED_PROJECTS = {
    "ihchina",
    "nzrc",
    "nongmuhr",
    "dialect-org",
    "cass-linguistics",
    "feiyiw",
    "aqsc-moa",
    "cnipa",
}


class ScrapyProjectDiscoveryTest(unittest.TestCase):
    def test_discovery_returns_only_eight_scoped_projects(self):
        projects = discover_projects(PROJECTS)

        self.assertEqual(set(projects), EXPECTED_PROJECTS)
        for source_id, project in projects.items():
            self.assertEqual(project.source_id, source_id)
            self.assertTrue(project.config_path.is_file())
            self.assertTrue(project.package_path.is_dir())

    def test_excluded_and_deferred_sources_have_no_scrapy_project(self):
        for source_id in (
            "5ajob",
            "zhongguoyuyan",
            "cnopendata",
            "open-meteo",
            "qweather",
        ):
            self.assertFalse((PROJECTS / source_id).exists())


class CollectionItemContractTest(unittest.TestCase):
    def _item(self, **overrides):
        payload = {
            "source_id": "ihchina",
            "source_item_id": "project-1",
            "source_url": "https://www.ihchina.cn/project/1",
            "long_term_url": "https://www.ihchina.cn/project/1",
            "detail_url": "https://www.ihchina.cn/project/1",
            "detail_url_status": "direct",
            "run_id": "run-1",
            "mode": "fixture",
            "rights_status": "attribution-required",
        }
        payload.update(overrides)
        return CollectionItem(**payload)

    def test_direct_detail_requires_detail_url(self):
        with self.assertRaises(ValueError):
            validate_item(
                self._item(detail_url=None, detail_url_status="direct")
            )

    def test_missing_detail_requires_locator(self):
        with self.assertRaises(ValueError):
            validate_item(
                self._item(
                    detail_url=None,
                    detail_url_status="missing",
                    locator=None,
                )
            )

    def test_validate_item_returns_serializable_mapping(self):
        item = self._item(locator="fixture row 1")

        payload = validate_item(item)

        self.assertEqual(payload["source_id"], "ihchina")
        json.dumps(payload)
        self.assertNotIn("response", payload)

    def test_natural_keys_are_stable(self):
        item = self._item()

        self.assertEqual(
            stage_natural_key(item, raw_fetch_id=7),
            ("ihchina", "project-1"),
        )
        self.assertEqual(
            candidate_natural_key(item),
            ("ihchina", "project-1"),
        )


class AdmissionContractTest(unittest.TestCase):
    def setUp(self):
        self.registry_path = REGISTRY

    def _admit(self, source_id, **overrides):
        item = CollectionItem(
            source_id=source_id,
            source_item_id="1",
            source_url="https://example.test/1",
            long_term_url="https://example.test/1",
            detail_url="https://example.test/1",
            detail_url_status="direct",
            run_id="run-1",
            mode="fixture",
            rights_status="attribution-required",
        )
        return evaluate_admission(
            item,
            registry_path=self.registry_path,
            robots=RobotsFact(
                decision=overrides.get("robots_decision", "allowed"),
                evidence_url="https://example.test/robots.txt",
            ),
        )

    def test_enabled_source_with_direct_detail_is_candidate(self):
        decision = self._admit("ihchina")

        self.assertEqual(decision.status, "candidate")
        self.assertTrue(decision.allowed)

    def test_disabled_source_is_blocked(self):
        decision = self._admit("5ajob")

        self.assertEqual(decision.status, "blocked")
        self.assertFalse(decision.allowed)
        self.assertIn("source", decision.reason)

    def test_robots_rejection_is_blocked(self):
        decision = self._admit("ihchina", robots_decision="disallowed")

        self.assertEqual(decision.status, "blocked")
        self.assertFalse(decision.allowed)

    def test_unknown_source_is_blocked_without_defaults(self):
        decision = self._admit("not-registered")

        self.assertEqual(decision.status, "blocked")
        self.assertFalse(decision.allowed)


class RunReportContractTest(unittest.TestCase):
    def test_live_report_has_auditable_counts_and_is_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            database_path = root / "crawler.db"
            conn = sqlite3.connect(database_path)
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
                    INSERT INTO raw_fetches (run_id) VALUES ('run-live');
                    INSERT INTO raw_fetches (run_id) VALUES ('run-live');
                    INSERT INTO stage_source_items (run_id) VALUES ('run-live');
                    INSERT INTO std_ich_projects (run_id, candidate_status)
                        VALUES ('run-live', 'candidate');
                    """
                )
                conn.commit()
            finally:
                conn.close()

            report = build_run_report(
                run_id="run-live",
                source_id="ihchina",
                mode="live",
                database_path=database_path,
                started_at="2026-10-21T01:00:00+00:00",
                finished_at="2026-10-21T01:01:00+00:00",
                request_count=2,
                item_counts={
                    "written": 1,
                    "blocked": 1,
                    "deferred": 0,
                    "skipped": 0,
                    "failed": 0,
                },
                errors=(),
                evidence_path=root / "download",
                report_root=root / "reports",
            )

            payload = report.to_dict()
            self.assertEqual(payload["run_id"], "run-live")
            self.assertEqual(payload["mode"], "live")
            self.assertEqual(payload["request_count"], 2)
            self.assertEqual(payload["raw_count"], 2)
            self.assertEqual(payload["stage_count"], 1)
            self.assertEqual(payload["candidate_count"], 1)
            self.assertEqual(payload["blocked"], 1)
            self.assertEqual(payload["deferred"], 0)
            self.assertEqual(payload["skipped"], 0)
            self.assertTrue(Path(report.report_path).is_file())
            persisted = json.loads(
                Path(report.report_path).read_text(encoding="utf-8")
            )
            self.assertEqual(persisted["status"], "partial")

    def test_partial_when_some_items_fail(self):
        report = RunReport(
            run_id="run-1",
            source_id="ihchina",
            mode="fixture",
            discovered=2,
            written=1,
            failed=1,
        )

        self.assertEqual(report.status, "partial")

    def test_failed_when_no_item_succeeds(self):
        report = RunReport(
            run_id="run-1",
            source_id="ihchina",
            mode="fixture",
            discovered=2,
            failed=2,
        )

        self.assertEqual(report.status, "failed")

    def test_empty_result_is_failed(self):
        report = RunReport(
            run_id="run-1",
            source_id="ihchina",
            mode="fixture",
            discovered=0,
        )

        self.assertEqual(report.status, "failed")


class SharedPackageBoundaryTest(unittest.TestCase):
    def test_shared_package_does_not_import_business_or_converter(self):
        shared_root = ROOT / "collection" / "shared" / "crawler_collection"
        forbidden = ("backend", "pipeline.converter", "pipeline.database")

        for path in shared_root.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            imports = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.extend(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imports.append(node.module)
            for module in imports:
                self.assertFalse(
                    any(module.startswith(name) for name in forbidden),
                    f"{path} imports {module}",
                )

    def test_fixture_paths_stay_under_evidence_root(self):
        fixture_root = ROOT / "tests" / "fixtures" / "evidence"
        self.assertTrue(fixture_root.is_dir())
        for child in fixture_root.iterdir():
            self.assertTrue(child.is_dir())
        for project in discover_projects(PROJECTS).values():
            expected = fixture_root / project.source_id
            self.assertTrue(expected.is_dir(), project.source_id)

    def test_fixture_root_is_not_created_inside_projects(self):
        for project in discover_projects(PROJECTS).values():
            self.assertFalse((project.package_path / "fixtures").exists())


if __name__ == "__main__":
    unittest.main()
