import re
import tempfile
import unittest
import sqlite3
from pathlib import Path

from crawler.pipeline import database


class SchemaContractTest(unittest.TestCase):
    def test_initialization_is_idempotent_and_creates_frozen_tables(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "crawler.db"
            first = database.connect(path)
            first.close()
            second = database.connect(path)
            try:
                tables = {
                    row[0]
                    for row in second.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    )
                }
                source_count = second.execute(
                    "SELECT COUNT(*) FROM std_sources"
                ).fetchone()[0]
                raw_files_sql = second.execute(
                    "SELECT sql FROM sqlite_master "
                    "WHERE type = 'table' AND name = 'raw_files'"
                ).fetchone()[0]
            finally:
                second.close()

            self.assertEqual(source_count, 14)
            self.assertNotIn(
                "UNIQUE(source_id, source_url, sha256)",
                raw_files_sql,
            )
            self.assertIn("file_url TEXT NOT NULL", raw_files_sql)
            self.assertIn("final_url TEXT NOT NULL", raw_files_sql)
            for table in (
                "std_sources",
                "std_agri_product_sources",
                "std_agri_product_aliases",
                "std_job_sources",
                "std_job_locations",
                "std_ich_inheritors",
                "std_ich_related_items",
                "std_ich_media_links",
                "import_batches",
                "import_conflicts",
                "import_batch_items",
                "stage_source_items",
            ):
                self.assertIn(table, tables)

    def test_schema_document_embeds_the_exact_database_ddl(self):
        document = (
            Path(__file__).resolve().parents[1]
            / "docs"
            / "schema"
            / "crawler-db.md"
        ).read_text(encoding="utf-8")
        match = re.search(
            r"## Physical DDL\n\n```sql\n(.*?)\n```",
            document,
            re.DOTALL,
        )
        self.assertIsNotNone(match)
        documented = re.sub(r"\s+", " ", match.group(1)).strip()
        actual = re.sub(r"\s+", " ", database.SCHEMA).strip()
        self.assertEqual(documented, actual)

    def test_primary_std_tables_reject_missing_detail_without_locator(self):
        with tempfile.TemporaryDirectory() as tmp:
            conn = database.connect(Path(tmp) / "crawler.db")
            try:
                point_id = self._insert_dialect_point(conn)
                lexeme_id = self._insert_dialect_lexeme(conn, point_id)
                cases = {
                    "std_ich_projects": (
                        """
                        INSERT INTO std_ich_projects (
                            source_id, source_item_id, source_url, long_term_url,
                            detail_url_status, rights_status, name, content_hash,
                            confidence, license_or_usage, publish_status,
                            retrieved_at, first_seen_at, last_seen_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            "ihchina", "missing-project",
                            "https://example.test/projects", "https://example.test/projects",
                            "missing", "attribution-required", "项目",
                            database.sha256_text("project"), "high",
                            "attribution-required", "draft", self._now(),
                            self._now(), self._now(),
                        ),
                    ),
                    "std_agri_products": (
                        """
                        INSERT INTO std_agri_products (
                            source_id, source_item_id, source_url, long_term_url,
                            detail_url_status, rights_status, cert_type,
                            product_name, normalized_name, content_hash,
                            confidence, license_or_usage, publish_status,
                            retrieved_at, first_seen_at, last_seen_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            "aqsc-moa", "missing-product",
                            "https://example.test/products", "https://example.test/products",
                            "missing", "attribution-required", "名特优新",
                            "产品", "产品", database.sha256_text("product"),
                            "medium", "attribution-required", "blocked",
                            self._now(), self._now(), self._now(),
                        ),
                    ),
                    "std_jobs": (
                        """
                        INSERT INTO std_jobs (
                            source_id, source_item_id, source_url, long_term_url,
                            detail_url_status, rights_status, title, content_hash,
                            confidence, license_or_usage, publish_status,
                            retrieved_at, first_seen_at, last_seen_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            "nzrc", "missing-job",
                            "https://example.test/jobs", "https://example.test/jobs",
                            "missing", "attribution-required", "岗位",
                            database.sha256_text("job"), "high",
                            "attribution-required", "draft", self._now(),
                            self._now(), self._now(),
                        ),
                    ),
                    "std_dialect_points": (
                        """
                        INSERT INTO std_dialect_points (
                            source_id, source_item_id, source_url, long_term_url,
                            detail_url_status, rights_status, region_raw,
                            content_hash, confidence, license_or_usage,
                            publish_status, retrieved_at, first_seen_at,
                            last_seen_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            "dialect-org", "missing-point",
                            "https://example.test/dialect", "https://example.test/dialect",
                            "missing", "attribution-required", "示例地区",
                            database.sha256_text("point"), "medium",
                            "attribution-required", "draft", self._now(),
                            self._now(), self._now(),
                        ),
                    ),
                    "std_ich_articles": (
                        """
                        INSERT INTO std_ich_articles (
                            source_id, source_item_id, source_url, long_term_url,
                            detail_url_status, rights_status, title, content_hash,
                            confidence, license_or_usage, publish_status,
                            retrieved_at, first_seen_at, last_seen_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            "feiyiw", "missing-article",
                            "https://example.test/articles", "https://example.test/articles",
                            "missing", "attribution-required", "文章",
                            database.sha256_text("article"), "medium",
                            "attribution-required", "draft", self._now(),
                            self._now(), self._now(),
                        ),
                    ),
                    "std_research_articles": (
                        """
                        INSERT INTO std_research_articles (
                            source_id, source_item_id, source_url, long_term_url,
                            detail_url_status, rights_status, title, body_access,
                            content_hash, confidence, license_or_usage,
                            publish_status, retrieved_at, first_seen_at,
                            last_seen_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            "cass-linguistics", "missing-research",
                            "https://example.test/research", "https://example.test/research",
                            "missing", "attribution-required", "研究",
                            "public", database.sha256_text("research"),
                            "medium", "attribution-required", "draft",
                            self._now(), self._now(), self._now(),
                        ),
                    ),
                    "std_dialect_lexemes": (
                        """
                        INSERT INTO std_dialect_lexemes (
                            point_id, source_id, source_item_id, source_url,
                            long_term_url, detail_url_status, lemma, audio_status,
                            rights_status, confidence, license_or_usage,
                            publish_status, retrieved_at, content_hash
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            point_id, "dialect-org", "missing-lexeme",
                            "https://example.test/dialect", "https://example.test/dialect",
                            "missing", "缺定位词", "missing",
                            "attribution-required", "medium",
                            "attribution-required", "draft", self._now(),
                            database.sha256_text("lexeme"),
                        ),
                    ),
                    "std_dialect_lexeme_sources": (
                        """
                        INSERT INTO std_dialect_lexeme_sources (
                            lexeme_id, source_id, source_item_id, source_url,
                            long_term_url, detail_url_status, rights_status,
                            retrieved_at, content_hash
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            lexeme_id, "dialect-org", "missing-source",
                            "https://example.test/dialect", "https://example.test/dialect",
                            "missing", "attribution-required", self._now(),
                            database.sha256_text("lexeme-source"),
                        ),
                    ),
                }
                for table, (sql, values) in cases.items():
                    with self.subTest(table=table):
                        with self.assertRaises(sqlite3.IntegrityError):
                            conn.execute(sql, values)
                        conn.rollback()
            finally:
                conn.close()

    def test_std_tables_reject_invalid_detail_status_and_direct_without_detail(self):
        with tempfile.TemporaryDirectory() as tmp:
            conn = database.connect(Path(tmp) / "crawler.db")
            try:
                base = (
                    "ihchina", "invalid-status",
                    "https://example.test/projects", "https://example.test/projects",
                    "attribution-required", "项目", database.sha256_text("project"),
                    "high", "attribution-required", "draft", self._now(),
                    self._now(), self._now(),
                )
                insert = """
                    INSERT INTO std_ich_projects (
                        source_id, source_item_id, source_url, long_term_url,
                        detail_url_status, rights_status, name, content_hash,
                        confidence, license_or_usage, publish_status,
                        retrieved_at, first_seen_at, last_seen_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """
                with self.assertRaises(sqlite3.IntegrityError):
                    conn.execute(insert, (*base[:4], "temporary", *base[4:]))
                conn.rollback()
                with self.assertRaises(sqlite3.IntegrityError):
                    conn.execute(insert, (*base[:4], "direct", *base[4:]))
            finally:
                conn.close()

    def test_relation_tables_carry_full_provenance(self):
        relation_tables = (
            "std_agri_product_sources",
            "std_agri_product_aliases",
            "std_ich_inheritors",
            "std_ich_related_items",
            "std_ich_media_links",
            "std_job_sources",
            "std_job_locations",
            "std_dialect_lexeme_sources",
        )
        with tempfile.TemporaryDirectory() as tmp:
            conn = database.connect(Path(tmp) / "crawler.db")
            try:
                for table in relation_tables:
                    with self.subTest(table=table):
                        columns = {
                            row[1]: row
                            for row in conn.execute(
                                f"PRAGMA table_info({table})"
                            ).fetchall()
                        }
                        for name in (
                            "source_url",
                            "long_term_url",
                            "detail_url_status",
                            "locator",
                        ):
                            self.assertIn(name, columns, table)
                        self.assertEqual(columns["source_url"][3], 1, table)
                        self.assertEqual(columns["long_term_url"][3], 1, table)
                        self.assertEqual(columns["detail_url_status"][3], 1, table)
            finally:
                conn.close()

    def test_relation_rows_store_source_url_long_term_status_and_locator(self):
        with tempfile.TemporaryDirectory() as tmp:
            conn = database.connect(Path(tmp) / "crawler.db")
            try:
                job_id = database.upsert_std_job(
                    conn,
                    {
                        "source_id": "nzrc",
                        "source_item_id": "job-1",
                        "source_url": "https://example.test/jobs/1",
                        "long_term_url": "https://example.test/jobs/1",
                        "detail_url": "https://example.test/jobs/1",
                        "detail_url_status": "direct",
                        "locator": "detail page",
                        "rights_status": "attribution-required",
                        "title": "示例岗位",
                        "location_raw": "示例省示例市",
                        "province": "示例省",
                        "city": "示例市",
                        "content_hash": database.sha256_text("job"),
                        "confidence": "high",
                        "license_or_usage": "attribution-required",
                        "publish_status": "draft",
                    },
                    self._now(),
                )
                job_source = conn.execute(
                    """
                    SELECT source_url, long_term_url, detail_url,
                           detail_url_status, locator
                    FROM std_job_sources WHERE job_id = ?
                    """,
                    (job_id,),
                ).fetchone()
                job_location = conn.execute(
                    """
                    SELECT source_url, long_term_url, detail_url,
                           detail_url_status, locator
                    FROM std_job_locations WHERE job_id = ?
                    """,
                    (job_id,),
                ).fetchone()
                self.assertEqual(
                    job_source,
                    (
                        "https://example.test/jobs/1",
                        "https://example.test/jobs/1",
                        "https://example.test/jobs/1",
                        "direct",
                        "detail page",
                    ),
                )
                self.assertEqual(job_location, job_source)
                with self.assertRaises(sqlite3.IntegrityError):
                    conn.execute(
                        """
                        INSERT INTO std_job_sources (
                            job_id, source_id, source_item_id, source_url,
                            long_term_url, detail_url_status, rights_status,
                            retrieved_at
                        ) VALUES (?, 'nzrc', 'job-2', ?, ?, 'missing',
                                  'attribution-required', ?)
                        """,
                        (
                            job_id,
                            "https://example.test/jobs/2",
                            "https://example.test/jobs/2",
                            self._now(),
                        ),
                    )
                conn.rollback()

                product_id = database.upsert_std_agri_product(
                    conn,
                    {
                        "source_id": "aqsc-moa",
                        "source_item_id": "product-1",
                        "source_url": "https://example.test/products/1",
                        "long_term_url": "https://example.test/announcement/1",
                        "detail_url": "https://example.test/products/1",
                        "detail_url_status": "direct",
                        "locator": "attachment row 1",
                        "rights_status": "attribution-required",
                        "cert_type": "名特优新",
                        "product_name": "示例产品",
                        "normalized_name": "示例产品",
                        "content_hash": database.sha256_text("product"),
                        "confidence": "medium",
                        "license_or_usage": "attribution-required",
                        "publish_status": "draft",
                    },
                    self._now(),
                )
                product_source = conn.execute(
                    """
                    SELECT source_url, long_term_url, detail_url,
                           detail_url_status, locator
                    FROM std_agri_product_sources WHERE product_id = ?
                    """,
                    (product_id,),
                ).fetchone()
                self.assertEqual(
                    product_source,
                    (
                        "https://example.test/products/1",
                        "https://example.test/announcement/1",
                        "https://example.test/products/1",
                        "direct",
                        "attachment row 1",
                    ),
                )

                project_id = self._insert_ich_project(conn)
                conn.execute(
                    """
                    INSERT INTO std_ich_inheritors (
                        project_id, source_id, source_item_id, source_url,
                        long_term_url, detail_url, detail_url_status, locator,
                        rights_status, name, retrieved_at, content_hash,
                        confidence
                    ) VALUES (?, 'ihchina', 'person-1', ?, ?, ?, 'direct',
                              'detail page', 'attribution-required',
                              '示例传承人', ?, ?, 'high')
                    """,
                    (
                        project_id,
                        "https://example.test/person/1",
                        "https://example.test/person/1",
                        "https://example.test/person/1",
                        self._now(),
                        database.sha256_text("person"),
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO std_ich_related_items (
                        source_id, subject_project_id, related_source_item_id,
                        relation_type, source_url, long_term_url, detail_url,
                        detail_url_status, locator, rights_status,
                        retrieved_at, content_hash
                    ) VALUES ('ihchina', ?, 'related-1', 'related', ?, ?, ?,
                              'direct', 'detail page',
                              'attribution-required', ?, ?)
                    """,
                    (
                        project_id,
                        "https://example.test/related/1",
                        "https://example.test/related/1",
                        "https://example.test/related/1",
                        self._now(),
                        database.sha256_text("related"),
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO std_ich_media_links (
                        project_id, source_id, source_item_id, source_url,
                        long_term_url, detail_url, detail_url_status, locator,
                        rights_status, media_url, availability, retrieved_at
                    ) VALUES (?, 'ihchina', 'project-1', ?, ?, ?, 'direct',
                              'detail page', 'attribution-required', ?, 'available', ?)
                    """,
                    (
                        project_id,
                        "https://example.test/project/1",
                        "https://example.test/project/1",
                        "https://example.test/project/1",
                        "https://example.test/media/1.jpg",
                        self._now(),
                    ),
                )
                for table, key in (
                    ("std_ich_inheritors", project_id),
                    ("std_ich_related_items", project_id),
                    ("std_ich_media_links", project_id),
                ):
                    row = conn.execute(
                        f"""
                        SELECT source_url, long_term_url, detail_url_status,
                               locator
                        FROM {table}
                        WHERE {"project_id" if table != "std_ich_related_items" else "subject_project_id"} = ?
                        """,
                        (key,),
                    ).fetchone()
                    self.assertIsNotNone(row, table)
                    self.assertTrue(row[0], table)
                    self.assertTrue(row[1], table)
                    self.assertEqual(row[2], "direct", table)
                    self.assertTrue(row[3], table)
            finally:
                conn.close()

    def test_std_agri_products_uses_source_pair_as_physical_natural_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            conn = database.connect(Path(tmp) / "crawler.db")
            try:
                values = (
                    "aqsc-moa", "duplicate", "https://example.test/product",
                    "https://example.test/product", "direct",
                    "https://example.test/product", "attribution-required",
                    "名特优新", "产品", "产品", database.sha256_text("product"),
                    "medium", "attribution-required", "draft", self._now(),
                    self._now(), self._now(),
                )
                sql = """
                    INSERT INTO std_agri_products (
                        source_id, source_item_id, source_url, long_term_url,
                        detail_url_status, detail_url, rights_status, cert_type,
                        product_name, normalized_name, content_hash, confidence,
                        license_or_usage, publish_status, retrieved_at,
                        first_seen_at, last_seen_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """
                conn.execute(sql, values)
                with self.assertRaises(sqlite3.IntegrityError):
                    conn.execute(sql, values)
            finally:
                conn.close()

    @staticmethod
    def _now():
        return "2026-10-20T00:00:00+08:00"

    def _insert_dialect_point(self, conn):
        return conn.execute(
            """
            INSERT INTO std_dialect_points (
                source_id, source_item_id, source_url, long_term_url,
                detail_url, detail_url_status, rights_status, region_raw,
                content_hash, confidence, license_or_usage, publish_status,
                retrieved_at, first_seen_at, last_seen_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "dialect-org", "point-1",
                "https://example.test/dialect/1", "https://example.test/dialect/1",
                "https://example.test/dialect/1", "direct",
                "attribution-required", "示例地区",
                database.sha256_text("point-1"), "medium",
                "attribution-required", "draft", self._now(), self._now(),
                self._now(),
            ),
        ).lastrowid

    def _insert_dialect_lexeme(self, conn, point_id):
        return conn.execute(
            """
            INSERT INTO std_dialect_lexemes (
                point_id, source_id, source_item_id, source_url, long_term_url,
                detail_url, detail_url_status, lemma, audio_status,
                rights_status, confidence, license_or_usage, publish_status,
                retrieved_at, content_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                point_id, "dialect-org", "lexeme-1",
                "https://example.test/dialect/1", "https://example.test/dialect/1",
                "https://example.test/dialect/1", "direct", "示例词",
                "missing", "attribution-required", "medium",
                "attribution-required", "draft", self._now(),
                database.sha256_text("lexeme-1"),
            ),
        ).lastrowid

    def _insert_ich_project(self, conn):
        return conn.execute(
            """
            INSERT INTO std_ich_projects (
                source_id, source_item_id, source_url, long_term_url,
                detail_url, detail_url_status, locator, rights_status,
                name, content_hash, confidence, license_or_usage,
                publish_status, retrieved_at, first_seen_at, last_seen_at
            ) VALUES ('ihchina', 'project-1', ?, ?, ?, 'direct',
                      'detail page', 'attribution-required', '示例项目',
                      ?, 'high', 'attribution-required', 'draft', ?, ?, ?)
            """,
            (
                "https://example.test/project/1",
                "https://example.test/project/1",
                "https://example.test/project/1",
                database.sha256_text("ich-project"),
                self._now(),
                self._now(),
                self._now(),
            ),
        ).lastrowid


if __name__ == "__main__":
    unittest.main()
