import unittest
from pathlib import Path
import sys

from scrapy.http import HtmlResponse


PROJECT_ROOT = (
    Path(__file__).resolve().parents[1]
    / "collection"
    / "projects"
    / "cass-linguistics"
)
sys.path.insert(0, str(PROJECT_ROOT))

from cass_linguistics.parsers import parse_article_detail, parse_article_list
from cass_linguistics.spiders.collection import CassLinguisticsSpider


LIST_HTML = """
<div class="li_pgUl"><div class="li_bqListRight">
  <h2><a href="/news/bensuo/202609/t20260904_6066095.html">公开研究</a></h2>
  <p>公开摘要</p>
  <span>时间：2026-09-04</span>
</div></div>
"""

DETAIL_HTML = """
<html><head><title>公开研究</title></head><body>
  <div class="TRS_Editor"><p>公开研究正文</p></div>
  <span>来源：中国社会科学网</span>
  <span>时间：2026-09-04</span>
</body></html>
"""


class CassLinguisticsScrapyTest(unittest.TestCase):
    def test_list_parser_keeps_public_article_links(self):
        response = HtmlResponse(
            url="http://ling.cass.cn/news/bensuo/",
            body=LIST_HTML.encode("utf-8"),
            encoding="utf-8",
        )

        parsed = parse_article_list(response)
        items = parsed["items"]

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["source_item_id"], "6066095")
        self.assertEqual(items[0]["title"], "公开研究")
        self.assertEqual(
            items[0]["detail_url"],
            "http://ling.cass.cn/news/bensuo/202609/t20260904_6066095.html",
        )

    def test_detail_parser_keeps_public_body_and_metadata(self):
        response = HtmlResponse(
            url=(
                "http://ling.cass.cn/news/bensuo/202609/"
                "t20260904_6066095.html"
            ),
            body=DETAIL_HTML.encode("utf-8"),
            encoding="utf-8",
        )

        item = parse_article_detail(response)

        self.assertEqual(item["title"], "公开研究")
        self.assertIn("公开研究正文", item["body_text"])
        self.assertEqual(item["extra"]["media"], "中国社会科学网")
        self.assertEqual(item["extra"]["published_at"], "2026-09-04")
        self.assertEqual(item["body_access"], "public")

    def test_external_login_domain_is_not_requested(self):
        spider = CassLinguisticsSpider()
        self.assertEqual(spider.name, "cass-linguistics")
        self.assertEqual(spider.source_id, "cass-linguistics")
        self.assertEqual(spider.allowed_domains, ["ling.cass.cn"])
        self.assertNotIn("www.dialectgrammar.com", spider.allowed_domains)


if __name__ == "__main__":
    unittest.main()
