"""Persist actual Scrapy responses as raw evidence before item processing."""

from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone

from scrapy.exceptions import IgnoreRequest

from .evidence import RawEvidence, sha256_bytes
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
            or str(Path(database_path).parent / "download"),
            settings.get("SOURCE_REGISTRY_PATH"),
        )

    def process_request(self, request, spider):
        run_id = getattr(spider, "run_id", None)
        if not run_id:
            raise RuntimeError(
                "spider run_id is missing; construct it with "
                "CollectionSpiderMixin.from_crawler"
            )
        request.meta["run_id"] = run_id
        request.meta.setdefault(
            "started_at", datetime.now(timezone.utc).isoformat()
        )
        request.meta.setdefault("robots_decision", "unknown")
        return None

    def process_response(self, request, response, spider):
        if request.meta.get("dont_obey_robotstxt"):
            return response
        body = response.body
        file_name = Path(response.url.split("?", 1)[0]).name
        run_id = request.meta.get("run_id") or getattr(spider, "run_id", None)
        if not run_id:
            raise RuntimeError("request is missing the crawl run_id")
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
                metadata={
                    "file_name": file_name or "response.bin",
                    "robots_status_code": request.meta.get(
                        "robots_status_code"
                    ),
                    "robots_evidence_url": request.meta.get(
                        "robots_evidence_url"
                    ),
                    "robots_checked_at": request.meta.get(
                        "robots_checked_at"
                    ),
                },
            )
        )
        request.meta["raw_evidence_id"] = raw_id
        request.meta["run_id"] = run_id
        request.meta["content_hash"] = content_hash
        return response

    def process_exception(self, request, exception, spider):
        if request.meta.get("dont_obey_robotstxt"):
            return None
        run_id = request.meta.get("run_id") or getattr(spider, "run_id", None)
        if not run_id:
            raise RuntimeError("request is missing the crawl run_id")
        now = datetime.now(timezone.utc).isoformat()
        is_robots_rejection = (
            isinstance(exception, IgnoreRequest)
            and "robots" in str(exception).lower()
        )
        robots_decision = request.meta.get("robots_decision", "unknown")
        if is_robots_rejection:
            robots_decision = "disallowed"
            request.meta["robots_decision"] = robots_decision
        self.runtime.persist_raw(
            RawEvidence(
                source_id=spider.source_id,
                request_url=request.url,
                final_url=request.url,
                source_url=request.meta.get("source_url") or request.url,
                long_term_url=(
                    request.meta.get("long_term_url") or request.url
                ),
                detail_url=request.meta.get("detail_url"),
                detail_url_status=(
                    "direct"
                    if request.meta.get("detail_url")
                    else "missing"
                ),
                fetch_url=request.url,
                locator=request.meta.get("locator") or request.url,
                body=b"",
                content_type="",
                status_code=None,
                started_at=request.meta.get("started_at") or now,
                retrieved_at=now,
                request_headers=dict(request.headers),
                response_headers={},
                robots_decision=robots_decision,
                fetch_status="error",
                error_message=f"{type(exception).__name__}: {exception}",
                run_id=run_id,
                metadata={
                    "file_name": "request-error.bin",
                    "robots_status_code": request.meta.get(
                        "robots_status_code"
                    ),
                    "robots_evidence_url": request.meta.get(
                        "robots_evidence_url"
                    ),
                    "robots_checked_at": request.meta.get(
                        "robots_checked_at"
                    ),
                },
            )
        )
        return None
