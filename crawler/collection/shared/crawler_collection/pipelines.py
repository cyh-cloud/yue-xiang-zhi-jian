"""Shared Pipeline boundary: raw, stage, and crawler-DB candidates only."""

from __future__ import annotations

from importlib import import_module
from pathlib import Path

from .items import validate_item
from .reporting import record_pipeline_result
from .runtime import CollectionRuntime


class CollectionPipeline:
    def __init__(
        self,
        database_path,
        download_root=None,
        registry_path=None,
        candidate_writer=None,
    ):
        self.runtime = CollectionRuntime(
            database_path=database_path,
            download_root=download_root
            or Path(database_path).parent / "download",
            registry_path=registry_path,
            candidate_writer=candidate_writer,
        )

    @classmethod
    def from_crawler(cls, crawler):
        settings = crawler.settings
        database_path = settings.get("COLLECTION_DATABASE_PATH")
        if not database_path:
            raise ValueError("COLLECTION_DATABASE_PATH is required")
        return cls(
            database_path,
            download_root=settings.get("COLLECTION_DOWNLOAD_ROOT"),
            registry_path=settings.get("SOURCE_REGISTRY_PATH"),
            candidate_writer=_load_candidate_writer(
                settings.get("COLLECTION_CANDIDATE_WRITER")
            ),
        )

    def process_item(self, item, spider):
        payload = validate_item(item)
        raw_evidence_id = payload.get("raw_evidence_id")
        if not raw_evidence_id:
            raise ValueError("raw_evidence_id is required before persistence")
        result = self.runtime.write_item(
            payload,
            raw_evidence_id=raw_evidence_id,
        )
        record_pipeline_result(spider, result)
        if isinstance(item, dict):
            item.update(result)
        return item


def _load_candidate_writer(dotted_path):
    if not dotted_path:
        return None
    module_name, attribute = dotted_path.rsplit(".", 1)
    return getattr(import_module(module_name), attribute)


def collection_settings(
    *,
    bot_name,
    package_name,
    database_path,
    download_root,
    registry_path,
    candidate_writer=None,
):
    return {
        "BOT_NAME": bot_name,
        "SPIDER_MODULES": [f"{package_name}.spiders"],
        "NEWSPIDER_MODULE": f"{package_name}.spiders",
        "ROBOTSTXT_OBEY": True,
        "USER_AGENT": (
            "yuexiang-crawler/0.1 "
            "(competition; noncommercial; contact: local)"
        ),
        "DOWNLOAD_DELAY": 1,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_TIMEOUT": 30,
        "RETRY_TIMES": 2,
        "COLLECTION_DATABASE_PATH": database_path,
        "COLLECTION_DOWNLOAD_ROOT": download_root,
        "SOURCE_REGISTRY_PATH": registry_path,
        "COLLECTION_CANDIDATE_WRITER": candidate_writer,
        "COLLECTION_REPORT_ROOT": str(
            Path(database_path).parent / "reports"
        ),
        "EXTENSIONS": {
            "crawler.collection.shared.crawler_collection.reporting."
            "RunReportExtension": 500,
        },
        "DOWNLOADER_MIDDLEWARES": {
            "scrapy.downloadermiddlewares.robotstxt."
            "RobotsTxtMiddleware": None,
            "crawler.collection.shared.crawler_collection.robots."
            "RobotsEvidenceMiddleware": 100,
            "crawler.collection.shared.crawler_collection.middlewares."
            "RawEvidenceMiddleware": 543,
        },
        "ITEM_PIPELINES": {
            "crawler.collection.shared.crawler_collection.pipelines."
            "CollectionPipeline": 300,
        },
    }
