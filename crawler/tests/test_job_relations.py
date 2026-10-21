import tempfile
import unittest
import sqlite3
from pathlib import Path

from crawler.collection.projects.nzrc.nzrc.candidate import (
    write_candidate as write_nzrc_candidate,
)
from crawler.collection.projects.nongmuhr.nongmuhr.candidate import (
    write_candidate as write_nongmuhr_candidate,
)
from crawler.collection.shared.crawler_collection.database import (
    CollectionDatabase,
)
from crawler.collection.shared.crawler_collection.runtime import (
    CollectionRuntime,
)


NOW = "2026-10-21T12:00:00+08:00"


def _job_item(**overrides):
    payload = {
        "source_id": "nzrc",
        "source_item_id": "8235500",
        "run_id": "nzrc-run-1",
        "source_url": "https://example.test/jobs/8235500.html",
        "long_term_url": "https://example.test/jobs/8235500.html",
        "detail_url": "https://example.test/jobs/8235500.html",
        "detail_url_status": "direct",
        "locator": "detail-page",
        "rights_status": "attribution-required",
        "attribution_required": True,
        "attribution_text": "示例农业公司",
        "rights_evidence_url": "https://example.test/rights",
        "content_hash": "job-hash-1",
        "confidence": "high",
        "license_or_usage": "attribution-required",
        "candidate_status": "candidate",
        "candidate_reason": None,
        "title": "销售经理",
        "body_text": "公开岗位职责",
        "extra": {
            "company_name": "示例农业公司",
            "location_raw": "广东",
            "province": "广东",
            "city": "广州",
            "county": "天河",
        },
    }
    payload.update(overrides)
    return payload


class JobRelationWriteTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "crawler.db"
        self.database = CollectionDatabase(self.db_path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_nzrc_writer_persists_source_and_location_relations(self):
        conn = self.database.connect()
        try:
            write_nzrc_candidate(conn, _job_item(), now=NOW)
            conn.commit()
            job_id = conn.execute(
                "SELECT id FROM std_jobs WHERE source_id = 'nzrc'"
            ).fetchone()[0]
            source = conn.execute(
                """
                SELECT source_item_id, source_url, long_term_url, detail_url,
                       detail_url_status, locator, rights_status,
                       attribution_required, attribution_text,
                       rights_evidence_url, is_primary
                FROM std_job_sources
                WHERE job_id = ?
                """,
                (job_id,),
            ).fetchone()
            location = conn.execute(
                """
                SELECT source_id, source_item_id, source_url, long_term_url,
                       detail_url, detail_url_status, locator, rights_status,
                       attribution_required, attribution_text,
                       rights_evidence_url, location_raw, province, city,
                       county, is_primary
                FROM std_job_locations
                WHERE job_id = ?
                """,
                (job_id,),
            ).fetchone()
        finally:
            conn.close()

        self.assertEqual(
            source,
            (
                "8235500",
                "https://example.test/jobs/8235500.html",
                "https://example.test/jobs/8235500.html",
                "https://example.test/jobs/8235500.html",
                "direct",
                "detail-page",
                "attribution-required",
                1,
                "示例农业公司",
                "https://example.test/rights",
                1,
            ),
        )
        self.assertEqual(
            location,
            (
                "nzrc",
                "8235500",
                "https://example.test/jobs/8235500.html",
                "https://example.test/jobs/8235500.html",
                "https://example.test/jobs/8235500.html",
                "direct",
                "detail-page",
                "attribution-required",
                1,
                "示例农业公司",
                "https://example.test/rights",
                "广东",
                "广东",
                "广州",
                "天河",
                1,
            ),
        )

    def test_nongmuhr_writer_keeps_multiple_locations_idempotently(self):
        item = _job_item(
            source_id="nongmuhr",
            source_item_id="13519",
            run_id="nongmuhr-run-1",
            source_url="https://example.test/nongmuhr/13519",
            long_term_url="https://example.test/nongmuhr/13519",
            detail_url="https://example.test/nongmuhr/13519",
            title="农资销售员",
            extra={
                "company_name": "示例农牧公司",
                "location_raw": "贵州省|四川省",
                "locations": [
                    {
                        "location_raw": "贵州省",
                        "province": "贵州省",
                    },
                    {
                        "location_raw": "四川省",
                        "province": "四川省",
                        "city": "成都市",
                        "county": "武侯区",
                    },
                ],
            },
        )
        conn = self.database.connect()
        try:
            write_nongmuhr_candidate(conn, item, now=NOW)
            write_nongmuhr_candidate(conn, item, now=NOW)
            conn.commit()
            job_id = conn.execute(
                "SELECT id FROM std_jobs WHERE source_id = 'nongmuhr'"
            ).fetchone()[0]
            source_count = conn.execute(
                "SELECT COUNT(*) FROM std_job_sources WHERE job_id = ?",
                (job_id,),
            ).fetchone()[0]
            locations = conn.execute(
                """
                SELECT location_raw, province, city, county, is_primary
                FROM std_job_locations
                WHERE job_id = ?
                ORDER BY id
                """,
                (job_id,),
            ).fetchall()
        finally:
            conn.close()

        self.assertEqual(source_count, 1)
        self.assertEqual(
            locations,
            [
                ("贵州省", "贵州省", None, None, 1),
                ("四川省", "四川省", "成都市", "武侯区", 0),
            ],
        )

    def test_relation_failure_rolls_back_job_and_source_rows(self):
        runtime = CollectionRuntime(
            database_path=self.db_path,
            download_root=Path(self.tmp.name) / "downloads",
            registry_path=Path("crawler/docs/sources.json"),
            candidate_writer=write_nzrc_candidate,
        )
        raw_id = runtime.persist_raw(
            runtime.evidence_from_fixture(
                source_id="nzrc",
                body=b"<html>job</html>",
                request_url="https://example.test/jobs/8235500.html",
                content_type="text/html",
                run_id="nzrc-run-1",
            )
        )
        conn = self.database.connect()
        try:
            conn.execute(
                """
                CREATE TRIGGER fail_job_location
                BEFORE INSERT ON std_job_locations
                BEGIN
                    SELECT RAISE(ABORT, 'location write failed');
                END
                """
            )
            conn.commit()
        finally:
            conn.close()

        with self.assertRaises(sqlite3.IntegrityError):
            runtime.write_item(
                _job_item(
                    mode="fixture",
                    raw_evidence_id=raw_id,
                    retrieved_at=NOW,
                ),
                raw_evidence_id=raw_id,
            )

        conn = self.database.connect()
        try:
            counts = tuple(
                conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in (
                    "stage_source_items",
                    "std_jobs",
                    "std_job_sources",
                    "std_job_locations",
                )
            )
        finally:
            conn.close()
        self.assertEqual(counts, (0, 0, 0, 0))


if __name__ == "__main__":
    unittest.main()
