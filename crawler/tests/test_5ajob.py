import json
import tempfile
import unittest
from pathlib import Path

from crawler.pipeline.offline_fixture import (
    OfflineFixtureConfig,
    run_offline_fixture,
)
from crawler.pipeline.sources import fiveajob


class FiveAJobSourceTest(unittest.TestCase):
    def test_list_fixture_can_parse_saved_detail_html(self):
        detail_html = """
        <div id="zhtitle">某农业服务组织</div>
        <div id="rjobid">50506</div>
        <div id="jobdetail">
          <h1>农业技术推广员</h1>
          <table>
            <tr><th>工作地点</th><td>广东省广州市</td></tr>
            <tr><th>月薪</th><td>6000-8000元</td></tr>
            <tr><th>学历要求</th><td>本科</td></tr>
            <tr><th>岗位描述</th><td>负责田间农技推广和植保巡查。</td></tr>
            <tr><th>应聘要求</th><td>农学相关专业。</td></tr>
          </table>
        </div>
        <div id="jobexpire">2026年05月25日至2026年11月21日</div>
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = root / "5ajob"
            fixture.mkdir()
            (fixture / "discover.json").write_text(
                json.dumps(
                    {
                        "pages": [
                            {
                                "page": 1,
                                "items": [
                                    {
                                        "job_id": "50506",
                                        "url": "http://www.5ajob.com/c-d-abc123-h/50506.html",
                                        "title": "农业技术推广员",
                                        "detail_html": detail_html,
                                    }
                                ],
                                "is_last": True,
                            }
                        ]
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

            discovered = fiveajob.discover(config)

            item = discovered["items"][0]
            self.assertEqual(item["company_name"], "某农业服务组织")
            self.assertEqual(item["location_raw"], "广东省广州市")
            self.assertEqual(item["salary_raw"], "6000-8000元")
            self.assertEqual(item["education_raw"], "本科")
            self.assertIn("田间农技推广", item["description"])
            self.assertEqual(item["requirements"], "农学相关专业。")
            self.assertEqual(
                item["deadline_at"],
                "2026年05月25日至2026年11月21日",
            )

    def test_prohibited_source_is_rejected_before_discovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = OfflineFixtureConfig(
                database_path=root / "crawler.db",
                download_root=root / "download",
                fixture_root=root / "missing-fixture",
            )

            result = run_offline_fixture("5ajob", "list-fixture", config)

            self.assertEqual(result.status, "blocked")
            self.assertEqual(result.discovered_count, 0)
            self.assertFalse(config.database_path.exists())

    def test_empty_company_hash_detail_url_is_canonicalized(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = root / "5ajob"
            fixture.mkdir()
            (fixture / "discover.json").write_text(
                json.dumps(
                    {
                        "pages": [
                            {
                                "page": 1,
                                "items": [
                                    {
                                        "job_id": "50690",
                                        "url": "http://www.5ajob.com/companyinfo/detail//htmljob/50690.html",
                                        "title": "农业技术推广员",
                                        "company_name": "某农业服务组织",
                                    }
                                ],
                                "is_last": True,
                            }
                        ]
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

            discovered = fiveajob.discover(config)
            self.assertEqual(len(discovered["items"]), 1)
            row = discovered["items"][0]
            self.assertEqual(
                row["source_url"],
                "http://www.5ajob.com/companyinfo/detail/htmljob/50690.html",
            )
            self.assertEqual(row["long_term_url"], row["source_url"])
            self.assertEqual(row["detail_url"], row["source_url"])

    def test_list_fixture_deduplicates_stops_on_no_new_ids_and_filters_jobs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = root / "5ajob"
            fixture.mkdir()
            pages = {
                "pages": [
                    {
                        "page": 1,
                        "items": [
                            {
                                "job_id": "50506",
                                "url": "http://www.5ajob.com/c-d-abc123-h/50506.html",
                                "title": "肥料区域经理-安徽",
                                "company_name": "时科生物科技（上海）有限公司",
                                "industry": "肥料",
                                "description": "负责区域肥料销售与农化服务",
                            },
                            {
                                "job_id": "50687",
                                "url": "http://www.5ajob.com/companyinfo/detail/7411bc9cc6dadd45/htmljob/50687.html",
                                "title": "前台接待",
                                "company_name": "金华市喆农商贸有限公司",
                                "industry": "商贸",
                                "description": "负责访客登记和电话转接",
                            },
                        ],
                    },
                    {
                        "page": 2,
                        "items": [
                            {
                                "job_id": "50506",
                                "url": "https://www.5ajob.com/c-d-abc123-h/50506.html#apply",
                                "title": "肥料区域经理-安徽",
                                "company_name": "时科生物科技（上海）有限公司",
                                "industry": "肥料",
                                "description": "负责区域肥料销售与农化服务",
                            }
                        ],
                    },
                    {
                        "page": 3,
                        "items": [
                            {
                                "job_id": "50688",
                                "url": "http://www.5ajob.com/companyinfo/detail/2d90e70b22e22eee/htmljob/50688.html",
                                "title": "农作物种植技术员",
                                "company_name": "山东省祥盛种业科技有限责任公司",
                                "industry": "农作物",
                                "description": "负责田间植保巡查和技术指导",
                            }
                        ],
                    },
                ]
            }
            (fixture / "discover.json").write_text(
                json.dumps(pages, ensure_ascii=False),
                encoding="utf-8",
            )
            config = OfflineFixtureConfig(
                database_path=root / "crawler.db",
                download_root=root / "download",
                fixture_root=fixture,
            )

            discovered = fiveajob.discover(config)

            self.assertEqual(len(discovered["items"]), 1)
            row = discovered["items"][0]
            self.assertEqual(row["source_item_id"], "50506")
            self.assertEqual(
                row["source_url"],
                "http://www.5ajob.com/c-d-abc123-h/50506.html",
            )
            self.assertEqual(row["long_term_url"], row["source_url"])
            self.assertEqual(row["detail_url"], row["source_url"])
            self.assertEqual(row["detail_url_status"], "direct")
            self.assertEqual(row["title"], "肥料区域经理-安徽")
            self.assertEqual(row["rights_status"], "prohibited")
            extra = row["extra"]
            relevance = extra["agriculture_relevance"]
            self.assertTrue(relevance["is_related"])
            self.assertIn("title", relevance["matched_fields"])
            self.assertIn("industry", relevance["matched_fields"])
            self.assertEqual(
                extra["discovery"]["stopped_reason"],
                "no_new_ids",
            )
            self.assertEqual(
                extra["discovery"]["excluded"][0]["source_item_id"],
                "50687",
            )
            self.assertEqual(extra["discovery"]["processed_pages"], [1, 2])


if __name__ == "__main__":
    unittest.main()
