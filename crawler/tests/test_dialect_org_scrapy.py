import unittest
from pathlib import Path
import sys
import tempfile

from scrapy.http import HtmlResponse, TextResponse


PROJECT_ROOT = (
    Path(__file__).resolve().parents[1]
    / "collection"
    / "projects"
    / "dialect-org"
)
sys.path.insert(0, str(PROJECT_ROOT))

from dialect_org.parsers import (
    parse_dialect_detail,
    parse_dialect_list,
)
from dialect_org.spiders.collection import (
    DialectOrgSpider,
)
from dialect_org.candidate import write_candidate
from crawler.collection.shared.crawler_collection.runtime import (
    CollectionRuntime,
)


class DialectOrgScrapyTest(unittest.TestCase):
    def test_list_parser_keeps_dialect_source_urls(self):
        response = TextResponse(
            url="https://dialect.org.cn/",
            body=(
                '<a href="/dialect/1">食饭</a>'
                '<a href="https://dialect.org.cn/dialect/1">duplicate</a>'
                '<a href="/dialect/2">饮茶</a>'
            ).encode("utf-8"),
            encoding="utf-8",
        )

        items = parse_dialect_list(response)

        self.assertEqual(
            [item["source_item_id"] for item in items], ["1", "2"]
        )
        self.assertEqual(
            items[0]["detail_url"],
            "https://dialect.org.cn/dialect/1",
        )

    def test_detail_parser_preserves_region_and_audio_status(self):
        response = HtmlResponse(
            url="https://dialect.org.cn/dialect/1",
            body=(
                '<main><div class="detail-header">'
                '<span class="card-tag">广东广州</span></div>'
                '<h1 class="detail-word">食饭</h1>'
                '<div class="detail-phonetic">Sik6 faan6</div>'
                '<div class="audio-box"><audio src='
                '"https://你的OSS bucket.oss-cn-hangzhou.aliyuncs.com/a.mp3">'
                "</audio></div>"
                '<div class="card"><p>粤语：吃饭</p></div></main>'
            ).encode("utf-8"),
            encoding="utf-8",
        )

        parsed = parse_dialect_detail(response)

        self.assertEqual(parsed["point"]["source_item_id"], "1")
        self.assertEqual(parsed["lexeme"]["lemma"], "食饭")
        self.assertEqual(parsed["lexeme"]["audio_status"], "invalid")
        self.assertEqual(parsed["point"]["province"], "广东")
        self.assertEqual(parsed["point"]["city"], "广州")
        self.assertTrue(parsed["point"]["extra"]["rights_risk"])

    def test_spider_is_site_specific(self):
        spider = DialectOrgSpider()
        self.assertEqual(spider.name, "dialect-org")
        self.assertEqual(spider.source_id, "dialect-org")
        self.assertEqual(spider.allowed_domains, ["dialect.org.cn"])

    def test_pipeline_runtime_persists_point_and_lexeme(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runtime = CollectionRuntime(
                database_path=root / "crawler.db",
                download_root=root / "downloads",
                registry_path=(
                    Path(__file__).resolve().parents[1]
                    / "docs"
                    / "sources.json"
                ),
                candidate_writer=write_candidate,
            )
            parsed = parse_dialect_detail(
                HtmlResponse(
                    url="https://dialect.org.cn/dialect/1",
                    body=(
                        '<main><div class="detail-header">'
                        '<span class="card-tag">广东广州</span></div>'
                        '<h1 class="detail-word">食饭</h1>'
                        '<div class="detail-phonetic">Sik6 faan6</div>'
                        '<div class="card"><p>粤语：吃饭</p></div></main>'
                    ).encode("utf-8"),
                    encoding="utf-8",
                )
            )
            point = dict(parsed["point"])
            point["extra"] = {
                **point["extra"],
                "lexeme": parsed["lexeme"],
            }
            point.setdefault("run_id", "test")
            point.setdefault("mode", "live")
            raw_id = runtime.persist_raw(
                runtime.evidence_from_fixture(
                    source_id="dialect-org",
                    body=b"<html/>",
                    request_url="https://dialect.org.cn/dialect/1",
                    content_type="text/html",
                    run_id="test",
                )
            )

            result = runtime.write_item(point, raw_evidence_id=raw_id)

            self.assertEqual(result["candidate_status"], "candidate")


if __name__ == "__main__":
    unittest.main()
