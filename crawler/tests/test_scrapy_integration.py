import ast
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from crawler.collection.shared.crawler_collection.evidence import RawEvidence
from crawler.collection.shared.crawler_collection.exit_codes import (
    FAILED,
    PARTIAL,
    SUCCESS,
    exit_code_for_status,
)
from crawler.collection.shared.crawler_collection.projects import (
    discover_projects,
    executable_source_ids,
)
from crawler.collection.shared.crawler_collection.registry import load_registry
from crawler.collection.shared.crawler_collection.runtime import CollectionRuntime


ROOT = Path(__file__).resolve().parents[1]
PROJECTS = ROOT / "collection" / "projects"
SHARED = ROOT / "collection" / "shared" / "crawler_collection"
REGISTRY = ROOT / "docs" / "sources.json"


class ScrapyIntegrationTest(unittest.TestCase):
    def test_exact_eight_projects_are_discoverable(self):
        projects = discover_projects(PROJECTS)
        expected = executable_source_ids(load_registry(REGISTRY))

        self.assertEqual(len(expected), 8)
        self.assertEqual(set(projects), expected)
        self.assertEqual(
            set(projects),
            {
                path.name
                for path in PROJECTS.iterdir()
                if path.is_dir() and path.name != "__pycache__"
            },
        )

    def test_excluded_and_deferred_sources_have_no_project(self):
        for source_id in (
            "5ajob",
            "zhongguoyuyan",
            "cnopendata",
            "open-meteo",
            "qweather",
            "weather",
        ):
            self.assertFalse((PROJECTS / source_id).exists(), source_id)

    def test_shared_package_has_no_business_or_converter_imports(self):
        forbidden = {"backend", "crawler.pipeline.converter"}
        for path in SHARED.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            imports = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.extend(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imports.append(node.module)
            for module in imports:
                self.assertFalse(
                    any(
                        module == token or module.startswith(token + ".")
                        for token in forbidden
                    ),
                    f"{path} imports {module}",
                )

    def test_weather_is_not_in_scrapy_projects(self):
        for path in PROJECTS.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix not in {".py", ".cfg"}:
                continue
            text = path.read_text(encoding="utf-8").lower()
            self.assertNotIn("weather.com.cn", text, path)
            self.assertNotIn("open-meteo", text, path)
            self.assertNotIn("qweather", text, path)

    def test_required_site_sample_records_exist(self):
        index = json.loads(
            (ROOT / "docs" / "operations" / "live-evidence-index.json")
            .read_text(encoding="utf-8")
        )
        self.assertEqual(index["source_count"], 8)
        for run in index["runs"]:
            acceptance = ROOT.parent / run["acceptance_record"]
            text = acceptance.read_text(encoding="utf-8")
            self.assertIn("验收结论: ", text, acceptance.name)
            self.assertIn(
                f"运行结果: {run['status']}",
                text,
                acceptance.name,
            )

    def test_file_sites_use_explicit_start_urls_for_live_canaries(self):
        sources = {
            "aqsc-moa": PROJECTS / "aqsc-moa" / "aqsc_moa" / "spiders" / "collection.py",
            "cnipa": PROJECTS / "cnipa" / "cnipa" / "spiders" / "collection.py",
        }
        for source_id, path in sources.items():
            text = path.read_text(encoding="utf-8")
            self.assertIn("live_enabled = True", text, source_id)
            self.assertIn("start_urls = []", text, source_id)


class LiveExitCodeTest(unittest.TestCase):
    def test_status_exit_code_contract(self):
        self.assertEqual(exit_code_for_status("succeeded"), SUCCESS)
        self.assertEqual(exit_code_for_status("partial"), PARTIAL)
        self.assertEqual(exit_code_for_status("failed"), FAILED)

    def test_live_clis_exit_partial_for_partial_report(self):
        projects = {
            "aqsc-moa": PROJECTS / "aqsc-moa",
            "cnipa": PROJECTS / "cnipa",
        }
        for source_id, project_root in projects.items():
            with self.subTest(source_id=source_id):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    report_root = root / "reports"
                    report_root.mkdir()
                    run_id = f"{source_id}-review-test"
                    (report_root / f"{run_id}.json").write_text(
                        json.dumps(
                            {"status": "partial", "run_id": run_id}
                        ),
                        encoding="utf-8",
                    )
                    script = (
                        "import sys\n"
                        "from pathlib import Path\n"
                        f"sys.path.insert(0, {str(project_root)!r})\n"
                        f"import {source_id.replace('-', '_')}.live as live\n"
                        "def fake_run(**kwargs):\n"
                        "    return kwargs['run_id'], "
                        "Path(kwargs['report_root']) / "
                        "(kwargs['run_id'] + '.json')\n"
                        "live.run_live_sample = fake_run\n"
                        "raise SystemExit(live.main(sys.argv[1:]))\n"
                    )
                    result = subprocess.run(
                        [
                            sys.executable,
                            "-c",
                            script,
                            "--database-path",
                            str(root / "crawler.db"),
                            "--download-root",
                            str(root / "download"),
                            "--registry-path",
                            str(REGISTRY),
                            "--report-root",
                            str(report_root),
                            "--run-id",
                            run_id,
                            "--start-url",
                            "https://example.test/",
                        ],
                        cwd=ROOT.parent,
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    self.assertEqual(
                        result.returncode,
                        PARTIAL,
                        result.stderr,
                    )

    def test_live_clis_exit_one_for_failed_report(self):
        projects = {
            "aqsc-moa": PROJECTS / "aqsc-moa",
            "cnipa": PROJECTS / "cnipa",
        }
        for source_id, project_root in projects.items():
            with self.subTest(source_id=source_id):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    report_root = root / "reports"
                    report_root.mkdir()
                    run_id = f"{source_id}-failed-test"
                    (report_root / f"{run_id}.json").write_text(
                        json.dumps(
                            {"status": "failed", "run_id": run_id}
                        ),
                        encoding="utf-8",
                    )
                    script = (
                        "import sys\n"
                        "from pathlib import Path\n"
                        f"sys.path.insert(0, {str(project_root)!r})\n"
                        f"import {source_id.replace('-', '_')}.live as live\n"
                        "def fake_run(**kwargs):\n"
                        "    return kwargs['run_id'], "
                        "Path(kwargs['report_root']) / "
                        "(kwargs['run_id'] + '.json')\n"
                        "live.run_live_sample = fake_run\n"
                        "raise SystemExit(live.main(sys.argv[1:]))\n"
                    )
                    result = subprocess.run(
                        [
                            sys.executable,
                            "-c",
                            script,
                            "--database-path",
                            str(root / "crawler.db"),
                            "--download-root",
                            str(root / "download"),
                            "--registry-path",
                            str(REGISTRY),
                            "--report-root",
                            str(report_root),
                            "--run-id",
                            run_id,
                            "--start-url",
                            "https://example.test/",
                        ],
                        cwd=ROOT.parent,
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    self.assertEqual(
                        result.returncode,
                        FAILED,
                        result.stderr,
                    )


class MissingLocatorStateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.database_path = self.root / "crawler.db"
        self.runtime = CollectionRuntime(
            database_path=self.database_path,
            download_root=self.root / "download",
            registry_path=REGISTRY,
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_list_item_without_locator_is_deferred_audit_record(self):
        raw_id = self.runtime.persist_raw(
            RawEvidence(
                source_id="aqsc-moa",
                request_url="https://example.test/list",
                final_url="https://example.test/list",
                long_term_url="https://example.test/list",
                body=b"<html></html>",
                content_type="text/html",
                locator="list=example.test/list",
                run_id="run-missing-locator",
                robots_decision="allowed",
            )
        )

        result = self.runtime.write_item(
            {
                "source_id": "aqsc-moa",
                "source_item_id": "missing-list-locator",
                "source_url": "https://example.test/list",
                "long_term_url": "https://example.test/list",
                "detail_url": None,
                "detail_url_status": "missing",
                "locator": None,
                "run_id": "run-missing-locator",
                "mode": "fixture",
                "title": "示例行",
                "candidate_status": "deferred",
                "candidate_reason": "locator:missing",
            },
            raw_evidence_id=raw_id,
        )

        self.assertEqual(result["candidate_status"], "blocked")
        self.assertEqual(
            result["candidate_reason"],
            "candidate_writer:missing",
        )
        conn = sqlite3.connect(self.database_path)
        try:
            row = conn.execute(
                "SELECT locator FROM stage_source_items "
                "WHERE source_item_id = ?",
                ("missing-list-locator",),
            ).fetchone()
        finally:
            conn.close()
        self.assertEqual(row, ("locator:missing",))

    def test_attachment_without_locator_is_also_deferred(self):
        raw_id = self.runtime.persist_raw(
            RawEvidence(
                source_id="aqsc-moa",
                request_url="https://example.test/attachment.xlsx",
                final_url="https://example.test/attachment.xlsx",
                long_term_url="https://example.test/list",
                fetch_url="https://example.test/attachment.xlsx",
                body=b"xlsx",
                content_type=(
                    "application/vnd.openxmlformats-officedocument."
                    "spreadsheetml.sheet"
                ),
                status_code=200,
                locator="file=attachment.xlsx; page=1",
                run_id="run-missing-attachment-locator",
                robots_decision="allowed",
                metadata={"file_name": "attachment.xlsx", "file_request": True},
            )
        )

        result = self.runtime.write_item(
            {
                "source_id": "aqsc-moa",
                "source_item_id": "missing-attachment-locator",
                "source_url": "https://example.test/attachment.xlsx",
                "long_term_url": "https://example.test/list",
                "detail_url": None,
                "detail_url_status": "missing",
                "locator": None,
                "run_id": "run-missing-attachment-locator",
                "mode": "fixture",
                "title": "附件行",
                "candidate_status": "deferred",
                "candidate_reason": "locator:missing",
            },
            raw_evidence_id=raw_id,
        )

        self.assertEqual(result["candidate_status"], "blocked")
        self.assertEqual(
            result["candidate_reason"],
            "candidate_writer:missing",
        )

    def test_attachment_file_403_keeps_error_metadata_not_body(self):
        raw_id = self.runtime.persist_raw(
            RawEvidence(
                source_id="aqsc-moa",
                request_url="https://example.test/file.xlsx",
                final_url="https://example.test/file.xlsx",
                long_term_url="https://example.test/list",
                fetch_url="https://example.test/file.xlsx",
                body=b"<html>WAF</html>",
                content_type="text/html",
                status_code=403,
                locator="file=file.xlsx; page=1",
                run_id="run-403",
                robots_decision="allowed",
                metadata={"file_name": "file.xlsx", "file_request": True},
            )
        )
        conn = sqlite3.connect(self.database_path)
        try:
            fetch = conn.execute(
                "SELECT body_saved, body_sha256, body_path "
                "FROM raw_fetches WHERE id = ?",
                (raw_id,),
            ).fetchone()
            file_row = conn.execute(
                "SELECT download_status, file_path, sha256, mime_type "
                "FROM raw_files WHERE raw_fetch_id = ?",
                (raw_id,),
            ).fetchone()
        finally:
            conn.close()
        self.assertEqual(fetch, (0, None, None))
        self.assertEqual(
            file_row,
            ("http_error", "", "", "text/html"),
        )


if __name__ == "__main__":
    unittest.main()
