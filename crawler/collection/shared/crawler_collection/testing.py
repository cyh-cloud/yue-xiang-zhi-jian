"""Deterministic helpers for project-level fixture replay tests."""

from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


FIXTURE_ROOT = Path(__file__).resolve().parents[3] / "tests" / "fixtures"


def source_fixture_dir(source_id):
    evidence_dir = FIXTURE_ROOT / "evidence" / source_id
    if not evidence_dir.is_dir():
        raise ValueError(
            f"fixture directory must be {evidence_dir.as_posix()}"
        )
    return evidence_dir


class _FixtureRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlparse(self.path).path
        route = self.server.routes.get(path)
        if route is None:
            status, content_type, body = (
                404,
                "text/plain; charset=utf-8",
                b"fixture route not found",
            )
        else:
            status, content_type, body = route
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return


class FixtureHTTPServer:
    """Serve fixture bytes to a real Scrapy process over localhost."""

    def __init__(self):
        self.routes = {
            "/robots.txt": (
                200,
                "text/plain; charset=utf-8",
                b"User-agent: *\nAllow: /\n",
            )
        }
        self._server = None
        self._thread = None

    def __enter__(self):
        self._server = ThreadingHTTPServer(
            ("127.0.0.1", 0), _FixtureRequestHandler
        )
        self._server.routes = self.routes
        self._thread = threading.Thread(
            target=self._server.serve_forever, daemon=True
        )
        self._thread.start()
        return self

    def __exit__(self, exc_type, exc, traceback):
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5)

    @property
    def base_url(self):
        if self._server is None:
            raise RuntimeError("fixture server is not running")
        return f"http://127.0.0.1:{self._server.server_port}"

    def add_route(self, path, body, *, content_type, status=200):
        if not path.startswith("/"):
            raise ValueError("fixture route path must start with /")
        self.routes[path] = (status, content_type, bytes(body))

    def url(self, path):
        return f"{self.base_url}{path}"
