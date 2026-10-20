import unittest

from scrapy.http import HtmlResponse

from crawler.collection.projects.nongmuhr.nongmuhr.parsers import (
    parse_job_detail,
    parse_job_list,
)
from crawler.collection.projects.nongmuhr.nongmuhr.spiders.collection import (
    NongmuhrSpider,
)


LIST_HTML = """
<html><body>
  <a href="/EmployView.aspx?id=13520">养殖员</a>
  <a href="/EmployView.aspx?id=13519">技术员</a>
</body></html>
"""

DETAIL_HTML = """
<html><body><div id="project_L">
  <h1><a href="/CompanyView.aspx?id=1">示例农牧公司</a></h1>
  <h2>招聘职位：养殖员</h2>
  <ul>
    <li>工作地点：广东</li><li>有效时间：90 天</li>
    <li>招聘方式：全职</li><li>招聘人数：2人</li>
    <li>性别要求：不限</li><li>承诺月薪：面议</li>
    <li>发布日期：2026-10-17</li><li>学历要求：大专</li>
  </ul>
  <div id="brief_info"><p>公开养殖岗位职责</p></div>
</div></body></html>
"""


class NongmuhrScrapyTest(unittest.TestCase):
    def test_list_parser_extracts_stable_job_ids(self):
        response = HtmlResponse(
            url="http://nongmuhr.com/Employ.aspx",
            body=LIST_HTML.encode("utf-8"),
            encoding="utf-8",
        )

        items = parse_job_list(response)

        self.assertEqual(
            [item["source_item_id"] for item in items],
            ["13520", "13519"],
        )
        self.assertEqual(
            items[0]["detail_url"],
            "http://nongmuhr.com/EmployView.aspx?id=13520",
        )

    def test_list_parser_accepts_capitalized_id_parameter(self):
        response = HtmlResponse(
            url="http://nongmuhr.com/Employ.aspx",
            body=b'<a href="EmployView.aspx?Id=13539">job</a>',
            encoding="utf-8",
        )

        self.assertEqual(
            parse_job_list(response)[0]["source_item_id"], "13539"
        )

    def test_detail_parser_extracts_expiry_and_public_fields(self):
        response = HtmlResponse(
            url="http://nongmuhr.com/EmployView.aspx?id=13520",
            body=DETAIL_HTML.encode("utf-8"),
            encoding="utf-8",
        )

        item = parse_job_detail(response)

        self.assertEqual(item["source_item_id"], "13520")
        self.assertEqual(item["title"], "养殖员")
        self.assertEqual(item["extra"]["validity_days"], 90)
        self.assertEqual(item["extra"]["headcount"], 2)
        self.assertIn("rights_risk", item["extra"])
        self.assertNotIn("contact_phone", item)

    def test_spider_is_site_specific(self):
        spider = NongmuhrSpider()
        self.assertEqual(spider.name, "nongmuhr")
        self.assertEqual(spider.source_id, "nongmuhr")
        self.assertEqual(spider.allowed_domains, ["nongmuhr.com"])


if __name__ == "__main__":
    unittest.main()
