# -*- coding: utf-8 -*-
"""tools/check_frontend_styles.py 的自检测试。

用例在临时目录里搭最小前端结构，不依赖真实仓库形态。真实仓库另有一条
空跑用例，保证当前过渡期的旧样式 import 被显式允许，而不是靠忽略目录通过。
"""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools import check_frontend_styles as checker


class CheckFrontendStylesTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def write(self, relative, content):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def check(self):
        return checker.check(self.root)

    def kinds(self, report):
        return [violation.kind for violation in report.violations]

    def reference_css(self, header=True):
        marker = (
            "/* 历史参照，禁止活动代码引用。 */\n"
            if header
            else ""
        )
        return self.write(
            "legacy/reference/frontend/legacy-public.css",
            marker + ".legacy { color: #123456; }\n",
        )

    def test_transitional_legacy_import_from_main_is_allowed(self):
        self.write(
            "frontend/src/main.ts",
            'import "./styles/legacy-public.css";\n'
            'import "./styles/global.css";\n',
        )
        self.write("frontend/src/styles/legacy-public.css", ":root {}\n")
        self.write("frontend/src/styles/global.css", "* { box-sizing: border-box; }\n")

        report = self.check()

        self.assertTrue(report.ok, checker.format_report(report))

    def test_second_import_of_transitional_legacy_sheet_is_rejected(self):
        self.write(
            "frontend/src/main.ts",
            'import "./styles/legacy-public.css";\n',
        )
        self.write(
            "frontend/src/extra.ts",
            'import "./styles/legacy-public.css";\n',
        )
        self.write("frontend/src/styles/legacy-public.css", ":root {}\n")

        report = self.check()

        self.assertEqual(self.kinds(report), [checker.KIND_LEGACY_IMPORT])
        self.assertEqual(report.violations[0].source, "frontend/src/extra.ts")

    def test_active_code_cannot_import_reference_css(self):
        self.reference_css()
        self.write(
            "frontend/src/extra.ts",
            'import "../../legacy/reference/frontend/legacy-public.css";\n',
        )

        report = self.check()

        self.assertEqual(self.kinds(report), [checker.KIND_LEGACY_IMPORT])
        self.assertEqual(
            report.violations[0].target,
            "legacy/reference/frontend/legacy-public.css",
        )

    def test_reference_copy_requires_historical_header(self):
        self.reference_css(header=False)

        report = self.check()

        self.assertEqual(self.kinds(report), [checker.KIND_REFERENCE_HEADER])
        self.assertEqual(
            report.violations[0].source,
            "legacy/reference/frontend/legacy-public.css",
        )

    def test_page_private_style_cannot_cross_page_domains(self):
        self.write(
            "frontend/src/views/ecommerce/Panel.vue",
            '<template><div /></template>\n'
            '<style src="@/views/agriculture/private.css"></style>\n',
        )
        self.write(
            "frontend/src/views/agriculture/private.css",
            ".field { color: var(--text-primary); }\n",
        )

        report = self.check()

        self.assertEqual(self.kinds(report), [checker.KIND_CROSS_PAGE_STYLE])
        self.assertEqual(
            report.violations[0].source,
            "frontend/src/views/ecommerce/Panel.vue",
        )
        self.assertEqual(
            report.violations[0].target,
            "frontend/src/views/agriculture/private.css",
        )

    def test_page_private_style_within_the_same_domain_is_allowed(self):
        self.write(
            "frontend/src/views/ecommerce/Panel.vue",
            '<template><div /></template>\n'
            '<style src="./panel.css"></style>\n',
        )
        self.write(
            "frontend/src/views/ecommerce/panel.css",
            ".field { color: var(--text-primary); }\n",
        )

        report = self.check()

        self.assertTrue(report.ok, checker.format_report(report))

    def test_shared_style_import_is_allowed(self):
        self.write(
            "frontend/src/views/ecommerce/Panel.vue",
            '<template><div /></template>\n'
            '<style src="@/styles/shared.css"></style>\n',
        )
        self.write(
            "frontend/src/styles/shared.css",
            ".shared { color: var(--text-primary); }\n",
        )

        report = self.check()

        self.assertTrue(report.ok, checker.format_report(report))

    def test_css_import_crossing_page_domains_is_rejected(self):
        self.write(
            "frontend/src/views/ecommerce/panel.css",
            '@import "../agriculture/private.css";\n',
        )
        self.write(
            "frontend/src/views/agriculture/private.css",
            ".field { color: var(--text-primary); }\n",
        )

        report = self.check()

        self.assertEqual(self.kinds(report), [checker.KIND_CROSS_PAGE_STYLE])

    def test_universal_override_outside_global_base_is_rejected(self):
        self.write(
            "frontend/src/views/ecommerce/Panel.vue",
            "<template><div /></template>\n"
            "<style>* { margin: 0; }</style>\n",
        )

        report = self.check()

        self.assertEqual(self.kinds(report), [checker.KIND_GLOBAL_OVERRIDE])
        self.assertEqual(
            report.violations[0].source,
            "frontend/src/views/ecommerce/Panel.vue",
        )

    def test_universal_reset_in_global_base_is_allowed(self):
        self.write(
            "frontend/src/styles/global.css",
            "*, *::before, *::after { box-sizing: border-box; }\n",
        )

        report = self.check()

        self.assertTrue(report.ok, checker.format_report(report))

    def test_scoped_universal_rule_in_shell_is_allowed(self):
        self.write(
            "frontend/src/styles/backoffice.css",
            ".bo-shell *, .bo-shell *::before { box-sizing: border-box; }\n",
        )

        report = self.check()

        self.assertTrue(report.ok, checker.format_report(report))

    def test_unscoped_universal_rule_in_shell_is_rejected(self):
        self.write(
            "frontend/src/styles/backoffice.css",
            "* { margin: 0; }\n",
        )

        report = self.check()

        self.assertEqual(self.kinds(report), [checker.KIND_GLOBAL_OVERRIDE])

    def test_raw_role_selector_outside_shell_is_rejected(self):
        self.write(
            "frontend/src/views/ecommerce/Panel.vue",
            "<template><div /></template>\n"
            '<style>[data-role="enterprise"] .card { color: red; }</style>\n',
        )

        report = self.check()

        self.assertEqual(self.kinds(report), [checker.KIND_RAW_ROLE_SELECTOR])
        self.assertIn("data-role", report.violations[0].message)

    def test_role_token_override_in_shell_is_allowed(self):
        self.write(
            "frontend/src/styles/backoffice.css",
            '.bo-shell[data-role="government"] { --bo-accent: #4a6fa5; }\n',
        )

        report = self.check()

        self.assertTrue(report.ok, checker.format_report(report))

    def test_command_line_run_on_real_repo_passes(self):
        import os

        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        result = subprocess.run(
            [sys.executable, str(REPO_ROOT / "tools" / "check_frontend_styles.py")],
            capture_output=True,
            env=env,
        )
        stdout = result.stdout.decode("utf-8", errors="replace")

        self.assertEqual(result.returncode, 0, stdout)
        self.assertIn("CSS 样式检查通过", stdout)


if __name__ == "__main__":
    unittest.main()
