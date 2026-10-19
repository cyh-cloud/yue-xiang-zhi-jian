import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from crawler.pipeline import database
from crawler.pipeline.converter import run_batch


class ConverterTest(unittest.TestCase):
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

    def _insert_ich(self, conn, *, source_id, item_id, name, description, retrieved_at):
        conn.execute(
            """
            INSERT INTO std_ich_projects (
                source_id, source_item_id, source_url, long_term_url,
                detail_url, detail_url_status, rights_status,
                attribution_required, ich_code, name, declaration_region,
                description_text, content_hash, confidence, license_or_usage,
                publish_status, retrieved_at, first_seen_at, last_seen_at, extra
            ) VALUES (?, ?, ?, ?, ?, 'direct', 'attribution-required', 1,
                      'Ⅷ-1', ?, '广东省', ?, ?, 'high', 'attribution-required',
                      'draft', ?, ?, ?, '{}')
            """,
            (
                source_id,
                item_id,
                f"https://example.test/{source_id}/{item_id}",
                f"https://example.test/{source_id}/{item_id}",
                f"https://example.test/{source_id}/{item_id}",
                name,
                description,
                database.sha256_text(description),
                retrieved_at,
                retrieved_at,
                retrieved_at,
            ),
        )

    def test_ich_dry_run_plans_one_row_and_keeps_conflict_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            crawler_db = root / "crawler.db"
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
            conn = database.connect(crawler_db)
            try:
                self._register_aggregator(conn)
                self._insert_ich(
                    conn,
                    source_id="ihchina",
                    item_id="1",
                    name="广绣",
                    description="官方正文",
                    retrieved_at="2026-10-19T01:00:00+08:00",
                )
                self._insert_ich(
                    conn,
                    source_id="aggregator",
                    item_id="a-1",
                    name="广绣",
                    description="聚合正文",
                    retrieved_at="2026-10-18T01:00:00+08:00",
                )
                conn.commit()
            finally:
                conn.close()

            result = run_batch(
                "ich",
                {
                    "batch_key": "ich-20261019-test",
                    "converter_version": "test-v1",
                    "target_database": "yuexiang",
                    "dry_run": True,
                },
                crawler_database_path=crawler_db,
                source_registry_path=registry,
            )

            self.assertEqual(result.status, "partial")
            self.assertIsNotNone(result.batch_id)
            self.assertEqual(result.input_count, 2)
            self.assertEqual(result.inserted_count, 1)
            self.assertEqual(result.conflict_count, 1)
            self.assertEqual(
                result.inserted_count
                + result.updated_count
                + result.skipped_count
                + result.conflict_count
                + result.failed_count,
                result.input_count,
            )
            row = result.by_entity["std_ich_projects"]["rows"][0]
            self.assertEqual(row["id"], "ich-1")
            self.assertEqual(row["name"], "广绣")
            self.assertEqual(row["source_id"], "ihchina")
            conflict = result.by_entity["std_ich_projects"]["conflicts"][0]
            self.assertEqual(conflict["field"], "description_text")
            self.assertEqual(
                {conflict["existing_source_url"], conflict["incoming_source_url"]},
                {
                    "https://example.test/ihchina/1",
                    "https://example.test/aggregator/a-1",
                },
            )
            self.assertEqual(
                {conflict["existing_retrieved_at"], conflict["incoming_retrieved_at"]},
                {"2026-10-19T01:00:00+08:00", "2026-10-18T01:00:00+08:00"},
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
            self.assertIn("import_batches", tables)
            self.assertIn("import_conflicts", tables)

    def test_weather_is_not_a_legal_domain(self):
        with self.assertRaises(ValueError):
            run_batch(
                "weather",
                {
                    "batch_key": "weather-1",
                    "converter_version": "test-v1",
                    "target_database": "yuexiang",
                    "dry_run": True,
                },
                crawler_database_path=Path("unused.db"),
            )

    def test_agri_dry_run_uses_cert_type_and_origin_scope_and_skips_missing_detail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            crawler_db = root / "crawler.db"
            conn = database.connect(crawler_db)
            try:
                base = {
                    "source_id": "aqsc-moa",
                    "rights_status": "attribution-required",
                    "attribution_required": 1,
                    "confidence": "medium",
                    "license_or_usage": "attribution-required",
                    "publish_status": "draft",
                    "retrieved_at": "2026-10-19T01:00:00+08:00",
                    "first_seen_at": "2026-10-19T01:00:00+08:00",
                    "last_seen_at": "2026-10-19T01:00:00+08:00",
                    "locator": None,
                    "extra": "{}",
                }
                rows = [
                    {
                        **base,
                        "source_item_id": "1",
                        "source_url": "https://example.test/announcement/1",
                        "long_term_url": "https://example.test/announcement/1",
                        "detail_url": "https://example.test/product/1",
                        "detail_url_status": "direct",
                        "cert_type": "名特优新",
                        "product_name": "甲鱼",
                        "product_name_raw": "甲鱼",
                        "normalized_name": "甲鱼",
                        "province": "广东省",
                        "region": None,
                        "origin_scope": "佛山市顺德区",
                        "content_hash": database.sha256_text("one"),
                    },
                    {
                        **base,
                        "source_item_id": "2",
                        "source_url": "https://example.test/announcement/2",
                        "long_term_url": "https://example.test/announcement/2",
                        "detail_url": "https://example.test/product/2",
                        "detail_url_status": "direct",
                        "cert_type": "地理标志",
                        "product_name": "甲鱼",
                        "product_name_raw": "甲鱼",
                        "normalized_name": "甲鱼",
                        "province": "广东省",
                        "region": None,
                        "origin_scope": "佛山市顺德区",
                        "content_hash": database.sha256_text("two"),
                    },
                    {
                        **base,
                        "source_item_id": "3",
                        "source_url": "https://example.test/announcement/3",
                        "long_term_url": "https://example.test/announcement/3",
                        "detail_url": None,
                        "detail_url_status": "missing",
                        "locator": "announcement row 3",
                        "cert_type": "特质农品",
                        "product_name": "无详情产品",
                        "product_name_raw": "无详情产品",
                        "normalized_name": "无详情产品",
                        "province": "广东省",
                        "region": "清远市",
                        "origin_scope": None,
                        "content_hash": database.sha256_text("three"),
                    },
                ]
                columns = list(rows[0])
                conn.executemany(
                    f"INSERT INTO std_agri_products ({','.join(columns)}) "
                    f"VALUES ({','.join('?' for _ in columns)})",
                    [[row[column] for column in columns] for row in rows],
                )
                conn.commit()
            finally:
                conn.close()

            result = run_batch(
                "agri",
                {
                    "batch_key": "agri-20261019-test",
                    "converter_version": "test-v1",
                    "target_database": "yuexiang",
                    "dry_run": True,
                },
                crawler_database_path=crawler_db,
            )

            self.assertEqual(result.status, "succeeded")
            self.assertEqual(result.input_count, 3)
            self.assertEqual(result.inserted_count, 2)
            self.assertEqual(result.skipped_count, 1)
            products = result.by_entity["std_agri_products"]["rows"]
            self.assertEqual(
                {row["cert_type"] for row in products},
                {"名特优新", "地理标志"},
            )
            self.assertTrue(
                all(row["region"] == "佛山市顺德区" for row in products)
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
            self.assertIn("import_batches", tables)
            self.assertIn("import_conflicts", tables)

    def test_converter_reads_only_std_tables(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            crawler_db = root / "crawler.db"
            conn = database.connect(crawler_db)
            try:
                conn.execute(
                    """
                    INSERT INTO raw_fetches (
                        source_id, request_url, final_url, source_url,
                        long_term_url, detail_url_status, locator, rights_status,
                        request_method, access_level, fetch_status,
                        started_at, created_at
                    ) VALUES (
                        'ihchina', 'https://example.test/raw',
                        'https://example.test/raw', 'https://example.test/raw',
                        'https://example.test/raw', 'missing', 'raw fixture row',
                        'attribution-required', 'GET', 'public', 'ok',
                        '2026-10-19T01:00:00+08:00',
                        '2026-10-19T01:00:00+08:00'
                    )
                    """
                )
                self._insert_ich(
                    conn,
                    source_id="ihchina",
                    item_id="2",
                    name="潮绣",
                    description="官方正文",
                    retrieved_at="2026-10-19T01:00:00+08:00",
                )
                conn.commit()
            finally:
                conn.close()

            result = run_batch(
                "ich",
                {
                    "batch_key": "ich-read-only-test",
                    "converter_version": "test-v1",
                    "target_database": "yuexiang",
                    "dry_run": True,
                },
                crawler_database_path=crawler_db,
            )

            self.assertEqual(result.input_count, 1)
            self.assertEqual(result.by_entity["std_ich_projects"]["rows"][0]["id"], "ich-2")


if __name__ == "__main__":
    unittest.main()
