"""Persist actual Scrapy responses as raw evidence before item processing."""

from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone

from .evidence import RawEvidence, sha256_bytes
from .run_id import new_run_id
from .runtime import CollectionRuntime


class RawEvidenceMiddleware:
    def __init__(self, database_path, download_root, registry_path=None):
        self.runtime = CollectionRuntime(
            database_path=database_path,
            download_root=download_root,
            registry_path=registry_path,
        )

    @classmethod
    def from_crawler(cls, crawler):
        settings = crawler.settings
        database_path = settings.get("COLLECTION_DATABASE_PATH")
        if not database_path:
            raise ValueError("COLLECTION_DATABASE_PATH is required")
        return cls(
            database_path,
            settings.get("COLLECTION_DOWNLOAD_ROOT")
            or str(Path(database_path).parent / "downloads"),
            settings.get("SOURCE_REGISTRY_PATH"),
        )

    def process_request(self, request, spider):
        request.meta.setdefault(
            "run_id",
            getattr(spider, "run_id", None) or new_run_id(spider.source_id),
        )
        request.meta.setdefault(
            "started_at", datetime.now(timezone.utc).isoformat()
        )
        if "robots_decision" not in request.meta:
            obey = False
            crawler = getattr(spider, "crawler", None)
            if crawler is not None:
                obey = crawler.settings.getbool("ROBOTSTXT_OBEY")
            request.meta["robots_decision"] = "allowed" if obey else "unknown"
        return None

    def process_response(self, request, response, spider):
        body = response.body
        file_name = Path(response.url.split("?", 1)[0]).name
        run_id = (
            request.meta.get("run_id")
            or getattr(spider, "run_id", None)
            or new_run_id(spider.source_id)
        )
        content_hash = sha256_bytes(body)
        raw_id = self.runtime.persist_raw(
            RawEvidence(
                source_id=spider.source_id,
                request_url=request.url,
                final_url=response.url,
                source_url=request.meta.get("source_url") or request.url,
                long_term_url=(
                    request.meta.get("long_term_url") or response.url
                ),
                detail_url=request.meta.get("detail_url"),
                detail_url_status=(
                    "direct"
                    if request.meta.get("detail_url")
                    else "missing"
                ),
                fetch_url=request.url,
                locator=request.meta.get("locator") or request.url,
                body=body,
                content_type=response.headers.get(
                    "Content-Type", b"application/octet-stream"
                ).decode("latin-1"),
                status_code=response.status,
                started_at=request.meta.get("started_at"),
                retrieved_at=datetime.now(timezone.utc).isoformat(),
                request_headers=dict(request.headers),
                response_headers=dict(response.headers),
                robots_decision=request.meta.get(
                    "robots_decision", "unknown"
                ),
                run_id=run_id,
                metadata={"file_name": file_name or "response.bin"},
            )
        )
        response.meta["raw_evidence_id"] = raw_id
        response.meta["run_id"] = run_id
        response.meta["content_hash"] = content_hash
        return response
