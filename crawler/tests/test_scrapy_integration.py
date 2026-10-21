import ast
import unittest
from pathlib import Path

from crawler.collection.shared.crawler_collection.projects import (
    discover_projects,
)


ROOT = Path(__file__).resolve().parents[1]
PROJECTS = ROOT / "collection" / "projects"
SHARED = ROOT / "collection" / "shared" / "crawler_collection"
REVIEWS = ROOT / "docs" / "reviews"


class ScrapyIntegrationTest(unittest.TestCase):
    def test_exact_eight_projects_are_discoverable(self):
        projects = discover_projects(PROJECTS)

        self.assertEqual(
            set(projects),
            {
                "ihchina",
                "nzrc",
                "nongmuhr",
                "dialect-org",
                "cass-linguistics",
                "feiyiw",
                "aqsc-moa",
                "cnipa",
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
        expected = {
            "ihchina-scrapy-sample.md": ("blocked", "partial"),
            "nzrc-scrapy-sample.md": ("blocked", "partial"),
            "nongmuhr-scrapy-sample.md": ("blocked", "failed"),
            "dialect-org-scrapy-sample.md": ("blocked", "partial"),
            "cass-linguistics-scrapy-sample.md": ("blocked", "partial"),
            "feiyiw-scrapy-sample.md": ("blocked", "partial"),
            "aqsc-moa-scrapy-sample.md": ("blocked", "partial"),
            "cnipa-scrapy-sample.md": ("approved-with-gaps", "partial"),
        }
        for name, (conclusion, run_status) in expected.items():
            text = (REVIEWS / name).read_text(encoding="utf-8")
            self.assertIn(f"验收结论: {conclusion}", text, name)
            self.assertIn(f"运行结果: {run_status}", text, name)

    def test_file_sites_use_explicit_start_urls_for_live_canaries(self):
        sources = {
            "aqsc-moa": PROJECTS / "aqsc-moa" / "aqsc_moa" / "spiders" / "collection.py",
            "cnipa": PROJECTS / "cnipa" / "cnipa" / "spiders" / "collection.py",
        }
        for source_id, path in sources.items():
            text = path.read_text(encoding="utf-8")
            self.assertIn("live_enabled = True", text, source_id)
            self.assertIn("start_urls = []", text, source_id)


if __name__ == "__main__":
    unittest.main()
