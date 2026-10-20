# -*- coding: utf-8 -*-
"""SPA 真实整站测试链的机械契约。

只检查启动器和配置承诺的组合关系：一条命令先构建，再由同一个 Python 入口拉起真实
Flask 与临时数据库，静态入口代理 /api 并在结束后清理。浏览器行为由 frontend/e2e
覆盖，这里不替它断言页面内容。
"""

import json
import os
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND = os.path.join(REPO_ROOT, "frontend")


class FrontendE2EStackContractTest(unittest.TestCase):
    def read(self, *parts):
        with open(os.path.join(REPO_ROOT, *parts), encoding="utf-8") as handle:
            return handle.read()

    def test_frontend_e2e_builds_before_starting_the_stack(self):
        package = json.loads(self.read("frontend", "package.json"))
        self.assertEqual(
            package["scripts"]["test:e2e"],
            "npm run build && playwright test && playwright test --config playwright.backend-unavailable.config.ts",
        )

    def test_one_static_entry_starts_real_flask_with_temp_database(self):
        config = self.read("frontend", "playwright.config.ts")
        launcher = self.read("e2e", "serve.py")

        self.assertIn('command: "python e2e/serve.py"', config)
        self.assertIn("YUEXIANG_DB: DB_PATH", config)
        self.assertIn("process.env.YUEXIANG_BASELINE_DB", config)
        self.assertNotIn("E2E_FRONTEND", config)
        self.assertIn("yuexiang-spa-e2e-", config)
        self.assertNotIn("npm run preview", config)

        self.assertIn("frontend", launcher)
        self.assertIn('"dist"', launcher)
        self.assertIn('"/api/"', launcher)
        self.assertIn("make_server(", launcher)
        self.assertIn("db_init.init_db()", launcher)
        self.assertIn("frontend/dist", config + launcher)
        self.assertIn("E2E_START_API", launcher)

    def test_static_entry_proxies_media_like_production_deployment(self):
        launcher = self.read("e2e", "serve.py")
        self.assertIn('prefixes = ("/uploads/", "/images/")', launcher)
        self.assertIn("def _proxy_media", launcher)

    def test_launcher_reuses_the_existing_baseline_and_temp_database(self):
        launcher = self.read("e2e", "serve.py")
        self.assertIn('os.environ["YUEXIANG_DB"]', launcher)
        self.assertIn('data" / "baseline.db', launcher)
        self.assertIn("shutil.copyfile(baseline, db)", launcher)
        self.assertEqual(launcher.count("db_init.init_db()"), 1)

    def test_retired_mpa_has_no_active_e2e_mode(self):
        launcher = self.read("e2e", "serve.py")
        self.assertNotIn("E2E_FRONTEND", launcher)
        self.assertNotIn('FRONTEND_MODE == "legacy"', launcher)
        self.assertFalse(
            os.path.exists(
                os.path.join(REPO_ROOT, "e2e", "playwright.config.js")
            )
        )

    def test_backend_unavailable_runs_in_a_dedicated_proxy_config(self):
        specs = self.read("frontend", "e2e-unavailable", "backend-unavailable.spec.ts")
        config = self.read("frontend", "playwright.backend-unavailable.config.ts")
        launcher = self.read("e2e", "serve.py")
        self.assertIn('code: "backend_unreachable"', specs)
        self.assertIn('E2E_START_API: "0"', config)
        self.assertIn("process.env.YUEXIANG_BASELINE_DB", config)
        self.assertIn('E2E_START_API', launcher)
        self.assertNotIn("test.skip", specs)
        self.assertNotIn("route.abort", specs)

    def test_teardown_uses_the_same_isolated_directory(self):
        teardown = self.read("e2e", "global-teardown.js")
        self.assertIn("process.env.E2E_TEMP_DIR", teardown)
        self.assertIn("fs.rmSync", teardown)


if __name__ == "__main__":
    unittest.main()
