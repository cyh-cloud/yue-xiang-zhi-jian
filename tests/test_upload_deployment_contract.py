# -*- coding: utf-8 -*-
"""上传与部署契约：共享上限、nginx 路由顺序、流式缓冲与媒体路径。"""

import os
import re
import sys
import unittest
import subprocess
from io import BytesIO
from unittest.mock import patch

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND = os.path.join(REPO_ROOT, "frontend")
BACKEND = os.path.join(REPO_ROOT, "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from shared.upload_limits import (  # noqa: E402
    MAX_UPLOAD_BYTES,
    MAX_UPLOAD_MEGABYTES,
    MAX_REQUEST_BYTES,
    MODEL_3D_EXTENSIONS,
)
from tools.render_nginx_config import render as render_nginx  # noqa: E402


def _read(*parts):
    with open(os.path.join(REPO_ROOT, *parts), encoding="utf-8") as handle:
        return handle.read()


def _nginx_locations(source):
    """Return location modifiers, paths and block bodies in file order."""
    locations = []
    pattern = re.compile(
        r"location\s+(?:=\s+|~\*?\s+|\^~\s+)?([^\s{]+)\s*\{", re.MULTILINE
    )
    for match in pattern.finditer(source):
        depth = 1
        offset = match.end()
        while offset < len(source) and depth:
            if source[offset] == "{":
                depth += 1
            elif source[offset] == "}":
                depth -= 1
            offset += 1
        locations.append((match.group(1), source[match.end():offset - 1]))
    return locations


class UploadLimitContractTest(unittest.TestCase):
    def test_shared_limit_is_50mb_and_flask_consumes_it(self):
        self.assertEqual(MAX_UPLOAD_BYTES, 50 * 1024 * 1024)
        self.assertEqual(MAX_UPLOAD_MEGABYTES, 50)
        self.assertGreater(MAX_REQUEST_BYTES, MAX_UPLOAD_BYTES)
        app_factory = _read("backend", "core", "app_factory.py")
        self.assertIn("MAX_CONTENT_LENGTH=MAX_REQUEST_BYTES", app_factory)

    def test_nginx_body_limit_matches_the_shared_limit(self):
        nginx = render_nginx(REPO_ROOT)
        matches = re.findall(r"client_max_body_size\s+(\d+)([kKmMgG]?)\s*;", nginx)
        self.assertEqual(matches, [("51", "m")])
        size = int(matches[0][0]) * 1024 * 1024
        self.assertGreaterEqual(size, MAX_REQUEST_BYTES)

    def test_nginx_template_renders_deterministically_without_placeholders(self):
        first = render_nginx(REPO_ROOT)
        second = render_nginx(REPO_ROOT)
        self.assertEqual(first, second)
        self.assertNotIn("{{", first)
        self.assertNotIn("REPO_ROOT", first)
        self.assertIn(REPO_ROOT.replace("\\", "/") + "/frontend/dist;", first)

    def test_nginx_ports_are_configurable_and_default_to_project_ports(self):
        rendered = render_nginx(REPO_ROOT, listen_port=8099, proxy_port=5001)
        self.assertIn("listen 8099;", rendered)
        self.assertIn("proxy_pass http://127.0.0.1:5001;", rendered)
        default = render_nginx(REPO_ROOT)
        self.assertIn("listen 8081;", default)
        self.assertIn("proxy_pass http://127.0.0.1:5000;", default)

    def test_frontend_prompt_reads_a_generated_shared_limit(self):
        target = os.path.join(FRONTEND, "src", "api", "uploadLimits.ts")
        with open(target, "rb") as handle:
            original = handle.read()
        self.addCleanup(self._restore_file, target, original)
        generate = subprocess.run(
            [sys.executable, os.path.join(REPO_ROOT, "tools", "sync_upload_limit.py")],
            cwd=REPO_ROOT,
            capture_output=True,
        )
        self.assertEqual(generate.returncode, 0, generate.stderr)
        with open(target, "rb") as handle:
            self.assertNotIn(b"\r\n", handle.read())
        with open(target, encoding="utf-8") as handle:
            generated = handle.read()
        self.assertIn(
            "export const MAX_REQUEST_BYTES = %d;" % MAX_REQUEST_BYTES,
            generated,
        )
        result = subprocess.run(
            [sys.executable, os.path.join(REPO_ROOT, "tools", "sync_upload_limit.py"), "--check"],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_upload_limit_check_accepts_windows_checkout_newlines(self):
        target = os.path.join(FRONTEND, "src", "api", "uploadLimits.ts")
        with open(target, "rb") as handle:
            original = handle.read()
        self.addCleanup(self._restore_file, target, original)
        with open(target, "wb") as handle:
            handle.write(original.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))

        result = subprocess.run(
            [sys.executable, os.path.join(REPO_ROOT, "tools", "sync_upload_limit.py"), "--check"],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_frontend_3d_extensions_are_generated_from_backend(self):
        target = os.path.join(FRONTEND, "src", "api", "uploadLimits.ts")
        with open(target, encoding="utf-8") as handle:
            generated = handle.read()
        self.assertIn(
            "export const MODEL_3D_EXTENSIONS = [%s] as const;"
            % ", ".join('"%s"' % extension for extension in MODEL_3D_EXTENSIONS),
            generated,
        )
        upload = _read("frontend", "src", "api", "upload.ts")
        self.assertIn(
            'import {\n  MAX_UPLOAD_BYTES,\n  MAX_UPLOAD_MEGABYTES,\n  MODEL_3D_EXTENSIONS,\n} from "./uploadLimits";',
            upload,
        )

    @staticmethod
    def _restore_file(path, content):
        with open(path, "wb") as handle:
            handle.write(content)

    def test_over_limit_request_returns_json_413_instead_of_html(self):
        from app import app
        client = app.test_client()
        login = client.post(
            "/api/auth/login",
            json={"username": "teacher_demo", "password": "123456"},
        )
        self.assertEqual(login.status_code, 200)
        session_id = login.get_json()["session_id"]

        original = app.config["MAX_CONTENT_LENGTH"]
        self.addCleanup(app.config.__setitem__, "MAX_CONTENT_LENGTH", original)
        app.config["MAX_CONTENT_LENGTH"] = 1024

        response = client.post(
            "/api/teacher/models-3d",
            data={"file": (BytesIO(b"x" * 2048), "too-large.glb")},
            content_type="multipart/form-data",
            headers={"X-Session-Id": session_id},
        )

        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.content_type, "application/json")
        self.assertEqual(response.get_json(), {
            "success": False,
            "code": "file_too_large",
            "message": "文件过大，上传文件不能超过 %dMB" % MAX_UPLOAD_MEGABYTES,
        })

    def test_multipart_overhead_does_not_count_against_the_file_limit(self):
        from app import app
        from db_connection import get_connection
        from db_domains import courses as courses_db
        from domains.teaching_support import routes as support_routes

        client = app.test_client()
        login = client.post(
            "/api/auth/login",
            json={"username": "teacher_demo", "password": "123456"},
        )
        session_id = login.get_json()["session_id"]

        original = app.config["MAX_CONTENT_LENGTH"]
        self.addCleanup(app.config.__setitem__, "MAX_CONTENT_LENGTH", original)
        app.config["MAX_CONTENT_LENGTH"] = 5 * 1024

        def cleanup():
            conn = get_connection()
            rows = conn.execute(
                "SELECT id, file_path FROM models_3d WHERE title = ?",
                ("__T_UPLOAD_BOUNDARY__",),
            ).fetchall()
            conn.close()
            for row in rows:
                filepath = courses_db.delete_model_3d(row["id"])
                if filepath:
                    full = os.path.join(REPO_ROOT, filepath)
                    if os.path.exists(full):
                        os.remove(full)

        self.addCleanup(cleanup)
        with patch.object(support_routes, "_MODEL_3D_MAX_BYTES", 4 * 1024):
            accepted = client.post(
                "/api/teacher/models-3d",
                data={
                    "file": (BytesIO(b"x" * (4 * 1024)), "boundary.glb"),
                    "title": "__T_UPLOAD_BOUNDARY__",
                },
                content_type="multipart/form-data",
                headers={"X-Session-Id": session_id},
            )
            rejected = client.post(
                "/api/teacher/models-3d",
                data={
                    "file": (BytesIO(b"x" * (4 * 1024 + 1)), "boundary.glb"),
                    "title": "__T_UPLOAD_BOUNDARY__",
                },
                content_type="multipart/form-data",
                headers={"X-Session-Id": session_id},
            )

        self.assertEqual(accepted.status_code, 200, accepted.data)
        self.assertTrue(accepted.get_json()["success"])
        self.assertEqual(rejected.status_code, 400, rejected.data)
        self.assertEqual(rejected.get_json()["code"], "file_too_large")

    def test_launcher_opens_the_flask_health_endpoint_not_the_spa_root(self):
        from run import startup_url

        self.assertEqual(
            startup_url(5000),
            "http://localhost:5000/api/health",
        )
        self.assertNotEqual(startup_url(5000), "http://localhost:5000")


class NginxRoutingContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = render_nginx(REPO_ROOT)
        cls.locations = _nginx_locations(cls.source)

    def test_api_media_and_spa_locations_exist(self):
        paths = [path for path, _ in self.locations]
        for expected in ("/api/", "/uploads/", "/images/", "/"):
            self.assertIn(expected, paths)

    def test_specific_locations_precede_spa_fallback(self):
        paths = [path for path, _ in self.locations]
        fallback = paths.index("/")
        for expected in ("/api/", "/uploads/", "/images/", "/assets/"):
            self.assertLess(paths.index(expected), fallback, expected)

    def test_streaming_api_disables_buffering_but_other_api_does_not(self):
        blocks = dict(self.locations)
        stream = next(
            (body for path, body in self.locations
             if path.startswith("/api/") and "ask/stream" in path),
            None,
        )
        self.assertIsNotNone(stream, "缺少 AI 流式接口的 nginx location")
        self.assertRegex(stream, r"proxy_buffering\s+off\s*;")
        self.assertRegex(blocks["/api/"], r"proxy_buffering\s+on\s*;")
        self.assertIn("proxy_read_timeout 120s;", stream)

    def test_media_locations_alias_repository_roots(self):
        blocks = dict(self.locations)
        project = REPO_ROOT.replace("\\", "/")
        self.assertIn("alias %s/uploads/;" % project, blocks["/uploads/"])
        self.assertIn("alias %s/images/;" % project, blocks["/images/"])


if __name__ == "__main__":
    unittest.main()
