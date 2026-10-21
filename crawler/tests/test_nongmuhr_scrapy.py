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
  <div id="joblist_table">
    <table class="joblist_b_border">
      <tr><td colspan="4">
        <div class="joblist_showlist"><table><tr>
          <td class="joblist_jobname" width="255">
            <a href="EmployView.aspx?Id=13553">设备工程师</a>
          </td>
          <td class="joblist_a">
            <div class="fontover_hide width_240">
              <a id="rptList_hlCompany_0"
                 href="CompanyView.aspx?Id=1137">江西华裕家禽育种有限公司</a>
            </div>
          </td>
          <td colspan="2">
            <div class="fontover_hide width_105">宜春市</div>
          </td>
          <td width="105">3天前</td>
        </tr></table></div>
        <div class="joblist_info"><table>
          <tr><td>
            <div class="job_list_zf">
              招聘人数： <b>1</b> | 月薪：8000-9999元 |
              学历要求：高中 公司规模：100－499人 |
              公司性质：外资/合资企业
            </div>
          </td></tr>
          <tr><td height="48">职位描述：负责养殖场设备维护。</td></tr>
        </table></div>
      </td></tr>
      <tr><td colspan="4">
        <div class="joblist_showlist"><table><tr>
          <td class="joblist_jobname" width="255">
            <a href="EmployView.aspx?Id=13556">管培生</a>
          </td>
          <td class="joblist_a">
            <div class="fontover_hide width_240">
              <a id="rptList_hlCompany_1"
                 href="CompanyView.aspx?Id=2360">河南浪之潮农业科技有限公司</a>
            </div>
          </td>
          <td colspan="2">
            <div class="fontover_hide width_105">不限地点</div>
          </td>
          <td width="105">2天前</td>
        </tr></table></div>
      </td></tr>
    </table>
  </div>
</body></html>
"""

DETAIL_HTML = """
<html><body>
  <div id="joblist"><div class="joblistonelf">设备工程师</div>
    <a id="hlCompanyName"
       href="CompanyView.aspx?Id=1137">江西华裕家禽育种有限公司</a>
  </div>
  <div class="saverg"><table>
    <tr><td>工作性质：</td><td>全职</td><td>部 门：</td><td>设备部</td></tr>
    <tr><td>招聘人数：</td><td>1</td><td>截止日期：</td><td>2026-07-30</td></tr>
    <tr><td>工作经验：</td><td>3年以上</td><td>学 历：</td><td>高中</td></tr>
    <tr><td>工作地点：</td><td>宜春市</td><td>性 别：</td><td>不限</td></tr>
    <tr><td>年 龄：</td><td>30-45</td><td>邮 件：</td><td>{{EMAIL_demo}}</td></tr>
    <tr><td>职位描述及具体要求：</td></tr>
    <tr><td style="word-break: break-all">负责养殖场设备维护。</td></tr>
    <tr><td>发布时间：</td><td>2025-08-10</td></tr>
  </table></div>
  <div id="joblist1"><td class="y12x">
    所属行业：养殖/宠物 公司规模：100－499人
    公司性质：外资/合资企业 所在地区:江西
  </td></div>
</body></html>
"""


class NongmuhrScrapyTest(unittest.TestCase):
    def test_list_parser_extracts_current_job_row_fields(self):
        response = HtmlResponse(
            url="http://nongmuhr.com/Employ.aspx",
            body=LIST_HTML.encode("utf-8"),
            encoding="utf-8",
        )

        items = parse_job_list(response)

        self.assertEqual(
            [item["source_item_id"] for item in items],
            ["13553", "13556"],
        )
        self.assertEqual(
            items[0]["detail_url"],
            "http://nongmuhr.com/EmployView.aspx?Id=13553",
        )
        self.assertEqual(items[0]["extra"]["company_name"], "江西华裕家禽育种有限公司")
        self.assertEqual(items[0]["extra"]["location_raw"], "宜春市")
        self.assertEqual(items[0]["extra"]["headcount"], 1)
        self.assertEqual(items[0]["extra"]["salary_raw"], "8000-9999元")
        self.assertEqual(items[0]["extra"]["education_raw"], "高中")

    def test_list_parser_accepts_capitalized_id_parameter(self):
        response = HtmlResponse(
            url="http://nongmuhr.com/Employ.aspx",
            body=b"""
            <div id="joblist_table"><table><tr><td>
              <div class="joblist_showlist">
                <table><tr><td class="joblist_jobname">
                  <a href="EmployView.aspx?Id=13539">job</a>
                </td></tr></table>
              </div>
            </td></tr></table></div>
            """,
            encoding="utf-8",
        )

        self.assertEqual(
            parse_job_list(response)[0]["source_item_id"], "13539"
        )

    def test_detail_parser_extracts_current_detail_table_fields(self):
        response = HtmlResponse(
            url="http://nongmuhr.com/EmployView.aspx?Id=13553",
            body=DETAIL_HTML.encode("utf-8"),
            encoding="utf-8",
        )

        item = parse_job_detail(response)

        self.assertEqual(item["source_item_id"], "13553")
        self.assertEqual(item["title"], "设备工程师")
        self.assertEqual(item["extra"]["company_name"], "江西华裕家禽育种有限公司")
        self.assertEqual(item["extra"]["company_url"], "http://nongmuhr.com/CompanyView.aspx?Id=1137")
        self.assertEqual(item["extra"]["headcount"], 1)
        self.assertEqual(item["extra"]["deadline_at"], "2026-07-30")
        self.assertEqual(item["extra"]["published_at"], "2025-08-10")
        self.assertEqual(item["body_text"], "负责养殖场设备维护。")
        self.assertIn("rights_risk", item["extra"])
        self.assertNotIn("contact_phone", item)

    def test_detail_parser_rejects_missing_job_title_container(self):
        response = HtmlResponse(
            url="http://nongmuhr.com/EmployView.aspx?Id=13553",
            body=b"<html><body><p>navigation only</p></body></html>",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(ValueError, "job title"):
            parse_job_detail(response)

    def test_spider_is_site_specific(self):
        spider = NongmuhrSpider()
        self.assertEqual(spider.name, "nongmuhr")
        self.assertEqual(spider.source_id, "nongmuhr")
        self.assertEqual(spider.allowed_domains, ["nongmuhr.com"])


if __name__ == "__main__":
    unittest.main()
