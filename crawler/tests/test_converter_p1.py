import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from crawler.pipeline import database
from crawler.pipeline.converter import run_batch


class P1ConverterTest(unittest.TestCase):
    def _register_aggregator(self, conn):
        conn.execute(
            """
            INSERT INTO std_sources (
                source_id, name, domains, content_domains, priority, status,
                access_level, rights_status, license_or_usage, confidence,
                is_enabled
            ) VALUES (
                'aggregator', 'Aggregator', '["example.test"]', '["jobs"]',
                'P2', 'approved-with-gaps', 'public', 'attribution-required',
                'attribution-required', 'medium', 1
            )
            """
        )

    def _insert_job(
        self,
        conn,
        *,
        item_id,
        title,
        deadline_at,
        status_text=None,
        source_id="nzrc",
        source_url=None,
    ):
        source_url = source_url or f"https://example.test/jobs/{item_id}"
        conn.execute(
            """
            INSERT INTO std_jobs (
                source_id, source_item_id, source_url, long_term_url,
                detail_url, detail_url_status, rights_status,
                attribution_required, title, company_name, location_raw,
                province, city, deadline_at, status_text, content_hash,
                confidence, license_or_usage, publish_status, retrieved_at,
                first_seen_at, last_seen_at, extra
            ) VALUES (?, ?, ?, ?, ?, 'direct', 'noncommercial-permitted',
                      1, ?, '示例农业公司', '广东省广州市', '广东', '广州',
                      ?, ?, ?, 'high', 'noncommercial-permitted', 'draft',
                      '2026-10-19T01:00:00+08:00',
                      '2026-10-19T01:00:00+08:00',
                      '2026-10-19T01:00:00+08:00', '{}')
            """,
            (
                source_id,
                item_id,
                source_url,
                source_url,
                source_url,
                title,
                deadline_at,
                status_text,
                database.sha256_text(f"{source_id}:{item_id}:{title}"),
            ),
        )

    def test_jobs_dry_run_keeps_expired_status_and_source_relations_without_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            crawler_db = root / "crawler.db"
            registry = root / "sources.json"
            registry.write_text(
                json.dumps(
                    {
                        "sources": [
                            {
                                "id": "nzrc",
                                "name": "NZRC",
                                "enabled": True,
                                "status": "approved-with-gaps",
                                "access": "public",
                                "rights_status": "attribution-required",
                                "priority": "P1",
                            },
                            {
                                "id": "aggregator",
                                "name": "Aggregator",
                                "enabled": True,
                                "status": "approved-with-gaps",
                                "access": "public",
                                "rights_status": "attribution-required",
                                "priority": "P2",
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            conn = database.connect(crawler_db)
            try:
                self._insert_job(
                    conn,
                    item_id="active-1",
                    title="农艺技术员",
                    deadline_at="2999-12-31",
                )
                self._insert_job(
                    conn,
                    item_id="expired-1",
                    title="水产养殖技术员",
                    deadline_at="2000-01-01",
                )
                conn.commit()
            finally:
                conn.close()

            result = run_batch(
                "jobs",
                {
                    "batch_key": "jobs-20261020-test",
                    "converter_version": "test-v1",
                    "target_database": "yuexiang",
                    "dry_run": True,
                },
                crawler_database_path=crawler_db,
                source_registry_path=registry,
            )

            self.assertEqual(result.status, "succeeded")
            self.assertIsNotNone(result.batch_id)
            self.assertEqual(result.input_count, 2)
            self.assertEqual(result.inserted_count, 2)
            self.assertEqual(result.conflict_count, 0)
            self.assertEqual(
                result.inserted_count
                + result.updated_count
                + result.skipped_count
                + result.conflict_count
                + result.failed_count,
                result.input_count,
            )

            rows = result.by_entity["std_jobs"]["rows"]
            self.assertEqual(
                {row["source_item_id"]: row["status"] for row in rows},
                {"active-1": "active", "expired-1": "expired"},
            )
            self.assertTrue(
                all(
                    row["source_relations"][0]["source_item_id"]
                    == row["source_item_id"]
                    for row in rows
                )
            )

            conn = sqlite3.connect(crawler_db)
            try:
                tables = {
                    row[0]
                    for row in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    )
                }
            finally:
                conn.close()
            self.assertNotIn("job_listings", tables)
            self.assertNotIn("recruitments", tables)
            self.assertIn("import_batches", tables)
            self.assertIn("import_conflicts", tables)

    def test_jobs_dry_run_preserves_distinct_sources_for_same_canonical_url(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            crawler_db = root / "crawler.db"
            registry = root / "sources.json"
            registry.write_text(
                json.dumps(
                    {
                        "sources": [
                            {
                                "id": "nzrc",
                                "name": "NZRC",
                                "enabled": True,
                                "status": "approved-with-gaps",
                                "access": "public",
                                "rights_status": "attribution-required",
                                "priority": "P1",
                            },
                            {
                                "id": "aggregator",
                                "name": "Aggregator",
                                "enabled": True,
                                "status": "approved-with-gaps",
                                "access": "public",
                                "rights_status": "attribution-required",
                                "priority": "P2",
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            conn = database.connect(crawler_db)
            try:
                self._register_aggregator(conn)
                self._insert_job(
                    conn,
                    item_id="nzrc-dup-1",
                    title="农艺技术员",
                    deadline_at="2999-12-31",
                    source_id="nzrc",
                    source_url="https://example.test/jobs/shared-1",
                )
                self._insert_job(
                    conn,
                    item_id="aggregator-dup-1",
                    title="农艺技术员",
                    deadline_at="2999-12-31",
                    source_id="aggregator",
                    source_url="https://example.test/jobs/shared-1",
                )
                conn.commit()
            finally:
                conn.close()

            result = run_batch(
                "jobs",
                {
                    "batch_key": "jobs-duplicate-test",
                    "converter_version": "test-v1",
                    "target_database": "yuexiang",
                    "dry_run": True,
                },
                crawler_database_path=crawler_db,
                source_registry_path=registry,
            )

            self.assertEqual(result.status, "succeeded")
            self.assertEqual(result.input_count, 2)
            self.assertEqual(result.inserted_count, 2)
            self.assertEqual(result.skipped_count, 0)
            self.assertEqual(
                result.inserted_count
                + result.updated_count
                + result.skipped_count
                + result.conflict_count
                + result.failed_count,
                result.input_count,
            )
            self.assertTrue(
                all(
                    len(row["source_relations"]) == 1
                    for row in result.by_entity["std_jobs"]["rows"]
                )
            )

    def _insert_dialect(
        self,
        conn,
        *,
        point_item_id,
        region_raw,
        province,
        city,
        lemma,
        source_item_id,
    ):
        cursor = conn.execute(
            """
            INSERT INTO std_dialect_points (
                source_id, source_item_id, source_url, long_term_url,
                detail_url, detail_url_status, rights_status,
                attribution_required, region_raw, province, city,
                dialect_name, point_note, confidence, license_or_usage,
                publish_status, retrieved_at, first_seen_at, last_seen_at,
                content_hash, extra
            ) VALUES (
                'dialect-org', ?, ?, ?, ?, 'direct',
                'assumed-noncommercial-user-risk', 0, ?, ?, ?, NULL, NULL,
                'high', 'assumed-noncommercial-user-risk', 'draft',
                '2026-10-19T01:00:00+08:00',
                '2026-10-19T01:00:00+08:00',
                '2026-10-19T01:00:00+08:00', ?, '{}'
            )
            """,
            (
                point_item_id,
                f"https://example.test/points/{point_item_id}",
                f"https://example.test/points/{point_item_id}",
                f"https://example.test/points/{point_item_id}",
                region_raw,
                province,
                city,
                database.sha256_text(f"point:{point_item_id}"),
            ),
        )
        point_id = cursor.lastrowid
        cursor = conn.execute(
            """
            INSERT INTO std_dialect_lexemes (
                point_id, source_id, source_item_id, source_url,
                long_term_url, detail_url, detail_url_status, lemma,
                phonetic, definition, example, audio_url, audio_status,
                rights_status, attribution_required, confidence,
                license_or_usage, publish_status, retrieved_at,
                content_hash, extra
            ) VALUES (?, 'dialect-org', ?, ?, ?, ?, 'direct', ?, 'sik6 faan6',
                      ?, NULL, NULL, 'missing', 'assumed-noncommercial-user-risk',
                      0, 'high', 'assumed-noncommercial-user-risk', 'draft',
                      '2026-10-19T01:00:00+08:00', ?, '{}')
            """,
            (
                point_id,
                source_item_id,
                f"https://example.test/dialect/{source_item_id}",
                f"https://example.test/dialect/{source_item_id}",
                f"https://example.test/dialect/{source_item_id}",
                lemma,
                f"{region_raw}：吃饭",
                database.sha256_text(f"lexeme:{point_item_id}:{lemma}"),
            ),
        )
        lexeme_id = cursor.lastrowid
        conn.execute(
            """
            INSERT INTO std_dialect_lexeme_sources (
                lexeme_id, source_id, source_item_id, source_url,
                long_term_url, detail_url, detail_url_status, rights_status,
                attribution_required, is_primary, retrieved_at,
                content_hash, extra
            ) VALUES (?, 'dialect-org', ?, ?, ?, ?, 'direct',
                      'assumed-noncommercial-user-risk', 0, 1,
                      '2026-10-19T01:00:00+08:00', ?, '{}')
            """,
            (
                lexeme_id,
                source_item_id,
                f"https://example.test/dialect/{source_item_id}",
                f"https://example.test/dialect/{source_item_id}",
                f"https://example.test/dialect/{source_item_id}",
                database.sha256_text(f"source:{source_item_id}"),
            ),
        )

    def test_dialects_dry_run_does_not_merge_same_lemma_across_points(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            crawler_db = root / "crawler.db"
            conn = database.connect(crawler_db)
            try:
                self._insert_dialect(
                    conn,
                    point_item_id="guangdong",
                    region_raw="广东广州",
                    province="广东",
                    city="广州",
                    lemma="食饭",
                    source_item_id="1",
                )
                self._insert_dialect(
                    conn,
                    point_item_id="shanghai",
                    region_raw="上海",
                    province="上海",
                    city="上海",
                    lemma="食饭",
                    source_item_id="2",
                )
                conn.commit()
            finally:
                conn.close()

            result = run_batch(
                "dialects",
                {
                    "batch_key": "dialects-20261020-test",
                    "converter_version": "test-v1",
                    "target_database": "yuexiang",
                    "dry_run": True,
                },
                crawler_database_path=crawler_db,
            )

            self.assertEqual(result.status, "succeeded")
            self.assertEqual(result.input_count, 2)
            self.assertEqual(result.inserted_count, 2)
            rows = result.by_entity["std_dialect_lexemes"]["rows"]
            self.assertEqual(
                {
                    (row["dialect_point"]["region_raw"], row["lemma"])
                    for row in rows
                },
                {("广东广州", "食饭"), ("上海", "食饭")},
            )
            self.assertEqual(
                {
                    row["source_relations"][0]["source_item_id"]
                    for row in rows
                },
                {"1", "2"},
            )
            self.assertEqual(
                {
                    row["dialect_point"]["source_url"]
                    for row in rows
                },
                {
                    "https://example.test/points/guangdong",
                    "https://example.test/points/shanghai",
                },
            )
            self.assertTrue(
                all(
                    row["dialect_point"]["source_relations"][0]["source_url"]
                    == row["dialect_point"]["source_url"]
                    for row in rows
                )
            )
            self.assertEqual(
                result.by_entity["std_dialect_lexemes"]["input_count"], 2
            )

            conn = sqlite3.connect(crawler_db)
            try:
                tables = {
                    row[0]
                    for row in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    )
                }
            finally:
                conn.close()
            self.assertNotIn("dialect_points", tables)
            self.assertNotIn("dialect_lexemes", tables)
            self.assertIn("import_batches", tables)
            self.assertIn("import_conflicts", tables)


if __name__ == "__main__":
    unittest.main()
