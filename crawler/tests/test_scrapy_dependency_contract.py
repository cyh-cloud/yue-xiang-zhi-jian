import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ScrapyDependencyContractTest(unittest.TestCase):
    def test_one_root_dependency_manifest_declares_scrapy(self):
        payload = tomllib.loads(
            (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        )
        dependencies = payload["project"]["dependencies"]

        self.assertTrue(any(dep.startswith("scrapy") for dep in dependencies))
        self.assertTrue((ROOT / "uv.lock").is_file())

    def test_projects_do_not_copy_lockfiles(self):
        projects = ROOT / "collection" / "projects"

        self.assertEqual(list(projects.rglob("uv.lock")), [])
        self.assertEqual(list(projects.rglob("pyproject.toml")), [])


if __name__ == "__main__":
    unittest.main()
