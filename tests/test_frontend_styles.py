# -*- coding: utf-8 -*-
"""Final CSS ownership contract for the active frontend."""

import os
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FRONTEND = REPO_ROOT / "frontend"
STYLES = FRONTEND / "src" / "styles"
REFERENCE = REPO_ROOT / "legacy" / "reference" / "frontend" / "legacy-public.css"


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
            ".backoffice-button",
            ".backoffice-field",
            ".backoffice-card",
            ".backoffice-table",
            ".backoffice-feedback",
            ".backoffice-state",
            ".backoffice-modal",
            ".message-center-wrap",
            ".message-dropdown",
            ".conversation-send",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, styles)
        self.assertNotIn("!important", styles)
        self.assertNotRegex(styles, r"(?m)^\s*:root\s*\{")
        self.assertNotRegex(styles, r"\[\s*data-role\b")
        self.assertRegex(styles, r"var\(--")

    def test_tokens_base_and_shell_have_expected_ownership(self):
        tokens = (STYLES / "tokens.css").read_text(encoding="utf-8")
        base = (STYLES / "base.css").read_text(encoding="utf-8")
        shell = (STYLES / "public-shell.css").read_text(encoding="utf-8")
        self.assertIn("--color-brand", tokens)
        self.assertIn('[data-theme="dark"]', tokens)
        self.assertIn("--surface-canvas", tokens)
        self.assertIn("box-sizing: border-box", base)
        self.assertIn(":focus-visible", base)
        self.assertIn("prefers-reduced-motion", base)
        self.assertIn(".public-shell", shell)
        self.assertIn(
            ".backoffice-shell",
            (STYLES / "backoffice.css").read_text(encoding="utf-8"),
        )


if __name__ == "__main__":
    unittest.main()
