"""Persist actual Scrapy responses as raw evidence before item processing."""

from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone
import re
from urllib.parse import urlparse

from scrapy import signals
from scrapy.exceptions import DownloadCancelledError, IgnoreRequest
from twisted.internet.defer import CancelledError

from .evidence import RawEvidence, sha256_bytes
from .runtime import CollectionRuntime


def _oversize_failure(exception, *, request, max_download_bytes):
    message = str(exception)
    lowered = message.lower()
    received = int(request.meta.get("collection_bytes_received") or 0)
    cancelled_oversize = (
        isinstance(exception, CancelledError)
        and received > max_download_bytes
    )
    is_oversize = isinstance(exception, DownloadCancelledError) or (
        "download max size" in lowered
        or "download_maxsize" in lowered
    ) or cancelled_oversize
    if not is_oversize:
        return None
    size_match = re.search(
        r"(?:receive|received)\s+(\d+)\s+bytes",
        message,
        re.IGNORECASE,
    )
    limit_match = re.search(
        r"(?:max size|limit)\s*[\(:= ]\s*(\d+)",
        message,
        re.IGNORECASE,
    )
    size = int(size_match.group(1)) if size_match else received or None
    if cancelled_oversize and not message:
        message = (
            f"Received {received} bytes which is larger than download "
            f"max size ({max_download_bytes}) in request {request.url}."
        )
    limit = (
        int(limit_match.group(1))
        if limit_match
        else (max_download_bytes if cancelled_oversize else None)
    )
    return {
        "size": size,
        "limit": limit,
        "reason": message,
    }


class RawEvidenceMiddleware:
    def __init__(
        self,
        database_path,
        download_root,
        registry_path=None,
        max_download_bytes=None,
    ):
        self.runtime = CollectionRuntime(
            database_path=database_path,
            download_root=download_root,
            registry_path=registry_path,
            max_download_bytes=(
                max_download_bytes
                if max_download_bytes is not None
                else 100 * 1024 * 1024
            ),
        )

    @classmethod
    def from_crawler(cls, crawler):
        settings = crawler.settings
        database_path = settings.get("COLLECTION_DATABASE_PATH")
        if not database_path:
            raise ValueError("COLLECTION_DATABASE_PATH is required")
        middleware = cls(
            database_path,
            settings.get("COLLECTION_DOWNLOAD_ROOT")
            or str(Path(database_path).parent / "download"),
            settings.get("SOURCE_REGISTRY_PATH"),
            settings.getint("DOWNLOAD_MAXSIZE"),
        )
        if getattr(crawler, "signals", None) is not None:
            crawler.signals.connect(
                middleware.bytes_received,
                signal=signals.bytes_received,
            )
        return middleware

    @staticmethod
    def bytes_received(data, request, spider):
        received = int(request.meta.get("collection_bytes_received") or 0)
        request.meta["collection_bytes_received"] = received + len(data)

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
        request.meta["collection_bytes_received"] = 0
        return None

    def process_response(self, request, response, spider):
        if request.meta.get("dont_obey_robotstxt"):
            return response
        self._ensure_request_locator(request)
        is_http_error = response.status >= 400
        body = response.body
        file_name = request.meta.get("file_name") or Path(
            response.url.split("?", 1)[0]
        ).name
        run_id = request.meta.get("run_id") or getattr(spider, "run_id", None)
        if not run_id:
            raise RuntimeError("request is missing the crawl run_id")
        content_hash = None if is_http_error else sha256_bytes(body)
        declared_size = response.headers.get("Content-Length")
        try:
            declared_size = (
                int(declared_size) if declared_size is not None else None
            )
        except (TypeError, ValueError):
            declared_size = None
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
                locator=request.meta.get("locator"),
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
                fetch_status=(
                    "http_error" if is_http_error else None
                ),
                error_message=(
                    f"HTTP {response.status}"
                    if is_http_error
                    else None
                ),
                run_id=run_id,
                declared_size=declared_size,
                metadata={
                    "file_name": file_name or "response.bin",
                    "file_request": bool(request.meta.get("file_name")),
                    "http_error": is_http_error,
                    "observed_body_bytes": len(response.body),
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
        if content_hash is not None:
            request.meta["content_hash"] = content_hash
        return response

    def process_exception(self, request, exception, spider):
        if request.meta.get("dont_obey_robotstxt"):
            return None
        self._ensure_request_locator(request)
        run_id = request.meta.get("run_id") or getattr(spider, "run_id", None)
        if not run_id:
            raise RuntimeError("request is missing the crawl run_id")
        now = datetime.now(timezone.utc).isoformat()
        message = f"{type(exception).__name__}: {exception}"
        lowered = message.lower()
        is_robots_rejection = (
            isinstance(exception, IgnoreRequest)
            and "robots" in lowered
        )
        robots_decision = request.meta.get("robots_decision", "unknown")
        if is_robots_rejection and "forbidden" in lowered:
            robots_decision = "disallowed"
            request.meta["robots_decision"] = robots_decision
        oversize = _oversize_failure(
            exception,
            request=request,
            max_download_bytes=self.runtime.max_download_bytes,
        )
        error_file_name = (
            request.meta.get("file_name")
            or Path(urlparse(request.url).path).name
            or "request-error.bin"
        )
        metadata = {
            "file_name": error_file_name,
            "file_request": bool(request.meta.get("file_name")),
            "robots_status_code": request.meta.get(
                "robots_status_code"
            ),
            "robots_evidence_url": request.meta.get(
                "robots_evidence_url"
            ),
            "robots_checked_at": request.meta.get(
                "robots_checked_at"
            ),
        }
        if oversize is not None:
            metadata.update(
                {
                    "oversize": True,
                    "oversize_reason": oversize["reason"],
                    "oversize_limit": oversize["limit"],
                    "oversize_size": oversize["size"],
                }
            )
        raw_id = self.runtime.persist_raw(
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
                locator=request.meta.get("locator"),
                body=b"",
                content_type="",
                status_code=None,
                started_at=request.meta.get("started_at") or now,
                retrieved_at=now,
                request_headers=dict(request.headers),
                response_headers={},
                robots_decision=robots_decision,
                fetch_status=(
                    "oversize" if oversize is not None else "error"
                ),
                error_message=message,
                run_id=run_id,
                declared_size=(
                    oversize["size"]
                    if oversize is not None
                    else None
                ),
                metadata=metadata,
            )
        )
        request.meta["raw_evidence_id"] = raw_id
        return None

    @staticmethod
    def _ensure_request_locator(request):
        if not str(request.meta.get("locator") or "").strip():
            request.meta["locator"] = "locator:missing"
