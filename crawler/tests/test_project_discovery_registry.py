import json
import tempfile
import unittest
from pathlib import Path

from crawler.collection.shared.crawler_collection.projects import (
    discover_projects,
    executable_source_ids,
)
from crawler.collection.shared.crawler_collection.registry import load_registry


class RegistryDrivenProjectDiscoveryTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.projects = self.root / "projects"
        self.projects.mkdir()
        self.registry = self.root / "sources.json"

    def _source(self, source_id, **overrides):
        payload = {
            "id": source_id,
            "enabled": True,
            "status": "approved-with-gaps",
            "run_modes": ["fixture", "live"],
        }
        payload.update(overrides)
        return payload

    def _write_registry(self, *sources):
        self.registry.write_text(
            json.dumps({"sources": list(sources)}),
            encoding="utf-8",
        )

    def _write_project(self, source_id, *, package=None):
        project_root = self.projects / source_id
        project_root.mkdir()
        (project_root / "scrapy.cfg").write_text(
            "[settings]\ndefault = settings\n",
            encoding="utf-8",
        )
        package_name = package or source_id.replace("-", "_")
        (project_root / package_name).mkdir()

    def test_project_set_is_derived_from_registry(self):
        self._write_registry(
            self._source("approved-site"),
            self._source("disabled-site", enabled=False),
            self._source("excluded-site", status="excluded"),
            self._source("runtime-only", run_modes=[]),
        )
        self._write_project("approved-site")

        projects = discover_projects(
            self.projects,
            registry_path=self.registry,
        )

        self.assertEqual(list(projects), ["approved-site"])

    def test_registry_status_change_rejects_unexpected_project(self):
        self._write_registry(
            self._source("site", status="blocked"),
        )
        self._write_project("site")

        with self.assertRaisesRegex(ValueError, "unexpected.*site"):
            discover_projects(self.projects, registry_path=self.registry)

    def test_changing_only_registry_changes_executable_source_set(self):
        self._write_registry(self._source("first"))

        first_set = executable_source_ids(load_registry(self.registry))
        self.assertEqual(set(first_set), {"first"})

        self._write_registry(
            self._source("first"),
            self._source("second", run_modes=["live"]),
        )
        second_set = executable_source_ids(load_registry(self.registry))
        self.assertEqual(set(second_set), {"first", "second"})

    def test_extra_project_directory_is_rejected(self):
        self._write_registry(self._source("site"))
        self._write_project("site")
        self._write_project("extra")

        with self.assertRaisesRegex(ValueError, "unexpected.*extra"):
            discover_projects(self.projects, registry_path=self.registry)

    def test_extra_bare_directory_is_rejected(self):
        self._write_registry(self._source("site"))
        self._write_project("site")
        (self.projects / "extra").mkdir()

        with self.assertRaisesRegex(ValueError, "unexpected.*extra"):
            discover_projects(self.projects, registry_path=self.registry)

    def test_missing_project_directory_is_rejected(self):
        self._write_registry(
            self._source("first"),
            self._source("second"),
        )
        self._write_project("first")

        with self.assertRaisesRegex(ValueError, "missing.*second"):
            discover_projects(self.projects, registry_path=self.registry)

    def test_package_identity_mismatch_is_rejected(self):
        self._write_registry(self._source("site"))
        self._write_project("site", package="wrong_package")

        with self.assertRaisesRegex(ValueError, "incomplete.*site"):
            discover_projects(self.projects, registry_path=self.registry)

    def test_project_without_scrapy_config_is_rejected(self):
        self._write_registry(self._source("site"))
        project_root = self.projects / "site"
        project_root.mkdir()
        (project_root / "site").mkdir()

        with self.assertRaisesRegex(ValueError, "incomplete.*site"):
            discover_projects(self.projects, registry_path=self.registry)

    def test_registry_without_project_truth_fails(self):
        self._write_registry(
            self._source("site", enabled=False, status="excluded", run_modes=[]),
        )
        self._write_project("site")

        with self.assertRaisesRegex(ValueError, "unexpected.*site"):
            discover_projects(self.projects, registry_path=self.registry)


if __name__ == "__main__":
    unittest.main()
