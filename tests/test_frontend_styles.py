# -*- coding: utf-8 -*-
"""Final CSS ownership contract for the active frontend."""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FRONTEND = REPO_ROOT / "frontend"
STYLES = FRONTEND / "src" / "styles"
REFERENCE = REPO_ROOT / "legacy" / "reference" / "frontend" / "legacy-public.css"
CHECKER = REPO_ROOT / "tools" / "check_frontend_styles.py"


class FrontendStyleContractTest(unittest.TestCase):
    def test_style_checker_passes_on_real_repo(self):
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        result = subprocess.run(
            [sys.executable, str(REPO_ROOT / "tools" / "check_frontend_styles.py")],
            capture_output=True,
            env=env,
        )
        stdout = result.stdout.decode("utf-8", errors="replace")
        self.assertEqual(result.returncode, 0, stdout)
        self.assertIn("CSS 样式检查通过", stdout)

    def test_entry_loads_layers_without_legacy_sheet(self):
        main = (FRONTEND / "src" / "main.ts").read_text(encoding="utf-8")
        tokens = main.index('"./styles/tokens.css"')
        base = main.index('"./styles/base.css"')
        components = main.index('"./styles/components.css"')
        self.assertLess(tokens, base)
        self.assertLess(base, components)
        self.assertNotIn("legacy-public.css", main)

    def test_active_legacy_sheet_is_gone_and_reference_is_marked(self):
        self.assertFalse((STYLES / "legacy-public.css").exists())
        self.assertTrue(REFERENCE.is_file())
        header = REFERENCE.read_text(encoding="utf-8")[:1600]
        self.assertIn("历史参照", header)
        self.assertIn("禁止活动代码引用", header)

    def test_components_own_shared_primitives_without_global_tokens(self):
        styles = (STYLES / "components.css").read_text(encoding="utf-8")
        for marker in (
            ".message-center-wrap",
            ".message-dropdown",
            ".conversation-send",
            ".modal-overlay",
            ".modal-content",
            ".modal-header",
            ".section-title",
            ".tab-content",
            ".card-section",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, styles)
        for marker in (
            ".backoffice-button",
            ".backoffice-field",
            ".backoffice-status",
            ".backoffice-card",
            ".backoffice-table",
            ".backoffice-feedback",
            ".backoffice-state",
            ".backoffice-modal",
        ):
            with self.subTest(backoffice_marker=marker):
                self.assertNotIn(marker, styles)
        self.assertNotIn("!important", styles)
        self.assertNotRegex(styles, r"(?m)^\s*:root\s*\{")
        self.assertNotRegex(styles, r"\[\s*data-role\b")
        self.assertRegex(styles, r"var\(--")
        self.assertNotRegex(styles, r"(?i)startup")
        for dead_selector in (
            ".admin-sub-tabs",
            ".sub-tab-btn",
            ".role-portal-",
            ".data-table",
            ".example-btn",
            ".progress-bar",
            ".auth-tabs",
        ):
            with self.subTest(dead_selector=dead_selector):
                self.assertNotIn(dead_selector, styles)

    def test_tokens_base_and_shell_have_expected_ownership(self):
        tokens = (STYLES / "tokens.css").read_text(encoding="utf-8")
        base = (STYLES / "base.css").read_text(encoding="utf-8")
        shell = (STYLES / "public-shell.css").read_text(encoding="utf-8")
        backoffice = (STYLES / "backoffice.css").read_text(encoding="utf-8")
        self.assertIn("--color-brand", tokens)
        self.assertIn('[data-theme="dark"]', tokens)
        self.assertIn("--surface-canvas", tokens)
        self.assertIn("box-sizing: border-box", base)
        self.assertIn(":focus-visible", base)
        self.assertIn("prefers-reduced-motion", base)
        self.assertIn(".public-shell", shell)
        self.assertIn(
            ".backoffice-shell",
            backoffice,
        )
        for marker in (
            ".backoffice-button",
            ".backoffice-field",
            ".backoffice-status",
            ".backoffice-card",
            ".backoffice-table",
            ".backoffice-feedback",
            ".backoffice-state",
            ".backoffice-modal",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, backoffice)
        self.assertIn("@media print", backoffice)
        self.assertIn(".backoffice-topbar", backoffice)
        self.assertIn(".backoffice-sidebar", backoffice)

    def test_public_shell_has_no_retired_sidebar_or_page_tokens(self):
        shell = (STYLES / "public-shell.css").read_text(encoding="utf-8")
        for marker in (
            ".bewly-",
            "#agriculture-tab",
            "#ecommerce-tab",
            "#employment-tab",
        ):
            with self.subTest(marker=marker):
                self.assertNotIn(marker, shell)


class CheckerCliFixtureTest(unittest.TestCase):
    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.root = Path(temp_dir.name)
        source = self.root / "frontend" / "src"
        source.mkdir(parents=True)
        shutil.copytree(STYLES, source / "styles")
        shutil.copy2(FRONTEND / "src" / "main.ts", source / "main.ts")

    def run_checker(self):
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        result = subprocess.run(
            [
                sys.executable,
                str(CHECKER),
                "--root",
                str(self.root),
            ],
            capture_output=True,
            env=env,
        )
        stdout = result.stdout.decode("utf-8", errors="replace")
        stderr = result.stderr.decode("utf-8", errors="replace")
        return result, stdout, stderr

    def test_active_entry_legacy_import_is_rejected(self):
        entry = self.root / "frontend" / "src" / "main.ts"
        entry.write_text(
            entry.read_text(encoding="utf-8").rstrip()
            + '\nimport "./styles/legacy-public.css";\n',
            encoding="utf-8",
        )
        import_line = len(entry.read_text(encoding="utf-8").splitlines())

        result, stdout, stderr = self.run_checker()

        self.assertEqual(result.returncode, 1, stdout + stderr)
        self.assertIn(
            f"[legacy-style-import] frontend/src/main.ts:{import_line}",
            stdout,
        )
        self.assertIn("-> frontend/src/styles/legacy-public.css", stdout)

    def test_cross_page_private_style_import_is_rejected(self):
        home = self.root / "frontend" / "src" / "views" / "home"
        crafts = self.root / "frontend" / "src" / "views" / "crafts"
        home.mkdir(parents=True)
        crafts.mkdir(parents=True)
        (crafts / "CraftsView.css").write_text(
            ".crafts-page {\n  color: black;\n}\n",
            encoding="utf-8",
        )
        import_statement = 'import "../crafts/CraftsView.css";'
        (home / "HomeView.vue").write_text(
            '<template>\n'
            '  <main class="home-page">Home</main>\n'
            '</template>\n'
            '\n'
            '<script setup lang="ts">\n'
            f'{import_statement}\n'
            '</script>\n',
            encoding="utf-8",
        )
        import_line = (
            (home / "HomeView.vue")
            .read_text(encoding="utf-8")
            .splitlines()
            .index(import_statement)
            + 1
        )

        result, stdout, stderr = self.run_checker()

        self.assertEqual(result.returncode, 1, stdout + stderr)
        self.assertIn(
            "[cross-page-style-import] "
            f"frontend/src/views/home/HomeView.vue:{import_line}",
            stdout,
        )
        self.assertIn("-> frontend/src/views/crafts/CraftsView.css", stdout)
        self.assertIn("来源域=home，目标域=crafts", stdout)

    def test_global_override_reports_key_selector(self):
        home = self.root / "frontend" / "src" / "views" / "home"
        home.mkdir(parents=True)
        selector = "body .home-page"
        (home / "HomeView.vue").write_text(
            '<template>\n'
            '  <main class="home-page">Home</main>\n'
            '</template>\n'
            '\n'
            '<style scoped>\n'
            f'{selector} {{\n'
            '  margin: 0;\n'
            '}\n'
            '</style>\n',
            encoding="utf-8",
        )
        selector_line = (
            (home / "HomeView.vue")
            .read_text(encoding="utf-8")
            .splitlines()
            .index(f"{selector} {{")
            + 1
        )

        result, stdout, stderr = self.run_checker()

        self.assertEqual(result.returncode, 1, stdout + stderr)
        self.assertIn(
            "[page-universal-override] "
            f"frontend/src/views/home/HomeView.vue:{selector_line}",
            stdout,
        )
        self.assertIn(f"命中选择器：{selector}", stdout)

    def test_shared_layer_root_and_global_overrides_are_rejected(self):
        components = self.root / "frontend" / "src" / "styles" / "components.css"
        selectors = (
            ("html[data-large-text] .btn", ".btn"),
            ("body[data-page] .main-content", ".main-content"),
        )
        components.write_text(
            components.read_text(encoding="utf-8").rstrip()
            + "\n\n/* fixture: shared layer root overrides */\n"
            + "\n".join(
                "%s {\n  margin-left: 1px;\n}" % selector
                for selector, _ in selectors
            )
            + "\n",
            encoding="utf-8",
        )
        lines = components.read_text(encoding="utf-8").splitlines()
        selector_lines = {
            selector: lines.index(f"{selector} {{") + 1 for selector, _ in selectors
        }

        result, stdout, stderr = self.run_checker()

        self.assertEqual(result.returncode, 1, stdout + stderr)
        for selector, _ in selectors:
            with self.subTest(selector=selector):
                self.assertIn(
                    "[shared-root-override] "
                    f"frontend/src/styles/components.css:{selector_lines[selector]}",
                    stdout,
                )
                self.assertIn(f"命中选择器：{selector}", stdout)
                self.assertIn(
                    "建议归属层：base.css 或对应外壳样式",
                    stdout,
                )

    def test_shared_layer_hero_selectors_are_rejected(self):
        components = self.root / "frontend" / "src" / "styles" / "components.css"
        selectors = (
            ".hero",
            ".hero-stats",
            ".stat-number",
            ".scroll-nav-hint",
        )
        components.write_text(
            components.read_text(encoding="utf-8").rstrip()
            + "\n\n/* fixture: homepage selectors in shared layer */\n"
            + "\n".join(
                "%s {\n  display: block;\n}" % selector
                for selector in selectors
            )
            + "\n",
            encoding="utf-8",
        )
        lines = components.read_text(encoding="utf-8").splitlines()
        selector_lines = {
            selector: lines.index(f"{selector} {{") + 1
            for selector in selectors
        }

        result, stdout, stderr = self.run_checker()

        self.assertEqual(result.returncode, 1, stdout + stderr)
        for selector in selectors:
            with self.subTest(selector=selector):
                self.assertIn(
                    "[shared-page-selector] "
                    f"frontend/src/styles/components.css:{selector_lines[selector]}",
                    stdout,
                )
                self.assertIn(f"命中选择器：{selector}", stdout)
                self.assertIn("建议归属层：frontend/src/views/home/home.css", stdout)

    def test_retired_startup_selectors_are_rejected_in_shared_layer(self):
        components = self.root / "frontend" / "src" / "styles" / "components.css"
        selector = '[data-theme="dark"] .startup-overview-card'
        components.write_text(
            components.read_text(encoding="utf-8").rstrip()
            + "\n\n/* fixture: retired startup selectors in shared layer */\n"
            + f"{selector} {{\n  display: block;\n}}\n",
            encoding="utf-8",
        )
        selector_line = (
            components.read_text(encoding="utf-8").splitlines().index(f"{selector} {{")
            + 1
        )

        result, stdout, stderr = self.run_checker()

        self.assertEqual(result.returncode, 1, stdout + stderr)
        self.assertIn(
            "[shared-page-selector] "
            f"frontend/src/styles/components.css:{selector_line}",
            stdout,
        )
        self.assertIn(f"命中选择器：{selector}", stdout)
        self.assertIn("建议归属层：frontend/src/views/home/home.css", stdout)

    def test_agriculture_selectors_are_rejected_in_shared_layer(self):
        components = self.root / "frontend" / "src" / "styles" / "components.css"
        selector = '[data-theme="dark"] .pest-crop-btn.active'
        components.write_text(
            components.read_text(encoding="utf-8").rstrip()
            + "\n\n/* fixture: agriculture selector in shared layer */\n"
            + f"{selector} {{\n  display: block;\n}}\n",
            encoding="utf-8",
        )
        selector_line = (
            components.read_text(encoding="utf-8").splitlines().index(f"{selector} {{")
            + 1
        )

        result, stdout, stderr = self.run_checker()

        self.assertEqual(result.returncode, 1, stdout + stderr)
        self.assertIn(
            "[shared-page-selector] "
            f"frontend/src/styles/components.css:{selector_line}",
            stdout,
        )
        self.assertIn(f"命中选择器：{selector}", stdout)
        self.assertIn(
            "建议归属层：frontend/src/views/agriculture/agriculture.css",
            stdout,
        )

    def test_ecommerce_selectors_are_rejected_in_shared_layer(self):
        components = self.root / "frontend" / "src" / "styles" / "components.css"
        selectors = (
            ".copywriting-panel",
            ".copywriting-stepper",
            ".copywriting-compare-card",
            ".training-submit-info",
            ".live-badge",
            ".comment-user",
            ".ec-tool-note",
        )
        components.write_text(
            components.read_text(encoding="utf-8").rstrip()
            + "\n\n/* fixture: ecommerce selectors in shared layer */\n"
            + "\n".join(
                "%s {\n  display: block;\n}" % selector
                for selector in selectors
            )
            + "\n",
            encoding="utf-8",
        )
        lines = components.read_text(encoding="utf-8").splitlines()
        selector_lines = {
            selector: lines.index(f"{selector} {{") + 1
            for selector in selectors
        }

        result, stdout, stderr = self.run_checker()

        self.assertEqual(result.returncode, 1, stdout + stderr)
        for selector in selectors:
            with self.subTest(selector=selector):
                self.assertIn(
                    "[shared-page-selector] "
                    f"frontend/src/styles/components.css:{selector_lines[selector]}",
                    stdout,
                )
                self.assertIn(f"命中选择器：{selector}", stdout)
                self.assertIn(
                    "建议归属层：frontend/src/views/ecommerce/ecommerce.css",
                    stdout,
                )

    def test_shared_comment_primitive_remains_allowed(self):
        components = self.root / "frontend" / "src" / "styles" / "components.css"
        selector = ".comment-item"
        components.write_text(
            components.read_text(encoding="utf-8").rstrip()
            + "\n\n/* fixture: real shared comment primitive */\n"
            + f"{selector} {{\n  display: block;\n}}\n",
            encoding="utf-8",
        )

        result, stdout, stderr = self.run_checker()

        self.assertEqual(result.returncode, 0, stdout + stderr)

    def test_backoffice_primitives_are_rejected_in_shared_layer(self):
        components = self.root / "frontend" / "src" / "styles" / "components.css"
        selectors = (
            ".backoffice-button",
            ".backoffice-status.is-active",
            ".backoffice-modal-head h2",
        )
        components.write_text(
            components.read_text(encoding="utf-8").rstrip()
            + "\n\n/* fixture: backoffice primitives in shared layer */\n"
            + "\n".join(
                "%s {\n  display: block;\n}" % selector
                for selector in selectors
            )
            + "\n",
            encoding="utf-8",
        )
        lines = components.read_text(encoding="utf-8").splitlines()
        selector_lines = {
            selector: lines.index(f"{selector} {{") + 1
            for selector in selectors
        }

        result, stdout, stderr = self.run_checker()

        self.assertEqual(result.returncode, 1, stdout + stderr)
        for selector in selectors:
            with self.subTest(selector=selector):
                self.assertIn(
                    "[shared-backoffice-selector] "
                    f"frontend/src/styles/components.css:{selector_lines[selector]}",
                    stdout,
                )
                self.assertIn(f"命中选择器：{selector}", stdout)
                self.assertIn(
                    "建议归属层：frontend/src/styles/backoffice.css",
                    stdout,
                )

    def test_page_level_universal_override_has_distinct_failure_kind(self):
        home = self.root / "frontend" / "src" / "views" / "home"
        home.mkdir(parents=True)
        selector = "body .home-page"
        (home / "HomeView.vue").write_text(
            '<template>\n'
            '  <main class="home-page">Home</main>\n'
            '</template>\n'
            '\n'
            '<style scoped>\n'
            f'{selector} {{\n'
            '  margin: 0;\n'
            '}\n'
            '</style>\n',
            encoding="utf-8",
        )
        selector_line = 6

        result, stdout, stderr = self.run_checker()

        self.assertEqual(result.returncode, 1, stdout + stderr)
        self.assertIn(
            "[page-universal-override] "
            f"frontend/src/views/home/HomeView.vue:{selector_line}",
            stdout,
        )
        self.assertNotIn("[universal-global-override]", stdout)
        self.assertIn(f"命中选择器：{selector}", stdout)
        self.assertIn(
            "建议归属层：页面根选择器或对应外壳根节点",
            stdout,
        )

    def test_remaining_page_selectors_are_rejected_in_shared_layer(self):
        components = self.root / "frontend" / "src" / "styles" / "components.css"
        selectors = (
            (".example-btn", "frontend/src/views/agriculture/agriculture.css"),
            (".product-icon", "frontend/src/views/agriculture/agriculture.css"),
            (".progress-bar", "frontend/src/views/ecommerce/ecommerce.css"),
            (".auth-tabs", "frontend/src/views/login/login.css"),
        )
        components.write_text(
            components.read_text(encoding="utf-8").rstrip()
            + "\n\n/* fixture: remaining page selectors in shared layer */\n"
            + "\n".join(
                "%s {\n  display: block;\n}" % selector
                for selector, _ in selectors
            )
            + "\n",
            encoding="utf-8",
        )
        lines = components.read_text(encoding="utf-8").splitlines()
        selector_lines = {
            selector: lines.index(f"{selector} {{") + 1
            for selector, _ in selectors
        }

        result, stdout, stderr = self.run_checker()

        self.assertEqual(result.returncode, 1, stdout + stderr)
        for selector, owner in selectors:
            with self.subTest(selector=selector):
                self.assertIn(
                    "[shared-page-selector] "
                    f"frontend/src/styles/components.css:{selector_lines[selector]}",
                    stdout,
                )
                self.assertIn(f"命中选择器：{selector}", stdout)
                self.assertIn(f"建议归属层：{owner}", stdout)


if __name__ == "__main__":
    unittest.main()
