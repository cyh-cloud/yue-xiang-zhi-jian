import tempfile
import unittest
from pathlib import Path

from crawler.pipeline import database
from crawler.pipeline.converter import run_batch


class PublicationGateTest(unittest.TestCase):
    def _batch(self, key):
        return {
            "batch_key": key,
            "converter_version": "test-v1",
            "target_database": "yuexiang",
            "dry_run": True,
        }

    def _insert_ich_rows(self, conn):
        rows = [
            ("missing", "missing", "https://example.test/ich/announcement", "draft"),
            ("relative", "direct", "/relative-detail", "draft"),
            ("blocked", "direct", "https://example.test/ich/blocked", "blocked"),
            ("valid", "direct", "https://example.test/ich/valid", "draft"),
        ]
        for item_id, status, detail_url, publish_status in rows:
            conn.execute(
                """
                INSERT INTO std_ich_projects (
                    source_id, source_item_id, source_url, long_term_url,
                    detail_url, detail_url_status, locator, rights_status,
                    attribution_required, ich_code, name, declaration_region,
                    description_text, content_hash, confidence,
                    license_or_usage, publish_status, retrieved_at,
                    first_seen_at, last_seen_at, extra
                ) VALUES (
                    'ihchina', ?, 'https://example.test/ich/list', ?,
                    ?, ?, 'attachment row 1', 'attribution-required', 1, 'Ⅰ-1', ?,
                    '广东省', '正文', ?, 'high', 'attribution-required', ?,
                    '2026-10-20T00:00:00+08:00',
                    '2026-10-20T00:00:00+08:00',
                    '2026-10-20T00:00:00+08:00', '{}'
                )
                """,
                (
                    item_id,
                    detail_url or "https://example.test/ich/announcement",
                    detail_url,
                    status,
                    f"项目-{item_id}",
                    database.sha256_text(item_id),
                    publish_status,
                ),
            )

    def _insert_agri_rows(self, conn):
        rows = [
            ("missing", "missing", "https://example.test/agri/announcement", "draft"),
            ("relative", "direct", "/relative-detail", "draft"),
            ("blocked", "direct", "https://example.test/agri/blocked", "blocked"),
            ("valid", "direct", "https://example.test/agri/valid", "draft"),
        ]
        for item_id, status, detail_url, publish_status in rows:
            conn.execute(
                """
                INSERT INTO std_agri_products (
                    source_id, source_item_id, source_url, long_term_url,
                    detail_url, detail_url_status, locator, rights_status,
                    attribution_required, cert_type, product_name,
                    product_name_raw, normalized_name, province, region,
                    content_hash, confidence, license_or_usage,
                    publish_status, retrieved_at, first_seen_at,
                    last_seen_at, extra
                ) VALUES (
                    'aqsc-moa', ?, 'https://example.test/agri/list', ?,
                    ?, ?, 'attachment row 1', 'attribution-required', 1,
                    '名特优新', ?, ?, ?, '广东省', '广州市', ?, 'medium',
                    'attribution-required', ?,
                    '2026-10-20T00:00:00+08:00',
                    '2026-10-20T00:00:00+08:00',
                    '2026-10-20T00:00:00+08:00', '{}'
                )
                """,
                (
                    item_id,
                    detail_url or "https://example.test/agri/announcement",
                    detail_url,
                    status,
                    f"产品-{item_id}",
                    f"产品-{item_id}",
                    f"产品-{item_id}",
                    database.sha256_text(item_id),
                    publish_status,
                ),
            )

    def _insert_job_rows(self, conn):
        rows = [
            ("missing", "missing", "https://example.test/jobs/announcement", "draft"),
            ("relative", "direct", "/relative-detail", "draft"),
            ("blocked", "direct", "https://example.test/jobs/blocked", "blocked"),
            ("valid", "direct", "https://example.test/jobs/valid", "draft"),
        ]
        for item_id, status, detail_url, publish_status in rows:
            conn.execute(
                """
                INSERT INTO std_jobs (
                    source_id, source_item_id, source_url, long_term_url,
                    detail_url, detail_url_status, locator, rights_status,
                    attribution_required, title, location_raw, content_hash,
                    confidence, license_or_usage, publish_status, retrieved_at,
                    first_seen_at, last_seen_at, extra
                ) VALUES (
                    'nzrc', ?, 'https://example.test/jobs/list', ?, ?, ?,
                    'attachment row 1', 'attribution-required', 1, ?,
                    '广东省广州市', ?, 'high',
                    'attribution-required', ?,
                    '2026-10-20T00:00:00+08:00',
                    '2026-10-20T00:00:00+08:00',
                    '2026-10-20T00:00:00+08:00', '{}'
                )
                """,
                (
                    item_id,
                    detail_url or "https://example.test/jobs/announcement",
                    detail_url,
                    status,
                    f"岗位-{item_id}",
                    database.sha256_text(item_id),
                    publish_status,
                ),
            )

    def _insert_dialect_rows(self, conn):
        rows = [
            ("missing", "missing", "https://example.test/dialect/announcement", "draft"),
            ("relative", "direct", "/relative-detail", "draft"),
            ("blocked", "direct", "https://example.test/dialect/blocked", "blocked"),
            ("valid", "direct", "https://example.test/dialect/valid", "draft"),
        ]
        for item_id, status, detail_url, publish_status in rows:
            point_id = conn.execute(
                """
                INSERT INTO std_dialect_points (
                    source_id, source_item_id, source_url, long_term_url,
                    detail_url, detail_url_status, locator, rights_status,
                    attribution_required, region_raw, province, city,
                    confidence, license_or_usage, publish_status,
                    retrieved_at, first_seen_at, last_seen_at,
                    content_hash, extra
                ) VALUES (
                    'dialect-org', ?, 'https://example.test/dialect/list', ?,
                    ?, ?, 'attachment row 1', 'attribution-required', 1, ?,
                    '广东省', '广州市',
                    'medium', 'attribution-required', ?,
                    '2026-10-20T00:00:00+08:00',
                    '2026-10-20T00:00:00+08:00',
                    '2026-10-20T00:00:00+08:00', ?, '{}'
                )
                """,
                (
                    item_id,
                    detail_url or "https://example.test/dialect/announcement",
                    detail_url,
                    status,
                    f"地区-{item_id}",
                    publish_status,
                    database.sha256_text(f"point:{item_id}"),
                ),
            ).lastrowid
            lexeme_id = conn.execute(
                """
                INSERT INTO std_dialect_lexemes (
                    point_id, source_id, source_item_id, source_url,
                    long_term_url, detail_url, detail_url_status,
                    locator, rights_status, attribution_required, lemma,
                    audio_status, confidence, license_or_usage,
                    publish_status, retrieved_at, content_hash, extra
                ) VALUES (
                    ?, 'dialect-org', ?, 'https://example.test/dialect/list',
                    ?, ?, ?, 'attachment row 1', 'attribution-required', 1, ?,
                    'missing', 'medium', 'attribution-required', ?,
                    '2026-10-20T00:00:00+08:00', ?, '{}'
                )
                """,
                (
                    point_id,
                    item_id,
                    detail_url or "https://example.test/dialect/announcement",
                    detail_url,
                    status,
                    f"词-{item_id}",
                    publish_status,
                    database.sha256_text(f"lexeme:{item_id}"),
                ),
            ).lastrowid
            conn.execute(
                """
                INSERT INTO std_dialect_lexeme_sources (
                    lexeme_id, source_id, source_item_id, source_url,
                    long_term_url, detail_url, detail_url_status,
                    locator, rights_status, attribution_required, is_primary,
                    retrieved_at, content_hash, extra
                ) VALUES (
                    ?, 'dialect-org', ?, 'https://example.test/dialect/list',
                    ?, ?, ?, 'attachment row 1', 'attribution-required', 1, 1,
                    '2026-10-20T00:00:00+08:00', ?, '{}'
                )
                """,
                (
                    lexeme_id,
                    item_id,
                    detail_url or "https://example.test/dialect/announcement",
                    detail_url,
                    status,
                    database.sha256_text(f"source:{item_id}"),
                ),
            )

    def _assert_single_valid_plan(self, domain, insert_rows, entity):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / "crawler.db"
            conn = database.connect(db_path)
            try:
                insert_rows(conn)
                conn.commit()
            finally:
                conn.close()

            result = run_batch(
                domain,
                self._batch(f"{domain}-publication-gate"),
                crawler_database_path=db_path,
            )

            self.assertEqual(result.input_count, 4)
            self.assertEqual(result.inserted_count, 1)
            self.assertEqual(result.skipped_count, 3)
            self.assertEqual(result.failed_count, 0)
            self.assertEqual(len(result.by_entity[entity]["rows"]), 1)
            self.assertIn(
                "valid",
                str(result.by_entity[entity]["rows"][0]),
            )

    def test_ich_requires_direct_absolute_detail_and_allowed_publish_status(self):
        self._assert_single_valid_plan(
            "ich", self._insert_ich_rows, "std_ich_projects"
        )

    def test_agri_requires_direct_absolute_detail_and_allowed_publish_status(self):
        self._assert_single_valid_plan(
            "agri", self._insert_agri_rows, "std_agri_products"
        )

    def test_jobs_requires_direct_absolute_detail_and_allowed_publish_status(self):
        self._assert_single_valid_plan("jobs", self._insert_job_rows, "std_jobs")

    def test_dialects_requires_direct_absolute_detail_and_allowed_publish_status(self):
        self._assert_single_valid_plan(
            "dialects", self._insert_dialect_rows, "std_dialect_lexemes"
        )


if __name__ == "__main__":
    unittest.main()
