import contextlib
import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from crawler.pipeline import database
from crawler.pipeline.cli import main


BUSINESS_SCHEMA = """
CREATE TABLE recruitments (
    key TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    org TEXT DEFAULT '',
    region TEXT DEFAULT '',
    category TEXT DEFAULT '',
    job_type TEXT DEFAULT '',
    headcount TEXT DEFAULT '',
    education TEXT DEFAULT '',
    experience TEXT DEFAULT '',
    salary TEXT DEFAULT '',
    description TEXT DEFAULT '',
    publish_date TEXT DEFAULT '',
    signup_start TEXT DEFAULT '',
    deadline TEXT DEFAULT '',
    signup_way TEXT DEFAULT '',
    contact TEXT DEFAULT '',
    sort_order INTEGER DEFAULT 0,
    extra TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE recruitment_sources (
    recruit_key TEXT NOT NULL,
    title TEXT DEFAULT '',
    media TEXT DEFAULT '',
    date TEXT DEFAULT '',
    url TEXT DEFAULT '',
    sort_order INTEGER DEFAULT 0,
    extra TEXT NOT NULL DEFAULT '{}',
    PRIMARY KEY (recruit_key, title)
);
"""


class ConverterCliTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.crawler_db = self.root / "crawler.db"
        self.business_db = self.root / "business.db"
        self.registry = self.root / "sources.json"
        self.registry.write_text(
            json.dumps(
                {
                    "sources": [
                        {
                            "id": "nongmuhr",
                            "name": "农牧人才网",
                            "enabled": True,
                            "status": "approved-with-gaps",
                            "access": "public",
                            "rights_status": "attribution-required",
                            "priority": "P1",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        business = sqlite3.connect(self.business_db)
        try:
            business.executescript(BUSINESS_SCHEMA)
            business.commit()
        finally:
            business.close()
        conn = database.connect(self.crawler_db)
        try:
            conn.execute(
                """
                INSERT INTO std_jobs (
                    source_id, source_item_id, source_url, long_term_url,
                    detail_url, detail_url_status, rights_status,
                    title, content_hash, confidence, license_or_usage,
                    publish_status, candidate_status, retrieved_at,
                    first_seen_at, last_seen_at
                ) VALUES (
                    'nongmuhr', 'cli-1', 'http://nongmuhr.com/EmployView.aspx?Id=1',
                    'http://nongmuhr.com/EmployView.aspx?Id=1',
                    'http://nongmuhr.com/EmployView.aspx?Id=1', 'direct',
                    'attribution-required', '岗位', 'hash', 'high',
                    'attribution-required', 'draft', 'candidate',
                    '2026-10-22T00:00:00+00:00',
                    '2026-10-22T00:00:00+00:00',
                    '2026-10-22T00:00:00+00:00'
                )
                """
            )
            conn.commit()
        finally:
            conn.close()

    def _run(self, *extra):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main(
                [
                    "--crawler-db",
                    str(self.crawler_db),
                    "--business-db",
                    str(self.business_db),
                    "--domain",
                    "jobs",
                    "--batch-key",
                    "cli-batch",
                    "--source-registry",
                    str(self.registry),
                    *extra,
                ]
            )
        return code, json.loads(output.getvalue())

    def test_cli_defaults_to_dry_run(self):
        code, payload = self._run()

        self.assertEqual(code, 0)
        self.assertEqual(payload["inserted_count"], 1)
        conn = sqlite3.connect(self.business_db)
        try:
            count = conn.execute("SELECT COUNT(*) FROM recruitments").fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(count, 0)

    def test_cli_write_flag_enables_business_write(self):
        code, payload = self._run("--write")

        self.assertEqual(code, 0)
        self.assertEqual(payload["inserted_count"], 1)
        conn = sqlite3.connect(self.business_db)
        try:
            row = conn.execute(
                "SELECT key FROM recruitments WHERE key = ?",
                ("job-nongmuhr-cli-1",),
            ).fetchone()
        finally:
            conn.close()
        self.assertEqual(row, ("job-nongmuhr-cli-1",))


if __name__ == "__main__":
    unittest.main()
