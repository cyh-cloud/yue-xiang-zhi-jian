import json
import tempfile
import unittest
from pathlib import Path

from crawler.pipeline import RunConfig, run_source
from crawler.pipeline import database
from crawler.pipeline.converter import run_batch


ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "docs" / "sources.json"


class SourceRegistryTest(unittest.TestCase):
    def test_legacy_entry_cannot_enable_a_mode_missing_from_registry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
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
                                "run_modes": ["fixture"],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            config = RunConfig(
                database_path=root / "crawler.db",
                download_root=root / "download",
                fixture_root=root / "fixture",
                source_root=root / "saved",
                registry_path=registry,
            )

            with self.assertRaises(ValueError):
                run_source("nzrc", "saved", config)

    def test_registry_has_final_ids_statuses_and_rights(self):
        payload = json.loads(SOURCES.read_text(encoding="utf-8"))
        sources = {source["id"]: source for source in payload["sources"]}

        self.assertEqual(len(sources), 14)
        self.assertEqual(
            {
                source_id
                for source_id, source in sources.items()
                if "weather" in source["content_domains"]
            },
            {"weather", "open-meteo", "qweather"},
        )
        self.assertEqual(sources["5ajob"]["rights_status"], "prohibited")
        self.assertEqual(sources["cnopendata"]["status"], "deferred")
        self.assertFalse(sources["cnopendata"]["enabled"])
        self.assertEqual(sources["zhongguoyuyan"]["status"], "excluded")
        self.assertEqual(sources["open-meteo"]["status"], "draft")
        self.assertEqual(sources["qweather"]["status"], "draft")
        self.assertEqual(sources["ihchina"]["run_modes"], ["fixture", "live"])
        self.assertEqual(sources["aqsc-moa"]["run_modes"], ["fixture"])
        self.assertEqual(sources["cnipa"]["run_modes"], ["fixture"])
        self.assertEqual(sources["cnopendata"]["run_modes"], [])
        self.assertTrue(sources["cnipa"]["attribution_required"])
        self.assertTrue(sources["cnipa"]["rights_evidence_url"])

    def test_legacy_entry_only_accepts_registry_declared_modes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = RunConfig(
                database_path=root / "crawler.db",
                download_root=root / "download",
                fixture_root=root / "fixture",
                source_root=root / "saved",
                xlsx_root=root / "xlsx",
                pdf_root=root / "pdf",
                registry_path=SOURCES,
            )

            cnipa = run_source("cnipa", "fixture", config)
            aqsc = run_source("aqsc-moa", "fixture", config)

            self.assertEqual(cnipa.status, "failed")
            self.assertEqual(aqsc.status, "failed")

    def test_blocked_registry_source_does_not_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = root / "fixture"
            fixture.mkdir()
            (fixture / "discover.json").write_text(
                json.dumps(
                    {
                        "source_id": "fixture-source",
                        "items": [
                            {
                                "source_item_id": "1",
                                "title": "Blocked fixture",
                                "source_url": "https://example.test/item/1",
                                "long_term_url": "https://example.test/item/1",
                                "detail_url": "https://example.test/item/1",
                                "detail_url_status": "direct",
                                "locator": "fixture item 1",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            registry = root / "sources.json"
            registry.write_text(
                json.dumps(
                    {
                        "sources": [
                            {
                                "id": "fixture-source",
                                "name": "Blocked fixture",
                                "enabled": True,
                                "status": "blocked",
                                "access": "public",
                                "rights_status": "attribution-required",
                                "run_modes": ["fixture"],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            config = RunConfig(
                database_path=root / "crawler.db",
                download_root=root / "download",
                fixture_root=fixture,
                registry_path=registry,
            )

            result = run_source("fixture-source", "fixture", config)

            self.assertEqual(result.status, "blocked")
            self.assertEqual(result.discovered_count, 0)
            self.assertFalse(config.database_path.exists())

    def test_converter_rejects_rows_from_blocked_registry_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / "crawler.db"
            registry = root / "sources.json"
            registry.write_text(
                json.dumps(
                    {
                        "sources": [
                            {
                                "id": "blocked-source",
                                "name": "Blocked source",
                                "enabled": True,
                                "status": "blocked",
                                "access": "public",
                                "rights_status": "attribution-required",
                                "run_modes": [],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            conn = database.connect(db_path)
            try:
                conn.execute(
                    """
                    INSERT INTO std_ich_projects (
                        source_id, source_item_id, source_url, long_term_url,
                        detail_url, detail_url_status, locator, rights_status,
                        attribution_required, ich_code, name,
                        declaration_region, description_text, content_hash,
                        confidence, license_or_usage, publish_status,
                        retrieved_at, first_seen_at, last_seen_at, extra
                    ) VALUES (
                        'blocked-source', '1',
                        'https://example.test/ich/1',
                        'https://example.test/ich/1',
                        'https://example.test/ich/1', 'direct', NULL,
                        'attribution-required', 1, 'Ⅰ-1', 'Blocked project',
                        '广东省', 'body', 'hash', 'high',
                        'attribution-required', 'draft',
                        '2026-10-20T00:00:00+00:00',
                        '2026-10-20T00:00:00+00:00',
                        '2026-10-20T00:00:00+00:00', '{}'
                    )
                    """
                )
                conn.commit()
            finally:
                conn.close()

            result = run_batch(
                "ich",
                {
                    "batch_key": "blocked-registry",
                    "converter_version": "test-v1",
                    "target_database": "yuexiang",
                    "dry_run": True,
                },
                crawler_database_path=db_path,
                source_registry_path=registry,
            )

            self.assertEqual(result.input_count, 1)
            self.assertEqual(result.inserted_count, 0)
            self.assertEqual(result.skipped_count, 1)


if __name__ == "__main__":
    unittest.main()
