import sqlite3
import tempfile
import unittest
from pathlib import Path

from crawler.collection.shared.crawler_collection.replay import (
    replay_fixture,
)


class FixtureReplayTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.fixture = self.root / "ihchina"
        self.fixture.mkdir()
        (self.fixture / "discover.json").write_text(
            """
            {
              "items": [
                {
                  "source_item_id": "1",
                  "title": "Fixture item",
                  "source_url": "https://example.test/1",
                  "long_term_url": "https://example.test/1",
                  "detail_url": "https://example.test/1",
                  "detail_url_status": "direct",
                  "locator": "fixture row 1"
                }
              ]
            }
            """,
            encoding="utf-8",
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_replay_twice_appends_raw_and_keeps_candidates_idempotent(self):
        first = replay_fixture(
            source_id="ihchina",
            fixture_dir=self.fixture,
            database_path=self.root / "crawler.db",
            download_root=self.root / "downloads",
            registry_path=Path("crawler/docs/sources.json"),
        )
        second = replay_fixture(
            source_id="ihchina",
            fixture_dir=self.fixture,
            database_path=self.root / "crawler.db",
            download_root=self.root / "downloads",
            registry_path=Path("crawler/docs/sources.json"),
        )

        self.assertEqual(first.status, "succeeded")
        self.assertEqual(second.status, "succeeded")
        conn = sqlite3.connect(self.root / "crawler.db")
        try:
            raw_count = conn.execute(
                "SELECT COUNT(*) FROM raw_fetches"
            ).fetchone()[0]
            stage_count = conn.execute(
                "SELECT COUNT(*) FROM stage_source_items"
            ).fetchone()[0]
            candidate_count = conn.execute(
                "SELECT COUNT(*) FROM std_ich_projects"
            ).fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(raw_count, 2)
        self.assertEqual(stage_count, 1)
        self.assertEqual(candidate_count, 1)
        self.assertEqual(first.stage_count, 1)
        self.assertEqual(second.stage_count, 1)
        self.assertEqual(second.candidate_count, 1)
        self.assertNotEqual(first.report_path, second.report_path)
        self.assertTrue(Path(first.report_path).is_file())
        self.assertTrue(Path(second.report_path).is_file())

    def test_empty_fixture_is_failed_not_succeeded(self):
        (self.fixture / "discover.json").write_text(
            '{"items": []}', encoding="utf-8"
        )

        result = replay_fixture(
            source_id="ihchina",
            fixture_dir=self.fixture,
            database_path=self.root / "crawler.db",
            download_root=self.root / "downloads",
            registry_path=Path("crawler/docs/sources.json"),
        )

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.discovered, 0)

    def test_missing_fixture_is_failed(self):
        result = replay_fixture(
            source_id="ihchina",
            fixture_dir=self.root / "missing",
            database_path=self.root / "crawler.db",
            download_root=self.root / "downloads",
            registry_path=Path("crawler/docs/sources.json"),
        )

        self.assertEqual(result.status, "failed")
        self.assertTrue(result.errors)

    def test_replay_does_not_touch_business_database(self):
        replay_fixture(
            source_id="ihchina",
            fixture_dir=self.fixture,
            database_path=self.root / "crawler.db",
            download_root=self.root / "downloads",
            registry_path=Path("crawler/docs/sources.json"),
        )

        self.assertFalse((self.root / "yuexiang.db").exists())


if __name__ == "__main__":
    unittest.main()
