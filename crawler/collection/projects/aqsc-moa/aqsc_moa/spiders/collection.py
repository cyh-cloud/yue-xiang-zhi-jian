import hashlib
import json
from pathlib import Path
from urllib.parse import urljoin, urlparse

import scrapy

from crawler.collection.shared.crawler_collection.items import (
    item_from_mapping,
)
from crawler.collection.shared.crawler_collection.registry import (
    load_registry,
)
from crawler.collection.shared.crawler_collection.spiders import (
    CollectionSpiderMixin,
)
from ..parsers import parse_embedded_rows, parse_xlsx_rows


def _source_domains(source_id):
    source = load_registry().get(source_id) or {}
    domains = [
        str(value).strip().lower()
        for value in source.get("domains") or []
        if str(value).strip()
    ]
    if not domains:
        raise RuntimeError(
            f"source registry has no allowed domains for {source_id}"
        )
    return domains


def _url_host(url):
    return (urlparse(url).hostname or "").lower()


class DisallowedUrl(ValueError):
    pass


class AqscMoaSpider(CollectionSpiderMixin, scrapy.Spider):
    name = "aqsc-moa"
    source_id = "aqsc-moa"
    allowed_domains = _source_domains("aqsc-moa")
    start_urls = []
    live_enabled = True
    max_download_bytes = 100 * 1024 * 1024

    def __init__(self, *args, start_urls=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.start_urls = list(start_urls or [])
        self.allowed_domains = list(type(self).allowed_domains)
        for url in self.start_urls:
            host = _url_host(url)
            if host in {"127.0.0.1", "localhost"}:
                if host not in self.allowed_domains:
                    self.allowed_domains.append(host)

    def start_requests(self):
        for url in self.start_urls:
            self._require_allowed_url(url)
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
                try:
                    self._require_allowed_url(carrier_url)
                except DisallowedUrl as exc:
                    yield self._blocked_item(
                        response,
                        str(exc),
                        source_url=carrier_url,
                        locator=carrier_url,
                    )
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
        try:
            file_url = self._attachment_url(response)
        except DisallowedUrl as exc:
            yield self._blocked_item(response, str(exc))
            return
        if file_url is not None:
            yield self._file_request(response, file_url)
            return

        records = self._embedded_records(response)
        if records:
            yield from self._record_items(response, records)
            return

        try:
            detail_url = self._aqsc_detail_url(response)
        except DisallowedUrl as exc:
            yield self._blocked_item(response, str(exc))
            return
        if detail_url is not None:
            carrier_title = " ".join(
                response.css("title::text").getall()
            ).strip()
            meta = {
                **response.meta,
                "source_url": detail_url,
                "title": response.meta.get("title") or carrier_title,
                "locator": (
                    f"carrier={response.meta.get('long_term_url')}; "
                    "detail=missing"
                ),
            }
            yield scrapy.Request(
                detail_url,
                callback=self.parse_attachment_page,
                dont_filter=True,
                meta={**meta, "handle_httpstatus_all": True},
            )
            return
        yield self._blocked_item(
            response, "carrier:attachment-link-missing"
        )

    def parse_attachment_page(self, response):
        if response.status >= 400:
            yield self._blocked_item(
                response, f"fetch:http_error:{response.status}"
            )
            return
        try:
            file_url = self._attachment_url(response)
        except DisallowedUrl as exc:
            yield self._blocked_item(response, str(exc))
            return
        if file_url is None:
            records = self._embedded_records(response)
            if records:
                yield from self._record_items(response, records)
            else:
                yield self._blocked_item(
                    response,
                    "carrier:attachment-and-embedded-table-missing",
                )
            return
        yield self._file_request(response, file_url)

    def parse_file(self, response):
        if response.status >= 400:
            yield self._blocked_item(
                response, f"fetch:http_error:{response.status}"
            )
            return
        file_name = response.meta.get("file_name") or response.url.rsplit(
            "/", 1
        )[-1]
        if Path(file_name).suffix.lower() == ".xls":
            yield self._blocked_item(
                response, "file:unsupported_extension:.xls"
            )
            return
        content_type = response.headers.get(
            "Content-Type", b""
        ).decode("latin-1").lower()
        if "spreadsheet" not in content_type and "excel" not in content_type:
            yield self._blocked_item(
                response, f"file:mime_type:{content_type or 'missing'}"
            )
            return
        metadata = {
            key: response.meta.get(key)
            for key in (
                "announcement_id",
                "announcement_no",
                "batch",
                "cert_type",
                "published_at",
                "source_url",
                "long_term_url",
                "candidate_reason",
            )
        }
        records = parse_xlsx_rows(
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

    def _embedded_records(self, response):
        try:
            return parse_embedded_rows(
                response.text,
                page_url=response.url,
                metadata=response.meta,
            )
        except Exception:
            return []

    def _record_items(self, response, records):
        for record in records:
            record["fetch_url"] = response.url
            record["mode"] = response.meta.get("mode", "live")
            yield item_from_mapping(
                record,
                source_id=self.source_id,
                response=response,
            )

    def _file_request(self, response, file_url):
        file_url = urljoin(response.url, file_url)
        self._require_allowed_url(file_url)
        file_name = file_url.split("?", 1)[0].rsplit("/", 1)[-1]
        source_url = (
            response.meta.get("file_source_url") or file_url
        )
        return scrapy.Request(
            file_url,
            callback=self.parse_file,
            dont_filter=True,
            meta={
                **response.meta,
                "source_url": source_url,
                "locator": f"file={file_name}; page=1",
                "file_name": file_name,
                "download_maxsize": self.max_download_bytes,
                "download_warnsize": self.max_download_bytes,
                "handle_httpstatus_all": True,
            },
        )

    def _attachment_url(self, response):
        candidates = []
        for href in response.css("a[href]::attr(href)").getall():
            path = href.split("?", 1)[0].lower()
            if path.endswith((".xlsx", ".xls")):
                candidates.append(
                    (Path(path).suffix, urljoin(response.url, href))
                )
        for suffix in (".xlsx", ".xls"):
            for candidate_suffix, url in candidates:
                if candidate_suffix != suffix:
                    continue
                self._require_allowed_url(url)
                return url
        return None

    def _aqsc_detail_url(self, response):
        for href in response.css("a[href]::attr(href)").getall():
            url = urljoin(response.url, href)
            if (
                "www.aqsc.agri.cn/" in url
                and url.split("?", 1)[0].endswith((".htm", ".html"))
            ):
                self._require_allowed_url(url)
                return url
        return None

    def _require_allowed_url(self, url):
        host = _url_host(url)
        if not host:
            raise DisallowedUrl(f"url:invalid:{url}")
        allowed = any(
            host == domain or host.endswith(f".{domain}")
            for domain in self.allowed_domains
        )
        if not allowed:
            raise DisallowedUrl(f"url:domain_not_allowed:{host}")

    def _blocked_item(
        self,
        response,
        reason,
        *,
        source_url=None,
        locator=None,
    ):
        try:
            meta = response.meta
        except AttributeError:
            meta = {}
        long_term_url = meta.get("long_term_url") or response.url
        failure_url = source_url or response.url
        source_key = hashlib.sha1(
            failure_url.encode("utf-8")
        ).hexdigest()[:12]
        payload = {
            "source_item_id": (
                meta.get("announcement_id")
                or f"blocked:{source_key}"
            ),
            "title": (
                meta.get("title")
                or self._response_title(response)
                or failure_url
            ),
            "source_url": failure_url,
            "long_term_url": long_term_url,
            "detail_url": None,
            "detail_url_status": "missing",
            "locator": locator
            or f"carrier={long_term_url}; status={response.status}",
            "candidate_status": "blocked",
            "candidate_reason": reason,
            "mode": meta.get("mode", "live"),
            "extra": {
                "status_code": response.status,
                "failure_url": failure_url,
                "release_condition": (
                    "www.aqsc.agri.cn robots and attachment access must "
                    "return a collectable response"
                ),
            },
        }
        return item_from_mapping(
            payload,
            source_id=self.source_id,
            response=response,
        )

    @staticmethod
    def _response_title(response):
        try:
            return response.css("title::text").get()
        except Exception:
            return None
