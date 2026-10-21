import io
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from openpyxl import Workbook
from scrapy.http import HtmlResponse, Request, Response

from crawler.collection.shared.crawler_collection.middlewares import (
    RawEvidenceMiddleware,
)
from crawler.collection.shared.crawler_collection.registry import (
    load_registry,
)


ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT / "collection" / "projects" / "aqsc-moa"
FIXTURE = ROOT / "tests" / "fixtures" / "evidence" / "aqsc-moa"
REGISTRY = ROOT / "docs" / "sources.json"
sys.path.insert(0, str(PROJECT_ROOT))

from aqsc_moa import live as live_module
from aqsc_moa.parsers import (  # noqa: E402
    parse_embedded_rows,
    parse_xlsx_rows,
)
from aqsc_moa.replay import replay_aqsc_fixture  # noqa: E402
from aqsc_moa.spiders.collection import AqscMoaSpider  # noqa: E402


class AqscMoaScrapyTest(unittest.TestCase):
    def test_live_canary_requires_explicit_start_urls_before_crawl(self):
        for start_urls in (None, [], ("",)):
            with self.subTest(start_urls=start_urls):
                with mock.patch.object(
                    live_module, "CrawlerProcess"
                ) as process:
                    with self.assertRaisesRegex(
                        ValueError, "explicit start URL"
                    ):
                        live_module.run_live_sample(
                            database_path=Path("unused.db"),
                            download_root=Path("unused-download"),
                            registry_path=REGISTRY,
                            report_root=Path("unused-reports"),
                            start_urls=start_urls,
                        )
                    process.assert_not_called()

    @staticmethod
    def _workbook_bytes(rows):
        workbook = Workbook()
        sheet = workbook.active
        sheet.append(
            [
                "序号",
                "省份",
                "县域",
                "证书编号",
                "产品名称",
                "获证单位",
            ]
        )
        for row in rows:
            sheet.append(row)
        body = io.BytesIO()
        workbook.save(body)
        workbook.close()
        return body.getvalue()

    def test_spider_is_live_enabled_with_explicit_start_urls(self):
        spider = AqscMoaSpider()
        self.assertEqual(spider.name, "aqsc-moa")
        self.assertEqual(spider.source_id, "aqsc-moa")
        self.assertTrue(spider.live_enabled)
        self.assertEqual(spider.start_urls, [])
        self.assertEqual(spider.max_download_bytes, 100 * 1024 * 1024)
        self.assertEqual(
            spider.allowed_domains,
            load_registry(REGISTRY)["aqsc-moa"]["domains"],
        )

    def test_xlsx_parser_keeps_sheet_and_row_locators(self):
        payload = json.loads(
            (FIXTURE / "discover.json").read_text(encoding="utf-8")
        )
        rows = []
        for item in payload["items"]:
            path = FIXTURE / item["file_name"]
            rows.extend(
                parse_xlsx_rows(
                    path.read_bytes(),
                    file_name=path.name,
                    metadata=item,
                )
            )

        self.assertEqual(len(rows), 8)
        self.assertEqual(
            rows[0]["locator"], "sheet=Sheet1; row=3; seq=1"
        )
        self.assertEqual(rows[0]["extra"]["cert_type"], "mingteyouxin")
        self.assertEqual(rows[4]["extra"]["cert_type"], "tezhi_nongpin")
        self.assertTrue(all(row["detail_url"] is None for row in rows))
        self.assertTrue(
            all(row["detail_url_status"] == "missing" for row in rows)
        )

    def test_xlsx_natural_keys_survive_row_reordering(self):
        rows = [
            [1, "甲省", "甲县", "CERT-2", "产品乙", "单位乙"],
            [2, "甲省", "甲县", "CERT-1", "产品甲", "单位甲"],
        ]
        metadata = {
            "announcement_id": "100",
            "batch": "2026年第一批",
        }

        first = parse_xlsx_rows(
            self._workbook_bytes(rows),
            file_name="first.xlsx",
            metadata=metadata,
        )
        second = parse_xlsx_rows(
            self._workbook_bytes(list(reversed(rows))),
            file_name="second.xlsx",
            metadata=metadata,
        )

        self.assertEqual(
            {row["source_item_id"]: row["title"] for row in first},
            {row["source_item_id"]: row["title"] for row in second},
        )
        self.assertTrue(
            all(
                row["source_item_id"].startswith("01:certificate=")
                for row in first
            )
        )
        self.assertIn("sheet=Sheet; row=", first[0]["locator"])

    def test_xlsx_without_certificate_uses_batch_and_subject_key(self):
        rows = [
            [1, "甲省", "甲县", None, "产品乙", "单位乙"],
            [2, "甲省", "甲县", None, "产品甲", "单位甲"],
        ]
        metadata = {
            "announcement_id": "101",
            "batch": "2026年第二批",
        }

        first = parse_xlsx_rows(
            self._workbook_bytes(rows),
            file_name="first.xlsx",
            metadata=metadata,
        )
        second = parse_xlsx_rows(
            self._workbook_bytes(list(reversed(rows))),
            file_name="second.xlsx",
            metadata=metadata,
        )

        self.assertEqual(
            {row["source_item_id"]: row["title"] for row in first},
            {row["source_item_id"]: row["title"] for row in second},
        )
        self.assertTrue(
            all(
                row["source_item_id"].startswith(
                    "02:batch=2026年第二批|product="
                )
                for row in first
            )
        )

    def test_embedded_details_table_uses_real_structure_and_deduplicates(self):
        html = (FIXTURE / "details-con-embedded.html").read_text(
            encoding="utf-8"
        )
        duplicated = html.replace(
            "</table>",
            (
                "<tr><td>9</td><td>示例省</td><td>示例县</td>"
                "<td>SYN-EMB-001</td><td>示例内嵌产品甲</td>"
                "<td>示例单位</td></tr></table>"
            ),
            1,
        )

        rows = parse_embedded_rows(
            duplicated,
            page_url=(
                "http://www.aqsc.agri.cn/tzgg/202609/"
                "t20260920_474564.htm"
            ),
            metadata={
                "announcement_id": "474564",
                "announcement_no": "第44号",
                "batch": "2026年第二批",
                "cert_type": "mingteyouxin",
                "source_url": (
                    "http://www.aqsc.agri.cn/tzgg/202609/"
                    "t20260920_474564.htm"
                ),
                "long_term_url": (
                    "http://www.aqsc.agri.cn/tzgg/202609/"
                    "t20260920_474564.htm"
                ),
            },
        )

        self.assertEqual(len(rows), 2)
        self.assertEqual(
            rows[0]["locator"], "table=1; row=3; seq=1"
        )
        self.assertEqual(rows[0]["title"], "示例内嵌产品甲")
        self.assertEqual(rows[0]["extra"]["source_kind"], "embedded_html")
        self.assertEqual(
            rows[0]["source_item_id"],
            "01:certificate=SYN-EMB-001",
        )

    def test_embedded_table_replays_through_project_spider(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = replay_aqsc_fixture(
                fixture_dir=FIXTURE,
                database_path=root / "crawler.db",
                download_root=root / "download",
                registry_path=REGISTRY,
                run_id="aqsc-embedded-test",
                manifest_name="embedded.json",
            )
            conn = sqlite3.connect(root / "crawler.db")
            try:
                stage_count = conn.execute(
                    "SELECT COUNT(*) FROM stage_source_items"
                ).fetchone()[0]
                candidate_count = conn.execute(
                    "SELECT COUNT(*) FROM std_agri_products"
                ).fetchone()[0]
                extra = json.loads(
                    conn.execute(
                        "SELECT extra FROM stage_source_items "
                        "ORDER BY id LIMIT 1"
                    ).fetchone()[0]
                )
            finally:
                conn.close()

        self.assertEqual(result.stage_count, 2)
        self.assertEqual(result.deferred, 2)
        self.assertEqual(stage_count, 2)
        self.assertEqual(candidate_count, 2)
        self.assertEqual(extra["source_kind"], "embedded_html")

    def test_attachment_takes_priority_over_embedded_table(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = replay_aqsc_fixture(
                fixture_dir=FIXTURE,
                database_path=root / "crawler.db",
                download_root=root / "download",
                registry_path=REGISTRY,
                run_id="aqsc-priority-test",
                manifest_name="priority.json",
            )
            conn = sqlite3.connect(root / "crawler.db")
            try:
                extras = [
                    json.loads(row[0])
                    for row in conn.execute(
                        "SELECT extra FROM stage_source_items"
                    )
                ]
            finally:
                conn.close()

        self.assertEqual(result.stage_count, 4)
        self.assertTrue(extras)
        self.assertTrue(
            all(extra["source_kind"] == "xlsx" for extra in extras)
        )

    def test_xls_attachment_is_blocked_as_unsupported(self):
        request = Request(
            "http://www.aqsc.agri.cn/file.xls",
            meta={"file_name": "file.xls"},
        )
        response = Response(
            request.url,
            body=b"legacy-xls",
            headers={"Content-Type": "application/vnd.ms-excel"},
            request=request,
        )

        item = next(AqscMoaSpider().parse_file(response))

        self.assertEqual(item.candidate_status, "blocked")
        self.assertEqual(
            item.candidate_reason,
            "file:unsupported_extension:.xls",
        )

    def test_disallowed_detail_and_attachment_links_are_blocked(self):
        spider = AqscMoaSpider()
        detail_request = Request(
            "http://www.aqsc.agri.cn/tzgg/202609/detail.htm"
        )
        detail_response = HtmlResponse(
            detail_request.url,
            body=(
                "<html><body><div class='Details_con'>"
                "<a href='https://evil.example/www.aqsc.agri.cn/"
                "detail.htm'>x</a>"
                "</div></body></html>"
            ).encode("utf-8"),
            encoding="utf-8",
            request=detail_request,
        )
        attachment_request = Request(
            "http://www.aqsc.agri.cn/tzgg/202609/detail.htm"
        )
        attachment_response = HtmlResponse(
            attachment_request.url,
            body=(
                "<html><body><div class='Details_con'>"
                "<a href='https://evil.example/file.xlsx'>x</a>"
                "</div></body></html>"
            ).encode("utf-8"),
            encoding="utf-8",
            request=attachment_request,
        )

        detail_item = next(spider.parse_carrier(detail_response))
        attachment_item = next(
            spider.parse_carrier(attachment_response)
        )

        self.assertEqual(detail_item.candidate_status, "blocked")
        self.assertIn("url:domain_not_allowed", detail_item.candidate_reason)
        self.assertEqual(attachment_item.candidate_status, "blocked")
        self.assertIn(
            "url:domain_not_allowed", attachment_item.candidate_reason
        )

    def test_fixture_replay_uses_spider_middleware_and_pipeline(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = replay_aqsc_fixture(
                fixture_dir=FIXTURE,
                database_path=root / "crawler.db",
                download_root=root / "download",
                registry_path=REGISTRY,
                run_id="aqsc-fixture-test",
            )
            conn = sqlite3.connect(root / "crawler.db")
            try:
                raw_count = conn.execute(
                    "SELECT COUNT(*) FROM raw_fetches"
                ).fetchone()[0]
                raw_file_count = conn.execute(
                    "SELECT COUNT(*) FROM raw_files "
                    "WHERE file_ext IN ('.xlsx', '.pdf')"
                ).fetchone()[0]
                stage_count = conn.execute(
                    "SELECT COUNT(*) FROM stage_source_items"
                ).fetchone()[0]
                rows = conn.execute(
                    "SELECT locator, detail_url, detail_url_status, "
                    "source_url, long_term_url, candidate_status, "
                    "candidate_reason FROM std_agri_products "
                    "ORDER BY source_item_id"
                ).fetchall()
            finally:
                conn.close()

        self.assertEqual(result.mode, "fixture")
        self.assertEqual(result.raw_count, 5)
        self.assertEqual(result.stage_count, 8)
        self.assertEqual(result.written, 0)
        self.assertEqual(result.deferred, 8)
        self.assertEqual(raw_count, 5)
        self.assertEqual(raw_file_count, 2)
        self.assertEqual(stage_count, 8)
        self.assertEqual(len(rows), 8)
        for row in rows:
            self.assertIn("sheet=Sheet1; row=", row[0])
            self.assertIsNone(row[1])
            self.assertEqual(row[2], "missing")
            self.assertTrue(row[3].startswith("http://www.aqsc.agri.cn/"))
            self.assertTrue(row[4].endswith(".htm"))
            self.assertEqual(row[5], "deferred")
            self.assertEqual(row[6], "file-source:fixture")

    def test_oversize_response_writes_note_without_file_body(self):
        class Spider:
            source_id = "aqsc-moa"
            run_id = "oversize-test"

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            middleware = RawEvidenceMiddleware(
                root / "crawler.db",
                root / "download",
                REGISTRY,
            )
            request = Request("http://example.test/huge.xlsx")
            middleware.process_request(request, Spider())
            response = Response(
                request.url,
                body=b"not the full file",
                headers={"Content-Length": "104857601"},
                request=request,
            )
            middleware.process_response(request, response, Spider())
            conn = sqlite3.connect(root / "crawler.db")
            try:
                status, note = conn.execute(
                    "SELECT download_status, oversize_note FROM raw_files"
                ).fetchone()
            finally:
                conn.close()
            note_path = root / "download" / "example.test" / "OVERSIZE.md"
            self.assertTrue(note_path.is_file())

        self.assertEqual(status, "oversize")
        self.assertIn("104857601", note)


if __name__ == "__main__":
    unittest.main()
