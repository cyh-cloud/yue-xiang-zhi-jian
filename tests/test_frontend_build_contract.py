# -*- coding: utf-8 -*-
"""Vue SPA 构建与部署契约的机械检查。"""

import os
import re
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND = os.path.join(REPO_ROOT, "frontend")
APP_FACTORY = os.path.join(REPO_ROOT, "backend", "core", "app_factory.py")
BACKEND = os.path.join(REPO_ROOT, "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from shared.upload_limits import (  # noqa: E402
    MAX_REQUEST_MEGABYTES,
    MAX_UPLOAD_MEGABYTES,
)
from tools.render_nginx_config import render as render_nginx  # noqa: E402


class FrontendBuildContractTest(unittest.TestCase):
    def test_frontend_has_a_single_spa_entry(self):
        index = os.path.join(FRONTEND, "index.html")
        with open(index, encoding="utf-8") as handle:
            source = handle.read()
        self.assertEqual(len(re.findall(r'<div id="app"></div>', source)), 1)
        self.assertIn('src="/src/main.ts"', source)

    def test_router_uses_history_mode_and_legacy_redirects(self):
        with open(os.path.join(FRONTEND, "src", "router", "index.ts"), encoding="utf-8") as handle:
            source = handle.read()
        self.assertIn("createWebHistory()", source)
        with open(
            os.path.join(FRONTEND, "src", "router", "legacyRedirects.ts"),
            encoding="utf-8",
        ) as handle:
            redirects = handle.read()
        self.assertIn('"/teacher-panel.html": "/teacher"', redirects)
        self.assertIn('"/agriculture.html": "/agriculture"', redirects)

    def test_vite_proxy_reads_backend_port_from_root_env(self):
        with open(os.path.join(FRONTEND, "vite.config.ts"), encoding="utf-8") as handle:
            source = handle.read()
        self.assertIn("loadEnv(mode, repoRoot", source)
        self.assertIn("env.PORT", source)
        self.assertNotIn('target: "http://127.0.0.1:5000"', source)

    def test_nginx_serves_spa_media_and_api(self):
        source = render_nginx(REPO_ROOT)
        self.assertIn("try_files $uri $uri/ /index.html;", source)
        self.assertIn("location /uploads/", source)
        self.assertIn("location /images/", source)
        self.assertIn("location /api/", source)
        self.assertIn("client_max_body_size %dm;" % MAX_REQUEST_MEGABYTES, source)

    def test_backend_upload_limit_matches_nginx(self):
        with open(APP_FACTORY, encoding="utf-8") as handle:
            source = handle.read()
        self.assertIn("MAX_CONTENT_LENGTH=MAX_REQUEST_BYTES", source)
        with open(
            os.path.join(REPO_ROOT, "backend", "shared", "upload_limits.py"),
            encoding="utf-8",
        ) as handle:
            limits = handle.read()
        self.assertIn("MAX_UPLOAD_BYTES = 50 * 1024 * 1024", limits)
        nginx = render_nginx(REPO_ROOT)
        self.assertIn("client_max_body_size %dm;" % MAX_REQUEST_MEGABYTES, nginx)
        with open(os.path.join(REPO_ROOT, "tests", "test_shared_layer.py"), encoding="utf-8") as handle:
            shared_test = handle.read()
        self.assertIn("MAX_REQUEST_BYTES", shared_test)

    def test_upload_limit_contract_is_one_shared_value(self):
        nginx = render_nginx(REPO_ROOT)
        self.assertIn("client_max_body_size %dm;" % MAX_REQUEST_MEGABYTES, nginx)
        with open(
            os.path.join(FRONTEND, "src", "api", "uploadLimits.ts"),
            encoding="utf-8",
        ) as handle:
            frontend = handle.read()
        self.assertIn("export const MAX_UPLOAD_BYTES = %d;" % (50 * 1024 * 1024), frontend)

    def test_community_length_limits_match_frontend(self):
        from domains.community import routes as community_routes

        with open(
            os.path.join(FRONTEND, "src", "api", "community.ts"),
            encoding="utf-8",
        ) as handle:
            frontend = handle.read()
        for name in (
            "DISCUSSION_TITLE_MAX_LEN",
            "DISCUSSION_CONTENT_MAX_LEN",
            "COMMENT_CONTENT_MAX_LEN",
        ):
            self.assertIn(
                "export const %s = %d;" % (name, getattr(community_routes, name)),
                frontend,
            )


if __name__ == "__main__":
    unittest.main()
