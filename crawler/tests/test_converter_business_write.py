import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from crawler.pipeline import business_write, database
from crawler.pipeline.converter import rollback_batch, run_batch


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
    PRIMARY KEY (recruit_key, title),
    FOREIGN KEY (recruit_key) REFERENCES recruitments(key) ON DELETE CASCADE
);
"""


class JobsBusinessWriteTest(unittest.TestCase):
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
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        business = sqlite3.connect(self.business_db)
        try:
            business.executescript(BUSINESS_SCHEMA)
            business.commit()
        finally:
            business.close()

    def _insert_job(
        self,
        conn,
        item_id,
        *,
        title="农艺技术员",
        candidate_status="candidate",
        source_url=None,
        deadline_at="2999-12-31",
        content_hash=None,
    ):
        source_url = source_url or (
            f"http://nongmuhr.com/EmployView.aspx?Id={item_id}"
        )
        content_hash = content_hash or database.sha256_text(
            f"nongmuhr:{item_id}:{title}"
        )
        conn.execute(
            """
            INSERT INTO std_jobs (
                source_id, source_item_id, source_url, long_term_url,
                detail_url, detail_url_status, rights_status,
                attribution_required, attribution_text, rights_evidence_url,
                title, title_raw, company_name, company_url,
                company_industry, company_size, company_nature,
                location_raw, province, city, employment_type, headcount,
                salary_raw, education_raw, experience_raw, published_at,
                deadline_at, content_hash, confidence, license_or_usage,
                publish_status, candidate_status, candidate_reason,
                retrieved_at, first_seen_at, last_seen_at, extra
            ) VALUES (
                'nongmuhr', ?, ?, ?, ?, 'direct', 'attribution-required',
                1, '农牧人才网', 'http://nongmuhr.com/', ?, ?, ?,
                'http://nongmuhr.com/CompanyView.aspx?Id=1',
                '农业种植养殖', '100-499人', '国有企业',
                '新疆自治区', '新疆', '', '全职', 2, '面议', '大专',
                '1年以上', '2025-08-19', ?, ?, 'high',
                'attribution-required', 'draft', ?, NULL,
                '2026-10-21T15:28:51+00:00',
                '2026-10-21T15:28:51+00:00',
                '2026-10-21T15:28:51+00:00',
                '{"company_industry": "农业种植养殖"}'
            )
            """,
            (
                item_id,
                source_url,
                source_url,
                source_url,
                title,
                title,
                "示例农牧公司",
                deadline_at,
                content_hash,
                candidate_status,
            ),
        )

    def _run(self, batch_key, *, dry_run=False):
        return run_batch(
            "jobs",
            {
                "batch_key": batch_key,
                "converter_version": "test-v1",
                "target_database": "yuexiang",
                "dry_run": dry_run,
            },
            crawler_database_path=self.crawler_db,
            business_database_path=self.business_db,
            source_registry_path=self.registry,
        )

    def _business_rows(self):
        conn = sqlite3.connect(self.business_db)
        conn.row_factory = sqlite3.Row
        try:
            rows = [
                dict(row)
                for row in conn.execute(
                    "SELECT * FROM recruitments ORDER BY key"
                )
            ]
            sources = [
                dict(row)
                for row in conn.execute(
                    "SELECT * FROM recruitment_sources ORDER BY recruit_key, title"
                )
            ]
        finally:
            conn.close()
        return rows, sources

    def test_write_upserts_candidate_jobs_and_sources_with_draft_review_state(self):
        conn = database.connect(self.crawler_db)
        try:
            self._insert_job(conn, "13563", title="外贸员")
            self._insert_job(conn, "13564", title="业务员")
            conn.commit()
        finally:
            conn.close()

        result = self._run("jobs-write-1")

        self.assertEqual(result.status, "succeeded")
        self.assertEqual(result.input_count, 2)
        self.assertEqual(result.inserted_count, 2)
        self.assertEqual(result.updated_count, 0)
        rows, sources = self._business_rows()
        self.assertEqual(len(rows), 2)
        self.assertEqual([row["key"] for row in rows], [
            "job-nongmuhr-13563",
            "job-nongmuhr-13564",
        ])
        self.assertEqual(rows[0]["title"], "外贸员")
        self.assertEqual(rows[0]["org"], "示例农牧公司")
        self.assertEqual(rows[0]["region"], "新疆自治区")
        self.assertEqual(rows[0]["category"], "农业种植养殖")
        self.assertEqual(rows[0]["job_type"], "全职")
        self.assertEqual(rows[0]["headcount"], "2")
        self.assertEqual(rows[0]["publish_date"], "2025-08-19")
        self.assertEqual(rows[0]["deadline"], "2999-12-31")
        extra = json.loads(rows[0]["extra"])
        self.assertEqual(extra["review_status"], "pending_review")
        self.assertEqual(extra["publish_status"], "draft")
        self.assertEqual(extra["import_batch_key"], "jobs-write-1")
        self.assertEqual(
            extra["detail_url"],
            "http://nongmuhr.com/EmployView.aspx?Id=13563",
        )
        self.assertEqual(len(sources), 2)
        self.assertEqual(
            {source["url"] for source in sources},
            {
                "http://nongmuhr.com/EmployView.aspx?Id=13563",
                "http://nongmuhr.com/EmployView.aspx?Id=13564",
            },
        )
        self.assertTrue(all(source["media"] == "农牧人才网" for source in sources))
        self.assertTrue(
            all(
                json.loads(source["extra"])["source_item_id"]
                in {"13563", "13564"}
                for source in sources
            )
        )

    def test_repeated_same_batch_and_new_batch_are_idempotent(self):
        conn = database.connect(self.crawler_db)
        try:
            self._insert_job(conn, "13563")
            conn.commit()
        finally:
            conn.close()

        first = self._run("jobs-write-idempotent")
        same_batch = self._run("jobs-write-idempotent")
        second = self._run("jobs-write-idempotent-2")

        self.assertEqual(first.inserted_count, 1)
        self.assertEqual(same_batch.batch_id, first.batch_id)
        self.assertEqual(same_batch.inserted_count, 1)
        self.assertEqual(second.inserted_count, 0)
        self.assertEqual(second.updated_count, 0)
        self.assertEqual(second.skipped_count, 1)
        rows, sources = self._business_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(sources), 1)
        self.assertEqual(
            json.loads(rows[0]["extra"])["import_batch_key"],
            "jobs-write-idempotent",
        )

    def test_deferred_and_blocked_jobs_never_reach_business_database(self):
        conn = database.connect(self.crawler_db)
        try:
            self._insert_job(conn, "deferred", candidate_status="deferred")
            self._insert_job(conn, "blocked", candidate_status="blocked")
            self._insert_job(conn, "candidate")
            conn.commit()
        finally:
            conn.close()

        result = self._run("jobs-write-status-gate")

        self.assertEqual(result.input_count, 3)
        self.assertEqual(result.inserted_count, 1)
        self.assertEqual(result.skipped_count, 2)
        rows, _sources = self._business_rows()
        self.assertEqual([row["key"] for row in rows], ["job-nongmuhr-candidate"])

    def test_dry_run_never_writes_business_tables(self):
        conn = database.connect(self.crawler_db)
        try:
            self._insert_job(conn, "dry-run")
            conn.commit()
        finally:
            conn.close()

        result = self._run("jobs-dry-run-only", dry_run=True)

        self.assertEqual(result.inserted_count, 1)
        rows, sources = self._business_rows()
        self.assertEqual(rows, [])
        self.assertEqual(sources, [])

    def test_manual_field_is_preserved_and_recorded_as_conflict(self):
        conn = database.connect(self.crawler_db)
        try:
            self._insert_job(conn, "locked", title="原始标题")
            conn.commit()
        finally:
            conn.close()
        self._run("jobs-write-before-lock")

        business = sqlite3.connect(self.business_db)
        try:
            extra = json.loads(
                business.execute(
                    "SELECT extra FROM recruitments WHERE key = ?",
                    ("job-nongmuhr-locked",),
                ).fetchone()[0]
            )
            extra["manual_fields"] = ["title"]
            business.execute(
                "UPDATE recruitments SET title = ?, extra = ? WHERE key = ?",
                ("人工标题", json.dumps(extra, ensure_ascii=False), "job-nongmuhr-locked"),
            )
            business.commit()
        finally:
            business.close()

        conn = sqlite3.connect(self.crawler_db)
        try:
            conn.execute(
                "UPDATE std_jobs SET title = ?, content_hash = ? WHERE source_item_id = ?",
                ("新标题", database.sha256_text("new-title"), "locked"),
            )
            conn.commit()
        finally:
            conn.close()

        result = self._run("jobs-write-after-lock")

        self.assertEqual(result.conflict_count, 1)
        self.assertEqual(result.updated_count, 0)
        rows, _sources = self._business_rows()
        self.assertEqual(rows[0]["title"], "人工标题")
        crawler = sqlite3.connect(self.crawler_db)
        try:
            conflict = crawler.execute(
                "SELECT target_table, target_field, reason FROM import_conflicts "
                "WHERE batch_id = ?",
                (result.batch_id,),
            ).fetchone()
        finally:
            crawler.close()
        self.assertEqual(
            conflict,
            ("recruitments", "title", "manual_field_locked"),
        )

    def test_transaction_failure_rolls_back_crawler_audit_and_business_rows(self):
        conn = database.connect(self.crawler_db)
        try:
            self._insert_job(conn, "rollback")
            conn.commit()
        finally:
            conn.close()

        with mock.patch.object(
            business_write,
            "_upsert_sources",
            side_effect=sqlite3.OperationalError("forced failure"),
        ):
            with self.assertRaises(sqlite3.OperationalError):
                self._run("jobs-write-rollback")

        rows, sources = self._business_rows()
        self.assertEqual(rows, [])
        self.assertEqual(sources, [])
        crawler = sqlite3.connect(self.crawler_db)
        try:
            batch_count = crawler.execute(
                "SELECT COUNT(*) FROM import_batches WHERE batch_key = ?",
                ("jobs-write-rollback",),
            ).fetchone()[0]
        finally:
            crawler.close()
        self.assertEqual(batch_count, 0)

    def test_business_batch_rollback_is_rejected_without_mutation(self):
        conn = database.connect(self.crawler_db)
        try:
            self._insert_job(conn, "rollback-guard")
            conn.commit()
        finally:
            conn.close()
        result = self._run("jobs-write-rollback-guard")

        with self.assertRaisesRegex(
            ValueError,
            "business-write batch rollback is not implemented",
        ):
            rollback_batch(
                result.batch_id,
                crawler_database_path=self.crawler_db,
            )

        rows, sources = self._business_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(sources), 1)
        crawler = sqlite3.connect(self.crawler_db)
        try:
            status = crawler.execute(
                "SELECT status FROM import_batches WHERE id = ?",
                (result.batch_id,),
            ).fetchone()[0]
        finally:
            crawler.close()
        self.assertEqual(status, "succeeded")


if __name__ == "__main__":
    unittest.main()
