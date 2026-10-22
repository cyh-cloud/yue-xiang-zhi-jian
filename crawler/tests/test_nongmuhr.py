import sqlite3
import tempfile
import unittest
from pathlib import Path

from crawler.pipeline.offline_fixture import (
    OfflineFixtureConfig,
    run_offline_fixture,
)


ROOT = Path(__file__).resolve().parents[1]
DOWNLOAD = ROOT / "tests" / "fixtures" / "evidence" / "nongmuhr"


class NongmuhrSourceTest(unittest.TestCase):
    def test_saved_details_project_jobs_and_preserve_description_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = OfflineFixtureConfig(
                database_path=root / "crawler.db",
                download_root=root / "download",
                fixture_root=root / "fixture",
                source_root=DOWNLOAD,
            )

            result = run_offline_fixture("nongmuhr", "saved", config)

            self.assertEqual(result.status, "succeeded")
            self.assertGreaterEqual(result.written_count, 2)
            conn = sqlite3.connect(config.database_path)
            try:
                rows = conn.execute(
                    "SELECT source_id, source_item_id, source_url, title, "
                    "rights_status, extra FROM std_jobs ORDER BY source_item_id"
                ).fetchall()
            finally:
                conn.close()
            self.assertTrue(rows)
            self.assertTrue(all(row[0] == "nongmuhr" for row in rows))
            self.assertTrue(all(row[2].startswith("http://nongmuhr.com/EmployView.aspx?id=") for row in rows))
            self.assertTrue(all(row[3] for row in rows))
            self.assertTrue(all(row[4] == "attribution-required" for row in rows))
            self.assertTrue(all("rights_risk" in row[5] for row in rows))
