import sqlite3
import tempfile
import unittest
from pathlib import Path

from crawler.pipeline import database


STD_TABLES = (
    "std_agri_products",
    "std_ich_projects",
    "std_jobs",
    "std_dialect_points",
    "std_ich_articles",
    "std_research_articles",
)


class CandidateStateSchemaTest(unittest.TestCase):
    def test_new_database_has_candidate_state_ubiquitously(self):
        with tempfile.TemporaryDirectory() as tmp:
            conn = database.connect(Path(tmp) / "crawler.db")
            try:
                for table in STD_TABLES:
                    columns = {
                        row[1]: row
                        for row in conn.execute(
                            f"PRAGMA table_info({table})"
                        ).fetchall()
                    }
                    self.assertIn("candidate_status", columns, table)
                    self.assertEqual(columns["candidate_status"][3], 1)
                    self.assertEqual(
                        columns["candidate_status"][4].strip("'"),
                        "candidate",
                    )
                    self.assertIn("candidate_reason", columns, table)
                self.assertIn(
                    "candidate_status IN ('candidate', 'blocked', 'deferred')",
                    database.SCHEMA,
                )
            finally:
                conn.close()

    def test_old_std_rows_receive_candidate_default_without_losing_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "crawler.db"
            conn = database.connect(path)
            try:
                conn.execute(
                    """
                    INSERT INTO std_ich_projects (
                        source_id, source_item_id, source_url, long_term_url,
                        detail_url, detail_url_status, locator, rights_status,
                        name, content_hash, confidence, license_or_usage,
                        publish_status, retrieved_at, first_seen_at, last_seen_at
                    ) VALUES ('ihchina', 'old-1', ?, ?, ?, 'direct', 'detail',
                              'attribution-required', '旧记录', ?, 'high',
                              'attribution-required', 'draft', ?, ?, ?)
                    """,
                    (
                        "https://example.test/1",
                        "https://example.test/1",
                        "https://example.test/1",
                        database.sha256_text("old"),
                        "2026-01-01T00:00:00+00:00",
                        "2026-01-01T00:00:00+00:00",
                        "2026-01-01T00:00:00+00:00",
                    ),
                )
                conn.commit()
            finally:
                conn.close()

            conn = sqlite3.connect(path)
            try:
                conn.execute("ALTER TABLE std_ich_projects DROP COLUMN candidate_status")
                conn.execute("ALTER TABLE std_ich_projects DROP COLUMN candidate_reason")
                conn.commit()
            finally:
                conn.close()

            conn = database.connect(path)
            try:
                row = conn.execute(
                    """
                    SELECT publish_status, candidate_status, candidate_reason
                    FROM std_ich_projects WHERE source_item_id = 'old-1'
                    """
                ).fetchone()
            finally:
                conn.close()

            self.assertEqual(row, ("draft", "candidate", None))

    def test_legacy_publish_status_is_not_used_as_candidate_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            conn = database.connect(Path(tmp) / "crawler.db")
            try:
                with self.assertRaises(sqlite3.IntegrityError):
                    conn.execute(
                        """
                        INSERT INTO std_jobs (
                            source_id, source_item_id, source_url,
                            long_term_url, detail_url, detail_url_status,
                            rights_status, title, content_hash, confidence,
                            license_or_usage, publish_status, candidate_status,
                            retrieved_at, first_seen_at, last_seen_at
                        ) VALUES ('nzrc', 'bad', ?, ?, ?, 'direct',
                                  'attribution-required', '岗位', 'h', 'high',
                                  'attribution-required', 'published', 'published',
                                  ?, ?, ?)
                        """,
                        (
                            "https://example.test/job/1",
                            "https://example.test/job/1",
                            "https://example.test/job/1",
                            "2026-01-01T00:00:00+00:00",
                            "2026-01-01T00:00:00+00:00",
                            "2026-01-01T00:00:00+00:00",
                        ),
                    )
                conn.rollback()
                conn.execute(
                    """
                    INSERT INTO std_jobs (
                        source_id, source_item_id, source_url, long_term_url,
                        detail_url, detail_url_status, rights_status, title,
                        content_hash, confidence, license_or_usage,
                        publish_status, candidate_status, candidate_reason,
                        retrieved_at, first_seen_at, last_seen_at
                    ) VALUES ('nzrc', 'ok', ?, ?, ?, 'direct',
                              'attribution-required', '岗位', 'h', 'high',
                              'attribution-required', 'published', 'blocked',
                              'missing_rights', ?, ?, ?)
                    """,
                    (
                        "https://example.test/job/2",
                        "https://example.test/job/2",
                        "https://example.test/job/2",
                        "2026-01-01T00:00:00+00:00",
                        "2026-01-01T00:00:00+00:00",
                        "2026-01-01T00:00:00+00:00",
                    ),
                )
            finally:
                conn.close()

    def test_migration_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "crawler.db"
            first = database.connect(path)
            first.close()
            second = database.connect(path)
            second.close()
            third = database.connect(path)
            try:
                for table in STD_TABLES:
                    columns = [
                        row[1]
                        for row in third.execute(
                            f"PRAGMA table_info({table})"
                        ).fetchall()
                    ]
                    self.assertEqual(
                        columns.count("candidate_status"), 1, table
                    )
                    self.assertEqual(
                        columns.count("candidate_reason"), 1, table
                    )
            finally:
                third.close()


if __name__ == "__main__":
    unittest.main()
