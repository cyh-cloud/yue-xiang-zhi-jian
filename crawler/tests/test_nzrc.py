import sqlite3
import tempfile
import unittest
from pathlib import Path

from crawler.pipeline.offline_fixture import (
    OfflineFixtureConfig,
    run_offline_fixture,
)


ROOT = Path(__file__).resolve().parents[1]
DOWNLOAD = ROOT / "tests" / "fixtures" / "evidence" / "nzrc"


class NzrcSourceTest(unittest.TestCase):
    def test_saved_detail_projects_job_and_keeps_private_contacts_null(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = OfflineFixtureConfig(
                database_path=root / "crawler.db",
                download_root=root / "download",
                fixture_root=root / "fixture",
                source_root=DOWNLOAD,
            )

            result = run_offline_fixture("nzrc", "saved", config)

            self.assertEqual(result.status, "succeeded")
            self.assertGreater(result.written_count, 0)
            conn = sqlite3.connect(config.database_path)
            try:
                row = conn.execute(
                    "SELECT source_id, source_item_id, source_url, title, "
                    "company_name, rights_status, extra FROM std_jobs "
                    "WHERE source_url LIKE 'http://www.nzrc.com.cn/company/jobs/%' LIMIT 1"
                ).fetchone()
            finally:
                conn.close()
            self.assertEqual(row[0], "nzrc")
            self.assertTrue(row[2].startswith("http://www.nzrc.com.cn/company/jobs/"))
            self.assertTrue(row[3])
            self.assertEqual(row[5], "attribution-required")
            self.assertIn("rights_risk", row[6])
            self.assertNotIn("contact_phone", row[6])
