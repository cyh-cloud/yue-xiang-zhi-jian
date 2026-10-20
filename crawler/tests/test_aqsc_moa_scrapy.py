import tempfile
import unittest
from pathlib import Path
import sys

PROJECT_ROOT = (
    Path(__file__).resolve().parents[1]
    / "collection"
    / "projects"
    / "aqsc-moa"
)
sys.path.insert(0, str(PROJECT_ROOT))

from aqsc_moa.parsers import (
    fixture_files,
    fixture_item,
)
from aqsc_moa.spiders.collection import (
    AqscMoaSpider,
)
from crawler.collection.shared.crawler_collection.evidence import RawEvidence
from crawler.collection.shared.crawler_collection.items import CollectionItem
from crawler.collection.shared.crawler_collection.runtime import CollectionRuntime


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "evidence" / "aqsc-moa"
REGISTRY = ROOT / "docs" / "sources.json"


class AqscMoaScrapySkeletonTest(unittest.TestCase):
    def test_spider_is_fixture_only_and_has_no_start_urls(self):
        spider = AqscMoaSpider()
        self.assertEqual(spider.name, "aqsc-moa")
        self.assertEqual(spider.source_id, "aqsc-moa")
        self.assertEqual(spider.start_urls, [])
        self.assertFalse(spider.live_enabled)

    def test_fixture_files_are_hashed_and_never_downloaded(self):
        records = fixture_files(FIXTURE)

        self.assertEqual(len(records), 2)
        self.assertTrue(all(record["mime_type"] for record in records))
        self.assertTrue(all(len(record["sha256"]) == 64 for record in records))
        self.assertTrue(all(record["locator"] for record in records))

    def test_missing_detail_fixture_row_stays_out_of_candidates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runtime = CollectionRuntime(
                database_path=root / "crawler.db",
                download_root=root / "downloads",
                registry_path=REGISTRY,
            )
            item = CollectionItem(
                **fixture_item(FIXTURE / "synthetic-mtyx-sample.xlsx")
            )
            raw_id = runtime.persist_raw(
                RawEvidence(
                    source_id="aqsc-moa",
                    request_url=item.source_url,
                    final_url=item.source_url,
                    body=b"fixture",
                    content_type="text/plain",
                    declared_size=1,
                    robots_decision="allowed",
                )
            )

            result = runtime.write_item(item, raw_evidence_id=raw_id)

        self.assertEqual(result["candidate_status"], "blocked")
        self.assertEqual(result["candidate_reason"], "detail_url:missing")


if __name__ == "__main__":
    unittest.main()
