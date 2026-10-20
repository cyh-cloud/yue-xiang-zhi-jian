import unittest

from scrapy.http import HtmlResponse

from crawler.collection.projects.nzrc.nzrc.parsers import (
    parse_job_detail,
    parse_job_list,
)
from crawler.collection.projects.nzrc.nzrc.spiders.collection import NzrcSpider


LIST_HTML = """
<html><body>
  <div class="detail_headline">
    <input name="checkbox2" value="8235500">
    <div class="career_name"><a class="green"
      href="/company/jobs/8235500.html">销售经理</a></div>
    <div class="corp_name"><a class="green"
      href="/company/companys/14747.html">示例农业公司</a></div>
    <div class="suozaidi">广东</div>
    <div class="shijian">2026-10-17</div>
  </div>
</body></html>
"""

DETAIL_HTML = """
<html><body><div id="project_L">
  <h1><a href="/company/companys/14747.html">示例农业公司</a></h1>
  <h2>招聘职位：销售经理</h2>
  <ul>
    <li>工作地点：广东</li><li>有效时间：90 天</li>
    <li>招聘方式：全职</li><li>招聘人数：1人</li>
    <li>性别要求：男</li><li>承诺月薪：面议</li>
    <li>发布日期：2026-10-17</li><li>学历要求：大专</li>
  </ul>
  <div id="brief_info"><p>公开岗位职责</p><p>公开任职要求</p></div>
  <div id="fixtel">***</div>
</div></body></html>
"""


class NzrcScrapyTest(unittest.TestCase):
    def test_list_parser_normalizes_job_and_company_urls(self):
        response = HtmlResponse(
            url="http://www.nzrc.com.cn/career_seek.html",
            body=LIST_HTML.encode("utf-8"),
            encoding="utf-8",
        )

        items = parse_job_list(response)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["source_item_id"], "8235500")
        self.assertEqual(items[0]["title"], "销售经理")
        self.assertEqual(
            items[0]["detail_url"],
            "http://www.nzrc.com.cn/company/jobs/8235500.html",
        )
        self.assertNotIn("contact_phone", items[0]["extra"])

    def test_detail_parser_keeps_public_fields_and_hides_contacts(self):
        response = HtmlResponse(
            url="http://www.nzrc.com.cn/company/jobs/8235500.html",
            body=DETAIL_HTML.encode("utf-8"),
            encoding="utf-8",
        )

        item = parse_job_detail(response)

        self.assertEqual(item["source_item_id"], "8235500")
        self.assertEqual(item["extra"]["company_name"], "示例农业公司")
        self.assertEqual(item["extra"]["validity_days"], 90)
        self.assertEqual(item["extra"]["headcount"], 1)
        self.assertNotIn("contact_phone", item)
        self.assertIn("rights_risk", item["extra"])

    def test_spider_is_site_specific(self):
        spider = NzrcSpider()
        self.assertEqual(spider.name, "nzrc")
        self.assertEqual(spider.source_id, "nzrc")
        self.assertEqual(spider.allowed_domains, ["www.nzrc.com.cn"])


if __name__ == "__main__":
    unittest.main()
