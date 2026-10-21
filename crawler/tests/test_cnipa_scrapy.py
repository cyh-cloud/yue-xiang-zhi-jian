import tempfile
import unittest
from pathlib import Path
import sys

from crawler.collection.shared.crawler_collection.evidence import RawEvidence
from crawler.collection.shared.crawler_collection.items import CollectionItem
from crawler.collection.shared.crawler_collection.runtime import CollectionRuntime


PROJECT_ROOT = (
    Path(__file__).resolve().parents[1]
    / "collection"
    / "projects"
    / "cnipa"
)
sys.path.insert(0, str(PROJECT_ROOT))

from cnipa.parsers import fixture_files, fixture_item
from cnipa.candidate import write_candidate
from cnipa.spiders.collection import CnipaSpider


ROOT = Path(__file__).resolve().parents[1]
PDF = (
    ROOT
    / "tests"
    / "fixtures"
    / "evidence"
    / "cnipa"
    / "synthetic-announcement-687.pdf"
)


class CnipaScrapySkeletonTest(unittest.TestCase):
    def test_spider_is_fixture_only_and_has_no_start_urls(self):
        spider = CnipaSpider()
        self.assertEqual(spider.name, "cnipa")
        self.assertEqual(spider.source_id, "cnipa")
        self.assertEqual(spider.start_urls, [])
        self.assertFalse(spider.live_enabled)

    def test_pdf_fixture_has_hash_page_locator_and_no_real_download(self):
        records = fixture_files(PDF.parent)

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["mime_type"], "application/pdf")
        self.assertEqual(len(records[0]["sha256"]), 64)
        self.assertIn("page=1", records[0]["locator"])
        self.assertEqual(records[0]["byte_size"], PDF.stat().st_size)

    def test_fixture_item_keeps_signature_out_of_long_term_url(self):
        item = fixture_item(PDF)

        self.assertEqual(
            item["long_term_url"],
            "https://ggfw.cnipa.gov.cn/dlbzsq/detail?id=541",
        )
        self.assertNotIn("X-Amz", item["long_term_url"])
        self.assertIn("X-Amz", item["fetch_url"])

    def test_missing_detail_row_uses_carrier_and_locator(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runtime = CollectionRuntime(
                database_path=root / "crawler.db",
                download_root=root / "downloads",
                registry_path=ROOT / "docs" / "sources.json",
                candidate_writer=write_candidate,
            )
            item = CollectionItem(**fixture_item(PDF))
            raw_id = runtime.persist_raw(
                RawEvidence(
                    source_id="cnipa",
                    request_url=item.source_url,
                    final_url=item.source_url,
                    body=b"fixture",
                    content_type="application/pdf",
                    declared_size=1,
                    robots_decision="allowed",
                )
            )

            result = runtime.write_item(item, raw_evidence_id=raw_id)

        self.assertEqual(result["candidate_status"], "candidate")


if __name__ == "__main__":
    unittest.main()
