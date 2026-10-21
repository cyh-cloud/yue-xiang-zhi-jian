import json
import hashlib
import sqlite3
import tempfile
import unittest
from dataclasses import asdict
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
from crawler.collection.projects.ihchina.ihchina.candidate import (
    write_candidate,
)
from crawler.collection.shared.crawler_collection.database import (
    CollectionDatabase,
)
from crawler.collection.shared.crawler_collection.items import CollectionItem
from crawler.collection.shared.crawler_collection.evidence import RawEvidence
from crawler.collection.shared.crawler_collection.runtime import CollectionRuntime


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

    def test_detail_parser_extracts_inheritors_related_projects_and_media(self):
        html = """
        <div class="article-mod2">
          <div class="t_head"><div class="h30">苗族古歌</div></div>
          <div class="text"><div class="p">
            项目详情正文
            <img src="/uploads/project.jpg">
          </div></div>
        </div>
        <div class="inherit_xx2">
          <div class="x-tables"><table>
            <tr><th>序号</th><th>姓名</th></tr>
            <tr>
              <td>01</td>
              <td><a href="/ccr_detail/716.html">王安江</a></td>
              <td>男</td>
              <td>1935.11</td>
              <td>苗族</td>
              <td>民间文学</td>
              <td>Ⅰ-1</td>
              <td>苗族古歌</td>
              <td>贵州省台江县</td>
            </tr>
          </table></div>
          <div class="x-tables"><table>
            <tr><th>编号</th><th>项目名称</th><th>类型</th><th>地区</th></tr>
            <tr>
              <td>Ⅰ-2</td>
              <td><a href="/project_details/12179.html">相关项目</a></td>
              <td>民间文学</td>
              <td>贵州省</td>
            </tr>
          </table></div>
        </div>
        """
        response = HtmlResponse(
            url="https://www.ihchina.cn/project_details/12178.html",
            body=html.encode("utf-8"),
            encoding="utf-8",
        )

        parsed = parse_project_detail(response)

        self.assertEqual(
            parsed["extra"]["inheritors"],
            [
                {
                    "source_item_id": "716",
                    "name": "王安江",
                    "gender": "男",
                    "birth_date": "1935.11",
                    "ethnicity": "苗族",
                    "category": "民间文学",
                    "ich_code": "Ⅰ-1",
                    "project_name": "苗族古歌",
                    "declaration_region": "贵州省台江县",
                    "source_url": "https://www.ihchina.cn/ccr_detail/716.html",
                }
            ],
        )
        self.assertEqual(
            parsed["extra"]["related_projects"],
            [
                {
                    "source_item_id": "12179",
                    "ich_code": "Ⅰ-2",
                    "name": "相关项目",
                    "category": "民间文学",
                    "declaration_region": "贵州省",
                    "source_url": (
                        "https://www.ihchina.cn/project_details/12179.html"
                    ),
                }
            ],
        )
        self.assertEqual(
            parsed["extra"]["media_links"],
            [
                {
                    "media_url": "https://www.ihchina.cn/uploads/project.jpg",
                    "media_type": "image",
                }
            ],
        )

    def test_detail_parser_skips_relations_without_detail_links(self):
        html = """
        <div class="article-mod2">
          <div class="t_head"><div class="h30">苗族古歌</div></div>
        </div>
        <div class="inherit_xx2">
          <div class="x-tables"><table>
            <tr><th>序号</th><th>姓名</th></tr>
            <tr><td>01</td><td>无链接传承人</td></tr>
          </table></div>
          <div class="x-tables"><table>
            <tr><th>编号</th><th>项目名称</th></tr>
            <tr><td>Ⅰ-2</td><td>无链接项目</td></tr>
          </table></div>
        </div>
        """
        response = HtmlResponse(
            url="https://www.ihchina.cn/project_details/12178.html",
            body=html.encode("utf-8"),
            encoding="utf-8",
        )

        parsed = parse_project_detail(response)

        self.assertEqual(parsed["extra"]["inheritors"], [])
        self.assertEqual(parsed["extra"]["related_projects"], [])

    def test_detail_parser_includes_header_media_and_pop_video(self):
        html = """
        <div class="article-mod2">
          <div class="t_head">
            <div class="h30">苗族古歌</div>
            <img src="/header.jpg">
            <div class="pop-video" data-src="/video.mp4"></div>
          </div>
          <div class="text"><div class="p">正文</div></div>
        </div>
        """
        response = HtmlResponse(
            url="https://www.ihchina.cn/project_details/12178.html",
            body=html.encode("utf-8"),
            encoding="utf-8",
        )

        parsed = parse_project_detail(response)

        self.assertEqual(
            parsed["extra"]["media_links"],
            [
                {
                    "media_url": "https://www.ihchina.cn/header.jpg",
                    "media_type": "image",
                },
                {
                    "media_url": "https://www.ihchina.cn/video.mp4",
                    "media_type": "video",
                },
            ],
        )

    def test_same_inheritor_can_belong_to_two_projects(self):
        with tempfile.TemporaryDirectory() as tmp:
            database_path = Path(tmp) / "crawler.db"
            conn = CollectionDatabase(database_path).connect()
            try:
                for project_id in ("project-1", "project-2"):
                    item = CollectionItem(
                        source_id="ihchina",
                        source_item_id=project_id,
                        source_url=(
                            "https://www.ihchina.cn/project_details/"
                            f"{project_id}.html"
                        ),
                        long_term_url=(
                            "https://www.ihchina.cn/project_details/"
                            f"{project_id}.html"
                        ),
                        detail_url=(
                            "https://www.ihchina.cn/project_details/"
                            f"{project_id}.html"
                        ),
                        detail_url_status="direct",
                        run_id="run-1",
                        mode="fixture",
                        rights_status="attribution-required",
                        title=f"项目 {project_id}",
                        content_hash=f"hash-{project_id}",
                        extra={
                            "inheritors": [
                                {
                                    "source_item_id": "716",
                                    "name": "王安江",
                                    "source_url": (
                                        "https://www.ihchina.cn/"
                                        "ccr_detail/716.html"
                                    ),
                                }
                            ]
                        },
                    )
                    write_candidate(
                        conn,
                        asdict(item),
                        now="2026-10-21T00:00:00Z",
                    )
                count = conn.execute(
                    "SELECT COUNT(*) FROM std_ich_inheritors"
                ).fetchone()[0]
            finally:
                conn.close()

        self.assertEqual(count, 2)

    def test_missing_detail_url_keeps_carrier_and_locator_auditable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_id = "ihchina-missing-detail"
            carrier_url = (
                "https://www.ihchina.cn/project?keywords=%E8%8B%97%E6%97%8F"
            )
            locator = "list row 7"
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
            raw_id = runtime.persist_raw(
                RawEvidence(
                    source_id="ihchina",
                    request_url=carrier_url,
                    final_url=carrier_url,
                    source_url=carrier_url,
                    long_term_url=carrier_url,
                    detail_url=None,
                    detail_url_status="missing",
                    locator=locator,
                    body=b'{"list":[{"id":12178}]}',
                    content_type="application/json",
                    run_id=run_id,
                    robots_decision="allowed",
                )
            )
            item = CollectionItem(
                source_id="ihchina",
                source_item_id="12178",
                source_url=carrier_url,
                long_term_url=carrier_url,
                detail_url=None,
                detail_url_status="missing",
                locator=locator,
                run_id=run_id,
                mode="fixture",
                rights_status="attribution-required",
                title="苗族古歌",
                candidate_status="deferred",
                candidate_reason="detail_url:missing",
            )

            result = runtime.write_item(item, raw_evidence_id=raw_id)

            conn = sqlite3.connect(root / "crawler.db")
            try:
                raw = conn.execute(
                    """
                    SELECT detail_url, detail_url_status, long_term_url, locator
                    FROM raw_fetches
                    """
                ).fetchone()
                stage = conn.execute(
                    """
                    SELECT detail_url, detail_url_status, long_term_url,
                           locator, raw_fetch_id
                    FROM stage_source_items
                    """
                ).fetchone()
                candidate = conn.execute(
                    """
                    SELECT detail_url, detail_url_status, long_term_url,
                           locator, candidate_status, candidate_reason
                    FROM std_ich_projects
                    """
                ).fetchone()
            finally:
                conn.close()

        self.assertEqual(result["candidate_status"], "deferred")
        self.assertEqual(result["candidate_reason"], "detail_url:missing")
        self.assertEqual(
            raw,
            (None, "missing", carrier_url, locator),
        )
        self.assertEqual(
            stage,
            (None, "missing", carrier_url, locator, raw_id),
        )
        self.assertEqual(
            candidate,
            (
                None,
                "missing",
                carrier_url,
                locator,
                "deferred",
                "detail_url:missing",
            ),
        )

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
            conn = sqlite3.connect(root / "crawler.db")
            try:
                raw_count = conn.execute(
                    "SELECT COUNT(*) FROM raw_fetches"
                ).fetchone()[0]
                stage_count = conn.execute(
                    "SELECT COUNT(*) FROM stage_source_items"
                ).fetchone()[0]
                candidate_count = conn.execute(
                    "SELECT COUNT(*) FROM std_ich_projects"
                ).fetchone()[0]
            finally:
                conn.close()

        self.assertEqual(first.status, "succeeded")
        self.assertEqual(second.status, "succeeded")
        self.assertEqual(first.raw_count, 3)
        self.assertEqual(second.raw_count, 3)
        self.assertEqual(first.stage_count, 2)
        self.assertEqual(second.stage_count, 2)
        self.assertEqual(raw_count, 6)
        self.assertEqual(stage_count, 2)
        self.assertEqual(candidate_count, 2)

    def test_fixture_replay_uses_real_scrapy_and_binds_each_response(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = replay_ihchina_fixture(
                fixture_dir=FIXTURE,
                database_path=root / "crawler.db",
                download_root=root / "downloads",
                registry_path=(
                    Path(__file__).resolve().parents[1]
                    / "docs"
                    / "sources.json"
                ),
            )

            conn = sqlite3.connect(root / "crawler.db")
            try:
                raw_rows = conn.execute(
                    """
                    SELECT request_url, body_sha256
                    FROM raw_fetches
                    ORDER BY id
                    """
                ).fetchall()
                stage_rows = conn.execute(
                    """
                    SELECT s.source_item_id, s.detail_url, r.request_url,
                           r.body_sha256
                    FROM stage_source_items AS s
                    JOIN raw_fetches AS r ON r.id = s.raw_fetch_id
                    ORDER BY s.source_item_id
                    """
                ).fetchall()
                candidate_count = conn.execute(
                    "SELECT COUNT(*) FROM std_ich_projects"
                ).fetchone()[0]
            finally:
                conn.close()

        expected = {
            (
                "https://www.ihchina.cn/getProject.html?"
                "category_id=16&limit=10&p=1",
                hashlib.sha256(
                    (FIXTURE / "discover.json").read_bytes()
                ).hexdigest(),
            ),
            (
                "https://www.ihchina.cn/project_details/12178.html",
                hashlib.sha256(
                    (FIXTURE / "detail-12178.html").read_bytes()
                ).hexdigest(),
            ),
            (
                "https://www.ihchina.cn/project_details/12179.html",
                hashlib.sha256(
                    (FIXTURE / "detail-12179.html").read_bytes()
                ).hexdigest(),
            ),
        }
        self.assertEqual(result.status, "succeeded")
        self.assertEqual(result.raw_count, 3)
        self.assertEqual(result.stage_count, 2)
        self.assertEqual(result.candidate_count, 2)
        self.assertEqual(set(raw_rows), expected)
        self.assertEqual(
            stage_rows,
            [
                (
                    "12178",
                    "https://www.ihchina.cn/project_details/12178.html",
                    "https://www.ihchina.cn/project_details/12178.html",
                    hashlib.sha256(
                        (FIXTURE / "detail-12178.html").read_bytes()
                    ).hexdigest(),
                ),
                (
                    "12179",
                    "https://www.ihchina.cn/project_details/12179.html",
                    "https://www.ihchina.cn/project_details/12179.html",
                    hashlib.sha256(
                        (FIXTURE / "detail-12179.html").read_bytes()
                    ).hexdigest(),
                ),
            ],
        )
        self.assertEqual(candidate_count, 2)

    def test_fixture_replay_persists_related_standard_entities(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            kwargs = {
                "fixture_dir": FIXTURE,
                "database_path": root / "crawler.db",
                "download_root": root / "downloads",
                "registry_path": (
                    Path(__file__).resolve().parents[1]
                    / "docs"
                    / "sources.json"
                ),
            }

            first = replay_ihchina_fixture(**kwargs)
            second = replay_ihchina_fixture(**kwargs)

            conn = sqlite3.connect(root / "crawler.db")
            try:
                counts = tuple(
                    conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                    for table in (
                        "std_ich_inheritors",
                        "std_ich_related_items",
                        "std_ich_media_links",
                    )
                )
                inheritor = conn.execute(
                    """
                    SELECT source_item_id, name, gender, birth_date,
                           ethnicity, category, ich_code, project_name,
                           declaration_region, source_url
                    FROM std_ich_inheritors
                    """
                ).fetchone()
                related = conn.execute(
                    """
                    SELECT related_source_item_id, relation_type, source_url
                    FROM std_ich_related_items
                    """
                ).fetchone()
                media = conn.execute(
                    """
                    SELECT media_url, media_type
                    FROM std_ich_media_links
                    """
                ).fetchone()
            finally:
                conn.close()

        self.assertEqual(first.status, "succeeded")
        self.assertEqual(second.status, "succeeded")
        self.assertEqual(counts, (1, 1, 1))
        self.assertEqual(
            inheritor,
            (
                "716",
                "王安江",
                "男",
                "1935.11",
                "苗族",
                "民间文学",
                "Ⅰ-1",
                "苗族古歌",
                "贵州省台江县",
                "https://www.ihchina.cn/ccr_detail/716.html",
            ),
        )
        self.assertEqual(
            related,
            (
                "12179",
                "民间文学",
                "https://www.ihchina.cn/project_details/12179.html",
            ),
        )
        self.assertEqual(
            media,
            (
                "https://www.ihchina.cn/uploads/project.jpg",
                "image",
            ),
        )


if __name__ == "__main__":
    unittest.main()
