"""Offline downloader middleware for ihchina fixture replay."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

from scrapy.http import HtmlResponse, TextResponse


class IhchinaFixtureDownloaderMiddleware:
    """Serve the project's recorded list and detail responses without network."""

    def __init__(self, fixture_dir):
        self.fixture_dir = Path(fixture_dir)

    @classmethod
    def from_crawler(cls, crawler):
        fixture_dir = crawler.settings.get("IHCHINA_FIXTURE_DIR")
        if not fixture_dir:
            raise ValueError("IHCHINA_FIXTURE_DIR is required")
        return cls(fixture_dir)

    def process_request(self, request, spider):
        path = urlparse(request.url).path
        if path.endswith("/getProject.html"):
            fixture_path = self.fixture_dir / "discover.json"
            content_type = "application/json; charset=utf-8"
            response_class = TextResponse
        elif "/project_details/" in path:
            source_item_id = (
                path.split("/project_details/", 1)[1].split(".", 1)[0]
            )
            fixture_path = (
                self.fixture_dir / f"detail-{source_item_id}.html"
            )
            content_type = "text/html; charset=utf-8"
            response_class = HtmlResponse
        else:
            return None

        body = fixture_path.read_bytes()
        if fixture_path.suffix == ".json":
            json.loads(body.decode("utf-8"))
        request.meta["robots_decision"] = "allowed"
        request.meta.setdefault(
            "robots_evidence_url",
            f"https://{urlparse(request.url).netloc}/robots.txt",
        )
        return response_class(
            request.url,
            body=body,
            encoding="utf-8",
            request=request,
            status=200,
            headers={"Content-Type": content_type},
        )
