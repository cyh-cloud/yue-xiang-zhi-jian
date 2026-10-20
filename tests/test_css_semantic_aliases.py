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


if __name__ == "__main__":
    unittest.main()
