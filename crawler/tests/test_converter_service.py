import sqlite3
import json
import tempfile
import unittest
from pathlib import Path

from crawler.pipeline import database
from crawler.pipeline.converter import rollback_batch, run_batch


class ConverterServiceTest(unittest.TestCase):
    def _insert_ich(self, conn, source_id, item_id, description, retrieved_at):
        conn.execute(
            """
            INSERT INTO std_ich_projects (
                source_id, source_item_id, source_url, long_term_url,
                detail_url, detail_url_status, rights_status,
                attribution_required, ich_code, name, declaration_region,
                description_text, content_hash, confidence,
                license_or_usage, publish_status, retrieved_at,
                first_seen_at, last_seen_at, extra
            ) VALUES (
                ?, ?, ?, ?, ?, 'direct', 'attribution-required', 1,
                'Ⅰ-1', '广绣', '广东省', ?, ?, 'high',
                'attribution-required', 'draft', ?, ?, ?, '{}'
            )
            """,
            (
                source_id,
                item_id,
                f"https://example.test/{source_id}/{item_id}",
                f"https://example.test/{source_id}/{item_id}",
                f"https://example.test/{source_id}/{item_id}",
                description,
                database.sha256_text(description),
                retrieved_at,
                retrieved_at,
                retrieved_at,
            ),
        )

    def _register_aggregator(self, conn):
        conn.execute(
            """
            INSERT INTO std_sources (
                source_id, name, domains, content_domains, priority, status,
                access_level, rights_status, license_or_usage, confidence,
                is_enabled
            ) VALUES (
                'aggregator', 'Aggregator', '["example.test"]', '["ich"]',
                'P2', 'approved-with-gaps', 'public', 'attribution-required',
                'attribution-required', 'medium', 1
            )
            """
        )

    def test_run_batch_uses_registry_priorities_and_persists_batch_and_conflicts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / "crawler.db"
            registry = root / "sources.json"
            registry.write_text(
                json.dumps(
                    {
                        "sources": [
                            {
                                "id": "ihchina",
                                "name": "IHChina",
                                "enabled": True,
                                "status": "approved-with-gaps",
                                "access": "public",
                                "rights_status": "attribution-required",
                                "priority": "P0",
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
            conn = database.connect(db_path)
            try:
                self._register_aggregator(conn)
                self._insert_ich(
                    conn,
                    "ihchina",
                    "official-1",
                    "官方正文",
                    "2026-10-19T01:00:00+08:00",
                )
                self._insert_ich(
                    conn,
                    "aggregator",
                    "aggregate-1",
                    "聚合正文",
                    "2026-10-20T01:00:00+08:00",
                )
                conn.commit()
            finally:
                conn.close()

            result = run_batch(
                "ich",
                {
                    "batch_key": "ich-service-contract",
                    "converter_version": "test-v1",
                    "target_database": "yuexiang",
                    "dry_run": True,
                },
                crawler_database_path=db_path,
                source_registry_path=registry,
            )

            self.assertIsNotNone(result.batch_id)
            self.assertEqual(result.inserted_count, 1)
            self.assertEqual(result.conflict_count, 1)
            self.assertEqual(
                result.by_entity["std_ich_projects"]["rows"][0]["source_id"],
                "ihchina",
            )

            conn = sqlite3.connect(db_path)
            try:
                batch = conn.execute(
                    """
                    SELECT status, input_count, inserted_count, conflict_count,
                           skipped_count, failed_count
                    FROM import_batches WHERE id = ?
                    """,
                    (result.batch_id,),
                ).fetchone()
                conflicts = conn.execute(
                    """
                    SELECT target_table, target_field, existing_source_id,
                           incoming_source_id, resolution
                    FROM import_conflicts WHERE batch_id = ?
                    """,
                    (result.batch_id,),
                ).fetchall()
                planned_items = conn.execute(
                    "SELECT COUNT(*) FROM import_batch_items WHERE batch_id = ?",
                    (result.batch_id,),
                ).fetchone()[0]
            finally:
                conn.close()

            self.assertEqual(batch[0], "partial")
            self.assertEqual(batch[1:], (2, 1, 1, 0, 0))
            self.assertEqual(planned_items, 1)
            self.assertEqual(
                conflicts,
                [
                    (
                        "std_ich_projects",
                        "description_text",
                        "ihchina",
                        "aggregator",
                        "unresolved",
                    )
                ],
            )

    def test_unregistered_source_has_no_silent_default_priority(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / "crawler.db"
            conn = database.connect(db_path)
            try:
                self._insert_ich(
                    conn,
                    "not-registered",
                    "1",
                    "未知来源",
                    "2026-10-20T01:00:00+08:00",
                )
                conn.commit()
            finally:
                conn.close()

            result = run_batch(
                "ich",
                {
                    "batch_key": "ich-unregistered-source",
                    "converter_version": "test-v1",
                    "target_database": "yuexiang",
                    "dry_run": True,
                },
                crawler_database_path=db_path,
            )

            self.assertEqual(result.input_count, 1)
            self.assertEqual(result.inserted_count, 0)
            self.assertEqual(result.skipped_count, 1)
            self.assertEqual(result.by_entity["std_ich_projects"]["rows"], [])

    def test_rollback_marks_completed_dry_run_batch_without_business_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / "crawler.db"
            conn = database.connect(db_path)
            try:
                self._insert_ich(
                    conn,
                    "ihchina",
                    "rollback-1",
                    "官方正文",
                    "2026-10-19T01:00:00+08:00",
                )
                conn.commit()
            finally:
                conn.close()

            result = run_batch(
                "ich",
                {
                    "batch_key": "ich-rollback",
                    "converter_version": "test-v1",
                    "target_database": "yuexiang",
                    "dry_run": True,
                },
                crawler_database_path=db_path,
            )
            rollback = rollback_batch(
                result.batch_id,
                crawler_database_path=db_path,
            )

            self.assertEqual(rollback.batch_id, result.batch_id)
            self.assertEqual(rollback.status, "rolled_back")
            self.assertEqual(rollback.rolled_back_count, 0)
            self.assertEqual(rollback.skipped_count, 1)
            conn = sqlite3.connect(db_path)
            try:
                status, note = conn.execute(
                    "SELECT status, rollback_note FROM import_batches WHERE id = ?",
                    (result.batch_id,),
                ).fetchone()
            finally:
                conn.close()
            self.assertEqual(status, "rolled_back")
            self.assertIn("dry-run", note)


if __name__ == "__main__":
    unittest.main()
