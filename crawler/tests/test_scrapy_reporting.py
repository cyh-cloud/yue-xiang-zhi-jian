import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from scrapy.http import HtmlResponse, Request

from crawler.collection.shared.crawler_collection.database import (
    CollectionDatabase,
)
from crawler.collection.shared.crawler_collection.reporting import (
    RunReportExtension,
)


class _Signals:
    def connect(self, *args, **kwargs):
        return None


class _Stats:
    def get_stats(self):
        return {}


class _Crawler:
    def __init__(self, root):
        self.settings = {
            "COLLECTION_DATABASE_PATH": str(root / "crawler.db"),
            "COLLECTION_DOWNLOAD_ROOT": str(root / "download"),
            "COLLECTION_REPORT_ROOT": str(root / "reports"),
        }
        self.signals = _Signals()
        self.stats = _Stats()


class _Spider:
    source_id = "nongmuhr"

    def __init__(self, run_id, item_counts=None):
        self.run_id = run_id
        self._collection_counts = dict(item_counts or {})


class RunReportFailureCountTest(unittest.TestCase):
    def _extension(self, root):
        database = CollectionDatabase(root / "crawler.db")
        conn = database.connect()
        conn.close()
        return RunReportExtension(_Crawler(root))

    def test_parse_failures_are_counted_and_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            extension = self._extension(root)
            spider = _Spider("nongmuhr-live")
            extension.spider_opened(spider)
            for index in range(10):
                request = Request(f"https://nongmuhr.example/job/{index}")
                response = HtmlResponse(
                    url=request.url,
                    request=request,
                    body=b"<html></html>",
                    status=200,
                )
                failure = SimpleNamespace(
                    value=AttributeError(
                        "'NoneType' object has no attribute 'select'"
                    )
                )
                extension.spider_error(failure, response, spider)

            extension.spider_closed(spider, "finished")

            report = spider.run_report
            self.assertEqual(report.failed, 10)
            self.assertEqual(report.failure_count, 10)
            self.assertEqual(report.status, "failed")
            self.assertIn("AttributeError", report.failure_reason)
            persisted = json.loads(
                Path(report.report_path).read_text(encoding="utf-8")
            )
            self.assertEqual(persisted["failure_count"], 10)

    def test_http_404_failures_are_counted_without_double_counting(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            extension = self._extension(root)
            spider = _Spider("cass-live", item_counts={"blocked": 5})
            extension.spider_opened(spider)
            for index in range(4):
                request = Request(f"https://cass.example/article/{index}")
                response = HtmlResponse(
                    url=request.url,
                    request=request,
                    body=b"missing",
                    status=404,
                )
                extension.response_received(response, request, spider)
                extension.spider_error(
                    SimpleNamespace(value=ValueError("unexpected 404 body")),
                    response,
                    spider,
                )

            extension.spider_closed(spider, "finished")

            report = spider.run_report
            self.assertEqual(report.failed, 4)
            self.assertEqual(report.failure_count, 4)
            self.assertEqual(report.blocked, 5)
            self.assertEqual(report.status, "partial")
            self.assertIn("HTTP 404", report.failure_reason)

    def test_parse_failure_without_response_is_still_counted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            extension = self._extension(root)
            spider = _Spider("nongmuhr-live")
            extension.spider_opened(spider)
            extension.spider_error(
                SimpleNamespace(value=ValueError("callback failed")),
                None,
                spider,
            )

            extension.spider_closed(spider, "finished")

            self.assertEqual(spider.run_report.failed, 1)
            self.assertEqual(spider.run_report.failure_count, 1)


if __name__ == "__main__":
    unittest.main()
