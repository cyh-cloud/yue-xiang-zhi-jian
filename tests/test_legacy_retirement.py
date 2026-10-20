# -*- coding: utf-8 -*-
"""T24: the retired multi-page frontend must stay out of the active runtime."""

import os
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(REPO_ROOT, "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

LEGACY_ROOT = os.path.join(REPO_ROOT, "legacy", "reference")
ACTIVE_MPA_FILES = (
    "index.html",
    "agriculture.html",
    "ecommerce.html",
    "crafts.html",
    "resources.html",
    "employment.html",
    "case-detail.html",
    "teacher.html",
    "teacher-panel.html",
    "admin.html",
    "government.html",
    "enterprise.html",
    "operator.html",
    "script.js",
    "portal.js",
    "portal.css",
    "sw.js",
)


def _read(*parts):
    with open(os.path.join(REPO_ROOT, *parts), encoding="utf-8") as handle:
        return handle.read()


class LegacyReferenceTest(unittest.TestCase):
    def test_old_pages_are_not_part_of_the_active_tree(self):
        for name in ACTIVE_MPA_FILES:
            with self.subTest(name=name):
                self.assertFalse(
                    os.path.exists(os.path.join(REPO_ROOT, name)),
                    "%s must move under legacy/reference" % name,
                )
        self.assertFalse(os.path.exists(os.path.join(REPO_ROOT, "js", "core.js")))

    def test_reference_copy_is_present_and_explicitly_read_only(self):
        self.assertTrue(os.path.isdir(LEGACY_ROOT))
        readme = _read("legacy", "reference", "README.md")
        self.assertIn("只读", readme)
        self.assertIn("不参与", readme)
        for name in ("index.html", "operator.html", "script.js", "sw.js"):
            with self.subTest(name=name):
                self.assertTrue(
                    os.path.isfile(os.path.join(LEGACY_ROOT, "mpa", name)),
                    "legacy reference is missing %s" % name,
                )

    def test_spa_keeps_its_shared_css_outside_the_reference_copy(self):
        self.assertFalse(os.path.exists(os.path.join(REPO_ROOT, "styles.css")))
        self.assertTrue(
            os.path.isfile(
                os.path.join(
                    REPO_ROOT, "frontend", "src", "styles", "legacy-public.css"
                )
            )
        )
        main = _read("frontend", "src", "main.ts")
        self.assertIn('"./styles/legacy-public.css"', main)
        self.assertNotIn('"../../styles.css"', main)


class FlaskFrontendRetirementTest(unittest.TestCase):
    def setUp(self):
        from app import app

        self.client = app.test_client()

    def test_flask_no_longer_serves_the_mpa(self):
        for path in (
            "/",
            "/index.html",
            "/styles.css",
            "/script.js",
            "/sw.js",
            "/js/core.js",
            "/crafts.html",
            "/case-detail.html",
        ):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 404, path)
                self.assertEqual(
                    response.get_json(),
                    {"success": False, "code": "not_found", "message": "文件不存在"},
                )

    def test_flask_still_serves_media_for_nginx_and_the_test_proxy(self):
        response = self.client.get("/images/pest/citrus_psyllid.jpg")
        self.assertEqual(response.status_code, 200)
        self.assertGreater(len(response.data), 0)
        response.close()


class ActiveTestConfigurationTest(unittest.TestCase):
    def test_old_e2e_suite_is_not_runnable_from_the_active_location(self):
        self.assertFalse(
            os.path.exists(os.path.join(REPO_ROOT, "e2e", "playwright.config.js"))
        )
        self.assertFalse(os.path.exists(os.path.join(REPO_ROOT, "e2e", "specs")))
        launcher = _read("e2e", "serve.py")
        self.assertNotIn("E2E_FRONTEND", launcher)
        self.assertNotIn('FRONTEND_MODE == "legacy"', launcher)

    def test_active_frontend_has_no_migration_placeholders(self):
        source = _read("frontend", "src", "router", "routes.ts")
        self.assertNotIn("PlaceholderView", source)
        self.assertNotIn("BackofficeSectionView", source)
        for phrase in ("业务页面将在后续阶段迁移", "区块已预留", "等待业务迁移"):
            with self.subTest(phrase=phrase):
                self.assertNotIn(
                    phrase,
                    _read("frontend", "src", "views", "PlaceholderView.vue")
                    if os.path.exists(
                        os.path.join(
                            REPO_ROOT,
                            "frontend",
                            "src",
                            "views",
                            "PlaceholderView.vue",
                        )
                    )
                    else "",
                )

    def test_docs_describe_one_runtime_and_six_roles(self):
        agents = _read("AGENTS.md")
        glossary = _read("GLOSSARY.md")
        structure = _read("PROJECT_STRUCTURE.md")
        self.assertIn("六类角色", agents)
        self.assertIn("Vue 单页面前端", agents)
        self.assertIn("nginx", glossary)
        self.assertIn("nginx", structure)
        self.assertNotIn("没有反向代理", glossary)
        self.assertNotIn("没有反向代理", structure)
        self.assertNotIn("多页面前端的 HTML", structure)


if __name__ == "__main__":
    unittest.main()
