import importlib
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

from scrapy.crawler import CrawlerProcess
from scrapy.http import HtmlResponse, Request
from scrapy.settings import Settings

from crawler.collection.shared.crawler_collection.middlewares import (
    RawEvidenceMiddleware,
)
from crawler.collection.shared.crawler_collection.pipelines import (
    CollectionPipeline,
)


ROOT = Path(__file__).resolve().parents[1]
PROJECTS = ROOT / "collection" / "projects"
sys.path.insert(
    0,
    str(PROJECTS / "ihchina"),
)


class ScrapyRuntimeIntegrationTest(unittest.TestCase):
    def test_all_projects_load_settings_and_collection_pipeline(self):
        for project_root in sorted(
            path
            for path in PROJECTS.iterdir()
            if path.is_dir()
            and path.name not in {"__pycache__"}
            and (path / "scrapy.cfg").is_file()
        ):
            source_id = project_root.name
            package = source_id.replace("-", "_")
            sys.path.insert(0, str(project_root))
            settings = importlib.import_module(f"{package}.settings")
            self.assertTrue(settings.COLLECTION_DATABASE_PATH, source_id)
            self.assertTrue(
                any(
                    name.endswith("RawEvidenceMiddleware")
                    for name in settings.DOWNLOADER_MIDDLEWARES
                ),
                source_id,
            )
            self.assertTrue(
                any(
                    name.endswith("CollectionPipeline")
                    for name in settings.ITEM_PIPELINES
                ),
                source_id,
            )

    def test_pipeline_from_crawler_constructs_without_manual_database_arg(self):
        settings = Settings(
            {
                "COLLECTION_DATABASE_PATH": str(
                    ROOT / ".tmp-test" / "crawler.db"
                ),
                "COLLECTION_DOWNLOAD_ROOT": str(ROOT / ".tmp-test"),
                "SOURCE_REGISTRY_PATH": str(ROOT / "docs" / "sources.json"),
            }
        )
        process = CrawlerProcess(settings)
        from ihchina.spiders.collection import IhchinaSpider

        crawler = process.create_crawler(IhchinaSpider)

        pipeline = CollectionPipeline.from_crawler(crawler)
        middleware = RawEvidenceMiddleware.from_crawler(crawler)

        self.assertIsNotNone(pipeline.runtime)
        self.assertIsNotNone(middleware.runtime)

    def test_nine_middleware_and_pipeline_imports_are_consistent(self):
        for project_root in sorted(
            path
            for path in PROJECTS.iterdir()
            if path.is_dir()
            and path.name not in {"__pycache__"}
            and (path / "scrapy.cfg").is_file()
        ):
            package = project_root.name.replace("-", "_")
            sys.path.insert(0, str(project_root))
            settings = importlib.import_module(f"{package}.settings")
            self.assertTrue(
                settings.DOWNLOADER_MIDDLEWARES[
                    "crawler.collection.shared.crawler_collection."
                    "middlewares.RawEvidenceMiddleware"
                ]
            )
            self.assertTrue(
                settings.ITEM_PIPELINES[
                    "crawler.collection.shared.crawler_collection."
                    "pipelines.CollectionPipeline"
                ]
            )

    def test_response_middleware_and_pipeline_persist_all_layers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = Settings(
                {
                    "COLLECTION_DATABASE_PATH": str(root / "crawler.db"),
                    "COLLECTION_DOWNLOAD_ROOT": str(root / "downloads"),
                    "SOURCE_REGISTRY_PATH": str(
                        ROOT / "docs" / "sources.json"
                    ),
                }
            )
            process = CrawlerProcess(settings)
            from ihchina.spiders.collection import IhchinaSpider

            crawler = process.create_crawler(IhchinaSpider)
            spider = IhchinaSpider.from_crawler(crawler)
            middleware = RawEvidenceMiddleware.from_crawler(crawler)
            pipeline = CollectionPipeline.from_crawler(crawler)
            request = Request(
                "https://www.ihchina.cn/project_details/12178.html",
                meta={
                    "detail_url": (
                        "https://www.ihchina.cn/project_details/12178.html"
                    ),
                    "long_term_url": (
                        "https://www.ihchina.cn/project_details/12178.html"
                    ),
                    "robots_decision": "allowed",
                },
            )
            response = HtmlResponse(
                request.url,
                body=(
                    '<div class="article-mod2">'
                    '<div class="t_head"><div class="h30">苗族古歌</div></div>'
                    '<div class="table"><div class="p">项目编号：Ⅰ-1</div></div>'
                    '<div class="text"><div class="p">正文</div></div></div>'
                ).encode("utf-8"),
                encoding="utf-8",
                request=request,
            )
            response = middleware.process_response(request, response, spider)
            item = {
                "source_id": "ihchina",
                "source_item_id": "12178",
                "source_url": request.url,
                "long_term_url": request.url,
                "detail_url": request.url,
                "detail_url_status": "direct",
                "run_id": "test",
                "mode": "live",
                "rights_status": "attribution-required",
                "title": "苗族古歌",
                "raw_evidence_id": response.meta["raw_evidence_id"],
            }
            pipeline.process_item(item, spider)

            conn = sqlite3.connect(root / "crawler.db")
            try:
                self.assertEqual(
                    conn.execute(
                        "SELECT COUNT(*) FROM raw_fetches"
                    ).fetchone()[0],
                    1,
                )
                self.assertEqual(
                    conn.execute(
                        "SELECT COUNT(*) FROM stage_source_items"
                    ).fetchone()[0],
                    1,
                )
                self.assertEqual(
                    conn.execute(
                        "SELECT COUNT(*) FROM std_ich_projects"
                    ).fetchone()[0],
                    1,
                )
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
