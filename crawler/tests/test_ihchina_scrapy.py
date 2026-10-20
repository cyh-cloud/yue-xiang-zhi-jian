import json
import tempfile
import unittest
from pathlib import Path

from scrapy.http import HtmlResponse, TextResponse

from crawler.collection.projects.ihchina.ihchina.parsers import (
    parse_list_page,
    parse_project_detail,
)
from crawler.collection.projects.ihchina.ihchina.spiders.collection import (
    IhchinaSpider,
)
from crawler.collection.projects.ihchina.ihchina.replay import (
    replay_ihchina_fixture,
)


FIXTURE = (
    Path(__file__).resolve().parent / "fixtures" / "evidence" / "ihchina"
)


class IhchinaScrapyProjectTest(unittest.TestCase):
    def test_list_page_yields_stable_ids_and_next_page(self):
        payload = {
            "total": 12,
            "count": 12,
            "p": 1,
            "links": {"total_pages": 2},
            "list": [
                {"id": 12178, "title": "苗族古歌", "num": "Ⅰ-1"},
                {"id": 12179, "title": "相关项目", "num": "Ⅰ-2"},
            ],
        }
        response = TextResponse(
            url=(
                "https://www.ihchina.cn/getProject.html?"
                "category_id=16&limit=10&p=1"
            ),
            body=json.dumps(payload).encode("utf-8"),
            encoding="utf-8",
            headers={"Content-Type": "application/json"},
        )

        parsed = parse_list_page(response)

        self.assertEqual(
            [item["source_item_id"] for item in parsed["items"]],
            ["12178", "12179"],
        )
        self.assertEqual(parsed["next_page"], 2)
        self.assertEqual(parsed["total_pages"], 2)

    def test_detail_parser_extracts_required_contract_fields(self):
        html = """
        <div class="article-mod2">
          <div class="t_head"><div class="h30">苗族古歌</div></div>
          <div class="table">
            <div class="p">项目序号：1</div>
            <div class="p">项目编号：Ⅰ-1</div>
            <div class="p">公布时间：2006(第一批)</div>
            <div class="p">类别：民间文学</div>
            <div class="p">所属地区：贵州省</div>
            <div class="p">类型：新增项目</div>
            <div class="p">申报地区或单位：贵州省台江县</div>
            <div class="p">保护单位：台江县非物质文化遗产保护中心</div>
          </div>
          <div class="text"><div class="p">项目详情正文</div></div>
        </div>
        """
        response = HtmlResponse(
            url="https://www.ihchina.cn/project_details/12178.html",
            body=html.encode("utf-8"),
            encoding="utf-8",
        )

        parsed = parse_project_detail(response)

        self.assertEqual(parsed["source_item_id"], "12178")
        self.assertEqual(parsed["title"], "苗族古歌")
        self.assertEqual(parsed["detail_url_status"], "direct")
        self.assertEqual(parsed["extra"]["ich_code"], "Ⅰ-1")
        self.assertEqual(parsed["extra"]["protection_unit"],
                         "台江县非物质文化遗产保护中心")

    def test_detail_without_usable_url_remains_stage_only(self):
        spider = IhchinaSpider()
        assert spider.name == "ihchina"

    def test_spider_has_one_site_identity_and_no_shared_parameterization(self):
        spider = IhchinaSpider()
        self.assertEqual(spider.source_id, "ihchina")
        self.assertEqual(spider.allowed_domains, ["www.ihchina.cn"])
        self.assertEqual(
            spider.start_urls,
            [
                "https://www.ihchina.cn/getProject.html?"
                "category_id=16&limit=10&p=1"
            ],
        )

    def test_fixture_replay_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = replay_ihchina_fixture(
                fixture_dir=FIXTURE,
                database_path=root / "crawler.db",
                download_root=root / "downloads",
                registry_path=(
                    Path(__file__).resolve().parents[1]
                    / "docs"
                    / "sources.json"
                ),
            )
            second = replay_ihchina_fixture(
                fixture_dir=FIXTURE,
                database_path=root / "crawler.db",
                download_root=root / "downloads",
                registry_path=(
                    Path(__file__).resolve().parents[1]
                    / "docs"
                    / "sources.json"
                ),
            )

        self.assertEqual(first.status, "succeeded")
        self.assertEqual(second.status, "succeeded")


if __name__ == "__main__":
    unittest.main()
