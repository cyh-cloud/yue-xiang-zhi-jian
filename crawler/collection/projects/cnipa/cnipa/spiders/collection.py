import hashlib
import json
import re
from pathlib import Path
from urllib.parse import parse_qs, unquote, urljoin, urlparse

import scrapy

from crawler.collection.shared.crawler_collection.items import (
    item_from_mapping,
)
from crawler.collection.shared.crawler_collection.spiders import (
    CollectionSpiderMixin,
)
from ..parsers import parse_pdf_rows


class CnipaSpider(CollectionSpiderMixin, scrapy.Spider):
    name = "cnipa"
    source_id = "cnipa"
    allowed_domains = []
    start_urls = []
    live_enabled = True
    max_download_bytes = 100 * 1024 * 1024

    def __init__(self, *args, start_urls=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.start_urls = list(start_urls or [])

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(
                url,
                callback=self.parse,
                dont_filter=True,
                meta={
                    "source_url": url,
                    "long_term_url": url,
                    "locator": url,
                    "mode": "live",
                    "candidate_reason": "file-source:live-canary",
                },
            )

    def parse(self, response):
        content_type = response.headers.get(
            "Content-Type", b""
        ).decode("latin-1")
        if response.url.endswith("discover.json") or (
            "json" in content_type
        ):
            payload = json.loads(response.text)
            for item in payload.get("items") or []:
                carrier_url = item.get("carrier_url")
                if not carrier_url:
                    continue
                meta = {
                    **{
                        key: value
                        for key, value in item.items()
                        if key not in {"file_name", "file_url"}
                    },
                    "source_url": item.get("source_url") or carrier_url,
                    "long_term_url": (
                        item.get("long_term_url") or carrier_url
                    ),
                    "mode": "fixture",
                    "candidate_reason": item.get("candidate_reason")
                    or "file-source:fixture",
                }
                yield scrapy.Request(
                    carrier_url,
                    callback=self.parse_carrier,
                    dont_filter=True,
                    meta=meta,
                )
            return
        yield from self.parse_carrier(response)

    def parse_carrier(self, response):
        title = self._first_text(
            response, ".index_title::text", "title::text"
        )
        published_at = self._first_text(
            response, ".index_time::text"
        )
        if published_at:
            published_at = re.sub(
                r"^发布时间\s*[：:]\s*", "", published_at
            )
        announcement_no = None
        if title:
            match = re.search(r"第\s*\d+\s*号", title)
            if match:
                announcement_no = "".join(match.group(0).split())
        announcement_id = response.meta.get("announcement_id")
        if not announcement_id:
            id_match = re.search(r"\d+", announcement_no or "")
            announcement_id = (
                id_match.group(0) if id_match else None
            )
        meta = {
            **response.meta,
            "title": title or response.meta.get("title"),
            "published_at": published_at
            or response.meta.get("published_at"),
            "announcement_no": announcement_no
            or response.meta.get("announcement_no"),
            "announcement_id": announcement_id,
            "long_term_url": response.meta.get("long_term_url")
            or response.url,
        }
        file_url = self._attachment_url(response)
        if file_url is None:
            yield self._blocked_item(
                response, "carrier:attachment-link-missing", meta=meta
            )
            return
        yield self._file_request(response, file_url, meta)

    def parse_file(self, response):
        if response.status >= 400:
            yield self._blocked_item(
                response, f"fetch:http_error:{response.status}"
            )
            return
        content_type = response.headers.get(
            "Content-Type", b""
        ).decode("latin-1").lower()
        if "pdf" not in content_type:
            yield self._blocked_item(
                response, f"file:mime_type:{content_type or 'missing'}"
            )
            return
        file_name = response.meta.get("file_name") or response.url.rsplit(
            "/", 1
        )[-1]
        metadata = {
            key: response.meta.get(key)
            for key in (
                "announcement_id",
                "announcement_no",
                "cert_type",
                "published_at",
                "source_url",
                "long_term_url",
                "candidate_reason",
            )
        }
        records = parse_pdf_rows(
            response.body,
            file_name=file_name,
            metadata=metadata,
        )
        if not records:
            yield self._blocked_item(response, "parse:no_product_rows")
            return
        for record in records:
            record["fetch_url"] = response.url
            record["mode"] = response.meta.get("mode", "live")
            yield item_from_mapping(
                record,
                source_id=self.source_id,
                response=response,
            )

    def _file_request(self, response, file_url, meta=None):
        file_url = urljoin(response.url, file_url)
        query = parse_qs(urlparse(file_url).query)
        file_name = (
            (query.get("showname") or query.get("filename") or [None])[0]
            or file_url.split("?", 1)[0].rsplit("/", 1)[-1]
        )
        file_name = Path(unquote(file_name)).name
        source_url = (
            (meta or response.meta).get("file_source_url") or file_url
        )
        return scrapy.Request(
            file_url,
            callback=self.parse_file,
            dont_filter=True,
            meta={
                **(meta or response.meta),
                "source_url": source_url,
                "locator": f"file={file_name}; page=1",
                "file_name": file_name,
                "download_maxsize": self.max_download_bytes,
                "download_warnsize": self.max_download_bytes,
                "handle_httpstatus_all": True,
            },
        )

    @staticmethod
    def _attachment_url(response):
        selectors = (
            ".index_art_con a[href]::attr(href)",
            "a.attachment[href]::attr(href)",
            "a[href]::attr(href)",
        )
        for selector in selectors:
            for href in response.css(selector).getall():
                path = href.split("#", 1)[0].lower()
                if path.endswith(".pdf"):
                    return urljoin(response.url, href)
        return None

    @staticmethod
    def _first_text(response, *selectors):
        for selector in selectors:
            values = response.css(selector).getall()
            for value in values:
                text = " ".join(value.split())
                if text:
                    return text
        return None

    def _blocked_item(self, response, reason, *, meta=None):
        meta = meta or response.meta
        long_term_url = meta.get("long_term_url") or response.url
        source_key = hashlib.sha1(
            response.url.encode("utf-8")
        ).hexdigest()[:12]
        payload = {
            "source_item_id": (
                meta.get("announcement_id") or f"blocked:{source_key}"
            ),
            "title": meta.get("title")
            or response.css("title::text").get()
            or response.url,
            "source_url": response.url,
            "long_term_url": long_term_url,
            "detail_url": None,
            "detail_url_status": "missing",
            "locator": (
                f"carrier={long_term_url}; status={response.status}"
            ),
            "candidate_status": "blocked",
            "candidate_reason": reason,
            "mode": meta.get("mode", "live"),
            "extra": {
                "status_code": response.status,
                "failure_url": response.url,
                "release_condition": (
                    "the carrier must expose a PDF attachment with a "
                    "text layer"
                ),
            },
        }
        return item_from_mapping(
            payload,
            source_id=self.source_id,
            response=response,
        )
