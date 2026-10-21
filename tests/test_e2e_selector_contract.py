# -*- coding: utf-8 -*-
"""Reject e2e selectors that bind to retired legacy class prefixes."""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
E2E_ROOT = REPO_ROOT / "frontend" / "e2e"

LEGACY_CLASS_RE = re.compile(
    r"\.(?:emp-|craft-|cs-|copy-|msg-|bo-|qa-|fdn-|guide-)"
)
PRIVATE_LAYOUT_SELECTORS = {
    "agriculture.spec.ts": (".farming-sources",),
    "operator-content.spec.ts": (".task-item",),
    "operator-crafts-dialects.spec.ts": (
        ".step",
        ".purchase-guide-item",
        ".dialect-card",
        ".dialect-greeting",
        ".phrase-item",
        ".voice-quick-btn",
    ),
}


class E2ESelectorContractTest(unittest.TestCase):
    def test_e2e_does_not_bind_to_retired_legacy_prefixes(self):
        violations = []
        for path in sorted(E2E_ROOT.rglob("*.ts")):
            source = path.read_text(encoding="utf-8")
            for match in LEGACY_CLASS_RE.finditer(source):
                line = source.count("\n", 0, match.start()) + 1
                violations.append(f"{path.relative_to(REPO_ROOT)}:{line}")
        self.assertEqual(violations, [])

    def test_e2e_does_not_bind_to_page_layout_class_selectors(self):
        violations = []
        for filename, selectors in PRIVATE_LAYOUT_SELECTORS.items():
            path = E2E_ROOT / filename
            source = path.read_text(encoding="utf-8")
            for selector in selectors:
                pattern = re.compile(
                    r"locator\(\s*[\"']" + re.escape(selector) + r"[\"']"
                )
                for match in pattern.finditer(source):
                    line = source.count("\n", 0, match.start()) + 1
                    violations.append(
                        f"{path.relative_to(REPO_ROOT)}:{line}: {selector}"
                    )
        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()
