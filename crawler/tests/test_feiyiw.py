import unittest

from crawler.pipeline.sources.feiyiw import (
    article_id_from_url,
    parse_article_detail,
    parse_article_list,
)


LIST_URL = "https://www.feiyiw.cn/index.php?app=article&cate_id=4"
DETAIL_URL = "https://www.feiyiw.cn/index.php?app=article&act=view&article_id=70177"


class FeiyiwSourceTest(unittest.TestCase):
    def test_public_detail_becomes_traceable_supplementary_record(self):
        html = """
        <html><body>
          <div id="page-article">
            <div class="col-main">
              <div class="title"><div class="location">非遗大数据</div></div>
              <div class="article-info">
                <h1>【传统美术】朝阳县烙画（朝阳市）传承人：闫海秋</h1>
                <h2>2026-10-16 15:56</h2>
              </div>
              <div class="article-detail">
                <p>【项目名称】朝阳县烙画</p>
                <p>【项目类别】传统美术</p>
                <p>【项目地区】辽宁省朝阳市朝阳县</p>
                <p>【项目级别】市级</p>
                <p>【项目批准时间】2021年</p>
                <p>【传承人简介】闫海秋，长期从事烙画创作。</p>
              </div>
            </div>
          </div>
        </body></html>
        """

        record = parse_article_detail(html, DETAIL_URL)

        self.assertEqual(record["source_id"], "feiyiw")
        self.assertEqual(record["source_item_id"], "70177")
        self.assertEqual(record["article_id"], "70177")
        self.assertEqual(record["source_url"], DETAIL_URL)
        self.assertEqual(record["long_term_url"], DETAIL_URL)
        self.assertEqual(record["detail_url"], DETAIL_URL)
        self.assertEqual(record["detail_url_status"], "direct")
        self.assertEqual(record["rights_status"], "attribution-required")
        self.assertEqual(record["attribution_text"], "外研非遗网（www.feiyiw.cn）")
        self.assertIn("rights_risk", record["extra"])
        self.assertIn("title", record)
        self.assertEqual(record["title"], "【传统美术】朝阳县烙画（朝阳市）传承人：闫海秋")
        self.assertEqual(record["published_at"], "2026-10-16 15:56")
        self.assertEqual(record["category_name"], "非遗大数据")
        self.assertEqual(
            record["extra"]["supplementary"],
            {
                "project_name": "朝阳县烙画",
                "ich_category": "传统美术",
                "region_text": "辽宁省朝阳市朝阳县",
                "level_text": "市级",
                "approval_text": "2021年",
                "inheritor_text": "闫海秋，长期从事烙画创作。",
            },
        )
        self.assertNotIn("std_ich_projects", record)

    def test_article_id_is_taken_from_long_term_detail_url(self):
        self.assertEqual(article_id_from_url(DETAIL_URL), "70177")
        self.assertIsNone(article_id_from_url("https://www.feiyiw.cn/"))

    def test_public_list_discovers_canonical_articles_without_member_links(self):
        html = """
        <html><body><div id="page-article"><div class="col-main">
          <ul class="content">
            <li>
              <a class="lebioa" href="/index.php?app=article&amp;act=view&amp;article_id=70177">【传统美术】朝阳县烙画</a>
              <span>2026.10.16</span>
            </li>
            <li>
              <a class="lebioa" href="/index.php?app=article&amp;act=view&amp;article_id=70177">【传统美术】朝阳县烙画</a>
              <span>2026.10.16</span>
            </li>
            <li><a href="/index.php?app=member&amp;act=login">会员登录</a></li>
            <li><a href="/index.php?app=shop&amp;act=buy&amp;article_id=70177">购买</a></li>
          </ul>
          <div class="page"><div class="total">共1176页</div></div>
        </div></div></body></html>
        """

        result = parse_article_list(html, LIST_URL)

        self.assertEqual(result["page_count"], 1176)
        self.assertEqual(result["next_page"], None)
        self.assertEqual(len(result["items"]), 1)
        item = result["items"][0]
        self.assertEqual(item["article_id"], "70177")
        self.assertEqual(item["source_item_id"], "70177")
        self.assertEqual(item["title"], "【传统美术】朝阳县烙画")
        self.assertEqual(item["list_date"], "2026.10.16")
        self.assertEqual(item["source_url"], "https://www.feiyiw.cn/index.php?app=article&cate_id=4")
        self.assertEqual(item["long_term_url"], DETAIL_URL)
        self.assertEqual(item["detail_url"], DETAIL_URL)
        self.assertEqual(item["detail_url_status"], "direct")
        self.assertEqual(item["rights_status"], "attribution-required")
        self.assertIn("rights_risk", item["extra"])

    def test_non_public_or_member_page_does_not_become_an_article(self):
        html = """
        <html><body><div id="page-article"><div class="col-main">
          <div class="article-info"><h1>会员中心</h1></div>
          <div class="member-content">登录后查看购买记录</div>
        </div></div></body></html>
        """

        with self.assertRaises(ValueError):
            parse_article_detail(
                html,
                "https://www.feiyiw.cn/index.php?app=member&act=login",
            )

    def test_member_and_shop_urls_are_rejected_even_with_article_id(self):
        html = """
        <html><body><div id="page-article"><div class="col-main">
          <div class="article-info"><h1>【传统美术】朝阳县烙画</h1></div>
          <div class="article-detail"><p>【项目名称】朝阳县烙画</p></div>
        </div></div></body></html>
        """

        for url in (
            "https://www.feiyiw.cn/index.php?app=member&act=view&article_id=70177",
            "https://www.feiyiw.cn/index.php?app=shop&act=buy&article_id=70177",
        ):
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    parse_article_detail(html, url)

    def test_article_detail_rejects_a_blank_body(self):
        html = """
        <html><body><div id="page-article"><div class="col-main">
          <div class="article-info">
            <h1>【传统美术】朝阳县烙画</h1>
            <h2>2026-10-16 15:56</h2>
          </div>
          <div class="article-detail"> </div>
        </div></div></body></html>
        """

        with self.assertRaises(ValueError):
            parse_article_detail(html, DETAIL_URL)

    def test_fixture_runner_writes_raw_stage_and_research_article(self):
        import json
        import sqlite3
        import tempfile
        from pathlib import Path

        from crawler.pipeline import RunConfig, run_source

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = root / "feiyiw"
            fixture.mkdir()
            detail_html = """
            <html><body><div id="page-article"><div class="col-main">
              <div class="title"><div class="location">非遗大数据</div></div>
              <div class="article-info"><h1>【传统美术】朝阳县烙画</h1><h2>2026-10-16 15:56</h2></div>
              <div class="article-detail"><p>【项目名称】朝阳县烙画</p><p>【项目类别】传统美术</p></div>
            </div></div></body></html>
            """
            (fixture / "discover.json").write_text(json.dumps({
                "items": [{"source_item_id": "70177", "detail_html": detail_html, "fetched_url": DETAIL_URL}]
            }, ensure_ascii=False), encoding="utf-8")
            config = RunConfig(database_path=root / "crawler.db", download_root=root / "download", fixture_root=fixture)
            result = run_source("feiyiw", "fixture", config)
            self.assertEqual(result.status, "succeeded")
            self.assertEqual(result.written_count, 1)
            conn = sqlite3.connect(config.database_path)
            try:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM raw_fetches").fetchone()[0], 1)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM stage_fixture_items").fetchone()[0], 1)
                row = conn.execute("SELECT source_id, source_item_id, long_term_url FROM std_ich_articles").fetchone()
            finally:
                conn.close()
            self.assertEqual(row[0], "feiyiw")
            self.assertEqual(row[1], "70177")
            self.assertEqual(row[2], DETAIL_URL)
