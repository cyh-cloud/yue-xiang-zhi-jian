# -*- coding: utf-8 -*-
"""Guards the contracted semantic class-name migration."""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPO_ROOT / "frontend" / "src"

RETIRED_PREFIXES = (
    "emp-",
    "craft-",
    "cs-",
    "copy-",
    "msg-",
    "bo-",
    "qa-",
    "fdn-",
    "guide-",
)


class SemanticAliasTest(unittest.TestCase):
    def test_active_styles_have_correct_owners_and_no_em_dash_comments(self):
        crafts = (SOURCE_ROOT / "views" / "crafts" / "crafts.css").read_text(
            encoding="utf-8"
        )
        agriculture = (
            SOURCE_ROOT / "views" / "agriculture" / "agriculture.css"
        ).read_text(encoding="utf-8")
        resources = (SOURCE_ROOT / "views" / "resources" / "resources.css").read_text(
            encoding="utf-8"
        )
        components = (SOURCE_ROOT / "styles" / "components.css").read_text(
            encoding="utf-8"
        )
        base = (SOURCE_ROOT / "styles" / "base.css").read_text(encoding="utf-8")
        backoffice = (SOURCE_ROOT / "styles" / "backoffice.css").read_text(
            encoding="utf-8"
        )

        self.assertIn(".control-group .btn.active", crafts)
        self.assertNotIn(".control-group .btn.active", components)

        self.assertIn(".modal-header h2", components)
        self.assertIn(".modal-header h3", components)

        self.assertIn(".backoffice-topbar", backoffice)
        self.assertIn(".backoffice-sidebar", backoffice)
        self.assertIn("@media print", backoffice)
        print_block = backoffice.split("@media print", 1)[1].split("@media", 1)[0]
        self.assertIn(".backoffice-topbar", print_block)
        self.assertIn(".backoffice-sidebar", print_block)
        self.assertNotIn(".backoffice-button", print_block)
        self.assertNotIn(".backoffice-field", print_block)

        for page_selector in (
            "html[data-large-text] #agriculture-tab .product-card",
            "html[data-large-text] #agriculture-tab .product-icon",
        ):
            with self.subTest(page_selector=page_selector):
                self.assertIn(page_selector, agriculture)
        self.assertNotRegex(
            agriculture,
            r"(?m)^\[data-large-text\]\s+#agriculture-tab\b",
        )
        self.assertNotRegex(
            resources,
            r"(?m)/\*.*[\u2014\u2013].*\*/",
        )
        self.assertIn("@media print", base)

    def test_static_classes_do_not_use_retired_prefixes(self):
        violations = []
        for path in sorted(SOURCE_ROOT.rglob("*.vue")):
            source = path.read_text(encoding="utf-8")
            start = source.find("<template>")
            end = source.rfind("</template>")
            if start < 0 or end <= start:
                continue
            template = source[start + len("<template>"):end]
            for match in re.finditer(r'(?<!:)class="([^"]*)"', template):
                for token in match.group(1).split():
                    if any(char in token for char in "{}$`"):
                        continue
                    if token.startswith(RETIRED_PREFIXES):
                        violations.append(
                            f"{path.relative_to(REPO_ROOT)}: {token}"
                        )
        self.assertEqual(violations, [])

    def test_class_attributes_do_not_repeat_tokens(self):
        violations = []
        for path in sorted(SOURCE_ROOT.rglob("*.vue")):
            source = path.read_text(encoding="utf-8")
            start = source.find("<template>")
            end = source.rfind("</template>")
            if start < 0 or end <= start:
                continue
            template = source[start + len("<template>"):end]
            for match in re.finditer(r'(?<!:)class="([^"]*)"', template):
                tokens = match.group(1).split()
                if len(tokens) != len(set(tokens)):
                    violations.append(str(path.relative_to(REPO_ROOT)))
        self.assertEqual(violations, [])

    def test_ids_and_testids_do_not_use_retired_prefixes(self):
        violations = []
        attribute = re.compile(
            r'(?<![\w:-])(?:id|data-testid|test-id)="([^"]+)"'
        )
        for path in sorted(SOURCE_ROOT.rglob("*.vue")):
            source = path.read_text(encoding="utf-8")
            for match in attribute.finditer(source):
                value = match.group(1)
                if value.startswith(RETIRED_PREFIXES):
                    violations.append(
                        f"{path.relative_to(REPO_ROOT)}: {value}"
                    )
        self.assertEqual(violations, [])

    def test_literal_local_fragment_targets_exist(self):
        violations = []
        id_attribute = re.compile(r'(?<![\w:-])id="([^"]+)"')
        for path in sorted(SOURCE_ROOT.rglob("*.vue")):
            source = path.read_text(encoding="utf-8")
            ids = set(id_attribute.findall(source))
            for match in re.finditer(r'(?<![\w:-])href="#([^"]+)"', source):
                target = match.group(1)
                if target not in ids:
                    violations.append(
                        f"{path.relative_to(REPO_ROOT)}: #{target}"
                    )
        self.assertEqual(violations, [])

    def test_e2e_testids_do_not_use_retired_prefixes(self):
        violations = []
        e2e_root = REPO_ROOT / "frontend" / "e2e"
        for path in sorted(e2e_root.rglob("*.ts")):
            source = path.read_text(encoding="utf-8")
            testids = re.findall(r'getByTestId\("([^"]+)"\)', source)
            testids += re.findall(r'\[data-testid="([^"]+)"\]', source)
            for testid in testids:
                if testid.startswith(RETIRED_PREFIXES):
                    violations.append(
                        f"{path.relative_to(REPO_ROOT)}: {testid}"
                    )
        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()
