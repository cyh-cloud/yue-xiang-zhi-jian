import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from crawler.pipeline.offline_fixture import (
    OfflineFixtureConfig,
    run_offline_fixture,
)


class IhchinaSourceTest(unittest.TestCase):
    def test_fixture_traverses_project_detail_inheritors_and_related_items(self):
        detail_html = """
        <div class="article-mod2">
          <div class="t_head"><div class="h30">苗族古歌</div></div>
          <div class="table">
            <p>项目序号：1</p>
            <p>项目编号：Ⅰ-1</p>
            <p>公布时间：2006(第一批)</p>
            <p>类别：民间文学</p>
            <p>所属地区：贵州省</p>
            <p>类型：新增项目</p>
            <p>申报地区或单位：贵州省台江县</p>
            <p>保护单位：台江县非物质文化遗产保护中心</p>
          </div>
          <div class="text"><div class="p">
            项目详情正文
            <img src="/uploads/project.jpg">
          </div></div>
        </div>
        <div class="inherit_xx2">
          <div class="x-tables"><table>
            <tr><th>序号</th><th>姓名</th><th>性别</th></tr>
            <tr><td>01</td><td><a href="/ccr_detail/716.html">王安江</a></td><td>男</td></tr>
          </table></div>
          <div class="x-tables"><table>
            <tr><th>编号</th><th>项目名称</th><th>类型</th><th>申报地区</th></tr>
            <tr><td>Ⅰ-1</td><td><a href="/project_details/12179.html">相关项目</a></td><td>民间文学</td><td>贵州省</td></tr>
          </table></div>
          <div class="list">
            <div class="title">相关资讯</div>
            <a class="list-link" href="/project_details/28021.html">
              <span class="date">2023.06.25</span>
              <span class="p">相关资讯标题</span>
            </a>
          </div>
        </div>
        """
        inheritor_html = """
        <div class="article-mod2">
          <div class="t_head"><div class="h30">王安江</div></div>
          <div class="table">
            <p>序号：01-0001</p>
            <p>性别：男</p>
            <p>民族：苗族</p>
            <p>项目名称：苗族古歌</p>
          </div>
          <div class="text"><div class="p">传承人生平与技艺说明</div></div>
        </div>
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = root / "ihchina"
            fixture.mkdir()
            (fixture / "discover.json").write_text(
                json.dumps(
                    {
                        "pages": [
                            {
                                "total": 1,
                                "count": 1,
                                "p": 1,
                                "list": [
                                    {
                                        "id": 12178,
                                        "title": "苗族古歌",
                                        "num": "Ⅰ-1",
                                    }
                                ],
                            }
                        ],
                        "details": {
                            "12178": {
                                "html": detail_html,
                                "inheritors": {"716": inheritor_html},
                            }
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            config = OfflineFixtureConfig(
                database_path=root / "crawler.db",
                download_root=root / "download",
                fixture_root=fixture,
            )

            result = run_offline_fixture("ihchina", "fixture", config)

            self.assertEqual(result.status, "succeeded")
            self.assertEqual(result.discovered_count, 1)
            self.assertEqual(result.fetched_count, 3)
            conn = sqlite3.connect(config.database_path)
            try:
                stage = conn.execute(
                    "SELECT extra FROM stage_source_items"
                ).fetchone()
                project = conn.execute(
                    "SELECT name, description_text FROM std_ich_projects"
                ).fetchone()
                fetches = conn.execute(
                    "SELECT request_url FROM raw_fetches ORDER BY id"
                ).fetchall()
            finally:
                conn.close()
            extra = json.loads(stage[0])
            self.assertEqual(extra["detail"]["inheritors"][0]["name"], "王安江")
            self.assertEqual(
                extra["detail"]["inheritors"][0]["biography_text"],
                "传承人生平与技艺说明",
            )
            self.assertEqual(
                extra["detail"]["related_projects"][0]["source_item_id"],
                "12179",
            )
            self.assertEqual(
                extra["detail"]["related_articles"][0]["title"],
                "相关资讯标题",
            )
            self.assertEqual(
                extra["detail"]["media_links"][0]["media_url"],
                "https://www.ihchina.cn/uploads/project.jpg",
            )
            self.assertEqual(project[0], "苗族古歌")
            self.assertIn("项目详情正文", project[1])
            self.assertIn(
                ("https://www.ihchina.cn/ccr_detail/716.html",),
                fetches,
            )

    def test_discover_and_project_to_std_from_fixture(self):
        item = {
            "id": 12178,
            "title": "苗族古歌",
            "auto_id": 1,
            "num": "Ⅰ-1",
            "project_num": "Ⅰ-001_01_522630",
            "type": "民间文学",
            "cate": "新增项目",
            "rx_time": "2006</br>(第一批)",
            "province": "贵州省台江县",
            "city": "522600",
            "area": "522630",
            "address": "520000",
            "unit": "贵州省台江县",
            "protect_unit": "台江县非物质文化遗产保护中心",
            "content": "申报地区或单位：贵州省台江县 &lt;br /&gt;正文",
            "modified": 1544782620,
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = root / "ihchina"
            fixture.mkdir()
            (fixture / "discover.json").write_text(
                json.dumps({"total": 3610, "count": 3610, "p": 1, "list": [item]}, ensure_ascii=False),
                encoding="utf-8",
            )
            config = OfflineFixtureConfig(
                database_path=root / "crawler.db",
                download_root=root / "download",
                fixture_root=fixture,
            )

            result = run_offline_fixture("ihchina", "fixture", config)

            self.assertEqual(result.status, "succeeded")
            self.assertEqual(result.discovered_count, 1)
            self.assertEqual(result.written_count, 1)
            conn = sqlite3.connect(config.database_path)
            try:
                project = conn.execute(
                    "SELECT name, ich_code, declaration_region, description_text, source_url, long_term_url FROM std_ich_projects"
                ).fetchone()
                raw = conn.execute("SELECT request_url FROM raw_fetches").fetchone()
            finally:
                conn.close()
            self.assertEqual(project[0], "苗族古歌")
            self.assertEqual(project[1], "Ⅰ-1")
            self.assertEqual(project[2], "贵州省台江县")
            self.assertNotIn("<", project[3])
            self.assertIn("getProject.html", project[4])
            self.assertIn("p=1", project[4])
            self.assertEqual(
                project[5],
                "https://www.ihchina.cn/project_details/12178.html",
            )
            self.assertIn("category_id=16", raw[0])
    def test_total_and_unique_ids_are_checked_from_saved_list_pages(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = root / "ihchina"
            fixture.mkdir()
            page1 = {
                "total": 3,
                "count": 3,
                "p": 1,
                "links": {"total_pages": 2},
                "list": [
                    {"id": 1, "title": "A", "num": "Ⅰ-1"},
                    {"id": 2, "title": "B", "num": "Ⅰ-2"},
                ],
            }
            page2 = {
                "total": 3,
                "count": 3,
                "p": 2,
                "links": {"total_pages": 2},
                "list": [{"id": 2, "title": "B duplicate", "num": "Ⅰ-2"}],
            }
            (fixture / "discover.json").write_text(
                json.dumps({"pages": [page1, page2]}, ensure_ascii=False),
                encoding="utf-8",
            )
            config = OfflineFixtureConfig(
                database_path=root / "crawler.db",
                download_root=root / "download",
                fixture_root=fixture,
            )

            result = run_offline_fixture("ihchina", "fixture", config)

            self.assertEqual(result.status, "succeeded")
            self.assertEqual(result.discovered_count, 2)
            self.assertEqual(result.written_count, 2)

    def test_live_mode_is_explicit_and_rejects_unknown_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = OfflineFixtureConfig(
                database_path=root / "crawler.db",
                download_root=root / "download",
                fixture_root=root / "fixture",
            )
            with self.assertRaises(ValueError):
                run_offline_fixture("unknown-source", "live", config)
