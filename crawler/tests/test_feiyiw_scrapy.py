import unittest
from pathlib import Path
import sys

from scrapy.http import HtmlResponse


PROJECT_ROOT = (
    Path(__file__).resolve().parents[1]
    / "collection"
    / "projects"
    / "feiyiw"
)
sys.path.insert(0, str(PROJECT_ROOT))

from feiyiw.parsers import parse_article_detail, parse_article_list
from feiyiw.spiders.collection import FeiyiwSpider


LIST_HTML = """
<html><body><div id="page-article"><div class="col-main">
  <ul class="content">
    <li><a class="lebioa" href="/index.php?app=article&amp;act=view&amp;article_id=70177">文章一</a><span>2026.10.16</span></li>
    <li><a class="lebioa" href="/index.php?app=member&amp;act=login">会员</a></li>
  </ul>
  <div class="page"><div class="total">共1176页</div></div>
</div></div></body></html>
"""

DETAIL_HTML = """
<html><body><div id="page-article"><div class="col-main">
  <div class="title"><div class="location">非遗大数据</div></div>
  <div class="article-info"><h1>文章一</h1><h2>2026-10-16 15:56</h2></div>
  <div class="article-detail"><p>【项目名称】示例项目</p><p>公开正文</p></div>
</div></div></body></html>
"""


class FeiyiwScrapyTest(unittest.TestCase):
    def test_list_parser_keeps_only_public_articles(self):
        response = HtmlResponse(
            url="https://www.feiyiw.cn/index.php?app=article&cate_id=4",
            body=LIST_HTML.encode("utf-8"),
            encoding="utf-8",
        )

        parsed = parse_article_list(response)

        self.assertEqual(len(parsed["items"]), 1)
        self.assertEqual(parsed["items"][0]["source_item_id"], "70177")
        self.assertEqual(parsed["items"][0]["published_at"], "2026.10.16")

    def test_detail_parser_extracts_body_and_date(self):
        response = HtmlResponse(
            url=(
                "https://www.feiyiw.cn/index.php?"
                "app=article&act=view&article_id=70177"
            ),
            body=DETAIL_HTML.encode("utf-8"),
            encoding="utf-8",
        )

        item = parse_article_detail(response)

        self.assertEqual(item["source_item_id"], "70177")
        self.assertEqual(item["title"], "文章一")
        self.assertIn("公开正文", item["body_text"])
        self.assertEqual(item["published_at"], "2026-10-16 15:56")
        self.assertNotIn("contact_phone", item)

    def test_spider_is_site_specific(self):
        spider = FeiyiwSpider()
        self.assertEqual(spider.name, "feiyiw")
        self.assertEqual(spider.source_id, "feiyiw")
        self.assertEqual(spider.allowed_domains, ["www.feiyiw.cn"])


if __name__ == "__main__":
    unittest.main()
